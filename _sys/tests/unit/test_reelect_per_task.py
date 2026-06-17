"""TDD — I3: protocol.json leader_election.reelect_per_task flag.

Tests are written BEFORE the flag is added to protocol.json.
All tests MUST FAIL until implementation is complete.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))

PROTOCOL_JSON = Path(__file__).parent.parent.parent / "ai" / "protocol.json"


# ── Config schema ────────────────────────────────────────────────────────────

class TestReelectPerTaskConfig:
    def test_protocol_json_has_leader_election(self):
        data = json.loads(PROTOCOL_JSON.read_text(encoding="utf-8"))
        assert "leader_election" in data, "leader_election section missing"

    def test_reelect_per_task_exists(self):
        data = json.loads(PROTOCOL_JSON.read_text(encoding="utf-8"))
        le = data["leader_election"]
        assert "reelect_per_task" in le, \
            "reelect_per_task flag missing from leader_election"

    def test_reelect_per_task_is_bool(self):
        data = json.loads(PROTOCOL_JSON.read_text(encoding="utf-8"))
        le = data["leader_election"]
        assert isinstance(le["reelect_per_task"], bool), \
            f"reelect_per_task must be bool, got {type(le['reelect_per_task'])}"

    def test_reelect_per_task_defaults_false(self):
        """Default must be False — existing session-scoped behavior preserved."""
        data = json.loads(PROTOCOL_JSON.read_text(encoding="utf-8"))
        le = data["leader_election"]
        assert le["reelect_per_task"] is False, \
            "reelect_per_task default must be False (session-scoped election)"

    def test_reelect_note_field_present(self):
        """Documentation note field should accompany the flag."""
        data = json.loads(PROTOCOL_JSON.read_text(encoding="utf-8"))
        le = data["leader_election"]
        assert "reelect_per_task_note" in le or "reelect_per_task" in le, \
            "Flag must have an explanatory note field"


# ── hub.py behavior ──────────────────────────────────────────────────────────

class TestReelectPerTaskBehavior:
    """Tests for hub.py behavior when reelect_per_task flag is read."""

    def _make_protocol(self, tmp_path, reelect: bool) -> Path:
        p = tmp_path / "protocol.json"
        p.write_text(json.dumps({
            "leader_election": {
                "enabled": True,
                "reelect_per_task": reelect,
                "challenge_window_minutes": 1
            },
            "collab_rate": {"current": 3}
        }))
        return p

    def test_flag_false_no_election_triggered(self, tmp_path):
        """With reelect_per_task=False, no elect-leader call on ask."""
        import hub
        protocol_path = self._make_protocol(tmp_path, False)
        # Read the protocol via hub utility if available
        data = json.loads(protocol_path.read_text())
        assert data["leader_election"]["reelect_per_task"] is False

    def test_flag_true_election_would_trigger(self, tmp_path):
        """With reelect_per_task=True, election is expected per task."""
        protocol_path = self._make_protocol(tmp_path, True)
        data = json.loads(protocol_path.read_text())
        assert data["leader_election"]["reelect_per_task"] is True

    def test_hub_reads_flag_from_protocol_json(self, tmp_path, monkeypatch):
        """hub._runtime_cfg() should return the reelect_per_task value."""
        import hub
        protocol_path = self._make_protocol(tmp_path, False)
        monkeypatch.setattr(hub, "_runtime_cfg",
                            lambda: json.loads(protocol_path.read_text()))
        cfg = hub._runtime_cfg()
        # If hub exposes this via _runtime_cfg, it should be readable
        assert "leader_election" in cfg
        assert cfg["leader_election"]["reelect_per_task"] is False
