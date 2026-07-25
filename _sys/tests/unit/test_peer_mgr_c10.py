"""
Unit and Integration Tests for Cluster C10 Items 4+5 (peer_mgr.py Concurrency & Transaction Safety)

Covers:
  1. Unique Temp Files & Atomic Write: _write_json_atomic creates unique temp files and replaces atomically.
  2. Abandoned Temp Cleanup: _cleanup_temp_files removes old *.tmp files.
  3. Operation Lock Serialization: _get_lock prevents concurrent interleaving.
  4. Multi-File Transaction Atomicity: PeerMgrTransaction stages, journals, CAS checks, and commits all target files.
  5. CAS Violation Rejection: Target file modification between stage and commit raises TransactionError.
  6. Interrupted Transaction Auto-Recovery: Interrupted staged transaction is auto-completed on next operation.
  7. CAS Baseline Drift Blocking: Baseline drift prevents auto-recovery and forces manual recover / error.
"""

import json
import time
from pathlib import Path
import sys
import pytest

SYS_DIR = Path(__file__).parent.parent.parent.resolve()
CLI_DIR = SYS_DIR / "cli"
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import peer_mgr


class TestC10AtomicSaveAndCleanup:
    """Tests for C10 Item 4: _save concurrency, unique temp files, and cleanup."""

    def test_write_json_atomic_creates_unique_temp_and_replaces(self, tmp_path):
        target = tmp_path / "test_config.json"
        data = {"key": "value", "count": 42}

        peer_mgr._write_json_atomic(target, data)

        assert target.exists()
        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert loaded == data
        # Ensure no residual .tmp files remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_cleanup_temp_files_removes_abandoned_tmp_files(self, monkeypatch, tmp_path):
        monkeypatch.setattr(peer_mgr, "_AI", tmp_path)

        old_tmp = tmp_path / "old_file.json.a1b2c3d4.tmp"
        old_tmp.write_text("abandoned content", encoding="utf-8")
        
        # Set mtime to 10 minutes ago
        past_time = time.time() - 600
        import os
        os.utime(old_tmp, (past_time, past_time))

        new_tmp = tmp_path / "recent_file.json.e5f6g7h8.tmp"
        new_tmp.write_text("active content", encoding="utf-8")

        cleaned = peer_mgr._cleanup_temp_files(max_age_seconds=300)

        assert cleaned == 1
        assert not old_tmp.exists()
        assert new_tmp.exists()


class TestC10MultiFileTransaction:
    """Tests for C10 Item 5: Multi-file transaction journal, CAS check, and recovery."""

    def test_transaction_stages_cas_checks_and_commits(self, monkeypatch, tmp_path):
        monkeypatch.setattr(peer_mgr, "_SYS", tmp_path)
        monkeypatch.setattr(peer_mgr, "_AI", tmp_path / "ai")
        monkeypatch.setattr(peer_mgr, "_LOCK_DIR", tmp_path / "ai" / ".lock")
        monkeypatch.setattr(peer_mgr, "_TXN_DIR", tmp_path / "ai" / ".peer_mgr_txn")

        f1 = tmp_path / "ai" / "file1.json"
        f2 = tmp_path / "ai" / "file2.json"
        f1.parent.mkdir(parents=True, exist_ok=True)
        f1.write_text(json.dumps({"f1": "v1"}), encoding="utf-8")
        f2.write_text(json.dumps({"f2": "v2"}), encoding="utf-8")

        txn = peer_mgr.PeerMgrTransaction("test_cmd", "cx")
        txn.stage(f1, {"f1": "updated_v1"})
        txn.stage(f2, {"f2": "updated_v2"})

        txn.commit()

        assert json.loads(f1.read_text("utf-8")) == {"f1": "updated_v1"}
        assert json.loads(f2.read_text("utf-8")) == {"f2": "updated_v2"}
        # Transaction journal should be cleaned up after successful commit
        assert not list((tmp_path / "ai" / ".peer_mgr_txn").glob("*.json"))

    def test_cas_violation_aborts_transaction_without_writing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(peer_mgr, "_SYS", tmp_path)
        monkeypatch.setattr(peer_mgr, "_AI", tmp_path / "ai")
        monkeypatch.setattr(peer_mgr, "_LOCK_DIR", tmp_path / "ai" / ".lock")
        monkeypatch.setattr(peer_mgr, "_TXN_DIR", tmp_path / "ai" / ".peer_mgr_txn")

        f1 = tmp_path / "ai" / "file1.json"
        f1.parent.mkdir(parents=True, exist_ok=True)
        f1.write_text(json.dumps({"f1": "original"}), encoding="utf-8")

        txn = peer_mgr.PeerMgrTransaction("test_cmd", "cx")
        txn.stage(f1, {"f1": "new_value"})

        # Mutate f1 externally after staging to trigger CAS mismatch
        f1.write_text(json.dumps({"f1": "concurrent_external_edit"}), encoding="utf-8")

        with pytest.raises(peer_mgr.TransactionError) as exc_info:
            txn.commit()

        assert "CAS failure" in str(exc_info.value)
        # Content on disk must NOT have been overwritten by staged content
        assert json.loads(f1.read_text("utf-8")) == {"f1": "concurrent_external_edit"}
        # Regression: the journal must not be left behind after a clean CAS
        # rollback -- nothing was written, so there is no ambiguous on-disk
        # state for a future recovery pass to resolve. A "rolled_back" status
        # is never matched by _check_and_recover_transactions() (which only
        # handles "staged"/"committing"), so an orphaned journal here would
        # accumulate forever, never cleaned up by anything.
        assert list(peer_mgr._TXN_DIR.glob("*.json")) == []

    def test_interrupted_transaction_auto_recovers(self, monkeypatch, tmp_path):
        monkeypatch.setattr(peer_mgr, "_SYS", tmp_path)
        monkeypatch.setattr(peer_mgr, "_AI", tmp_path / "ai")
        monkeypatch.setattr(peer_mgr, "_LOCK_DIR", tmp_path / "ai" / ".lock")
        monkeypatch.setattr(peer_mgr, "_TXN_DIR", tmp_path / "ai" / ".peer_mgr_txn")

        f1 = tmp_path / "ai" / "file1.json"
        f1.parent.mkdir(parents=True, exist_ok=True)
        f1.write_text(json.dumps({"f1": "initial"}), encoding="utf-8")

        # Simulate an interrupted transaction journal file left on disk
        txn_dir = tmp_path / "ai" / ".peer_mgr_txn"
        txn_dir.mkdir(parents=True, exist_ok=True)
        
        rel_str = str(f1.relative_to(tmp_path))
        staged_data = {"f1": "auto_recovered_value"}
        jdata = {
            "txn_id": "txn_interrupted_123",
            "cmd": "suspend",
            "peer_id": "cx",
            "status": "staged",
            "created_at": "2026-07-25T16:00:00+00:00",
            "targets": {
                rel_str: {
                    "baseline_sha256": peer_mgr._sha256(json.dumps({"f1": "initial"})),
                    "staged_sha256": peer_mgr._sha256(json.dumps(staged_data, indent=2) + "\n"),
                    "staged_data": staged_data,
                }
            }
        }
        (txn_dir / "txn_interrupted_123.json").write_text(json.dumps(jdata), encoding="utf-8")

        # Run recovery check
        peer_mgr._check_and_recover_transactions()

        # f1 should be auto-recovered to staged_data
        assert json.loads(f1.read_text("utf-8")) == staged_data
        # Journal file should be cleaned up
        assert not (txn_dir / "txn_interrupted_123.json").exists()

    def test_baseline_drift_blocks_auto_recovery(self, monkeypatch, tmp_path):
        monkeypatch.setattr(peer_mgr, "_SYS", tmp_path)
        monkeypatch.setattr(peer_mgr, "_AI", tmp_path / "ai")
        monkeypatch.setattr(peer_mgr, "_LOCK_DIR", tmp_path / "ai" / ".lock")
        monkeypatch.setattr(peer_mgr, "_TXN_DIR", tmp_path / "ai" / ".peer_mgr_txn")

        f1 = tmp_path / "ai" / "file1.json"
        f1.parent.mkdir(parents=True, exist_ok=True)
        # Content changed externally (drift)
        f1.write_text(json.dumps({"f1": "external_modified"}), encoding="utf-8")

        txn_dir = tmp_path / "ai" / ".peer_mgr_txn"
        txn_dir.mkdir(parents=True, exist_ok=True)
        
        rel_str = str(f1.relative_to(tmp_path))
        jdata = {
            "txn_id": "txn_drift_456",
            "cmd": "suspend",
            "peer_id": "cx",
            "status": "staged",
            "created_at": "2026-07-25T16:00:00+00:00",
            "targets": {
                rel_str: {
                    "baseline_sha256": peer_mgr._sha256(json.dumps({"f1": "old_baseline"})),
                    "staged_sha256": "fake_staged_sha",
                    "staged_data": {"f1": "staged_val"},
                }
            }
        }
        (txn_dir / "txn_drift_456.json").write_text(json.dumps(jdata), encoding="utf-8")

        with pytest.raises(peer_mgr.TransactionError) as exc_info:
            peer_mgr._check_and_recover_transactions()

        assert "Incomplete transaction txn_drift_456 blocking execution" in str(exc_info.value)
        # Content remains unchanged on disk
        assert json.loads(f1.read_text("utf-8")) == {"f1": "external_modified"}


class TestC10LockAcquisition:
    """Tests for C10 Item 4: _get_lock, including the filelock-unavailable
    fallback path. Regression (cross-verification finding): the fallback's
    O_EXCL-based BasicFileLock previously could NEVER acquire the lock at
    all, unconditionally -- _get_lock() unconditionally pre-created the lock
    file before constructing the lock object (a step meant to work around a
    real Windows transient-permission race for the REAL filelock library,
    which tolerates the file already existing), but BasicFileLock's own
    os.O_EXCL open requires the file to NOT already exist -- so every
    acquisition attempt raised FileExistsError, retried until the 10s
    timeout, and then raised TimeoutError. This was 100% reproducible
    regardless of actual contention, a permanent self-inflicted deadlock any
    time the `filelock` package was unavailable."""

    def test_real_filelock_acquires_and_releases(self, monkeypatch, tmp_path):
        monkeypatch.setattr(peer_mgr, "_LOCK_DIR", tmp_path / "ai" / ".lock")
        with peer_mgr._get_lock(timeout=5.0):
            pass  # must not raise / must not time out

    def test_fallback_lock_acquires_with_zero_contention_when_filelock_unavailable(self, monkeypatch, tmp_path):
        """The exact bug: force the `from filelock import FileLock` branch to
        fail (simulating an environment without the filelock package
        installed) and confirm the fallback still successfully acquires the
        lock under ZERO real contention -- before the fix this always timed
        out after 10s regardless."""
        monkeypatch.setattr(peer_mgr, "_LOCK_DIR", tmp_path / "ai" / ".lock")
        monkeypatch.setitem(sys.modules, "filelock", None)  # forces ImportError on `from filelock import ...`
        with peer_mgr._get_lock(timeout=2.0):
            pass  # must not raise / must not time out

    def test_fallback_lock_actually_excludes_a_second_acquirer(self, monkeypatch, tmp_path):
        """The fallback lock must still provide real mutual exclusion once
        it's actually fixed to be acquirable at all."""
        monkeypatch.setattr(peer_mgr, "_LOCK_DIR", tmp_path / "ai" / ".lock")
        monkeypatch.setitem(sys.modules, "filelock", None)
        with peer_mgr._get_lock(timeout=2.0):
            with pytest.raises(TimeoutError):
                with peer_mgr._get_lock(timeout=0.3):
                    pass
