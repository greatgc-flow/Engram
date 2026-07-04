"""Reaping robustness: _kill_process_tree must reap the tree even without psutil.

A timed-out ask that leaves psutil unavailable previously became a no-op (int-pid
PTY path), leaking an orphaned agy/node subprocess. The fallback routes to
taskkill (Windows) / os.kill (POSIX).
"""
import sys
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub  # noqa: E402


def test_fallback_used_when_psutil_none(monkeypatch):
    calls = []
    monkeypatch.setattr(hub, "psutil", None)
    monkeypatch.setattr(hub, "_kill_tree_no_psutil", lambda pid: calls.append(pid))
    hub._kill_process_tree(4321)
    assert calls == [4321]  # int pid routed to the no-psutil fallback


def test_no_psutil_windows_uses_taskkill(monkeypatch):
    ran = {}
    monkeypatch.setattr(hub.sys, "platform", "win32")
    monkeypatch.setattr(hub.subprocess, "run",
                        lambda cmd, **k: ran.update({"cmd": cmd}))
    hub._kill_tree_no_psutil(9999)
    assert ran["cmd"] == ["taskkill", "/F", "/T", "/PID", "9999"]


def test_kill_process_tree_ignores_bad_pid(monkeypatch):
    # None / negative pid must be a safe no-op (never raises).
    hub._kill_process_tree(None)
    hub._kill_process_tree(-1)


def test_fallback_never_raises(monkeypatch):
    monkeypatch.setattr(hub, "psutil", None)

    def boom(*a, **k):
        raise RuntimeError("taskkill missing")
    monkeypatch.setattr(hub.subprocess, "run", boom)
    monkeypatch.setattr(hub.sys, "platform", "win32")
    # _kill_process_tree swallows fallback errors.
    hub._kill_process_tree(1234)
