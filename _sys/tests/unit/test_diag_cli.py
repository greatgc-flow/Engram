import importlib.util
import io
import json
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


SYS_DIR = Path(__file__).resolve().parents[2]
DIAG_PATH = SYS_DIR / "cli" / "diag.py"


def load_diag():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("diag_under_test", DIAG_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_snapshot():
    """The collection layer lives in _sys/core/snapshot.py since r-f291 (W4).
    Tests that monkeypatch moved internals (SYS_DIR, gather_peer, source
    probes, ...) must patch the snapshot module — patching the diag re-export
    does not reach snapshot-global lookups."""
    if str(SYS_DIR / "core") not in sys.path:
        sys.path.insert(0, str(SYS_DIR / "core"))
    import snapshot
    return snapshot


def test_watch_below_minimum_is_rejected_with_clear_error(capsys):
    diag = load_diag()

    with pytest.raises(SystemExit) as exc:
        diag.parse_args(["--watch", "1"])

    assert exc.value.code != 0
    assert "minimum interval is 2" in capsys.readouterr().err


def test_interval_alias_uses_watch_mode_and_same_interval_floor(capsys):
    diag = load_diag()

    args = diag.parse_args(["--interval", "3"])

    assert args.watch is True
    assert args.interval == 3

    with pytest.raises(SystemExit) as exc:
        diag.parse_args(["--interval", "1"])

    assert exc.value.code != 0
    assert "minimum interval is 2" in capsys.readouterr().err


def test_json_one_shot_emits_single_json_object(monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(diag, "collect_snapshot", lambda: {"schema_version": 1, "peers": []})
    out = io.StringIO()

    diag.main(["--json"], stdout=out)

    rendered = out.getvalue()
    parsed = json.loads(rendered)
    assert parsed["schema_version"] == 1
    assert rendered.count("\n") == 1
    assert "\x1b[" not in rendered


def test_json_watch_emits_ndjson_without_ansi(monkeypatch):
    diag = load_diag()
    calls = iter([
        {"schema_version": 1, "seq": 1},
        {"schema_version": 1, "seq": 2},
    ])
    monkeypatch.setattr(diag, "collect_snapshot", lambda: next(calls))
    sleeps = []
    out = io.StringIO()

    diag.run_watch(interval=2, json_mode=True, stdout=out, sleep=sleeps.append, max_frames=2)

    lines = out.getvalue().splitlines()
    assert [json.loads(line)["seq"] for line in lines] == [1, 2]
    assert sleeps == [2]
    assert "\x1b[" not in out.getvalue()


def test_codex_rate_limits_deadline_survives_blocking_readline(monkeypatch):
    diag = load_diag()

    class BlockingStdout:
        def readline(self):
            time.sleep(0.2)
            return ""

    class FakeStdin:
        def write(self, _text):
            return None

        def flush(self):
            return None

    class FakeProc:
        def __init__(self):
            self.stdin = FakeStdin()
            self.stdout = BlockingStdout()
            self.killed = False

        def poll(self):
            return None

        def kill(self):
            self.killed = True

    monkeypatch.setattr(shutil, "which", lambda _name: "codex")
    monkeypatch.setattr(diag.subprocess, "Popen", lambda *args, **kwargs: FakeProc())

    started = time.monotonic()
    assert diag._codex_rate_limits(deadline_sec=0.05) is None
    assert time.monotonic() - started < 0.15

def test_codex_rate_limits_are_cached_for_expensive_ttl(monkeypatch):
    diag = load_diag()
    calls = []

    def fetch():
        calls.append("fetch")
        return {"primary": {"usedPercent": len(calls), "resetsAt": 1}}

    monkeypatch.setattr(load_snapshot(), "_codex_rate_limits", fetch)
    diag._CODEX_RATE_LIMIT_CACHE.clear()

    first = diag._cached_codex_rate_limits(clock=lambda: 100.0)
    second = diag._cached_codex_rate_limits(clock=lambda: 159.0)
    third = diag._cached_codex_rate_limits(clock=lambda: 161.0)

    assert first is second
    assert third is not second
    assert len(calls) == 2

def test_parse_claude_usage_inline_output_from_real_cli_shape():
    diag = load_diag()
    text = """You are currently using your subscription to power your Claude Code usage

Current session: 100% used · resets Jul 3, 11:30am (Asia/Seoul)
Current week (all models): 41% used · resets Jul 7, 10pm (Asia/Seoul)
Current week (Fable): 14% used · resets Jul 7, 10pm (Asia/Seoul)
"""
    now = datetime(2026, 7, 3, 10, 30, tzinfo=timezone(timedelta(hours=9)))

    rows = diag._parse_claude_usage(text, now=now)

    by_label = {row["label"]: row for row in rows}
    assert set(by_label) == {"C-5H", "C-7D", "F-7D"}
    assert by_label["C-5H"]["used_frac"] == pytest.approx(1.0)
    assert by_label["C-7D"]["used_frac"] == pytest.approx(0.41)
    assert by_label["F-7D"]["used_frac"] == pytest.approx(0.14)
    assert all(row["source"] == "cc_usage" for row in rows)
    assert all("resets" not in row["reset"].lower() for row in rows)


def test_statusline_json_real_fable_weekly_reaches_diag_normalization(monkeypatch, tmp_path):
    snapshot = load_snapshot()
    fake_sys = tmp_path / "_sys"
    live_file = fake_sys / "claude" / "config" / "status_input.log"
    live_file.parent.mkdir(parents=True)
    live_file.write_text(json.dumps({
        "model": {"display_name": "Fable"},
        "rate_limits": {
            "five_hour": {"used_percentage": 10},
            "fable_weekly": {"used_percentage": 12},
        },
    }), encoding="utf-8")
    peer_dir = tmp_path / "cc"
    peer_dir.mkdir()
    monkeypatch.setattr(snapshot, "SYS_DIR", fake_sys)
    monkeypatch.setattr(snapshot, "_cached_claude_usage_quotas", lambda: None)

    record = snapshot.gather_peer("cc", {"cc": peer_dir})

    by_label = {row["label"]: row for row in record["quotas"]}
    assert by_label["C-5H"]["used_frac"] == pytest.approx(0.10)
    assert by_label["F-7D"]["used_frac"] == pytest.approx(0.12)
    assert by_label["F-7D"]["source"] == "cc"


def test_parse_claude_usage_multiline_output_from_terminal_shape():
    diag = load_diag()
    text = """
Current session
 100% used
Resets 11:29am (Asia/Seoul)

Current week (all models)
 41% used
Resets Jul 7, 9:59pm (Asia/Seoul)
"""
    now = datetime(2026, 7, 3, 10, 30, tzinfo=timezone(timedelta(hours=9)))

    rows = diag._parse_claude_usage(text, now=now)

    by_label = {row["label"]: row for row in rows}
    assert set(by_label) == {"C-5H", "C-7D"}
    assert by_label["C-5H"]["used_frac"] == pytest.approx(1.0)
    assert by_label["C-7D"]["used_frac"] == pytest.approx(0.41)


def test_claude_usage_probe_runs_real_usage_command(monkeypatch):
    diag = load_diag()
    calls = []

    class Completed:
        stdout = "Current session: 100% used · resets Jul 3, 11:30am (Asia/Seoul)\n"
        stderr = ""

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr(load_snapshot(), "_real_binary", lambda peer: "claude-real.cmd")
    monkeypatch.setattr(diag.subprocess, "run", fake_run)

    rows = diag._claude_usage_quotas()

    assert rows[0]["label"] == "C-5H"
    assert calls[0][0] == ["claude-real.cmd", "/usage"]
    assert calls[0][1]["env"]["CLAUDE_CONFIG_DIR"].endswith(str(Path("_sys/claude/config")))


def test_claude_usage_is_cached_for_expensive_ttl(monkeypatch):
    diag = load_diag()
    calls = []

    def fetch():
        calls.append("fetch")
        return [{"label": "C-5H", "used_frac": len(calls), "source": "cc_usage"}]

    monkeypatch.setattr(load_snapshot(), "_claude_usage_quotas", fetch)
    diag._CLAUDE_USAGE_CACHE.clear()

    first = diag._cached_claude_usage_quotas(clock=lambda: 100.0)
    second = diag._cached_claude_usage_quotas(clock=lambda: 159.0)
    third = diag._cached_claude_usage_quotas(clock=lambda: 161.0)

    assert first is second
    assert third is not second
    assert len(calls) == 2


def test_cc_usage_quota_source_tag_is_cli_live():
    diag = load_diag()
    observed = datetime(2026, 7, 3, 10, 30, tzinfo=timezone(timedelta(hours=9))).isoformat()
    info = {
        "peer": "cc", "source": "live", "gate": True, "quarantined": False,
        "model": "Opus", "ctx_used": 0, "ctx_window": 1000000, "ctx_pct": 0,
        "ctx_known": True, "cost": 0.0, "agent_state": None, "plan_tier": None,
        "sessions": 1, "total_tokens": None, "empty": False,
        "quotas": [{"label": "C-5H", "used_frac": 1.0, "source": "cc_usage"}],
        "quota_observed_at": observed, "quota_source_kind": "live",
    }

    rec = diag.normalize_peer(info)

    assert rec["domains"]["quota"]["source"]["ttl_sec"] == 60
    assert rec["domains"]["quota"]["source"]["observed_at"] == observed
    assert diag._source_tag(rec, "quota") == "cli_live"

def test_reset_formatter_includes_local_timezone_and_relative_countdown():
    diag = load_diag()
    reset_at = datetime.now(timezone.utc).astimezone() + timedelta(minutes=70)

    rendered = diag._fmt_reset(reset_at.isoformat())

    assert "in 1h" in rendered
    assert reset_at.strftime("%z") in rendered or reset_at.tzname() in rendered


# ???? TDD slice 1: normalized telemetry record (吏?/吏?3.1) ??????????????????????????????????????????????????

_VALID_SOURCE_KINDS = {"live", "cached", "snapshot", "estimated", "unknown"}
_VALID_CONFIDENCE = {"exact", "estimated", "last_known", "unknown"}


def test_normalize_peer_every_domain_carries_source_metadata():
    diag = load_diag()
    info = {
        "peer": "cc", "source": "live", "gate": True, "quarantined": False,
        "model": "Opus", "ctx_used": 100000, "ctx_window": 1000000, "ctx_pct": 10.0,
        "ctx_known": True, "cost": 0.5, "agent_state": "idle", "plan_tier": None,
        "sessions": 3, "total_tokens": None, "empty": False,
        "quotas": [{"label": "5H", "used_frac": 0.1, "reset": "x", "metric": "10% used"}],
    }

    rec = diag.normalize_peer(info)

    assert rec["peer"] == "cc"
    assert isinstance(rec.get("domains"), dict) and rec["domains"]
    for domain, drec in rec["domains"].items():
        src = drec.get("source")
        assert src is not None, f"{domain} missing source"
        assert src["kind"] in _VALID_SOURCE_KINDS
        assert src["confidence"] in _VALID_CONFIDENCE
        assert "observed_at" in src and "ttl_sec" in src


def test_normalize_unknown_context_is_null_not_zero():
    diag = load_diag()
    info = {
        "peer": "cx", "source": "app-server", "gate": True, "quarantined": False,
        "model": "gpt", "ctx_used": 0, "ctx_window": 128000, "ctx_pct": None,
        "ctx_known": False, "cost": None, "agent_state": None, "plan_tier": None,
        "sessions": None, "total_tokens": 96000000, "empty": False,
        "quotas": [{"label": "5H", "used_frac": 0.01, "reset": "x", "metric": "1% used",
                    "expensive": True}],
    }

    rec = diag.normalize_peer(info)
    ctx = rec["domains"]["context"]

    assert ctx["used_tokens"] is None          # unknown, never 0
    assert ctx["utilization_pct"] is None
    assert ctx["source"]["confidence"] == "unknown"


def test_normalize_expensive_quota_uses_longer_ttl_than_local():
    diag = load_diag()
    info = {
        "peer": "cx", "source": "app-server", "gate": True, "quarantined": False,
        "model": "gpt", "ctx_used": 0, "ctx_window": 128000, "ctx_pct": None,
        "ctx_known": False, "cost": None, "agent_state": None, "plan_tier": None,
        "sessions": None, "total_tokens": None, "empty": False, "quotas": [],
    }

    rec = diag.normalize_peer(info)

    # cx quota comes from the codex app-server (expensive) -> 60s TTL; local health -> 5s
    assert rec["domains"]["quota"]["source"]["ttl_sec"] == 60
    assert rec["domains"]["health"]["source"]["ttl_sec"] == 5


def test_collect_snapshot_peers_are_normalized():
    diag = load_diag()
    snap = diag.collect_snapshot()
    assert snap["schema_version"] == 1
    for peer in snap["peers"]:
        assert "domains" in peer
        assert "context" in peer["domains"]


# ???? TDD slice 2: redaction (吏?) ??????????????????????????????????????????????????????????????????????????????????????????????????

def test_mask_email_hides_local_part_keeps_domain():
    diag = load_diag()
    masked = diag._mask_email("greatgc@gmail.com")
    assert "greatgc" not in masked
    assert masked.endswith("@gmail.com")
    assert masked != "greatgc@gmail.com"


def test_mask_email_handles_missing_or_malformed():
    diag = load_diag()
    assert diag._mask_email(None) is None
    assert diag._mask_email("") in (None, "")
    # non-email string must not be echoed back verbatim as if valid
    assert diag._mask_email("notanemail") == "***"


def test_normalize_account_exposes_only_masked_email():
    diag = load_diag()
    info = {
        "peer": "ag", "source": "live", "gate": True, "quarantined": False,
        "model": "Gemini", "ctx_used": 0, "ctx_window": 1000000, "ctx_pct": 0,
        "ctx_known": True, "cost": None, "agent_state": "idle",
        "plan_tier": "Google AI Pro", "email": "greatgc@gmail.com",
        "sessions": None, "total_tokens": None, "empty": False, "quotas": [],
    }
    rec = diag.normalize_peer(info)
    acct = rec["domains"]["account"]
    assert acct.get("email") == "g***@gmail.com" or "greatgc" not in str(acct.get("email"))
    # the whole record must never carry the raw address anywhere
    import json as _j
    assert "greatgc@gmail.com" not in _j.dumps(rec)


def test_snapshot_json_contains_no_raw_email(monkeypatch):
    diag = load_diag()
    raw_info = {
        "peer": "ag", "source": "live", "gate": True, "quarantined": False,
        "model": "Gemini", "ctx_used": 0, "ctx_window": 1000000, "ctx_pct": 0,
        "ctx_known": True, "cost": None, "agent_state": "idle",
        "plan_tier": "Google AI Pro", "email": "greatgc@gmail.com",
        "sessions": None, "total_tokens": None, "empty": False, "quotas": [],
    }
    rec = diag.normalize_peer(dict(raw_info))
    monkeypatch.setattr(diag, "collect_snapshot",
                        lambda: {"schema_version": 1, "peers": [rec]})
    out = io.StringIO()
    diag.emit_json_snapshot(out)
    assert "greatgc@gmail.com" not in out.getvalue()


# ???? TDD slice 3: resilience (吏?1) ??????????????????????????????????????????????????????????????????????????????????????????????

def test_gather_peer_missing_dir_does_not_raise(tmp_path):
    diag = load_diag()
    info = diag.gather_peer("zz", {"zz": tmp_path / "nope"})
    assert info["empty"] is True
    assert info["ctx_known"] is False


def test_collect_snapshot_survives_collector_exception(monkeypatch):
    diag = load_diag()

    def boom(peer, dirs):
        raise RuntimeError("sqlite exploded")
    monkeypatch.setattr(load_snapshot(), "gather_peer", boom)

    snap = diag.collect_snapshot()  # must NOT raise even if every collector throws
    assert snap["peers"], "snapshot should still list peers"
    assert all(rec.get("errors") for rec in snap["peers"]), (
        "trapped collector errors must be surfaced, not silent"
    )


def test_is_synthetic_peer_filters_test_fixtures():
    diag = load_diag()
    assert diag._is_synthetic_peer("testpeer") is True
    assert diag._is_synthetic_peer("cx") is False
    assert diag._is_synthetic_peer("cc") is False


# ── D1: staleness (observed_at = source mtime + SOURCE_STALE) ────────────────────

def test_normalize_uses_source_observed_at_not_now():
    diag = load_diag()
    stamp = "2020-01-01T00:00:00+00:00"
    rec = diag.normalize_peer({
        "peer": "cc", "source": "live", "ctx_known": True, "ctx_window": 1000,
        "ctx_used": 10, "ctx_pct": 1.0, "empty": False, "quotas": [], "errors": [],
        "observed_at": stamp,
    })
    assert rec["domains"]["context"]["source"]["observed_at"] == stamp


def test_source_stale_alert_fires_on_old_data():
    diag = load_diag()
    stale = diag.normalize_peer({
        "peer": "cc", "source": "live", "ctx_known": True, "ctx_window": 1000,
        "ctx_used": 10, "ctx_pct": 1.0, "empty": False, "quotas": [], "errors": [],
        "age_sec": 999999,
    })
    fresh = diag.normalize_peer({
        "peer": "cc", "source": "live", "ctx_known": True, "ctx_window": 1000,
        "ctx_used": 10, "ctx_pct": 1.0, "empty": False, "quotas": [], "errors": [],
        "age_sec": 5,
    })
    assert "SOURCE_STALE" in {a["code"] for a in stale["alerts"]}
    assert "SOURCE_STALE" not in {a["code"] for a in fresh["alerts"]}


def test_source_stale_alert_distinguishes_fresh_quota_source():
    diag = load_diag()
    rec = diag.normalize_peer({
        "peer": "cc", "source": "live", "ctx_known": True, "ctx_window": 1000,
        "ctx_used": 10, "ctx_pct": 1.0, "empty": False,
        "quotas": [{"label": "C-5H", "used_frac": 1.0, "source": "cc_usage"}],
        "errors": [], "age_sec": 999999,
        "observed_at": "2026-07-03T14:00:00+09:00",
        "quota_observed_at": "2026-07-03T15:00:00+09:00",
        "quota_source_kind": "live",
    })
    alert = next(a for a in rec["alerts"] if a["code"] == "SOURCE_STALE")

    assert "quota source is cli_live" in alert["message"]


# ── D2: cx context from rollout token_count ─────────────────────────────────────

def test_parse_rollout_context_reads_token_count(tmp_path):
    diag = load_diag()
    roll = tmp_path / "r.jsonl"
    roll.write_text(
        '{"type":"event_msg","payload":{"type":"token_count","info":'
        '{"last_token_usage":{"total_tokens":21494},"model_context_window":258400}}}\n',
        encoding="utf-8",
    )
    used, win = diag._parse_rollout_context(roll)
    assert used == 21494 and win == 258400


def test_parse_rollout_context_tolerates_truncated_tail(tmp_path):
    diag = load_diag()
    roll = tmp_path / "r.jsonl"
    roll.write_text(
        '{"type":"event_msg","payload":{"type":"token_count","info":'
        '{"last_token_usage":{"total_tokens":100},"model_context_window":1000}}}\n'
        '{"type":"event_msg","payload":{"type":"token_c',  # truncated final line
        encoding="utf-8",
    )
    used, win = diag._parse_rollout_context(roll)
    assert used == 100 and win == 1000  # last complete event wins, no raise


def test_parse_rollout_context_missing_file_returns_none(tmp_path):
    diag = load_diag()
    assert diag._parse_rollout_context(tmp_path / "nope.jsonl") == (None, None)


# ── D4: pacing shows value + emoji ──────────────────────────────────────────────

def test_fmt_pacing_includes_ratio_value_with_emoji():
    diag = load_diag()
    rendered = diag._fmt_pacing({"ratio": 1.05, "status": "danger", "indicator": "🔥"})
    assert "1.05x" in rendered          # value, not just emoji
    assert "🔥" in rendered
    assert diag._fmt_pacing({"ratio": 0.0, "status": "unknown", "indicator": ""}) == ""


# ???? TDD slice 4: alerts (吏?) ????????????????????????????????????????????????????????????????????????????????????????????????????????

def _rec_with(diag, **overrides):
    base = {
        "peer": "cc", "source": "live", "gate": True, "quarantined": False,
        "model": "M", "ctx_used": 100, "ctx_window": 1000, "ctx_pct": 10.0,
        "ctx_known": True, "cost": 0.1, "agent_state": "idle", "plan_tier": "Pro",
        "email": "a@b.com", "sessions": 1, "total_tokens": None, "empty": False,
        "quotas": [], "errors": [],
    }
    base.update(overrides)
    return diag.normalize_peer(base)


def _codes(alerts):
    return {a["code"] for a in alerts}


def test_alerts_context_warn_and_critical():
    diag = load_diag()
    warn = diag._compute_alerts(_rec_with(diag, ctx_pct=85.0))
    crit = diag._compute_alerts(_rec_with(diag, ctx_pct=97.0))
    assert "CONTEXT_WARN" in _codes(warn) and "CONTEXT_CRITICAL" not in _codes(warn)
    assert "CONTEXT_CRITICAL" in _codes(crit)


def test_alerts_ctx_unknown_suppresses_context_thresholds():
    diag = load_diag()
    alerts = _codes(diag._compute_alerts(_rec_with(diag, ctx_known=False, ctx_pct=None)))
    assert "CTX_UNKNOWN" in alerts
    assert "CONTEXT_WARN" not in alerts and "CONTEXT_CRITICAL" not in alerts


def test_alerts_quota_warn_and_critical():
    diag = load_diag()
    warn = diag._compute_alerts(_rec_with(diag, quotas=[{"label": "5H", "used_frac": 0.80, "reset": "x", "metric": "m"}]))
    crit = diag._compute_alerts(_rec_with(diag, quotas=[{"label": "5H", "used_frac": 0.93, "reset": "x", "metric": "m"}]))
    assert "QUOTA_WARN" in _codes(warn)
    assert "QUOTA_CRITICAL" in _codes(crit)


def test_alerts_account_unknown_and_diag_error():
    diag = load_diag()
    acct = diag._compute_alerts(_rec_with(diag, plan_tier=None, email=None))
    assert "ACCOUNT_UNKNOWN" in _codes(acct)
    err = diag._compute_alerts(_rec_with(diag, errors=["sqlite_read: OperationalError"]))
    assert "DIAG_INTERNAL_ERROR" in _codes(err)


def test_snapshot_records_carry_alerts_list():
    diag = load_diag()
    snap = diag.collect_snapshot()
    for peer in snap["peers"]:
        assert isinstance(peer.get("alerts"), list)


def test_profile_rows_split_cc_fable_quota_and_context_sources():
    diag = load_diag()
    observed = "2026-07-03T00:00:00+00:00"
    cc_rec = diag.normalize_peer({
        "peer": "cc", "source": "live", "gate": True, "quarantined": False,
        "model": "Opus", "ctx_used": 100, "ctx_window": 1000000, "ctx_pct": 0.01,
        "ctx_known": True, "cost": None, "agent_state": "idle", "plan_tier": "Pro",
        "sessions": None, "total_tokens": None, "empty": False, "errors": [],
        "quotas": [
            {"label": "C-5H", "used_frac": 0.1, "reset": "x"},
            {"label": "F-5H", "used_frac": 0.2, "reset": "x"},
        ],
    })
    orch = {"hub_nodes": [{
        "node_id": "cc", "type": "peer", "enabled": True, "default_profile": "deepthink",
        "profiles": {
            "deepthink": {"model_id": "claude-opus", "reasoning_effort": "high",
                          "runtime_context_window": 1000000, "routing_state": "eligible"},
            "fable": {"model_id": "claude-fable-5", "reasoning_effort": "high",
                      "runtime_context_window": 200000, "routing_state": "eligible"},
        },
    }]}

    rows = {r["profile"]: r for r in diag._build_profile_rows(orch, [cc_rec], observed)}

    assert rows["cc.deepthink"]["context"]["basis"] == "measured_active_profile"
    assert rows["cc.deepthink"]["sources"]["context"] == "statusline"
    assert [b["label"] for b in rows["cc.deepthink"]["quota"]["buckets"]] == ["C-5H"]
    assert rows["cc.fable"]["context"]["window_tokens"] == 200000
    assert rows["cc.fable"]["sources"]["context"] == "orchestration"
    assert [b["label"] for b in rows["cc.fable"]["quota"]["buckets"]] == ["C-5H", "F-5H"]


def test_profile_rows_assign_ag_manual_profiles_to_3p_quota_pool():
    diag = load_diag()
    observed = "2026-07-03T00:00:00+00:00"
    ag_rec = diag.normalize_peer({
        "peer": "ag", "source": "live", "gate": True, "quarantined": False,
        "model": "Gemini", "ctx_used": 0, "ctx_window": 1048576, "ctx_pct": 0,
        "ctx_known": True, "cost": None, "agent_state": "idle", "plan_tier": "Pro",
        "sessions": None, "total_tokens": None, "empty": False, "errors": [],
        "quotas": [
            {"label": "G-5H", "used_frac": 0.1, "reset": "x"},
            {"label": "3P-5H", "used_frac": 0.2, "reset": "x"},
        ],
    })
    orch = {"hub_nodes": [{
        "node_id": "ag", "type": "peer", "enabled": True, "default_profile": "deepthink",
        "profiles": {
            "deepthink": {"runtime_model": "Gemini Pro", "reasoning_effort": "high",
                          "runtime_context_window": 1048576, "routing_state": "eligible"},
            "opus": {"runtime_model": "Claude Opus", "reasoning_effort": "high",
                     "runtime_context_window": None, "routing_state": "manual_only"},
        },
    }]}

    rows = {r["profile"]: r for r in diag._build_profile_rows(orch, [ag_rec], observed)}

    assert [b["label"] for b in rows["ag.deepthink"]["quota"]["buckets"]] == ["G-5H"]
    assert [b["label"] for b in rows["ag.opus"]["quota"]["buckets"]] == ["3P-5H"]
    assert rows["ag.opus"]["state"] == "manual_only"


def test_dashboard_uses_one_collected_snapshot_for_profile_render(monkeypatch):
    diag = load_diag()
    raw = {
        "peer": "cc", "source": "live", "gate": True, "quarantined": False,
        "quarantine_reason": None, "model": "Opus", "ctx_used": 1,
        "ctx_window": 100, "ctx_pct": 1.0, "ctx_known": True, "cost": None,
        "agent_state": "idle", "plan_tier": "Pro", "sessions": None,
        "total_tokens": None, "empty": False, "errors": [], "quotas": [],
    }
    rec = diag.normalize_peer(raw)
    snapshot = {
        "schema_version": 1,
        "observed_at": "2026-07-03T00:00:00+00:00",
        "peers": [rec],
        "profiles": [{
            "profile": "cc.deepthink", "model": "Opus", "effort": "high",
            "context": {"window_tokens": 100},
            "sources": {"context": "statusline", "quota": "absent"},
            "state": "eligible",
        }],
    }
    calls = []
    monkeypatch.setattr(diag, "collect_snapshot", lambda: calls.append("collect") or snapshot)
    monkeypatch.setattr(diag.subprocess, "run", lambda *args, **kwargs: None)

    out = io.StringIO()
    diag.render_dashboard(out)

    assert calls == ["collect"]

# ???? TDD slice 5: detail views (吏?.2) ????????????????????????????????????????????????????????????????????????????????????????

def test_dashboard_follows_action_first_section_order(monkeypatch):
    """FP-4 (unanimous 2026-07-03): PROFILES&QUOTAS → DETAIL → SESSIONS/HEADROOM
    → ALERTS → SUMMARY, identical in default and watch mode (volatile last)."""
    diag = load_diag()
    raw = {
        "peer": "cc", "source": "live", "gate": True, "quarantined": False,
        "quarantine_reason": None, "model": "Opus", "ctx_used": 1,
        "ctx_window": 100, "ctx_pct": 1.0, "ctx_known": True, "cost": None,
        "agent_state": "idle", "plan_tier": "Pro", "sessions": None,
        "total_tokens": None, "empty": False, "errors": [], "quotas": [],
    }
    rec = diag.normalize_peer(raw)
    rec["alerts"] = []
    snapshot = {"schema_version": 1, "peers": [rec], "profiles": []}
    monkeypatch.setattr(diag, "collect_snapshot", lambda: snapshot)
    monkeypatch.setattr(diag.subprocess, "run", lambda *args, **kwargs: None)

    out = io.StringIO()
    diag.render_dashboard(out)
    text = out.getvalue()

    assert (text.index(" ATTENTION")
            < text.index(" SUMMARY")
            < text.index(" HEADROOM")
            < text.index(" RECENT SESSIONS")
            < text.index(" PROFILES & ROUTING")
            < text.index(" POLICY")
            < text.index(" FRAME"))
    assert " PEER DETAIL" not in text
    assert "(no alerts)" in text
    assert text.index("(no alerts)") < text.index(" SUMMARY")
    assert text.rstrip().endswith("LIMITED RESETS none")


def test_watch_dashboard_keeps_action_first_order(monkeypatch):
    diag = load_diag()
    raw = {
        "peer": "cc", "source": "live", "gate": True, "quarantined": False,
        "quarantine_reason": None, "model": "Opus", "ctx_used": 1,
        "ctx_window": 100, "ctx_pct": 1.0, "ctx_known": True, "cost": None,
        "agent_state": "idle", "plan_tier": "Pro", "sessions": None,
        "total_tokens": None, "empty": False, "errors": [], "quotas": [],
    }
    rec = diag.normalize_peer(raw)
    snapshot = {"schema_version": 1, "peers": [rec], "profiles": []}
    monkeypatch.setattr(diag, "collect_snapshot", lambda: snapshot)
    monkeypatch.setattr(diag.subprocess, "run", lambda *args, **kwargs: None)

    out = io.StringIO()
    diag.render_dashboard(out, watch_mode=True)
    text = out.getvalue()

    assert text.index(" ATTENTION") < text.index(" SUMMARY") < text.index(" HEADROOM")
    assert text.index(" HEADROOM") < text.index(" RECENT SESSIONS") < text.index(" FRAME")
    assert " PEER DETAIL" not in text

def test_peers_view_is_opt_in_and_default_dashboard_omits_cards(monkeypatch):
    diag = load_diag()
    raw = {
        "peer": "cc", "source": "live", "gate": True, "quarantined": False,
        "quarantine_reason": None, "model": "Opus", "ctx_used": 1,
        "ctx_window": 100, "ctx_pct": 1.0, "ctx_known": True, "cost": None,
        "agent_state": "idle", "plan_tier": "Pro", "sessions": None,
        "total_tokens": None, "empty": False, "errors": [], "quotas": [],
    }
    rec = diag.normalize_peer(raw)
    rec["alerts"] = []
    snapshot = {"schema_version": 1, "peers": [rec], "profiles": [], "sessions": []}
    monkeypatch.setattr(diag, "collect_snapshot", lambda: snapshot)
    monkeypatch.setattr(diag.subprocess, "run", lambda *args, **kwargs: None)

    default = io.StringIO()
    diag.render_dashboard(default)
    peers = io.StringIO()
    assert diag.main(["--peers"], stdout=peers) == 0

    assert "PEER DETAIL" not in default.getvalue()
    assert "[ CC ]" not in default.getvalue()
    assert "PEER DETAIL" in peers.getvalue()
    assert "[ CC ]" in peers.getvalue()


def test_tty_dashboard_elides_wide_rows_instead_of_wrapping(monkeypatch):
    diag = load_diag()

    class TtyBuffer(io.StringIO):
        def isatty(self):
            return True

    raw = {
        "peer": "cc", "source": "live", "gate": True, "quarantined": False,
        "quarantine_reason": None, "model": "model-name-that-is-deliberately-too-wide-for-a-tty-row",
        "ctx_used": 1, "ctx_window": 100, "ctx_pct": 1.0, "ctx_known": True,
        "cost": None, "agent_state": "idle", "plan_tier": "Pro", "sessions": None,
        "total_tokens": None, "empty": False, "errors": [], "quotas": [],
    }
    rec = diag.normalize_peer(raw)
    rec["alerts"] = []
    snapshot = {"schema_version": 1, "peers": [rec], "profiles": [], "sessions": []}
    monkeypatch.setattr(diag, "collect_snapshot", lambda: snapshot)
    monkeypatch.setattr(diag.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(diag.shutil, "get_terminal_size", lambda: type(
        "Size", (), {"columns": 60, "lines": 24}
    )())

    out = TtyBuffer()
    diag.render_dashboard(out)

    assert all(diag._dw(line) <= 60 for line in out.getvalue().splitlines())
    assert "..." in out.getvalue()


def test_frame_footer_freshness_and_no_limited_resets(monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(diag, "expensive_source_age_sec", lambda: 17)
    rendered = datetime(2026, 7, 8, 10, 0, 0, tzinfo=timezone(timedelta(hours=9)))
    snapshot = {
        "observed_at": "2026-07-08T09:59:55+09:00",
        "peers": [],
        "profiles": [],
    }

    out = io.StringIO()
    diag.render_frame_footer(out, snapshot=snapshot, rendered_at=rendered)
    text = out.getvalue()

    assert "TTL snapshot refreshed 2026-07-08 09:59:55 +0900" in text
    assert "age 5s / TTL 60s" in text
    assert "local TTL 5s" in text
    assert "expensive quota cache 17s / TTL 60s" in text
    assert "RENDERED 2026-07-08 10:00:00 +0900" in text
    assert text.rstrip().endswith("LIMITED RESETS none")


def test_frame_footer_single_limited_reset(monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(diag, "expensive_source_age_sec", lambda: None)
    rendered = datetime(2026, 7, 8, 10, 0, 0, tzinfo=timezone(timedelta(hours=9)))
    snapshot = {
        "observed_at": "2026-07-08T10:00:00+09:00",
        "profiles": [{"profile": "ag.standard"}],
        "peers": [{
            "peer": "ag",
            "domains": {"health": {"profiles": {
                "standard": {"rate_limit_state": {
                    "limited": True,
                    "reset_at": "2026-07-08T10:15:00+09:00",
                }},
            }}},
        }],
    }

    out = io.StringIO()
    diag.render_frame_footer(out, snapshot=snapshot, rendered_at=rendered)
    text = out.getvalue()

    assert "LIMITED RESETS\n" in text
    assert "ag.standard" in text
    assert "in 15m" in text
    assert "2026-07-08 10:15:00 +0900" in text


def test_limited_reset_rows_sort_filter_and_unknown():
    diag = load_diag()
    rendered = datetime(2026, 7, 8, 10, 0, 0, tzinfo=timezone(timedelta(hours=9)))
    snapshot = {
        "profiles": [
            {"profile": "ag.standard"},
            {"profile": "ag.opus"},
            {"profile": "ag.effort"},
            {"profile": "cc.fable"},
            {"profile": "cx.deepthink"},
        ],
        "peers": [
            {"peer": "ag", "domains": {"health": {"profiles": {
                "standard": {"rate_limit_state": {
                    "limited": True, "reset_at": "2026-07-08T10:30:00+09:00"}},
                "opus": {"rate_limit_state": {"limited": True}},
                "effort": {"rate_limit_state": {
                    "limited": False, "reset_at": "2026-07-08T10:05:00+09:00"}},
            }}}},
            {"peer": "cc", "domains": {"health": {"profiles": {
                "fable": {"rate_limit_state": {
                    "limited": True, "reset_at": "2026-07-08T09:59:00+09:00"}},
                "ghost": {"rate_limit_state": {
                    "limited": True, "reset_at": "2026-07-08T10:01:00+09:00"}},
            }}}},
            {"peer": "cx", "domains": {"health": {"profiles": {
                "deepthink": {"rate_limit_state": {
                    "limited": True, "reset_at": "2026-07-08T10:10:00+09:00"}},
            }}}},
        ],
    }

    rows = diag._limited_reset_rows(snapshot, rendered)

    assert [row["profile"] for row in rows] == ["cx.deepthink", "ag.standard", "ag.opus"]
    assert [row["remaining_sec"] for row in rows[:2]] == [600, 1800]
    assert rows[2]["remaining_sec"] is None


def test_headroom_requires_quota_and_context_numeric():
    diag = load_diag()
    snapshot = {
        "profiles": [
            {
                "profile": "ag.deepthink",
                "state": "eligible",
                "effort": "high",
                "quota": {"buckets": [{"used_frac": 0.25}]},
                "context": {"utilization_pct": 40.0},
                "sources": {"context": "statusline", "quota": "statusline"},
            },
            {
                "profile": "cc.fable",
                "state": "eligible",
                "effort": "high",
                "quota": {"buckets": [{"used_frac": 0.10}]},
                "context": {"utilization_pct": None},
                "sources": {"context": "orchestration", "quota": "statusline"},
            },
            {
                "profile": "cx.deepthink",
                "state": "eligible",
                "effort": "xhigh",
                "quota": {"buckets": []},
                "context": {"utilization_pct": 10.0},
                "sources": {"context": "health", "quota": "absent"},
            },
        ],
    }

    rows = {row["profile"]: row for row in diag._derive_headroom_rows(snapshot)}

    assert rows["ag.deepthink"]["quota_remaining"] == pytest.approx(0.75)
    assert rows["ag.deepthink"]["context_remaining"] == pytest.approx(0.60)
    assert rows["ag.deepthink"]["headroom"] == pytest.approx(0.60)
    assert rows["cc.fable"]["headroom"] is None
    assert rows["cx.deepthink"]["headroom"] is None


def test_headroom_next_target_marks_weaker_tier_risk():
    diag = load_diag()
    snapshot = {
        "profiles": [
            {
                "profile": "ag.standard",
                "state": "eligible",
                "effort": "low",
                "quota": {"buckets": [{"used_frac": 0.05}]},
                "context": {"utilization_pct": 10.0},
                "sources": {"context": "statusline", "quota": "statusline"},
            },
            {
                "profile": "cx.deepthink",
                "state": "eligible",
                "effort": "xhigh",
                "quota": {"buckets": [{"used_frac": 0.45}]},
                "context": {"utilization_pct": 45.0},
                "sources": {"context": "health", "quota": "app_server"},
            },
            {
                "profile": "ag.opus",
                "state": "manual_only",
                "effort": "high",
                "quota": {"buckets": [{"used_frac": 0.0}]},
                "context": {"utilization_pct": None},
                "sources": {"context": "absent", "quota": "statusline"},
            },
        ],
    }

    rows = diag._derive_headroom_rows(snapshot)
    target = diag._next_headroom_target(rows)

    assert target["profile"] == "ag.standard"
    assert target["tier_risk"] is True

    out = io.StringIO()
    diag.render_headroom(out, snapshot=snapshot)
    text = out.getvalue()
    assert "NEXT ag.standard headroom 90% TIER RISK" in text
    assert "ag.opus" in text and "absent" in text


def test_session_rows_active_only_with_lease_and_context(tmp_path, monkeypatch):
    diag = load_diag()
    # Isolate from the real _sys tree: per-session sources resolve under SYS_DIR.
    monkeypatch.setattr(load_snapshot(), "SYS_DIR", tmp_path)
    peer_dir = tmp_path / "codex"
    peer_dir.mkdir()
    (peer_dir / "session_state.json").write_text(json.dumps({
        "active": {
            "room-x:cx.deepthink": {
                "session_id": "abcdef123456",
                "scope_key": "room-x:cx.deepthink",
                "created_at": "2026-07-03T08:00:00",
                "last_used_at": "2026-07-03T09:00:00",
                "last_ask_id": "ask-1",
                "status": "active",
            }
        },
        "history": [{
            "session_id": "retired",
            "scope_key": "room-x:cx.standard",
            "status": "retired",
        }],
    }), encoding="utf-8")
    leases = {
        "cx.deepthink": {
            "status": "closed",
            "expires_at": "2026-07-03T09:30:00",
            "heartbeat_at": None,
        }
    }

    def read_json_file(path):
        if str(path).endswith("leases.json"):
            return leases, "2026-07-03T09:01:00+09:00"
        return json.loads(Path(path).read_text(encoding="utf-8")), "2026-07-03T09:02:00+09:00"

    monkeypatch.setattr(load_snapshot(), "_read_json_file", read_json_file)

    rows = diag._build_session_rows(
        ["cx"],
        {"cx": peer_dir},
        [{
            "profile": "cx.deepthink",
            "context": {
                "used_tokens": 100,
                "window_tokens": 1000,
                "utilization_pct": 10.0,
                "source_tag": "health",
            },
        }],
        "2026-07-03T09:03:00+09:00",
    )

    assert [row["profile"] for row in rows] == ["cx.deepthink"]
    assert rows[0]["lease"]["status"] == "closed"
    # FP-1: no per-session source exists here, so the profile aggregate (100)
    # must NOT be copied into the session row — honest value is absent.
    assert rows[0]["context"]["used_tokens"] is None
    assert rows[0]["context"]["source_tag"] == "absent"
    assert rows[0]["scope_key"] == "room-x:cx.deepthink"


def test_sessions_view_renders_absent_context(monkeypatch):
    diag = load_diag()
    snapshot = {
        "sessions": [{
            "profile": "cc.fable",
            "status": "active",
            "scope_key": "room-x:cc.fable",
            "last_used_at": "2026-07-03T09:00:00",
            "context": {"used_tokens": None, "window_tokens": 200000},
            "lease": {"status": "failed"},
        }]
    }
    monkeypatch.setattr(diag, "collect_snapshot", lambda: snapshot)

    out = io.StringIO()
    diag.render_sessions(out)
    text = out.getvalue()

    assert "cc.fable" in text
    assert "[FAILED]" in text
    assert "absent" in text


def test_sessions_view_can_consume_existing_snapshot(monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(diag, "collect_snapshot", lambda: (_ for _ in ()).throw(AssertionError("recollected")))
    snapshot = {
        "sessions": [{
            "profile": "cx.deepthink",
            "status": "active",
            "scope_key": "room-x:cx.deepthink",
            "last_used_at": "2026-07-03T09:00:00",
            "context": {"used_tokens": 100, "window_tokens": 1000, "utilization_pct": 10.0},
            "lease": {"status": "closed"},
        }]
    }

    out = io.StringIO()
    diag.render_sessions(out, snapshot=snapshot)

    assert "cx.deepthink" in out.getvalue()
    assert "100/1k 10%" in out.getvalue()


def test_recent_session_views_mark_closed_lease_state():
    diag = load_diag()
    snapshot = {
        "peers": [{"peer": "cc"}],
        "sessions": [{
            "peer": "cc", "profile": "cc.fable", "model": "long-model-name",
            "status": "active", "scope_key": "room-x:cc.fable",
            "last_used_at": "2026-07-03T09:00:00+00:00",
            "context": {"used_tokens": 250000, "window_tokens": 200000, "utilization_pct": 125.0},
            "lease": {"status": "closed", "expires_at": "2026-07-03T09:30:00+00:00"},
        }],
    }
    full = io.StringIO()
    diag.render_sessions(full, snapshot=snapshot)
    hud = io.StringIO()
    diag.render_recent_sessions(
        hud, snapshot, now=datetime(2026, 7, 3, 10, tzinfo=timezone.utc), columns=80,
    )
    assert "ACTIVE SESSIONS" in hud.getvalue()
    assert "ROOM / STATE" in hud.getvalue()
    assert "[CLOSED]" in hud.getvalue()
    assert "[CLOSED]" in full.getvalue()
    assert "RECENT SESSIONS" not in hud.getvalue()


def test_open_lease_requires_unexpired_timestamp_for_open_state():
    diag = load_diag()
    now = datetime(2026, 7, 3, 10, tzinfo=timezone.utc)
    assert diag._session_lease_state({"lease": {
        "status": "open", "expires_at": "2026-07-03T10:30:00+00:00",
    }}, now) == "[OPEN]"
    assert diag._session_lease_state({"lease": {
        "status": "open", "expires_at": "2026-07-03T09:30:00+00:00",
    }}, now) == "[STALE]"
    assert diag._session_lease_state({"lease": {"status": "open"}}, now) == "[STALE]"


def test_profiles_view_never_leaks_raw_profile_args():
    diag = load_diag()
    out = io.StringIO()
    assert diag.main(["--profiles"], stdout=out) == 0
    text = out.getvalue()
    assert "profile_args" not in text
    assert "model_reasoning_effort" not in text  # raw adapter arg must not leak
    # but it should still show real profile facts
    assert "standard" in text or "deepthink" in text


def test_accounts_view_has_no_unmasked_email(monkeypatch):
    diag = load_diag()
    rec = diag.normalize_peer({
        "peer": "ag", "source": "live", "plan_tier": "Google AI Pro",
        "email": "greatgc@gmail.com", "ctx_known": True, "ctx_window": 1000,
        "ctx_used": 1, "ctx_pct": 0, "empty": False, "quotas": [], "errors": [],
    })
    monkeypatch.setattr(diag, "collect_snapshot", lambda: {"schema_version": 1, "peers": [rec]})
    out = io.StringIO()
    assert diag.main(["--accounts"], stdout=out) == 0
    assert "greatgc@gmail.com" not in out.getvalue()


def test_git_project_status_degrades_on_failure(monkeypatch):
    diag = load_diag()

    def boom(*a, **k):
        raise OSError("git missing")
    monkeypatch.setattr(diag.subprocess, "run", boom)
    status = diag._git_project_status()  # must not raise
    assert status.get("state") in ("unknown", "clean", "dirty")


def test_tokens_view_is_null_safe(monkeypatch):
    diag = load_diag()
    rec = diag.normalize_peer({
        "peer": "cx", "source": "app-server", "cost": None, "total_tokens": None,
        "ctx_known": False, "ctx_window": 128000, "ctx_used": 0, "ctx_pct": None,
        "empty": False, "quotas": [], "errors": [],
    })
    monkeypatch.setattr(diag, "collect_snapshot", lambda: {"schema_version": 1, "peers": [rec]})
    out = io.StringIO()
    assert diag.main(["--tokens"], stdout=out) == 0  # no crash on nulls
    assert "cx" in out.getvalue().lower()


# ── PATH-shadow fix: diag must call the REAL codex, not our _sys/cli wrapper ─────

def test_codex_binary_skips_sys_cli_wrapper():
    diag = load_diag()
    exe = diag._codex_binary()
    assert exe, "should resolve a codex binary"
    p = str(exe).replace("\\", "/").lower()
    # our wrapper (_sys/cli/codex[.bat]) runs the heavy codex_entry.py init/context-fill
    # flow — wrong for a raw app-server RPC. Must resolve the real npm-global binary.
    assert "/_sys/cli/codex" not in p and "/cli/codex" not in p
    assert "npm-global" in p and p.endswith("codex.cmd")


# ── FP-1: per-session measured context (unanimous 2026-07-03) ─────────────────

def test_fp1_cx_sqlite_rollout_resolution(tmp_path, monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(load_snapshot(), "SYS_DIR", tmp_path)
    monkeypatch.setattr(load_snapshot(), "_parse_rollout_context",
                        lambda p: (420, 100000) if str(p) == "my_rollout.jsonl" else (None, None))

    db_dir = tmp_path / "codex" / "config"
    db_dir.mkdir(parents=True)
    import sqlite3
    conn = sqlite3.connect(db_dir / "state_5.sqlite")
    conn.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, model TEXT)")
    conn.execute("INSERT INTO threads VALUES ('sess1', 'my_rollout.jsonl', 'measured-gpt')")
    conn.commit()
    conn.close()

    ctx = diag._session_context_measured(
        "cx", {"session_id": "sess1"}, {"context": {"window_tokens": 128000}},
        "2026-07-03T00:00:00")

    assert ctx["used_tokens"] == 420
    assert ctx["window_tokens"] == 100000  # measured window wins over profile
    assert ctx["source_tag"] == "rollout"
    assert ctx["measured_model"] == "measured-gpt"


def test_fp1_cc_session_jsonl_usage_extraction(tmp_path, monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(load_snapshot(), "SYS_DIR", tmp_path)

    proj_dir = tmp_path / "claude" / "config" / "projects" / "my_proj"
    proj_dir.mkdir(parents=True)
    (proj_dir / "sess2.jsonl").write_text(
        '{"message": {"model": "claude-test", "usage": {"input_tokens": 10, "output_tokens": 20}}}\n',
        encoding="utf-8")

    ctx = diag._session_context_measured(
        "cc", {"session_id": "sess2"}, {"context": {"window_tokens": 200000}},
        "2026-07-03T00:00:00")

    assert ctx["used_tokens"] == 30
    assert ctx["window_tokens"] == 200000
    assert ctx["source_tag"] == "session_jsonl"
    assert ctx["measured_model"] == "claude-test"


def test_fp1_ag_has_no_per_session_source_so_absent(tmp_path, monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(load_snapshot(), "SYS_DIR", tmp_path)

    ctx = diag._session_context_measured(
        "ag", {"session_id": "sess3"}, {"context": {"window_tokens": 1048576}},
        "2026-07-03T00:00:00")

    assert ctx["used_tokens"] is None
    assert ctx["window_tokens"] == 1048576  # capacity may show; usage never fabricated
    assert ctx["source_tag"] == "absent"


def test_fp1_profile_copy_regression(tmp_path, monkeypatch):
    """cx guard (Final Call): a profile with known aggregate ctx + a session with
    no per-session source must yield absent — never the aggregate value."""
    diag = load_diag()
    monkeypatch.setattr(load_snapshot(), "SYS_DIR", tmp_path)

    profile_row = {"context": {"used_tokens": 9999, "window_tokens": 200000}}
    ctx = diag._session_context_measured(
        "cx", {"session_id": "nonexistent"}, profile_row, "2026-07-03T00:00:00")

    assert ctx["used_tokens"] is None
    assert ctx["used_tokens"] != 9999
    assert ctx["window_tokens"] == 200000
    assert ctx["source_tag"] == "absent"


# --------------------------------------------------------------------------
# D9 - standalone --live HUD (--watch-summary remains a hidden compatibility alias)
# --------------------------------------------------------------------------

class _FakeTTY(io.StringIO):
    """A StringIO that reports itself as a TTY, for exercising the
    cursor-repaint escape-sequence branches of run_watch()."""

    def isatty(self):
        return True


def _fake_snapshot(peer="cc"):
    return {"schema_version": 1, "observed_at": "2026-07-13T10:00:00+00:00",
            "profiles": [], "sessions": [], "peers": [{"peer": peer, "raw": {
        "peer": peer, "gate": None, "quarantined": None, "quarantine_reason": None,
        "model": "Unknown", "ctx_used": 0, "ctx_window": "Unknown", "ctx_pct": None,
        "cost": None, "source": "none", "agent_state": None, "plan_tier": None,
        "quotas": [], "sessions": None, "total_tokens": None, "empty": True,
        "ctx_known": False, "errors": [],
    }}]}


def test_live_flag_alias_interval_and_mutual_exclusion(capsys):
    diag = load_diag()

    args = diag.parse_args(["--live"])
    assert args.live is True
    assert args.watch is False
    assert args.interval is None

    args = diag.parse_args(["--live", "3"])
    assert args.live is True
    assert args.interval == 3

    args = diag.parse_args(["--live", "--interval", "3"])
    assert args.live is True
    assert args.interval == 3

    compat = diag.parse_args(["--watch-summary", "3"])
    assert compat.live is True
    assert compat.watch_summary is True
    assert compat.interval == 3

    with pytest.raises(SystemExit):
        diag.parse_args(["--watch", "--live"])

    with pytest.raises(SystemExit) as exc:
        diag.parse_args(["--live", "1"])
    assert exc.value.code != 0
    assert "minimum interval is 2" in capsys.readouterr().err


def test_watch_summary_alias_is_hidden_from_help(capsys):
    diag = load_diag()

    with pytest.raises(SystemExit):
        diag.parse_args(["--help"])
    help_text = capsys.readouterr().out
    assert "--live" in help_text
    assert "--watch-summary" not in help_text


def _session_row(peer, profile, last_used, pct=10.0, scope="room-proj-b"):
    return {
        "peer": peer,
        "profile": f"{peer}.{profile}",
        "last_used_at": last_used,
        "context": {"utilization_pct": pct} if pct is not None else {},
        "scope_key": f"{scope}:{peer}.{profile}",
    }


def _snapshot_with_sessions(rows):
    snap = _fake_snapshot("cc")
    peers = []
    for row in rows:
        if row["peer"] not in peers:
            peers.append(row["peer"])
    snap["sessions"] = rows
    snap["peers"] = [
        {"peer": peer, "raw": {**_fake_snapshot(peer)["peers"][0]["raw"]}}
        for peer in peers
    ]
    return snap


def test_live_non_tty_is_plain_sequential_and_collects_once_per_tick(monkeypatch):
    diag = load_diag()
    calls = []

    def collect_snapshot(*, use_cache):
        calls.append(use_cache)
        return _fake_snapshot()

    monkeypatch.setattr(diag, "collect_snapshot", collect_snapshot)
    monkeypatch.setattr(
        diag.subprocess,
        "run",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("hub.py spawned")),
    )
    out = io.StringIO()

    diag.run_watch(interval=0, stdout=out, max_frames=3, summary_only=True, sleep=lambda s: None)

    text = out.getvalue()
    assert calls == [False, False, False]
    assert text.count("PEER HEALTH") == 3
    assert text.count("QUOTA POOLS") == 3
    assert text.count("ACTIVE SESSIONS") == 3
    assert text.count("OBSERVATION") == 3
    assert " PROFILES & ROUTING" not in text
    assert " POLICY" not in text
    assert "\033[" not in text


def test_live_tty_blits_from_tick_zero_without_cursor_up_or_subprocess(monkeypatch):
    diag = load_diag()
    calls = []
    monkeypatch.setattr(diag, "collect_snapshot", lambda *, use_cache: (calls.append(use_cache), _fake_snapshot())[1])
    monkeypatch.setattr(diag, "shutil", type("S", (), {
        "get_terminal_size": staticmethod(lambda: (80, 24)),
    }))
    monkeypatch.setattr(
        diag.subprocess,
        "run",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("hub.py spawned")),
    )
    out = _FakeTTY()

    diag.run_watch(interval=0, stdout=out, max_frames=2, summary_only=True, sleep=lambda s: None)

    text = out.getvalue()
    assert calls == [False, False]
    assert text.count("\033[H") == 2
    assert text.count("\033[J") == 2
    assert not any(f"\033[{n}A" in text for n in range(1, 200))


def test_live_resize_recomputes_height_budget_without_full_dashboard(monkeypatch):
    diag = load_diag()
    rows = [
        _session_row(peer, "deepthink", f"2026-07-13T0{9-rank}:00:00+00:00")
        for rank in range(3)
        for peer in ("cc", "ag", "cx")
    ]
    snap = _snapshot_with_sessions(rows)
    monkeypatch.setattr(diag, "collect_snapshot", lambda *, use_cache: snap)
    sizes = iter([(60, 16), (60, 30)])
    monkeypatch.setattr(diag, "shutil", type("S", (), {
        "get_terminal_size": staticmethod(lambda: next(sizes)),
    }))
    frames = []
    monkeypatch.setattr(diag, "_blit_frame", lambda _out, text, _sync: frames.append(text))

    diag.run_watch(interval=0, stdout=_FakeTTY(), max_frames=2, summary_only=True, sleep=lambda s: None)

    assert len(frames) == 2
    assert len(frames[0].splitlines()) <= 16
    assert len(frames[1].splitlines()) <= 30
    assert all(diag._dw(line) <= 60 for frame in frames for line in frame.splitlines())
    assert frames[1].count("deepthink") > frames[0].count("deepthink")
    assert " PROFILES & ROUTING" not in "".join(frames)


def test_recent_sessions_sort_missing_last_and_cap_three(monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(
        diag,
        "collect_snapshot",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("renderer recollected")),
    )
    rows = [
        _session_row("cc", "newest", "2026-07-13T09:59:00+00:00"),
        _session_row("cc", "missing", "not-a-time"),
        _session_row("cc", "middle", "2026-07-13T09:30:00+00:00"),
        _session_row("cc", "oldest", "2026-07-13T09:00:00+00:00"),
    ]
    out = io.StringIO()

    diag.render_recent_sessions(
        out,
        _snapshot_with_sessions(rows),
        now=datetime(2026, 7, 13, 10, tzinfo=timezone.utc),
        columns=80,
    )

    text = out.getvalue()
    assert text.index("cc.newest") < text.index("cc.middle") < text.index("cc.oldest")
    assert "cc.missing" not in text
    assert text.count("cc.") == 3


def test_recent_sessions_round_robin_and_exact_hidden_count():
    diag = load_diag()
    rows = [
        _session_row(peer, f"p{rank}", f"2026-07-13T0{9-rank}:00:00+00:00")
        for rank in range(3)
        for peer in ("cc", "cx")
    ]
    out = io.StringIO()

    diag.render_recent_sessions(
        out,
        _snapshot_with_sessions(rows),
        now=datetime(2026, 7, 13, 10, tzinfo=timezone.utc),
        columns=80,
        line_budget=5,
    )

    text = out.getvalue()
    assert "cc.p0" in text and "cx.p0" in text
    assert "cc.p1" not in text and "cx.p1" not in text
    assert "  +4 hidden" in text


def test_recent_sessions_display_globally_newest_first_after_fair_selection():
    diag = load_diag()
    rows = [
        _session_row("cc", "old", "2026-07-13T09:10:00+00:00"),
        _session_row("ag", "new", "2026-07-13T09:50:00+00:00"),
        _session_row("cx", "middle", "2026-07-13T09:25:00+00:00"),
    ]
    out = io.StringIO()

    diag.render_recent_sessions(
        out, _snapshot_with_sessions(rows),
        now=datetime(2026, 7, 13, 10, tzinfo=timezone.utc), columns=80,
    )

    text = out.getvalue()
    assert text.index("ag.new") < text.index("cx.middle") < text.index("cc.old")


def test_recent_sessions_budget_keeps_one_newest_row_per_peer_before_display_sort():
    diag = load_diag()
    rows = [
        _session_row(peer, f"p{rank}", f"2026-07-13T{hour:02d}:{minute-rank:02d}:00+00:00")
        for peer, hour, minute in (("cc", 9, 10), ("ag", 9, 50), ("cx", 9, 25))
        for rank in range(2)
    ]
    out = io.StringIO()

    diag.render_recent_sessions(
        out, _snapshot_with_sessions(rows),
        now=datetime(2026, 7, 13, 10, tzinfo=timezone.utc), columns=80,
        line_budget=6,
    )

    text = out.getvalue()
    assert all(f"{peer}.p0" in text for peer in ("cc", "ag", "cx"))
    assert all(f"{peer}.p1" not in text for peer in ("cc", "ag", "cx"))
    assert text.index("ag.p0") < text.index("cx.p0") < text.index("cc.p0")


def test_recent_sessions_tiny_budget_uses_one_line_per_peer_digest():
    diag = load_diag()
    rows = [
        _session_row(peer, f"p{rank}", f"2026-07-13T{hour-rank:02d}:00:00+00:00")
        for peer, hour in (("cc", 9), ("ag", 10))
        for rank in range(3)
    ]
    out = io.StringIO()

    diag.render_recent_sessions(
        out,
        _snapshot_with_sessions(rows),
        now=datetime(2026, 7, 13, 10, tzinfo=timezone.utc),
        columns=80,
        line_budget=3,
    )

    lines = out.getvalue().splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("ACTIVE SESSIONS")
    assert lines[1].startswith("AG:") and lines[1].endswith("(3)")
    assert lines[2].startswith("CC:") and lines[2].endswith("(3)")


def test_recent_sessions_wide_mode_shows_session_model_and_narrow_mode_omits_it():
    diag = load_diag()
    row = _session_row("cc", "deepthink", "2026-07-13T09:59:00+00:00")
    row["model"] = "[decl] Exact Model"
    snapshot = _snapshot_with_sessions([row])
    wide = io.StringIO()
    narrow = io.StringIO()
    now = datetime(2026, 7, 13, 10, tzinfo=timezone.utc)

    diag.render_recent_sessions(wide, snapshot, now=now, columns=120)
    diag.render_recent_sessions(narrow, snapshot, now=now, columns=80)

    wide_lines = wide.getvalue().splitlines()
    assert "MODEL" in wide_lines[1]
    assert "[decl] Exact Model" in wide.getvalue()
    assert all(diag._dw(line) <= 120 for line in wide_lines)
    assert "MODEL" not in narrow.getvalue()
    assert "[decl] Exact Model" not in narrow.getvalue()


def test_recent_sessions_skips_peers_without_session_rows():
    diag = load_diag()
    snap = _snapshot_with_sessions([
        _session_row("cc", "fable", "2026-07-13T09:59:00+00:00"),
    ])
    snap["peers"].append({"peer": "ag", "raw": _fake_snapshot("ag")["peers"][0]["raw"]})
    out = io.StringIO()

    diag.render_recent_sessions(
        out,
        snap,
        now=datetime(2026, 7, 13, 10, tzinfo=timezone.utc),
        columns=80,
    )

    assert "cc.fable" in out.getvalue()
    assert "AG:" not in out.getvalue()
