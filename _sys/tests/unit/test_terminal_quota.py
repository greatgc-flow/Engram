"""Terminal-quota-exhaustion resilience (mega-mece-audit-2026-07-16, 5-way
debate, 4 rounds to unanimous): atomic terminal-handoff + the freshness-only
watchdog sweep. All state I/O MUST go through tmp_path -- these actions write
human_interface_peer/leadership, and running them against the real .ai/
directory would corrupt the live system's terminal assignment."""
from __future__ import annotations

import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub  # noqa: E402


def test_terminal_handoff_atomically_updates_all_identity_fields(tmp_path):
    hub._write_json(tmp_path / "state.json", {"human_interface_peer": "cc"})

    hub.action_terminal_handoff(tmp_path, "cc", "ag", "test")

    state = hub._read_json(tmp_path / "state.json")
    assert state.get("human_interface_peer") == "ag"
    assert state.get("active_console_peer") == "ag"
    assert state.get("leader") == "ag"
    assert state.get("active_coordinator") == "ag"
    assert state.get("leadership", {}).get("peer") == "ag"
    assert state.get("leadership", {}).get("status") == "ACTIVE"


def test_select_human_interface_peer_prefers_recorded_handoff_over_default(monkeypatch, tmp_path):
    """Point 5 of the converged design: a real handoff away from the
    configured default ('cc') must stick, not silently snap back."""
    hub._write_json(tmp_path / "state.json", {"human_interface_peer": "ag"})
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {
        "leader_election": {"human_interface_peer": "cc"},
    })
    monkeypatch.setattr(hub, "_human_interface_peer_eligibility", lambda *a, **k: {
        "peer": a[1] if len(a) > 1 else k.get("peer"),
        "profile": None,
        "eligible": True,
        "reason": "eligible",
        "details": {},
    })
    monkeypatch.setattr(hub, "_load_orchestration", lambda: {"hub_nodes": []})

    selection = hub._select_human_interface_peer(tmp_path)

    assert selection["peer"] == "ag"
    assert selection["reason"] == "active_recorded_terminal"


def test_terminal_duty_sweep_replaces_a_stale_terminal(monkeypatch, tmp_path):
    hub._write_json(tmp_path / "state.json", {
        "human_interface_peer": "ag",
        "human_interface_peer_assigned_at": "2000-01-01T00:00:00",
    })
    monkeypatch.setattr(hub, "_human_interface_assignment_fresh", lambda *a, **k: (False, "terminal_assignment_stale"))
    calls = []
    monkeypatch.setattr(hub, "_select_human_interface_peer", lambda *a, **k: {"peer": "cx", "profile": "effort"})
    monkeypatch.setattr(hub, "action_terminal_handoff", lambda ai_root, cur, nxt, reason="": calls.append((cur, nxt, reason)))

    hub.action_terminal_duty_sweep(tmp_path)

    assert calls == [("ag", "cx", "sweep_stale_terminal")]


def test_terminal_duty_sweep_does_nothing_when_fresh(monkeypatch, tmp_path):
    hub._write_json(tmp_path / "state.json", {"human_interface_peer": "ag"})
    monkeypatch.setattr(hub, "_human_interface_assignment_fresh", lambda *a, **k: (True, "fresh"))
    calls = []
    monkeypatch.setattr(hub, "action_terminal_handoff", lambda *a, **k: calls.append(a))

    hub.action_terminal_duty_sweep(tmp_path)

    assert calls == []
