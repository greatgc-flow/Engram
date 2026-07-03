"""
OS-level File Locking Stress Test
Verifies that hub.py correctly handles concurrent access from multiple OS processes.

NOTE: Uses subprocess.Popen directly (not ProcessPoolExecutor) to avoid double-layer
process spawning on Windows. ProcessPoolExecutor + subprocess.run = Python interpreter
per pool worker × subprocess per task = OOM risk at ~150MB per Python process.
"""
import subprocess
import time
import json
import os
import pytest
from pathlib import Path

_SUBPROCESS_TIMEOUT = 30  # seconds per hub.py call


class TestLockingStress:
    """Stress test for file-based IPC and state locking."""

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
        """Run a single hub command synchronously with timeout."""
        origin = "cc"
        if "--from" in args:
            origin = args[args.index("--from") + 1]
        elif "--agent" in args:
            origin = args[args.index("--agent") + 1]
        sub_env = {**os.environ, "HUB_ORIGIN": origin}
        return subprocess.run(
            [str(env["venv_py"]), str(env["hub_py"])] + args,
            cwd=env["root"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_SUBPROCESS_TIMEOUT,
            env=sub_env,
        )

    def _run_hub_parallel(self, env, arg_list):
        """Spawn hub.py subprocesses in parallel via Popen, collect results.
        Avoids ProcessPoolExecutor to prevent double-layer process spawning.
        """
        procs = []
        for args in arg_list:
            origin = "cc"
            if "--from" in args:
                origin = args[args.index("--from") + 1]
            elif "--agent" in args:
                origin = args[args.index("--agent") + 1]
            sub_env = {**os.environ, "HUB_ORIGIN": origin}
            procs.append(
                subprocess.Popen(
                    [str(env["venv_py"]), str(env["hub_py"])] + args,
                    cwd=env["root"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=sub_env,
                )
            )
        results = []
        for p in procs:
            try:
                stdout, stderr = p.communicate(timeout=_SUBPROCESS_TIMEOUT)
            except subprocess.TimeoutExpired:
                p.kill()
                stdout, stderr = p.communicate()
            results.append(subprocess.CompletedProcess(
                args=p.args, returncode=p.returncode,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
            ))
        return results

    def test_parallel_init_session(self, test_env):
        """Launch 4 parallel hub processes trying to init-session.
        All should succeed; filelock serializes writes so no corruption.
        """
        agents = [f"agent_{i}" for i in range(4)]
        arg_list = [["init-session", "--agent", a, "--room", "stress-room"] for a in agents]
        results = self._run_hub_parallel(test_env, arg_list)

        for i, res in enumerate(results):
            assert res.returncode == 0, f"Agent {i} failed: {res.stderr}"

        state_path = test_env["root"] / ".ai" / "state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text("utf-8"))

        for a in agents:
            assert a in state["members"], f"Agent {a} missing from members list"

    def test_concurrent_consensus_votes(self, test_env):
        """Verify 4 processes voting concurrently don't corrupt the consensus file."""
        self.run_hub_cmd(test_env, ["init-session", "--agent", "admin"])
        voters = [f"v_{i}" for i in range(4)]  # 4 voters, not 8, to keep memory bounded
        self.run_hub_cmd(test_env, [
            "consensus-propose", "--subject", "parallel-vote",
            "--voters", ",".join(voters)
        ])

        round_files = list((test_env["root"] / ".ai" / "consensus").glob("*.json"))
        assert len(round_files) == 1
        round_id = json.loads(round_files[0].read_text("utf-8"))["round_id"]

        arg_list = [
            ["consensus-vote", "--round-id", round_id, "--voter", v, "--vote", "agree"]
            for v in voters
        ]
        results = self._run_hub_parallel(test_env, arg_list)

        for i, res in enumerate(results):
            assert res.returncode == 0, f"Voter {i} failed: {res.stderr}"

        updated_round = json.loads(round_files[0].read_text("utf-8"))
        assert len(updated_round["votes"]) == 4
        assert updated_round["status"] == "finalized"
