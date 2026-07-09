"""_sys/tests/unit/test_cli_canary.py — Unit tests for check_cli_canary.py"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SYS_DIR / "checks"))
import check_cli_canary as ccc  # noqa: E402
import check_cli_reality as ccr  # noqa: E402

MOCK_ORCHESTRATION = {
    "canary_config": {
        "budget_cap": 2,
        "budget_window_hours": 5.0
    },
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
                    "profile_args": ["--model", "claude-haiku"]
                },
                "effort": {
                    "model_id": "claude-sonnet",
                    "cost_tier": "mid",
                    "routing_state": "eligible",
                    "profile_args": ["--model", "claude-sonnet"]
                },
                "deepthink": {
                    "model_id": "claude-opus",
                    "cost_tier": "high",
                    "routing_state": "eligible",
                    "profile_args": ["--model", "claude-opus"]
                }
            }
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
                    "profile_args": ["--model", "gemini-flash"]
                },
                "deepthink": {
                    "runtime_model": "gemini-pro",
                    "cost_tier": "high",
                    "routing_state": "eligible",
                    "profile_args": ["--model", "gemini-pro"]
                }
            }
        },
        {
            "node_id": "cx",
            "type": "peer",
            "enabled": False,
            "profiles": {
                "standard": {
                    "model_id": "gpt-mini",
                    "cost_tier": "low",
                    "routing_state": "eligible"
                }
            }
        }
    ]
}


class TestCheapestProfile:
    def test_cheapest_profile(self):
        cc_node = MOCK_ORCHESTRATION["hub_nodes"][0]
        assert ccc._cheapest_profile(cc_node) == "standard"

        import copy
        cc_blocked = copy.deepcopy(cc_node)
        cc_blocked["profiles"]["standard"]["routing_state"] = "blocked"
        assert ccc._cheapest_profile(cc_blocked) == "effort"
        
        cc_blocked["profiles"]["effort"]["routing_state"] = "blocked"
        cc_blocked["profiles"]["deepthink"]["routing_state"] = "blocked"
        assert ccc._cheapest_profile(cc_blocked) is None


class TestCanaryProbe:
    def test_canary_probe_success(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")
        
        invoker_called = []
        def mock_invoker(peer, profile, model, prompt):
            invoker_called.append((peer, profile, model, prompt))
            return "OK"
            
        verdict = ccc.canary_probe(
            peer="cc",
            profile_name="standard",
            orch=MOCK_ORCHESTRATION,
            invoker=mock_invoker,
            force=True,
            ai_root=tmp_path
        )
        
        assert verdict["status"] == "PASS"
        assert verdict["stage"] == "reply"
        assert verdict["model"] == "claude-haiku"
        assert verdict["reply"] == "OK"
        assert len(invoker_called) == 1
        assert invoker_called[0] == ("cc", "standard", "claude-haiku", "Respond with exactly: OK")

    def test_canary_probe_reply_fail(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")
        
        def mock_invoker(peer, profile, model, prompt):
            return "NOPE"
            
        verdict = ccc.canary_probe(
            peer="cc",
            profile_name="standard",
            orch=MOCK_ORCHESTRATION,
            invoker=mock_invoker,
            force=True,
            ai_root=tmp_path
        )
        
        assert verdict["status"] == "FAIL"
        assert verdict["stage"] == "reply"
        assert verdict["reply"] == "NOPE"

    def test_canary_probe_reply_negation_is_fail(self, monkeypatch, tmp_path):
        # Regression: a substring "OK" test false-PASSes replies like "NOT OK".
        # The assertion must be an exact normalized match (prompt demands "OK").
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")

        for bad_reply in ("NOT OK", "OK but failed", "not ok"):
            def mock_invoker(peer, profile, model, prompt, _r=bad_reply):
                return _r

            verdict = ccc.canary_probe(
                peer="cc",
                profile_name="standard",
                orch=MOCK_ORCHESTRATION,
                invoker=mock_invoker,
                force=True,
                ai_root=tmp_path,
                bypass_budget=True,
            )
            assert verdict["status"] == "FAIL", f"{bad_reply!r} must not PASS"
            assert verdict["stage"] == "reply"

    def test_canary_probe_reply_normalized_ok(self, monkeypatch, tmp_path):
        # Whitespace/newline-wrapped and lower-case exact "OK" still PASS.
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")

        for good_reply in ("OK", " OK\n", "ok", "\tOK  "):
            def mock_invoker(peer, profile, model, prompt, _r=good_reply):
                return _r

            verdict = ccc.canary_probe(
                peer="cc",
                profile_name="standard",
                orch=MOCK_ORCHESTRATION,
                invoker=mock_invoker,
                force=True,
                ai_root=tmp_path,
                bypass_budget=True,
            )
            assert verdict["status"] == "PASS", f"{good_reply!r} must PASS"

    def test_canary_probe_launch_fail(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")
        
        def mock_invoker(peer, profile, model, prompt):
            raise RuntimeError("failed to launch binary")
            
        verdict = ccc.canary_probe(
            peer="cc",
            profile_name="standard",
            orch=MOCK_ORCHESTRATION,
            invoker=mock_invoker,
            force=True,
            ai_root=tmp_path
        )
        
        assert verdict["status"] == "FAIL"
        assert verdict["stage"] == "launch"
        assert "failed to launch binary" in verdict["detail"]

    def test_canary_probe_operand_drift(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")
        
        monkeypatch.setattr(ccc, "validate_model_operand", lambda node: "mocked operand drift error")
        
        invoker_called = False
        def mock_invoker(peer, profile, model, prompt):
            nonlocal invoker_called
            invoker_called = True
            return "OK"
            
        verdict = ccc.canary_probe(
            peer="cc",
            profile_name="standard",
            orch=MOCK_ORCHESTRATION,
            invoker=mock_invoker,
            force=True,
            ai_root=tmp_path
        )
        
        assert verdict["status"] == "FAIL"
        assert verdict["stage"] == "operand_validation"
        assert verdict["detail"] == "mocked operand drift error"
        assert not invoker_called


class TestBudgetAndCache:
    def test_canary_probe_budget(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")
        
        def mock_invoker(peer, profile, model, prompt):
            return "OK"
            
        budget_file = tmp_path / "canary_budget.json"
        now_ts = datetime.now(timezone.utc).timestamp()
        budget_file.write_text(json.dumps([now_ts - 100, now_ts - 50]), encoding="utf-8")
        
        verdict = ccc.canary_probe(
            peer="cc",
            profile_name="standard",
            orch=MOCK_ORCHESTRATION,
            invoker=mock_invoker,
            force=True,
            ai_root=tmp_path
        )
        
        assert verdict["status"] == "SKIP"
        assert verdict["reason"] == "budget"

    def test_canary_probe_cache(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")
        
        invoker_count = 0
        def mock_invoker(peer, profile, model, prompt):
            nonlocal invoker_count
            invoker_count += 1
            return "OK"
            
        v1 = ccc.canary_probe(
            peer="cc",
            profile_name="standard",
            orch=MOCK_ORCHESTRATION,
            invoker=mock_invoker,
            force=False,
            ai_root=tmp_path
        )
        assert v1["status"] == "PASS"
        assert not v1.get("cached")
        assert invoker_count == 1
        
        v2 = ccc.canary_probe(
            peer="cc",
            profile_name="standard",
            orch=MOCK_ORCHESTRATION,
            invoker=mock_invoker,
            force=False,
            ai_root=tmp_path
        )
        assert v2["status"] == "PASS"
        assert v2.get("cached") is True
        assert invoker_count == 1
        
        v3 = ccc.canary_probe(
            peer="cc",
            profile_name="standard",
            orch=MOCK_ORCHESTRATION,
            invoker=mock_invoker,
            force=True,
            ai_root=tmp_path
        )
        assert v3["status"] == "PASS"
        assert not v3.get("cached")
        assert invoker_count == 2


class TestRunCanary:
    def test_run_canary_default_behavior(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")
        
        invoked = []
        def mock_invoker(peer, profile, model, prompt):
            invoked.append((peer, profile))
            return "OK"
            
        verdicts = ccc.run_canary(
            orch=MOCK_ORCHESTRATION,
            invoker=mock_invoker,
            ai_root=tmp_path
        )
        
        assert len(verdicts) == 2
        assert invoked == [("cc", "standard"), ("ag", "standard")]
        assert all(v["status"] == "PASS" for v in verdicts)

    def test_run_canary_all_profiles(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")
        
        invoked = []
        def mock_invoker(peer, profile, model, prompt):
            invoked.append((peer, profile))
            return "OK"
            
        verdicts = ccc.run_canary(
            orch=MOCK_ORCHESTRATION,
            all_profiles=True,
            invoker=mock_invoker,
            ai_root=tmp_path
        )
        
        assert len(verdicts) == 5
        assert set(invoked) == {
            ("cc", "standard"), ("cc", "effort"), ("cc", "deepthink"),
            ("ag", "standard"), ("ag", "deepthink")
        }

    def test_run_canary_crash_safe(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccr, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccr, "real_binary", lambda peer: tmp_path / f"{peer}_bin")
        
        def mock_invoker(peer, profile, model, prompt):
            if peer == "cc":
                raise RuntimeError("crash")
            return "OK"
            
        verdicts = ccc.run_canary(
            orch=MOCK_ORCHESTRATION,
            invoker=mock_invoker,
            ai_root=tmp_path
        )
        
        assert len(verdicts) == 2
        v_cc = next(v for v in verdicts if v["peer"] == "cc")
        v_ag = next(v for v in verdicts if v["peer"] == "ag")
        
        assert v_cc["status"] == "FAIL"
        assert v_cc["stage"] == "launch"
        assert v_ag["status"] == "PASS"


def test_record_budget_invocation_ignores_malformed_file(tmp_path):
    """A non-list budget file is treated as empty rather than crashing."""
    budget_file = tmp_path / "canary_budget.json"
    budget_file.write_text(json.dumps({"not": "a list"}), encoding="utf-8")

    ccc.record_budget_invocation(tmp_path, 1000.0)

    saved = json.loads(budget_file.read_text(encoding="utf-8"))
    assert saved == [1000.0]


def test_record_budget_invocation_persistence_failure_is_logged(monkeypatch, tmp_path, capsys):
    """A failed budget-file write is surfaced (stderr), not silently ignored."""
    def fail_write(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_write)

    ccc.record_budget_invocation(tmp_path, 123.0)

    err = capsys.readouterr().err
    assert "failed to persist budget invocation" in err
    assert "disk full" in err
