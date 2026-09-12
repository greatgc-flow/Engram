import sys
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub
import pytest


class _DispatchCaptured(Exception):
    def __init__(self, session_id, query):
        super().__init__(session_id)
        self.session_id = session_id
        self.query = query


class _RecordingAdapter:
    def context_policy(self, node):
        return hub.hub_peer.ContextPolicy()

    def session_fingerprint(self, node):
        return "fingerprint"

    def build_session_cmd(self, node, query, session_id=None):
        raise _DispatchCaptured(session_id, query)

    def build_cmd(self, node, query):
        raise _DispatchCaptured(None, query)


def _run_reuse_branch(monkeypatch, tmp_path, utilization_pct, session_policy="auto", peer="cx", profile="cx.effort", protocol_cfg=None):
    if protocol_cfg is None:
        protocol_cfg = {
            "active_constraints": {
                "session_rotation_utilization_threshold": 0.75,
            },
            "session": {"context_fill_sections": ["GOAL"]},
        }
    ai_root = tmp_path / ".ai"
    handoff_dir = ai_root / "sessions" / "room-1"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (ai_root / "state.json").write_text(
        '{"room_id": "room-1", "members": {}, "phase": "active"}',
        encoding="utf-8",
    )
    (handoff_dir / "handoff.md").write_text(
        "## [GOAL]\n- continuity survives rotation\n",
        encoding="utf-8",
    )

    node = {
        "node_id": profile,
        "invoke": "fake",
        "session_mode": "reuse",
    }
    existing = {
        "session_id": "session-existing",
        "scope_key": f"room-1:{profile}",
        "status": "active",
        "fingerprint": "fingerprint",
    }
    session_row = {
        "peer": peer,
        "profile": profile,
        "scope_key": f"room-1:{profile}",
        "session_id": "session-existing",
        "context": {"utilization_pct": utilization_pct},
    }
    retired = []
    adapter = _RecordingAdapter()

    monkeypatch.setattr(hub, "_oversized_ask_limits", lambda: (0, 0))
    monkeypatch.setattr(hub, "_select_ask_profile", lambda to, query: (to, None))
    monkeypatch.setattr(hub, "_terminal_spend_guard", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_guard_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_load_nodes", lambda _ai_root: {profile: node})
    monkeypatch.setattr(hub, "_load_orchestration", lambda: {})
    monkeypatch.setattr(hub, "_resolve_profile_id", lambda _node_id: profile)
    monkeypatch.setattr(hub, "is_routable", lambda node_id, orch=None: True)
    def fake_root_peer_id(node_id, orch=None):
        return peer

    monkeypatch.setattr(hub.hub_peer, "root_peer_id", fake_root_peer_id)
    monkeypatch.setattr(hub.hub_peer, "get_adapter", lambda _node: adapter)
    monkeypatch.setattr(hub, "_CONTEXT_GATE_AVAILABLE", False)
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)
    monkeypatch.setattr(hub, "_load_balancer_config", lambda: {})
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: protocol_cfg)
    monkeypatch.setattr(
        hub.snapshot,
        "collect_snapshot",
        lambda use_cache=True: {"sessions": [session_row]},
    )
    monkeypatch.setattr(hub, "_lease_sweep", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "action_consensus_sweep", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_ask_health_precheck", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_get_active_session", lambda p, scope: existing)
    monkeypatch.setattr(
        hub,
        "_retire_session",
        lambda p, scope, reason, ai_root=None: retired.append((p, scope, reason)),
    )
    monkeypatch.setattr(hub, "_shadow_log_load_balance", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_get_active_runtime_directives", lambda path: [])
    monkeypatch.setattr(hub, "_load_active_lessons", lambda **kwargs: [])

    with pytest.raises(_DispatchCaptured) as captured:
        hub._action_ask_inner(
            to=profile,
            query="continue",
            query_file=None,
            timeout_sec=0,
            ai_root=ai_root,
            quiet=True,
            include_context=True,
            session_policy=session_policy,
            origin="test",
        )
    return captured.value, retired

def test_session_policy_auto_matches_node_capability():
    # 'auto' means use whatever the node natively supports
    node_with_reuse = {"node_id": "test", "session_mode": "reuse"}
    node_without = {"node_id": "test", "session_mode": "none"}
    
    assert hub._session_reuse_enabled(node_with_reuse, "auto") is True
    assert hub._session_reuse_enabled(node_without, "auto") is False

def test_session_policy_fresh_or_none_always_disables():
    # 'fresh' or 'none' overrides a capable node
    node_with_reuse = {"node_id": "test", "session_mode": "reuse"}
    
    assert hub._session_reuse_enabled(node_with_reuse, "fresh") is False
    assert hub._session_reuse_enabled(node_with_reuse, "none") is False

def test_session_policy_reuse_enforces_capability():
    # 'reuse' works if the node has it
    node_with_reuse = {"node_id": "test", "session_mode": "reuse"}
    assert hub._session_reuse_enabled(node_with_reuse, "reuse") is True
    
    # 'reuse' raises if the node lacks capability
    node_without = {"node_id": "test", "session_mode": "none"}
    with pytest.raises(ValueError, match="no configured session-reuse capability"):
        hub._session_reuse_enabled(node_without, "reuse")


def test_session_below_rotation_threshold_is_reused(monkeypatch, tmp_path):
    captured, retired = _run_reuse_branch(monkeypatch, tmp_path, 74.9)

    assert captured.session_id == "session-existing"
    assert retired == []


def test_session_at_rotation_threshold_starts_fresh_with_handoff(
    monkeypatch, tmp_path, capsys,
):
    captured, retired = _run_reuse_branch(
        monkeypatch, tmp_path, 75.0, session_policy="reuse"
    )

    assert captured.session_id is None
    assert retired == [
        ("cx", "room-1:cx.effort", "context_utilization_threshold"),
    ]
    assert "[HANDOFF]" in captured.query
    assert "continuity survives rotation" in captured.query
    warning = capsys.readouterr().err
    assert "[HUB:WARN] auto-rotated cx.effort session session-existing" in warning
    assert "utilization 75.0% >= threshold 75.0%" in warning


def test_session_with_absent_utilization_fails_open_to_reuse(monkeypatch, tmp_path):
    captured, retired = _run_reuse_branch(monkeypatch, tmp_path, None)

    assert captured.session_id == "session-existing"
    assert retired == []


def test_protocol_declares_session_rotation_threshold():
    active_constraints = hub._load_protocol_cfg().get("active_constraints", {})

    assert active_constraints.get("session_rotation_utilization_threshold") == 0.75

def test_session_rotation_override_honored_for_cc(monkeypatch, tmp_path):
    protocol_cfg = {
        "active_constraints": {
            "session_rotation_utilization_threshold": 0.75,
            "session_rotation_utilization_threshold_by_peer": {"cc": 0.90},
        },
        "session": {"context_fill_sections": ["GOAL"]},
    }
    # Fake root_peer_id as 'cc'
    monkeypatch.setattr(hub.hub_peer, "root_peer_id", lambda node_id, orch=None: "cc")
    
    # 80% is BELOW the 0.90 threshold for cc, so it should be reused
    captured, retired = _run_reuse_branch(monkeypatch, tmp_path, 80.0, peer="cc", profile="cc.effort", protocol_cfg=protocol_cfg)
    assert captured.session_id == "session-existing"
    assert retired == []

    # 91% is ABOVE the 0.90 threshold for cc, so it should rotate
    captured, retired = _run_reuse_branch(monkeypatch, tmp_path, 91.0, peer="cc", profile="cc.effort", protocol_cfg=protocol_cfg)
    assert captured.session_id is None
    assert len(retired) == 1
    assert retired[0][2] == "context_utilization_threshold"

def test_session_rotation_fallback_for_peer_without_override(monkeypatch, tmp_path):
    protocol_cfg = {
        "active_constraints": {
            "session_rotation_utilization_threshold": 0.75,
            "session_rotation_utilization_threshold_by_peer": {"cc": 0.90},
        },
        "session": {"context_fill_sections": ["GOAL"]},
    }
    # Fake root_peer_id as 'ag', which has no override
    monkeypatch.setattr(hub.hub_peer, "root_peer_id", lambda node_id, orch=None: "ag")

    # 80% is ABOVE the 0.75 fallback threshold for ag, so it should rotate
    captured, retired = _run_reuse_branch(monkeypatch, tmp_path, 80.0, peer="ag", profile="ag.effort", protocol_cfg=protocol_cfg)
    assert captured.session_id is None
    assert len(retired) == 1
    assert retired[0][2] == "context_utilization_threshold"

def test_velocity_signal_skipped_deliberately():
    # As requested: documented decision
    # The velocity signal isn't cheaply implementable without a disproportionate new tracking mechanism.
    # snapshot.py only retains the point-in-time utilization_pct for the active session, 
    # and extracting previous session frames requires parsing legacy histories or sqlite databases
    # which is computationally expensive and complex just for this.
    pass
