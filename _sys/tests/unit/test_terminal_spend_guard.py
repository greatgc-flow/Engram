"""D7 terminal-spend guard and LB-profile preservation contracts."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub  # noqa: E402


class ReachedDispatch(Exception):
    pass


def _patch_until_dispatch(monkeypatch, target):
    monkeypatch.setattr(hub, "_oversized_ask_limits", lambda: (0, 0))
    monkeypatch.setattr(hub, "_guard_action", lambda *a, **k: None)
    monkeypatch.setattr(
        hub, "_load_nodes",
        lambda ai_root: {target: {"invoke": "unused", "requires_pty": False}},
    )
    monkeypatch.setattr(hub, "_load_orchestration", lambda: {})
    monkeypatch.setattr(hub, "is_routable", lambda *a, **k: True)
    monkeypatch.setattr(hub, "_HUB_PEER_AVAILABLE", False)
    monkeypatch.setattr(
        hub, "_lease_sweep",
        lambda *a, **k: (_ for _ in ()).throw(ReachedDispatch()),
    )


def _terminal_selection(peer="cc"):
    return {"peer": peer, "profile": f"{peer}.deepthink", "eligible": True}


def test_explicit_terminal_profile_warns_records_and_proceeds(monkeypatch, tmp_path, capsys):
    _patch_until_dispatch(monkeypatch, "cc.deepthink")
    monkeypatch.setattr(hub, "_select_ask_profile", lambda to, q: (
        "cc.deepthink",
        {"root_peer": "cc", "selected_profile": "deepthink", "explicit": True,
         "classifier_triggered": False, "fallback_from": None, "node_id": "cc.deepthink"},
    ))
    monkeypatch.setattr(hub, "_select_human_interface_peer", lambda *a, **k: _terminal_selection())
    metrics = []
    monkeypatch.setattr(hub, "_record_routing_metric", lambda ai, event, **kw: metrics.append((event, kw)))

    with pytest.raises(ReachedDispatch):
        hub._action_ask_inner("cc.deepthink", "q", None, 10, tmp_path)

    assert "[HUB:WARN] terminal-token spend: cc.deepthink is on the human-interface peer; " \
           "use --allow-terminal-spend to acknowledge" in capsys.readouterr().err
    event = next(fields for name, fields in metrics if name == "terminal_spend_guard")
    assert event == {
        "mode": "warn", "reason": "explicit_target", "terminal_peer": "cc",
        "requested_target": "cc.deepthink", "resolved_target": "cc.deepthink",
        "origin": "terminal", "acknowledged": False,
    }


def test_allow_terminal_spend_acknowledges_silently(monkeypatch, tmp_path, capsys):
    _patch_until_dispatch(monkeypatch, "cc.deepthink")
    monkeypatch.setattr(hub, "_select_ask_profile", lambda to, q: (
        "cc.deepthink",
        {"root_peer": "cc", "selected_profile": "deepthink", "explicit": True,
         "classifier_triggered": False, "fallback_from": None, "node_id": "cc.deepthink"},
    ))
    monkeypatch.setattr(hub, "_select_human_interface_peer", lambda *a, **k: _terminal_selection())
    metrics = []
    monkeypatch.setattr(hub, "_record_routing_metric", lambda ai, event, **kw: metrics.append((event, kw)))

    with pytest.raises(ReachedDispatch):
        hub._action_ask_inner(
            "cc.deepthink", "q", None, 10, tmp_path, allow_terminal_spend=True
        )

    assert "terminal-token spend" not in capsys.readouterr().err
    event = next(fields for name, fields in metrics if name == "terminal_spend_guard")
    assert event["acknowledged"] is True
    assert event["reason"] == "explicit_target"


def test_terminal_same_peer_fallback_records_specific_reason(monkeypatch, tmp_path):
    _patch_until_dispatch(monkeypatch, "cc.standard")
    monkeypatch.setattr(hub, "_select_ask_profile", lambda to, q: (
        "cc.standard",
        {"root_peer": "cc", "selected_profile": "standard", "explicit": True,
         "classifier_triggered": False, "fallback_from": "effort", "node_id": "cc.standard"},
    ))
    monkeypatch.setattr(hub, "_select_human_interface_peer", lambda *a, **k: _terminal_selection())
    metrics = []
    monkeypatch.setattr(hub, "_record_routing_metric", lambda ai, event, **kw: metrics.append((event, kw)))

    with pytest.raises(ReachedDispatch):
        hub._action_ask_inner("cc.effort", "q", None, 10, tmp_path)

    event = next(fields for name, fields in metrics if name == "terminal_spend_guard")
    assert event["reason"] == "same_peer_fallback"
    assert event["requested_target"] == "cc.effort"
    assert event["resolved_target"] == "cc.standard"


def test_worker_explicit_terminal_target_uses_worker_reason(monkeypatch, tmp_path):
    _patch_until_dispatch(monkeypatch, "cc.standard")
    monkeypatch.setattr(hub, "_select_ask_profile", lambda to, q: (
        "cc.standard",
        {"root_peer": "cc", "selected_profile": "standard", "explicit": False,
         "classifier_triggered": True, "fallback_from": None, "node_id": "cc.standard"},
    ))
    monkeypatch.setattr(hub, "_select_human_interface_peer", lambda *a, **k: _terminal_selection())
    metrics = []
    monkeypatch.setattr(hub, "_record_routing_metric", lambda ai, event, **kw: metrics.append((event, kw)))

    with pytest.raises(ReachedDispatch):
        hub._action_ask_inner("cc", "q", None, 10, tmp_path, origin="worker")

    event = next(fields for name, fields in metrics if name == "terminal_spend_guard")
    assert event["reason"] == "worker_explicit_target"
    assert event["origin"] == "worker"


def test_lb_locked_profile_bypasses_profile_router_end_to_end(monkeypatch, tmp_path):
    _patch_until_dispatch(monkeypatch, "ag.gptoss")
    monkeypatch.setattr(
        hub, "_select_ask_profile",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LB profile was reclassified")),
    )
    monkeypatch.setattr(
        hub, "_select_human_interface_peer",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("AUTO target was guarded as explicit")),
    )

    with pytest.raises(ReachedDispatch):
        hub._action_ask_inner(
            "ag.gptoss", "q", None, 10, tmp_path, _load_balanced=True
        )


def test_action_ask_threads_terminal_spend_and_lb_flags(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(hub, "_action_ask_inner", lambda *a, **kw: captured.update(kw))

    hub.action_ask(
        "ag.gptoss", "q", None, 10, tmp_path,
        allow_governed_mutation=True,
        allow_terminal_spend=True,
        _load_balanced=True,
    )

    assert captured["allow_terminal_spend"] is True
    assert captured["_load_balanced"] is True


def test_cli_threads_allow_terminal_spend_and_auto_lock(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(hub, "find_ai_root", lambda: tmp_path)
    monkeypatch.setattr(hub, "ensure_ai_dir", lambda ai_root: None)
    monkeypatch.setattr(hub, "action_ask", lambda *a, **kw: calls.append((a, kw)))

    monkeypatch.setattr(sys, "argv", [
        "hub.py", "ask", "--to", "cc.deepthink", "--query", "q",
        "--allow-terminal-spend",
    ])
    hub.main()
    assert calls[-1][1]["allow_terminal_spend"] is True
    assert calls[-1][1]["_load_balanced"] is False

    monkeypatch.setattr(
        hub, "resolve_auto_target",
        lambda *a, **k: {"target": "ag.gptoss", "weights": {"ag": 1.0}},
    )
    monkeypatch.setattr(sys, "argv", ["hub.py", "ask", "--to", "auto", "--query", "q"])
    hub.main()
    assert calls[-1][0][0] == "ag.gptoss"
    assert calls[-1][1]["_load_balanced"] is True
