"""format_quota_bucket — every quota bucket renders identically; 0% keeps the full
shape (bar + emoji + pacing), and unmeasured buckets render the literal 'absent'
(never 0, blank, or an estimate). Fixes the reported 0%-row inconsistency."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # _sys/
DIAG = ROOT / "cli" / "diag.py"
QUOTA = ROOT / "core" / "quota.py"

GREEN, YELLOW, RED = "\U0001f7e2", "\U0001f7e1", "\U0001f534"


def _diag():
    spec = importlib.util.spec_from_file_location("diag_under_test", DIAG)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _quota():
    spec = importlib.util.spec_from_file_location("quota_under_test", QUOTA)
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


def test_time_to_exhaustion_is_pure_and_never_guesses_missing_inputs():
    quota = _quota()

    assert quota.time_to_exhaustion(0.68, 6.29, 168.0) == pytest.approx(8.5469, rel=1e-4)
    assert quota.time_to_exhaustion(1.0, 6.29, 168.0) == 0.0
    assert quota.time_to_exhaustion(0.20, 0.0, 5.0) == float("inf")
    assert quota.time_to_exhaustion(0.20, None, 5.0) is None
    assert quota.time_to_exhaustion(0.20, 1.0, None) is None
    assert quota.time_to_exhaustion("bad", 1.0, 5.0) is None


def test_dependency_groups_keep_independent_ag_pools_separate_and_pick_binding_window():
    d = _diag()
    rows = [
        {"owner": "ag", "pool": "3P-5H", "used_frac": 0.95,
         "pacing": {"ratio": 10.42}, "reset_in_seconds": 3600, "source": "SL"},
        {"owner": "ag", "pool": "3P-7D", "used_frac": 0.02,
         "pacing": {"ratio": 0.20}, "reset_in_seconds": 500_000, "source": "SL"},
        {"owner": "ag", "pool": "G-5H", "used_frac": 0.10,
         "pacing": {"ratio": 1.05}, "reset_in_seconds": 3600, "source": "SL"},
        {"owner": "ag", "pool": "G-7D", "used_frac": 0.47,
         "pacing": {"ratio": 0.75}, "reset_in_seconds": 86_400, "source": "SL"},
    ]

    groups = {group["pool"]: group for group in d._quota_dependency_groups(rows)}

    assert set(groups) == {"3P", "G"}
    assert groups["3P"]["state"] == "binding"
    assert groups["3P"]["primary"]["pool"] == "3P-5H"
    assert groups["G"]["state"] == "safe"
    assert groups["G"]["primary"]["pool"] == "G-5H"


def test_dependency_group_is_binding_absent_when_any_window_cannot_be_classified():
    d = _diag()
    groups = d._quota_dependency_groups([
        {"owner": "cc", "pool": "C-5H", "used_frac": 0.20,
         "pacing": None, "reset_in_seconds": 3600, "source": "CLI"},
        {"owner": "cc", "pool": "C-7D", "used_frac": 0.35,
         "pacing": {"ratio": 0.50}, "reset_in_seconds": 3600, "source": "CLI"},
    ])

    assert len(groups) == 1
    assert groups[0]["state"] == "absent"
    assert "binding absent" in d._quota_dependency_group_text(groups[0]).lower()


def test_summary_and_live_share_one_dependency_group_payload(capsys):
    d = _diag()
    quotas = [
        {"label": "C-5H", "used_frac": 0.20, "pacing": {"ratio": 0.55},
         "reset": "in 1h", "reset_in_seconds": 3600},
        {"label": "C-7D", "used_frac": 0.35, "pacing": {"ratio": 2.25},
         "reset": "in 100h", "reset_in_seconds": 360_000},
    ]
    info = {
        "peer": "cc", "cost": None, "source": "cli_live", "ctx_window": 1,
        "ctx_used": 0, "ctx_pct": 0.0, "ctx_known": True, "gate": True,
        "empty": False, "quotas": quotas,
    }
    expected_group = d._quota_dependency_groups([
        {"owner": "cc", "pool": q["label"], "source": "CLI", **q}
        for q in quotas
    ])[0]
    expected_payload = d._quota_dependency_group_text(expected_group)

    d.render_summary([info])
    summary = capsys.readouterr().out
    live = __import__("io").StringIO()
    d.render_live_quota_pools(
        live, {"peers": [{"peer": "cc", "raw": info}]}, columns=160, line_budget=None,
    )
    live_text = live.getvalue()

    assert expected_group["state"] == "binding"
    assert expected_group["primary"]["pool"] == "C-7D"
    assert summary.count("C-pool") == 1
    assert live_text.count("C-pool") == 1
    assert expected_payload in summary
    assert expected_payload in live_text
    assert "(5H 20% 0.55x)" in expected_payload


def test_real_binary_rejects_wrapper_and_unknown():
    d = _diag()
    with pytest.raises(ValueError):
        d._real_binary("nope")
    b = d._real_binary("cx")
    if b is not None:  # binary may be absent in some environments
        assert Path(b).parent.name != "cli"
