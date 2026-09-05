"""Tests for scrubber.py Tier 5 Python purge."""
import sys
import os
import subprocess
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "core"))
import scrubber  # noqa: E402


def test_tier5_synchronously_renames_dir_and_creates_bat(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    py_dir = sys_dir / "env" / "python"
    py_dir.mkdir(parents=True)
    (py_dir / "test.txt").write_bytes(b"x" * 123)
    
    popen_calls = []
    class MockPopen:
        def __init__(self, args, cwd=None, **kwargs):
            popen_calls.append({"args": args, "cwd": cwd})
    monkeypatch.setattr(subprocess, "Popen", MockPopen)
    
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    monkeypatch.setenv("TEMP", str(temp_dir))
    
    freed = scrubber._tier5(tmp_path, sys_dir, dry_run=False)
    
    assert freed == 123
    assert not py_dir.exists()
    
    purge_dir = sys_dir / "env" / "python.purge"
    assert purge_dir.exists()
    
    bat_path = temp_dir / "_purge_python.bat"
    assert bat_path.exists()
    
    bat_content = bat_path.read_text(encoding="mbcs")
    assert f'rmdir /s /q "{str(purge_dir)}"' in bat_content
    
    assert len(popen_calls) == 1
    call = popen_calls[0]
    assert call["args"] == ["cmd", "/c", ".\\_purge_python.bat"]
    assert call["cwd"] == str(temp_dir)


def test_tier5_percent_escaping(tmp_path, monkeypatch):
    sys_dir = tmp_path / "test%dir" / "_sys"
    py_dir = sys_dir / "env" / "python"
    py_dir.mkdir(parents=True)
    (py_dir / "test.txt").write_bytes(b"x" * 123)
    
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: None)
    
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    monkeypatch.setenv("TEMP", str(temp_dir))
    
    scrubber._tier5(tmp_path, sys_dir, dry_run=False)
    
    purge_dir = sys_dir / "env" / "python.purge"
    bat_path = temp_dir / "_purge_python.bat"
    
    bat_content = bat_path.read_text(encoding="mbcs")
    expected_path_str = str(purge_dir).replace("%", "%%")
    assert f'rmdir /s /q "{expected_path_str}"' in bat_content


def test_tier5_dry_run_does_not_delete(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    py_dir = sys_dir / "env" / "python"
    py_dir.mkdir(parents=True)
    (py_dir / "test.txt").write_bytes(b"x" * 123)
    
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: None)
    
    freed = scrubber._tier5(tmp_path, sys_dir, dry_run=True)
    
    assert freed == 123
    assert py_dir.exists()
