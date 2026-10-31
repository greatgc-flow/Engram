"""Windows smoke: absolute ENGRAM_SYS_DIR must not be prefixed with %~dp0.

Only a disposable tmp_path is touched. This invokes the real top-level
engram.cmd but does not bootstrap, update, install, call providers, or need
a portable Python distribution. The version command reads a synthetic
core/version.json and proves CMD root discovery/selection.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from _sys.core.root import find_root


ROOT = find_root(__file__).parent
pytestmark = pytest.mark.skipif(os.name != "nt", reason="requires cmd.exe")


def _write_sys(folder: Path, version: str) -> None:
    core = folder / "core"
    core.mkdir(parents=True)
    (core / "dispatch.bat").write_text("@echo off\nexit /b 0\n", encoding="utf-8")
    (core / "version.json").write_text(
        json.dumps({"version": version}), encoding="utf-8"
    )


def _run_version(root: Path, override: str | None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if override is None:
        env.pop("ENGRAM_SYS_DIR", None)
    else:
        env["ENGRAM_SYS_DIR"] = override
    launcher = root / "engram.cmd"
    # Quoting matches the real cmd.exe /c launcher with paths containing spaces.
    command = f'cmd.exe /d /c ""{launcher}" version"'
    return subprocess.run(
        command,
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
        timeout=25,
        check=False,
    )


def test_absolute_override_selects_renamed_system_path(tmp_path: Path) -> None:
    root = tmp_path / "portable root"
    root.mkdir()
    shutil.copy2(ROOT / "engram.cmd", root / "engram.cmd")
    _write_sys(root / "_sys", "0.0.0-shadow")
    renamed = root / "renamed runtime"
    _write_sys(renamed, "9.8.7-absolute")

    result = _run_version(root, str(renamed))

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "Engram 9.8.7-absolute (Portable Dev Runtime)" in result.stdout
    assert "0.0.0-shadow" not in result.stdout


def test_relative_override_still_selects_renamed_system_path(tmp_path: Path) -> None:
    root = tmp_path / "portable root"
    root.mkdir()
    shutil.copy2(ROOT / "engram.cmd", root / "engram.cmd")
    _write_sys(root / "_sys", "0.0.0-shadow")
    _write_sys(root / "renamed runtime", "9.8.7-relative")

    result = _run_version(root, "renamed runtime")

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "Engram 9.8.7-relative (Portable Dev Runtime)" in result.stdout
    assert "0.0.0-shadow" not in result.stdout


def test_invalid_absolute_override_falls_back_to_default(tmp_path: Path) -> None:
    root = tmp_path / "portable root"
    root.mkdir()
    shutil.copy2(ROOT / "engram.cmd", root / "engram.cmd")
    _write_sys(root / "_sys", "9.8.7-default")

    result = _run_version(root, str(tmp_path / "missing runtime"))

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "Engram 9.8.7-default (Portable Dev Runtime)" in result.stdout
