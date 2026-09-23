import pytest
from pathlib import Path
import json

from _sys.core import state_paths
from _sys.checks.check_root_hygiene import check_root

def test_writers_land_at_new_paths(tmp_path):
    sys_dir = tmp_path / "_sys"

    assert state_paths.discovery_cache(sys_dir) == sys_dir / "data" / "state" / "update" / "tool_discovery_cache.json"
    assert state_paths.deferred_retries(sys_dir) == sys_dir / "data" / "state" / "update" / "tool_deferred_retries.json"
    assert state_paths.proposals_dir(sys_dir) == sys_dir / "data" / "state" / "update" / "proposals"
    assert state_paths.receipts_dir(sys_dir) == sys_dir / "data" / "state" / "update" / "receipts"
    assert state_paths.launcher_log_dir(sys_dir) == sys_dir / "data" / "logs" / "launcher"

def test_credential_shaped_names():
    assert isinstance(state_paths.CREDENTIAL_SHAPED_NAMES, frozenset)
    assert state_paths.CREDENTIAL_SHAPED_NAMES == frozenset({
        "auth.json", ".credentials.json", "credentials.json", "token.json",
        "hosts.yml",
    })

def test_hygiene_error_info_behavior(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True if self.name == ".ai" or self == tmp_path else False)

    # 1. Engram-owned .ai/
    ai_dir = tmp_path / ".ai"
    ai_dir.mkdir()
    (ai_dir / "tool_discovery_cache.json").touch()

    # Monkeypatch PORTABLE_ROOT in check_root_hygiene
    import _sys.checks.check_root_hygiene as hygiene
    monkeypatch.setattr(hygiene, "PORTABLE_ROOT", tmp_path)

    errors = check_root()
    assert any("Engram-owned state in .ai/" in e for e in errors)

    # 2. External .ai/
    (ai_dir / "tool_discovery_cache.json").unlink()
    (ai_dir / "some_other_file.txt").touch()

    errors = check_root()
    assert not any("Engram-owned state in .ai/" in e for e in errors)
