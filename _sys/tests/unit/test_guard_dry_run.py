"""Dry-run tests for hub operational guard decisions."""
import copy
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub


AI_ROOT = Path("dry-run-ai-root-does-not-exist")


@pytest.fixture
def tmp_path():
    """Avoid the suite autouse fixture touching tempfile in restricted sandboxes."""
    return AI_ROOT


def _patch_guard_inputs(monkeypatch, current, phase="active"):
    cfg = copy.deepcopy(hub._load_protocol_cfg())
    cfg.setdefault("collab_rate", {})["current"] = current
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: cfg)
    monkeypatch.setattr(hub, "_current_phase", lambda _ai_root: phase)
    monkeypatch.setattr(hub, "_has_finalized_consensus", lambda _ai_root: False)


def _dry_run_without_side_effects(monkeypatch, **kwargs):
    def _forbidden(*_args, **_kwargs):
        raise AssertionError("dry-run guard must not enforce or log side effects")

    monkeypatch.setattr(hub, "_log_p2p", _forbidden)
    monkeypatch.setattr(sys, "exit", _forbidden)
    return hub._guard_action_dry_run(AI_ROOT, **kwargs)


def test_guard_dry_run_reports_read_only_allow_without_exit_or_mutation(monkeypatch):
    _patch_guard_inputs(monkeypatch, 0)

    result = _dry_run_without_side_effects(
        monkeypatch,
        action="status",
        force_tier0=False,
        origin="terminal",
    )

    assert result["would_block"] is False
    assert result["code"] == 0
    assert result["matched_rule"] is None


def test_guard_dry_run_reports_terminal_mutation_block_without_exit_or_mutation(monkeypatch):
    _patch_guard_inputs(monkeypatch, 0)

    result = _dry_run_without_side_effects(
        monkeypatch,
        action="update-status",
        force_tier0=False,
        origin="terminal",
    )

    assert result["would_block"] is True
    assert result["code"] == 3
    assert result["matched_rule"] == "pro19_terminal_mutating"
    assert "terminal/router cannot execute" in result["reason"]


def test_guard_dry_run_reports_collab_rate_block_without_exit_or_mutation(monkeypatch):
    _patch_guard_inputs(monkeypatch, 10)

    result = _dry_run_without_side_effects(
        monkeypatch,
        action="archive-file",
        force_tier0=False,
        origin="cc.effort",
    )

    assert result["would_block"] is True
    assert result["code"] == 3
    assert result["matched_rule"] == "collab_rate_guard"
    assert "requires finalized consensus" in result["reason"]


def test_guard_dry_run_allows_collab_rate_exempt_action_without_exit_or_mutation(monkeypatch):
    _patch_guard_inputs(monkeypatch, 10)

    result = _dry_run_without_side_effects(
        monkeypatch,
        action="update-status",
        force_tier0=False,
        origin="cc.effort",
    )

    assert result["would_block"] is False
    assert result["code"] == 0
    assert result["matched_rule"] is None


def test_guard_dry_run_soak_matrix_zero_mismatches(monkeypatch):
    cases = [
        {
            "name": "read_only_allowed",
            "action": "status",
            "origin": "terminal",
            "phase": "active",
            "collab_rate": 10,
            "expected_block": False,
            "expected_rule": None,
        },
        {
            "name": "terminal_mutating_blocked",
            "action": "update-status",
            "origin": "terminal",
            "phase": "active",
            "collab_rate": 0,
            "expected_block": True,
            "expected_rule": "pro19_terminal_mutating",
        },
        {
            "name": "collab_rate_mutating_blocked",
            "action": "archive-file",
            "origin": "cc.effort",
            "phase": "active",
            "collab_rate": 10,
            "expected_block": True,
            "expected_rule": "collab_rate_guard",
        },
        {
            "name": "no_code_phase_mutating_blocked",
            "action": "archive-file",
            "origin": "cc.effort",
            "phase": "discussion",
            "collab_rate": 0,
            "expected_block": True,
            "expected_rule": "phase_action_matrix",
        },
        {
            "name": "explicit_exempt_allowed",
            "action": "update-status",
            "origin": "cc.effort",
            "phase": "active",
            "collab_rate": 10,
            "expected_block": False,
            "expected_rule": None,
        },
    ]

    rng = random.Random(20260708)
    mismatches = []
    for _ in range(20):
        ordered = cases[:]
        rng.shuffle(ordered)
        for case in ordered:
            _patch_guard_inputs(monkeypatch, case["collab_rate"], phase=case["phase"])
            result = _dry_run_without_side_effects(
                monkeypatch,
                action=case["action"],
                force_tier0=False,
                origin=case["origin"],
            )
            if (
                result["would_block"] != case["expected_block"]
                or result["matched_rule"] != case["expected_rule"]
            ):
                mismatches.append((case["name"], result))

    assert mismatches == []
