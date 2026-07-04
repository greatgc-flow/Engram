"""Tests for arbiter live-wiring step 1 in hub.py.

Covers rolling budget persistence and the no-model-call arbiter decision
orchestrator. Live cc.fable invocation and persistence are deferred (step 2).
cx authored these tests; the impl was applied by the terminal (LL-005).
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub


CONFIG = {
    "arbiter_models": ["cc.fable", "cc.deepthink"],
    "triggers": ["dissent", "high_risk", "r10_final"],
    "invocation_budget_5h": 5,
}


NOW = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)


def _ai_root(tmp_path):
    root = tmp_path / ".ai"
    root.mkdir()
    return root


def _snapshot_with_fable():
    return {
        "profiles": [
            {
                "profile": "cc.fable",
                "peer": "cc",
                "state": "eligible",
                "effort": "deepthink",
                "cost_tier": "high",
                "quota": {"buckets": [{"used_frac": 0.10}]},
                "context": {"utilization_pct": 20.0},
                "sources": {},
            }
        ]
    }


def test_arbiter_budget_fresh_record_increment_and_rollover(tmp_path):
    ai_root = _ai_root(tmp_path)

    assert hub._arbiter_budget_count(ai_root, now=NOW) == 0

    hub._arbiter_record_invocation(ai_root, now=NOW)
    assert hub._arbiter_budget_count(ai_root, now=NOW) == 1

    hub._arbiter_record_invocation(ai_root, now=NOW + timedelta(minutes=1))
    assert hub._arbiter_budget_count(ai_root, now=NOW + timedelta(minutes=2)) == 2

    later = NOW + timedelta(hours=5, seconds=1)
    assert hub._arbiter_budget_count(ai_root, now=later) == 0

    hub._arbiter_record_invocation(ai_root, now=later)
    assert hub._arbiter_budget_count(ai_root, now=later) == 1


def test_arbiter_budget_corrupt_file_is_zero(tmp_path):
    ai_root = _ai_root(tmp_path)
    (ai_root / "arbiter_budget.json").write_text("{not-json", encoding="utf-8")

    assert hub._arbiter_budget_count(ai_root, now=NOW) == 0


def test_arbiter_decide_fires_with_budget_ok_and_available_arbiter(tmp_path):
    ai_root = _ai_root(tmp_path)

    result = hub.arbiter_decide(
        ai_root,
        {"kind": "dissent"},
        CONFIG,
        snapshot_obj=_snapshot_with_fable(),
        now=NOW,
    )

    assert result["fire"] is True
    assert result["reason"] == "triggered"
    assert result["kind"] == "dissent"
    assert result["authority"] == "override"
    assert result["arbiter"] == "cc.fable"
    assert result["budget_count"] == 0
    assert hub._arbiter_budget_count(ai_root, now=NOW) == 0
    assert not (ai_root / "arbiter_budget.json").exists()


def test_arbiter_decide_no_arbiter_available_when_selector_returns_none(monkeypatch, tmp_path):
    ai_root = _ai_root(tmp_path)
    monkeypatch.setattr(hub.snapshot, "select_arbiter", lambda *_args, **_kwargs: None)

    result = hub.arbiter_decide(
        ai_root,
        {"kind": "high_risk"},
        CONFIG,
        snapshot_obj={"profiles": []},
        now=NOW,
    )

    assert result["fire"] is False
    assert result["reason"] == "no_arbiter_available"
    assert result["kind"] == "high_risk"
    assert result["authority"] == "override"
    assert result["arbiter"] is None
    assert result["budget_count"] == 0


def test_arbiter_decide_not_a_trigger_for_routine(monkeypatch, tmp_path):
    ai_root = _ai_root(tmp_path)

    def fail_select(*_args, **_kwargs):
        raise AssertionError("select_arbiter must not run for non-trigger contexts")

    monkeypatch.setattr(hub.snapshot, "select_arbiter", fail_select)

    result = hub.arbiter_decide(
        ai_root,
        {"kind": "routine"},
        CONFIG,
        snapshot_obj=_snapshot_with_fable(),
        now=NOW,
    )

    assert result["fire"] is False
    assert result["reason"] == "not_a_trigger"
    assert result["kind"] == "routine"
    assert result["authority"] == "advisory"
    assert result["arbiter"] is None
    assert result["budget_count"] == 0


def test_arbiter_decide_snapshot_unavailable(monkeypatch, tmp_path):
    ai_root = _ai_root(tmp_path)
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", False)

    result = hub.arbiter_decide(
        ai_root,
        {"kind": "dissent"},
        CONFIG,
        snapshot_obj=_snapshot_with_fable(),
        now=NOW,
    )

    assert result == {
        "fire": False,
        "reason": "snapshot_unavailable",
        "kind": "dissent",
        "authority": "override",
        "arbiter": None,
        "budget_count": 0,
    }
