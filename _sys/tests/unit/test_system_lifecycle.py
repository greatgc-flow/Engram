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
