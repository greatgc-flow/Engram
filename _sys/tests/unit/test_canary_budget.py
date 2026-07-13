"""T44a contracts for the shared, fail-closed canary budget ledger."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "checks"))

import canary_budget


NOW = datetime(2026, 7, 14, tzinfo=timezone.utc)
VALID_QUOTA = {"source_tag": "cli_live", "remaining": 0.50}
ORCH_3P = {
    "hub_nodes": [{
        "node_id": "ag", "type": "peer", "profiles": {
            "opus": {"quota_families": ["3P"]},
            "gptoss": {"quota_families": ["3P"]},
        },
    }]
}


def _reserve(tmp_path, *, subject="cc.standard", now=NOW, cap=2, floor=0.25,
             quota=VALID_QUOTA, orchestration=None):
    return canary_budget.reserve_canary_invocation(
        tmp_path,
        kind="cli_canary",
        subject=subject,
        now=now,
        cap=cap,
        window_hours=5.0,
        reserve_floor=floor,
        quota_source_tag=quota["source_tag"],
        quota_remaining=quota["remaining"],
        orchestration=orchestration,
    )


def test_budget_reservation_is_atomic_and_precedes_invocation(tmp_path):
    reservation = _reserve(tmp_path)

    assert reservation["granted"] is True
    ledger = json.loads((tmp_path / "canary_budget.json").read_text(encoding="utf-8"))
    assert ledger["schema_version"] == 2
    assert ledger["entries"][0]["state"] == "reserved"
    assert ledger["entries"][0]["reservation_id"] == reservation["reservation_id"]


def test_budget_cap_and_reserve_floor_deny_without_invoking(tmp_path):
    first = _reserve(tmp_path, cap=1)
    capped = _reserve(tmp_path, cap=1)
    floor_denied = _reserve(tmp_path / "floor", quota={"source_tag": "cli_live", "remaining": 0.25})
    absent_denied = _reserve(tmp_path / "absent", quota={"source_tag": "absent", "remaining": None})

    assert first["granted"] is True
    assert capped == {"granted": False, "reason": "budget"}
    assert floor_denied == {"granted": False, "reason": "quota_below_reserve_floor"}
    assert absent_denied == {"granted": False, "reason": "quota_absent"}


def test_cli_canary_and_capability_canary_share_one_ledger(tmp_path):
    first = _reserve(tmp_path, cap=1)
    second = canary_budget.reserve_canary_invocation(
        tmp_path,
        kind="capability_core",
        subject="cx.deepthink",
        now=NOW,
        cap=1,
        window_hours=5.0,
        reserve_floor=0.25,
        quota_source_tag="app_server",
        quota_remaining=0.50,
    )

    assert first["granted"] is True
    assert second == {"granted": False, "reason": "budget"}


def test_canary_budget_lock_file_is_separate_from_ledger(tmp_path):
    from hub import _get_lock

    _reserve(tmp_path)

    # The ledger is a plain JSON file; the lock never sits on the JSON itself
    # (Windows WinError 32 forbids replacing a file held open by a reader).
    assert (tmp_path / "canary_budget.json").is_file()
    assert not (tmp_path / "canary_budget.json.lock").exists()
    # The lock lives in a SEPARATE .lock/ dir; filelock releases (and may unlink)
    # it after the reservation, so assert it exists while the lock is held.
    with _get_lock(tmp_path, "canary_budget"):
        assert (tmp_path / ".lock" / "canary_budget.lock").is_file()


def test_3p_canary_deducts_from_shared_pool(tmp_path):
    opus = _reserve(tmp_path, subject="ag.opus", orchestration=ORCH_3P)
    gptoss = _reserve(tmp_path, subject="ag.gptoss", orchestration=ORCH_3P)

    assert opus["granted"] is True
    assert gptoss["granted"] is True
    ledger = json.loads((tmp_path / "canary_budget.json").read_text(encoding="utf-8"))
    assert [entry["quota_pool"] for entry in ledger["entries"]] == ["3P", "3P"]


def test_reserve_floor_unset_is_fail_closed_deny_all(tmp_path):
    result = canary_budget.reserve_canary_invocation(
        tmp_path,
        kind="cli_canary",
        subject="cc.standard",
        now=NOW,
        cap=None,
        window_hours=None,
        reserve_floor=None,
        quota_source_tag="cli_live",
        quota_remaining=0.50,
    )

    assert result == {"granted": False, "reason": "budget_disabled"}


def test_expired_reservations_are_pruned(tmp_path):
    first = _reserve(tmp_path, cap=1, now=NOW)
    later = NOW + timedelta(hours=6)
    second = _reserve(tmp_path, cap=1, now=later)

    assert first["granted"] is True
    assert second["granted"] is True
    ledger = json.loads((tmp_path / "canary_budget.json").read_text(encoding="utf-8"))
    assert len(ledger["entries"]) == 1
    assert ledger["entries"][0]["reservation_id"] == second["reservation_id"]


def test_consume_and_release_finalize_state(tmp_path):
    consumed = _reserve(tmp_path)
    released = _reserve(tmp_path)

    consumed_entry = canary_budget.consume_canary_reservation(
        tmp_path, consumed["reservation_id"], actual_tokens=None, now=NOW
    )
    released_entry = canary_budget.release_canary_reservation(
        tmp_path, released["reservation_id"], now=NOW
    )

    assert consumed_entry["state"] == "consumed"
    assert consumed_entry["actual_tokens"] is None
    assert released_entry["state"] == "released"
