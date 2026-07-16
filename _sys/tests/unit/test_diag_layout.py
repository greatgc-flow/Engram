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


def test_render_summary_uses_peer_facts_and_urgent_quota_order():
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
    lines = text.splitlines()
    header_index = next(i for i, line in enumerate(lines) if "PEER" in line and "CONTEXT" in line)
    header = lines[header_index]
    peer_line = lines[header_index + 1]
    assert "MODEL" not in header
    assert "Opus" not in peer_line
    assert text.index("C-pool") < text.index("F-pool")
    assert "\U0001F534" in text   # 🔴 (>=0.90)
    assert "\U0001F7E2" in text   # 🟢 (0%)
    assert "WARN" in text         # >=0.90


def test_render_summary_orders_quota_rows_by_used_fraction_descending():
    diag = load_diag()
    info = {
        "peer": "cc", "model": "must-not-render", "cost": None, "source": "cli_live",
        "ctx_window": 1000, "ctx_used": 100, "ctx_pct": 10.0, "ctx_known": True,
        "gate": True, "empty": False,
        "quotas": [
            {"label": "A-low", "used_frac": 0.10, "reset": "later", "pacing": None},
            {"label": "Z-high", "used_frac": 0.90, "reset": "later", "pacing": None},
            {"label": "M-mid", "used_frac": 0.50, "reset": "later", "pacing": None},
        ],
    }
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        diag.render_summary([info])
    finally:
        sys.stdout = old

    text = out.getvalue()
    assert "must-not-render" not in text
    assert text.index("Z-pool") < text.index("M-pool") < text.index("A-pool")


def test_quota_rows_sort_measured_pacing_before_used_fraction_without_fabricating_absent():
    diag = load_diag()
    quotas = [
        {"label": "absentHigh-5H", "used_frac": 0.95, "reset": "later", "pacing": None},
        {"label": "pacedLow-5H", "used_frac": 0.10, "reset": "later", "pacing": {"ratio": 1.10}},
        {"label": "pacedHigh-5H", "used_frac": 0.20, "reset": "later", "pacing": {"ratio": 1.50}},
        {"label": "absentMid-5H", "used_frac": 0.50, "reset": "later", "pacing": {}},
    ]
    snapshot = {"peers": [{"peer": "cc", "raw": {
        "peer": "cc", "source": "cli_live", "quotas": quotas,
    }}]}
    out = io.StringIO()

    diag.render_live_quota_pools(out, snapshot, columns=120, line_budget=None)

    text = out.getvalue()
    assert text.index("pacedHigh-pool") < text.index("pacedLow-pool")
    assert text.index("pacedLow-pool") < text.index("absentHigh-pool") < text.index("absentMid-pool")

    info = {
        "peer": "cc", "cost": None, "source": "cli_live", "ctx_window": 1,
        "ctx_used": 0, "ctx_pct": 0.0, "ctx_known": True, "gate": True,
        "empty": False, "quotas": quotas,
    }
    summary = io.StringIO()
    old = sys.stdout
    sys.stdout = summary
    try:
        diag.render_summary([info])
    finally:
        sys.stdout = old
    rendered = summary.getvalue()
    assert rendered.index("pacedHigh-pool") < rendered.index("pacedLow-pool")
    assert rendered.index("pacedLow-pool") < rendered.index("absentHigh-pool") < rendered.index("absentMid-pool")


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
    assert len(text.splitlines()) <= 20
    assert text.index("PEER HEALTH") < text.index("QUOTA POOLS") < text.index("ACTIVE SESSIONS") < text.index("OBSERVATION")


def test_live_peer_health_contains_only_peer_and_state():
    diag = load_diag()
    snapshot = {"peers": [{"peer": "cc", "raw": {
        "peer": "cc", "gate": True, "quarantined": False,
        "model": "must-not-render", "ctx_used": 99, "ctx_window": 100,
        "ctx_pct": 99.0, "cost": 12.34, "source": "cli_live",
    }}]}
    out = io.StringIO()

    diag.render_live_peer_health(out, snapshot, columns=80)

    text = out.getvalue()
    assert "PEER HEALTH" in text and "CC" in text and "OPEN" in text
    assert "must-not-render" not in text
    assert "99/100" not in text
    assert "$12.3400" not in text


def test_live_quota_pools_is_global_urgent_order_and_reports_hidden_count():
    diag = load_diag()
    snapshot = {"peers": [
        {"peer": "cc", "raw": {"peer": "cc", "source": "cli_live", "quotas": [
            {"label": "C-high", "used_frac": 0.90, "pacing": None, "reset": "soon"},
            {"label": "C-low", "used_frac": 0.10, "pacing": None, "reset": "later"},
        ]}},
        {"peer": "ag", "raw": {"peer": "ag", "source": "statusline", "quotas": [
            {"label": "A-mid", "used_frac": 0.50, "pacing": None, "reset": "later"},
            {"label": "A-low", "used_frac": 0.20, "pacing": None, "reset": "later"},
            {"label": "A-unknown", "used_frac": None, "pacing": None, "reset": "?"},
        ]}},
        {"peer": "cx", "raw": {"peer": "cx", "source": "cli_live", "quotas": [
            {"label": "X-low", "used_frac": 0.05, "pacing": None, "reset": "later"},
        ]}},
        {"peer": "ab", "raw": {"peer": "ab", "source": "cli_live", "quotas": [
            {"label": "Y-low", "used_frac": 0.01, "pacing": None, "reset": "later"},
        ]}},
    ]}
    out = io.StringIO()

    # budget=5: 2 header lines (section + column) + 2 detail rows + 1 hidden-count line
    diag.render_live_quota_pools(out, snapshot, columns=80, line_budget=5)

    text = out.getvalue()
    assert text.index("C-pool") < text.index("A-pool")
    assert "X-pool" not in text
    assert "+2 pools hidden" in text


def test_live_routing_alerts_omits_empty_and_caps_limited_resets():
    diag = load_diag()
    rendered = datetime(2026, 7, 8, 10, tzinfo=timezone.utc)
    empty = io.StringIO()
    diag.render_routing_alerts(empty, {"peers": [], "profiles": []}, columns=80, rendered_at=rendered)
    assert empty.getvalue() == ""

    snapshot = {
        "profiles": [{"profile": f"ag.p{i}"} for i in range(3)],
        "peers": [{"peer": "ag", "domains": {"health": {"profiles": {
            f"p{i}": {"rate_limit_state": {
                "limited": True, "reset_at": f"2026-07-08T10:{10 + i:02d}:00+00:00",
            }} for i in range(3)
        }}}}],
    }
    out = io.StringIO()
    diag.render_routing_alerts(out, snapshot, columns=80, rendered_at=rendered)
    text = out.getvalue()
    assert "ROUTING ALERTS" in text
    assert "ag.p0" in text and "ag.p1" in text and "ag.p2" not in text
    assert "+1 alerts hidden" in text


def test_live_observation_has_only_ttl_and_rendered_provenance(monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(diag, "expensive_source_age_sec", lambda: 17)
    out = io.StringIO()

    diag.render_observation(
        out,
        {"observed_at": "2026-07-08T09:59:55+00:00"},
        datetime(2026, 7, 8, 10, tzinfo=timezone.utc),
        columns=80,
    )

    text = out.getvalue()
    assert "OBSERVATION" in text and "TTL snapshot" in text and "RENDERED" in text
    assert "LIMITED RESETS" not in text


def test_live_five_section_frame_fits_80x24_with_multiple_peers_pools_and_sessions():
    diag = load_diag()
    raw_peers = []
    sessions = []
    for peer, used in (("cc", (0.90, 0.40, 0.10)), ("ag", (0.80, 0.30)), ("cx", (0.70, 0.20))):
        raw_peers.append({"peer": peer, "raw": {
            "peer": peer, "gate": True, "quarantined": False, "source": "cli_live",
            "quotas": [
                {"label": f"{peer}-{index}", "used_frac": value, "pacing": None, "reset": "later"}
                for index, value in enumerate(used)
            ],
        }})
        sessions.extend({
            "peer": peer, "profile": f"{peer}.p{index}",
            "last_used_at": f"2026-07-13T09:{50 - index:02d}:00+00:00",
            "context": {"utilization_pct": float(index)},
            "scope_key": f"room:{peer}.p{index}",
        } for index in range(3))
    snapshot = {"observed_at": "2026-07-13T10:00:00+00:00", "peers": raw_peers,
                "profiles": [], "sessions": sessions}
    out = io.StringIO()

    diag.render_summary_frame(
        out, snapshot, terminal_lines=24, columns=80,
        now=datetime(2026, 7, 13, 10, tzinfo=timezone.utc),
    )

    lines = out.getvalue().splitlines()
    assert len(lines) <= 24
    assert all(diag._dw(line) <= 80 for line in lines)
    assert "PEER HEALTH" in out.getvalue()
    assert "QUOTA POOLS" in out.getvalue()
    assert "ACTIVE SESSIONS" in out.getvalue()
    assert "OBSERVATION" in out.getvalue()


def test_live_peer_health_packs_into_one_line_and_sorts_abnormal_first():
    """T60: PEER HEALTH is packed into as few lines as fit, abnormal states first."""
    diag = load_diag()
    snapshot = {"peers": [
        {"peer": "cc", "domains": {"health": {"age_sec": 28}},
         "raw": {"peer": "cc", "gate": True, "quarantined": False}},
        {"peer": "cx", "domains": {"health": {"age_sec": 38}},
         "raw": {"peer": "cx", "gate": True, "quarantined": True}},
        {"peer": "ag", "domains": {"health": {"age_sec": 31}},
         "raw": {"peer": "ag", "gate": True, "quarantined": False}},
    ]}
    out = io.StringIO()
    diag.render_live_peer_health(out, snapshot, columns=80)
    text = out.getvalue()
    lines = text.splitlines()
    assert len(lines) == 1
    assert "-- PEER HEALTH --" in lines[0]
    # abnormal (CX:QUARANTINE) sorts before the OPEN peers
    assert text.index("CX:QUARANTINE") < text.index("CC:OPEN")
    assert text.index("CX:QUARANTINE") < text.index("AG:OPEN")
    assert "38s" in text and "28s" in text and "31s" in text


def test_live_peer_health_wraps_when_it_does_not_fit_narrow_columns():
    diag = load_diag()
    snapshot = {"peers": [
        {"peer": p, "domains": {"health": {"age_sec": 5}},
         "raw": {"peer": p, "gate": True, "quarantined": False}}
        for p in ("cc", "cx", "ag")
    ]}
    out = io.StringIO()
    diag.render_live_peer_health(out, snapshot, columns=20)
    lines = out.getvalue().splitlines()
    assert len(lines) > 1
    for line in lines:
        assert len(line) <= 20 or "..." in line
    # every peer still appears somewhere (none dropped by the wrap)
    joined = "\n".join(lines)
    assert "CC:OPEN" in joined and "CX:OPEN" in joined and "AG:OPEN" in joined


def test_live_quota_pools_hidden_line_points_to_full_diag():
    diag = load_diag()
    snapshot = {"peers": [
        {"peer": "cc", "raw": {"peer": "cc", "source": "cli_live", "quotas": [
            {"label": f"P{i}-5H", "used_frac": 0.1 * i, "pacing": None, "reset": "later"}
            for i in range(1, 6)
        ]}},
    ]}
    out = io.StringIO()
    diag.render_live_quota_pools(out, snapshot, columns=80, line_budget=4)
    text = out.getvalue()
    assert "pools hidden; run diag for all" in text


def test_live_quota_pools_expand_toggle_shows_all_or_hides_with_truthful_hint():
    diag = load_diag()
    snapshot = {"peers": [{"peer": "cc", "raw": {
        "peer": "cc", "source": "cli_live", "quotas": [
            {"label": f"P{i}-5H", "used_frac": 0.1 * i, "pacing": None, "reset": "later"}
            for i in range(1, 6)
        ],
    }}]}
    collapsed = io.StringIO()
    expanded = io.StringIO()

    diag.render_live_quota_pools(
        collapsed, snapshot, columns=80, line_budget=4,
        expanded=False, toggle_available=True,
    )
    diag.render_live_quota_pools(
        expanded, snapshot, columns=80, line_budget=4,
        expanded=True, toggle_available=True,
    )

    collapsed_text = collapsed.getvalue()
    expanded_text = expanded.getvalue()
    assert "P1" not in collapsed_text
    assert "pools hidden (press 'p' to expand)" in collapsed_text
    assert "(all 5 pools; press 'p' to collapse)" in expanded_text
    assert all(f"P{i}" in expanded_text for i in range(1, 6))
    assert "pools hidden" not in expanded_text


def test_dashboard_title_is_engram_not_antigravity(monkeypatch, tmp_path):
    diag = load_diag()
    assert "Engram Multi-Peer Diagnostics" in Path(diag.__file__).read_text(encoding="utf-8")
    assert "Antigravity Collaboration Environment Diagnostics" not in Path(diag.__file__).read_text(encoding="utf-8")



def test_render_attention_session_over_capacity(monkeypatch):
    diag = load_diag()
    render_attention = diag.render_attention
    import io
    snap = {
        "sessions": [
            {"profile": "p1", "model": "m1", "context": {"used": 150, "window": 100}},
            {"profile": "p1", "model": "m1", "context": {"used": 200, "window": 100}},
            {"profile": "p2", "model": "m2", "context": {"used": 150, "window": 200}},
        ]
    }
    
    def fake_read_text(self, *a, **kw):
        return '{"models": {"m1": {"context_limit": 100}}}'
        
    monkeypatch.setattr(Path, "read_text", fake_read_text)
    
    buf = io.StringIO()
    render_attention(buf, snapshot=snap)
    out = buf.getvalue()
    
    assert "[CRIT] p1: SESSION_CONTEXT_OVER_CAPACITY 150%" in out
    assert "[CRIT] p1: SESSION_CONTEXT_OVER_CAPACITY 200%" not in out
    assert "[CRIT] p2: SESSION_CONTEXT_OVER_CAPACITY" not in out

def test_quota_narrow_terminal_degradation_tiers():
    diag = load_diag()
    group = {
        "pool": "ag",
        "primary": {
            "label": "ag",
            "_suffix": "5H",
            "used_frac": 0.5,
            "pacing": {"ratio": 1.7},
            "_eta_full": 5.0,
            "_reset_hours": 3.0,
        },
        "secondary": [
            {
                "label": "ag",
                "_suffix": "7D",
                "used_frac": 0.8,
                "pacing": {"ratio": 0.9},
                "_eta_full": 10.0,
                "_reset_hours": 12.0,
            }
        ]
    }
    
    # Tier 0: full
    t0 = diag._quota_dependency_group_text(group, tier=0)
    assert "resets" in t0
    assert "1.70x" in t0
    assert "1.20x" in t0
    
    # Tier 1: drop reset
    t1 = diag._quota_dependency_group_text(group, tier=1)
    assert "resets" not in t1
    assert "1.70x" in t1
    assert "1.20x" in t1
    
    # Tier 2: drop pacing
    t2 = diag._quota_dependency_group_text(group, tier=2)
    assert "1.70x" not in t2
    assert "1.20x" in t2
    assert "50%" in t2
    assert "80%" in t2
    
    # Tier 3: binding-only floor
    t3 = diag._quota_dependency_group_text(group, tier=3)
    assert "7D" in t3  # Because 12/10 = 1.2x (max urg)
    assert "5H" not in t3
    
