"""Tests for hub.py's freshness-sweep entry point (Task 10, 2026-07-19/20
absent-audit consensus).

A single detection-only daily-cadence entry point across three drift
sources built earlier this session: CLI tool version freshness (Task 6),
AI CLI reality drift (Task 7), and policy decision drift (Task 9). Never
mutates anything -- only reports findings to PENDING_ISSUES and its own
state file. Self-gated on a minimum interval so a stray extra invocation
doesn't re-spend the same real HTTP/subprocess cost twice in one day.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
CHECKS = ROOT / "_sys" / "checks"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))
if str(CHECKS) not in sys.path:
    sys.path.insert(0, str(CHECKS))

import hub  # noqa: E402
import check_tool_updates  # noqa: E402  (ensures the module is importable for @patch("check_tool_updates...."))
import check_cli_reality  # noqa: E402
import check_policy_ledger  # noqa: E402


def _clean_ok_result():
    return {"updates_discovered": [], "up_to_date": ["ripgrep"], "errors": [], "rate_limited": []}


def _clean_refresh_results():
    return {"ag": "interval_not_expired"}


def _clean_report():
    return {"drift_summary": {"total": 0, "p0": 0, "p1": 0, "items": []}}


@pytest.fixture
def ai_root(tmp_path):
    (tmp_path / "state.json").write_text(json.dumps({"room_id": "test-room"}), encoding="utf-8")
    return tmp_path


def _handoff_pending_issues(ai_root):
    handoff_path = ai_root / "sessions" / "test-room" / "handoff.json"
    if not handoff_path.exists():
        return []
    data = json.loads(handoff_path.read_text(encoding="utf-8"))
    return data.get("sections", {}).get("PENDING_ISSUES", [])


@patch("check_policy_ledger.check_policy_ledger", return_value=[])
@patch("check_cli_reality.run", return_value=_clean_report())
@patch("check_cli_reality.auto_refresh_observed", return_value=_clean_refresh_results())
@patch("check_tool_updates.run", return_value=_clean_ok_result())
class TestFreshnessSweepClean:
    def test_first_run_executes_all_three_checks(self, mock_tu, mock_refresh, mock_report, mock_ledger, ai_root):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
        mock_tu.assert_called_once()
        mock_refresh.assert_called_once()
        mock_report.assert_called_once()
        mock_ledger.assert_called_once()

    def test_clean_run_has_no_findings(self, mock_tu, mock_refresh, mock_report, mock_ledger, ai_root):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
        state = json.loads((ai_root / hub._FRESHNESS_SWEEP_STATE_NAME).read_text(encoding="utf-8"))
        assert state["findings"] == []
        assert set(state["checks_run"]) == {"tool-updates", "cli-reality", "policy-ledger"}
        assert _handoff_pending_issues(ai_root) == []

    def test_second_run_within_interval_is_skipped(self, mock_tu, mock_refresh, mock_report, mock_ledger, ai_root):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
        mock_tu.reset_mock()
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0 + 3600)  # 1h later
        mock_tu.assert_not_called()

    def test_run_after_interval_expires(self, mock_tu, mock_refresh, mock_report, mock_ledger, ai_root):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
        mock_tu.reset_mock()
        past_min_interval = 1_000_000.0 + hub._FRESHNESS_SWEEP_MIN_INTERVAL_HOURS * 3600 + 1
        hub.action_freshness_sweep(ai_root, now_ts=past_min_interval)
        mock_tu.assert_called_once()

    def test_force_bypasses_interval_gate(self, mock_tu, mock_refresh, mock_report, mock_ledger, ai_root):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
        mock_tu.reset_mock()
        hub.action_freshness_sweep(ai_root, force=True, now_ts=1_000_000.0 + 60)
        mock_tu.assert_called_once()

    def test_state_records_last_run_timestamp(self, mock_tu, mock_refresh, mock_report, mock_ledger, ai_root):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
        state = json.loads((ai_root / hub._FRESHNESS_SWEEP_STATE_NAME).read_text(encoding="utf-8"))
        assert state["last_run_ts"] == 1_000_000.0
        assert "last_run_at" in state


@patch("check_policy_ledger.check_policy_ledger", return_value=[])
@patch("check_cli_reality.run", return_value=_clean_report())
@patch("check_cli_reality.auto_refresh_observed", return_value=_clean_refresh_results())
def test_tool_updates_findings_reported(mock_refresh, mock_report, mock_ledger, ai_root):
    with patch("check_tool_updates.run", return_value={
        "updates_discovered": [{"tool": "ripgrep"}, {"tool": "bat"}], "errors": [],
    }):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
    state = json.loads((ai_root / hub._FRESHNESS_SWEEP_STATE_NAME).read_text(encoding="utf-8"))
    assert any("tool-updates" in f and "2 update" in f for f in state["findings"])
    issues = _handoff_pending_issues(ai_root)
    assert any("freshness-sweep" in i and "tool-updates" in i for i in issues)


@patch("check_policy_ledger.check_policy_ledger", return_value=[])
@patch("check_tool_updates.run", return_value=_clean_ok_result())
def test_cli_reality_drift_findings_reported(mock_tu, mock_ledger, ai_root):
    with patch("check_cli_reality.auto_refresh_observed", return_value={"cc": "refreshed"}), \
         patch("check_cli_reality.run", return_value={
             "drift_summary": {"total": 2, "p0": 1, "p1": 1, "items": []}}):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
    state = json.loads((ai_root / hub._FRESHNESS_SWEEP_STATE_NAME).read_text(encoding="utf-8"))
    assert any("cli-reality" in f and "2 drift" in f for f in state["findings"])


@patch("check_cli_reality.run", return_value=_clean_report())
@patch("check_cli_reality.auto_refresh_observed", return_value=_clean_refresh_results())
@patch("check_tool_updates.run", return_value=_clean_ok_result())
def test_policy_ledger_drift_findings_reported(mock_tu, mock_refresh, mock_report, ai_root):
    with patch("check_policy_ledger.check_policy_ledger", return_value=["d1: DRIFT -- x"]):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
    state = json.loads((ai_root / hub._FRESHNESS_SWEEP_STATE_NAME).read_text(encoding="utf-8"))
    assert any("policy-ledger" in f and "1 drift" in f for f in state["findings"])


@patch("check_policy_ledger.check_policy_ledger", return_value=[])
@patch("check_cli_reality.run", return_value=_clean_report())
@patch("check_cli_reality.auto_refresh_observed", return_value=_clean_refresh_results())
def test_one_check_failing_does_not_crash_the_others(mock_refresh, mock_report, mock_ledger, ai_root):
    with patch("check_tool_updates.run", side_effect=RuntimeError("network exploded")):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
    state = json.loads((ai_root / hub._FRESHNESS_SWEEP_STATE_NAME).read_text(encoding="utf-8"))
    assert any("tool-updates" in f and "sweep failed" in f for f in state["findings"])
    # the other two checks still ran and were recorded clean
    assert "cli-reality" in state["checks_run"]
    assert "policy-ledger" in state["checks_run"]


def test_never_calls_apply_or_install_paths(ai_root):
    # Task 10 is explicitly detection-only: assert the mutation-capable
    # entry points are never touched, not just that we didn't observe a
    # mutation this run.
    with patch("check_tool_updates.run", return_value=_clean_ok_result()) as mock_tu, \
         patch("check_tool_updates.apply_proposal") as mock_apply, \
         patch("check_cli_reality.auto_refresh_observed", return_value=_clean_refresh_results()), \
         patch("check_cli_reality.run", return_value=_clean_report()), \
         patch("check_policy_ledger.check_policy_ledger", return_value=[]):
        hub.action_freshness_sweep(ai_root, now_ts=1_000_000.0)
    mock_tu.assert_called_once_with(propose_diff=True)
    mock_apply.assert_not_called()
