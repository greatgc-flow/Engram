"""hub.find_ai_root — phantom .ai guard (2026-07-07).

Regression: a peer (ag) whose CWD resolved into <root>/_sys/antigravity/config/
scratch (which had grown a stray .ai) had find_ai_root() return that PHANTOM
.ai instead of the canonical <root>/.ai, so consensus votes silently landed in
the wrong tree (hub.py:4870 silent exit 1). Fix: a .ai/.git discovered INSIDE
our own _sys/ tree is machinery debris and is skipped in favor of canonical.
"""
import os
import sys
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parents[2]  # _sys/
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub

CANONICAL_AI = SYS_DIR.parent / ".ai"


@pytest.fixture
def _restore_cwd():
    prev = Path.cwd()
    yield
    os.chdir(prev)


def test_phantom_ai_under_sys_tree_is_ignored(tmp_path_factory, _restore_cwd, monkeypatch):
    # Build a phantom scratch dir *inside* the real _sys tree with its own .ai.
    phantom = SYS_DIR / "tests" / ".phantom_ai_tmp" / "deep"
    (phantom / ".ai" / "consensus").mkdir(parents=True, exist_ok=True)
    try:
        monkeypatch.delenv("HUB_AI_ROOT", raising=False)
        os.chdir(phantom)
        resolved = hub.find_ai_root()
        # Must skip the phantom and land on canonical <root>/.ai
        assert resolved.resolve() == CANONICAL_AI.resolve()
        assert (SYS_DIR / "tests" / ".phantom_ai_tmp") not in resolved.parents
    finally:
        # cleanup the phantom tree
        import shutil
        shutil.rmtree(SYS_DIR / "tests" / ".phantom_ai_tmp", ignore_errors=True)


def test_hub_ai_root_env_override_wins(_restore_cwd, monkeypatch, tmp_path):
    override = tmp_path / "custom" / ".ai"
    override.mkdir(parents=True)
    monkeypatch.setenv("HUB_AI_ROOT", str(override))
    assert hub.find_ai_root().resolve() == override.resolve()


def test_canonical_resolution_from_root(_restore_cwd, monkeypatch):
    monkeypatch.delenv("HUB_AI_ROOT", raising=False)
    os.chdir(SYS_DIR.parent)  # portable root, has real .ai + .git
    assert hub.find_ai_root().resolve() == CANONICAL_AI.resolve()
