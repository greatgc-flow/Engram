"""_sys/tests/unit/test_cli_canary.py — Unit tests for check_cli_canary.py"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SYS_DIR / "checks"))
import check_cli_canary as ccc  # noqa: E402
import check_cli_reality as ccr  # noqa: E402

MOCK_ORCHESTRATION = {
    "canary_config": {
        "budget_cap": 2,
        "budget_window_hours": 5.0,
        "reserve_floor": 0.25,
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


@pytest.fixture(autouse=True)
def _machine_quota(monkeypatch):
    """Canary unit tests inject observed quota; production reads snapshot."""
    monkeypatch.setattr(
        ccc, "_canary_quota",
        lambda peer, profile: {"source_tag": "cli_live", "remaining": 0.50},
    )


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
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
        
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
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
        
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
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
        import copy
        orch = copy.deepcopy(MOCK_ORCHESTRATION)
        orch["canary_config"]["budget_cap"] = 4

        for bad_reply in ("NOT OK", "OK but failed", "not ok"):
            def mock_invoker(peer, profile, model, prompt, _r=bad_reply):
                return _r

            verdict = ccc.canary_probe(
                peer="cc",
                profile_name="standard",
                orch=orch,
                invoker=mock_invoker,
                force=True,
                ai_root=tmp_path,
            )
            assert verdict["status"] == "FAIL", f"{bad_reply!r} must not PASS"
            assert verdict["stage"] == "reply"

    def test_canary_probe_reply_normalized_ok(self, monkeypatch, tmp_path):
        # Whitespace/newline-wrapped and lower-case exact "OK" still PASS.
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
        import copy
        orch = copy.deepcopy(MOCK_ORCHESTRATION)
        orch["canary_config"]["budget_cap"] = 5

        for good_reply in ("OK", " OK\n", "ok", "\tOK  "):
            def mock_invoker(peer, profile, model, prompt, _r=good_reply):
                return _r

            verdict = ccc.canary_probe(
                peer="cc",
                profile_name="standard",
                orch=orch,
                invoker=mock_invoker,
                force=True,
                ai_root=tmp_path,
            )
            assert verdict["status"] == "PASS", f"{good_reply!r} must PASS"

    def test_canary_probe_launch_fail(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
        
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
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
        
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
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
        
        def mock_invoker(peer, profile, model, prompt):
            return "OK"
            
        now = datetime.now(timezone.utc)
        for subject in ("cc.effort", "ag.standard"):
            reserved = ccc.reserve_canary_invocation(
                tmp_path, kind="cli_canary", subject=subject, now=now,
                cap=2, window_hours=5.0, reserve_floor=0.25,
                quota_source_tag="cli_live", quota_remaining=0.50,
                orchestration=MOCK_ORCHESTRATION,
            )
            assert reserved["granted"]
        
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
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
        
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
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
        
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
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")

        # T16 (2026-07-10): all_profiles fan-out is budget-capped now (no
        # longer an implicit bypass) - this test verifies the target-
        # expansion logic itself (every peer's every profile), so give it
        # enough budget headroom to not be about budget capping.
        import copy
        orch = copy.deepcopy(MOCK_ORCHESTRATION)
        orch["canary_config"]["budget_cap"] = 10

        invoked = []
        def mock_invoker(peer, profile, model, prompt):
            invoked.append((peer, profile))
            return "OK"

        verdicts = ccc.run_canary(
            orch=orch,
            all_profiles=True,
            invoker=mock_invoker,
            ai_root=tmp_path
        )

        assert len(verdicts) == 5
        assert set(invoked) == {
            ("cc", "standard"), ("cc", "effort"), ("cc", "deepthink"),
            ("ag", "standard"), ("ag", "deepthink")
        }

    def test_run_canary_all_profiles_is_budget_capped(self, monkeypatch, tmp_path):
        """T16 (2026-07-10): all_profiles fan-out is no longer an implicit
        budget bypass - MOCK_ORCHESTRATION's budget_cap=2 must cap the
        5-target fan-out at 2 real invocations, the rest SKIP on budget."""
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")

        invoked = []
        def mock_invoker(peer, profile, model, prompt):
            invoked.append((peer, profile))
            return "OK"

        verdicts = ccc.run_canary(
            orch=MOCK_ORCHESTRATION,
            all_profiles=True,
            invoker=mock_invoker,
            ai_root=tmp_path,
        )

        assert len(verdicts) == 5
        assert len(invoked) == 2
        skipped = [v for v in verdicts if v["status"] == "SKIP"]
        assert len(skipped) == 3
        assert all(v["reason"] == "budget" for v in skipped)

    def test_run_canary_root_peer_all_profiles_is_not_explicit_budget_bypass(self, monkeypatch, tmp_path):
        """T16: peers=['cc'] + all_profiles=True is a fan-out (bulk), not a
        specific single target - must NOT bypass an exhausted budget."""
        import copy
        orch = copy.deepcopy(MOCK_ORCHESTRATION)
        orch["canary_config"]["budget_cap"] = 0

        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")

        invoked = []
        verdicts = ccc.run_canary(
            orch=orch,
            peers=["cc"],
            all_profiles=True,
            invoker=lambda *args: invoked.append(args) or "OK",
            ai_root=tmp_path,
        )

        assert invoked == []
        assert verdicts
        assert all(v["status"] == "SKIP" and v["reason"] == "budget_disabled" for v in verdicts)

    def test_run_canary_explicit_peer_profile_never_bypasses_budget(self, monkeypatch, tmp_path):
        """T44a removes the former explicit-target budget-bypass path."""
        import copy
        orch = copy.deepcopy(MOCK_ORCHESTRATION)
        orch["canary_config"]["budget_cap"] = 0

        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")

        verdicts = ccc.run_canary(
            orch=orch,
            peers=["cc.standard"],
            invoker=lambda *args: "OK",
            ai_root=tmp_path,
        )

        assert len(verdicts) == 1
        assert verdicts[0]["status"] == "SKIP"
        assert verdicts[0]["reason"] == "budget_disabled"

    def test_run_canary_crash_safe(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
        monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
        
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


def test_cli_probe_reserves_before_invoking(monkeypatch, tmp_path):
    """The invoker can observe its reservation; it is consumed afterwards."""
    monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
    monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")

    def invoker(*_args):
        ledger = json.loads((tmp_path / "canary_budget.json").read_text(encoding="utf-8"))
        assert ledger["entries"][-1]["state"] == "reserved"
        return "OK"

    verdict = ccc.canary_probe("cc", "standard", MOCK_ORCHESTRATION, invoker=invoker, force=True, ai_root=tmp_path)
    ledger = json.loads((tmp_path / "canary_budget.json").read_text(encoding="utf-8"))
    assert verdict["status"] == "PASS"
    assert ledger["entries"][-1]["state"] == "consumed"
