"""PTY transport tests (ag-only path) — A2/A5/A7 + _PtyAskResult.

Uses a fake winpty child so no real `agy` is launched. Targets `_ask_with_pty`
directly: the A2 fix (a blocking read must NOT prevent the execution deadline),
exit-code capture (A5), spawn-failure transport error, cwd propagation (A7),
silent-zombie timeout, and the CONDITION-2 lease contract (open-here, the
caller closes).

NOTE: authored by the terminal as a verification artifact while worker peers
were quota/transport-blocked; the production PTY implementation was worker-
applied (cc.deepthink) and N=2 ratified. Asserts against the real applied API.
"""
import sys
import time
import types
import threading

import pytest

sys.path.insert(0, __import__("os").path.join(
    __import__("os").path.dirname(__file__), "..", "..", "core"))
import hub  # noqa: E402


class _FakePty:
    """Minimal stand-in for winpty.PtyProcess."""
    spawn_calls: list = []
    _behavior: dict = {}

    def __init__(self, behavior):
        self.behavior = behavior
        self.pid = behavior.get("pid", 4242)
        self.exitstatus = behavior.get("exitstatus", 0)
        self._reads = list(behavior.get("reads", []))  # str chunks; then EOF
        self._alive = True
        self.terminated = False
        self.closed = False

    @classmethod
    def spawn(cls, cmd, cwd=None, env=None):
        cls.spawn_calls.append({"cmd": cmd, "cwd": cwd, "env": env})
        if cls._behavior.get("spawn_raises"):
            raise RuntimeError("spawn boom")
        return cls(cls._behavior)

    def read(self, n):
        if self.behavior.get("block"):
            # Simulate a blocking read that ends only when the main thread
            # terminates/closes us (the A2 scenario). Daemon reader → no hang.
            while self._alive and not self.terminated and not self.closed:
                time.sleep(0.01)
            raise EOFError()
        if self._reads:
            return self._reads.pop(0)
        self._alive = False
        raise EOFError()

    def isalive(self):
        return self._alive and not self.terminated and not self.closed

    def terminate(self, force=False):
        self.terminated = True
        self._alive = False

    def close(self, force=False):
        self.closed = True
        self._alive = False


@pytest.fixture
def fake_winpty(monkeypatch):
    """Install a fake `winpty` module; reset spawn log per test."""
    _FakePty.spawn_calls = []
    _FakePty._behavior = {}
    fake_mod = types.ModuleType("winpty")
    fake_mod.PtyProcess = _FakePty
    monkeypatch.setitem(sys.modules, "winpty", fake_mod)

    def _set(**behavior):
        _FakePty._behavior = behavior
    return _set


def test_ptyaskresult_fields():
    r = hub._PtyAskResult(
        text="x", elapsed=1, exit_code=0, timed_out=False,
        timeout_kind=None, pid=1,
    )
    assert (r.text, r.exit_code, r.timed_out, r.pid) == ("x", 0, False, 1)
    assert r.transport_error is None
    with pytest.raises(Exception):  # frozen dataclass
        r.text = "y"


def test_normal_eof_returns_output_and_exit_code(fake_winpty):
    fake_winpty(reads=["hello ", "world"], exitstatus=0)
    r = hub._ask_with_pty(["agy"], "ag", 30, {}, quiet=True, ai_root=None)
    assert "hello world" in r.text
    assert r.exit_code == 0
    assert r.timed_out is False
    assert r.transport_error is None
    assert r.pid == 4242


def test_nonzero_exit_is_captured(fake_winpty):
    fake_winpty(reads=["nope"], exitstatus=7)
    r = hub._ask_with_pty(["agy"], "ag", 30, {}, quiet=True, ai_root=None)
    assert r.exit_code == 7
    assert r.timed_out is False


def test_blocking_read_honors_execution_deadline(fake_winpty):
    """THE A2 fix: a child whose read() blocks indefinitely must still be cut
    at the execution deadline (not run unbounded), and reported timed_out."""
    fake_winpty(block=True)
    t0 = time.monotonic()
    r = hub._ask_with_pty(["agy"], "ag", 1, {}, quiet=True, ai_root=None)
    wall = time.monotonic() - t0
    assert r.timed_out is True
    assert r.timeout_kind == "deadline"
    assert wall < 4, f"deadline not honored during blocking read (wall={wall:.1f}s)"


def test_silent_zombie_timeout(fake_winpty, monkeypatch):
    """Alive but silent child is killed by the zombie guard."""
    # heartbeat, lease_timeout, zombie  → tiny zombie so the test is fast.
    monkeypatch.setattr(hub, "_lease_cfg", lambda: (30, 300, 1))
    fake_winpty(block=True)
    r = hub._ask_with_pty(["agy"], "ag", 60, {}, quiet=True, ai_root=None)
    assert r.timed_out is True
    assert r.timeout_kind == "zombie"


def test_spawn_failure_returns_transport_error(fake_winpty):
    fake_winpty(spawn_raises=True)
    r = hub._ask_with_pty(["agy"], "ag", 30, {}, quiet=True, ai_root=None)
    assert r.transport_error is not None
    assert "pty_spawn_failed" in r.transport_error
    assert r.pid == -1
    assert r.timed_out is False


def test_cwd_is_propagated_to_spawn(fake_winpty):
    fake_winpty(reads=["ok"], exitstatus=0)
    hub._ask_with_pty(["agy"], "ag", 30, {}, quiet=True, ai_root=None,
                      cwd=r"D:\proj root")
    assert _FakePty.spawn_calls[-1]["cwd"] == r"D:\proj root"


def test_ask_with_pty_opens_lease_but_does_not_close(fake_winpty, monkeypatch):
    """CONDITION-2: the lease is OPENED here, never CLOSED here (the caller's
    PTY `finally` closes it exactly once)."""
    opened, closed = [], []
    monkeypatch.setattr(hub, "_lease_open",
                        lambda *a, **k: opened.append((a, k)))
    monkeypatch.setattr(hub, "_lease_close",
                        lambda *a, **k: closed.append((a, k)))
    monkeypatch.setattr(hub, "_lease_renew", lambda *a, **k: None)
    fake_winpty(reads=["ok"], exitstatus=0)
    r = hub._ask_with_pty(["agy"], "ag", 30, {}, quiet=True, ai_root="/tmp/x",
                          ask_id="ask-abcd")
    assert opened, "_ask_with_pty must open the lease"
    assert not closed, "_ask_with_pty must NOT close the lease (caller does)"
    assert r.exit_code == 0


def test_staged_prompt_filename_is_not_ephemeral():
    """A1 staged file {ask_id}-ag-prompt.txt must NOT match the ephemeral
    auto-name regex (so it is governed only by the explicit finally delete,
    never the single-use unlink path)."""
    from pathlib import Path
    p = Path("/repo/ipc/ask-ab12-ag-prompt.txt")
    assert hub._is_ephemeral_query_file(p) is False


def test_pty_inline_command_limit_constant():
    assert hub._PTY_INLINE_COMMAND_LIMIT == 24_000
