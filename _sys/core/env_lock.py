"""env_lock.py - exclusive lock for environment-mutating operations.

Design: docs/design/engram-env-resilience-design-2026-10-02.md, section 9.

The lock is a file created with exclusive-create semantics. Its content records
the owner ({pid, start_time, op_id}). A lock is *stale* only when the owning
process is gone or its start time no longer matches (pid reuse). A stale lock is
broken atomically (rename to a unique name, then delete) so that concurrent
starters cannot both win.

Every component that mutates the environment (provisioner venv block, updater,
registrar writes, layout migration, ...) must hold this lock; use ``guard``.
``inspect`` is read-only and is what ``doctor`` uses (doctor never takes the lock).
"""
from __future__ import annotations

import contextlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Callable, Iterator, Optional

LOCK_FILENAME = "env-op.lock"
# Tolerance when comparing a recorded process start time with the live one.
_START_TIME_TOLERANCE_S = 2.0
# An unreadable lock record younger than this is assumed to be mid-write by a live owner
# (only reachable on filesystems without hard links, see _create_exclusive).
_UNREADABLE_GRACE_S = 5.0

ProcessProbe = Callable[[int], Optional[float]]


class EnvLockBusy(RuntimeError):
    """Another live process holds the environment lock."""

    def __init__(self, owner: dict):
        self.owner = owner
        super().__init__(
            f"environment lock is held by op {owner.get('op_id')!r} (pid {owner.get('pid')})"
        )


def lock_path(sys_dir: Path) -> Path:
    return Path(sys_dir) / "data" / "state" / LOCK_FILENAME


def default_process_probe(pid: int) -> Optional[float]:
    """Return the process start time (epoch seconds) or None if it does not exist.

    Returns -1.0 when the process exists but its start time cannot be read
    (e.g. access denied); callers treat that as "alive".
    """
    try:
        import psutil  # type: ignore
    except ImportError:
        psutil = None  # type: ignore
    if psutil is not None:
        try:
            return float(psutil.Process(pid).create_time())
        except psutil.NoSuchProcess:
            return None
        except psutil.AccessDenied:
            return -1.0
        except Exception:
            return None
    return _win_process_start_time(pid)


def _win_process_start_time(pid: int) -> Optional[float]:
    if os.name != "nt":  # pragma: no cover - Engram is Windows-only; keep the module importable
        try:
            os.kill(pid, 0)
            return -1.0
        except OSError:
            return None
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    ERROR_ACCESS_DENIED = 5
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return -1.0 if ctypes.get_last_error() == ERROR_ACCESS_DENIED else None
    try:
        creation, exit_t, kernel, user = (wintypes.FILETIME() for _ in range(4))
        ok = kernel32.GetProcessTimes(
            handle, ctypes.byref(creation), ctypes.byref(exit_t),
            ctypes.byref(kernel), ctypes.byref(user),
        )
        if not ok:
            return -1.0
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        # FILETIME is 100ns ticks since 1601-01-01.
        return ticks / 10_000_000 - 11_644_473_600
    finally:
        kernel32.CloseHandle(handle)


def _read_owner(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or "pid" not in data:
        return None
    return data


def _owner_is_stale(owner: Optional[dict], probe: ProcessProbe, path: Optional[Path] = None) -> bool:
    if owner is None:
        # An unreadable record cannot identify a live owner - but a *very recent* one may
        # simply be mid-write, so only an old one is stale.
        if path is not None:
            try:
                if time.time() - path.stat().st_mtime < _UNREADABLE_GRACE_S:
                    return False
            except OSError:
                return True
        return True
    live_start = probe(int(owner["pid"]))
    if live_start is None:
        return True
    if live_start < 0:  # alive, start time unknown
        return False
    recorded = owner.get("start_time")
    if not isinstance(recorded, (int, float)):
        return False
    return abs(float(recorded) - live_start) > _START_TIME_TOLERANCE_S


class LockHandle:
    def __init__(self, path: Path, op_id: str, pid: int):
        self.path = path
        self.op_id = op_id
        self.pid = pid
        self._released = False

    def release(self) -> None:
        """Remove the lock only if it is still ours (idempotent)."""
        if self._released:
            return
        self._released = True
        owner = _read_owner(self.path)
        if owner and owner.get("op_id") == self.op_id and owner.get("pid") == self.pid:
            with contextlib.suppress(OSError):
                self.path.unlink()

    def __enter__(self) -> "LockHandle":
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def _break_stale(path: Path, judged: Optional[dict]) -> None:
    """Atomically remove a lock judged stale: rename to a unique name, then delete."""
    broken = path.with_name(f"{path.name}.broken-{uuid.uuid4().hex}")
    try:
        os.replace(path, broken)
    except FileNotFoundError:
        return  # someone else already broke it
    # If what we renamed is not what we judged stale (a new owner slipped in),
    # put it back without clobbering anything.
    if _read_owner(broken) != judged:
        try:
            os.link(broken, path)
        except OSError:
            pass
    with contextlib.suppress(OSError):
        broken.unlink()


def _create_exclusive(path: Path, record: str) -> bool:
    """Create ``path`` with complete content, atomically, only if it does not exist.

    Preferred: write a private temp file, then hard-link it into place. ``os.link`` fails
    with FileExistsError if the lock exists and the content is never visible half-written,
    so a concurrent starter can never mistake a fresh lock for a corrupt one.
    Fallback (filesystems without hard links, e.g. exFAT USB drives): O_EXCL create + write;
    the brief empty window is covered by _UNREADABLE_GRACE_S in _owner_is_stale.
    Returns True when the lock was created, False when it already existed.
    """
    tmp = path.with_name(f"{path.name}.new-{uuid.uuid4().hex}")
    with open(tmp, "wb") as fh:
        fh.write(record.encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())
    try:
        try:
            os.link(tmp, path)
            return True
        except FileExistsError:
            return False
        except OSError:
            pass  # hard links unsupported here -> fall back
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        os.write(fd, record.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    return True


def acquire(
    sys_dir: Path,
    op_id: str,
    *,
    pid: Optional[int] = None,
    start_time: Optional[float] = None,
    process_probe: ProcessProbe = default_process_probe,
) -> LockHandle:
    path = lock_path(sys_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    pid = os.getpid() if pid is None else pid
    if start_time is None:
        probed = process_probe(pid)
        start_time = probed if probed and probed > 0 else time.time()
    record = json.dumps({"pid": pid, "start_time": start_time, "op_id": op_id})

    for _ in range(5):
        if _create_exclusive(path, record):
            return LockHandle(path, op_id, pid)
        owner = _read_owner(path)
        if _owner_is_stale(owner, process_probe, path):
            _break_stale(path, owner)
            continue
        raise EnvLockBusy(owner or {})
    raise EnvLockBusy(_read_owner(path) or {})


@contextlib.contextmanager
def guard(sys_dir: Path, op_id: str, **kwargs) -> Iterator[LockHandle]:
    handle = acquire(sys_dir, op_id, **kwargs)
    try:
        yield handle
    finally:
        handle.release()


def inspect(sys_dir: Path, *, process_probe: ProcessProbe = default_process_probe) -> dict:
    """Read-only lock state: free | held | stale."""
    path = lock_path(sys_dir)
    if not path.exists():
        return {"state": "free"}
    owner = _read_owner(path)
    if _owner_is_stale(owner, process_probe, path):
        return {"state": "stale", "owner": owner}
    return {"state": "held", "owner": owner}
