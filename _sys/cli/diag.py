import os
import argparse
import io
import json
import re
import subprocess
from pathlib import Path
import sys
import time
from contextlib import redirect_stdout
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

CLI_DIR = Path(__file__).parent
SYS_DIR = CLI_DIR.parent
PORTABLE_ROOT = SYS_DIR.parent

sys.path.insert(0, str(SYS_DIR / "core"))
import snapshot as _snapshot
from snapshot import (
    telemetry_config, clear_expensive_cache, expensive_source_age_sec,
    SNAPSHOT_TTL_SEC, _SNAPSHOT_CACHE,
    _REAL_BINARIES, EXPENSIVE_SOURCE_TTL_SEC, _CODEX_RATE_LIMIT_CACHE,
    _CLAUDE_USAGE_CACHE, _LOCAL_TTL_SEC, _SYNTHETIC_PEERS, _EFFORT_STRENGTH,
    QUOTA_WARN_FRAC, QUOTA_CRIT_FRAC, STALE_THRESHOLD_SEC,
    _bar, _short, _parse_reset, _rel, _fmt_reset, _real_binary,
    _codex_binary, _codex_rate_limits, _parse_claude_usage_reset,
    _claude_usage_emit, _parse_claude_usage, _claude_usage_quotas,
    _parse_rollout_context, _codex_context, _cached_codex_rate_limits,
    _cached_claude_usage_quotas, _discover_peers, _read_orchestration,
    _read_json_file, gather_peer, _is_synthetic_peer, _fmt_pacing,
    format_quota_bucket, _mask_email, _source_meta, _source_tag,
    _quota_family_for_profile, _filter_profile_buckets, _profile_source,
    _build_profile_rows, _clamped_remaining_from_used_frac,
    _quota_remaining, _context_remaining, _effort_strength,
    _derive_headroom_rows, _next_headroom_target, _fmt_remaining,
    _profile_id_from_scope, _session_context_measured, _build_session_rows,
    _governance_params, _alert, _compute_alerts, normalize_peer,
    collect_snapshot, snapshot_hash, snapshot_failover_target,
)


# --------------------------------------------------------------------------
# Display helpers (no external deps; ASCII-only, color strictly TTY-gated)
# --------------------------------------------------------------------------

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
_ANSI = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m",
    "cyan": "\033[36m",
}


def _c(text, *codes):
    """Wrap text in ANSI codes only when color is enabled."""
    if not _COLOR or not codes:
        return text
    prefix = "".join(_ANSI.get(code, "") for code in codes)
    return f"{prefix}{text}{_ANSI['reset']}"


def _dw(s):
    """Display width: emoji/CJK = 2 cols, combining/ZWJ/VS = 0, ANSI stripped."""
    import unicodedata
    if not isinstance(s, str):
        s = str(s)
    s = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", s)
    w = 0
    for ch in s:
        cp = ord(ch)
        cat = unicodedata.category(ch)
        if cat.startswith("M") or cp in (0x200D, 0x200B) or 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
            continue
        if 0x1F300 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF:
            w += 2
        elif unicodedata.east_asian_width(ch) in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


def _pad(s, width, align="left"):
    """Pad to a target DISPLAY width using _dw (pad RAW text before coloring)."""
    if not isinstance(s, str):
        s = str(s)
    diff = width - _dw(s)
    if diff <= 0:
        return s
    if align == "right":
        return " " * diff + s
    if align == "center":
        return " " * (diff // 2) + s + " " * (diff - diff // 2)
    return s + " " * diff



def _sev_color(used_frac):
    """Map a USED fraction (0..1) to a severity color name."""
    if used_frac >= 0.90:
        return "red"
    if used_frac >= 0.75:
        return "yellow"
    return "green"












# --------------------------------------------------------------------------
# Live quota source for Codex (no local persistence)
# --------------------------------------------------------------------------































# --------------------------------------------------------------------------
# Per-peer metric gathering
# --------------------------------------------------------------------------






# Friendly labels for ag's quota buckets.




# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def _health_label(info):
    if info["empty"]:
        return _c("NO DATA", "dim")
    if info.get("quarantined"):
        return _c("QUARANTINE", "red", "bold")
    if info.get("gate") is False:
        return _c("GATE SHUT", "yellow")
    if info.get("gate") is True:
        return _c("OPEN", "green")
    return _c("?", "dim")


def render_summary(infos):
    """SUMMARY (nearest prompt): per-peer header + sorted quota continuation rows
    (label, glyph, pct, pace, reset), WARN>=0.90, glyph=absent(literal)/emoji."""
    print("\n" + "=" * 60)
    print(_c(" SUMMARY", "bold"))
    print("=" * 60)
    headers = [_pad("PEER", 5), _pad("GATE", 6), _pad("MODEL", 24),
               _pad("CONTEXT(used/win %)", 19), _pad("COST", 9), _pad("SRC", 12)]
    print(_c(" ".join(headers).rstrip(), "dim"))
    for info in infos:
        peer = info["peer"].upper()
        model = info["model"] or "Unknown"
        if len(model) > 24:
            model = model[:21] + "..."
        cost = f"${info['cost']:.4f}" if isinstance(info["cost"], (int, float)) else "-"
        gate_raw = "OPEN" if info.get("gate") else ("QUAR" if info.get("quarantined")
                    else ("SHUT" if info.get("gate") is False else "n/a"))
        gate_cell = _pad(gate_raw, 6)
        if gate_raw == "OPEN":
            gate_cell = _c(gate_cell, "green")
        elif gate_raw == "QUAR":
            gate_cell = _c(gate_cell, "red", "bold")
        elif gate_raw == "SHUT":
            gate_cell = _c(gate_cell, "yellow")
        print(f"{_pad(peer, 5)} {gate_cell} {_pad(model, 24)} "
              f"{_pad(_ctx_cell_raw(info), 19)} {_pad(cost, 9)} {_pad(info.get('source', 'none'), 12)}")
        for q in sorted(info.get("quotas") or [], key=lambda x: str(x.get("label", ""))):
            uf = q.get("used_frac")
            if uf is None:
                continue
            glyph = "🚫" if uf >= 1.0 else ("🔴" if uf >= 0.90
                    else ("🟡" if uf >= 0.75 else "🟢"))
            pct = _pad(f"{uf * 100:.0f}%", 4, align="right")
            pace = _pad(_fmt_pacing(q.get("pacing")), 10)
            warn = "  " + _c("WARN", "red", "bold") if uf >= 0.90 else ""
            print(f"  ↳ {_pad(q.get('label', ''), 6)} {_pad(glyph, 2)} {pct} {pace} resets {q.get('reset') or '?'}{warn}")


def _ctx_cell_raw(info):
    win = _short(info["ctx_window"])
    if not info.get("ctx_known"):
        return f"?/{win}"
    used = _short(info["ctx_used"])
    pct = f"{info['ctx_pct']:.0f}%" if isinstance(info["ctx_pct"], (int, float)) else "--"
    return f"{used}/{win} {pct}"


def render_card(info):
    peer = info["peer"].upper()
    print()
    if info["empty"]:
        print(f"[ {peer} ] " + _c("(no data found)", "dim"))
        return
    head_bits = [info["model"] or "Unknown", _health_label(info)]
    if info.get("agent_state"):
        head_bits.append(str(info["agent_state"]).upper())
    if isinstance(info["cost"], (int, float)):
        head_bits.append(f"${info['cost']:.4f}")
    print(f"[ {_c(peer, 'bold', 'cyan')} ] " + " | ".join(head_bits))
    if info.get("plan_tier"):
        print(_c(f"   Plan: {info['plan_tier']}", "dim"))
    print("-" * 60)
    if not info.get("ctx_known"):
        print(f" Context : (current occupancy n/a)  window {_short(info['ctx_window'])}")
    else:
        cpct = info["ctx_pct"] if isinstance(info["ctx_pct"], (int, float)) else 0
        bar = _bar(cpct / 100.0)
        print(f" Context : {bar} {cpct:>4.0f}% ({_short(info['ctx_used'])}/{_short(info['ctx_window'])})")
    if info.get("quarantine_reason"):
        print(_c(f" Quarantine reason: {info['quarantine_reason']}", "red"))
    if info.get("total_tokens"):
        print(_c(f" Total historical tokens: {info['total_tokens']:,}", "dim"))
    if info.get("sessions") is not None:
        print(_c(f" Sessions today: {info['sessions']}", "dim"))

    profile_health = info.get("profile_health") if isinstance(info.get("profile_health"), dict) else {}
    if str(info.get("peer") or "").lower() == "cc" and "fable" in profile_health:
        print(_c(" Fable quota: F-7D when present; 5h uses C-5H (no F-5H/F-7H bucket)", "dim"))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="diag")
    parser.add_argument("--json", dest="json_mode", action="store_true",
                        help="emit normalized telemetry JSON")
    parser.add_argument("--watch", nargs="?", const=-1.0, type=float, metavar="SECONDS",
                        help="refresh repeatedly; interval defaults to telemetry-config watch.default_interval_sec")
    parser.add_argument("--interval", type=float, metavar="SECONDS",
                        help="alias for --watch SECONDS")
    parser.add_argument("--fresh", action="store_true",
                        help="force one bypass of the 60s expensive-source cache (quota/rate-limits)")
    parser.add_argument("--profiles", action="store_true", help="reserved profile detail view")
    parser.add_argument("--accounts", action="store_true", help="reserved account detail view")
    parser.add_argument("--tokens", action="store_true", help="reserved token detail view")
    parser.add_argument("--sessions", action="store_true", help="reserved session detail view")
    parser.add_argument("--project", action="store_true", help="reserved project detail view")
    parser.add_argument("--headroom", action="store_true", help="derived routing headroom view")
    args = parser.parse_args(argv)

    requested_interval = args.interval if args.interval is not None else args.watch
    args.watch = requested_interval is not None
    # const sentinel (-1.0) = bare --watch -> use config default interval (None).
    args.interval = None if requested_interval == -1.0 else requested_interval
    if args.watch and args.interval is not None:
        min_iv = telemetry_config()["watch"]["min_interval_sec"]
        if args.interval < min_iv:
            parser.error(f"minimum interval is {min_iv} seconds")
        if float(args.interval).is_integer():
            args.interval = int(args.interval)
    return args
















































def _ctx_session_cell(context):
    context = context or {}
    used = context.get("used_tokens")
    window = context.get("window_tokens")
    if not isinstance(used, (int, float)):
        return "absent"
    pct = context.get("utilization_pct")
    pct_s = f" {pct:.0f}%" if isinstance(pct, (int, float)) else ""
    win_s = _short(window) if isinstance(window, (int, float)) else "?"
    return f"{_short(used)}/{win_s}{pct_s}"


# Quota alert thresholds (§7). Context thresholds come from governance_params.json.
# Source data older than this is flagged SOURCE_STALE (status logs only refresh when
# that peer's statusline renders, so an idle peer's quota/context can be stale) (D1).











_FRAME_NOW = object()


def _frame_dt(value=_FRAME_NOW):
    if value is _FRAME_NOW:
        return datetime.now().astimezone()
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        if isinstance(value, (int, float)):
            dt = _parse_reset(value)
            return dt.astimezone() if dt else None
        text = str(value).strip()
        if not text:
            return None
        if text.replace(".", "", 1).isdigit():
            dt = _parse_reset(text)
            return dt.astimezone() if dt else None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt.astimezone()


def _fmt_frame_dt(value):
    dt = _frame_dt(value)
    return dt.strftime("%Y-%m-%d %H:%M:%S %z") if dt else "absent"


def _snapshot_age_seconds(snapshot, now=None):
    now_dt = _frame_dt() if now is None else _frame_dt(now)
    observed = _frame_dt((snapshot or {}).get("observed_at"))
    if not now_dt or not observed:
        return None
    return max(0, int((now_dt - observed).total_seconds()))


def _limited_reset_rows(snapshot, now=None):
    """Current profile-level usage limits sorted by reset countdown."""
    snapshot = snapshot or {}
    now_dt = _frame_dt() if now is None else _frame_dt(now)
    active_profiles = {
        str(row.get("profile"))
        for row in snapshot.get("profiles") or []
        if row.get("profile")
    }
    rows = []
    for rec in snapshot.get("peers") or []:
        peer = rec.get("peer")
        if not peer:
            continue
        health = (rec.get("domains") or {}).get("health") or {}
        profiles = health.get("profiles") or (rec.get("raw") or {}).get("profile_health") or {}
        if not isinstance(profiles, dict):
            continue
        for name, profile_health in profiles.items():
            if not isinstance(profile_health, dict):
                continue
            rate_state = profile_health.get("rate_limit_state")
            if not (isinstance(rate_state, dict) and rate_state.get("limited") is True):
                continue
            profile_id = str(name) if "." in str(name) else f"{peer}.{name}"
            if active_profiles and profile_id not in active_profiles:
                continue
            reset_at = _frame_dt(rate_state.get("reset_at"))
            remaining = None
            if reset_at and now_dt:
                remaining = int((reset_at - now_dt).total_seconds())
                if remaining <= 0:
                    continue
            rows.append({
                "profile": profile_id,
                "reset_at": reset_at,
                "remaining_sec": remaining,
            })
    return sorted(rows, key=lambda row: (
        row["remaining_sec"] if isinstance(row.get("remaining_sec"), int) else float("inf"),
        row.get("profile") or "",
    ))


def render_frame_footer(stdout=None, snapshot=None, rendered_at=None):
    out = stdout or sys.stdout
    snapshot = snapshot or {}
    rendered = _frame_dt() if rendered_at is None else _frame_dt(rendered_at)
    tc = telemetry_config()
    ttl = tc.get("ttl", {})
    snapshot_ttl = ttl.get("snapshot_sec", "absent")
    local_ttl = ttl.get("local_sec", "absent")
    expensive_ttl = ttl.get("expensive_source_sec", "absent")
    snapshot_age = _snapshot_age_seconds(snapshot, rendered)
    snapshot_age_txt = f"{snapshot_age}s" if isinstance(snapshot_age, int) else "absent"
    expensive_age = expensive_source_age_sec()
    expensive_age_txt = f"{expensive_age}s" if isinstance(expensive_age, int) else "absent"

    out.write("\n" + "=" * 60 + "\n")
    out.write(_c(" FRAME", "bold") + "\n")
    out.write("=" * 60 + "\n")
    out.write(
        f"TTL snapshot refreshed {_fmt_frame_dt(snapshot.get('observed_at'))} "
        f"(age {snapshot_age_txt} / TTL {snapshot_ttl}s); "
        f"local TTL {local_ttl}s; expensive quota cache {expensive_age_txt} / TTL {expensive_ttl}s\n"
    )
    out.write(f"RENDERED {_fmt_frame_dt(rendered)}\n")

    rows = _limited_reset_rows(snapshot, rendered)
    if not rows:
        out.write("LIMITED RESETS none\n")
        return
    out.write("LIMITED RESETS\n")
    for row in rows:
        remaining = row.get("remaining_sec")
        remaining_txt = _rel(remaining) if isinstance(remaining, int) else "absent"
        out.write(
            f"  {str(row.get('profile') or 'absent'):<22} "
            f"{remaining_txt:<10} resets {_fmt_frame_dt(row.get('reset_at'))}\n"
        )


def render_dashboard(stdout=None, watch_mode=False):
    out = stdout or sys.stdout
    with redirect_stdout(out):
        print("=" * 60)
        print(_c(" Antigravity Collaboration Environment Diagnostics", "bold"))
        print("=" * 60)
        print(_c(" Reset times shown in local time. Set NO_COLOR=1 to disable color.", "dim"))

        print("\n[ROOM & HUB STATUS]")
        hub_py = SYS_DIR / "core" / "hub.py"
        if hub_py.exists():
            # Capture (not stream) so watch-mode double-buffering can blit the
            # whole frame in one write; direct stdout= would bypass the buffer.
            if watch_mode:
                res = subprocess.run(["python", str(hub_py), "status"],
                                     capture_output=True, text=True)
                print(getattr(res, "stdout", "") or "", end="")
            else:
                out.flush()
                subprocess.run(["python", str(hub_py), "status"], stdout=out)
        else:
            print("hub.py not found.")

        snapshot = collect_snapshot()
        infos = [p["raw"] for p in snapshot["peers"]]

        # Section order is the unanimous FP-4 spec (2026-07-03, reconfirmed
        # 2026-07-08 w/ ag+cx): static first, volatile nearest the prompt —
        # PROFILES&ROUTING → DETAIL → SESSIONS/HEADROOM → ALERTS → POLICY →
        # SUMMARY → FRAME. SUMMARY is the final CONTENT panel (nearest the
        # prompt among domain-data panels); POLICY must precede it. FRAME is
        # a meta-footer ABOUT the render itself (snapshot staleness/TTL age,
        # rendered-at timestamp, imminent rate-limit resets) — distinct from
        # content panels, so it is always the true last line of output, after
        # SUMMARY (ag verdict 2026-07-08, re-confirmed after this same rule
        # was silently re-broken once already today — see backlog-5whys-
        # consensus-2026-07-08-round3.md for why this class of regression
        # keeps recurring). Order is expressed as ONE list below (not
        # scattered print() calls) so it is structurally enforced, not just
        # documented in a comment that can be quietly outpaced by an edit.
        def _render_panel_header(title):
            print("\n" + "=" * 60)
            print(_c(title, "bold"))
            print("=" * 60)

        def _render_peer_detail():
            for info in infos:
                render_card(info)

        def _render_active_sessions_and_headroom():
            render_sessions(out, snapshot=snapshot)
            target = _next_headroom_target(_derive_headroom_rows(snapshot))
            if target:
                risk = " TIER RISK" if target.get("tier_risk") else ""
                out.write(f"NEXT FAILOVER TARGET: {target.get('profile')} "
                          f"headroom {_fmt_remaining(target.get('headroom'))}{risk}\n")

        def _render_alerts():
            alert_count = 0
            for rec in snapshot["peers"]:
                for alert in rec.get("alerts") or []:
                    sev = str(alert.get("severity") or "info").upper()
                    print(f"[{sev}] {rec.get('peer')}: {alert.get('code')} {alert.get('message')}")
                    alert_count += 1
            if not alert_count:
                print("(no alerts)")

        content_panels = [
            (" PROFILES & ROUTING", lambda: render_profiles(out, snapshot=snapshot)),
            (" PEER DETAIL", _render_peer_detail),
            (" ACTIVE SESSIONS & HEADROOM", _render_active_sessions_and_headroom),
            (" ALERTS", _render_alerts),
            (" POLICY", lambda: render_policy(out)),
            (" SUMMARY", lambda: render_summary(infos)),  # self-prints its own header
        ]

        for title, render_fn in content_panels:
            if title == " SUMMARY":
                render_fn()
                continue
            _render_panel_header(title)
            render_fn()

        render_frame_footer(out, snapshot=snapshot)


def _load_routing_cfg():
    try:
        return json.loads((SYS_DIR / "ai" / "routing-config.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def render_policy(stdout=None):
    """POLICY (MECE §6): effective operational knobs + their config source path.
    'what is happening' (other panels) vs 'why' (the policy that governs it).
    Operational knobs only — not a full config dump (design 2026-07-08 §3)."""
    out = stdout or sys.stdout
    tc = telemetry_config()
    rc = _load_routing_cfg()
    tlb = rc.get("token_load_balancing", {}) or {}
    hb = tlb.get("headroom_bias", {}) or {}
    ca = tlb.get("context_affinity", {}) or {}
    rows = [
        ("snapshot TTL", f"{tc['ttl']['snapshot_sec']}s", "telemetry-config.json:ttl.snapshot_sec"),
        ("expensive-source TTL", f"{tc['ttl']['expensive_source_sec']}s", "telemetry-config.json:ttl.expensive_source_sec"),
        ("local TTL", f"{tc['ttl']['local_sec']}s", "telemetry-config.json:ttl.local_sec"),
        ("probe deadline", f"{tc['probe']['deadline_sec']}s", "telemetry-config.json:probe.deadline_sec"),
        ("quota warn / crit", f"{tc['display']['warn_frac']:.0%} / {tc['display']['crit_frac']:.0%}", "telemetry-config.json:display"),
        ("watch interval / min", f"{tc['watch']['default_interval_sec']}s / {tc['watch']['min_interval_sec']}s", "telemetry-config.json:watch"),
        ("watch sync-output", str(tc['watch']['sync_output']), "telemetry-config.json:watch.sync_output"),
        ("headroom floor", str(tlb.get("effective_headroom_floor", "-")), "routing-config.json:token_load_balancing.effective_headroom_floor"),
        ("headroom bias band", f"{hb.get('min','-')}..{hb.get('max','-')}", "routing-config.json:token_load_balancing.headroom_bias"),
        ("bulk-exclude profiles", ",".join(tlb.get("bulk_exclude_profiles", []) or []) or "(none)", "routing-config.json:token_load_balancing.bulk_exclude_profiles"),
        ("context affinity", ("on" if ca.get("enabled") else "off") if ca else "unset", "routing-config.json:token_load_balancing.context_affinity"),
        ("LB enabled", str(tlb.get("enabled", "-")), "routing-config.json:token_load_balancing.enabled"),
    ]
    out.write(f"{_pad('KNOB', 22)} {_pad('VALUE', 16)} {_c('SOURCE', 'dim')}\n")
    for knob, val, src in rows:
        out.write(f"{_pad(knob, 22)} {_pad(val, 16)} {_c(src, 'dim')}\n")
    # Transparency (peers unanimous): show how old the cached quota probe is, so a
    # --watch frame's quota/pacing isn't mistaken for real-time. --fresh forces a bypass.
    age = expensive_source_age_sec()
    age_txt = f"cached {age}s ago (TTL {tc['ttl']['expensive_source_sec']}s; --fresh to bypass)" \
        if isinstance(age, int) else "not yet probed"
    out.write(f"{_pad('quota probe age', 22)} {_c(age_txt, 'dim')}\n")


def emit_json_snapshot(stdout=None):
    out = stdout or sys.stdout
    out.write(json.dumps(collect_snapshot(), ensure_ascii=False, sort_keys=True) + "\n")
    out.flush()


def _blit_frame(out, text, sync):
    """Double-buffered in-place repaint (token-session-policy-design-2026-07-08 §4).

    No alt-screen (scrollback preserved). Build the whole frame off-screen, then
    blit: optional synchronized-output wrapper (?2026h/l — ignored by terminals
    that don't support it), cursor-home (\\033[H), each line cleared to EOL
    (\\033[K) so it overwrites in place, and a final erase-to-end-of-screen
    (\\033[J) so a shorter frame leaves no stale tail. Replaces the old
    \\033[2J full-clear that caused flicker.
    """
    lines = text.split("\n")
    body = "\r\n".join(line + "\033[K" for line in lines)
    seq = ("\033[?2026h" if sync else "") + "\033[H" + body + "\033[J" + \
          ("\033[?2026l" if sync else "")
    out.write(seq)
    out.flush()


def run_watch(interval=None, json_mode=False, stdout=None, sleep=time.sleep, max_frames=None):
    out = stdout or sys.stdout
    wcfg = telemetry_config()["watch"]
    if interval is None:
        interval = wcfg.get("default_interval_sec", 5)
    interval = max(interval, wcfg.get("min_interval_sec", 2))
    is_tty = bool(getattr(out, "isatty", lambda: False)())
    sync_mode = wcfg.get("sync_output", "auto")
    sync = is_tty and (sync_mode == "on" or (sync_mode == "auto"))
    frames = 0
    try:
        if is_tty and not json_mode:
            out.write("\033[2J\033[H")  # one-time clear to start from a clean screen
        while max_frames is None or frames < max_frames:
            if json_mode:
                emit_json_snapshot(out)
            elif is_tty:
                buf = io.StringIO()
                render_dashboard(buf, watch_mode=True)
                _blit_frame(out, buf.getvalue(), sync)
            else:
                render_dashboard(out, watch_mode=True)  # non-TTY: plain frames
                out.flush()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
            sleep(interval)
    except KeyboardInterrupt:
        return 130
    return 0


# --------------------------------------------------------------------------
# Detail views (§6.2) — all strictly read-only
# --------------------------------------------------------------------------

def render_profiles(stdout=None, snapshot=None):
    """PROFILES & ROUTING (MECE topology only): profile | model | eff | tier |
    ctx(declared window) | state | src. No quota (quota lives in SUMMARY)."""
    out = stdout or sys.stdout
    if snapshot is None:
        snapshot = collect_snapshot()
    rows = snapshot.get("profiles") or []
    if not rows:
        out.write("(profile rows unavailable)\n")
        return
    headers = [_pad("PROFILE", 22), _pad("MODEL", 28), _pad("EFF", 5),
               _pad("TIER", 5), _pad("CTX", 12), _pad("STATE", 12), _pad("SRC", 13)]
    out.write(" ".join(headers).rstrip() + "\n")

    def _fmt_src(tag):
        return {"orchestration": "decl", "cli_live": "cliv", "app_server": "app",
                "statusline": "live", "health": "hlth", "absent": "-"}.get(tag, str(tag)[:4])

    for row in rows:
        sources = row.get("sources") or {}
        model = row.get("model") or "absent"
        if sources.get("model") == "orchestration" and model != "absent":
            model = f"[decl] {model}"
        effort = str(row.get("effort") or "absent")[:5]
        tier = str(row.get("cost_tier") or "absent")[:5]
        ctx = row.get("context") or {}
        win = ctx.get("window_tokens")
        ctx_val = _short(win) if win is not None else "absent"
        state = row.get("state") or "unknown"
        src = f"c:{_fmt_src(sources.get('context'))} q:{_fmt_src(sources.get('quota'))}"

        c_state = _pad(state, 12)
        if state == "eligible":
            c_state = _c(c_state, "green")
        elif state == "manual_only":
            c_state = _c(c_state, "yellow")
        out.write(f"{_pad(str(row.get('profile') or 'absent'), 22)} {_pad(str(model)[:28], 28)} "
                  f"{_pad(effort, 5)} {_pad(tier, 5)} {_pad(ctx_val, 12)} {c_state} {_pad(src, 13)}\n")


def render_headroom(stdout=None, snapshot=None):
    """Derived failover/headroom view. Consumes collect_snapshot only."""
    out = stdout or sys.stdout
    if snapshot is None:
        snapshot = collect_snapshot()
    rows = _derive_headroom_rows(snapshot)
    target = _next_headroom_target(rows)
    if target:
        risk = " TIER RISK" if target.get("tier_risk") else ""
        out.write(f"NEXT {target.get('profile')} headroom {_fmt_remaining(target.get('headroom'))}{risk}\n")
    else:
        out.write("NEXT absent\n")
    out.write("PROFILE                HEADROOM QUOTA    CTX      EFFORT   STATE       SOURCE\n")
    for row in rows:
        sources = row.get("sources") or {}
        source_str = f"ctx:{sources.get('context') or '?'} q:{sources.get('quota') or '?'}"
        risk = " TIER RISK" if row.get("tier_risk") else ""
        out.write(
            f"{str(row.get('profile') or '?'):<22} "
            f"{_fmt_remaining(row.get('headroom')):<8} "
            f"{_fmt_remaining(row.get('quota_remaining')):<8} "
            f"{_fmt_remaining(row.get('context_remaining')):<8} "
            f"{str(row.get('effort') or '?'):<8} "
            f"{str(row.get('state') or 'unknown'):<11} "
            f"{source_str}{risk}\n"
        )


def render_accounts(stdout=None):
    """Redacted account/plan view (§5) — masked email only, never raw ids."""
    out = stdout or sys.stdout
    out.write("PEER   PLAN                  EMAIL\n")
    for p in collect_snapshot()["peers"]:
        acct = p.get("domains", {}).get("account", {})
        out.write(f"{str(p.get('peer') or '?'):<6} {str(acct.get('plan_tier') or '-'):<21} "
                  f"{acct.get('email') or '-'}\n")


def render_tokens(stdout=None):
    """Context / cost / token-history view. Null renders as 'unknown', never 0."""
    out = stdout or sys.stdout
    out.write("PEER   COST         CONTEXT             TOTAL_TOKENS\n")
    for p in collect_snapshot()["peers"]:
        dom = p.get("domains", {})
        cost = dom.get("cost", {}).get("total_cost_usd")
        cost_s = f"${cost:.4f}" if isinstance(cost, (int, float)) else "unknown"
        ctx = dom.get("context", {})
        used, win = ctx.get("used_tokens"), ctx.get("window_tokens")
        used_s = _short(used) if isinstance(used, (int, float)) else "unknown"
        win_s = _short(win) if isinstance(win, (int, float)) else "?"
        tot = dom.get("cost", {}).get("total_tokens")
        tot_s = f"{tot:,}" if isinstance(tot, (int, float)) else "unknown"
        out.write(f"{str(p.get('peer') or '?'):<6} {cost_s:<12} {used_s + '/' + win_s:<19} {tot_s}\n")


def render_sessions(stdout=None, snapshot=None):
    """Session state / continuity view."""
    out = stdout or sys.stdout
    if snapshot is None:
        snapshot = collect_snapshot()
    rows = snapshot.get("sessions") or []
    if not rows:
        out.write("(no active sessions)\n")
        return
    out.write("PROFILE                MODEL                      STATUS    LEASE     LAST_USED           CTX             SCOPE\n")
    for row in rows:
        lease_status = (row.get("lease") or {}).get("status") or "absent"
        last_used = str(row.get("last_used_at") or "-")[:19]
        out.write(
            f"{str(row.get('profile') or '?'):<22} "
            f"{str(row.get('model') or 'absent')[:26]:<26} "
            f"{str(row.get('status') or 'unknown'):<9} "
            f"{str(lease_status):<9} "
            f"{last_used:<19} "
            f"{_ctx_session_cell(row.get('context')):<15} "
            f"{row.get('scope_key') or '-'}\n"
        )


def _git_project_status():
    """Read-only git working-tree summary. Bounded, no shell, no network,
    GIT_OPTIONAL_LOCKS=0 (never writes index). Degrades to 'unknown' on failure."""
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    try:
        r = subprocess.run(["git", "-C", str(PORTABLE_ROOT), "status", "--porcelain"],
                           capture_output=True, text=True, timeout=10, env=env)
        if r.returncode != 0:
            return {"state": "unknown"}
        changed = len([ln for ln in r.stdout.splitlines() if ln.strip()])
        return {"state": "dirty" if changed else "clean", "changed": changed}
    except Exception:
        return {"state": "unknown"}


def render_project(stdout=None):
    out = stdout or sys.stdout
    st = _git_project_status()
    out.write("[PROJECT]\n")
    line = f" git working tree: {st.get('state')}"
    if st.get("changed") is not None:
        line += f" ({st['changed']} changed)"
    out.write(line + "\n")


def main(argv=None, stdout=None):
    args = parse_args(argv)
    out = stdout or sys.stdout
    if getattr(args, "fresh", False):
        clear_expensive_cache()  # opt-in: force one bypass of the 60s quota cache
    if args.watch:
        return run_watch(interval=args.interval, json_mode=args.json_mode, stdout=out)
    if args.json_mode:
        emit_json_snapshot(out)
        return 0
    if args.profiles:
        render_profiles(out); return 0
    if args.accounts:
        render_accounts(out); return 0
    if args.tokens:
        render_tokens(out); return 0
    if args.sessions:
        render_sessions(out); return 0
    if args.project:
        render_project(out); return 0
    if args.headroom:
        render_headroom(out); return 0
    render_dashboard(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
