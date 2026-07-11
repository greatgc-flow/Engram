"""Tests for T3: pre-dispatch oversized-ask guard.

A single ask with too many task items or too many raw characters can run
past the zombie timeout with zero output (ag's tool-calling loop doesn't
flush partial output on large multi-item asks - this is an ag-specific
characteristic, not a universal peer trait). hub.py's guard reflects that:
every peer gets a non-lethal oversized_ask_detected warning, but only a
peer declared vulnerable (hard_reject=True, currently proxied by
requires_pty=true i.e. ag) is actually rejected before dispatch. Peer
comms otherwise remain UNLIMITED in time and content (see T19's
zombie_profile_map note) - this guard is not a universal content cap.

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

    def test_records_routing_metric_on_warn(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hub, "_record_routing_metric",
            lambda ai_root, event, **kw: calls.append((event, kw)),
        )
        hub._guard_oversized_ask("x" * 100, 0, 10, "cx", hard_reject=False, ai_root=tmp_path)
        assert calls and calls[0][0] == "oversized_ask_detected"
        assert calls[0][1]["hard_reject"] is False


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
    context-inflated, and (b) hard-rejects only a peer whose node declares
    requires_pty=true, warning (not rejecting) every other peer."""

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

    def test_pty_peer_is_hard_rejected_at_depth_zero(self, monkeypatch, tmp_path):
        self._patch_pre_guard_scaffolding(monkeypatch, {"requires_pty": True})

        with pytest.raises(SystemExit) as exc:
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
        assert exc.value.code == 1

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
