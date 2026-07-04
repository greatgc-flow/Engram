"""Tests for the token load balancer — Phase 1 (snapshot.select_load_balanced_peer).

Design contract: _sys/docs/history/ops/token-load-balancing-design.md
(ag design + cx review). cx authored these tests; the impl was applied by the
terminal (peers do not write governed files — LL-20260703-005).
"""
import sys
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import snapshot


CONFIG = {
    "enabled": True,
    "effective_headroom_floor": 0.10,
    "terminal_hard_exclude": True,
    "cost_map": {"low": 0.0, "mid": 0.02, "high": 0.04},
}


def _row(peer, headroom, state="eligible", profile=None, cost_tier="low", effort="high"):
    return {
        "peer": peer,
        "profile": profile or f"{peer}.effort",
        "state": state,
        "effort": effort,
        "cost_tier": cost_tier,
        "quota_remaining": headroom,
        "context_remaining": headroom,
        "headroom": headroom,
        "tier_strength": 2,
        "tier_risk": False,
        "sources": {},
    }


def _patch_rows(monkeypatch, rows):
    monkeypatch.setattr(snapshot, "_derive_headroom_rows", lambda _snapshot: list(rows))


def test_terminal_hard_excluded_when_non_terminal_above_floor(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("cc", 0.09),
        _row("ag", 0.31),
        _row("cx", 0.12),
    ])

    result = snapshot.select_load_balanced_peer({}, CONFIG, terminal_peer="cc", ask_id="a1")

    assert result["selected_peer"] != "cc"
    assert result["weights"]["cc"] == 0.0
    assert result["terminal_excluded"] == "non_terminal_above_floor"


def test_terminal_participates_when_all_non_terminals_below_floor(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("cc", 0.20),
        _row("ag", 0.05),
        _row("cx", 0.03),
    ])

    result = snapshot.select_load_balanced_peer({}, CONFIG, terminal_peer="cc", ask_id="a2")

    assert result["weights"]["cc"] > 0.0
    assert result["terminal_excluded"] is None
    assert "cc" in result["candidates"]


def test_seeded_selection_is_deterministic_for_same_snapshot_and_ask(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("ag", 0.31),
        _row("cx", 0.12),
    ])
    snap = {"schema_version": 1, "profiles": [{"profile": "dummy"}]}

    first = snapshot.select_load_balanced_peer(snap, CONFIG, ask_id="same")
    second = snapshot.select_load_balanced_peer(snap, CONFIG, ask_id="same")

    assert first["seed"] == second["seed"]
    assert first["draw"] == second["draw"]
    assert first["selected_peer"] == second["selected_peer"]


def test_proportional_distribution_prefers_higher_headroom_peer(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("cc", 0.09),
        _row("ag", 0.31),
        _row("cx", 0.122),
    ])

    counts = {"ag": 0, "cx": 0, "cc": 0}
    for i in range(5000):
        result = snapshot.select_load_balanced_peer(
            {"schema_version": 1},
            CONFIG,
            terminal_peer="cc",
            ask_id=f"ask-{i}",
        )
        counts[result["selected_peer"]] += 1

    ag_share = counts["ag"] / (counts["ag"] + counts["cx"])
    assert counts["cc"] == 0
    assert 0.69 <= ag_share <= 0.74


def test_per_peer_aggregation_does_not_double_weight_multiple_profiles(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("ag", 0.31, profile="ag.deepthink"),
        _row("ag", 0.29, profile="ag.effort"),
        _row("cx", 0.12, profile="cx.effort"),
    ])

    result = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="aggregate")

    assert result["candidates"] == ["ag", "cx"]
    assert result["weights"]["ag"] == pytest.approx(0.31)
    assert result["weights"]["cx"] == pytest.approx(0.12)


def test_absent_headroom_and_non_eligible_rows_are_filtered(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("ag", None),
        _row("cx", 0.50, state="quarantined"),
        _row("cc", 0.10),
    ])

    result = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="filter")

    assert result["candidates"] == ["cc"]
    assert result["selected_peer"] == "cc"


def test_cost_tie_break_is_applied(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("ag", 0.30, cost_tier="low"),
        _row("cx", 0.30, cost_tier="high"),
        _row("cc", 0.30, cost_tier=None),
    ])

    result = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="cost")

    assert result["weights"]["ag"] == pytest.approx(0.30)
    assert result["weights"]["cx"] == pytest.approx(0.26)
    assert result["weights"]["cc"] == pytest.approx(0.30)


def test_no_candidate_returns_none(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("ag", None),
        _row("cx", 0.20, state="manual_only"),
    ])

    result = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="none")

    assert result["selected"] is None
    assert result["selected_peer"] is None
    assert result["weights"] == {}
    assert result["reason"] == "no_eligible_candidate"


def test_worked_example_probabilities_match_design_doc(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("cc", 0.090, cost_tier="low"),
        _row("ag", 0.310, cost_tier="low"),
        _row("cx", 0.122, cost_tier="low"),
    ])

    result = snapshot.select_load_balanced_peer(
        {"schema_version": 1},
        CONFIG,
        terminal_peer="cc",
        ask_id="worked-example",
    )

    assert result["weights"]["cc"] == 0.0
    assert result["probabilities"]["ag"] == pytest.approx(0.7176, abs=0.001)
    assert result["probabilities"]["cx"] == pytest.approx(0.2824, abs=0.001)
    assert result["terminal_excluded"] == "non_terminal_above_floor"


# ── P1 shadow hook (hub._shadow_log_load_balance) ────────────────────────────

def _load_hub():
    import importlib
    if str(CORE_DIR) not in sys.path:
        sys.path.insert(0, str(CORE_DIR))
    import hub
    return hub


def test_shadow_hook_logs_would_select(monkeypatch, tmp_path):
    hub = _load_hub()
    ai_root = tmp_path / ".ai"; ai_root.mkdir()
    (ai_root / "state.json").write_text('{"active_coordinator": "cc"}', encoding="utf-8")
    monkeypatch.setattr(hub, "_load_balancer_config",
                        lambda: {"shadow_log": True, "enabled": False,
                                 "effective_headroom_floor": 0.10, "terminal_hard_exclude": True,
                                 "cost_map": {}})
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)
    # Cache-only: the hook reads an already-warm snapshot, never re-collects.
    monkeypatch.setattr(hub.snapshot, "_SNAPSHOT_CACHE", {"snapshot": {"schema_version": 1}})
    monkeypatch.setattr(hub.snapshot, "select_load_balanced_peer",
                        lambda *a, **k: {"selected_peer": "ag", "weights": {"ag": 0.31, "cc": 0.0},
                                         "probabilities": {"ag": 1.0}, "terminal_excluded": "non_terminal_above_floor",
                                         "reason": "selected"})
    logged = {}
    monkeypatch.setattr(hub, "_record_routing_metric",
                        lambda ai, event, **f: logged.update({"event": event, **f}))

    hub._shadow_log_load_balance(ai_root, "cc", "terminal")

    assert logged["event"] == "load_balance_shadow"
    assert logged["actual_peer"] == "cc"
    assert logged["would_select"] == "ag"
    assert logged["driving"] is False
    assert logged["terminal_peer"] == "cc"


def test_shadow_hook_skips_non_terminal_origin(monkeypatch, tmp_path):
    """Peer-worker asks (origin != terminal) never shadow-log — no snapshot work."""
    hub = _load_hub()
    called = {"cfg": 0}
    monkeypatch.setattr(hub, "_load_balancer_config",
                        lambda: called.__setitem__("cfg", called["cfg"] + 1) or {"shadow_log": True})
    hub._shadow_log_load_balance(tmp_path / ".ai", "cc", "worker")
    assert called["cfg"] == 0  # returned before even reading config


def test_shadow_hook_skips_on_cold_cache(monkeypatch, tmp_path):
    """Cold snapshot cache -> skip (never triggers a fresh probe in the hot path)."""
    hub = _load_hub()
    ai_root = tmp_path / ".ai"; ai_root.mkdir()
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {"shadow_log": True})
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)
    monkeypatch.setattr(hub.snapshot, "_SNAPSHOT_CACHE", {"snapshot": None})
    logged = {"n": 0}
    monkeypatch.setattr(hub, "_record_routing_metric", lambda *a, **k: logged.__setitem__("n", logged["n"] + 1))
    hub._shadow_log_load_balance(ai_root, "cc", "terminal")
    assert logged["n"] == 0


def test_shadow_hook_off_when_disabled(monkeypatch, tmp_path):
    hub = _load_hub()
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {"shadow_log": False, "enabled": False})
    called = {"n": 0}
    monkeypatch.setattr(hub, "_record_routing_metric", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    hub._shadow_log_load_balance(tmp_path / ".ai", "cc", "terminal")
    assert called["n"] == 0


def test_shadow_hook_is_crash_safe(monkeypatch, tmp_path):
    hub = _load_hub()
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {"shadow_log": True})
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)
    monkeypatch.setattr(hub.snapshot, "_SNAPSHOT_CACHE", {"snapshot": {"schema_version": 1}})
    def _boom(*a, **k):
        raise RuntimeError("selector exploded")
    monkeypatch.setattr(hub.snapshot, "select_load_balanced_peer", _boom)
    # must NOT raise
    hub._shadow_log_load_balance(tmp_path / ".ai", "cc", "terminal")


# ── Arbiter-P1: premium/arbiter structural exclusion from bulk (DIR-005) ──────

def test_premium_profile_is_excluded_from_bulk(monkeypatch):
    cfg = {**CONFIG, "arbiter_models": ["cc.fable"]}
    _patch_rows(monkeypatch, [
        _row("cc", 0.90, profile="cc.fable"),
        _row("ag", 0.20, profile="ag.deepthink"),
    ])
    result = snapshot.select_load_balanced_peer({}, cfg, ask_id="premium-profile")
    assert result["selected_peer"] == "ag"
    assert "cc" not in result["candidates"]
    assert "cc" not in result["weights"]
    assert result["premium_excluded"] == ["cc"]


def test_profile_level_arbiter_entry_excludes_whole_peer(monkeypatch):
    cfg = {**CONFIG, "arbiter_models": ["cc.deepthink"]}
    _patch_rows(monkeypatch, [
        _row("cc", 0.90, profile="cc.deepthink"),
        _row("cc", 0.80, profile="cc.effort"),
        _row("ag", 0.20, profile="ag.deepthink"),
    ])
    result = snapshot.select_load_balanced_peer({}, cfg, ask_id="whole-peer")
    assert result["selected_peer"] == "ag"
    assert result["candidates"] == ["ag"]
    assert "cc" not in result["weights"]
    assert result["premium_excluded"] == ["cc"]


def test_premium_only_eligible_returns_no_candidate(monkeypatch):
    cfg = {**CONFIG, "arbiter_models": ["cc.fable"]}
    _patch_rows(monkeypatch, [
        _row("cc", 0.90, profile="cc.fable"),
        _row("ag", None, profile="ag.deepthink"),
    ])
    result = snapshot.select_load_balanced_peer({}, cfg, ask_id="premium-only")
    assert result["selected"] is None
    assert result["selected_peer"] is None
    assert result["reason"] == "no_eligible_candidate"
    assert result["premium_excluded"] == ["cc"]


def test_premium_exclusion_and_terminal_exclusion_both_apply(monkeypatch):
    cfg = {**CONFIG, "arbiter_models": ["ag.deepthink"]}
    _patch_rows(monkeypatch, [
        _row("cc", 0.09, profile="cc.effort"),
        _row("ag", 0.31, profile="ag.deepthink"),
        _row("cx", 0.12, profile="cx.effort"),
    ])
    result = snapshot.select_load_balanced_peer({}, cfg, terminal_peer="cc", ask_id="both")
    assert result["selected_peer"] == "cx"
    assert result["premium_excluded"] == ["ag"]
    assert result["terminal_excluded"] == "non_terminal_above_floor"
    assert result["weights"]["cc"] == 0.0
    assert "ag" not in result["weights"]
    assert result["candidates"] == ["cc", "cx"]


def test_empty_arbiter_models_preserves_existing_behavior(monkeypatch):
    cfg = {**CONFIG, "arbiter_models": []}
    _patch_rows(monkeypatch, [
        _row("cc", 0.09, profile="cc.fable"),
        _row("ag", 0.31, profile="ag.deepthink"),
    ])
    result = snapshot.select_load_balanced_peer({}, cfg, terminal_peer="cc", ask_id="empty-arbiter")
    assert "cc" in result["candidates"]
    assert "ag" in result["candidates"]
    assert result["weights"]["cc"] == 0.0
    assert result["terminal_excluded"] == "non_terminal_above_floor"
    assert result["premium_excluded"] == []
