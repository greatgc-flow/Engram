"""Shared peer telemetry snapshot collection and routing derivation.

Extracted from _sys/cli/diag.py by consensus r-f291 (2026-07-03, W4 Option B).
This module owns collection, normalization, and derived ranking only; CLI
rendering stays in diag.py. hub.py consumes the SAME collect_snapshot() so the
renderer and the failover router share one source of truth.
"""
import os
import copy
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

# ── Telemetry config (MECE constants; token-session-policy-design-2026-07-08) ──
# Operational constants live in _sys/ai/telemetry-config.json; a missing/invalid
# key degrades to the documented default here (never crashes). Vendor facts
# (quota window_hours 5/168) and math invariants stay in code.
_TELEMETRY_DEFAULTS = {
    "ttl": {"snapshot_sec": 60, "expensive_source_sec": 60, "local_sec": 5},
    "probe": {"deadline_sec": 12},
    "display": {"warn_frac": 0.75, "crit_frac": 0.90},
    "watch": {"default_interval_sec": 5, "min_interval_sec": 2, "sync_output": "auto"},
}
_TELEMETRY_CACHE = {"cfg": None}


def telemetry_config():
    """Load _sys/ai/telemetry-config.json merged over defaults (cached).

    Provenance for the diag POLICY panel: (value, "telemetry-config.json:<path>").
    """
    if _TELEMETRY_CACHE["cfg"] is not None:
        return _TELEMETRY_CACHE["cfg"]
    cfg = {k: dict(v) for k, v in _TELEMETRY_DEFAULTS.items()}
    try:
        raw = json.loads((SYS_DIR / "ai" / "telemetry-config.json").read_text(encoding="utf-8"))
        for section, defaults in _TELEMETRY_DEFAULTS.items():
            got = raw.get(section)
            if isinstance(got, dict):
                for key, dflt in defaults.items():
                    val = got.get(key, dflt)
                    # type-guard: keep the default if the override is the wrong type
                    cfg[section][key] = val if isinstance(val, type(dflt)) else dflt
    except Exception:
        pass  # any read/parse failure -> documented defaults
    _TELEMETRY_CACHE["cfg"] = cfg
    return cfg


def _tcfg(section, key):
    return telemetry_config()[section][key]


# In-process snapshot cache for router consumers (hub). CLI renderers collect
# fresh by default so --watch never freezes on a stale frame.
SNAPSHOT_TTL_SEC = telemetry_config()["ttl"]["snapshot_sec"]
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


def _kill_process_tree_windows(pid: int) -> None:
    """Kill pid AND its full descendant tree. `codex.cmd` -> cmd.exe -> node.exe ->
    codex.exe is a 3+ level chain; a bare proc.kill() on the Popen handle only
    kills the immediate cmd.exe wrapper, orphaning node.exe/codex.exe forever.
    Found live 2026-07-17 (closure review, cx.deepthink): 558 orphaned node.exe +
    558 codex.exe processes (~41GB working set), accumulating ~1/minute at the
    probe's TTL cadence with none ever reaped. taskkill /T reaps the whole tree;
    no psutil dependency needed (this module doesn't otherwise import it)."""
    if not pid or pid < 0:
        return
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True, timeout=10)
    except Exception:
        pass


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


def _codex_rate_limits(deadline_sec=None):
    """Query the codex app-server (initialize -> initialized -> account/rateLimits/read)
    for live 5h/weekly rate-limit reset times AND any rate-limit reset credits.
    Codex does not persist these locally.

    A background reader thread feeds lines to a queue so the deadline is honored
    EVEN IF proc.stdout.readline() blocks (the app-server is a daemon and, under a
    denied sandbox, can spawn-EPERM and never emit — which previously hung diag for
    tens of minutes). Returns the complete result dict (rateLimits +
    rateLimitsByLimitId + rateLimitResetCredits, each independently absent/null/
    object per design doc §2.1) or None.

    No top-level "jsonrpc" envelope: this mirrors the app-server's own framing,
    confirmed via [cli_live] protocol generation of the installed Codex CLI."""
    if deadline_sec is None:
        deadline_sec = _tcfg("probe", "deadline_sec")
    import threading, queue
    codex_exe = _codex_binary()
    if not codex_exe:
        return None
    proc = None
    try:
        proc = subprocess.Popen([codex_exe, "app-server"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

        q: "queue.Queue" = queue.Queue()

        def _reader():
            try:
                while True:
                    line = proc.stdout.readline()
                    # `not line` alone assumes a well-behaved pipe (real subprocess
                    # closing stdout -> b""); also bail once the process itself has
                    # exited, so a readline() that keeps returning something
                    # non-empty-but-meaningless (e.g. T73: a mocked stdout in tests
                    # that don't isolate subprocess.Popen from this module) can't
                    # spin this thread and its queue unbounded.
                    if not line or proc.poll() is not None:
                        break
                    q.put(line)
            except Exception:
                pass
            q.put(None)  # EOF / reader-done sentinel

        threading.Thread(target=_reader, daemon=True).start()
        deadline = time.monotonic() + deadline_sec

        def _wait_for_id(expected_id):
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                try:
                    line = q.get(timeout=min(0.5, remaining))
                except queue.Empty:
                    continue
                if line is None:
                    return None
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("id") == expected_id and isinstance(obj.get("result"), dict):
                    return obj["result"]

        try:
            proc.stdin.write(json.dumps({
                "id": 0, "method": "initialize", "params": {
                    "clientInfo": {"name": "hub-credit", "version": "1.0"},
                    "capabilities": {"experimentalApi": True},
                },
            }) + "\n")
            proc.stdin.flush()
        except Exception:
            return None

        # Wait for id:0's success before sending `initialized` + the request --
        # a strict app-server may reject a premature `initialized` notification
        # (design doc §2.4).
        if _wait_for_id(0) is None:
            return None

        try:
            proc.stdin.write(json.dumps({"method": "initialized"}) + "\n")
            proc.stdin.write(json.dumps({
                "id": 1, "method": "account/rateLimits/read", "params": None,
            }) + "\n")
            proc.stdin.flush()
        except Exception:
            return None

        return _wait_for_id(1)
    except Exception:
        pass
    finally:
        if proc and proc.poll() is None:
            _kill_process_tree_windows(proc.pid)
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
        "reset_at": reset_at,
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


def _claude_usage_quotas(deadline_sec=None):
    """Run the real Claude CLI usage command. No help-output inference."""
    if deadline_sec is None:
        deadline_sec = _tcfg("probe", "deadline_sec")
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


EXPENSIVE_SOURCE_TTL_SEC = telemetry_config()["ttl"]["expensive_source_sec"]


_CODEX_RATE_LIMIT_CACHE = {}


_CLAUDE_USAGE_CACHE = {}


def clear_expensive_cache():
    """Drop the in-process expensive-source caches (codex rate-limits, claude
    /usage) so the next collect re-probes. Backs diag `--fresh` (design 2026-07-08
    freshness §): watch keeps the 60s TTL by default; --fresh forces one bypass."""
    _CODEX_RATE_LIMIT_CACHE.clear()
    _CLAUDE_USAGE_CACHE.clear()


def expensive_source_age_sec(clock=time.monotonic):
    """Age (seconds) of the OLDEST live expensive-source cache entry, or None if
    nothing is cached. Surfaced so the UI can show 'quota cached Ns ago' instead
    of implying the value is real-time (peers: transparency default)."""
    ttl = EXPENSIVE_SOURCE_TTL_SEC
    ages = []
    for cache, key in ((_CODEX_RATE_LIMIT_CACHE, "rate_limits"), (_CLAUDE_USAGE_CACHE, "usage")):
        entry = cache.get(key)
        if entry and "expires_at" in entry:
            ages.append(max(0, int(ttl - (float(entry["expires_at"]) - clock()))))
    return max(ages) if ages else None


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


def _codex_quota_buckets(rate_limits):
    """Normalize Codex app-server rate-limit buckets using reported windows."""
    if not isinstance(rate_limits, dict):
        return []

    buckets = []
    legacy_windows = {
        "primary": ("X-5H", 5.0),
        "secondary": ("X-7D", 168.0),
    }
    for key in ("primary", "secondary"):
        q = rate_limits.get(key)
        if not isinstance(q, dict):
            continue

        label, window_hours = legacy_windows[key]
        duration_mins = q.get("windowDurationMins")
        if duration_mins is not None:
            try:
                reported_hours = float(duration_mins) / 60.0
                if reported_hours <= 0:
                    raise ValueError("window duration must be positive")
                if reported_hours <= 24:
                    reported_label = f"X-{round(reported_hours)}H"
                else:
                    reported_label = f"X-{round(reported_hours / 24.0)}D"
            except (TypeError, ValueError, OverflowError):
                pass
            else:
                label = reported_label
                window_hours = reported_hours

        used = q.get("usedPercent", 0) or 0
        used_frac = used / 100.0

        import quota as qmgr
        resets_at = q.get("resetsAt")
        reset_at = _parse_reset(resets_at)
        rem_sec = qmgr.get_remaining_seconds(resets_at_iso=resets_at)
        pacing = qmgr.calculate_pacing(used_frac, rem_sec, window_hours)

        buckets.append({
            "label": label, "used_frac": used_frac,
            "reset": _fmt_reset(resets_at),
            "reset_at": reset_at.isoformat() if reset_at else None,
            "pacing": pacing,
            "metric": f"{float(used):.1f}% used{_fmt_pacing(pacing)}",
            "pacing_ratio": pacing.get("ratio"), "pacing_status": pacing.get("status"),
        })
    return buckets


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


def _capture_profile_from_active_session(peer_id, peer_dir, session_id):
    """Resolve a capture to a profile only through an exact active-session id.

    Model/display-name matching is intentionally excluded: aliases and sibling
    profiles can share a model, so it is not reliable provenance (DIR-004).
    """
    if not session_id:
        return None
    state, _ = _read_json_file(Path(peer_dir) / "session_state.json")
    active = state.get("active") if isinstance(state, dict) else None
    if not isinstance(active, dict):
        return None
    matches = set()
    for scope_key, entry in active.items():
        if not isinstance(entry, dict):
            continue
        if str(entry.get("session_id") or "") != str(session_id):
            continue
        profile_id = _profile_id_from_scope(entry.get("scope_key") or scope_key, peer_id)
        if str(profile_id).startswith(f"{peer_id}."):
            matches.add(str(profile_id))
    return next(iter(matches)) if len(matches) == 1 else None


_AG_QUOTA_LABELS = {
    "gemini-5h": "G-5H", "gemini-weekly": "G-7D",
    "3p-5h": "3P-5H", "3p-weekly": "3P-7D",
}

# ag has no active quota probe (unlike cc's /usage CLI call and cx's app-server
# RPC) -- its quota is read passively from ag_statusline_stdin.log, which only
# updates when an ag session's statusline renders. A partial/init statusline
# frame (or simply no ag session running recently) can leave that file with no
# usable "quota" key, which used to drop straight to zero quota rows / ABS in
# diag even though a perfectly good quota reading was seen minutes/hours ago.
# This cache preserves the last frame that DID have real quota data, so a gap
# degrades to "stale but shown" instead of "gone" (2026-07-19, cx design).
_AG_LAST_GOOD_QUOTA_PATH = SYS_DIR / "data" / "temp" / "ag_last_good_quota.json"


def _load_ag_last_good_quota():
    try:
        return json.loads(_AG_LAST_GOOD_QUOTA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_ag_last_good_quota(quotas, observed_at):
    try:
        _AG_LAST_GOOD_QUOTA_PATH.parent.mkdir(parents=True, exist_ok=True)
        _AG_LAST_GOOD_QUOTA_PATH.write_text(
            json.dumps({"quotas": quotas, "observed_at": observed_at}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


# ag's statusline log is overwrite-only (single latest frame) but DOES carry
# exact per-session context/token data while it's live -- _session_context_
# measured (RECENT SESSIONS) previously had no ag branch at all and fell
# straight to absent for every ag row, even one from seconds ago. This is
# T75's pattern applied to a second data class (2026-07-19/20 absent-audit
# A2, fable+cx dissent from treating it as structural): persist a small,
# TTL-bounded per-session_id map so a session's real data survives past the
# moment its statusline frame gets overwritten by the next one.
_AG_SESSION_CONTEXT_PATH = SYS_DIR / "data" / "temp" / "ag_session_context.json"
_AG_SESSION_CONTEXT_MAX_ENTRIES = 50


def _load_ag_session_context(session_id):
    if not session_id:
        return None
    try:
        store = json.loads(_AG_SESSION_CONTEXT_PATH.read_text(encoding="utf-8"))
        return store.get(str(session_id))
    except Exception:
        return None


def _save_ag_session_context(session_id, used_tokens, window_tokens, model, observed_at):
    if not session_id:
        return
    try:
        _AG_SESSION_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            store = json.loads(_AG_SESSION_CONTEXT_PATH.read_text(encoding="utf-8"))
        except Exception:
            store = {}
        store[str(session_id)] = {
            "used_tokens": used_tokens, "window_tokens": window_tokens,
            "model": model, "observed_at": observed_at,
        }
        if len(store) > _AG_SESSION_CONTEXT_MAX_ENTRIES:
            ordered = sorted(store.items(), key=lambda kv: kv[1].get("observed_at") or "")
            store = dict(ordered[-_AG_SESSION_CONTEXT_MAX_ENTRIES:])
        _AG_SESSION_CONTEXT_PATH.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def gather_peer(peer, peer_dirs):
    """Collect a normalized metrics dict for one peer."""
    info = {
        "peer": peer, "gate": None, "quarantined": None, "quarantine_reason": None,
        "model": "Unknown", "ctx_used": 0, "ctx_window": "Unknown", "ctx_pct": None,
        "cost": None, "source": "none", "agent_state": None, "plan_tier": None,
        "quotas": [], "sessions": None, "total_tokens": None, "empty": True,
        "ctx_known": False, "errors": [],
        "health_observed_at": None, "health_age_sec": None,
        "capture_session_id": None, "capture_profile": None,
    }

    # Live state log (cc/ag publish one; cx is queried live below).
    live_file = None
    if peer == "ag":
        live_file = SYS_DIR / "data" / "temp" / "ag_statusline_stdin.log"
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
        try:
            health_mtime = health_file.stat().st_mtime
            info["health_observed_at"] = datetime.fromtimestamp(
                health_mtime, tz=timezone.utc).astimezone().isoformat()
            info["health_age_sec"] = max(0, int(time.time() - health_mtime))
        except OSError:
            pass

    capture_session_id = data.get("session_id") if isinstance(data, dict) else None
    if capture_session_id is not None and str(capture_session_id).strip():
        info["capture_session_id"] = str(capture_session_id)
        info["capture_profile"] = _capture_profile_from_active_session(
            peer, peer_dirs[peer], info["capture_session_id"])

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
    profile_health = avail.get("profiles", {})
    info["gate"] = avail.get("gate_open")
    info["quarantined"] = avail.get("quarantined")
    info["quarantine_reason"] = avail.get("quarantine_reason") or avail.get("reason")
    info["profile_health"] = profile_health if isinstance(profile_health, dict) else {}

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
            reset_at = _parse_reset(q.get("reset_time"))
            rem_sec = qmgr.get_remaining_seconds(reset_in_seconds=reset_sec)
            pacing = qmgr.calculate_pacing(used_frac, rem_sec, window_hours) if used_frac is not None else None
            quotas.append({
                "label": label, "used_frac": used_frac, "pacing": pacing,
                "reset": _fmt_reset(q.get("reset_time"), reset_sec),
                "reset_at": reset_at.isoformat() if reset_at else None,
                "reset_in_seconds": reset_sec,
                "source": "ag",
            })
        if peer == "ag" and quotas:
            _save_ag_last_good_quota(quotas, info.get("observed_at"))
    elif peer == "ag":
        # No usable "quota" key in the current live frame (statusline hasn't
        # rendered recently, or rendered a partial/init frame) -- fall back to
        # the last frame that DID have real quota data instead of showing zero
        # pools. Tag it so callers (diag) can render it as stale-but-real
        # rather than indistinguishable from a fresh reading.
        cached = _load_ag_last_good_quota()
        if cached and cached.get("quotas"):
            quotas = [dict(q, stale_fallback=True) for q in cached["quotas"]]
            info["quota_observed_at"] = cached.get("observed_at")
            info["quota_stale_fallback"] = True
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
            reset_at = _parse_reset(resets_at)
            reset_sec = q.get("reset_in_seconds")
            
            if reset_sec is not None:
                rem_sec = qmgr.get_remaining_seconds(reset_in_seconds=reset_sec)
            else:
                rem_sec = qmgr.get_remaining_seconds(resets_at_iso=resets_at)
                
            pacing = qmgr.calculate_pacing(used_frac, rem_sec, window_hours) if used_frac is not None else None
            quotas.append({
                "label": label, "used_frac": used_frac, "pacing": pacing,
                "reset": _fmt_reset(resets_at, reset_sec),
                "reset_at": reset_at.isoformat() if reset_at else None,
                "reset_in_seconds": reset_sec,
                "source": "cc",
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
            quotas.extend(_codex_quota_buckets(rl.get("rateLimits")))
            # Same cached app-server response already carries reset-credit
            # counts (design doc §2.1) -- surface it for diag's peer badge
            # without a second fetch/cache. availableCount is peer-account-
            # wide (a reset clears ALL of a peer's pools at once), so this
            # is intentionally not attached to any individual quota bucket.
            reset_credits = rl.get("rateLimitResetCredits")
            if isinstance(reset_credits, dict):
                info["reset_credits_available"] = reset_credits.get("availableCount")
        elif not quotas:
            info["cx_quota_unavailable"] = True

    if effort_val and effort_val.lower() not in model_name.lower() and effort_val != "null":
        model_name = f"{model_name} ({effort_val})"
    info["model"] = model_name
    quotas.sort(key=lambda q: str(q.get("label", "")))
    info["quotas"] = quotas

    # Context percentage fallback (only when occupancy is genuinely known)
    if (info["ctx_pct"] is None and info["ctx_known"]
            and isinstance(info["ctx_window"], (int, float)) and info["ctx_window"]):
        info["ctx_pct"] = round(info["ctx_used"] / info["ctx_window"] * 100, 1)

    if peer == "ag" and info["capture_session_id"] and info["ctx_known"]:
        window_val = info["ctx_window"] if isinstance(info["ctx_window"], (int, float)) else None
        _save_ag_session_context(
            info["capture_session_id"], info["ctx_used"], window_val,
            info["model"], info.get("observed_at"),
        )
    return info


_LOCAL_TTL_SEC = telemetry_config()["ttl"]["local_sec"]


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
    emoji = "🔴" if frac >= QUOTA_CRIT_FRAC else "🟡" if frac >= QUOTA_WARN_FRAC else "🟢"
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


_MODEL_REGISTRY_CACHE = None


def _load_model_registry():
    """Cached model-registry.json (vendor-documented model facts). Used as a
    DECL fallback for a profile's context limit when orchestration.json has
    no direct runtime_context_window/context_window (e.g. ag.opus, whose CLI
    operand string isn't a registry key -- linked via registry_model_id
    instead). Never used as a measured source."""
    global _MODEL_REGISTRY_CACHE
    if _MODEL_REGISTRY_CACHE is None:
        try:
            data = json.loads((SYS_DIR / "ai" / "model-registry.json").read_text(encoding="utf-8"))
            _MODEL_REGISTRY_CACHE = data.get("models") or {}
        except Exception:
            _MODEL_REGISTRY_CACHE = {}
    return _MODEL_REGISTRY_CACHE


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


_QUOTA_FAMILY_PREFIXES = {
    "C": "C-",
    "F": "F-",
    "G": "G-",
    "3P": "3P-",
    "X": "X-",
}

# Transitional compatibility for pre-D4 orchestration fixtures/configs. Keep
# this explicit and narrow: an unknown enabled profile has no binding, and the
# removed ag.sonnet profile must never regain the old guessed 3P family.
_LEGACY_QUOTA_FAMILIES = {
    "cc.standard": ("C-",),
    "cc.effort": ("C-",),
    "cc.deepthink": ("C-",),
    "cc.fable": ("F-", "C-"),
    "ag.standard": ("G-",),
    "ag.effort": ("G-",),
    "ag.deepthink": ("G-",),
    "ag.opus": ("3P-",),
    "ag.gptoss": ("3P-",),
    "cx.standard": ("X-",),
    "cx.effort": ("X-",),
    "cx.deepthink": ("X-",),
}


def _quota_family_for_profile(peer_id, profile_name, orchestration=None):
    """Return declared quota-family bucket prefixes for ``peer.profile``.

    ``quota_families`` is policy metadata from orchestration, not telemetry;
    bucket source tags continue to come from the app-server/statusline records.
    The optional orchestration argument lets snapshot collection load config
    once and reuse it for every profile row.
    """
    orch = orchestration
    if orch is None:
        try:
            orch = _read_orchestration()
        except Exception:
            orch = {}

    profile = None
    enabled = None
    for node in (orch or {}).get("hub_nodes", []):
        if node.get("type") == "peer" and node.get("node_id") == peer_id:
            enabled = node.get("enabled", True) is not False
            profile = (node.get("profiles") or {}).get(profile_name)
            break

    if isinstance(profile, dict):
        declared = profile.get("quota_families")
        if isinstance(declared, list) and declared:
            if any(family not in _QUOTA_FAMILY_PREFIXES for family in declared):
                return None  # fail closed; check_config reports the declaration error
            return tuple(_QUOTA_FAMILY_PREFIXES[family] for family in declared)
        if enabled is False:
            return None
        return _LEGACY_QUOTA_FAMILIES.get(f"{peer_id}.{profile_name}")

    # Unknown profiles are absent rather than inheriting a peer-wide guess.
    return None


def _filter_profile_buckets(peer_id, profile_name, buckets, orchestration=None):
    family = _quota_family_for_profile(peer_id, profile_name, orchestration)
    if not family:
        return []
    return [b for b in (buckets or []) if str(b.get("label", "")).startswith(family)]


def _profile_source(kind, tag, observed_at, confidence="last_known"):
    ttl = EXPENSIVE_SOURCE_TTL_SEC if tag == "app_server" else _LOCAL_TTL_SEC
    return {"source": _source_meta(kind, observed_at, ttl, confidence), "source_tag": tag}


def profile_health_gate_open(profile_health):
    """Effective profile gate. Expired cooldowns are treated open without writing.

    SSOT (2026-07-08): also imported directly by hub_profile_router.py so the
    routing layer and the display layer agree on cooldown expiry — previously
    the router used a raw `gate_open is False` check with no expiry awareness,
    which could keep an explicit-profile ask (e.g. cc.fable) blocked long after
    its rate-limit window had actually reset, while diag correctly showed it as
    open again."""
    if not isinstance(profile_health, dict):
        return True
    if profile_health.get("gate_open") is not False:
        return True
    rls = profile_health.get("rate_limit_state")
    if isinstance(rls, dict) and rls.get("limited"):
        reset_str = rls.get("reset_at")
        if reset_str:
            try:
                reset_dt = datetime.fromisoformat(reset_str)
                now = datetime.now(reset_dt.tzinfo) if reset_dt.tzinfo else datetime.now()
                if now >= reset_dt:
                    return True
            except (ValueError, TypeError):
                pass
    return False


_profile_health_gate_open = profile_health_gate_open


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
        root_health = domains.get("health") or {}
        health_profiles = root_health.get("profiles") or {}
        default_profile = node.get("default_profile")
        capture_profile = (peer_rec.get("raw") or {}).get("capture_profile")
        for profile_name, prof in (node.get("profiles") or {}).items():
            profile_id = f"{peer_id}.{profile_name}"
            model = prof.get("model_id") or prof.get("runtime_model")
            effort = prof.get("reasoning_effort")
            declared_ctx = prof.get("runtime_context_window") or prof.get("context_window")
            if declared_ctx is None and prof.get("registry_model_id"):
                registry_entry = _load_model_registry().get(prof["registry_model_id"])
                if isinstance(registry_entry, dict):
                    declared_ctx = registry_entry.get("context_limit")
            has_measured_ctx = isinstance(root_ctx.get("window_tokens"), (int, float))
            attributed_capture = profile_id == capture_profile
            unattributed_representative = capture_profile is None and profile_name == default_profile
            use_active_ctx = has_measured_ctx and (
                attributed_capture or unattributed_representative)
            if use_active_ctx:
                ctx_tag = _source_tag(peer_rec, "context")
                context = {
                    "window_tokens": root_ctx.get("window_tokens"),
                    "used_tokens": root_ctx.get("used_tokens"),
                    "utilization_pct": root_ctx.get("utilization_pct"),
                    "basis": (
                        "measured_active_profile" if attributed_capture
                        else "measured_unattributed_active_capture"
                    ),
                    **_profile_source(root_ctx.get("source", {}).get("kind", "live"), ctx_tag,
                                      root_ctx.get("source", {}).get("observed_at", observed_at),
                                      root_ctx.get("source", {}).get("confidence", "exact")
                                      if attributed_capture else "last_known"),
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
                # 3-way consensus (2026-07-19/20 absent-audit, A5): flat "absent"
                # conflates "structurally not applicable right now" with "should
                # be measurable but the pipeline is broken" -- exactly the class
                # of bug T75 hid in for weeks. Distinguish the two common cases
                # observable here; anything else stays the honest "source_unavailable".
                if capture_profile and capture_profile != profile_id:
                    # This peer HAS an active/recent session, just not for this
                    # profile -- benign, expected, not worth investigating.
                    ctx_reason = "no_session"
                elif prof.get("registry_model_id") or prof.get("runtime_context_window") is not None:
                    # A source WAS declared/linked for this profile (a registry
                    # link, or an explicit-but-non-numeric window field) yet
                    # produced nothing -- a real, worth-investigating gap.
                    ctx_reason = "not_observed"
                else:
                    # No source of any kind is declared for this profile at all.
                    ctx_reason = "source_unavailable"
                context = {
                    "window_tokens": None,
                    "used_tokens": None,
                    "utilization_pct": None,
                    "basis": "unavailable",
                    "reason": ctx_reason,
                    **_profile_source("unknown", "absent", observed_at, "unknown"),
                }

            buckets = _filter_profile_buckets(
                peer_id, profile_name, root_quota.get("buckets") or [], orch
            )
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

            # Measured > declared only when the capture's exact session id was
            # resolved to this profile. Unattributed captures remain peer-level;
            # model-name guessing would silently poison profile headroom (T59).
            is_active = profile_id == capture_profile
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
            state = prof.get("routing_state") or "unknown"
            profile_health = health_profiles.get(profile_name, {})
            if state == "eligible" and not _profile_health_gate_open(profile_health):
                state = "blocked"
            rows.append({
                "profile": profile_id,
                "peer": peer_id,
                "profile_name": profile_name,
                "profile_class": prof.get("profile_class"),
                "quota_families": list(prof.get("quota_families") or []),
                "model": model,
                "effort": effort,
                "cost_tier": prof.get("cost_tier"),
                "routing_state": prof.get("routing_state"),
                "intelligence_evidence": copy.deepcopy(prof.get("intelligence_evidence")),
                "profile_intent": copy.deepcopy(prof.get("profile_intent")),
                "state": state,
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


def _profile_pacing_max(profile):
    """Worst (max) pacing ratio across a profile's quota buckets; 1.0 when none is
    measured (DIR-004: absent pacing is never a penalty and never fabricated)."""
    ratios = []
    for b in ((profile.get("quota") or {}).get("buckets") or []):
        if not isinstance(b, dict):
            continue
        pacing = b.get("pacing")
        r = pacing.get("ratio") if isinstance(pacing, dict) else None
        if not isinstance(r, (int, float)):
            r = b.get("pacing_ratio")
        if isinstance(r, (int, float)):
            ratios.append(float(r))
    return max(ratios) if ratios else 1.0

def pacing_admission_for_profile(profile, config):
    """
    Returns "allow", "over_cap", or "unknown" based on pacing <= max_ratio hard gate.
    DIR-004: Never assume "safe" for unmeasured. Returns "unknown" when absent.
    """
    pacing_gate = config.get("pacing_hard_gate", {})
    if not pacing_gate.get("enabled", False):
        return "allow"
    
    max_ratio = float(pacing_gate.get("max_ratio", 1.0))
    
    buckets = ((profile.get("quota") or {}).get("buckets") or [])
    has_valid = False
    
    for b in buckets:
        if not isinstance(b, dict): continue
        pacing = b.get("pacing")
        
        elapsed_frac = pacing.get("elapsed_frac") if isinstance(pacing, dict) else None
        used_frac = b.get("used_frac")
        
        r = pacing.get("ratio") if isinstance(pacing, dict) else None
        if not isinstance(r, (int, float)):
            r = b.get("pacing_ratio")
            
        if isinstance(r, (int, float)) and isinstance(used_frac, (int, float)) and isinstance(elapsed_frac, (int, float)):
            has_valid = True
            if float(used_frac) > 0.10 and float(elapsed_frac) > 0.10 and float(r) > max_ratio:
                return "over_cap"
                
    if not has_valid:
        return "unknown"
        
    return "allow"


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
        window_tokens = (profile.get("context") or {}).get("window_tokens")
        abs_headroom = (
            float(window_tokens) * float(context_remaining)
            if isinstance(window_tokens, (int, float)) and context_remaining is not None
            else None
        )
        rows.append({
            "profile": profile.get("profile"),
            "peer": profile.get("peer"),
            "state": profile.get("state") or "unknown",
            "effort": profile.get("effort"),
            "cost_tier": profile.get("cost_tier"),
            "quota_remaining": quota_remaining,
            "context_remaining": context_remaining,
            "headroom": headroom,
            "context_window_tokens": window_tokens if isinstance(window_tokens, (int, float)) else None,
            "abs_headroom": abs_headroom,
            "pacing_max": _profile_pacing_max(profile),
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
    cx: state_5.sqlite threads(id)->rollout_path; cc: projects/*/<session_id>.jsonl;
    ag: persisted statusline capture (see _save_ag_session_context — ag's own
    live log is overwrite-only, so gather_peer() snapshots each session_id's
    frame before it's lost). No per-session source (missing file, unknown id,
    never captured) => absent — a profile aggregate is NEVER copied into a
    session row (DIR-004)."""
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

    if peer_id == "ag":
        cached = _load_ag_session_context(session_id)
        if cached and isinstance(cached.get("used_tokens"), (int, float)):
            used = cached["used_tokens"]
            win = cached.get("window_tokens")
            win = win if isinstance(win, (int, float)) else (
                window if isinstance(window, (int, float)) else None)
            pct = round(used / win * 100, 1) if isinstance(win, (int, float)) and win else None
            return {
                "used_tokens": used,
                "window_tokens": win,
                "utilization_pct": pct,
                "source": _source_meta("cached", observed_at, _LOCAL_TTL_SEC, "last_known"),
                "source_tag": "ag_session_cache",
                "measured_model": cached.get("model"),
            }
        return _absent()

    return _absent()


def _find_lease_for_peer(leases: dict, peer_id: str) -> dict:
    """T83: leases.json is keyed by lease_id (uuid), not peer_id -- a peer can
    now have multiple concurrent lease entries. Prefer an unexpired open
    lease, otherwise fall back to the newest terminal one, matching by
    entry["peer_id"] rather than the dict key."""
    candidates = [v for v in leases.values() if isinstance(v, dict) and v.get("peer_id") == peer_id]
    if not candidates:
        return {}
    open_candidates = [c for c in candidates if c.get("status") == "open"]
    pool = open_candidates or candidates
    pool.sort(key=lambda c: c.get("started_at") or "", reverse=True)
    return pool[0]


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
            lease = _find_lease_for_peer(leases, profile_id) or _find_lease_for_peer(leases, peer_id)
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


QUOTA_WARN_FRAC = telemetry_config()["display"]["warn_frac"]


QUOTA_CRIT_FRAC = telemetry_config()["display"]["crit_frac"]


def _stale_threshold_sec():
    try:
        proto = json.loads((SYS_DIR / "ai" / "protocol.json").read_text(encoding="utf-8"))
        comm = proto.get("communication_policy", {})
        zmap = comm.get("zombie_profile_map") or {}
        base = comm.get("zombie_timeout_sec", 600)
        return max([base] + list(zmap.values()))
    except Exception:
        return 900

STALE_THRESHOLD_SEC = _stale_threshold_sec()


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
        # ag has no active quota probe (passive statusline-log only) -- going
        # stale for an hour simply means no ag session ran recently, which is
        # expected/idle behavior, not a collector problem. WARN-ing on every
        # idle hour is alert fatigue for a designed characteristic (2026-07-19
        # consensus, fable+cx). Falls back to last-good quota (see
        # _load_ag_last_good_quota) so the reading itself isn't lost either.
        sev = "info" if record.get("peer") == "ag" else "warn"
        alerts.append(_alert(sev, "SOURCE_STALE", msg))

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
        "basis": (
            "measured_attributed_session_capture"
            if ctx_known and info.get("capture_profile")
            else "measured_unattributed_active_capture" if ctx_known
            else "unavailable"
        ),
        "capture_session_id": info.get("capture_session_id"),
        "capture_profile": info.get("capture_profile"),
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
    health_observed = info.get("health_observed_at") or observed
    health = {
        "gate_open": info.get("gate"),
        "quarantined": info.get("quarantined"),
        "profiles": info.get("profile_health") or {},
        "age_sec": info.get("health_age_sec") if isinstance(info.get("health_age_sec"), int) else None,
        "source": _source_meta("cached", health_observed, _LOCAL_TTL_SEC,
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
    """Canonical routing-relevant sha256 for routing-decision audit trails.

    Declared profile policy annotations are intentionally excluded: D3/D6
    metadata must not perturb deterministic bulk routing or arbiter priority.
    """
    def strip_declared_policy(value):
        if isinstance(value, dict):
            return {
                key: strip_declared_policy(item)
                for key, item in value.items()
                if key not in {"intelligence_evidence", "profile_intent"}
            }
        if isinstance(value, list):
            return [strip_declared_policy(item) for item in value]
        if isinstance(value, tuple):
            return tuple(strip_declared_policy(item) for item in value)
        return value

    payload = json.dumps(strip_declared_policy(snapshot), ensure_ascii=False, sort_keys=True,
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


def should_switch_session_peer(incumbent_abs, challenger_abs, switch_ratio=2.0,
                               incumbent_stale=False, incumbent_near_floor=False):
    """Session-reuse HYSTERESIS (design 2026-07-08 §1). Keep the incumbent session
    peer unless: it is stale, or within the headroom floor, or a challenger has
    >= switch_ratio times its ABSOLUTE free context headroom. Prevents oscillation
    and permanent pinning of long chains to one peer. Pure/testable.
    """
    if incumbent_stale or incumbent_near_floor:
        return True
    if not isinstance(incumbent_abs, (int, float)) or incumbent_abs <= 0:
        return True  # unknown/exhausted incumbent -> allow switch
    if not isinstance(challenger_abs, (int, float)) or challenger_abs <= 0:
        return False
    return challenger_abs >= switch_ratio * incumbent_abs


def _capability_shadow_vector(vector):
    """Return a valid Phase-3a requirement vector, else ``None``.

    This is intentionally a narrow schema gate.  Invalid or absent task
    metadata produces no shadow capability decision and cannot perturb live
    balancing.
    """
    if not isinstance(vector, dict) or vector.get("schema_version") != 1:
        return None
    if vector.get("complexity") not in {"low", "medium", "high"}:
        return None
    requirements = vector.get("requirements")
    if not isinstance(requirements, dict):
        return None
    axes = ("reasoning_correctness", "code_fidelity", "agentic_reliability", "long_context_quality")
    for axis in axes:
        requirement = requirements.get(axis)
        if not isinstance(requirement, dict) or not isinstance(requirement.get("required"), bool):
            return None
    long_context = requirements["long_context_quality"]
    minimum = long_context.get("minimum_length_tokens")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
        return None
    return vector


def _capability_shadow_analysis(candidates, vector, reality, ask_id, explicit_target=False):
    """Simulate T45 gates 5/6 without mutating candidates or weights.

    The analysis consumes only the resolved overlay's certified empirical axes
    and declared feasibility status.  Declared composite values are never read.
    """
    vector = _capability_shadow_vector(vector)
    if vector is None:
        return None
    subjects = (reality or {}).get("subjects", {}) if isinstance(reality, dict) else {}
    required = [axis for axis, rule in vector["requirements"].items() if rule.get("required")]
    removed, would_rows = [], []
    bulk_fitness = {}
    explicit_target = bool(explicit_target)
    for row in candidates:
        profile = row.get("profile") or f"{row.get('peer')}.unknown"
        bulk_fitness[profile] = 1.0  # H5 unset: declared-only is precisely neutral.
        subject = subjects.get(profile) if isinstance(subjects, dict) else {}
        axes = subject.get("axes", {}) if isinstance(subject, dict) else {}
        feasibility = ((subject.get("measurement_feasibility") or {}).get("performance") or {}).get("status")
        blocked = feasibility == "blocked_pending_pty_harness"
        failed_axis = None
        failed_reason = None
        for axis in required:
            observed = axes.get(axis) if isinstance(axes, dict) else None
            valid_empirical = (
                isinstance(observed, dict)
                and observed.get("source_tag") == "empirical_probe"
                and observed.get("evidence_band") == "CERTIFIED"
            )
            if not valid_empirical:
                if blocked:
                    continue  # feasibility-blocked is allowed, never stranded.
                failed_axis, failed_reason = axis, "missing_score_measurable"
                break
            if axis == "long_context_quality":
                minimum = vector["requirements"][axis]["minimum_length_tokens"]
                context = row.get("context") or {}
                window = context.get("window_tokens")
                source = context.get("source_tag")
                if source not in {"app_server", "statusline", "cli_live"} or not isinstance(window, (int, float)) or window < minimum:
                    if blocked:
                        continue
                    failed_axis, failed_reason = axis, "context_unmeasured_or_insufficient"
                    break
        if failed_axis and not explicit_target:
            removed.append({"profile": profile, "axis": failed_axis, "reason": failed_reason})
        else:
            would_rows.append(row)
    empty = bool(candidates) and not would_rows
    policy = "warn_then_allow" if explicit_target else ("fail_loud" if empty else ("hard_remove" if removed else "allow"))
    return {
        "event": "capability_route_shadow",
        "ask_id": ask_id,
        "would_candidates": [row.get("profile") for row in would_rows if row.get("profile")],
        "removed": removed,
        "missing_score_policy": policy,
        "empty_result": empty,
        "explicit_target_override": explicit_target,
        "bulk_fitness": bulk_fitness,
        "driving": False,
    }


def select_load_balanced_peer(snapshot, config, terminal_peer=None, ask_id="", rng=None, inflight=None, task_tokens=0):
    """Token load balancer — Phase 1 (design: ops/token-load-balancing-design.md).

    Route an ask to the peer that best equalizes token burn-down: peer-level
    aggregation of headroom, HARD terminal exclusion (the terminal is dropped
    whenever any non-terminal peer has headroom >= floor — the "terminal tokens
    always minimal" requirement), numeric cost tie-break, and a DETERMINISTIC
    seeded weighted-random draw (seed = sha256(snapshot_hash:ask_id)) so every
    decision is reproducible and auditable. Pure; no I/O. Pacing and in-flight
    deductions are live; warm-up remains future work.

    Returns an audit dict: selected row/peer, per-peer weights + probabilities,
    seed, draw, terminal_excluded reason, candidate peers, and a reason code.
    """
    import random as _random
    eps = 0.01
    cost_map = config.get("cost_map", {}) or {}
    floor = config.get("effective_headroom_floor", 0.10)
    hard_exclude = config.get("terminal_hard_exclude", True)
    arbiter_models = set(config.get("arbiter_models", []) or [])
    shared_events = []

    def _empty(reason, premium=None):
        return {"selected": None, "selected_peer": None, "weights": {},
                "probabilities": {}, "terminal_excluded": None,
                "premium_excluded": sorted(premium or []), "seed": None,
                "draw": None, "candidates": [], "reason": reason,
                "representative_profiles": {},
                "telemetry_events": list(shared_events)}

    # Candidate prefilter (hard): eligible + measured (non-absent) headroom.
    eligible = [
        r for r in _derive_headroom_rows(snapshot)
        if r.get("state") == "eligible" and isinstance(r.get("headroom"), (int, float))
    ]

    sq_cfg = config.get("shared_quota_reserve", {}) or {}
    if sq_cfg.get("enabled"):
        families = sq_cfg.get("families", {}) or {}
        family_headrooms = {}
        for family, fam_cfg in families.items():
            min_rem = None
            for p in snapshot.get("profiles", []):
                for b in ((p.get("quota") or {}).get("buckets") or []):
                    lbl = b.get("label", "")
                    if lbl == family or lbl.startswith(family + "-"):
                        uf = b.get("used_frac")
                        if isinstance(uf, (int, float)):
                            rem = max(0.0, min(1.0, 1.0 - float(uf)))
                            if min_rem is None or rem < min_rem:
                                min_rem = rem
            if min_rem is not None:
                family_headrooms[family] = min_rem

        for family, fam_cfg in families.items():
            reserve_frac = fam_cfg.get("reserve_fraction", 0.0)
            reserve_for = set(fam_cfg.get("reserve_for", []) or [])
            rem_headroom = family_headrooms.get(family)
            if rem_headroom is None:
                continue

            is_clamped_active = rem_headroom < reserve_frac

            for r in eligible:
                prof_id = r.get("profile")
                has_family_bucket = False
                for p in snapshot.get("profiles", []):
                    if p.get("profile") == prof_id:
                        for b in ((p.get("quota") or {}).get("buckets") or []):
                            lbl = b.get("label", "")
                            if lbl == family or lbl.startswith(family + "-"):
                                has_family_bucket = True
                                break
                        break

                if has_family_bucket:
                    if prof_id in reserve_for:
                        # Reserved profile: Check if critically low
                        crit_thresh = round(1.0 - QUOTA_CRIT_FRAC, 4)
                        if rem_headroom <= crit_thresh:
                            shared_events.append({
                                "event": "premium_starvation_warning",
                                "family": family,
                                "profile": prof_id,
                                "remaining_headroom": round(rem_headroom, 4),
                                "threshold": crit_thresh
                            })
                    else:
                        # Bulk candidate: Clamp if active
                        if is_clamped_active:
                            r["headroom"] = 0.0
                            r["quota_remaining"] = 0.0
                            shared_events.append({
                                "event": "shared_quota_reserve_clamp",
                                "family": family,
                                "profile": prof_id,
                                "remaining_headroom": round(rem_headroom, 4),
                                "reserve_fraction": reserve_frac
                            })

    if not eligible:
        return _empty("no_eligible_candidate")

    # Hard admission gate: pacing <= 1.0
    pacing_gate = config.get("pacing_hard_gate", {})
    if pacing_gate.get("enabled", False):
        unknown_policy = pacing_gate.get("unknown_policy", "deny")
        allowed_states = {"allow"}
        if unknown_policy == "allow":
            allowed_states.add("unknown")

        # pacing_admission_for_profile expects a RAW profile dict (quota.buckets),
        # matching _profile_pacing_max's calling convention -- `eligible` rows
        # come from _derive_headroom_rows() and do NOT carry quota.buckets, so
        # look the raw profile back up by id (else every row reads as "unknown").
        raw_profiles_by_id = {
            p.get("profile"): p for p in snapshot.get("profiles", []) if p.get("profile")
        }

        new_eligible = []
        pacing_excluded = []
        for r in eligible:
            raw_profile = raw_profiles_by_id.get(r.get("profile")) or {}
            adm = pacing_admission_for_profile(raw_profile, config)
            if adm in allowed_states:
                new_eligible.append(r)
            else:
                pacing_excluded.append(r.get("profile") or r.get("peer"))
        
        eligible = new_eligible
        if not eligible:
            out = _empty("no_eligible_candidate")
            out["pacing_excluded"] = pacing_excluded
            return out

    # Profile-level bulk exclusion (distinct from the peer-level arbiter_models
    # exclusion below): drop ONLY the listed profile rows, keeping the rest of
    # their peer's profiles bulk-eligible. Used for a premium model that shares a
    # peer with cheap bulk workers (e.g. ag.opus shares peer 'ag' with the Gemini
    # bulk profiles). Forward-looking guard even if routing_state is later flipped.
    bulk_exclude_profiles = set(config.get("bulk_exclude_profiles", []) or [])
    if bulk_exclude_profiles:
        eligible = [r for r in eligible if r.get("profile") not in bulk_exclude_profiles]
        if not eligible:
            return _empty("no_eligible_candidate")

    # Premium/arbiter structural exclusion from BULK (DIR-005): drop only rows
    # whose profile id is listed in config.arbiter_models, so cheap sibling
    # profiles on the same peer remain bulk-eligible. A bare peer id in
    # arbiter_models remains an intentional whole-peer exclusion. Independent of
    # the terminal exclusion; premium ID is structural, not the stale
    # active_coordinator.
    premium_excluded = {
        r.get("profile") or r.get("peer") for r in eligible
        if r.get("peer") in arbiter_models or r.get("profile") in arbiter_models
    }
    candidates = [
        r for r in eligible
        if r.get("peer") not in arbiter_models and r.get("profile") not in arbiter_models
    ]
    if not candidates:
        return _empty("no_eligible_candidate", premium_excluded)

    # T45 gates 5/6: evaluate capability requirements and context fit only as
    # a shadow.  ``candidates`` remains the live list for every calculation
    # below; the resulting event is emitted through the normal hub telemetry
    # loop after an actual selection is known.
    capability_shadow = _capability_shadow_analysis(
        candidates,
        config.get("task_requirement_vector"),
        config.get("capability_reality"),
        ask_id,
        explicit_target=config.get("explicit_target", False),
    )

    # Peer-level aggregation: each peer's representative = its max-headroom row
    # (so multiple profiles of one peer are not double-weighted).
    representatives = {}
    for r in candidates:
        peer = r.get("peer")
        cur = representatives.get(peer)
        if cur is None or r["headroom"] > cur["headroom"]:
            representatives[peer] = r
    peers = list(representatives.keys())

    # Effective headroom = H_base / max(1, pacing), then numeric cost tie-break.
    # The pacing penalty is default-on (and explicitly enabled in routing config);
    # absent pacing = 1.0 (no penalty, DIR-004). Terminal exclusion compares H_eff.
    pacing_enabled = config.get("pacing_penalty_enabled", True)
    h_eff, pacing_applied = {}, {}
    for peer in peers:
        p_max = representatives[peer].get("pacing_max", 1.0)
        if not isinstance(p_max, (int, float)):
            p_max = 1.0
        pacing_applied[peer] = round(float(p_max), 2)
        base = float(representatives[peer]["headroom"])
        h_eff[peer] = base / max(1.0, float(p_max)) if pacing_enabled else base

    # P1.5 in-flight deduction: subtract budget already committed by dispatched-
    # but-not-yet-reflected asks (convergence under 60s-cached telemetry). Applied
    # after pacing, before cost; clamped at 0; opt-in. Absent/non-numeric = 0
    # (DIR-004: no fabrication). Recorded regardless of enable for audit.
    inflight = inflight or {}
    inflight_enabled = config.get("inflight_deduction_enabled", True)
    inflight_applied = {}
    for peer in peers:
        v = inflight.get(peer, 0.0)
        amt = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0
        inflight_applied[peer] = round(amt, 4)
        if inflight_enabled and amt:
            h_eff[peer] = max(0.0, h_eff[peer] - amt)

    raw_weights = {}
    for peer in peers:
        ct = representatives[peer].get("cost_tier")
        cost = cost_map.get(ct, 0.0) if isinstance(ct, str) else 0.0
        raw_weights[peer] = max(eps, h_eff[peer] - cost)

    # Headroom bias — DERIVED from measured absolute free capacity (no magic
    # multiplier, DIR-004). A peer with a much larger absolute headroom (e.g. ag's
    # ~1M-token window vs cx's 258k) should absorb a larger AUTO share, but the
    # fraction-based h_eff hides window size. bias = sqrt(abs_headroom / mean) —
    # sqrt DAMPENS the raw ratio (linear ~3.9x -> ~1.4x) so a big-window peer can
    # never starve a smaller one; then clamped to a safety band [min,max]. Gates:
    # (a) a peer with no MEASURED abs_headroom gets no bias (never fabricated);
    # (b) an amplifying bias (>1) is clamped to 1.0 for an over-pacing peer
    # (pacing_max>1.0) so bias can't pull bulk onto a rate-danger peer (cx). An
    # explicit peer_weight_bias entry is a MANUAL override and takes precedence.
    hb = config.get("headroom_bias", {}) or {}
    hb_enabled = hb.get("enabled", True)
    hb_min, hb_max = float(hb.get("min", 0.75)), float(hb.get("max", 1.5))
    manual_bias = config.get("peer_weight_bias", {}) or {}
    _abs = [representatives[p].get("abs_headroom") for p in peers]
    _abs = [a for a in _abs if isinstance(a, (int, float)) and not isinstance(a, bool) and a > 0]
    mean_abs = (sum(_abs) / len(_abs)) if _abs else None
    bias_applied = {}
    for peer in peers:
        mb = manual_bias.get(peer)
        ah = representatives[peer].get("abs_headroom")
        if isinstance(mb, (int, float)) and not isinstance(mb, bool) and mb > 0:
            b = float(mb)  # manual override wins
        elif hb_enabled and mean_abs and isinstance(ah, (int, float)) and not isinstance(ah, bool) and ah > 0:
            b = (float(ah) / mean_abs) ** 0.5           # sqrt-dampened ratio
            b = max(hb_min, min(hb_max, b))             # safety band (anti-starvation)
        else:
            continue  # no measured abs headroom -> no bias (DIR-004)
        if b > 1.0 and float(pacing_applied.get(peer, 1.0)) > 1.0:
            b = 1.0  # rate-danger gate: never amplify onto an over-pacing peer
        bias_applied[peer] = round(float(b), 3)
        raw_weights[peer] = max(eps, raw_weights[peer] * float(b))

    # Context affinity (design 2026-07-08 §1): a HEAVY task (estimated size >=
    # heavy_task_tokens) is steered onto the candidate with the most ABSOLUTE free
    # context (ag's ~1M window) beyond the routine bias, so large/multi-turn chains
    # land where the context fits. Bounded by max_lift; over-pacing peers not
    # amplified; needs a measured abs_headroom. Only fires when task_tokens is given.
    ca = config.get("context_affinity", {}) or {}
    affinity_applied = None
    if ca.get("enabled", False) and task_tokens and task_tokens >= ca.get("heavy_task_tokens", 32000):
        cand_abs = {p: representatives[p].get("abs_headroom") for p in peers
                    if isinstance(representatives[p].get("abs_headroom"), (int, float))
                    and not isinstance(representatives[p].get("abs_headroom"), bool)
                    and representatives[p].get("abs_headroom") > 0}
        if cand_abs:
            top = max(cand_abs, key=cand_abs.get)
            if float(pacing_applied.get(top, 1.0)) <= 1.0:  # skip over-pacing peer
                lift = float(ca.get("max_lift", 1.5))
                raw_weights[top] = max(eps, raw_weights[top] * lift)
                affinity_applied = {"peer": top, "lift": round(lift, 3), "task_tokens": int(task_tokens)}

    # HARD terminal exclusion: if any non-terminal peer's H_eff is at/above the
    # floor, the terminal is zeroed out (never a discount — always minimal).
    terminal_excluded = None
    if hard_exclude and terminal_peer and terminal_peer in raw_weights:
        if any(h_eff[p] >= floor for p in peers if p != terminal_peer):
            raw_weights[terminal_peer] = 0.0
            terminal_excluded = "non_terminal_above_floor"

    total = sum(raw_weights.values())
    if total <= 0.0:
        out = _empty("no_positive_weight", premium_excluded)
        out["weights"] = {peer: round(raw_weights[peer], 4) for peer in peers}
        out["candidates"] = peers
        out["terminal_excluded"] = terminal_excluded
        out["pacing_applied"] = pacing_applied
        out["inflight_applied"] = inflight_applied
        out["bias_applied"] = bias_applied
        out["affinity_applied"] = affinity_applied
        return out

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

    if capability_shadow is not None:
        capability_shadow["actual_profile"] = representatives[selected_peer].get("profile")
        shared_events.append(capability_shadow)

    return {
        "selected": representatives[selected_peer],
        "selected_peer": selected_peer,
        "representative_profiles": {
            peer: row.get("profile") for peer, row in representatives.items()
            if row.get("profile")
        },
        "weights": {peer: round(raw_weights[peer], 4) for peer in peers},
        "probabilities": {peer: round(raw_weights[peer] / total, 4) for peer in peers},
        "terminal_excluded": terminal_excluded,
        "premium_excluded": sorted(premium_excluded),
        "pacing_applied": pacing_applied,
        "inflight_applied": inflight_applied,
        "bias_applied": bias_applied,
        "affinity_applied": affinity_applied,
        "seed": seed,
        "draw": draw,
        "candidates": peers,
        "reason": "selected",
        "telemetry_events": list(shared_events),
    }


# ── Smartest-Model Final Arbiter — decision layer (DIR-005) ──────────────────
# Pure functions only: pick the arbiter, decide whether to fire, and shape the
# FINAL_OPINION record. Live invocation (calling the arbiter, applying its
# verdict, budget persistence) is a later increment.

def select_arbiter(snapshot, config, context=None):
    """Pick the arbiter (premium/smartest model) for a final-opinion pass: the
    FIRST entry of config.arbiter_models (ordered priority) that is currently
    usable — an entry is usable if some row in _derive_headroom_rows matches it
    (by profile id first, else peer id), is state=='eligible', and has non-absent
    (numeric, incl 0.0) headroom. Deterministic config-order fallback chain;
    returns the arbiter id or None if none usable (caller degrades to plain peer
    consensus)."""
    arbiter_models = config.get("arbiter_models", []) or []
    usable = {}
    over_cap = {}
    
    pacing_gate = config.get("pacing_hard_gate", {})
    unknown_policy = pacing_gate.get("unknown_policy", "deny")
    allowed_states = {"allow"}
    if unknown_policy == "allow":
        allowed_states.add("unknown")

    # See select_load_balanced_peer's identical note: pacing_admission_for_profile
    # needs the RAW profile (quota.buckets), not a _derive_headroom_rows row.
    raw_profiles_by_id = {
        p.get("profile"): p for p in snapshot.get("profiles", []) if p.get("profile")
    }

    for r in _derive_headroom_rows(snapshot):
        if r.get("state") != "eligible" or not isinstance(r.get("headroom"), (int, float)):
            continue
        prof, peer = r.get("profile"), r.get("peer")

        if pacing_gate.get("enabled", False):
            raw_profile = raw_profiles_by_id.get(prof) or {}
            adm = pacing_admission_for_profile(raw_profile, config)
        else:
            adm = "allow"
        
        if adm in allowed_states:
            if prof is not None:
                usable[prof] = True
            if peer is not None:
                usable.setdefault(peer, True)
        elif adm == "over_cap":
            if prof is not None:
                over_cap[prof] = True
            if peer is not None:
                over_cap.setdefault(peer, True)
                
    for entry in arbiter_models:
        if usable.get(entry):
            return entry
            
    # Carve-out: If none allowed, check over-cap ones IF dissent/high_risk
    kind = (context or {}).get("kind")
    if kind in ("dissent", "high_risk"):
        for entry in arbiter_models:
            if over_cap.get(entry):
                # We return it. The caller must log pacing_cap_override.
                return entry
                
    return None


def evaluate_arbiter_trigger(context, config, invocations_this_window=0):
    """DIR-005 trigger gate: fire the arbiter only for a configured trigger kind
    within the 5h invocation budget. Authority is 'override' for dissent/high_risk
    (user-ratified 2026-07-04), else 'advisory'."""
    kind = (context or {}).get("kind")
    triggers = config.get("triggers", []) or []
    authority = "override" if kind in ("dissent", "r10_final") else "advisory"
    try:
        budget = int(config.get("invocation_budget_5h", 5))
    except (TypeError, ValueError):
        budget = 5
    try:
        used = int(invocations_this_window)
    except (TypeError, ValueError):
        used = 0
    if kind not in triggers:
        return {"fire": False, "reason": "not_a_trigger", "kind": kind, "authority": authority}
    if used >= budget:
        return {"fire": False, "reason": "budget_exhausted", "kind": kind, "authority": authority}
    return {"fire": True, "reason": "triggered", "kind": kind, "authority": authority}


def build_final_opinion_record(round_id, arbiter, kind, authority, verdict, dissent_summary=None, pacing_cap_override=False):
    """Structured, JSON-serializable FINAL_OPINION record (later persisted to the
    consensus record / routing_metrics by the live-wiring increment)."""
    rec = {
        "type": "FINAL_OPINION",
        "round_id": round_id,
        "arbiter": arbiter,
        "kind": kind,
        "authority": authority,
        "verdict": verdict,
        "dissent_summary": dissent_summary,
        "ts": datetime.now().astimezone().isoformat(),
    }
    if pacing_cap_override:
        rec["pacing_cap_override"] = True
    return rec
