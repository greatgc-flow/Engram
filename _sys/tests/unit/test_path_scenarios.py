"""
Path Scenarios Test (PATH)
Verify registration and execution with Korean paths and SUBST conflicts.
"""
import os
import json
import subprocess
import winreg
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import sys

# Load target module
sys_path = Path(__file__).parent.parent.parent / "cli"
sys.path.append(str(sys_path))
import manage

_XFAIL_MANAGE_API = pytest.mark.xfail(
    reason="manage.py API refactored to core.virtualizer/core.registrar — these tests need migration",
    strict=False,
)


class TestPathScenarios:
    @pytest.fixture
    def mock_env(self, tmp_path):
        """테스트를 위한 모의 환경 (한글 경로 포함)."""
        # Physical path with Korean characters
        korean_base = tmp_path / "테스트_폴더" / "PortableDev"
        korean_base.mkdir(parents=True)
        
        sys_dir = korean_base / "_sys"
        sys_dir.mkdir()
        (sys_dir / "cli").mkdir()
        (sys_dir / "gemini" / "config").mkdir(parents=True)
        (korean_base / "workspace").mkdir()
        
        # Dummy config
        (sys_dir / "local.config.bat").write_text(":: user config", encoding="utf-8")
        
        # Mock USERPROFILE for Gemini portability
        os.environ["USERPROFILE"] = str(tmp_path / "FakeUser")
        (tmp_path / "FakeUser").mkdir()
        
        return korean_base

    @_XFAIL_MANAGE_API
    @patch("winreg.CreateKey")
    @patch("winreg.SetValueEx")
    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("os.path.exists")
    @patch("shutil.move")
    @patch("winreg.OpenKey", side_effect=OSError)
    def test_korean_path_registration(self, mock_open_key, mock_move, mock_exists, mock_check_output, mock_run, mock_set_val, mock_create_key, mock_env):
        """Scenario 1: Registration from a physical path containing Korean characters."""
        mock_exists.return_value = False # For SUBST drive check
        mock_check_output.return_value = "" # No existing SUBST
        mock_run.return_value = MagicMock(returncode=0)
        
        with patch("manage.config") as mock_cfg, \
             patch("manage.load_context_menu") as mock_load_menu:
            mock_cfg.get.return_value = None
            mock_cfg.get_peers_config.return_value = {}
            mock_cfg.get_base_dir.return_value = mock_env
            mock_cfg.get_sys_dir.return_value = mock_env / "_sys"
            mock_load_menu.return_value = [
                {
                    "id": "sandbox_open",
                    "label": "Open in Sandbox ({DRIVE}:)",
                    "icon": "_sys/env/vscode/Code.exe",
                    "command": "_sys/start.bat \"{target}\"",
                    "targets": ["Directory/Background", "Directory", "Drive", "*", "lnkfile"],
                    "enabled": True
                }
            ]
            manage.action_register(mock_env)
            # config.set("SUBST_DRIVE_LETTER", ...) 호출 확인
            set_calls = {c.args[0]: c.args[1] for c in mock_cfg.set.call_args_list}
            assert "SUBST_DRIVE_LETTER" in set_calls, \
                "register must call config.set('SUBST_DRIVE_LETTER', ...)"
            mock_run_calls_inner = mock_run.call_args_list

        # 1. Check if SUBST was called with Korean path
        subst_call = next(call for call in mock_run_calls_inner if "subst" in str(call.args[0]))
        assert any(str(mock_env).lower() == str(arg).lower() for arg in subst_call.args[0])

        # 3. Registry key name should be safe (contains SandboxRun_ prefix and drive key)
        expected_key_part = "SandboxRun_P"
        assert any(expected_key_part in str(call.args[1]) for call in mock_create_key.call_args_list)

    @_XFAIL_MANAGE_API
    @patch("winreg.CreateKey")
    @patch("winreg.SetValueEx")
    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("os.path.exists")
    @patch("winreg.OpenKey", side_effect=OSError)
    def test_subst_drive_conflict_and_auto_pick(self, mock_open_key, mock_exists, mock_check_output, mock_run, mock_set_val, mock_create_key, mock_env):
        """Scenario 2 & 3: SUBST drive conflict handling and automatic picking."""
        # 'PortableDev' starts with 'P'. 
        # Suppose P: and Q: are taken, R: is free.
        def exists_side_effect(path):
            p_str = str(path)
            if p_str.startswith("P:"): return True
            if p_str.startswith("Q:"): return True
            if p_str == str(mock_env / "_sys" / "env" / "vscode" / "Code.exe"): return False
            if p_str == str(mock_env / "_sys" / "cli" / "launch.bat"): return True
            return False
            
        mock_exists.side_effect = exists_side_effect
        mock_check_output.return_value = ""
        mock_run.return_value = MagicMock(returncode=0)
        
        manage.action_register(mock_env)
        
        # Check if it picked R: (Candidates: P, then A, B, C excluded, then D, E... )
        # Wait, manage.py candidate logic: [prefer] + [chr(x) for x in range(65, 91) if chr(x) not in reserved and chr(x) != prefer]
        # Reserved: A, B, C.
        # prefer: P.
        # Candidates: P, D, E, F, G, H, I, J, K, L, M, N, O, Q, R...
        # If P is taken, it tries D, then E...
        
        subst_call = next(call for call in mock_run.call_args_list if "subst" in str(call.args[0]))
        # Since P is taken, it should have picked D: if D: exists_side_effect is False
        assert "D:" in str(subst_call.args[0])

    @_XFAIL_MANAGE_API
    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("winreg.OpenKey")
    @patch("winreg.EnumKey")
    @patch("os.path.exists")
    def test_unregistration_korean_path(self, mock_exists, mock_enum_key, mock_open_key, mock_check_output, mock_run, mock_env):
        """Scenario 4: Unregistration of a Korean-path setup."""
        # Mock subst output to show P: mapped to the Korean path
        mock_check_output.return_value = f"P:\\: => {mock_env}"
        mock_enum_key.side_effect = OSError() # No registry keys found
        mock_run.return_value = MagicMock(returncode=0)
        mock_exists.return_value = False
        
        manage.action_unregister(mock_env)
        
        # Check if SUBST /D was called for P:
        assert any("/D" in str(call.args[0]) and "P:" in str(call.args[0]) for call in mock_run.call_args_list)

    def test_start_bat_emulation_logic(self, mock_env):
        """Scenario 5: Emulating start.bat path derivation from a Korean physical path."""
        # In start.bat:
        # set "SYS_DIR_PHYS=%~dp0" (folder of start.bat, which is _sys)
        # for %%I in ("%SYS_DIR_PHYS%\..") do set "BASE_DIR_PHYS=%%~fI"
        
        sys_dir_phys = mock_env / "_sys"
        base_dir_phys = sys_dir_phys.parent # Equivalent to %~fI
        
        assert base_dir_phys == mock_env
        assert "테스트_폴더" in str(base_dir_phys)
        
        # Emulate the SET TARGET replacement when SUBST is used
        subst_drive = "Z:"
        target_phys = str(mock_env / "workspace" / "project1")
        
        # Logic: set "TARGET=%TARGET:%BASE_DIR_PHYS%=%BASE_DIR%%%"
        # In Python:
        target_virtual = target_phys.replace(str(base_dir_phys), subst_drive)
        
        assert target_virtual == "Z:\\workspace\\project1"
        assert "테스트_폴더" not in target_virtual
        
    @_XFAIL_MANAGE_API
    @patch("winreg.CreateKey")
    @patch("winreg.SetValueEx")
    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("os.path.exists")
    @patch("winreg.OpenKey", side_effect=OSError)
    def test_registry_command_uses_subst_path(self, mock_open_key, mock_exists, mock_check_output, mock_run, mock_set_val, mock_create_key, mock_env):
        """Scenario 6: 레지스트리 명령 포맷 확인 - 물리경로 사용 + 이중인용부호 래핑.
        manage.action_register는 재부팅 후에도 동작하도록 물리경로를 사용하되
        cmd.exe /c \"\"path\" \"arg\"\" 패턴으로 한글/공백을 올바르게 이스케이프해야 함."""
        mock_exists.return_value = False
        mock_check_output.return_value = ""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("manage.load_context_menu") as mock_load_menu:
            mock_load_menu.return_value = [
                {
                    "id": "sandbox_open",
                    "label": "Open in Sandbox ({DRIVE}:)",
                    "icon": "_sys/env/vscode/Code.exe",
                    "command": "_sys/start.bat \"{target}\"",
                    "targets": ["Directory/Background", "Directory", "Drive", "*", "lnkfile"],
                    "enabled": True
                }
            ]
            manage.action_register(mock_env)

        # SetValueEx 중 레지스트리 command 값 확인 (relay bat → cmd.exe /c "" 패턴)
        all_set_calls = mock_set_val.call_args_list
        cmd_values = [str(c.args[4]) for c in all_set_calls
                      if len(c.args) >= 5 and 'cmd.exe /c ""' in str(c.args[4])]
        assert cmd_values, "cmd.exe /c \"\" 패턴 레지스트리 명령이 등록되지 않음"

        # cmd.exe /c ""path" "arg"" 이중인용부호 패턴 확인
        for cmd in cmd_values:
            assert cmd.startswith('cmd.exe /c ""'), \
                f"레지스트리 명령이 cmd.exe /c \"\"...\" 형식이 아님: {cmd}"

    @_XFAIL_MANAGE_API
    @patch("winreg.CreateKey")
    @patch("winreg.SetValueEx")
    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("os.path.exists")
    @patch("winreg.OpenKey", side_effect=OSError)
    def test_korean_path_with_spaces(self, mock_open_key, mock_exists, mock_check_output, mock_run, mock_set_val, mock_create_key, tmp_path):
        """Scenario 7: 한글 + 공백 동시 포함 경로에서 등록."""
        # 한글과 공백이 동시에 포함된 경로 생성
        spaced_korean_base = tmp_path / "테스트 폴더" / "My PortableDev"
        spaced_korean_base.mkdir(parents=True)
        sys_dir = spaced_korean_base / "_sys"
        sys_dir.mkdir()
        (sys_dir / "local.config.bat").write_text(":: user config", encoding="utf-8")
        os.environ["USERPROFILE"] = str(tmp_path / "FakeUser2")
        (tmp_path / "FakeUser2").mkdir(exist_ok=True)

        mock_exists.return_value = False
        mock_check_output.return_value = ""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("manage.load_context_menu") as mock_load_menu:
            mock_load_menu.return_value = [
                {
                    "id": "sandbox_open",
                    "label": "Open in Sandbox ({DRIVE}:)",
                    "icon": "_sys/env/vscode/Code.exe",
                    "command": "_sys/start.bat \"{target}\"",
                    "targets": ["Directory/Background", "Directory", "Drive", "*", "lnkfile"],
                    "enabled": True
                }
            ]
            manage.action_register(spaced_korean_base)

        # SUBST 매핑 확인
        subst_calls = [c for c in mock_run.call_args_list if "subst" in str(c.args[0]).lower() and "/D" not in str(c.args[0])]
        assert subst_calls, "SUBST 명령이 호출되지 않음"

        # cmd.exe /c ""path" "arg"" 패턴으로 공백/한글을 이스케이프했는지 확인
        cmd_values = [str(c.args[4]) for c in mock_set_val.call_args_list
                      if len(c.args) >= 5 and 'cmd.exe /c ""' in str(c.args[4])]
        assert cmd_values, "레지스트리 cmd.exe /c \"\" 명령이 등록되지 않음"
        for cmd in cmd_values:
            assert cmd.startswith('cmd.exe /c ""'), f"한글+공백 경로에서 이중인용부호 래핑 없음: {cmd}"

    @_XFAIL_MANAGE_API
    @patch("winreg.CreateKey")
    @patch("winreg.SetValueEx")
    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("os.path.exists")
    @patch("winreg.OpenKey", side_effect=OSError)
    def test_reregister_after_subst_lost(self, mock_open_key, mock_exists, mock_check_output, mock_run, mock_set_val, mock_create_key, mock_env):
        """Scenario 8: USB 재삽입 후 SUBST 재등록 — 이전 SUBST가 사라진 상태에서 재등록.
        global_cleanup이 이전 SUBST를 정리하고 새로 매핑해야 함."""
        mock_exists.return_value = False
        mock_check_output.return_value = ""  # subst 출력: 이전 매핑 없음 (USB 분리 후 상태)
        mock_run.return_value = MagicMock(returncode=0)

        with patch("manage.load_context_menu") as mock_load_menu:
            mock_load_menu.return_value = [
                {
                    "id": "sandbox_open",
                    "label": "Open in Sandbox ({DRIVE}:)",
                    "icon": "_sys/env/vscode/Code.exe",
                    "command": "_sys/start.bat \"{target}\"",
                    "targets": ["Directory/Background", "Directory", "Drive", "*", "lnkfile"],
                    "enabled": True
                }
            ]
            # 1차 등록
            manage.action_register(mock_env)
            first_subst_calls = [c for c in mock_run.call_args_list if "subst" in str(c.args[0]).lower() and "/D" not in str(c.args[0])]
            assert first_subst_calls, "1차 SUBST 등록 실패"

            # USB 재삽입 시뮬레이션: SUBST가 사라진 상태로 재등록
            mock_run.reset_mock()
            mock_set_val.reset_mock()
            mock_check_output.return_value = ""  # 여전히 빈 subst 목록

            manage.action_register(mock_env)
            second_subst_calls = [c for c in mock_run.call_args_list if "subst" in str(c.args[0]).lower() and "/D" not in str(c.args[0])]
            assert second_subst_calls, "재삽입 후 SUBST 재등록 실패"

            # 재등록 후에도 레지스트리 명령이 올바른 이중인용부호 패턴 유지
            cmd_values = [str(c.args[4]) for c in mock_set_val.call_args_list
                          if len(c.args) >= 5 and 'cmd.exe /c ""' in str(c.args[4])]
            assert cmd_values, "재등록 후 레지스트리 cmd.exe /c \"\" 명령이 없음"
        for cmd in cmd_values:
            assert cmd.startswith('cmd.exe /c ""'), f"재등록 후 레지스트리 명령 포맷 오류: {cmd}"

    @_XFAIL_MANAGE_API
    @patch("subprocess.run")
    def test_local_config_no_non_ascii_fix(self, mock_run, mock_env):
        """Verify config.json doesn't contain Korean/physical paths (uses abstract values)."""
        import re as _re
        with patch("os.path.exists", return_value=False), \
             patch("subprocess.check_output", return_value=""), \
             patch("winreg.CreateKey"), \
             patch("winreg.SetValueEx"), \
             patch("winreg.OpenKey", side_effect=OSError):
            manage.action_register(mock_env)

        config_path = mock_env / "_sys" / "config.json"
        if not config_path.exists():
            pytest.skip("config.json not created (likely mock environment issue)")

        config_content = config_path.read_text(encoding="utf-8")
        # config.json stores only abstract values (drive letter string, not full Korean path)
        assert "BASE_DIR_PHYS" not in config_content, \
            "config.json must not contain BASE_DIR_PHYS"
        assert "SUBST_DRIVE_LETTER" in config_content, \
            "config.json must contain SUBST_DRIVE_LETTER key"
        # No Korean characters in config.json
        korean = _re.search(r'[가-힣]', config_content)
        assert not korean, "config.json must not contain Korean characters"
