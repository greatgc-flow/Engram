"""_sys/tests/unit/test_canary_observed.py — Unit tests for check_cli_canary.py build/emit observed captures"""
from __future__ import annotations

import copy
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
        "budget_cap": 10,
        "budget_window_hours": 5.0
    },
    "hub_nodes": [
        {
            "node_id": "cc",
            "type": "peer",
            "enabled": True,
            "invoke": "_sys/tools/cc_bin",
            "profiles": {
                "standard": {
                    "model_id": "claude-haiku",
                    "cost_tier": "low",
                    "routing_state": "eligible"
                },
                "deepthink": {
                    "model_id": "claude-opus",
                    "cost_tier": "high",
                    "routing_state": "eligible"
                }
            }
        },
        {
            "node_id": "ag",
            "type": "peer",
            "enabled": True,
            "invoke": "_sys/tools/ag_bin",
            "profiles": {
                "standard": {
                    "runtime_model": "gemini-flash",
                    "cost_tier": "low",
                    "routing_state": "eligible"
                }
            }
        }
    ]
}


def test_build_observed_capture(tmp_path):
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
    verdicts = [
        {"peer": "cc", "profile": "standard", "model": "claude-haiku", "status": "PASS", "ts": "2026-07-04T12:00:00Z"},
        {"peer": "cc", "profile": "deepthink", "model": "claude-opus", "status": "FAIL", "ts": "2026-07-04T12:00:00Z"},
        {"peer": "ag", "profile": "standard", "model": "gemini-flash", "status": "PASS", "ts": "2026-07-04T12:00:00Z"},
    ]
    
    capture = ccc.build_observed_capture(verdicts, now=now)
    
    # 1. PASS models captured, FAIL/SKIP excluded
    assert "claude-haiku" in capture["cc"]["models"]
    assert "claude-opus" not in capture["cc"]["models"]
    assert "gemini-flash" in capture["ag"]["models"]
    
    # 2. Schema keys present (models/captured_at/provenance)
    for peer in ["cc", "ag"]:
        assert "models" in capture[peer]
        assert "captured_at" in capture[peer]
        assert "provenance" in capture[peer]
        assert capture[peer]["captured_at"] == now.isoformat()
        
    assert len(capture["cc"]["provenance"]) == 1
    assert capture["cc"]["provenance"][0]["model"] == "claude-haiku"
    assert capture["cc"]["provenance"][0]["profile"] == "standard"
    assert capture["cc"]["provenance"][0]["verdict"] == "PASS"


def test_build_observed_capture_empty_on_all_fail(tmp_path):
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
    verdicts = [
        {"peer": "cc", "profile": "standard", "model": "claude-haiku", "status": "FAIL", "ts": "2026-07-04T12:00:00Z"},
        {"peer": "cc", "profile": "deepthink", "model": "claude-opus", "status": "SKIP", "ts": "2026-07-04T12:00:00Z"},
    ]
    
    capture = ccc.build_observed_capture(verdicts, now=now)

    # A peer with no PASS is OMITTED (not emitted as models:[]), so
    # check_cli_reality.load_observed_models returns None => ABSENT, not a
    # measured empty list that would false-flag every declared model CONTRADICTED.
    assert "cc" not in capture
    assert capture == {}


def test_emit_observed_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(ccc, "fingerprint", lambda path: {"sha256": "dummy_sha", "exists": True})
    monkeypatch.setattr(ccc, "real_binary", lambda peer, orch=None: tmp_path / f"{peer}_bin")
    # T44a: canary invocation now requires a granted budget reservation. Grant it by
    # supplying a reserve floor and a machine-observed quota above the floor (the
    # production _canary_quota reads a live snapshot that is absent under test).
    monkeypatch.setattr(ccc, "_canary_quota",
                        lambda peer, profile: {"source_tag": "app_server", "remaining": 0.9})
    orch = copy.deepcopy(MOCK_ORCHESTRATION)
    orch["canary_config"]["reserve_floor"] = 0.1

    def mock_invoker(peer, profile, model, prompt):
        if peer == "cc" and profile == "deepthink":
            return "NOPE"
        return "OK"

    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)

    capture = ccc.emit_observed_capture(
        orch=orch,
        ai_root=tmp_path,
        invoker=mock_invoker,
        now=now
    )
    
    # Check return value
    assert "cc" in capture
    assert "ag" in capture
    assert "claude-haiku" in capture["cc"]["models"]
    assert "claude-opus" not in capture["cc"]["models"]
    assert "gemini-flash" in capture["ag"]["models"]
    
    # Check file exists and has same content
    out_file = tmp_path / "cli-reality-observed.json"
    assert out_file.exists()
    
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data == capture
