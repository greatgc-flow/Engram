"""Tests for the LL-20260703-005 out-of-band governed-mutation guard (hub.py).

Consensus 2026-07-03 (ag design, cx refined): peers must not mutate governed
files during advisory asks. The guard sha256-hashes the governed manifest before
a peer executes and re-hashes in a crash-safe finally covering BOTH the PTY and
non-PTY paths; a change (when not allow_governed_mutation) logs a violation.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub


def _make_governed(tmp_path, monkeypatch, name="gov.json", body="v1"):
    """Point the guard's manifest resolver at a single temp governed file."""
    f = tmp_path / name
    f.write_text(body, encoding="utf-8")
    monkeypatch.setattr(hub, "_governed_files", lambda *a, **k: [f.resolve()])
    return f


def test_manifest_resolves_and_excludes_generated(monkeypatch):
    files = hub._governed_files()
    assert files, "governed manifest resolved empty"
    assert any(str(p).endswith("orchestration.json") for p in files)
    assert not any("__pycache__" in str(p) for p in files)
    assert not any(str(p).endswith(".pyc") for p in files)


def test_snapshot_always_hashes_every_file(monkeypatch, tmp_path):
    f = _make_governed(tmp_path, monkeypatch, body="content")
    snap = hub._snapshot_governed_hashes()
    import hashlib
    assert snap[str(f.resolve())] == hashlib.sha256(b"content").hexdigest()


def test_mutation_detected_and_logged(monkeypatch, tmp_path):
    f = _make_governed(tmp_path, monkeypatch, body="original")
    pre = hub._snapshot_governed_hashes()
    # simulate a peer rewriting the governed file DURING the ask window
    f.write_text("mutated-by-peer", encoding="utf-8")
    ai_root = tmp_path / ".ai"
    changed = hub._governed_post_check(pre, ai_root, "ag", "worker")
    assert changed == [str(f.resolve())]
    log = ai_root / "operational_errors.jsonl"
    assert log.exists()
    rec = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert rec["type"] == "GOVERNED_MUTATION_VIOLATION"
    assert rec["lesson"] == "LL-20260703-005"
    assert rec["peer"] == "ag"


def test_size_preserving_mtime_restore_still_detected(monkeypatch, tmp_path):
    """cx bypass case: same byte-length change + restored mtime must still be
    caught (detection is content sha256, never mtime/size)."""
    f = _make_governed(tmp_path, monkeypatch, body="AAAA")
    st = f.stat()
    pre = hub._snapshot_governed_hashes()
    f.write_text("BBBB", encoding="utf-8")  # same length
    import os
    os.utime(f, (st.st_atime, st.st_mtime))  # restore mtime
    changed = hub._governed_post_check(pre, tmp_path / ".ai", "ag", "worker")
    assert changed == [str(f.resolve())]


def test_no_mutation_no_violation(monkeypatch, tmp_path):
    _make_governed(tmp_path, monkeypatch, body="stable")
    pre = hub._snapshot_governed_hashes()
    ai_root = tmp_path / ".ai"
    changed = hub._governed_post_check(pre, ai_root, "cc", "worker")
    assert changed == []
    assert not (ai_root / "operational_errors.jsonl").exists()


def test_terminal_edit_outside_window_no_false_positive(monkeypatch, tmp_path):
    """A change captured in BOTH pre and post (i.e. already present, not made
    during the window) does not flag."""
    f = _make_governed(tmp_path, monkeypatch, body="edited-by-terminal-before")
    pre = hub._snapshot_governed_hashes()  # terminal edit already baked into pre
    changed = hub._governed_post_check(pre, tmp_path / ".ai", "cc", "worker")
    assert changed == []


def test_allow_governed_mutation_skips_guard(monkeypatch, tmp_path):
    """action_ask(allow_governed_mutation=True) must not snapshot/guard."""
    called = {"snap": 0}
    real = hub._snapshot_governed_hashes
    monkeypatch.setattr(hub, "_snapshot_governed_hashes",
                        lambda *a, **k: called.__setitem__("snap", called["snap"] + 1) or real(*a, **k))
    # _action_ask_inner is heavy; stub it so we only exercise the wrapper guard.
    monkeypatch.setattr(hub, "_action_ask_inner", lambda *a, **k: None)
    hub.action_ask("cc", "q", None, 10, tmp_path / ".ai", allow_governed_mutation=True)
    assert called["snap"] == 0  # guarded snapshot never taken when authorized


def test_guard_runs_when_not_authorized(monkeypatch, tmp_path):
    called = {"snap": 0, "post": 0}
    monkeypatch.setattr(hub, "_snapshot_governed_hashes",
                        lambda *a, **k: called.__setitem__("snap", called["snap"] + 1) or {})
    monkeypatch.setattr(hub, "_governed_post_check",
                        lambda *a, **k: called.__setitem__("post", called["post"] + 1) or [])
    monkeypatch.setattr(hub, "_action_ask_inner", lambda *a, **k: None)
    hub.action_ask("cc", "q", None, 10, tmp_path / ".ai")
    assert called["snap"] == 1
    assert called["post"] == 1  # finally always post-checks


def test_guard_post_check_error_never_breaks_ask(monkeypatch, tmp_path):
    """A crash inside the guard's post-check must not propagate (crash-safe)."""
    monkeypatch.setattr(hub, "_snapshot_governed_hashes", lambda *a, **k: {})
    def _boom(*a, **k):
        raise RuntimeError("guard exploded")
    monkeypatch.setattr(hub, "_governed_post_check", _boom)
    monkeypatch.setattr(hub, "_action_ask_inner", lambda *a, **k: None)
    # must return cleanly despite the guard error
    hub.action_ask("cc", "q", None, 10, tmp_path / ".ai")
