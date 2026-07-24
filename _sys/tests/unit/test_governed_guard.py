"""Tests for the LL-20260703-005 out-of-band governed-mutation guard (hub.py).

Consensus 2026-07-03 (ag design, cx refined): peers must not mutate governed
files during advisory asks. The guard sha256-hashes the governed manifest before
a peer executes and re-hashes in a crash-safe finally covering BOTH the PTY and
non-PTY paths; a change (when not allow_governed_mutation) logs a violation.

2026-07-24 (Cluster C1, design converged via ag+cx mutual-critical unanimous
rounds, see docs-v2/ops/backlog-design-consensus-2026-07-24.md): a before/after
hash window proves temporal overlap, not authorship. Automatic `git checkout`/
file-deletion revert is deleted entirely -- an unattributed change during an
ask's window is now non-destructively quarantined (live bytes preserved) and
NEVER blamed on the dispatching peer (no health penalty). The guard is fail-
closed: pre-check failure prevents dispatch, post-check failure prevents
normal success but never breaks the ask's own generated response. A change
IS attributed (and excluded from the unattributed set) if it's explained by a
MutationReceipt from a host-mediated commit via `_commit_host_mutation`.
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
    # C1: never a "VIOLATION" attributed to a specific peer -- unattributed.
    assert rec["type"] == "UNATTRIBUTED_GOVERNED_CHANGE"
    assert rec["lesson"] == "LL-20260703-005"
    assert rec["peer"] == "ag"
    # C1: live bytes are always preserved -- never reverted.
    assert f.read_text(encoding="utf-8") == "mutated-by-peer"


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
    hub.action_ask("cc", "q", None, 10, tmp_path / ".ai", allow_governed_mutation=True,
                    governed_mutation_reason="test: authorized broker execution")
    assert called["snap"] == 0  # guarded snapshot never taken when authorized


def test_allow_governed_mutation_without_reason_fails_closed(monkeypatch, tmp_path):
    """2026-07-17: allow_governed_mutation=True with no reason must NOT bypass the
    guard -- the flag was found live as an ungated bypass with no audit trail."""
    called = {"snap": 0}
    real = hub._snapshot_governed_hashes
    monkeypatch.setattr(hub, "_snapshot_governed_hashes",
                        lambda *a, **k: called.__setitem__("snap", called["snap"] + 1) or real(*a, **k))
    monkeypatch.setattr(hub, "_action_ask_inner", lambda *a, **k: None)
    hub.action_ask("cc", "q", None, 10, tmp_path / ".ai", allow_governed_mutation=True,
                    governed_mutation_reason=None)
    assert called["snap"] >= 1  # guard still runs (pre + post snapshot): no reason == not authorized


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


# --- C1 fail-closed tests (replace the pre-fix fail-OPEN contract) ---------

def test_c1_fail_closed_pre_check_failure_blocks_execution(monkeypatch, tmp_path):
    """C1 fail-closed 1: pre-check snapshot failure prevents child execution
    entirely (the pre-fix behavior swallowed this and dispatched anyway)."""
    def _boom(*a, **k):
        raise RuntimeError("pre snapshot failed")
    monkeypatch.setattr(hub, "_snapshot_governed_hashes", _boom)
    called = {"inner": False}
    monkeypatch.setattr(hub, "_action_ask_inner", lambda *a, **k: called.__setitem__("inner", True))

    import pytest
    with pytest.raises(RuntimeError, match="pre snapshot failed"):
        hub.action_ask("cc", "q", None, 10, tmp_path / ".ai")
    assert not called["inner"], "child execution must be prevented on pre-check failure"


def test_c1_fail_closed_post_check_failure_propagates(monkeypatch, tmp_path):
    """C1 fail-closed 2: post-check verification failure must propagate
    (the pre-fix behavior printed a warning and returned success cleanly --
    an EXISTING test explicitly required that fail-open contract; this test
    replaces it, not silently alters it)."""
    monkeypatch.setattr(hub, "_snapshot_governed_hashes", lambda *a, **k: {})
    monkeypatch.setattr(hub, "_phantom_scan", lambda *a, **k: set())
    def _boom(*a, **k):
        raise RuntimeError("post verify failed")
    monkeypatch.setattr(hub, "_governed_post_check", _boom)
    monkeypatch.setattr(hub, "_action_ask_inner", lambda *a, **k: None)

    import pytest
    with pytest.raises(RuntimeError, match="post verify failed"):
        hub.action_ask("cc", "q", None, 10, tmp_path / ".ai")


def test_c1_ordinary_ask_clean_ask_guard_record(monkeypatch, tmp_path):
    """C1 scenario A: an ordinary ask with no concurrent activity completes
    with a clean AskGuardRecord."""
    _make_governed(tmp_path, monkeypatch, name="clean.json", body="original")
    ai_root = tmp_path / ".ai"
    monkeypatch.setattr(hub, "_phantom_scan", lambda *a, **k: set())
    monkeypatch.setattr(hub, "_action_ask_inner", lambda *a, **k: None)

    hub.action_ask("cc", "q", None, 10, ai_root)

    guards = list((ai_root / "ask_guards").glob("*.json"))
    assert len(guards) == 1
    rec = json.loads(guards[0].read_text(encoding="utf-8"))
    assert rec["status"] == "clean"
    assert rec["unattributed_files"] == []


def test_c1_unattributed_change_quarantined_not_reverted(monkeypatch, tmp_path):
    """C1 scenario B: an unattributed change during the ask window is
    quarantined (never reverted), the dispatching peer receives NO health
    penalty (no _record_ask_failure call), and the AskGuardRecord becomes
    'indeterminate'."""
    f = _make_governed(tmp_path, monkeypatch, name="unattributed.json", body="original")
    ai_root = tmp_path / ".ai"
    monkeypatch.setattr(hub, "_phantom_scan", lambda *a, **k: set())

    def _simulate_ask(*a, **k):
        f.write_text("mutated-by-external", encoding="utf-8")
    monkeypatch.setattr(hub, "_action_ask_inner", _simulate_ask)

    recorded_failures = []
    monkeypatch.setattr(hub, "_record_ask_failure", lambda *a, **k: recorded_failures.append((a, k)))
    recorded_history = []
    monkeypatch.setattr(hub, "_append_ask_history", lambda *a, **k: recorded_history.append((a, k)))

    import pytest
    with pytest.raises(SystemExit) as exc_info:
        hub.action_ask("cc", "q", None, 10, ai_root)
    assert exc_info.value.code == 1

    # Live bytes were NEVER reverted.
    assert f.read_text(encoding="utf-8") == "mutated-by-external"

    # Quarantine evidence was written.
    quarantine_files = list((ai_root / "quarantine").rglob("*"))
    assert quarantine_files, "expected quarantined evidence, found none"

    # C1: no peer health penalty for an unattributed change.
    assert recorded_failures == []
    # History is still recorded, but under the new non-blaming label.
    assert len(recorded_history) == 1
    assert recorded_history[0][0][6] == "UNATTRIBUTED_GOVERNED_CHANGE"

    guards = list((ai_root / "ask_guards").glob("*.json"))
    assert len(guards) == 1
    rec = json.loads(guards[0].read_text(encoding="utf-8"))
    assert rec["status"] == "indeterminate"
    assert len(rec["unattributed_files"]) == 1


def test_c1_concurrent_write_survives_no_git_checkout(monkeypatch, tmp_path):
    """C1 scenario C: automatic git checkout/deletion is deleted entirely --
    a second external write during the detection window always survives."""
    f = _make_governed(tmp_path, monkeypatch, name="concurrent.json", body="original")
    ai_root = tmp_path / ".ai"
    import hashlib
    h_orig = hashlib.sha256(b"original").hexdigest()
    pre = {str(f.resolve()): h_orig}

    # A write happens during the (simulated) ask window.
    f.write_text("second-external-write", encoding="utf-8")

    git_called = {"any": False}
    import subprocess
    real_run = subprocess.run
    def _mock_run(cmd, *a, **k):
        if isinstance(cmd, (list, tuple)) and "checkout" in cmd:
            git_called["any"] = True
        return real_run(cmd, *a, **k) if not (isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git") else None
    monkeypatch.setattr(subprocess, "run", _mock_run)

    unattributed = hub._verify_ask_guard_record(pre, ai_root, "ag", "terminal", ask_id="ask-concurrent")

    assert not git_called["any"], "git checkout must never be called by post verification"
    assert unattributed == [str(f.resolve())]
    assert f.read_text(encoding="utf-8") == "second-external-write"


def test_c1_host_mutation_commit_cas_success(monkeypatch, tmp_path):
    """C1 host commit: a scratch-written MutationRequest is processed
    atomically with a CAS revision check and produces an immutable
    MutationReceipt; the receipted change is explained (not unattributed)."""
    f = _make_governed(tmp_path, monkeypatch, name="target.json", body="v1")
    ai_root = tmp_path / ".ai"
    ask_id = "ask-host-commit"

    import hashlib
    h_v1 = hashlib.sha256(b"v1").hexdigest()

    scratch_dir = ai_root / "scratch" / ask_id
    scratch_dir.mkdir(parents=True, exist_ok=True)
    hub._write_json(scratch_dir / "mutation_request.json", {
        "ask_id": ask_id,
        "target_file": str(f.resolve()),
        "status": "untrusted_proposal",
    })

    receipt = hub._commit_host_mutation(ai_root, ask_id, f.resolve(), "v2-authorized", h_v1)

    assert f.read_text(encoding="utf-8") == "v2-authorized"

    host_req = hub._read_json(ai_root / "mutation_requests" / f"{ask_id}.json")
    assert host_req["status"] == "authorized"

    rcpt_file = ai_root / "mutation_receipts" / f"{receipt['receipt_id']}.json"
    assert rcpt_file.exists()

    try:
        expected_rel = str(f.relative_to(hub._REPO_ROOT))
    except ValueError:
        expected_rel = str(f.resolve())
    assert receipt["paths"] == [expected_rel]

    # A change explained by this receipt is NOT unattributed.
    pre = {str(f.resolve()): h_v1}
    unattributed = hub._verify_ask_guard_record(pre, ai_root, "ag", "worker", ask_id=ask_id)
    assert unattributed == []


def test_c1_pass2_success_published_only_after_clean_verification(monkeypatch, tmp_path):
    """C1 pass 2: _action_ask_inner() defers success bookkeeping (health
    record, history, routing metric, REPLY print) into a returned
    _PendingAskSuccess -- action_ask() must only .publish() it AFTER the
    guard post-check confirms no violation, never before."""
    _make_governed(tmp_path, monkeypatch, name="clean2.json", body="original")
    ai_root = tmp_path / ".ai"
    monkeypatch.setattr(hub, "_phantom_scan", lambda *a, **k: set())

    publish_calls = []
    published_pending = hub._PendingAskSuccess(
        health_peer="cc", elapsed=1, ai_root=ai_root, profile_key="cc.effort",
        to="cc", query_file=None, output_file=None, quiet=True, output="hello",
        out_path=None,
    )
    real_record_ask_success = hub._record_ask_success
    monkeypatch.setattr(hub, "_record_ask_success",
                         lambda *a, **k: publish_calls.append("record_ask_success"))

    monkeypatch.setattr(hub, "_action_ask_inner", lambda *a, **k: published_pending)

    hub.action_ask("cc", "q", None, 10, ai_root)

    assert publish_calls == ["record_ask_success"], "clean ask must publish exactly once"


def test_c1_pass2_success_never_published_on_violation(monkeypatch, tmp_path):
    """C1 pass 2: the counterpart to the test above -- when the post-check
    finds a violation, the deferred success must NEVER be published (no
    _record_ask_success call, no REPLY print), even though
    _action_ask_inner() already returned a fully-built _PendingAskSuccess."""
    f = _make_governed(tmp_path, monkeypatch, name="violation2.json", body="original")
    ai_root = tmp_path / ".ai"
    monkeypatch.setattr(hub, "_phantom_scan", lambda *a, **k: set())

    published_pending = hub._PendingAskSuccess(
        health_peer="cc", elapsed=1, ai_root=ai_root, profile_key="cc.effort",
        to="cc", query_file=None, output_file=None, quiet=True, output="hello",
        out_path=None,
    )

    def _simulate_ask_with_unattributed_change(*a, **k):
        f.write_text("mutated-during-ask", encoding="utf-8")
        return published_pending
    monkeypatch.setattr(hub, "_action_ask_inner", _simulate_ask_with_unattributed_change)

    publish_calls = []
    monkeypatch.setattr(hub, "_record_ask_success",
                         lambda *a, **k: publish_calls.append("record_ask_success"))

    import pytest
    with pytest.raises(SystemExit) as exc_info:
        hub.action_ask("cc", "q", None, 10, ai_root)
    assert exc_info.value.code == 1

    assert publish_calls == [], "a violation must suppress the deferred success entirely"


def test_c1_pass2_no_bypass_of_deferred_success_inside_action_ask_inner():
    """C1 pass 2 structural regression guard: cx's cross-verification found
    a SECOND, non-obvious success-publishing site inside _action_ask_inner()
    (the permanent-resume-failure -> fresh-retry success branch) that
    bypassed _PendingAskSuccess entirely -- a plain code-review missed it
    because it's deeply nested. Rather than trust that every current and
    future success-recording call site remembers to defer, assert
    STRUCTURALLY (via AST) that _action_ask_inner() contains ZERO direct
    calls to _record_ask_success -- every such call must live inside
    _PendingAskSuccess.publish(), reached only through action_ask()'s
    guard-gated finally block."""
    import ast
    hub_src = Path(hub.__file__).read_text(encoding="utf-8")
    tree = ast.parse(hub_src)
    fn = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.FunctionDef) and n.name == "_action_ask_inner"),
        None,
    )
    assert fn is not None, "_action_ask_inner not found"

    # No direct _record_ask_success calls at all -- it only belongs inside
    # _PendingAskSuccess.publish().
    record_success_calls = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_record_ask_success"
    ]
    assert record_success_calls == [], (
        f"_action_ask_inner() must never call _record_ask_success directly "
        f"(found {len(record_success_calls)} call(s))."
    )

    # No _append_ask_history(..., True, ...) (success=True as the 6th
    # positional arg) -- only failure-outcome calls (success=False) may
    # stay immediate/inline.
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_append_ask_history" and len(n.args) >= 6):
            success_arg_dump = ast.dump(n.args[5])
            assert "True" not in success_arg_dump, (
                f"_action_ask_inner() line {n.lineno}: _append_ask_history "
                f"called with success=True directly -- must go through "
                f"_PendingAskSuccess.publish() instead."
            )

    # No _record_routing_metric(..., outcome="success", ...) directly.
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_record_routing_metric"):
            for kw in n.keywords:
                if kw.arg == "outcome" and "success" in ast.dump(kw.value):
                    raise AssertionError(
                        f"_action_ask_inner() line {n.lineno}: "
                        f"_record_routing_metric called with a success "
                        f"outcome directly -- must go through "
                        f"_PendingAskSuccess.publish() instead."
                    )


def test_c1_host_mutation_commit_cas_mismatch_raises(monkeypatch, tmp_path):
    """C1 host commit: a stale expected_revision is rejected (CAS conflict),
    never silently overwritten."""
    f = _make_governed(tmp_path, monkeypatch, name="cas_target.json", body="v1")
    ai_root = tmp_path / ".ai"
    ask_id = "ask-cas-conflict"

    scratch_dir = ai_root / "scratch" / ask_id
    scratch_dir.mkdir(parents=True, exist_ok=True)
    hub._write_json(scratch_dir / "mutation_request.json", {"ask_id": ask_id, "status": "untrusted_proposal"})

    import pytest
    with pytest.raises(RuntimeError, match="CAS revision mismatch"):
        hub._commit_host_mutation(ai_root, ask_id, f.resolve(), "new-content", "stale-wrong-hash")

    # File must be untouched on a CAS conflict.
    assert f.read_text(encoding="utf-8") == "v1"
