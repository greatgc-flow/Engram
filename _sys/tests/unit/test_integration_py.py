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
        return subprocess.run(
            [str(vpy), str(hub)] + args, cwd=cwd,
            check=True, timeout=_HUB_TIMEOUT, **kwargs
        )

    def _out(self, vpy, hub, args, cwd):
        """subprocess.check_output wrapper with guaranteed timeout."""
        return subprocess.check_output(
            [str(vpy), str(hub)] + args,
            cwd=cwd, text=True, encoding="utf-8", timeout=_HUB_TIMEOUT
        )

    def test_scenario_nway_lifecycle(self, test_env):
        """[세션/상태] N-Way 단일 룸 생명주기 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]

        room_id = "test-room-123"
        self._run(vpy, hub, ["init-session", "--agent", "cc", "--room", room_id], root)
        self._run(vpy, hub, ["init-session", "--agent", "ca", "--room", room_id], root)
        self._run(vpy, hub, ["init-session", "--agent", "gc", "--room", room_id], root)

        state = json.loads((root / ".ai/state.json").read_text("utf-8"))
        assert state["room_id"] == room_id
        assert "cc" in state["members"]
        assert "ca" in state["members"]
        assert "gc" in state["members"]

        self._run(vpy, hub, ["send", "--from", "cc", "--to", "ca", "--msg", "p2p-hi"], root)
        out = self._out(vpy, hub, ["check", "--target", "ca"], root)
        assert "p2p-hi" in out

    def test_scenario_p2p_consensus(self, test_env):
        """[권한/의사결정] P2P 무제한 합의 및 교차 발의 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]

        self._run(vpy, hub, ["consensus-propose", "--subject", "p2p-test", "--voters", "cc,ca,gc", "--from", "gc"], root)

        rounds = list((root / ".ai/consensus").glob("*.json"))
        assert len(rounds) == 1
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]

        self._run(vpy, hub, ["consensus-vote", "--round-id", rid, "--voter", "cc", "--vote", "disagree", "--reason", "more info req"], root)
        self._run(vpy, hub, ["consensus-vote", "--round-id", rid, "--voter", "ca", "--vote", "agree"], root)
        self._run(vpy, hub, ["consensus-vote", "--round-id", rid, "--voter", "gc", "--vote", "agree"], root)

        round_data = json.loads(rounds[0].read_text("utf-8"))
        assert round_data["status"] == "escalated"
        assert round_data["outcome"] == "human_gate"

    def test_scenario_division_of_labor(self, test_env):
        """[분업/실행] 다중 노드 태스크 분할 및 병렬 실행 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]

        self._run(vpy, hub, ["init-session", "--agent", "cc"], root)
        self._run(vpy, hub, ["send", "--from", "cc", "--to", "gc", "--msg", "write-doc", "--type", "DIRECTIVE"], root)
        self._run(vpy, hub, ["send", "--from", "cc", "--to", "ca", "--msg", "write-code", "--type", "DIRECTIVE"], root)
        self._run(vpy, hub, ["send", "--from", "gc", "--to", "cc", "--msg", "doc-done", "--type", "ARTIFACT"], root)
        self._run(vpy, hub, ["send", "--from", "ca", "--to", "cc", "--msg", "code-done", "--type", "ARTIFACT"], root)

        inbox = self._out(vpy, hub, ["check", "--target", "cc"], root)
        assert "doc-done" in inbox
        assert "code-done" in inbox

    def test_scenario_cross_validation(self, test_env):
        """[검증] 전원 교차 검토(Cross-check) 흐름 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]

        self._run(vpy, hub, ["init-session", "--agent", "cc"], root)
        self._run(vpy, hub, ["init-session", "--agent", "ca"], root)
        self._run(vpy, hub, ["init-session", "--agent", "gc"], root)
        self._run(vpy, hub, ["send", "--from", "ca", "--to", "cc", "--msg", "feat-x", "--type", "ARTIFACT"], root)
        self._run(vpy, hub, ["send", "--from", "gc", "--to", "ca", "--msg", "PASS: doc aligns", "--type", "VERIFY"], root)
        self._run(vpy, hub, ["send", "--from", "cc", "--to", "ca", "--msg", "PASS: code logic ok", "--type", "VERIFY"], root)

        ca_inbox = self._out(vpy, hub, ["check", "--target", "ca"], root)
        assert "doc aligns" in ca_inbox
        assert "code logic ok" in ca_inbox

    def test_scenario_collab_rate(self, test_env):
        """[정책] COLLAB_RATE=10 에 따른 합의 필수성 로직(모의) 검증."""
        root, vpy, hub = test_env["root"], test_env["venv_py"], test_env["hub_py"]

        self._run(vpy, hub, ["init-session", "--agent", "cc"], root)
        self._run(vpy, hub, ["consensus-propose", "--subject", "high-rate-task", "--voters", "cc,ca,gc"], root)

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

        self._run(vpy, hub, ["send", "--from", "cc", "--to", "gc", "--msg", "ext-msg-test"], ext_project)
        inbox = self._out(vpy, hub, ["check", "--target", "gc"], ext_project)
        assert "ext-msg-test" in inbox

        ws_root = test_env["root"]
        if (ws_root / ".ai" / "state.json").exists():
            ws_state = json.loads((ws_root / ".ai" / "state.json").read_text("utf-8"))
            assert ws_state.get("room_id") != "ext-room-1"
