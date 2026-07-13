"""T45 shadow capability-gate contracts: telemetry only, never live routing."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "core"))
import snapshot

BASE_CONFIG = {"effective_headroom_floor": 0.1, "terminal_hard_exclude": False, "cost_map": {"low": 0.0}}
VECTOR = {"schema_version": 1, "complexity": "medium", "requirements": {
    "reasoning_correctness": {"required": True}, "code_fidelity": {"required": False},
    "agentic_reliability": {"required": False}, "long_context_quality": {"required": False, "minimum_length_tokens": 8000},
}}

def _row(peer):
    return {"peer": peer, "profile": f"{peer}.effort", "state": "eligible", "headroom": 0.8,
            "cost_tier": "low", "context": {"source_tag": "cli_live", "window_tokens": 200000}}

def _reality(*, cc="measurable", ag="blocked_pending_pty_harness", certified=()):
    subjects = {}
    for peer, status in (("cc", cc), ("ag", ag)):
        subject = f"{peer}.effort"
        subjects[subject] = {"measurement_feasibility": {"performance": {"status": status}}, "axes": {
            "reasoning_correctness": {"source_tag": "empirical_probe" if subject in certified else "absent", "evidence_band": "CERTIFIED" if subject in certified else "ABSENT"},
        }}
    return {"schema_version": 1, "subjects": subjects}

def _decision(monkeypatch, cfg):
    rows = [_row("cc"), _row("ag")]
    monkeypatch.setattr(snapshot, "_derive_headroom_rows", lambda _snapshot: copy.deepcopy(rows))
    return snapshot.select_load_balanced_peer({"profiles": rows}, cfg, ask_id="t45")

def _event(result):
    return next(event for event in result["telemetry_events"] if event["event"] == "capability_route_shadow")

def test_capability_shadow_event_never_changes_live_route(monkeypatch):
    plain = _decision(monkeypatch, BASE_CONFIG)
    shadow = _decision(monkeypatch, {**BASE_CONFIG, "task_requirement_vector": VECTOR, "capability_reality": _reality()})
    keys = ("selected_peer", "candidates", "weights", "probabilities", "seed", "draw", "representative_profiles")
    assert {key: plain[key] for key in keys} == {key: shadow[key] for key in keys}
    assert _event(shadow)["driving"] is False

def test_declaration_only_profile_has_neutral_bulk_fitness(monkeypatch):
    result = _decision(monkeypatch, {**BASE_CONFIG, "task_requirement_vector": VECTOR, "capability_reality": _reality()})
    assert set(_event(result)["bulk_fitness"].values()) == {1.0}

def test_feasibility_blocked_ag_profile_is_not_stranded(monkeypatch):
    event = _event(_decision(monkeypatch, {**BASE_CONFIG, "task_requirement_vector": VECTOR, "capability_reality": _reality()}))
    assert "ag.effort" in event["would_candidates"]
    assert all(item["profile"] != "ag.effort" for item in event["removed"])

def test_measurable_unmeasured_axis_is_shadow_hard_removed(monkeypatch):
    event = _event(_decision(monkeypatch, {**BASE_CONFIG, "task_requirement_vector": VECTOR, "capability_reality": _reality()}))
    assert {item["profile"] for item in event["removed"]} == {"cc.effort"}
    assert event["removed"][0]["reason"] == "missing_score_measurable"

def test_empty_shadow_candidate_set_is_fail_loud(monkeypatch):
    event = _event(_decision(monkeypatch, {**BASE_CONFIG, "task_requirement_vector": VECTOR, "capability_reality": _reality(cc="measurable", ag="measurable")}))
    assert event["empty_result"] is True
    assert event["missing_score_policy"] == "fail_loud"

def test_explicit_target_is_warn_then_allow(monkeypatch):
    event = _event(_decision(monkeypatch, {**BASE_CONFIG, "explicit_target": True, "task_requirement_vector": VECTOR, "capability_reality": _reality(cc="measurable", ag="measurable")}))
    assert event["explicit_target_override"] is True
    assert event["missing_score_policy"] == "warn_then_allow"
    assert set(event["would_candidates"]) == {"cc.effort", "ag.effort"}

def test_legacy_external_composite_never_enters_shadow_logic(monkeypatch):
    reality = _reality()
    reality["subjects"]["cc.effort"]["axes"]["legacy_external_composite"] = {"effective_value": 99, "source_tag": "declared", "evidence_band": "DECLARED"}
    event = _event(_decision(monkeypatch, {**BASE_CONFIG, "task_requirement_vector": VECTOR, "capability_reality": reality}))
    assert "legacy_external_composite" not in json.dumps(event)
    assert event["bulk_fitness"]["cc.effort"] == 1.0
