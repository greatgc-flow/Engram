"""Tests for arbiter live-wiring step 2 (condensed input + invocation orchestrator).

No real model/network call is made here (invoker is mocked). cx authored these
tests; the impl was applied by the terminal (LL-005).
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


NOW = datetime(2026, 7, 4, 14, 0, tzinfo=timezone.utc)


def _ai_root(tmp_path):
    root = tmp_path / ".ai"
    root.mkdir()
    return root


def _fire_decision():
    return {
        "fire": True,
        "reason": "triggered",
        "kind": "dissent",
        "authority": "override",
        "arbiter": "cc.fable",
        "budget_count": 0,
    }


def test_condense_arbiter_input_includes_sections_in_stable_order():
    text = hub.condense_arbiter_input({
        "proposal": "merge branch",
        "positions": {"cx": "GO", "ag": "NO-GO", "cc": "GO"},
        "blockers": ["missing test"],
        "evidence": ["_sys/core/hub.py:1", "_sys/core/snapshot.py:2"],
    })

    assert "PROPOSAL: merge branch" in text
    assert "POSITIONS:" in text
    assert text.index("  ag: NO-GO") < text.index("  cc: GO") < text.index("  cx: GO")
    assert text.index("PROPOSAL:") < text.index("POSITIONS:") < text.index("BLOCKERS:") < text.index("EVIDENCE:")
    assert "  - missing test" in text
    assert "  - _sys/core/hub.py:1" in text


def test_condense_arbiter_input_omits_missing_sections():
    text = hub.condense_arbiter_input({"positions": {"cx": "GO"}})

    assert "POSITIONS:" in text
    assert "PROPOSAL:" not in text
    assert "BLOCKERS:" not in text
    assert "EVIDENCE:" not in text


def test_condense_arbiter_input_caps_length_with_marker():
    text = hub.condense_arbiter_input({"proposal": "x" * 5000})

    assert len(text) <= 1200
    assert text.endswith("...<truncated>")


def test_condense_arbiter_input_never_raises_on_weird_types():
    class BadStr:
        def __str__(self):
            raise RuntimeError("bad str")

    text = hub.condense_arbiter_input({
        "proposal": BadStr(),
        "positions": {BadStr(): BadStr()},
        "blockers": BadStr(),
        "evidence": {BadStr()},
    })

    assert "<unprintable>" in text


def test_invoke_arbiter_calls_invoker_once_persists_record_and_increments_budget(tmp_path):
    ai_root = _ai_root(tmp_path)
    calls = []

    def invoker(arbiter_id, prompt):
        calls.append((arbiter_id, prompt))
        return "FINAL: GO"

    context = {
        "round_id": "r-1234",
        "proposal": "merge branch",
        "positions": {"cx": "GO", "ag": "NO-GO"},
        "blockers": ["ag dissent"],
        "evidence": ["ops.md:10"],
    }

    record = hub.invoke_arbiter(ai_root, _fire_decision(), context, {}, invoker, now=NOW)

    assert len(calls) == 1
    assert calls[0][0] == "cc.fable"
    assert "PROPOSAL: merge branch" in calls[0][1]
    assert record["type"] == "FINAL_OPINION"
    assert record["round_id"] == "r-1234"
    assert record["arbiter"] == "cc.fable"
    assert record["authority"] == "override"
    assert record["verdict"] == "FINAL: GO"
    assert hub._arbiter_budget_count(ai_root, now=NOW) == 1

    lines = (ai_root / "final_opinions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    persisted = json.loads(lines[0])
    assert persisted["type"] == "FINAL_OPINION"
    assert persisted["arbiter"] == "cc.fable"
    assert persisted["verdict"] == "FINAL: GO"
    assert persisted["authority"] == "override"


def test_invoke_arbiter_fire_false_noops(tmp_path):
    ai_root = _ai_root(tmp_path)

    def fail_invoker(*_args):
        raise AssertionError("invoker must not be called")

    result = hub.invoke_arbiter(
        ai_root,
        {"fire": False, "reason": "not_a_trigger", "kind": "routine", "authority": "advisory"},
        {"proposal": "routine"},
        {},
        fail_invoker,
        now=NOW,
    )

    assert result is None
    assert not (ai_root / "final_opinions.jsonl").exists()
    assert hub._arbiter_budget_count(ai_root, now=NOW) == 0


def test_invoke_arbiter_without_invoker_does_not_spend_budget(tmp_path):
    ai_root = _ai_root(tmp_path)

    result = hub.invoke_arbiter(
        ai_root,
        _fire_decision(),
        {"proposal": "merge branch"},
        {},
        None,
        now=NOW,
    )

    assert result["error"] == "no_invoker"
    assert result["arbiter"] == "cc.fable"
    assert not (ai_root / "final_opinions.jsonl").exists()
    assert hub._arbiter_budget_count(ai_root, now=NOW) == 0


def test_invoke_arbiter_invoker_failure_does_not_spend_budget_or_persist(tmp_path):
    ai_root = _ai_root(tmp_path)

    def boom(_arbiter_id, _prompt):
        raise RuntimeError("model failed")

    result = hub.invoke_arbiter(
        ai_root,
        _fire_decision(),
        {"proposal": "merge branch"},
        {},
        boom,
        now=NOW,
    )

    assert result["error"] == "invoker_failed"
    assert result["detail"] == "model failed"
    assert result["arbiter"] == "cc.fable"
    assert hub._arbiter_budget_count(ai_root, now=NOW) == 0
    assert not (ai_root / "final_opinions.jsonl").exists()
