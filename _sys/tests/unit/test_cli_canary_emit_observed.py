"""Regression tests for two real bugs in check_cli_canary.py's --emit-observed
path: (1) main() called emit_observed_capture() with no peers/force at all, so
--peer and --force were silently no-ops whenever --emit-observed was also
passed - the tool never did a fresh probe of just the requested target. (2)
once peers/force are wired through, a restricted --peer scope would overwrite
cli-reality-observed.json wholesale, silently dropping every other peer's
existing entry from what's meant to be a shared multi-peer snapshot."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SYS_DIR / "checks"))
import check_cli_canary as ccc  # noqa: E402

MOCK_ORCH = {
    "canary_config": {"budget_cap": 10, "budget_window_hours": 5.0, "reserve_floor": 0.0},
    "hub_nodes": [
        {
            "node_id": "cc",
            "type": "peer",
            "enabled": True,
            "profiles": {
                "standard": {
                    "model_id": "claude-haiku",
                    "cost_tier": "low",
                    "routing_state": "eligible",
                    "profile_args": ["--model", "claude-haiku"],
                },
            },
        },
        {
            "node_id": "ag",
            "type": "peer",
            "enabled": True,
            "profiles": {
                "standard": {
                    "runtime_model": "gemini-flash",
                    "cost_tier": "low",
                    "routing_state": "eligible",
                    "profile_args": ["--model", "gemini-flash"],
                },
            },
        },
    ],
}


def _mock_invoker(peer, profile, model, prompt):
    return "OK"


def _patch_probe_plumbing(monkeypatch, tmp_path):
    monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy", "exists": True})
    monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")


def test_restricted_peer_scope_merges_not_overwrites(monkeypatch, tmp_path):
    _patch_probe_plumbing(monkeypatch, tmp_path)

    # First: a full capture with both cc and ag.
    ccc.emit_observed_capture(MOCK_ORCH, tmp_path, invoker=_mock_invoker, force=True)
    out_file = tmp_path / "cli-reality-observed.json"
    before = json.loads(out_file.read_text(encoding="utf-8"))
    assert "cc" in before and "ag" in before

    # Then: a restricted re-probe of only cc must not drop ag's entry.
    ccc.emit_observed_capture(MOCK_ORCH, tmp_path, invoker=_mock_invoker, force=True, peers=["cc"])
    after = json.loads(out_file.read_text(encoding="utf-8"))
    assert "ag" in after, "restricted --peer scope silently dropped another peer's entry"
    assert "cc" in after


def test_main_wires_peer_and_force_through_emit_observed(monkeypatch, tmp_path):
    """main() used to call emit_observed_capture(orch, _AI_DIR) with no
    peers/force at all - --peer/--force were pure no-ops under --emit-observed."""
    _patch_probe_plumbing(monkeypatch, tmp_path)

    calls = []
    real = ccc.emit_observed_capture

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(ccc, "emit_observed_capture", spy)
    monkeypatch.setattr(ccc, "_AI_DIR", tmp_path)

    orch_path = tmp_path / "orchestration.json"
    orch_path.write_text(json.dumps(MOCK_ORCH), encoding="utf-8")
    monkeypatch.setattr(ccc, "_SYS_DIR", tmp_path.parent)
    (tmp_path.parent / "ai").mkdir(exist_ok=True)
    (tmp_path.parent / "ai" / "orchestration.json").write_text(json.dumps(MOCK_ORCH), encoding="utf-8")

    ccc.main(["--peer", "cc", "--force", "--emit-observed"])

    assert len(calls) == 1
    assert calls[0].get("peers") == ["cc"]
    assert calls[0].get("force") is True
