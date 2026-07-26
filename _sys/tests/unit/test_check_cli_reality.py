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
            boundary = ccr.real_binary(peer)
            assert boundary.status == ccr.BOUNDARY_BINARY_PRESENT
            assert boundary.launcher_path is not None
            assert boundary.fingerprint_path is not None
            assert not ccr.is_wrapper(boundary), f"{peer} resolved to a _sys/cli wrapper"
            assert (
                "cli" not in boundary.launcher_path.parts
                or boundary.launcher_path.parent.name != "cli"
            )

    def test_wrapper_detection(self):
        assert ccr.is_wrapper(SYS_DIR / "cli" / "claude.bat")
        assert not ccr.is_wrapper(SYS_DIR / "env" / "nodejs" / "npm-global" / "claude.cmd")

    def test_unknown_peer_is_structured(self):
        boundary = ccr.real_binary("nope")
        assert boundary.status == ccr.BOUNDARY_UNKNOWN_OR_DISABLED
        assert not boundary.binary_present


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

    def test_missing_configured_sys_relative_path_is_structured(self):
        boundary = ccr.real_binary("test_peer", self._ORCH)
        assert boundary.status == ccr.BOUNDARY_MISSING_CONFIGURED_PATH
        assert boundary.launcher_path is not None
        assert boundary.launcher_path.is_absolute()
        assert "_sys" in [p.lower() for p in boundary.launcher_path.parts]

    def test_disabled_peer_is_structured(self):
        boundary = ccr.real_binary("disabled_peer", self._ORCH)
        assert boundary.status == ccr.BOUNDARY_UNKNOWN_OR_DISABLED

    def test_unknown_peer_id_is_structured(self):
        boundary = ccr.real_binary("totally_not_a_peer", self._ORCH)
        assert boundary.status == ccr.BOUNDARY_UNKNOWN_OR_DISABLED

    def test_non_peer_type_node_is_not_matched(self):
        boundary = ccr.real_binary("test_peer.deepthink", self._ORCH)
        assert boundary.status == ccr.BOUNDARY_UNKNOWN_OR_DISABLED

    def test_bare_command_degrades_via_path_lookup(self):
        boundary = ccr.real_binary("bare_peer", self._ORCH)
        assert boundary.status == ccr.BOUNDARY_BINARY_PRESENT
        assert boundary.launcher_path.name.lower() in ("python", "python.exe")

    def test_bare_command_not_on_path_is_structured(self):
        orch = {"hub_nodes": [
            {"type": "peer", "node_id": "p", "invoke": "definitely-not-a-real-command-xyz", "enabled": True},
        ]}
        boundary = ccr.real_binary("p", orch)
        assert boundary.status == ccr.BOUNDARY_BARE_COMMAND_ABSENT

    def test_wrapper_script_target_is_structured(self):
        boundary = ccr.real_binary("wrap", self._ORCH)
        assert boundary.status == ccr.BOUNDARY_WRAPPER_REJECTED

    def test_missing_invoke_field_is_structured(self):
        boundary = ccr.real_binary("no_invoke", self._ORCH)
        assert boundary.status == ccr.BOUNDARY_MISSING_CONFIGURED_PATH

    def test_defaults_to_loading_real_orchestration_when_orch_omitted(self):
        # No orch passed -> loads the real orchestration.json; cc/ag/cx must
        # all resolve without raising (already covered by
        # test_real_binary_is_not_wrapper, this just documents the contract).
        for peer in ("cc", "ag", "cx"):
            assert ccr.real_binary(peer).status == ccr.BOUNDARY_BINARY_PRESENT


class TestApplySecuritySemantics:
    """T15 (design 2026-07-09 §Topic B): peer_console.py's policy-to-CLI layer."""

    @staticmethod
    def _load_peer_console():
        import importlib.util
        import sys
        path = SYS_DIR / "cli" / "peer_console.py"
        spec = importlib.util.spec_from_file_location("peer_console_under_test", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["peer_console_under_test"] = module
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
        assert ccr.classify_model("anything", None) == "UNMEASURED"

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

    def test_unmeasured_when_no_observed_models(self):
        rep = ccr.reconcile_peer(
            "ag", declared_models=["X"],
            observed={"actual_models": None, "version": None,
                      "declared_version": None, "fingerprint": {}},
        )
        model_probe = next(p for p in rep["probes"] if p["kind"] == "model")
        assert model_probe["verdict"] == "UNMEASURED"
        assert model_probe["observed"] is None  # never fabricated

    def test_build_report_counts_p0(self):
        rep = ccr.reconcile_peer(
            "ag", declared_models=["GPT-4o (3P)"],
            observed={"actual_models": AGY_REAL_MODELS, "version": "1.0.15",
                      "declared_version": "1.0.15", "fingerprint": {}},
        )
        report = ccr.build_report([rep], observed_at="2026-07-03T00:00:00")
        assert report["schema_version"] == 2
        assert report["drift_summary"]["p0"] == 1
        assert report["drift_summary"]["total"] == 1
        assert "never mutates orchestration" in report["note"].lower()


class TestRunNoLive:
    def test_run_no_live_honest_unmeasured(self, tmp_path):
        # Isolate from any real .ai/cli-reality-observed.json capture: with no
        # observed models, every model probe must be ABSENT, never a fabricated MATCH.
        orch = {"hub_nodes": [
            {"node_id": "cc", "type": "peer", "enabled": True, "invoke": "/fake/cc-bin",
             "profiles": {"deepthink": {"model_id": "claude-opus-4-8"}}},
            {"node_id": "cx", "type": "peer", "enabled": True, "invoke": "/fake/cx-bin", "profiles": {}},
            {"node_id": "ag", "type": "peer", "enabled": True, "invoke": "/fake/ag-bin",
             "profiles": {"deepthink": {"runtime_model": "Gemini 3.1 Pro (High)"}}},
        ]}
        report = ccr.run(orch=orch, live=False, ai_root=tmp_path)
        assert report["kind"] == "cli_reality_drift_report"
        peers = {p["peer"] for p in report["peers"]}
        assert peers == {"cc", "cx", "ag"}
        # With no observation entry, every model probe is UNMEASURED.
        for pr in report["peers"]:
            for probe in pr["probes"]:
                if probe["kind"] == "model":
                    assert probe["verdict"] == "UNMEASURED"


class TestAutoRefresh:
    def test_auto_refresh_logic(self, monkeypatch, tmp_path):
        # 2026-07-20: check_and_update_budget() is a deprecated shim that
        # always returns False -- auto_refresh_observed() no longer gates on
        # it (that was the actual bug: every refresh silently skipped
        # forever). Real budget denial now flows through run_canary()'s own
        # per-profile canary_budget reservation, expressed here as SKIP
        # verdicts, matching production behavior exactly.
        from datetime import datetime, timezone

        orch = {
            "canary_config": {"budget_cap": 10, "budget_window_hours": 5.0},
            "hub_nodes": [
                {"node_id": "ag", "type": "peer", "enabled": True, "invoke": str(tmp_path / "ag.exe")},
            ],
        }
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (tmp_path / "ag.exe").write_bytes(b"stub")
        observed_file = ai_root / "cli-reality-observed.json"

        # Mock fingerprint
        def mock_fingerprint(path):
            return {"sha256": "hash_v1"}
        monkeypatch.setattr(ccr, "fingerprint", mock_fingerprint)
        monkeypatch.setattr(ccr, "probe_enumerated_models", lambda peer, orch, timeout=20: None)

        # Mock run_canary: budget_ok toggles between real PASS verdicts and
        # the SKIP verdicts run_canary itself returns on a real budget denial.
        budget_ok = True
        probes_called = []

        def mock_run_canary(*args, **kwargs):
            probes_called.append(kwargs.get('peers'))
            if budget_ok:
                return [{"peer": "ag", "status": "PASS", "model": "Model-A", "profile": "p1"}]
            return [{"peer": "ag", "profile": "p1", "status": "SKIP", "reason": "budget"}]

        import check_cli_canary
        monkeypatch.setattr(check_cli_canary, "run_canary", mock_run_canary)

        # Scenario 1: changed hash (no existing data) -> proceeds to probe
        now = datetime.now(timezone.utc).timestamp()
        res = ccr.auto_refresh_observed(orch, ai_root=ai_root, now_ts=now)
        assert res["ag"] == "refreshed"
        assert ["ag"] in probes_called
        probes_called.clear()

        # verify file saved
        import json
        saved = json.loads(observed_file.read_text(encoding="utf-8"))
        assert saved["schema_version"] == 2
        assert saved["kind"] == ccr.OBSERVATION_STORE_KIND
        assert saved["peers"]["ag"]["binary"]["fingerprint"]["sha256"] == "hash_v1"
        assert "Model-A" in saved["peers"]["ag"]["models"]
        assert (
            saved["peers"]["ag"]["evidence_completeness"]
            == ccr.EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY
        )

        # Scenario 2: under 24h old AND hash unchanged -> no refresh
        now_1h = now + 3600
        res = ccr.auto_refresh_observed(orch, ai_root=ai_root, now_ts=now_1h)
        assert res["ag"] == "interval_not_expired"
        assert len(probes_called) == 0

        # Scenario 3 (T16, 2026-07-10): interval expired (>= 24h) AND hash
        # unchanged -> a binary hash alone can't prove server-side model
        # drift didn't happen, so this now performs a REAL budgeted re-probe
        # instead of just bumping captured_at and skipping.
        now_25h = now + 25 * 3600
        res = ccr.auto_refresh_observed(orch, ai_root=ai_root, now_ts=now_25h)
        assert res["ag"] == "refreshed"
        assert ["ag"] in probes_called
        probes_called.clear()

        # Scenario 4 (T16): same expired-but-unchanged case again (>= 24h
        # past scenario 3's refresh, since captured_at was just bumped), but
        # the real budget ledger denies (run_canary returns all-SKIP) ->
        # must report the real denial reason, not silently succeed.
        now_50h = now + 50 * 3600
        budget_ok = False
        res = ccr.auto_refresh_observed(orch, ai_root=ai_root, now_ts=now_50h)
        assert res["ag"] == "skipped_budget"
        assert ["ag"] in probes_called
        probes_called.clear()

        # Scenario 5: changed hash -> proceeds to probe, but budget exhausted
        def mock_fingerprint_v2(path):
            return {"sha256": "hash_v2"}
        monkeypatch.setattr(ccr, "fingerprint", mock_fingerprint_v2)
        res = ccr.auto_refresh_observed(orch, ai_root=ai_root, now_ts=now_25h)
        assert res["ag"] == "skipped_budget"
        assert ["ag"] in probes_called
        probes_called.clear()

        # Scenario 6: changed hash, budget ok -> refreshed
        budget_ok = True
        res = ccr.auto_refresh_observed(orch, ai_root=ai_root, now_ts=now_25h)
        assert res["ag"] == "refreshed"
        assert ["ag"] in probes_called

    def test_auto_refresh_never_calls_deprecated_budget_shim(self, monkeypatch, tmp_path):
        # Regression: the old gate called check_and_update_budget(), which
        # always returns False, silently skipping every refresh forever.
        # Assert the deprecated shim is never even invoked anymore.
        from datetime import datetime, timezone

        orch = {
            "canary_config": {"budget_cap": 10, "budget_window_hours": 5.0},
            "hub_nodes": [
                {"node_id": "ag", "type": "peer", "enabled": True, "invoke": str(tmp_path / "ag.exe")},
            ],
        }
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (tmp_path / "ag.exe").write_bytes(b"stub")
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "hash_v1"})
        monkeypatch.setattr(ccr, "probe_enumerated_models", lambda peer, orch, timeout=20: None)

        import check_cli_canary

        def fail_if_called(*_a, **_k):
            raise AssertionError("check_and_update_budget must not be called anymore")
        monkeypatch.setattr(check_cli_canary, "check_and_update_budget", fail_if_called)
        monkeypatch.setattr(
            check_cli_canary, "run_canary",
            lambda *a, **k: [{"peer": "ag", "status": "PASS", "model": "Model-A", "profile": "p1"}])

        now = datetime.now(timezone.utc).timestamp()
        res = ccr.auto_refresh_observed(orch, ai_root=ai_root, now_ts=now)
        assert res["ag"] == "refreshed"

    def test_auto_refresh_skip_reason_reflects_real_denial_kind(self, monkeypatch, tmp_path):
        from datetime import datetime, timezone

        orch = {"hub_nodes": [
            {"node_id": "ag", "type": "peer", "enabled": True, "invoke": str(tmp_path / "ag.exe")},
        ]}
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (tmp_path / "ag.exe").write_bytes(b"stub")
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "hash_v1"})
        monkeypatch.setattr(ccr, "probe_enumerated_models", lambda peer, orch, timeout=20: None)

        import check_cli_canary
        monkeypatch.setattr(
            check_cli_canary, "run_canary",
            lambda *a, **k: [{"peer": "ag", "profile": "p1", "status": "SKIP", "reason": "quota_absent"}])

        now = datetime.now(timezone.utc).timestamp()
        res = ccr.auto_refresh_observed(orch, ai_root=ai_root, now_ts=now)
        assert res["ag"] == "skipped_quota_absent"

    def test_auto_refresh_uses_enumerated_catalog_when_available(self, monkeypatch, tmp_path):
        from datetime import datetime, timezone

        orch = {"hub_nodes": [
            {"node_id": "ag", "type": "peer", "enabled": True, "invoke": str(tmp_path / "ag.exe"),
             "model_enumeration_argv": ["models"]},
        ]}
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        (tmp_path / "ag.exe").write_bytes(b"stub")
        observed_file = ai_root / "cli-reality-observed.json"
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "hash_v1"})

        import check_cli_canary
        monkeypatch.setattr(
            check_cli_canary, "run_canary",
            lambda *a, **k: [{"peer": "ag", "status": "PASS", "model": "Confirmed-Model", "profile": "p1"}])
        monkeypatch.setattr(
            ccr, "probe_enumerated_models",
            lambda peer, orch, timeout=20: ["Real-Model-A", "Real-Model-B"])

        now = datetime.now(timezone.utc).timestamp()
        res = ccr.auto_refresh_observed(orch, ai_root=ai_root, now_ts=now)
        assert res["ag"] == "refreshed"

        import json
        saved = json.loads(observed_file.read_text(encoding="utf-8"))
        assert saved["peers"]["ag"]["catalog_models"] == ["Real-Model-A", "Real-Model-B"]
        assert (
            saved["peers"]["ag"]["evidence_completeness"]
            == ccr.EVIDENCE_COMPLETE_CATALOG
        )


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


class TestProbeEnumeratedModels:
    """agy.exe has a real `models` subcommand (see AGY_REAL_MODELS -- a live
    capture at the top of this file); cc/cx have no equivalent and both treat
    an unmatched bare argument as a live prompt, so enumeration must be
    strictly opt-in via a declared model_enumeration_argv, never attempted
    on a peer that hasn't declared one."""

    def test_no_declared_argv_returns_none_without_any_subprocess_call(self, monkeypatch, tmp_path):
        orch = {"hub_nodes": [
            {"node_id": "cc", "type": "peer", "enabled": True, "invoke": str(tmp_path / "cc.exe")},
        ]}

        def fail_if_called(*_a, **_k):
            raise AssertionError("must not invoke subprocess for a peer with no declared argv")
        monkeypatch.setattr(ccr.subprocess, "run", fail_if_called)

        assert ccr.probe_enumerated_models("cc", orch) is None

    def test_declared_argv_parses_stdout_lines(self, monkeypatch, tmp_path):
        bin_path = tmp_path / "ag.exe"
        bin_path.write_text("stub", encoding="utf-8")
        orch = {"hub_nodes": [
            {"node_id": "ag", "type": "peer", "enabled": True, "invoke": str(bin_path),
             "model_enumeration_argv": ["models"]},
        ]}
        captured_argv = []

        def fake_run(argv, capture_output=None, text=None, timeout=None):
            captured_argv.extend(argv)
            return _FakeCompletedProcess(returncode=0, stdout="\n".join(AGY_REAL_MODELS) + "\n")
        monkeypatch.setattr(ccr.subprocess, "run", fake_run)

        result = ccr.probe_enumerated_models("ag", orch)
        assert set(result) == set(AGY_REAL_MODELS)
        assert captured_argv == [str(bin_path), "models"]

    def test_nonzero_exit_returns_none(self, monkeypatch, tmp_path):
        bin_path = tmp_path / "ag.exe"
        bin_path.write_text("stub", encoding="utf-8")
        orch = {"hub_nodes": [
            {"node_id": "ag", "type": "peer", "enabled": True, "invoke": str(bin_path),
             "model_enumeration_argv": ["models"]},
        ]}
        monkeypatch.setattr(
            ccr.subprocess, "run",
            lambda *a, **k: _FakeCompletedProcess(returncode=1, stdout=""))
        assert ccr.probe_enumerated_models("ag", orch) is None

    def test_empty_stdout_returns_none(self, monkeypatch, tmp_path):
        bin_path = tmp_path / "ag.exe"
        bin_path.write_text("stub", encoding="utf-8")
        orch = {"hub_nodes": [
            {"node_id": "ag", "type": "peer", "enabled": True, "invoke": str(bin_path),
             "model_enumeration_argv": ["models"]},
        ]}
        monkeypatch.setattr(
            ccr.subprocess, "run",
            lambda *a, **k: _FakeCompletedProcess(returncode=0, stdout="   \n\n"))
        assert ccr.probe_enumerated_models("ag", orch) is None

    def test_subprocess_failure_returns_none(self, monkeypatch, tmp_path):
        bin_path = tmp_path / "ag.exe"
        bin_path.write_text("stub", encoding="utf-8")
        orch = {"hub_nodes": [
            {"node_id": "ag", "type": "peer", "enabled": True, "invoke": str(bin_path),
             "model_enumeration_argv": ["models"]},
        ]}

        def raise_timeout(*_a, **_k):
            raise ccr.subprocess.TimeoutExpired(cmd="ag.exe", timeout=20)
        monkeypatch.setattr(ccr.subprocess, "run", raise_timeout)
        assert ccr.probe_enumerated_models("ag", orch) is None

    def test_missing_binary_returns_none_without_subprocess_call(self, monkeypatch, tmp_path):
        orch = {"hub_nodes": [
            {"node_id": "ag", "type": "peer", "enabled": True, "invoke": str(tmp_path / "does_not_exist.exe"),
             "model_enumeration_argv": ["models"]},
        ]}

        def fail_if_called(*_a, **_k):
            raise AssertionError("must not invoke subprocess for a nonexistent binary")
        monkeypatch.setattr(ccr.subprocess, "run", fail_if_called)
        assert ccr.probe_enumerated_models("ag", orch) is None
