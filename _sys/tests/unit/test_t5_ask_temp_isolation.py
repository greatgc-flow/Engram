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
