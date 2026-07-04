"""B5 — stale active_coordinator guard (_fresh_active_coordinator).

A days-old coordinator left in state.json (e.g. from a prior test mission) must
NOT be trusted for terminal identity; only a coordinator proven fresh by
leadership.challenge_until (future) or role_assignments.coordinator.assigned_at
(within a 4h TTL) is returned, else None (VACANT).
"""
import sys
from datetime import datetime
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub  # noqa: E402


NOW = datetime(2026, 7, 4, 12, 0, 0)


def test_fresh_via_assigned_at():
    state = {
        "active_coordinator": "cc",
        "role_assignments": {"coordinator": {"assigned_at": "2026-07-04T10:00:00"}},
    }
    assert hub._fresh_active_coordinator(state, now=NOW) == "cc"


def test_fresh_via_challenge_until():
    state = {
        "active_coordinator": "cc",
        "leadership": {"challenge_until": "2026-07-04T13:00:00"},
    }
    assert hub._fresh_active_coordinator(state, now=NOW) == "cc"


def test_stale_old_assigned_at():
    # The real bug: cx assigned 4 days ago (test mission) -> not fresh -> None.
    state = {
        "active_coordinator": "cx",
        "role_assignments": {"coordinator": {"assigned_at": "2026-06-30T23:18:43"}},
    }
    assert hub._fresh_active_coordinator(state, now=NOW) is None


def test_stale_expired_challenge_until():
    state = {
        "active_coordinator": "cx",
        "leadership": {"challenge_until": "2026-07-04T11:00:00"},
    }
    assert hub._fresh_active_coordinator(state, now=NOW) is None


def test_missing_signals_is_none():
    assert hub._fresh_active_coordinator({"active_coordinator": "ag"}, now=NOW) is None


def test_empty_state_is_none():
    assert hub._fresh_active_coordinator({}, now=NOW) is None


def test_stale_then_fresh_fallback():
    # Expired challenge_until but a fresh assigned_at still proves freshness.
    state = {
        "active_coordinator": "cc",
        "leadership": {"challenge_until": "2026-07-04T11:00:00"},
        "role_assignments": {"coordinator": {"assigned_at": "2026-07-04T11:30:00"}},
    }
    assert hub._fresh_active_coordinator(state, now=NOW) == "cc"
