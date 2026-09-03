"""Tests for local.config.bat's per-PC override mechanism (launcher.py).

Covers the real gap found and fixed 2026-09-04: the template documented
BASE_DIR_WORKSPACE/NPM_CONFIG_PREFIX overrides that no code actually
consumed (BASE_DIR_WORKSPACE: zero consumers at all; NPM_CONFIG_PREFIX:
unconditionally overwritten by build_env() even if pre-set). See
_sys/data/sessions/2026-09-03_separation-completion-backlog.md item 4.
"""
import os
import sys
from pathlib import Path

import pytest

SYS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS))

from core.launcher import (
    _load_local_config_overrides,
    _resolve_default_target,
    build_env,
)


# ── _load_local_config_overrides ────────────────────────────────────────────

def test_no_local_config_file_returns_empty(tmp_path):
    assert _load_local_config_overrides(tmp_path) == {}


def test_parses_recognized_override_keys(tmp_path):
    (tmp_path / "local.config.bat").write_text(
        '@echo off\n'
        ':: comment line, ignored\n'
        'set "BASE_DIR_WORKSPACE=D:\\Projects\\MyWork"\n'
        'set "NPM_CONFIG_PREFIX=D:\\npm-global"\n',
        encoding="utf-8",
    )
    overrides = _load_local_config_overrides(tmp_path)
    assert overrides == {
        "BASE_DIR_WORKSPACE": "D:\\Projects\\MyWork",
        "NPM_CONFIG_PREFIX": "D:\\npm-global",
    }


def test_commented_and_unrecognized_lines_ignored(tmp_path):
    (tmp_path / "local.config.bat").write_text(
        ':: set "BASE_DIR_WORKSPACE=D:\\Should\\Not\\Apply"\n'
        'set "SOME_UNRELATED_VAR=should not appear"\n'
        'set "NPM_CONFIG_PREFIX=D:\\real-npm"\n',
        encoding="utf-8",
    )
    overrides = _load_local_config_overrides(tmp_path)
    assert overrides == {"NPM_CONFIG_PREFIX": "D:\\real-npm"}


def test_percent_var_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", "C:\\Users\\Test\\AppData\\Roaming")
    (tmp_path / "local.config.bat").write_text(
        'set "NPM_CONFIG_PREFIX=%APPDATA%\\npm"\n',
        encoding="utf-8",
    )
    overrides = _load_local_config_overrides(tmp_path)
    assert overrides["NPM_CONFIG_PREFIX"] == "C:\\Users\\Test\\AppData\\Roaming\\npm"


def test_does_not_mutate_process_environment(tmp_path, monkeypatch):
    """Reading local.config.bat must never leak into os.environ -- it's read
    as data, not executed, precisely to avoid ambient-environment collision."""
    monkeypatch.delenv("NPM_CONFIG_PREFIX", raising=False)
    (tmp_path / "local.config.bat").write_text(
        'set "NPM_CONFIG_PREFIX=D:\\npm-global"\n',
        encoding="utf-8",
    )
    _load_local_config_overrides(tmp_path)
    assert "NPM_CONFIG_PREFIX" not in os.environ


# ── build_env() honors the NPM_CONFIG_PREFIX override ───────────────────────

def _make_sys_dir(tmp_path: Path) -> Path:
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    (sys_dir / "env.json").write_text(
        '{"env_vars": {}, "tool_env_vars": '
        '{"NPM_CONFIG_PREFIX": {"base": "env", "sub": "nodejs/npm-global"}}, '
        '"path_entries": []}',
        encoding="utf-8",
    )
    return sys_dir


def test_build_env_uses_computed_default_without_override(tmp_path):
    sys_dir = _make_sys_dir(tmp_path)
    env = build_env(tmp_path, sys_dir)
    expected = str(sys_dir / "env" / "nodejs" / "npm-global")
    assert env["NPM_CONFIG_PREFIX"] == expected


def test_build_env_honors_local_config_override(tmp_path):
    sys_dir = _make_sys_dir(tmp_path)
    (sys_dir / "local.config.bat").write_text(
        'set "NPM_CONFIG_PREFIX=D:\\custom-npm-global"\n',
        encoding="utf-8",
    )
    env = build_env(tmp_path, sys_dir)
    assert env["NPM_CONFIG_PREFIX"] == "D:\\custom-npm-global"


# ── _resolve_default_target ──────────────────────────────────────────────────

def test_default_target_falls_back_to_base_dir_when_no_workspace(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    assert _resolve_default_target(tmp_path, sys_dir) == tmp_path


def test_default_target_uses_workspace_subfolder_if_present(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    assert _resolve_default_target(tmp_path, sys_dir) == workspace


def test_default_target_override_wins_over_workspace_subfolder(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    (tmp_path / "workspace").mkdir()
    custom = tmp_path / "elsewhere"
    custom.mkdir()
    (sys_dir / "local.config.bat").write_text(
        f'set "BASE_DIR_WORKSPACE={custom}"\n',
        encoding="utf-8",
    )
    assert _resolve_default_target(tmp_path, sys_dir) == custom
