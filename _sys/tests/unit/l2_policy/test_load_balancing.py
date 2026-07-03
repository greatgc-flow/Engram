import pytest
import sys
from pathlib import Path

# Add core/ to sys.path so we can import hub and snapshot (r-f291 W4)
root_dir = Path(__file__).resolve().parent.parent.parent.parent
core_dir = root_dir / "core"
cli_dir = root_dir / "cli"
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))
if str(cli_dir) not in sys.path:
    sys.path.insert(0, str(cli_dir))

import hub
import snapshot

def test_matching_peers_quota_margin_bonus(monkeypatch):
    """
    Test that _matching_peers properly calculates quota_margin_bonus based on diag.py telemetry
    and handles AP-20 monopoly guard.
    """
    # 1. Mock _load_protocol_cfg and _load_orchestration
    def mock_proto_cfg():
        return {
            "leader_election": {
                "election_score": {
                    "capability_match_max": 10,
                    "health_score": {"GREEN": 3, "YELLOW": 1, "STALE": -5, "RED": "blocked"},
                    "continuity_bonus_max": 2,
                }
            }
        }
    monkeypatch.setattr(hub, "_load_protocol_cfg", mock_proto_cfg)

    def mock_orch():
        return {
            "hub_nodes": [
                {"node_id": "peerA", "enabled": True, "aliases": []},
                {"node_id": "peerB", "enabled": True, "aliases": []},
                {"node_id": "peerC", "enabled": True, "aliases": []},
                {"node_id": "peerD", "enabled": True, "aliases": []},
                {"node_id": "peerE", "enabled": True, "aliases": []},
            ],
            "roles_registry": {}
        }
    monkeypatch.setattr(hub, "_load_orchestration", mock_orch)

    # 2. Mock _peer_effective_health
    def mock_peer_health(node_id):
        # All GREEN with some basic profile
        h_data = {
            "profile": {
                "capabilities": ["general"],
                "cost_tier": "mid",
                "tier": "mid"
            },
            "session_health": {"session_count_today": 1}
        }
        return "GREEN", h_data
    monkeypatch.setattr(hub, "_peer_effective_health", mock_peer_health)
    
    # 3. Mock state.json read
    monkeypatch.setattr(hub, "_read_json", lambda p: {})

    # 4. Mock snapshot.collect_snapshot
    def mock_collect_snapshot(use_cache=False, **_kw):
        return {
            "peers": [
                {"peer": "peerA", "domains": {"quota": {"buckets": [{"used_frac": 0.05}]}}}, # 95% remaining => +3
                {"peer": "peerB", "domains": {"quota": {"buckets": [{"used_frac": 0.20}]}}}, # 80% remaining => +2
                {"peer": "peerC", "domains": {"quota": {"buckets": [{"used_frac": 0.40}]}}}, # 60% remaining => +1
                {"peer": "peerD", "domains": {"quota": {"buckets": [{"used_frac": 0.80}]}}}, # 20% remaining => -1
                {"peer": "peerE", "domains": {"quota": {"buckets": [{"used_frac": 0.95}]}}}, # 5% remaining => -3
                # We need one exhausted peer to test HARD_CLOSED (0% remaining => excluded)
            ]
        }
    monkeypatch.setattr(snapshot, "collect_snapshot", mock_collect_snapshot)
    
    # Actually, we need to mock find_ai_root to not fail
    monkeypatch.setattr(hub, "find_ai_root", lambda: Path("mocked"))

    matches = hub._matching_peers("general", "mid")
    
    scores = {m["node_id"]: m["score"] for m in matches}
    
    # Base score = 10 (capability) + 3 (health_score GREEN) - 1 (cost penalty mid) = 12.
    assert scores["peerA"] == 12 + 3
    assert scores["peerB"] == 12 + 2
    assert scores["peerC"] == 12 + 1
    assert scores["peerD"] == 12 - 1
    assert scores["peerE"] == 12 - 3

def test_matching_peers_exhausted(monkeypatch):
    # Same mocks, but peer is exhausted
    def mock_proto_cfg():
        return {"leader_election": {"election_score": {"capability_match_max": 10, "health_score": {"GREEN": 3}}}}
    monkeypatch.setattr(hub, "_load_protocol_cfg", mock_proto_cfg)

    def mock_orch():
        return {
            "hub_nodes": [
                {"node_id": "peerA", "enabled": True},
            ]
        }
    monkeypatch.setattr(hub, "_load_orchestration", mock_orch)

    monkeypatch.setattr(hub, "_peer_effective_health", lambda node_id: ("GREEN", {"profile": {"capabilities": ["general"]}, "session_health": {"session_count_today": 1}}))
    monkeypatch.setattr(hub, "_read_json", lambda p: {})
    
    def mock_collect_snapshot(use_cache=False, **_kw):
        return {
            "peers": [
                {"peer": "peerA", "domains": {"quota": {"buckets": [{"used_frac": 1.0}]}}}, # 0% remaining => HARD_CLOSED
            ]
        }
    monkeypatch.setattr(snapshot, "collect_snapshot", mock_collect_snapshot)
    monkeypatch.setattr(hub, "find_ai_root", lambda: Path("mocked"))

    matches = hub._matching_peers("general", "mid")
    # Should be excluded
    assert len(matches) == 0

def test_matching_peers_ap20_penalty(monkeypatch):
    def mock_proto_cfg():
        return {"leader_election": {"election_score": {"capability_match_max": 10, "health_score": {"GREEN": 3}}}}
    monkeypatch.setattr(hub, "_load_protocol_cfg", mock_proto_cfg)

    def mock_orch():
        return {
            "hub_nodes": [{"node_id": "peerA", "enabled": True, "aliases": []}],
            "roles_registry": {}
        }
    monkeypatch.setattr(hub, "_load_orchestration", mock_orch)

    monkeypatch.setattr(hub, "_peer_effective_health", lambda node_id: ("GREEN", {"profile": {"capabilities": ["general"], "cost_tier": "mid"}, "session_health": {"session_count_today": 1}}))
    
    # Mock AP-20 history: peerA was leader twice
    monkeypatch.setattr(hub, "_read_json", lambda p: {"coordinator_history": [{"peer": "peerA"}, {"peer": "peerA"}]})
    monkeypatch.setattr(snapshot, "collect_snapshot", lambda use_cache=False, **_kw: {"peers": [{"peer": "peerA", "domains": {"quota": {"buckets": [{"used_frac": 0.50}]}}}]})
    monkeypatch.setattr(hub, "find_ai_root", lambda: Path("mocked"))

    matches = hub._matching_peers("general", "mid")
    # Base score = 10 + 3 - 1 = 12
    # Quota Margin Bonus (50% remaining) = +1
    # AP-20 Penalty = -2
    # Total = 11
    assert matches[0]["score"] == 11


