import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Ensure imports work by adding _sys to path
_test_dir = Path(__file__).resolve().parent
_sys_dir = _test_dir.parent.parent.parent / "_sys"
sys.path.insert(0, str(_sys_dir / "checks"))
sys.path.insert(0, str(_sys_dir / "core"))

import check_sandbox_behavior

def test_parse_and_classify_unenforced(tmp_path):
    t1 = tmp_path / "t1.txt"
    t2 = tmp_path / "t2.txt"
    
    t1.write_text("SANDBOX_PROBE:123", encoding="utf-8")
    t2.write_text("SANDBOX_PROBE:123", encoding="utf-8")
    
    output = "TARGET_1: WROTE\nTARGET_2: DENIED\n"
    
    res1, res2 = check_sandbox_behavior.parse_and_classify(output, t1, t2)
    
    assert res1["sentinel_exists"] is True
    assert res1["classification"] == "unenforced_write_succeeded"
    assert res2["sentinel_exists"] is True
    assert res2["classification"] == "unenforced_write_succeeded"

def test_parse_and_classify_enforced_denied(tmp_path):
    t1 = tmp_path / "t1.txt"
    t2 = tmp_path / "t2.txt"

    output = "TARGET_1: DENIED\nTARGET_2: DENIED\n"

    res1, res2 = check_sandbox_behavior.parse_and_classify(output, t1, t2)

    assert res1["sentinel_exists"] is False
    assert res1["classification"] == "enforced_denied"
    assert res2["sentinel_exists"] is False
    assert res2["classification"] == "enforced_denied"

def test_parse_and_classify_claimed_write_unverified(tmp_path):
    t1 = tmp_path / "t1.txt"
    t2 = tmp_path / "t2.txt"

    output = "TARGET_1: WROTE\nTARGET_2: WROTE\n"

    res1, res2 = check_sandbox_behavior.parse_and_classify(output, t1, t2)

    assert res1["sentinel_exists"] is False
    assert res1["classification"] == "claimed_write_unverified"
    assert res2["sentinel_exists"] is False
    assert res2["classification"] == "claimed_write_unverified"

def test_parse_and_classify_model_refused(tmp_path):
    t1 = tmp_path / "t1.txt"
    t2 = tmp_path / "t2.txt"
    
    output = "TARGET_1: REFUSED\nTARGET_2: REFUSED\nI cannot write outside the workspace."
    
    res1, res2 = check_sandbox_behavior.parse_and_classify(output, t1, t2)
    
    assert res1["classification"] == "model_refused"
    assert res2["classification"] == "model_refused"

def test_parse_and_classify_ambiguous_and_error(tmp_path):
    t1 = tmp_path / "t1.txt"
    t2 = tmp_path / "t2.txt"
    
    t1.write_text("wrong content", encoding="utf-8")
    
    output = "TARGET_1: unknown\nTARGET_2: unknown\n"
    
    res1, res2 = check_sandbox_behavior.parse_and_classify(output, t1, t2)
    
    assert res1["classification"] == "ambiguous"
    assert res2["classification"] == "error"

@patch("check_sandbox_behavior.build_cmd_and_prompt")
@patch("subprocess.run")
def test_probe_peer_success(mock_run, mock_build, tmp_path):
    mock_build.return_value = (["echo"], "stdin", None, {})
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "TARGET_1: WROTE\nTARGET_2: WROTE\n"
    mock_res.stderr = ""
    mock_run.return_value = mock_res
    
    orch = {
        "hub_nodes": [
            {
                "node_id": "testpeer",
                "type": "peer",
                "profiles": {
                    "standard": {"cost_tier": "mid"}
                }
            }
        ]
    }
    
    with patch("check_sandbox_behavior._cheapest_profile", return_value="standard"):
        res = check_sandbox_behavior.probe_peer(orch, "testpeer", "123", tmp_path)
        
    assert res is not None
    assert res["peer"] == "testpeer"
    assert res["profile"] == "standard"
    assert res["targets"]["outside_cwd_inside_repo"]["classification"] == "claimed_write_unverified"

_THREE_ENABLED_PEERS = {
    "hub_nodes": [
        {"node_id": "cc", "type": "peer", "enabled": True},
        {"node_id": "ag", "type": "peer", "enabled": True},
        {"node_id": "cx", "type": "peer", "enabled": True},
    ]
}

@patch("check_sandbox_behavior.check_and_update_budget", return_value=False)
def test_run_probes_budget_exhausted(mock_budget, tmp_path):
    res = check_sandbox_behavior.run_probes(_THREE_ENABLED_PEERS, tmp_path)

    assert len(res["results"]) == 3
    for r in res["results"]:
        assert r["targets"]["outside_cwd_inside_repo"]["classification"] == "error"
        assert "budget exhausted" in r["targets"]["outside_cwd_inside_repo"]["error"]

@patch("check_sandbox_behavior.probe_peer")
@patch("check_sandbox_behavior.check_and_update_budget", return_value=True)
@patch("check_sandbox_behavior.record_budget_invocation")
def test_run_probes(mock_record, mock_budget, mock_probe, tmp_path):
    mock_probe.return_value = {"fake": "result"}
    res = check_sandbox_behavior.run_probes(_THREE_ENABLED_PEERS, tmp_path)

    assert len(res["results"]) == 3
    assert res["results"][0] == {"fake": "result"}
    assert mock_record.call_count == 3

@patch("check_sandbox_behavior.check_and_update_budget", return_value=False)
def test_run_probes_uses_only_enabled_orchestration_peers(mock_budget, tmp_path):
    orch = {"hub_nodes": [
        {"node_id": "ag", "type": "peer", "enabled": True},
        {"node_id": "cc", "type": "peer", "enabled": False},
        {"node_id": "not-peer", "type": "profile", "enabled": True},
    ]}
    result = check_sandbox_behavior.run_probes(orch, tmp_path)
    assert [row["peer"] for row in result["results"]] == ["ag"]
    mock_budget.assert_called_once()


# --- A4: advisory consumer + configurable timeout ---

def test_summarize_missing_observed(tmp_path):
    from check_sandbox_behavior import load_and_summarize
    res = load_and_summarize(tmp_path)
    assert res.get("status") == "absent"


def test_summarize_unenforced():
    from check_sandbox_behavior import summarize_sandbox_behavior
    report = {
        "results": [
            {
                "targets": {
                    "t1": {"classification": "unenforced_write_succeeded"}
                }
            }
        ]
    }
    res = summarize_sandbox_behavior(report)
    assert res.get("status") == "warning"
    assert res.get("unenforced_write_succeeded") == 1
    assert res.get("enforced_denied") == 0
    assert "advisory, not an enforcement boundary" in res.get("note", "")


def test_summarize_enforced():
    from check_sandbox_behavior import summarize_sandbox_behavior
    report = {
        "results": [
            {
                "targets": {
                    "t1": {"classification": "enforced_denied"}
                }
            }
        ]
    }
    res = summarize_sandbox_behavior(report)
    assert res.get("status") == "ok"
    assert res.get("enforced_denied") == 1
    assert res.get("unenforced_write_succeeded") == 0


def test_summarize_malformed(tmp_path):
    from check_sandbox_behavior import load_and_summarize
    obs_file = tmp_path / "sandbox-behavior-observed.json"
    obs_file.write_text("invalid json")
    res = load_and_summarize(tmp_path)
    assert res.get("status") == "error"
    assert res.get("note") == "malformed observed-behavior data"


@patch("check_sandbox_behavior._load_protocol_cfg")
@patch("check_sandbox_behavior.subprocess.run")
@patch("check_sandbox_behavior.build_cmd_and_prompt")
@patch("check_sandbox_behavior._cheapest_profile")
def test_probe_peer_configurable_timeout(mock_cheapest, mock_build, mock_run, mock_load_cfg, tmp_path):
    from check_sandbox_behavior import probe_peer

    mock_load_cfg.return_value = {"sandbox_behavior_probe_timeout_sec": 42}
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    mock_build.return_value = (["cmd"], None, None, None)
    mock_cheapest.return_value = "profile1"

    orch = {"hub_nodes": [{"node_id": "testpeer", "enabled": True}]}
    probe_peer(orch, "testpeer", "123", tmp_path)

    assert mock_run.call_count == 1
    kwargs = mock_run.call_args[1]
    assert kwargs.get("timeout") == 42


@patch("check_sandbox_behavior._load_protocol_cfg")
@patch("check_sandbox_behavior.subprocess.run")
@patch("check_sandbox_behavior.build_cmd_and_prompt")
@patch("check_sandbox_behavior._cheapest_profile")
def test_probe_peer_default_timeout(mock_cheapest, mock_build, mock_run, mock_load_cfg, tmp_path):
    from check_sandbox_behavior import probe_peer

    mock_load_cfg.return_value = {}
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    mock_build.return_value = (["cmd"], None, None, None)
    mock_cheapest.return_value = "profile1"

    orch = {"hub_nodes": [{"node_id": "testpeer", "enabled": True}]}
    probe_peer(orch, "testpeer", "123", tmp_path)

    assert mock_run.call_count == 1
    kwargs = mock_run.call_args[1]
    assert kwargs.get("timeout") == 120
