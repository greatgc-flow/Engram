import os
import argparse
import io
import json
import re
import shutil
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


def _elide_display(value, width):
    """Elide text to a display-cell width without splitting ANSI/wide cells."""
    text = str(value)
    if width is None or _dw(text) <= width:
        return text
    if width <= 0:
        return ""
    if width <= 3:
        return "." * width
    marker = "..."
    target = width - _dw(marker)
    used = 0
    chars = []
    had_ansi = False
    pos = 0
    while pos < len(text):
        ansi = re.match(r"\x1b\[[0-9;?]*[a-zA-Z]", text[pos:])
        if ansi:
            chars.append(ansi.group(0))
            pos += len(ansi.group(0))
            had_ansi = True
            continue
        char = text[pos]
        char_width = _dw(char)
        if used + char_width > target:
            break
        chars.append(char)
        used += char_width
        pos += 1
    reset = _ANSI["reset"] if had_ansi else ""
    return "".join(chars) + marker + reset



def _sev_color(used_frac):
    """Map a USED fraction (0..1) to a severity color name."""
    if used_frac >= QUOTA_CRIT_FRAC:
        return "red"
    if used_frac >= QUOTA_WARN_FRAC:
        return "yellow"
    return "green"


_SOURCE_CODES = {
    "cli_live": "CLI",
    "app_server": "APP",
    "statusline": "STAT",
    "empirical_probe": "PROBE",
    "declared, unverified": "DECL",
    "absent": "ABS",
}


def _source_code(value):
    """Render source provenance with one stable, compact vocabulary."""
    key = str(value or "").strip().lower()
    canonical = {
        "cli_live": "cli_live", "app_server": "app_server",
        "app-server": "app_server", "statusline": "statusline",
        "live": "statusline", "health": "statusline",
        "empirical_probe": "empirical_probe",
        "orchestration": "declared, unverified", "decl": "declared, unverified",
        "declared": "declared, unverified",
    }.get(key, "absent")
    return _SOURCE_CODES[canonical]


def _source_legend():
    return ("SRC LEGEND: CLI=cli_live APP=app_server STAT=statusline "
            "PROBE=empirical_probe DECL=declared, unverified ABS=absent")


def _intelligence_display(evidence):
    """Compact, explicitly declared D3 evidence label for profile detail."""
    if not isinstance(evidence, dict):
        return "absent"
    if evidence.get("source_kind") != "declared" or evidence.get("verification") != "unverified":
        return "absent"
    estimate = evidence.get("estimate")
    if not isinstance(estimate, dict):
        return "absent"

    def fmt(value):
        return f"{value:g}" if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    if estimate.get("kind") == "point":
        value = fmt(estimate.get("value"))
        return f"~{value} [decl]" if value is not None else "absent"
    if estimate.get("kind") == "range":
        minimum, maximum = fmt(estimate.get("min")), fmt(estimate.get("max"))
        if minimum is not None and maximum is not None:
            return f"~{minimum}-{maximum} [decl]"
    return "absent"


def _peer_state_label(info):
    """Canonical peer-state precedence for every peer-level renderer."""
    if info.get("quarantined"):
        return "QUARANTINE"
    if info.get("gate") is False:
        return "GATE SHUT"
    if info.get("gate") is True:
        return "OPEN"
    return "UNKNOWN"


def _peer_state_cell(info, width=11):
    state = _peer_state_label(info)
    cell = _pad(state, width)
    if state == "OPEN":
        return _c(cell, "green")
    if state == "QUARANTINE":
        return _c(cell, "red", "bold")
    if state == "GATE SHUT":
        return _c(cell, "yellow")
    return _c(cell, "dim")


def _severity_glyph(*, used_frac=None, pacing=None):
    """One quota/pacing glyph source with an ASCII fallback for plain output."""
    if isinstance(used_frac, (int, float)):
        level = "stop" if used_frac >= 1.0 else (
            "crit" if used_frac >= QUOTA_CRIT_FRAC else (
                "warn" if used_frac >= QUOTA_WARN_FRAC else "ok"))
    else:
        status = str((pacing or {}).get("status") or "").lower()
        indicator = str((pacing or {}).get("indicator") or "")
        level = "crit" if status in {"danger", "critical", "crit"} or indicator == "🔴" else (
            "warn" if status in {"warning", "warn"} or indicator == "🟡" else "ok")
    if not _COLOR:
        return {"stop": "[CRIT]", "crit": "[CRIT]", "warn": "[WARN]", "ok": "[OK]"}[level]
    return {"stop": "🚫", "crit": "🔴", "warn": "🟡", "ok": "🟢"}[level]


def _pacing_cell(pacing):
    if not isinstance(pacing, dict) or not isinstance(pacing.get("ratio"), (int, float)):
        return ""
    return f"{_severity_glyph(pacing=pacing)} {pacing['ratio']:.2f}x"


def _arbiter_model_ids() -> set:
    """Return routing-config.json's token_load_balancing.arbiter_models as a set."""
    data, _observed = _read_json_file(SYS_DIR / "ai" / "routing-config.json")
    if not isinstance(data, dict):
        return set()
    balancing = data.get("token_load_balancing")
    if not isinstance(balancing, dict):
        return set()
    models = balancing.get("arbiter_models")
    return {str(model) for model in models} if isinstance(models, list) else set()












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

def render_summary(infos):
    """SUMMARY (nearest prompt): per-peer header + sorted quota continuation rows
    (label, glyph, pct, pace, reset), WARN>=0.90, glyph=absent(literal)/emoji."""
    print("\n" + "=" * 60)
    print(_c(" SUMMARY", "bold"))
    print("=" * 60)
    headers = [_pad("PEER", 5), _pad("STATE", 11),
               _pad("CONTEXT(used/win %)", 19), _pad("COST", 9), _pad("SRC", 12)]
    print(_c(" ".join(headers).rstrip(), "dim"))
    for info in infos:
        peer = info["peer"].upper()
        cost = f"${info['cost']:.4f}" if isinstance(info["cost"], (int, float)) else "-"
        state_cell = _peer_state_cell(info)
        print(f"{_pad(peer, 5)} {state_cell} "
              f"{_pad(_ctx_cell_raw(info), 19)} {_pad(cost, 9)} {_pad(_source_code(info.get('source')), 12)}")
        visible_quotas = [
            quota for quota in (info.get("quotas") or [])
            if quota.get("used_frac") is not None
        ]
        for q in sorted(visible_quotas, key=lambda x: (-x["used_frac"], str(x.get("label", "")))):
            uf = q.get("used_frac")
            glyph = _severity_glyph(used_frac=uf)
            pct = _pad(f"{uf * 100:.0f}%", 4, align="right")
            pace = _pad(_pacing_cell(q.get("pacing")), 12)
            warn = "  " + _c("WARN", "red", "bold") if uf >= QUOTA_CRIT_FRAC else ""
            print(f"  ↳ {_pad(q.get('label', ''), 6)} {_pad(glyph, 2)} {pct} {pace} resets {q.get('reset') or '?'}{warn}")

    print(_c(_source_legend(), "dim"))


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
    head_bits = [info["model"] or "Unknown", _peer_state_cell(info, 0)]
    if info.get("agent_state"):
        head_bits.append(str(info["agent_state"]).upper())
    if isinstance(info["cost"], (int, float)):
        head_bits.append(f"${info['cost']:.4f}")
    print(f"[ {_c(peer, 'bold', 'cyan')} ] " + " | ".join(head_bits))
    if info.get("plan_tier"):
        print(_c(f"   Plan: {info['plan_tier']}", "dim"))
    print(_c(f"   Source: {_source_code(info.get('source'))}", "dim"))
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
    peer = str(info.get("peer") or "").lower()
    active_arbiters = {
        f"{peer}.{profile_name}" for profile_name in profile_health
    } & _arbiter_model_ids()
    has_f_family = any(
        str(quota.get("label") or "").startswith("F-")
        for quota in info.get("quotas", [])
        if isinstance(quota, dict)
    )
    if active_arbiters and has_f_family:
        print(_c(
            " Arbiter quota: F-7D when present; 5h uses C-5H "
            "(no F-5H/F-7H bucket)",
            "dim",
        ))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="diag")
    parser.add_argument("--json", dest="json_mode", action="store_true",
                        help="emit normalized telemetry JSON")
    watch_group = parser.add_mutually_exclusive_group()
    watch_group.add_argument("--watch", nargs="?", const=-1.0, type=float, metavar="SECONDS",
                        help="refresh repeatedly; interval defaults to telemetry-config watch.default_interval_sec")
    watch_group.add_argument("--live", nargs="?", const=-1.0, type=float, metavar="SECONDS",
                        help="compact live SUMMARY + recent sessions + FRAME HUD")
    watch_group.add_argument("--watch-summary", dest="watch_summary_compat", nargs="?",
                        const=-1.0, type=float, metavar="SECONDS", help=argparse.SUPPRESS)
    parser.add_argument("--interval", type=float, metavar="SECONDS",
                        help="interval alias for --watch/--live SECONDS")
    parser.add_argument("--fresh", action="store_true",
                        help="force one bypass of the 60s expensive-source cache (quota/rate-limits)")
    parser.add_argument("--profiles", action="store_true", help="reserved profile detail view")
    parser.add_argument("--peers", action="store_true", help="peer detail cards")
    parser.add_argument("--accounts", action="store_true", help="reserved account detail view")
    parser.add_argument("--tokens", action="store_true", help="reserved token detail view")
    parser.add_argument("--sessions", action="store_true", help="reserved session detail view")
    parser.add_argument("--project", action="store_true", help="reserved project detail view")
    parser.add_argument("--headroom", action="store_true", help="derived routing headroom view")
    args = parser.parse_args(argv)

    live_value = args.live if args.live is not None else args.watch_summary_compat
    live_mode = live_value is not None
    requested_interval = args.interval if args.interval is not None else (
        live_value if live_mode else args.watch
    )
    args.watch = requested_interval is not None and not live_mode
    args.live = live_mode
    args.watch_summary = live_mode  # compatibility for callers using the old parsed attribute
    # const sentinel (-1.0) = bare --watch/--live -> use config default interval (None).
    args.interval = None if requested_interval == -1.0 else requested_interval
    if (args.watch or args.live) and args.interval is not None:
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


def _session_sort_key(row):
    last_used = _frame_dt(row.get("last_used_at"))
    return (
        last_used is not None,
        last_used.timestamp() if last_used is not None else float("-inf"),
        str(row.get("profile") or ""),
    )


def _session_display_sort_key(peer, row):
    """Global newest-first display order; selection remains peer-fair."""
    last_used = _frame_dt(row.get("last_used_at"))
    return (
        last_used is None,
        -(last_used.timestamp()) if last_used is not None else 0.0,
        _session_profile(row, peer),
        str(row.get("scope_key") or ""),
    )


def _session_age_text(last_used_at, now):
    last_used = _frame_dt(last_used_at)
    if last_used is None:
        return "?"
    seconds = max(0, int((now - last_used).total_seconds()))
    if seconds < 60:
        return "now"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _session_profile(row, peer):
    profile = str(row.get("profile") or peer or "?")
    if peer and profile not in (peer, "?") and "." not in profile:
        profile = f"{peer}.{profile}"
    return profile


def _session_scope(row, profile):
    scope = str(row.get("scope_key") or "-")
    suffix = f":{profile}"
    if scope.endswith(suffix):
        scope = scope[:-len(suffix)] or "-"
    return scope


def _session_lease_state(row, now):
    """Truthful lease-state token; post-mortem rows remain visible."""
    lease = row.get("lease") or {}
    status = str(lease.get("status") or "absent").upper()
    if status == "OPEN":
        expires = _frame_dt(lease.get("expires_at"))
        if expires is None or now is None or expires <= now:
            status = "STALE"
    return f"[{status}]"


def _session_room_state(row, profile, now, width):
    state = _session_lease_state(row, now)
    room = _session_scope(row, profile)
    if width is None:
        return f"{room} {state}"
    state_width = _dw(state)
    room_width = width - state_width - 1
    if room_width <= 0:
        return _elide_display(state, width)
    return f"{_elide_display(room, room_width)} {state}"


def _session_ctx_text(row):
    pct = (row.get("context") or {}).get("utilization_pct")
    return f"{pct:.0f}%" if isinstance(pct, (int, float)) else "absent"


def _compact_session_row(row, peer, now, columns):
    profile = _session_profile(row, peer)
    age = _session_age_text(row.get("last_used_at"), now)
    ctx = _session_ctx_text(row)
    room_state = _session_room_state(row, profile, now, None)
    if columns is None:
        return f"{profile} {age} {ctx} {room_state}"
    profile_cell = _pad(_elide_display(profile, 20), 20)
    prefix = f"{profile_cell} {_pad(age, 5, align='right')} {_pad(ctx, 7)}"
    if columns is not None and columns >= 120:
        model = _pad(_elide_display(str(row.get("model") or "absent"), 24), 24)
        prefix = f"{prefix} {model}"
    room_width = columns - _dw(prefix) - 1
    if room_width <= 0:
        return _elide_display(prefix, columns)
    return f"{prefix} {_session_room_state(row, profile, now, room_width)}"


def _session_digest(row, peer, count, now, columns):
    profile = _session_profile(row, peer)
    age = _session_age_text(row.get("last_used_at"), now)
    ctx = _session_ctx_text(row)
    room_state = _session_room_state(row, profile, now, None)
    text = f"{str(peer).upper()}: {profile} {age} {ctx} {room_state} ({count})"
    return _elide_display(text, columns)


def render_recent_sessions(out, snapshot, *, now=None, columns=80, line_budget=None):
    """Compact recent sessions from one supplied snapshot; never recollects."""
    if line_budget is not None:
        line_budget = max(0, int(line_budget))
        if line_budget == 0:
            return
    rendered_now = _frame_dt() if now is None else _frame_dt(now)
    rendered_now = rendered_now or _frame_dt()

    groups = {}
    for row in snapshot.get("sessions") or []:
        if not isinstance(row, dict) or not row.get("peer"):
            continue
        groups.setdefault(str(row["peer"]), []).append(row)
    if not groups:
        out.write(_elide_display("RECENT SESSIONS none", columns) + "\n")
        return

    snapshot_peer_order = [
        str(rec.get("peer")) for rec in snapshot.get("peers") or []
        if isinstance(rec, dict) and rec.get("peer") in groups
    ]
    peer_order = snapshot_peer_order + sorted(set(groups) - set(snapshot_peer_order))
    capped = {
        peer: sorted(groups[peer], key=_session_sort_key, reverse=True)[:3]
        for peer in peer_order
    }

    round_robin = []
    for rank in range(3):
        for peer in peer_order:
            if rank < len(capped[peer]):
                round_robin.append((peer, capped[peer][rank]))

    title = _elide_display("RECENT SESSIONS (newest first; max 3/peer)", columns)
    header_prefix = f"{_pad('PROFILE', 20)} {_pad('AGE', 5, align='right')} {_pad('CTX', 7)}"
    if columns is not None and columns >= 120:
        header_prefix = f"{header_prefix} {_pad('MODEL', 24)}"
    header = header_prefix if columns is not None and _dw(header_prefix) >= columns else f"{header_prefix} ROOM / STATE"
    header = _elide_display(header, columns)

    candidate_count = len(round_robin)
    if line_budget is None:
        selected = round_robin
        hidden = 0
    else:
        available = max(0, line_budget - 2)
        row_slots = available
        if candidate_count > row_slots:
            row_slots = max(0, row_slots - 1)

        # If every peer cannot receive its newest detailed row, use a digest.
        if row_slots < len(peer_order) and candidate_count > row_slots:
            digest_peer_order = sorted(
                peer_order,
                key=lambda peer: _session_display_sort_key(peer, capped[peer][0]),
            )
            if line_budget >= 1 + len(peer_order):
                lines = [title]
                lines.extend(
                    _session_digest(capped[peer][0], peer, len(capped[peer]), rendered_now, columns)
                    for peer in digest_peer_order
                )
            else:
                items = []
                for peer in digest_peer_order:
                    row = capped[peer][0]
                    profile = _session_profile(row, peer)
                    age = _session_age_text(row.get("last_used_at"), rendered_now)
                    ctx = _session_ctx_text(row)
                    room_state = _session_room_state(row, profile, rendered_now, None)
                    items.append(f"{peer.upper()}:{profile}@{age}/{ctx}/{room_state}({len(capped[peer])})")
                lines = [_elide_display("SESS " + " ".join(items), columns)]
            out.write("\n".join(lines[:line_budget]) + "\n")
            return

        selected = round_robin[:row_slots]
        hidden = candidate_count - len(selected)

    selected = sorted(selected, key=lambda item: _session_display_sort_key(*item))

    lines = [title, header]
    lines.extend(
        _compact_session_row(row, peer, rendered_now, columns)
        for peer, row in selected
    )
    if hidden:
        lines.append(_elide_display(f"  +{hidden} hidden", columns))
    if line_budget is not None:
        lines = lines[:line_budget]
    out.write("\n".join(lines) + "\n")


def render_summary_frame(out, snapshot, *, terminal_lines=None, columns=80, now=None):
    """Render the standalone live HUD: SUMMARY, recent sessions, then FRAME."""
    summary_buf = io.StringIO()
    with redirect_stdout(summary_buf):
        infos = [p["raw"] for p in snapshot.get("peers") or []]
        render_summary(infos)
    summary_text = summary_buf.getvalue()

    frame_buf = io.StringIO()
    render_frame_footer(frame_buf, snapshot=snapshot, rendered_at=now)
    frame_text = frame_buf.getvalue()

    line_budget = None
    if terminal_lines is not None:
        summary_lines = len(summary_text.splitlines())
        frame_lines = len(frame_text.splitlines())
        line_budget = max(0, int(terminal_lines) - summary_lines - frame_lines - 1)

    out.write(summary_text)
    render_recent_sessions(
        out, snapshot, now=now, columns=columns, line_budget=line_budget,
    )
    out.write(frame_text)


def _compact_room_status(status_text):
    """Reduce hub status to the operator facts needed in the dashboard."""
    values = {}
    for line in str(status_text or "").splitlines():
        match = re.match(r"\*\*(.+?)\*\*:\s*(.*)", line.strip())
        if match:
            values[match.group(1).strip().lower()] = match.group(2).strip()
    roles = values.get("roles", "")
    coordinator = re.search(r"(?:^|[,\s])coordinator=([^,\s]+)", roles)
    parts = [
        f"room={values.get('room id', 'absent')}",
        f"leader={values.get('leader', 'absent')}",
        f"coordinator={coordinator.group(1) if coordinator else 'absent'}",
        f"mission={values.get('mission', 'absent')}",
        f"phase={values.get('phase', 'absent')}",
    ]
    blocked = values.get("blocked")
    if blocked:
        parts.append(f"blocked={blocked}")
    return "ROOM " + " ".join(parts)


def _next_target_line(snapshot):
    target = _next_headroom_target(_derive_headroom_rows(snapshot))
    if not target:
        return "NEXT FAILOVER TARGET: absent"
    risk = " TIER RISK" if target.get("tier_risk") else ""
    return (f"NEXT FAILOVER TARGET: {target.get('profile')} "
            f"headroom {_fmt_remaining(target.get('headroom'))}{risk}")


def render_attention(stdout=None, snapshot=None):
    """Attention strip: alerts, unavailable peers, over-cap sessions, target."""
    out = stdout or sys.stdout
    snapshot = snapshot if snapshot is not None else collect_snapshot()
    lines = []
    severity = {"critical": "CRIT", "warn": "WARN", "info": "INFO"}
    for rec in snapshot.get("peers") or []:
        peer = rec.get("peer") or "?"
        for alert in rec.get("alerts") or []:
            sev = severity.get(str(alert.get("severity") or "").lower(), "INFO")
            lines.append(f"[{sev}] {peer}: {alert.get('code')} {alert.get('message')}")
        health = (rec.get("domains") or {}).get("health") or {}
        if health.get("quarantined"):
            lines.append(f"[CRIT] {peer}: QUARANTINE peer is quarantined")
        elif health.get("gate_open") is False:
            lines.append(f"[WARN] {peer}: GATE_SHUT gate is closed")
    for row in snapshot.get("sessions") or []:
        pct = (row.get("context") or {}).get("utilization_pct")
        if isinstance(pct, (int, float)) and pct > 100:
            lines.append(
                f"[CRIT] {row.get('profile') or '?'}: SESSION_CONTEXT_OVER_CAPACITY {pct:.0f}%"
            )
    if not lines:
        lines.append("(no alerts)")
    out.write("\n".join(lines) + "\n")
    out.write(_next_target_line(snapshot) + "\n")


def render_peers(stdout=None, snapshot=None):
    """Opt-in peer cards; kept out of the default scan-oriented dashboard."""
    out = stdout or sys.stdout
    snapshot = snapshot if snapshot is not None else collect_snapshot()
    with redirect_stdout(out):
        print("PEER DETAIL")
        for record in snapshot.get("peers") or []:
            render_card(record.get("raw") or {})


def _render_summary_to(out, infos):
    """Adapt print-based SUMMARY to the renderer stream contract."""
    with redirect_stdout(out):
        render_summary(infos)


def render_dashboard(stdout=None, watch_mode=False, snapshot=None):
    out = stdout or sys.stdout
    columns = shutil.get_terminal_size().columns if bool(getattr(out, "isatty", lambda: False)()) else None

    def _write_width_safe(text):
        if columns is None:
            out.write(text)
            return
        out.write("\n".join(_elide_display(line, columns) for line in text.splitlines()) + "\n")

    def _render_width_safe(render_fn):
        if columns is None:
            render_fn(out)
            return
        buf = io.StringIO()
        render_fn(buf)
        _write_width_safe(buf.getvalue().rstrip("\n"))

    with redirect_stdout(out):
        print("=" * 60)
        print(_c(" Antigravity Collaboration Environment Diagnostics", "bold"))
        print("=" * 60)
        print(_c(_elide_display(" Reset times shown in local time. Set NO_COLOR=1 to disable color.", columns), "dim"))

        print("\n[ROOM]")
        hub_py = SYS_DIR / "core" / "hub.py"
        if hub_py.exists():
            # The dashboard is a scan surface, not a handoff reader. Capture
            # the existing status command and keep only the room-level facts.
            res = subprocess.run(["python", str(hub_py), "status"],
                                 capture_output=True, text=True)
            print(_elide_display(_compact_room_status(getattr(res, "stdout", "") or ""), columns))
        else:
            print("ROOM status unavailable")

        if snapshot is None:
            snapshot = collect_snapshot()
        infos = [p["raw"] for p in snapshot["peers"]]

        # Historical FP-4 order (superseded by the action-first list below):
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

        content_panels = [
            (" ATTENTION", lambda target: render_attention(target, snapshot=snapshot)),
            (" SUMMARY", lambda target: _render_summary_to(target, infos)),
            (" HEADROOM", lambda target: render_headroom(target, snapshot=snapshot, include_target=False)),
            (" RECENT SESSIONS", lambda target: render_sessions(target, snapshot=snapshot)),
            (" PROFILES & ROUTING", lambda target: render_profiles(target, snapshot=snapshot)),
            (" POLICY", lambda target: render_policy(target)),
        ]

        for title, render_fn in content_panels:
            if title == " SUMMARY":
                _render_width_safe(render_fn)
                continue
            _render_panel_header(title)
            _render_width_safe(render_fn)

        _render_width_safe(lambda target: render_frame_footer(target, snapshot=snapshot))


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


def run_watch(interval=None, json_mode=False, stdout=None, sleep=time.sleep, max_frames=None, summary_only=False):
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
        if is_tty and not json_mode and not summary_only:
            out.write("\033[2J\033[H")  # one-time clear to start from a clean screen
        while max_frames is None or frames < max_frames:
            if json_mode:
                emit_json_snapshot(out)
            elif summary_only:
                # Standalone HUD from tick zero. Session state is intentionally
                # collected uncached on every tick; only expensive sources keep
                # their own source-level TTL.
                snap = collect_snapshot(use_cache=False)
                buf = io.StringIO()
                if is_tty:
                    term_size = shutil.get_terminal_size()
                    render_summary_frame(
                        buf,
                        snap,
                        terminal_lines=term_size[1],
                        columns=term_size[0],
                    )
                    text = "\n".join(
                        _elide_display(line, term_size[0])
                        for line in buf.getvalue().rstrip("\n").splitlines()
                    )
                    _blit_frame(out, text, sync)
                else:
                    render_summary_frame(buf, snap, columns=None)
                    out.write(buf.getvalue().rstrip("\n") + "\n")
                    out.flush()
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
    ctx(declared window) | state | source | declared intelligence. No quota
    (quota lives in SUMMARY)."""
    out = stdout or sys.stdout
    if snapshot is None:
        snapshot = collect_snapshot()
    rows = snapshot.get("profiles") or []
    if not rows:
        out.write("(profile rows unavailable)\n")
        return
    headers = [_pad("PROFILE", 22), _pad("MODEL", 28), _pad("EFF", 5),
               _pad("TIER", 5), _pad("CTX", 12), _pad("STATE", 12), _pad("SRC", 13),
               _pad("INTEL", 15)]
    out.write(" ".join(headers).rstrip() + "\n")

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
        src = f"c:{_source_code(sources.get('context'))} q:{_source_code(sources.get('quota'))}"
        intelligence = _elide_display(_intelligence_display(row.get("intelligence_evidence")), 15)

        c_state = _pad(state, 12)
        if state == "eligible":
            c_state = _c(c_state, "green")
        elif state == "manual_only":
            c_state = _c(c_state, "yellow")
        model = _elide_display(model, 28)
        out.write(f"{_pad(str(row.get('profile') or 'absent'), 22)} {_pad(model, 28)} "
                  f"{_pad(effort, 5)} {_pad(tier, 5)} {_pad(ctx_val, 12)} {c_state} "
                  f"{_pad(src, 13)} {_pad(intelligence, 15)}\n")
    out.write(_c(_source_legend(), "dim") + "\n")


def render_headroom(stdout=None, snapshot=None, include_target=True):
    """Derived failover/headroom view. Consumes collect_snapshot only."""
    out = stdout or sys.stdout
    if snapshot is None:
        snapshot = collect_snapshot()
    rows = _derive_headroom_rows(snapshot)
    if include_target:
        target = _next_headroom_target(rows)
        if target:
            risk = " TIER RISK" if target.get("tier_risk") else ""
            out.write(f"NEXT {target.get('profile')} headroom {_fmt_remaining(target.get('headroom'))}{risk}\n")
        else:
            out.write("NEXT absent\n")
    out.write("PROFILE                HEADROOM QUOTA    CTX      EFFORT   STATE       SOURCE\n")
    for row in rows:
        sources = row.get("sources") or {}
        source_str = (f"ctx:{_source_code(sources.get('context'))} "
                      f"q:{_source_code(sources.get('quota'))}")
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
        out.write("(no recent sessions)\n")
        return
    out.write("PROFILE                MODEL                      STATUS    LEASE_STATE LAST_USED           CTX             SCOPE\n")
    for row in rows:
        lease_state = _session_lease_state(row, _frame_dt())
        last_used = str(row.get("last_used_at") or "-")[:19]
        model = _elide_display(row.get("model") or "absent", 26)
        out.write(
            f"{str(row.get('profile') or '?'):<22} "
            f"{_pad(model, 26)} "
            f"{str(row.get('status') or 'unknown'):<9} "
            f"{_pad(lease_state, 11)} "
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
    if args.watch or args.live:
        return run_watch(interval=args.interval, json_mode=args.json_mode, stdout=out,
                          summary_only=args.live)
    if args.json_mode:
        emit_json_snapshot(out)
        return 0
    if args.profiles:
        render_profiles(out); return 0
    if args.peers:
        render_peers(out); return 0
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
