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


# ── .engram/ dotdir consolidation (ratified 2026-09-09, item 6) ────────────


def _make_engram_sys_dir(tmp_path: Path) -> Path:
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    (sys_dir / "env.json").write_text(
        '{"env_vars": {}, "tool_env_vars": {'
        '"CLAUDE_CONFIG_DIR": {"base": "engram", "sub": "claude"}, '
        '"CODEX_HOME": {"base": "engram", "sub": "codex"}, '
        '"GEMINI_DIR": {"base": "engram", "sub": "agy"}, '
        '"GH_CONFIG_DIR": {"base": "engram", "sub": "gh"}, '
        '"PEERHUB_CONFIG_HOME": {"base": "engram", "sub": "peerhub/config"}'
        '}, "path_entries": []}',
        encoding="utf-8",
    )
    return sys_dir


def test_build_env_resolves_ai_cli_vars_under_engram_dotdir(tmp_path):
    sys_dir = _make_engram_sys_dir(tmp_path)
    env = build_env(tmp_path, sys_dir)
    assert env["CLAUDE_CONFIG_DIR"] == str(tmp_path / ".engram" / "claude")
    assert env["CODEX_HOME"] == str(tmp_path / ".engram" / "codex")
    assert env["GEMINI_DIR"] == str(tmp_path / ".engram" / "agy")
    assert env["GH_CONFIG_DIR"] == str(tmp_path / ".engram" / "gh")
    assert env["PEERHUB_CONFIG_HOME"] == str(tmp_path / ".engram" / "peerhub" / "config")


def test_build_env_creates_engram_subdirs_idempotently(tmp_path):
    sys_dir = _make_engram_sys_dir(tmp_path)
    build_env(tmp_path, sys_dir)
    build_env(tmp_path, sys_dir)  # must not raise the second time
    for sub in ("claude", "codex", "agy", "gh"):
        assert (tmp_path / ".engram" / sub).is_dir()
    assert (tmp_path / ".engram" / "peerhub" / "config").is_dir()


def test_build_env_git_config_global_retargeted_to_engram_when_present(tmp_path, monkeypatch):
    monkeypatch.delenv("GIT_CONFIG_GLOBAL", raising=False)
    sys_dir = _make_engram_sys_dir(tmp_path)
    engram_git = tmp_path / ".engram" / "git"
    engram_git.mkdir(parents=True)
    (engram_git / ".gitconfig").write_text("[user]\nname = test\n", encoding="utf-8")

    env = build_env(tmp_path, sys_dir)

    assert env["GIT_CONFIG_GLOBAL"] == str(engram_git / ".gitconfig")


def test_build_env_git_config_global_absent_when_no_file_exists(tmp_path, monkeypatch):
    """The .exists() guard is kept -- retargeting must not fabricate a
    GIT_CONFIG_GLOBAL pointing at a file that was never created."""
    monkeypatch.delenv("GIT_CONFIG_GLOBAL", raising=False)
    sys_dir = _make_engram_sys_dir(tmp_path)
    env = build_env(tmp_path, sys_dir)
    assert "GIT_CONFIG_GLOBAL" not in env


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
