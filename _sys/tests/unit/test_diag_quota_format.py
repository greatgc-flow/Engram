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
    assert "≥0.00x" in d._quota_dependency_group_text(groups[0])


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
    assert "20% Pace 0.55x" in expected_payload
    assert "35% Pace 2.25x" in expected_payload
    assert "2.06x" in expected_payload


def test_summary_shows_adjusted_exh_with_raw_in_tail_for_eligible_credits(capsys):
    """2026-07-22 (user request): EXH itself becomes raw EXH / (1 +
    eligible_credits) so priority can be read off EXH alone; the unadjusted
    number moves to a 'RAW ... (ticket count)' tail instead of disappearing.
    Peers without the credit concept never render the tail at all."""
    d = _diag()
    quotas = [{"label": "X-7D", "used_frac": 0.55, "pacing": {"ratio": 1.29},
               "reset": "in 3d", "reset_in_seconds": 260_000}]
    info = {
        "peer": "cx", "cost": None, "source": "app_server", "ctx_window": 1,
        "ctx_used": 0, "ctx_pct": 0.0, "ctx_known": True, "gate": True,
        "empty": False, "quotas": quotas, "eligible_credits": 3,
    }

    d.render_summary([info])
    summary = capsys.readouterr().out

    assert "RAW 1.23x" in summary  # raw EXH preserved, now in the RAW tail
    assert "0.31x" in summary  # adjusted EXH (1.23 / (1+3)) is now the main value


def test_raw_exh_tail_does_not_downgrade_tier_for_other_peers():
    """cx.effort's HIGH finding (still applies after the 2026-07-22 EXH/RAW
    swap): the RAW tail text on cx's row must not be counted in the shared
    tier fit-check -- a long "RAW ... manual" tail on ONE peer's row must not
    push ALL peers into the tier-3 BINDING fallback, which drops EXH entirely
    for every row."""
    d = _diag()
    cx_group = {
        "pool": "X", "state": "binding",
        "primary": {"used_frac": 0.55, "_eta_full": 100, "_reset_hours": 130,
                     "_suffix": "7D", "pacing": {"ratio": 1.29}},
        "secondary": [],
        "_has_credit_concept": True, "_eligible_credits": 3,
    }
    other_group = {
        "pool": "C", "state": "binding",
        "primary": {"used_frac": 0.20, "_eta_full": 200, "_reset_hours": 100,
                     "_suffix": "7D", "pacing": {"ratio": 0.55}},
        "secondary": [],
        "_has_credit_concept": False, "_eligible_credits": None,
    }

    tier = d._select_quota_tier([cx_group, other_group], 80, prefix_len=13)
    other_text = d._quota_dependency_group_text(other_group, tier=tier)

    assert tier < 3  # not forced into the EXH-dropping BINDING fallback
    assert "0.55x" in other_text  # raw EXH still visible for the unrelated peer


def test_summary_exh_unadjusted_when_credit_data_unreadable(capsys):
    """has_credit_concept true but eligible_credits unset (fetch failed /
    ambiguous) must leave EXH as the raw/unadjusted number (never a guessed
    adjustment) and say so explicitly rather than silently guessing."""
    d = _diag()
    quotas = [{"label": "X-7D", "used_frac": 0.55, "pacing": {"ratio": 1.29},
               "reset": "in 3d", "reset_in_seconds": 260_000}]
    info = {
        "peer": "cx", "cost": None, "source": "app_server", "ctx_window": 1,
        "ctx_used": 0, "ctx_pct": 0.0, "ctx_known": True, "gate": True,
        "empty": False, "quotas": quotas,
    }

    d.render_summary([info])
    summary = capsys.readouterr().out

    assert "1.29x" in summary  # main EXH is the raw value, unadjusted
    assert "EXH unadjusted (credits unknown)" in summary


def test_summary_no_raw_tail_for_peers_without_credit_concept(capsys):
    d = _diag()
    quotas = [{"label": "C-7D", "used_frac": 0.20, "pacing": {"ratio": 0.55},
               "reset": "in 1h", "reset_in_seconds": 3600}]
    info = {
        "peer": "cc", "cost": None, "source": "cli_live", "ctx_window": 1,
        "ctx_used": 0, "ctx_pct": 0.0, "ctx_known": True, "gate": True,
        "empty": False, "quotas": quotas,
    }

    d.render_summary([info])
    summary = capsys.readouterr().out

    assert "RAW" not in summary
    assert "unadjusted" not in summary


def test_summary_shows_reset_credit_badge_separate_from_pool_exh(capsys):
    """Reset-credit count renders once on the peer row (account-wide, not
    per-pool), never folded into any pool's EXH/pacing number."""
    d = _diag()
    info = {
        "peer": "cx", "cost": None, "source": "app_server", "ctx_window": 1,
        "ctx_used": 0, "ctx_pct": 0.0, "ctx_known": True, "gate": True,
        "empty": False, "quotas": [], "reset_credits_available": 3,
    }

    d.render_summary([info])
    summary = capsys.readouterr().out

    assert "\U0001f3ab3" in summary


def test_summary_omits_credit_badge_when_not_measured(capsys):
    d = _diag()
    info = {
        "peer": "cc", "cost": None, "source": "cli_live", "ctx_window": 1,
        "ctx_used": 0, "ctx_pct": 0.0, "ctx_known": True, "gate": True,
        "empty": False, "quotas": [],
    }

    d.render_summary([info])
    summary = capsys.readouterr().out

    assert "\U0001f3ab" not in summary


def test_real_binary_rejects_wrapper_and_unknown():
    d = _diag()
    with pytest.raises(ValueError):
        d._real_binary("nope")
    b = d._real_binary("cx")
    if b is not None:  # binary may be absent in some environments
        assert Path(b).parent.name != "cli"
