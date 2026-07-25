"""
Unit and Integration Tests for Cluster C6 (Consensus Voter-Health Live-Recheck & Vote Immutability)

Covers:
  1. Quorum Snapshot Capture: captured_at, collab_rate, decision_rule, required_voters, excluded_voters, observations.
  2. Mid-Round Peer Health Immunity: cast agree stands even if voter later goes RED.
  3. Mid-Round Config Stability: snapshotted collab_rate is immutable mid-ballot.
  4. Uncast Required Voter Health Change: uncast voter going RED does not force immediate escalation.
  5. Proposal RED Peer Exclusion: peer RED at proposal time excluded from required_voters; survivors finalize.
  6. Legacy Round Protection: missing quorum_snapshot fails closed to human_gate.
  7. Direct Vote Immutability: identical resubmit = no-op; differing resubmit = VOTE_ALREADY_CAST error.
  8. Broker Merge Vote Immutability: identical resubmit = no-op (None); differing resubmit = rejected (None).
  9. Piggyback Maintenance Sweep: action_init_session & _action_ask_inner trigger consensus sweep.
"""

import json
from pathlib import Path
import sys
import pytest

SYS_DIR = Path(__file__).parent.parent.parent.resolve()
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

import core.hub as hub


class TestC6QuorumSnapshot:
    """Tests for quorum_snapshot creation and eligibility freezing."""

    def test_propose_captures_quorum_snapshot(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        def _mock_health(peer_id, ai_root=None):
            if peer_id == "cx":
                return ("RED", {})
            return ("GREEN", {})

        monkeypatch.setattr(hub, "_peer_effective_health", _mock_health)
        monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {"collab_rate": {"current": 10}})

        hub.action_consensus_propose(ai_root, "test-subject", ["cc", "ag", "cx"], "cc")

        rounds = list((ai_root / "consensus").glob("*.json"))
        assert len(rounds) == 1
        data = json.loads(rounds[0].read_text("utf-8"))

        assert "quorum_snapshot" in data
        snap = data["quorum_snapshot"]
        assert snap["collab_rate"] == 10
        assert snap["decision_rule"] == "unanimous"
        assert set(snap["required_voters"]) == {"cc", "ag"}
        assert "cx" in snap["excluded_voters"]
        assert snap["excluded_voters"]["cx"]["reason"] == "health_red"
        assert snap["observations"]["cc"]["eligible"] is True
        assert snap["observations"]["cx"]["eligible"] is False

    def test_propose_red_peer_excluded_and_survivors_finalize(self, monkeypatch, tmp_path):
        """A peer RED at proposal time is excluded from required_voters; survivors finalize unanimously."""
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("RED", {}) if v == "cx" else ("GREEN", {}))
        monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {"collab_rate": {"current": 10}})

        hub.action_consensus_propose(ai_root, "test-red-propose", ["cc", "ag", "cx"], "cc")

        rounds = list((ai_root / "consensus").glob("*.json"))
        rpath = rounds[0]
        rid = json.loads(rpath.read_text("utf-8"))["round_id"]

        hub.action_consensus_vote(ai_root, rid, "cc", "agree", "ok")
        hub.action_consensus_vote(ai_root, rid, "ag", "agree", "ok")

        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "finalized"
        assert data["outcome"] == "unanimous"

    def test_voter_going_red_mid_round_does_not_invalidate_cast_agree(self, monkeypatch, tmp_path):
        """CRITICAL C6 BUG FIX: A voter casting agree while healthy stays valid even if peer goes RED later."""
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        # Proposal time: all green
        monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("GREEN", {}))
        monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {"collab_rate": {"current": 10}})

        hub.action_consensus_propose(ai_root, "test-midround-red", ["cc", "ag"], "cc")

        rounds = list((ai_root / "consensus").glob("*.json"))
        rpath = rounds[0]
        data = json.loads(rpath.read_text("utf-8"))
        rid = data["round_id"]

        # cc votes agree
        hub.action_consensus_vote(ai_root, rid, "cc", "agree", "LGTM")

        # Now ag turns RED before voting
        monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("RED", {}))

        # ag votes agree (or host merges vote)
        hub.action_consensus_vote(ai_root, rid, "ag", "agree", "LGTM")

        # Round MUST be finalized unanimous, NOT escalated human_gate
        data_after = json.loads(rpath.read_text("utf-8"))
        assert data_after["status"] == "finalized"
        assert data_after["outcome"] == "unanimous"

    def test_mid_round_collab_rate_change_is_ignored(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        collab_cfg = {"collab_rate": {"current": 0}}
        monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("GREEN", {}))
        monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: collab_cfg)

        hub.action_consensus_propose(ai_root, "test-collab-change", ["cc", "ag", "cx"], "cc")

        rounds = list((ai_root / "consensus").glob("*.json"))
        rpath = rounds[0]
        data = json.loads(rpath.read_text("utf-8"))
        rid = data["round_id"]

        # Collab rate changes to 10 mid-round
        collab_cfg["collab_rate"]["current"] = 10

        # Votes: cc agrees, ag agrees (non-proposer agree), cx abstains.
        # Under snapshotted collab_rate=0: mix of agree+abstain finalizes with "majority".
        # Under live collab_rate=10: mix of agree+abstain would escalate with "human_gate_unanimity_failed".
        hub.action_consensus_vote(ai_root, rid, "cc", "agree", "ok")
        hub.action_consensus_vote(ai_root, rid, "ag", "agree", "ok")
        hub.action_consensus_vote(ai_root, rid, "cx", "abstain", "ok")

        data_after = json.loads(rpath.read_text("utf-8"))
        assert data_after["status"] == "finalized"
        assert data_after["outcome"] == "majority"

    def test_uncast_required_voter_going_red_waits_does_not_escalate_immediately(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("GREEN", {}))
        hub.action_consensus_propose(ai_root, "test-uncast-red", ["cc", "ag", "cx"], "cc")

        rounds = list((ai_root / "consensus").glob("*.json"))
        rpath = rounds[0]
        data = json.loads(rpath.read_text("utf-8"))
        rid = data["round_id"]

        # cc votes agree
        hub.action_consensus_vote(ai_root, rid, "cc", "agree", "ok")

        # cx turns RED mid-round
        monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("RED", {}) if v == "cx" else ("GREEN", {}))

        # _decide_consensus called again (e.g. by check)
        data_mid = json.loads(rpath.read_text("utf-8"))
        closed = hub._decide_consensus(ai_root, data_mid)

        # MUST NOT be closed yet (round stays in voting waiting for ag/cx or sweep)
        assert closed is False
        assert data_mid["status"] == "voting"

    def test_legacy_round_without_quorum_snapshot_fails_closed(self, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        legacy_data = {
            "round_id": "r-legacy",
            "subject": "old-round",
            "proposed_by": "cc",
            "status": "voting",
            "voters": ["cc", "ag"],
            "votes": {"cc": {"vote": "agree"}, "ag": {"vote": "agree"}},
        }

        closed = hub._decide_consensus(ai_root, legacy_data)
        assert closed is True
        assert legacy_data["status"] == "escalated"
        assert legacy_data["outcome"] == "human_gate"


class TestC6VoteImmutability:
    """Tests for vote immutability (direct & broker merge)."""

    def test_direct_vote_identical_resubmit_is_idempotent_noop(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("GREEN", {}))
        hub.action_consensus_propose(ai_root, "test-immutability-direct", ["cc", "ag", "cx"], "cc")

        rounds = list((ai_root / "consensus").glob("*.json"))
        rpath = rounds[0]
        rid = json.loads(rpath.read_text("utf-8"))["round_id"]

        # First vote
        hub.action_consensus_vote(ai_root, rid, "ag", "agree", "Reason 1")

        # Identical resubmit should not raise SystemExit
        hub.action_consensus_vote(ai_root, rid, "ag", "agree", "Reason 1")

        data = json.loads(rpath.read_text("utf-8"))
        assert data["votes"]["ag"]["vote"] == "agree"
        assert data["votes"]["ag"]["reason"] == "Reason 1"

    def test_direct_vote_differing_resubmit_raises_vote_already_cast(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("GREEN", {}))
        hub.action_consensus_propose(ai_root, "test-immutability-diff", ["cc", "ag", "cx"], "cc")

        rounds = list((ai_root / "consensus").glob("*.json"))
        rpath = rounds[0]
        rid = json.loads(rpath.read_text("utf-8"))["round_id"]

        hub.action_consensus_vote(ai_root, rid, "ag", "agree", "Reason 1")

        with pytest.raises(SystemExit) as exc_info:
            hub.action_consensus_vote(ai_root, rid, "ag", "disagree", "Changed my mind")

        assert exc_info.value.code == 1

    def test_broker_merge_identical_resubmit_returns_none(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("GREEN", {}))
        hub.action_consensus_propose(ai_root, "test-broker-noop", ["cc", "ag", "cx"], "cc")

        rounds = list((ai_root / "consensus").glob("*.json"))
        rpath = rounds[0]

        # First merge
        vote1 = {"voter": "ag", "vote": "agree", "reason": "R1"}
        res1 = hub._apply_vote_merge(ai_root, rpath, vote1)
        assert res1 is None  # round not closed yet, but vote applied

        # Second identical merge
        res2 = hub._apply_vote_merge(ai_root, rpath, vote1)
        assert res2 is None

    def test_broker_merge_differing_resubmit_returns_none_rejects(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        monkeypatch.setattr(hub, "_peer_effective_health", lambda v, ai_root=None: ("GREEN", {}))
        hub.action_consensus_propose(ai_root, "test-broker-diff", ["cc", "ag", "cx"], "cc")

        rounds = list((ai_root / "consensus").glob("*.json"))
        rpath = rounds[0]

        vote1 = {"voter": "ag", "vote": "agree", "reason": "R1"}
        hub._apply_vote_merge(ai_root, rpath, vote1)

        vote2 = {"voter": "ag", "vote": "disagree", "reason": "R2"}
        res = hub._apply_vote_merge(ai_root, rpath, vote2)

        assert res is None
        data = json.loads(rpath.read_text("utf-8"))
        assert data["votes"]["ag"]["vote"] == "agree"  # Original vote preserved


class TestC6MaintenanceSweepWiring:
    """Tests that piggyback entry points invoke action_consensus_sweep."""

    def test_init_session_invokes_consensus_sweep(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (ai_root / "state.json").write_text(json.dumps({"version": 1}), encoding="utf-8")

        sweep_called = []
        monkeypatch.setattr(hub, "action_consensus_sweep", lambda root: sweep_called.append(root))

        hub.action_init_session(ai_root, "cc")
        assert len(sweep_called) > 0
