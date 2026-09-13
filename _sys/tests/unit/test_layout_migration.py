import json
import logging
from pathlib import Path
import pytest
from unittest.mock import patch

from _sys.core.layout_migration import merge_declarations_impl

@pytest.fixture
def migration_env(tmp_path):
    # Setup mock paths inside tmp_path
    live_dir = tmp_path / "_sys"
    live_dir.mkdir()
    
    defaults_dir = tmp_path / "_sys" / "defaults"
    defaults_dir.mkdir(parents=True)
    
    base_state_dir = tmp_path / "_sys" / "data" / "state" / "defaults-base"
    base_state_dir.mkdir(parents=True)
    
    manifest_base_dir = tmp_path / "_sys" / "core" / "release-manifests" / "3.2.6-defaults"
    manifest_base_dir.mkdir(parents=True)
    
    return {
        "live": live_dir,
        "defaults": defaults_dir,
        "base_state": base_state_dir,
        "manifest": manifest_base_dir
    }

def test_merge_declarations_runtimes(migration_env, caplog):
    caplog.set_level(logging.INFO)
    
    # 1. ours == base -> take theirs
    # 2. ours advanced -> ours != base, keep ours, reported
    # 3. component added upstream -> added
    # 4. component removed upstream with ours == base -> removed
    # 5. component removed upstream with ours != base -> kept, reported
    # 6. _comment taken from theirs
    
    base_json = {
        "_comment": "old comment",
        "runtimes": {
            "python": {"version": "3.13"}, # ours == base
            "nodejs": {"version": "20.0"}, # ours != base (advanced)
            "go": {"version": "1.20"} # removed upstream, ours == base
        },
        "tools": {
            "rg": {"version": "12.0"} # removed upstream, ours != base
        }
    }
    
    ours_json = {
        "_comment": "old comment",
        "runtimes": {
            "python": {"version": "3.13"},
            "nodejs": {"version": "20.1"}, # advanced locally
            "go": {"version": "1.20"}
        },
        "tools": {
            "rg": {"version": "13.0"} # advanced locally, removed upstream
        }
    }
    
    theirs_json = {
        "_comment": "new comment", # taken from theirs
        "runtimes": {
            "python": {"version": "3.14"}, # ours == base, take theirs
            "nodejs": {"version": "22.0"}, # ours != base, keep ours
            "rust": {"version": "1.70"} # added upstream
        },
        "tools": {}
    }
    
    with open(migration_env["base_state"] / "runtimes.json", "w") as f:
        json.dump(base_json, f)
    with open(migration_env["live"] / "runtimes.json", "w") as f:
        json.dump(ours_json, f)
    with open(migration_env["defaults"] / "runtimes.json", "w") as f:
        json.dump(theirs_json, f)
        
    merge_declarations_impl(migration_env["defaults"], migration_env["live"], migration_env["base_state"], migration_env["manifest"], ["runtimes.json", "tool-catalog.v1.json"])
    
    # Assertions
    with open(migration_env["live"] / "runtimes.json") as f:
        merged = json.load(f)
        
    assert merged["_comment"] == "new comment"
    assert merged["runtimes"]["python"]["version"] == "3.14" # take theirs
    assert merged["runtimes"]["nodejs"]["version"] == "20.1" # keep ours
    assert merged["runtimes"]["rust"]["version"] == "1.70" # added
    assert "go" not in merged["runtimes"] # removed
    assert merged["tools"]["rg"]["version"] == "13.0" # kept, reported
    
    assert "kept local modifications instead of taking upstream update" in caplog.text
    assert "kept local modifications despite upstream removal" in caplog.text
    
    # Assert backups
    assert (migration_env["base_state"] / "runtimes.json.pre-merge.bak").exists()
    
    # Assert base updated
    with open(migration_env["base_state"] / "runtimes.json") as f:
        new_base = json.load(f)
    assert new_base["runtimes"]["python"]["version"] == "3.14"


def test_merge_declarations_tool_catalog(migration_env):
    base_json = {
        "$schema": "old",
        "tools": [
            {"tool_id": "a", "v": "1"}, # ours == base
            {"tool_id": "b", "v": "1"}, # ours != base
            {"tool_id": "c", "v": "1"}, # removed, ours == base
            {"tool_id": "d", "v": "1"}  # removed, ours != base
        ]
    }
    
    ours_json = {
        "$schema": "old",
        "tools": [
            {"tool_id": "a", "v": "1"},
            {"tool_id": "b", "v": "2"},
            {"tool_id": "c", "v": "1"},
            {"tool_id": "d", "v": "2"}
        ]
    }
    
    theirs_json = {
        "$schema": "new",
        "tools": [
            {"tool_id": "a", "v": "3"},
            {"tool_id": "b", "v": "3"},
            {"tool_id": "e", "v": "1"}
        ]
    }
    
    with open(migration_env["base_state"] / "tool-catalog.v1.json", "w") as f:
        json.dump(base_json, f)
    with open(migration_env["live"] / "tool-catalog.v1.json", "w") as f:
        json.dump(ours_json, f)
    with open(migration_env["defaults"] / "tool-catalog.v1.json", "w") as f:
        json.dump(theirs_json, f)
        
    merge_declarations_impl(migration_env["defaults"], migration_env["live"], migration_env["base_state"], migration_env["manifest"], ["runtimes.json", "tool-catalog.v1.json"])
    
    with open(migration_env["live"] / "tool-catalog.v1.json") as f:
        merged = json.load(f)
        
    assert merged["$schema"] == "new"
    
    tools = {t["tool_id"]: t["v"] for t in merged["tools"]}
    assert tools["a"] == "3"
    assert tools["b"] == "2"
    assert "c" not in tools
    assert tools["d"] == "2"
    assert tools["e"] == "1"

def test_atomic_write_exception(migration_env, monkeypatch):
    ours_json = {"runtimes": {}}
    theirs_json = {"runtimes": {}}
    
    with open(migration_env["live"] / "runtimes.json", "w") as f:
        json.dump(ours_json, f)
    with open(migration_env["defaults"] / "runtimes.json", "w") as f:
        json.dump(theirs_json, f)
        
    # Inject exception during _atomic_write_json
    def mock_atomic_write(*args, **kwargs):
        raise OSError("Disk full")
        
    monkeypatch.setattr("_sys.core.layout_migration._atomic_write_json", mock_atomic_write)
    
    with pytest.raises(SystemExit) as excinfo:
        merge_declarations_impl(migration_env["defaults"], migration_env["live"], migration_env["base_state"], migration_env["manifest"], ["runtimes.json", "tool-catalog.v1.json"])
        
    assert excinfo.value.code == 1
    
    # Verify live file is intact
    with open(migration_env["live"] / "runtimes.json") as f:
        assert json.load(f) == ours_json
