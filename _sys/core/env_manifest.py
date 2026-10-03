"""env_manifest.py - the environment manifest and root-drift detection.

Design: docs/design/engram-env-resilience-design-2026-10-02.md, sections 3 and 5.

The manifest (``_sys/data/state/env.manifest.json``) records what Engram *applied*:
install identity, root, managed Python version and the venv's interpreter version.
Everything else is observed from disk and compared against it.

Single-writer rule: only a fresh install (``commit_install``) and, in later phases,
``repair``/``update`` write it. ``doctor`` and the launcher only read. Adoption of an
existing install from evidence is a *pure proposal* here (``propose_adoption``).
"""
from __future__ import annotations

import datetime
import json
import ntpath
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

MANIFEST_FILENAME = "env.manifest.json"
SCHEMA_VERSION = 1
LAST_BASE_DIR_FILENAME = "last_base_dir.txt"
_REQUIRED_KEYS = ("schema_version", "install_id", "root")
_REPLACE_ATTEMPTS = 5
_REPLACE_BACKOFF_S = 0.1


def manifest_path(sys_dir: Path) -> Path:
    return Path(sys_dir) / "data" / "state" / MANIFEST_FILENAME


@dataclass
class ManifestRead:
    status: str  # absent | ok | corrupt | unsupported
    data: Optional[dict] = None
    detail: str = ""


def read_manifest(sys_dir: Path) -> ManifestRead:
    path = manifest_path(sys_dir)
    if not path.exists():
        return ManifestRead("absent")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ManifestRead("corrupt", None, str(exc))
    if not isinstance(data, dict):
        return ManifestRead("corrupt", None, "manifest is not a JSON object")
    sv = data.get("schema_version")
    if isinstance(sv, int) and sv != SCHEMA_VERSION:
        return ManifestRead("unsupported", None, f"schema_version {sv}")
    missing = [k for k in _REQUIRED_KEYS if k not in data]
    if missing:
        return ManifestRead("corrupt", None, f"missing keys: {', '.join(missing)}")
    return ManifestRead("ok", data)


def _atomic_write_text(path: Path, text: str, *, replace=os.replace, sleep=time.sleep) -> None:
    """write -> flush -> fsync -> replace, with bounded retry on Windows file-lock races.

    CONVENTION (Windows file-system safety): bounded retry with backoff, then surface the failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        for attempt in range(_REPLACE_ATTEMPTS):
            try:
                replace(tmp, path)
                return
            except PermissionError:
                if attempt == _REPLACE_ATTEMPTS - 1:
                    raise
                sleep(_REPLACE_BACKOFF_S * (2 ** attempt))
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def write_manifest(sys_dir: Path, data: dict, *, replace=os.replace, sleep=time.sleep) -> None:
    _atomic_write_text(
        manifest_path(sys_dir),
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        replace=replace, sleep=sleep,
    )


def new_install_id() -> str:
    return str(uuid.uuid4())


# ---- root identity ---------------------------------------------------------------

_DRIVE_ONLY = re.compile(r"^[A-Za-z]:[\\/]*$")


def _norm(path: str) -> str:
    """Normalize for comparison; a bare drive ("D:") and its root ("D:\\") are the same place."""
    text = str(path)
    if _DRIVE_ONLY.match(text):
        return text[0].lower() + ":\\"
    return ntpath.normcase(ntpath.normpath(text))


def roots_equal(a: str, b: str) -> bool:
    return _norm(a) == _norm(b)


def _default_volume_serial(path: str) -> Optional[str]:
    if os.name != "nt":  # pragma: no cover
        return None
    try:
        import ctypes
        serial = ctypes.c_uint32(0)
        anchor = ntpath.splitdrive(str(path))[0] + "\\"
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(anchor), None, 0, ctypes.byref(serial), None, None, None, 0
        )
        if not ok:
            return None
        v = serial.value
        return f"{v >> 16:04X}-{v & 0xFFFF:04X}"
    except Exception:
        return None


def current_root_identity(
    base_dir: Path,
    *,
    realpath: Callable[[str], str] = os.path.realpath,
    volume_serial: Callable[[str], Optional[str]] = _default_volume_serial,
) -> dict:
    """Logical root as given, physical root resolved (SUBST/junctions), volume serial (diagnostic only)."""
    logical = str(base_dir)
    physical = realpath(logical)
    return {
        "logical": logical,
        "physical": physical,
        "volume_serial": volume_serial(physical),
    }


# ---- previous-root evidence -----------------------------------------------------------

_SYS_LAYOUT_SUFFIX = re.compile(r"[\\/][^\\/]+[\\/]env[\\/]python[\\/]?$", re.IGNORECASE)


def _root_from_pyvenv_home(home: str) -> Optional[str]:
    """``<root>\\<sys_dir>\\env\\python`` -> ``<root>``; anything else -> None."""
    m = _SYS_LAYOUT_SUFFIX.search(home.strip())
    if not m:
        return None
    root = home.strip()[: m.start()]
    if _DRIVE_ONLY.match(root):  # install at a drive root: "D:\\_sys\\env\\python" -> "D:\\", not "D:"
        root = root[0] + ":\\"
    return root or None


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def previous_root_evidence(
    sys_dir: Path, *, localappdata: Optional[Path] = None
) -> list[tuple[str, str]]:
    """Ordered evidence of where this install *used to* live (design section 3).

    Order: pyvenv.cfg home -> data/state/*.state.json base_dir -> registrar sidecars
    -> data/last_base_dir.txt. Sources that are absent are skipped.
    """
    sys_dir = Path(sys_dir)
    out: list[tuple[str, str]] = []

    cfg = _read_text(sys_dir / "env" / "venv" / "pyvenv.cfg")
    if cfg:
        m = re.search(r"(?m)^home\s*=\s*(.+)$", cfg)
        if m:
            root = _root_from_pyvenv_home(m.group(1))
            if root:
                out.append(("pyvenv.cfg", root))

    state_dir = sys_dir / "data" / "state"
    if state_dir.is_dir():
        for sf in sorted(state_dir.glob("*.state.json")):
            try:
                base = json.loads(sf.read_text(encoding="utf-8")).get("base_dir")
            except (OSError, ValueError, AttributeError):
                continue
            if isinstance(base, str) and base:
                out.append(("state", base))
                break

    if localappdata is not None and Path(localappdata).is_dir():
        # Sidecars are shared by *every* Engram install on the machine. Only an
        # unambiguous record (all sidecars agree on one root) is usable as evidence;
        # detect_root_drift additionally ignores it while that root still exists
        # (it may simply be another install).
        roots = []
        for sc in sorted(Path(localappdata).glob("SandboxRun_*.root.txt")):
            val = _read_text(sc)
            if val:
                roots.append(val)
        distinct = {_norm(r): r for r in roots}
        if len(distinct) == 1:
            out.append(("sidecar", next(iter(distinct.values()))))

    last = _read_text(sys_dir / "data" / LAST_BASE_DIR_FILENAME)
    if last:
        out.append(("last_base_dir", last))
    return out


# ---- drift detection ----------------------------------------------------------------------

@dataclass
class RootDrift:
    status: str  # consistent | moved | copied | unknown
    previous_root: Optional[str] = None
    source: Optional[str] = None


def detect_root_drift(
    manifest: Optional[dict],
    base_dir: Path,
    sys_dir: Path,
    *,
    realpath: Callable[[str], str] = os.path.realpath,
    path_exists: Callable[[str], bool] = os.path.exists,
    localappdata: Optional[Path] = None,
) -> RootDrift:
    """Compare the current root with the recorded one (manifest first, then disk evidence).

    Read-only. A SUBST/drive-letter alias of the same physical folder is *not* a move.
    ``copied`` means the old root still exists, so this location is probably a copy
    (the manifest ``install_id`` is what tells them apart for certain; section 3).
    """
    current_logical = str(base_dir)
    current_physical = realpath(current_logical)

    def same(candidate: str) -> bool:
        return roots_equal(candidate, current_logical) or roots_equal(
            realpath(candidate), current_physical
        )

    if manifest:
        root = manifest.get("root") or {}
        recorded = [root.get("physical"), root.get("logical")]
        recorded = [r for r in recorded if r]
        if recorded:
            if any(same(r) for r in recorded):
                return RootDrift("consistent", None, "manifest")
            previous = root.get("logical") or recorded[0]
            status = "copied" if any(path_exists(r) for r in recorded) else "moved"
            return RootDrift(status, previous, "manifest")

    evidence = previous_root_evidence(sys_dir, localappdata=localappdata)
    for source, prev in evidence:
        if same(prev):
            return RootDrift("consistent", None, source)
        if source == "sidecar" and path_exists(prev):
            continue  # a live root recorded by a shared sidecar is probably another install
        status = "copied" if path_exists(prev) else "moved"
        return RootDrift(status, prev, source)
    return RootDrift("unknown")


# ---- adoption proposal (pure) -----------------------------------------------------------------

def _default_python_version_probe(python_exe: str) -> Optional[str]:
    try:
        out = subprocess.run(
            [python_exe, "--version"], capture_output=True, encoding="utf-8", errors="replace", timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(\d+\.\d+\.\d+)", out.stdout + out.stderr)
    return m.group(1) if m else None


def _pyvenv_version(sys_dir: Path) -> Optional[str]:
    cfg = _read_text(Path(sys_dir) / "env" / "venv" / "pyvenv.cfg")
    if not cfg:
        return None
    m = re.search(r"(?m)^version\s*=\s*(\d+\.\d+\.\d+)", cfg)
    return m.group(1) if m else None


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def propose_adoption(
    sys_dir: Path,
    base_dir: Path,
    *,
    python_version_probe: Callable[[str], Optional[str]] = _default_python_version_probe,
    engram_version: Optional[str] = None,
    realpath: Callable[[str], str] = os.path.realpath,
    volume_serial: Callable[[str], Optional[str]] = _default_volume_serial,
    now: Optional[str] = None,
) -> dict:
    """Build (never write) a manifest from what is on disk."""
    sys_dir = Path(sys_dir)
    python_exe = str(sys_dir / "env" / "python" / "python.exe")
    return {
        "schema_version": SCHEMA_VERSION,
        "engram_version": engram_version,
        "sys_dir_name": sys_dir.name,
        "install_id": new_install_id(),
        "root": current_root_identity(base_dir, realpath=realpath, volume_serial=volume_serial),
        "python": {"version": python_version_probe(python_exe)},
        "venv": {"python_version": _pyvenv_version(sys_dir)},
        "adopted_from_evidence": True,
        "created_at": now or _utc_now(),
    }


# ---- fresh-install commit (pipeline operation `env.commit_install`) ---------------------------------

def _engram_version(sys_dir: Path) -> Optional[str]:
    try:
        return json.loads((Path(sys_dir) / "core" / "version.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None


def commit_install(
    ctx: dict,
    *,
    python_version_probe: Callable[[str], Optional[str]] = _default_python_version_probe,
    engram_version: Optional[str] = None,
    realpath: Callable[[str], str] = os.path.realpath,
    volume_serial: Callable[[str], Optional[str]] = _default_volume_serial,
) -> dict:
    """Write the manifest and ``last_base_dir.txt`` for a **fresh** install only.

    An install that already has ``install.state.json`` (re-run, or an existing install
    that predates the manifest) is left untouched: its move signal must survive, and
    adoption goes through ``repair`` (later phase), never through a plain ``install``.
    """
    base_dir = Path(ctx["base_dir"])
    sys_dir = Path(ctx["sys_dir"])
    state_dir = Path(ctx["paths"]["state"])

    if manifest_path(sys_dir).exists() or (state_dir / "install.state.json").exists():
        print("  [--] Environment manifest: existing install, not rewritten")
        return {"status": "success", "operation": "env.commit_install", "skipped": True}

    proposal = propose_adoption(
        sys_dir, base_dir,
        python_version_probe=python_version_probe,
        engram_version=engram_version or _engram_version(sys_dir),
        realpath=realpath, volume_serial=volume_serial,
    )
    proposal["adopted_from_evidence"] = False  # fresh install, nothing was adopted
    write_manifest(sys_dir, proposal)
    _atomic_write_text(sys_dir / "data" / LAST_BASE_DIR_FILENAME, str(base_dir))
    print("  [OK] Environment manifest written (fresh install)")
    return {"status": "success", "operation": "env.commit_install"}
