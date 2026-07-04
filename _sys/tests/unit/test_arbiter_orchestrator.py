"""Tests for final arbiter step 3B/C orchestration.

Enable-gated only. Tests always inject a mock invoker or use disabled config;
no real arbiter subprocess/model call is made. cx authored these tests; the impl
was applied by the terminal (LL-005).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub


NOW = datetime(2026, 7, 4, 15, 0, tzinfo=timezone.utc)

ENABLED_CONFIG = {
    "enabled": True,
    "arbiter_models": ["cc.fable"],
    "triggers": ["dissent", "high_risk", "r10_final"],
    "invocation_budget_5h": 5,
}

DISABLED_CONFIG = {
    **ENABLED_CONFIG,
    "enabled": False,
}


def _ai_root(tmp_path):
    root = tmp_path / ".ai"
    root.mkdir()
    return root


def _unanimous_round():
    return {
        "round_id": "r-ok",
        "subject": "merge branch",
        "voters": ["cc", "ag", "cx"],
        "votes": {
            "cc": {"vote": "agree", "reason": "ok"},
            "ag": {"vote": "agree", "reason": "ok"},
            "cx": {"vote": "agree", "reason": "ok"},
        },
        "status": "finalized",
    }


def _dissent_round():
    return {
        "round_id": "r-no",
        "subject": "merge branch",
        "voters": ["cc", "ag", "cx"],
        "votes": {
            "cc": {"vote": "agree", "reason": "ok"},
            "ag": {"vote": "disagree", "reason": "missing test"},
            "cx": {"vote": "agree", "reason": "ok"},
        },
        "status": "rejected",
    }


def test_disabled_config_never_calls_invoker(tmp_path):
    ai_root = _ai_root(tmp_path)
    called = {"n": 0}

    def invoker(_arbiter, _prompt):
        called["n"] += 1
        return "SHOULD NOT RUN"

    result = hub.run_arbiter_on_round(
        ai_root,
        _dissent_round(),
        config=DISABLED_CONFIG,
        invoker=invoker,
        now=NOW,
    )

    assert result == {"fired": False, "reason": "arbiter_disabled"}
    assert called["n"] == 0
    assert hub._arbiter_budget_count(ai_root, now=NOW) == 0


def test_enabled_unanimous_round_is_not_a_trigger_and_never_calls_invoker(tmp_path):
    ai_root = _ai_root(tmp_path)

    def fail_invoker(_arbiter, _prompt):
        raise AssertionError("invoker must not run for routine consensus")

    result = hub.run_arbiter_on_round(
        ai_root,
        _unanimous_round(),
        config=ENABLED_CONFIG,
        invoker=fail_invoker,
        now=NOW,
    )

    assert result["fired"] is False
    assert result["reason"] == "not_a_trigger"
    assert result["kind"] == "routine"
    assert hub._arbiter_budget_count(ai_root, now=NOW) == 0


def test_enabled_dissent_fires_persists_final_opinion_and_spends_budget(monkeypatch, tmp_path):
    ai_root = _ai_root(tmp_path)

    def fake_decide(_ai_root, context, _cfg, now=None):
        assert context["kind"] == "dissent"
        assert context["round_id"] == "r-no"
        return {
            "fire": True,
            "reason": "triggered",
            "kind": "dissent",
            "authority": "override",
            "arbiter": "cc.fable",
            "budget_count": 0,
        }

    monkeypatch.setattr(hub, "arbiter_decide", fake_decide)

    calls = []

    def invoker(arbiter, prompt):
        calls.append((arbiter, prompt))
        return "GO"

    result = hub.run_arbiter_on_round(
        ai_root,
        _dissent_round(),
        config=ENABLED_CONFIG,
        invoker=invoker,
        now=NOW,
    )

    assert result["fired"] is True
    opinion = result["final_opinion"]
    assert opinion["type"] == "FINAL_OPINION"
    assert opinion["arbiter"] == "cc.fable"
    assert opinion["verdict"] == "GO"
    assert opinion["authority"] == "override"
    assert len(calls) == 1
    assert calls[0][0] == "cc.fable"
    assert "PROPOSAL: merge branch" in calls[0][1]
    assert hub._arbiter_budget_count(ai_root, now=NOW) == 1

    lines = (ai_root / "final_opinions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    persisted = json.loads(lines[0])
    assert persisted["type"] == "FINAL_OPINION"
    assert persisted["verdict"] == "GO"


def test_enabled_dissent_invoker_failure_does_not_spend_budget(monkeypatch, tmp_path):
    ai_root = _ai_root(tmp_path)

    monkeypatch.setattr(
        hub,
        "arbiter_decide",
        lambda *_args, **_kwargs: {
            "fire": True,
            "reason": "triggered",
            "kind": "dissent",
            "authority": "override",
            "arbiter": "cc.fable",
            "budget_count": 0,
        },
    )

    def boom(_arbiter, _prompt):
        raise RuntimeError("model failed")

    result = hub.run_arbiter_on_round(
        ai_root,
        _dissent_round(),
        config=ENABLED_CONFIG,
        invoker=boom,
        now=NOW,
    )

    assert result["fired"] is False
    assert result["reason"] == "invoker_failed"
    assert result["detail"] == "model failed"
    assert hub._arbiter_budget_count(ai_root, now=NOW) == 0
    assert not (ai_root / "final_opinions.jsonl").exists()


def test_final_arbiter_config_merges_token_lb_arbiter_models_and_final_gate(monkeypatch):
    def fake_loads(_text):
        return {
            "token_load_balancing": {
                "enabled": False,
                "arbiter_models": ["cc.fable", "cc.deepthink"],
                "cost_map": {"high": 0.04},
            },
            "final_arbiter": {
                "enabled": True,
                "triggers": ["dissent"],
                "invocation_budget_5h": 3,
            },
        }

    monkeypatch.setattr(hub.json, "loads", fake_loads)

    cfg = hub._final_arbiter_config()

    assert cfg["enabled"] is True
    assert cfg["arbiter_models"] == ["cc.fable", "cc.deepthink"]
    assert cfg["triggers"] == ["dissent"]
    assert cfg["invocation_budget_5h"] == 3
    assert cfg["cost_map"] == {"high": 0.04}
