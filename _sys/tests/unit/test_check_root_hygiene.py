import pytest
import subprocess
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add _sys/checks to sys.path so we can import check_root_hygiene
SYS_DIR = Path(__file__).resolve().parent.parent.parent
CHECKS_DIR = SYS_DIR / "checks"
if str(CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKS_DIR))

from check_root_hygiene import check_root, check_closure, main, ALLOWLIST

@patch("check_root_hygiene.PORTABLE_ROOT")
def test_check_root_clean(mock_root):
    # Mock PORTABLE_ROOT.iterdir to return only ALLOWLIST items
    mock_root.exists.return_value = True
    mock_root.iterdir.return_value = [MagicMock(name=item) for item in ALLOWLIST]
    for i, item in enumerate(ALLOWLIST):
        mock_root.iterdir.return_value[i].name = item
        
    errors = check_root()
    assert not errors

@patch("check_root_hygiene.PORTABLE_ROOT")
def test_check_root_dirty(mock_root):
    mock_root.exists.return_value = True
    unexpected = MagicMock()
    unexpected.name = "unexpected_file.txt"
    mock_root.iterdir.return_value = [unexpected]
    
    errors = check_root()
    assert len(errors) == 1
    assert "Unexpected entry at root: unexpected_file.txt" in errors[0]

@patch("subprocess.run")
@patch("check_backlog.check_backlog")
def test_check_closure_clean(mock_check_backlog, mock_run):
    mock_check_backlog.return_value = []
    
    def side_effect(*args, **kwargs):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        return mock_proc
        
    mock_run.side_effect = side_effect
    
    errors = check_closure()
    assert not errors
    assert mock_check_backlog.called
    assert mock_run.call_count == 2

@patch("subprocess.run")
@patch("check_backlog.check_backlog")
def test_check_closure_dirty(mock_check_backlog, mock_run):
    mock_check_backlog.return_value = ["Backlog validation failed"]
    
    def side_effect(cmd, **kwargs):
        mock_proc = MagicMock()
        if "status" in cmd:
            mock_proc.returncode = 0
            mock_proc.stdout = "M some_file.py"
            mock_proc.stderr = ""
        elif "diff" in cmd:
            mock_proc.returncode = 2
            mock_proc.stdout = "whitespace error"
            mock_proc.stderr = ""
        return mock_proc
        
    mock_run.side_effect = side_effect
    
    errors = check_closure()
    assert len(errors) == 3
    assert "git working tree not clean:\nM some_file.py" in errors
    assert "git diff --check found whitespace errors or failed:\nwhitespace error" in errors
    assert "Backlog validation failed" in errors

@patch("check_root_hygiene.check_root")
@patch("check_root_hygiene.check_closure")
def test_main_default(mock_closure, mock_root, capsys):
    mock_root.return_value = []
    exit_code = main([])
    assert exit_code == 0
    assert not mock_closure.called
    
    out, _ = capsys.readouterr()
    assert "[CHK-ROOT] OK. Root is clean." in out

@patch("check_root_hygiene.check_root")
@patch("check_root_hygiene.check_closure")
def test_main_closure(mock_closure, mock_root, capsys):
    mock_root.return_value = []
    mock_closure.return_value = []
    exit_code = main(["--closure"])
    assert exit_code == 0
    assert mock_closure.called
    
    out, _ = capsys.readouterr()
    assert "and closure is verified." in out

@patch("check_root_hygiene.check_root")
def test_main_errors(mock_root, capsys):
    mock_root.return_value = ["Unexpected file: foo.txt"]
    exit_code = main([])
    assert exit_code == 2
    
    out, _ = capsys.readouterr()
    assert "[CHK-ROOT] Validation failed:" in out
    assert "  - Unexpected file: foo.txt" in out
