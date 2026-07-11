"""Tests for operational_guard_matrix.py - D2 (INV-26) independent guard oracle.

The oracle must NOT call hub.py's own decision logic (that would be tautological
- see the module docstring) - these tests instead pin the oracle's behavior on
hand-picked cases covering each of _guard_action_dry_run's 7 rule branches, plus
structural properties of the generated matrix (no duplicate case_keys, full
branch coverage in the stratified sample).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import operational_guard_matrix as ogm

CFG = {
    "enabled": True,
    "mutating_hub_actions": ["propose-change"],
    "semi_governed_hub_actions": ["semi-action"],
    "read_only_hub_actions": ["status", "ask"],
    "recovery_hub_actions": ["peer-recover"],
    "decision_tier_floor": {"enabled": True, "mutating_hub_actions_min_tier": "effort"},
    "collab_rate_guard": {
        "enabled": True, "threshold": 10, "require_finalized_consensus": True,
        "exempt_actions": ["ask"],
    },
    "no_code_phases": ["discussion"],
    "allow_missing_phase": True,
    "missing_phase_policy": "allow_with_warning",
    "phase_action_matrix": {
        "default": {
            "mutating_hub_actions": "allow", "semi_governed_hub_actions": "allow",
            "read_only_hub_actions": "allow", "recovery_hub_actions": "allow",
            "unknown_actions": "requires_classification",
        },
        "no_code": {
            "mutating_hub_actions": "block", "semi_governed_hub_actions": "requires_classification",
            "read_only_hub_actions": "allow", "recovery_hub_actions": "allow",
            "unknown_actions": "requires_classification",
        },
    },
}
ORCH = {"hub_nodes": [{"node_id": "cc", "default_profile": "deepthink"}]}


def _case(**overrides) -> ogm.GuardCase:
    defaults = dict(
        action="status", origin="terminal", phase_key="default", force_tier0=False,
        collab_bucket="below_threshold", finalized_consensus=False, coordinator_bucket="healthy",
    )
    defaults.update(overrides)
    return ogm.GuardCase(**defaults)


def test_force_tier0_always_allows():
    d = ogm.expected_decision(_case(action="propose-change", force_tier0=True), CFG, ORCH)
    assert d.would_block is False


def test_disabled_guard_always_allows():
    cfg = dict(CFG, enabled=False)
    d = ogm.expected_decision(_case(action="propose-change"), cfg, ORCH)
    assert d.would_block is False


def test_terminal_mutating_action_is_blocked_pro19():
    d = ogm.expected_decision(_case(action="propose-change", origin="terminal"), CFG, ORCH)
    assert d.would_block is True
    assert d.matched_rule == "pro19_terminal_mutating"


def test_tier_floor_blocks_standard_tier_worker():
    d = ogm.expected_decision(
        _case(action="propose-change", origin="worker", worker_tier="standard"), CFG, ORCH,
    )
    assert d.would_block is True
    assert d.matched_rule == "tier_floor"


def test_tier_floor_allows_effort_tier_worker():
    d = ogm.expected_decision(
        _case(action="propose-change", origin="worker", worker_tier="effort"), CFG, ORCH,
    )
    assert d.would_block is False


def test_collab_rate_guard_blocks_without_consensus_at_threshold():
    d = ogm.expected_decision(
        _case(action="propose-change", origin="worker", worker_tier="deepthink",
              collab_bucket="at_or_above_threshold", finalized_consensus=False),
        CFG, ORCH,
    )
    assert d.would_block is True
    assert d.matched_rule == "collab_rate_guard"


def test_collab_rate_guard_allows_with_finalized_consensus():
    d = ogm.expected_decision(
        _case(action="propose-change", origin="worker", worker_tier="deepthink",
              collab_bucket="at_or_above_threshold", finalized_consensus=True),
        CFG, ORCH,
    )
    assert d.would_block is False


def test_collab_rate_guard_exempt_action_is_never_blocked():
    d = ogm.expected_decision(
        _case(action="ask", origin="terminal", collab_bucket="at_or_above_threshold", finalized_consensus=False),
        CFG, ORCH,
    )
    assert d.would_block is False


def test_semi_governed_blocks_at_threshold_without_consensus_when_healthy():
    d = ogm.expected_decision(
        _case(action="semi-action", origin="worker", worker_tier="deepthink",
              collab_bucket="at_or_above_threshold", finalized_consensus=False, coordinator_bucket="healthy"),
        CFG, ORCH,
    )
    assert d.would_block is True
    assert d.matched_rule == "semi_governed_consensus"


def test_semi_governed_allows_during_recovery_even_without_consensus():
    d = ogm.expected_decision(
        _case(action="semi-action", origin="worker", worker_tier="deepthink",
              collab_bucket="at_or_above_threshold", finalized_consensus=False, coordinator_bucket="recovery"),
        CFG, ORCH,
    )
    assert d.would_block is False


def test_no_code_phase_blocks_mutating_action():
    d = ogm.expected_decision(
        _case(action="propose-change", origin="worker", worker_tier="deepthink", phase_key="no_code"),
        CFG, ORCH,
    )
    assert d.would_block is True
    assert d.matched_rule == "phase_action_matrix"


def test_unknown_action_requires_classification_by_default():
    d = ogm.expected_decision(_case(action="__totally_unknown__", phase_key="default"), CFG, ORCH)
    assert d.would_block is True
    assert d.matched_rule == "phase_requires_classification"


def test_missing_phase_allows_with_warning_policy():
    d = ogm.expected_decision(_case(action="status", phase_key="unset"), CFG, ORCH)
    assert d.would_block is False


def test_missing_phase_blocks_when_policy_disallows():
    cfg = dict(CFG, allow_missing_phase=False, missing_phase_policy="block")
    d = ogm.expected_decision(_case(action="status", phase_key="unset"), cfg, ORCH)
    assert d.would_block is True
    assert d.matched_rule == "missing_phase_policy"


def test_enumerate_cases_has_no_duplicate_case_keys():
    cases = ogm.enumerate_cases(CFG, ORCH)
    keys = [c.case_key() for c in cases]
    assert len(keys) == len(set(keys))


def test_enumerate_cases_includes_worker_tier_variants_only_for_worker_origin():
    cases = ogm.enumerate_cases(CFG, ORCH)
    non_worker_tiers = {c.worker_tier for c in cases if c.origin != "worker"}
    assert non_worker_tiers == {"standard"}
    worker_tiers = {c.worker_tier for c in cases if c.origin == "worker"}
    assert worker_tiers == {"standard", "effort", "deepthink"}


def test_stratified_sample_covers_every_distinct_outcome_bucket():
    cases = ogm.enumerate_cases(CFG, ORCH)
    all_buckets = {
        (ogm.expected_decision(c, CFG, ORCH).action_group, ogm.expected_decision(c, CFG, ORCH).matched_rule)
        for c in cases
    }
    sample = ogm.stratified_sample_for_shuffle(cases, CFG, ORCH)
    sample_buckets = {
        (ogm.expected_decision(c, CFG, ORCH).action_group, ogm.expected_decision(c, CFG, ORCH).matched_rule)
        for c in sample
    }
    assert sample_buckets == all_buckets
    assert len(sample) < len(cases)


def test_stratified_sample_is_deterministic():
    cases = ogm.enumerate_cases(CFG, ORCH)
    s1 = [c.case_key() for c in ogm.stratified_sample_for_shuffle(cases, CFG, ORCH)]
    s2 = [c.case_key() for c in ogm.stratified_sample_for_shuffle(cases, CFG, ORCH)]
    assert s1 == s2
