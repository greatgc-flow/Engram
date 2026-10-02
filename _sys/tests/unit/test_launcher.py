import json
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

SYS = find_root(__file__)
sys.path.insert(0, str(SYS))

from core.launcher import _note_root_drift

# --- Tests for _note_root_drift ------------------------------------------------
# Design: docs/design/engram-env-resilience-design-2026-10-02.md section 3 ("Launcher fix").
# The launcher used to overwrite data/last_base_dir.txt on EVERY launch, erasing the
# only signal that the install had moved before anything could read it. It is now
# strictly read-only: it compares and hints; only a committed install/repair writes.


@pytest.fixture(autouse=True)
def _hermetic_localappdata(tmp_path, monkeypatch):
    """Never read the developer machine's real %LOCALAPPDATA%\SandboxRun_* sidecars."""
    local = tmp_path / "localappdata"
    local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    return local


def _sys_dir(tmp_path, name="base"):
    base = tmp_path / name
    sys_dir = base / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    return base, sys_dir


def test_launch_never_writes_last_base_dir_on_first_run(tmp_path):
    base, sys_dir = _sys_dir(tmp_path)
    _note_root_drift(base, sys_dir, print_fn=lambda *_: None)
    assert not (sys_dir / "data" / "last_base_dir.txt").exists()


def test_launch_never_overwrites_last_base_dir_after_a_move(tmp_path):
    base, sys_dir = _sys_dir(tmp_path, "new_base")
    last = sys_dir / "data" / "last_base_dir.txt"
    old = str(tmp_path / "old_base")
    last.write_text(old, encoding="utf-8")

    _note_root_drift(base, sys_dir, print_fn=lambda *_: None)

    assert last.read_text(encoding="utf-8") == old  # the move signal survives the launch


def test_hint_printed_when_root_moved(tmp_path):
    base, sys_dir = _sys_dir(tmp_path, "new_base")
    (sys_dir / "data" / "last_base_dir.txt").write_text(str(tmp_path / "gone_base"), encoding="utf-8")
    lines = []
    status = _note_root_drift(base, sys_dir, print_fn=lines.append)
    assert status == "moved"
    assert len(lines) == 1 and "root changed" in lines[0].lower()
    assert str(tmp_path / "gone_base") in lines[0]


def test_hint_uses_manifest_when_present(tmp_path):
    from core import env_manifest
    base, sys_dir = _sys_dir(tmp_path, "new_base")
    env_manifest.write_manifest(sys_dir, {
        "schema_version": 1, "install_id": "x" * 36,
        "root": {"logical": str(tmp_path / "gone_base"), "physical": str(tmp_path / "gone_base")},
    })
    lines = []
    assert _note_root_drift(base, sys_dir, print_fn=lines.append) == "moved"
    assert len(lines) == 1


def test_silent_when_consistent(tmp_path):
    base, sys_dir = _sys_dir(tmp_path)
    (sys_dir / "data" / "last_base_dir.txt").write_text(str(base), encoding="utf-8")
    lines = []
    assert _note_root_drift(base, sys_dir, print_fn=lines.append) == "consistent"
    assert lines == []


def test_silent_when_no_evidence(tmp_path):
    base, sys_dir = _sys_dir(tmp_path)
    lines = []
    assert _note_root_drift(base, sys_dir, print_fn=lines.append) == "unknown"
    assert lines == []


def test_drift_check_never_raises_on_corrupt_state(tmp_path):
    base, sys_dir = _sys_dir(tmp_path)
    (sys_dir / "data" / "state" / "env.manifest.json").write_text("{bad", encoding="utf-8")
    assert _note_root_drift(base, sys_dir, print_fn=lambda *_: None) in {"unknown", "consistent", "moved", "copied"}


def test_sidecar_of_a_live_foreign_install_is_not_evidence_of_a_move(tmp_path, _hermetic_localappdata):
    base, sys_dir = _sys_dir(tmp_path)
    other = tmp_path / "other_install"
    other.mkdir()
    (_hermetic_localappdata / "SandboxRun_x_engram_open.root.txt").write_text(str(other), encoding="utf-8")
    lines = []
    assert _note_root_drift(base, sys_dir, print_fn=lines.append) == "unknown"
    assert lines == []


def test_sidecar_pointing_at_a_vanished_root_is_evidence(tmp_path, _hermetic_localappdata):
    base, sys_dir = _sys_dir(tmp_path)
    (_hermetic_localappdata / "SandboxRun_x_engram_open.root.txt").write_text(
        str(tmp_path / "vanished"), encoding="utf-8")
    assert _note_root_drift(base, sys_dir, print_fn=lambda *_: None) == "moved"
