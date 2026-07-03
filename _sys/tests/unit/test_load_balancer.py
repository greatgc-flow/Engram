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
