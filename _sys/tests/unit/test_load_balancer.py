"""Tests for the token load balancer — Phase 1 (snapshot.select_load_balanced_peer).

Design contract: _sys/docs/history/ops/token-load-balancing-design.md
(ag design + cx review). cx authored these tests; the impl was applied by the
terminal (peers do not write governed files — LL-20260703-005).
"""
import copy
import json
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


def _profile_conf(routing_state="eligible"):
    return {
        "model_id": "test-model",
        "reasoning_effort": "low",
        "runtime_context_window": 1000,
        "routing_state": routing_state,
        "cost_tier": "low",
    }


def _orch_with_profiles(peer, profiles):
    return {
        "hub_nodes": [{
            "type": "peer",
            "enabled": True,
            "node_id": peer,
            "default_profile": "standard",
            "profiles": profiles,
        }]
    }


def _profile_record(peer, bucket_label, profile_health=None):
    observed = "2026-07-08T00:00:00+00:00"
    return {
        "peer": peer,
        "model": "test-model",
        "domains": {
            "context": {
                "window_tokens": 1000,
                "used_tokens": 100,
                "utilization_pct": 10.0,
                "source": {"kind": "cached", "observed_at": observed, "confidence": "exact"},
            },
            "quota": {
                "buckets": [{"label": bucket_label, "used_frac": 0.10}],
                "source": {"kind": "cached", "observed_at": observed, "confidence": "exact"},
            },
            "health": {"profiles": profile_health or {}},
        },
        "raw": {"source": "health"},
    }


def test_build_profile_rows_blocks_closed_profile_and_lb_excludes_it(monkeypatch):
    observed = "2026-07-08T00:00:00+00:00"
    orch = {"hub_nodes": [
        _orch_with_profiles("ag", {"standard": _profile_conf()})["hub_nodes"][0],
        _orch_with_profiles("cx", {"standard": _profile_conf()})["hub_nodes"][0],
    ]}
    records = [
        _profile_record("ag", "G-5H", {"standard": {
            "gate_open": False,
            "rate_limit_state": {"limited": True, "reset_at": "2999-01-01T00:00:00+00:00"},
        }}),
        _profile_record("cx", "X-5H"),
    ]

    rows = snapshot._build_profile_rows(orch, records, observed)
    rows_by_profile = {r["profile"]: r for r in rows}
    assert rows_by_profile["ag.standard"]["state"] == "blocked"
    assert rows_by_profile["cx.standard"]["state"] == "eligible"

    lb_rows = [{**r, "quota_remaining": 0.5, "context_remaining": 0.5, "headroom": 0.5,
                "tier_strength": 2, "tier_risk": False} for r in rows]
    _patch_rows(monkeypatch, lb_rows)
    result = snapshot.select_load_balanced_peer({"profiles": rows}, CONFIG, ask_id="profile-health")
    assert result["selected_peer"] == "cx"
    assert "ag" not in result["weights"]


def test_declared_intelligence_evidence_does_not_change_routing_weights_or_arbiter_pick():
    observed = "2026-07-08T00:00:00+00:00"
    profiles = {
        "fable": {**_profile_conf(), "quota_families": ["C"]},
        "effort": {**_profile_conf(), "quota_families": ["G"]},
    }
    cc = _orch_with_profiles("cc", {"fable": profiles["fable"]})["hub_nodes"][0]
    ag = _orch_with_profiles("ag", {"effort": profiles["effort"]})["hub_nodes"][0]
    cc["default_profile"] = "fable"
    ag["default_profile"] = "effort"
    orch = {"hub_nodes": [cc, ag]}
    records = [_profile_record("cc", "C-5H"), _profile_record("ag", "G-5H")]
    plain = {"profiles": snapshot._build_profile_rows(orch, records, observed)}
    declared = copy.deepcopy(plain)
    declared["profiles"][0]["intelligence_evidence"] = {
        "estimate": {"kind": "point", "value": 60.0, "approximate": True},
        "source_kind": "declared", "verification": "unverified",
    }
    declared["profiles"][0]["profile_intent"] = {
        "selection_basis": "resilience_over_external_composite",
    }
    routing_cfg = {**CONFIG, "arbiter_models": []}
    plain_result = snapshot.select_load_balanced_peer(plain, routing_cfg, ask_id="d3-equivalence")
    declared_result = snapshot.select_load_balanced_peer(declared, routing_cfg, ask_id="d3-equivalence")
    assert json.dumps(plain_result, sort_keys=True) == json.dumps(declared_result, sort_keys=True)
    assert plain_result["weights"]
    arbiter_cfg = {"arbiter_models": ["cc.fable", "ag.effort"]}
    assert snapshot.select_arbiter(plain, arbiter_cfg) == "cc.fable"
    assert snapshot.select_arbiter(plain, arbiter_cfg) == snapshot.select_arbiter(declared, arbiter_cfg)


def test_profile_rows_propagate_declared_policy_metadata():
    observed = "2026-07-08T00:00:00+00:00"
    profile = {
        **_profile_conf(),
        "quota_families": ["G"],
        "intelligence_evidence": {
            "estimate": {"kind": "range", "min": 46.0, "max": 47.0, "approximate": True},
            "source_kind": "declared", "verification": "unverified",
        },
        "profile_intent": {"selection_basis": "resilience_over_external_composite"},
    }
    orch = _orch_with_profiles("ag", {"deepthink": profile})
    row = snapshot._build_profile_rows(orch, [_profile_record("ag", "G-5H")], observed)[0]
    assert row["intelligence_evidence"] == profile["intelligence_evidence"]
    assert row["profile_intent"] == profile["profile_intent"]


def test_build_profile_rows_expired_profile_cooldown_is_eligible():
    observed = "2026-07-08T00:00:00+00:00"
    orch = _orch_with_profiles("ag", {"standard": _profile_conf()})
    records = [_profile_record("ag", "G-5H", {"standard": {
        "gate_open": False,
        "rate_limit_state": {"limited": True, "reset_at": "2000-01-01T00:00:00+00:00"},
    }})]

    rows = snapshot._build_profile_rows(orch, records, observed)
    assert rows[0]["state"] == "eligible"


def test_build_profile_rows_missing_profile_health_does_not_block():
    observed = "2026-07-08T00:00:00+00:00"
    orch = _orch_with_profiles("ag", {"standard": _profile_conf()})
    records = [_profile_record("ag", "G-5H")]

    rows = snapshot._build_profile_rows(orch, records, observed)
    assert rows[0]["state"] == "eligible"


def test_build_profile_rows_ignores_removed_profile_health():
    observed = "2026-07-08T00:00:00+00:00"
    orch = _orch_with_profiles("ag", {"standard": _profile_conf()})
    records = [_profile_record("ag", "G-5H", {
        "removed": {"gate_open": True},
        "standard": {"gate_open": True},
    })]

    rows = snapshot._build_profile_rows(orch, records, observed)
    assert [r["profile"] for r in rows] == ["ag.standard"]


def test_build_profile_rows_malformed_profile_cooldown_is_blocked_fail_safe():
    observed = "2026-07-08T00:00:00+00:00"
    orch = _orch_with_profiles("ag", {"standard": _profile_conf()})
    records = [
        _profile_record("ag", "G-5H", {
            "standard": {
                "gate_open": False,
                "rate_limit_state": {
                    "limited": True,
                    "reset_at": 12345,
                },
            }
        })
    ]

    rows = snapshot._build_profile_rows(orch, records, observed)

    assert rows[0]["profile"] == "ag.standard"
    assert rows[0]["state"] == "blocked"


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


def test_peer_weight_bias_shifts_share_toward_biased_peer(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("ag", 0.40),
        _row("cx", 0.40),
    ])
    base = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="b0")
    biased = snapshot.select_load_balanced_peer(
        {}, {**CONFIG, "peer_weight_bias": {"ag": 1.5}}, ask_id="b0")

    assert base["probabilities"]["ag"] == pytest.approx(0.5, abs=0.02)
    assert biased["probabilities"]["ag"] > base["probabilities"]["ag"]
    assert biased["bias_applied"] == {"ag": 1.5}
    assert biased["probabilities"]["ag"] == pytest.approx(0.6, abs=0.02)


def test_peer_weight_bias_clamped_for_over_pacing_peer(monkeypatch):
    # ag is over-pacing (pacing_max=2.0): an amplifying bias must be clamped to 1.0
    # so it cannot pull more bulk work onto a rate-danger peer.
    ag_row = _row("ag", 0.40)
    ag_row["pacing_max"] = 2.0
    _patch_rows(monkeypatch, [ag_row, _row("cx", 0.40)])

    res = snapshot.select_load_balanced_peer(
        {}, {**CONFIG, "peer_weight_bias": {"ag": 1.5}, "pacing_penalty_enabled": False},
        ask_id="b1")

    # bias clamped to 1.0 (recorded as such for audit); ag not amplified
    assert res["bias_applied"].get("ag") == 1.0
    assert res["probabilities"]["ag"] == pytest.approx(0.5, abs=0.02)


def test_derived_headroom_bias_favors_larger_absolute_window(monkeypatch):
    # ag has a much larger absolute free capacity than cx -> derived (sqrt-damped)
    # bias steers more share to ag, but cx is clamped at the band floor (not starved).
    ag_row = _row("ag", 0.40); ag_row["abs_headroom"] = 1_045_000
    cx_row = _row("cx", 0.40); cx_row["abs_headroom"] = 223_000
    _patch_rows(monkeypatch, [ag_row, cx_row])
    cfg = {**CONFIG, "headroom_bias": {"enabled": True, "min": 0.75, "max": 1.5}}

    res = snapshot.select_load_balanced_peer({}, cfg, ask_id="d0")

    assert res["bias_applied"]["ag"] > 1.0
    assert res["bias_applied"]["cx"] == 0.75          # clamped at floor, not 0.59
    assert res["probabilities"]["ag"] > res["probabilities"]["cx"]
    assert res["bias_applied"]["ag"] == pytest.approx(1.28, abs=0.05)  # sqrt-damped, not 4.7x


def test_derived_bias_absent_without_measured_abs_headroom(monkeypatch):
    # No abs_headroom on any row -> no bias fabricated (DIR-004).
    _patch_rows(monkeypatch, [_row("ag", 0.40), _row("cx", 0.40)])
    cfg = {**CONFIG, "headroom_bias": {"enabled": True}}

    res = snapshot.select_load_balanced_peer({}, cfg, ask_id="d1")

    assert res["bias_applied"] == {}
    assert res["probabilities"]["ag"] == pytest.approx(0.5, abs=0.02)


def test_derived_bias_clamped_for_over_pacing_peer(monkeypatch):
    ag_row = _row("ag", 0.40); ag_row["abs_headroom"] = 1_045_000; ag_row["pacing_max"] = 2.0
    cx_row = _row("cx", 0.40); cx_row["abs_headroom"] = 223_000
    _patch_rows(monkeypatch, [ag_row, cx_row])
    cfg = {**CONFIG, "headroom_bias": {"enabled": True}, "pacing_penalty_enabled": False}

    res = snapshot.select_load_balanced_peer({}, cfg, ask_id="d2")

    assert res["bias_applied"]["ag"] == 1.0            # amplification gated by pacing danger


def test_manual_bias_overrides_derived(monkeypatch):
    ag_row = _row("ag", 0.40); ag_row["abs_headroom"] = 1_045_000
    cx_row = _row("cx", 0.40); cx_row["abs_headroom"] = 223_000
    _patch_rows(monkeypatch, [ag_row, cx_row])
    cfg = {**CONFIG, "headroom_bias": {"enabled": True}, "peer_weight_bias": {"ag": 1.1}}

    res = snapshot.select_load_balanced_peer({}, cfg, ask_id="d3")

    assert res["bias_applied"]["ag"] == 1.1            # manual pin wins over derived 1.28


def test_context_affinity_lifts_biggest_window_only_for_heavy_tasks(monkeypatch):
    ag_row = _row("ag", 0.40); ag_row["abs_headroom"] = 1_045_000
    cx_row = _row("cx", 0.40); cx_row["abs_headroom"] = 223_000
    _patch_rows(monkeypatch, [ag_row, cx_row])
    cfg = {**CONFIG, "context_affinity": {
        "enabled": True, "heavy_task_tokens": 32000, "max_lift": 1.5}}

    light = snapshot.select_load_balanced_peer({}, cfg, ask_id="c0", task_tokens=500)
    heavy = snapshot.select_load_balanced_peer({}, cfg, ask_id="c0", task_tokens=100000)

    assert light["affinity_applied"] is None
    assert heavy["affinity_applied"]["peer"] == "ag"
    assert heavy["affinity_applied"]["lift"] == 1.5
    assert heavy["probabilities"]["ag"] > light["probabilities"]["ag"]


def test_context_affinity_skips_over_pacing_top_peer(monkeypatch):
    ag_row = _row("ag", 0.40); ag_row["abs_headroom"] = 1_045_000; ag_row["pacing_max"] = 2.0
    cx_row = _row("cx", 0.40); cx_row["abs_headroom"] = 223_000
    _patch_rows(monkeypatch, [ag_row, cx_row])
    cfg = {**CONFIG, "context_affinity": {"enabled": True, "heavy_task_tokens": 1000, "max_lift": 1.5},
           "pacing_penalty_enabled": False}

    res = snapshot.select_load_balanced_peer({}, cfg, ask_id="c1", task_tokens=50000)
    assert res["affinity_applied"] is None       # ag is over-pacing -> not lifted


def test_should_switch_session_peer_hysteresis():
    # keep incumbent unless challenger has >= switch_ratio x its abs headroom
    assert snapshot.should_switch_session_peer(100_000, 150_000, switch_ratio=2.0) is False
    assert snapshot.should_switch_session_peer(100_000, 210_000, switch_ratio=2.0) is True
    assert snapshot.should_switch_session_peer(100_000, 0, incumbent_stale=True) is True
    assert snapshot.should_switch_session_peer(100_000, 50_000, incumbent_near_floor=True) is True
    assert snapshot.should_switch_session_peer(0, 10_000) is True   # exhausted incumbent


def test_bulk_exclude_profile_drops_only_that_profile_not_whole_peer(monkeypatch):
    # ag.opus (premium) is profile-excluded; ag's Gemini bulk profile stays eligible.
    _patch_rows(monkeypatch, [
        _row("ag", 0.40, profile="ag.opus", cost_tier="high"),
        _row("ag", 0.30, profile="ag.deepthink"),
        _row("cx", 0.12, profile="cx.effort"),
    ])
    cfg = {**CONFIG, "bulk_exclude_profiles": ["ag.opus"]}

    result = snapshot.select_load_balanced_peer({}, cfg, ask_id="bx1")

    assert "ag" in result["weights"]          # peer 'ag' still bulk-eligible
    assert result["weights"]["ag"] > 0.0
    # ag's representative must be the non-excluded profile, never ag.opus
    ag_rows = [c for c in result["candidates"] if c == "ag"]
    assert ag_rows, "ag should remain a candidate via ag.deepthink"


def test_bulk_exclude_profile_removes_peer_when_it_is_the_only_row(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("ag", 0.40, profile="ag.opus", cost_tier="high"),
        _row("cx", 0.20, profile="cx.effort"),
    ])
    cfg = {**CONFIG, "bulk_exclude_profiles": ["ag.opus"]}

    result = snapshot.select_load_balanced_peer({}, cfg, ask_id="bx2")

    assert result["selected_peer"] == "cx"
    assert "ag" not in result["weights"]


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
    assert result["representative_profiles"]["ag"] == "ag.deepthink"


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
    assert result["premium_excluded"] == ["cc.fable"]


def test_profile_level_arbiter_entry_excludes_only_that_profile(monkeypatch):
    cfg = {**CONFIG, "arbiter_models": ["cc.deepthink"]}
    _patch_rows(monkeypatch, [
        _row("cc", 0.90, profile="cc.deepthink"),
        _row("cc", 0.80, profile="cc.effort"),
        _row("ag", 0.20, profile="ag.deepthink"),
    ])
    result = snapshot.select_load_balanced_peer({}, cfg, ask_id="profile-only")
    assert "cc" in result["candidates"]
    assert "cc" in result["weights"]
    assert result["premium_excluded"] == ["cc.deepthink"]
    assert result["selected"]["profile"] == "cc.effort"


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
    assert result["premium_excluded"] == ["cc.fable"]


def test_premium_exclusion_and_terminal_exclusion_both_apply(monkeypatch):
    cfg = {**CONFIG, "arbiter_models": ["ag.deepthink"]}
    _patch_rows(monkeypatch, [
        _row("cc", 0.09, profile="cc.effort"),
        _row("ag", 0.31, profile="ag.deepthink"),
        _row("cx", 0.12, profile="cx.effort"),
    ])
    result = snapshot.select_load_balanced_peer({}, cfg, terminal_peer="cc", ask_id="both")
    assert result["selected_peer"] == "cx"
    assert result["premium_excluded"] == ["ag.deepthink"]
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


def test_bare_peer_arbiter_entry_still_excludes_all_peer_rows(monkeypatch):
    cfg = {**CONFIG, "arbiter_models": ["cc"]}
    _patch_rows(monkeypatch, [
        _row("cc", 0.90, profile="cc.deepthink"),
        _row("cc", 0.80, profile="cc.effort"),
        _row("ag", 0.20, profile="ag.deepthink"),
    ])
    result = snapshot.select_load_balanced_peer({}, cfg, ask_id="bare-peer")
    assert result["selected_peer"] == "ag"
    assert result["candidates"] == ["ag"]
    assert "cc" not in result["weights"]
    assert result["premium_excluded"] == ["cc.deepthink", "cc.effort"]


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


def test_pacing_default_and_explicit_true_are_byte_identical(monkeypatch):
    """T56: the explicit config key preserves the established default-on behavior."""
    rows = [
        _row_pacing("ag", 0.40, pacing_max=2.0),
        _row_pacing("cx", 0.20, pacing_max=1.0),
    ]
    monkeypatch.setattr(snapshot, "_derive_headroom_rows", lambda _snapshot: copy.deepcopy(rows))

    implicit = snapshot.select_load_balanced_peer({}, CONFIG, ask_id="pacing-explicit")
    explicit = snapshot.select_load_balanced_peer(
        {}, {**CONFIG, "pacing_penalty_enabled": True}, ask_id="pacing-explicit"
    )

    assert implicit == explicit


def test_live_routing_config_declares_pacing_penalty_enabled():
    """T56: the live config documents the default instead of relying on fallback."""
    routing = json.loads((SYS_DIR / "ai" / "routing-config.json").read_text(encoding="utf-8"))
    assert routing["token_load_balancing"]["pacing_penalty_enabled"] is True


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


def test_filter_profile_buckets_fable_includes_c_buckets():
    buckets = [{"label": "C-5H"}, {"label": "C-7D"}, {"label": "F-7D"}, {"label": "X-5H"}]
    fable_buckets = snapshot._filter_profile_buckets("cc", "fable", buckets)
    assert [b.get("label") for b in fable_buckets] == ["C-5H", "C-7D", "F-7D"]

    standard_buckets = snapshot._filter_profile_buckets("cc", "standard", buckets)
    assert [b.get("label") for b in standard_buckets] == ["C-5H", "C-7D"]

    measured = snapshot._filter_profile_buckets("cc", "fable", [
        {"label": "C-5H", "used_frac": 0.20},
        {"label": "F-7D", "used_frac": 0.75},
        {"label": "X-7D", "used_frac": 0.99},
    ])
    fable_remaining = snapshot._quota_remaining({"quota": {"buckets": measured}})
    assert fable_remaining == pytest.approx(0.25)


def test_declared_quota_family_assignments_and_snapshot_metadata():
    orch = snapshot._read_orchestration()
    expected = {
        "cc.standard": ("C-",),
        "cc.effort": ("C-",),
        "cc.deepthink": ("C-",),
        "cc.fable": ("F-", "C-"),
        "ag.standard": ("G-",),
        "ag.effort": ("G-",),
        "ag.deepthink": ("G-",),
        "ag.opus": ("3P-",),
        "ag.gptoss": ("3P-",),
        "cx.standard": ("X-",),
        "cx.effort": ("X-",),
        "cx.deepthink": ("X-",),
    }
    for profile_id, families in expected.items():
        peer_id, profile_name = profile_id.split(".", 1)
        assert snapshot._quota_family_for_profile(peer_id, profile_name, orch) == families

    observed = "2026-07-13T00:00:00+00:00"
    rows = snapshot._build_profile_rows(
        _orch_with_profiles("cx", {
            "standard": {
                **_profile_conf(),
                "profile_class": "tier",
                "quota_families": ["X"],
            }
        }),
        [_profile_record("cx", "X-7D")],
        observed,
    )
    assert rows[0]["profile_class"] == "tier"
    assert rows[0]["quota_families"] == ["X"]


def test_quota_family_legacy_fallback_omits_removed_ag_sonnet():
    legacy = {
        "hub_nodes": [{
            "node_id": "ag",
            "type": "peer",
            "enabled": True,
            "profiles": {
                "standard": {"routing_state": "eligible"},
                "opus": {"routing_state": "manual_only"},
                "sonnet": {"routing_state": "eligible"},
                "unknown": {"routing_state": "eligible"},
            },
        }]
    }
    assert snapshot._quota_family_for_profile("ag", "standard", legacy) == ("G-",)
    assert snapshot._quota_family_for_profile("ag", "opus", legacy) == ("3P-",)
    assert snapshot._quota_family_for_profile("ag", "sonnet", legacy) is None
    assert snapshot._quota_family_for_profile("ag", "unknown", legacy) is None


def test_shared_quota_reserve_clamping_and_telemetry():
    cfg = {
        "enabled": True,
        "effective_headroom_floor": 0.10,
        "shared_quota_reserve": {
            "enabled": True,
            "families": {
                "3P": {
                    "reserve_for": ["peer2.reserved"],
                    "reserve_fraction": 0.25
                }
            }
        }
    }

    # Case A: Headroom is plenty (remaining headroom = 0.40 > 0.25)
    snap_plenty = {
        "profiles": [
            {
                "profile": "peer2.reserved",
                "peer": "peer2",
                "state": "eligible",
                "quota": {"buckets": [{"label": "3P-WEEKLY", "used_frac": 0.60}]},
                "context": {"utilization_pct": 0.0}
            },
            {
                "profile": "peer1.bulk",
                "peer": "peer1",
                "state": "eligible",
                "quota": {"buckets": [{"label": "3P-WEEKLY", "used_frac": 0.60}]},
                "context": {"utilization_pct": 0.0}
            }
        ]
    }
    result_plenty = snapshot.select_load_balanced_peer(snap_plenty, cfg, ask_id="test-plenty")
    assert result_plenty["selected_peer"] is not None
    assert result_plenty["weights"]["peer1"] == pytest.approx(0.40)
    assert result_plenty["weights"]["peer2"] == pytest.approx(0.40)
    assert not result_plenty.get("telemetry_events")

    # Case B: Headroom is below reserve (remaining = 0.20 < 0.25)
    snap_clamped = {
        "profiles": [
            {
                "profile": "peer2.reserved",
                "peer": "peer2",
                "state": "eligible",
                "quota": {"buckets": [{"label": "3P-WEEKLY", "used_frac": 0.80}]},
                "context": {"utilization_pct": 0.0}
            },
            {
                "profile": "peer1.bulk",
                "peer": "peer1",
                "state": "eligible",
                "quota": {"buckets": [{"label": "3P-WEEKLY", "used_frac": 0.80}]},
                "context": {"utilization_pct": 0.0}
            }
        ]
    }
    result_clamped = snapshot.select_load_balanced_peer(snap_clamped, cfg, ask_id="test-clamped")
    # peer1 (bulk) should be clamped to eps (0.01)
    assert result_clamped["weights"]["peer1"] == pytest.approx(0.01)
    # peer2 (reserved) is not clamped
    assert result_clamped["weights"]["peer2"] == pytest.approx(0.20)
    
    # Telemetry should contain clamp event
    events = result_clamped.get("telemetry_events", [])
    clamp_events = [e for e in events if e.get("event") == "shared_quota_reserve_clamp"]
    assert len(clamp_events) == 1
    assert clamp_events[0]["family"] == "3P"
    assert clamp_events[0]["profile"] == "peer1.bulk"
    assert clamp_events[0]["remaining_headroom"] == pytest.approx(0.20)
    assert clamp_events[0]["reserve_fraction"] == 0.25

    # Case C: Regression guard (reserve disabled)
    cfg_disabled = {
        "enabled": True,
        "effective_headroom_floor": 0.10,
        "shared_quota_reserve": {
            "enabled": False,
            "families": {
                "3P": {
                    "reserve_for": ["peer2.reserved"],
                    "reserve_fraction": 0.25
                }
            }
        }
    }
    result_disabled = snapshot.select_load_balanced_peer(snap_clamped, cfg_disabled, ask_id="test-disabled")
    assert result_disabled["weights"]["peer1"] == pytest.approx(0.20)
    assert result_disabled["weights"]["peer2"] == pytest.approx(0.20)
    assert not result_disabled.get("telemetry_events")

    # Case D: Reserved profile critically low warning (remaining = 0.05 <= 0.10)
    snap_critical = {
        "profiles": [
            {
                "profile": "peer2.reserved",
                "peer": "peer2",
                "state": "eligible",
                "quota": {"buckets": [{"label": "3P-WEEKLY", "used_frac": 0.95}]},
                "context": {"utilization_pct": 0.0}
            },
            {
                "profile": "peer1.bulk",
                "peer": "peer1",
                "state": "eligible",
                "quota": {"buckets": [{"label": "3P-WEEKLY", "used_frac": 0.95}]},
                "context": {"utilization_pct": 0.0}
            }
        ]
    }
    result_critical = snapshot.select_load_balanced_peer(snap_critical, cfg, ask_id="test-critical")
    events_crit = result_critical.get("telemetry_events", [])
    starvation_events = [e for e in events_crit if e.get("event") == "premium_starvation_warning"]
    assert len(starvation_events) == 1
    assert starvation_events[0]["family"] == "3P"
    assert starvation_events[0]["profile"] == "peer2.reserved"
    assert starvation_events[0]["remaining_headroom"] == pytest.approx(0.05)
    assert starvation_events[0]["threshold"] == pytest.approx(0.10)
