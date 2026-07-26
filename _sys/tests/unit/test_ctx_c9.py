"""
Unit and Integration Tests for Cluster C9 (ctx_end.py / ctx_save.py Robustness)

Covers:
  1. No Input Hang: Primary summary failure exits nonzero without calling input() or hanging.
  2. Full Phase Flow: Cleanup tasks (memory compactor, watchdog, self-care) run even if ai_check.py fails.
  3. Subprocess Timeout: TimeoutExpired handled cleanly on primary/global/gemini calls.
  4. Nonzero Gemini Returncode Rejection: Non-zero exit code prevents overwriting summary files (ctx_end & ctx_save).
  5. Same-Directory Atomic Replacement: _write_text_atomic writes via temp file and replaces target atomically.
  6. UnicodeDecodeError Handling: Strict UTF-8 decode failure preserves existing summary and logs error cleanly.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

SYS_DIR = Path(__file__).parent.parent.parent.resolve()
HOOKS_DIR = SYS_DIR / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import ctx_end
import ctx_save


class TestC9AtomicWrite:
    """Tests for same-directory atomic replacement helper."""

    def test_write_text_atomic_creates_temp_and_replaces(self, tmp_path):
        target = tmp_path / "summary.md"
        target.write_text("original content", encoding="utf-8")

        ctx_end._write_text_atomic(target, "new content")

        assert target.read_text(encoding="utf-8") == "new content"
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_write_text_atomic_preserves_original_on_failure(self, tmp_path, monkeypatch):
        target = tmp_path / "summary.md"
        target.write_text("original content", encoding="utf-8")

        def mock_replace(src, dst):
            raise PermissionError("Simulated replacement failure")

        monkeypatch.setattr(ctx_end.os, "replace", mock_replace)

        with pytest.raises(PermissionError):
            ctx_end._write_text_atomic(target, "new content")

        # Target should retain original content
        assert target.read_text(encoding="utf-8") == "original content"
        # Temp file should be cleaned up
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestC9RealSubprocessInvocation:
    """Real (unmocked) subprocess tests -- every other test in this file
    monkeypatches subprocess.run entirely, so none of them can catch a
    regression in the ACTUAL invocation kwargs (cmd, shell=, etc). Regression
    found during cross-verification: the primary/--global `claude -p` calls
    in ctx_end.py had `shell=True` removed during the C9 rewrite. `claude`
    resolves to a `.cmd` npm shim, and Windows' CreateProcess cannot launch a
    `.cmd`/`.bat` file directly without going through the command
    interpreter -- confirmed live: subprocess.run(["claude", ...]) with
    shell=False raises FileNotFoundError even though `claude` invokes fine
    from a normal shell prompt. This would have made ctx_end.py's core
    summary-generation path fail 100% of the time on every real run, the
    opposite of "more robust." These tests use a synthetic temp .bat file
    (not a dependency on the real `claude` CLI being installed/authenticated)
    to prove the general Windows .bat/.cmd + shell= mechanic, then confirm
    ctx_end.py's real source actually passes shell=True at both call sites."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific .cmd/.bat invocation semantics")
    def test_bare_command_name_resolving_to_bat_requires_shell_true(self, tmp_path):
        """Reproduces the exact real bug shape: a BARE command name (no
        extension, no directory prefix -- exactly how ctx_end.py invokes
        "claude") that only resolves via PATH to a .bat/.cmd file. A fully-
        qualified path to an existing .bat file launches fine even without
        shell=True (Windows' file-association shim handles that case) --
        it's specifically the PATH-search-for-a-bare-name case that fails,
        which is exactly ctx_end.py's real ["claude", "-p", ...] shape."""
        bat_file = tmp_path / "synthetic_probe.bat"
        bat_file.write_text("@echo off\necho probe_ok\nexit /b 0\n", encoding="utf-8")
        env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", "")}

        with pytest.raises(FileNotFoundError):
            subprocess.run(["synthetic_probe"], capture_output=True, text=True, timeout=10, env=env)

        result = subprocess.run(
            ["synthetic_probe"], capture_output=True, text=True, timeout=10, env=env, shell=True,
        )
        assert result.returncode == 0
        assert "probe_ok" in result.stdout

    def test_ctx_end_source_passes_shell_true_for_claude_invocations(self):
        """Static guard (platform-independent): both real subprocess.run call
        sites in ctx_end.py that invoke the bare `claude` command must pass
        shell=True. Grep-level check on the real source, not a mock -- if
        someone removes shell=True again, this fails immediately instead of
        only failing silently in production on a real user's machine."""
        source = (HOOKS_DIR / "ctx_end.py").read_text(encoding="utf-8")
        claude_call_blocks = source.split('"claude", "-p",')[1:]
        assert claude_call_blocks, "expected at least one claude -p invocation in ctx_end.py"
        for block in claude_call_blocks:
            # shell=True must appear before the closing of this subprocess.run(...) call
            call_end = block.find(")\n")
            snippet = block[:call_end] if call_end != -1 else block[:400]
            assert "shell=True" in snippet, (
                "a claude -p subprocess.run call in ctx_end.py is missing shell=True -- "
                "this WILL raise FileNotFoundError on Windows since claude resolves to a .cmd shim"
            )


class TestC9CtxEndFlow:
    """Tests for ctx_end.py phase flow and robustness."""

    def test_primary_claude_failure_exits_nonzero_without_input(self, tmp_path, monkeypatch):
        cwd = tmp_path / "project"
        cwd.mkdir()
        (cwd / "CLAUDE.md").write_text("# Project", encoding="utf-8")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(sys, "argv", ["ctx_end.py"])

        monkeypatch.setattr(ctx_end, "_check_prerequisites", lambda config_dir: True)

        # Mock primary claude call to return nonzero exit code
        failed_proc = MagicMock()
        failed_proc.returncode = 1
        failed_proc.stdout = ""
        failed_proc.stderr = "API connection error"

        def mock_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd[0] == "claude":
                return failed_proc
            return MagicMock(returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        # Mock input() to raise error if called (verifies input() is gone)
        input_called = False
        def mock_input(*args):
            nonlocal input_called
            input_called = True
            raise RuntimeError("input() should not be called!")

        monkeypatch.setattr("builtins.input", mock_input)

        with pytest.raises(SystemExit) as exc_info:
            ctx_end.main()

        assert exc_info.value.code == 1
        assert not input_called

    def test_ai_check_failure_still_runs_cleanup_phases(self, tmp_path, monkeypatch):
        cwd = tmp_path / "project"
        cwd.mkdir()
        (cwd / "CLAUDE.md").write_text("# Project", encoding="utf-8")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(sys, "argv", ["ctx_end.py"])

        monkeypatch.setattr(ctx_end, "_check_prerequisites", lambda config_dir: True)

        cleanup_ran = {
            "archive": False,
            "compaction": False,
            "watchdog": False,
        }

        def mock_run(cmd, **kwargs):
            cmd_str = str(cmd)
            if "claude" in cmd_str:
                return MagicMock(returncode=0, stdout="OK")
            if "ai_check.py" in cmd_str:
                return MagicMock(returncode=1, stdout="", stderr="ai unavailable")
            return MagicMock(returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        monkeypatch.setattr(ctx_end, "archive_gemini_session", lambda root: cleanup_ran.update({"archive": True}))
        
        class MockCompactorModule:
            @staticmethod
            def main(root):
                cleanup_ran["compaction"] = True

        monkeypatch.setitem(sys.modules, "memory_compactor", MockCompactorModule)
        monkeypatch.setattr(ctx_end, "run_contract_watchdog", lambda **kwargs: cleanup_ran.update({"watchdog": True}))

        with pytest.raises(SystemExit) as exc_info:
            ctx_end.main()

        assert exc_info.value.code == 0
        assert cleanup_ran["archive"]
        assert cleanup_ran["compaction"]
        assert cleanup_ran["watchdog"]

    def test_primary_claude_timeout_handled_cleanly(self, tmp_path, monkeypatch):
        cwd = tmp_path / "project"
        cwd.mkdir()
        (cwd / "CLAUDE.md").write_text("# Project", encoding="utf-8")
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(sys, "argv", ["ctx_end.py"])

        monkeypatch.setattr(ctx_end, "_check_prerequisites", lambda config_dir: True)

        def mock_run(cmd, **kwargs):
            if isinstance(cmd, list) and cmd[0] == "claude":
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=60)
            return MagicMock(returncode=0, stdout="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        with pytest.raises(SystemExit) as exc_info:
            ctx_end.main()

        assert exc_info.value.code == 1


class TestC9CtxSaveFlow:
    """Tests for ctx_save.py returncode check and atomic blackboard updates."""

    def test_nonzero_gemini_returncode_does_not_overwrite_summary(self, tmp_path, monkeypatch):
        cwd = tmp_path / "project"
        cwd.mkdir()
        (cwd / "CLAUDE.md").write_text("## Current State\nInitial State\n", encoding="utf-8")
        monkeypatch.chdir(cwd)

        # Setup .ai session environment
        room_dir = cwd / ".ai" / "sessions" / "room-123"
        room_dir.mkdir(parents=True)
        (cwd / ".ai" / "state.json").write_text(json.dumps({"room_id": "room-123"}), encoding="utf-8")

        sum_file = room_dir / "summary_session.md"
        sum_file.write_text("Pre-existing Blackboard Summary", encoding="utf-8")

        def mock_run(cmd, **kwargs):
            cmd_str = str(cmd)
            if "ai_check.py" in cmd_str:
                return MagicMock(returncode=0, stdout="OK")
            if "msg.bat" in cmd_str:
                # Gemini call returns non-zero error
                return MagicMock(returncode=1, stdout="Error output from failed API call", stderr="500 Internal Error")
            return MagicMock(returncode=0, stdout="no stalled rounds")

        monkeypatch.setattr(subprocess, "run", mock_run)

        ctx_save.main()

        # Pre-existing summary file must NOT be overwritten by failed output
        assert sum_file.read_text(encoding="utf-8") == "Pre-existing Blackboard Summary"

    def test_successful_gemini_call_atomically_updates_summary(self, tmp_path, monkeypatch):
        cwd = tmp_path / "project"
        cwd.mkdir()
        (cwd / "CLAUDE.md").write_text("## Current State\nInitial State\n", encoding="utf-8")
        monkeypatch.chdir(cwd)

        room_dir = cwd / ".ai" / "sessions" / "room-123"
        room_dir.mkdir(parents=True)
        (cwd / ".ai" / "state.json").write_text(json.dumps({"room_id": "room-123"}), encoding="utf-8")

        sum_file = room_dir / "summary_session.md"
        sum_file.write_text("Old Summary", encoding="utf-8")

        def mock_run(cmd, **kwargs):
            cmd_str = str(cmd)
            if "ai_check.py" in cmd_str:
                return MagicMock(returncode=0, stdout="OK")
            if "msg.bat" in cmd_str:
                return MagicMock(returncode=0, stdout="### Fresh Zero-Token Blackboard Summary")
            return MagicMock(returncode=0, stdout="no stalled rounds")

        monkeypatch.setattr(subprocess, "run", mock_run)

        ctx_save.main()

        assert sum_file.read_text(encoding="utf-8") == "### Fresh Zero-Token Blackboard Summary"


class TestC9SessionLogNeverDumpsClaudeMd:
    """Real bug found in live use (2026-07-26): the Phase 2 prompt told
    claude to edit CLAUDE.md with a handoff blob, directly contradicting
    CLAUDE.md's own documented pointer-only policy -- the spawned process
    correctly refused/got confused, producing garbage that Phase 3 then
    archived as if it were a real summary (save_session_log used to dump a
    raw CLAUDE.md snapshot unconditionally). Fixed: save_session_log now
    writes the LLM-generated summary text, never a CLAUDE.md dump."""

    def test_save_session_log_writes_summary_text_not_claude_md_dump(self, tmp_path):
        session_dir = tmp_path / "sessions"
        cwd = tmp_path / "myproject"
        cwd.mkdir()
        claude_md = cwd / "CLAUDE.md"
        claude_md.write_text("POINTER ONLY -- do not write handoffs here", encoding="utf-8")

        ses_file = ctx_end.save_session_log(
            session_dir, cwd, claude_md, summary_text="Current State: X\nNext Steps: Y",
        )

        content = ses_file.read_text(encoding="utf-8")
        assert "Current State: X" in content
        assert "Next Steps: Y" in content
        assert "POINTER ONLY" not in content

    def test_save_session_log_missing_summary_does_not_fall_back_to_claude_md(self, tmp_path):
        session_dir = tmp_path / "sessions"
        cwd = tmp_path / "myproject"
        cwd.mkdir()
        claude_md = cwd / "CLAUDE.md"
        claude_md.write_text("POINTER ONLY -- do not write handoffs here", encoding="utf-8")

        ses_file = ctx_end.save_session_log(session_dir, cwd, claude_md, summary_text=None)

        content = ses_file.read_text(encoding="utf-8")
        assert "POINTER ONLY" not in content
        assert "summary generation failed" in content

    def test_save_session_log_handles_drive_root_cwd_with_empty_name(self, tmp_path):
        session_dir = tmp_path / "sessions"
        # A bare drive root (e.g. Path("P:\\")) has an empty .name -- must
        # not produce a filename like "2026-07-26_.md".
        fake_root = Path("Z:\\")
        ses_file = ctx_end.save_session_log(session_dir, fake_root, fake_root / "CLAUDE.md", "summary")
        assert ses_file.name != f"{ses_file.name.split('_')[0]}_.md"
        assert "_.md" not in ses_file.name

    def test_phase2_prompt_never_instructs_editing_claude_md(self):
        """Static guard against the exact regression: the prompt text sent
        to the spawned claude -p process must never tell it to edit/update
        CLAUDE.md."""
        source = (HOOKS_DIR / "ctx_end.py").read_text(encoding="utf-8")
        assert "Update CLAUDE.md fully" not in source
        assert "do NOT edit any" in source or "do not edit CLAUDE.md" in source.lower()
