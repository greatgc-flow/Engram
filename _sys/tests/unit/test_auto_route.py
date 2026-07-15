"""Tests for the load-balancer DRIVING path (hub.resolve_auto_target / --to auto).

Opt-in routing; existing explicit --to is untouched. ag designed this; the
terminal applied it (peers do not write governed files — LL-005).
"""
import copy
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
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {
        "enabled": True, "terminal_hard_exclude": False,
    })
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)

    class DummySnapshot:
        def collect_snapshot(self, *a, **k):
            return {"nodes": {}}
        def select_load_balanced_peer(self, snap, cfg, terminal_peer=None, ask_id="", **kw):
            return {
                "selected_peer": "ag",
                "selected": {"peer": "ag", "profile": "ag.gptoss"},
                "representative_profiles": {"ag": "ag.gptoss"},
                "weights": {"ag": 10},
                "reason": "selected",
            }
        def snapshot_hash(self, snap):
            return "hash123"

    monkeypatch.setattr(hub, "snapshot", DummySnapshot())
    metrics = []
    monkeypatch.setattr(hub, "_record_routing_metric",
                        lambda ai, event, **kw: metrics.append((event, kw)))

    res = hub.resolve_auto_target(tmp_path)
    assert res["target"] == "ag.gptoss"
    assert res["reason"] == "load_balanced"
    assert res["weights"] == {"ag": 10}
    assert res["snapshot_hash"] == "hash123"
    assert metrics[0][0] == "load_balance_route"
    assert metrics[0][1]["target"] == "ag.gptoss"
    assert metrics[0][1]["snapshot_hash"] == "hash123"


def test_load_balance_route_metric_is_enriched_without_changing_auto_route(monkeypatch, tmp_path):
    """T57: telemetry is additive; the selected route is unchanged by recording it."""
    config = {"enabled": True, "terminal_hard_exclude": False}
    decision = {
        "selected_peer": "ag",
        "selected": {
            "peer": "ag", "profile": "ag.gptoss", "quota_families": ["3P"],
        },
        "representative_profiles": {"ag": "ag.gptoss", "cx": "cx.effort"},
        "weights": {"ag": 0.6, "cx": 0.4},
        "probabilities": {"ag": 0.6, "cx": 0.4},
        "pacing_applied": {"ag": 1.25, "cx": 1.0},
        "telemetry_events": [{"event": "shared_quota_reserve_clamp", "profile": "cx.effort"}],
        "reason": "selected",
    }

    class DummySnapshot:
        def collect_snapshot(self, *a, **k):
            return {"nodes": {}}
        def select_load_balanced_peer(self, snap, cfg, terminal_peer=None, ask_id="", **kw):
            return copy.deepcopy(decision)
        def snapshot_hash(self, snap):
            return "hash-enriched"

    monkeypatch.setattr(hub, "snapshot", DummySnapshot())
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)
    metrics = []
    monkeypatch.setattr(
        hub, "_record_routing_metric", lambda _root, event, **fields: metrics.append((event, fields))
    )

    first = hub.resolve_auto_target(tmp_path, config=config)
    first_metric = next(fields for event, fields in metrics if event == "load_balance_route")
    metrics.clear()
    second = hub.resolve_auto_target(tmp_path, config=config)

    assert first == second
    assert first_metric["pacing_applied"] == {"ag": 1.25, "cx": 1.0}
    assert sum(first_metric["probabilities"].values()) == 1.0
    assert first_metric["representative_profiles"] == {"ag": "ag.gptoss", "cx": "cx.effort"}
    assert first_metric["quota_families"] == ["3P"]
    assert first_metric["reserve_clamp_applied"] is True


def test_enabled_selector_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {
        "enabled": True, "terminal_hard_exclude": False,
    })
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
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {
        "enabled": True, "terminal_hard_exclude": False,
    })
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", False)

    res = hub.resolve_auto_target(tmp_path)
    assert res["target"] is None
    assert res["reason"] == "snapshot_unavailable"


def test_crash_safe(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {
        "enabled": True, "terminal_hard_exclude": False,
    })
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)

    class DummySnapshot:
        def collect_snapshot(self, *a, **k):
            raise ValueError("Intentional crash")

    monkeypatch.setattr(hub, "snapshot", DummySnapshot())
    res = hub.resolve_auto_target(tmp_path)
    assert res["target"] is None
    assert "Intentional crash" in res["reason"]


def test_auto_uses_human_interface_terminal_not_active_coordinator(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)
    monkeypatch.setattr(
        hub, "_select_human_interface_peer",
        lambda ai_root, now=None: {"peer": "cc", "profile": "cc.deepthink", "eligible": True},
    )
    (tmp_path / "state.json").write_text('{"active_coordinator":"cx"}', encoding="utf-8")
    seen = {}

    class DummySnapshot:
        def collect_snapshot(self, *a, **k):
            return {"nodes": {}}
        def select_load_balanced_peer(self, snap, cfg, terminal_peer=None, ask_id="", **kw):
            seen["terminal_peer"] = terminal_peer
            return {
                "selected_peer": "ag",
                "selected": {"peer": "ag", "profile": "ag.gptoss"},
                "representative_profiles": {"ag": "ag.gptoss"},
                "weights": {"cc": 0.0, "ag": 1.0},
            }
        def snapshot_hash(self, snap):
            return "hash-terminal"

    monkeypatch.setattr(hub, "snapshot", DummySnapshot())
    monkeypatch.setattr(hub, "_record_routing_metric", lambda *a, **k: None)
    res = hub.resolve_auto_target(
        tmp_path, config={"enabled": True, "terminal_hard_exclude": True}
    )

    assert seen["terminal_peer"] == "cc"
    assert res["target"] == "ag.gptoss"


def test_auto_fails_loud_when_terminal_identity_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)
    monkeypatch.setattr(
        hub, "_select_human_interface_peer",
        lambda ai_root, now=None: {
            "peer": None, "profile": None, "eligible": False,
            "reason": "no_eligible_human_interface_peer",
        },
    )

    class DummySnapshot:
        def collect_snapshot(self, *a, **k):
            raise AssertionError("snapshot collection must not run without terminal identity")

    monkeypatch.setattr(hub, "snapshot", DummySnapshot())
    res = hub.resolve_auto_target(
        tmp_path, config={"enabled": True, "terminal_hard_exclude": True}
    )

    assert res["target"] is None
    assert res["reason"] == "terminal_identity_absent"
    assert res["terminal_reason"] == "no_eligible_human_interface_peer"


def test_hysteresis_uses_post_exclusion_representative_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)
    monkeypatch.setattr(
        hub, "_select_human_interface_peer",
        lambda ai_root, now=None: {"peer": "cc", "profile": "cc.deepthink", "eligible": True},
    )
    monkeypatch.setattr(
        hub, "_session_hysteresis_target",
        lambda snap, ai_root, selected, terminal_peer, cfg: ("ag", "session_hysteresis_kept"),
    )

    class DummySnapshot:
        def collect_snapshot(self, *a, **k):
            return {}
        def select_load_balanced_peer(self, snap, cfg, terminal_peer=None, ask_id="", **kw):
            return {
                "selected_peer": "cx",
                "selected": {"peer": "cx", "profile": "cx.deepthink"},
                "representative_profiles": {
                    "ag": "ag.gptoss",
                    "cx": "cx.deepthink",
                },
                "weights": {"ag": 0.4, "cx": 0.6},
            }
        def snapshot_hash(self, snap):
            return "hash-hysteresis"

    monkeypatch.setattr(hub, "snapshot", DummySnapshot())
    monkeypatch.setattr(hub, "_record_routing_metric", lambda *a, **k: None)
    res = hub.resolve_auto_target(
        tmp_path, config={"enabled": True, "terminal_hard_exclude": True}
    )

    assert res["target"] == "ag.gptoss"
    assert res["reason"] == "session_hysteresis_kept"


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
