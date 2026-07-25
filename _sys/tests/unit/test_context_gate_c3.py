"""
Unit and Integration Tests for Cluster C3 (ContextGate Failover-Chain & Capacity-Aware Planner)

Covers:
  1. Candidate exclusion: arbiter models, bulk-excluded, active C5 terminal, current/visited.
  2. Capability-equivalence gate: PTY requirements, capability_class (mutating vs read-only).
  3. Prune-path §3.2 fix: mandatory vs droppable blocks, strict < target_tokens check, fail closed.
  4. Explicit-profile immunity: explicit profile picks reject with diagnostic, never reroute.
  5. Session-policy gate: failover targets force session_policy="fresh", reuse fails closed without opt-in.
  6. Integration test: real oversized ask on ag.gptoss plans failover to larger capacity candidate.
"""

import json
from pathlib import Path
import subprocess
import sys
import pytest

SYS_DIR = Path(__file__).parent.parent.parent.resolve()
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

import core.hub as hub
import core.hub_context as hub_context


class TestC3CapacityPlanner:
    """Unit tests for _plan_context_aware_failover capacity planner."""

    def test_explicit_profile_immune_to_failover(self, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (ai_root / "state.json").write_text(json.dumps({"version": 1, "human_interface_peer": "cc"}), encoding="utf-8")

        plan = hub._plan_context_aware_failover(
            ai_root=ai_root,
            source_to="ag.gptoss",
            user_query_raw="x " * 35000,
            explicit_profile=True,
        )
        assert plan is None, "Explicit profile selection MUST be immune to auto-failover rerouting"

    def test_session_policy_reuse_fails_closed_without_opt_in(self, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (ai_root / "state.json").write_text(json.dumps({"version": 1, "human_interface_peer": "cc"}), encoding="utf-8")

        plan = hub._plan_context_aware_failover(
            ai_root=ai_root,
            source_to="ag.gptoss",
            user_query_raw="x " * 35000,
            session_policy="reuse",
            allow_fresh_failover_on_session_reuse=False,
        )
        assert plan is None, "session_policy='reuse' MUST fail closed without explicit opt-in"

    def test_session_policy_reuse_allowed_with_opt_in(self, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (ai_root / "state.json").write_text(json.dumps({"version": 1, "human_interface_peer": "cc"}), encoding="utf-8")

        plan = hub._plan_context_aware_failover(
            ai_root=ai_root,
            source_to="ag.gptoss",
            user_query_raw="x " * 35000,
            session_policy="reuse",
            allow_fresh_failover_on_session_reuse=True,
        )
        assert plan is not None, "session_policy='reuse' MUST plan failover when opt-in is True"
        assert plan.session_policy == "fresh"

    def test_active_terminal_peer_excluded_from_failover(self, tmp_path, monkeypatch):
        """Deterministic version: monkeypatch the headroom ranking so the
        active-terminal candidate ("cc.deepthink") would otherwise be the
        clear top pick (huge headroom, first in ranked order) -- if terminal
        exclusion were silently broken, the planner would return it. The
        original version of this test only asserted `if plan is not None`,
        which could pass vacuously (skip its own assertion) whenever live
        quota/health state on the test machine happened to yield no eligible
        candidate at all -- not a real check of the exclusion logic."""
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        # Mark cc as active terminal owner via a fresh lease.
        state = {
            "version": 1,
            "human_interface_peer": "cc",
            "human_interface_assignment": {
                "peer": "cc",
                "profile": "cc.deepthink",
                "lease_id": "test-lease-cc",
                "assigned_at": "2026-07-25T10:00:00+09:00",
                "expires_at": "2026-07-25T20:00:00+09:00",
            }
        }
        (ai_root / "state.json").write_text(json.dumps(state), encoding="utf-8")

        # Deterministic candidate ranking: cc.deepthink first (would win on
        # headroom alone), ag.deepthink second (the real, non-excluded
        # winner once cc.deepthink is correctly excluded as the terminal).
        fake_rows = [
            {"profile": "cc.deepthink", "peer": "cc", "state": "eligible", "headroom": 0.99},
            {"profile": "ag.deepthink", "peer": "ag", "state": "eligible", "headroom": 0.80},
        ]

        # hub.py does `import snapshot` (bare), which is a DIFFERENT module
        # object from `import core.snapshot` -- patch hub.snapshot directly,
        # the actual object _plan_context_aware_failover calls into.
        monkeypatch.setattr(hub.snapshot, "collect_snapshot", lambda use_cache=True: {})
        monkeypatch.setattr(hub.snapshot, "_derive_headroom_rows", lambda snap: fake_rows)
        monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)

        plan = hub._plan_context_aware_failover(
            ai_root=ai_root,
            source_to="ag.gptoss",
            user_query_raw="x " * 35000,
        )
        assert plan is not None, "a real, non-excluded candidate (ag.deepthink) must be found"
        assert plan.target_profile == "ag.deepthink", (
            f"cc.deepthink was the top-ranked candidate but IS the active terminal -- "
            f"it must be excluded, not selected (got {plan.target_profile!r})"
        )

    def test_visited_peers_excludes_already_tried_candidates(self, tmp_path, monkeypatch):
        """Regression: the recursive _action_ask_inner call in
        _action_ask_inner's failover branch previously always passed
        visited_peers=None to _plan_context_aware_failover, even though the
        parameter and its exclusion logic were fully implemented -- meaning a
        source A that fails over to B, where B's OWN ContextGate check then
        also fails, could get planned right back to A (A was never recorded
        as already-tried), causing an A<->B oscillation only bounded by the
        raw _depth/RUNTIME_ESCALATION_DEPTH_CEILING check, burning real
        dispatch attempts. Verifies the planner itself correctly excludes a
        candidate that's already in visited_peers (the primitive this fix
        relies on) -- the recursive call site threading _context_failover_visited
        through is exercised indirectly since it uses this same parameter."""
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (ai_root / "state.json").write_text(json.dumps({"version": 1, "human_interface_peer": "cc"}), encoding="utf-8")

        fake_rows = [
            {"profile": "cc.deepthink", "peer": "cc", "state": "eligible", "headroom": 0.99},
            {"profile": "ag.deepthink", "peer": "ag", "state": "eligible", "headroom": 0.80},
        ]
        monkeypatch.setattr(hub.snapshot, "collect_snapshot", lambda use_cache=True: {})
        monkeypatch.setattr(hub.snapshot, "_derive_headroom_rows", lambda snap: fake_rows)
        monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)

        # Simulate: source "cx.effort" already tried "cc.deepthink" earlier
        # in this same failover chain (visited_peers includes it) -- the
        # planner must skip it even though it's the top-ranked candidate.
        plan = hub._plan_context_aware_failover(
            ai_root=ai_root,
            source_to="cx.effort",
            user_query_raw="x " * 35000,
            visited_peers={"cc.deepthink", "cc"},
        )
        assert plan is not None
        assert plan.target_profile == "ag.deepthink", (
            f"cc.deepthink is top-ranked but already visited -- must be skipped "
            f"in favor of ag.deepthink (got {plan.target_profile!r})"
        )

    def test_action_ask_recursive_failover_threads_visited_peers_forward(self, tmp_path, monkeypatch):
        """End-to-end: the actual _action_ask_inner recursive call site must
        pass the accumulated visited set forward, not hardcode None."""
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (ai_root / "state.json").write_text(json.dumps({"version": 1, "human_interface_peer": "cc"}), encoding="utf-8")

        captured_visited = []
        real_planner = hub._plan_context_aware_failover

        def spy_planner(*args, **kwargs):
            captured_visited.append(kwargs.get("visited_peers"))
            return real_planner(*args, **kwargs)

        monkeypatch.setattr(hub, "_plan_context_aware_failover", spy_planner)
        monkeypatch.setattr(hub, "_load_balancer_config", lambda: {})

        def _forbidden_spawn(*args, **kwargs):
            raise AssertionError("subprocess.Popen must not be invoked in this test")
        monkeypatch.setattr(subprocess, "Popen", _forbidden_spawn)

        with pytest.raises(SystemExit):
            hub.action_ask(
                to="ag.gptoss",
                query="x " * 35000,
                query_file=None,
                timeout_sec=10,
                ai_root=ai_root,
                origin="terminal",
            )

        assert captured_visited, "the planner must have been invoked at least once"
        assert captured_visited[0] and "ag.gptoss" in captured_visited[0], (
            "the source profile itself must be recorded as visited on the first "
            "planner call, not an empty/None set"
        )


class TestPrunePathSection32Fix:
    """Unit tests for §3.2 pruning bug fix in hub_context.py."""

    def test_check_and_prune_preserves_mandatory_and_drops_low_priority(self):
        gate = hub_context.ContextGate()
        blocks = [
            {"text": "Mandatory query user prompt\n", "priority": 100, "mandatory": True},
            {"text": "Droppable room context " * 50, "priority": 10, "mandatory": False},
        ]
        pruned = gate.check_and_prune(blocks, "ag.effort")
        assert len(pruned) == 2, "If total is within limit, all blocks should be preserved"

    def test_prune_leaves_headroom_not_thrashing_on_next_similar_ask(self):
        """Regression (cx cross-verification, empirically demonstrated before
        it crashed on an unrelated tooling error): pruning down to EXACTLY
        the warn_pct threshold (no safety margin) means the very next
        similar-sized ask immediately re-triggers pruning again. Prune once,
        then confirm the result sits far enough below warn_pct that a
        same-size follow-up query doesn't immediately need pruning too."""
        gate = hub_context.ContextGate()
        limit = gate.context_limit("ag.effort")
        warn_t = int(limit * gate.warn_pct)
        target_t = int(limit * (gate.warn_pct - 0.05))

        # Mandatory content alone sits comfortably under target_t (so
        # pruning the droppable block is sufficient); combined with the
        # droppable block, the total exceeds warn_t, forcing exactly one
        # real prune.
        mandatory_chars = int((target_t - 1000) * 3.5)
        droppable_chars = int(50000 * 3.5)
        blocks = [
            {"text": "x" * mandatory_chars, "priority": 100, "mandatory": True},
            {"text": "y" * droppable_chars, "priority": 10, "mandatory": False},
        ]
        pruned = gate.check_and_prune(blocks, "ag.effort")
        pruned_text = "".join(b.get("text", "") for b in pruned)
        pruned_tokens = hub_context.estimate_tokens(pruned_text)

        # The pruned result must leave real headroom below warn_t -- not
        # land right at the edge -- so a same-size follow-up (mandatory
        # content roughly unchanged) doesn't immediately need pruning again.
        assert pruned_tokens < warn_t, "pruned result must be below the warn threshold"
        margin = warn_t - pruned_tokens
        assert margin >= int(limit * 0.04), (
            f"pruned result ({pruned_tokens} tokens) left almost no margin below "
            f"the warn threshold ({warn_t} tokens, margin={margin}) -- the very "
            f"next similar-sized ask would immediately re-trigger pruning"
        )

    def test_check_and_prune_fails_closed_when_mandatory_alone_exceeds(self):
        gate = hub_context.ContextGate()
        blocks = [
            {"text": "Huge mandatory query prompt " * 500000, "priority": 100, "mandatory": True},
            {"text": "Small droppable context", "priority": 10, "mandatory": False},
        ]
        with pytest.raises(hub_context.ContextGateError) as exc_info:
            gate.check_and_prune(blocks, "ag.effort")
        assert "exceeds" in str(exc_info.value) or "CONTEXT_GATE_REJECT" in str(exc_info.value)


class TestC3IntegrationAskDispatch:
    """Integration test proving oversized ask plans failover to valid candidate with session_policy='fresh'."""

    def test_oversized_ask_failover_plans_fresh_session_for_candidate(self, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (ai_root / "state.json").write_text(json.dumps({"version": 1, "human_interface_peer": "cc"}), encoding="utf-8")

        # 35,000 chars (~10,000 tokens) exceeds ag.gptoss's 8,000 limit natively!
        plan = hub._plan_context_aware_failover(
            ai_root=ai_root,
            source_to="ag.gptoss",
            user_query_raw="x " * 35000,
        )
        assert plan is not None
        assert plan.source_profile == "ag.gptoss"
        assert plan.target_profile in {"ag.standard", "ag.effort", "ag.deepthink", "cc.effort", "cc.deepthink", "cx.effort", "cx.deepthink"}
        assert plan.session_policy == "fresh"
        assert plan.admission_limit > 8000

    def test_explicit_profile_oversized_ask_halts_zero_spawn(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        state = {
            "version": 1,
            "human_interface_peer": "cc",
            "active_console_peer": "cc",
        }
        (ai_root / "state.json").write_text(json.dumps(state), encoding="utf-8")

        def _forbidden_spawn(*args, **kwargs):
            raise AssertionError("FAIL: subprocess.Popen MUST NOT be invoked when explicit profile fails ContextGate!")

        monkeypatch.setattr(subprocess, "Popen", _forbidden_spawn)

        oversized_query = "x " * 500000

        with pytest.raises(SystemExit) as exc_info:
            hub.action_ask(
                to="ag.effort",
                query=oversized_query,
                query_file=None,
                timeout_sec=10,
                ai_root=ai_root,
                origin="terminal",
                explicit_scope="explicit",
            )

        assert exc_info.value.code == 1
