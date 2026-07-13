"""
Path Scenarios Test (PATH)
Verify registration and execution with Korean paths and SUBST conflicts.
Migrated from manage.py API to core.virtualizer + core.registrar (new API).
"""
import datetime
import json
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import sys

_sys_path = Path(__file__).parent.parent.parent  # _sys/
if str(_sys_path) not in sys.path:
    sys.path.insert(0, str(_sys_path))

from core import virtualizer, registrar  # noqa: E402

_real_os_exists = os.path.exists


def _no_drive_exists(path: object) -> bool:
    """os.path.exists 선택적 mock: 드라이브 존재 체크만 False, 실제 경로는 real check."""
    p = str(path)
    # 드라이브 문자 체크 (X: 또는 X:\)
    if len(p) in (2, 3) and p[1] == ":" and (len(p) == 2 or p[2] == "\\"):
        return False
    return _real_os_exists(path)


def _make_ctx(base_dir: Path, tmp_path: Path) -> dict:
    local_dir = tmp_path / "_local"
    local_dir.mkdir(parents=True, exist_ok=True)
    return {
        "base_dir": base_dir,
        "sys_dir": base_dir / "_sys",
        "paths": {
            "state":        tmp_path / "_state",
            "generated":    tmp_path / "_gen",
            "localappdata": local_dir,
        },
        "args":  [],
        "state": {},
    }


class TestPathScenarios:
    @pytest.fixture
    def korean_base(self, tmp_path):
        """한글 경로를 포함한 기본 디렉터리."""
        base = tmp_path / "테스트_폴더" / "PortableDev"
        (base / "_sys" / "ai").mkdir(parents=True)
        return base

    def test_korean_path_registration(self, korean_base, tmp_path):
        """Scenario 1: 한글 물리 경로에서 SUBST 드라이브 할당."""
        with patch.object(virtualizer, "_get_subst_mappings", return_value={}), \
             patch("os.path.exists", side_effect=_no_drive_exists), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            result = virtualizer._assign_subst(korean_base, korean_base / "_sys")

        assert result is not None, "드라이브 문자가 할당되어야 함"
        subst_calls = [
            c for c in mock_run.call_args_list
            if isinstance(c.args[0], list)
            and len(c.args[0]) >= 3
            and c.args[0][0].lower() == "subst"
            and "/D" not in c.args[0]
        ]
        assert subst_calls, "subst 명령이 호출되어야 함"
        # c.args[0][2] is the base_dir path passed to subst
        assert any(c.args[0][2] == str(korean_base) for c in subst_calls), \
            "SUBST 호출에 한글 물리 경로가 포함되어야 함"

    def test_subst_drive_conflict_and_auto_pick(self, korean_base, tmp_path):
        """Scenario 2&3: P: 충돌 시 다음 가용 드라이브(D:) 자동 선택.
        예약(A,B,C), P: 실존하는 다른 경로로 점유 → mapped.exists()=True → skip → D: 선택."""
        other_dir = tmp_path / "other_sandbox"
        other_dir.mkdir()
        taken_map = {"P": other_dir}  # P: → 실존 경로 (exists()=True via real check)

        # _no_drive_exists: 드라이브 체크만 False, 실제 경로 exists()는 real check 유지
        with patch.object(virtualizer, "_get_subst_mappings", return_value=taken_map), \
             patch("os.path.exists", side_effect=_no_drive_exists), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = virtualizer._assign_subst(korean_base, korean_base / "_sys")

        # other_dir.exists()=True → P: skipped → 첫 가용 = D:
        assert result == "D", f"P: 충돌 시 D: 가 선택되어야 하지만 {result}: 가 선택됨"

    def test_unregistration_korean_path(self, korean_base, tmp_path):
        """Scenario 4: 한글 경로 해제 시 subst /D 호출."""
        with patch.object(virtualizer, "_get_subst_mappings",
                          return_value={"P": korean_base}), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            virtualizer._release_subst(korean_base)

        release_calls = [
            c for c in mock_run.call_args_list
            if isinstance(c.args[0], list) and "/D" in c.args[0]
        ]
        assert release_calls, "subst /D 가 호출되어야 함"
        assert any("P:" in str(c) for c in release_calls), "P: 가 해제되어야 함"

    def test_start_bat_emulation_logic(self, tmp_path):
        """Scenario 5: start.bat 경로 파생 로직 — SUBST 치환 후 한글 문자 제거 확인."""
        sys_dir_phys = tmp_path / "테스트_폴더" / "PortableDev" / "_sys"
        sys_dir_phys.mkdir(parents=True)
        base_dir_phys = sys_dir_phys.parent

        assert "테스트_폴더" in str(base_dir_phys)
        subst_drive = "Z:"
        target_phys = str(base_dir_phys / "workspace" / "project1")
        target_virtual = target_phys.replace(str(base_dir_phys), subst_drive)
        assert target_virtual == "Z:\\workspace\\project1"
        assert "테스트_폴더" not in target_virtual

    def test_registry_command_uses_subst_path(self, korean_base, tmp_path):
        """Scenario 6: 레지스트리 명령에 cmd.exe /c \"\" 이중인용부호 래핑 확인."""
        sys_dir = korean_base / "_sys"
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
            "relay": {
                "content_template": '@echo off\ncall "{root}\\_sys\\start.bat" "%~1"'
            },
            "entries": [
                {
                    "id": "sandbox_open",
                    "label": "Open Sandbox ({DRIVE}:)",
                    "icon": "",
                    "targets": ["Directory"],
                    "enabled": True,
                }
            ],
        }
        sys_dir.mkdir(parents=True, exist_ok=True)
        (sys_dir / "context_menu.json").write_text(json.dumps(ctx_menu), encoding="utf-8")

        ctx = _make_ctx(korean_base, tmp_path)
        ctx["state"]["subst_drive"] = "P"
        local_dir = ctx["paths"]["localappdata"]

        with patch.dict(os.environ, {"LOCALAPPDATA": str(local_dir)}), \
             patch("winreg.CreateKey", return_value=MagicMock()), \
             patch("winreg.SetValueEx") as mock_set_val, \
             patch("winreg.CloseKey"), \
             patch.object(registrar, "_resolve_icon", return_value=None), \
             patch.object(registrar, "_clean_orphans"):
            result = registrar.apply(ctx)

        assert result["status"] == "success"

        cmd_values = [
            str(c.args[4]) for c in mock_set_val.call_args_list
            if len(c.args) >= 5
            and isinstance(c.args[4], str)
            and 'cmd.exe /c ""' in c.args[4]
        ]
        assert cmd_values, 'cmd.exe /c "" 패턴이 레지스트리 명령에 있어야 함'
        for cmd in cmd_values:
            assert cmd.startswith('cmd.exe /c ""'), f"이중인용부호 래핑 없음: {cmd}"

    def test_registry_apply_reports_failed_write(self, korean_base, tmp_path):
        """A registry write error must make register fail truthfully."""
        sys_dir = korean_base / "_sys"
        sys_dir.mkdir(parents=True, exist_ok=True)
        (sys_dir / "context_menu.json").write_text(
            json.dumps(
                {
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
                            "id": "sandbox_open",
                            "label": "Open Sandbox ({DRIVE}:)",
                            "icon": "",
                            "targets": ["Directory"],
                            "enabled": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        ctx = _make_ctx(korean_base, tmp_path)
        ctx["state"]["subst_drive"] = "P"

        with patch.dict(os.environ, {"LOCALAPPDATA": str(ctx["paths"]["localappdata"])}), \
             patch("winreg.CreateKey", side_effect=PermissionError("denied")), \
             patch.object(registrar, "_resolve_icon", return_value=None), \
             patch.object(registrar, "_clean_orphans"):
            result = registrar.apply(ctx)

        assert result["status"] == "failed"
        assert any("registry write failed" in error for error in result["errors"])

    def test_korean_path_with_spaces(self, tmp_path):
        """Scenario 7: 한글 + 공백 경로에서 SUBST 정상 할당."""
        base = tmp_path / "테스트 폴더" / "My PortableDev"
        (base / "_sys" / "ai").mkdir(parents=True)

        with patch.object(virtualizer, "_get_subst_mappings", return_value={}), \
             patch("os.path.exists", side_effect=_no_drive_exists), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            result = virtualizer._assign_subst(base, base / "_sys")

        assert result is not None, "한글+공백 경로에서도 드라이브가 할당되어야 함"
        subst_calls = [
            c for c in mock_run.call_args_list
            if isinstance(c.args[0], list)
            and "subst" in c.args[0][0].lower()
            and "/D" not in c.args[0]
        ]
        assert subst_calls, "subst 명령이 호출되어야 함"

    def test_reregister_after_subst_lost(self, korean_base, tmp_path):
        """Scenario 8: USB 재삽입 후 SUBST 재등록 — 두 번 모두 드라이브 할당."""
        with patch.object(virtualizer, "_get_subst_mappings", return_value={}), \
             patch("os.path.exists", side_effect=_no_drive_exists), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)):
            r1 = virtualizer._assign_subst(korean_base, korean_base / "_sys")

        # USB 재삽입 — SUBST 소멸 후 재등록
        with patch.object(virtualizer, "_get_subst_mappings", return_value={}), \
             patch("os.path.exists", side_effect=_no_drive_exists), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)):
            r2 = virtualizer._assign_subst(korean_base, korean_base / "_sys")

        assert r1 is not None, "1차 등록에서 드라이브 할당 실패"
        assert r2 is not None, "재삽입 후 재등록에서 드라이브 할당 실패"

    def test_local_config_no_non_ascii_fix(self, korean_base, tmp_path):
        """register.state.json: 드라이브 문자 저장, 한글 값 없음."""
        ctx = _make_ctx(korean_base, tmp_path)
        ctx["state"]["subst_drive"] = "P"
        ctx["state"]["junctions"] = []

        state_dir = ctx["paths"]["state"]
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "register.state.json"
        payload = {
            "timestamp": datetime.datetime.now().isoformat(),
            "base_dir":  str(korean_base),
            **ctx["state"],
        }
        state_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert "subst_drive" in data, "state에 subst_drive 키가 있어야 함"
        assert data["subst_drive"] == "P", "드라이브 문자만 저장되어야 함"
        assert not re.search(r"[가-힣]", str(data["subst_drive"])), \
            "drivevalue에 한글이 없어야 함"
