"""Tests for T5: per-ask scratch TEMP dir isolation and stale-orphan sweep.

Peer subprocesses (cx especially) were inheriting the shared _sys/data/temp/
directory, creating stray files they could not later clean up. Each ask now
gets its own TEMP/TMP/TMPDIR pointed at a fresh _sys/data/temp/ask_<id> dir,
torn down (best-effort) when the ask completes. A stale-sibling sweep at
setup time reaps orphans whose own teardown failed (e.g. a locked file),
without touching a concurrent live ask's directory.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub


class TestSweepStaleAskTempDirs:
    def test_removes_dirs_older_than_max_age(self, tmp_path):
        old_dir = tmp_path / "ask_stale123"
        old_dir.mkdir()
        (old_dir / "leftover.txt").write_text("x", encoding="utf-8")
        old_time = time.time() - 7200  # 2 hours old
        import os
        os.utime(old_dir, (old_time, old_time))

        hub._sweep_stale_ask_temp_dirs(tmp_path, max_age_sec=3600)

        assert not old_dir.exists()

    def test_never_touches_a_fresh_concurrent_ask_dir(self, tmp_path):
        fresh_dir = tmp_path / "ask_live456"
        fresh_dir.mkdir()
        (fresh_dir / "in_progress.txt").write_text("still working", encoding="utf-8")

        hub._sweep_stale_ask_temp_dirs(tmp_path, max_age_sec=3600)

        assert fresh_dir.exists()
        assert (fresh_dir / "in_progress.txt").read_text(encoding="utf-8") == "still working"

    def test_ignores_non_ask_prefixed_entries(self, tmp_path):
        other_dir = tmp_path / "not_an_ask_dir"
        other_dir.mkdir()
        import os
        old_time = time.time() - 7200
        os.utime(other_dir, (old_time, old_time))

        hub._sweep_stale_ask_temp_dirs(tmp_path, max_age_sec=3600)

        assert other_dir.exists()

    def test_missing_temp_root_is_a_no_op(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        hub._sweep_stale_ask_temp_dirs(missing, max_age_sec=3600)  # must not raise

    def test_survives_a_permission_error_on_one_entry(self, tmp_path, monkeypatch):
        old_dir = tmp_path / "ask_locked789"
        old_dir.mkdir()
        import os
        old_time = time.time() - 7200
        os.utime(old_dir, (old_time, old_time))

        real_rmtree = hub.shutil.rmtree

        def fake_rmtree(path, ignore_errors=False):
            raise OSError("simulated lock")

        monkeypatch.setattr(hub.shutil, "rmtree", fake_rmtree)

        hub._sweep_stale_ask_temp_dirs(tmp_path, max_age_sec=3600)  # must not raise


class TestAskTempDirSkipsOverrideUnderProjectDir:
    """2026-09-23: two different custom temp-dir placements under
    project_dir (dot-prefixed, then plain-named) BOTH failed for a real
    cx dispatch with PermissionError -- and Get-Acl on the directory
    raised UnauthorizedAccessException even for a bare read, pointing at
    a genuine Windows mandatory-integrity mismatch (hub.py's own
    medium-integrity process creates the dir; Codex's spawned children,
    e.g. pytest, run at low integrity and can't access an object created
    by a higher-integrity process without an explicit low-IL ACE). The
    fix is to not fight that: skip the T5 custom-TEMP override entirely
    when project_dir is set, leaving TEMP/TMP/TMPDIR at whatever this
    process's own ambient environment already provides (every integrity
    level already has access to the standard per-user system temp dir).
    This is a source-level guard (see test_codex_dispatch_fixes.py for why
    _action_ask_inner isn't mocked end-to-end).
    """

    def test_project_dir_branch_does_not_override_temp_env_vars(self):
        hub_source = Path(hub.__file__).read_text(encoding="utf-8")
        if_start = hub_source.index("if project_dir:")
        else_start = hub_source.index("\n    else:", if_start)
        if_block = hub_source[if_start:else_start]

        assert "hub_ask_temp" not in if_block, (
            "no custom temp-dir placement under project_dir -- both a dot- "
            "and non-dot-prefixed one failed with a real integrity-level "
            "mismatch; don't reintroduce one without solving that first"
        )
        for var in ("TEMP", "TMP", "TMPDIR"):
            assert f'process_env["{var}"]' not in if_block, (
                f"project_dir branch must not set {var} -- let it inherit "
                "this process's own ambient environment"
            )

    def test_default_branch_still_uses_the_isolated_ask_temp_dir(self):
        hub_source = Path(hub.__file__).read_text(encoding="utf-8")
        else_start = hub_source.index("\n    else:", hub_source.index("if project_dir:"))
        block_end = hub_source.index("process_env[\"TMPDIR\"]", else_start)
        else_block = hub_source[else_start:block_end]

        assert '_ask_temp_root = Path(__file__).resolve().parent.parent / "data" / "temp"' in else_block
        assert 'process_env["TEMP"] = str(ask_temp_dir)' in else_block
