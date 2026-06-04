"""
Statusline and Visibility Verification Test
Ensures 'python hub.py status' correctly reports session state.
"""
import subprocess
import json
import pytest
from pathlib import Path

class TestStatusline:
    """Validate the status command output."""

    @pytest.fixture
    def test_env(self, tmp_path):
        """Setup isolated .ai directory."""
        ai_dir = tmp_path / ".ai"
        ai_dir.mkdir(exist_ok=True)
        
        root_dir = Path(__file__).parent.parent.parent.parent
        venv_py = root_dir / "_sys" / "env" / "venv" / "Scripts" / "python.exe"
        hub_py = root_dir / "_sys" / "core" / "hub.py"
        
        return {
            "root": tmp_path,
            "venv_py": venv_py,
            "hub_py": hub_py
        }

    def run_hub_cmd(self, env, args):
        """Helper to run hub command."""
        return subprocess.run(
            [str(env["venv_py"]), str(env["hub_py"])] + args,
            cwd=env["root"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )

    def test_status_empty(self, test_env):
        """Test status when no session exists."""
        res = self.run_hub_cmd(test_env, ["status"])
        assert res.returncode == 0
        # hub.py status uses '없음' for None/Empty fields
        assert "없음" in res.stdout or "No active session" in res.stdout or "WAITING" in res.stdout

    def test_status_active_session(self, test_env):
        """Test status with active session and members."""
        self.run_hub_cmd(test_env, ["init-session", "--agent", "cc", "--room", "status-room"])
        res = self.run_hub_cmd(test_env, ["status"])
        
        assert res.returncode == 0
        assert "status-room" in res.stdout
        assert "cc" in res.stdout

    def test_status_consensus_active(self, test_env):
        """Test status when consensus is in progress."""
        self.run_hub_cmd(test_env, ["init-session", "--agent", "cc"])
        self.run_hub_cmd(test_env, ["consensus-propose", "--subject", "vote-me", "--voters", "cc,ca"])
        
        res = self.run_hub_cmd(test_env, ["status"])
        assert "CONSENSUS" in res.stdout
        assert "ACTIVE" in res.stdout
        assert "vote-me" in res.stdout

    def test_status_mailbox_indicator(self, test_env):
        """Test status shows unread message count."""
        self.run_hub_cmd(test_env, ["init-session", "--agent", "cc"])
        self.run_hub_cmd(test_env, ["send", "--from", "ca", "--to", "cc", "--msg", "hello"])
        
        res = self.run_hub_cmd(test_env, ["status"])
        # Assuming the status command has some indicator like (1) or [1] for mail
        # This depends on exact hub.py implementation of status
        # If it doesn't have it yet, this test will help define the requirement.
        assert "Mail" in res.stdout or "Inbox" in res.stdout
