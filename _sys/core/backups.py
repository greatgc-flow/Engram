"""backups.py - the environment backup registry (design P2).

Design: docs/design/engram-env-resilience-design-2026-10-02.md, section 8.

Layout: ``_sys/data/backups/env/<kind>/<UTC-timestamp>-<label>/`` containing
``BACKUP.json`` (the ownership marker) and ``payload/`` (the preserved tree).
Ownership is marker-based: tidy may only ever delete marker-bearing directories under
this root, never anything matched by a name pattern alone.

Write-ahead rule: the marker (state ``pending``) is written BEFORE the payload moves, so a
crash can only leave a marked-pending dir or nothing - never an unmanaged duplicate.
Pending backups are never deleted; ones whose operation is gone are marked ``orphaned``
after a grace period and become deletable only after their own ttl.
"""
from __future__ import annotations

import datetime
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from core import cli_help
from core.env_manifest import _atomic_write_text

MARKER = "BACKUP.json"
PAYLOAD = "payload"
SCHEMA_VERSION = 1

# kind -> (min_keep, ttl_days). min_keep is an absolute floor (it overrides the size cap).
KIND_POLICY: dict[str, tuple[int, int]] = {
    "python": (1, 14),
    "venv": (1, 7),
    "venv-interp": (2, 14),
    "venv-freeze": (5, 180),
    "state": (3, 60),
    "registry-export": (3, 60),
    "ai-state": (3, 30),
    "core-update": (1, 14),
    "legacy-old": (0, 14),
}

ORPHAN_GRACE_HOURS = 24
LATEST_PROTECTION_HOURS = 72
DEFAULT_SIZE_CAP_BYTES = 2 * 2**30
_LABEL_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_RENAME_ATTEMPTS = 5
_RENAME_BACKOFF_S = 0.1
_ERROR_NOT_SAME_DEVICE = 17  # winerror for a cross-volume rename
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

Rename = Callable[[str, str], None]


class BackupVerificationError(RuntimeError):
    """A cross-volume copy did not match its source; the source was left untouched."""


@dataclass
class BackupRef:
    kind: str
    path: Path
    meta: dict = field(default_factory=dict)


@dataclass
class ScanResult:
    valid: list[BackupRef] = field(default_factory=list)
    invalid: list[Path] = field(default_factory=list)    # marker present but unreadable/incomplete
    unmarked: list[Path] = field(default_factory=list)   # no marker -> not ours, never touched


@dataclass
class RetentionPlan:
    delete: list[tuple[BackupRef, str]] = field(default_factory=list)
    orphan_marks: list[BackupRef] = field(default_factory=list)
    keep: list[tuple[BackupRef, str]] = field(default_factory=list)


# ---- time helpers ---------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts: str) -> datetime.datetime:
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def _compact(ts: str) -> str:
    return ts.replace("-", "").replace(":", "")


def _age(now: str, then: str) -> datetime.timedelta:
    return _parse(now) - _parse(then)


# ---- paths / safety -----------------------------------------------------------------------

def backups_root(sys_dir: Path) -> Path:
    return Path(sys_dir) / "data" / "backups" / "env"


def _is_reparse_point(path: Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)


def _under(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False


def _dir_size(path: Path) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        # never descend into junctions/symlinks (cross-review ag.deepthink: recursion/inflation)
        dirnames[:] = [d for d in dirnames if not _is_reparse_point(Path(dirpath) / d)]
        for name in filenames:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                pass
    return total


def _tree_fingerprint(path: Path) -> dict[str, tuple[int, str]]:
    """relative posix path -> (size, sha256) for every regular file."""
    out: dict[str, tuple[int, str]] = {}
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if not _is_reparse_point(Path(dirpath) / d)]
        for name in filenames:
            full = Path(dirpath) / name
            h = hashlib.sha256()
            with open(full, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            out[full.relative_to(path).as_posix()] = (full.stat().st_size, h.hexdigest())
    return out


def _rmtree(path: Path) -> None:
    def _on_error(func, p, exc_info):
        os.chmod(p, stat.S_IWRITE)  # read-only files (git objects, ...)
        func(p)

    shutil.rmtree(path, onerror=_on_error)


def _move_dir(src: Path, dst: Path, *, rename: Rename, sleep: Callable[[float], None]) -> None:
    """Rename with bounded retry; cross-volume falls back to verified copy -> delete source.

    The source is only deleted after the copy verified (file list + sizes + sha256).
    """
    for attempt in range(_RENAME_ATTEMPTS):
        try:
            rename(str(src), str(dst))
            return
        except OSError as exc:
            if exc.errno == errno.EXDEV or getattr(exc, "winerror", None) == _ERROR_NOT_SAME_DEVICE:
                break
            if attempt == _RENAME_ATTEMPTS - 1:
                raise
            sleep(_RENAME_BACKOFF_S * (2 ** attempt))
    # cross-volume fallback
    before = _tree_fingerprint(src)
    shutil.copytree(src, dst, symlinks=True)
    if _tree_fingerprint(dst) != before:
        _rmtree(dst)
        raise BackupVerificationError(f"copy of {src} did not verify; source left in place")
    _rmtree(src)


# ---- marker I/O ---------------------------------------------------------------------------------

_REQUIRED_META = ("schema_version", "kind", "state", "created_at")


def _write_meta(dest: Path, meta: dict, *, replace=os.replace, sleep=time.sleep) -> None:
    _atomic_write_text(dest / MARKER, json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                       replace=replace, sleep=sleep)


def _read_meta(dest: Path) -> Optional[dict]:
    try:
        meta = json.loads((dest / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict) or any(k not in meta for k in _REQUIRED_META):
        return None
    if meta["kind"] not in KIND_POLICY:
        return None
    for key in ("created_at", "committed_at", "orphaned_at"):
        if meta.get(key) is not None:
            try:
                _parse(meta[key])
            except (ValueError, TypeError):
                return None  # unreadable timestamps would crash retention planning; treat as invalid
    return meta


# ---- public API ------------------------------------------------------------------------------------

def create(
    sys_dir: Path,
    kind: str,
    source: Path,
    *,
    reason: str,
    op_id: str,
    label: str,
    now: Optional[str] = None,
    engram_version: Optional[str] = None,
    rename: Rename = os.rename,
    sleep: Callable[[float], None] = time.sleep,
    dest: Optional[Path] = None,
) -> BackupRef:
    """Preserve ``source`` (a directory) in the registry. State starts as ``pending``.

    ``dest`` lets an engine use a path it allocated and journaled BEFORE the operation (write-ahead,
    design 9): it must be a direct child of ``<root>/<kind>/``. A marker left by a crashed attempt is
    reused; a destination that already holds a payload is refused.
    """
    if kind not in KIND_POLICY:
        raise ValueError(f"unknown backup kind {kind!r}")
    if not _LABEL_RE.match(label or "") or ".." in label:
        raise ValueError(f"invalid backup label {label!r}")
    source = Path(source)
    if not source.is_dir():
        raise FileNotFoundError(f"backup source is not a directory: {source}")
    if _is_reparse_point(source):
        raise ValueError(f"refusing to back up a reparse point: {source}")
    now = now or _utc_now()
    min_keep, ttl_days = KIND_POLICY[kind]

    root = backups_root(sys_dir)
    if dest is not None:
        dest = Path(dest)
        kind_dir = (root / kind).resolve()
        if dest.resolve().parent != kind_dir:
            raise ValueError(f"backup destination must be a direct child of {kind_dir}: {dest}")
        if (dest / PAYLOAD).exists():
            raise FileExistsError(f"backup destination already holds a payload: {dest}")
        dest.mkdir(parents=True, exist_ok=True)
    else:
        dest = root / kind / f"{_compact(now)}-{label}"
        n = 1
        while dest.exists():
            n += 1
            dest = root / kind / f"{_compact(now)}-{label}-{n}"
        dest.mkdir(parents=True)

    meta = {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "state": "pending",
        "created_at": now,
        "engram_version": engram_version,
        "op_id": op_id,
        "source_path": str(source),
        "reason": reason,
        "size_bytes": _dir_size(source),
        "ttl_days": ttl_days,
        "min_keep": min_keep,
        "pinned": False,
        "restore_hint": f"engram snapshots restore {dest.name}",
    }
    _write_meta(dest, meta)                       # write-ahead: marker first
    _move_dir(source, dest / PAYLOAD, rename=rename, sleep=sleep)
    return BackupRef(kind, dest, meta)


def create_text(
    sys_dir: Path,
    kind: str,
    filename: str,
    text: str,
    *,
    reason: str,
    op_id: str,
    label: str,
    now: Optional[str] = None,
    engram_version: Optional[str] = None,
    replace=os.replace,
    sleep: Callable[[float], None] = time.sleep,
) -> BackupRef:
    """Record a small text artifact (e.g. a venv package snapshot) as an already-committed backup.

    Nothing is moved, so there is no pending window: marker and payload are written, then
    the marker is committed. ``source_path`` is None (not restorable as a directory).
    """
    if kind not in KIND_POLICY:
        raise ValueError(f"unknown backup kind {kind!r}")
    if not _LABEL_RE.match(label or "") or ".." in label:
        raise ValueError(f"invalid backup label {label!r}")
    if not _LABEL_RE.match(filename or "") or ".." in filename:
        raise ValueError(f"invalid payload filename {filename!r}")
    now = now or _utc_now()
    min_keep, ttl_days = KIND_POLICY[kind]
    root = backups_root(sys_dir)
    dest = root / kind / f"{_compact(now)}-{label}"
    n = 1
    while dest.exists():
        n += 1
        dest = root / kind / f"{_compact(now)}-{label}-{n}"
    (dest / PAYLOAD).mkdir(parents=True)
    meta = {
        "schema_version": SCHEMA_VERSION, "kind": kind, "state": "pending", "created_at": now,
        "engram_version": engram_version, "op_id": op_id, "source_path": None, "reason": reason,
        "size_bytes": len(text.encode("utf-8")), "ttl_days": ttl_days, "min_keep": min_keep,
        "pinned": False, "restore_hint": None,
    }
    _write_meta(dest, meta, replace=replace, sleep=sleep)
    _atomic_write_text(dest / PAYLOAD / filename, text, replace=replace, sleep=sleep)
    ref = BackupRef(kind, dest, meta)
    meta.update(state="committed", committed_at=now)
    _write_meta(dest, meta, replace=replace, sleep=sleep)
    return ref


def create_file(
    sys_dir: Path,
    kind: str,
    source: Path,
    *,
    reason: str,
    op_id: str,
    label: str,
    copy: bool = False,
    now: Optional[str] = None,
    engram_version: Optional[str] = None,
) -> BackupRef:
    """Preserve one regular file (``Engram.exe.old``, ``*.pre-merge.bak``) as a committed backup.

    ``copy=False`` moves the file into ``payload/<name>`` (never deletes it); ``copy=True`` keeps the
    original in place (for a live file about to be rewritten). Marker first (write-ahead), then the
    file lands, then the marker commits; a failure leaves the original untouched.
    """
    if kind not in KIND_POLICY:
        raise ValueError(f"unknown backup kind {kind!r}")
    if not _LABEL_RE.match(label or "") or ".." in label:
        raise ValueError(f"invalid backup label {label!r}")
    source = Path(source)
    if not source.is_file() or _is_reparse_point(source):
        raise FileNotFoundError(f"backup source is not a regular file: {source}")
    now = now or _utc_now()
    min_keep, ttl_days = KIND_POLICY[kind]
    root = backups_root(sys_dir)
    dest = root / kind / f"{_compact(now)}-{label}"
    n = 1
    while dest.exists():
        n += 1
        dest = root / kind / f"{_compact(now)}-{label}-{n}"
    (dest / PAYLOAD).mkdir(parents=True)
    meta = {
        "schema_version": SCHEMA_VERSION, "kind": kind, "state": "pending", "created_at": now,
        "engram_version": engram_version, "op_id": op_id, "source_path": None, "reason": reason,
        "size_bytes": source.stat().st_size, "ttl_days": ttl_days, "min_keep": min_keep,
        "pinned": False, "restore_hint": None,
    }
    _write_meta(dest, meta)
    target = dest / PAYLOAD / source.name
    if copy:
        shutil.copy2(source, target)
    else:
        try:
            os.replace(source, target)
        except OSError:
            shutil.copy2(source, target)
            if target.stat().st_size != source.stat().st_size:
                target.unlink()
                raise BackupVerificationError(f"copy of {source} did not verify; source left in place")
            source.unlink()
    ref = BackupRef(kind, dest, meta)
    return commit(ref, now=now)


def _update(ref: BackupRef, **changes) -> BackupRef:
    meta = _read_meta(ref.path) or dict(ref.meta)
    meta.update(changes)
    _write_meta(ref.path, meta)
    ref.meta = meta
    return ref


def commit(ref: BackupRef, *, now: Optional[str] = None) -> BackupRef:
    """Mark the backup committed (the operation that produced it verified). Idempotent."""
    current = _read_meta(ref.path) or ref.meta
    if current.get("state") == "committed" and current.get("committed_at"):
        ref.meta = current
        return ref
    return _update(ref, state="committed", committed_at=now or _utc_now())


def mark_orphaned(ref: BackupRef, *, now: Optional[str] = None) -> BackupRef:
    return _update(ref, state="orphaned", orphaned_at=now or _utc_now())


def pin(ref: BackupRef) -> BackupRef:
    return _update(ref, pinned=True)


def unpin(ref: BackupRef) -> BackupRef:
    return _update(ref, pinned=False)


def scan(sys_dir: Path) -> ScanResult:
    root = backups_root(sys_dir)
    result = ScanResult()
    if not root.is_dir():
        return result
    for kind in sorted(KIND_POLICY):
        kind_dir = root / kind
        if not kind_dir.is_dir() or _is_reparse_point(kind_dir):
            continue
        for child in sorted(kind_dir.iterdir()):
            if not child.is_dir():
                continue
            if not (child / MARKER).exists():
                result.unmarked.append(child)
                continue
            meta = _read_meta(child)
            if meta is None or meta["kind"] != kind:
                result.invalid.append(child)
                continue
            result.valid.append(BackupRef(kind, child, meta))
    return result


def restore(ref: BackupRef, *, rename: Rename = os.rename, sleep: Callable[[float], None] = time.sleep) -> Path:
    """Move the payload back to where it came from. Refuses to overwrite anything."""
    if not ref.meta.get("source_path"):
        raise ValueError(f"backup {ref.path.name} holds a file snapshot, not a restorable directory")
    target = Path(ref.meta["source_path"])
    payload = ref.path / PAYLOAD
    if target.exists():
        raise FileExistsError(f"restore target already exists: {target}")
    if not payload.is_dir():
        raise FileNotFoundError(f"backup has no payload: {ref.path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    _move_dir(payload, target, rename=rename, sleep=sleep)
    _update(ref, state="restored", restored_at=_utc_now())
    return target


def default_size_cap(*, free_bytes: Optional[int]) -> int:
    """min(2 GiB, 10% of free space) - scales down on constrained disks."""
    if free_bytes is None:
        return DEFAULT_SIZE_CAP_BYTES
    return min(DEFAULT_SIZE_CAP_BYTES, free_bytes // 10)


# ---- retention ------------------------------------------------------------------------------------------

def _clock(meta: dict) -> str:
    """The instant the ttl clock started: commit time (committed) or orphaning time (orphaned)."""
    if meta.get("state") == "orphaned":
        return meta.get("orphaned_at") or meta["created_at"]
    return meta.get("committed_at") or meta["created_at"]


def plan_retention(
    refs: Iterable[BackupRef],
    *,
    now: str,
    active_op_ids: Iterable[str] = (),
    size_cap_bytes: Optional[int] = None,
    keep_override: Optional[int] = None,
    root: Optional[Path] = None,
    protect: Iterable[Path] = (),
) -> RetentionPlan:
    """Pure planning: decide what may be deleted. Touches nothing.

    Rules (design 8.3): only marker-bearing refs under ``root``; never pending/pinned/reparse;
    ttl runs from commit (or orphaning); ``min_keep`` is an absolute floor that also beats the
    size cap; the newest commit of a kind survives the cap for 72 h; ``keep_override`` can only
    raise the floor.
    """
    plan = RetentionPlan()
    active = set(active_op_ids)
    candidates: list[BackupRef] = []
    sized: list[BackupRef] = []

    protected_paths = {Path(p) for p in protect}
    for ref in refs:
        if Path(ref.path) in protected_paths:
            plan.keep.append((ref, "adopted in this run"))
            continue
        try:
            for key in ("created_at", "committed_at", "orphaned_at"):
                if ref.meta.get(key) is not None:
                    _parse(ref.meta[key])
        except (ValueError, TypeError):
            plan.keep.append((ref, "unparsable timestamp"))
            continue
        if root is not None and not _under(ref.path, root):
            plan.keep.append((ref, "outside registry root"))
            continue
        if _is_reparse_point(ref.path):
            plan.keep.append((ref, "reparse point"))
            continue
        sized.append(ref)
        state = ref.meta.get("state")
        if state == "pending":
            created_age = _age(now, ref.meta["created_at"])
            if (created_age > datetime.timedelta(hours=ORPHAN_GRACE_HOURS)
                    and ref.meta.get("op_id") not in active and not ref.meta.get("pinned")):
                plan.orphan_marks.append(ref)
            plan.keep.append((ref, "pending"))
            continue
        if ref.meta.get("pinned"):
            plan.keep.append((ref, "pinned"))
            continue
        if state == "restored":
            plan.delete.append((ref, "restored"))   # its payload is gone; only the empty marker dir remains
            continue
        if state in ("committed", "orphaned"):
            candidates.append(ref)
        else:
            plan.keep.append((ref, f"state {state!r}"))

    deleted: set[Path] = {r.path for r, _ in plan.delete}
    protected_floor: set[Path] = set()
    protected_latest: set[Path] = set()

    by_kind: dict[str, list[BackupRef]] = {}
    for ref in candidates:
        by_kind.setdefault(ref.kind, []).append(ref)

    for kind, items in by_kind.items():
        policy_floor, ttl_days = KIND_POLICY[kind]
        floor = max(policy_floor, keep_override or 0)
        committed = sorted((r for r in items if r.meta["state"] == "committed"),
                           key=lambda r: _clock(r.meta), reverse=True)
        for r in committed[:floor]:
            protected_floor.add(r.path)
        if committed and _age(now, _clock(committed[0].meta)) < datetime.timedelta(hours=LATEST_PROTECTION_HOURS):
            protected_latest.add(committed[0].path)
        for r in items:
            if r.path in protected_floor:
                plan.keep.append((r, "min_keep floor"))
                continue
            if _age(now, _clock(r.meta)) > datetime.timedelta(days=ttl_days):
                plan.delete.append((r, "ttl"))
                deleted.add(r.path)

    if size_cap_bytes is not None:
        total = sum(int(r.meta.get("size_bytes") or 0) for r in sized if r.path not in deleted)
        evictable = sorted(
            (r for r in candidates
             if r.path not in deleted and r.path not in protected_floor and r.path not in protected_latest),
            key=lambda r: _clock(r.meta),
        )
        for r in evictable:
            if total <= size_cap_bytes:
                break
            plan.delete.append((r, "size_cap"))
            deleted.add(r.path)
            total -= int(r.meta.get("size_bytes") or 0)

    return plan


def apply_orphan_marks(plan: RetentionPlan, *, now: str) -> None:
    for ref in plan.orphan_marks:
        mark_orphaned(ref, now=now)


# ---- legacy `<name>_old` adoption ------------------------------------------------------------------------------

# component -> any-of relative paths that prove the directory really is that component's old copy
_LEGACY_SIGNATURES: dict[str, tuple[str, ...]] = {
    "git": ("cmd/git.exe", "bin/git.exe"),
    "vscode": ("Code.exe",),
    "nodejs": ("node.exe",),
    "pwsh": ("pwsh.exe",),
    "python": ("python.exe",),
}


def _looks_like_component(directory: Path, component: str) -> bool:
    signature = _LEGACY_SIGNATURES.get(component)
    if signature:
        return any((directory / rel).is_file() for rel in signature)
    # unknown tool: require at least one executable within two levels
    for depth_glob in ("*.exe", "*/*.exe"):
        if any(p.is_file() for p in directory.glob(depth_glob)):
            return True
    return False


def find_legacy_candidates(sys_dir: Path) -> list[Path]:
    """``env/<name>_old`` dirs that pass structural verification (name match alone is not enough)."""
    env = Path(sys_dir) / "env"
    if not env.is_dir():
        return []
    found = []
    for child in sorted(env.iterdir()):
        if child.is_dir() and child.name.endswith("_old") and not _is_reparse_point(child):
            if _looks_like_component(child, child.name[: -len("_old")]):
                found.append(child)
    return found


def adopt_legacy(
    sys_dir: Path,
    *,
    now: Optional[str] = None,
    confirm: Callable[[Path], bool] = lambda c: True,
    rename: Rename = os.rename,
    sleep: Callable[[float], None] = time.sleep,
) -> list[BackupRef]:
    """Move confirmed, structurally valid ``*_old`` dirs into the registry as ``legacy-old``."""
    now = now or _utc_now()
    adopted = []
    for candidate in find_legacy_candidates(sys_dir):
        if not confirm(candidate):
            continue
        ref = create(sys_dir, "legacy-old", candidate, reason="adopted legacy *_old directory",
                     op_id="adopt-legacy", label=candidate.name, now=now, rename=rename, sleep=sleep)
        commit(ref, now=now)
        adopted.append(ref)
    return adopted


def plan_legacy_purge(refs: Iterable[BackupRef], *, root: Optional[Path] = None) -> RetentionPlan:
    """Pure planning for ``engram tidy --purge-legacy``: every ``legacy-old`` backup is deletable at once
    (no ttl, min_keep 0) EXCEPT pinned, pending, reparse-point, out-of-root or unparsable-marker entries.
    Other kinds are never considered."""
    plan = RetentionPlan()
    for ref in refs:
        if ref.kind != "legacy-old":
            continue
        try:
            for key in ("created_at", "committed_at", "orphaned_at"):
                if ref.meta.get(key) is not None:
                    _parse(ref.meta[key])
        except (ValueError, TypeError):
            plan.keep.append((ref, "unparsable timestamp"))
            continue
        if root is not None and not _under(ref.path, root):
            plan.keep.append((ref, "outside registry root"))
        elif _is_reparse_point(ref.path):
            plan.keep.append((ref, "reparse point"))
        elif ref.meta.get("pinned"):
            plan.keep.append((ref, "pinned"))
        elif ref.meta.get("state") == "pending":
            plan.keep.append((ref, "pending"))
        else:
            plan.delete.append((ref, "purge-legacy"))
    return plan


# ---- `engram snapshots` front-end ----------------------------------------------------------------------------------

# Options each action accepts (anything else is a usage error, exit 2). --dry-run is a no-op alias of the default.
_ACTION_FLAGS = {
    "list": {"--json"},
    "show": set(),
    "pin": set(),
    "unpin": set(),
    "restore": {"--apply", "--dry-run"},
}

# Kinds whose restore must go through the lock + journal repair engine (design section 9).
_ENGINE_ONLY_KINDS = frozenset({"python", "venv", "venv-interp"})


def _resolve(sys_dir: Path, token: str) -> tuple[Optional[BackupRef], str]:
    refs = scan(sys_dir).valid
    if "/" in token:
        kind, _, name = token.partition("/")
        matches = [r for r in refs if r.kind == kind and r.path.name == name]
    else:
        matches = [r for r in refs if r.path.name == token]
    if not matches:
        return None, f"no backup named {token!r}"
    if len(matches) > 1:
        kinds = ", ".join(sorted(r.kind for r in matches))
        return None, f"{token!r} is ambiguous ({kinds}); use <kind>/<name>"
    return matches[0], ""


def _fail(detail: str, exit_code: int = 11) -> dict:
    """A failure that was already printed: the CLI exits with ``exit_code`` and no traceback."""
    print(f"[Error] {detail}")
    return {"status": "failed", "operation": "backups.snapshots", "detail": detail,
            "exit_code": exit_code, "quiet": True}


def _ok(**extra) -> dict:
    return {"status": "success", "operation": "backups.snapshots", **extra}


def _fmt_size(n: int) -> str:
    return f"{n / 1048576:.1f} MiB" if n >= 1048576 else f"{n / 1024:.1f} KiB"


def snapshots_main(ctx: dict) -> dict:
    from core import env_lock  # local import keeps the registry importable on its own in tests

    sys_dir = Path(ctx["sys_dir"])
    args = list(ctx.get("args") or [])
    if not args or cli_help.wants_help(args):
        cli_help.print_verb_help("snapshots")
        return _ok()
    action, rest = args[0].lower(), args[1:]
    if action in _ACTION_FLAGS:
        for flag in (a for a in rest if a.startswith("-")):
            if flag not in _ACTION_FLAGS[action]:
                try:
                    cli_help.unknown_option("snapshots", flag)
                except SystemExit:  # the message is already printed
                    return {"status": "failed", "operation": "backups.snapshots", "detail": "usage",
                            "exit_code": 2, "quiet": True}

    if action == "list":
        found = scan(sys_dir)
        rows = [{
            "kind": r.kind, "name": r.path.name, "state": r.meta["state"], "pinned": bool(r.meta.get("pinned")),
            "size_bytes": int(r.meta.get("size_bytes") or 0), "created_at": r.meta["created_at"],
            "committed_at": r.meta.get("committed_at"), "op_id": r.meta.get("op_id"),
            "source_path": r.meta.get("source_path"),
        } for r in found.valid]
        if "--json" in rest:
            print(json.dumps(rows, indent=2))
            return _ok()
        if not rows and not found.invalid and not found.unmarked:
            print("no backups registered")
            return _ok()
        for row in rows:
            flag = " pinned" if row["pinned"] else ""
            print(f"{row['kind']:<16} {row['name']:<44} {row['state']:<10} {_fmt_size(row['size_bytes']):>10}{flag}")
        if found.unmarked:
            print(f"({len(found.unmarked)} unmarked dir(s) ignored - not owned by the registry)")
        if found.invalid:
            print(f"({len(found.invalid)} backup dir(s) with an invalid marker - left untouched)")
        return _ok()

    if action in ("show", "pin", "unpin", "restore"):
        names = [a for a in rest if not a.startswith("--")]
        if len(names) != 1:
            return _fail(f"'{action}' needs exactly one backup name (see: engram snapshots list)", 2)
        ref, problem = _resolve(sys_dir, names[0])
        if ref is None:
            return _fail(problem)
        if action == "show":
            print(json.dumps(ref.meta, indent=2, ensure_ascii=False))
            return _ok()
        if action in ("pin", "unpin"):
            (pin if action == "pin" else unpin)(ref)
            print(f"[OK] {ref.kind}/{ref.path.name} {'pinned' if action == 'pin' else 'unpinned'}")
            return _ok()
        # restore
        if ref.kind in _ENGINE_ONLY_KINDS:
            return _fail(f"{ref.kind} backups are restored through 'engram repair' (lock + journal); "
                         f"that engine is not available yet, so 'snapshots restore' refuses to guess")
        if not ref.meta.get("source_path"):
            return _fail(f"{ref.kind}/{ref.path.name} is a file snapshot, not a restorable directory")
        target = Path(ref.meta["source_path"])
        if "--apply" not in rest or "--dry-run" in rest:
            print(f"[dry-run] would move the payload of {ref.kind}/{ref.path.name} back to {target}")
            print("          re-run with --apply to restore")
            return _ok()
        try:
            with env_lock.guard(sys_dir, f"snapshots-restore-{ref.path.name}"):
                restored = restore(ref)
        except env_lock.EnvLockBusy as exc:
            return _fail(f"environment lock is busy: {exc}")
        except (FileExistsError, FileNotFoundError, ValueError, OSError) as exc:
            return _fail(str(exc))
        print(f"[OK] restored to {restored}")
        return _ok()

    if action.startswith("-"):
        cli_help.report_unknown("snapshots", "option", action, ())
    else:
        cli_help.report_unknown("snapshots", "action", action, _ACTION_FLAGS)
    return {"status": "failed", "operation": "backups.snapshots", "detail": "usage", "exit_code": 2, "quiet": True}
