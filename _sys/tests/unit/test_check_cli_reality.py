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
            {"node_id": "cc", "profiles": {"deepthink": {"model_id": "claude-opus-4-8"}}},
            {"node_id": "cx", "profiles": {}},
            {"node_id": "ag", "profiles": {"deepthink": {"runtime_model": "Gemini 3.1 Pro (High)"}}},
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

        orch = {"canary_config": {"budget_cap": 10, "budget_window_hours": 5.0}}
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        observed_file = ai_root / "cli-reality-observed.json"

        # Mock real binary paths
        monkeypatch.setattr(ccr, "REAL_BINARIES", {"ag": tmp_path / "ag.exe"})

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

        # Scenario 2: under 24h old AND hash unchanged -> no refresh (interval not yet expired)
        now_1h = now + 3600
        res = ccr.auto_refresh_observed(orch, ai_root, now_ts=now_1h)
        assert "interval not yet expired" in res["ag"]
        assert len(probes_called) == 0

        # Scenario 3: interval expired (>= 24h) AND hash unchanged -> skip probe (skipped, unchanged)
        now_25h = now + 25 * 3600
        res = ccr.auto_refresh_observed(orch, ai_root, now_ts=now_25h)
        assert "skipped, unchanged" in res["ag"]
        assert len(probes_called) == 0

        # Scenario 4: changed hash -> proceeds to probe, but budget exhausted
        def mock_fingerprint_v2(path):
            return {"sha256": "hash_v2"}
        monkeypatch.setattr(ccr, "fingerprint", mock_fingerprint_v2)
        budget_ok = False
        res = ccr.auto_refresh_observed(orch, ai_root, now_ts=now_25h)
        assert "budget exhausted" in res["ag"]
        assert len(probes_called) == 0

        # Scenario 5: changed hash, budget ok -> refreshed
        budget_ok = True
        res = ccr.auto_refresh_observed(orch, ai_root, now_ts=now_25h)
        assert res["ag"] == "refreshed"
        assert ["ag"] in probes_called
