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
