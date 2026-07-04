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
    # Fresh coordinator: a far-future challenge_until proves freshness so the
    # stale-coordinator guard (_fresh_active_coordinator) returns "cc".
    (ai_root / "state.json").write_text(
        '{"active_coordinator": "cc", "leadership": {"challenge_until": "2099-01-01T00:00:00"}}',
        encoding="utf-8")
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


# ── P2: Pacing Penalty Tests (design contract §3.3) ──────────────────────────

def _row_pacing(peer, headroom, state="eligible", profile=None, cost_tier="low", effort="high", pacing_max=1.0):
    return {
        "peer": peer,
        "profile": profile or f"{peer}.effort",
        "state": state,
        "effort": effort,
        "cost_tier": cost_tier,
        "quota_remaining": headroom,
        "context_remaining": headroom,
        "headroom": headroom,
        "pacing_max": pacing_max,
        "tier_strength": 2,
        "tier_risk": False,
        "sources": {},
    }


def test_pacing_penalty_halves_headroom(monkeypatch):
    _patch_rows(monkeypatch, [
        _row_pacing("ag", 0.40, pacing_max=2.0),
        _row_pacing("cx", 0.20, pacing_max=1.0),
    ])
    result = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="pacing-halves")
    assert result["weights"]["ag"] == pytest.approx(0.20)
    assert result["weights"]["cx"] == pytest.approx(0.20)
    assert result["probabilities"]["ag"] == pytest.approx(0.5, abs=0.001)
    assert result["probabilities"]["cx"] == pytest.approx(0.5, abs=0.001)
    assert result["pacing_applied"]["ag"] == 2.0
    assert result["pacing_applied"]["cx"] == 1.0


def test_pacing_below_one_has_no_penalty(monkeypatch):
    _patch_rows(monkeypatch, [
        _row_pacing("ag", 0.20, pacing_max=0.5),
        _row_pacing("cx", 0.20, pacing_max=1.0),
    ])
    result = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="pacing-below-one")
    assert result["weights"]["ag"] == pytest.approx(0.20)
    assert result["weights"]["cx"] == pytest.approx(0.20)


def test_absent_pacing_treated_as_one(monkeypatch):
    r1 = _row_pacing("ag", 0.20)
    del r1["pacing_max"]
    _patch_rows(monkeypatch, [
        r1,
        _row_pacing("cx", 0.20, pacing_max=1.0),
    ])
    result = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="pacing-absent")
    assert result["weights"]["ag"] == pytest.approx(0.20)
    assert result["weights"]["cx"] == pytest.approx(0.20)
    assert result["pacing_applied"]["ag"] == 1.0
    assert result["pacing_applied"]["cx"] == 1.0


def test_pacing_penalty_disabled(monkeypatch):
    cfg = {**CONFIG, "pacing_penalty_enabled": False}
    _patch_rows(monkeypatch, [
        _row_pacing("ag", 0.40, pacing_max=2.0),
        _row_pacing("cx", 0.20, pacing_max=1.0),
    ])
    result = snapshot.select_load_balanced_peer({}, cfg, ask_id="pacing-disabled")
    assert result["weights"]["ag"] == pytest.approx(0.40)
    assert result["weights"]["cx"] == pytest.approx(0.20)
    assert result["probabilities"]["ag"] == pytest.approx(2/3, abs=0.001)
    assert result["probabilities"]["cx"] == pytest.approx(1/3, abs=0.001)


def test_design_worked_example_with_pacing(monkeypatch):
    _patch_rows(monkeypatch, [
        _row_pacing("cc", 0.12, pacing_max=1.33),
        _row_pacing("ag", 0.31, pacing_max=0.75),
        _row_pacing("cx", 0.20, pacing_max=1.64),
    ])
    result = snapshot.select_load_balanced_peer(
        {"schema_version": 1}, CONFIG, terminal_peer="cc", ask_id="worked-example-pacing")
    assert result["selected_peer"] != "cc"
    assert result["weights"]["cc"] == 0.0
    assert result["probabilities"]["ag"] == pytest.approx(0.31 / 0.432, abs=0.001)
    assert result["probabilities"]["cx"] == pytest.approx((0.20/1.64) / 0.432, abs=0.001)
    assert result["terminal_excluded"] == "non_terminal_above_floor"
    assert result["pacing_applied"]["cc"] == 1.33
    assert result["pacing_applied"]["ag"] == 0.75
    assert result["pacing_applied"]["cx"] == 1.64


def test_derive_headroom_rows_pacing_extraction():
    snap = {
        "profiles": [
            {"profile": "ag.standard", "peer": "ag", "state": "eligible", "effort": "low",
             "quota": {"buckets": [{"used_frac": 0.05, "pacing": {"ratio": 1.25}},
                                    {"used_frac": 0.10, "pacing_ratio": 1.50}]},
             "context": {"utilization_pct": 10.0}, "sources": {}},
            {"profile": "cx.deepthink", "peer": "cx", "state": "eligible", "effort": "xhigh",
             "quota": {"buckets": [{"used_frac": 0.20}]},
             "context": {"utilization_pct": 20.0}, "sources": {}},
        ]
    }
    rows_by_profile = {r["profile"]: r for r in snapshot._derive_headroom_rows(snap)}
    assert rows_by_profile["ag.standard"]["pacing_max"] == pytest.approx(1.50)
    assert rows_by_profile["cx.deepthink"]["pacing_max"] == pytest.approx(1.0)


# ── P1.5 In-flight load deduction tests ─────────────────────────────────────

def test_inflight_reduces_headroom_by_deduction(monkeypatch):
    _patch_rows(monkeypatch, [_row("ag", 0.40), _row("cx", 0.30)])
    res_none = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="no-inflight")
    res_inflight = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="inflight", inflight={"ag": 0.15})
    assert res_inflight["weights"]["ag"] == pytest.approx(res_none["weights"]["ag"] - 0.15)
    assert res_inflight["weights"]["cx"] == pytest.approx(res_none["weights"]["cx"])
    assert res_inflight["inflight_applied"]["ag"] == 0.15
    assert res_inflight["inflight_applied"]["cx"] == 0.0


def test_two_equal_headroom_peers_one_with_inflight_prefers_other(monkeypatch):
    _patch_rows(monkeypatch, [_row("ag", 0.30), _row("cx", 0.30)])
    result = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="equal-headroom", inflight={"ag": 0.10})
    assert result["weights"]["ag"] == pytest.approx(0.20)
    assert result["weights"]["cx"] == pytest.approx(0.30)
    assert result["probabilities"]["cx"] == pytest.approx(0.60)
    assert result["probabilities"]["ag"] == pytest.approx(0.40)


def test_inflight_pushing_below_floor_restores_terminal(monkeypatch):
    _patch_rows(monkeypatch, [_row("cc", 0.05), _row("ag", 0.15), _row("cx", 0.05)])
    res_no = snapshot.select_load_balanced_peer({}, CONFIG, terminal_peer="cc", ask_id="no-inflight-floor")
    assert res_no["terminal_excluded"] == "non_terminal_above_floor"
    assert res_no["weights"]["cc"] == 0.0
    res_with = snapshot.select_load_balanced_peer({}, CONFIG, terminal_peer="cc", ask_id="inflight-floor", inflight={"ag": 0.06})
    assert res_with["terminal_excluded"] is None
    assert res_with["weights"]["cc"] > 0.0


def test_inflight_deduction_disabled_ignores_inflight(monkeypatch):
    _patch_rows(monkeypatch, [_row("ag", 0.40), _row("cx", 0.20)])
    cfg = {**CONFIG, "inflight_deduction_enabled": False}
    result = snapshot.select_load_balanced_peer({}, cfg, ask_id="disabled", inflight={"ag": 0.15})
    assert result["weights"]["ag"] == pytest.approx(0.40)
    assert result["weights"]["cx"] == pytest.approx(0.20)
    assert result["inflight_applied"]["ag"] == 0.15


def test_absent_or_empty_inflight_behaves_normally(monkeypatch):
    _patch_rows(monkeypatch, [_row("cc", 0.090), _row("ag", 0.310), _row("cx", 0.122)])
    res_none = snapshot.select_load_balanced_peer({"schema_version": 1}, CONFIG, terminal_peer="cc", ask_id="wx-none")
    assert res_none["weights"]["cc"] == 0.0
    assert res_none["probabilities"]["ag"] == pytest.approx(0.7176, abs=0.001)
    assert res_none["inflight_applied"]["ag"] == 0.0
    res_empty = snapshot.select_load_balanced_peer({"schema_version": 1}, CONFIG, terminal_peer="cc", ask_id="wx-empty", inflight={})
    assert res_empty["probabilities"]["cx"] == pytest.approx(0.2824, abs=0.001)


def test_non_numeric_inflight_coerced_to_zero(monkeypatch):
    _patch_rows(monkeypatch, [_row("ag", 0.40), _row("cx", 0.30)])
    result = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="non-numeric", inflight={"ag": "invalid", "cx": None, "cc": True})
    assert result["weights"]["ag"] == pytest.approx(0.40)
    assert result["weights"]["cx"] == pytest.approx(0.30)
    assert result["inflight_applied"]["ag"] == 0.0
    assert result["inflight_applied"]["cx"] == 0.0


def test_inflight_clamping_floors_headroom_at_zero(monkeypatch):
    _patch_rows(monkeypatch, [_row("ag", 0.40), _row("cx", 0.30)])
    result = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="clamped", inflight={"ag": 0.50})
    assert result["weights"]["ag"] == pytest.approx(0.01)
    assert result["weights"]["cx"] == pytest.approx(0.30)
