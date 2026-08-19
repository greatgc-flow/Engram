from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # _sys/
GUARD = ROOT / "checks" / "check_contracts.py"


def _mod():
    spec = importlib.util.spec_from_file_location("check_contracts_gate_ut", GUARD)
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(m)
    return m


def _prepare(monkeypatch, tmp_path, rc: int, output: str = "internal error"):
    m = _mod()
    monkeypatch.setattr(m, "_STATE_FILE", tmp_path / "check_contracts_state.json")
    monkeypatch.setattr(m, "_OPERATIONAL_ERRORS_LOG", tmp_path / "operational_errors.jsonl")
    monkeypatch.setattr(m, "run_contracts", lambda: (rc, output))
    return m


def _run_main(m, args: list[str]) -> int:
    with pytest.raises(SystemExit) as exc:
        m.main(args)
    return exc.value.code


def _read_state(m) -> dict:
    return json.loads(m._STATE_FILE.read_text(encoding="utf-8"))


def _read_log_entries(m) -> list[dict]:
    if not m._OPERATIONAL_ERRORS_LOG.exists():
        return []
    return [
        json.loads(line)
        for line in m._OPERATIONAL_ERRORS_LOG.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_governed_core_internal_error_blocks_with_claude_hook_exit_2(monkeypatch, tmp_path):
    m = _prepare(monkeypatch, tmp_path, rc=2, output="pytest internal failure")
    changed = m._SYS_DIR / "ai" / "orchestration.json"

    code = _run_main(m, ["--changed-file", str(changed)])

    assert code == 2
    state = _read_state(m)
    assert state["consecutive_fail_open"] == 1

    entries = _read_log_entries(m)
    assert len(entries) == 1
    assert entries[0]["pattern"] == "CONTRACT_CHECK_FAIL_CLOSED"
    assert entries[0]["exit_code"] == 2
    assert entries[0]["process_exit_code"] == 2
    assert entries[0]["policy_exit_code"] == 3
    assert entries[0]["governed_core"] is True
    assert entries[0]["force_tier0"] is False


def test_non_governed_internal_error_is_visible_but_non_blocking(monkeypatch, tmp_path):
    m = _prepare(monkeypatch, tmp_path, rc=2, output="pytest internal failure")
    changed = m._SYS_DIR / "checks" / "non_governed_check.py"

    code = _run_main(m, ["--changed-file", str(changed)])

    assert code == 1
    state = _read_state(m)
    assert state["consecutive_fail_open"] == 1

    entries = _read_log_entries(m)
    assert len(entries) == 1
    assert entries[0]["pattern"] == "CONTRACT_CHECK_INTERNAL_ERROR"
    assert entries[0]["exit_code"] == 1
    assert entries[0]["process_exit_code"] == 1
    assert entries[0]["policy_exit_code"] == 2
    assert entries[0]["governed_core"] is False


def test_force_tier0_logs_and_downgrades_governed_core_to_non_blocking(monkeypatch, tmp_path):
    m = _prepare(monkeypatch, tmp_path, rc=2, output="pytest internal failure")
    changed = m._SYS_DIR / "ai" / "orchestration.json"

    code = _run_main(m, ["--changed-file", str(changed), "--force-tier0"])

    assert code == 1
    state = _read_state(m)
    assert state["consecutive_fail_open"] == 1

    entries = _read_log_entries(m)
    assert len(entries) == 1
    assert entries[0]["pattern"] == "CONTRACT_CHECK_FAIL_CLOSED_OVERRIDE"
    assert entries[0]["exit_code"] == 1
    assert entries[0]["process_exit_code"] == 1
    assert entries[0]["policy_exit_code"] == 3
    assert entries[0]["governed_core"] is True
    assert entries[0]["force_tier0"] is True
    assert "force_tier0=True" in entries[0]["detail"]


def test_three_consecutive_fail_opens_then_escalates_to_blocking_exit_2(monkeypatch, tmp_path):
    m = _prepare(monkeypatch, tmp_path, rc=2, output="pytest internal failure")
    changed = m._SYS_DIR / "checks" / "non_governed_check.py"

    assert _run_main(m, ["--changed-file", str(changed)]) == 1
    assert _run_main(m, ["--changed-file", str(changed)]) == 1
    assert _run_main(m, ["--changed-file", str(changed)]) == 1
    assert _run_main(m, ["--changed-file", str(changed)]) == 2

    state = _read_state(m)
    assert state["consecutive_fail_open"] == 4

    entries = _read_log_entries(m)
    assert len(entries) == 4
    assert entries[-1]["pattern"] == "CONTRACT_CHECK_FAIL_OPEN_CAP_EXCEEDED"
    assert entries[-1]["exit_code"] == 2
    assert entries[-1]["process_exit_code"] == 2
    assert entries[-1]["policy_exit_code"] == 4
    assert entries[-1]["consecutive_fail_open"] == 4


def test_successful_run_resets_consecutive_counter(monkeypatch, tmp_path):
    m = _prepare(monkeypatch, tmp_path, rc=0, output="1 passed")
    m._STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    m._STATE_FILE.write_text(
        json.dumps({
            "consecutive_fail_open": 2,
            "last_result": "internal_failure",
            "last_ts": "2026-07-12T00:00:00Z",
        }),
        encoding="utf-8",
    )

    changed = m._SYS_DIR / "ai" / "orchestration.json"
    code = _run_main(m, ["--changed-file", str(changed)])

    assert code == 0
    state = _read_state(m)
    assert state["consecutive_fail_open"] == 0
    assert state["last_result"] == "pass"


def test_real_contract_violation_blocks_and_never_increments_counter(monkeypatch, tmp_path):
    m = _prepare(monkeypatch, tmp_path, rc=1, output="contract failed")
    m._STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    m._STATE_FILE.write_text(
        json.dumps({
            "consecutive_fail_open": 2,
            "last_result": "internal_failure",
            "last_ts": "2026-07-12T00:00:00Z",
        }),
        encoding="utf-8",
    )

    changed = m._SYS_DIR / "ai" / "orchestration.json"
    code = _run_main(m, ["--changed-file", str(changed)])

    assert code == 2
    state = _read_state(m)
    assert state["consecutive_fail_open"] == 2
    assert state["last_result"] == "contract_violation"
    assert _read_log_entries(m) == []
