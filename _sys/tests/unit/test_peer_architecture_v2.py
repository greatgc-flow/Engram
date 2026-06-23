"""MECE contracts added by the 2026-06-19 peer architecture review."""
import json
import subprocess
import sys
from pathlib import Path

SYS = Path(__file__).parent.parent.parent
ROOT = SYS.parent
sys.path.insert(0, str(SYS / "core"))
sys.path.insert(0, str(SYS / "tests"))
import hub
import hub_peer
import benchmark_peer_routing


def _json(rel):
    return json.loads((SYS / rel).read_text(encoding="utf-8"))


def test_root_default_profile_is_applied():
    nodes = hub._default_nodes()["nodes"]
    assert nodes["cx"]["profile_id"] == "cx.standard"
    assert nodes["cc"]["profile_id"] == "cc.standard"
    assert nodes["ag"]["profile_id"] == "ag.standard"
    assert nodes["cc"]["model_availability"] == "verified_local"
    assert nodes["cx"]["model_availability"] == "verified_local"


def test_ag_deepthink_is_routable_after_local_model_verification():
    assert hub.is_routable("ag.deepthink")
    assert "ag.deepthink" in hub._default_nodes()["nodes"]


def test_profile_invocation_contains_model_options():
    nodes = hub._default_nodes()["nodes"]
    cmd, _ = hub_peer.get_adapter(nodes["cx.deepthink"]).build_cmd(
        nodes["cx.deepthink"], "review", None
    )
    assert "--model" in cmd and "gpt-5.5" in cmd
    assert 'model_reasoning_effort="xhigh"' in cmd


def test_ag_profile_invocation_contains_verified_runtime_model():
    nodes = hub._default_nodes()["nodes"]
    cmd, _ = hub_peer.get_adapter(nodes["ag.deepthink"]).build_cmd(
        nodes["ag.deepthink"], "review", None
    )
    assert cmd[-2:] == ["--model", "Gemini 3.1 Pro (High)"]


def test_profile_session_fingerprint_inputs_are_distinct():
    nodes = hub._default_nodes()["nodes"]
    standard = json.dumps(
        {"profile_id": nodes["cx.standard"]["profile_id"], "profile_args": nodes["cx.standard"]["profile_args"]},
        sort_keys=True,
    )
    deep = json.dumps(
        {"profile_id": nodes["cx.deepthink"]["profile_id"], "profile_args": nodes["cx.deepthink"]["profile_args"]},
        sort_keys=True,
    )
    assert standard != deep


def test_installation_registry_has_no_model_profiles():
    peers = _json("ai/peers.json")["peers"]
    assert all("model_profiles" not in peer for peer in peers.values())


def test_status_config_has_no_legacy_gate_command():
    text = (SYS / "ai" / "status_checks.json").read_text(encoding="utf-8")
    assert "gemini-status.bat" not in text
    assert "_sys/gemini/status.json" not in text


def test_model_status_uses_orchestration_profile_not_stale_health(monkeypatch, capsys):
    node = {
        "node_id": "cx",
        "enabled": True,
        "default_profile": "standard",
        "profiles": {
            "standard": {
                "model_id": "gpt-current",
                "reasoning_effort": "low",
                "cost_tier": "low",
                "runtime_context_window": 272000,
            }
        },
    }
    stale_health = {
        "profile": {
            "context_window": 128000,
            "cost_tier": "mid",
            "tier": "mid",
            "capabilities": ["code-review"],
        }
    }
    monkeypatch.setattr(hub, "_load_orchestration", lambda: {"hub_nodes": [node]})
    monkeypatch.setattr(
        hub,
        "_peer_effective_health",
        lambda _: ("GREEN", stale_health),
    )

    hub.action_model_status()

    output = capsys.readouterr().out
    assert "gpt-current" in output
    assert "272000" in output
    assert "128000" not in output


def test_transient_scan_detects_python_temp_probe(tmp_path, capsys):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    (tmp_path / "abcdefgh").write_bytes(b"blat")
    (tmp_path / "keepfile").write_bytes(b"data")

    hub.action_transient_scan(ai_root)

    output = capsys.readouterr().out
    assert "abcdefgh" in output
    assert "keepfile" not in output


def test_runtime_state_normalization_removes_disabled_and_retired_peers(
    tmp_path,
    monkeypatch,
):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    (ai_root / "state.json").write_text(
        json.dumps({
            "members": {"cc": "c1", "gc": "g1", "cc-deep": "d1"},
            "active_coordinator": "gc",
            "human_interface_peer": "gc",
            "leader": "gc",
            "leadership": {"peer": "gc", "status": "ACTIVE"},
            "role_assignments": {"reviewer": "gc", "coder": "cc"},
        }),
        encoding="utf-8",
    )
    (ai_root / "nodes.json").write_text(
        json.dumps({
            "version": "1",
            "nodes": {
                "cc": {"invoke": "old"},
                "gc": {"invoke": "old"},
                "cc-deep": {"invoke": "old"},
                "custom": {"invoke": "custom-cli"},
            },
        }),
        encoding="utf-8",
    )
    (ai_root / "leases.json").write_text(
        json.dumps({
            "cc-deep": {"status": "closed"},
            "cc": {"status": "closed"},
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        hub,
        "_runtime_node_policy",
        lambda: (
            {"cc", "cc.standard", "gc", "gc.standard"},
            {"cc"},
            {"cc-deep", "gc-plan"},
        ),
    )

    hub._normalize_runtime_files(ai_root)

    state = json.loads((ai_root / "state.json").read_text(encoding="utf-8"))
    nodes = json.loads((ai_root / "nodes.json").read_text(encoding="utf-8"))
    leases = json.loads((ai_root / "leases.json").read_text(encoding="utf-8"))
    assert state["members"] == {"cc": "c1"}
    assert state["active_coordinator"] is None
    assert state["human_interface_peer"] is None
    assert state["leader"] is None
    assert state["leadership"]["status"] == "VACANT"
    assert state["role_assignments"] == {"coder": {"peer": "cc"}}
    assert nodes == {
        "version": "2",
        "nodes": {"custom": {"invoke": "custom-cli"}},
    }
    assert leases == {"cc": {"status": "closed"}}


def test_active_governance_and_role_parity():
    orch = _json("ai/orchestration.json")
    active = {n["node_id"] for n in orch["hub_nodes"] if n.get("enabled") is not False}
    voters = set(orch["consensus"]["default_voters"])
    assert voters == active
    for peers in orch["roles_registry"].values():
        assert set(peers) == active


def test_no_runtime_health_or_status_files_tracked():
    tracked = subprocess.run(
        ["git", "ls-files", "_sys/*/health.json", "_sys/*/status.json", ".ai/*"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert tracked == []


def test_general_specific_docs_have_common_status_pattern():
    for peer_id in ("cc", "ag", "cx"):
        content = (SYS / "docs-v2" / "specific" / f"{peer_id}.md").read_text(
            encoding="utf-8"
        )
        for pattern in (
            "Status:",
            "Permission",
            "## Runtime Profiles",
            "## Context and Collaboration",
        ):
            assert pattern in content, f"{peer_id}.md missing common pattern: {pattern}"


def test_routing_microbenchmark_thresholds():
    result = benchmark_peer_routing.run(iterations=200)
    assert result["normalize_uncached"]["median_ms"] < 1.0
    assert result["normalize_cached"]["median_ms"] < 0.1
    # One sample checks all normalized nodes, so this threshold is per full tree.
    assert result["routability"]["median_ms"] < 5.0
    assert result["auto_profile"]["median_ms"] < 1.0
