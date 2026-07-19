"""T74 (2026-07-19 consensus, cx design): ag has no active quota probe --
quota is read passively from ag_statusline_stdin.log, which only updates
when an ag session's statusline renders. A partial/init frame (or simply no
recent ag session) used to drop straight to zero quota rows in diag. These
tests cover the last-good-quota cache (persists a real reading across gaps)
and the SOURCE_STALE severity downgrade for ag (expected-when-idle, not a
collector failure -- avoid alert fatigue on a designed characteristic).
"""
import json
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
if str(SYS_DIR / "core") not in sys.path:
    sys.path.insert(0, str(SYS_DIR / "core"))
import snapshot


def test_ag_last_good_quota_round_trip(tmp_path, monkeypatch):
    cache_path = tmp_path / "ag_last_good_quota.json"
    monkeypatch.setattr(snapshot, "_AG_LAST_GOOD_QUOTA_PATH", cache_path)

    assert snapshot._load_ag_last_good_quota() is None

    quotas = [{"label": "G-5H", "used_frac": 0.3, "source": "ag"}]
    snapshot._save_ag_last_good_quota(quotas, "2026-07-19T22:00:00+09:00")

    cached = snapshot._load_ag_last_good_quota()
    assert cached["quotas"] == quotas
    assert cached["observed_at"] == "2026-07-19T22:00:00+09:00"


def test_ag_last_good_quota_load_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, "_AG_LAST_GOOD_QUOTA_PATH", tmp_path / "does_not_exist.json")
    assert snapshot._load_ag_last_good_quota() is None


def test_ag_last_good_quota_load_corrupt_file_returns_none(tmp_path, monkeypatch):
    bad = tmp_path / "corrupt.json"
    bad.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(snapshot, "_AG_LAST_GOOD_QUOTA_PATH", bad)
    assert snapshot._load_ag_last_good_quota() is None


def test_ag_last_good_quota_save_never_raises_on_write_failure(tmp_path, monkeypatch):
    # Point at a path whose parent can't be created (a file, not a dir) --
    # save must degrade silently, never crash the caller.
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(snapshot, "_AG_LAST_GOOD_QUOTA_PATH", blocker / "sub" / "cache.json")
    snapshot._save_ag_last_good_quota([{"label": "G-5H"}], "now")  # must not raise


def test_source_stale_alert_is_info_for_ag_not_warn():
    record = {
        "peer": "ag",
        "raw": {"age_sec": snapshot.STALE_THRESHOLD_SEC + 500},
        "domains": {
            "context": {"utilization_pct": None, "used_tokens": None},
            "quota": {},
        },
        "errors": [],
    }
    alerts = snapshot._compute_alerts(record)
    stale = [a for a in alerts if a["code"] == "SOURCE_STALE"]
    assert len(stale) == 1
    assert stale[0]["severity"] == "info"


def test_source_stale_alert_is_warn_for_non_ag_peers():
    record = {
        "peer": "cc",
        "raw": {"age_sec": snapshot.STALE_THRESHOLD_SEC + 500},
        "domains": {
            "context": {"utilization_pct": None, "used_tokens": None},
            "quota": {},
        },
        "errors": [],
    }
    alerts = snapshot._compute_alerts(record)
    stale = [a for a in alerts if a["code"] == "SOURCE_STALE"]
    assert len(stale) == 1
    assert stale[0]["severity"] == "warn"
