"""Tests for T16 (design 2026-07-09 pretdd-prep, unanimous ag/cx/fable):
shared _common.validate_ai_json() + per-file real required-key schemas."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "checks"))

import _common  # noqa: E402
import check_health  # noqa: E402


SCHEMAS = {
    "health": ("version", "generated_at", "session_context", "executive_summary",
               "technical_state", "strategy_for_next_session"),
    "agents": ("scan_ts", "overlaps", "gaps", "inconsistencies", "ok_count"),
    "risk": ("agent", "timestamp", "task_summary", "risks", "overall_risk", "proceed"),
    "versions": ("ripgrep", "fd", "jq", "bat", "delta", "fzf", "oh-my-posh", "nodejs-lts"),
}


@pytest.mark.parametrize("required", SCHEMAS.values(), ids=SCHEMAS.keys())
def test_validate_ai_json_rejects_missing_real_schema_key(required):
    payload = {key: "ok" for key in required[:-1]}  # missing the last required key
    with pytest.raises(_common.ContractViolationError):
        _common.validate_ai_json(json.dumps(payload), required)


@pytest.mark.parametrize("required", SCHEMAS.values(), ids=SCHEMAS.keys())
def test_validate_ai_json_accepts_all_real_schema_keys(required):
    payload = {key: "ok" for key in required}
    result = _common.validate_ai_json(json.dumps(payload), required)
    assert all(key in result for key in required)


def test_validate_ai_json_extracts_fenced_json():
    assert _common.validate_ai_json("```json\n{\"ok\": true}\n```", ("ok",)) == {"ok": True}


def test_validate_ai_json_rejects_non_object():
    with pytest.raises(_common.ContractViolationError):
        _common.validate_ai_json("[1, 2, 3]", ("ok",))


def test_validate_ai_json_rejects_invalid_json():
    with pytest.raises(_common.ContractViolationError):
        _common.validate_ai_json("not json at all", ("ok",))


def test_check_health_invalid_handoff_does_not_overwrite_existing_file(monkeypatch, tmp_path):
    sys_dir = tmp_path / "_sys"
    monkeypatch.setattr(check_health, "_PORTABLE_ROOT", tmp_path)
    monkeypatch.setattr(check_health, "_SYS_DIR", sys_dir)

    project_dir = check_health._claude_project_dir(tmp_path)
    project_dir.mkdir(parents=True)
    (project_dir / "session.jsonl").write_text("session", encoding="utf-8")

    sessions_dir = tmp_path / "_archive" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "s.md").write_text("session log", encoding="utf-8")

    handoff_file = tmp_path / "_archive" / "session-handoff.json"
    handoff_file.write_text('{"keep": true}', encoding="utf-8")

    (sys_dir / "claude").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(check_health, "ai_available", lambda: True)
    monkeypatch.setattr(check_health, "archive_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(check_health, "log_collab", lambda *args, **kwargs: None)
    monkeypatch.setattr(check_health.sys, "argv", ["check_health.py", "--force"])
    monkeypatch.setattr(
        check_health,
        "gemini_call",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["hub.py"], returncode=0, stdout='{"version":"1.0"}', stderr=""
        ),
    )

    with pytest.raises(SystemExit) as exc:
        check_health.main()

    assert exc.value.code == 1
    assert handoff_file.read_text(encoding="utf-8") == '{"keep": true}'


def test_check_health_valid_handoff_overwrites_and_normalizes(monkeypatch, tmp_path):
    sys_dir = tmp_path / "_sys"
    monkeypatch.setattr(check_health, "_PORTABLE_ROOT", tmp_path)
    monkeypatch.setattr(check_health, "_SYS_DIR", sys_dir)

    project_dir = check_health._claude_project_dir(tmp_path)
    project_dir.mkdir(parents=True)
    (project_dir / "session.jsonl").write_text("session", encoding="utf-8")

    sessions_dir = tmp_path / "_archive" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "s.md").write_text("session log", encoding="utf-8")

    handoff_file = tmp_path / "_archive" / "session-handoff.json"
    handoff_file.write_text('{"keep": true}', encoding="utf-8")

    (sys_dir / "claude").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(check_health, "ai_available", lambda: True)
    monkeypatch.setattr(check_health, "archive_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(check_health, "log_collab", lambda *args, **kwargs: None)
    monkeypatch.setattr(check_health.sys, "argv", ["check_health.py", "--force"])

    valid_payload = {
        "version": "1.0",
        "generated_at": "2026-07-10T00:00:00Z",
        "session_context": {},
        "executive_summary": {},
        "technical_state": {},
        "strategy_for_next_session": {},
    }
    monkeypatch.setattr(
        check_health,
        "gemini_call",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["hub.py"], returncode=0, stdout=json.dumps(valid_payload), stderr=""
        ),
    )

    check_health.main()

    saved = json.loads(handoff_file.read_text(encoding="utf-8"))
    assert saved["version"] == "1.0"
    assert saved != {"keep": True}
