"""
Unit and Integration Tests for Cluster C2 (ContextGate Capacity / Model-Resolution)

Covers:
  1. Pure resolver tests for all 5 live ag.* profiles + cc.*/cx.*
  2. Priority 1..4 resolution precedence (declared -> registry_id -> model_id match -> UnknownModelCapacityError)
  3. ag.gptoss -> context_window_kind="proven_lower_bound"
  4. CJK token formula regression (241,778 Hangul chars -> exactly 124,342 tokens)
  5. Fail-closed error handling (UnknownModelCapacityError, ContextGateConfigError)
  6. Real integration test proving subprocess.Popen is NEVER invoked when ContextGate rejects
"""

import json
from pathlib import Path
import subprocess
import sys
import pytest

SYS_DIR = Path(__file__).parent.parent.parent.resolve()
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

import core.hub as hub
import core.hub_context as hub_context


class TestContextTargetResolver:
    """Pure unit tests for resolve_context_target across live profiles."""

    def test_ag_standard_profile(self):
        target = hub_context.resolve_context_target("ag.standard")
        assert target.profile_id == "ag.standard"
        assert target.admission_limit == 1048576
        assert target.limit_basis == "profile_declared_limit"
        assert target.context_window_kind == "ceiling"

    def test_ag_effort_profile(self):
        target = hub_context.resolve_context_target("ag.effort")
        assert target.profile_id == "ag.effort"
        assert target.admission_limit == 1048576
        assert target.limit_basis == "profile_declared_limit"
        assert target.context_window_kind == "ceiling"

    def test_ag_deepthink_profile(self):
        target = hub_context.resolve_context_target("ag.deepthink")
        assert target.profile_id == "ag.deepthink"
        assert target.admission_limit == 1048576
        assert target.limit_basis == "profile_declared_limit"
        assert target.context_window_kind == "ceiling"

    def test_ag_opus_profile_priority_2(self):
        target = hub_context.resolve_context_target("ag.opus")
        assert target.profile_id == "ag.opus"
        assert target.admission_limit == 1000000
        assert target.limit_basis == "registry_model_id"
        assert target.registry_model_id == "claude-opus-4-6"
        assert target.context_window_kind == "ceiling"

    def test_ag_gptoss_profile_proven_lower_bound(self):
        target = hub_context.resolve_context_target("ag.gptoss")
        assert target.profile_id == "ag.gptoss"
        assert target.admission_limit == 8000
        assert target.limit_basis == "profile_declared_limit"
        assert target.context_window_kind == "proven_lower_bound"

    def test_cc_effort_profile(self):
        target = hub_context.resolve_context_target("cc.effort")
        assert target.profile_id == "cc.effort"
        assert target.admission_limit == 1000000
        assert target.limit_basis == "profile_declared_limit"
        assert target.context_window_kind == "ceiling"

    def test_cx_effort_profile(self):
        target = hub_context.resolve_context_target("cx.effort")
        assert target.profile_id == "cx.effort"
        assert target.admission_limit == 272000
        assert target.limit_basis == "profile_declared_limit"
        assert target.context_window_kind == "ceiling"


class TestCJKTokenFormula:
    """Regression test for CJK token estimation formula (Bug 2)."""

    def test_hangul_241778_chars_token_target(self):
        cjk_text = "안" * 241778
        estimated = hub_context.estimate_tokens(cjk_text)
        assert estimated == 124342, f"Expected 124342 tokens for 241,778 CJK chars, got {estimated}"


class TestFailClosedSchemaAndUnknownModel:
    """Unit tests for schema corruption and unknown model capacity fail-closed behavior."""

    def test_unknown_profile_raises_unknown_model_capacity_error(self):
        with pytest.raises(hub_context.UnknownModelCapacityError) as exc_info:
            hub_context.resolve_context_target("ag.nonexistent_profile_xyz")
        assert "ag.nonexistent_profile_xyz" in str(exc_info.value)
        assert exc_info.value.error_type == "UNKNOWN_MODEL_CAPACITY"

    def test_unknown_raw_model_slug_raises_unknown_model_capacity_error(self):
        with pytest.raises(hub_context.UnknownModelCapacityError):
            hub_context.resolve_context_target("unregistered-vendor-model-999")

    def test_corrupt_registry_json_raises_context_gate_config_error(self, tmp_path):
        bad_reg = tmp_path / "model-registry.json"
        bad_reg.write_text("{corrupt json", encoding="utf-8")
        with pytest.raises(hub_context.ContextGateConfigError) as exc_info:
            hub_context.ContextGate(registry_path=bad_reg)
        assert "JSON parse error" in str(exc_info.value)

    def test_non_numeric_context_limit_raises_context_gate_config_error(self, tmp_path):
        bad_reg = tmp_path / "model-registry.json"
        bad_reg.write_text(json.dumps({
            "models": {
                "bad-model": {"context_limit": "invalid_string_limit"}
            }
        }), encoding="utf-8")
        with pytest.raises(hub_context.ContextGateConfigError) as exc_info:
            hub_context.ContextGate(registry_path=bad_reg)
        assert "non-positive or non-integer" in str(exc_info.value)

    def test_fractional_context_limit_raises_context_gate_config_error(self, tmp_path):
        """Regression (ag cross-verification finding): a fractional context_limit
        like 0.5 must be rejected at config-load time, not silently truncated
        to int(0.5) == 0 downstream -- a 0-token admission limit would make
        every query to that model fail closed for a confusing reason instead
        of a clear config error."""
        bad_reg = tmp_path / "model-registry.json"
        bad_reg.write_text(json.dumps({
            "models": {
                "bad-model": {"context_limit": 0.5}
            }
        }), encoding="utf-8")
        with pytest.raises(hub_context.ContextGateConfigError) as exc_info:
            hub_context.ContextGate(registry_path=bad_reg)
        assert "non-positive or non-integer" in str(exc_info.value)


class TestContextGateDispatchIntegration:
    """Integration test proving subprocess.Popen is NEVER invoked when ContextGate rejects."""

    def test_action_ask_unknown_capacity_halts_before_subprocess_spawn(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        # Write state.json
        state = {
            "version": 1,
            "human_interface_peer": "cc",
            "active_console_peer": "cc",
        }
        (ai_root / "state.json").write_text(json.dumps(state), encoding="utf-8")

        def _forbidden_spawn(*args, **kwargs):
            raise AssertionError("FAIL: subprocess.Popen MUST NOT be invoked when ContextGate rejects dispatch!")

        monkeypatch.setattr(subprocess, "Popen", _forbidden_spawn)

        # Dispatch action_ask against an unknown unmapped model target
        with pytest.raises(SystemExit) as exc_info:
            hub.action_ask(
                to="unregistered_model_target_xyz",
                query="Hello test",
                query_file=None,
                timeout_sec=10,
                ai_root=ai_root,
                origin="terminal",
            )

        assert exc_info.value.code == 1

    def test_action_ask_context_limit_exceeded_halts_before_subprocess_spawn(self, monkeypatch, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()

        state = {
            "version": 1,
            "human_interface_peer": "cc",
            "active_console_peer": "cc",
        }
        (ai_root / "state.json").write_text(json.dumps(state), encoding="utf-8")

        def _forbidden_spawn(*args, **kwargs):
            raise AssertionError("FAIL: subprocess.Popen MUST NOT be invoked when ContextGate rejects dispatch!")

        monkeypatch.setattr(subprocess, "Popen", _forbidden_spawn)

        # Huge prompt exceeding ag.gptoss's 8,000 token limit
        oversized_query = "x " * 50000

        with pytest.raises(SystemExit) as exc_info:
            hub.action_ask(
                to="ag.gptoss",
                query=oversized_query,
                query_file=None,
                timeout_sec=10,
                ai_root=ai_root,
                origin="terminal",
            )

        assert exc_info.value.code == 1
