"""Regression tests for hub.py's vendor reset-time parsing.

See docs/design/quota-efficiency-RATIFIED-cx-astra-2026-09-13.md section 4
(bug 3): a bare time-of-day with no date, once already past today, used to
be rolled forward a full day -- fabricating a 24h block that was empirically
false. Fixed to return None (unknown) instead of guessing "tomorrow".
"""
import datetime as datetime_module
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub


def _freeze(monkeypatch, fixed_now: datetime) -> None:
    # _parse_reset_time does `from datetime import datetime` INSIDE the
    # function body, re-resolving it from the stdlib `datetime` module on
    # every call -- so the fake `now()` must be installed on that module's
    # `datetime` attribute, not on `hub`'s own namespace.
    class FixedDatetime(datetime_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    monkeypatch.setattr(datetime_module, "datetime", FixedDatetime)


def test_reset_time_bare_time_in_future_today_is_parsed(monkeypatch):
    fixed_now = datetime(2026, 9, 14, 2, 0, 0)
    _freeze(monkeypatch, fixed_now)
    result = hub._parse_reset_time("You've hit your usage limit. try again at 4:28 AM.")
    assert result is not None
    parsed = datetime.fromisoformat(result)
    assert parsed.date() == fixed_now.date()
    assert (parsed.hour, parsed.minute) == (4, 28)


def test_reset_time_bare_time_already_past_today_returns_none(monkeypatch):
    fixed_now = datetime(2026, 9, 13, 23, 35, 0)
    _freeze(monkeypatch, fixed_now)
    result = hub._parse_reset_time("rate limited, try again at 11:27 PM")
    assert result is None


def test_reset_time_bare_time_exactly_now_returns_none(monkeypatch):
    fixed_now = datetime(2026, 9, 13, 23, 27, 0)
    _freeze(monkeypatch, fixed_now)
    result = hub._parse_reset_time("rate limited, try again at 11:27 PM")
    assert result is None


def test_reset_time_full_date_still_parsed():
    result = hub._parse_reset_time("try again at Sep 20, 2026 11:27 PM")
    assert result is not None
    parsed = datetime.fromisoformat(result)
    assert (parsed.year, parsed.month, parsed.day) == (2026, 9, 20)
    assert (parsed.hour, parsed.minute) == (23, 27)


def test_classify_ask_failure_ambiguous_bare_time_sets_no_reset_at(monkeypatch):
    fixed_now = datetime(2026, 9, 13, 23, 35, 0)
    _freeze(monkeypatch, fixed_now)
    reason, extra = hub._classify_ask_failure(
        "rate limit exceeded, try again at 11:27 PM"
    )
    assert reason == "rate_or_session_limit"
    assert "rate_limit_state" not in extra
