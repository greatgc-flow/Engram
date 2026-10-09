"""Bounded-HOLD contract tests for the Sandbox wait step (EN-GAP-P1-005).

Executes .github/scripts/wait_for_sandbox.js under Node.js using
tools/release_gate/wait_for_sandbox_driver.js with stubbed GitHub API and fake timers.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import pytest

NODE_BIN = shutil.which("node")

# Skip ONLY if Node.js is not on PATH, with an explicit reason.
pytestmark = pytest.mark.skipif(
    NODE_BIN is None,
    reason="Node.js executable is not available on PATH",
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DRIVER_PATH = REPO_ROOT / "tools" / "release_gate" / "wait_for_sandbox_driver.js"
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "wait_for_sandbox.js"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "sandbox-gate.yml"


def run_driver(
    scenario: str | None = None,
    config: dict | None = None,
    script: Path | None = None,
    json_mode: bool = True,
) -> tuple[int, dict, subprocess.CompletedProcess[str]]:
    """Execute the Node driver and return (exit_code, parsed_json_or_empty, proc)."""
    assert NODE_BIN is not None, "Node.js must be available"
    cmd: list[str] = [NODE_BIN, str(DRIVER_PATH)]
    if json_mode:
        cmd.append("--json")
    if scenario:
        cmd.extend(["--scenario", scenario])
    if config:
        cmd.extend(["--config", json.dumps(config)])
    if script:
        cmd.extend(["--script", str(script)])

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    parsed: dict = {}
    if json_mode and proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            pass
    return proc.returncode, parsed, proc


class TestSandboxWaitContract:
    """Test suite verifying the bounded-HOLD contract of wait_for_sandbox.js."""

    def test_sandbox_success_resolves(self) -> None:
        """Sandbox job success => resolves with zero exit code and PASS message."""
        code, data, _ = run_driver(scenario="success")
        assert code == 0
        assert data.get("status") == "PASS"
        assert data.get("error") is None
        assert any("PASS: Sandbox completed successfully" in msg for msg in data.get("info_messages", []))

    def test_sandbox_failure_is_hold(self) -> None:
        """Sandbox job completed failure => HOLD error thrown."""
        code, data, _ = run_driver(scenario="failure")
        assert code != 0
        assert data.get("status") == "HOLD"
        assert "HOLD: Sandbox concluded failure" in (data.get("error") or "")

    def test_sandbox_cancelled_is_hold(self) -> None:
        """Sandbox job completed cancelled => HOLD error thrown."""
        code, data, _ = run_driver(scenario="cancelled")
        assert code != 0
        assert data.get("status") == "HOLD"
        assert "HOLD: Sandbox concluded cancelled" in (data.get("error") or "")

    def test_sandbox_skipped_is_hold(self) -> None:
        """Sandbox job completed skipped => HOLD error thrown."""
        code, data, _ = run_driver(scenario="skipped")
        assert code != 0
        assert data.get("status") == "HOLD"
        assert "HOLD: Sandbox concluded skipped" in (data.get("error") or "")

    def test_sandbox_job_never_appears_is_deadline_hold(self) -> None:
        """Sandbox job never appears in job list => deadline HOLD (simulated 45 min, no real wait)."""
        code, data, _ = run_driver(scenario="job_never_appears")
        assert code != 0
        assert data.get("status") == "HOLD"
        assert data.get("polls") == 180
        assert data.get("elapsed_ms") == 45 * 60 * 1000
        assert "HOLD: Sandbox runner unavailable or evidence deadline exceeded (45 minutes)" in (data.get("error") or "")

    def test_sandbox_runner_never_picks_up_is_deadline_hold(self) -> None:
        """Sandbox job stays queued without being picked up => deadline HOLD (180 polls, 45 min)."""
        code, data, _ = run_driver(scenario="runner_never_picks_up")
        assert code != 0
        assert data.get("status") == "HOLD"
        assert data.get("polls") == 180
        assert data.get("elapsed_ms") == 45 * 60 * 1000
        assert "HOLD: Sandbox runner unavailable or evidence deadline exceeded (45 minutes)" in (data.get("error") or "")

    def test_sandbox_job_appears_late_resolves(self) -> None:
        """Sandbox job appears queued/in_progress then completes success => resolves."""
        code, data, _ = run_driver(scenario="appears_late")
        assert code == 0
        assert data.get("status") == "PASS"
        assert data.get("polls", 0) > 1
        assert data.get("error") is None
        assert any("PASS: Sandbox completed successfully" in msg for msg in data.get("info_messages", []))

    def test_sandbox_api_error_is_hold_never_silent_pass(self) -> None:
        """GitHub API error => HOLD, never silent pass."""
        code, data, _ = run_driver(scenario="api_error")
        assert code != 0
        assert data.get("status") == "HOLD"
        err = data.get("error") or ""
        assert err.startswith("HOLD: GitHub API error:")
        assert "500" in err

    def test_sandbox_malformed_job_list_is_hold(self) -> None:
        """Malformed job response (not an array) => HOLD."""
        code, data, _ = run_driver(scenario="malformed_list")
        assert code != 0
        assert data.get("status") == "HOLD"
        assert "HOLD: malformed or empty job list" in (data.get("error") or "")

    def test_sandbox_null_job_list_is_hold(self) -> None:
        """Null job response => HOLD."""
        code, data, _ = run_driver(scenario="null_list")
        assert code != 0
        assert data.get("status") == "HOLD"
        assert "HOLD: malformed or empty job list" in (data.get("error") or "")

    def test_sandbox_empty_job_list_is_hold(self) -> None:
        """Empty job response array => HOLD."""
        code, data, _ = run_driver(scenario="empty_list")
        assert code != 0
        assert data.get("status") == "HOLD"
        assert "HOLD: malformed or empty job list" in (data.get("error") or "")

    def test_raw_driver_cli_exit_codes(self) -> None:
        """Verify non-JSON CLI execution: exit code 0 and stdout PASS, exit code 1 and stderr HOLD."""
        code_pass, _, proc_pass = run_driver(scenario="success", json_mode=False)
        assert code_pass == 0
        assert "PASS" in proc_pass.stdout

        code_fail, _, proc_fail = run_driver(scenario="failure", json_mode=False)
        assert code_fail == 1
        assert "HOLD: Sandbox concluded failure" in proc_fail.stderr

    def test_custom_sequence_via_config(self) -> None:
        """Configurable poll response sequence: multiple pending polls followed by success."""
        custom_config = {
            "responses": [
                [{"name": "build-candidate", "status": "completed"}],
                [{"name": "clean-room-sandbox", "status": "in_progress"}],
                [{"name": "clean-room-sandbox", "status": "completed", "conclusion": "success"}],
            ]
        }
        code, data, _ = run_driver(config=custom_config)
        assert code == 0
        assert data.get("status") == "PASS"
        assert data.get("polls") == 3
        assert data.get("elapsed_ms") == 30000

    def test_hosted_success_resolves_even_if_sandbox_queued(self) -> None:
        """Hosted job succeeds while sandbox job is still queued => resolves PASS."""
        config = {
            "responses": [
                [
                    {"name": "clean-room-sandbox", "status": "queued"},
                    {"name": "clean-room-hosted", "status": "completed", "conclusion": "success"},
                ]
            ]
        }
        code, data, _ = run_driver(config=config)
        assert code == 0
        assert data.get("status") == "PASS"
        assert any("PASS: Sandbox completed successfully" in msg for msg in data.get("info_messages", []))

    def test_hosted_success_resolves_when_sandbox_failed(self) -> None:
        """Sandbox job failed but hosted job succeeded => resolves PASS."""
        config = {
            "responses": [
                [
                    {"name": "clean-room-sandbox", "status": "completed", "conclusion": "failure"},
                    {"name": "clean-room-hosted", "status": "completed", "conclusion": "success"},
                ]
            ]
        }
        code, data, _ = run_driver(config=config)
        assert code == 0
        assert data.get("status") == "PASS"

    def test_sandbox_success_resolves_when_hosted_failed(self) -> None:
        """Hosted job failed but sandbox job succeeded => resolves PASS."""
        config = {
            "responses": [
                [
                    {"name": "clean-room-hosted", "status": "completed", "conclusion": "failure"},
                    {"name": "clean-room-sandbox", "status": "completed", "conclusion": "success"},
                ]
            ]
        }
        code, data, _ = run_driver(config=config)
        assert code == 0
        assert data.get("status") == "PASS"

    def test_both_candidate_jobs_failed_is_hold(self) -> None:
        """Both clean-room jobs failed => throws HOLD."""
        config = {
            "responses": [
                [
                    {"name": "clean-room-sandbox", "status": "completed", "conclusion": "failure"},
                    {"name": "clean-room-hosted", "status": "completed", "conclusion": "failure"},
                ]
            ]
        }
        code, data, _ = run_driver(config=config)
        assert code != 0
        assert data.get("status") == "HOLD"
        assert "HOLD: Sandbox concluded failure" in (data.get("error") or "")

    def test_hosted_failure_waits_for_sandbox_in_progress(self) -> None:
        """Hosted job failed on poll 1 while sandbox is in progress, sandbox succeeds on poll 2 => PASS."""
        config = {
            "responses": [
                [
                    {"name": "clean-room-hosted", "status": "completed", "conclusion": "failure"},
                    {"name": "clean-room-sandbox", "status": "in_progress"},
                ],
                [
                    {"name": "clean-room-hosted", "status": "completed", "conclusion": "failure"},
                    {"name": "clean-room-sandbox", "status": "completed", "conclusion": "success"},
                ],
            ]
        }
        code, data, _ = run_driver(config=config)
        assert code == 0
        assert data.get("status") == "PASS"
        assert data.get("polls") == 2
        assert data.get("elapsed_ms") == 15000

    def test_sandbox_skipped_hosted_in_progress_keeps_polling(self) -> None:
        """Sandbox skipped while hosted is in progress => keeps polling until hosted completes."""
        config = {
            "responses": [
                [
                    {"name": "clean-room-sandbox", "status": "completed", "conclusion": "skipped"},
                    {"name": "clean-room-hosted", "status": "in_progress"},
                ],
                [
                    {"name": "clean-room-sandbox", "status": "completed", "conclusion": "skipped"},
                    {"name": "clean-room-hosted", "status": "in_progress"},
                ],
                [
                    {"name": "clean-room-sandbox", "status": "completed", "conclusion": "skipped"},
                    {"name": "clean-room-hosted", "status": "completed", "conclusion": "success"},
                ],
            ]
        }
        code, data, _ = run_driver(config=config)
        assert code == 0
        assert data.get("status") == "PASS"
        assert data.get("polls") == 3
        assert data.get("elapsed_ms") == 30000
        assert any("PASS: Sandbox completed successfully" in msg for msg in data.get("info_messages", []))

    def test_sandbox_skipped_hosted_success_resolves(self) -> None:
        """Sandbox skipped but hosted succeeded => resolves PASS."""
        config = {
            "responses": [
                [
                    {"name": "clean-room-sandbox", "status": "completed", "conclusion": "skipped"},
                    {"name": "clean-room-hosted", "status": "completed", "conclusion": "success"},
                ]
            ]
        }
        code, data, _ = run_driver(config=config)
        assert code == 0
        assert data.get("status") == "PASS"
        assert any("PASS: Sandbox completed successfully" in msg for msg in data.get("info_messages", []))

    def test_sandbox_skipped_hosted_failure_is_hold(self) -> None:
        """Sandbox skipped and hosted failed => throws HOLD."""
        config = {
            "responses": [
                [
                    {"name": "clean-room-sandbox", "status": "completed", "conclusion": "skipped"},
                    {"name": "clean-room-hosted", "status": "completed", "conclusion": "failure"},
                ]
            ]
        }
        code, data, _ = run_driver(config=config)
        assert code != 0
        assert data.get("status") == "HOLD"
        assert "HOLD: Sandbox concluded" in (data.get("error") or "")

    def test_workflow_clean_room_sandbox_opt_in_guard(self) -> None:
        """Workflow asserts opt-in 'if' exists on clean-room-sandbox and clean-room-hosted has NO opt-in."""
        assert WORKFLOW_PATH.is_file(), f"Workflow file not found: {WORKFLOW_PATH}"
        text = WORKFLOW_PATH.read_text(encoding="utf-8")

        # Parse jobs from workflow text using regex (cheap regex, no yaml lib)
        sandbox_match = re.search(
            r"  clean-room-sandbox:\n(.*?)(?=\n  [a-zA-Z0-9_-]+:|\Z)",
            text,
            re.DOTALL,
        )
        assert sandbox_match is not None, "clean-room-sandbox job not found in workflow"
        sandbox_block = sandbox_match.group(1)

        hosted_match = re.search(
            r"  clean-room-hosted:\n(.*?)(?=\n  [a-zA-Z0-9_-]+:|\Z)",
            text,
            re.DOTALL,
        )
        assert hosted_match is not None, "clean-room-hosted job not found in workflow"
        hosted_block = hosted_match.group(1)

        # Opt-in 'if' must exist on clean-room-sandbox
        opt_in_pattern = r"^\s*if:\s*\${{\s*vars\.ENGRAM_SANDBOX_RUNNER\s*==\s*['\"]true['\"]\s*}}"
        assert re.search(opt_in_pattern, sandbox_block, re.MULTILINE) is not None, (
            "clean-room-sandbox must have job-level if: ${{ vars.ENGRAM_SANDBOX_RUNNER == 'true' }}"
        )

        # clean-room-hosted must NOT have any such opt-in
        assert "ENGRAM_SANDBOX_RUNNER" not in hosted_block, (
            "clean-room-hosted must not reference ENGRAM_SANDBOX_RUNNER"
        )
        hosted_header = hosted_block.split("steps:")[0]
        assert not re.search(r"^\s*if:", hosted_header, re.MULTILINE), (
            "clean-room-hosted must not have job-level 'if'"
        )
