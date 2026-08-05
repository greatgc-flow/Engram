"""Unit & Structural Tests for S3 Console Runner Adoption (Cluster S3).

Covers:
1. Structural AST test: codex_entry.py, claude_entry.py, agy_entry.py MUST NOT call subprocess directly.
2. Lease-duty mapping (exhaustive, all 4 InvocationKinds + fail-loud on unmapped).
3. Failure-abort vs ALLOW_UNLEASED_CONSOLE=1 break-glass behavior.
4. Separate break-glass assertion: ALLOW_UNLEASED_CONSOLE does NOT bypass C8 security validation.
5. Heartbeat CAS rejection stops renewal without killing child process.
6. Strict 1-way dependency guarantee: argv -> C8 prep -> ConsoleLaunch -> Lease -> Spawn.
"""
import ast
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

SYS_DIR = Path(__file__).parent.parent.parent.resolve()
CLI_DIR = SYS_DIR / "cli"
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

from peer_console import InvocationKind, SecurityValidationError
from console_runner import (
    ConsoleSessionSpec,
    run_console_session,
    should_claim_lease,
)


class TestS3StructuralEntryPoints:
    """Structural AST test forcing all console wrappers through console_runner."""

    @pytest.mark.parametrize("entry_file", ["codex_entry.py", "claude_entry.py", "agy_entry.py"])
    def test_no_direct_subprocess_calls_in_wrappers(self, entry_file):
        file_path = CLI_DIR / entry_file
        assert file_path.exists(), f"Wrapper file {entry_file} must exist"

        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in {"run", "Popen", "call", "check_call", "check_output"}:
                    if isinstance(node.value, ast.Name) and node.value.id == "subprocess":
                        pytest.fail(
                            f"{entry_file} calls subprocess.{node.attr} directly at line {node.lineno}! "
                            f"All console wrappers must route process execution through console_runner.py."
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "subprocess":
                        pytest.fail(
                            f"{entry_file} imports 'subprocess' directly at line {node.lineno}! "
                            f"Wrappers must not perform direct subprocess calls."
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module == "subprocess":
                    pytest.fail(
                        f"{entry_file} imports from 'subprocess' at line {node.lineno}! "
                        f"Wrappers must not perform direct subprocess calls."
                    )


class TestS3LeaseDutyMapping:
    """Exhaustive testing for should_claim_lease across InvocationKind enum."""

    def test_local_agent_claims_lease(self):
        assert should_claim_lease(InvocationKind.LOCAL_AGENT) is True

    def test_remote_agent_claims_lease(self):
        assert should_claim_lease(InvocationKind.REMOTE_AGENT) is True

    def test_help_or_version_no_lease(self):
        assert should_claim_lease(InvocationKind.HELP_OR_VERSION) is False

    def test_admin_or_service_no_lease(self):
        assert should_claim_lease(InvocationKind.ADMIN_OR_SERVICE) is False

    def test_unmapped_invocation_kind_raises_loudly(self):
        class FakeKind:
            value = "fake_unmapped"

        with pytest.raises(ValueError, match="Unhandled InvocationKind"):
            should_claim_lease(FakeKind)  # type: ignore


class TestS3LeaseFailureSemantics:
    """Claim failure abort vs break-glass behavior tests."""

    def test_claim_failure_aborts_by_default(self, monkeypatch):
        monkeypatch.delenv("ALLOW_UNLEASED_CONSOLE", raising=False)

        def mock_hub_action(args, env, **kwargs):
            res = MagicMock()
            if args[0] == "terminal-handoff":
                res.returncode = 1
                res.stderr = "Handoff lock collision"
                res.stdout = ""
            else:
                res.returncode = 0
                res.stdout = ""
                res.stderr = ""
            return res

        monkeypatch.setattr("console_runner._run_hub_action", mock_hub_action)

        process_spawned = False

        def mock_popen(cmd, env=None, cwd=None, **kwargs):
            nonlocal process_spawned
            process_spawned = True
            proc = MagicMock()
            proc.pid = 1234
            proc.wait.return_value = 0
            proc.returncode = 0
            return proc

        spec = ConsoleSessionSpec(peer_id="cx", cmd_prefix=["codex"], env={})
        res = run_console_session(spec, ["exec"], _popen_runner=mock_popen)

        assert res.exit_code == 1
        assert res.lease_claimed is False
        assert res.lease_id is None
        assert isinstance(res.error, RuntimeError)
        assert process_spawned is False, "Child process must NOT be spawned on claim failure when break-glass is disabled"

    def test_claim_failure_proceeds_with_break_glass(self, monkeypatch):
        monkeypatch.setenv("ALLOW_UNLEASED_CONSOLE", "1")

        def mock_hub_action(args, env, **kwargs):
            res = MagicMock()
            if args[0] == "terminal-handoff":
                res.returncode = 1
                res.stderr = "Handoff lock collision"
                res.stdout = ""
            else:
                res.returncode = 0
                res.stdout = ""
                res.stderr = ""
            return res

        monkeypatch.setattr("console_runner._run_hub_action", mock_hub_action)

        process_spawned = False

        def mock_popen(cmd, env=None, cwd=None, **kwargs):
            nonlocal process_spawned
            process_spawned = True
            proc = MagicMock()
            proc.pid = 1234
            proc.wait.return_value = 0
            proc.returncode = 0
            return proc

        spec = ConsoleSessionSpec(peer_id="cx", cmd_prefix=["codex"], env={})
        res = run_console_session(spec, ["exec"], _popen_runner=mock_popen)

        assert res.exit_code == 0
        assert res.lease_claimed is False
        assert res.lease_id is None
        assert process_spawned is True, "Child process SHOULD spawn degraded when ALLOW_UNLEASED_CONSOLE=1 break-glass is set"

    def test_break_glass_does_not_bypass_c8_security_validation(self, monkeypatch):
        """ALLOW_UNLEASED_CONSOLE=1 break-glass MUST NOT bypass forbidden-arg security checks."""
        monkeypatch.setenv("ALLOW_UNLEASED_CONSOLE", "1")
        monkeypatch.delenv("ALLOW_BREAK_GLASS_DANGER_ACCESS", raising=False)

        spec = ConsoleSessionSpec(peer_id="cx", cmd_prefix=["codex"], env={})

        with pytest.raises(SecurityValidationError, match=r"Forbidden security (argument|value)"):
            run_console_session(spec, ["exec", "-s", "danger-full-access"])


class TestS3HeartbeatCASRejection:
    """CAS rejection during heartbeat stops renewal without killing vendor child process."""

    def test_cas_rejection_stops_renewing_without_killing_process(self, monkeypatch):
        heartbeat_calls = 0

        def mock_hub_action(args, env, **kwargs):
            nonlocal heartbeat_calls
            res = MagicMock()
            if args[0] == "terminal-handoff":
                res.returncode = 0
                res.stdout = "[HUB] TERMINAL-HANDOFF complete | lease=term-lease-cas-test"
                res.stderr = ""
            elif args[0] == "terminal-heartbeat":
                heartbeat_calls += 1
                res.returncode = 1
                res.stdout = ""
                res.stderr = "[HUB:WARN] terminal-heartbeat CAS rejection for peer=cx: stale lease_id"
            else:
                res.returncode = 0
                res.stdout = ""
                res.stderr = ""
            return res

        monkeypatch.setattr("console_runner._run_hub_action", mock_hub_action)

        proc = MagicMock()
        proc.pid = 5678
        proc.returncode = 0

        def mock_wait():
            import time
            time.sleep(0.3)
            return 0

        proc.wait.side_effect = mock_wait

        spec = ConsoleSessionSpec(
            peer_id="cx",
            cmd_prefix=["codex"],
            env={},
            heartbeat_interval_sec=0.05,
        )

        res = run_console_session(spec, ["exec"], _popen_runner=lambda cmd, env=None, cwd=None, **kwargs: proc)

        assert res.exit_code == 0
        assert res.lease_claimed is True
        assert res.lease_id == "term-lease-cas-test"
        assert heartbeat_calls >= 1


class TestS3HeartbeatCloseRace:
    """Independent cross-verification (cx) found a real, reproducible HIGH-
    severity race: a late heartbeat could land (and succeed) AFTER
    terminal-close already ran, since hub.py's CAS check only compares
    lease_id, not close_reason/expiry -- effectively reviving a just-closed
    lease. Fixed with a lock shared between every heartbeat call and the
    final close call."""

    def test_no_heartbeat_call_recorded_after_terminal_close(self, monkeypatch):
        import time as time_mod
        call_log: list[str] = []
        lock = __import__("threading").Lock()

        def mock_hub_action(args, env, **kwargs):
            res = MagicMock()
            action = args[0]
            if action == "terminal-handoff":
                res.returncode = 0
                res.stdout = "[HUB] TERMINAL-HANDOFF complete | lease=term-lease-race-test"
                res.stderr = ""
            elif action == "terminal-heartbeat":
                # Simulate a slow/transient-failing heartbeat call so it is
                # very likely still in flight when the main thread's wait()
                # returns and shutdown begins.
                with lock:
                    call_log.append("heartbeat-start")
                time_mod.sleep(0.15)
                res.returncode = 1
                res.stdout = ""
                res.stderr = "transient error, no CAS/stale text here"
                with lock:
                    call_log.append("heartbeat-end")
            elif action == "terminal-close":
                with lock:
                    call_log.append("close")
                res.returncode = 0
                res.stdout = ""
                res.stderr = ""
            else:
                res.returncode = 0
                res.stdout = ""
                res.stderr = ""
            return res

        monkeypatch.setattr("console_runner._run_hub_action", mock_hub_action)

        proc = MagicMock()
        proc.pid = 4242
        proc.returncode = 0
        proc.wait.side_effect = lambda: time_mod.sleep(0.05) or 0

        spec = ConsoleSessionSpec(
            peer_id="cx", cmd_prefix=["codex"], env={}, heartbeat_interval_sec=0.02,
        )
        res = run_console_session(spec, ["exec"], _popen_runner=lambda cmd, env=None, cwd=None, **kwargs: proc)

        assert res.exit_code == 0
        assert "close" in call_log
        close_index = call_log.index("close")
        # No heartbeat call may start (or still be running/end) after close.
        assert "heartbeat-start" not in call_log[close_index + 1:]
        assert "heartbeat-end" not in call_log[close_index + 1:]


class TestS3LeaseClaimCorrelation:
    """Independent cross-verification (cx) found _claim_terminal_lease()
    could adopt an unrelated/stale lease_id from state.json instead of the
    one actually just minted by the immediately-preceding terminal-handoff
    call. The freshly-printed stdout lease_id (guaranteed correlated to
    THIS call) must win over any state.json read."""

    def test_stdout_lease_id_wins_over_stale_state_json(self, monkeypatch, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(
            '{"human_interface_assignment": {"peer": "cx", "lease_id": "term-lease-STALE"}}',
            encoding="utf-8",
        )
        monkeypatch.setattr("console_runner._PORTABLE_ROOT", tmp_path)

        def mock_hub_action(args, env, **kwargs):
            res = MagicMock()
            if args[0] == "terminal-handoff":
                res.returncode = 0
                res.stdout = "[HUB] TERMINAL-HANDOFF complete | lease=term-lease-FRESH"
                res.stderr = ""
            else:
                res.returncode = 0
                res.stdout = ""
                res.stderr = ""
            return res

        monkeypatch.setattr("console_runner._run_hub_action", mock_hub_action)

        import console_runner as cr
        spec = ConsoleSessionSpec(peer_id="cx", cmd_prefix=["codex"], env={})
        lease_id, err = cr._claim_terminal_lease(spec, InvocationKind.LOCAL_AGENT)

        assert err is None
        assert lease_id == "term-lease-FRESH"


class TestS3HealthTrackingMigrationFidelity:
    """Independent cross-verification (cx) found two real health-tracking
    migration regressions against each peer's original pre-S3 convention."""

    def test_cx_invocation_metrics_only_written_at_finish_not_start(self, tmp_path):
        import console_runner as cr
        health_path = tmp_path / "health.json"
        health_path.write_text('{"availability": {}}', encoding="utf-8")
        spec = ConsoleSessionSpec(peer_id="cx", cmd_prefix=["codex"], env={}, health_json_path=health_path)

        cr._update_peer_health_json(spec, 0, 0, None, stage="start")
        data = __import__("json").loads(health_path.read_text(encoding="utf-8"))
        assert "last_invocation_duration_ms" not in data["availability"]
        assert "last_invocation_exit_code" not in data["availability"]

        cr._update_peer_health_json(spec, 0, 1234, None, stage="finish")
        data = __import__("json").loads(health_path.read_text(encoding="utf-8"))
        assert data["availability"]["last_invocation_duration_ms"] == 1234
        assert data["availability"]["last_invocation_exit_code"] == 0

    def test_ag_keyboard_interrupt_maps_to_red_default_maps_to_green(self, monkeypatch):
        statuses: dict[str, list[str]] = {"cx": [], "ag": []}

        def mock_hub_action(args, env, **kwargs):
            res = MagicMock()
            res.returncode = 0
            res.stdout = ""
            res.stderr = ""
            if args and args[0] == "terminal-handoff":
                res.stdout = "[HUB] TERMINAL-HANDOFF complete | lease=term-lease-kbint-test"
            elif args and args[0] == "health-update" and "--status" in args:
                peer = args[args.index("--peer") + 1]
                status = args[args.index("--status") + 1]
                statuses.setdefault(peer, []).append(status)
            return res

        monkeypatch.setattr("console_runner._run_hub_action", mock_hub_action)

        def interrupting_popen(cmd, env=None, cwd=None, **kwargs):
            proc = MagicMock()
            proc.pid = 1
            proc.wait.side_effect = KeyboardInterrupt()
            return proc

        cx_spec = ConsoleSessionSpec(peer_id="cx", cmd_prefix=["codex"], env={})
        cx_res = run_console_session(cx_spec, ["exec"], _popen_runner=interrupting_popen)
        assert cx_res.exit_code == 130
        assert statuses["cx"][-1] == "GREEN"

        ag_spec = ConsoleSessionSpec(
            peer_id="ag", cmd_prefix=["agy"], env={}, keyboard_interrupt_is_success=False,
        )
        ag_res = run_console_session(ag_spec, [], _popen_runner=interrupting_popen)
        assert ag_res.exit_code == 130
        assert statuses["ag"][-1] == "RED"


class TestS3OneWayDependency:
    """Enforces: argv -> C8 security prep -> ConsoleLaunch -> Lease Lifecycle -> Spawn/Wait."""

    def test_one_way_dependency_lease_failure_preserves_validated_argv(self, monkeypatch):
        monkeypatch.setenv("ALLOW_UNLEASED_CONSOLE", "1")

        def mock_hub_action(args, env, **kwargs):
            res = MagicMock()
            if args[0] == "terminal-handoff":
                res.returncode = 1
                res.stderr = "Lease service down"
            else:
                res.returncode = 0
                res.stdout = ""
                res.stderr = ""
            return res

        monkeypatch.setattr("console_runner._run_hub_action", mock_hub_action)

        spawned_cmd = None

        def mock_popen(cmd, env=None, cwd=None, **kwargs):
            nonlocal spawned_cmd
            spawned_cmd = cmd
            proc = MagicMock()
            proc.pid = 999
            proc.wait.return_value = 0
            proc.returncode = 0
            return proc

        spec = ConsoleSessionSpec(peer_id="cc", cmd_prefix=["claude"], env={})
        res = run_console_session(spec, [], _popen_runner=mock_popen)

        # C8 prep output must match spawned command
        assert spawned_cmd == ["claude"] + res.launch.final_argv
        assert "--dangerously-skip-permissions" in res.launch.final_argv
        assert res.launch.invocation_kind == InvocationKind.LOCAL_AGENT


class TestS3ChildConsoleIsolation:
    """2026-08-05: the real CLI child used to inherit the launching wrapper's
    console/process group, so a single Ctrl+C reaching that console killed
    every nested layer (cmd.exe's batch job, this python wrapper, and the
    real CLI) at once, regardless of where the interrupt came from."""

    def test_windows_spawn_uses_new_process_group(self, monkeypatch):
        monkeypatch.setenv("ALLOW_UNLEASED_CONSOLE", "1")
        monkeypatch.setattr("console_runner._run_hub_action", lambda *a, **k: MagicMock(returncode=1, stdout="", stderr="no lease service in test"))
        monkeypatch.setattr(sys, "platform", "win32")

        captured_kwargs = {}

        def mock_popen(cmd, env=None, cwd=None, **kwargs):
            captured_kwargs.update(kwargs)
            proc = MagicMock()
            proc.pid = 1
            proc.wait.return_value = 0
            proc.returncode = 0
            return proc

        spec = ConsoleSessionSpec(peer_id="cc", cmd_prefix=["claude"], env={})
        run_console_session(spec, [], _popen_runner=mock_popen)

        import subprocess
        assert captured_kwargs.get("creationflags") == subprocess.CREATE_NEW_PROCESS_GROUP

    def test_non_windows_spawn_omits_creationflags(self, monkeypatch):
        monkeypatch.setenv("ALLOW_UNLEASED_CONSOLE", "1")
        monkeypatch.setattr("console_runner._run_hub_action", lambda *a, **k: MagicMock(returncode=1, stdout="", stderr="no lease service in test"))
        monkeypatch.setattr(sys, "platform", "linux")

        captured_kwargs = {}

        def mock_popen(cmd, env=None, cwd=None, **kwargs):
            captured_kwargs.update(kwargs)
            proc = MagicMock()
            proc.pid = 1
            proc.wait.return_value = 0
            proc.returncode = 0
            return proc

        spec = ConsoleSessionSpec(peer_id="cc", cmd_prefix=["claude"], env={})
        run_console_session(spec, [], _popen_runner=mock_popen)

        assert "creationflags" not in captured_kwargs
