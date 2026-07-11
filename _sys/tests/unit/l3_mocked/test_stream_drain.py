import json
import os
import sys
import subprocess
import threading
import time
import pytest
from pathlib import Path

# Add core to sys.path to import hub
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from core import hub

def test_stream_process_output_drain(tmp_path):
    """
    Test that _stream_process_output fully drains stdout and stderr
    even if the process exits quickly or produces a lot of stderr.
    """
    script_path = tmp_path / "dummy.py"
    script_path.write_text("""
import sys
import time

print("STDOUT 1")
print("STDERR 1", file=sys.stderr)
sys.stderr.flush()
sys.stdout.flush()
time.sleep(0.1)
print("STDOUT 2")
print("STDERR 2", file=sys.stderr)
""", encoding="utf-8")

    proc = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    output_bytes, process_err_bytes = hub._stream_process_output(
        proc=proc,
        cmd=["dummy.py"],
        input_bytes=None,
        heartbeat_sec=1.0,
        zombie_timeout_sec=5.0,
        timeout_sec=5.0,
        ai_root=tmp_path,
        to="dummy",
        lease_timeout_sec=5.0
    )

    output_str = output_bytes.decode('utf-8')
    process_err_str = process_err_bytes.decode('utf-8')

    assert "STDOUT 1" in output_str
    assert "STDOUT 2" in output_str
    assert "STDERR 1" in process_err_str
    assert "STDERR 2" in process_err_str


def test_stream_process_output_warns_on_silent_startup_without_killing(tmp_path, monkeypatch):
    """A peer that stays silent past the (non-lethal) warning threshold must
    emit a peer_silent_startup telemetry event but NEVER be killed by it -
    only the zombie window (reset on any output) can terminate the process."""
    script_path = tmp_path / "silent_then_output.py"
    script_path.write_text(
        """
import time
time.sleep(0.35)
print("DONE", flush=True)
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(hub, "_silent_startup_warning_sec", lambda: 0.05)
    proc = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    output_bytes, process_err_bytes = hub._stream_process_output(
        proc=proc,
        cmd=[sys.executable, str(script_path)],
        input_bytes=None,
        heartbeat_sec=1.0,
        zombie_timeout_sec=2.0,
        timeout_sec=2.0,
        ai_root=tmp_path,
        to="dummy",
        lease_timeout_sec=5.0,
    )

    assert "DONE" in output_bytes.decode("utf-8")
    assert process_err_bytes.decode("utf-8") == ""

    metrics_path = tmp_path / "routing_metrics.jsonl"
    events = [
        json.loads(line)
        for line in metrics_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    warning_events = [event for event in events if event.get("event") == "peer_silent_startup"]
    assert len(warning_events) == 1
    event = warning_events[0]
    assert event["level"] == "warning"
    assert event["peer_id"] == "dummy"
    assert event["node_id"] == "dummy"
    assert event["threshold_sec"] == int(0.05)
    assert event["elapsed_sec"] >= 0
    assert event["transport"] == "subprocess"


@pytest.mark.skipif(sys.platform != "win32", reason="_ask_with_pty is Windows-only (pywinpty)")
def test_ask_with_pty_does_not_kill_a_legitimately_slow_peer(tmp_path, monkeypatch):
    """The PTY path (ag/antigravity on Windows) must apply the SAME unified
    silence window as the subprocess path - this is exactly the code path
    ag's original round-1 diff missed, leaving it on the old kill-capable
    staged startup timeout while cx's path got fixed. This is the core safety
    property; see the note below on why the peer_silent_startup telemetry
    assertion is NOT made here for the PTY transport specifically."""
    pytest.importorskip("winpty")

    script_path = tmp_path / "silent_then_output.py"
    script_path.write_text(
        """
import time
time.sleep(0.35)
print("DONE", flush=True)
""",
        encoding="utf-8",
    )

    # NOTE (verified empirically, not assumed): Windows PTY emits terminal-init
    # escape sequences (window title / mode queries, e.g. "\x1b[1t") within
    # single-digit milliseconds of every spawn, before the child script itself
    # produces any real output. This means the "not chunks" gate in
    # _ask_with_pty's peer_silent_startup check is satisfied almost instantly
    # by PTY noise on EVERY call, regardless of tier - the telemetry event is
    # not a meaningful signal for this transport (unlike the plain subprocess
    # path, which has no such noise). This does NOT affect the actual safety
    # fix: last_activity resets on any byte (including PTY noise) is fine and
    # conservative for the kill-avoidance guarantee, which is what this test
    # verifies. The telemetry gap is a known, non-blocking follow-up.
    monkeypatch.setattr(hub, "_silent_startup_warning_sec", lambda: 0.05)

    result = hub._ask_with_pty(
        cmd=[sys.executable, str(script_path)],
        node_id="dummy",
        timeout_sec=5,
        process_env=dict(os.environ),
        ai_root=tmp_path,
    )

    assert result.timed_out is False
    assert result.timeout_kind is None
    assert "DONE" in result.text
