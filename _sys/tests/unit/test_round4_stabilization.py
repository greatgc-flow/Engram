from __future__ import annotations

import sys
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub  # noqa: E402
import registrar  # noqa: E402


def test_broker_submit_rejects_invalid_json_cleanly(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        hub.action_broker_submit(tmp_path, "some-target", "not valid json", origin="test")
    assert exc_info.value.code == 1
    assert "invalid JSON payload" in capsys.readouterr().err


def test_registrar_icon_cache_survives_missing_powershell(tmp_path, monkeypatch):
    def _raise(*args, **kwargs):
        raise FileNotFoundError("powershell not found")

    monkeypatch.setattr(registrar.subprocess, "run", _raise)
    exe = tmp_path / "peer.exe"
    exe.write_bytes(b"stub")
    result = registrar._resolve_icon(
        "{peer}", {"peer": exe}, tmp_path, "peer-key"
    )
    # Falls back to the raw .exe path instead of crashing on the missing powershell.
    assert result == str(exe)


def test_registrar_unregister_survives_missing_reg_exe(tmp_path, monkeypatch):
    def _raise(*args, **kwargs):
        raise FileNotFoundError("reg.exe not found")

    monkeypatch.setattr(registrar.subprocess, "run", _raise)
    monkeypatch.setattr(registrar, "_hkcu_key_state", lambda full_reg: "present")

    errors = registrar._unregister_entry(
        "peer-key", {"t1": {"path": "Software\\Classes\\*\\shell\\peer"}}, tmp_path
    )
    # No crash; the still-present key is reported as a normal (non-exception) error.
    assert any("removal" in e for e in errors)
