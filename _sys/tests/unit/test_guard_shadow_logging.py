"""Tests for D2 (INV-26) Gate 3: _guard_action's shadow-logging wiring.

_guard_action is the REAL enforcing wrapper (unlike _guard_action_dry_run, which
is side-effect-free) - these tests verify it logs an operational_guard_shadow
event via _record_routing_metric on every real outcome path (allow, block,
force-tier0 bypass), without changing its actual enforcement behavior.
"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub

AI_ROOT = Path("shadow-logging-ai-root-does-not-exist")


def _patch_guard_inputs(monkeypatch, current=0, phase="active", finalized_consensus=False, coordinator_health="GREEN"):
    cfg = copy.deepcopy(hub._load_protocol_cfg())
    cfg.setdefault("collab_rate", {})["current"] = current
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: cfg)
    monkeypatch.setattr(hub, "_current_phase", lambda _ai_root: phase)
    monkeypatch.setattr(hub, "_has_finalized_consensus", lambda _ai_root: finalized_consensus)
    monkeypatch.setattr(hub, "_current_coordinator_health", lambda _ai_root: coordinator_health)


def _capture_shadow_events(monkeypatch):
    events = []

    def _fake_record(ai_root, event, **fields):
        events.append({"event": event, **fields})

    monkeypatch.setattr(hub, "_record_routing_metric", _fake_record)
    return events


def test_guard_action_logs_shadow_event_on_allow(monkeypatch):
    _patch_guard_inputs(monkeypatch)
    monkeypatch.setattr(hub, "_log_p2p", lambda *a, **kw: None)
    events = _capture_shadow_events(monkeypatch)

    hub._guard_action(AI_ROOT, "status", force_tier0=False, origin="terminal")

    shadow = [e for e in events if e["event"] == "operational_guard_shadow"]
    assert len(shadow) == 1
    assert shadow[0]["real_outcome"] == "allow"
    assert shadow[0]["dry_run_would_block"] is False
    assert shadow[0]["shadow_match"] is True


def test_guard_action_logs_shadow_event_before_sys_exit_on_block(monkeypatch):
    _patch_guard_inputs(monkeypatch)
    monkeypatch.setattr(hub, "_log_p2p", lambda *a, **kw: None)
    events = _capture_shadow_events(monkeypatch)

    with pytest.raises(SystemExit):
        hub._guard_action(AI_ROOT, "propose-change", force_tier0=False, origin="terminal")

    shadow = [e for e in events if e["event"] == "operational_guard_shadow"]
    assert len(shadow) == 1
    assert shadow[0]["real_outcome"] == "block"
    assert shadow[0]["dry_run_would_block"] is True
    assert shadow[0]["shadow_match"] is True


def test_guard_action_logs_force_tier0_bypass(monkeypatch):
    _patch_guard_inputs(monkeypatch)
    monkeypatch.setattr(hub, "_log_p2p", lambda *a, **kw: None)
    events = _capture_shadow_events(monkeypatch)

    hub._guard_action(AI_ROOT, "propose-change", force_tier0=True, origin="terminal")

    shadow = [e for e in events if e["event"] == "operational_guard_shadow"]
    assert len(shadow) == 1
    assert shadow[0]["real_outcome"] == "force_tier0_bypass"


def test_guard_action_shadow_logging_never_breaks_enforcement_on_logger_failure(monkeypatch):
    """A broken telemetry sink must not silently change enforcement (allow a
    blocked action through, or block an allowed one) - _record_guard_shadow
    catches its own exceptions (hub.py:_record_guard_shadow)."""
    _patch_guard_inputs(monkeypatch)
    monkeypatch.setattr(hub, "_log_p2p", lambda *a, **kw: None)

    def _broken_record(*a, **kw):
        raise RuntimeError("telemetry sink down")

    monkeypatch.setattr(hub, "_record_routing_metric", _broken_record)

    with pytest.raises(SystemExit):
        hub._guard_action(AI_ROOT, "propose-change", force_tier0=False, origin="terminal")


def test_guard_shadow_case_key_matches_matrix_oracle_format(monkeypatch):
    import operational_guard_matrix as ogm

    _patch_guard_inputs(monkeypatch, current=10, finalized_consensus=True, coordinator_health="RED")
    events = _capture_shadow_events(monkeypatch)
    monkeypatch.setattr(hub, "_log_p2p", lambda *a, **kw: None)

    hub._guard_action(AI_ROOT, "status", force_tier0=False, origin="terminal")

    shadow = [e for e in events if e["event"] == "operational_guard_shadow"][0]
    case = ogm.GuardCase(
        action="status", origin="terminal", phase_key=shadow["phase_key"], force_tier0=False,
        collab_bucket=shadow["collab_bucket"], finalized_consensus=shadow["finalized_consensus"],
        coordinator_bucket=shadow["coordinator_bucket"],
    )
    assert shadow["case_key"] == case.case_key()
