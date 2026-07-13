"""Tests for _sys/core/snapshot.py — the shared telemetry SSOT (r-f291 W4)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import snapshot
import quota


def test_snapshot_import_smoke():
    assert callable(snapshot.collect_snapshot)
    assert callable(snapshot.snapshot_failover_target)
    assert callable(snapshot.snapshot_hash)


@pytest.mark.parametrize(
    ("rate_limits", "expected_label", "expected_window_hours"),
    [
        (
            {
                "primary": {
                    "usedPercent": 8,
                    "windowDurationMins": 10080,
                    "resetsAt": 1784498297,
                },
                "secondary": None,
            },
            "X-7D",
            168.0,
        ),
        (
            {
                "primary": {
                    "usedPercent": 8,
                    "windowDurationMins": 300,
                    "resetsAt": 1784498297,
                }
            },
            "X-5H",
            5.0,
        ),
        (
            {"primary": {"usedPercent": 8, "resetsAt": 1784498297}},
            "X-5H",
            5.0,
        ),
    ],
)
def test_codex_quota_buckets_use_reported_window_or_legacy_fallback(
        monkeypatch, rate_limits, expected_label, expected_window_hours):
    pacing_calls = []

    def fake_calculate_pacing(used_frac, rem_sec, window_hours):
        pacing_calls.append((used_frac, rem_sec, window_hours))
        return {"ratio": 0.5, "status": "ok"}

    monkeypatch.setattr(quota, "calculate_pacing", fake_calculate_pacing)

    buckets = snapshot._codex_quota_buckets(rate_limits)

    assert len(buckets) == 1
    assert buckets[0]["label"] == expected_label
    if expected_window_hours == 168.0:
        assert buckets[0]["label"] != "X-5H"
    assert len(pacing_calls) == 1
    assert pacing_calls[0][0] == pytest.approx(0.08)
    assert pacing_calls[0][2] == expected_window_hours


def test_collect_snapshot_shape(monkeypatch):
    monkeypatch.setattr(snapshot, "_discover_peers", lambda: (["p"], {"p": Path("missing")}))
    monkeypatch.setattr(snapshot, "gather_peer", lambda peer, dirs: {
        "peer": peer, "source": "none", "model": "Unknown", "ctx_known": False,
        "ctx_window": "Unknown", "ctx_used": 0, "ctx_pct": None, "cost": None,
        "sessions": None, "total_tokens": None, "empty": True, "quotas": [],
        "errors": [],
    })
    monkeypatch.setattr(snapshot, "_read_orchestration", lambda: {"hub_nodes": []})

    snap = snapshot.collect_snapshot(use_cache=False)

    assert snap["schema_version"] == 1
    assert isinstance(snap["peers"], list)
    assert isinstance(snap["profiles"], list)
    assert isinstance(snap["sessions"], list)


def test_collect_snapshot_ttl_cache_reuses_within_window(monkeypatch):
    calls = []

    def fake_discover():
        calls.append("collect")
        return ([], {})

    monkeypatch.setattr(snapshot, "_discover_peers", fake_discover)
    monkeypatch.setattr(snapshot, "_read_orchestration", lambda: {"hub_nodes": []})
    snapshot._SNAPSHOT_CACHE.update({"expires_at": 0.0, "snapshot": None})

    first = snapshot.collect_snapshot(use_cache=True, clock=lambda: 100.0)
    second = snapshot.collect_snapshot(use_cache=True, clock=lambda: 100.0 + snapshot.SNAPSHOT_TTL_SEC - 1)
    third = snapshot.collect_snapshot(use_cache=True, clock=lambda: 100.0 + snapshot.SNAPSHOT_TTL_SEC + 1)
    fresh = snapshot.collect_snapshot(use_cache=False, clock=lambda: 100.0)

    assert first is second
    assert third is not second
    assert fresh is not third
    assert calls.count("collect") == 3
    snapshot._SNAPSHOT_CACHE.update({"expires_at": 0.0, "snapshot": None})


def test_snapshot_hash_is_stable_and_order_insensitive():
    a = {"x": 1, "y": [1, 2]}
    b = {"y": [1, 2], "x": 1}
    assert snapshot.snapshot_hash(a) == snapshot.snapshot_hash(b)
    assert len(snapshot.snapshot_hash(a)) == 64


def test_snapshot_failover_picks_max_headroom_eligible_profile():
    snap = {
        "profiles": [
            {
                "profile": "cc.deepthink", "peer": "cc", "state": "eligible",
                "effort": "high",
                "quota": {"buckets": [{"used_frac": 0.50}]},
                "context": {"utilization_pct": 50.0},
            },
            {
                "profile": "ag.standard", "peer": "ag", "state": "eligible",
                "effort": "low",
                "quota": {"buckets": [{"used_frac": 0.10}]},
                "context": {"utilization_pct": 20.0},
            },
        ]
    }
    row = snapshot.snapshot_failover_target(snapshot=snap)
    assert row["profile"] == "ag.standard"
    assert row["headroom"] == 0.80


def test_snapshot_failover_respects_exclude_and_eligibility():
    snap = {
        "profiles": [
            {
                "profile": "ag.standard", "peer": "ag", "state": "eligible",
                "effort": "low",
                "quota": {"buckets": [{"used_frac": 0.10}]},
                "context": {"utilization_pct": 20.0},
            },
            {
                "profile": "cx.effort", "peer": "cx", "state": "manual_only",
                "effort": "high",
                "quota": {"buckets": [{"used_frac": 0.05}]},
                "context": {"utilization_pct": 10.0},
            },
        ]
    }
    assert snapshot.snapshot_failover_target(exclude=["ag"], snapshot=snap) is None
    assert snapshot.snapshot_failover_target(snapshot=snap)["profile"] == "ag.standard"
