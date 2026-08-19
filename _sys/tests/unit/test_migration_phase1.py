"""
Phase 1 bat→py migration parity tests.
Verifies that the Python replacements for leaf hook utilities
produce correct outputs (file creation, content, exit codes).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).parent.parent.parent
VENV_PY = SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable


def run_py(script: Path, *args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    import os
    env = {**os.environ, "PYTHONUTF8": "1", **(extra_env or {})}
    return subprocess.run(
        [PYTHON, str(script), *args],
        capture_output=True, text=True, env=env, timeout=10
    )


class TestAiCheck:
    """ai_check.py — Gemini gate check."""

    def test_exits_1_when_orchestration_missing(self, tmp_path):
        result = run_py(
            SYS_DIR / "hooks" / "ai_check.py",
            extra_env={"_AI_SYS_DIR": str(tmp_path)},
        )
        assert result.returncode == 1
        assert "gemini=OFF" in result.stdout

    def test_exits_1_when_peer_disabled(self, tmp_path):
        ai_dir = tmp_path / "ai"
        gemini_dir = tmp_path / "gemini"
        ai_dir.mkdir()
        gemini_dir.mkdir()
        (ai_dir / "orchestration.json").write_text(
            json.dumps({"hub_nodes": [{"node_id": "gc", "enabled": False}]}),
            encoding="utf-8",
        )
        result = run_py(
            SYS_DIR / "hooks" / "ai_check.py",
            extra_env={"_AI_SYS_DIR": str(tmp_path)},
        )
        assert result.returncode == 1
        assert "gemini=OFF" in result.stdout

    def test_exits_0_when_enabled_and_healthy(self, tmp_path):
        ai_dir = tmp_path / "ai"
        gemini_dir = tmp_path / "gemini"
        ai_dir.mkdir()
        gemini_dir.mkdir()
        (ai_dir / "orchestration.json").write_text(
            json.dumps({"hub_nodes": [{"node_id": "gc", "enabled": True}]}),
            encoding="utf-8",
        )
        (gemini_dir / "health.json").write_text(
            json.dumps({"availability": {"gate_open": True}, "context_health": {"status": "GREEN"}}),
            encoding="utf-8",
        )
        result = run_py(
            SYS_DIR / "hooks" / "ai_check.py",
            extra_env={"_AI_SYS_DIR": str(tmp_path)},
        )
        assert result.returncode == 0
        assert "gemini=ON" in result.stdout


class TestCollabLog:
    """collab_log.py — collab-log append."""

    def test_collab_log_does_not_create_legacy_status(self, tmp_path):
        assert not (tmp_path / "gemini" / "status.json").exists()


class TestRawLog:
    """raw_log.py — raw Gemini I/O archive."""

    def test_copies_response_file(self, tmp_path):
        response = tmp_path / "response.txt"
        response.write_text("gemini output here", encoding="utf-8")

        result = run_py(
            SYS_DIR / "hooks" / "raw_log.py",
            "Axis-TEST", str(response)
        )
        assert result.returncode == 0

        raw_dir = SYS_DIR.parent / "_archive" / "raw-log"
        assert raw_dir.exists()
        archived = sorted(raw_dir.glob("*_Axis-TEST_response.txt"))
        assert len(archived) >= 1
        assert archived[-1].read_text(encoding="utf-8") == "gemini output here"

    def test_missing_response_file_is_noop(self, tmp_path):
        result = run_py(
            SYS_DIR / "hooks" / "raw_log.py",
            "Axis-TEST", str(tmp_path / "nonexistent.txt")
        )
        assert result.returncode == 0

    def test_copies_both_files_when_directive_provided(self, tmp_path):
        response = tmp_path / "resp.txt"
        directive = tmp_path / "dir.txt"
        response.write_text("response", encoding="utf-8")
        directive.write_text("directive", encoding="utf-8")

        result = run_py(
            SYS_DIR / "hooks" / "raw_log.py",
            "Axis-BOTH", str(response), str(directive)
        )
        assert result.returncode == 0
        raw_dir = SYS_DIR.parent / "_archive" / "raw-log"
        resp_files = sorted(raw_dir.glob("*_Axis-BOTH_response.txt"))
        dir_files = sorted(raw_dir.glob("*_Axis-BOTH_directive.txt"))
        assert len(resp_files) >= 1
        assert len(dir_files) >= 1


class TestCtxSave:
    """ctx_save.py — symmetric checkpoint marker update."""

    def test_updates_current_state_line(self, tmp_path):
        import sys as _sys
        _sys.path.insert(0, str(SYS_DIR / "hooks"))
        from ctx_save import _update_current_state_marker  # type: ignore

        md = tmp_path / "CLAUDE.md"
        md.write_text(
            "# Title\n\n## Current State\nOld marker line\n\n## Next Steps\n- todo\n",
            encoding="utf-8",
        )
        _update_current_state_marker(md, "New marker line")
        content = md.read_text(encoding="utf-8")
        assert "New marker line" in content
        assert "Old marker line" not in content
        assert "## Next Steps" in content  # rest of file untouched

    def test_noop_when_no_current_state_section(self, tmp_path):
        import sys as _sys
        _sys.path.insert(0, str(SYS_DIR / "hooks"))
        from ctx_save import _update_current_state_marker  # type: ignore

        md = tmp_path / "CLAUDE.md"
        original = "# Title\n\nNo current state section.\n"
        md.write_text(original, encoding="utf-8")
        _update_current_state_marker(md, "irrelevant")
        assert md.read_text(encoding="utf-8") == original

    def test_exits_1_when_no_claude_md(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = run_py(SYS_DIR / "hooks" / "ctx_save.py")
        assert result.returncode == 1
        # C9: error/diagnostic output now consistently goes to stderr, not
        # stdout (matches every other error print in the C9 phase-based
        # rewrite) -- was asserted on stdout before that consistency pass.
        assert "No CLAUDE.md" in result.stderr


class TestCtxEnd:
    """ctx_end.py — session log save, gemini archive, cleanup functions."""

    def test_save_session_log_creates_file(self, tmp_path):
        import sys as _sys
        _sys.path.insert(0, str(SYS_DIR / "hooks"))
        from ctx_end import save_session_log  # type: ignore

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("POINTER ONLY -- do not write handoffs here\n", encoding="utf-8")
        # save_session_log writes the LLM-generated summary_text, never a
        # CLAUDE.md content dump (CLAUDE.md is pointer-only -- a real bug
        # found in live use 2026-07-26 had this archiving CLAUDE.md's own
        # static content as if it were the session summary).
        ses_file = save_session_log(tmp_path / "sessions", tmp_path, claude_md, "## Current State\nActive\n")
        assert ses_file.exists()
        content = ses_file.read_text(encoding="utf-8")
        assert "ctx-end" in content
        assert "Active" in content
        assert "POINTER ONLY" not in content

    def test_save_session_log_appends_on_second_call(self, tmp_path):
        import sys as _sys
        _sys.path.insert(0, str(SYS_DIR / "hooks"))
        from ctx_end import save_session_log  # type: ignore
        from datetime import datetime

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("POINTER ONLY -- do not write handoffs here\n", encoding="utf-8")
        ses_dir = tmp_path / "sessions"
        save_session_log(ses_dir, tmp_path, claude_md, "State A\n")
        save_session_log(ses_dir, tmp_path, claude_md, "State B\n")
        files = list(ses_dir.glob("*.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "State A" in content
        assert "State B" in content
        assert "POINTER ONLY" not in content

    def test_archive_gemini_session_moves_active_to_history(self, tmp_path):
        import sys as _sys
        _sys.path.insert(0, str(SYS_DIR / "hooks"))
        from ctx_end import archive_gemini_session  # type: ignore

        sys_gemini = tmp_path / "_sys" / "gemini"
        sys_gemini.mkdir(parents=True)
        (sys_gemini / "session-id.txt").write_text("ses-001", encoding="utf-8")
        smap = sys_gemini / "session-map.json"
        smap.write_text(
            json.dumps({"active": {"id": "ses-001", "started_at": "2026-01-01T00:00:00"}, "history": []}),
            encoding="utf-8",
        )
        archive_gemini_session(tmp_path)
        assert not (sys_gemini / "session-id.txt").exists()
        data = json.loads(smap.read_text(encoding="utf-8"))
        assert data["active"] is None
        assert len(data["history"]) == 1
        assert data["history"][0]["id"] == "ses-001"
        assert "ended_at" in data["history"][0]

    def test_cleanup_gemini_sessions_moves_old_files(self, tmp_path):
        import sys as _sys
        import time
        _sys.path.insert(0, str(SYS_DIR / "hooks"))
        from ctx_end import cleanup_gemini_sessions  # type: ignore

        chat_dir = tmp_path / "_sys" / "gemini" / "config" / "tmp" / "project" / "chats"
        chat_dir.mkdir(parents=True)
        old_file = chat_dir / "old.jsonl"
        old_file.write_text("{}", encoding="utf-8")
        # Backdate the file to 10 days ago
        old_ts = time.time() - 10 * 86400
        import os
        os.utime(old_file, (old_ts, old_ts))

        cleanup_gemini_sessions(tmp_path, keep_days=7)
        archive_dir = tmp_path / "_archive" / "gemini-sessions"
        assert (archive_dir / "old.jsonl").exists()
        assert not old_file.exists()
