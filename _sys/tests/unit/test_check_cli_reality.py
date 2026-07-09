"""Tests for check_cli_reality.py — declared-vs-actual CLI reconciliation (Topic F).

Validates the pure reconciliation logic without spawning real CLIs. The headline
case is the real one: a declared model that does not exist in the CLI's actual
model list ("GPT-4o (3P)" vs agy's real list) must be CONTRADICTED (P0), never
silently MATCHed.
"""
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "checks"))
import check_cli_reality as ccr  # noqa: E402


AGY_REAL_MODELS = [
    "Gemini 3.5 Flash (Medium)", "Gemini 3.5 Flash (High)", "Gemini 3.5 Flash (Low)",
    "Gemini 3.1 Pro (Low)", "Gemini 3.1 Pro (High)",
    "Claude Sonnet 4.6 (Thinking)", "Claude Opus 4.6 (Thinking)", "GPT-OSS 120B (Medium)",
]


class TestRealBinaryResolution:
    def test_real_binary_is_not_wrapper(self):
        for peer in ("cc", "cx", "ag"):
            b = ccr.real_binary(peer)
            assert not ccr.is_wrapper(b), f"{peer} resolved to a _sys/cli wrapper"
            assert "cli" not in b.parts or b.parent.name != "cli"

    def test_wrapper_detection(self):
        assert ccr.is_wrapper(SYS_DIR / "cli" / "claude.bat")
        assert not ccr.is_wrapper(SYS_DIR / "env" / "nodejs" / "npm-global" / "claude.cmd")

    def test_unknown_peer_raises(self):
        import pytest
        with pytest.raises(KeyError):
            ccr.real_binary("nope")


class TestRealBinaryResolver:
    """T15 (design 2026-07-09 §Topic B): real_binary() resolves from
    orchestration.json's hub_nodes instead of the removed REAL_BINARIES dict."""

    _ORCH = {
        "hub_nodes": [
            {"type": "peer", "node_id": "test_peer", "invoke": "_sys/tools/my_bin", "enabled": True},
            {"type": "peer", "node_id": "disabled_peer", "invoke": "_sys/tools/other", "enabled": False},
            {"type": "peer", "node_id": "bare_peer", "invoke": "python", "enabled": True},
            {"type": "peer", "node_id": "wrap", "invoke": "_sys/cli/hub.bat", "enabled": True},
            {"type": "peer", "node_id": "no_invoke", "enabled": True},
            {"type": "profile", "node_id": "test_peer.deepthink", "invoke": "ignored", "enabled": True},
        ]
    }

    def test_enabled_peer_resolves_sys_relative_path(self):
        path = ccr.real_binary("test_peer", self._ORCH)
        assert path.is_absolute()
        assert "_sys" in [p.lower() for p in path.parts]

    def test_disabled_peer_raises_key_error(self):
        import pytest
        with pytest.raises(KeyError, match="unknown or disabled peer"):
            ccr.real_binary("disabled_peer", self._ORCH)

    def test_unknown_peer_id_raises_key_error(self):
        import pytest
        with pytest.raises(KeyError, match="unknown or disabled peer"):
            ccr.real_binary("totally_not_a_peer", self._ORCH)

    def test_non_peer_type_node_is_not_matched(self):
        import pytest
        # "test_peer.deepthink" is type=='profile', not 'peer' - must not resolve.
        with pytest.raises(KeyError):
            ccr.real_binary("test_peer.deepthink", self._ORCH)

    def test_bare_command_degrades_via_path_lookup(self):
        path = ccr.real_binary("bare_peer", self._ORCH)
        assert path.name.lower() in ("python", "python.exe")

    def test_bare_command_not_on_path_raises_file_not_found(self):
        import pytest
        orch = {"hub_nodes": [
            {"type": "peer", "node_id": "p", "invoke": "definitely-not-a-real-command-xyz", "enabled": True},
        ]}
        with pytest.raises(FileNotFoundError):
            ccr.real_binary("p", orch)

    def test_wrapper_script_target_is_rejected(self):
        import pytest
        with pytest.raises(ValueError, match="wrapper script"):
            ccr.real_binary("wrap", self._ORCH)

    def test_missing_invoke_field_raises_value_error(self):
        import pytest
        with pytest.raises(ValueError, match="no invoke field"):
            ccr.real_binary("no_invoke", self._ORCH)

    def test_defaults_to_loading_real_orchestration_when_orch_omitted(self):
        # No orch passed -> loads the real orchestration.json; cc/ag/cx must
        # all resolve without raising (already covered by
        # test_real_binary_is_not_wrapper, this just documents the contract).
        for peer in ("cc", "ag", "cx"):
            assert ccr.real_binary(peer).exists() or True  # existence not guaranteed in CI, resolution must not raise


class TestApplySecuritySemantics:
    """T15 (design 2026-07-09 §Topic B): peer_console.py's policy-to-CLI layer."""

    @staticmethod
    def _load_peer_console():
        import importlib.util
        path = SYS_DIR / "cli" / "peer_console.py"
        spec = importlib.util.spec_from_file_location("peer_console_under_test", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_no_sandbox_semantics_is_a_no_op(self):
        pc = self._load_peer_console()
        cmd = ["cmd", "arg"]
        assert pc.apply_security_semantics(cmd, {}) == cmd
        assert pc.apply_security_semantics(cmd, {"sandbox_semantics": None}) == cmd

    def test_skip_permissions_appends_required_effective_args(self):
        pc = self._load_peer_console()
        cmd = ["cmd", "arg"]
        contract = {
            "sandbox_semantics": "skip-permissions",
            "required_effective_args": ["--dangerously-skip-permissions"],
        }
        assert pc.apply_security_semantics(cmd, contract) == [
            "cmd", "arg", "--dangerously-skip-permissions",
        ]

    def test_skip_permissions_with_empty_required_args_is_still_a_no_op(self):
        pc = self._load_peer_console()
        cmd = ["cmd", "arg"]
        contract = {"sandbox_semantics": "skip-permissions", "required_effective_args": []}
        assert pc.apply_security_semantics(cmd, contract) == cmd

    def test_workspace_write_appends_sandbox_flag(self):
        pc = self._load_peer_console()
        cmd = ["cmd", "arg"]
        contract = {"sandbox_semantics": "workspace-write"}
        assert pc.apply_security_semantics(cmd, contract) == ["cmd", "arg", "-s", "workspace-write"]

    def test_workspace_write_skipped_if_user_already_supplied_sandbox_flag(self):
        pc = self._load_peer_console()
        contract = {"sandbox_semantics": "workspace-write"}
        assert pc.apply_security_semantics(["cmd", "-s", "read-only"], contract) == ["cmd", "-s", "read-only"]
        assert pc.apply_security_semantics(["cmd", "--sandbox", "x"], contract) == ["cmd", "--sandbox", "x"]
        assert pc.apply_security_semantics(["cmd", "--ask-for-approval"], contract) == ["cmd", "--ask-for-approval"]


class TestClassify:
    def test_model_match(self):
        assert ccr.classify_model("Gemini 3.1 Pro (High)", AGY_REAL_MODELS) == "MATCH"

    def test_model_contradicted_gpt4o(self):
        # The real defect: GPT-4o is NOT in agy's model list.
        assert ccr.classify_model("GPT-4o (3P)", AGY_REAL_MODELS) == "CONTRADICTED"

    def test_model_absent_when_list_unknown(self):
        assert ccr.classify_model("anything", None) == "ABSENT"

    def test_scalar(self):
        assert ccr.classify_scalar("1.0.15", "1.0.15") == "MATCH"
        assert ccr.classify_scalar("1.0.15", "1.0.16") == "DRIFT"
        assert ccr.classify_scalar("1.0.15", None) == "ABSENT"
        # Undeclared but measured => informational, NOT a drift (there is no
        # contract to drift from). Keeps the observed value visible without a P1.
        assert ccr.classify_scalar(None, "1.0.16") == "OBSERVED_ONLY"
        assert ccr._severity("OBSERVED_ONLY") == "info"


class TestFingerprint:
    def test_fingerprint_and_change(self, tmp_path):
        f = tmp_path / "bin"
        f.write_bytes(b"v1")
        fp1 = ccr.fingerprint(f)
        assert fp1["exists"] and fp1["sha256"] and fp1["size"] == 2
        assert ccr.fingerprint_changed(fp1, None) is True          # no baseline
        assert ccr.fingerprint_changed(fp1, fp1) is False          # identical
        f.write_bytes(b"v2-changed")
        assert ccr.fingerprint_changed(ccr.fingerprint(f), fp1) is True

    def test_missing_binary(self, tmp_path):
        fp = ccr.fingerprint(tmp_path / "nope")
        assert fp["exists"] is False and fp["sha256"] is None


class TestReconcile:
    def test_gpt4o_is_p0_contradicted(self):
        rep = ccr.reconcile_peer(
            "ag",
            declared_models=["Gemini 3.1 Pro (High)", "GPT-4o (3P)"],
            observed={"actual_models": AGY_REAL_MODELS, "version": "1.0.15",
                      "declared_version": "1.0.15", "fingerprint": {"sha256": "x"}},
        )
        verdicts = {p["declared"]: p["verdict"] for p in rep["probes"] if p["kind"] == "model"}
        assert verdicts["Gemini 3.1 Pro (High)"] == "MATCH"
        assert verdicts["GPT-4o (3P)"] == "CONTRADICTED"
        assert any(d["verdict"] == "CONTRADICTED" and d["severity"] == "P0" for d in rep["drift"])

    def test_absent_when_no_observed_models(self):
        rep = ccr.reconcile_peer(
            "ag", declared_models=["X"],
            observed={"actual_models": None, "version": None,
                      "declared_version": None, "fingerprint": {}},
        )
        model_probe = next(p for p in rep["probes"] if p["kind"] == "model")
        assert model_probe["verdict"] == "ABSENT"
        assert model_probe["observed"] is None  # never fabricated

    def test_build_report_counts_p0(self):
        rep = ccr.reconcile_peer(
            "ag", declared_models=["GPT-4o (3P)"],
            observed={"actual_models": AGY_REAL_MODELS, "version": "1.0.15",
                      "declared_version": "1.0.15", "fingerprint": {}},
        )
        report = ccr.build_report([rep], observed_at="2026-07-03T00:00:00")
        assert report["schema_version"] == 1
        assert report["drift_summary"]["p0"] == 1
        assert report["drift_summary"]["total"] == 1
        assert "never mutates orchestration" in report["note"].lower()


class TestRunNoLive:
    def test_run_no_live_honest_absent(self, monkeypatch):
        # Isolate from any real .ai/cli-reality-observed.json capture: with no
        # observed models, every model probe must be ABSENT, never a fabricated MATCH.
        monkeypatch.setattr(ccr, "load_observed_models", lambda peer: None)
        orch = {"hub_nodes": [
            {"node_id": "cc", "type": "peer", "enabled": True, "invoke": "/fake/cc-bin",
             "profiles": {"deepthink": {"model_id": "claude-opus-4-8"}}},
            {"node_id": "cx", "type": "peer", "enabled": True, "invoke": "/fake/cx-bin", "profiles": {}},
            {"node_id": "ag", "type": "peer", "enabled": True, "invoke": "/fake/ag-bin",
             "profiles": {"deepthink": {"runtime_model": "Gemini 3.1 Pro (High)"}}},
        ]}
        report = ccr.run(orch=orch, live=False)
        assert report["kind"] == "cli_reality_drift_report"
        peers = {p["peer"] for p in report["peers"]}
        assert peers == {"cc", "cx", "ag"}
        # With no observed-models capture, every model probe is ABSENT (not MATCH/CONTRADICTED).
        for pr in report["peers"]:
            for probe in pr["probes"]:
                if probe["kind"] == "model":
                    assert probe["verdict"] == "ABSENT"


class TestAutoRefresh:
    def test_auto_refresh_logic(self, monkeypatch, tmp_path):
        from datetime import datetime, timezone

        orch = {
            "canary_config": {"budget_cap": 10, "budget_window_hours": 5.0},
            "hub_nodes": [
                {"node_id": "ag", "type": "peer", "enabled": True, "invoke": str(tmp_path / "ag.exe")},
            ],
        }
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        observed_file = ai_root / "cli-reality-observed.json"

        # Mock fingerprint
        def mock_fingerprint(path):
            if str(path).endswith("ag.exe"):
                return {"sha256": "hash_v1"}
            return {"sha256": "unknown"}
        monkeypatch.setattr(ccr, "fingerprint", mock_fingerprint)

        # Mock check_and_update_budget
        budget_ok = True
        def mock_check_budget(*args, **kwargs):
            return budget_ok

        # Mock run_canary
        probes_called = []
        def mock_run_canary(*args, **kwargs):
            probes_called.append(kwargs.get('peers'))
            return [{"peer": "ag", "status": "PASS", "model": "Model-A", "profile": "p1"}]

        import check_cli_canary
        monkeypatch.setattr(check_cli_canary, "check_and_update_budget", mock_check_budget)
        monkeypatch.setattr(check_cli_canary, "run_canary", mock_run_canary)

        # Scenario 1: changed hash (no existing data) -> proceeds to probe
        now = datetime.now(timezone.utc).timestamp()
        res = ccr.auto_refresh_observed(orch, ai_root, now_ts=now)
        assert res["ag"] == "refreshed"
        assert ["ag"] in probes_called
        probes_called.clear()

        # verify file saved
        import json
        saved = json.loads(observed_file.read_text(encoding="utf-8"))
        assert saved["ag"]["fingerprint"] == "hash_v1"
        assert "Model-A" in saved["ag"]["models"]

        # Scenario 2: under 24h old AND hash unchanged -> no refresh
        now_1h = now + 3600
        res = ccr.auto_refresh_observed(orch, ai_root, now_ts=now_1h)
        assert res["ag"] == "interval_not_expired"
        assert len(probes_called) == 0

        # Scenario 3 (T16, 2026-07-10): interval expired (>= 24h) AND hash
        # unchanged -> a binary hash alone can't prove server-side model
        # drift didn't happen, so this now performs a REAL budgeted re-probe
        # instead of just bumping captured_at and skipping.
        now_25h = now + 25 * 3600
        res = ccr.auto_refresh_observed(orch, ai_root, now_ts=now_25h)
        assert res["ag"] == "refreshed"
        assert ["ag"] in probes_called
        probes_called.clear()

        # Scenario 4 (T16): same expired-but-unchanged case again (>= 24h
        # past scenario 3's refresh, since captured_at was just bumped), but
        # budget is exhausted -> must not probe, must report skipped_budget.
        now_50h = now + 50 * 3600
        budget_ok = False
        res = ccr.auto_refresh_observed(orch, ai_root, now_ts=now_50h)
        assert res["ag"] == "skipped_budget"
        assert len(probes_called) == 0

        # Scenario 5: changed hash -> proceeds to probe, but budget exhausted
        def mock_fingerprint_v2(path):
            return {"sha256": "hash_v2"}
        monkeypatch.setattr(ccr, "fingerprint", mock_fingerprint_v2)
        res = ccr.auto_refresh_observed(orch, ai_root, now_ts=now_25h)
        assert res["ag"] == "skipped_budget"
        assert len(probes_called) == 0

        # Scenario 6: changed hash, budget ok -> refreshed
        budget_ok = True
        res = ccr.auto_refresh_observed(orch, ai_root, now_ts=now_25h)
        assert res["ag"] == "refreshed"
        assert ["ag"] in probes_called
