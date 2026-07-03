"""Shared peer telemetry snapshot collection and routing derivation.

Extracted from _sys/cli/diag.py by consensus r-f291 (2026-07-03, W4 Option B).
This module owns collection, normalization, and derived ranking only; CLI
rendering stays in diag.py. hub.py consumes the SAME collect_snapshot() so the
renderer and the failover router share one source of truth.
"""
import os
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

CORE_DIR = Path(__file__).parent
SYS_DIR = CORE_DIR.parent
PORTABLE_ROOT = SYS_DIR.parent
CLI_DIR = SYS_DIR / "cli"

if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from hub_peer import resolve_peer_sys_dir

# In-process snapshot cache for router consumers (hub). CLI renderers collect
# fresh by default so --watch never freezes on a 60s-old frame.
SNAPSHOT_TTL_SEC = 60
_SNAPSHOT_CACHE = {"expires_at": 0.0, "snapshot": None}

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


_REAL_BINARIES = {
    "cc": SYS_DIR / "env" / "nodejs" / "npm-global" / "claude.cmd",
    "cx": SYS_DIR / "env" / "nodejs" / "npm-global" / "codex.cmd",
    # agy lives under _sys/tools, matching orchestration.json invoke path.
    # (was PORTABLE_ROOT/tools/agy — a nonexistent path; cx pre-merge review.)
    "ag": SYS_DIR / "tools" / "agy" / "agy.exe",
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


_CLAUDE_USAGE_SECTIONS = {
    "current session": ("C-5H", 5.0),
    "current week (all models)": ("C-7D", 168.0),
    "current week (fable)": ("F-7D", 168.0),
}


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_claude_usage_reset(text, now=None):
    """Parse Claude `/usage` reset text into ISO8601 local time.

    Examples observed from the real CLI:
    - Jul 3, 11:30am (Asia/Seoul)
    - Jul 7, 10pm (Asia/Seoul)
    - 11:29am (Asia/Seoul)
    """
    if not isinstance(text, str) or not text.strip():
        return None
    now = now or datetime.now().astimezone()
    value = text.strip()
    tz_name = None
    m_tz = re.search(r"\(([^)]+)\)\s*$", value)
    if m_tz:
        tz_name = m_tz.group(1).strip()
        value = value[:m_tz.start()].strip()
    try:
        tz = ZoneInfo(tz_name) if tz_name else now.tzinfo
    except Exception:
        tz = now.tzinfo

    m_date = re.match(
        r"^(?:(?P<mon>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s*)?"
        r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>[ap]m)$",
        value,
        re.IGNORECASE,
    )
    if not m_date:
        return None
    mon_text = m_date.group("mon")
    if mon_text:
        month = _MONTHS.get(mon_text.lower())
        day = int(m_date.group("day"))
    else:
        month = now.month
        day = now.day
    if not month:
        return None
    hour = int(m_date.group("hour"))
    minute = int(m_date.group("minute") or 0)
    ampm = m_date.group("ampm").lower()
    if hour == 12:
        hour = 0
    if ampm == "pm":
        hour += 12
    try:
        dt = datetime(now.year, month, day, hour, minute, tzinfo=tz)
    except ValueError:
        return None
    now_in_tz = now.astimezone(tz)
    if mon_text and dt < now_in_tz - timedelta(days=30):
        try:
            dt = datetime(now.year + 1, month, day, hour, minute, tzinfo=tz)
        except ValueError:
            pass
    elif not mon_text and dt < now_in_tz:
        dt = dt + timedelta(days=1)
    return dt.astimezone().isoformat()


def _claude_usage_emit(section, used_pct, reset_text, now=None):
    key = str(section or "").strip().lower()
    spec = _CLAUDE_USAGE_SECTIONS.get(key)
    if not spec:
        return None
    reset_at = _parse_claude_usage_reset(reset_text, now=now)
    if reset_at is None:
        return None
    try:
        used_frac = max(0.0, min(1.0, float(used_pct) / 100.0))
    except (TypeError, ValueError):
        return None
    label, window_hours = spec
    import quota as qmgr
    rem_sec = qmgr.get_remaining_seconds(resets_at_iso=reset_at)
    pacing = qmgr.calculate_pacing(used_frac, rem_sec, window_hours)
    return {
        "label": label,
        "used_frac": used_frac,
        "pacing": pacing,
        "reset": _fmt_reset(reset_at),
        "source": "cc_usage",
        "metric": f"{float(used_pct):.0f}% used{_fmt_pacing(pacing)}",
        "pacing_ratio": pacing.get("ratio"),
        "pacing_status": pacing.get("status"),
    }


def _parse_claude_usage(text, now=None):
    """Parse explicit quota/reset rows from real `claude /usage` output."""
    if not isinstance(text, str) or not text.strip():
        return []
    rows = []
    current_section = None
    current_pct = None
    inline = re.compile(
        r"^(Current session|Current week \(all models\)|Current week \(Fable\)):"
        r"\s*([0-9]+(?:\.[0-9]+)?)%\s+used\b.*?\bresets\s+(.+)$",
        re.IGNORECASE,
    )
    section_names = {k.lower(): k for k in _CLAUDE_USAGE_SECTIONS}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = inline.match(line)
        if m:
            row = _claude_usage_emit(m.group(1), m.group(2), m.group(3), now=now)
            if row:
                rows.append(row)
            current_section = None
            current_pct = None
            continue
        lowered = line.lower().rstrip(":")
        if lowered in section_names:
            current_section = section_names[lowered]
            current_pct = None
            continue
        if current_section and current_pct is None:
            m_pct = re.search(r"([0-9]+(?:\.[0-9]+)?)%\s+used\b", line, re.IGNORECASE)
            if m_pct:
                current_pct = m_pct.group(1)
            continue
        if current_section and current_pct is not None:
            m_reset = re.search(r"\bresets?\s+(.+)$", line, re.IGNORECASE)
            if m_reset:
                row = _claude_usage_emit(current_section, current_pct, m_reset.group(1), now=now)
                if row:
                    rows.append(row)
                current_section = None
                current_pct = None
    return rows


def _claude_usage_quotas(deadline_sec=12):
    """Run the real Claude CLI usage command. No help-output inference."""
    claude_exe = _real_binary("cc")
    if not claude_exe:
        return None
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str((SYS_DIR / "claude" / "config").resolve())
    try:
        proc = subprocess.run(
            [claude_exe, "/usage"],
            cwd=str(PORTABLE_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=deadline_sec,
            errors="replace",
        )
    except Exception:
        return None
    text = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    quotas = _parse_claude_usage(text)
    return quotas or None


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


_CLAUDE_USAGE_CACHE = {}


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


def _cached_claude_usage_quotas(ttl_sec=EXPENSIVE_SOURCE_TTL_SEC, clock=time.monotonic):
    now = clock()
    cached = _CLAUDE_USAGE_CACHE.get("usage")
    if cached and now < cached["expires_at"]:
        return cached["value"]
    value = _claude_usage_quotas()
    _CLAUDE_USAGE_CACHE["usage"] = {
        "value": value,
        "expires_at": now + ttl_sec,
    }
    return value


def _discover_peers():
    """Return (peers, peer_dirs) from orchestration.json, with a static fallback."""
    peers = []
    peer_dirs = {}
    try:
        orch_data = _read_orchestration()
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


def _read_orchestration():
    return json.loads((SYS_DIR / "ai" / "orchestration.json").read_text(encoding="utf-8"))


def _read_json_file(path):
    try:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        try:
            observed = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).astimezone().isoformat()
        except OSError:
            observed = datetime.now().astimezone().isoformat()
        return data, observed
    except Exception:
        return {}, None


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
    if peer == "cc":
        usage_quotas = _cached_claude_usage_quotas()
        if usage_quotas:
            usage_labels = {q.get("label") for q in usage_quotas}
            quotas = [
                q for q in quotas
                if q.get("label") not in usage_labels and q.get("source") != "cc_usage"
            ]
            quotas.extend(usage_quotas)
            info["quota_observed_at"] = datetime.now().astimezone().isoformat()
            info["quota_source_kind"] = "live"
            info["quota_source_tag"] = "cli_live"

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


def _source_tag(record, domain_name):
    """Specific source tag for profile rows; missing data stays absent."""
    if domain_name == "quota":
        buckets = (((record.get("domains") or {}).get("quota") or {}).get("buckets") or [])
        bucket_sources = {b.get("source") for b in buckets if isinstance(b, dict)}
        if "cc_usage" in bucket_sources:
            return "cli_live"
    raw_source = (record.get("raw") or {}).get("source")
    if raw_source == "app-server":
        return "app_server"
    if raw_source == "live":
        return "statusline"
    if raw_source == "health":
        return "health"
    source = (((record.get("domains") or {}).get(domain_name) or {}).get("source") or {}).get("kind")
    if source == "live":
        return "cli_live"
    if source == "cached":
        return "health"
    return "absent"


def _quota_family_for_profile(peer_id, profile_name):
    if peer_id == "cc":
        return "F-" if profile_name == "fable" else "C-"
    if peer_id == "ag":
        return "3P-" if profile_name in {"opus", "gptoss", "sonnet"} else "G-"
    if peer_id == "cx":
        return "X-"
    return None


def _filter_profile_buckets(peer_id, profile_name, buckets):
    family = _quota_family_for_profile(peer_id, profile_name)
    if not family:
        return list(buckets or [])
    return [b for b in (buckets or []) if str(b.get("label", "")).startswith(family)]


def _profile_source(kind, tag, observed_at, confidence="last_known"):
    ttl = EXPENSIVE_SOURCE_TTL_SEC if tag == "app_server" else _LOCAL_TTL_SEC
    return {"source": _source_meta(kind, observed_at, ttl, confidence), "source_tag": tag}


def _build_profile_rows(orch, peer_records, observed_at):
    """First-class per-profile rows derived from one collected peer snapshot."""
    by_peer = {rec.get("peer"): rec for rec in peer_records or []}
    rows = []
    for node in orch.get("hub_nodes", []):
        if node.get("type") != "peer" or not node.get("enabled", True):
            continue
        peer_id = node.get("node_id")
        if not peer_id:
            continue
        peer_rec = by_peer.get(peer_id, {})
        domains = peer_rec.get("domains") or {}
        root_ctx = domains.get("context") or {}
        root_quota = domains.get("quota") or {}
        default_profile = node.get("default_profile")
        for profile_name, prof in (node.get("profiles") or {}).items():
            model = prof.get("model_id") or prof.get("runtime_model")
            effort = prof.get("reasoning_effort")
            declared_ctx = prof.get("runtime_context_window") or prof.get("context_window")
            use_active_ctx = (
                profile_name == default_profile
                and isinstance(root_ctx.get("window_tokens"), (int, float))
            )
            if use_active_ctx:
                ctx_tag = _source_tag(peer_rec, "context")
                context = {
                    "window_tokens": root_ctx.get("window_tokens"),
                    "used_tokens": root_ctx.get("used_tokens"),
                    "utilization_pct": root_ctx.get("utilization_pct"),
                    "basis": "measured_active_profile",
                    **_profile_source(root_ctx.get("source", {}).get("kind", "live"), ctx_tag,
                                      root_ctx.get("source", {}).get("observed_at", observed_at),
                                      root_ctx.get("source", {}).get("confidence", "exact")),
                }
            elif isinstance(declared_ctx, (int, float)):
                context = {
                    "window_tokens": declared_ctx,
                    "used_tokens": None,
                    "utilization_pct": None,
                    "basis": "declared_profile_capacity",
                    **_profile_source("cached", "orchestration", observed_at),
                }
            else:
                context = {
                    "window_tokens": None,
                    "used_tokens": None,
                    "utilization_pct": None,
                    "basis": "unavailable",
                    **_profile_source("unknown", "absent", observed_at, "unknown"),
                }

            buckets = _filter_profile_buckets(peer_id, profile_name, root_quota.get("buckets") or [])
            if buckets:
                quota_tag = _source_tag(peer_rec, "quota")
                quota = {
                    "buckets": buckets,
                    **_profile_source(root_quota.get("source", {}).get("kind", "live"), quota_tag,
                                      root_quota.get("source", {}).get("observed_at", observed_at),
                                      root_quota.get("source", {}).get("confidence", "exact")),
                }
            else:
                quota = {"buckets": [], **_profile_source("unknown", "absent", observed_at, "unknown")}

            # measured > declared (FP-2): the ACTIVE profile shows the live model
            # from the peer snapshot, source-tagged; non-active keep the declared
            # orchestration value (rendered "[decl]" downstream).
            is_active = profile_name == default_profile
            measured_model = peer_rec.get("model")
            if is_active and measured_model and measured_model != "Unknown":
                model = str(measured_model)
                raw_source = (peer_rec.get("raw") or {}).get("source")
                model_tag = {
                    "app-server": "app_server",
                    "live": "statusline",
                    "health": "health",
                }.get(raw_source, "absent")
            else:
                model_tag = "orchestration" if model else "absent"
            effort_tag = "orchestration" if effort else "absent"
            routing_tag = "orchestration" if prof.get("routing_state") else "absent"
            rows.append({
                "profile": f"{peer_id}.{profile_name}",
                "peer": peer_id,
                "profile_name": profile_name,
                "model": model,
                "effort": effort,
                "cost_tier": prof.get("cost_tier"),
                "routing_state": prof.get("routing_state"),
                "state": prof.get("routing_state") or "unknown",
                "context": context,
                "quota": quota,
                "sources": {
                    "model": model_tag,
                    "effort": effort_tag,
                    "context": context.get("source_tag"),
                    "quota": quota.get("source_tag"),
                    "routing": routing_tag,
                },
            })
    return rows


_EFFORT_STRENGTH = {
    "low": 1,
    "medium": 2,
    "mid": 2,
    "high": 3,
    "max": 4,
    "xhigh": 4,
}


def _clamped_remaining_from_used_frac(used_frac):
    if not isinstance(used_frac, (int, float)):
        return None
    return max(0.0, min(1.0, 1.0 - float(used_frac)))


def _quota_remaining(profile_row):
    buckets = ((profile_row.get("quota") or {}).get("buckets") or [])
    values = []
    for bucket in buckets:
        remaining = _clamped_remaining_from_used_frac(bucket.get("used_frac"))
        if remaining is not None:
            values.append(remaining)
    return min(values) if values else None


def _context_remaining(profile_row):
    util = (profile_row.get("context") or {}).get("utilization_pct")
    if not isinstance(util, (int, float)):
        return None
    return max(0.0, min(1.0, 1.0 - (float(util) / 100.0)))


def _effort_strength(value):
    return _EFFORT_STRENGTH.get(str(value or "").lower(), 0)


def _derive_headroom_rows(snapshot):
    """Derived routing headroom. Missing inputs remain absent, never estimated."""
    rows = []
    profiles = snapshot.get("profiles") or []
    max_eligible_strength = max(
        (_effort_strength(row.get("effort")) for row in profiles if row.get("state") == "eligible"),
        default=0,
    )
    for profile in profiles:
        quota_remaining = _quota_remaining(profile)
        context_remaining = _context_remaining(profile)
        headroom = (
            min(quota_remaining, context_remaining)
            if quota_remaining is not None and context_remaining is not None
            else None
        )
        strength = _effort_strength(profile.get("effort"))
        rows.append({
            "profile": profile.get("profile"),
            "peer": profile.get("peer"),
            "state": profile.get("state") or "unknown",
            "effort": profile.get("effort"),
            "cost_tier": profile.get("cost_tier"),
            "quota_remaining": quota_remaining,
            "context_remaining": context_remaining,
            "headroom": headroom,
            "tier_strength": strength,
            "tier_risk": (
                headroom is not None
                and profile.get("state") == "eligible"
                and strength < max_eligible_strength
            ),
            "sources": profile.get("sources") or {},
        })
    rows.sort(key=lambda r: (
        r.get("headroom") is not None,
        r.get("state") == "eligible",
        r.get("headroom") if r.get("headroom") is not None else -1.0,
        r.get("tier_strength", 0),
    ), reverse=True)
    return rows


def _next_headroom_target(rows):
    candidates = [
        row for row in rows
        if row.get("state") == "eligible" and isinstance(row.get("headroom"), (int, float))
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (r["headroom"], r.get("tier_strength", 0), r.get("profile") or ""))


def _fmt_remaining(value):
    if not isinstance(value, (int, float)):
        return "absent"
    return f"{max(0.0, min(1.0, value)) * 100:.0f}%"


def _profile_id_from_scope(scope_key, peer_id):
    text = str(scope_key or "")
    if ":" in text:
        candidate = text.rsplit(":", 1)[1]
        return candidate or peer_id
    return peer_id


def _session_context_measured(peer_id, entry, profile_row, observed_at):
    """Per-session context/model read from a REAL per-session source only (FP-1).
    cx: state_5.sqlite threads(id)->rollout_path; cc: projects/*/<session_id>.jsonl.
    No per-session source (ag, missing file, unknown id) => absent — a profile
    aggregate is NEVER copied into a session row (DIR-004)."""
    session_id = entry.get("session_id")
    window = ((profile_row or {}).get("context") or {}).get("window_tokens")

    def _absent():
        return {
            "used_tokens": None,
            "window_tokens": window if isinstance(window, (int, float)) else None,
            "utilization_pct": None,
            "source": _source_meta("unknown", observed_at, _LOCAL_TTL_SEC, "unknown"),
            "source_tag": "absent",
            "measured_model": None,
        }

    if not session_id:
        return _absent()

    if peer_id == "cx":
        db_path = SYS_DIR / "codex" / "config" / "state_5.sqlite"
        if db_path.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                row = conn.execute(
                    "SELECT rollout_path, model FROM threads WHERE id=?",
                    (session_id,)).fetchone()
                conn.close()
                if row and row[0]:
                    used, win = _parse_rollout_context(row[0])
                    if isinstance(used, (int, float)):
                        if not isinstance(win, (int, float)):
                            win = window if isinstance(window, (int, float)) else None
                        pct = round(used / win * 100, 1) if isinstance(win, (int, float)) and win else None
                        return {
                            "used_tokens": used,
                            "window_tokens": win,
                            "utilization_pct": pct,
                            "source": _source_meta("cached", observed_at, _LOCAL_TTL_SEC, "exact"),
                            "source_tag": "rollout",
                            "measured_model": str(row[1]) if row[1] else None,
                        }
            except Exception:
                pass
        return _absent()

    if peer_id == "cc":
        base_dir = SYS_DIR / "claude" / "config" / "projects"
        if base_dir.exists():
            try:
                found = sorted(base_dir.glob(f"*/{session_id}.jsonl"))
                if found:
                    lines = found[0].read_text(encoding="utf-8").splitlines()
                    for line in reversed(lines[-100:]):
                        if '"usage"' not in line:
                            continue
                        try:
                            obj = json.loads(line)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        msg = obj.get("message")
                        if not isinstance(msg, dict):
                            continue
                        usage = msg.get("usage")
                        if not isinstance(usage, dict):
                            continue
                        used = (usage.get("input_tokens", 0)
                                + usage.get("cache_read_input_tokens", 0)
                                + usage.get("cache_creation_input_tokens", 0)
                                + usage.get("output_tokens", 0))
                        pct = round(used / window * 100, 1) if isinstance(window, (int, float)) and window else None
                        return {
                            "used_tokens": used,
                            "window_tokens": window if isinstance(window, (int, float)) else None,
                            "utilization_pct": pct,
                            "source": _source_meta("cached", observed_at, _LOCAL_TTL_SEC, "exact"),
                            "source_tag": "session_jsonl",
                            "measured_model": msg.get("model"),
                        }
            except Exception:
                pass
        return _absent()

    return _absent()


def _build_session_rows(peers, peer_dirs, profiles, observed_at):
    """Active session rows with lease/context attached. History stays out."""
    leases, lease_observed = _read_json_file(PORTABLE_ROOT / ".ai" / "leases.json")
    profiles_by_id = {row.get("profile"): row for row in profiles or []}
    rows = []
    for peer_id in peers:
        session_path = peer_dirs.get(peer_id, SYS_DIR / peer_id) / "session_state.json"
        state, session_observed = _read_json_file(session_path)
        active = state.get("active") if isinstance(state, dict) else {}
        if not isinstance(active, dict):
            continue
        for scope_key, entry in active.items():
            if not isinstance(entry, dict):
                continue
            profile_id = _profile_id_from_scope(entry.get("scope_key") or scope_key, peer_id)
            lease = leases.get(profile_id) or leases.get(peer_id) or {}
            profile_row = profiles_by_id.get(profile_id)
            ctx = _session_context_measured(peer_id, entry, profile_row, observed_at)
            measured_model = ctx.pop("measured_model", None)
            profile_model = (profile_row or {}).get("model")
            if measured_model:
                session_model = str(measured_model)
            elif profile_model:
                session_model = f"[decl] {profile_model}"
            else:
                session_model = "absent"
            rows.append({
                "peer": peer_id,
                "profile": profile_id,
                "scope_key": entry.get("scope_key") or scope_key,
                "session_id": entry.get("session_id"),
                "status": entry.get("status") or "unknown",
                "created_at": entry.get("created_at"),
                "last_used_at": entry.get("last_used_at"),
                "last_ask_id": entry.get("last_ask_id"),
                "model": session_model,
                "context": ctx,
                "lease": {
                    "status": lease.get("status") if isinstance(lease, dict) else None,
                    "expires_at": lease.get("expires_at") if isinstance(lease, dict) else None,
                    "heartbeat_at": lease.get("heartbeat_at") if isinstance(lease, dict) else None,
                    "source": _source_meta(
                        "cached" if lease else "unknown",
                        lease_observed or observed_at,
                        _LOCAL_TTL_SEC,
                        "last_known" if lease else "unknown",
                    ),
                },
                "source": _source_meta(
                    "cached",
                    session_observed or observed_at,
                    _LOCAL_TTL_SEC,
                    "last_known",
                ),
            })
    rows.sort(key=lambda r: (str(r.get("last_used_at") or ""), str(r.get("profile") or "")), reverse=True)
    return rows


QUOTA_WARN_FRAC = 0.75


QUOTA_CRIT_FRAC = 0.90


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
        msg = f"source data {int(age)}s old (> {STALE_THRESHOLD_SEC}s); may be pre-reset"
        # DIR-004: distinguish a freshly-measured quota source from stale general
        # data so the reader does not discard a live quota reading (measured >
        # declared applies to freshness too).
        quota_tag = _source_tag(record, "quota")
        if quota_tag in ("cli_live", "app_server"):
            msg += f" — but quota source is {quota_tag} (freshly measured)"
        alerts.append(_alert("warn", "SOURCE_STALE", msg))

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
    expensive = (
        info.get("peer") == "cx"
        or any(q.get("expensive") or q.get("source") == "cc_usage" for q in quotas)
    )
    quota_kind = info.get("quota_source_kind") or kind
    quota_observed = info.get("quota_observed_at") or observed
    quota = {
        "buckets": quotas,
        "source": _source_meta(quota_kind if quotas else "unknown", quota_observed,
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


def collect_snapshot(use_cache=False, clock=time.monotonic):
    """One normalized snapshot consumed by BOTH the diag renderer and the hub
    failover router (r-f291 SSOT). `use_cache=True` (router path) reuses an
    in-process snapshot for SNAPSHOT_TTL_SEC; CLI renderers default to fresh
    collection so --watch frames never freeze."""
    if use_cache:
        cached = _SNAPSHOT_CACHE.get("snapshot")
        if cached is not None and clock() < float(_SNAPSHOT_CACHE.get("expires_at", 0.0)):
            return cached
    peers, peer_dirs = _discover_peers()
    now = datetime.now().astimezone()
    observed_at = now.isoformat()
    records = []
    for p in peers:
        try:
            info = gather_peer(p, peer_dirs)
        except Exception as exc:
            # Resilience: a broken collector degrades to an unknown record
            # with the error surfaced (never crashes the whole snapshot).
            info = {"peer": p, "empty": True, "ctx_known": False, "source": "none",
                    "errors": [f"collector_error: {type(exc).__name__}: {exc}"]}
        records.append(normalize_peer(info, now))
    profile_errors = []
    try:
        profiles = _build_profile_rows(_read_orchestration(), records, observed_at)
    except Exception as exc:
        profiles = []
        profile_errors.append(f"profile_rows: {type(exc).__name__}: {exc}")
    try:
        sessions = _build_session_rows(peers, peer_dirs, profiles, observed_at)
    except Exception as exc:
        sessions = []
        profile_errors.append(f"session_rows: {type(exc).__name__}: {exc}")
    snapshot = {
        "schema_version": 1,
        "observed_at": observed_at,
        "peers": records,
        "profiles": profiles,
        "sessions": sessions,
    }
    if profile_errors:
        snapshot["errors"] = profile_errors
    if use_cache:
        _SNAPSHOT_CACHE["snapshot"] = snapshot
        _SNAPSHOT_CACHE["expires_at"] = clock() + SNAPSHOT_TTL_SEC
    return snapshot


def snapshot_hash(snapshot):
    """Canonical sha256 of a snapshot for routing-decision audit trails."""
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshot_failover_target(exclude=None, snapshot=None):
    """Best failover profile row from headroom ranking (max headroom, eligible
    only), skipping excluded profiles/peers. Returns the row or None."""
    exclude_set = {str(item) for item in (exclude or []) if item}
    snapshot = snapshot if snapshot is not None else collect_snapshot(use_cache=True)
    for row in _derive_headroom_rows(snapshot):
        if row.get("state") != "eligible":
            continue
        if not isinstance(row.get("headroom"), (int, float)):
            continue
        if row.get("profile") in exclude_set or row.get("peer") in exclude_set:
            continue
        return row
    return None


def select_load_balanced_peer(snapshot, config, terminal_peer=None, ask_id="", rng=None):
    """Token load balancer — Phase 1 (design: ops/token-load-balancing-design.md).

    Route an ask to the peer that best equalizes token burn-down: peer-level
    aggregation of headroom, HARD terminal exclusion (the terminal is dropped
    whenever any non-terminal peer has headroom >= floor — the "terminal tokens
    always minimal" requirement), numeric cost tie-break, and a DETERMINISTIC
    seeded weighted-random draw (seed = sha256(snapshot_hash:ask_id)) so every
    decision is reproducible and auditable. Pure; no I/O. (P1 omits pacing=P2,
    in-flight deduction/task-size=P1.5, warm-up=P2.)

    Returns an audit dict: selected row/peer, per-peer weights + probabilities,
    seed, draw, terminal_excluded reason, candidate peers, and a reason code.
    """
    import random as _random
    eps = 0.01
    cost_map = config.get("cost_map", {}) or {}
    floor = config.get("effective_headroom_floor", 0.10)
    hard_exclude = config.get("terminal_hard_exclude", True)

    def _empty(reason):
        return {"selected": None, "selected_peer": None, "weights": {},
                "probabilities": {}, "terminal_excluded": None, "seed": None,
                "draw": None, "candidates": [], "reason": reason}

    # Candidate prefilter (hard): eligible + measured (non-absent) headroom.
    candidates = [
        r for r in _derive_headroom_rows(snapshot)
        if r.get("state") == "eligible" and isinstance(r.get("headroom"), (int, float))
    ]
    if not candidates:
        return _empty("no_eligible_candidate")

    # Peer-level aggregation: each peer's representative = its max-headroom row
    # (so multiple profiles of one peer are not double-weighted).
    representatives = {}
    for r in candidates:
        peer = r.get("peer")
        cur = representatives.get(peer)
        if cur is None or r["headroom"] > cur["headroom"]:
            representatives[peer] = r
    peers = list(representatives.keys())

    # Effective headroom (P1: no pacing) minus numeric cost tie-break.
    raw_weights = {}
    for peer in peers:
        rep = representatives[peer]
        ct = rep.get("cost_tier")
        cost = cost_map.get(ct, 0.0) if isinstance(ct, str) else 0.0
        raw_weights[peer] = max(eps, float(rep["headroom"]) - cost)

    # HARD terminal exclusion: if any non-terminal peer is at/above the floor,
    # the terminal is zeroed out (never a discount — always minimal).
    terminal_excluded = None
    if hard_exclude and terminal_peer and terminal_peer in raw_weights:
        if any(float(representatives[p]["headroom"]) >= floor
               for p in peers if p != terminal_peer):
            raw_weights[terminal_peer] = 0.0
            terminal_excluded = "non_terminal_above_floor"

    total = sum(raw_weights.values())
    if total <= 0.0:
        return _empty("no_positive_weight")

    # Deterministic seeded weighted-random over positive-weight peers only
    # (a zeroed/excluded peer is never drawn, even if draw == 0.0).
    seed = int(hashlib.sha256(f"{snapshot_hash(snapshot)}:{ask_id}".encode("utf-8")).hexdigest()[:16], 16)
    rng = rng or _random.Random(seed)
    draw = rng.random()
    positive_peers = [p for p in peers if raw_weights[p] > 0.0]
    selected_peer = None
    cursor = 0.0
    for peer in positive_peers:
        cursor += raw_weights[peer] / total
        if draw <= cursor:
            selected_peer = peer
            break
    if selected_peer is None:
        selected_peer = positive_peers[-1]

    return {
        "selected": representatives[selected_peer],
        "selected_peer": selected_peer,
        "weights": {peer: round(raw_weights[peer], 4) for peer in peers},
        "probabilities": {peer: round(raw_weights[peer] / total, 4) for peer in peers},
        "terminal_excluded": terminal_excluded,
        "seed": seed,
        "draw": draw,
        "candidates": peers,
        "reason": "selected",
    }
