import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

SYS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS))

from core.launcher import _map_subst_drive, _relocate

# --- Tests for _map_subst_drive ---

@patch("core.launcher.subprocess.run")
@patch("core.launcher.os.path.exists")
@patch("core.launcher.time.sleep")
def test_map_subst_drive_not_mapped_yet(mock_sleep, mock_exists, mock_run):
    """Standard case: drive is not currently mapped, subst succeeds."""
    mock_exists.side_effect = [False, True]

    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_run.return_value = mock_res

    _map_subst_drive(Path("C:/my/base"), "Z")

    mock_run.assert_called_once_with(["subst", "Z:", "C:\\my\\base"], capture_output=True)
    # os.path.exists's 2nd call (inside the post-mapping poll loop) returns True
    # on the first iteration, which sleeps once before breaking.
    mock_sleep.assert_called_once_with(0.2)

@patch("core.launcher.subprocess.run")
@patch("core.launcher.os.path.exists")
@patch("core.launcher.Path.exists")
@patch("core.launcher.time.sleep")
def test_map_subst_drive_already_correctly_mapped(mock_sleep, mock_path_exists, mock_exists, mock_run):
    """Edge case: drive is already correctly mapped to our workspace."""
    mock_exists.return_value = True
    mock_path_exists.return_value = True

    _map_subst_drive(Path("C:/my/base"), "Z")
    mock_run.assert_not_called()

@patch("core.launcher.subprocess.run")
@patch("core.launcher.os.path.exists")
@patch("core.launcher.Path.exists")
@patch("core.launcher.time.sleep")
def test_map_subst_drive_occupied_and_remap_succeeds(mock_sleep, mock_path_exists, mock_exists, mock_run):
    """High-risk case: drive occupied by another path, must be removed and re-added."""
    mock_exists.return_value = True
    mock_path_exists.return_value = False

    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_run.return_value = mock_res

    _map_subst_drive(Path("C:/my/base"), "Z")

    assert mock_run.call_count == 2
    mock_run.assert_any_call(["subst", "Z:", "/D"], capture_output=True)
    mock_run.assert_any_call(["subst", "Z:", "C:\\my\\base"], capture_output=True)

@patch("core.launcher.subprocess.run")
@patch("core.launcher.os.path.exists")
def test_map_subst_drive_subst_fails_directly(mock_exists, mock_run):
    """Failure case: drive not occupied but subst fails."""
    mock_exists.return_value = False

    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_run.return_value = mock_res

    with pytest.raises(RuntimeError, match="subst Z: failed"):
        _map_subst_drive(Path("C:/my/base"), "Z")

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

