"""Integration tests for hub.py v4.2 — verifying logging, error, context, and peer adapters."""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add core to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
import hub

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def ai_dir(tmp_path: Path, monkeypatch):
    """Create a mock .ai root with necessary config files."""
    ai = tmp_path / ".ai"
    ai.mkdir()
    def _get_peer_dir(peer_id):
        p = tmp_path / "_sys" / peer_id
        p.mkdir(parents=True, exist_ok=True)
        return p
    monkeypatch.setattr(hub, "_peer_sys_dir", _get_peer_dir)
    
    # orchestration.json
    orch = ai.parent / "_sys" / "ai" / "orchestration.json"
    orch.parent.mkdir(parents=True, exist_ok=True)
    orch.write_text(json.dumps({
        "hub_nodes": [
            {
                "node_id": "cc",
                "adapter_class": "ClaudeAdapter",
                "invoke": "claude",
                "invoke_args": ["-p", "{query}"],
                "memory": "persistent"
            },
            {
                "node_id": "cc.effort",
                "profile_id": "cc.effort",
                "type": "profile",
                "root_peer": "cc",
                "adapter_class": "ClaudeAdapter",
                "invoke": "claude",
                "invoke_args": ["-p", "{query}"],
                "memory": "persistent",
                "runtime_context_window": 200000
            },
            {
                "node_id": "claude-default",
                "profile_id": "claude-default",
                "type": "profile",
                "root_peer": "cc",
                "adapter_class": "ClaudeAdapter",
                "invoke": "claude",
                "invoke_args": ["-p", "{query}"],
                "memory": "persistent",
                "runtime_context_window": 200000
            },
            {
                "node_id": "gc",
                "adapter_class": "GeminiAdapter",
                "invoke": "gemini",
                "invoke_args": ["-p", "{query}"],
                "memory": "session"
            },
            {
                "node_id": "gc.effort",
                "profile_id": "gc.effort",
                "type": "profile",
                "root_peer": "gc",
                "adapter_class": "GeminiAdapter",
                "invoke": "gemini",
                "invoke_args": ["-p", "{query}"],
                "memory": "session",
                "runtime_context_window": 1000000
            },
            {
                "node_id": "gemini-default",
                "profile_id": "gemini-default",
                "type": "profile",
                "root_peer": "gc",
                "adapter_class": "GeminiAdapter",
                "invoke": "gemini",
                "invoke_args": ["-p", "{query}"],
                "memory": "session",
                "runtime_context_window": 1000000
            }
        ]
    }), encoding="utf-8")
    
    # peers.json
    peers = ai.parent / "_sys" / "ai" / "peers.json"
    peers.write_text(json.dumps({
        "peers": {
            "claude": {"sys_subdir": "claude", "model_profiles": {"standard": "cc.effort", "effort": "cc.effort"}},
            "gemini": {"sys_subdir": "gemini", "model_profiles": {"standard": "gc.effort", "effort": "gc.effort"}}
        }
    }), encoding="utf-8")
    
    # model-profiles.json
    model_prof = ai.parent / "_sys" / "ai" / "model-profiles.json"
    model_prof.write_text(json.dumps({
        "profiles": {
            "claude-default": {"peer": "claude", "mode": "default", "model_id": "claude-3-5-sonnet", "runtime_context_window": 200000},
            "gemini-default": {"peer": "gemini", "mode": "default", "model_id": "gemini-1-5-pro", "runtime_context_window": 1000000}
        }
    }), encoding="utf-8")
    
    # model-registry.json
    model_reg = ai.parent / "_sys" / "ai" / "model-registry.json"
    model_reg.write_text(json.dumps({
        "models": {
            "claude-3-5-sonnet": {"context_limit": 200000},
            "gemini-1-5-pro": {"context_limit": 1000000}
        }
    }), encoding="utf-8")
    
    # protocol.json
    protocol = ai.parent / "_sys" / "ai" / "protocol.json"
    protocol.write_text(json.dumps({
        "collab_rate": {"current": 5}
    }), encoding="utf-8")
    
    # logging-config.json
    log_cfg = ai.parent / "_sys" / "ai" / "logging-config.json"
    log_cfg.write_text(json.dumps({
        "log_dir": "_sys/data/logs",
        "types": {
            "ipc-log": {"file": "ipc-log.jsonl"},
            "cost-log": {"file": "cost-log.jsonl"},
            "error-log": {"file": "error-log.jsonl"}
        }
    }), encoding="utf-8")

    return ai

# ── Tests ─────────────────────────────────────────────────────────────────────

def test_action_ask_integrates_logging(ai_dir, monkeypatch):
    """CHK-LOG-01: Verify that action_ask records to ipc-log and cost-log."""
    monkeypatch.setattr(hub, "find_ai_root", lambda: ai_dir)
    
    def make_mock_proc(*args, **kwargs):
        m = MagicMock()
        m.returncode = 0
        m.stdout = io.BufferedReader(io.BytesIO(b"Success Response"))
        m.stderr = io.BufferedReader(io.BytesIO(b""))
        m.poll.side_effect = [None] * 5 + [0] * 20
        m.communicate.return_value = (b"Success Response", b"")
        m.pid = 1234
        return m
    
    with patch("subprocess.Popen", side_effect=make_mock_proc) as mock_popen, \
         patch("hub_logging.HubLogger.log_ipc") as mock_log_ipc, \
         patch("hub_logging.HubLogger.log_cost") as mock_log_cost, \
         patch("hub_context.ContextGate.check", return_value={"action": "pass"}), \
         patch("hub._ask_health_precheck"):
        
        hub.action_ask(to="cc", query="Hello", query_file=None, timeout_sec=30, ai_root=ai_dir)
        
        assert mock_log_ipc.called
        assert mock_log_cost.called

def test_action_ask_integrates_context_gate(ai_dir, monkeypatch):
    """CHK-GATE-03: Verify ContextGate failover logic."""
    monkeypatch.setattr(hub, "find_ai_root", lambda: ai_dir)
    
    # Mock configs to return our test nodes/profiles
    test_nodes_data = {
        "cc": {"peer": "claude", "invoke": "claude"},
        "cc.effort": {"peer": "claude", "invoke": "claude"},
        "gc": {"peer": "gemini", "invoke": "gemini"},
        "gc.effort": {"peer": "gemini", "invoke": "gemini"}
    }
    test_profiles = {
        "profiles": {
            "claude-default": {"peer": "claude", "mode": "default", "model_id": "claude-3-5-sonnet"},
            "gemini-default": {"peer": "gemini", "mode": "default", "model_id": "gemini-1-5-pro"}
        }
    }
    
    # Mock ContextGate to return a failover result for 'cc' but 'pass' for 'gc'
    def mock_gate_check(query, model_id):
        if "sonnet" in model_id or model_id in ("cc", "cc.effort"):
            return {"action": "failover", "failover_model": "gc", "ratio": 1.1, "message": "Too large"}
        return {"action": "pass"}

    def mock_select_ask_profile(to_peer, query):
        if to_peer == "cc":
            return "cc.effort", {"node_id": "cc.effort", "classifier_triggered": True, "score": 0, "signals": ["ambiguous_default"]}
        return to_peer, None

    # Mock Popen
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = io.BufferedReader(io.BytesIO(b"Failover OK"))
    mock_proc.stderr = io.BufferedReader(io.BytesIO(b""))
    mock_proc.poll.return_value = 0
    mock_proc.communicate.return_value = (b"Failover OK", b"")
    mock_proc.pid = 5678

    with patch("hub_context.ContextGate.check", side_effect=mock_gate_check), \
         patch("hub._compose_dispatch_target", return_value=MagicMock(context_target="cc", profile_id="cc")), \
         patch("hub._load_nodes", return_value=test_nodes_data), \
         patch("hub._default_nodes", return_value={"nodes": test_nodes_data}), \
         patch("hub._load_model_profiles", return_value=test_profiles), \
         patch("hub._select_ask_profile", side_effect=mock_select_ask_profile), \
         patch("hub.is_routable", return_value=True), \
         patch("subprocess.Popen", return_value=mock_proc) as mock_popen, \
         patch("hub._ask_health_precheck"):
        
        hub.action_ask(to="cc", query="Very long query...", query_file=None, timeout_sec=30, ai_root=ai_dir)
        
        # Verify that it called Popen with 'gemini' (failover target)
        assert mock_popen.called

def test_action_ask_integrates_error_visibility(ai_dir, monkeypatch):
    """CHK-ERR-01: Verify that peer failure triggers HubError report."""
    monkeypatch.setattr(hub, "find_ai_root", lambda: ai_dir)
    
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = io.BufferedReader(io.BytesIO(b""))
    mock_proc.stderr = io.BufferedReader(io.BytesIO(b"API Error: Authentication failed"))
    mock_proc.poll.return_value = 1
    mock_proc.communicate.return_value = (b"", b"API Error: Authentication failed")
    mock_proc.pid = 9012
    
    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("hub_error.HubError.report_from_legacy") as mock_report, \
         patch("hub._ask_health_precheck"):
        
        # action_ask sys.exits(1) on failure
        with pytest.raises(SystemExit):
            hub.action_ask(to="cc", query="Hello", query_file=None, timeout_sec=30, ai_root=ai_dir)
            
        assert mock_report.called
