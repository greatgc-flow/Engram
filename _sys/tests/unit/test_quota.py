import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import quota

def test_calculate_pacing_zero_window_hours():
    # Should not raise ZeroDivisionError
    result = quota.calculate_pacing(0.5, 3600, 0.0)
    assert result["status"] == "unknown"
    assert result["ratio"] == 0.0

def test_calculate_pacing_normal():
    result = quota.calculate_pacing(0.5, 1800, 1.0)
    assert result["status"] in ("safe", "warn", "danger")

def test_calculate_pacing_negative_window_hours():
    result = quota.calculate_pacing(0.5, 3600, -1.0)
    assert result["status"] == "unknown"
    assert result["ratio"] == 0.0
