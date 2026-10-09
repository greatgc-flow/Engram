"""Deterministic Windows locked-file / share-mode tests for backup/restore/reset/tidy.

EN-GAP-P1-002: Real OS locks (dwShareMode=0 via CreateFileW) on files inside the data tree
must cause CLI operations to fail explicitly with nonzero exit, name the locked path in
the error output, display no success marker, and release the lock holder in finally.
The fixtures check preservation when the only restore payload is the locked file;
they do not assert transaction-wide rollback for arbitrary restore failures.
"""
from __future__ import annotations

import contextlib
import ctypes
from ctypes import wintypes
import errno
import json
from pathlib import Path
import shutil
import sys

import pytest

from checks import backup_personal_data
from core import dispatcher, tidy_temp

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows locked-file share-mode tests require win32",
)

# Win32 API constants for exclusive share-mode locking
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_NONE = 0
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


@contextlib.contextmanager
def locked_file_share_mode(path: Path):
    """Acquire an exclusive OS file lock with dwShareMode=0 through ctypes on Windows.

    With dwShareMode=0, no sharing (read, write, or delete) is granted to any other
    process or file handle. The handle is strictly closed in finally.
    """
    path = Path(path).resolve()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    CreateFileW = kernel32.CreateFileW
    CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    CreateFileW.restype = wintypes.HANDLE

    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL

    handle = CreateFileW(
        str(path),
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_NONE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle is None or handle == INVALID_HANDLE_VALUE or handle == -1 or handle == 0xFFFFFFFFFFFFFFFF:
        err = ctypes.get_last_error()
        raise ctypes.WinError(err)

    try:
        yield path
    finally:
        CloseHandle(handle)


@pytest.fixture
def cli_root(tmp_path, monkeypatch):
    root = tmp_path / "Engram fault fixture"
    sys_dir = root / "_sys"
    (sys_dir / "config").mkdir(parents=True)
    (sys_dir / "config" / "environment.json").write_text(
        json.dumps({"paths": {"state": str(sys_dir / "data" / "state")}}),
        encoding="utf-8",
    )
    shutil.copy2(
        Path(dispatcher.__file__).parents[1] / "dispatch.json",
        sys_dir / "dispatch.json",
    )
    monkeypatch.setattr(dispatcher, "base_dir", root)
    monkeypatch.setattr(dispatcher, "sys_dir", sys_dir)
    # Preserve tidy's module globals because run() configures them in place.
    for name, value in vars(tidy_temp).copy().items():
        if name.isupper():
            monkeypatch.setattr(tidy_temp, name, value)
    monkeypatch.setattr(backup_personal_data, "check_running_processes", lambda _: [])
    return root, sys_dir


def _tree(path: Path) -> dict[str, bytes]:
    return {
        p.relative_to(path).as_posix(): p.read_bytes()
        for p in path.rglob("*")
        if p.is_file()
    } if path.exists() else {}


def _invoke(verb: str, *args):
    """Match script exit semantics while leaving unexpected exceptions visible."""
    try:
        return dispatcher.main(["dispatcher.py", verb, *map(str, args)])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    except (OSError, RuntimeError):
        return 1


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows locked-file share-mode tests require win32",
)
def test_locked_file_share_mode_helper_locks_exclusively(tmp_path):
    """Sanity check that locked_file_share_mode prevents reads and releases in finally."""
    probe = tmp_path / "probe.txt"
    probe.write_text("probe content", encoding="utf-8")
    with locked_file_share_mode(probe):
        with pytest.raises(PermissionError) as exc_info:
            probe.read_bytes()
        # CPython's CRT file opens can report EACCES without a Win32 code.
        assert exc_info.value.winerror == 32 or (
            exc_info.value.winerror is None and exc_info.value.errno == errno.EACCES
        )
    # Lock holder released in finally
    assert probe.read_text(encoding="utf-8") == "probe content"


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows locked-file share-mode tests require win32",
)
@pytest.mark.parametrize("verb", ["backup", "restore", "reset", "tidy"])
def test_locked_file_share_mode_aborts_without_partial_deletion(
    cli_root, capsys, verb
):
    root, sys_dir = cli_root
    if verb == "tidy":
        target = sys_dir / "tests" / ".pytest_cache"
        args = ["--only", "pytest_cache_default", "--apply"]
    else:
        target = root / ".engram"
        if verb == "reset":
            args = ["--apply", "--yes"]
        elif verb == "backup":
            args = []
        else:  # restore
            bundle = root / "restore-bundle"
            incoming = bundle / "claude" / "settings.json"
            incoming.parent.mkdir(parents=True)
            incoming.write_bytes(b'{"replacement":true}')
            args = [bundle, "--apply"]

    locked_file = target / "claude" / "settings.json"
    locked_file.parent.mkdir(parents=True, exist_ok=True)
    locked_file.write_bytes(b'{"original":true}')
    untouched = target / "untouched.bin"
    untouched.write_bytes(b"preserve non-allowlisted data too")
    before = _tree(target)

    lock_released = False
    try:
        with locked_file_share_mode(locked_file):
            code = _invoke(verb, *args)
            captured = capsys.readouterr()
            output = captured.out + captured.err
    finally:
        lock_released = True

    # 1. Nonzero exit
    assert code != 0, f"Expected nonzero exit code for {verb}, got {code}. Output:\n{output}"

    # 2. Error names the locked path
    assert (
        str(locked_file) in output
        or str(locked_file.resolve()) in output
        or locked_file.name in output
    ), f"Locked path '{locked_file}' not found in output for {verb}:\n{output}"

    # 3. No success marker
    if verb == "backup":
        assert "Done. Manifest written" not in output, output
        assert "Done." not in output.splitlines(), output
    elif verb == "restore":
        assert "Done." not in output.splitlines(), output
    elif verb == "reset":
        assert "Reset complete." not in output.splitlines(), output
    assert "(applied)" not in output, output

    # 4. No partial deletion of other files
    assert untouched.exists(), f"untouched.bin was partially deleted during {verb}"
    assert untouched.read_bytes() == before["untouched.bin"], f"untouched.bin modified during {verb}"
    assert _tree(target) == before, f"Files under {target} were modified or deleted during failed {verb}"

    # 5. Lock holder is released in finally
    assert lock_released is True
    with open(locked_file, "r+b") as f:
        assert f.read() == before["claude/settings.json"]
        f.seek(0)
        f.write(b'{"original":true}')


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows locked-file share-mode tests require win32",
)
def test_restore_force_locked_file_aborts_without_partial_deletion(cli_root, capsys):
    """Restore with --force waives pre-restore snapshot but must still fail on locked live file."""
    root, _ = cli_root
    target = root / ".engram"
    bundle = root / "restore-bundle"
    incoming = bundle / "claude" / "settings.json"
    incoming.parent.mkdir(parents=True)
    incoming.write_bytes(b'{"replacement":true}')
    args = [bundle, "--apply", "--force"]

    locked_file = target / "claude" / "settings.json"
    locked_file.parent.mkdir(parents=True, exist_ok=True)
    locked_file.write_bytes(b'{"original":true}')
    untouched = target / "untouched.bin"
    untouched.write_bytes(b"preserve non-allowlisted data too")
    before = _tree(target)

    lock_released = False
    try:
        with locked_file_share_mode(locked_file):
            code = _invoke("restore", *args)
            captured = capsys.readouterr()
            output = captured.out + captured.err
    finally:
        lock_released = True

    assert code != 0, f"Expected nonzero exit code for restore --force. Output:\n{output}"
    assert (
        str(locked_file) in output
        or str(locked_file.resolve()) in output
        or locked_file.name in output
    ), f"Locked path '{locked_file}' not found in output:\n{output}"
    assert "Done." not in output.splitlines(), output
    assert "(applied)" not in output, output
    assert untouched.exists()
    assert untouched.read_bytes() == before["untouched.bin"]
    assert _tree(target) == before
    assert lock_released is True
    with open(locked_file, "r+b") as f:
        assert f.read() == before["claude/settings.json"]
