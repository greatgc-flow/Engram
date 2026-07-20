import pytest
import json
from pathlib import Path
import sys

SYS_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SYS_DIR))

from checks.check_backlog import check_backlog

def test_check_backlog_handles_null_evidence_and_supersedes(tmp_path, monkeypatch):
    """
    Test that check_backlog doesn't crash when evidence_commit or supersedes is null.
    """
    import checks.check_backlog as check_backlog_mod
    
    # Mock BACKLOG_PATH to use our temp file
    backlog_file = tmp_path / "backlog.json"
    backlog_data = {
        "schema_version": 1,
        "items": [
            {
                "id": "item1",
                "status": "done",
                "evidence_commit": None,
                "supersedes": None
            }
        ]
    }
    backlog_file.write_text(json.dumps(backlog_data), encoding="utf-8")
    
    monkeypatch.setattr(check_backlog_mod, "BACKLOG_PATH", backlog_file)
    monkeypatch.setattr(check_backlog_mod, "PORTABLE_ROOT", tmp_path)
    
    # Check that it returns validation errors instead of raising TypeError.
    # Note: With the bug present, this call will raise a TypeError.
    try:
        errors = check_backlog(live=True)
    except TypeError:
        pytest.fail("check_backlog crashed with a TypeError due to null lists!")
        
    assert any("requires a non-empty 'evidence_commit' list" in e for e in errors)
