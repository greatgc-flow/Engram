"""Tests for scrubber.py Tier 2 D10 rollback-dir purge (tool_v{X}_old)."""
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "core"))
import scrubber  # noqa: E402


def test_tier2_purges_old_rollback_dirs_but_keeps_active(tmp_path):
    sys_dir = tmp_path / "_sys"
    tools_dir = sys_dir / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "ripgrep_old").mkdir()
    (tools_dir / "ripgrep_old" / "rg.exe").write_bytes(b"stale")
    active_dir = tools_dir / "ripgrep"
    active_dir.mkdir()
    (active_dir / "rg.exe").write_bytes(b"current")

    scrubber._tier2(tmp_path, sys_dir, dry_run=False)

    assert not (tools_dir / "ripgrep_old").exists()
    assert (active_dir / "rg.exe").exists()


def test_tier2_dry_run_does_not_delete(tmp_path):
    sys_dir = tmp_path / "_sys"
    tools_dir = sys_dir / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "codex_old").mkdir()

    scrubber._tier2(tmp_path, sys_dir, dry_run=True)

    assert (tools_dir / "codex_old").exists()
