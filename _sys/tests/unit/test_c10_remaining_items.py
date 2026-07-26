"""Focused regressions for the remaining C10 single-pass items."""
from __future__ import annotations

import dataclasses
import inspect
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[3]
SYS = ROOT / "_sys"
CORE = SYS / "core"
CLI = SYS / "cli"
for path in (CORE, CLI):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import diag
import hub
import hub_peer
import quota_capabilities
import snapshot


def _orchestration():
    return json.loads((SYS / "ai" / "orchestration.json").read_text(encoding="utf-8"))


def test_reset_credit_capability_is_explicit_and_root_normalized():
    orch = _orchestration()
    assert quota_capabilities.supports_reset_credits("cx", orchestration=orch)
    assert quota_capabilities.supports_reset_credits("codex", orchestration=orch)
    assert quota_capabilities.supports_reset_credits("cx.deepthink", orchestration=orch)
    assert not quota_capabilities.supports_reset_credits("cc", orchestration=orch)

    # Transient telemetry cannot manufacture a missing capability.
    cc = next(node for node in orch["hub_nodes"] if node["node_id"] == "cc")
    cc["rateLimitResetCredits"] = {"availableCount": 99}
    assert not quota_capabilities.supports_reset_credits("cc", orchestration=orch)


def test_all_three_credit_consumers_use_the_shared_capability_helper():
    assert "supports_reset_credits" in inspect.getsource(hub.action_credit_status)
    assert "supports_reset_credits" in inspect.getsource(snapshot.gather_peer)
    assert "supports_reset_credits" in inspect.getsource(diag.render_summary)


def test_credit_status_rejects_unsupported_peer_before_client(monkeypatch):
    client = MagicMock(side_effect=AssertionError("client must not be opened"))
    monkeypatch.setattr(hub, "CodexAccountClient", client)
    with pytest.raises(SystemExit) as exc:
        hub.action_credit_status("cc")
    assert exc.value.code == 3
    client.assert_not_called()


def test_admission_normalizes_profiles_aliases_and_registered_services():
    assert hub._canonical_admission_identity("claude", role="sender") == "cc"
    assert hub._canonical_admission_identity("cx.deepthink", role="recipient") == "cx"
    assert hub._canonical_admission_identity("system", role="sender") == "system"
    with pytest.raises(ValueError):
        hub._canonical_admission_identity("arbitrary-daemon", role="sender")


def test_init_session_rejects_before_any_sweep_or_state_mutation(monkeypatch, tmp_path):
    sweep = MagicMock()
    monkeypatch.setattr(hub, "_lease_sweep", sweep)
    with pytest.raises(SystemExit):
        hub.action_init_session(tmp_path / ".ai", "arbitrary")
    sweep.assert_not_called()
    assert not (tmp_path / ".ai").exists()


def test_send_validates_every_identity_before_policy_or_payload_write(monkeypatch, tmp_path):
    policy = MagicMock(side_effect=AssertionError("policy read is after admission"))
    monkeypatch.setattr(hub, "_load_lifecycle_policy", policy)
    with pytest.raises(SystemExit):
        hub.action_send(
            tmp_path / ".ai", "cx.effort", "cc", "x" * 100_000,
            cc_list=["ag", "not-a-peer"],
        )
    policy.assert_not_called()
    assert not (tmp_path / ".ai" / "payloads").exists()


def test_agy_prepare_input_stages_exact_utf8_and_is_immutable(tmp_path):
    adapter = hub_peer.AgyAdapter()
    node = {
        "invoke": "agy",
        "invoke_args": ["-p", "{query}"],
        "requires_pty": True,
    }
    query = "한글🙂\n" * 20
    invocation = hub_peer.SessionInvocation(
        adapter.build_cmd(node, query)[0], False, None
    )
    prepared = adapter.prepare_input(
        node, query, invocation, ask_id="ask-safe", ai_root=tmp_path / ".ai",
        cwd=tmp_path, transport_limits={"inline_command_chars": 1},
    )
    try:
        assert len(prepared.staged_artifacts) == 1
        staged = prepared.staged_artifacts[0]
        assert staged.parent == (tmp_path / ".ai" / "ipc").resolve()
        assert staged.read_bytes() == query.encode("utf-8")
        metadata = dict(prepared.cleanup_metadata)
        assert metadata["utf8_bytes"] == str(len(query.encode("utf-8")))
        assert metadata["sha256"] in " ".join(prepared.argv)
        with pytest.raises(dataclasses.FrozenInstanceError):
            prepared.argv = ()
    finally:
        for artifact in prepared.staged_artifacts:
            artifact.unlink(missing_ok=True)


def test_agy_prepare_input_rejects_crafted_ask_id(tmp_path):
    adapter = hub_peer.AgyAdapter()
    node = {"invoke": "agy", "invoke_args": ["-p", "{query}"], "requires_pty": True}
    query = "oversized"
    invocation = hub_peer.SessionInvocation(adapter.build_cmd(node, query)[0], False)
    with pytest.raises(ValueError, match="unsafe"):
        adapter.prepare_input(
            node, query, invocation, ask_id="../escape", ai_root=tmp_path / ".ai",
            cwd=tmp_path, transport_limits={"inline_command_chars": 1},
        )
    assert not (tmp_path / "escape-ag-prompt.txt").exists()


def test_hub_owns_prepared_artifact_cleanup_and_no_longer_decides_staging():
    source = inspect.getsource(hub._action_ask_inner)
    assert "for staged_path in prepared.staged_artifacts" in source
    assert "list2cmdline(cmd)" not in source
    assert "ag-prompt" not in source


@pytest.mark.skipif(sys.platform != "win32", reason="PTY dispatch is Windows-only")
def test_staged_prompt_lives_through_pty_child_and_is_cleaned_after(
    monkeypatch, tmp_path
):
    from test_process_lease_supervision_c7 import _patch_ask_runtime

    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub.ensure_ai_dir(ai_root)
    _patch_ask_runtime(monkeypatch)
    monkeypatch.setattr(hub, "_oversized_ask_limits", lambda: (0, 0))
    adapter = hub_peer.AgyAdapter()
    prepared_seen = []
    original_prepare = adapter.prepare_input

    def tracking_prepare(*args, **kwargs):
        prepared = original_prepare(*args, **kwargs)
        prepared_seen.append(prepared)
        return prepared

    monkeypatch.setattr(adapter, "prepare_input", tracking_prepare)
    monkeypatch.setattr(hub.hub_peer, "get_adapter", lambda node: adapter)
    monkeypatch.setattr(hub, "_lease_close", lambda *args, **kwargs: None)

    query = "한글🙂" * 10_000

    def fake_pty(*args, **kwargs):
        assert prepared_seen
        staged = prepared_seen[0].staged_artifacts[0]
        assert staged.exists()
        assert staged.read_bytes() == query.encode("utf-8")
        return hub._PtyAskResult(
            text="answer\n", elapsed=1, exit_code=0, timed_out=False,
            timeout_kind=None, pid=44001, lease_id="c10-stage",
        )

    monkeypatch.setattr(hub, "_ask_with_pty", fake_pty)
    hub.action_ask(
        to="ag.standard", query=query, query_file=None, timeout_sec=5,
        ai_root=ai_root, quiet=True, output_file=None, include_context=False,
        session_policy="none", _escalation_depth=1, origin="test",
        allow_governed_mutation=True, governed_mutation_reason="C10 regression",
    )
    assert prepared_seen
    assert not prepared_seen[0].staged_artifacts[0].exists()


def test_quota_timestamp_rejects_naive_with_provenance():
    parsed, provenance = snapshot._parse_quota_reset(
        "2030-01-01T12:00:00", provider="vendor"
    )
    assert parsed is None
    assert provenance["reason"] == "naive_timestamp"
    assert provenance["timezone_policy"] == "reject_naive"


def test_quota_timestamp_honors_explicit_provider_timezone_contract():
    parsed, provenance = snapshot._parse_quota_reset(
        "2030-01-01T12:00:00",
        provider="vendor",
        timezone_contract="Asia/Seoul",
    )
    assert parsed is not None
    assert provenance["timezone_policy"] == "provider_contract:Asia/Seoul"


def test_context_ack_removed_from_live_api_protocol_and_guard():
    protocol = json.loads((SYS / "ai" / "protocol.json").read_text(encoding="utf-8"))
    assert not hasattr(hub, "action_context_ack")
    assert "context-ack" not in json.dumps(protocol)
    assert "context_ack" not in protocol.get("operational_guard", {})
    assert "context-ack" not in hub._SYSTEM_EXEMPT_ACTIONS


def test_unknown_pacing_renderer_never_fabricates_zero_ratio():
    rendered = snapshot.format_quota_bucket({
        "used_frac": 0.5,
        "pacing": {
            "ratio": None, "status": "unknown", "indicator": "",
            "invalid_input_reason": "window_hours_not_finite",
        },
    })
    assert "0.00x" not in rendered
    assert "?" in rendered


def test_context_gate_traceability_points_to_live_docs_and_tests():
    trace = json.loads((SYS / "ai" / "traceability_map.json").read_text(encoding="utf-8"))
    entry = next(item for item in trace["entries"] if item["id"] == "context-gate")
    assert entry["docs"] == [
        "_sys/docs-v2/general/lifecycle.md#20-contextgate-v10-design"
    ]
    assert entry["tests"] == [
        "_sys/tests/unit/test_context_gate_c2.py",
        "_sys/tests/unit/test_context_gate_c3.py",
    ]
    lifecycle = (SYS / "docs-v2" / "general" / "lifecycle.md").read_text(
        encoding="utf-8"
    )
    assert "## 20. ContextGate v1.0 Design" in lifecycle
    for ref in entry["tests"]:
        assert (ROOT / ref).is_file()
