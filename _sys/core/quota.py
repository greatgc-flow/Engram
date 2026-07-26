"""Quota time normalization and pacing calculations."""
from __future__ import annotations

import math
import time

try:
    from .timestamps import parse_iso_timestamp
except ImportError:
    from timestamps import parse_iso_timestamp


def _finite_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, f"{field}_not_numeric"
    number = float(value)
    if not math.isfinite(number):
        return None, f"{field}_not_finite"
    return number, None


def _unknown(reason):
    return {
        "ratio": None,
        "status": "unknown",
        "indicator": "",
        "invalid_input_reason": reason,
    }


def get_remaining_seconds(reset_in_seconds=None, resets_at_iso=None, now_ts=None):
    """Normalize expiry formats without guessing a vendor timezone."""
    if reset_in_seconds is not None:
        try:
            if isinstance(reset_in_seconds, bool):
                raise TypeError("booleans are not durations")
            duration = float(reset_in_seconds)
            if not math.isfinite(duration):
                raise ValueError("duration must be finite")
            return max(0.0, duration)
        except (TypeError, ValueError, OverflowError):
            return None
    if not resets_at_iso:
        return None

    now_ts = time.time() if now_ts is None else now_ts
    if isinstance(resets_at_iso, bool):
        return None
    if isinstance(resets_at_iso, (int, float)):
        ts = float(resets_at_iso)
        if not math.isfinite(ts):
            return None
        if ts > 2e10:
            ts /= 1000.0
        return max(0.0, ts - now_ts)

    try:
        reset_ts = parse_iso_timestamp(
            resets_at_iso, naive_policy="reject"
        ).timestamp()
        return max(0.0, reset_ts - now_ts)
    except (TypeError, ValueError, OverflowError):
        return None


def calculate_pacing(used_frac, remaining_seconds, window_hours):
    """Return measured pacing or a machine-readable unknown-input result."""
    used_frac, reason = _finite_number(used_frac, "used_frac")
    if reason:
        return _unknown(reason)
    remaining_seconds, reason = _finite_number(
        remaining_seconds, "remaining_seconds"
    )
    if reason:
        return _unknown(reason)
    window_hours, reason = _finite_number(window_hours, "window_hours")
    if reason:
        return _unknown(reason)

    if used_frac < 0.0 or used_frac > 1.0:
        return _unknown("used_frac_out_of_range")
    if remaining_seconds < 0.0:
        return _unknown("remaining_seconds_out_of_range")
    if window_hours <= 0.0:
        return _unknown("window_hours_out_of_range")
    if used_frac == 0.0:
        return {"ratio": 0.0, "status": "safe", "indicator": "🟢"}

    total_seconds = window_hours * 3600.0
    elapsed_seconds = max(0.0, total_seconds - remaining_seconds)
    elapsed_frac = elapsed_seconds / total_seconds
    pacing_ratio = used_frac / max(0.05, elapsed_frac)

    if pacing_ratio > 1.0:
        status, indicator = "danger", "🔴"
    elif pacing_ratio >= 0.8:
        status, indicator = "warn", "🟡"
    else:
        status, indicator = "safe", "🟢"
    return {
        "ratio": round(pacing_ratio, 2),
        "status": status,
        "indicator": indicator,
        "elapsed_frac": elapsed_frac,
    }


def time_to_exhaustion(used_frac, pacing_ratio, window_hours):
    """Return projected hours until a quota bucket reaches 100%.

    The projection uses only measured bucket inputs. ``None`` means the
    projection is absent; a zero measured burn rate means exhaustion is
    infinitely far away. Values are intentionally not rounded here so callers
    can compare the projection with the bucket's own reset precisely.
    """
    values = (used_frac, pacing_ratio, window_hours)
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values
    ):
        return None
    used_frac, pacing_ratio, window_hours = map(float, values)
    if not all(
        math.isfinite(value)
        for value in (used_frac, pacing_ratio, window_hours)
    ):
        return None
    if used_frac < 0.0 or pacing_ratio < 0.0 or window_hours <= 0.0:
        return None
    if used_frac >= 1.0:
        return 0.0
    if pacing_ratio == 0.0:
        return math.inf
    return (1.0 - used_frac) * window_hours / pacing_ratio
