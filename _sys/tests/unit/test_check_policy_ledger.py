"""Tests for check_policy_ledger.py (CHK-LEDGER, Task 9).

Motivated by a real incident: intelligence-scores.md's status banner said a
policy decision was "unapplied" for hours after it had actually landed --
nobody re-checked it against the real config. These tests exercise the
generic re-verification mechanism (json_value / text_contains checks against
live files for every status="applied" decision) without depending on the
repo's real ledger content (that's covered separately by running the checker
against the live tree, e.g. as part of the pre-commit hook).
"""
import json
import sys
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "checks"))
import check_policy_ledger as cpl  # noqa: E402


def _write_ledger(ai_dir: Path, decisions: list[dict]):
    ai_dir.mkdir(parents=True, exist_ok=True)
    (ai_dir / "policy-decisions.json").write_text(
        json.dumps({"schema_version": 1, "decisions": decisions}), encoding="utf-8")


def test_no_ledger_file_is_clean(tmp_path):
    assert cpl.check_policy_ledger(tmp_path) == []


def test_malformed_json_is_reported(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "policy-decisions.json").write_text("{ not json", encoding="utf-8")
    errors = cpl.check_policy_ledger(tmp_path)
    assert len(errors) == 1
    assert "failed to parse" in errors[0]


def test_missing_decision_id_is_reported(tmp_path):
    _write_ledger(tmp_path, [{"status": "proposed"}])
    errors = cpl.check_policy_ledger(tmp_path)
    assert any("decision_id" in e for e in errors)


def test_duplicate_decision_id_is_reported(tmp_path):
    _write_ledger(tmp_path, [
        {"decision_id": "dup", "status": "proposed"},
        {"decision_id": "dup", "status": "proposed"},
    ])
    errors = cpl.check_policy_ledger(tmp_path)
    assert any("duplicate" in e.lower() for e in errors)


def test_invalid_status_is_reported(tmp_path):
    _write_ledger(tmp_path, [{"decision_id": "d1", "status": "maybe"}])
    errors = cpl.check_policy_ledger(tmp_path)
    assert any("status must be one of" in e for e in errors)


def test_non_applied_statuses_are_not_checked(tmp_path):
    # proposed/approved/superseded decisions carry no live-verification
    # burden -- only "applied" claims something about current reality.
    _write_ledger(tmp_path, [
        {"decision_id": "d1", "status": "proposed"},
        {"decision_id": "d2", "status": "approved"},
        {"decision_id": "d3", "status": "superseded"},
    ])
    assert cpl.check_policy_ledger(tmp_path) == []


def test_applied_without_checks_is_reported(tmp_path):
    _write_ledger(tmp_path, [{"decision_id": "d1", "status": "applied"}])
    errors = cpl.check_policy_ledger(tmp_path)
    assert any("non-empty 'checks' list" in e for e in errors)


def test_applied_json_value_check_passes_when_live_matches(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg_root"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "some_config.json").write_text(
        json.dumps({"a": {"b": [1, 2, 3]}}), encoding="utf-8")
    monkeypatch.setattr(cpl, "_PORTABLE_ROOT", cfg_dir)

    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, [{
        "decision_id": "d1",
        "status": "applied",
        "checks": [{
            "kind": "json_value",
            "path": "some_config.json",
            "pointer": "/a/b",
            "expected": [1, 2, 3],
        }],
    }])
    assert cpl.check_policy_ledger(ledger_dir) == []


def test_applied_json_value_check_flags_drift_when_live_config_changed(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg_root"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "some_config.json").write_text(
        json.dumps({"a": {"b": [1, 2]}}), encoding="utf-8")  # drifted from [1,2,3]
    monkeypatch.setattr(cpl, "_PORTABLE_ROOT", cfg_dir)

    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, [{
        "decision_id": "d1",
        "status": "applied",
        "checks": [{
            "kind": "json_value",
            "path": "some_config.json",
            "pointer": "/a/b",
            "expected": [1, 2, 3],
        }],
    }])
    errors = cpl.check_policy_ledger(ledger_dir)
    assert len(errors) == 1
    assert "DRIFT" in errors[0]
    assert "d1" in errors[0]


def test_applied_text_contains_check_flags_drift_when_banner_removed(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg_root"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "notes.md").write_text("nothing relevant here", encoding="utf-8")
    monkeypatch.setattr(cpl, "_PORTABLE_ROOT", cfg_dir)

    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, [{
        "decision_id": "d1",
        "status": "applied",
        "checks": [{
            "kind": "text_contains",
            "path": "notes.md",
            "expected_substring": "RESOLVED",
        }],
    }])
    errors = cpl.check_policy_ledger(ledger_dir)
    assert len(errors) == 1
    assert "DRIFT" in errors[0]


def test_check_missing_path_is_reported_not_crashed(tmp_path):
    _write_ledger(tmp_path, [{
        "decision_id": "d1",
        "status": "applied",
        "checks": [{
            "kind": "json_value",
            "path": "does/not/exist.json",
            "pointer": "/x",
            "expected": 1,
        }],
    }])
    errors = cpl.check_policy_ledger(tmp_path)
    assert len(errors) == 1
    assert "does not exist" in errors[0]


def test_unknown_check_kind_is_reported(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg_root"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "x.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cpl, "_PORTABLE_ROOT", cfg_dir)

    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, [{
        "decision_id": "d1",
        "status": "applied",
        "checks": [{"kind": "vibes", "path": "x.json"}],
    }])
    errors = cpl.check_policy_ledger(ledger_dir)
    assert any("unknown check kind" in e for e in errors)


def test_json_pointer_resolves_list_index():
    data = {"a": [{"b": "first"}, {"b": "second"}]}
    assert cpl._resolve_json_pointer(data, "/a/1/b") == "second"


def test_json_pointer_bad_path_raises():
    with pytest.raises((KeyError, IndexError, TypeError)):
        cpl._resolve_json_pointer({"a": 1}, "/a/b")


def test_real_ledger_is_clean_against_live_tree():
    # The actual seeded decisions in this repo must currently verify clean --
    # this is the live regression test for the exact incident class this
    # checker exists to catch.
    errors = cpl.check_policy_ledger(SYS_DIR / "ai")
    assert errors == []


def test_main_returns_nonzero_on_violation(tmp_path):
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, [{"decision_id": "d1", "status": "unknown_status"}])
    rc = cpl.main(["--ai-dir", str(ledger_dir)])
    assert rc == 1


def test_main_returns_zero_when_clean(tmp_path):
    rc = cpl.main(["--ai-dir", str(tmp_path)])
    assert rc == 0
