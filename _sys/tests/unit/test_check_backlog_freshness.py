"""F1: read-only backlog freshness signals (advisory, never mutates)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
if str(SYS_DIR / "checks") not in sys.path:
    sys.path.insert(0, str(SYS_DIR / "checks"))

import check_backlog as cb

NOW = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)


def _codes(data):
    warnings, _ = cb.freshness_report(data, now=NOW)
    return [w["code"] for w in warnings]


def test_verification_overdue_only_for_open_items_past_threshold():
    data = {"items": [
        {"id": "A", "status": "proposed", "last_verified_at": "2026-05-01T00:00:00+00:00", "next_action": "x"},  # 75d > 30d
        {"id": "B", "status": "deferred", "last_verified_at": "2026-06-01T00:00:00+00:00", "next_action": "x"},   # 44d < 180d -> ok
        {"id": "C", "status": "done", "last_verified_at": "2020-01-01T00:00:00+00:00", "evidence_commit": ["x"]},  # done -> not checked
    ]}
    codes = _codes(data)
    assert "verification_overdue" in codes
    assert sum(1 for c in codes if c == "verification_overdue") == 1  # only A


def test_future_or_missing_timestamp_is_unverifiable_not_overdue():
    data = {"items": [
        {"id": "A", "status": "active", "last_verified_at": "2099-01-01T00:00:00+00:00", "next_action": "x"},
        {"id": "B", "status": "active", "next_action": "x"},  # missing
    ]}
    codes = _codes(data)
    assert codes.count("verification_unverifiable") == 2
    assert "verification_overdue" not in codes


def test_dangling_only_for_repo_root_paths_partial_paths_unverifiable(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, "PORTABLE_ROOT", tmp_path)
    (tmp_path / "_sys" / "core").mkdir(parents=True)
    (tmp_path / "_sys" / "core" / "real.py").write_text("x", encoding="utf-8")
    data = {"items": [{"id": "A", "status": "done", "evidence_commit": ["x"], "source_refs": [
        "_sys/core/real.py",              # exists -> ok
        "_sys/core/gone.py",              # repo path, missing -> dangling
        "ops/partial.md",                 # partial path (no repo root) -> unverifiable
        "just-a-filename.md",             # bare -> unverifiable
        "https://example.com/x",          # url -> unverifiable
    ]}]}
    warnings, summary = cb.freshness_report(data, now=NOW)
    codes = [w["code"] for w in warnings]
    assert codes.count("dangling_source_ref") == 1
    assert summary["unverifiable_source_refs"] == 3


def test_supersession_target_still_open_and_blocker_hygiene():
    data = {"items": [
        {"id": "A", "status": "proposed", "supersedes": ["B"], "next_action": "x"},
        {"id": "B", "status": "proposed", "next_action": "x"},   # still open -> flagged
        {"id": "C", "status": "blocked", "blocker": "Z9", "next_action": "x"},   # Z9 unknown -> broken
        {"id": "D", "status": "blocked", "blocker": "E", "next_action": "x"},    # E done -> stale
        {"id": "E", "status": "done", "evidence_commit": ["x"]},
        {"id": "F", "status": "blocked", "blocker": "needs a long prose reason here", "next_action": "x"},  # prose -> skipped
    ]}
    codes = _codes(data)
    assert "supersession_target_still_open" in codes
    assert "broken_blocker" in codes
    assert "stale_blocker" in codes
    # a prose blocker is NOT flagged as broken (id-like only)
    assert not any(w for w in cb.freshness_report(data, now=NOW)[0]
                   if w["id"] == "F" and w["code"] == "broken_blocker")


def test_empty_next_action_only_on_proposed_active():
    data = {"items": [
        {"id": "A", "status": "proposed", "next_action": "  "},   # empty -> flagged
        {"id": "B", "status": "done", "evidence_commit": ["x"], "next_action": ""},  # done -> not flagged
    ]}
    codes = _codes(data)
    assert codes.count("empty_next_action") == 1


def test_circular_blocker_chain_detected():
    data = {"items": [
        {"id": "A", "status": "blocked", "blocker": "B", "next_action": "x"},
        {"id": "B", "status": "blocked", "blocker": "A", "next_action": "x"},
    ]}
    assert "circular_blocker" in _codes(data)


def test_freshness_report_never_mutates_the_backlog():
    import copy
    data = {"items": [{"id": "A", "status": "proposed", "last_verified_at": "2020-01-01T00:00:00+00:00", "next_action": "x"}]}
    snapshot = copy.deepcopy(data)
    cb.freshness_report(data, now=NOW)
    assert data == snapshot  # read-only
