"""
Unit tests for self_care.py (TDD - Step 4).
Covers the 7-step self-care lifecycle and CLI entry points.
"""
import sys
import json
import pytest
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# 1. Setup path to find self_care.py in _sys/checks
SYS_DIR = Path(__file__).parent.parent.parent.resolve()
CHECKS_DIR = SYS_DIR / "checks"
if str(CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKS_DIR))

# Import will fail until self_care.py is created (TDD)
# from self_care import SelfCare, main

@pytest.fixture
def mock_env(tmp_path):
    """Sets up a mock _sys and _archive environment."""
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    archive_dir = tmp_path / "_archive"
    archive_dir.mkdir()

    # Mock health.json
    health_file = sys_dir / "health.json"
    health_data = {
        "status": "GREEN",
        "last_check": "20260618120000",
        "checks": {"portability": "OK", "deps": "OK"}
    }
    health_file.write_text(json.dumps(health_data), encoding="utf-8")

    # Mock runtime-directives.jsonl (for Cleanup test)
    directives_file = sys_dir / "runtime-directives.jsonl"
    now = time.time()
    directives = [
        {"id": "DIR-VALID", "ttl": 3600, "timestamp": now, "rule": "valid rule"},
        {"id": "DIR-EXPIRED", "ttl": 60, "timestamp": now - 3600, "rule": "expired rule"}
    ]
    with open(directives_file, "w", encoding="utf-8") as f:
        for d in directives:
            f.write(json.dumps(d) + "\n")

    return {
        "root": tmp_path,
        "sys": sys_dir,
        "archive": archive_dir,
        "health": health_file,
        "directives": directives_file,
        "log": archive_dir / "self-care-log.jsonl"
    }

class TestSelfCare:
    """TDD for SelfCare logic."""

    def test_observe_reads_health_and_directives(self, mock_env):
        """Step 1: Observe reads health.json and runtime-directives.jsonl."""
        from self_care import SelfCare
        sc = SelfCare(sys_dir=mock_env["sys"])
        sc.observe()

        assert sc.state["health"]["status"] == "GREEN"
        # Only valid directives should be kept in state after observation?
        # Or all are loaded and cleanup() filters?
        # The prompt says cleanup removes entries. So observe loads all.
        assert len(sc.state["directives"]) == 2

    def test_validate_calls_virtualizer_status(self, mock_env):
        """Step 2: Validate calls virtualizer.py --status."""
        from self_care import SelfCare
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Status: OK")
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.validate()

            # Verify virtualizer.py --status call
            args, kwargs = mock_run.call_args
            cmd = " ".join(args[0])
            assert "virtualizer.py" in cmd
            assert "--status" in cmd

    def test_cleanup_sweeps_expired_directives(self, mock_env):
        """Step 3: Cleanup removes expired entries (TTL) from directives file."""
        from self_care import SelfCare
        sc = SelfCare(sys_dir=mock_env["sys"])
        sc.observe() # Load 2
        sc.cleanup() # Sweep 1

        assert len(sc.state["directives"]) == 1
        assert sc.state["directives"][0]["id"] == "DIR-VALID"

        # Verify file persistence
        content = mock_env["directives"].read_text(encoding="utf-8")
        assert "DIR-EXPIRED" not in content
        assert "DIR-VALID" in content

    def test_scan_calls_saturation_scan(self, mock_env):
        """Step 4: Scan invokes saturation_scan.py."""
        from self_care import SelfCare
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Findings: High saturation in core/")
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.scan()

            args, kwargs = mock_run.call_args
            cmd = " ".join(args[0])
            assert "saturation_scan.py" in cmd

    def test_scan_failure_is_recorded(self, mock_env):
        """scan() records saturation_scan.py subprocess failure into state['errors']."""
        from self_care import SelfCare
        failed = MagicMock(
            returncode=2, stdout="",
            stderr="saturation_scan.py: error: unrecognized arguments",
        )
        with patch("subprocess.run", return_value=failed) as mock_run:
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.scan()

        assert "--quiet" not in mock_run.call_args[0][0]
        assert sc.state["scan_findings"] == ""
        assert sc.state["steps_completed"] == ["scan"]
        assert sc.state["errors"] == [
            "scan: saturation_scan.py failed with exit code 2: "
            "saturation_scan.py: error: unrecognized arguments"
        ]

    def test_propose_on_saturation_findings(self, mock_env):
        """Step 5: Propose calls hub.py proposal-add if scan findings exist."""
        from self_care import SelfCare
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.state["scan_findings"] = "Saturation detected"
            sc.propose()

            args, kwargs = mock_run.call_args
            cmd = " ".join(args[0])
            assert "hub.py" in cmd
            assert "proposal-add" in cmd

    def test_propose_uses_subject_flag(self, mock_env):
        """A-01: self_care propose uses --subject instead of --title."""
        from self_care import SelfCare
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.state["scan_findings"] = "Saturation detected"
            sc.propose()

            args = mock_run.call_args[0][0]
            assert "--subject" in args, "propose must use --subject"
            assert "--title" not in args, "propose must not use --title"

    def test_lesson_graduation_uses_subject_flag(self, mock_env):
        """A-01: self_care lesson_graduation uses --subject instead of --title."""
        from self_care import SelfCare

        # Setup mock environment for lesson graduation
        gov_path = mock_env["sys"] / "ai" / "governance_params.json"
        gov_path.parent.mkdir(parents=True, exist_ok=True)
        gov_path.write_text(json.dumps({"lesson_graduation_auto_propose": True}), encoding="utf-8")

        knowledge_dir = mock_env["sys"] / "ai" / "knowledge" / "general"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        lessons_path = knowledge_dir / "active-lessons.jsonl"

        # Write a mock lesson that meets the threshold
        # Use ISO8601 with Z to ensure it parses correctly and is considered recent
        lesson = {
            "id": "L-123",
            "status": "active",
            "title": "Test Lesson",
            "source_refs": [
                {"id": "1", "type": "debate", "ts": "2026-06-25T12:00:00Z"},
                {"id": "2", "type": "debate", "ts": "2026-06-25T12:00:00Z"},
                {"id": "3", "type": "debate", "ts": "2026-06-25T12:00:00Z"}
            ]
        }
        lessons_path.write_text(json.dumps(lesson) + "\n", encoding="utf-8")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.lesson_graduation()

            args = mock_run.call_args[0][0]
            assert "--subject" in args, "lesson_graduation must use --subject"
            assert "--title" not in args, "lesson_graduation must not use --title"

    def test_sync_calls_sync_docs_dry_run(self, mock_env):
        """Step 6: Sync invokes sync_docs.py --dry-run."""
        from self_care import SelfCare
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.sync()

            args, kwargs = mock_run.call_args
            cmd = " ".join(args[0])
            assert "sync_docs.py" in cmd
            assert "--dry-run" in cmd

    def test_record_writes_to_archive(self, mock_env):
        """Step 7: Record appends summary to _archive/self-care-log.jsonl."""
        from self_care import SelfCare
        sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
        sc.state["steps_completed"] = ["observe", "validate"]
        sc.record(trigger="manual")

        log_file = mock_env["log"]
        assert log_file.exists()
        log_data = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert log_data["trigger"] == "manual"
        assert "observe" in log_data["steps"]

    def test_step_failure_is_non_blocking(self, mock_env):
        """Failures in individual steps do not stop the execution of others."""
        from self_care import SelfCare
        sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])

        # Inject failure in cleanup
        with patch.object(SelfCare, "cleanup", side_effect=Exception("Cleanup error")):
            with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                sc.run(trigger="test")

        # Even if cleanup failed, record() should have run
        assert mock_env["log"].exists()
        log_data = json.loads(mock_env["log"].read_text(encoding="utf-8").strip())
        assert any("Cleanup error" in err for err in log_data.get("errors", []))

    def test_trigger_arg_recorded_in_log(self, mock_env):
        """The --trigger value is correctly captured in the log entry."""
        from self_care import SelfCare
        sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
        sc.record(trigger="commit_interval")

        log_data = json.loads(mock_env["log"].read_text(encoding="utf-8").strip())
        assert log_data["trigger"] == "commit_interval"

    def test_main_cli_exits_zero_on_success(self, mock_env):
        """CLI entry point exits with code 0 on successful run."""
        # For TDD, we can test the main() function directly with mocks
        from self_care import main
        with patch("sys.argv", ["self_care.py", "--trigger", "manual"]):
            with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                with patch("self_care.SelfCare.record") as mock_record:
                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 0 or e.code is None

    def test_protocol_session_step_args_accepted(self, mock_env):
        """P0.4: Check that self_care.py argparse accepts args defined in protocol.json schedule."""
        from self_care import main

        # Test observe step args
        with patch("sys.argv", ["self_care.py", "observe"]):
            with patch("self_care.SelfCare.observe") as mock_observe:
                with patch("self_care.SelfCare.record") as mock_record:
                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 0 or e.code is None
                    mock_observe.assert_called_once()

        # Test lesson graduation step args
        with patch("sys.argv", ["self_care.py", "--lesson-grad-only"]):
            with patch("self_care.SelfCare.lesson_graduation") as mock_lesson_grad:
                with patch("self_care.SelfCare.record") as mock_record:
                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 0 or e.code is None
                    mock_lesson_grad.assert_called_once()


class TestRunCheckedStep:
    """A3: self_care.py return-code recording via _run_checked_step."""

    def test_run_checked_step_success_records_no_error_and_step_appends(self, mock_env):
        from self_care import SelfCare

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.validate()

        assert sc.state["errors"] == []
        assert "validate" in sc.state["steps_completed"]

    def test_run_checked_step_nonzero_records_structured_error_and_skips_step(self, mock_env):
        from self_care import SelfCare

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=9, stdout="bad stdout", stderr="bad stderr")
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.validate()

        assert "validate" not in sc.state["steps_completed"]
        assert len(sc.state["errors"]) == 1

        err = sc.state["errors"][0]
        assert err["step"] == "validate"
        assert err["returncode"] == 9
        assert err["stdout_tail"] == "bad stdout"
        assert err["stderr_tail"] == "bad stderr"
        assert err["severity"] == "warn"
        assert err["ts"]
        assert any("virtualizer.py" in part for part in err["cmd"])

    def test_run_checked_step_truncates_stdout_and_stderr_tails(self):
        from self_care import _OUTPUT_TAIL_LIMIT, _run_checked_step

        long_stdout = "O" * (_OUTPUT_TAIL_LIMIT + 200)
        long_stderr = "E" * (_OUTPUT_TAIL_LIMIT + 300)
        state = {"errors": []}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=5, stdout=long_stdout, stderr=long_stderr)
            _run_checked_step(state, "validate", ["fake-cmd"])

        err = state["errors"][0]
        assert len(err["stdout_tail"]) == _OUTPUT_TAIL_LIMIT
        assert len(err["stderr_tail"]) == _OUTPUT_TAIL_LIMIT
        assert err["stdout_tail"] == long_stdout[-_OUTPUT_TAIL_LIMIT:]
        assert err["stderr_tail"] == long_stderr[-_OUTPUT_TAIL_LIMIT:]

    def test_run_checked_step_exception_records_structured_error_without_raising(self):
        from self_care import _run_checked_step

        state = {"errors": []}

        with patch("subprocess.run", side_effect=RuntimeError("boom")):
            result = _run_checked_step(state, "sync", ["fake-cmd"])

        assert result.returncode == 1
        assert len(state["errors"]) == 1
        err = state["errors"][0]
        assert err["step"] == "sync"
        assert err["returncode"] == 1
        assert err["stdout_tail"] == ""
        assert "RuntimeError: boom" in err["stderr_tail"]
        assert err["severity"] == "warn"

    def test_validate_nonzero_records_error_and_does_not_complete_step(self, mock_env):
        from self_care import SelfCare

        with patch("subprocess.run", return_value=MagicMock(returncode=2, stdout="", stderr="validate failed")):
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.validate()

        assert "validate" not in sc.state["steps_completed"]
        assert sc.state["errors"][0]["step"] == "validate"
        assert sc.state["errors"][0]["returncode"] == 2

    def test_propose_nonzero_records_error_and_does_not_complete_step(self, mock_env):
        from self_care import SelfCare

        with patch("subprocess.run", return_value=MagicMock(returncode=2, stdout="", stderr="proposal failed")):
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.state["scan_findings"] = "Saturation detected"
            sc.propose()

        assert "propose" not in sc.state["steps_completed"]
        assert sc.state["errors"][0]["step"] == "propose"
        assert sc.state["errors"][0]["returncode"] == 2

    def test_lesson_graduation_nonzero_records_error_and_does_not_complete_step(self, mock_env):
        from self_care import SelfCare

        gov_path = mock_env["sys"] / "ai" / "governance_params.json"
        gov_path.parent.mkdir(parents=True, exist_ok=True)
        gov_path.write_text(json.dumps({"lesson_graduation_auto_propose": True}), encoding="utf-8")

        knowledge_dir = mock_env["sys"] / "ai" / "knowledge" / "general"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        lessons_path = knowledge_dir / "active-lessons.jsonl"
        lesson = {
            "id": "L-FAIL",
            "status": "active",
            "title": "Failing Lesson",
            "compact_rule": "test rule",
            "source_refs": [
                {"id": "1", "type": "debate", "ts": "2026-06-25T12:00:00Z"},
                {"id": "2", "type": "debate", "ts": "2026-06-25T12:00:00Z"},
                {"id": "3", "type": "debate", "ts": "2026-06-25T12:00:00Z"},
            ],
        }
        lessons_path.write_text(json.dumps(lesson) + "\n", encoding="utf-8")

        with patch("subprocess.run", return_value=MagicMock(returncode=2, stdout="", stderr="graduation failed")):
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.lesson_graduation()

        assert "lesson_graduation" not in sc.state["steps_completed"]
        assert sc.state["graduation_candidates"] == ["L-FAIL"]
        assert sc.state["errors"][0]["step"] == "lesson_graduation"
        assert sc.state["errors"][0]["returncode"] == 2

    def test_sync_nonzero_records_error_and_does_not_complete_step(self, mock_env):
        from self_care import SelfCare

        with patch("subprocess.run", return_value=MagicMock(returncode=2, stdout="", stderr="sync failed")):
            sc = SelfCare(sys_dir=mock_env["sys"])
            sc.sync()

        assert "sync" not in sc.state["steps_completed"]
        assert sc.state["errors"][0]["step"] == "sync"
        assert sc.state["errors"][0]["returncode"] == 2


class TestProposeDedup:
    """T89: propose() must not create a new proposal for a finding-fingerprint
    that already has an open proposal recorded within the dedup window, even
    across separate SelfCare instances (simulating separate session-end runs)."""

    def test_repeated_identical_findings_only_propose_once(self, mock_env):
        from self_care import SelfCare

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_run:
            sc1 = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc1.state["scan_findings"] = "[START] ... commit_count=0\n[HIGH] core/big.py too long"
            sc1.propose()

            sc2 = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc2.state["scan_findings"] = "[START] ... commit_count=10\n[HIGH] core/big.py too long"
            sc2.propose()

        assert mock_run.call_count == 1
        assert "propose" in sc1.state["steps_completed"]
        assert "propose" in sc2.state["steps_completed"]

    def test_different_findings_propose_again(self, mock_env):
        from self_care import SelfCare

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_run:
            sc1 = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc1.state["scan_findings"] = "[HIGH] core/big.py too long"
            sc1.propose()

            sc2 = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc2.state["scan_findings"] = "[HIGH] core/other.py too long"
            sc2.propose()

        assert mock_run.call_count == 2

    def test_dedup_seen_store_persists_across_instances(self, mock_env):
        from self_care import SelfCare, _SATURATION_SEEN_FILENAME

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):
            sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc.state["scan_findings"] = "[HIGH] core/big.py too long"
            sc.propose()

        seen_path = mock_env["archive"] / _SATURATION_SEEN_FILENAME
        assert seen_path.exists()
        seen = json.loads(seen_path.read_text(encoding="utf-8"))
        assert len(seen) == 1
        entry = next(iter(seen.values()))
        assert entry["repeat_count"] == 1
        assert "first_seen" in entry and "last_seen" in entry

    def test_dedup_does_not_leave_stale_lock_file(self, mock_env):
        from self_care import SelfCare, _SATURATION_SEEN_FILENAME

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):
            sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc.state["scan_findings"] = "[HIGH] core/big.py too long"
            sc.propose()

        lock_path = mock_env["archive"] / f"{_SATURATION_SEEN_FILENAME}.lock"
        assert not lock_path.exists()

    def test_dedup_no_leftover_tmp_file_after_atomic_write(self, mock_env):
        from self_care import SelfCare, _SATURATION_SEEN_FILENAME

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):
            sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc.state["scan_findings"] = "[HIGH] core/big.py too long"
            sc.propose()

        leftovers = list(mock_env["archive"].glob(f"{_SATURATION_SEEN_FILENAME}.tmp*"))
        assert leftovers == []

    def test_stale_lock_from_a_crashed_process_is_stolen_not_permanent(self, mock_env):
        """A lock file older than the staleness threshold must be reclaimed
        instead of permanently disabling dedup (cross-review finding)."""
        import os
        from self_care import SelfCare, _SATURATION_SEEN_FILENAME, _LOCK_STALE_AFTER_SECONDS

        lock_path = mock_env["archive"] / f"{_SATURATION_SEEN_FILENAME}.lock"
        os.close(os.open(str(lock_path), os.O_CREAT | os.O_WRONLY))
        stale_time = time.time() - _LOCK_STALE_AFTER_SECONDS - 5
        os.utime(lock_path, (stale_time, stale_time))

        start = time.time()
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):
            sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc.state["scan_findings"] = "[HIGH] core/big.py too long"
            sc.propose()
        elapsed = time.time() - start

        # Should reclaim near-instantly, not burn the full 5s contention timeout.
        assert elapsed < 4.0
        assert not lock_path.exists()
        seen_path = mock_env["archive"] / _SATURATION_SEEN_FILENAME
        assert json.loads(seen_path.read_text(encoding="utf-8"))

    def test_clean_scan_does_not_trigger_a_proposal(self, mock_env):
        """A genuinely clean "0 finding(s)" report is non-empty stdout but is
        not an actual finding; propose() must not create a proposal about it
        (cross-review finding, cx, 2026-08-02)."""
        from self_care import SelfCare

        clean_report = (
            "[START] saturation-scan  sys_root=X  commit_count=10\n"
            "  lines: 0 finding(s)\n  invariants: 0 finding(s)\n  imports: 0 finding(s)\n"
            "\n=== saturation-scan: 0 finding(s) ===\n  All checks passed."
        )
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_run:
            sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc.state["scan_findings"] = clean_report
            sc.propose()

        mock_run.assert_not_called()
        assert "propose" in sc.state["steps_completed"]

    def test_lock_contention_fails_closed_not_open(self, mock_env, monkeypatch):
        """If the lock can't be acquired within the timeout, propose() must
        NOT proceed unprotected (that was an earlier version's bug -- it let
        two racing calls both mutate state). It must skip this attempt and
        leave 'propose' incomplete so a later run retries."""
        import os
        import self_care as self_care_module
        from self_care import SelfCare, _SATURATION_SEEN_FILENAME

        monkeypatch.setattr(self_care_module, "_LOCK_ACQUIRE_TIMEOUT_SECONDS", 0.3)

        lock_path = mock_env["archive"] / f"{_SATURATION_SEEN_FILENAME}.lock"
        mock_env["archive"].mkdir(parents=True, exist_ok=True)
        held_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_run:
                sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
                sc.state["scan_findings"] = "[HIGH] core/big.py too long"
                sc.propose()

            mock_run.assert_not_called()
            assert "propose" not in sc.state["steps_completed"]
            assert any("could not acquire" in e for e in sc.state["errors"])
        finally:
            os.close(held_fd)
            lock_path.unlink()

    def test_dedup_checks_open_status_not_just_elapsed_time(self, mock_env):
        """Once the tracked proposal is fully resolved (no PENDING voters
        left), a recurring fingerprint must be allowed to propose again even
        within the 7-day window -- 'at most one OPEN proposal' per T89(a),
        not 'at most one proposal per 7 days' (cross-review finding, cx,
        2026-08-02)."""
        from self_care import SelfCare, _findings_fingerprint

        findings = "[HIGH] core/big.py too long"
        fingerprint = _findings_fingerprint(findings)
        proposals_dir = mock_env["sys"] / "ai" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        proposal_path = proposals_dir / "20260802-auto--saturation-detected-001.md"
        proposal_path.write_text(
            "[PROPOSAL: 20260802-auto--saturation-detected-001]\n"
            "Votes:\n- cc: AGREE\n- ag: DISAGREE\n- cx: AGREE\n",
            encoding="utf-8",
        )

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_run:
            sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc._save_saturation_seen({
                fingerprint: {
                    "first_seen": "2026-07-30T00:00:00Z",
                    "last_seen": "2026-08-01T00:00:00Z",
                    "repeat_count": 1,
                    "proposal_id": "20260802-auto--saturation-detected-001",
                }
            })
            sc.state["scan_findings"] = findings
            sc.propose()

        # All voters resolved -> proposal is no longer open -> a fresh one is allowed.
        mock_run.assert_called_once()

    def test_dedup_stays_suppressed_while_tracked_proposal_still_pending(self, mock_env):
        """The mirror case: while the tracked proposal still has a PENDING
        voter, a recurring fingerprint must stay deduped regardless of
        elapsed time."""
        from self_care import SelfCare, _findings_fingerprint

        findings = "[HIGH] core/big.py too long"
        fingerprint = _findings_fingerprint(findings)
        proposals_dir = mock_env["sys"] / "ai" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        proposal_path = proposals_dir / "20260802-auto--saturation-detected-002.md"
        proposal_path.write_text(
            "[PROPOSAL: 20260802-auto--saturation-detected-002]\n"
            "Votes:\n- cc: AGREE\n- ag: PENDING\n- cx: AGREE\n",
            encoding="utf-8",
        )

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_run:
            sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc._save_saturation_seen({
                fingerprint: {
                    "first_seen": "2026-06-01T00:00:00Z",
                    "last_seen": "2026-06-01T00:00:00Z",
                    "repeat_count": 1,
                    "proposal_id": "20260802-auto--saturation-detected-002",
                }
            })
            sc.state["scan_findings"] = findings
            sc.propose()

        mock_run.assert_not_called()
        assert "propose" in sc.state["steps_completed"]

    def test_successful_propose_captures_proposal_id(self, mock_env):
        from self_care import SelfCare, _SATURATION_SEEN_FILENAME

        hub_stdout = (
            "[HUB] PROPOSAL-ADD 20260802-auto--saturation-detected-003 | from=cc | impact=MED\n"
            "      Vote with: hub.py proposal-vote --proposal-id ...\n"
        )
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=hub_stdout, stderr="")):
            sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc.state["scan_findings"] = "[HIGH] core/big.py too long"
            sc.propose()

        seen_path = mock_env["archive"] / _SATURATION_SEEN_FILENAME
        seen = json.loads(seen_path.read_text(encoding="utf-8"))
        entry = next(iter(seen.values()))
        assert entry["proposal_id"] == "20260802-auto--saturation-detected-003"

    def test_lock_loop_bounded_even_when_unlink_always_fails(self, mock_env, monkeypatch):
        """cx's suggested regression test: if a stale lock's unlink keeps
        raising (e.g. a genuine permissions issue, not just a dead holder),
        the acquisition loop must still return at ~timeout, not hang."""
        import os
        from pathlib import Path
        import self_care as self_care_module

        lock_path = mock_env["archive"] / "stuck.lock"
        mock_env["archive"].mkdir(parents=True, exist_ok=True)
        os.close(os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        stale_time = time.time() - self_care_module._LOCK_STALE_AFTER_SECONDS - 5
        os.utime(lock_path, (stale_time, stale_time))

        with patch.object(Path, "unlink", side_effect=OSError("permission denied")):
            start = time.monotonic()
            with self_care_module._file_lock(lock_path, timeout=0.5) as acquired:
                pass
            elapsed = time.monotonic() - start

        assert acquired is False
        assert elapsed < 2.0

    def test_skip_message_does_not_trigger_a_proposal(self, mock_env):
        """saturation_scan.py's own [SKIP] stdout line is non-empty but is not
        an actual finding; propose() must not create a proposal about it."""
        from self_care import SelfCare

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_run:
            sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc.state["scan_findings"] = "[SKIP] commit_count not tracked in state.json — use --force to run now."
            sc.propose()

        mock_run.assert_not_called()
        assert "propose" in sc.state["steps_completed"]

    def test_original_propose_test_still_holds_with_dedup(self, mock_env):
        """Sanity: the existing propose test's exact assertions must still pass
        now that propose() has an additional dedup path."""
        from self_care import SelfCare
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sc = SelfCare(sys_dir=mock_env["sys"], archive_dir=mock_env["archive"])
            sc.state["scan_findings"] = "Saturation detected"
            sc.propose()

            args, kwargs = mock_run.call_args
            cmd = " ".join(args[0])
            assert "hub.py" in cmd
            assert "proposal-add" in cmd
