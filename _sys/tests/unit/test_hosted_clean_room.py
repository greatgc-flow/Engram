"""Offline contracts for hosted clean-room driver (EN-GAP-P1-005).

Verifies isolation assertions, candidate check sequence, and provider evidence schema.
"""
from __future__ import annotations

import json
import hashlib
import zipfile
from pathlib import Path
import pytest

from tools.release_gate import hosted_clean_room


def make_candidate(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    if files is None:
        files = {"Engram-v2.1.0-portable-x64.zip": "a" * 64}
    candidate = {
        "tag": "v2.1.0",
        "commit": "0" * 40,
        "candidate_sha256s": files,
    }
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    return path


def make_archive(tmp_path):
    archive = tmp_path / "Engram-v2.1.0-portable-x64.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("engram.cmd", "@echo off")
        zf.writestr("_sys/core/bootstrap.bat", "@echo off")
    return archive, make_candidate(tmp_path, {archive.name: hashlib.sha256(archive.read_bytes()).hexdigest()})


def test_hosted_clean_room_success(tmp_path: Path) -> None:
    archive, cand_path = make_archive(tmp_path)
    clean_root = tmp_path / "clean_root"

    out_path = tmp_path / "evidence.json"
    commands_run = []

    def stub_runner(cmd, cwd, env):
        commands_run.append((cmd, cwd))
        return "PASS"

    evidence = hosted_clean_room.execute_hosted_clean_room(
        candidate_path=cand_path,
        clean_root=clean_root,
        candidate_zip=archive,
        out_path=out_path,
        workflow_run_id="999",
        image="test-image-v1",
        runner=stub_runner,
    )

    assert evidence["status"] == "PASS"
    assert evidence["provider"] == "hosted-ephemeral-vm"
    assert evidence["runner_environment"] == "github-hosted"
    assert evidence["workflow_run_id"] == "999"
    assert evidence["image"] == "test-image-v1"
    assert evidence["cancelled"] is False
    assert evidence["skipped"] is False

    # Check commands sequence
    assert len(commands_run) == 3
    assert "--skip-vscode" in commands_run[0][0]
    assert "doctor" in commands_run[1][0]
    assert "update" in commands_run[2][0]


def test_clean_root_with_git_holds(tmp_path: Path) -> None:
    cand_path = make_candidate(tmp_path)
    clean_root = tmp_path / "clean_root"
    clean_root.mkdir()
    (clean_root / ".git").mkdir()
    (clean_root / "engram.cmd").write_text("@echo off", encoding="utf-8")
    out_path = tmp_path / "evidence.json"

    with pytest.raises(hosted_clean_room.Hold, match=r"\.git"):
        hosted_clean_room.execute_hosted_clean_room(
            candidate_path=cand_path,
            clean_root=clean_root,
            out_path=out_path,
        )


def test_clean_root_with_dev_requirements_holds(tmp_path: Path) -> None:
    cand_path = make_candidate(tmp_path)
    clean_root = tmp_path / "clean_root"
    clean_root.mkdir()
    (clean_root / "requirements-dev.txt").write_text("pytest\n", encoding="utf-8")
    (clean_root / "engram.cmd").write_text("@echo off", encoding="utf-8")
    out_path = tmp_path / "evidence.json"

    with pytest.raises(hosted_clean_room.Hold, match="requirements-dev.txt"):
        hosted_clean_room.execute_hosted_clean_room(
            candidate_path=cand_path,
            clean_root=clean_root,
            out_path=out_path,
        )


def test_failed_command_holds(tmp_path: Path) -> None:
    archive, cand_path = make_archive(tmp_path)
    clean_root = tmp_path / "clean_root"

    out_path = tmp_path / "evidence.json"

    def failing_runner(cmd, cwd, env):
        raise hosted_clean_room.Hold("bootstrap failed")

    with pytest.raises(hosted_clean_room.Hold, match="bootstrap failed"):
        hosted_clean_room.execute_hosted_clean_room(
            candidate_path=cand_path,
            clean_root=clean_root,
            out_path=out_path,
            runner=failing_runner,
            candidate_zip=archive,
        )


def test_main_cli_emits_hold_on_failure(tmp_path: Path) -> None:
    cand_path = make_candidate(tmp_path)
    clean_root = tmp_path / "clean_root"
    clean_root.mkdir()
    # Missing engram.cmd and archive => fails
    out_path = tmp_path / "evidence.json"

    rc = hosted_clean_room.main([
        "--candidate", str(cand_path),
        "--clean-root", str(clean_root),
        "--out", str(out_path),
    ])
    assert rc == 1
    assert out_path.exists()
    evidence = json.loads(out_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "HOLD"
    assert evidence["provider"] == "hosted-ephemeral-vm"
    assert evidence["runner_environment"] == "github-hosted"
