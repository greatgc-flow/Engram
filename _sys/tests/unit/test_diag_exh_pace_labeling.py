"""TDD for the pretdd-prep-2026-07-21-diag-quota-metrics.md Topic 1 design:
URG -> EXH rename (column header, docstrings, internal var names) and explicit
"Pace" labeling on the per-bucket pacing ratio, with the necessary column-width
widening to keep alignment. Written before the implementation change."""
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "cli"))
import diag  # noqa: E402


def test_column_header_says_exh_not_urg():
    header_tier0 = diag._quota_columns_for_tier(0)
    header_tier2 = diag._quota_columns_for_tier(2)
    assert "EXH" in header_tier0
    assert "URG" not in header_tier0
    assert "EXH" in header_tier2
    assert "URG" not in header_tier2


def _one_bucket_group(ratio=0.75, used_frac=0.5, eta_full=8.0, reset_hours=6.0):
    return {
        "pool": "cc",
        "primary": {
            "label": "cc", "_suffix": "5H", "used_frac": used_frac,
            "pacing": {"ratio": ratio}, "_eta_full": eta_full, "_reset_hours": reset_hours,
        },
        "secondary": [],
    }


def test_bucket_pace_is_explicitly_labeled():
    group = _one_bucket_group(ratio=0.75)
    text_tier0 = diag._quota_dependency_group_text(group, tier=0)
    assert "Pace 0.75x" in text_tier0


def test_bucket_pace_unknown_ratio_still_labeled():
    group = _one_bucket_group()
    group["primary"]["pacing"] = {}
    text_tier0 = diag._quota_dependency_group_text(group, tier=0)
    assert "Pace ?" in text_tier0


def test_exh_line_has_no_stale_urg_text():
    group = _one_bucket_group()
    text_tier0 = diag._quota_dependency_group_text(group, tier=0)
    assert "URG" not in text_tier0


def test_column_alignment_survives_pace_label_widening():
    """Two groups, one with a full "Pace N.NNx" cell and one with "--" (no
    bucket for that window) must still line up on the '|' divider - i.e. the
    width contract must be applied consistently to both branches."""
    wide_group = _one_bucket_group(ratio=1.23)
    narrow_group = {
        "pool": "ag",
        "primary": {
            "label": "ag", "_suffix": "7D", "used_frac": 0.3,
            "pacing": {"ratio": 0.4}, "_eta_full": 20.0, "_reset_hours": 8.0,
        },
        "secondary": [],
    }
    wide_text = diag._quota_dependency_group_text(wide_group, tier=0)
    narrow_text = diag._quota_dependency_group_text(narrow_group, tier=0)
    wide_divider = wide_text.index("|")
    narrow_divider = narrow_text.index("|")
    assert wide_divider == narrow_divider, (
        f"'|' divider misaligned after Pace-label widening: {wide_divider} vs {narrow_divider}\n"
        f"wide:   {wide_text!r}\nnarrow: {narrow_text!r}"
    )
