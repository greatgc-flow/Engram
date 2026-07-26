import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# The module to test
from _sys.core import hub

# T73: patch("...subprocess.Popen") patches the real, global subprocess module
# (hub.subprocess IS the subprocess module), which also poisons snapshot.py's
# OWN unrelated subprocess.Popen usage if action_ask happens to trigger
# _terminal_spend_guard -> _select_human_interface_peer -> collect_snapshot ->
# _codex_rate_limits. That function's reader thread does
# `while True: line = proc.stdout.readline(); if not line: break` -- against a
# MagicMock, readline() always returns a new (truthy) child Mock, so the loop
# never terminates: a real, deterministic infinite loop + unbounded queue growth
# (confirmed live: one repro run hit 16GB+ RAM in seconds). Every test below
# that calls action_ask patches _terminal_spend_guard to a no-op so it can
# never reach that code path -- these tests are about ask/lease/PTY behavior,
# not the terminal-spend-guard subsystem.
#
# Same class of bug, different mechanism: _action_ask_inner also has its own
# separate pacing_hard_gate check (unrelated to _terminal_spend_guard) that
# calls snapshot.collect_snapshot()/pacing_admission_for_profile() directly.
# This reads THIS MACHINE's real, current cc pacing ratio -- so a real busy
# day (this session alone made hundreds of real asks) can push it over the
# gate's max_ratio and reject a "to=cc" ask that has nothing to do with
# pacing at all. Every test also forces _SNAPSHOT_AVAILABLE=False, which
# every snapshot-dependent optional gate (pacing included) checks first and
# skips cleanly when false -- broader and more future-proof than patching
# each gate individually.

def test_at1_lease_closed_on_failure(tmp_path):
    """A subprocess ask that raises/exits nonzero still closes its lease."""
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    
    with patch("_sys.core.hub.subprocess.Popen") as mock_popen, \
         patch("_sys.core.hub._lease_close") as mock_lease_close, \
         patch("_sys.core.hub._kill_process_tree") as mock_kill, \
         patch("_sys.core.hub._record_ask_failure") as mock_record_failure, \
         patch("_sys.core.hub._append_ask_history"), \
         patch("_sys.core.hub._terminal_spend_guard"), \
         patch("_sys.core.hub._SNAPSHOT_AVAILABLE", False):

        # Setup mock process that fails
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.returncode = 1
        mock_proc.stdout.read.side_effect = [b"", b""] + [b""] * 50
        mock_proc.stderr.read.side_effect = [b"", b""] + [b""] * 50
        mock_proc.communicate.return_value = (b"", b"Error!")
        mock_proc.poll.return_value = 1
        mock_popen.return_value = mock_proc
        
        with pytest.raises(SystemExit) as exc:
            hub.action_ask(
                to="cc",
                query="test",
                query_file=None,
                timeout_sec=10,
                ai_root=ai_root,
                quiet=True,
                output_file=None,
                include_context=False,
                session_policy="auto",
                explicit_scope=None,
                _depth=0,
                origin="test"
            )
        
        from unittest.mock import ANY
        assert exc.value.code != 0
        # Ensure lease was closed even on exit, with whatever profile id it resolved to
        mock_lease_close.assert_called_with(ai_root, ANY, 12345, "failed")
        # A process that already EXITED (returncode set) must NOT be re-reaped —
        # the finally only reaps still-running processes (returncode is None).
        mock_kill.assert_not_called()

def test_at1_process_tree_reaped_on_timeout(tmp_path):
    """A PTY (or subprocess) ask that times out reaps the child tree."""
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    
    import subprocess
    with patch("_sys.core.hub.subprocess.Popen") as mock_popen, \
         patch("_sys.core.hub._stream_process_output",
               side_effect=subprocess.TimeoutExpired(cmd=["test"], timeout=1)), \
         patch("_sys.core.hub._kill_process_tree") as mock_kill, \
         patch("_sys.core.hub._record_ask_failure"), \
         patch("_sys.core.hub._append_ask_history"), \
         patch("_sys.core.hub._lease_close"), \
         patch("_sys.core.hub._terminal_spend_guard"), \
         patch("_sys.core.hub._SNAPSHOT_AVAILABLE", False):

        # Setup mock process that times out immediately (streaming reader raises).
        mock_proc = MagicMock()
        mock_proc.pid = 999
        mock_proc.poll.return_value = None
        # Still-running after timeout → returncode is None → finally MUST reap it.
        mock_proc.returncode = None
        mock_popen.return_value = mock_proc

        with pytest.raises(SystemExit) as exc:
            hub.action_ask(
                to="cc",
                query="test timeout",
                query_file=None,
                timeout_sec=1,
                ai_root=ai_root,
                quiet=True,
                output_file=None,
                include_context=False,
                session_policy="auto",
                explicit_scope=None,
                _depth=0,
                origin="test"
            )
        
        assert exc.value.code != 0
        mock_kill.assert_called_with(mock_proc)


def test_at1_health_written_before_exit(tmp_path):
    """On failure, health write must happen before function exits."""
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    
    with patch("_sys.core.hub.subprocess.Popen") as mock_popen, \
         patch("_sys.core.hub._record_ask_failure") as mock_record_failure, \
         patch("_sys.core.hub._kill_process_tree") as mock_kill, \
         patch("_sys.core.hub._append_ask_history"), \
         patch("_sys.core.hub._lease_close"), \
         patch("_sys.core.hub._terminal_spend_guard"), \
         patch("_sys.core.hub._SNAPSHOT_AVAILABLE", False):

        # Setup mock process that raises an exception
        mock_popen.side_effect = PermissionError("Cannot execute")
        
        with pytest.raises(SystemExit) as exc:
            hub.action_ask(
                to="cc",
                query="test failure",
                query_file=None,
                timeout_sec=10,
                ai_root=ai_root,
                quiet=True,
                output_file=None,
                include_context=False,
                session_policy="auto",
                explicit_scope=None,
                _depth=0,
                origin="test"
            )
        
        assert exc.value.code != 0
        # Health record must be called
        mock_record_failure.assert_called()


def test_at1_pty_success_not_reaped(tmp_path):
    """A PTY ask (to="ag") that returns a result successfully does NOT call _kill_process_tree."""
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)

    with patch("_sys.core.hub._ask_with_pty") as mock_ask, \
         patch("_sys.core.hub._kill_process_tree") as mock_kill, \
         patch("_sys.core.hub._ask_health_precheck", lambda *a, **k: None), \
         patch("_sys.core.hub._record_ask_success"), \
         patch("_sys.core.hub._append_ask_history"), \
         patch("_sys.core.hub._lease_close") as mock_lease_close, \
         patch("_sys.core.hub._runtime_cfg", return_value={"ag": {"requires_pty": True}}), \
         patch("_sys.core.hub._terminal_spend_guard"), \
         patch("_sys.core.hub._SNAPSHOT_AVAILABLE", False):
        
        from _sys.core.hub import _PtyAskResult
        mock_ask.return_value = _PtyAskResult(
            text="success", elapsed=1, exit_code=0, timed_out=False,
            timeout_kind=None, pid=54321, transport_error=None
        )

        hub.action_ask(
            to="ag",
            query="test",
            query_file=None,
            timeout_sec=10,
            ai_root=ai_root,
            quiet=True,
            output_file=None,
            include_context=False,
            session_policy="auto",
            explicit_scope=None,
            _depth=0,
            origin="test"
        )
        
        mock_kill.assert_not_called()


def test_at1_terminal_timeout_not_permanent_red(tmp_path):
    """after a terminal-timeout failure record, a subsequent success clears RED"""
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    
    cc_dir = tmp_path / "cc"
    cc_dir.mkdir()
    
    import subprocess
    with patch("_sys.core.hub.subprocess.Popen") as mock_popen, \
         patch("_sys.core.hub._stream_process_output",
               side_effect=subprocess.TimeoutExpired(cmd=["test"], timeout=1)), \
         patch("_sys.core.hub._kill_process_tree"), \
         patch("_sys.core.hub._append_ask_history"), \
         patch("_sys.core.hub._lease_close"), \
         patch("_sys.core.hub._load_orchestration", return_value={"hub_nodes": [{"type": "peer", "node_id": "cc", "enabled": True}]}), \
         patch("_sys.core.hub._peer_sys_dir", return_value=cc_dir), \
         patch("_sys.core.hub._terminal_spend_guard"), \
         patch("_sys.core.hub._CONTEXT_GATE_AVAILABLE", False), \
         patch("_sys.core.hub._SNAPSHOT_AVAILABLE", False):

        mock_proc = MagicMock()
        mock_proc.pid = 999
        mock_proc.poll.return_value = None
        mock_proc.returncode = None
        mock_popen.return_value = mock_proc
        
        with pytest.raises(SystemExit):
            hub.action_ask(
                to="cc",
                query="test timeout red",
                query_file=None,
                timeout_sec=1,
                ai_root=ai_root,
                quiet=True,
                output_file=None,
                include_context=False,
                session_policy="auto",
                explicit_scope=None,
                _depth=0,
                origin="test"
            )
            
    import json
    health_file = cc_dir / "health.json"
    data = json.loads(health_file.read_text())
    
    assert data.get("context_health", {}).get("status") != "RED"
    assert data.get("session_health", {}).get("transient_failures", 0) > 0


def test_at1_terminal_timeout_does_not_close_gate(tmp_path):
    """consensus-snapshot neutrality: a terminal_timeout must NOT close gate_open
    (the peer is presumed healthy; the hub killed it for its own deadline). Closing
    the gate would drop the peer from the consensus gate-OPEN quorum snapshot."""
    from _sys.core import hub
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    health_dir = tmp_path / "health"
    health_dir.mkdir()

    # Record a terminal_timeout failure directly.
    hub._record_ask_failure("cc", "terminal_timeout", "hub deadline", 5, ai_root, health_dir=health_dir)

    data = hub._read_json(health_dir / "health.json") if (health_dir / "health.json").exists() else {}
    avail = data.get("availability", {})
    # gate must remain open (not False) and status must not be RED.
    assert avail.get("gate_open") is not False, "terminal_timeout wrongly closed the gate (quorum impact)"
    assert data.get("context_health", {}).get("status") != "RED", "terminal_timeout wrongly RED-ed the peer"


def test_w1_missing_query_file_fails_loudly(tmp_path, capsys):
    """W1 (consensus 2026-07-03): a missing --query-file must print a clear
    stderr error (IPC files are single-use) and record an ask_history failure —
    never a silent exit 1."""
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)

    with patch("_sys.core.hub._append_ask_history") as mock_history, \
         patch("_sys.core.hub._terminal_spend_guard"), \
         patch("_sys.core.hub._SNAPSHOT_AVAILABLE", False):
        with pytest.raises(SystemExit) as exc:
            hub.action_ask(
                to="cc",
                query="",
                query_file=str(tmp_path / "nonexistent-ipc-file.txt"),
                timeout_sec=10,
                ai_root=ai_root,
                quiet=True,
                output_file=None,
                include_context=False,
                session_policy="auto",
                explicit_scope=None,
                _depth=0,
                origin="test",
            )

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "query file not found" in err
    assert "single-use" in err
    mock_history.assert_called_once()
    args = mock_history.call_args[0]
    assert args[5] is False  # success flag
    assert args[6] == "query_file_missing"


class TestT86TerminalHandoffDetectionSurvivesQueryFileUnlink:
    """T86 (backlog.json, deferred since 2026-07-22, fixed here): the
    terminal-handoff marker used to be re-read from query_file AFTER the
    ephemeral file was already unlink()'d a few lines earlier in the same
    ask flow -- the re-read always raised FileNotFoundError, silently
    swallowed by a bare `except Exception: pass`, so a real terminal-handoff
    ask could never be recognized as one and could get wrongly blocked by
    the pacing_hard_gate's over_cap guard. Fixed by capturing the marker
    once from raw_content, before the unlink."""

    def _run_with_pacing_over_cap(self, tmp_path, query_text):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        hub.ensure_ai_dir(ai_root)
        qf = tmp_path / "q.txt"
        qf.write_text(query_text, encoding="utf-8")

        surfaced_reasons = []

        def fake_surface(ai_root, to, reason, recovery_peer=None):
            surfaced_reasons.append(reason)

        mock_snapshot_row = {"profile": "cc.deepthink", "peer": "cc"}
        fake_snap = {"profiles": [mock_snapshot_row]}

        with patch("_sys.core.hub._load_balancer_config",
                   return_value={"pacing_hard_gate": {"enabled": True}}), \
             patch("_sys.core.hub._SNAPSHOT_AVAILABLE", True), \
             patch("_sys.core.hub.snapshot") as mock_snapshot_mod, \
             patch("_sys.core.hub.resolve_terminal_identity",
                   return_value={"peer": "cc", "is_active_terminal": True}), \
             patch("_sys.core.hub._human_interface_profile_for_peer",
                   return_value="cc.deepthink"), \
             patch("_sys.core.hub._surface_pre_dispatch_failure", side_effect=fake_surface), \
             patch("_sys.core.hub._terminal_spend_guard"), \
             patch("_sys.core.hub.subprocess.Popen") as mock_popen:

            mock_snapshot_mod._SNAPSHOT_CACHE = {}
            mock_snapshot_mod.collect_snapshot.return_value = fake_snap
            mock_snapshot_mod.pacing_admission_for_profile.return_value = "over_cap"

            mock_proc = MagicMock()
            mock_proc.pid = 4242
            mock_proc.returncode = 0
            mock_proc.stdout.read.side_effect = [b""] * 50
            mock_proc.stderr.read.side_effect = [b""] * 50
            mock_proc.poll.return_value = 0
            mock_popen.return_value = mock_proc

            try:
                hub.action_ask(
                    to="cc", query="unused", query_file=str(qf), timeout_sec=5,
                    ai_root=ai_root, quiet=True, output_file=None,
                    include_context=False, session_policy="auto",
                    explicit_scope=None, _depth=0, origin="test",
                )
            except SystemExit:
                pass

        return surfaced_reasons

    def test_handoff_marked_ask_is_not_blocked_by_pacing_over_cap(self, tmp_path):
        reasons = self._run_with_pacing_over_cap(tmp_path, "please run terminal-handoff now")
        assert "terminal_pacing_exhausted" not in reasons

    def test_non_handoff_ask_is_blocked_by_pacing_over_cap(self, tmp_path):
        reasons = self._run_with_pacing_over_cap(tmp_path, "just a normal question")
        assert "terminal_pacing_exhausted" in reasons
