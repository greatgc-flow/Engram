"""C7 process supervision, soft-skip, and lease timestamp regressions."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from _sys.core import hub


class _FakeAdapter:
    def build_cmd(self, node, query):
        return [sys.executable, "-c", "pass"], False

    def parse_output(self, raw_text, node):
        return raw_text

    def session_fingerprint(self, node):
        return "c7-test"


def _patch_ask_runtime(monkeypatch):
    """Keep action_ask focused on its transport/supervision control flow."""
    healthy = {
        "context_health": {"status": "GREEN"},
        "session_health": {"consecutive_failures": 0},
        "availability": {"gate_open": True, "profiles": {}},
    }
    monkeypatch.setattr(
        hub,
        "_read_peer_health",
        lambda *args, **kwargs: ("GREEN", healthy),
    )
    monkeypatch.setattr(hub, "_lease_sweep", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "action_consensus_sweep", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_ask_health_precheck", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_guard_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_terminal_spend_guard", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_record_ask_failure", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_record_ask_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_append_ask_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_record_routing_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_append_handoff_item", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_get_logger", lambda: None)
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", False)
    monkeypatch.setattr(hub, "_CONTEXT_GATE_AVAILABLE", False)
    monkeypatch.setattr(hub, "_resolve_invoke_cli", lambda exe: sys.executable)
    monkeypatch.setattr(hub.hub_peer, "get_adapter", lambda node: _FakeAdapter())


@pytest.mark.parametrize(
    ("spawned", "expected_category"),
    [(False, "not_started"), (True, "execution_uncertain")],
)
def test_pipe_transient_soft_skip_exits_7_by_execution_certainty(
    monkeypatch, tmp_path, capsys, spawned, expected_category
):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    _patch_ask_runtime(monkeypatch)

    if spawned:
        proc = MagicMock()
        proc.pid = 41001
        proc.returncode = 1
        proc.poll.return_value = 1
        monkeypatch.setattr(hub, "_spawn_process", lambda *args, **kwargs: proc)
        monkeypatch.setattr(
            hub,
            "_stream_process_output",
            lambda *args, **kwargs: (b"", b"rate limit exceeded"),
        )
        monkeypatch.setattr(hub, "_lease_open", lambda *args, **kwargs: "lease-c7")
        monkeypatch.setattr(hub, "_lease_close", lambda *args, **kwargs: None)
    else:
        denied = hub.SandboxSpawnDeniedError(
            ["blocked-cli"], PermissionError("spawn denied")
        )

        def _deny(*args, **kwargs):
            raise denied

        monkeypatch.setattr(hub, "_spawn_process", _deny)

    with pytest.raises(SystemExit) as exc:
        hub.action_ask(
            to="cc.standard",
            query="c7 soft skip",
            query_file=None,
            timeout_sec=5,
            ai_root=ai_root,
            quiet=True,
            output_file=None,
            include_context=False,
            session_policy="none",
            _escalation_depth=1,
            origin="test",
            allow_governed_mutation=True,
            governed_mutation_reason="C7 regression",
        )

    assert exc.value.code == hub.SOFT_SKIP_EXIT
    captured = capsys.readouterr()
    assert f"category={expected_category}" in captured.out + captured.err


@pytest.mark.parametrize(
    ("codes", "expected_exit"),
    [
        ({"cc": 0, "ag": 7, "cx": 2}, None),
        ({"cc": 7, "ag": 7, "cx": 7}, 7),
        ({"cc": 7, "ag": 2, "cx": 1}, 2),
    ],
    ids=["one_answered", "all_soft_skipped", "hard_failure_without_answer"],
)
def test_action_ask_all_aggregates_child_exit_codes(
    monkeypatch, tmp_path, capsys, codes, expected_exit
):
    peers = list(codes)
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setattr(
        hub,
        "_load_orchestration",
        lambda: {
            "hub_nodes": [
                {"node_id": peer, "type": "peer", "enabled": True}
                for peer in peers
            ]
        },
    )
    monkeypatch.setattr(hub, "is_routable", lambda *args, **kwargs: True)

    def _run(cmd, **kwargs):
        peer = cmd[cmd.index("--to") + 1]
        code = codes[peer]
        return subprocess.CompletedProcess(
            cmd,
            code,
            stdout=(f"answer from {peer}" if code == 0 else ""),
            stderr=(f"exit {code}" if code else ""),
        )

    monkeypatch.setattr(hub.subprocess, "run", _run)

    if expected_exit is None:
        hub.action_ask_all("question", None, 5, None, quiet=True)
    else:
        with pytest.raises(SystemExit) as exc:
            hub.action_ask_all("question", None, 5, None, quiet=True)
        assert exc.value.code == expected_exit

    output = capsys.readouterr().out
    if hub.SOFT_SKIP_EXIT in codes.values():
        assert "[SOFT-SKIP]" in output


def test_pipe_escalation_closes_source_lease_before_recursing_once(
    monkeypatch, tmp_path
):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    _patch_ask_runtime(monkeypatch)

    procs = []
    for pid in (42001, 42002):
        proc = MagicMock()
        proc.pid = pid
        proc.returncode = 0
        proc.poll.return_value = 0
        procs.append(proc)
    spawn_index = 0
    events = []

    def _spawn(*args, **kwargs):
        nonlocal spawn_index
        proc = procs[spawn_index]
        spawn_index += 1
        events.append(("spawn", proc.pid))
        return proc

    stream_results = iter([(b"[ESCALATE]\n", b""), (b"final answer\n", b"")])
    lease_ids = iter(["lease-source", "lease-target"])
    opened_ask_ids = []

    def _open(root, peer, pid, timeout, ask_id=None, ask_query_file=None):
        lease_id = next(lease_ids)
        opened_ask_ids.append(ask_id)
        events.append(("open", lease_id, pid))
        return lease_id

    def _close(root, lease_id, pid, status):
        events.append(("close", lease_id, pid, status))

    monkeypatch.setattr(hub, "_spawn_process", _spawn)
    monkeypatch.setattr(
        hub, "_stream_process_output", lambda *args, **kwargs: next(stream_results)
    )
    monkeypatch.setattr(hub, "_lease_open", _open)
    monkeypatch.setattr(hub, "_lease_close", _close)
    monkeypatch.setattr(
        hub,
        "_runtime_escalation_target",
        lambda selected: "cc.effort" if selected == "cc.standard" else None,
    )

    hub.action_ask(
        to="cc.standard",
        query="discover complexity",
        query_file=None,
        timeout_sec=5,
        ai_root=ai_root,
        quiet=True,
        output_file=None,
        include_context=False,
        session_policy="none",
        _escalation_depth=1,
        origin="test",
        allow_governed_mutation=True,
        governed_mutation_reason="C7 regression",
    )

    assert events == [
        ("spawn", 42001),
        ("open", "lease-source", 42001),
        ("close", "lease-source", 42001, "escalated"),
        ("spawn", 42002),
        ("open", "lease-target", 42002),
        ("close", "lease-target", 42002, "closed"),
    ]
    assert opened_ask_ids[0] == opened_ask_ids[1]


@pytest.mark.skipif(sys.platform != "win32", reason="PTY dispatch is Windows-only")
def test_pty_escalation_closes_source_lease_before_recursing_once(
    monkeypatch, tmp_path
):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    _patch_ask_runtime(monkeypatch)

    results = iter(
        [
            hub._PtyAskResult(
                text="[ESCALATE]\n",
                elapsed=1,
                exit_code=0,
                timed_out=False,
                timeout_kind=None,
                pid=43001,
                lease_id="pty-source",
            ),
            hub._PtyAskResult(
                text="final answer\n",
                elapsed=1,
                exit_code=0,
                timed_out=False,
                timeout_kind=None,
                pid=43002,
                lease_id="pty-target",
            ),
        ]
    )
    events = []
    ask_ids = []

    def _ask_with_pty(cmd, node_id, timeout_sec, process_env, **kwargs):
        result = next(results)
        ask_ids.append(kwargs.get("ask_id"))
        events.append(("spawn", result.pid))
        return result

    def _close(root, lease_id, pid, status):
        events.append(("close", lease_id, pid, status))

    monkeypatch.setattr(hub, "_ask_with_pty", _ask_with_pty)
    monkeypatch.setattr(hub, "_lease_close", _close)
    monkeypatch.setattr(
        hub,
        "_runtime_escalation_target",
        lambda selected: "ag.effort" if selected == "ag.standard" else None,
    )

    hub.action_ask(
        to="ag.standard",
        query="discover complexity",
        query_file=None,
        timeout_sec=5,
        ai_root=ai_root,
        quiet=True,
        output_file=None,
        include_context=False,
        session_policy="none",
        _escalation_depth=1,
        origin="test",
        allow_governed_mutation=True,
        governed_mutation_reason="C7 regression",
    )

    assert events == [
        ("spawn", 43001),
        ("close", "pty-source", 43001, "escalated"),
        ("spawn", 43002),
        ("close", "pty-target", 43002, "closed"),
    ]
    assert ask_ids[0] == ask_ids[1]


@pytest.mark.skipif(sys.platform != "win32", reason="PTY dispatch is Windows-only")
def test_pty_timeout_soft_skips_instead_of_hard_failing(monkeypatch, tmp_path, capsys):
    """Regression (ag cross-verification finding): the PTY result.timed_out
    branch previously always called sys.exit(1), even though its own
    reason ("terminal_timeout") is a _TRANSIENT_REASONS member and the
    sibling result.exit_code!=0 block already soft-skips on it -- an
    inconsistent PTY-only gap versus the Pipe transport's equivalent path."""
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    _patch_ask_runtime(monkeypatch)

    result = hub._PtyAskResult(
        text="",
        elapsed=5,
        exit_code=None,
        timed_out=True,
        timeout_kind="hard",
        pid=49001,
        lease_id="pty-timeout",
    )
    monkeypatch.setattr(hub, "_ask_with_pty", lambda *args, **kwargs: result)
    monkeypatch.setattr(hub, "_lease_close", lambda *args, **kwargs: None)

    with pytest.raises(SystemExit) as exc:
        hub.action_ask(
            to="ag.standard",
            query="pty timeout regression",
            query_file=None,
            timeout_sec=5,
            ai_root=ai_root,
            quiet=True,
            output_file=None,
            include_context=False,
            session_policy="none",
            _escalation_depth=1,
            origin="test",
            allow_governed_mutation=True,
            governed_mutation_reason="C7 regression",
        )

    assert exc.value.code == hub.SOFT_SKIP_EXIT
    captured = capsys.readouterr()
    assert "category=execution_uncertain" in captured.out + captured.err


@pytest.mark.skipif(sys.platform != "win32", reason="PTY dispatch is Windows-only")
def test_pty_transient_transport_error_soft_skips_instead_of_hard_failing(
    monkeypatch, tmp_path, capsys
):
    """Same gap as the timeout case, for a transient transport_error (e.g. a
    rate limit hit while the PTY child was starting/running)."""
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    _patch_ask_runtime(monkeypatch)

    result = hub._PtyAskResult(
        text="",
        elapsed=2,
        exit_code=None,
        timed_out=False,
        timeout_kind=None,
        pid=49002,
        lease_id="pty-transport-error",
        transport_error="rate limit exceeded, retry after reset",
    )
    monkeypatch.setattr(hub, "_ask_with_pty", lambda *args, **kwargs: result)
    monkeypatch.setattr(hub, "_lease_close", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        hub,
        "_classify_ask_failure",
        lambda detail: ("rate_or_session_limit", {"rate_limit_state": {"reset_at": "soon"}}),
    )

    with pytest.raises(SystemExit) as exc:
        hub.action_ask(
            to="ag.standard",
            query="pty transport error regression",
            query_file=None,
            timeout_sec=5,
            ai_root=ai_root,
            quiet=True,
            output_file=None,
            include_context=False,
            session_policy="none",
            _escalation_depth=1,
            origin="test",
            allow_governed_mutation=True,
            governed_mutation_reason="C7 regression",
        )

    assert exc.value.code == hub.SOFT_SKIP_EXIT
    captured = capsys.readouterr()
    assert "category=execution_uncertain" in captured.out + captured.err


def test_pipe_escalation_aborts_when_source_lease_close_fails(
    monkeypatch, tmp_path
):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    _patch_ask_runtime(monkeypatch)

    proc = MagicMock()
    proc.pid = 44001
    proc.returncode = 0
    proc.poll.return_value = 0
    spawn_count = 0

    def _spawn(*args, **kwargs):
        nonlocal spawn_count
        spawn_count += 1
        return proc

    def _close(root, lease_id, pid, status):
        if status == "escalated":
            raise hub.LeaseOwnershipError("source lease close failed")

    monkeypatch.setattr(hub, "_spawn_process", _spawn)
    monkeypatch.setattr(
        hub,
        "_stream_process_output",
        lambda *args, **kwargs: (b"[ESCALATE]\n", b""),
    )
    monkeypatch.setattr(hub, "_lease_open", lambda *args, **kwargs: "lease-source")
    monkeypatch.setattr(hub, "_lease_close", _close)
    monkeypatch.setattr(hub, "_runtime_escalation_target", lambda selected: "cc.effort")

    with pytest.raises(SystemExit) as exc:
        hub.action_ask(
            to="cc.standard",
            query="discover complexity",
            query_file=None,
            timeout_sec=5,
            ai_root=ai_root,
            quiet=True,
            output_file=None,
            include_context=False,
            session_policy="none",
            _escalation_depth=1,
            origin="test",
            allow_governed_mutation=True,
            governed_mutation_reason="C7 regression",
        )

    assert exc.value.code != 0
    assert spawn_count == 1


def test_small_flushed_chunks_keep_pipe_alive_until_clean_exit(tmp_path):
    """Old BufferedReader.read(65536) blocked until EOF and timed this child out."""
    script = tmp_path / "small_chunks.py"
    script.write_text(
        "import sys, time\n"
        "for _ in range(8):\n"
        "    sys.stdout.buffer.write(b'x')\n"
        "    sys.stdout.buffer.flush()\n"
        "    time.sleep(0.12)\n",
        encoding="utf-8",
    )
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    )

    out, err = hub._stream_process_output(
        proc,
        [sys.executable, str(script)],
        None,
        heartbeat_sec=0.05,
        zombie_timeout_sec=0.4,
        timeout_sec=3,
        ai_root=None,
        to="c7-small-chunks",
        lease_timeout_sec=5,
    )

    assert out == b"x" * 8
    assert err == b""
    assert proc.returncode == 0


def test_raw_pipe_fallback_uses_os_read():
    read_fd, write_fd = os.pipe()
    raw_reader = os.fdopen(read_fd, "rb", buffering=0)
    assert isinstance(raw_reader, io.FileIO)
    writer_done = threading.Event()

    class _RawProc:
        stdin = None
        stderr = None
        stdout = raw_reader
        pid = 45001

        def poll(self):
            return 0 if writer_done.is_set() else None

    def _writer():
        os.write(write_fd, b"raw-fallback")
        os.close(write_fd)
        writer_done.set()

    thread = threading.Thread(target=_writer)
    thread.start()
    try:
        out, err = hub._stream_process_output(
            _RawProc(),
            ["raw-proc"],
            None,
            heartbeat_sec=0.05,
            zombie_timeout_sec=1,
            timeout_sec=2,
            ai_root=None,
            to="raw-proc",
            lease_timeout_sec=5,
        )
    finally:
        thread.join(timeout=2)
        raw_reader.close()

    assert out == b"raw-fallback"
    assert err == b""


def test_reader_thread_exception_is_surfaced_to_supervisor():
    class _BrokenStream:
        def fileno(self):
            raise OSError("reader exploded")

    class _BrokenProc:
        stdin = None
        stdout = _BrokenStream()
        stderr = None
        pid = 46001

        def poll(self):
            return None

    with pytest.raises(hub.PipeReaderError, match="stdout reader failed.*reader exploded"):
        hub._stream_process_output(
            _BrokenProc(),
            ["broken-proc"],
            None,
            heartbeat_sec=0.05,
            zombie_timeout_sec=1,
            timeout_sec=2,
            ai_root=None,
            to="broken-proc",
            lease_timeout_sec=5,
        )


def test_lease_writers_preserve_timezone_offsets(monkeypatch, tmp_path):
    ai_root = tmp_path / ".ai"
    (ai_root / ".lock").mkdir(parents=True)
    (ai_root / "state.json").write_text("{}", encoding="utf-8")
    (ai_root / "leases.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(hub, "_now", lambda: "2040-01-02T03:04:05+09:00")

    lease_id = hub._lease_open(ai_root, "cx", 47001, 90, ask_id="ask-c7")
    assert lease_id is not None
    leases = json.loads((ai_root / "leases.json").read_text(encoding="utf-8"))
    assert leases[lease_id]["started_at"] == "2040-01-02T03:04:05+09:00"
    assert leases[lease_id]["expires_at"] == "2040-01-02T03:05:35+09:00"

    hub._lease_renew(ai_root, lease_id, 47001, 120)
    leases = json.loads((ai_root / "leases.json").read_text(encoding="utf-8"))
    assert leases[lease_id]["heartbeat_at"] == "2040-01-02T03:04:05+09:00"
    assert leases[lease_id]["expires_at"] == "2040-01-02T03:06:05+09:00"


def test_legacy_naive_lease_timestamp_is_localized_before_utc_conversion():
    kst = timezone(timedelta(hours=9))
    parsed = hub._parse_lease_timestamp(
        "2040-01-02T03:04:05",
        local_timezone=kst,
    )

    assert parsed == datetime(2040, 1, 1, 18, 4, 5, tzinfo=timezone.utc)
    assert parsed != datetime(2040, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_lease_sweep_quarantines_invalid_timestamps_and_validates_pid(
    monkeypatch, tmp_path, capsys
):
    ai_root = tmp_path / ".ai"
    (ai_root / ".lock").mkdir(parents=True)
    leases = {
        "missing-ts": {
            "peer_id": "cc",
            "pid": 48001,
            "status": "open",
        },
        "corrupt-ts": {
            "peer_id": "ag",
            "pid": 48002,
            "status": "open",
            "expires_at": "not-a-timestamp",
        },
        "expired-valid-pid": {
            "peer_id": "cx",
            "pid": 48003,
            "status": "open",
            "expires_at": "2039-12-31T23:59:59",
        },
        "expired-invalid-pid": {
            "peer_id": "cx",
            "pid": "48004",
            "status": "open",
            "expires_at": "2039-12-31T23:59:59",
        },
    }
    (ai_root / "leases.json").write_text(
        json.dumps(leases), encoding="utf-8"
    )
    killed = []
    monkeypatch.setattr(hub, "_now", lambda: "2040-01-01T00:00:01")
    monkeypatch.setattr(hub, "_pid_alive", lambda pid: pid == 48003)
    monkeypatch.setattr(hub, "_kill_process_tree", killed.append)
    monkeypatch.setattr(hub, "_record_ask_failure", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_log_p2p", lambda *args, **kwargs: None)

    hub._lease_sweep(ai_root)

    swept = json.loads((ai_root / "leases.json").read_text(encoding="utf-8"))
    for lease_id in ("missing-ts", "corrupt-ts"):
        assert swept[lease_id]["status"] == "invalid_timestamp"
        assert swept[lease_id]["quarantined"] is True
        assert swept[lease_id]["quarantine_reason"] == "invalid_timestamp"
    assert swept["expired-valid-pid"]["status"] == "expired"
    assert swept["expired-invalid-pid"]["status"] == "expired"
    assert killed == [48003]
    err = capsys.readouterr().err
    assert "reason=invalid_timestamp" in err
    assert "invalid pid='48004'; kill skipped" in err


def test_real_arbiter_soft_skip_has_distinct_telemetry_tag(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        hub.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            hub.SOFT_SKIP_EXIT,
            stdout="",
            stderr="temporarily unavailable",
        ),
    )
    invoker = hub._real_arbiter_invoker(tmp_path)

    result = hub.invoke_arbiter(
        tmp_path,
        {
            "fire": True,
            "arbiter": "cc.fable",
            "kind": "dissent",
            "authority": "override",
        },
        {"round_id": "r-c7", "proposal": "test"},
        {},
        invoker,
    )

    assert result["error"] == "arbiter_soft_skipped"
    assert "soft-skipped" in result["detail"]
