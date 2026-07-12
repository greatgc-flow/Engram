from __future__ import annotations

import json
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub  # noqa: E402


def _patch_leader_claim_env(monkeypatch, tmp_path, state: dict, *, threshold: int = 3):
    directives_path = tmp_path / "runtime-directives.jsonl"
    written_states: list[dict] = []

    monkeypatch.setattr(
        hub,
        "_load_protocol_cfg",
        lambda: {
            "leader_election": {
                "challenge_window_minutes": 1,
                "yield_failure_threshold": threshold,
            }
        },
    )
    monkeypatch.setattr(hub, "_runtime_directives_path", lambda ai_root=None: directives_path)
    monkeypatch.setattr(hub, "_get_lock", lambda ai_root, name: nullcontext())
    monkeypatch.setattr(hub, "_read_json", lambda path: state)
    monkeypatch.setattr(hub, "_write_state", lambda ai_root, new_state: written_states.append(dict(new_state)))
    monkeypatch.setattr(hub, "_append_handoff_item", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_log_p2p", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_now", lambda: "2026-07-12T00:00:00")

    return directives_path, written_states


def _read_directives(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_ap20_violation_writes_broadcast_runtime_directive(monkeypatch, tmp_path):
    state = {
        "room_id": "room-test",
        "coordinator_history": [
            {"peer": "ag"},
            {"peer": "ag"},
            {"peer": "ag"},
        ],
    }
    directives_path, _ = _patch_leader_claim_env(monkeypatch, tmp_path, state, threshold=3)

    with pytest.raises(SystemExit) as exc:
        hub.action_leader_claim(tmp_path, "ag", reason="test")

    assert exc.value.code == 1

    entries = _read_directives(directives_path)
    assert len(entries) == 1

    entry = entries[0]
    assert entry["trigger_reason"] == "ap20_coordinator_monopoly"
    assert entry["source_peer"] == "ag"
    assert entry["clear_condition"] == "other_peer_leads_or_expiry"
    assert entry["trigger_count"] == 1
    assert entry["status"] == "active"
    assert "target_peers" not in entry
    assert "consecutive_history=['ag', 'ag', 'ag']" == entry["trigger_detail"]
    assert "must not attempt another coordinator claim" in entry["rule"]


def test_ap20_repeat_violation_bumps_existing_directive_not_duplicate(monkeypatch, tmp_path):
    state = {
        "room_id": "room-test",
        "coordinator_history": [
            {"peer": "ag"},
            {"peer": "ag"},
            {"peer": "ag"},
        ],
    }
    directives_path, _ = _patch_leader_claim_env(monkeypatch, tmp_path, state, threshold=3)

    with pytest.raises(SystemExit):
        hub.action_leader_claim(tmp_path, "ag", reason="first")

    with pytest.raises(SystemExit):
        hub.action_leader_claim(tmp_path, "ag", reason="second")

    entries = _read_directives(directives_path)
    assert len(entries) == 1
    assert entries[0]["trigger_reason"] == "ap20_coordinator_monopoly"
    assert entries[0]["source_peer"] == "ag"
    assert entries[0]["trigger_count"] == 2
    assert "last_triggered_at" in entries[0]


def test_ap20_threshold_comes_from_protocol_not_hardcoded_three(monkeypatch, tmp_path):
    state = {
        "room_id": "room-test",
        "coordinator_history": [
            {"peer": "cx"},
            {"peer": "cx"},
        ],
    }
    directives_path, _ = _patch_leader_claim_env(monkeypatch, tmp_path, state, threshold=2)

    with pytest.raises(SystemExit) as exc:
        hub.action_leader_claim(tmp_path, "cx", reason="threshold-two")

    assert exc.value.code == 1

    entries = _read_directives(directives_path)
    assert len(entries) == 1
    assert entries[0]["source_peer"] == "cx"
    assert entries[0]["trigger_detail"] == "consecutive_history=['cx', 'cx']"
    assert "2 consecutive terms" in entries[0]["rule"]


@pytest.mark.parametrize(
    "history",
    [
        [{"peer": "ag"}, {"peer": "ag"}],
        [{"peer": "ag"}, {"peer": "cc"}, {"peer": "ag"}],
    ],
)
def test_ap20_non_violation_does_not_exit_or_write_directive(monkeypatch, tmp_path, history):
    state = {
        "room_id": "room-test",
        "coordinator_history": list(history),
    }
    directives_path, written_states = _patch_leader_claim_env(monkeypatch, tmp_path, state, threshold=3)

    hub.action_leader_claim(tmp_path, "ag", reason="allowed")

    assert _read_directives(directives_path) == []
    assert written_states
    assert written_states[-1]["active_coordinator"] == "ag"
    assert written_states[-1]["leader"] == "ag"


def test_ap20_reject_behavior_remains_sys_exit_1(monkeypatch, tmp_path):
    state = {
        "room_id": "room-test",
        "coordinator_history": [
            {"peer": "cc"},
            {"peer": "cc"},
            {"peer": "cc"},
        ],
    }
    directives_path, written_states = _patch_leader_claim_env(monkeypatch, tmp_path, state, threshold=3)

    with pytest.raises(SystemExit) as exc:
        hub.action_leader_claim(tmp_path, "cc", reason="still-rejected")

    assert exc.value.code == 1
    assert _read_directives(directives_path)
    assert written_states == []
