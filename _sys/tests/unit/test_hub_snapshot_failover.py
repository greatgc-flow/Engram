"""Tests for hub's snapshot-based failover choice (r-f291 W4): routing
decisions consume the shared snapshot, log its hash, and fail open."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub


def test_snapshot_failover_choice_logs_hash(monkeypatch, tmp_path):
    snap = {
        "schema_version": 1,
        "profiles": [{
            "profile": "ag.standard", "peer": "ag", "state": "eligible",
            "effort": "low",
            "quota": {"buckets": [{"used_frac": 0.10}]},
            "context": {"utilization_pct": 20.0},
        }],
    }
    events = []
    monkeypatch.setattr(hub.snapshot, "collect_snapshot", lambda use_cache=False, **_kw: snap)
    monkeypatch.setattr(hub, "_record_routing_metric",
                        lambda ai_root, event, **fields: events.append((event, fields)))

    target, snap_hash = hub._snapshot_failover_choice(tmp_path, exclude=["cx"])

    assert target == "ag.standard"
    assert snap_hash
    assert events[0][0] == "snapshot_failover_rank"
    assert events[0][1]["snapshot_hash"] == snap_hash
    assert events[0][1]["outcome"] == "selected"


def test_snapshot_failover_choice_excludes_exhausted_peer(monkeypatch, tmp_path):
    snap = {
        "schema_version": 1,
        "profiles": [{
            "profile": "ag.standard", "peer": "ag", "state": "eligible",
            "effort": "low",
            "quota": {"buckets": [{"used_frac": 0.10}]},
            "context": {"utilization_pct": 20.0},
        }],
    }
    monkeypatch.setattr(hub.snapshot, "collect_snapshot", lambda use_cache=False, **_kw: snap)
    monkeypatch.setattr(hub, "_record_routing_metric", lambda *a, **k: None)

    target, _ = hub._snapshot_failover_choice(tmp_path, exclude=["ag"])

    assert target is None


def test_snapshot_failover_choice_fails_open(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(hub.snapshot, "collect_snapshot",
                        lambda use_cache=False, **_kw: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(hub, "_record_routing_metric",
                        lambda ai_root, event, **fields: events.append((event, fields)))

    target, snap_hash = hub._snapshot_failover_choice(tmp_path, exclude=["cx"])

    assert target is None
    assert snap_hash is None
    assert events[0][1]["outcome"] == "fallback_health_based"


def test_snapshot_failover_choice_applies_exclusions(monkeypatch, tmp_path):
    snap = {
        "schema_version": 1,
        "profiles": [{
            "profile": "ag.standard", "peer": "ag", "state": "eligible",
            "headroom": 50.0,
        }, {
            "profile": "cc.deepthink", "peer": "cc", "state": "eligible",
            "headroom": 100.0,
        }, {
            "profile": "cx.effort", "peer": "cx", "state": "eligible",
            "headroom": 75.0,
        }],
    }
    monkeypatch.setattr(hub.snapshot, "collect_snapshot", lambda use_cache=False, **_kw: snap)
    monkeypatch.setattr(hub.snapshot, "_derive_headroom_rows", lambda s: s["profiles"])
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {"arbiter_models": ["cc.deepthink"]})
    
    def fake_read_json(path):
        if path.name == "state.json":
            return {"human_interface_peer": "cx"}
        return {}
    monkeypatch.setattr(hub, "_read_json", fake_read_json)
    monkeypatch.setattr(hub, "_record_routing_metric", lambda *a, **k: None)

    target, _ = hub._snapshot_failover_choice(tmp_path, exclude=[])

    assert target == "ag.standard"
