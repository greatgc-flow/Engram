"""format_quota_bucket — every quota bucket renders identically; 0% keeps the full
shape (bar + emoji + pacing), and unmeasured buckets render the literal 'absent'
(never 0, blank, or an estimate). Fixes the reported 0%-row inconsistency."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # _sys/
DIAG = ROOT / "cli" / "diag.py"

GREEN, YELLOW, RED = "\U0001f7e2", "\U0001f7e1", "\U0001f534"


def _diag():
    spec = importlib.util.spec_from_file_location("diag_under_test", DIAG)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_zero_percent_keeps_full_shape():
    d = _diag()
    out = d.format_quota_bucket({"used_frac": 0.0, "pacing_ratio": 0.0})
    assert GREEN in out and "0.00x" in out and "0%" in out
    assert out.strip() and out != "absent"  # never blank


def test_absent_is_literal_never_fabricated():
    d = _diag()
    assert d.format_quota_bucket({"used_frac": None}) == "absent"
    assert d.format_quota_bucket({"source": "absent", "used_frac": 0.5}) == "absent"
    assert d.format_quota_bucket("not-a-dict") == "absent"
    assert d.format_quota_bucket({"used_frac": "bad"}) == "absent"


def test_severity_thresholds():
    d = _diag()
    assert GREEN in d.format_quota_bucket({"used_frac": d.QUOTA_WARN_FRAC - 0.05, "pacing_ratio": 1.0})
    assert YELLOW in d.format_quota_bucket({"used_frac": d.QUOTA_WARN_FRAC + 0.01, "pacing_ratio": 1.0})
    assert RED in d.format_quota_bucket({"used_frac": d.QUOTA_CRIT_FRAC + 0.01, "pacing_ratio": 1.0})


def test_real_binary_rejects_wrapper_and_unknown():
    d = _diag()
    with pytest.raises(ValueError):
        d._real_binary("nope")
    b = d._real_binary("cx")
    if b is not None:  # binary may be absent in some environments
        assert Path(b).parent.name != "cli"
