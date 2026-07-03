import os
import argparse
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
    print("\n" + "=" * 60)
    print(_c(" SUMMARY", "bold"))
    print("=" * 60)
    header = f"{'PEER':<5} {'GATE':<6} {'MODEL':<24} {'CONTEXT':<14} {'COST':<9} DATA"
    print(_c(header, "dim"))
    for info in infos:
        peer = info["peer"].upper()
        model = (info["model"] or "Unknown")
        if len(model) > 24:
            model = model[:21] + "..."
        cost = f"${info['cost']:.4f}" if isinstance(info["cost"], (int, float)) else "-"
        # Pad on the raw cells, then colorize gate separately to keep alignment.
        gate_raw = "OPEN" if info.get("gate") else ("QUAR" if info.get("quarantined")
                                                    else ("SHUT" if info.get("gate") is False else "n/a"))
        line = f"{peer:<5} {gate_raw:<6} {model:<24} {_ctx_cell_raw(info):<14} {cost:<9} {info['source']}"
        print(line)


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

    # Context bar
    if not info.get("ctx_known"):
        print(f" Context : (current occupancy n/a)  window {_short(info['ctx_window'])}")
    else:
        cpct = info["ctx_pct"] if isinstance(info["ctx_pct"], (int, float)) else 0
        bar = _bar(cpct / 100.0)
        print(f" Context : {bar} {cpct:>4.0f}% ({_short(info['ctx_used'])}/{_short(info['ctx_window'])})")

    # Quota bars
    if info["quotas"]:
        width = max(len(q["label"]) for q in info["quotas"])
        for q in info["quotas"]:
            uf = q.get("used_frac")
            is_num = isinstance(uf, (int, float))
            metric = format_quota_bucket(q)
            warn = "  " + _c("WARN", "red", "bold") if (is_num and uf >= 0.90) else ""
            print(f" {q['label']:<{width}} : {metric:<24} resets {q['reset']}{warn}")
    elif info.get("cx_quota_unavailable"):
        print(_c(" Quota   : (codex app-server unavailable)", "dim"))

    if info.get("quarantine_reason"):
        print(_c(f" Quarantine reason: {info['quarantine_reason']}", "red"))
    if info.get("total_tokens"):
        print(_c(f" Total historical tokens: {info['total_tokens']:,}", "dim"))
    if info.get("sessions") is not None:
        print(_c(f" Sessions today: {info['sessions']}", "dim"))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="diag")
    parser.add_argument("--json", dest="json_mode", action="store_true",
                        help="emit normalized telemetry JSON")
    parser.add_argument("--watch", nargs="?", const=5, type=float, metavar="SECONDS",
                        help="refresh repeatedly; defaults to 5 seconds")
    parser.add_argument("--interval", type=float, metavar="SECONDS",
                        help="alias for --watch SECONDS")
    parser.add_argument("--profiles", action="store_true", help="reserved profile detail view")
    parser.add_argument("--accounts", action="store_true", help="reserved account detail view")
    parser.add_argument("--tokens", action="store_true", help="reserved token detail view")
    parser.add_argument("--sessions", action="store_true", help="reserved session detail view")
    parser.add_argument("--project", action="store_true", help="reserved project detail view")
    parser.add_argument("--headroom", action="store_true", help="derived routing headroom view")
    args = parser.parse_args(argv)

    requested_interval = args.interval if args.interval is not None else args.watch
    args.watch = requested_interval is not None
    args.interval = requested_interval
    if args.watch:
        if args.interval < 2:
            parser.error("minimum interval is 2 seconds")
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











def render_dashboard(stdout=None, watch_mode=False):
    out = stdout or sys.stdout
    with redirect_stdout(out):
        print("=" * 60)
        print(_c(" Antigravity Collaboration Environment Diagnostics", "bold"))
        print("=" * 60)
        print(_c(" Reset times shown in local time. Set NO_COLOR=1 to disable color.", "dim"))

        print("\n[ROOM & HUB STATUS]")
        out.flush()
        hub_py = SYS_DIR / "core" / "hub.py"
        if hub_py.exists():
            subprocess.run(["python", str(hub_py), "status"], stdout=out)
        else:
            print("hub.py not found.")

        snapshot = collect_snapshot()
        infos = [p["raw"] for p in snapshot["peers"]]

        # Section order is the unanimous FP-4 spec (2026-07-03): static first,
        # volatile nearest the prompt — PROFILES&QUOTAS → DETAIL → SESSIONS/
        # HEADROOM → ALERTS → SUMMARY, identical in default and watch mode.
        print("\n" + "=" * 60)
        print(_c(" PEER PROFILES & QUOTAS", "bold"))
        print("=" * 60)
        render_profiles(out, snapshot=snapshot)

        print("\n" + "=" * 60)
        print(_c(" PEER DETAIL", "bold"))
        print("=" * 60)
        for info in infos:
            render_card(info)

        print("\n" + "=" * 60)
        print(_c(" ACTIVE SESSIONS & HEADROOM", "bold"))
        print("=" * 60)
        render_sessions(out, snapshot=snapshot)
        target = _next_headroom_target(_derive_headroom_rows(snapshot))
        if target:
            risk = " TIER RISK" if target.get("tier_risk") else ""
            out.write(f"NEXT FAILOVER TARGET: {target.get('profile')} "
                      f"headroom {_fmt_remaining(target.get('headroom'))}{risk}\n")

        print("\n" + "=" * 60)
        print(_c(" ALERTS", "bold"))
        print("=" * 60)
        alert_count = 0
        for rec in snapshot["peers"]:
            for alert in rec.get("alerts") or []:
                sev = str(alert.get("severity") or "info").upper()
                print(f"[{sev}] {rec.get('peer')}: {alert.get('code')} {alert.get('message')}")
                alert_count += 1
        if not alert_count:
            print("(no alerts)")

        render_summary(infos)

        print("\n" + "=" * 60)
        print(_c(" Note: run '_sys\\cli\\diag' (or diag.bat) anytime to view this screen.", "dim"))
        print("=" * 60)


def emit_json_snapshot(stdout=None):
    out = stdout or sys.stdout
    out.write(json.dumps(collect_snapshot(), ensure_ascii=False, sort_keys=True) + "\n")
    out.flush()


def run_watch(interval=5, json_mode=False, stdout=None, sleep=time.sleep, max_frames=None):
    out = stdout or sys.stdout
    frames = 0
    try:
        while max_frames is None or frames < max_frames:
            if json_mode:
                emit_json_snapshot(out)
            else:
                if hasattr(out, "isatty") and out.isatty():
                    out.write("\033[2J\033[H")
                render_dashboard(out, watch_mode=True)
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
    """Generated-profile rows from the normalized snapshot.

    The snapshot owns collection; this renderer only formats profile rows and never
    exposes raw profile_args / adapter flags (section 6.3).
    """
    out = stdout or sys.stdout
    if snapshot is None:
        snapshot = collect_snapshot()
    rows = snapshot.get("profiles") or []
    if not rows:
        out.write("(profile rows unavailable)\n")
        return
    out.write(f"{'PEER.PROFILE':<22} {'MODEL':<28} {'EFF':<5} {'CTX(used/cap %)':<18} "
              f"{'5H(bar % pace)':<26} {'WEEKLY(bar % pace)':<26} {'RESET':<18} {'SRC':<12} STATE\n")
    for row in rows:
        sources = row.get("sources") or {}
        model = row.get("model") or "absent"
        if sources.get("model") == "orchestration" and model != "absent":
            model = f"[decl] {model}"
        effort = str(row.get("effort") or "absent")[:5]

        ctx = row.get("context") or {}
        win = ctx.get("window_tokens")
        used = ctx.get("used_tokens")
        pct = ctx.get("utilization_pct")
        if win is None:
            ctx_str = "absent"
        elif sources.get("context") == "orchestration":
            ctx_str = f"[decl] {_short(win)}"
        else:
            used_s = _short(used) if used is not None else "?"
            pct_s = f" {pct:.0f}%" if isinstance(pct, (int, float)) else ""
            ctx_str = f"{used_s}/{_short(win)}{pct_s}"

        bucket_5h = bucket_weekly = None
        for b in (row.get("quota") or {}).get("buckets") or []:
            label = str(b.get("label", ""))
            if "5H" in label:
                bucket_5h = b
            elif "7D" in label:
                bucket_weekly = b
        q_5h = format_quota_bucket(bucket_5h) if bucket_5h else "absent"
        q_weekly = format_quota_bucket(bucket_weekly) if bucket_weekly else "absent"

        reset_str = "absent"
        for b in (bucket_5h, bucket_weekly):
            reset = b.get("reset") if b else None
            if reset and str(reset) not in ("?", "absent"):
                m = re.search(r"\((in [^)]+)\)", str(reset))
                reset_str = m.group(1) if m else str(reset)[:18]
                break

        def _fmt_src(tag):
            return {"orchestration": "decl", "cli_live": "cliv", "app_server": "app",
                    "statusline": "live", "health": "hlth", "absent": "-"}.get(tag, str(tag)[:4])

        source_str = f"c:{_fmt_src(sources.get('context'))} q:{_fmt_src(sources.get('quota'))}"
        state = row.get("state") or "unknown"
        out.write(f"{str(row.get('profile') or 'absent'):<22} {str(model)[:28]:<28} {effort:<5} "
                  f"{ctx_str:<18} {q_5h:<26} {q_weekly:<26} {reset_str:<18} {source_str:<12} {state}\n")


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
