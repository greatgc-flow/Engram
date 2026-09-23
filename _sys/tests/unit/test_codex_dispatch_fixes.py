import re
import sys
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub  # noqa: E402
import hub_peer  # noqa: E402


def test_codex_adapter_context_policy_skips_stale_room_context():
    """CodexAdapter must read files live (query_first, skip_room_context) --
    a static room-context snapshot embedded at dispatch time can go stale by
    the time Codex's apply_patch actually runs, causing real context-line
    mismatches (confirmed 2026-09-12 in cx.deepthink's health.json log)."""
    adapter = hub_peer.CodexAdapter()
    policy = adapter.context_policy({"node_id": "cx.deepthink"})

    assert policy.query_first is True
    assert policy.skip_room_context is True
    assert policy.skip_room_context_when_complete is True


def test_proc_cwd_uses_resolved_path_in_both_dispatch_branches():
    """Both proc_cwd sites in _action_ask_inner must resolve() the SUBST
    drive to its real path before handing it to the child process as cwd.

    P:\\ is a SUBST-mapped drive. Codex's own sandbox resolves P:\\ to its
    real underlying target internally; an unresolved P:\\ cwd here caused a
    real apparent-path/real-path mismatch that made Codex reject legitimate
    writes as "outside the project" (see
    reference_codex_subst_sandbox_conflict_2026_08_21). This is a source-
    level regression guard rather than a full _action_ask_inner mock replay:
    that function's dispatch pipeline is too deeply entangled (profile
    routing, context gate, session reuse, adapter selection, PTY vs plain-
    subprocess branch selection) to exercise end-to-end without a fragile,
    unrelated-refactor-breaking mock scaffold for a one-token change whose
    correctness is otherwise fully covered by Path.resolve()'s own stdlib
    guarantees.

    2026-09-23: both sites also gained an opt-in `project_dir` override (a
    peer can be dispatched against an explicit target directory instead of
    the default ai_root.parent, needed when that target is itself outside
    the default project -- e.g. a different git repo entirely, which is a
    stricter case than the SUBST/apparent-path mismatch this test was
    originally written for). The fallback branch (no project_dir given)
    must still resolve() ai_root.parent exactly as before.
    """
    hub_source = Path(hub.__file__).read_text(encoding="utf-8")
    occurrences = re.findall(
        r"proc_cwd\s*=\s*str\(Path\(project_dir\)\.resolve\(\)\)\s+if project_dir else "
        r"\(str\(ai_root\.parent(\.resolve\(\))?\)\s+if ai_root else None\)",
        hub_source,
    )
    assert len(occurrences) == 2, (
        f"expected exactly 2 proc_cwd assignment sites, found {len(occurrences)}; "
        "update this test if a proc_cwd site was added/removed/renamed"
    )
    assert all(resolve_call == ".resolve()" for resolve_call in occurrences), (
        "every proc_cwd site's ai_root.parent fallback must call .resolve() -- found an unresolved one"
    )


def test_action_ask_accepts_project_dir_and_threads_it_through_retries():
    """`project_dir` must be a real parameter on both action_ask and
    _action_ask_inner, and every recursive self-call of _action_ask_inner
    (escalation/failover retries) must forward it -- a retry that silently
    dropped the override would dispatch against the wrong cwd on its second
    attempt, defeating the whole point of passing --project-dir."""
    import inspect

    assert "project_dir" in inspect.signature(hub.action_ask).parameters
    assert "project_dir" in inspect.signature(hub._action_ask_inner).parameters

    hub_source = Path(hub.__file__).read_text(encoding="utf-8")
    inner_start = hub_source.index("def _action_ask_inner(")
    inner_body = hub_source[inner_start:]
    recursive_call_sites = list(re.finditer(r"return _action_ask_inner\(", inner_body))
    assert len(recursive_call_sites) >= 1, "expected at least one recursive retry call site"
    for m in recursive_call_sites:
        call_end = inner_body.index("\n                )", m.start())
        call_text = inner_body[m.start():call_end]
        assert "project_dir=project_dir" in call_text, (
            f"recursive _action_ask_inner call at offset {m.start()} does not forward project_dir"
        )
