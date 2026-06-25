"""Tests for hub_health.py — PeerHealthState and HealthReader."""
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))

import hub_health
from hub_health import PeerHealthState, HealthReader, _load_json


# ── _load_json ────────────────────────────────────────────────────────────────

class TestLoadJson:
    def test_loads_valid_json(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        result = _load_json(f)
        assert result == {"key": "value"}

    def test_returns_empty_dict_on_missing_file(self, tmp_path):
        result = _load_json(tmp_path / "missing.json")
        assert result == {}

    def test_returns_empty_dict_on_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{ not valid json }", encoding="utf-8")
        result = _load_json(f)
        assert result == {}


# ── PeerHealthState ───────────────────────────────────────────────────────────

def _make_health_data(status="GREEN", jsonl_mb=10.0, failures=0,
                       entrypoint_ok=True, authenticated=True):
    return {
        "context_health": {
            "status": status,
            "jsonl_mb": jsonl_mb,
            "checked_at": "2026-06-18T00:00:00Z",
        },
        "session_health": {"consecutive_failures": failures},
        "availability": {
            "entrypoint_ok": entrypoint_ok,
            "authenticated": authenticated,
        }
    }


class TestPeerHealthState:
    def test_green_gate_is_open(self):
        state = PeerHealthState("gc", _make_health_data("GREEN"))
        assert state.context_status == "GREEN"
        assert state.gate_open is True

    def test_yellow_gate_is_open(self):
        state = PeerHealthState("gc", _make_health_data("YELLOW"))
        assert state.gate_open is True

    def test_red_gate_is_closed(self):
        state = PeerHealthState("cx", _make_health_data("RED"))
        assert state.gate_open is False

    def test_unknown_gate_is_closed(self):
        state = PeerHealthState("ag", _make_health_data("UNKNOWN"))
        assert state.gate_open is False

    def test_stale_gate_is_closed(self):
        state = PeerHealthState("cc", _make_health_data("STALE"))
        assert state.gate_open is False

    def test_consecutive_failures_read(self):
        state = PeerHealthState("gc", _make_health_data(failures=3))
        assert state.consecutive_failures == 3

    def test_jsonl_mb_read(self):
        state = PeerHealthState("gc", _make_health_data(jsonl_mb=42.5))
        assert state.jsonl_mb == pytest.approx(42.5)

    def test_entrypoint_false_propagates(self):
        state = PeerHealthState("cx", _make_health_data(entrypoint_ok=False))
        assert state.entrypoint_ok is False

    def test_authenticated_false_propagates(self):
        state = PeerHealthState("cx", _make_health_data(authenticated=False))
        assert state.authenticated is False

    def test_to_dict_keys(self):
        state = PeerHealthState("gc", _make_health_data())
        d = state.to_dict()
        assert "peer_id" in d
        assert "context_status" in d
        assert "gate" in d
        assert "jsonl_mb" in d
        assert "consecutive_failures" in d
        assert "entrypoint_ok" in d
        assert "authenticated" in d
        assert "checked_at" in d

    def test_to_dict_gate_open_value(self):
        state = PeerHealthState("gc", _make_health_data("GREEN"))
        assert state.to_dict()["gate"] == "open"

    def test_to_dict_gate_closed_value(self):
        state = PeerHealthState("cx", _make_health_data("RED"))
        assert state.to_dict()["gate"] == "closed"

    def test_empty_data_returns_unknown(self):
        state = PeerHealthState("xx", {})
        assert state.context_status == "UNKNOWN"
        assert state.gate_open is False

    def test_status_is_uppercased(self):
        data = {"context_health": {"status": "green"}}
        state = PeerHealthState("gc", data)
        assert state.context_status == "GREEN"

    def test_repr_contains_peer_and_status(self):
        state = PeerHealthState("gc", _make_health_data("GREEN"))
        r = repr(state)
        assert "gc" in r
        assert "GREEN" in r


# ── HealthReader ──────────────────────────────────────────────────────────────

class TestHealthReader:
    def _make_reader(self, tmp_path, peer_configs: dict):
        """Set up a HealthReader with fake peer dirs + health.json files."""
        peer_dirs = {}
        for peer_id, data in peer_configs.items():
            peer_dir = tmp_path / peer_id
            peer_dir.mkdir()
            (peer_dir / "health.json").write_text(json.dumps(data), encoding="utf-8")
            peer_dirs[peer_id] = peer_dir

        reader = HealthReader.__new__(HealthReader)
        reader._peer_dirs = peer_dirs
        return reader

    def test_get_peer_state_returns_typed_state(self, tmp_path):
        reader = self._make_reader(tmp_path, {
            "gemini": _make_health_data("GREEN"),
        })
        state = reader.get_peer_state("gemini")
        assert state is not None
        assert isinstance(state, PeerHealthState)
        assert state.context_status == "GREEN"

    def test_get_peer_state_unknown_returns_none(self, tmp_path):
        reader = self._make_reader(tmp_path, {})
        state = reader.get_peer_state("doesnotexist")
        assert state is None

    def test_all_states_returns_all_peers(self, tmp_path):
        reader = self._make_reader(tmp_path, {
            "gemini": _make_health_data("GREEN"),
            "codex": _make_health_data("RED"),
        })
        states = reader.all_states()
        assert "gemini" in states
        assert "codex" in states
        assert len(states) == 2

    def test_eligible_peers_includes_green(self, tmp_path):
        reader = self._make_reader(tmp_path, {
            "gemini": _make_health_data("GREEN"),
            "codex": _make_health_data("RED"),
        })
        eligible = reader.eligible_peers()
        assert "gemini" in eligible
        assert "codex" not in eligible

    def test_eligible_peers_includes_yellow(self, tmp_path):
        reader = self._make_reader(tmp_path, {
            "gemini": _make_health_data("YELLOW"),
        })
        eligible = reader.eligible_peers()
        assert "gemini" in eligible

    def test_eligible_peers_require_green_excludes_yellow(self, tmp_path):
        reader = self._make_reader(tmp_path, {
            "gemini": _make_health_data("YELLOW"),
            "claude": _make_health_data("GREEN"),
        })
        green_only = reader.eligible_peers(require_green=True)
        assert "gemini" not in green_only
        assert "claude" in green_only

    def test_eligible_peers_excludes_bad_entrypoint(self, tmp_path):
        reader = self._make_reader(tmp_path, {
            "gemini": _make_health_data("GREEN", entrypoint_ok=False),
        })
        eligible = reader.eligible_peers()
        assert "gemini" not in eligible

    def test_summary_structure(self, tmp_path):
        reader = self._make_reader(tmp_path, {
            "gemini": _make_health_data("GREEN"),
        })
        summary = reader.summary()
        assert "peers" in summary
        assert "eligible" in summary
        assert "ts" in summary
        assert "gemini" in summary["peers"]

    def test_missing_health_json_returns_empty_state(self, tmp_path):
        peer_dir = tmp_path / "ghost"
        peer_dir.mkdir()
        reader = HealthReader.__new__(HealthReader)
        reader._peer_dirs = {"ghost": peer_dir}
        state = reader.get_peer_state("ghost")
        assert state is not None
        assert state.context_status == "UNKNOWN"

    def test_no_peers_returns_empty(self, tmp_path):
        reader = self._make_reader(tmp_path, {})
        assert reader.all_states() == {}
        assert reader.eligible_peers() == []


def test_peer_health_read_is_nonmutating(tmp_path, monkeypatch):
    """P0.1: _peer_effective_health with recover=False does not auto-recover STALE peers."""
    import hub
    ai_root = tmp_path / "_sys" / "ai"
    ai_root.mkdir(parents=True)
    peer_id = "testpeer"
    peer_sys = tmp_path / "_sys" / peer_id
    peer_sys.mkdir(parents=True)
    
    # Mock paths
    monkeypatch.setattr(hub.hub_peer, "resolve_peer_sys_dir", lambda p: peer_id if p == peer_id else None)
    monkeypatch.setattr(hub, "_peer_sys_dir", lambda pid: peer_sys)
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {})
    
    health_file = peer_sys / "health.json"
    from datetime import datetime, timedelta, timezone
    stale_time = (datetime.now() - timedelta(minutes=130)).strftime("%Y%m%dT%H%M%S")
    health_data = {
        "context_health": {
            "status": "GREEN",
            "checked_at": stale_time
        }
    }
    health_file.write_text(json.dumps(health_data), encoding="utf-8")
    
    mtime_before = health_file.stat().st_mtime
    bytes_before = health_file.read_bytes()
    
    # Act
    status, data = hub._peer_effective_health(peer_id, ai_root=ai_root)
    
    # Assert
    assert status == "STALE"
    mtime_after = health_file.stat().st_mtime
    bytes_after = health_file.read_bytes()
    assert mtime_before == mtime_after
    assert bytes_before == bytes_after


def test_action_health_check_default_targets(capsys, monkeypatch):
    """Blocker 1: health-check defaults to enabled orchestration node_ids (cc/ag/cx), omits gc."""
    import hub
    
    monkeypatch.setattr(hub, "_load_orchestration", lambda: {"hub_nodes": [
        {"node_id": "cc", "type": "peer", "enabled": True},
        {"node_id": "ag", "type": "peer", "enabled": True},
        {"node_id": "cx", "type": "peer", "enabled": True},
        {"node_id": "gc", "type": "peer", "enabled": False},
    ]})
    
    # Provide fake peers data so we don't depend on actual peers.json
    monkeypatch.setattr(hub, "_load_peers", lambda: {"peers": {"claude": {}, "gemini": {}, "codex": {}, "antigravity": {}}})
    monkeypatch.setattr(hub.hub_peer, "resolve_peer_sys_dir", lambda peer: {"cc":"claude","ag":"antigravity","cx":"codex","gc":"gemini"}.get(peer, peer))
    
    # Prevent actual _peer_effective_health execution which requires physical files
    monkeypatch.setattr(hub, "_peer_effective_health", lambda pid, ai_root=None, recover=False: ("GREEN", {}))
    
    # Create fake health.json for each peer directory so they aren't UNKNOWN
    import pathlib
    base_dir = pathlib.Path(__file__).parent.parent.parent.parent / "_sys"
    
    # Mocking Path.exists and read_text for the health paths
    original_exists = pathlib.Path.exists
    original_read_text = pathlib.Path.read_text
    
    def fake_exists(path_obj):
        if path_obj.name == "health.json":
            return True
        return original_exists(path_obj)
        
    def fake_read_text(path_obj, encoding=None):
        if path_obj.name == "health.json":
            return json.dumps({"context_health": {"status": "GREEN", "jsonl_mb": 1.0}})
        return original_read_text(path_obj, encoding=encoding)
        
    monkeypatch.setattr(pathlib.Path, "exists", fake_exists)
    monkeypatch.setattr(pathlib.Path, "read_text", fake_read_text)

    hub.action_health_check()
    
    captured = capsys.readouterr().out
    
    # Ensure cc, ag, cx are listed and gc is omitted
    assert "cc=" in captured
    assert "ag=" in captured
    assert "cx=" in captured
    assert "gc=" not in captured


def test_hub_health_eligible_excludes_disabled_gemini(monkeypatch):
    """Blocker 2: hub_health.py --eligible respects orchestration ENABLED roots and resolves via node_ids."""
    monkeypatch.setattr(hub_health, "_load_json", lambda path: {"hub_nodes": [
        {"node_id": "cc", "type": "peer", "enabled": True},
        {"node_id": "ag", "type": "peer", "enabled": True},
        {"node_id": "cx", "type": "peer", "enabled": True},
        {"node_id": "gc", "type": "peer", "enabled": False},
    ]} if path.name == "orchestration.json" else {"peers": {"claude": {}, "gemini": {}, "codex": {}, "antigravity": {}}})
    
    monkeypatch.setattr(hub_health, "resolve_peer_sys_dir", lambda peer: {"cc":"claude","ag":"antigravity","cx":"codex","gc":"gemini"}.get(peer, peer))
    
    import pathlib
    original_is_dir = pathlib.Path.is_dir
    def fake_is_dir(path_obj):
        if path_obj.name in ["claude", "antigravity", "codex", "gemini"]:
            return True
        return original_is_dir(path_obj)
    monkeypatch.setattr(pathlib.Path, "is_dir", fake_is_dir)
    
    # Force _load_json within hub_health to return a GREEN state for all health.json to isolate the test to filtering logic
    original_load_json = hub_health._load_json
    def fake_load_json(path_obj):
        if path_obj.name == "health.json":
            return {
                "context_health": {"status": "GREEN", "checked_at": "now"},
                "session_health": {"consecutive_failures": 0},
                "availability": {"entrypoint_ok": True, "authenticated": True}
            }
        return original_load_json(path_obj)
    monkeypatch.setattr(hub_health, "_load_json", fake_load_json)

    reader = HealthReader()
    eligible = reader.eligible_peers()
    
    # cc, ag, cx should be eligible
    assert "cc" in eligible
    assert "ag" in eligible
    assert "cx" in eligible
    
    # gemini (installation name) and gc (disabled) should NOT be eligible
    assert "gc" not in eligible
    assert "gemini" not in eligible
