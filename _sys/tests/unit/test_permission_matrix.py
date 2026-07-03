"""Contract tests for the peer permission/security matrix."""
import json
import sys
from pathlib import Path

SYS = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SYS / "cli"))

from peer_console import peer_default_args

ORCHESTRATION = SYS / "ai" / "orchestration.json"


def _raw():
    return json.loads(ORCHESTRATION.read_text(encoding="utf-8"))


def _root_nodes():
    return {
        node["node_id"]: node
        for node in _raw()["hub_nodes"]
        if node.get("type") == "peer"
    }


def _args(node):
    return [str(arg) for arg in node.get("invoke_args", [])]


def _joined(args):
    return " ".join(args)


def test_active_peer_capability_classes_are_explicit():
    data = _raw()
    permission_classes = set(data.get("permission_classes", {}))
    nodes = _root_nodes()
    expected = {
        "ag": "unsandboxed_trusted_mutation",
        "cc": "tool_scoped_mutation",
        "cx": "sandboxed_mutation",
    }

    for peer_id, capability_class in expected.items():
        assert capability_class in permission_classes
        assert nodes[peer_id].get("enabled") is True
        assert nodes[peer_id].get("capability_class") == capability_class


def test_ag_uses_pty_skip_permissions_without_fake_sandbox():
    ag = _root_nodes()["ag"]
    args = _args(ag)

    assert ag.get("requires_pty") is True
    assert "--dangerously-skip-permissions" in args
    assert "--permission-mode" not in args
    assert "--sandbox" not in args
    assert "-s" not in args


def test_cx_requires_workspace_write_without_full_danger_bypass():
    cx = _root_nodes()["cx"]
    args = _args(cx)
    joined = _joined(args)

    assert "workspace-write" in joined
    assert "--dangerously-skip-permissions" not in args
    assert "dangerously-bypass-approvals-and-sandbox" not in joined


def test_cc_uses_allowlist_target_without_skip_debt():
    cc = _root_nodes()["cc"]
    args = _args(cc)
    required_tools = {
        "Read",
        "Grep",
        "Glob",
        "Edit",
        "Bash(python*)",
        "Bash(git status*)",
        "Bash(git diff*)",
        "Bash(git log*)",
    }

    assert "--dangerously-skip-permissions" not in args
    assert "--permission-mode" in args
    assert "default" in args
    assert any(arg in args for arg in ("--allowedTools", "--allowed-tools"))
    assert required_tools.issubset(set(args))
    assert cc.get("capability_class") == "tool_scoped_mutation"


def test_no_active_peer_uses_forbidden_full_bypass_flags():
    forbidden = (
        "dangerously-bypass-approvals-and-sandbox",
        "--yolo",
        "yolo",
        "full-auto",
        "--skip-trust",
    )

    for peer_id, node in _root_nodes().items():
        if node.get("enabled") is False:
            continue
        joined = _joined(_args(node))
        for flag in forbidden:
            assert flag not in joined, f"{peer_id} uses forbidden flag {flag}"


def test_gc_is_not_an_active_orchestration_peer_and_console_has_no_yolo():
    nodes = _root_nodes()
    assert "gc" not in nodes or nodes["gc"].get("enabled") is False
    assert "ca" not in nodes or nodes["ca"].get("enabled") is False

    gc_console_args = peer_default_args("gc", [])
    assert "yolo" not in gc_console_args
    assert "--yolo" not in gc_console_args
