"""Consensus voter eligibility vs STALE health (_healthy_peer allow_stale).

A peer idling to HEALTH=STALE (aged bookkeeping, not RED) must remain a valid
consensus VOTER, or a long session silently empties the voter list and consensus
cannot run. Routing keeps the strict default (STALE ineligible).
"""
import json
import sys
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub  # noqa: E402


def _fake_health(status, gate_open=True):
    return lambda peer_id, ai_root=None: (status, {"availability": {"gate_open": gate_open}})


# "testpeer" is not in orchestration, so the profile-gate branch is skipped.
def test_stale_excluded_for_routing_included_for_voting(monkeypatch):
    monkeypatch.setattr(hub, "_peer_effective_health", _fake_health("STALE"))
    assert hub._healthy_peer("testpeer") is False                       # routing default
    assert hub._healthy_peer("testpeer", allow_stale=True) is True      # consensus voting


def test_red_excluded_in_both_modes(monkeypatch):
    monkeypatch.setattr(hub, "_peer_effective_health", _fake_health("RED"))
    assert hub._healthy_peer("testpeer") is False
    assert hub._healthy_peer("testpeer", allow_stale=True) is False


def test_green_included_in_both_modes(monkeypatch):
    monkeypatch.setattr(hub, "_peer_effective_health", _fake_health("GREEN"))
    assert hub._healthy_peer("testpeer") is True
    assert hub._healthy_peer("testpeer", allow_stale=True) is True


def test_closed_gate_excluded_even_when_stale_allowed(monkeypatch):
    monkeypatch.setattr(hub, "_peer_effective_health", _fake_health("STALE", gate_open=False))
    assert hub._healthy_peer("testpeer", allow_stale=True) is False


def _all_agree_round():
    return {
        "round_id": "r-x",
        "proposed_by": "cc",
        "voters": ["cc", "ag", "cx"],
        "votes": {"cc": {"vote": "agree"}, "ag": {"vote": "agree"}, "cx": {"vote": "agree"}},
        "quorum_snapshot": {
            "captured_at": "2026-07-25T10:00:00+09:00",
            "collab_rate": 10,
            "decision_rule": "unanimous",
            "required_voters": ["cc", "ag", "cx"],
            "excluded_voters": {},
            "observations": {"cc": {"status": "GREEN", "eligible": True}, "ag": {"status": "GREEN", "eligible": True}, "cx": {"status": "GREEN", "eligible": True}},
        }
    }


def test_decide_consensus_stale_voter_finalizes(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("STALE", {}))
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {"collab_rate": {"current": 10}})
    data = _all_agree_round()
    assert hub._decide_consensus(tmp_path, data) is True
    assert (data["status"], data["outcome"]) == ("finalized", "unanimous")


def test_decide_consensus_legacy_round_fails_closed(monkeypatch, tmp_path):
    # Legacy round without quorum_snapshot field fails CLOSED to human_gate
    data = {"round_id": "r-legacy", "proposed_by": "cc", "voters": ["cc", "ag", "cx"],
            "votes": {"cc": {"vote": "agree"}, "ag": {"vote": "agree"}, "cx": {"vote": "agree"}}}
    assert hub._decide_consensus(tmp_path, data) is True
    assert (data["status"], data["outcome"]) == ("escalated", "human_gate")


def test_propose_no_longer_drops_red_peers_from_voter_snapshot(monkeypatch, tmp_path):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("RED", {}))
    hub.action_consensus_propose(ai_root, "subj", ["cc", "ag", "cx"], "cc")
    rounds = list((ai_root / "consensus").glob("*.json"))
    assert len(rounds) == 1
    data = json.loads(rounds[0].read_text("utf-8"))
    assert set(data["voters"]) == {"cc", "ag", "cx"}  # RED peer (cx) NOT dropped from voters
    assert "quorum_snapshot" in data
    assert data["quorum_snapshot"]["required_voters"] == []
    assert set(data["quorum_snapshot"]["excluded_voters"]) == {"cc", "ag", "cx"}
