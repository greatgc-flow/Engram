"""
hub.py N-Node 합의(Consensus) 심화 테스트 — MECE 보완 (P1, P2, P3)
기권(Abstain), 에스컬레이션(Escalated), 동적 노드 확장 검증
"""
import json
import re
import pytest
from pathlib import Path
import hub

class TestConsensusAdvanced:
    """N-Node 합의 프로토콜 심화 시나리오."""
    
    @pytest.fixture(autouse=True)
    def mock_health(self, monkeypatch):
        monkeypatch.setattr(hub, "_peer_effective_health", lambda *args, **kwargs: ("GREEN", {}))

    def test_p1_dynamic_node_consensus(self, ai_dir, capsys):
        """노드 동적 확장 후 합의 과정 포함 검증."""
        # 1. 새 노드 n1 등록
        hub.action_register_node(ai_dir, "n1", 4, "sensor", "custom-cli", "-p,{query}", "session", 0)
        
        # 2. n1을 포함한 합의 제안
        hub.action_consensus_propose(ai_dir, "Add n1 to team", ["cc", "ca", "gc", "n1"], "cc")
        
        out = capsys.readouterr().out
        assert "PROPOSE" in out
        
        # round_id 추출
        import re
        match = re.search(r"PROPOSE (r-\w+)", out)
        round_id = match.group(1)
        
        # 3. 모든 노드 투표 (n1 포함)
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "ca", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "gc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "n1", "agree", "test")
        
        # 4. 결과 확인
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "finalized"
        assert data["outcome"] == "unanimous"

    def test_p2_abstain_finalization(self, ai_dir, capsys):
        """기권(Abstain)이 포함된 합의 종결 검증."""
        hub.action_consensus_propose(ai_dir, "Minor change", ["cc", "ca", "gc"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        # cc: agree, ca: abstain, gc: agree
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "ca", "abstain", "test")
        hub.action_consensus_vote(ai_dir, round_id, "gc", "agree", "test")
        
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        # 반대가 없으면 finalized
        assert data["status"] == "finalized"
        assert data["outcome"] == "abstain" # agree + abstain = abstain (not unanimous)

    def test_p2_pure_abstain_finalization(self, ai_dir, capsys):
        """전원 기권 시의 결과 검증."""
        hub.action_consensus_propose(ai_dir, "No opinion", ["cc", "ca", "gc"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        hub.action_consensus_vote(ai_dir, round_id, "cc", "abstain", "test")
        hub.action_consensus_vote(ai_dir, round_id, "ca", "abstain", "test")
        hub.action_consensus_vote(ai_dir, round_id, "gc", "abstain", "test")
        
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "finalized"
        assert data["outcome"] == "abstain"

    def test_p3_disagree_escalation(self, ai_dir, capsys):
        """단 1명이라도 반대 시 즉시 ESCALATED 전환 검증."""
        hub.action_consensus_propose(ai_dir, "Risky change", ["cc", "ca", "gc"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "ca", "disagree", "Too risky")
        hub.action_consensus_vote(ai_dir, round_id, "gc", "agree", "test")
        
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "escalated"
        assert data["outcome"] == "human_gate"

    def test_consensus_history_auto_recording(self, ai_dir, capsys):
        """합의 종결 시 handoff.md에 자동 기록되는지 검증."""
        # 세션 초기화 필수
        hub.action_init_session(ai_dir, "cc")
        hub.action_init_session(ai_dir, "gc")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        room_id = state["room_id"]
        
        hub.action_consensus_propose(ai_dir, "History test", ["cc", "ca", "gc"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "ca", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "gc", "agree", "test")
        
        handoff_path = ai_dir / "sessions" / room_id / "handoff.md"
        content = handoff_path.read_text("utf-8")
        assert "CONSENSUS_HISTORY" in content
        assert f"{round_id}: History test — FINALIZED" in content

    def test_consensus_emits_decision_capsule(self, ai_dir, capsys):
        """Finalized consensus must emit a machine-readable decision capsule."""
        hub.action_consensus_propose(ai_dir, "Capsule test", ["cc", "gc"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "gc", "agree", "test")
        
        capsule_path = ai_dir / "consensus" / f"{round_id}.capsule.json"
        assert capsule_path.exists(), "Decision capsule was not created"
        
        data = json.loads(capsule_path.read_text("utf-8"))
        assert data["round_id"] == round_id
        assert "approved_scope" in data
        assert "change_summary" in data
        assert "doc_targets" in data
        assert data["status"] == "finalized"

    def test_consensus_keystone_no_supermajority(self, ai_dir, capsys, monkeypatch):
        """P0.2: mid-round-closed round where active-but-not-all voters agree must escalate to human_gate (NOT finalize)."""
        # Propose with 3 voters
        hub.action_consensus_propose(ai_dir, "Supermajority test", ["cc", "gc", "cx"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        
        # Make cx STALE
        monkeypatch.setattr(hub, "_peer_effective_health", lambda pid, **kw: ("STALE", {}) if pid == "cx" else ("GREEN", {}))
        
        # gc votes and triggers mid_round_closed evaluation
        hub.action_consensus_vote(ai_dir, round_id, "gc", "agree", "test")
        
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "escalated"
        assert data["outcome"] == "human_gate"

    def test_consensus_finalize_requires_unanimous_gateopen_plus_nonproposer(self, ai_dir, capsys):
        """P0.2: all gate-OPEN voters agree + >=1 non-proposer -> finalized. proposer-only -> escalate."""
        # 1. Proposer only (N=1)
        hub.action_consensus_propose(ai_dir, "Proposer only", ["cc"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "escalated"
        assert data["outcome"] == "human_gate"

        # 2. All agree + >=1 nonproposer
        hub.action_consensus_propose(ai_dir, "Normal", ["cc", "gc"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "gc", "agree", "test")
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "finalized"
        assert data["outcome"] == "unanimous"

        # 3. Any disagree
        hub.action_consensus_propose(ai_dir, "Disagree", ["cc", "gc"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "test")
        hub.action_consensus_vote(ai_dir, round_id, "gc", "disagree", "test")
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "escalated"
        assert data["outcome"] == "human_gate"

    def test_consensus_sweep_escalates_on_timeout(self, ai_dir, capsys, monkeypatch):
        """P0.3: round stalled past timeout -> escalated/timeout."""
        hub.action_consensus_propose(ai_dir, "Timeout", ["cc", "gc"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        # Fake proposed_at to be older than timeout
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        from datetime import datetime, timedelta
        data["proposed_at"] = (datetime.now() - timedelta(minutes=40)).isoformat()
        rpath.write_text(json.dumps(data), "utf-8")
        
        hub.action_consensus_sweep(ai_dir, timeout_minutes=30)
        
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "escalated"
        assert data["outcome"] == "timeout"

    def test_consensus_sweep_ignores_fresh_rounds(self, ai_dir, capsys):
        """P0.3: round within window is untouched."""
        hub.action_consensus_propose(ai_dir, "Fresh", ["cc", "gc"], "cc")
        out = capsys.readouterr().out
        round_id = re.search(r"PROPOSE (r-\w+)", out).group(1)
        
        hub.action_consensus_sweep(ai_dir, timeout_minutes=30)
        
        rpath = ai_dir / "consensus" / f"{round_id}.json"
        data = json.loads(rpath.read_text("utf-8"))
        assert data["status"] == "voting"
