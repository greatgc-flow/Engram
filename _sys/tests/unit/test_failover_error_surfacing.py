"""T54: actionable ask-failure surfacing without retry or reroute."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from _sys.core import hub


def test_pre_dispatch_red_target_is_explicitly_not_invoked(monkeypatch, tmp_path, capsys):
    metrics = []
    monkeypatch.setattr(
        hub,
        "_peer_effective_health",
        lambda peer_id: (
            "RED",
            {
                "availability": {"quarantined": True, "gate_open": False},
                "session_health": {"last_failure_reason": "operational_error:nonzero_exit"},
            },
        ),
    )
    monkeypatch.setattr(hub, "_load_orchestration", lambda: {"hub_nodes": []})
    monkeypatch.setattr(
        hub,
        "_record_routing_metric",
        lambda ai_root, event, **fields: metrics.append({"event": event, **fields}),
    )

    with pytest.raises(SystemExit) as exc:
        hub._ask_health_precheck("ag", tmp_path / ".ai")

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "target_not_invoked=true" in err
    assert "phase=pre_dispatch" in err
    assert "peer-recover --peer ag" in err
    assert "--to auto" in err
    assert metrics[-1] == {
        "event": "direct_ask",
        "selected_peer": "ag",
        "outcome": "failure",
        "failure_reason": "operational_error:nonzero_exit",
        "dispatch_phase": "pre_dispatch",
        "execution_certainty": "not_started",
        "target_not_invoked": True,
    }


def test_post_spawn_nonzero_is_uncertain_and_never_rerouted(tmp_path, capsys):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)

    proc = MagicMock()
    proc.pid = 12345
    proc.returncode = 7
    metrics = []

    with (
        patch("_sys.core.hub._spawn_process", return_value=proc),
        patch("_sys.core.hub._stream_process_output", return_value=(b"", b"fatal")),
        patch("_sys.core.hub._lease_sweep"),
        patch("_sys.core.hub._lease_open"),
        patch("_sys.core.hub._lease_close") as lease_close,
        patch("_sys.core.hub._ask_health_precheck"),
        patch("_sys.core.hub._guard_action"),
        patch("_sys.core.hub._record_ask_failure"),
        patch("_sys.core.hub._append_ask_history"),
        patch("_sys.core.hub._record_routing_metric") as record_metric,
        patch("_sys.core.hub._snapshot_failover_choice") as failover_choice,
    ):
        record_metric.side_effect = (
            lambda root, event, **fields: metrics.append({"event": event, **fields})
        )
        with pytest.raises(SystemExit) as exc:
            hub.action_ask(
                to="cc.standard",
                query="read-only diagnostic",
                query_file=None,
                timeout_sec=10,
                ai_root=ai_root,
                quiet=True,
                output_file=None,
                include_context=False,
                session_policy="off",
                explicit_scope=None,
                origin="test",
                allow_governed_mutation=True,
            )

    assert exc.value.code == 1  # unchanged from the existing nonzero path
    err = capsys.readouterr().err
    assert "cc.standard failed after dispatch" in err
    assert "execution_state=uncertain" in err
    assert "automatic retry suppressed to avoid duplicate side effects" in err
    post_metric = next(
        item for item in metrics
        if item.get("dispatch_phase") == "post_spawn"
    )
    assert post_metric["selected_peer"] == "cc.standard"
    assert post_metric["execution_certainty"] == "uncertain"
    assert post_metric["retry_suppressed_reason"] == "duplicate_execution_risk"
    lease_close.assert_called_with(ai_root, "cc.standard", 12345, "failed")
    failover_choice.assert_not_called()

