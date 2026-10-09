"""backup_personal_data.py -- copy-based backup of the 3 AI CLIs' personal/
durable data, sourced from the single `.engram/` live root (item 11,
dotdir consolidation, ratified 2026-09-09 -- see
docs/design/dotdir-consolidation-RATIFIED-2026-09-09.md in the peerhub
repo). Extended 2026-09-19 for first-class engram backup/restore/reset
CLI verbs with zip archives, process-liveness safety invariants, and
pre-restore snapshots.

Context: an earlier, separate legacy environment (P:, frozen, not this
repo) has a same-named script that reads from 3 scattered
`_sys/{claude,codex,antigravity}/config` directories, because that
environment predates the env.json-driven redirect and never adopted it.
This repo already puts every AI CLI's live config under one root --
`.engram/{claude,codex,agy}` (items 5-7, this repo's `_sys/core/
launcher.py` + `_sys/env.json`) -- so this version has exactly one source
tree to filter, not three, and the `ai-config` member of the legacy
version (a bundle of a separate, since-removed orchestration CLI's own
`_sys/ai/` config) is dropped entirely: this repo has no such CLI and no
`_sys/ai/` (see the Engram/PeerHub full-separation goal -- that CLI was
deliberately removed from Engram).

`.engram/` itself is explicitly a LIVE root (ratified doc, item 2.3): it
accumulates real caches and credentials over time, so it is never itself
something you'd hand off, sync, or commit wholesale. This script's job is
to extract just the durable, non-secret, non-cache subset via an explicit
named allowlist -- never a wholesale directory copy with an exclude list,
so a credential file simply never has an entry that would ever pick it up,
rather than needing to be actively filtered out every time -- into a
separate, portable backup bundle (.zip by default).

Usage:
    engram backup [--out PATH] [--include-uncovered]
    engram restore PATH [--force] [--apply]
    engram reset [--yes] [--all] [--apply]

Or standalone script:
    python _sys/checks/backup_personal_data.py --base-dir PATH --backup [--out PATH] [--include-uncovered]
    python _sys/checks/backup_personal_data.py --base-dir PATH --restore PATH [--force] [--apply]
    python _sys/checks/backup_personal_data.py --base-dir PATH --reset [--yes] [--all] [--apply]
    python _sys/checks/backup_personal_data.py --list PATH
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

# Ensure _sys directory is importable when invoked standalone
_SYS_DIR = Path(__file__).resolve().parent.parent
if str(_SYS_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS_DIR))
sys.path.insert(0, str(_SYS_DIR / "core"))
from root import bootstrap_root_package  # noqa: E402

bootstrap_root_package(_SYS_DIR)
from core import cli_help  # noqa: E402

# Filenames that look like vendor credentials. This is a defensive
# assertion on the allowlist itself (see _assert_no_credential_shaped_items)
# and the basis of the behavioral test that a live .engram/ containing
# these names never produces a bundle containing them -- the actual
# safeguard is that ITEMS below is an explicit named allowlist, so a
# credential file simply has no entry that would ever copy it. Centralized
# in _sys/core/state_paths.py, shared with _sys/core/migrate_ais_to_engram.py.
try:
    from _sys.core.state_paths import CREDENTIAL_SHAPED_NAMES  # noqa: E402
except ImportError:
    from state_paths import CREDENTIAL_SHAPED_NAMES  # noqa: E402


@dataclass(frozen=True)
class SyncItem:
    """One named, itemized thing to copy in each direction.

    Both paths are relative -- `live_relpath` to `.engram/`, `bundle_relpath`
    to the bundle root -- so the same table works for both --backup and
    --restore. `kind` is "dir" (shutil.copytree, replacing the destination
    wholesale) or "file" (shutil.copy2). Never a wildcard/glob: every real
    item this script touches is named explicitly.
    """

    label: str
    live_relpath: str
    bundle_relpath: str
    kind: str  # "dir" | "file"


ITEMS: tuple[SyncItem, ...] = (
    SyncItem("claude/projects", "claude/projects", "claude/projects", "dir"),
    SyncItem("claude/CLAUDE.md", "claude/CLAUDE.md", "claude/CLAUDE.md", "file"),
    SyncItem("claude/settings.json", "claude/settings.json", "claude/settings.json", "file"),
    SyncItem("codex/CODEX.md", "codex/CODEX.md", "codex/CODEX.md", "file"),
    SyncItem("codex/config.toml", "codex/config.toml", "codex/config.toml", "file"),
    SyncItem("codex/rules", "codex/rules", "codex/rules", "dir"),
    SyncItem("codex/skills", "codex/skills", "codex/skills", "dir"),
    SyncItem("codex/memories_1.sqlite", "codex/memories_1.sqlite", "codex/memories_1.sqlite", "file"),
    SyncItem("agy/AGY.md", "agy/AGY.md", "agy/AGY.md", "file"),
    SyncItem("agy/settings.json", "agy/settings.json", "agy/settings.json", "file"),
    SyncItem("agy/keybindings.json", "agy/keybindings.json", "agy/keybindings.json", "file"),
    SyncItem("agy/conversation_summaries.db", "agy/conversation_summaries.db", "agy/conversation_summaries.db", "file"),
    SyncItem("agy/knowledge", "agy/knowledge", "agy/knowledge", "dir"),
    SyncItem("agy/skills", "agy/skills", "agy/skills", "dir"),
)

# Items whose live/session data is genuinely irreplaceable if clobbered --
# restoring these requires --force if the live copy already exists.
_RESTORE_PROTECTED_LABELS = frozenset({"claude/projects"})


class CredentialShapedItemError(RuntimeError):
    """Raised if ITEMS itself ever names a credential-shaped file."""


class DiskSpaceError(RuntimeError):
    """Raised when available disk space is insufficient for backup/snapshot."""


SENSITIVE_PATTERNS = [
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r".*token.*", re.IGNORECASE),
    re.compile(r".*secret.*", re.IGNORECASE),
    re.compile(r".*credential.*", re.IGNORECASE),
    re.compile(r".*id_rsa.*", re.IGNORECASE),
    re.compile(r".*\.pem$", re.IGNORECASE),
    re.compile(r".*\.key$", re.IGNORECASE),
]

KNOWN_IGNORE_DIRS = frozenset({
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "venv", ".venv", "env", "_sys",
})


def is_sensitive_path(path: Path) -> bool:
    """Return True if path matches known sensitive/credential patterns."""
    name = path.name
    for pat in SENSITIVE_PATTERNS:
        if pat.search(name):
            return True
    return False


def ensure_long_path_prefix(path: Path | str) -> str:
    """Windows extended-length path prefix (\\\\?\\) support for paths > 260 chars."""
    p_str = str(path)
    if os.name == "nt" and len(p_str) > 260 and not p_str.startswith(("\\\\?\\", "\\\\.\\")):
        abs_path = os.path.abspath(p_str)
        if abs_path.startswith("\\\\"):
            return "\\\\?\\UNC\\" + abs_path[2:]
        return "\\\\?\\" + abs_path
    return p_str


def strip_long_path_prefix(path_str: str) -> str:
    """Strip \\\\?\\ prefix if present."""
    if path_str.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path_str[8:]
    elif path_str.startswith("\\\\?\\"):
        return path_str[4:]
    return path_str


def scan_uncovered_items(base_dir: Path) -> list[Path]:
    """Generic filesystem scanner discovering uncovered user dotdirs, configs, and custom files.

    Safeguards:
    1. Inode/Device pair tracking (st_ino, st_dev) prevents symlink loops and escapes.
    2. Sensitive patterns (.env, *token*, *id_rsa*) are strictly excluded.
    3. KNOWN_IGNORE_DIRS are pruned immediately.
    4. Base items managed by standard backup (.engram, _sys, workspace) are skipped.
    """
    base_dir = Path(base_dir).resolve()
    if not base_dir.exists():
        return []

    visited_inodes: set[tuple[int, int]] = set()
    uncovered: list[Path] = []

    # First record base_dir inode
    try:
        st = base_dir.stat()
        visited_inodes.add((st.st_ino, st.st_dev))
    except OSError:
        pass

    try:
        entries = sorted(list(base_dir.iterdir()), key=lambda p: p.name.lower())
    except OSError:
        return []

    for entry in entries:
        name_lower = entry.name.lower()
        if name_lower in {".engram", "_sys", "workspace", "$recycle.bin", "system volume information"}:
            continue
        if name_lower in KNOWN_IGNORE_DIRS:
            continue
        if is_sensitive_path(entry):
            continue

        # Inode / symlink check
        try:
            # Check for symlink / junction escaping base_dir
            if entry.is_symlink() or (hasattr(entry, "is_junction") and entry.is_junction()):
                target = entry.resolve()
                try:
                    if os.path.commonpath([str(target).lower(), str(base_dir).lower()]) != str(base_dir).lower():
                        continue  # Escapes base_dir
                except ValueError:
                    continue  # Cross-drive symlink
            stat_info = entry.stat()
            inode_pair = (stat_info.st_ino, stat_info.st_dev)
            if inode_pair in visited_inodes:
                continue
            visited_inodes.add(inode_pair)
        except OSError:
            continue

        uncovered.append(entry)

    return uncovered


def _assert_no_credential_shaped_items() -> None:
    """A bad ITEMS edit fails immediately at import time, not only in a
    targeted test -- item 11's "assert no credential-shaped file can ever
    enter it" requirement, checked against the allowlist's own shape."""

    for item in ITEMS:
        name = Path(item.live_relpath).name.lower()
        if name in CREDENTIAL_SHAPED_NAMES:
            raise CredentialShapedItemError(
                f"ITEMS entry {item.label!r} names a credential-shaped "
                f"file ({name!r}) -- refusing to load this module."
            )


_assert_no_credential_shaped_items()


def check_running_processes(sys_dir: Path | None = None) -> list[str]:
    """Check if any of claude.exe, codex.exe, agy.exe are running against this install.

    Reuses provisioner._is_peer_leased for process-liveness inspection.
    When node.exe is detected under sys_dir for codex, reports 'codex (node.exe)'
    to reflect the actual process image while preserving safe refusal semantics.
    """
    if sys_dir is None:
        sys_dir = _SYS_DIR

    try:
        from core import provisioner
    except ImportError:
        return []

    running = []
    for tool, display_name in (("claude", "claude.exe"), ("codex", "codex.exe"), ("ag", "agy.exe")):
        if provisioner._is_peer_leased(sys_dir, tool):
            if tool == "codex":
                # Disambiguate whether codex.exe or node.exe is actually running
                try:
                    import psutil
                except ImportError:
                    running.append(display_name)
                else:
                    psutil_err = getattr(psutil, "Error", None)
                    psutil_exceptions = (
                        (psutil_err, OSError, AttributeError)
                        if isinstance(psutil_err, type) and issubclass(psutil_err, BaseException)
                        else (OSError, AttributeError)
                    )
                    try:
                        root = str(sys_dir.resolve()).lower()
                        found_names = set()
                        for proc in psutil.process_iter(["name", "exe"]):
                            try:
                                pname = (proc.info.get("name") or "").lower()
                                if pname in ("codex.exe", "node.exe"):
                                    pexe = proc.info.get("exe")
                                    if pexe and str(pexe).lower().startswith(root):
                                        found_names.add(pname)
                            except (getattr(psutil, "NoSuchProcess", ()), getattr(psutil, "AccessDenied", ())):
                                continue
                        if "node.exe" in found_names and "codex.exe" not in found_names:
                            running.append("node.exe")
                        elif "codex.exe" in found_names and "node.exe" in found_names:
                            running.append("codex.exe")
                            running.append("node.exe")
                        else:
                            running.append(display_name)
                    except psutil_exceptions:
                        running.append(display_name)
            else:
                running.append(display_name)
    return running


def _source_matches_kind(path: Path, kind: str) -> bool:
    """Only an absent source may be skipped; access errors must abort."""
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise OSError(f"Cannot inspect backup source {path}: {exc}") from exc
    return stat.S_ISDIR(mode) if kind == "dir" else stat.S_ISREG(mode)


def _sync_item_to_bundle(item: SyncItem, engram_dir: Path, bundle_dir: Path) -> int | None:
    """Copy one item .engram/ -> bundle. Returns a file count, or None if
    the live source doesn't exist (not every item is present on every
    install -- e.g. Antigravity may not have run yet)."""

    live = engram_dir / item.live_relpath
    dest = bundle_dir / item.bundle_relpath
    if item.kind == "dir":
        if not _source_matches_kind(live, "dir"):
            return None
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(live, dest)
        return sum(1 for _ in dest.rglob("*") if _.is_file())
    else:
        if not _source_matches_kind(live, "file"):
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(live, dest)
        except OSError as exc:
            raise OSError(f"Cannot back up {live}: {exc}") from exc
        return 1


def _restore_item(item: SyncItem, bundle_dir: Path, engram_dir: Path, force: bool) -> str:
    """Copy one item bundle -> .engram/. Returns a short status string."""

    src = bundle_dir / item.bundle_relpath
    live = engram_dir / item.live_relpath
    if item.kind == "dir":
        if not src.is_dir():
            return "skip (not in bundle)"
        if live.exists():
            if item.label in _RESTORE_PROTECTED_LABELS and not force:
                return f"REFUSED (exists, use --force): {live}"
            shutil.rmtree(live)
        live.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, live)
        count = sum(1 for _ in live.rglob("*") if _.is_file())
        return f"restored ({count} files) -> {live}"
    else:
        if not src.is_file():
            return "skip (not in bundle)"
        live.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, live)
        except OSError as exc:
            raise OSError(f"Cannot restore {live}: {exc}") from exc
        return f"restored -> {live}"


def _restore_from_folder(engram_dir: Path, src_dir: Path, force: bool) -> None:
    for item in ITEMS:
        status = _restore_item(item, src_dir, engram_dir, force)
        tag = "REFUSED" if status.startswith("REFUSED") else ("SKIP" if status.startswith("skip") else "OK")
        print(f"  [{tag:>7}] {item.label:<32} {status}")

    print("\nDone.")


def do_backup(
    engram_dir: Path,
    out_path: Path | None = None,
    *,
    as_zip: bool | None = None,
    base_dir: Path | None = None,
    sys_dir: Path | None = None,
    custom_extras: Sequence[Path] | None = None,
) -> Path:
    if base_dir is None:
        base_dir = engram_dir.parent
    if sys_dir is None:
        sys_dir = (base_dir / _SYS_DIR.name) if base_dir else _SYS_DIR

    # Process liveness warning (does not refuse)
    running = check_running_processes(sys_dir)
    if running:
        print(f"[WARNING] Managed AI process(es) currently running: {', '.join(running)}")
        if any("node.exe" in r for r in running):
            print("  Note: 'node.exe' represents a Node-based AI CLI (e.g. Codex).")
        print("File copies taken during active sessions may produce partial reads.\n")

    # Determine archive vs plain-folder mode
    if as_zip is None:
        if out_path is None:
            as_zip = True
        elif str(out_path).lower().endswith(".zip"):
            as_zip = True
        else:
            as_zip = False

    # Pre-flight Disk Space Check
    # Estimate total size of items to back up
    estimated_bytes = 0
    if engram_dir.exists():
        for root_p, _, files_p in os.walk(engram_dir):
            for f in files_p:
                try:
                    estimated_bytes += (Path(root_p) / f).stat().st_size
                except OSError:
                    pass
    if custom_extras:
        for extra in custom_extras:
            if extra.is_file():
                try:
                    estimated_bytes += extra.stat().st_size
                except OSError:
                    pass
            elif extra.is_dir():
                for root_p, _, files_p in os.walk(extra):
                    for f in files_p:
                        try:
                            estimated_bytes += (Path(root_p) / f).stat().st_size
                        except OSError:
                            pass

    required_bytes = max(int(estimated_bytes * 1.2), 500 * 1024 * 1024)
    target_check_dir = sys_dir if out_path is None else Path(out_path).parent
    try:
        disk_stat = shutil.disk_usage(target_check_dir if target_check_dir.exists() else base_dir)
        if disk_stat.free < required_bytes:
            raise DiskSpaceError(
                f"Insufficient free disk space on target drive: {disk_stat.free // (1024 * 1024)}MB free, "
                f"required at least {required_bytes // (1024 * 1024)}MB (1.2x size buffer or 500MB)."
            )
    except OSError:
        pass

    if as_zip:
        if out_path is None:
            backups_dir = sys_dir / "data" / "backups"
            backups_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_zip = backups_dir / f"engram_backup_{stamp}.zip"
        else:
            is_dir_target = False
            if isinstance(out_path, str) and out_path.endswith(("/", "\\")):
                is_dir_target = True
            out_p = Path(out_path)
            if is_dir_target or out_p.is_dir():
                out_p.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                target_zip = out_p / f"engram_backup_{stamp}.zip"
            elif str(out_p).lower().endswith(".zip"):
                out_p.parent.mkdir(parents=True, exist_ok=True)
                target_zip = out_p
            else:
                target_zip = out_p.parent / (out_p.name + ".zip")
                target_zip.parent.mkdir(parents=True, exist_ok=True)

        print(f"Backing up personal AI-CLI data from {engram_dir} to: {target_zip}\n")

        with tempfile.TemporaryDirectory() as tmp_bundle:
            bundle_path = Path(tmp_bundle)
            manifest_lines: list[str] = []
            for item in ITEMS:
                result = _sync_item_to_bundle(item, engram_dir, bundle_path)
                source = engram_dir / item.live_relpath
                if result is None:
                    print(f"  [SKIP] {item.label:<32} source not found: {source}")
                    manifest_lines.append(f"{item.label}: SKIPPED (source not found)")
                else:
                    print(f"  [OK]   {item.label:<32} <- {source} ({result} file{'s' if result != 1 else ''})")
                    manifest_lines.append(f"{item.label}: {result} file(s) <- {source}")

            extras_meta: list[dict[str, Any]] = []
            if custom_extras:
                extras_bundle_root = bundle_path / "custom_extras"
                for extra in custom_extras:
                    extra_p = Path(extra)
                    if not extra_p.exists():
                        continue
                    try:
                        rel = extra_p.resolve().relative_to(base_dir.resolve())
                    except ValueError:
                        rel = Path(extra_p.name)
                    dest = extras_bundle_root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if extra_p.is_dir():
                        shutil.copytree(extra_p, dest, dirs_exist_ok=True)
                        extras_meta.append({"relpath": str(rel).replace("\\", "/"), "kind": "dir"})
                    else:
                        shutil.copy2(extra_p, dest)
                        extras_meta.append({"relpath": str(rel).replace("\\", "/"), "kind": "file"})
                    manifest_lines.append(f"custom_extra:{rel}: 1 item <- {extra_p}")
                    print(f"  [EXTRA] {str(rel):<31} <- {extra_p}")

            manifest = bundle_path / "MANIFEST.txt"
            manifest.write_text(
                "backup_personal_data.py .engram/ backup bundle\n"
                f"synced_at: {datetime.now(timezone.utc).isoformat()}\n"
                f"source: {engram_dir}\n\n"
                + "\n".join(manifest_lines)
                + "\n\n"
                "Deliberately excluded: auth.json, .credentials.json,\n"
                "credentials.json, token.json, hosts.yml, and any other\n"
                "credential/secret file (excluded by construction -- every item\n"
                "above is an explicit named allowlist entry, never a wholesale\n"
                "directory copy); all 3 tools' caches/logs/queues/crash-dumps/CLI\n"
                "internals.\n",
                encoding="utf-8",
            )

            manifest_json = bundle_path / "MANIFEST.json"
            manifest_json.write_text(
                json.dumps(
                    {
                        "manifest_version": 2,
                        "synced_at": datetime.now(timezone.utc).isoformat(),
                        "source": str(engram_dir),
                        "custom_extras": extras_meta,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            # Atomic creation of the zip archive with long path support
            temp_zip_dest = target_zip.parent / f".tmp_{target_zip.name}"
            long_temp_dest = ensure_long_path_prefix(temp_zip_dest)
            with zipfile.ZipFile(long_temp_dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for root_p, _, files in os.walk(bundle_path):
                    for f in files:
                        fp = Path(root_p) / f
                        arcname = fp.relative_to(bundle_path)
                        zf.write(ensure_long_path_prefix(fp), arcname)

            if target_zip.exists():
                target_zip.unlink()
            Path(strip_long_path_prefix(long_temp_dest)).replace(target_zip)

        print(f"\nDone. Manifest written inside {target_zip}")
        print("\n[NOTE] Same-drive backup created. This protects against accidental local")
        print("resets/config mistakes, NOT drive failure. For disaster recovery, copy")
        print("this backup file off-drive (USB, external drive, cloud storage).")
        return target_zip
    else:
        # Legacy plain-folder backup
        out_dir = Path(out_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"Backing up personal AI-CLI data from {engram_dir} to: {out_dir}\n")

        manifest_lines = []
        for item in ITEMS:
            result = _sync_item_to_bundle(item, engram_dir, out_dir)
            source = engram_dir / item.live_relpath
            if result is None:
                print(f"  [SKIP] {item.label:<32} source not found: {source}")
                manifest_lines.append(f"{item.label}: SKIPPED (source not found)")
            else:
                print(f"  [OK]   {item.label:<32} <- {source} ({result} file{'s' if result != 1 else ''})")
                manifest_lines.append(f"{item.label}: {result} file(s) <- {source}")

        manifest = out_dir / "MANIFEST.txt"
        manifest.write_text(
            "backup_personal_data.py .engram/ backup bundle\n"
            f"synced_at: {datetime.now(timezone.utc).isoformat()}\n"
            f"source: {engram_dir}\n\n"
            + "\n".join(manifest_lines)
            + "\n\n"
            "Deliberately excluded: auth.json, .credentials.json,\n"
            "credentials.json, token.json, hosts.yml, and any other\n"
            "credential/secret file (excluded by construction -- every item\n"
            "above is an explicit named allowlist entry, never a wholesale\n"
            "directory copy); all 3 tools' caches/logs/queues/crash-dumps/CLI\n"
            "internals.\n",
            encoding="utf-8",
        )
        print(f"\nDone. Manifest written to {manifest}")
        return out_dir


def _check_restore_path(root: Path, path: Path, *, recursive: bool = False) -> None:
    """Reject redirects before resolving containment or traversing a tree."""
    root = Path(os.path.abspath(root))
    path = Path(os.path.abspath(path))
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Restore path escapes root: {path}") from exc

    def inspect(candidate: Path) -> bool:
        try:
            info = os.lstat(candidate)
        except FileNotFoundError:
            return False
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Restore path contains a reparse point: {candidate}")
        return stat.S_ISDIR(info.st_mode)

    # Include ancestors of the supplied root: resolving them first would hide
    # a junction or symlink in the root itself or its parent chain.
    for candidate in reversed((path, *path.parents)):
        inspect(candidate)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Restore path escapes resolved root: {path}")
    if recursive and inspect(path):
        pending = [path]
        while pending:
            for child in pending.pop().iterdir():
                if inspect(child):
                    pending.append(child)


def _validated_restore_extras(bundle: Path, base_dir: Path) -> list[tuple[Path, Path, str]]:
    manifest = bundle / "MANIFEST.json"
    _check_restore_path(bundle, manifest)
    if not manifest.is_file():
        return []
    data = json.loads(manifest.read_text(encoding="utf-8"))
    extras = data.get("custom_extras", [])
    if not isinstance(extras, list):
        raise ValueError("custom_extras must be a list")
    result = []
    for extra in extras:
        if not isinstance(extra, dict):
            raise ValueError("Invalid custom_extras entry")
        rel = extra.get("relpath")
        kind = extra.get("kind")
        if (not isinstance(rel, str) or not rel or "\\" in rel or ":" in rel
                or any(part in {"", ".", ".."} or part.rstrip(" .") != part
                       for part in rel.split("/")) or kind not in {"dir", "file"}):
            raise ValueError(f"Noncanonical custom_extras path: {rel!r}")
        src = bundle / "custom_extras" / rel
        dst = base_dir / rel
        _check_restore_path(bundle, src, recursive=True)
        _check_restore_path(base_dir, dst, recursive=True)
        result.append((src, dst, kind))
    return result


def do_restore(
    engram_dir: Path,
    src_path: Path,
    force: bool = False,
    *,
    base_dir: Path | None = None,
    sys_dir: Path | None = None,
    apply: bool = True,
) -> dict[str, Any]:
    src_path = Path(src_path)
    if not src_path.exists():
        raise SystemExit(f"Path does not exist: {src_path}")

    if base_dir is None:
        base_dir = engram_dir.parent
    if sys_dir is None:
        sys_dir = (base_dir / _SYS_DIR.name) if base_dir else _SYS_DIR

    # Dry-Run mode
    if not apply:
        print("[Engram Restore] DRY-RUN MODE (Default: preview only)")
        print(f"Target bundle: {src_path}")
        print(f"Target destination: {engram_dir}")
        print("No files will be modified. Run with '--apply' to execute restore.\n")
        return {"dry_run": True, "source": src_path, "engram_dir": engram_dir}

    # Process liveness check on restore
    running = check_running_processes(sys_dir)
    if running:
        print(f"[Error] Cannot restore: managed AI CLI process(es) currently running: {', '.join(running)}")
        if any("node.exe" in r for r in running):
            print("Note: 'node.exe' represents a Node-based AI CLI (e.g. Codex).")
        print("Please close all running AI CLIs and try again.")
        sys.exit(1)

    def _restore_bundle_dir(temp_bundle: Path) -> None:
        extras = _validated_restore_extras(temp_bundle, base_dir)
        # Validate every extra before snapshots or standard payload writes.
        if not force and engram_dir.is_dir() and any(engram_dir.iterdir()):
            backups_dir = sys_dir / "data" / "backups"
            backups_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snap_path = backups_dir / f"pre_restore_{stamp}.zip"
            print(f"[SNAPSHOT] Creating automatic pre-restore backup at: {snap_path}")
            do_backup(engram_dir, snap_path, as_zip=True, base_dir=base_dir, sys_dir=sys_dir)

        _restore_from_folder(engram_dir, temp_bundle, force)
        for src, dst, kind in extras:
            _check_restore_path(temp_bundle, src, recursive=True)
            _check_restore_path(base_dir, dst, recursive=True)
            if kind == "dir" and src.is_dir():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dst, dirs_exist_ok=True)
                print(f"  [OK]   custom_extra dir  -> {dst}")
            elif kind == "file" and src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  [OK]   custom_extra file -> {dst}")

    if zipfile.is_zipfile(src_path):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_bundle = Path(tmp_dir)
            with zipfile.ZipFile(src_path, "r") as zf:
                zf.extractall(temp_bundle)
            _restore_bundle_dir(temp_bundle)
    elif src_path.is_dir():
        _restore_bundle_dir(src_path)
    else:
        raise SystemExit(f"Not a valid zip file or directory: {src_path}")

    return {"dry_run": False, "source": src_path, "engram_dir": engram_dir}


def do_list(src_path: Path) -> None:
    src_path = Path(src_path)
    if not src_path.exists():
        raise SystemExit(f"Path does not exist: {src_path}")

    if zipfile.is_zipfile(src_path):
        with zipfile.ZipFile(src_path, "r") as zf:
            names = zf.namelist()
            if "MANIFEST.txt" in names:
                print(zf.read("MANIFEST.txt").decode("utf-8"))
            else:
                print(f"(no MANIFEST.txt found in {src_path}, listing top-level contents)")
                top_level = sorted({n.split("/")[0] for n in names if n})
                for item in top_level:
                    print(f"  {item}")
    elif src_path.is_dir():
        manifest = src_path / "MANIFEST.txt"
        if manifest.is_file():
            print(manifest.read_text(encoding="utf-8"))
        else:
            print(f"(no MANIFEST.txt found in {src_path}, listing top-level contents)")
            for item in sorted(src_path.iterdir()):
                print(f"  {item.name}{'/' if item.is_dir() else ''}")
    else:
        raise SystemExit(f"Not a valid zip file or directory: {src_path}")


def do_reset(
    base_dir: Path,
    yes: bool = False,
    all_data: bool = False,
    sys_dir: Path | None = None,
    apply: bool = True,
) -> dict[str, Any]:
    if sys_dir is None:
        sys_dir = (base_dir / _SYS_DIR.name) if base_dir else _SYS_DIR

    engram_dir = base_dir / ".engram"
    workspace_dir = base_dir / "workspace"

    # Scan user dotdirs (like .peerhub, etc.)
    extra_dotdirs: list[Path] = []
    if base_dir.exists():
        for d in scan_uncovered_items(base_dir):
            if d.is_dir() and d.name.startswith("."):
                extra_dotdirs.append(d)

    # Dry-Run mode
    if not apply:
        print("[Engram Reset] DRY-RUN MODE (Default: preview only)")
        print("Below is the execution plan for reset. No files were deleted.")
        print(f"\n[Plan: Pre-reset Safety Snapshot]")
        print(f"  -> Will create snapshot in: {sys_dir / 'data' / 'backups' / 'safety_pre_reset_<timestamp>.zip'}")
        print("\n[Plan: Targets to be purged]")
        if engram_dir.exists():
            print(f"  - [DIR]  {engram_dir}")
        for ed in extra_dotdirs:
            print(f"  - [DIR]  {ed} (discovered dotdir)")
        if all_data and workspace_dir.exists():
            print(f"  - [DIR]  {workspace_dir} (--all scope)")
        print("\nRun with '--apply' to execute this plan.")
        return {
            "dry_run": True,
            "targets": [engram_dir] + extra_dotdirs + ([workspace_dir] if all_data else []),
        }

    # Process liveness check on reset
    running = check_running_processes(sys_dir)
    if running:
        print(f"[Error] Cannot reset: managed AI CLI process(es) currently running: {', '.join(running)}")
        if any("node.exe" in r for r in running):
            print("Note: 'node.exe' represents a Node-based AI CLI (e.g. Codex).")
        print("Please close all running AI CLIs and try again.")
        sys.exit(1)

    # Confirmation 1: Default scope ([y/N], skippable with --yes)
    if not yes:
        try:
            resp = input(f"Reset personal AI state in {engram_dir}? [y/N] ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(3)
        if resp.lower() != "y":
            print("Reset cancelled.")
            sys.exit(3)

    # Confirmation 2: If --all, typed-folder-name gate (un-bypassable even with --yes)
    if all_data:
        try:
            prompt = f"Type the folder name '{base_dir.name}' to also permanently delete .engram/ and workspace/: "
            resp = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(3)
        if resp != base_dir.name:
            print("Folder name does not match. Aborting.")
            sys.exit(3)

    # Phase 1: 2PC Mandatory Safety Snapshot
    backups_dir = sys_dir / "data" / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety_snap = backups_dir / f"safety_pre_reset_{stamp}.zip"

    print(f"[Phase 1: 2PC Safety Snapshot] Creating: {safety_snap}")
    do_backup(
        engram_dir,
        safety_snap,
        as_zip=True,
        base_dir=base_dir,
        sys_dir=sys_dir,
        custom_extras=extra_dotdirs,
    )

    # Verify snapshot archive integrity (fail-closed)
    try:
        with zipfile.ZipFile(safety_snap, "r") as zf:
            corrupt = zf.testzip()
            if corrupt is not None:
                raise RuntimeError(f"Corrupt entry detected: {corrupt}")
    except Exception as e:
        if safety_snap.exists():
            safety_snap.unlink()
        raise RuntimeError(f"Safety snapshot integrity check failed: {e}. Aborting reset to prevent data loss.")

    # Phase 2: Clean Sweep with Rename-then-Purge pattern
    def _safe_purge(target_dir: Path) -> None:
        if not os.path.lexists(target_dir):
            return
        temp_renamed = target_dir.parent / f".purge_{stamp}_{target_dir.name}"
        if os.path.lexists(temp_renamed):
            raise FileExistsError(f"Purge staging target already exists: {temp_renamed}")
        try:
            target_dir.rename(temp_renamed)
        except OSError:
            # Fallback to direct rmtree if rename fails
            shutil.rmtree(target_dir)
        else:
            shutil.rmtree(temp_renamed)
        if os.path.lexists(target_dir) or os.path.lexists(temp_renamed):
            raise OSError(f"Purge postcondition failed: {target_dir} or {temp_renamed} remains")

    if engram_dir.exists():
        _safe_purge(engram_dir)
        print(f"  [OK] Removed personal AI state: {engram_dir}")
    else:
        print(f"  [SKIP] .engram/ does not exist: {engram_dir}")

    for ed in extra_dotdirs:
        if ed.exists():
            _safe_purge(ed)
            print(f"  [OK] Removed discovered dotdir: {ed}")

    if all_data:
        if workspace_dir.exists():
            _safe_purge(workspace_dir)
            print(f"  [OK] Removed workspace projects: {workspace_dir}")
        else:
            print(f"  [SKIP] workspace/ does not exist: {workspace_dir}")

    print("\nReset complete.")
    return {"dry_run": False, "snapshot_path": safety_snap}


# ----------------------------------------------------------------------------
# Dispatcher Pipeline Adapters
# ----------------------------------------------------------------------------



def run_backup(ctx: dict) -> None:
    """Entry point for 'backup' pipeline in dispatch.json."""
    base_dir = ctx["base_dir"]
    sys_dir = ctx.get("sys_dir", (base_dir / _SYS_DIR.name) if base_dir else _SYS_DIR)
    engram_dir = base_dir / ".engram"
    args = ctx.get("args", [])

    if cli_help.wants_help(args):
        cli_help.print_verb_help("backup")
        sys.exit(0)

    out_path = None
    include_uncovered = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--include-uncovered":
            include_uncovered = True
            i += 1
        elif arg == "--out" or arg.startswith("--out="):
            if out_path is not None:
                cli_help.usage_error("backup", "--out specified more than once.")
            if arg == "--out":
                if i + 1 >= len(args):
                    cli_help.usage_error("backup", "--out requires a PATH argument.")
                raw_out = args[i + 1]
                if raw_out.startswith("-"):
                    cli_help.usage_error("backup", "--out requires a PATH argument.")
                i += 2
            else:
                raw_out = arg.split("=", 1)[1]
                if not raw_out or raw_out.startswith("-"):
                    cli_help.usage_error("backup", "--out requires a PATH argument.")
                i += 1
            caller_cwd = os.environ.get("ENGRAM_CALLER_CWD")
            if caller_cwd and not Path(raw_out).is_absolute():
                out_path = Path(caller_cwd) / raw_out
            else:
                out_path = Path(raw_out)
            if raw_out.endswith(("/", "\\")):
                out_path.mkdir(parents=True, exist_ok=True)
        elif arg.startswith("-"):
            cli_help.unknown_option("backup", arg)
        else:
            cli_help.unexpected_argument("backup", arg)

    custom_extras = scan_uncovered_items(base_dir) if include_uncovered else None
    do_backup(engram_dir, out_path, as_zip=True, base_dir=base_dir, sys_dir=sys_dir, custom_extras=custom_extras)


def run_restore(ctx: dict) -> None:
    """Entry point for 'restore' pipeline in dispatch.json."""
    base_dir = ctx["base_dir"]
    sys_dir = ctx.get("sys_dir", (base_dir / _SYS_DIR.name) if base_dir else _SYS_DIR)
    engram_dir = base_dir / ".engram"
    args = ctx.get("args", [])

    if cli_help.wants_help(args):
        cli_help.print_verb_help("restore")
        sys.exit(0)

    force = False
    apply = False

    target_path = None
    dry_run = False
    for a in args:
        if a == "--apply":
            apply = True
        elif a == "--dry-run":
            dry_run = True
        elif a in ("--force", "-f"):
            force = True
        elif a.startswith("-"):
            cli_help.unknown_option("restore", a)
        else:
            if target_path is not None:
                cli_help.unexpected_argument("restore", a)
            caller_cwd = os.environ.get("ENGRAM_CALLER_CWD")
            if caller_cwd and not Path(a).is_absolute():
                target_path = Path(caller_cwd) / a
            else:
                target_path = Path(a)

    if target_path is None:
        cli_help.usage_error("restore", "'engram restore' requires a PATH to a backup .zip or bundle folder.")
    if dry_run:
        apply = False  # --dry-run always wins

    do_restore(engram_dir, target_path, force=force, base_dir=base_dir, sys_dir=sys_dir, apply=apply)


def run_reset(ctx: dict) -> None:
    """Entry point for 'reset' pipeline in dispatch.json."""
    base_dir = ctx["base_dir"]
    sys_dir = ctx.get("sys_dir", (base_dir / _SYS_DIR.name) if base_dir else _SYS_DIR)
    args = ctx.get("args", [])

    if cli_help.wants_help(args):
        cli_help.print_verb_help("reset")
        sys.exit(0)

    yes = False
    all_data = False
    apply = False
    dry_run = False

    for a in args:
        if a == "--apply":
            apply = True
        elif a in ("--yes", "-y"):
            yes = True
        elif a == "--all":
            all_data = True
        elif a == "--dry-run":
            dry_run = True
        elif a.startswith("-"):
            cli_help.unknown_option("reset", a)
        else:
            cli_help.unexpected_argument("reset", a)

    if dry_run:
        apply = False  # --dry-run always wins
    do_reset(base_dir, yes=yes, all_data=all_data, sys_dir=sys_dir, apply=apply)


# ----------------------------------------------------------------------------
# Standalone CLI Main
# ----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--base-dir", help="Portable root (contains .engram/); required with --backup/--restore/--reset")
    parser.add_argument("--sys-dir", help="Runtime sys directory (defaults to _SYS_DIR)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backup", action="store_true", help="Back up .engram/'s durable subset to --out")
    group.add_argument("--restore", metavar="PATH", help="Restore a bundle back into .engram/")
    group.add_argument("--reset", action="store_true", help="Reset personal AI state (.engram/ by default; --all includes workspace/)")
    group.add_argument("--list", metavar="PATH", help="Show what a bundle contains (does not need --base-dir)")
    parser.add_argument("--out", metavar="PATH", help="Target path for --backup (defaults to sys_dir/data/backups/engram_backup_<timestamp>.zip)")
    parser.add_argument("--apply", action="store_true", help="Actually execute restore or reset (default: dry-run preview)")
    parser.add_argument("--include-uncovered", action="store_true", help="With --backup, package discovered extra dotdirs/files")
    parser.add_argument("--force", action="store_true", help="With --restore, overwrite existing live session/project data")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip [y/N] confirmation for --reset")
    parser.add_argument("--all", action="store_true", dest="all_data", help="With --reset, also delete workspace/")
    args = parser.parse_args(argv)

    if args.list:
        do_list(Path(args.list).resolve())
        return 0

    if not args.base_dir:
        parser.error("--backup/--restore/--reset require --base-dir PATH")
    base_dir = Path(args.base_dir).resolve()
    engram_dir = base_dir / ".engram"
    sys_dir = Path(args.sys_dir).resolve() if getattr(args, "sys_dir", None) else (base_dir / _SYS_DIR.name)

    if args.backup:
        out_target = Path(args.out).resolve() if args.out else None
        custom_extras = scan_uncovered_items(base_dir) if args.include_uncovered else None
        do_backup(engram_dir, out_target, base_dir=base_dir, sys_dir=sys_dir, custom_extras=custom_extras)
    elif args.restore:
        do_restore(engram_dir, Path(args.restore).resolve(), force=args.force, base_dir=base_dir, sys_dir=sys_dir, apply=args.apply)
    elif args.reset:
        do_reset(base_dir, yes=args.yes, all_data=args.all_data, sys_dir=sys_dir, apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
