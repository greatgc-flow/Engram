"""T44c real-invoker wiring contracts; all native process calls are mocked."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "checks"))
import check_capability_core as core


ORCH = {"hub_nodes": [{"node_id": "cc", "type": "peer", "profiles": {
    "standard": {"cost_tier": "low", "quota_families": ["C"]},
    "deepthink": {"cost_tier": "high", "quota_families": ["C"]},
}}]}
FP = {"peer": "cc", "profile": "standard", "model_id": "m", "reasoning_effort": "low", "adapter": "x", "invoke_args": [], "profile_config_sha256": "a" * 64, "binary": {"exists": True, "sha256": "b" * 64}}
BUDGET = {"cap": 3, "window_hours": 5.0, "reserve_floor": .25}
QUOTA = {"source_tag": "cli_live", "remaining": .5}


def _perfect(workspace, fixture):
    (workspace / "reasoning_answers.json").write_text(json.dumps(fixture["reasoning_answers"]), encoding="utf-8")
    (workspace / "code" / "buggy_normalizer.py").write_text(fixture["expected_code"], encoding="utf-8")
    agentic = workspace / "agentic"
    for rel, data in fixture["agentic_fixture"]["expected_bytes"].items():
        path = agentic / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    (agentic / "failure_report.json").write_text(json.dumps({"target": "impossible_target_dir", "status": "failed"}), encoding="utf-8")
    return {}


def test_core_prompt_names_reasoning_code_agentic_and_workspace(tmp_path):
    fixture = core.prepare_core_fixture(tmp_path)
    prompt = core.build_capability_core_prompt(fixture, tmp_path)
    for key in ("sum_17_25", "product_7_8", "difference_100_37", "quotient_144_12", "reasoning_answers.json", "code/buggy_normalizer.py", "agentic"):
        assert key in prompt
    assert "workspace" in prompt.lower() and "only" in prompt.lower()


def test_mocked_perfect_invoker_yields_max_axes_and_record(tmp_path):
    result = core.run_capability_core(peer="cc", profile="standard", orch=ORCH, ai_root=tmp_path / "ai", workspace=tmp_path / "work", invoker=_perfect, runtime_fingerprint=FP, budget=BUDGET, quota=QUOTA, records_path=tmp_path / "records.jsonl")
    assert result["axis_scores"] == {"reasoning_correctness": 100, "code_fidelity": 100, "agentic_reliability": 100}
    assert (tmp_path / "records.jsonl").exists()


def test_mocked_wrong_answer_scores_partial(tmp_path):
    def wrong(workspace, fixture):
        _perfect(workspace, fixture)
        (workspace / "reasoning_answers.json").write_text(json.dumps({key: "0" for key in fixture["reasoning_answers"]}), encoding="utf-8")
        return {}
    result = core.run_capability_core(peer="cc", profile="standard", orch=ORCH, ai_root=tmp_path / "ai", workspace=tmp_path / "work", invoker=wrong, runtime_fingerprint=FP, budget=BUDGET, quota=QUOTA)
    assert result["axis_scores"]["reasoning_correctness"] == 0


def test_default_core_invoker_calls_native_driver_with_built_prompt(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(core, "invoke_peer_native_write", lambda peer, profile, prompt, workspace, orch, timeout: called.update({"peer": peer, "profile": profile, "prompt": prompt, "workspace": workspace}) or type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    fixture = core.prepare_core_fixture(tmp_path)
    result = core.default_core_invoker("cc", "standard", ORCH, timeout=12)(tmp_path, fixture)
    assert called["peer"] == "cc" and called["profile"] == "standard"
    assert "reasoning_answers.json" in called["prompt"]
    assert result["returncode"] == 0


def test_cli_execute_without_budget_flags_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "_load_orchestration", lambda _: ORCH)
    monkeypatch.setattr(core, "resolve_runtime_fingerprint", lambda *args: FP)
    monkeypatch.setattr(core, "_canary_quota", lambda *args: QUOTA)
    assert core.main(["--peer", "cc.standard", "--execute", "--artifact-root", str(tmp_path)]) == 2


def test_cli_premium_without_allowlist_denied(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "_load_orchestration", lambda _: ORCH)
    monkeypatch.setattr(core, "resolve_runtime_fingerprint", lambda *args: FP)
    monkeypatch.setattr(core, "_canary_quota", lambda *args: QUOTA)
    assert core.main(["--peer", "cc.deepthink", "--execute", "--budget-cap", "1", "--budget-window", "5", "--reserve-floor", ".25", "--artifact-root", str(tmp_path)]) == 2


def test_cli_dry_run_writes_nothing(tmp_path):
    assert core.main(["--peer", "cc.standard", "--artifact-root", str(tmp_path)]) == 0
    assert list(tmp_path.iterdir()) == []
