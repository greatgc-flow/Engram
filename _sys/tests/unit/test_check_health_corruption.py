"""Tests for check_health.py corruption handling."""
import json
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "checks"))
from check_health import _update_health_json, _mark_health_error


def test_update_health_json_with_corrupt_file(tmp_path: Path):
    """
    If health.json is corrupted (e.g. empty or invalid JSON), _update_health_json
    should recover gracefully and write the new state rather than silently failing.
    """
    health_file = tmp_path / "health.json"
    
    # Simulate a corrupted health file (invalid JSON)
    health_file.write_text("{ corrupt json", encoding="utf-8")
    
    # Update health
    _update_health_json(health_file, 1.5, "RED")
    
    # The file should be overwritten with valid JSON
    assert health_file.exists()
    content = json.loads(health_file.read_text(encoding="utf-8"))
    
    assert "context_health" in content
    assert content["context_health"]["jsonl_mb"] == 1.5
    assert content["context_health"]["status"] == "RED"


def test_mark_health_error_with_corrupt_file(tmp_path: Path):
    """
    If health.json is corrupted, _mark_health_error should recover gracefully
    and record the error rather than silently failing.
    """
    health_file = tmp_path / "health.json"
    
    # Simulate a corrupted health file (invalid JSON)
    health_file.write_text("{ corrupt json", encoding="utf-8")
    
    # Mark an error
    _mark_health_error(health_file, "20260720")
    
    # The file should be overwritten with valid JSON
    assert health_file.exists()
    content = json.loads(health_file.read_text(encoding="utf-8"))
    
    assert "session_health" in content
    assert content["session_health"]["last_failure_reason"] == "context_health_failed_20260720"
