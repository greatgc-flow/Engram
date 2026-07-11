"""Tests for check_operational_guard_matrix.py - D2 Gate 1/2 runner.

Runs the REAL cross-check (oracle vs hub.py's actual _guard_action_dry_run)
against a small subset of cases, not the full ~55k-case live matrix - that full
run is exercised directly via `python check_operational_guard_matrix.py`
(see the check's own module docstring), not on every default pytest run.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # _sys/
GUARD = ROOT / "checks" / "check_operational_guard_matrix.py"
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub  # noqa: E402
import operational_guard_matrix as ogm  # noqa: E402


def _mod():
    spec = importlib.util.spec_from_file_location("check_operational_guard_matrix_ut", GUARD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_gate1_zero_mismatches_on_live_config_small_subset():
    m = _mod()
    cfg = hub._load_protocol_cfg().get("operational_guard", {})
    orchestration = hub._load_orchestration()
    cases = ogm.enumerate_cases(cfg, orchestration)
    subset = ogm.stratified_sample_for_shuffle(cases, cfg, orchestration)  # ~1 per outcome bucket
    problems = m._mismatches(subset, cfg, orchestration)
    assert problems == []


def test_gate2_shuffle_is_order_independent_on_live_config_small_subset():
    m = _mod()
    cfg = hub._load_protocol_cfg().get("operational_guard", {})
    orchestration = hub._load_orchestration()
    cases = ogm.enumerate_cases(cfg, orchestration)
    problems = m.gate2(cases, cfg, orchestration, passes=5, seed=1)
    assert problems == []


def test_real_guard_harness_restores_hub_globals_after_use():
    cfg = hub._load_protocol_cfg().get("operational_guard", {})
    orchestration = hub._load_orchestration()
    originals = (
        hub._load_protocol_cfg, hub._current_phase,
        hub._has_finalized_consensus, hub._current_coordinator_health,
    )
    m = _mod()
    with m._RealGuardHarness(cfg, orchestration) as harness:
        harness.real_decision_for(ogm.GuardCase(
            action="status", origin="terminal", phase_key="default", force_tier0=False,
            collab_bucket="below_threshold", finalized_consensus=False, coordinator_bucket="healthy",
        ))
    assert (
        hub._load_protocol_cfg, hub._current_phase,
        hub._has_finalized_consensus, hub._current_coordinator_health,
    ) == originals
