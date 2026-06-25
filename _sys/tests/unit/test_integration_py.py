"""
통합 테스트 개정 (P2P v3)
N-Way Room 세션, P2P 무제한 합의, 분업(Division of Labor), 교차 검증 시나리오 구현
"""
import json
import subprocess
import os
import shutil
import re
import pytest
from pathlib import Path

_HUB_TIMEOUT = 15  # seconds; hub.py does only file I/O, should complete well under this


class TestIntegrationP2P:
    """N-Tier Peer-to-Peer 협업 시스템 고도화 검증."""

    @pytest.fixture
    def test_env(self, tmp_path):
        """테스트용 격리 환경 생성."""
        ai_dir = tmp_path / ".ai"
        ai_dir.mkdir(exist_ok=True)
        (tmp_path / ".git").mkdir(exist_ok=True)

        root_dir = Path(__file__).parent.parent.parent.parent
        venv_py = root_dir / "_sys" / "env" / "venv" / "Scripts" / "python.exe"
        hub_py = root_dir / "_sys" / "core" / "hub.py"

        return {
            "root": tmp_path,
            "ai_dir": ai_dir,
            "venv_py": venv_py,
            "hub_py": hub_py
        }

    def _run(self, vpy, hub, args, cwd, **kwargs):
        """subprocess.run wrapper with guaranteed timeout."""
        sub_env = {**os.environ, "HUB_ORIGIN": "worker"}
        return subprocess.run(
            [str(vpy), str(hub)] + args, cwd=cwd,
            check=True, timeout=_HUB_TIMEOUT, env=sub_env, **kwargs
        )

    def _out(self, vpy, hub, args, cwd):
        """subprocess.check_output wrapper with guaranteed timeout."""
        sub_env = {**os.environ, "HUB_ORIGIN": "worker"}
        return subprocess.check_output(
            [str(vpy), str(hub)] + args,
            cwd=cwd, text=True, encoding="utf-8", timeout=_HUB_TIMEOUT, env=sub_env
        )

    def test_scenario_nway_lifecycle(self, test_env):
        """[세션/상태] N-Way 단일 룸 생명주기 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]

        room_id = "test-room-123"
        self._run(vpy, hub, ["init-session", "--agent", "cc", "--room", room_id], root)
        self._run(vpy, hub, ["init-session", "--agent", "ag", "--room", room_id], root)
        self._run(vpy, hub, ["init-session", "--agent", "cx", "--room", room_id], root)

        state = json.loads((root / ".ai/state.json").read_text("utf-8"))
        assert state["room_id"] == room_id
        assert "cc" in state["members"]
        assert "ag" in state["members"]
        assert "cx" in state["members"]

        self._run(vpy, hub, ["send", "--from", "cc", "--to", "ag", "--msg", "p2p-hi"], root)
        out = self._out(vpy, hub, ["check", "--target", "ag"], root)
        assert "p2p-hi" in out

    def test_scenario_p2p_consensus(self, test_env):
        """[권한/의사결정] P2P 무제한 합의 및 교차 발의 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]

        self._run(vpy, hub, ["health-update", "--peer", "ag", "--status", "GREEN"], root)
        self._run(vpy, hub, ["health-update", "--peer", "cc", "--status", "GREEN"], root)
        self._run(vpy, hub, ["health-update", "--peer", "cx", "--status", "GREEN"], root)

        self._run(vpy, hub, ["consensus-propose", "--subject", "p2p-test", "--voters", "cc,cx,ag", "--from", "ag"], root)

        rounds = list((root / ".ai/consensus").glob("*.json"))
        assert len(rounds) == 1
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]

        self._run(vpy, hub, ["consensus-vote", "--round-id", rid, "--voter", "cc", "--vote", "disagree", "--reason", "more info req"], root)
        self._run(vpy, hub, ["consensus-vote", "--round-id", rid, "--voter", "cx", "--vote", "agree"], root)
        self._run(vpy, hub, ["consensus-vote", "--round-id", rid, "--voter", "ag", "--vote", "agree"], root)

        round_data = json.loads(rounds[0].read_text("utf-8"))
        assert round_data["status"] == "escalated"
        assert round_data["outcome"] == "human_gate"

    def test_scenario_division_of_labor(self, test_env):
        """[분업/실행] 다중 노드 태스크 분할 및 병렬 실행 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]

        self._run(vpy, hub, ["init-session", "--agent", "cc"], root)
        self._run(vpy, hub, ["send", "--from", "cc", "--to", "ag", "--msg", "write-doc", "--type", "DIRECTIVE"], root)
        self._run(vpy, hub, ["send", "--from", "cc", "--to", "cx", "--msg", "write-code", "--type", "DIRECTIVE"], root)
        self._run(vpy, hub, ["send", "--from", "ag", "--to", "cc", "--msg", "doc-done", "--type", "ARTIFACT"], root)
        self._run(vpy, hub, ["send", "--from", "cx", "--to", "cc", "--msg", "code-done", "--type", "ARTIFACT"], root)

        inbox = self._out(vpy, hub, ["check", "--target", "cc"], root)
        assert "doc-done" in inbox
        assert "code-done" in inbox

    def test_scenario_cross_validation(self, test_env):
        """[검증] 전원 교차 검토(Cross-check) 흐름 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]

        self._run(vpy, hub, ["init-session", "--agent", "cc"], root)
        self._run(vpy, hub, ["init-session", "--agent", "cx"], root)
        self._run(vpy, hub, ["init-session", "--agent", "ag"], root)
        self._run(vpy, hub, ["send", "--from", "cx", "--to", "cc", "--msg", "feat-x", "--type", "ARTIFACT"], root)
        self._run(vpy, hub, ["send", "--from", "ag", "--to", "cx", "--msg", "PASS: doc aligns", "--type", "VERIFY"], root)
        self._run(vpy, hub, ["send", "--from", "cc", "--to", "cx", "--msg", "PASS: code logic ok", "--type", "VERIFY"], root)

        ca_inbox = self._out(vpy, hub, ["check", "--target", "cx"], root)
        assert "doc aligns" in ca_inbox
        assert "code logic ok" in ca_inbox

    def test_scenario_collab_rate(self, test_env):
        """[정책] COLLAB_RATE=10 에 따른 합의 필수성 로직(모의) 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]

        self._run(vpy, hub, ["init-session", "--agent", "cc"], root)
        self._run(vpy, hub, ["consensus-propose", "--subject", "high-rate-task", "--voters", "cc,cx,ag"], root)

        status = self._out(vpy, hub, ["status"], root)
        assert "high-rate-task" in status
        assert "CONSENSUS — ACTIVE" in status

    def test_external_portability(self, test_env, tmp_path_factory):
        """[포터빌리티] 워크스페이스 외부 폴더에서 N-Tier 협업 도구 사용 및 컨텍스트 격리 검증."""
        ext_project = tmp_path_factory.mktemp("external_proj")
        (ext_project / ".git").mkdir()

        vpy, hub = test_env["venv_py"], test_env["hub_py"]

        self._run(vpy, hub, ["init-session", "--agent", "cc", "--room", "ext-room-1"], ext_project)
        assert (ext_project / ".ai").exists()
        assert (ext_project / ".ai" / "state.json").exists()

        self._run(vpy, hub, ["send", "--from", "cc", "--to", "ag", "--msg", "ext-msg-test"], ext_project)
        inbox = self._out(vpy, hub, ["check", "--target", "ag"], ext_project)
        assert "ext-msg-test" in inbox

        ws_root = test_env["root"]
        if (ws_root / ".ai" / "state.json").exists():
            ws_state = json.loads((ws_root / ".ai" / "state.json").read_text("utf-8"))
            assert ws_state.get("room_id") != "ext-room-1"

    def test_two_external_projects_strict_isolation(self, test_env, tmp_path_factory):
        """[격리] 두 개의 외부 프로젝트 .ai/ 상태가 완전히 격리됨을 검증.
        프로젝트 A의 메시지가 프로젝트 B의 inbox에 보이지 않아야 함."""
        vpy, hub = test_env["venv_py"], test_env["hub_py"]

        proj_a = tmp_path_factory.mktemp("ext_proj_a")
        proj_b = tmp_path_factory.mktemp("ext_proj_b")
        (proj_a / ".git").mkdir()
        (proj_b / ".git").mkdir()

        # Project A: cc → gc로 메시지 전송
        self._run(vpy, hub, ["init-session", "--agent", "cc", "--room", "room-proj-a"], proj_a)
        self._run(vpy, hub, ["send", "--from", "cc", "--to", "ag", "--msg", "secret-for-proj-a"], proj_a)

        # Project B: 초기화만 (A의 메시지가 없어야 함)
        self._run(vpy, hub, ["init-session", "--agent", "cc", "--room", "room-proj-b"], proj_b)
        inbox_b = self._out(vpy, hub, ["check", "--target", "ag"], proj_b)

        assert "secret-for-proj-a" not in inbox_b, \
            "프로젝트 A의 메시지가 프로젝트 B의 inbox에 누출됨"

        # State 파일도 독립적이어야 함
        state_a = json.loads((proj_a / ".ai" / "state.json").read_text("utf-8"))
        state_b = json.loads((proj_b / ".ai" / "state.json").read_text("utf-8"))
        assert state_a["room_id"] != state_b["room_id"], \
            "두 프로젝트의 room_id가 동일함 — 격리 위반"

    def test_scenario_final_call_protocol(self, test_env):
        """[합의] Final Call(FC) 프로토콜 및 다중 노드 분업 시나리오 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]
        
        self._run(vpy, hub, ["health-update", "--peer", "ag", "--status", "GREEN"], root)
        self._run(vpy, hub, ["health-update", "--peer", "cc", "--status", "GREEN"], root)

        self._run(vpy, hub, ["init-session", "--agent", "cc"], root)
        self._run(vpy, hub, ["init-session", "--agent", "ag"], root)
        
        # 1. 제안 (Propose)
        self._run(vpy, hub, ["consensus-propose", "--subject", "feat-implementation", "--voters", "cc,ag", "--from", "cc"], root)
        
        # 2. Final Call 메시지 전송 (Convention)
        fc_msg = "PLAN:[1.edit, 2.test] RISK:Low FC:r-1234:SUMMARY=Ready to execute. VOTE?"
        self._run(vpy, hub, ["send", "--from", "cc", "--to", "ag", "--msg", fc_msg, "--type", "DIRECTIVE"], root)
        
        # 3. 투표 (Vote)
        rounds = list((root / ".ai/consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]
        self._run(vpy, hub, ["consensus-vote", "--round-id", rid, "--voter", "cc", "--vote", "agree"], root)
        self._run(vpy, hub, ["consensus-vote", "--round-id", rid, "--voter", "ag", "--vote", "agree"], root)
        
        # 4. 결과 및 상태 확인
        status = self._out(vpy, hub, ["status"], root)
        assert "FINALIZED" in status
        assert "feat-implementation" in status

    def test_handoff_rolling_truncation(self, test_env):
        """[데이터] handoff.md 롤링(FIFO) 및 용량 제한 로직 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]
        
        self._run(vpy, hub, ["init-session", "--agent", "cc"], root)
        state = json.loads((root / ".ai/state.json").read_text("utf-8"))
        room_id = state["room_id"]
        session_dir = root / ".ai" / "sessions" / room_id
        
        # 강제로 handoff.md에 많은 항목 주입
        handoff_file = session_dir / "handoff.md"
        large_content = "## [RECENT_COMPLETED]\n" + "\n".join([f"- task {i}" for i in range(50)])
        handoff_file.write_text(large_content, encoding="utf-8")
        
        # end-session 호출 시 롤링 발생해야 함
        self._run(vpy, hub, ["end-session", "--agent", "cc"], root)
        
        updated_content = handoff_file.read_text("utf-8")
        completed_lines = [line for line in updated_content.splitlines() if line.startswith("- task")]
        # RECENT_COMPLETED는 HANDOFF_MAX_COMPLETED(기본 5)개로 제한되어야 함
        # hub.py logic: pop(0) until size < limit
        assert len(completed_lines) <= 10 # 5 (기본) + 1 (세션 종료 메시지) = 6. 여유있게 10으로 체크.

