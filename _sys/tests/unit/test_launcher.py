import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

SYS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS))

from core.launcher import _relocate

# --- Tests for _relocate ---

def test_relocate_no_prior_mapping(tmp_path):
    """Edge case: first run, no last_base_dir.txt exists."""
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    base_dir = tmp_path / "base"

    _relocate(base_dir, sys_dir)

    last_file = sys_dir / "data" / "last_base_dir.txt"
    assert last_file.exists()
    assert last_file.read_text(encoding="utf-8") == str(base_dir)

def test_relocate_no_change(tmp_path):
    """Standard case: drive hasn't moved, do nothing."""
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "base"

    last_file = sys_dir / "data" / "last_base_dir.txt"
    last_file.parent.mkdir(parents=True)
    last_file.write_text(str(base_dir), encoding="utf-8")

    _relocate(base_dir, sys_dir)
    assert last_file.read_text(encoding="utf-8") == str(base_dir)

def test_relocate_drive_moved(tmp_path):
    """Case: drive moved, updates last_base_dir.txt."""
    new_base_dir = tmp_path / "new_base"
    sys_dir = new_base_dir / "_sys"

    old_base = str(tmp_path / "old_base")
    new_base = str(new_base_dir)

    last_file = sys_dir / "data" / "last_base_dir.txt"
    last_file.parent.mkdir(parents=True)
    last_file.write_text(old_base, encoding="utf-8")

    _relocate(Path(new_base), sys_dir)

    assert last_file.read_text(encoding="utf-8") == new_base

