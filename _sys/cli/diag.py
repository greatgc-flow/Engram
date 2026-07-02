import os
import argparse
import json
import subprocess
from pathlib import Path
import sys
import time
from contextlib import redirect_stdout
from datetime import datetime, timezone

CLI_DIR = Path(__file__).parent
SYS_DIR = CLI_DIR.parent
PORTABLE_ROOT = SYS_DIR.parent

sys.path.insert(0, str(SYS_DIR / "core"))
from hub_peer import resolve_peer_sys_dir


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


def _bar(frac, width=10):
    """ASCII progress bar like [####------] for frac in 0..1 (USED)."""
    try:
        frac = max(0.0, min(1.0, float(frac)))
    except (TypeError, ValueError):
        frac = 0.0
    fill = int(round(frac * width))
    return "[" + "#" * fill + "-" * (width - fill) + "]"


def _short(n):
    """Compact token count: 58787 -> 58k, 1000000 -> 1M."""
    if not isinstance(n, (int, float)):
        return str(n)
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n // 1000}k"
    return str(n)


def _parse_reset(value):
    """Parse an epoch (int/float/digit-string; /1000 if milliseconds) or an
    ISO8601 string into a timezone-aware datetime in LOCAL time.
    Returns None on failure (never raises)."""
    if value is None or value == "":
        return None
    # Numeric epoch (int/float or pure digit / float string)
    is_numeric = isinstance(value, (int, float))
    if not is_numeric and isinstance(value, str):
        is_numeric = value.strip().replace(".", "", 1).isdigit()
    if is_numeric:
        try:
            num = float(value)
            if abs(num) > 1e12:  # looks like milliseconds
                num /= 1000.0
            return datetime.fromtimestamp(num, tz=timezone.utc).astimezone()
        except (ValueError, OSError, OverflowError):
            return None
    # ISO8601 string
    try:
        s = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone()
    except (ValueError, TypeError):
        return None


def _rel(seconds):
    """Relative countdown string compressed to two units."""
    secs = int(seconds)
    if secs <= 0:
        return "now"
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    if days > 0:
        return f"in {days}d {hours}h"
    if hours > 0:
        return f"in {hours}h {mins}m"
    return f"in {mins}m"


def _fmt_reset(value, rel_seconds=None):
    """Single shared reset formatter for cc/ag/cx:
    'MM/DD HH:MM +0900 (in Xh Ym)' in local time, with the year across years.
    rel_seconds (e.g. ag reset_in_seconds) is used only as a fallback."""
    dt = _parse_reset(value)
    if dt is None:
        if rel_seconds is not None:
            return _rel(rel_seconds)
        return str(value) if value not in (None, "") else "?"
    now = datetime.now().astimezone()
    abs_fmt = "%Y-%m-%d %H:%M %z" if dt.year != now.year else "%m/%d %H:%M %z"
    abs_str = dt.strftime(abs_fmt)
    return f"{abs_str} ({_rel((dt - now).total_seconds())})"


# --------------------------------------------------------------------------
# Live quota source for Codex (no local persistence)
# --------------------------------------------------------------------------

_REAL_BINARIES = {
    "cc": SYS_DIR / "env" / "nodejs" / "npm-global" / "claude.cmd",
    "cx": SYS_DIR / "env" / "nodejs" / "npm-global" / "codex.cmd",
    "ag": PORTABLE_ROOT / "tools" / "agy" / "agy.exe",
}


def _real_binary(peer):
    """Resolve the REAL peer CLI, NEVER our `_sys/cli` wrapper."""
    cand = _REAL_BINARIES.get(peer)
    if cand is None:
        raise ValueError(f"unknown peer binary: {peer}")
    if not cand.exists():
        return None
    resolved = cand.resolve()
    if resolved == CLI_DIR.resolve() or CLI_DIR.resolve() in resolved.parents:
        raise RuntimeError(f"refusing wrapper binary for {peer}: {resolved}")
    return str(resolved)


def _codex_binary():
    """Back-compat alias = real Codex CLI. NEVER our `_sys/cli` wrapper.

    `_sys/cli` is first on PATH, so a bare `codex` (incl. Windows `shutil.which`
    matching `codex.bat` via PATHEXT) resolves to our wrapper, which runs the heavy
    `codex_entry.py` flow (hub init-session + context-fill + status). That is wrong
    and slow for a raw app-server RPC — it was the real root of the diag `--json`
    stall. Prefer the npm-global binary directly."""
    import shutil
    cand = SYS_DIR / "env" / "nodejs" / "npm-global" / "codex.cmd"
    if cand.exists():
        return str(cand)
    return shutil.which("codex.cmd")  # real .cmd; our wrapper is codex.bat / codex


def _codex_rate_limits(deadline_sec=12):
    """Query the codex app-server (initialize -> account/rateLimits/read) for live
    5h/weekly rate-limit reset times. Codex does not persist these locally.

    A background reader thread feeds lines to a queue so the deadline is honored
    EVEN IF proc.stdout.readline() blocks (the app-server is a daemon and, under a
    denied sandbox, can spawn-EPERM and never emit — which previously hung diag for
    tens of minutes). Returns the rateLimits dict or None."""
    import threading, queue
    msgs = (
        '{"jsonrpc":"2.0","id":0,"method":"initialize","params":'
        '{"clientInfo":{"name":"diag","version":"1.0"},"apiVersion":"v2"}}\n'
        '{"jsonrpc":"2.0","id":1,"method":"account/rateLimits/read","params":{}}\n'
    )
    codex_exe = _codex_binary()
    if not codex_exe:
        return None
    proc = None
    try:
        proc = subprocess.Popen([codex_exe, "app-server"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            proc.stdin.write(msgs)
            proc.stdin.flush()
        except Exception:
            return None

        q: "queue.Queue" = queue.Queue()

        def _reader():
            try:
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    q.put(line)
            except Exception:
                pass
            q.put(None)  # EOF / reader-done sentinel

        threading.Thread(target=_reader, daemon=True).start()

        deadline = time.monotonic() + deadline_sec
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break  # deadline enforced regardless of a blocked readline
            try:
                line = q.get(timeout=min(0.5, remaining))
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if obj.get("id") == 1 and isinstance(obj.get("result"), dict):
                return obj["result"].get("rateLimits")
    except Exception:
        pass
    finally:
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass
    return None


def _parse_rollout_context(path):
    """Parse a codex thread rollout JSONL for its last `event_msg/token_count`
    event → (used_tokens, window_tokens). Current occupancy is
    last_token_usage.total_tokens; model_context_window is capacity (per cx). The
    last COMPLETE event wins — a truncated final line is tolerated (D2)."""
    info = None
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            payload = obj.get("payload", {})
            if isinstance(payload, dict) and payload.get("type") == "token_count":
                info = payload.get("info")
    except (OSError, ValueError):
        return (None, None)
    if not isinstance(info, dict):
        return (None, None)
    win = info.get("model_context_window")
    used = (info.get("last_token_usage") or {}).get("total_tokens")
    return (used if isinstance(used, (int, float)) else None,
            win if isinstance(win, (int, float)) else None)


def _codex_context():
    """cx current context occupancy from the newest thread's rollout (D2).
    Returns (used_tokens, window_tokens) or (None, None)."""
    db_path = SYS_DIR / "codex" / "config" / "state_5.sqlite"
    if not db_path.exists():
        return (None, None)
    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT rollout_path FROM threads ORDER BY updated_at DESC LIMIT 1").fetchone()
        conn.close()
    except Exception:
        return (None, None)
    if not row or not row[0]:
        return (None, None)
    return _parse_rollout_context(row[0])


EXPENSIVE_SOURCE_TTL_SEC = 60
_CODEX_RATE_LIMIT_CACHE = {}


def _cached_codex_rate_limits(ttl_sec=EXPENSIVE_SOURCE_TTL_SEC, clock=time.monotonic):
    now = clock()
    cached = _CODEX_RATE_LIMIT_CACHE.get("rate_limits")
    if cached and now < cached["expires_at"]:
        return cached["value"]
    value = _codex_rate_limits()
    _CODEX_RATE_LIMIT_CACHE["rate_limits"] = {
        "value": value,
        "expires_at": now + ttl_sec,
    }
    return value



# --------------------------------------------------------------------------
# Per-peer metric gathering
# --------------------------------------------------------------------------

def _discover_peers():
    """Return (peers, peer_dirs) from orchestration.json, with a static fallback."""
    peers = []
    peer_dirs = {}
    orch_file = SYS_DIR / "ai" / "orchestration.json"
    if orch_file.exists():
        try:
            orch_data = json.loads(orch_file.read_text(encoding="utf-8"))
            for node in orch_data.get("hub_nodes", []):
                if node.get("type") == "peer" and node.get("enabled", True):
                    pid = node.get("node_id")
                    if pid:
                        peers.append(pid)
                        subdir = resolve_peer_sys_dir(pid)
                        peer_dirs[pid] = SYS_DIR / (subdir if subdir else pid)
        except Exception:
            pass
    if not peers:
        peers = ["ag", "cc", "cx"]
        peer_dirs = {
            "ag": SYS_DIR / "antigravity",
            "cc": SYS_DIR / "claude",
            "cx": SYS_DIR / "codex",
        }
    return peers, peer_dirs


# Friendly labels for ag's quota buckets.
_AG_QUOTA_LABELS = {
    "gemini-5h": "G-5H", "gemini-weekly": "G-7D",
    "3p-5h": "3P-5H", "3p-weekly": "3P-7D",
}


def gather_peer(peer, peer_dirs):
    """Collect a normalized metrics dict for one peer."""
    info = {
        "peer": peer, "gate": None, "quarantined": None, "quarantine_reason": None,
        "model": "Unknown", "ctx_used": 0, "ctx_window": "Unknown", "ctx_pct": None,
        "cost": None, "source": "none", "agent_state": None, "plan_tier": None,
        "quotas": [], "sessions": None, "total_tokens": None, "empty": True,
        "ctx_known": False, "errors": [],
    }

    # Live state log (cc/ag publish one; cx is queried live below).
    live_file = None
    if peer == "ag":
        live_file = CLI_DIR / "ag_stdin.log"
    elif peer == "cc":
        live_file = SYS_DIR / "claude" / "config" / "status_input.log"

    data = {}
    if live_file and live_file.exists():
        try:
            data = json.loads(live_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    health_data = {}
    health_file = peer_dirs[peer] / "health.json"
    if health_file.exists():
        try:
            health_data = json.loads(health_file.read_text(encoding="utf-8"))
        except Exception:
            health_data = {}

    if not data and not health_data:
        return info
    info["empty"] = False
    info["source"] = "live" if data else "health"

    # Source freshness (D1): observed_at = capture time of the source file, plus age.
    src_file = live_file if (live_file and live_file.exists()) else (
        health_file if health_file.exists() else None)
    if src_file:
        try:
            mt = src_file.stat().st_mtime
            info["observed_at"] = datetime.fromtimestamp(mt, tz=timezone.utc).astimezone().isoformat()
            info["age_sec"] = max(0, int(time.time() - mt))
        except OSError:
            pass

    # Health / gate
    avail = health_data.get("availability", {})
    info["gate"] = avail.get("gate_open")
    info["quarantined"] = avail.get("quarantined")
    info["quarantine_reason"] = avail.get("quarantine_reason") or avail.get("reason")

    # Context & tokens (live preferred)
    if "context_window" in data:
        ctx = data["context_window"]
        info["ctx_window"] = ctx.get("context_window_size", "Unknown")
        info["ctx_used"] = ctx.get("total_input_tokens", 0) + ctx.get("total_output_tokens", 0)
        cur_usage = ctx.get("current_usage")
        if info["ctx_used"] == 0 and isinstance(cur_usage, dict):
            info["ctx_used"] = cur_usage.get("input_tokens", 0) + cur_usage.get("output_tokens", 0)
        if isinstance(ctx.get("used_percentage"), (int, float)):
            info["ctx_pct"] = ctx["used_percentage"]
        info["ctx_known"] = True
    elif "context_used_tokens" in data:
        info["ctx_used"] = data["context_used_tokens"]
        info["ctx_window"] = data.get("context_total_tokens", "Unknown")
        info["ctx_known"] = True
    else:
        ctx = health_data.get("context_health", {})
        profile = health_data.get("profile", {})
        if profile:
            info["model"] = profile.get("model", "Unknown")
            info["ctx_window"] = profile.get("runtime_context_window", "Unknown")
        info["ctx_used"] = ctx.get("session_token_count", 0)
        info["ctx_known"] = "session_token_count" in ctx

    # Model + effort
    model_name = "Unknown"
    effort_val = ""
    if "model" in data:
        if isinstance(data["model"], dict):
            model_name = data["model"].get("display_name") or data["model"].get("id", "Unknown")
        else:
            model_name = str(data["model"])
    elif "model_name" in data:
        model_name = str(data["model_name"])

    if "model_reasoning_effort" in data:
        mre = data["model_reasoning_effort"]
        effort_val = mre.get("level", "") if isinstance(mre, dict) else str(mre)
    elif "effort" in data:
        ef = data["effort"]
        effort_val = ef.get("level", "") if isinstance(ef, dict) else str(ef)

    # Cost / state / tier
    if "cost" in data and isinstance(data["cost"], dict):
        info["cost"] = data["cost"].get("total_cost_usd")
    info["agent_state"] = data.get("agent_state")
    info["plan_tier"] = data.get("plan_tier")
    info["email"] = data.get("email")  # masked at the normalization boundary (§5)
    session_h = health_data.get("session_health", {})
    if "session_count_today" in session_h:
        info["sessions"] = session_h.get("session_count_today")

    # Quotas (normalized to USED fraction)
    quotas = []
    if "quota" in data and isinstance(data["quota"], dict):  # ag
        for key, label in _AG_QUOTA_LABELS.items():
            q = data["quota"].get(key)
            if not isinstance(q, dict):
                continue
            rem = q.get("remaining_fraction")
            used_frac = max(0.0, min(1.0, 1.0 - rem)) if isinstance(rem, (int, float)) else None
            
            import quota as qmgr
            window_hours = 5.0 if "5H" in label else 168.0
            reset_sec = q.get("reset_in_seconds")
            rem_sec = qmgr.get_remaining_seconds(reset_in_seconds=reset_sec)
            pacing = qmgr.calculate_pacing(used_frac, rem_sec, window_hours) if used_frac is not None else None
            quotas.append({
                "label": label, "used_frac": used_frac, "pacing": pacing,
                "reset": _fmt_reset(q.get("reset_time"), reset_sec), "source": "ag",
            })
    if "rate_limits" in data and isinstance(data["rate_limits"], dict):  # cc
        rl = data["rate_limits"]
        for key, q in rl.items():
            if not isinstance(q, dict):
                continue
            up = q.get("used_percentage")
            used_frac = up / 100.0 if isinstance(up, (int, float)) else None
            
            # Dynamically determine the label and window
            prefix = "F-" if "fable" in key else "C-"
            if "five" in key or "5h" in key:
                label = f"{prefix}5H"
                window_hours = 5.0
            elif "seven" in key or "weekly" in key or "7d" in key:
                label = f"{prefix}7D"
                window_hours = 168.0
            else:
                label = f"{prefix}{key}"
                window_hours = 168.0  # safe fallback
            
            import quota as qmgr
            resets_at = q.get("resets_at") or q.get("reset_at")
            reset_sec = q.get("reset_in_seconds")
            
            if reset_sec is not None:
                rem_sec = qmgr.get_remaining_seconds(reset_in_seconds=reset_sec)
            else:
                rem_sec = qmgr.get_remaining_seconds(resets_at_iso=resets_at)
                
            pacing = qmgr.calculate_pacing(used_frac, rem_sec, window_hours) if used_frac is not None else None
            quotas.append({
                "label": label, "used_frac": used_frac, "pacing": pacing,
                "reset": _fmt_reset(resets_at, reset_sec), "source": "cc",
            })

    # Codex: model/tokens/effort from sqlite + live rate limits from app-server
    if peer == "cx":
        db_path = SYS_DIR / "codex" / "config" / "state_5.sqlite"
        if db_path.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                cur = conn.cursor()
                cur.execute("SELECT model, tokens_used, reasoning_effort FROM threads "
                            "WHERE tokens_used > 0 ORDER BY updated_at DESC LIMIT 1;")
                row = cur.fetchone()
                if row:
                    if row[0]:
                        model_name = str(row[0])
                    # row[1] (tokens_used) is the thread's CUMULATIVE token total,
                    # not current context occupancy - surfaced as total_tokens, not ctx.
                    if row[2]:
                        effort_val = str(row[2])
                cur.execute("SELECT SUM(tokens_used) FROM threads;")
                row_sum = cur.fetchone()
                if row_sum and row_sum[0]:
                    info["total_tokens"] = int(row_sum[0])
                conn.close()
                info["empty"] = False
            except Exception as exc:
                info["errors"].append(f"sqlite_read: {type(exc).__name__}")
        # cx current context occupancy from the newest rollout token_count (D2).
        c_used, c_win = _codex_context()
        if isinstance(c_win, (int, float)) and c_win:
            info["ctx_window"] = c_win
            info["ctx_used"] = c_used if isinstance(c_used, (int, float)) else 0
            info["ctx_known"] = c_used is not None
            if c_used is not None:
                info["ctx_pct"] = round(c_used / c_win * 100, 1)
            info["empty"] = False
        rl = _cached_codex_rate_limits()
        if rl:
            info["source"] = "app-server"
            for key, label in (("primary", "X-5H"), ("secondary", "X-7D")):
                q = rl.get(key)
                if not isinstance(q, dict):
                    continue
                used = q.get("usedPercent", 0) or 0
                used_frac = used / 100.0
                
                import quota as qmgr
                window_hours = 5.0 if "5H" in label else 168.0
                resets_at = q.get("resetsAt")
                rem_sec = qmgr.get_remaining_seconds(resets_at_iso=resets_at)
                pacing = qmgr.calculate_pacing(used_frac, rem_sec, window_hours)

                quotas.append({
                    "label": label, "used_frac": used_frac,
                    "reset": _fmt_reset(resets_at),
                    "metric": f"{float(used):.1f}% used{_fmt_pacing(pacing)}",
                    "pacing_ratio": pacing.get("ratio"), "pacing_status": pacing.get("status"),
                })
        elif not quotas:
            info["cx_quota_unavailable"] = True

    if effort_val and effort_val.lower() not in model_name.lower() and effort_val != "null":
        model_name = f"{model_name} ({effort_val})"
    info["model"] = model_name
    info["quotas"] = quotas

    # Context percentage fallback (only when occupancy is genuinely known)
    if (info["ctx_pct"] is None and info["ctx_known"]
            and isinstance(info["ctx_window"], (int, float)) and info["ctx_window"]):
        info["ctx_pct"] = round(info["ctx_used"] / info["ctx_window"] * 100, 1)
    return info


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


_LOCAL_TTL_SEC = 5


_SYNTHETIC_PEERS = {"testpeer"}


def _is_synthetic_peer(name):
    """True for test-fixture / non-orchestration peers so log-derived signals
    ignore them (keeps diagnostics honest — see §11.3)."""
    if not name or name in _SYNTHETIC_PEERS:
        return True
    try:
        known, _ = _discover_peers()
    except Exception:
        known = ["ag", "cc", "cx"]
    return name not in known


def _fmt_pacing(pacing):
    """Render a pacing dict ({ratio,status,indicator}) as value + emoji (D4),
    e.g. ' 🟢 1.05x'. Empty when pacing is unknown."""
    if not pacing or not pacing.get("indicator"):
        return ""
    return f" {pacing['indicator']} {pacing['ratio']:.2f}x"


def format_quota_bucket(bucket):
    """Render one quota bucket identically everywhere. Unknown/unmeasured buckets
    are the literal string 'absent' — never 0, blank, or an estimate."""
    if not isinstance(bucket, dict):
        return "absent"
    used_frac = bucket.get("used_frac")
    if bucket.get("source") == "absent" or used_frac is None:
        return "absent"
    try:
        frac = max(0.0, min(1.0, float(used_frac)))
    except (TypeError, ValueError):
        return "absent"
    emoji = "🔴" if frac >= 0.90 else "🟡" if frac >= 0.75 else "🟢"
    pacing = _fmt_pacing(bucket.get("pacing"))
    if not pacing:
        ratio = bucket.get("pacing_ratio")
        pacing = f" {emoji} {ratio:.2f}x" if isinstance(ratio, (int, float)) else f" {emoji} 0.00x"
    return f"{_bar(frac)} {frac * 100:.0f}%{pacing}"


def _mask_email(email):
    """Redact an email for telemetry (§5): keep only first local char + domain.
    Returns None for empty, '***' for non-email strings."""
    if not email:
        return None
    s = str(email)
    local, sep, domain = s.partition("@")
    if not sep or not local or not domain:
        return "***"
    return f"{local[0]}***@{domain}"


def _source_meta(kind, observed_at, ttl_sec, confidence):
    """Normalized source-provenance block (§4)."""
    return {"kind": kind, "observed_at": observed_at, "ttl_sec": ttl_sec, "confidence": confidence}


# Quota alert thresholds (§7). Context thresholds come from governance_params.json.
QUOTA_WARN_FRAC = 0.75
QUOTA_CRIT_FRAC = 0.90
# Source data older than this is flagged SOURCE_STALE (status logs only refresh when
# that peer's statusline renders, so an idle peer's quota/context can be stale) (D1).
STALE_THRESHOLD_SEC = 300


def _governance_params():
    try:
        return json.loads((SYS_DIR / "ai" / "governance_params.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _alert(severity, code, message):
    return {"severity": severity, "code": code, "message": message}


def _compute_alerts(record):
    """Deterministic alerts (§7) computed from a normalized peer record.
    CTX_UNKNOWN suppresses context threshold alerts (no precise claims)."""
    gp = _governance_params()
    warn_pct = float(gp.get("context_gate_warn_pct", 0.8)) * 100
    crit_pct = float(gp.get("context_gate_failover_pct", 0.95)) * 100
    dom = record.get("domains", {})
    alerts = []

    # Collector failures first — visibility over silent masking.
    for err in record.get("errors", []):
        alerts.append(_alert("critical", "DIAG_INTERNAL_ERROR", str(err)))

    age = record.get("raw", {}).get("age_sec")
    if isinstance(age, (int, float)) and age > STALE_THRESHOLD_SEC:
        alerts.append(_alert("warn", "SOURCE_STALE",
                             f"source data {int(age)}s old (> {STALE_THRESHOLD_SEC}s); may be pre-reset"))

    ctx = dom.get("context", {})
    util = ctx.get("utilization_pct")
    if ctx.get("used_tokens") is None:
        alerts.append(_alert("warn", "CTX_UNKNOWN",
                             "current context occupancy unknown; avoid precise remaining-token claims"))
    elif isinstance(util, (int, float)):
        if util >= crit_pct:
            alerts.append(_alert("critical", "CONTEXT_CRITICAL", f"context {util:.0f}% >= {crit_pct:.0f}%"))
        elif util >= warn_pct:
            alerts.append(_alert("warn", "CONTEXT_WARN", f"context {util:.0f}% >= {warn_pct:.0f}%"))

    worst = None
    for bucket in dom.get("quota", {}).get("buckets", []):
        frac = bucket.get("used_frac")
        if isinstance(frac, (int, float)):
            worst = frac if worst is None else max(worst, frac)
    if worst is not None:
        if worst >= QUOTA_CRIT_FRAC:
            alerts.append(_alert("critical", "QUOTA_CRITICAL", f"quota {worst * 100:.0f}% used"))
        elif worst >= QUOTA_WARN_FRAC:
            alerts.append(_alert("warn", "QUOTA_WARN", f"quota {worst * 100:.0f}% used"))

    acct = dom.get("account", {})
    if not acct.get("plan_tier") and not acct.get("email"):
        alerts.append(_alert("info", "ACCOUNT_UNKNOWN", "account/plan/expiry unavailable"))

    if dom.get("session", {}).get("source", {}).get("confidence") == "unknown":
        alerts.append(_alert("info", "SESSION_UNVERIFIABLE", "session state could not be verified"))

    return alerts


def normalize_peer(info, now=None):
    """Map a raw gather_peer() dict into the normalized per-domain telemetry
    record (§4). Every domain carries source provenance; unknown numerics stay
    None (never 0). The raw dict is preserved under "raw" for renderers/drill-down."""
    now = now or datetime.now().astimezone()
    # observed_at reflects when the SOURCE data was captured (file mtime), not when
    # diag ran — otherwise a stale snapshot looks fresh (D1).
    observed = info.get("observed_at") or now.isoformat()
    raw_src = info.get("source", "none")
    kind = {"live": "live", "app-server": "live", "health": "cached"}.get(raw_src, "unknown")

    # Context ---------------------------------------------------------------
    ctx_known = bool(info.get("ctx_known"))
    window = info.get("ctx_window")
    pct = info.get("ctx_pct")
    ctx_conf = "exact" if (ctx_known and kind == "live") else ("last_known" if ctx_known else "unknown")
    context = {
        "window_tokens": window if isinstance(window, (int, float)) else None,
        "used_tokens": info.get("ctx_used") if ctx_known else None,
        "utilization_pct": pct if isinstance(pct, (int, float)) else None,
        "source": _source_meta(kind if ctx_known else "unknown", observed, _LOCAL_TTL_SEC, ctx_conf),
    }

    # Quota (cx quota is fetched from the codex app-server = expensive TTL) --
    quotas = info.get("quotas", [])
    expensive = info.get("peer") == "cx" or any(q.get("expensive") for q in quotas)
    quota = {
        "buckets": quotas,
        "source": _source_meta(kind if quotas else "unknown", observed,
                               EXPENSIVE_SOURCE_TTL_SEC if expensive else _LOCAL_TTL_SEC,
                               "exact" if quotas else "unknown"),
    }

    # Cost ------------------------------------------------------------------
    cost_val = info.get("cost")
    cost = {
        "total_cost_usd": cost_val if isinstance(cost_val, (int, float)) else None,
        "total_tokens": info.get("total_tokens"),
        "source": _source_meta(kind, observed, _LOCAL_TTL_SEC,
                               "exact" if isinstance(cost_val, (int, float)) else "unknown"),
    }

    # Session ---------------------------------------------------------------
    session = {
        "state": info.get("agent_state"),
        "sessions_today": info.get("sessions"),
        "source": _source_meta("cached", observed, _LOCAL_TTL_SEC,
                               "last_known" if info.get("sessions") is not None else "unknown"),
    }

    # Account — identifiers are redacted before leaving this boundary (§5) ---
    masked_email = _mask_email(info.get("email"))
    has_account = bool(info.get("plan_tier") or masked_email)
    account = {
        "plan_tier": info.get("plan_tier"),
        "email": masked_email,
        "source": _source_meta(kind if has_account else "unknown", observed,
                               _LOCAL_TTL_SEC, "last_known" if has_account else "unknown"),
    }

    # Health / gate ---------------------------------------------------------
    health = {
        "gate_open": info.get("gate"),
        "quarantined": info.get("quarantined"),
        "source": _source_meta("cached", observed, _LOCAL_TTL_SEC,
                               "last_known" if not info.get("empty") else "unknown"),
    }

    # Sanitized raw passthrough: never let raw account identifiers leak via "raw".
    safe_raw = dict(info)
    if info.get("email"):
        safe_raw["email"] = masked_email

    record = {
        "peer": info.get("peer"),
        "model": info.get("model"),
        "errors": list(info.get("errors", [])),
        "domains": {
            "context": context, "quota": quota, "cost": cost,
            "session": session, "account": account, "health": health,
        },
        "raw": safe_raw,
    }
    record["alerts"] = _compute_alerts(record)
    return record


def collect_snapshot():
    peers, peer_dirs = _discover_peers()
    now = datetime.now().astimezone()
    records = []
    for p in peers:
        try:
            info = gather_peer(p, peer_dirs)
        except Exception as exc:
            # Resilience (§11): a broken collector degrades to an unknown record
            # with the error surfaced (never crashes the whole snapshot).
            info = {"peer": p, "empty": True, "ctx_known": False, "source": "none",
                    "errors": [f"collector_error: {type(exc).__name__}: {exc}"]}
        records.append(normalize_peer(info, now))
    return {
        "schema_version": 1,
        "observed_at": now.isoformat(),
        "peers": records,
    }


def render_dashboard(stdout=None):
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

        print("\n" + "=" * 60)
        print(_c(" PEER PROFILES", "bold"))
        print("=" * 60)
        render_profiles(out)

        render_summary(infos)

        print("\n" + "=" * 60)
        print(_c(" PEER DETAIL", "bold"))
        print("=" * 60)
        for info in infos:
            render_card(info)

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
                render_dashboard(out)
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

def render_profiles(stdout=None):
    """Generated-profile matrix from orchestration.json. Never inlines raw
    profile_args / adapter flags (§6.3)."""
    out = stdout or sys.stdout
    out.write("PEER.PROFILE           MODEL                      EFFORT   CTX      ROUTING\n")
    measured_ctx = {}
    try:
        for peer in collect_snapshot().get("peers", []):
            cw = (peer.get("raw") or {}).get("ctx_window")
            if isinstance(cw, (int, float)):
                measured_ctx[peer.get("peer")] = cw
    except Exception:
        measured_ctx = {}
    try:
        orch = json.loads((SYS_DIR / "ai" / "orchestration.json").read_text(encoding="utf-8"))
    except Exception:
        out.write("(orchestration.json unavailable)\n")
        return
    for node in orch.get("hub_nodes", []):
        if node.get("type") != "peer" or not node.get("enabled", True):
            continue
        pid = node.get("node_id", "?")
        for pname, prof in (node.get("profiles") or {}).items():
            model = prof.get("model_id") or prof.get("runtime_model")
            effort = prof.get("reasoning_effort")
            # measured window (live snapshot) is SSOT; declared is capacity-intent fallback
            ctx_val = measured_ctx.get(pid) or prof.get("runtime_context_window") or prof.get("context_window")
            routing = prof.get("routing_state")

            if not ctx_val or not model or not effort:
                try:
                    subdir = resolve_peer_sys_dir(pid)
                    hfile = SYS_DIR / (subdir if subdir else pid) / "health.json"
                    if hfile.exists():
                        hdata = json.loads(hfile.read_text(encoding="utf-8"))
                        hprof = hdata.get("profile", {})
                        if not model:
                            model = hprof.get("model") or hprof.get("model_id") or hprof.get("runtime_model")
                        if not effort:
                            effort = hprof.get("reasoning_effort") or hprof.get("effort")
                        if not ctx_val:
                            ctx_val = hprof.get("context_window") or hdata.get("context_health", {}).get("context_window")
                except Exception:
                    pass

            model_str = str(model) if model else "?"
            effort_str = str(effort) if effort else "?"
            ctx_str = _short(ctx_val) if ctx_val else "?"
            routing_str = str(routing) if routing else "?"
            
            out.write(f"{pid + '.' + pname:<22} {model_str:<26} {effort_str:<8} {ctx_str:<8} {routing_str}\n")


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


def render_sessions(stdout=None):
    """Session state / continuity view."""
    out = stdout or sys.stdout
    out.write("PEER   STATE        SESSIONS_TODAY  DATA\n")
    for p in collect_snapshot()["peers"]:
        s = p.get("domains", {}).get("session", {})
        cnt = s.get("sessions_today")
        out.write(f"{str(p.get('peer') or '?'):<6} {str(s.get('state') or 'unknown'):<12} "
                  f"{(cnt if cnt is not None else '-'):<15} {s.get('source', {}).get('kind', '?')}\n")


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
    render_dashboard(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())