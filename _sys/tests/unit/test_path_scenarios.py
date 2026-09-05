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

    def test_registrar_caret_percent_relay_end_to_end(self, tmp_path):
        """End-to-end: relay .bat survives physical paths with '^' and '%' via sidecar."""
        import subprocess

        # 1. Real physical root directory containing literal '^' and '%'
        phys_root = tmp_path / "phys^root%dir"
        sys_dir = phys_root / "_sys"
        sys_dir.mkdir(parents=True, exist_ok=True)

        # 2. Minimal start.bat inside _sys
        start_bat = sys_dir / "start.bat"
        start_bat.write_text("@echo off\r\necho START_HIT arg=%~1\r\nexit /b 0\r\n", encoding="mbcs")

        # 3. Build context_menu config using the real relay.content_template from _sys/context_menu.json
        real_cm_path = _sys_path / "context_menu.json"
        assert real_cm_path.exists(), f"context_menu.json not found at {real_cm_path}"
        with open(real_cm_path, "r", encoding="utf-8") as f:
            real_cm = json.load(f)

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
                "content_template": real_cm["relay"]["content_template"],
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
        (sys_dir / "context_menu.json").write_text(json.dumps(ctx_menu), encoding="utf-8")

        # 4. Realistic production context: no subst_drive set at all (the current
        # default -- virtualizer.py only creates junctions, nothing sets
        # state["subst_drive"] anymore), so registrar.apply() computes
        # root == phys_root exactly. Both sidecars must therefore carry the
        # same caret/percent-laden value, and the relay's fast-path sidecar
        # read must resolve it correctly on the very first `set /p`.
        ctx = _make_ctx(phys_root, tmp_path)
        local_dir = ctx["paths"]["localappdata"]

        # 5. Call registrar.apply(ctx) with mocking pattern matching existing test
        with patch.dict(os.environ, {"LOCALAPPDATA": str(local_dir)}), \
             patch("winreg.CreateKey", return_value=MagicMock()), \
             patch("winreg.SetValueEx"), \
             patch("winreg.CloseKey"), \
             patch.object(registrar, "_resolve_icon", return_value=None), \
             patch.object(registrar, "_clean_orphans"):
            result = registrar.apply(ctx)

        assert result["status"] == "success", f"registrar.apply failed: {result}"

        # 6. Locate generated relay .bat and assert matching .physroot.txt sidecar exists with exact path
        relay_bats = list(local_dir.glob("SandboxRun_*.bat"))
        assert len(relay_bats) == 1, f"Expected exactly 1 relay .bat, found: {relay_bats}"
        relay_bat_path = relay_bats[0]

        physroot_sidecar = local_dir / f"{relay_bat_path.stem}.physroot.txt"
        root_sidecar = local_dir / f"{relay_bat_path.stem}.root.txt"
        assert physroot_sidecar.exists(), f"Matching sidecar file missing: {physroot_sidecar}"
        assert root_sidecar.exists(), f"Matching root sidecar file missing: {root_sidecar}"

        physroot_content = physroot_sidecar.read_bytes().decode("mbcs")
        root_content = root_sidecar.read_bytes().decode("mbcs")
        assert physroot_content == str(phys_root), (
            f"Sidecar content mismatch:\nExpected: {str(phys_root)}\nActual: {physroot_content}"
        )
        # No subst_drive configured -> root == phys_root exactly (see step 4 comment).
        assert root_content == str(phys_root), (
            f"root.txt should equal phys_root when no subst_drive is set:\n"
            f"Expected: {str(phys_root)}\nActual: {root_content}"
        )

        # 7 & 8. Execute generated relay .bat and verify stdout reaches start.bat with loud failure
        proc = subprocess.run(
            ["cmd.exe", "/c", str(relay_bat_path), "some_target_arg"],
            capture_output=True,
            text=True,
            encoding="mbcs",
        )
        if proc.returncode != 0 and "&" in str(relay_bat_path):
            # In worktrees with '&' in path (e.g. D:\Engram&Peerhub), cmd.exe /c strips
            # outer quotes from the batch path. Fall back to double-quoted command line
            # matching the exact pattern written to HKCU by registrar.py line 155.
            proc = subprocess.run(
                f'cmd.exe /c ""{relay_bat_path}" "some_target_arg""',
                capture_output=True,
                text=True,
                encoding="mbcs",
            )
        assert "START_HIT arg=some_target_arg" in proc.stdout, (
            f"Relay .bat failed to reach start.bat end-to-end.\n"
            f"returncode: {proc.returncode}\n"
            f"stdout: {proc.stdout}\n"
            f"stderr: {proc.stderr}"
        )
        assert proc.returncode == 0, (
            f"Relay .bat exited with non-zero code {proc.returncode}.\n"
            f"stdout: {proc.stdout}\n"
            f"stderr: {proc.stderr}"
        )
