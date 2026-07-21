import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "_sys"))
from core.doctor import run

def test_doctor_missing_keys_no_crash(monkeypatch, capsys):
    import core.doctor
    
    monkeypatch.setattr(core.doctor, "check_python", lambda sys_dir: {"ok": False, "level": "error"})
    monkeypatch.setattr(core.doctor, "check_components", lambda sys_dir: {"ok": True})
    monkeypatch.setattr(core.doctor, "check_subst", lambda base_dir: {"ok": False})
    monkeypatch.setattr(core.doctor, "check_registration", lambda base_dir, sys_dir: {"ok": False})
    monkeypatch.setattr(core.doctor, "check_sessions", lambda sys_dir: {"ok": True})
    monkeypatch.setattr(core.doctor, "check_elevation", lambda: {"ok": False})
    
    ctx = {
        "base_dir": "/mock/base",
        "sys_dir": "/mock/sys",
        "args": []
    }
    
    result = run(ctx)
    
    assert result["status"] == "failed"
    assert "no detail provided" in result["detail"]
    
    captured = capsys.readouterr()
    assert "unknown" in captured.out
    assert "no detail provided" in captured.out
