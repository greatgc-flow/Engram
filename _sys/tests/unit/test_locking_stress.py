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
        """Setup isolated .ai directory.

        Peer HEALTH is not isolated by tmp_path -- _peer_sys_dir() resolves to
        the real, global _sys/<peer>/health.json regardless of ai_root/cwd
        (T72: confirmed live, a stale `quarantined: true` on cc's real health
        made _decide_consensus's mid_round_closed RED-voter check force-
        escalate every round here, unrelated to anything this test does).
        Force a clean GREEN baseline before each test so a leftover
        quarantine/RED elsewhere on the machine can't make this test flaky.
        """
        ai_dir = tmp_path / ".ai"
        ai_dir.mkdir(exist_ok=True)

        root_dir = Path(__file__).parent.parent.parent.parent
        venv_py = root_dir / "_sys" / "env" / "venv" / "Scripts" / "python.exe"
        hub_py = root_dir / "_sys" / "core" / "hub.py"

        subprocess.run(
            [str(venv_py), str(hub_py), "peer-recover", "--peer", "all"],
            cwd=tmp_path, capture_output=True, timeout=_SUBPROCESS_TIMEOUT,
        )

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

        Top-5 #1 (2026-07-25): all 4 joins use the SAME canonical root peer id
        ("cc"), not distinct synthetic names (formerly "agent_0".."agent_3").
        `_normalize_runtime_files()` (now correctly lock-protected, sharing the
        SAME "state"/"nodes"/"leases" lock names as every other writer of those
        files -- part of this fix) purges any member not in the live routing
        config's active root-peer set by design; a synthetic, unconfigured name
        was never guaranteed to survive a normalize pass even pre-fix -- it
        just usually raced ahead of the purge while _normalize_runtime_files
        ran unlocked. Real lock serialization now makes that pre-existing purge
        trigger reliably, which is orthogonal to what this test actually
        verifies: that 4 real OS processes hammering the SAME lock never
        corrupt state.json. Using a real, always-surviving peer id isolates
        that property from the unrelated peer-canonicalization feature.
        """
        agents = ["cc"] * 4
        arg_list = [["init-session", "--agent", a, "--room", "stress-room"] for a in agents]
        results = self._run_hub_parallel(test_env, arg_list)

        for i, res in enumerate(results):
            assert res.returncode == 0, f"Agent {i} failed: {res.stderr}"

        state_path = test_env["root"] / ".ai" / "state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text("utf-8"))

        # No corruption/lost-update under contention: exactly one "cc" entry,
        # not a partial write, duplicate key, or malformed members dict.
        assert state["members"] == {"cc": state["members"].get("cc")}
        assert state["members"]["cc"], "cc's session id must survive concurrent joins"

    def test_concurrent_consensus_votes(self, test_env):
        """Verify concurrent processes voting don't corrupt the consensus file.

        Uses the real canonical R:10 voter set (cc/ag/cx), not synthetic names --
        this test invokes the real hub.py against the real protocol.json (no
        isolated config), so a synthetic --voters subset is now rejected by the
        2026-07-17 INV-03 fix (arbitrary --voters must match canonical at R:10).
        Still a genuine concurrent-write stress test with 3 truly parallel
        subprocesses racing on the same round file's lock.
        """
        self.run_hub_cmd(test_env, ["init-session", "--agent", "admin"])
        voters = ["cc", "ag", "cx"]
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
        assert len(updated_round["votes"]) == 3
        assert updated_round["status"] == "finalized"
