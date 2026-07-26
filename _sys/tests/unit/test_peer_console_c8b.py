"""
Unit Tests for Cluster C8-B (peer_console.py Consolidation & prepare_console_launch API)

Covers:
  1. InvocationKind classification (LOCAL_AGENT, REMOTE_AGENT, ADMIN_OR_SERVICE, HELP_OR_VERSION).
  2. ConsoleLaunch dataclass shape and immutability.
  3. LOCAL_AGENT defaults & root-scope flag insertion for active peers.
  4. REMOTE_AGENT (codex cloud / cloud exec): model defaults applied, local sandbox flags NOT applied, remote banner.
  5. ADMIN_OR_SERVICE / HELP_OR_VERSION: no defaults, no banner, argv unchanged.
  6. forbidden_effective_args runtime rejection & ALLOW_BREAK_GLASS_DANGER_ACCESS=1 override.
  7. Truthful banner generation & custom model profile resolution (.custom).
  8. Unrecognized subcommand drift test.
  9. Real CLI binary availability check.
"""

import os
import shutil
import pytest
from pathlib import Path

import sys
SYS_DIR = Path(__file__).parent.parent.parent.resolve()
CLI_DIR = SYS_DIR / "cli"
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import peer_console
from peer_console import (
    InvocationKind,
    ConsoleLaunch,
    SecurityValidationError,
    prepare_console_launch,
)


class TestC8BConsolidation:
    """Test C8-B prepare_console_launch API and security consolidation."""

    def test_console_launch_dataclass_shape(self):
        launch = prepare_console_launch("cx", ["exec", "prompt"])
        assert isinstance(launch, ConsoleLaunch)
        assert launch.peer_id == "cx"
        assert launch.invocation_kind == InvocationKind.LOCAL_AGENT
        assert isinstance(launch.final_argv, list)
        assert "-s" in launch.final_argv
        assert launch.effective_model is not None
        assert launch.effective_profile.startswith("cx.")
        assert launch.banner_message is not None

    def test_local_agent_command_matrix(self):
        cases = [
            ("cx", ["exec", "prompt"], InvocationKind.LOCAL_AGENT, "-s"),
            ("cx", ["review", "--uncommitted"], InvocationKind.LOCAL_AGENT, "-s"),
            ("cx", ["resume", "123"], InvocationKind.LOCAL_AGENT, "-s"),
            ("cx", ["fork", "456"], InvocationKind.LOCAL_AGENT, "-s"),
            ("cx", ["my plain prompt"], InvocationKind.LOCAL_AGENT, "-s"),
            ("cc", ["interactive prompt"], InvocationKind.LOCAL_AGENT, "--dangerously-skip-permissions"),
            ("ag", ["interactive prompt"], InvocationKind.LOCAL_AGENT, "--dangerously-skip-permissions"),
        ]
        for peer, args, expected_kind, expected_flag in cases:
            launch = prepare_console_launch(peer, args)
            assert launch.invocation_kind == expected_kind
            assert expected_flag in launch.final_argv
            assert launch.banner_message is not None

    def test_remote_agent_cloud_behavior(self):
        # Remote agent command (codex cloud exec)
        launch = prepare_console_launch("cx", ["cloud", "exec", "task"])
        assert launch.invocation_kind == InvocationKind.REMOTE_AGENT
        # Must NOT insert local sandbox flag -s workspace-write
        assert "-s" not in launch.final_argv
        assert "--sandbox" not in launch.final_argv
        # Independent cross-verification found the real `codex cloud exec`
        # subcommand rejects --model entirely ("error: unexpected argument
        # '--model' found" against the real installed binary) -- profile
        # defaults must never be inserted for REMOTE_AGENT.
        assert "--model" not in launch.final_argv
        assert launch.final_argv == ["cloud", "exec", "task"]
        # Must include remote banner
        assert launch.banner_message is not None
        assert "[remote-profile]" in launch.banner_message

    @pytest.mark.skipif(not shutil.which("codex.cmd") and not shutil.which("codex"),
                         reason="real codex CLI not installed in this environment")
    def test_remote_agent_cloud_exec_argv_accepted_by_real_parser(self):
        import subprocess
        codex_cmd = shutil.which("codex.cmd") or shutil.which("codex")
        launch = prepare_console_launch("cx", ["cloud", "exec", "--env", "test-env", "hello"])
        proc = subprocess.run(
            [codex_cmd, *launch.final_argv, "--help"], capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0, f"real codex rejected {launch.final_argv}: {proc.stderr}"

    def test_dangerous_value_via_ask_for_approval_flag_rejected(self, monkeypatch):
        """Independent cross-verification found -a/--ask-for-approval was
        missing from _DANGEROUS_VALUE_FLAGS: `exec -a danger-full-access`
        both bypassed the forbidden-arg check (the value was scanned as an
        unmonitored bare positional) AND suppressed the -s workspace-write
        default (since _has_flag saw -a present and assumed an explicit
        safe choice)."""
        monkeypatch.delenv("ALLOW_BREAK_GLASS_DANGER_ACCESS", raising=False)
        with pytest.raises(SecurityValidationError):
            prepare_console_launch("cx", ["exec", "-a", "danger-full-access", "do work"])
        with pytest.raises(SecurityValidationError):
            prepare_console_launch("cx", ["exec", "--ask-for-approval", "danger-full-access", "x"])
        # A legitimate approval-policy value must still pass through untouched.
        launch = prepare_console_launch("cx", ["exec", "-a", "on-request", "prompt"])
        assert "-a" in launch.final_argv and "on-request" in launch.final_argv

    def test_forbidden_args_check_excludes_terminator_tail(self):
        """Independent cross-verification found _check_forbidden_args scanned
        the FULL final_argv including content after a literal '--', so
        legitimate prompt text starting with a dash placed after the
        terminator (e.g. `codex exec -- -yolo`) was wrongly blocked -- '--'
        marks everything after it as positional per POSIX/clap convention."""
        launch = prepare_console_launch("cx", ["exec", "--", "-yolo"])
        assert launch.final_argv[-2:] == ["--", "-yolo"]

    def test_admin_and_help_commands_get_no_defaults_or_banner(self):
        admin_cases = [
            ("cx", ["delete", "session-123"]),
            ("cx", ["login"]),
            ("cx", ["mcp"]),
            ("cc", ["doctor"]),
            ("ag", ["models"]),
        ]
        for peer, args in admin_cases:
            launch = prepare_console_launch(peer, args)
            assert launch.invocation_kind == InvocationKind.ADMIN_OR_SERVICE
            assert launch.final_argv == args
            assert launch.banner_message is None

        help_cases = [
            ("cx", ["exec", "--help"]),
            ("cc", ["-h"]),
            ("ag", ["--version"]),
        ]
        for peer, args in help_cases:
            launch = prepare_console_launch(peer, args)
            assert launch.invocation_kind == InvocationKind.HELP_OR_VERSION
            assert launch.final_argv == args
            assert launch.banner_message is None

    def test_forbidden_args_check_ignores_bare_positional_prompt_text(self, monkeypatch):
        """cc's cold review found a real false positive in an earlier draft:
        _check_forbidden_args scanned EVERY argv token indiscriminately, so a
        completely innocuous one-word prompt matching a dangerous keyword
        (e.g. `codex exec "yolo"`) was blocked as if it were the actual
        --yolo flag. Must only match genuine flag usage (leading dash) or
        the value immediately following a known sandbox/approval flag."""
        monkeypatch.delenv("ALLOW_BREAK_GLASS_DANGER_ACCESS", raising=False)
        for bare_prompt in ("yolo", "full-auto", "danger-full-access",
                             "dangerously-bypass-approvals-and-sandbox"):
            launch = prepare_console_launch("cx", ["exec", bare_prompt])
            assert bare_prompt in launch.final_argv

    def test_forbidden_args_runtime_rejection_and_break_glass(self, monkeypatch):
        monkeypatch.delenv("ALLOW_BREAK_GLASS_DANGER_ACCESS", raising=False)

        # Rejection by default for forbidden flags
        with pytest.raises(SecurityValidationError) as exc_info:
            prepare_console_launch("cx", ["exec", "--dangerously-bypass-approvals-and-sandbox", "prompt"])
        assert "Forbidden security argument" in str(exc_info.value)

        with pytest.raises(SecurityValidationError):
            prepare_console_launch("cx", ["exec", "-s", "danger-full-access", "prompt"])

        # Acceptance when break-glass env var is set
        monkeypatch.setenv("ALLOW_BREAK_GLASS_DANGER_ACCESS", "1")
        launch = prepare_console_launch("cx", ["exec", "--dangerously-bypass-approvals-and-sandbox", "prompt"])
        assert "--dangerously-bypass-approvals-and-sandbox" in launch.final_argv

    def test_truthful_banner_custom_profile_resolution(self):
        # Passing an explicit unlisted model must resolve to .custom profile
        launch = prepare_console_launch("cx", ["exec", "--model", "custom-experimental-model", "prompt"])
        assert launch.effective_model == "custom-experimental-model"
        assert launch.effective_profile == "cx.custom"
        assert "cx.custom" in launch.banner_message
        assert "--model custom-experimental-model" in launch.banner_message

    def test_unrecognized_subcommand_classification_drift(self):
        """Unrecognized subcommand drift check."""
        # Unrecognized top-level positional arg defaults to LOCAL_AGENT (plain prompt)
        launch = prepare_console_launch("cx", ["unrecognized_subcommand_123"])
        assert launch.invocation_kind == InvocationKind.LOCAL_AGENT
        assert "-s" in launch.final_argv

    def test_real_cli_binary_verifications(self):
        """Every peer resolved by prepare_console_launch has a real installed
        binary at the path the entry points actually invoke -- a tautological
        `x is not None or Path(x).exists()` check (an earlier draft's
        version) is always True regardless of whether the file exists, and
        provides zero real verification."""
        candidates = {
            "cx": SYS_DIR / "env" / "nodejs" / "npm-global" / "codex.cmd",
            "cc": SYS_DIR / "env" / "nodejs" / "npm-global" / "claude.cmd",
            "ag": SYS_DIR / "tools" / "agy" / "agy.exe",
        }
        for peer_id, expected_path in candidates.items():
            resolved = shutil.which(expected_path.stem) is not None or expected_path.exists()
            assert resolved, f"{peer_id}'s real CLI binary not found at {expected_path} or on PATH"
