"""Tests for the diag MECE redesign — display width + section field ownership.

Design: _sys/docs/history/ops/diag-redesign-design.md (ag impl, cx-GO). Quota
lives ONLY in SUMMARY; PROFILES is topology-only; emoji cells use _dw/_pad.
"""
import io
import sys
from datetime import datetime, timezone
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]


def load_diag():
    import importlib.util
    spec = importlib.util.spec_from_file_location("diag_layout_under_test", SYS_DIR / "cli" / "diag.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_snapshot():
    if str(SYS_DIR / "core") not in sys.path:
        sys.path.insert(0, str(SYS_DIR / "core"))
    import snapshot
    return snapshot


def test_dw_widths():
    diag = load_diag()
    assert diag._dw("🟢") == 2
    assert diag._dw("🚫") == 2
    assert diag._dw("text 🟢") == 7
    assert diag._dw("中文") == 4
    assert diag._dw(diag._c("text", "green")) == 4   # ANSI stripped
    assert diag._dw("ö") == 1                    # combining mark = 0
    assert diag._dw("absent") == 6


def test_pad_display_width():
    diag = load_diag()
    assert diag._pad("🟢", 4) == "🟢  "
    assert diag._pad("中文", 6, align="right") == "  中文"
    colored = diag._c("text", "green")
    assert diag._pad(colored, 6) == colored + "  "     # pad after color, width by _dw


def test_elide_display_preserves_complete_ansi_sequences():
    diag = load_diag()
    text = "\033[31m" + ("x" * 20) + "\033[0m"
    elided = diag._elide_display(text, 10)
    assert diag._dw(elided) == 10
    assert "\033[31m" in elided
    assert elided.endswith("\033[0m")


def test_render_profiles_has_no_quota_columns():
    diag = load_diag()
    snap = {"profiles": [{
        "profile": "cc.deepthink", "peer": "cc", "model": "Opus", "effort": "high",
        "cost_tier": "high", "context": {"window_tokens": 1000},
        "quota": {"buckets": [{"label": "C-5H", "used_frac": 0.5}]},
        "sources": {"model": "orchestration", "context": "cli_live", "quota": "cli_live"},
        "state": "eligible",
    }]}
    out = io.StringIO()
    diag.render_profiles(out, snapshot=snap)
    text = out.getvalue()
    assert "PROFILE" in text and "TIER" in text and "STATE" in text
    assert "5H" not in text and "WEEKLY" not in text and "resets" not in text
    assert "[decl] Opus" in text  # orchestration-sourced model prefixed


def test_render_profiles_renders_declared_intelligence_or_absent():
    diag = load_diag()
    out = io.StringIO()
    diag.render_profiles(out, snapshot={"profiles": [
        {
            "profile": "cx.deepthink", "model": "Sol", "effort": "xhigh", "cost_tier": "high",
            "context": {"window_tokens": 100}, "state": "eligible", "sources": {},
            "intelligence_evidence": {
                "estimate": {"kind": "point", "value": 59.0, "approximate": True},
                "source_kind": "declared", "verification": "unverified",
            },
        },
        {
            "profile": "ag.deepthink", "model": "Pro", "effort": "high", "cost_tier": "high",
            "context": {"window_tokens": 100}, "state": "eligible", "sources": {},
            "intelligence_evidence": {
                "estimate": {"kind": "range", "min": 46.0, "max": 47.0, "approximate": True},
                "source_kind": "declared", "verification": "unverified",
            },
        },
        {
            "profile": "cc.standard", "model": "Haiku", "effort": "low", "cost_tier": "low",
            "context": {"window_tokens": 100}, "state": "eligible", "sources": {},
        },
    ]})
    text = out.getvalue()
    assert "INTEL" in text
    assert "~59 [decl]" in text
    assert "~46-47 [decl]" in text
    assert "absent" in text


def test_render_summary_sorted_continuation_rows_and_glyphs():
    diag = load_diag()
    infos = [{
        "peer": "cc", "model": "Opus", "cost": 0.5, "source": "cli_live",
        "ctx_window": 1000, "ctx_used": 100, "ctx_pct": 10.0, "ctx_known": True,
        "gate": True, "empty": False,
        "quotas": [
            {"label": "C-7D", "used_frac": 0.95, "reset": "tomorrow", "pacing": None},
            {"label": "C-5H", "used_frac": 1.0, "reset": "in 1h", "pacing": None},
            {"label": "F-5H", "used_frac": 0.0, "reset": "in 2h", "pacing": None},
        ],
    }]
    out = io.StringIO()
    old = sys.stdout
    old_color = diag._COLOR
    sys.stdout = out
    diag._COLOR = True
    try:
        diag.render_summary(infos)
    finally:
        sys.stdout = old
        diag._COLOR = old_color
    text = out.getvalue()
    assert text.index("C-5H") < text.index("C-7D") < text.index("F-5H")  # sorted
    assert "\U0001F6AB" in text   # 🚫 saturated (>=1.0)
    assert "\U0001F534" in text   # 🔴 (>=0.90)
    assert "\U0001F7E2" in text   # 🟢 (0%)
    assert "WARN" in text         # >=0.90


def test_peer_state_precedence_quarantine_over_open():
    diag = load_diag()
    info = {
        "peer": "cc", "model": "M", "cost": None, "source": "live",
        "ctx_window": 100, "ctx_used": 1, "ctx_pct": 1.0, "ctx_known": True,
        "gate": True, "quarantined": True, "empty": False, "quotas": [],
    }
    assert diag._peer_state_label(info) == "QUARANTINE"
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        diag.render_summary([info])
    finally:
        sys.stdout = old
    assert "QUARANTINE" in out.getvalue()
    assert "CC    OPEN" not in out.getvalue()


def test_source_codes_are_consistent_across_summary_profiles_and_card():
    diag = load_diag()
    raw = {
        "peer": "cc", "model": "M", "cost": None, "source": "live",
        "ctx_window": 100, "ctx_used": 1, "ctx_pct": 1.0, "ctx_known": True,
        "gate": True, "quarantined": False, "empty": False, "quotas": [],
    }
    summary = io.StringIO()
    old = sys.stdout
    sys.stdout = summary
    try:
        diag.render_summary([raw])
    finally:
        sys.stdout = old
    profiles = io.StringIO()
    diag.render_profiles(profiles, snapshot={"profiles": [{
        "profile": "cc.standard", "model": "M", "effort": "low", "cost_tier": "low",
        "context": {"window_tokens": 100}, "state": "eligible",
        "sources": {"model": "statusline", "context": "live", "quota": "app_server"},
    }]})
    card = io.StringIO()
    old = sys.stdout
    sys.stdout = card
    try:
        diag.render_card(raw)
    finally:
        sys.stdout = old
    assert "STAT" in summary.getvalue()
    assert "c:STAT q:APP" in profiles.getvalue()
    assert "Source: STAT" in card.getvalue()
    assert "CLI=cli_live" in summary.getvalue()


def test_model_elision_is_display_width_safe_after_prefixing():
    diag = load_diag()
    long_model = "model-name-that-exceeds-the-available-cell-width"
    rendered = diag._elide_display("[decl] " + long_model, 28)
    assert rendered.endswith("...")
    assert diag._dw(rendered) == 28
    out = io.StringIO()
    diag.render_profiles(out, snapshot={"profiles": [{
        "profile": "cc.standard", "model": long_model, "effort": "low", "cost_tier": "low",
        "context": {"window_tokens": 100}, "state": "eligible",
        "sources": {"model": "orchestration", "context": "orchestration", "quota": "absent"},
    }]})
    assert "..." in out.getvalue()


def test_plain_output_uses_text_severity_tokens_without_ansi_or_emoji():
    diag = load_diag()
    old_color = diag._COLOR
    diag._COLOR = False
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        diag.render_summary([{
            "peer": "cc", "model": "M", "cost": None, "source": "live",
            "ctx_window": 100, "ctx_used": 1, "ctx_pct": 1.0, "ctx_known": True,
            "gate": True, "quarantined": False, "empty": False,
            "quotas": [{"label": "C-5H", "used_frac": 0.95,
                        "pacing": {"ratio": 1.05, "status": "danger", "indicator": "x"}}],
        }])
    finally:
        sys.stdout = old
        diag._COLOR = old_color
    text = out.getvalue()
    assert "[CRIT]" in text
    assert "\033[" not in text
    assert not any(ch in text for ch in ("🟢", "🟡", "🔴", "🚫"))


def test_snapshot_absent_stays_literal():
    snapshot = load_snapshot()
    assert snapshot.format_quota_bucket({"used_frac": None}) == "absent"
    assert snapshot.format_quota_bucket("not-a-dict") == "absent"
    assert "[----------] 0%" in snapshot.format_quota_bucket({"used_frac": 0.0})


def test_recent_session_rows_never_exceed_requested_display_width():
    diag = load_diag()
    snapshot = {
        "peers": [{"peer": "cx"}],
        "sessions": [{
            "peer": "cx",
            "profile": "cx.deepthink-profile-name-that-is-too-long",
            "last_used_at": "2026-07-13T09:57:00+00:00",
            "context": {},
            "scope_key": "room-with-a-very-long-name-that-must-be-elided",
        }],
    }
    out = io.StringIO()

    diag.render_recent_sessions(
        out,
        snapshot,
        now=datetime(2026, 7, 13, 10, tzinfo=timezone.utc),
        columns=40,
    )

    lines = out.getvalue().splitlines()
    assert lines
    assert all(diag._dw(line) <= 40 for line in lines)
    assert any("absent" in line for line in lines)


def test_summary_frame_respects_terminal_height_budget_and_panel_order():
    diag = load_diag()
    raw = {
        "peer": "cc", "gate": True, "quarantined": False,
        "model": "model", "ctx_used": 10, "ctx_window": 100,
        "ctx_pct": 10.0, "cost": None, "source": "cli_live",
        "quotas": [], "empty": False, "ctx_known": True,
    }
    sessions = [{
        "peer": "cc", "profile": f"cc.p{i}",
        "last_used_at": f"2026-07-13T09:5{i}:00+00:00",
        "context": {"utilization_pct": i},
        "scope_key": f"room-{i}:cc.p{i}",
    } for i in range(5)]
    snapshot = {
        "observed_at": "2026-07-13T10:00:00+00:00",
        "peers": [{"peer": "cc", "raw": raw}],
        "profiles": [],
        "sessions": sessions,
    }
    out = io.StringIO()

    diag.render_summary_frame(
        out,
        snapshot,
        terminal_lines=20,
        columns=80,
        now=datetime(2026, 7, 13, 10, tzinfo=timezone.utc),
    )

    text = out.getvalue()
    assert len(text.splitlines()) <= 19  # one row is deliberately reserved
    assert text.index(" SUMMARY") < text.index("RECENT SESSIONS") < text.index(" FRAME")
