"""Tests for hub.find_ai_root() phantom-fix (consensus 2026-07-04).

Precedence: HUB_AI_ROOT env override > CWD-upward .ai/.git walk (portability) >
canonical portable-root .ai (never a phantom cwd/.ai at a nondeterministic
worker cwd — the bug that lost consensus round r-bd7c).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub

CANONICAL = Path(hub.__file__).resolve().parents[2] / ".ai"


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("HUB_AI_ROOT", str(tmp_path))
    assert hub.find_ai_root() == tmp_path.resolve()


def test_blank_env_override_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("HUB_AI_ROOT", "   ")
    monkeypatch.chdir(tmp_path)  # no .ai/.git here
    assert hub.find_ai_root() == CANONICAL


def test_cwd_walk_finds_local_ai_for_portability(monkeypatch, tmp_path):
    """An external project dir with its OWN .ai must resolve to ITS .ai."""
    monkeypatch.delenv("HUB_AI_ROOT", raising=False)
    (tmp_path / ".ai").mkdir()
    monkeypatch.chdir(tmp_path)
    assert hub.find_ai_root() == (tmp_path / ".ai").resolve()


def test_cwd_walk_finds_git_project(monkeypatch, tmp_path):
    monkeypatch.delenv("HUB_AI_ROOT", raising=False)
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "src" / "pkg"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    assert hub.find_ai_root() == (tmp_path / ".ai").resolve()


def test_no_marker_falls_back_to_canonical_not_phantom(monkeypatch, tmp_path):
    """A dir with neither .ai nor .git must NOT auto-create a phantom cwd/.ai;
    it falls back to the canonical portable-root .ai."""
    monkeypatch.delenv("HUB_AI_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    result = hub.find_ai_root()
    assert result == CANONICAL
    assert result != (tmp_path / ".ai").resolve()
