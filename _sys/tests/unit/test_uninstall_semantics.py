import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import sys

_SYS_DIR = Path(__file__).resolve().parents[2]

def get_uninstall_func():
    if str(_SYS_DIR) not in sys.path:
        sys.path.insert(0, str(_SYS_DIR))
    from cli.manage import uninstall
    return uninstall

@pytest.fixture
def mock_ctx(tmp_path):
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    sys_dir = base_dir / "_sys"
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    localappdata = tmp_path / "localappdata"
    localappdata.mkdir()
    
    ctx = {
        "base_dir": base_dir,
        "sys_dir": sys_dir,
        "paths": {
            "state": state_dir,
            "generated": sys_dir / "data" / "generated",
            "localappdata": localappdata,
        },
        "args": [],
        "state": {},
    }
    return ctx

def test_uninstall_happy_path(mock_ctx):
    import hashlib
    uninstall_fn = get_uninstall_func()
    
    with patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit", side_effect=SystemExit) as mock_exit:
        
        try:
            uninstall_fn(mock_ctx)
        except SystemExit:
            pass
        
        install_id = hashlib.sha256(str(mock_ctx["base_dir"].absolute()).lower().encode("utf-8")).hexdigest()
        journal_path = mock_ctx["paths"]["localappdata"] / "Engram" / "uninstall" / install_id / "journal.json"
        
        assert journal_path.exists(), "Journal must be written"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        assert journal["operation"] == "uninstall"
        assert journal["status"] == "IN_PROGRESS"
        assert not journal["error_recoverable"]
        
        # Check that helper was generated and Popen was called
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "cmd.exe"
        assert args[1] == "/c"
        cwd = mock_popen.call_args.kwargs.get("cwd")
        helper_path = Path(cwd) / args[2] if cwd else Path(args[2])
        assert helper_path.exists()
        assert helper_path.name == "EngramUninstallHelper.bat"
        assert "BASE_DIR" in helper_path.read_text(encoding="utf-8")
        
        mock_exit.assert_called_once_with(0)

def test_uninstall_registered_branch(mock_ctx):
    import hashlib
    uninstall_fn = get_uninstall_func()
    
    # Mark as registered
    (mock_ctx["paths"]["state"] / "register.state.json").write_text("{}")
    
    with patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit", side_effect=SystemExit) as mock_exit, \
         patch("core.registrar.remove") as mock_remove, \
         patch("core.virtualizer.unmount") as mock_unmount:
         
        try:
            uninstall_fn(mock_ctx)
        except SystemExit:
            pass
        
        mock_remove.assert_called_once_with(mock_ctx)
        mock_unmount.assert_called_once_with(mock_ctx)
        
        install_id = hashlib.sha256(str(mock_ctx["base_dir"].absolute()).lower().encode("utf-8")).hexdigest()
        journal_path = mock_ctx["paths"]["localappdata"] / "Engram" / "uninstall" / install_id / "journal.json"
        
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        assert "registry_cleanup" in journal["steps"]
        assert "junction_cleanup" in journal["steps"]

def test_uninstall_failure_path(mock_ctx):
    import hashlib
    uninstall_fn = get_uninstall_func()
    
    # Mark as registered
    (mock_ctx["paths"]["state"] / "register.state.json").write_text("{}")
    
    with patch("core.registrar.remove", side_effect=Exception("mocked failure")), \
         patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit", side_effect=SystemExit) as mock_exit:
         
        try:
            uninstall_fn(mock_ctx)
        except SystemExit:
            pass
        
        install_id = hashlib.sha256(str(mock_ctx["base_dir"].absolute()).lower().encode("utf-8")).hexdigest()
        journal_path = mock_ctx["paths"]["localappdata"] / "Engram" / "uninstall" / install_id / "journal.json"
        
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        assert journal["status"] == "FAILED_RECOVERABLE"
        assert journal["error_recoverable"] is True
        
        mock_exit.assert_called_once_with(1)
        mock_popen.assert_not_called()


def test_uninstall_helper_invocation_pattern_actually_runs_in_ampersand_dir(tmp_path):
    """The exact subprocess argv/cwd shape manage.py's uninstall() uses
    (cmd.exe /c .\\HelperName.bat with cwd=parent, commit e794415) must
    actually execute in a real "&"-laden directory. A bare relative name
    (no ".\\" prefix) was found to fail with "not recognized as an internal
    or external command" even with cwd correctly set -- only the
    ".\\"-prefixed form works. Tests the real invocation pattern directly
    rather than the full uninstall() pipeline (registry/junction cleanup,
    parent-PID wait loop, journal updates), which is already covered by
    the mocked tests above."""
    import subprocess

    fixture_dir = tmp_path / "engram&uninstall_test"
    fixture_dir.mkdir()
    helper_path = fixture_dir / "EngramUninstallHelper.bat"
    helper_path.write_text("@echo off\r\necho HELPER_RAN\r\nexit /b 0\r\n", encoding="utf-8")

    proc = subprocess.run(
        ["cmd.exe", "/c", f".\\{helper_path.name}"],
        cwd=str(helper_path.parent),
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
    )
    assert proc.returncode == 0, (
        f"Expected the .\\-prefixed invocation to succeed.\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    assert "HELPER_RAN" in proc.stdout


def test_uninstall_helper_bare_name_invocation_fails_in_ampersand_dir(tmp_path):
    """Sanity check for the test above: confirms the bare (non-".\\"-prefixed)
    form genuinely fails in a real "&"-laden cwd, so the ".\\"-prefixed
    test isn't vacuously passing for an unrelated reason."""
    import subprocess

    fixture_dir = tmp_path / "engram&uninstall_test2"
    fixture_dir.mkdir()
    helper_path = fixture_dir / "EngramUninstallHelper.bat"
    helper_path.write_text("@echo off\r\necho HELPER_RAN\r\nexit /b 0\r\n", encoding="utf-8")

    proc = subprocess.run(
        ["cmd.exe", "/c", helper_path.name],  # bare, no ".\\" prefix -- the buggy form
        cwd=str(helper_path.parent),
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
    )
    assert proc.returncode != 0
    assert "HELPER_RAN" not in proc.stdout
