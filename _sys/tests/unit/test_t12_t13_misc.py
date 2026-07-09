"""Tests for T12/T13 hardcoding-audit fixes (2026-07-09)."""
import importlib.util
import io
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest


SYS_DIR = Path(__file__).resolve().parents[2]
CHECKS_DIR = SYS_DIR / "checks"
CLI_DIR = SYS_DIR / "cli"
sys.path.insert(0, str(CHECKS_DIR))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_saturation_default_root_is_sys(monkeypatch):
    module = _load("saturation_t12", CHECKS_DIR / "saturation_scan.py")
    seen = []

    monkeypatch.setattr(module, "_read_commit_count", lambda root: 0)
    monkeypatch.setattr(module, "scan_lines", lambda root: seen.append(root) or [])
    monkeypatch.setattr(module.sys, "argv", [
        "saturation_scan.py", "--force", "--checks", "lines",
    ])

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert exc.value.code == 0
    assert seen == [SYS_DIR]


def test_claude_project_key_preserves_drive_identity():
    module = _load("health_t12", CHECKS_DIR / "check_health.py")
    assert module._claude_project_key(Path("P:\\")) == "P--"
    assert (
        module._claude_project_key(Path(r"D:\PortableDev (v2.0)"))
        == "D--PortableDev--v2-0-"
    )


def test_claude_project_dir_uses_encoded_root(tmp_path):
    module = _load("health_dir_t12", CHECKS_DIR / "check_health.py")
    projects = tmp_path / "projects"
    result = module._claude_project_dir(
        Path(r"D:\PortableDev (v2.0)"),
        projects,
    )
    assert result == projects / "D--PortableDev--v2-0-"


def test_agents_dir_comes_from_peers_config(tmp_path):
    module = _load("agents_t12", CHECKS_DIR / "check_agents.py")
    root = tmp_path
    ai_dir = root / "_sys" / "ai"
    ai_dir.mkdir(parents=True)
    (ai_dir / "peers.json").write_text(json.dumps({
        "peers": {
            "claude": {
                "sys_subdir": "claude",
                "project_junction": {"portable_subpath": "project"},
            }
        }
    }), encoding="utf-8")

    assert module._configured_agents_dir(root) == (
        root / "_sys" / "claude" / "project" / "agents"
    )


def test_dependency_merge_reports_missing_coverage(tmp_path, capsys):
    module = _load("deps_t12", CHECKS_DIR / "check_deps.py")
    root = tmp_path
    sys_dir = root / "_sys"
    target = sys_dir / "hooks" / "ctx_save.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('ok')\n", encoding="utf-8")

    merged = module._merge_target_files(root, sys_dir)
    output = capsys.readouterr().out

    assert "=== COVERAGE ===" in merged
    assert "_sys/hooks/ctx_save.py" in merged
    assert "Merged 1 of 11 selected files" in output
    assert "Skipped missing selected targets" in output


def test_batch_review_policy_is_protocol_backed(tmp_path, monkeypatch):
    module = _load("batch_t12", CLI_DIR / "batch_review.py")
    protocol = tmp_path / "protocol.json"
    state = tmp_path / "review-state.json"
    protocol.write_text(json.dumps({
        "collab_rate": {
            "current": 10,
            "review_interval_min": 5,
            "batch_review_min_collab_rate": 7,
        }
    }), encoding="utf-8")

    monkeypatch.setattr(module, "_PROTOCOL_FILE", protocol)
    monkeypatch.setattr(module, "_REVIEW_STATE_FILE", state)

    policy = module._load_collab_policy()
    assert policy is not None
    assert module._ratio_ok(policy) is True

    now = datetime(2026, 7, 9, 12, 0, 0)
    state.write_text(json.dumps({
        "last_review_ts": (now - timedelta(minutes=4)).isoformat()
    }), encoding="utf-8")
    assert module._time_gate_ok(policy, now=now) is False

    state.write_text(json.dumps({
        "last_review_ts": (now - timedelta(minutes=6)).isoformat()
    }), encoding="utf-8")
    assert module._time_gate_ok(policy, now=now) is True


def test_protocol_declares_batch_review_threshold():
    protocol = json.loads(
        (SYS_DIR / "ai" / "protocol.json").read_text(encoding="utf-8")
    )
    assert protocol["collab_rate"]["batch_review_min_collab_rate"] == 7


def test_ag_statusline_uses_scratch_and_timeout(tmp_path, monkeypatch, capsys):
    module = _load("ag_status_t12", CLI_DIR / "ag_statusline.py")
    assert module.STDIN_LOG == (
        module.SYS_DIR / "data" / "temp" / "ag_statusline_stdin.log"
    )

    log_path = tmp_path / "ag_statusline_stdin.log"
    monkeypatch.setattr(module, "STDIN_LOG", log_path)
    monkeypatch.setattr(module.sys, "stdin", io.StringIO('{"model":"test"}'))

    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(stdout="ag:test", stderr="", returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    module.main()

    assert log_path.read_text(encoding="utf-8") == '{"model":"test"}'
    assert captured["timeout"] == module.STATUSLINE_TIMEOUT_SEC
    assert capsys.readouterr().out == "ag:test"


def test_retired_gc_recovery_guidance_is_absent():
    for path in (
        CHECKS_DIR / "check_agents.py",
        CHECKS_DIR / "check_health.py",
        CHECKS_DIR / "check_versions.py",
    ):
        source = path.read_text(encoding="utf-8")
        assert "--peer gc" not in source
        assert "Run 'gemini' interactively" not in source
