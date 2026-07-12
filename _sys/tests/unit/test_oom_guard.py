import os
import json
import time
from pathlib import Path
from conftest import _enforce_oom_guard

def test_oom_guard_fires_below_threshold(monkeypatch, tmp_path):
    marker_file = tmp_path / "oom_marker.json"
    
    exited = False
    def mock_exit(code):
        nonlocal exited
        exited = True

    monkeypatch.setattr(os, "_exit", mock_exit)
    
    # 500 MB available, threshold 512 MB -> should fire
    _enforce_oom_guard(512.0, 500.0, marker_path=str(marker_file))
    
    assert exited is True
    assert marker_file.exists()
    
    data = json.loads(marker_file.read_text(encoding="utf-8"))
    assert "timestamp" in data
    assert data["pid"] == os.getpid()
    assert data["available_mb"] == 500.0
    assert data["threshold_mb"] == 512.0
    assert data["reason"] == "OOM Guard triggered"

def test_oom_guard_does_not_fire_above_threshold(monkeypatch, tmp_path):
    marker_file = tmp_path / "oom_marker.json"
    
    exited = False
    def mock_exit(code):
        nonlocal exited
        exited = True

    monkeypatch.setattr(os, "_exit", mock_exit)
    
    # 600 MB available, threshold 512 MB -> should NOT fire
    _enforce_oom_guard(512.0, 600.0, marker_path=str(marker_file))
    
    assert exited is False
    assert not marker_file.exists()
