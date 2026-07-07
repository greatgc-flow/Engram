"""Tests for the load-balancer DRIVING path (hub.resolve_auto_target / --to auto).

Opt-in routing; existing explicit --to is untouched. ag designed this; the
terminal applied it (peers do not write governed files — LL-005).
"""
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub


def test_lb_disabled_does_not_collect(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {"enabled": False})
    collected = {"n": 0}

    class DummySnapshot:
        def collect_snapshot(self, *a, **k):
            collected["n"] += 1
            return {}

    monkeypatch.setattr(hub, "snapshot", DummySnapshot())
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)

    res = hub.resolve_auto_target(tmp_path)
    assert res["target"] is None
    assert res["reason"] == "lb_disabled"
    assert collected["n"] == 0


def test_enabled_selector_returns_ag_and_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {"enabled": True})
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)

    class DummySnapshot:
        def collect_snapshot(self, *a, **k):
            return {"nodes": {}}
        def select_load_balanced_peer(self, snap, cfg, terminal_peer=None, ask_id="", **kw):
            return {"selected_peer": "ag", "weights": {"ag": 10}, "reason": "selected"}
        def snapshot_hash(self, snap):
            return "hash123"

    monkeypatch.setattr(hub, "snapshot", DummySnapshot())
    metrics = []
    monkeypatch.setattr(hub, "_record_routing_metric",
                        lambda ai, event, **kw: metrics.append((event, kw)))

    res = hub.resolve_auto_target(tmp_path)
    assert res["target"] == "ag"
    assert res["reason"] == "load_balanced"
    assert res["weights"] == {"ag": 10}
    assert res["snapshot_hash"] == "hash123"
    assert metrics[0][0] == "load_balance_route"
    assert metrics[0][1]["target"] == "ag"
    assert metrics[0][1]["snapshot_hash"] == "hash123"


def test_enabled_selector_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {"enabled": True})
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)

    class DummySnapshot:
        def collect_snapshot(self, *a, **k):
            return {}
        def select_load_balanced_peer(self, snap, cfg, terminal_peer=None, ask_id="", **kw):
            return {"selected_peer": None, "reason": "no_eligible_candidate"}

    monkeypatch.setattr(hub, "snapshot", DummySnapshot())
    res = hub.resolve_auto_target(tmp_path)
    assert res["target"] is None
    assert res["reason"] == "no_eligible_candidate"


def test_snapshot_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {"enabled": True})
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", False)

    res = hub.resolve_auto_target(tmp_path)
    assert res["target"] is None
    assert res["reason"] == "snapshot_unavailable"


def test_crash_safe(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {"enabled": True})
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)

    class DummySnapshot:
        def collect_snapshot(self, *a, **k):
            raise ValueError("Intentional crash")

    monkeypatch.setattr(hub, "snapshot", DummySnapshot())
    res = hub.resolve_auto_target(tmp_path)
    assert res["target"] is None
    assert "Intentional crash" in res["reason"]


def test_session_hysteresis_keeps_incumbent(monkeypatch):
    import snapshot
    snap = {"sessions": [{"scope_key": "room1:ag.deepthink", "status": "active", "peer": "ag"}]}
    monkeypatch.setattr(snapshot, "_derive_headroom_rows", lambda _s: [
        {"peer": "ag", "state": "eligible", "abs_headroom": 900000, "headroom": 0.9},
        {"peer": "cx", "state": "eligible", "abs_headroom": 200000, "headroom": 0.8},
    ])
    monkeypatch.setattr(hub, "_read_json", lambda p: {"room_id": "room1"})
    cfg = {"context_affinity": {"enabled": True, "switch_ratio": 2.0},
           "effective_headroom_floor": 0.10}
    # selected cx, but incumbent ag has >2x abs headroom -> keep ag
    target, reason = hub._session_hysteresis_target(snap, Path("x"), "cx", "cc", cfg)
    assert target == "ag" and reason == "session_hysteresis_kept"


def test_session_hysteresis_switches_on_big_challenger(monkeypatch):
    import snapshot
    snap = {"sessions": [{"scope_key": "room1:ag.deepthink", "status": "active", "peer": "ag"}]}
    monkeypatch.setattr(snapshot, "_derive_headroom_rows", lambda _s: [
        {"peer": "ag", "state": "eligible", "abs_headroom": 300000, "headroom": 0.3},
        {"peer": "cx", "state": "eligible", "abs_headroom": 900000, "headroom": 0.9},
    ])
    monkeypatch.setattr(hub, "_read_json", lambda p: {"room_id": "room1"})
    cfg = {"context_affinity": {"enabled": True, "switch_ratio": 2.0}}
    target, reason = hub._session_hysteresis_target(snap, Path("x"), "cx", "cc", cfg)
    assert target == "cx" and reason is None


def test_session_hysteresis_never_pins_terminal(monkeypatch):
    snap = {"sessions": [{"scope_key": "room1:cc.effort", "status": "active", "peer": "cc"}]}
    monkeypatch.setattr(hub, "_read_json", lambda p: {"room_id": "room1"})
    cfg = {"context_affinity": {"enabled": True}}
    target, reason = hub._session_hysteresis_target(snap, Path("x"), "ag", "cc", cfg)
    assert target == "ag" and reason is None
