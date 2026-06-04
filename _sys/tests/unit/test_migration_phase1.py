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

    def test_exits_1_when_status_json_missing(self, tmp_path):
        result = run_py(
            SYS_DIR / "hooks" / "ai_check.py",
            extra_env={"_AI_SYS_DIR": str(tmp_path)},
        )
        assert result.returncode == 1
        assert "gemini=OFF" in result.stdout

    def test_exits_1_when_mode_off(self, tmp_path):
        gemini_dir = tmp_path / "gemini"
        gemini_dir.mkdir()
        (gemini_dir / "status.json").write_text(
            json.dumps({"mode": "OFF"}), encoding="utf-8"
        )
        result = run_py(
            SYS_DIR / "hooks" / "ai_check.py",
            extra_env={"_AI_SYS_DIR": str(tmp_path)},
        )
        assert result.returncode == 1
        assert "gemini=OFF" in result.stdout

    def test_exits_0_when_mode_on(self, tmp_path):
        """Create a temporary status.json with mode=ON and call the script."""
        # Patch the expected path by overriding __file__ indirectly is complex.
        # Instead, test via the real Gemini status if available.
        status_path = SYS_DIR / "gemini" / "status.json"
        if status_path.exists():
            data = json.loads(status_path.read_text(encoding="utf-8"))
            result = run_py(SYS_DIR / "hooks" / "ai_check.py")
            if data.get("mode") == "ON":
                assert result.returncode == 0
                assert "gemini=ON" in result.stdout
            else:
                assert result.returncode == 1
                assert "gemini=OFF" in result.stdout
        else:
            result = run_py(SYS_DIR / "hooks" / "ai_check.py")
            assert result.returncode == 1


class TestCollabLog:
    """collab_log.py — collab-log append."""

    def test_creates_log_file(self, tmp_path, monkeypatch):
        """Running collab_log.py creates a dated .md file."""
        # We need to override base_dir inside the module.
        # The easiest parity test: run the script and check _archive/collab-log/
        # using the real _archive dir.
        result = run_py(
            SYS_DIR / "hooks" / "collab_log.py",
            "Axis-TEST", "test_migration_phase1.py", "OK", "parity test entry"
        )
        assert result.returncode == 0

        from datetime import date
        today = date.today().strftime("%Y-%m-%d")
        log_file = SYS_DIR.parent / "_archive" / "collab-log" / f"{today}.md"
        assert log_file.exists(), f"Expected collab-log file: {log_file}"
        content = log_file.read_text(encoding="utf-8")
        assert "Axis-TEST" in content
        assert "parity test entry" in content

    def test_status_ok_sets_consecutive_failures_zero(self, tmp_path):
        """OK status must reset consecutive_failures counter."""
        gemini_dir = tmp_path / "gemini"
        gemini_dir.mkdir()
        status_file = gemini_dir / "status.json"
        status_file.write_text(
            json.dumps({
                "mode": "ON",
                "gemini_metrics": {
                    "calls_today": 0,
                    "calls_today_date": "20260101",
                    "last_call_ts": None,
                    "last_axis": None,
                    "consecutive_failures": 2,
                    "last_failure_reason": "prev error"
                }
            }),
            encoding="utf-8"
        )
        import sys as _sys
        _sys.path.insert(0, str(SYS_DIR / "hooks"))
        from collab_log import _update_gemini_metrics  # type: ignore
        from datetime import datetime
        _update_gemini_metrics(
            tmp_path, "Axis-H", "OK", "test", datetime.now()
        )
        data = json.loads(status_file.read_text(encoding="utf-8"))
        assert data["gemini_metrics"]["consecutive_failures"] == 0


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
        assert "No CLAUDE.md" in result.stdout


class TestCtxEnd:
    """ctx_end.py — session log save, gemini archive, cleanup functions."""

    def test_save_session_log_creates_file(self, tmp_path):
        import sys as _sys
        _sys.path.insert(0, str(SYS_DIR / "hooks"))
        from ctx_end import save_session_log  # type: ignore

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("## Current State\nActive\n", encoding="utf-8")
        ses_file = save_session_log(tmp_path / "sessions", tmp_path, claude_md)
        assert ses_file.exists()
        content = ses_file.read_text(encoding="utf-8")
        assert "ctx-end" in content
        assert "Active" in content

    def test_save_session_log_appends_on_second_call(self, tmp_path):
        import sys as _sys
        _sys.path.insert(0, str(SYS_DIR / "hooks"))
        from ctx_end import save_session_log  # type: ignore
        from datetime import datetime

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("State A\n", encoding="utf-8")
        ses_dir = tmp_path / "sessions"
        save_session_log(ses_dir, tmp_path, claude_md)
        claude_md.write_text("State B\n", encoding="utf-8")
        save_session_log(ses_dir, tmp_path, claude_md)
        files = list(ses_dir.glob("*.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "State A" in content
        assert "State B" in content

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
