"""Consensus voter eligibility vs STALE health (_healthy_peer allow_stale).

A peer idling to HEALTH=STALE (aged bookkeeping, not RED) must remain a valid
consensus VOTER, or a long session silently empties the voter list and consensus
cannot run. Routing keeps the strict default (STALE ineligible).
"""
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
    return {"round_id": "r-x", "proposed_by": "cc", "voters": ["cc", "ag", "cx"],
            "votes": {"cc": {"vote": "agree"}, "ag": {"vote": "agree"}, "cx": {"vote": "agree"}}}


def test_decide_consensus_stale_voter_finalizes(monkeypatch, tmp_path):
    # Completes the r-34dc fix: a STALE voter must NOT force human_gate escalation;
    # a fully-agreed round finalizes normally.
    monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("STALE", {}))
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {"collab_rate": {"current": 10}})
    data = _all_agree_round()
    assert hub._decide_consensus(tmp_path, data) is True
    assert (data["status"], data["outcome"]) == ("finalized", "unanimous")


def test_decide_consensus_red_voter_escalates(monkeypatch, tmp_path):
    # A RED voter (genuinely unavailable) still forces human_gate escalation.
    monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("RED", {}))
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {"collab_rate": {"current": 10}})
    data = _all_agree_round()
    assert hub._decide_consensus(tmp_path, data) is True
    assert data["status"] == "escalated"
