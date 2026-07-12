"""check_peer_characteristics (CHK-PEER-CHR) - peer/model characteristics registry guard.

Proves the live registry is clean, and that the check fires on representative
schema violations and a past-due review_after date.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # _sys/
GUARD = ROOT / "checks" / "check_peer_characteristics.py"


def _mod():
    spec = importlib.util.spec_from_file_location("check_peer_characteristics_ut", GUARD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_live_registry_is_clean():
    errors, warnings = _mod().check_peer_characteristics()
    assert errors == []


def test_missing_registry_file_is_an_error(monkeypatch, tmp_path):
    m = _mod()
    monkeypatch.setattr(m, "REGISTRY_PATH", tmp_path / "does_not_exist.jsonl")
    errors, warnings = m.check_peer_characteristics()
    assert any("not found" in e for e in errors)


def test_invalid_json_line_is_an_error(monkeypatch, tmp_path):
    m = _mod()
    fake = tmp_path / "peer-characteristics.jsonl"
    fake.write_text("{not valid json\n", encoding="utf-8")
    monkeypatch.setattr(m, "REGISTRY_PATH", fake)
    errors, warnings = m.check_peer_characteristics()
    assert any("invalid JSON" in e for e in errors)


def test_missing_required_field_is_an_error(monkeypatch, tmp_path):
    m = _mod()
    fake = tmp_path / "peer-characteristics.jsonl"
    entry = {"id": "PC-TEST-1", "peer": "ag"}  # missing most required fields
    fake.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "REGISTRY_PATH", fake)
    errors, warnings = m.check_peer_characteristics()
    assert any("missing required field 'description'" in e for e in errors)
    assert any("missing required field 'status'" in e for e in errors)


def test_duplicate_id_is_an_error(monkeypatch, tmp_path):
    m = _mod()
    fake = tmp_path / "peer-characteristics.jsonl"
    entry = _valid_entry()
    fake.write_text(json.dumps(entry) + "\n" + json.dumps(entry) + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "REGISTRY_PATH", fake)
    errors, warnings = m.check_peer_characteristics()
    assert any("Duplicate entry id" in e for e in errors)


def test_invalid_status_is_an_error(monkeypatch, tmp_path):
    m = _mod()
    fake = tmp_path / "peer-characteristics.jsonl"
    entry = _valid_entry()
    entry["status"] = "not-a-real-status"
    fake.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "REGISTRY_PATH", fake)
    errors, warnings = m.check_peer_characteristics()
    assert any("invalid status" in e for e in errors)


def test_past_review_after_is_a_warning_not_an_error(monkeypatch, tmp_path):
    m = _mod()
    fake = tmp_path / "peer-characteristics.jsonl"
    entry = _valid_entry()
    entry["review_after"] = "2020-01-01"  # long past
    fake.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "REGISTRY_PATH", fake)
    errors, warnings = m.check_peer_characteristics()
    assert errors == []
    assert any("past its review_after date" in w for w in warnings)


def test_missing_workaround_ref_file_is_a_warning_not_an_error(monkeypatch, tmp_path):
    m = _mod()
    fake = tmp_path / "peer-characteristics.jsonl"
    entry = _valid_entry()
    entry["mitigation"]["workaround_refs"] = ["_sys/core/this_file_does_not_exist.py"]
    fake.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "REGISTRY_PATH", fake)
    errors, warnings = m.check_peer_characteristics()
    assert errors == []
    assert any("does not resolve to a file on disk" in w for w in warnings)


def test_structured_recheck_contract_fields_are_validated(monkeypatch, tmp_path):
    m = _mod()
    fake = tmp_path / "peer-characteristics.jsonl"
    entry = _valid_entry()
    entry["recheck_contract"].update({
        "runnable_probe_cmd": ["python", "_sys/checks/check_peer_capability_canary.py", "--peer", "cx.standard"],
        "expected_exit_code": 0,
        "recheck_interval_days": 7,
        "owner": "coordinator",
    })
    fake.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "REGISTRY_PATH", fake)
    errors, warnings = m.check_peer_characteristics()
    assert errors == []


def test_invalid_structured_recheck_contract_fields_are_errors(monkeypatch, tmp_path):
    m = _mod()
    fake = tmp_path / "peer-characteristics.jsonl"
    entry = _valid_entry()
    entry["recheck_contract"].update({
        "runnable_probe_cmd": "python _sys/checks/check_peer_capability_canary.py",
        "expected_exit_code": "0",
        "recheck_interval_days": 0,
        "owner": "",
    })
    fake.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "REGISTRY_PATH", fake)
    errors, warnings = m.check_peer_characteristics()
    assert any("runnable_probe_cmd must be a non-empty list of strings" in e for e in errors)
    assert any("expected_exit_code must be a non-negative integer" in e for e in errors)
    assert any("recheck_interval_days must be a positive integer" in e for e in errors)
    assert any("owner must be a non-empty string" in e for e in errors)


def _valid_entry() -> dict:
    return {
        "id": "PC-TEST-1",
        "peer": "ag",
        "description": "test entry",
        "diagnostics": {"diagnosed_at": "2026-07-11", "evidence_source_tag": "declared_unverified"},
        "mitigation": {"type": "test", "workaround_refs": [], "description": "test"},
        "status": "mitigated",
        "recheck_contract": {"trigger": "test trigger", "required_probe": "test probe"},
        "review_after": "2099-01-01",
    }
