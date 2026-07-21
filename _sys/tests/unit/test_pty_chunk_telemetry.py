"""Tests for T23: permanent PTY reader-loop chunk-arrival telemetry.

Added 2026-07-12 (cc.fable-ratified) as the load-bearing measurement for
distinguishing real CPU/priority throttling of a backgrounded process tree
(steady, evenly-paced chunk reads) from PTY-reader-thread/ConPTY-backpressure
starvation (bursty reads - many chunks dequeued at once after a long gap) -
see peer-characteristics.jsonl's PC-20260712-agent-backgrounding-degrades-long-asks.
Purely additive observability; does not change _ask_with_pty's read/dequeue
timing or the zombie-timeout/heartbeat mechanisms.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import pytest

import hub


def _chunk(read_elapsed, dequeue_elapsed, byte_count, bytes_total, queue_delay):
    return {
        "read_elapsed_sec": read_elapsed,
        "dequeue_elapsed_sec": dequeue_elapsed,
        "byte_count": byte_count,
        "bytes_total": bytes_total,
        "queue_delay_sec": queue_delay,
    }


class TestPtyChunkTelemetryConfig:
    def test_defaults_when_config_missing(self, monkeypatch):
        monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {})
        assert hub._pty_chunk_telemetry_cfg() == (True, 500)

    def test_reads_declared_config(self, monkeypatch):
        monkeypatch.setattr(
            hub, "_load_protocol_cfg",
            lambda: {"communication_policy": {"pty_chunk_telemetry_enabled": False, "pty_chunk_telemetry_max_chunks": 10}},
        )
        assert hub._pty_chunk_telemetry_cfg() == (False, 10)

    def test_falls_back_safely_on_error(self, monkeypatch):
        def _boom():
            raise RuntimeError("config load failed")
        monkeypatch.setattr(hub, "_load_protocol_cfg", _boom)
        assert hub._pty_chunk_telemetry_cfg() == (True, 500)


class TestChunkByteCount:
    def test_counts_bytes_directly(self):
        assert hub._chunk_byte_count(b"hello") == 5

    def test_counts_str_as_utf8_bytes(self):
        assert hub._chunk_byte_count("héllo") == len("héllo".encode("utf-8"))


class TestPercentileHelper:
    def test_empty_list_returns_none(self):
        assert hub._pct([], 0.5) is None

    def test_single_value(self):
        assert hub._pct([3.0], 0.95) == 3.0

    def test_p50_of_sorted_values(self):
        # [1,2,3,4,5] -> p50 (median) is 3.0
        assert hub._pct([5.0, 1.0, 3.0, 2.0, 4.0], 0.5) == 3.0


class TestRecordPtyChunkArrivalMetric:
    def test_records_aggregate_event_shape(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )
        chunks = [
            _chunk(0.0, 0.01, 10, 10, 0.01),
            _chunk(1.0, 1.02, 20, 30, 0.02),
        ]
        hub._record_pty_chunk_arrival_metric(
            tmp_path, peer_id="ag", ask_id="ask-1", pid=123,
            elapsed_sec=5, timed_out=False, timeout_kind=None, transport_error=None,
            chunks=chunks, max_chunks=500,
        )
        assert calls and calls[0][0] == "pty_chunk_arrival"
        fields = calls[0][1]
        assert fields["peer_id"] == "ag"
        assert fields["ask_id"] == "ask-1"
        assert fields["pid"] == 123
        assert fields["chunks_observed"] == 2
        assert fields["chunks_recorded"] == 2
        assert fields["chunks_truncated"] is False
        assert fields["bytes_total"] == 30
        assert fields["chunks"] == chunks

    def test_percentile_and_gap_aggregation_is_correct(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )
        # read gaps: 1.0 -> 0.0=1.0, 3.0 -> 1.0=2.0
        chunks = [
            _chunk(0.0, 0.05, 5, 5, 0.05),
            _chunk(1.0, 1.10, 5, 10, 0.10),
            _chunk(3.0, 3.20, 5, 15, 0.20),
        ]
        hub._record_pty_chunk_arrival_metric(
            tmp_path, peer_id="ag", ask_id=None, pid=1,
            elapsed_sec=3, timed_out=False, timeout_kind=None, transport_error=None,
            chunks=chunks, max_chunks=500,
        )
        fields = calls[0][1]
        assert fields["read_gap_min_sec"] == 1.0
        assert fields["read_gap_max_sec"] == 2.0
        assert fields["queue_delay_min_sec"] == 0.05
        assert fields["queue_delay_max_sec"] == 0.20

    def test_truncates_recorded_chunks_but_keeps_full_summary(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )
        chunks = [
            _chunk(0.0, 0.01, 10, 10, 0.01),
            _chunk(1.0, 1.01, 10, 20, 0.01),
            _chunk(2.0, 2.01, 10, 30, 0.01),
        ]
        hub._record_pty_chunk_arrival_metric(
            tmp_path, peer_id="ag", ask_id=None, pid=1,
            elapsed_sec=2, timed_out=False, timeout_kind=None, transport_error=None,
            chunks=chunks, max_chunks=2,
        )
        fields = calls[0][1]
        assert fields["chunks_observed"] == 3
        assert fields["chunks_recorded"] == 2
        assert fields["chunks_truncated"] is True
        assert fields["bytes_total"] == 30  # summary reflects ALL chunks, not just recorded

    def test_no_ai_root_is_a_noop(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )
        hub._record_pty_chunk_arrival_metric(
            None, peer_id="ag", ask_id=None, pid=1,
            elapsed_sec=0, timed_out=False, timeout_kind=None, transport_error=None,
            chunks=[], max_chunks=500,
        )
        assert calls == []

    def test_empty_chunks_records_zero_bytes_and_no_gap_stats(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )
        hub._record_pty_chunk_arrival_metric(
            tmp_path, peer_id="ag", ask_id=None, pid=1,
            elapsed_sec=60, timed_out=True, timeout_kind="zombie", transport_error=None,
            chunks=[], max_chunks=500,
        )
        fields = calls[0][1]
        assert fields["bytes_total"] == 0
        assert fields["chunks_observed"] == 0
        assert fields["read_gap_min_sec"] is None
        assert fields["timed_out"] is True
        assert fields["timeout_kind"] == "zombie"


@pytest.mark.skipif(sys.platform != "win32", reason="pywinpty is Windows-only")
class TestPtyChunkTelemetryFromRealPty:
    def test_records_from_real_pty_invocation(self, tmp_path, monkeypatch):
        pytest.importorskip("winpty")
        monkeypatch.setattr(hub, "_pty_chunk_telemetry_cfg", lambda: (True, 500))
        monkeypatch.setattr(hub, "_lease_open", lambda *a, **kw: None)
        monkeypatch.setattr(hub, "_lease_renew", lambda *a, **kw: None)
        monkeypatch.setattr(hub, "_lease_cfg", lambda node_id: (1.0, 5.0, 5.0))
        monkeypatch.setattr(hub, "_silent_startup_warning_sec", lambda: 0)

        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )

        cmd = [sys.executable, "-c", "print('line one'); print('line two')"]
        result = hub._ask_with_pty(cmd, "test-node", 10, {**__import__("os").environ}, quiet=True, ai_root=tmp_path)

        assert not result.timed_out
        pty_events = [c for c in calls if c[0] == "pty_chunk_arrival"]
        assert len(pty_events) == 1
        assert pty_events[0][1]["chunks_observed"] >= 1

    def test_disabled_by_config_emits_no_event(self, tmp_path, monkeypatch):
        pytest.importorskip("winpty")
        monkeypatch.setattr(hub, "_pty_chunk_telemetry_cfg", lambda: (False, 500))
        monkeypatch.setattr(hub, "_lease_open", lambda *a, **kw: None)
        monkeypatch.setattr(hub, "_lease_renew", lambda *a, **kw: None)
        monkeypatch.setattr(hub, "_lease_cfg", lambda node_id: (1.0, 5.0, 5.0))
        monkeypatch.setattr(hub, "_silent_startup_warning_sec", lambda: 0)

        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )

        cmd = [sys.executable, "-c", "print('line one')"]
        hub._ask_with_pty(cmd, "test-node", 10, {**__import__("os").environ}, quiet=True, ai_root=tmp_path)

        assert not any(c[0] == "pty_chunk_arrival" for c in calls)


@pytest.mark.skipif(sys.platform != "win32", reason="pywinpty is Windows-only")
class TestPtyTimeoutCleanupDoesNotDeadlock:
    """T84 (2026-07-22, ag.deepthink's forensic trace): p.terminate()/p.close()
    call winpty's C-extension winpty_free, which can block the MAIN THREAD
    indefinitely if winpty-agent.exe is itself wedged -- masking a correctly-
    firing zombie watchdog as "never fired" from the outside, since hub.py
    never reaches the code that reports the timeout. Cleanup now runs on a
    bounded daemon thread so a hung winpty_free is abandoned, not awaited."""

    def test_hung_pty_cleanup_does_not_block_the_timeout_report(self, tmp_path, monkeypatch):
        pytest.importorskip("winpty")
        monkeypatch.setattr(hub, "_lease_open", lambda *a, **kw: None)
        monkeypatch.setattr(hub, "_lease_renew", lambda *a, **kw: None)
        monkeypatch.setattr(hub, "_lease_cfg", lambda node_id: (0.1, 0.5, 0.2))
        monkeypatch.setattr(hub, "_silent_startup_warning_sec", lambda: 0)
        monkeypatch.setattr(hub, "_kill_process_tree", lambda pid: None)

        import winpty as _winpty

        def _hang(*_args, **_kwargs):
            time.sleep(10)

        monkeypatch.setattr(_winpty.PtyProcess, "terminate", _hang)
        monkeypatch.setattr(_winpty.PtyProcess, "close", _hang)

        # A process that just sleeps -- never produces output, so the tiny
        # zombie_timeout_sec (0.2s) above forces timed_out=True quickly.
        cmd = [sys.executable, "-c", "import time; time.sleep(30)"]

        started = time.monotonic()
        result = hub._ask_with_pty(
            cmd, "test-node", 5, {**__import__("os").environ}, quiet=True, ai_root=tmp_path,
        )
        elapsed = time.monotonic() - started

        assert result.timed_out is True
        # Bounded by the cleanup thread's join(timeout=2.0), not the hang's 10s.
        assert elapsed < 5.0


class TestNonPtyPathNeverEmitsPtyChunkArrival:
    def test_stream_process_output_does_not_record_pty_metric(self, tmp_path, monkeypatch):
        import subprocess
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )
        script = tmp_path / "dummy.py"
        script.write_text("print('hello')\n", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE,
        )
        hub._stream_process_output(
            proc=proc, cmd=["dummy.py"], input_bytes=None,
            heartbeat_sec=1.0, zombie_timeout_sec=5.0, timeout_sec=5.0,
            ai_root=tmp_path, to="dummy", lease_timeout_sec=5.0,
        )
        assert not any(c[0] == "pty_chunk_arrival" for c in calls)
