from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
CHECKS_DIR = SYS_DIR / "checks"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))
if str(CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKS_DIR))

import check_peer_capability_canary as cpc  # noqa: E402
import hub  # noqa: E402


NOW = datetime(2026, 7, 13, 10, 0, 0)


def _orch(*nodes: dict) -> dict:
    return {"hub_nodes": list(nodes)}


def _peer(node_id: str, *, default_profile: str = "effort", enabled: bool = True) -> dict:
    return {
        "node_id": node_id,
        "type": "peer",
        "enabled": enabled,
        "default_profile": default_profile,
        "profiles": {
            "standard": {"routing_state": "eligible"},
            "effort": {"routing_state": "eligible"},
            "deepthink": {"routing_state": "eligible"},
        },
    }


def _health(status: str = "GREEN", *, quarantined: bool = False, gate_open: bool = True) -> tuple[str, dict]:
    return (
        status,
        {
            "availability": {
                "quarantined": quarantined,
                "gate_open": gate_open,
                "profiles": {
                    "standard": {"gate_open": True},
                    "effort": {"gate_open": True},
                    "deepthink": {"gate_open": True},
                },
            }
        },
    )


def _patch_common(
    monkeypatch,
    tmp_path: Path,
    *,
    state: dict,
    orch: dict,
    health_by_peer: dict[str, tuple[str, dict]],
    score_entries: list[dict] | None = None,
    valid_records: set[tuple[str, str]] | None = None,
) -> None:
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(
        hub,
        "_load_protocol_cfg",
        lambda: {
            "leader_election": {
                "human_interface_peer": "cc",
                "human_interface_peer_freshness_minutes": 30,
            },
            "decision_tier_floor": {
                "terminal_file_write_min_tier": "effort",
            },
        },
    )
    monkeypatch.setattr(hub, "_load_orchestration", lambda: orch)
    monkeypatch.setattr(
        hub,
        "_peer_effective_health",
        lambda peer, stale_minutes=None, ai_root=None, recover=False: health_by_peer.get(peer, _health("RED")),
    )
    monkeypatch.setattr(cpc, "load_score_entries", lambda: list(score_entries or []))

    valid_records = valid_records or set()

    def _valid(entry, now=None, expected_runtime_fingerprint=None):
        return (entry.get("peer"), entry.get("profile")) in valid_records

    monkeypatch.setattr(cpc, "is_capability_record_valid", _valid)


def test_eligible_cc_stays_configured_default(monkeypatch, tmp_path):
    _patch_common(
        monkeypatch,
        tmp_path,
        state={
            "human_interface_peer": "cc",
            "human_interface_peer_assigned_at": "2026-07-13T09:50:00",
        },
        orch=_orch(_peer("cc", default_profile="deepthink"), _peer("cx", default_profile="effort")),
        health_by_peer={"cc": _health(), "cx": _health()},
    )

    selection = hub._select_human_interface_peer(tmp_path, now=NOW)

    assert selection["peer"] == "cc"
    assert selection["profile"] == "deepthink"
    assert selection["reason"] == "configured_default"


def test_non_cc_selected_when_cc_quarantined(monkeypatch, tmp_path):
    _patch_common(
        monkeypatch,
        tmp_path,
        state={
            "human_interface_peer": "cc",
            "human_interface_peer_assigned_at": "2026-07-13T09:50:00",
        },
        orch=_orch(_peer("cc", default_profile="deepthink"), _peer("cx", default_profile="effort")),
        health_by_peer={"cc": _health("RED", quarantined=True), "cx": _health()},
    )

    selection = hub._select_human_interface_peer(tmp_path, now=NOW)

    assert selection["peer"] == "cx"
    assert selection["profile"] == "effort"
    assert selection["reason"] == "fallback_highest_eligible_tier"


def test_capability_record_present_requires_valid_unexpired_pass(monkeypatch, tmp_path):
    invalid_record = {
        "peer": "cx",
        "profile": "effort",
        "capability_id": "direct_file_write.safe_utf8.v1",
        "passed": False,
    }
    _patch_common(
        monkeypatch,
        tmp_path,
        state={
            "human_interface_peer": "cc",
            "human_interface_peer_assigned_at": "2026-07-13T09:50:00",
        },
        orch=_orch(_peer("cc", default_profile="deepthink"), _peer("cx", default_profile="effort")),
        health_by_peer={"cc": _health("RED", quarantined=True), "cx": _health()},
        score_entries=[invalid_record],
        valid_records=set(),
    )

    selection = hub._select_human_interface_peer(tmp_path, now=NOW)
    cx_eval = next(item for item in selection["evaluated"] if item["peer"] == "cx")

    assert selection["peer"] is None
    assert cx_eval["eligible"] is False
    assert cx_eval["reason"] == "capability_invalid"


def test_expired_terminal_freshness_rejects(monkeypatch, tmp_path):
    _patch_common(
        monkeypatch,
        tmp_path,
        state={
            "human_interface_peer": "cc",
            "human_interface_peer_assigned_at": "2026-07-13T09:00:00",
        },
        orch=_orch(_peer("cc", default_profile="deepthink")),
        health_by_peer={"cc": _health()},
    )

    result = hub._human_interface_peer_eligibility(tmp_path, "cc", "deepthink", now=NOW)

    assert result["eligible"] is False
    assert result["reason"] == "terminal_assignment_stale"


def test_expired_real_assignment_time_field_rejects(monkeypatch, tmp_path):
    """action_terminal_handoff() actually writes human_interface_assignment_time
    (not human_interface_peer_assigned_at, which no production code ever writes).
    Before this fix, _human_interface_assignment_fresh() never checked this
    field, so `candidates` was always empty and stale assignments were always
    reported fresh -- making action_terminal_duty_sweep() a permanent no-op
    regardless of true age."""
    _patch_common(
        monkeypatch,
        tmp_path,
        state={
            "human_interface_peer": "cc",
            "human_interface_assignment_time": "2026-07-13T09:00:00",
        },
        orch=_orch(_peer("cc", default_profile="deepthink")),
        health_by_peer={"cc": _health()},
    )

    result = hub._human_interface_peer_eligibility(tmp_path, "cc", "deepthink", now=NOW)

    assert result["eligible"] is False
    assert result["reason"] == "terminal_assignment_stale"


def test_no_eligible_peer_returns_no_terminal(monkeypatch, tmp_path):
    _patch_common(
        monkeypatch,
        tmp_path,
        state={},
        orch=_orch(_peer("cc", default_profile="standard"), _peer("cx", default_profile="standard")),
        health_by_peer={"cc": _health("RED"), "cx": _health("GREEN")},
    )

    selection = hub._select_human_interface_peer(tmp_path, now=NOW)

    assert selection["peer"] is None
    assert selection["profile"] is None
    assert selection["eligible"] is False
    assert selection["reason"] == "no_eligible_human_interface_peer"
