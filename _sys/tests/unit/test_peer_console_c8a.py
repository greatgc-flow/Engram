"""
Unit Tests for Cluster C8-A (peer_console.py Codex Security Hotfix & Root-Scope Flag Insertion)

Covers:
  (a) Agent commands (exec, review, resume, fork) get -s workspace-write inserted BEFORE the subcommand.
  (b) Explicit user sandbox/approval flags (-s danger-full-access, --ask-for-approval) are preserved untouched.
  (c) Admin commands (delete, login, mcp) bypass defaults and return argv unchanged.
  (d) Flag-atomicity fix: bare 'workspace-write' string as a positional argument does not falsely suppress -s insertion.
  (e) Root plain prompt ('codex "prompt"') receives root-scope sandbox insertion & profile defaults.
  (f) Help and version flags (--help, -v) short-circuit without mutating args.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).parent.parent.parent.resolve()
CLI_DIR = SYS_DIR / "cli"
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import peer_console

_CODEX_CMD = shutil.which("codex.cmd") or shutil.which("codex")


class TestC8ACodexSecurityDefaults:
    """Test C8-A Codex security flag insertion and command classification."""

    def test_agent_commands_get_sandbox_inserted_before_subcommand(self):
        # -s workspace-write AND the root-only profile defaults (--model,
        # -c model_reasoning_effort=...) must both land before the
        # subcommand token, as one combined root-scope block -- codex
        # rejects '--model'/'-c ...' appended after the subcommand exactly
        # like it rejects '-s workspace-write' there (live-verified:
        # 'codex review --uncommitted --model X' exits 2, "unexpected
        # argument '--model'").
        cases = [
            ["exec", "prompt"],
            ["review", "--uncommitted"],
            ["resume", "session-123"],
            ["fork", "session-456"],
            ["e", "quick prompt"],
        ]
        for input_args in cases:
            res = peer_console.peer_default_args("cx", input_args)
            assert res[0] == "-s" and res[1] == "workspace-write", f"Failed for {input_args}: got {res}"
            subcommand_idx = res.index(input_args[0])
            # Nothing from the original argv appears before the subcommand
            # token -- only inserted root-scope defaults precede it.
            assert res[:subcommand_idx + 1] == res[:subcommand_idx] + [input_args[0]]
            assert all(flag in res[:subcommand_idx] for flag in ("-s", "workspace-write", "--model"))
            # Everything after the subcommand is the original trailing argv, untouched and in order.
            assert res[subcommand_idx:subcommand_idx + len(input_args)] == input_args

    def test_user_explicit_sandbox_flags_preserved(self, monkeypatch):
        monkeypatch.setenv("ALLOW_BREAK_GLASS_DANGER_ACCESS", "1")
        # An explicit user sandbox/approval choice must never be overridden
        # or duplicated -- but root-only profile defaults (--model, ...) are
        # an independent axis and still get inserted at root scope.
        cases = [
            ["exec", "-s", "danger-full-access", "prompt"],
            ["review", "--ask-for-approval"],
            ["resume", "--dangerously-bypass-approvals-and-sandbox", "123"],
            ["fork", "--sandbox", "read-only", "456"],
            # -a/--ask-for-approval takes a value (<APPROVAL_POLICY>,
            # live-verified via `codex --help`) -- a bare "-a exec" would
            # have "exec" consumed as -a's value, not recognized as the
            # subcommand at all, so the value must be realistic here.
            ["-a", "on-request", "exec", "prompt"],
        ]
        for input_args in cases:
            res = peer_console.peer_default_args("cx", input_args)
            # Must NOT insert another -s workspace-write
            assert res.count("-s") <= 1
            assert "workspace-write" not in res
            # The user's own explicit tokens all survive, in their original
            # relative order.
            search_from = 0
            for token in input_args:
                idx = res.index(token, search_from)
                search_from = idx + 1

    def test_delete_command_bypasses_defaults_and_banner(self):
        input_args = ["delete", "session-789"]
        res = peer_console.peer_default_args("cx", input_args)
        assert res == input_args

    def test_admin_commands_bypass_defaults(self):
        admin_cmds = ["login", "logout", "mcp", "app-server", "doctor", "sandbox"]
        for cmd in admin_cmds:
            input_args = [cmd]
            res = peer_console.peer_default_args("cx", input_args)
            assert res == input_args, f"Admin command '{cmd}' should return unchanged, got {res}"

    def test_bare_workspace_write_string_does_not_suppress_flag_insertion(self):
        # Position argument containing bare string 'workspace-write'
        input_args = ["exec", "clean files in workspace-write directory"]
        res = peer_console.peer_default_args("cx", input_args)

        # Flag -s workspace-write MUST be inserted despite 'workspace-write' string being present
        assert res[:2] == ["-s", "workspace-write"]
        assert "clean files in workspace-write directory" in res

    def test_plain_prompt_root_invocation(self):
        input_args = ["my plain prompt"]
        res = peer_console.peer_default_args("cx", input_args)

        assert res[0] == "-s"
        assert res[1] == "workspace-write"
        assert "my plain prompt" in res

    def test_help_and_version_short_circuit(self):
        for help_flag in ["--help", "-h", "--version", "-v"]:
            input_args = ["exec", help_flag]
            res = peer_console.peer_default_args("cx", input_args)
            assert res == input_args

    def test_profile_defaults_inserted_at_root_not_after_subcommand(self):
        """Independent cross-verification (cx, 2026-07-26) found this as a
        release-blocking regression: appending --model/-c after the
        subcommand (the old _append_profile_defaults behavior) produces
        argv the real codex CLI rejects for review/exec/resume/fork, exactly
        like appending -s workspace-write there does. Both must be inserted
        together, at the same root-scope point, before the subcommand."""
        res = peer_console.peer_default_args("cx", ["review", "--uncommitted"])
        subcommand_idx = res.index("review")
        assert "--model" in res[:subcommand_idx]
        assert res[subcommand_idx:] == ["review", "--uncommitted"]

    @pytest.mark.skipif(not _CODEX_CMD, reason="real codex CLI not installed in this environment")
    def test_review_argv_is_accepted_by_the_real_parser(self):
        res = peer_console.peer_default_args("cx", ["review", "--uncommitted"])
        proc = subprocess.run(
            [_CODEX_CMD, *res, "--help"], capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0, f"real codex rejected {res}: {proc.stderr}"

    def test_option_terminator_excludes_trailing_tokens_from_insertion(self):
        # Independent cross-verification (cx) found the terminator bypass:
        # tokens after a literal '--' are positional per POSIX/clap
        # convention and must never be scanned for flags/help, nor have
        # defaults inserted after it.
        res = peer_console.peer_default_args("cx", ["exec", "--", "--help"])
        assert res[0] == "-s" and res[1] == "workspace-write"
        assert res[-2:] == ["--", "--help"]

        # A leading terminator: nothing before it to insert into-place
        # relative to, but the sandbox default must still take effect as a
        # REAL root option -- inserted before '--', never after it (the old
        # bug: flags landed after '--' and became inert positional noise).
        res2 = peer_console.peer_default_args("cx", ["--", "hello"])
        term_idx = res2.index("--")
        assert res2[term_idx:] == ["--", "hello"]
        assert "-s" in res2[:term_idx] and "workspace-write" in res2[:term_idx]

    def test_option_value_pair_not_split_by_root_insertion(self):
        # Independent cross-verification (cx) found ["--model","gpt-5","plain
        # prompt"] used to split the existing (--model, gpt-5) pair by
        # inserting new flags between them.
        res = peer_console.peer_default_args("cx", ["--model", "gpt-5", "plain prompt"])
        idx = res.index("--model")
        assert res[idx + 1] == "gpt-5", f"--model's own value was split apart: {res}"

    def test_concatenated_short_alias_recognized(self):
        # Independent cross-verification (cx): codex accepts concatenated
        # short-flag forms like '-sread-only'; _has_flag must recognize
        # these so a redundant conflicting -s workspace-write isn't injected
        # alongside the user's own explicit choice.
        res = peer_console.peer_default_args("cx", ["exec", "-sread-only", "prompt"])
        assert res.count("-s") <= 1
        assert "workspace-write" not in res
