"""
시스템 라이프사이클 테스트 (SYS)
Register, Unregister, Cleanup 기능의 MECE 시나리오 검증.
Migrated from manage.py API to core.virtualizer + core.registrar (new API).
"""
import os
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import sys

_real_os_exists = os.path.exists


def _no_drive_exists(path: object) -> bool:
    """드라이브 존재 체크만 False, 실제 경로는 real check."""
    p = str(path)
    if len(p) in (2, 3) and p[1] == ":" and (len(p) == 2 or p[2] == "\\"):
        return False
    return _real_os_exists(path)

from _sys.core.root import find_root

_sys_path = find_root(__file__)
_cli_path = _sys_path / "cli"
for p in (_cli_path, _sys_path):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core import registrar  # noqa: E402


def _make_ctx(base_dir: Path, tmp_path: Path) -> dict:
    return {
        "base_dir": base_dir,
        "sys_dir": base_dir / "_sys",
        "paths": {
            "state":        tmp_path / "_state",
            "generated":    tmp_path / "_gen",
            "localappdata": tmp_path / "_local",
        },
        "args":  [],
        "state": {},
    }


class TestSystemLifecycle:

    @pytest.fixture
    def mock_env(self, tmp_path):
        """테스트를 위한 모의 환경 (BASE_DIR 및 관련 폴더)."""
        base_dir = tmp_path / "PortableDev"
        sys_dir = base_dir / "_sys"
        sys_dir.mkdir(parents=True)
        (sys_dir / "cli").mkdir()
        (sys_dir / "env").mkdir()
        (sys_dir / "data").mkdir()
        (sys_dir / "tools").mkdir()
        (base_dir / "workspace").mkdir()
        (base_dir / "_archive").mkdir()
        (base_dir / "README.md").write_text("dummy", encoding="utf-8")
        (sys_dir / "local.config.bat").write_text(":: user config", encoding="utf-8")
        return base_dir

    def test_menu_enable_disable_round_trip(self, mock_env, tmp_path):
        """menu enable/disable round-trips cleanly using registrar without virtualizer."""
        ctx = _make_ctx(mock_env, tmp_path)
        ctx_menu = {
            "win11_classic_menu": False,
            "registry": {
                "targets": {
                    "Directory": {
                        "path": r"Software\Classes\Directory\shell",
                        "arg": "%V",
                    }
                }
            },
            "entries": [
                {
                    "id": "open_folder",
                    "label": "Open Engram",
                    "targets": ["Directory"],
                    "enabled": True,
                }
            ],
        }
        (mock_env / "_sys" / "context_menu.json").write_text(json.dumps(ctx_menu), encoding="utf-8")
        with patch.object(registrar, "_write_relay"), \
             patch.object(registrar, "_write_sidecar"), \
             patch("winreg.CreateKey", return_value=MagicMock()), \
             patch("winreg.SetValueEx"), \
             patch("winreg.CloseKey"), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)), \
             patch.object(registrar, "_clean_orphans"):
            apply_res = registrar.apply(ctx)
            assert apply_res["status"] == "success"
            assert "registry_entries" in ctx["state"]

            remove_res = registrar.remove(ctx)
            assert remove_res["status"] == "success"


    def test_registrar_apply_empty_or_missing_config_is_success_not_failure(self, mock_env, tmp_path):
        """T28 regression (ag-caught): an empty/missing context_menu.json is a
        valid 'context menus disabled' state and must NOT fail the install
        pipeline. apply() returns success (skipped), never 'failed'."""
        ctx = _make_ctx(mock_env, tmp_path)
        with patch.object(registrar, "_load_context_menu", return_value={}):
            result = registrar.apply(ctx)
        assert result["status"] == "success"

    def test_registrar_remove_missing_config_is_success_not_failure(self, mock_env, tmp_path):
        """T28 regression (ag-caught): a missing context_menu.json on remove is
        fine — saved prior state drives teardown; unregister must NOT fail."""
        ctx = _make_ctx(mock_env, tmp_path)
        with patch.object(registrar, "_load_context_menu", return_value={}), \
             patch.object(registrar, "_load_state", return_value={}), \
             patch.object(registrar, "_clean_orphans", return_value=None), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = registrar.remove(ctx)
        assert result["status"] == "success"


class TestFullLifecycleMECETransitions:
    """End-to-End MECE Lifecycle State Machine & Zero-Host Residual Tests."""

    def test_full_mece_lifecycle_round_trip(self, tmp_path, monkeypatch):
        """State 1 (Initialized) -> State 2 (Registered) -> State 3 (Diagnostic Healthy)
        -> State 4 (Backup) -> State 5 (Reset) -> State 6 (Restore) -> State 7 (Tidy)
        -> State 8 (Unregistered)."""
        from core import doctor, registrar, tidy_temp
        from checks import backup_personal_data

        base_dir = tmp_path / "EngramLive"
        sys_dir = base_dir / "_sys"
        sys_dir.mkdir(parents=True)
        (base_dir / "workspace").mkdir()
        (sys_dir / "env" / "python").mkdir(parents=True)
        (sys_dir / "env" / "python" / "python.exe").write_bytes(b"MZfake")
        (sys_dir / "runtimes.json").write_text(json.dumps({
            "runtimes": {"python": {"version": "3.14.5"}},
            "tools": {},
        }), encoding="utf-8")

        # Create personal AI data under .engram/
        engram_dir = base_dir / ".engram"
        claude_dir = engram_dir / "claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text('{"theme":"dark"}', encoding="utf-8")

        # Context menu config
        ctx_menu = {
            "win11_classic_menu": False,
            "registry": {
                "targets": {
                    "Directory": {
                        "path": r"Software\Classes\Directory\shell",
                        "arg": "%V",
                    }
                }
            },
            "entries": [{"id": "open", "label": "Open Engram", "targets": ["Directory"], "enabled": True}],
        }
        (sys_dir / "context_menu.json").write_text(json.dumps(ctx_menu), encoding="utf-8")

        ctx = _make_ctx(base_dir, tmp_path)

        # 1. Registration
        with patch.object(registrar, "_write_relay"), \
             patch.object(registrar, "_write_sidecar"), \
             patch("winreg.CreateKey", return_value=MagicMock()), \
             patch("winreg.SetValueEx"), \
             patch("winreg.CloseKey"), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)), \
             patch.object(registrar, "_clean_orphans"):
            reg_res = registrar.apply(ctx)
            assert reg_res["status"] == "success"

        # 2. Doctor Health Check
        monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: "3.14.5")
        doc_res = doctor.run({"base_dir": base_dir, "sys_dir": sys_dir, "args": ["--json"]})
        assert doc_res["status"] == "success"

        # 3. Backup Personal AI State
        backup_zip = sys_dir / "data" / "backups" / "test_backup.zip"
        backup_ctx = {
            "base_dir": base_dir,
            "sys_dir": sys_dir,
            "args": ["--out", str(backup_zip)],
        }
        backup_personal_data.run_backup(backup_ctx)
        assert backup_zip.is_file(), "Backup archive must be created"

        # 4. Reset Personal State
        reset_ctx = {
            "base_dir": base_dir,
            "sys_dir": sys_dir,
            "args": ["--yes"],
        }
        backup_personal_data.run_reset(reset_ctx)
        assert not (claude_dir / "settings.json").exists(), "Live settings must be wiped on reset"

        # 5. Restore Personal State from Backup
        restore_ctx = {
            "base_dir": base_dir,
            "sys_dir": sys_dir,
            "args": [str(backup_zip), "--force"],
        }
        backup_personal_data.run_restore(restore_ctx)
        assert (claude_dir / "settings.json").is_file(), "Personal settings must be recovered after restore"
        assert json.loads((claude_dir / "settings.json").read_text(encoding="utf-8")) == {"theme": "dark"}

        # 6. Tidy Temp
        tidy_res = tidy_temp.run({"base_dir": base_dir, "sys_dir": sys_dir, "args": ["--apply"]})
        assert tidy_res.get("status") in ("success", "ok")
        # Ensure user data is 100% protected and never deleted by tidy
        assert (claude_dir / "settings.json").is_file(), "User personal data must never be touched by tidy"
        assert (base_dir / "workspace").is_dir(), "Workspace must never be touched by tidy"

        # 7. Unregistration
        with patch.object(registrar, "_load_context_menu", return_value=ctx_menu), \
             patch.object(registrar, "_clean_orphans", return_value=None), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)):
            unreg_res = registrar.remove(ctx)
            assert unreg_res["status"] == "success"
