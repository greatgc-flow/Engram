import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import quota
import math
import pytest

def test_calculate_pacing_zero_window_hours():
    # Should not raise ZeroDivisionError
    result = quota.calculate_pacing(0.5, 3600, 0.0)
    assert result["status"] == "unknown"
    assert result["ratio"] is None
    assert result["invalid_input_reason"] == "window_hours_out_of_range"

def test_calculate_pacing_normal():
    result = quota.calculate_pacing(0.5, 1800, 1.0)
    assert result["status"] in ("safe", "warn", "danger")

def test_calculate_pacing_negative_window_hours():
    result = quota.calculate_pacing(0.5, 3600, -1.0)
    assert result["status"] == "unknown"
    assert result["ratio"] is None


@pytest.mark.parametrize("value", [True, "abc", float("nan"), float("inf")])
def test_get_remaining_seconds_rejects_invalid_duration(value):
    assert quota.get_remaining_seconds(reset_in_seconds=value) is None


def test_get_remaining_seconds_preserves_expired_duration_behavior():
    assert quota.get_remaining_seconds(reset_in_seconds=-1) == 0.0


@pytest.mark.parametrize(
    ("field", "args", "reason"),
    [
        ("used", (float("nan"), 1.0, 1.0), "used_frac_not_finite"),
        ("remaining", (0.1, True, 1.0), "remaining_seconds_not_numeric"),
        ("window", (0.1, 1.0, float("inf")), "window_hours_not_finite"),
    ],
)
def test_calculate_pacing_rejects_all_invalid_numeric_inputs(field, args, reason):
    result = quota.calculate_pacing(*args)
    assert result == {
        "ratio": None,
        "status": "unknown",
        "indicator": "",
        "invalid_input_reason": reason,
    }


def test_vendor_iso_timestamp_rejects_naive_but_accepts_aware():
    assert quota.get_remaining_seconds(
        resets_at_iso="2030-01-01T00:00:00", now_ts=0
    ) is None
    assert quota.get_remaining_seconds(
        resets_at_iso="2030-01-01T00:00:00+00:00", now_ts=0
    ) > 0
