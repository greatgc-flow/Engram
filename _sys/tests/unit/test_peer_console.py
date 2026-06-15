import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli"))
from peer_console import peer_default_args


def test_claude_defaults_to_full_permissions():
    args = peer_default_args("cc", [])
    assert "--allowedTools" in args
    assert "--permission-mode" in args
    assert "acceptEdits" in args


def test_claude_respects_explicit_permission_mode():
    args = peer_default_args("cc", ["--permission-mode", "plan"])
    assert args == ["--permission-mode", "plan"]


def test_claude_does_not_modify_management_command():
    args = peer_default_args("cc", ["doctor"])
    assert args == ["doctor"]


def test_gemini_defaults_to_auto_edit_and_trust():
    args = peer_default_args("gc", [])
    assert args == ["--approval-mode", "auto_edit", "--skip-trust"]


def test_gemini_respects_plan_override_but_keeps_trust_skip():
    args = peer_default_args("gc", ["--approval-mode", "plan"])
    assert args == ["--approval-mode", "plan", "--skip-trust"]


def test_gemini_does_not_modify_management_command():
    args = peer_default_args("gc", ["mcp"])
    assert args == ["mcp"]


def test_codex_defaults_to_workspace_write():
    args = peer_default_args("cx", [])
    assert args == ["-s", "workspace-write", "--ignore-rules"]


def test_codex_respects_explicit_sandbox_policy():
    args = peer_default_args("cx", ["--sandbox", "workspace-write", "--ask-for-approval", "on-request"])
    assert args == ["--sandbox", "workspace-write", "--ask-for-approval", "on-request"]


def test_codex_does_not_modify_management_command():
    args = peer_default_args("cx", ["doctor"])
    assert args == ["doctor"]


def test_agy_defaults_to_skip_permissions():
    args = peer_default_args("ag", [])
    assert args == ["--dangerously-skip-permissions"]


def test_agy_respects_sandbox_override():
    args = peer_default_args("ag", ["--sandbox"])
    assert args == ["--sandbox"]


def test_help_is_not_modified():
    args = peer_default_args("cx", ["--help"])
    assert args == ["--help"]
