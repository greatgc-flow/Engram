import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli"))
import hub
import hub_peer
from peer_console import peer_default_args


def _mock_proc(stdout=b"ok", stderr=b"", returncode=0):
    proc = MagicMock()
    proc.pid = 12345
    proc.returncode = returncode
    proc.communicate.return_value = (stdout, stderr)
    proc.poll.return_value = None
    proc.stdout = MagicMock()
    proc.stderr = MagicMock()
    return proc


def test_cx_no_dangerously_bypass_flag():
    node = hub._default_nodes()["nodes"]["cx"]
    args, use_stdin = hub_peer.get_adapter(node).build_cmd(node, "test")
    assert "--dangerously-bypass-approvals-and-sandbox" not in args
    assert use_stdin is True


def test_cx_uses_workspace_write_sandbox():
    node = hub._default_nodes()["nodes"]["cx"]
    args, _ = hub_peer.get_adapter(node).build_cmd(node, "test")
    assert 'sandbox="workspace-write"' in args


def test_cc_uses_dir002_skip_permissions():
    args = peer_default_args("cc", [])
    assert "--dangerously-skip-permissions" in args


def test_cc_does_not_mix_legacy_allowed_tools():
    args = peer_default_args("cc", [])
    assert "--allowedTools" not in args


def test_cc_does_not_mix_legacy_accept_edits():
    args = peer_default_args("cc", [])
    assert "--permission-mode" not in args
    assert "acceptEdits" not in args


def test_gc_no_yolo():
    args = peer_default_args("gc", [])
    assert "yolo" not in args


def test_hub_timeout_zero_is_unlimited(monkeypatch):
    monkeypatch.setattr(hub, "_runtime_cfg", lambda: {"ask_default_timeout_sec": 7})
    monkeypatch.setattr(hub, "_lease_cfg", lambda: (999, 1800, 1800))  # heartbeat, lease, zombie
    monkeypatch.setattr(hub, "_load_orchestration", lambda: {
        "hub_nodes": [{
            "node_id": "mock_peer",
            "type": "peer",
            "invoke": "mock-cli",
            "invoke_args": ["-p", "{query}"],
            "timeout": 0,
        }]
    })

    proc = _mock_proc()
    with patch("shutil.which", return_value="mock-cli"), \
         patch("subprocess.Popen", return_value=proc):
        hub.action_ask("mock_peer", "hello", None, 0, None, quiet=True)

    assert proc.communicate.call_args.kwargs["timeout"] == 999


def test_hub_lease_timeout_is_1800():
    _, lease_timeout_sec, _ = hub._lease_cfg()  # (heartbeat, lease, zombie)
    assert lease_timeout_sec >= 1800


def test_cx_parity_accepts_config_sandbox_form():
    """cx workspace-write sandbox parity passes whether enforced via -s or -c sandbox=."""
    # Real config: cx uses `-c sandbox="workspace-write"` -> must produce NO cx parity error.
    errors = hub._check_flag_parity()
    cx_errors = [e for e in errors if e.startswith("PARITY cx")]
    gc_errors = [e for e in errors if e.startswith("PARITY gc")]
    assert cx_errors == [], f"unexpected cx parity errors: {cx_errors}"
    assert gc_errors == [], f"gc was retired; must not be a parity target: {gc_errors}"


def test_cx_parity_still_fails_when_sandbox_absent():
    """Security not weakened: a cx command with NO workspace-write sandbox is flagged."""
    orch = hub.hub_peer.normalize_orchestration(hub._load_orchestration())
    for node in orch.get("hub_nodes", []):
        if node.get("node_id") == "cx":
            node["invoke_args"] = ["exec", "{query}", "--json"]  # strip sandbox
    with patch.object(hub.hub_peer, "normalize_orchestration", return_value=orch):
        errors = hub._check_flag_parity()
    assert any("PARITY cx" in e and "workspace-write" in e for e in errors), \
        f"sandbox-absent cx must be flagged, got: {errors}"


def test_ask_actions_are_classified_not_unknown():
    """Regression: ask/ask-all/ask-stream/relay must be classified (read_only),
    else the phase-policy gate blocks them as 'unknown_actions' when a phase is set
    (root cause of intermittent [HUB:BLOCK] 'ask has no phase policy during active')."""
    for action in ("ask", "ask-all", "ask-stream", "relay"):
        group = hub._action_group(action)
        assert group == "read_only_hub_actions", f"{action} regressed to group={group}"
