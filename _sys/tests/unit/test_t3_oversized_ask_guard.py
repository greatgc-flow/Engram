"""Tests for T3: pre-dispatch oversized-ask guard.

A single ask with too many task items or too many raw characters can run
past the zombie timeout with zero output. Root-cause recheck (2026-07-12,
direct A/B measurement): a known-vulnerable peer (requires_pty=true, i.e.
ag) doesn't actually lose output - it silently batch-processes internally
then dumps everything at the end, which can exceed even T19's extended
zombie window on genuinely complex tasks (confirmed: an unmodified 7-item
task failed silently at 752s; the same task succeeded at 352s once
instructed to emit progress). hub.py's guard reflects this: every peer
gets a non-lethal oversized_ask_detected warning, and a peer declared
vulnerable additionally gets its query wrapped with an incremental-
progress instruction (progress_mitigation) before dispatch, rather than
being hard-rejected - --force-tier0 bypasses the injection entirely and
proceeds with the query unmodified, accepting the silent-batch risk. Peer
comms otherwise remain UNLIMITED in time and content (see T19's
zombie_profile_map note) - this guard is not a universal content cap. The
hard-reject code path itself remains a supported capability of
_guard_oversized_ask (tested below) but is no longer invoked from the
production ask path.

The guard runs after peer/node resolution (so it can read the target
peer's requires_pty) and only on the true top-level ask (_depth == 0 and
_escalation_depth == 0), so it never re-evaluates a context-inflated
prompt during ContextGate failover recursion.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import pytest

import hub


class TestOversizedAskTaskCount:
    def test_counts_numbered_and_bulleted_items(self):
        text = "1. a\n2. b\n3. c\n- d\n* e\nplain text\n"
        assert hub._oversized_ask_task_count(text) == 5

    def test_empty_text_counts_zero(self):
        assert hub._oversized_ask_task_count("") == 0


class TestOversizedAskStats:
    def test_flags_over_char_limit(self):
        reasons, task_count, char_count = hub._oversized_ask_stats("x" * 11, 0, 10)
        assert reasons == ["chars=11 > limit=10"]
        assert char_count == 11

    def test_flags_over_task_limit(self):
        text = "\n".join(f"{i}. task" for i in range(1, 7))
        reasons, task_count, char_count = hub._oversized_ask_stats(text, 5, 0)
        assert reasons == ["task_items=6 > limit=5"]
        assert task_count == 6

    def test_no_reasons_when_under_both_limits(self):
        reasons, _, _ = hub._oversized_ask_stats("short", 5, 8000)
        assert reasons == []


class TestInjectOversizedProgressInstruction:
    def test_wraps_original_query_verbatim(self):
        raw = "please review these six files and report back"
        injected = hub._inject_oversized_progress_instruction(raw)
        assert hub._OVERSIZED_PROGRESS_MARKER in injected
        assert "[USER REQUEST]" in injected
        assert raw in injected

    def test_is_idempotent_if_marker_already_present(self):
        raw = "please review these six files and report back"
        once = hub._inject_oversized_progress_instruction(raw)
        twice = hub._inject_oversized_progress_instruction(once)
        assert once == twice
        assert once.count(hub._OVERSIZED_PROGRESS_MARKER) == 1


class TestGuardOversizedAsk:
    def test_hard_reject_true_rejects_by_chars(self, capsys):
        with pytest.raises(SystemExit) as exc:
            hub._guard_oversized_ask("x" * 11, 0, 10, "ag", hard_reject=True)
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "chars=11 > limit=10" in err
        assert "[HUB:ERROR]" in err

    def test_hard_reject_true_rejects_by_task_count(self, capsys):
        text = "\n".join(f"{i}. task" for i in range(1, 7))
        with pytest.raises(SystemExit) as exc:
            hub._guard_oversized_ask(text, 5, 0, "ag", hard_reject=True)
        assert exc.value.code == 1
        assert "task_items=6 > limit=5" in capsys.readouterr().err

    def test_hard_reject_false_only_warns_and_does_not_raise(self, capsys):
        text = "\n".join(f"{i}. task" for i in range(1, 7))
        hub._guard_oversized_ask(text, 5, 0, "cx", hard_reject=False)  # must not raise
        err = capsys.readouterr().err
        assert "[HUB:WARN]" in err
        assert "oversized ask detected" in err

    def test_allows_under_limits_regardless_of_hard_reject(self):
        text = "\n".join(f"{i}. task" for i in range(1, 5))
        hub._guard_oversized_ask(text, 5, 8000, "ag", hard_reject=True)  # must not raise
        hub._guard_oversized_ask(text, 5, 8000, "cx", hard_reject=False)  # must not raise

    def test_records_routing_metric_on_reject(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )
        with pytest.raises(SystemExit):
            hub._guard_oversized_ask("x" * 100, 0, 10, "ag", hard_reject=True, ai_root=tmp_path)
        assert calls and calls[0][0] == "oversized_ask_detected"
        assert calls[0][1]["hard_reject"] is True
        assert calls[0][1]["force_tier0_override"] is False

    def test_records_routing_metric_on_warn(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )
        hub._guard_oversized_ask("x" * 100, 0, 10, "cx", hard_reject=False, ai_root=tmp_path)
        assert calls and calls[0][0] == "oversized_ask_detected"
        assert calls[0][1]["hard_reject"] is False
        assert calls[0][1]["force_tier0_override"] is False

    def test_force_tier0_override_warns_records_and_does_not_raise(self, tmp_path, monkeypatch, capsys):
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )

        hub._guard_oversized_ask(
            "x" * 100, 0, 10, "ag",
            hard_reject=False,
            ai_root=tmp_path,
            force_tier0_override=True,
        )

        err = capsys.readouterr().err
        assert "[HUB:WARN]" in err
        assert "--force-tier0 override" in err
        assert calls and calls[0][0] == "oversized_ask_detected"
        assert calls[0][1]["hard_reject"] is False
        assert calls[0][1]["force_tier0_override"] is True


class TestOversizedAskLimitsConfig:
    def test_protocol_declares_oversized_ask_limits(self):
        cfg = hub._load_protocol_cfg()
        comm = cfg.get("communication_policy", {})
        assert comm.get("oversized_ask_max_tasks") == 5
        assert comm.get("oversized_ask_max_chars") == 8000
        assert "_note_oversized_ask_guard" in comm

    def test_limits_disabled_when_zero(self, monkeypatch):
        monkeypatch.setattr(
            hub,
            "_load_protocol_cfg",
            lambda: {"communication_policy": {"oversized_ask_max_tasks": 0, "oversized_ask_max_chars": 0}},
        )
        assert hub._oversized_ask_limits() == (0, 0)


class TestDepthAndPeerScopeOnActionAskInner:
    """Verifies the guard (a) fires only on the true top-level call
    (_depth==0, _escalation_depth==0), not on ContextGate-failover or
    runtime-escalation recursion where the passed-in query may already be
    context-inflated, and (b) as of the 2026-07-12 recheck, injects an
    incremental-progress instruction (rather than hard-rejecting) for a peer
    whose node declares requires_pty=true, proceeding to dispatch either way;
    every other peer just gets a warning with no query mutation."""

    def _oversized_query(self):
        return "\n".join(f"{i}. do task {i}" for i in range(1, 8))  # 7 items > max_tasks(5)

    def _patch_pre_guard_scaffolding(self, monkeypatch, node: dict):
        """Bypass everything _action_ask_inner does before the guard's new
        insertion point (profile routing, action-guard, node/orchestration
        loading, hub_peer lookups) so the test exercises only the guard's
        placement and peer-scoping, not unrelated subsystems."""
        monkeypatch.setattr(hub, "_oversized_ask_limits", lambda: (5, 8000))
        monkeypatch.setattr(hub, "_select_ask_profile", lambda to, q: (to, None))
        monkeypatch.setattr(hub, "_guard_action", lambda *a, **kw: None)
        monkeypatch.setattr(hub, "_load_nodes", lambda ai_root: {"ag": node, "cx": node})
        monkeypatch.setattr(hub, "_load_orchestration", lambda: {})
        monkeypatch.setattr(hub, "is_routable", lambda node_id, orch=None: True)
        monkeypatch.setattr(hub, "_HUB_PEER_AVAILABLE", False)

        class _PastGuardSentinel(Exception):
            pass

        monkeypatch.setattr(
            hub, "_lease_sweep",
            lambda *a, **kw: (_ for _ in ()).throw(_PastGuardSentinel("reached past the guard")),
        )
        return _PastGuardSentinel

    def test_pty_peer_gets_progress_injection_and_proceeds_at_depth_zero(self, monkeypatch, tmp_path):
        sentinel_cls = self._patch_pre_guard_scaffolding(monkeypatch, {"requires_pty": True})
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )

        with pytest.raises(sentinel_cls):
            hub._action_ask_inner(
                to="ag",
                query=self._oversized_query(),
                query_file=None,
                timeout_sec=60,
                ai_root=tmp_path,
                quiet=True,
                _depth=0,
                _escalation_depth=0,
            )

        events = [c[0] for c in calls]
        assert "oversized_ask_detected" in events
        assert "oversized_ask_progress_injected" in events
        detected = next(c for c in calls if c[0] == "oversized_ask_detected")
        assert detected[1]["hard_reject"] is False
        assert detected[1]["force_tier0_override"] is False
        assert detected[1]["progress_mitigation"] is True

    def test_force_tier0_bypasses_progress_injection_at_depth_zero(self, monkeypatch, tmp_path):
        sentinel_cls = self._patch_pre_guard_scaffolding(monkeypatch, {"requires_pty": True})
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )

        with pytest.raises(sentinel_cls):
            hub._action_ask_inner(
                to="ag",
                query=self._oversized_query(),
                query_file=None,
                timeout_sec=60,
                ai_root=tmp_path,
                quiet=True,
                _depth=0,
                _escalation_depth=0,
                force_tier0=True,
            )

        events = [c[0] for c in calls]
        assert "oversized_ask_detected" in events
        assert "oversized_ask_progress_injected" not in events
        detected = next(c for c in calls if c[0] == "oversized_ask_detected")
        assert detected[1]["hard_reject"] is False
        assert detected[1]["force_tier0_override"] is True
        assert detected[1]["progress_mitigation"] is False

    def test_non_pty_peer_only_warns_and_proceeds_past_guard(self, monkeypatch, tmp_path):
        sentinel_cls = self._patch_pre_guard_scaffolding(monkeypatch, {"requires_pty": False})

        with pytest.raises(sentinel_cls):
            hub._action_ask_inner(
                to="cx",
                query=self._oversized_query(),
                query_file=None,
                timeout_sec=60,
                ai_root=tmp_path,
                quiet=True,
                _depth=0,
                _escalation_depth=0,
            )

    def test_depth_nonzero_skips_reguard_even_for_pty_peer(self, monkeypatch, tmp_path):
        sentinel_cls = self._patch_pre_guard_scaffolding(monkeypatch, {"requires_pty": True})

        with pytest.raises(sentinel_cls):
            hub._action_ask_inner(
                to="ag",
                query=self._oversized_query(),
                query_file=None,
                timeout_sec=60,
                ai_root=tmp_path,
                quiet=True,
                include_context=False,
                _depth=1,
                _escalation_depth=0,
            )

    def test_escalation_depth_nonzero_also_skips_reguard_for_pty_peer(self, monkeypatch, tmp_path):
        sentinel_cls = self._patch_pre_guard_scaffolding(monkeypatch, {"requires_pty": True})

        with pytest.raises(sentinel_cls):
            hub._action_ask_inner(
                to="ag",
                query=self._oversized_query(),
                query_file=None,
                timeout_sec=60,
                ai_root=tmp_path,
                quiet=True,
                _depth=0,
                _escalation_depth=1,
            )


class TestForceTier0Threading:
    def test_action_ask_threads_force_tier0_to_inner(self, monkeypatch, tmp_path):
        captured = {}

        def _fake_inner(*args, **kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(hub, "_action_ask_inner", _fake_inner)

        hub.action_ask(
            "ag", "query", None, 60, tmp_path,
            allow_governed_mutation=True,
            force_tier0=True,
        )

        assert captured["force_tier0"] is True

    def test_cli_force_tier0_reaches_action_ask(self, monkeypatch, tmp_path):
        captured = {}

        def _fake_action_ask(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

        monkeypatch.setattr(sys, "argv", [
            "hub.py", "ask", "--to", "ag", "--query", "hello", "--force-tier0",
        ])
        monkeypatch.setattr(hub, "find_ai_root", lambda: tmp_path)
        monkeypatch.setattr(hub, "ensure_ai_dir", lambda ai_root: None)
        monkeypatch.setattr(hub, "action_ask", _fake_action_ask)

        hub.main()

        assert captured["args"][0] == "ag"
        assert captured["kwargs"]["force_tier0"] is True
