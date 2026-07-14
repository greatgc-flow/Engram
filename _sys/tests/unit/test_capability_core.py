"""T44b deterministic, mock-only capability-canary contracts."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "checks"))

import check_capability_core as core


NOW = datetime(2026, 7, 14, tzinfo=timezone.utc)
FP = {
    "peer": "cc", "profile": "standard", "model_id": "mock-model",
    "reasoning_effort": "low", "adapter": "MockAdapter", "invoke_args": [],
    "profile_config_sha256": "a" * 64,
    "binary": {"exists": True, "sha256": "b" * 64},
}
BUDGET = {"cap": 10, "window_hours": 5.0, "reserve_floor": 0.25}
QUOTA = {"source_tag": "cli_live", "remaining": 0.50}
ORCH = {"hub_nodes": [{"node_id": "cc", "type": "peer", "profiles": {
    "standard": {"cost_tier": "low", "quota_families": ["C"]},
    "deepthink": {"cost_tier": "high", "quota_families": ["C"]},
}}]}


def _perfect_core_invoker(workspace, fixture):
    (workspace / "reasoning_answers.json").write_text(
        json.dumps(fixture["reasoning_answers"]), encoding="utf-8"
    )
    (workspace / "code" / "buggy_normalizer.py").write_text(
        fixture["expected_code"], encoding="utf-8"
    )
    agentic = workspace / "agentic"
    for rel, data in fixture["agentic_fixture"]["expected_bytes"].items():
        path = agentic / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (agentic / "failure_report.json").write_text(
        json.dumps({"target": "impossible_target_dir", "status": "failed"}), encoding="utf-8"
    )
    return {}


def _run_core(tmp_path, **kwargs):
    return core.run_capability_core(
        peer="cc", profile="standard", orch=ORCH, ai_root=tmp_path / ".ai",
        workspace=tmp_path / "workspace", invoker=_perfect_core_invoker,
        runtime_fingerprint=FP, budget=BUDGET, quota=QUOTA, now=NOW, **kwargs,
    )


def test_capability_core_scores_are_deterministic(tmp_path):
    one = _run_core(tmp_path / "one")
    two = _run_core(tmp_path / "two")

    assert one["axis_scores"] == two["axis_scores"] == {
        "reasoning_correctness": 100, "code_fidelity": 100, "agentic_reliability": 100,
    }
    assert one["shadow_only"] is True


def test_core_aggregate_is_minimum_of_three_runs():
    entries = [
        {"judgeable": True, "runtime_fingerprint": FP, "axis_scores": {"reasoning_correctness": 100, "code_fidelity": 90, "agentic_reliability": 80}},
        {"judgeable": True, "runtime_fingerprint": FP, "axis_scores": {"reasoning_correctness": 75, "code_fidelity": 95, "agentic_reliability": 85}},
        {"judgeable": True, "runtime_fingerprint": FP, "axis_scores": {"reasoning_correctness": 90, "code_fidelity": 70, "agentic_reliability": 100}},
    ]
    aggregate = core.aggregate_core_runs(entries, expected_runtime_fingerprint=FP)

    assert aggregate["valid"] is True
    assert aggregate["axis_scores"] == {"reasoning_correctness": 75, "code_fidelity": 70, "agentic_reliability": 80}


def test_long_context_rejects_unmeasured_or_insufficient_capacity(tmp_path):
    called = []
    invoker = lambda *_args: called.append(True) or {}
    for capacity in ({"source_tag": "orchestration", "window_tokens": 999999}, {"source_tag": "cli_live", "window_tokens": 7_999}):
        result = core.run_long_context(
            peer="cc", profile="standard", orch=ORCH, ai_root=tmp_path / "ai",
            workspace=tmp_path / "ctx", length_tokens=8_000, capacity=capacity,
            invoker=invoker, budget=BUDGET, quota=QUOTA, now=NOW,
        )
        assert result["status"] == "SKIP"
    assert called == []


def test_actual_tokens_stays_absent_without_machine_usage(tmp_path):
    result = _run_core(tmp_path)
    ledger = json.loads((tmp_path / ".ai" / "canary_budget.json").read_text(encoding="utf-8"))

    assert result["actual_tokens"] is None
    assert ledger["entries"][-1]["actual_tokens"] is None


def test_missing_tokenizer_uses_conservative_fallback_not_crash():
    assert core.estimate_tokens("abcd", tokenizer=None) == 2
    fixture = core.generate_long_context_fixture(8_000, seed=7, tokenizer=None)
    assert fixture["requested_fixture_tokens"] == 8_000
    assert fixture["tokenizer"] == "byte_fallback_2_bytes_per_token"
    assert core.estimate_tokens(fixture["prompt"], tokenizer=None) <= 8_000


def test_premium_measurement_requires_allowlist_and_explicit_execute(tmp_path):
    denied = core.run_capability_core(
        peer="cc", profile="deepthink", orch=ORCH, ai_root=tmp_path / "ai",
        workspace=tmp_path / "workspace", invoker=_perfect_core_invoker,
        runtime_fingerprint=FP, budget=BUDGET, quota=QUOTA, now=NOW,
    )
    assert denied == {"status": "SKIP", "reason": "premium_not_authorized", "shadow_only": True}


def test_capability_core_reserves_before_invoking_and_releases_on_failure(tmp_path):
    def failing_invoker(workspace, fixture):
        ledger = json.loads((tmp_path / "ai" / "canary_budget.json").read_text(encoding="utf-8"))
        assert ledger["entries"][-1]["state"] == "reserved"
        raise RuntimeError("mock launch failure")

    result = core.run_capability_core(
        peer="cc", profile="standard", orch=ORCH, ai_root=tmp_path / "ai",
        workspace=tmp_path / "workspace", invoker=failing_invoker,
        runtime_fingerprint=FP, budget=BUDGET, quota=QUOTA, now=NOW,
    )
    ledger = json.loads((tmp_path / "ai" / "canary_budget.json").read_text(encoding="utf-8"))
    assert result["status"] == "FAIL"
    assert ledger["entries"][-1]["state"] == "released"


def test_phase2_never_changes_live_route(tmp_path):
    route = {"selected": "cc.standard", "candidates": ["cc.standard", "cx.effort"]}
    before = json.dumps(route, sort_keys=True)
    result = _run_core(tmp_path)

    assert result["shadow_only"] is True
    assert json.dumps(route, sort_keys=True) == before


def test_score_reasoning_does_not_crash_on_non_dict_json(tmp_path):
    """T52 #8: a model that writes valid JSON that is not an object (a list) must
    not crash _score_reasoning; it is not judgeable and scores 0."""
    (tmp_path / "reasoning_answers.json").write_text('["58","36","41","47"]', encoding="utf-8")
    score, judgeable, matches = core._score_reasoning(tmp_path)
    assert score == 0
    assert judgeable is False
    assert all(v is False for v in matches.values())


def test_aggregate_rejects_run_missing_an_axis(tmp_path):
    """T52 #9: a run missing an axis (only reasoning_correctness) must NOT certify
    with a silently-zeroed axis — aggregate is valid=False."""
    entries = [
        {"judgeable": True, "runtime_fingerprint": FP, "axis_scores": {"reasoning_correctness": 100, "code_fidelity": 100, "agentic_reliability": 100}},
        {"judgeable": True, "runtime_fingerprint": FP, "axis_scores": {"reasoning_correctness": 100, "code_fidelity": 100, "agentic_reliability": 100}},
        {"judgeable": True, "runtime_fingerprint": FP, "axis_scores": {"reasoning_correctness": 100}},
    ]
    aggregate = core.aggregate_core_runs(entries, expected_runtime_fingerprint=FP)
    assert aggregate["valid"] is False
    assert aggregate["axis_scores"] == {"reasoning_correctness": None, "code_fidelity": None, "agentic_reliability": None}


def test_capability_core_records_resolve_to_certified_axes_end_to_end(tmp_path, monkeypatch):
    """T53 end-to-end (the integration the T52 audit found was never verified):
    run_capability_core -> per-axis empirical records -> resolve_capability_reality
    -> the overlay CERTIFIES each axis with its measured score."""
    import check_capability
    import check_peer_capability_canary
    records_path = tmp_path / "ledger.jsonl"
    _run_core(tmp_path / "run", records_path=records_path)
    records = [json.loads(l) for l in records_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    per_axis = {r["capability_id"] for r in records if ":" in r.get("capability_id", "")}
    assert per_axis == {
        "capability-core.v1:reasoning_correctness",
        "capability-core.v1:code_fidelity",
        "capability-core.v1:agentic_reliability",
    }
    # resolver must match the record fingerprint to the subject's resolved one
    monkeypatch.setattr(check_peer_capability_canary, "resolve_runtime_fingerprint", lambda o, p, pr: FP)
    reality = check_capability.resolve_capability_reality(
        ORCH, {"profiles": []}, {"schema_version": 1, "subjects": {}}, records, NOW,
    )
    axes = reality["subjects"]["cc.standard"]["axes"]
    for axis in ("reasoning_correctness", "code_fidelity", "agentic_reliability"):
        cap_id = f"capability-core.v1:{axis}"
        assert axes[cap_id]["evidence_band"] == "CERTIFIED", axes[cap_id]
        assert axes[cap_id]["effective_value"] == 100
