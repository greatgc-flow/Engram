import json
import pytest
from pathlib import Path
import re
import os
import hub

class TestHubKeystone:

    def test_h1_consensus_reachable_with_gate_closed(self, ai_dir, capsys, monkeypatch):
        """consensus REACHABLE with cx gate-CLOSED: snapshot = {cc, ag} (N=2), both agree + proposer!=sole-agreer -> FINALIZES."""
        def mock_health(peer_id, *args, **kwargs):
            if peer_id == "cx": return "RED", {}
            return "GREEN", {}
        monkeypatch.setattr(hub, "_peer_effective_health", mock_health)
        
        hub.action_consensus_propose(ai_dir, "Test reachable", ["cc", "ag", "cx"], "cc")
        out = capsys.readouterr().out
        match = re.search(r"PROPOSE (r-\w+)", out)
        assert match is not None
        round_id = match.group(1)
        
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "ag", "agree", "test")
        
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "finalized"
        assert data["outcome"] == "unanimous"

    def test_h1_proposer_cannot_self_finalize(self, ai_dir, capsys, monkeypatch):
        """proposer cannot self-finalize: only proposer agrees -> NOT finalized."""
        monkeypatch.setattr(hub, "_peer_effective_health", lambda *args, **kwargs: ("GREEN", {}))
        
        hub.action_consensus_propose(ai_dir, "Test self-finalize", ["cc", "ag"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "ag", "abstain", "test")
        
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "escalated"
        assert data["outcome"] == "human_gate"

    def test_h1_n_less_than_2_escalates(self, ai_dir, capsys, monkeypatch):
        """N<2 (only 1 gate-OPEN voter) -> escalates to human, not finalize."""
        def mock_health(peer_id, *args, **kwargs):
            if peer_id in ("ag", "cx"): return "RED", {}
            return "GREEN", {}
        monkeypatch.setattr(hub, "_peer_effective_health", mock_health)
        
        hub.action_consensus_propose(ai_dir, "Test N<2", ["cc", "ag", "cx"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "escalated"
        assert data["outcome"] == "human_gate"

    def test_h1_mid_round_gate_closure_blocks(self, ai_dir, capsys, monkeypatch):
        """mid-round gate closure of an un-voted snapshot voter -> blocks + escalates (no silent pass)."""
        healths = {"cc": "GREEN", "ag": "GREEN", "cx": "GREEN"}
        def mock_health(peer_id, *args, **kwargs):
            return healths.get(peer_id, "GREEN"), {}
        monkeypatch.setattr(hub, "_peer_effective_health", mock_health)
        
        hub.action_consensus_propose(ai_dir, "Test mid-round closure", ["cc", "ag", "cx"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        
        # Now ag's gate closes
        healths["ag"] = "RED"
        
        # cx votes, should trigger mid-round closure escalation because ag is now RED and hasn't voted
        hub.action_consensus_vote(ai_dir, round_id, "cx", "agree", "test")
        
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "escalated"
        assert data["outcome"] == "human_gate"

    def test_h1_disagree_still_blocks(self, ai_dir, capsys, monkeypatch):
        """disagree still blocks (human_gate)."""
        monkeypatch.setattr(hub, "_peer_effective_health", lambda *args, **kwargs: ("GREEN", {}))
        
        hub.action_consensus_propose(ai_dir, "Test disagree blocks", ["cc", "ag"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "ag", "disagree", "test")
        
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "escalated"
        assert data["outcome"] == "human_gate"

    def test_d1_invariant_writer(self, ai_dir, capsys, monkeypatch):
        """D-1: a CONSENSUS_OK proposal actually appends a new INV-NN row to a temp 10-invariants.md"""
        # Create a mock 10-invariants.md
        docs_dir = ai_dir.parent / "docs-v2"
        docs_dir.mkdir(parents=True, exist_ok=True)
        inv_file = docs_dir / "10-invariants.md"
        inv_file.write_text("| ID | Rule |\n|---|---|\n| INV-01 | Old rule |\n", encoding="utf-8")
        
        def mock_health(peer_id, *args, **kwargs):
            if peer_id == "cx": return "RED", {}
            return "GREEN", {}
        monkeypatch.setattr(hub, "_peer_effective_health", mock_health)
        
        # Mock _proposals_dir to write inside ai_dir / "proposals" instead of the real sys dir
        prop_dir = ai_dir / "proposals"
        prop_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(hub, "_proposals_dir", lambda: prop_dir)
        
        hub.action_proposal_add(ai_dir, "D1 Writer Test", "cc", "high", "Testing D1", "New rule content")
        out = capsys.readouterr().out
        match = re.search(r"PROPOSAL-ADD (\d{8}-[\w-]+-\d+)", out)
        assert match is not None
        proposal_id = match.group(1)
        
        hub.action_proposal_vote(ai_dir, proposal_id, "cc", "agree", "test")
        hub.action_proposal_vote(ai_dir, proposal_id, "ag", "agree", "test")
        
        out = capsys.readouterr().out
        assert "CONSENSUS_OK" in out
        
        content = inv_file.read_text(encoding="utf-8")
        assert "INV-02" in content
        assert "New rule content" in content
        assert f"[Proposal {proposal_id}]" in content
        
        # Test idempotency
        hub.action_proposal_vote(ai_dir, proposal_id, "cc", "agree", "test")
        content2 = inv_file.read_text(encoding="utf-8")
        assert content == content2
