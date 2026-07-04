"""Tests for arbiter invocation decision helpers in snapshot.py.

Design contract: _sys/docs/history/ops/token-load-balancing-design.md
Smartest-Model Final Arbiter section + DIR-005. cx authored these tests; the
impl was applied by the terminal (peers do not write governed files, LL-005).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import snapshot


CONFIG = {
    "arbiter_models": ["cc.fable", "cc.deepthink"],
    "triggers": ["dissent", "high_risk", "r10_final"],
    "invocation_budget_5h": 5,
}


def _row(peer, headroom, state="eligible", profile=None):
    return {
        "peer": peer,
        "profile": profile or f"{peer}.effort",
        "state": state,
        "headroom": headroom,
    }


def _patch_rows(monkeypatch, rows):
    monkeypatch.setattr(snapshot, "_derive_headroom_rows", lambda _snapshot: list(rows))


def test_select_arbiter_picks_first_usable_in_config_order(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("cc", 0.42, profile="cc.fable"),
        _row("cc", 0.88, profile="cc.deepthink"),
    ])

    assert snapshot.select_arbiter({}, CONFIG) == "cc.fable"


def test_select_arbiter_skips_red_or_absent_primary_and_falls_back(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("cc", 0.90, state="quarantined", profile="cc.fable"),
        _row("ag", None, profile="ag.deepthink"),
        _row("cx", 0.31, profile="cx.deepthink"),
    ])
    cfg = {**CONFIG, "arbiter_models": ["cc.fable", "ag.deepthink", "cx.deepthink"]}

    assert snapshot.select_arbiter({}, cfg) == "cx.deepthink"


def test_select_arbiter_returns_none_when_all_unusable(monkeypatch):
    _patch_rows(monkeypatch, [
        _row("cc", None, profile="cc.fable"),
        _row("cc", 0.20, state="RED", profile="cc.deepthink"),
    ])

    assert snapshot.select_arbiter({}, CONFIG) is None


@pytest.mark.parametrize(("arbiter_models", "expected"), [
    (["cc.fable"], "cc.fable"),
    (["ag"], "ag"),
])
def test_select_arbiter_matches_profile_id_or_peer_id(monkeypatch, arbiter_models, expected):
    _patch_rows(monkeypatch, [
        _row("cc", 0.40, profile="cc.fable"),
        _row("ag", 0.30, profile="ag.effort"),
    ])

    assert snapshot.select_arbiter({}, {"arbiter_models": arbiter_models}) == expected


@pytest.mark.parametrize(("kind", "authority"), [
    ("dissent", "override"),
    ("high_risk", "override"),
    ("r10_final", "advisory"),
])
def test_evaluate_arbiter_trigger_fires_for_configured_kinds_with_budget(kind, authority):
    result = snapshot.evaluate_arbiter_trigger({"kind": kind}, CONFIG, invocations_this_window=0)

    assert result == {
        "fire": True,
        "reason": "triggered",
        "kind": kind,
        "authority": authority,
    }


def test_evaluate_arbiter_trigger_rejects_routine_as_not_a_trigger():
    result = snapshot.evaluate_arbiter_trigger({"kind": "routine"}, CONFIG, invocations_this_window=0)

    assert result == {
        "fire": False,
        "reason": "not_a_trigger",
        "kind": "routine",
        "authority": "advisory",
    }


def test_evaluate_arbiter_trigger_rejects_when_budget_exhausted():
    result = snapshot.evaluate_arbiter_trigger({"kind": "dissent"}, CONFIG, invocations_this_window=5)

    assert result == {
        "fire": False,
        "reason": "budget_exhausted",
        "kind": "dissent",
        "authority": "override",
    }


def test_build_final_opinion_record_shape_json_serializable_and_authority_passthrough():
    record = snapshot.build_final_opinion_record(
        round_id="r-1234",
        arbiter="cc.fable",
        kind="dissent",
        authority="override",
        verdict="GO",
        dissent_summary="cc disagreed with ag on rollback risk",
    )

    assert record["type"] == "FINAL_OPINION"
    assert record["round_id"] == "r-1234"
    assert record["arbiter"] == "cc.fable"
    assert record["kind"] == "dissent"
    assert record["authority"] == "override"
    assert record["verdict"] == "GO"
    assert record["dissent_summary"] == "cc disagreed with ag on rollback risk"
    datetime.fromisoformat(record["ts"])
    json.dumps(record)
