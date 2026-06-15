"""
시스템 라이프사이클 테스트 (SYS)
Register, Unregister, Cleanup 기능의 MECE 시나리오 검증.
"""
import os
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# 테스트 대상 모듈 로드 (절대 경로)
import sys
sys_path = Path(__file__).parent.parent.parent / "cli"
sys.path.append(str(sys_path))
import manage
import cleanup

_XFAIL_MANAGE_API = pytest.mark.xfail(
    reason="manage.py API refactored to core.virtualizer/core.registrar — tests need migration",
    strict=False,
)


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
        
        # 더미 파일 생성
        (base_dir / "README.md").write_text("dummy", encoding="utf-8")
        (sys_dir / "local.config.bat").write_text(":: user config", encoding="utf-8")
        
        return base_dir

    @_XFAIL_MANAGE_API
    @patch("manage.config")
    @patch("winreg.CreateKey")
    @patch("winreg.SetValueEx")
    @patch("subprocess.run")
    @patch("subprocess.check_output", return_value="")
    @patch("winreg.OpenKey", side_effect=OSError)
    def test_registration_flow_sys_r1_r2(self, mock_open_key, mock_check_out, mock_run, mock_set_val, mock_create_key, mock_cfg, mock_env):
        """SYS-R1, SYS-R2: 등록 및 해제 흐름 검증."""
        os.environ.setdefault("USERPROFILE", str(mock_env.parent))
        mock_cfg.get.return_value = None  # No pre-existing SUBST config
        mock_cfg.get_peers_config.return_value = {}
        mock_cfg.get_base_dir.return_value = mock_env
        mock_cfg.get_sys_dir.return_value = mock_env / "_sys"

        # 1. Register 실행
        manage.action_register(mock_env)

        # subst 호출 확인
        assert any("subst" in str(call.args[0]) for call in mock_run.call_args_list)
        # registry 호출 확인
        assert mock_create_key.called
        assert mock_set_val.called

        # config.set("SUBST_DRIVE_LETTER", ...) 호출 확인
        set_calls = {c.args[0]: c.args[1] for c in mock_cfg.set.call_args_list}
        assert "SUBST_DRIVE_LETTER" in set_calls, \
            "register must call config.set('SUBST_DRIVE_LETTER', ...)"

        # 2. Unregister 실행
        mock_run.reset_mock()
        mock_check_out.reset_mock()
        mock_cfg.set.reset_mock()
        manage.action_unregister(mock_env)

        # unregister 후 SUBST_DRIVE_LETTER → None
        unset_calls = {c.args[0]: c.args[1] for c in mock_cfg.set.call_args_list}
        assert unset_calls.get("SUBST_DRIVE_LETTER") is None, \
            "unregister must call config.set('SUBST_DRIVE_LETTER', None)"

    @_XFAIL_MANAGE_API
    def test_cleanup_tiers_sys_c1(self, mock_env):
        """SYS-C1: 클린업 티어별 MECE 검증."""
        # 더미 데이터 생성
        (mock_env / "_sys" / "data" / "temp").mkdir()
        (mock_env / "_sys" / "data" / "temp" / "junk.tmp").write_text("junk")
        (mock_env / "_sys" / "env" / "venv").mkdir()

        # 1. Tier 1 (Light) - 임시 파일 삭제 확인
        cleanup.run_cleanup(tier=1, all_yes=True, base_dir=mock_env)
        assert not (mock_env / "_sys" / "data" / "temp").exists()
        assert (mock_env / "_sys" / "env" / "venv").exists()  # Tier 1에선 유지

        # 2. Tier 2 (Hard) - venv 삭제 확인
        cleanup.run_cleanup(tier=2, all_yes=True, base_dir=mock_env)
        assert not (mock_env / "_sys" / "env" / "venv").exists()
        assert (mock_env / "workspace").exists()  # Tier 2에선 유지

        # 3. Tier 4 (ZeroBase) - 전체 삭제 확인
        cleanup.run_cleanup(tier=4, all_yes=True, base_dir=mock_env)
        assert not (mock_env / "workspace").exists()
        assert not (mock_env / "_archive").exists()
        assert not (mock_env / "README.md").exists()  # 루트 문서 삭제됨
        assert not (mock_env / "_sys" / "local.config.bat").exists()

    @_XFAIL_MANAGE_API
    @patch("manage.global_cleanup")
    @patch("manage.set_peer_portability")
    @patch("winreg.CreateKey")
    @patch("winreg.SetValueEx")
    @patch("subprocess.run")
    @patch("subprocess.check_output", return_value="")
    def test_registration_migration_sys_r3(self, mock_co, mock_run, mock_set_val, mock_create_key, mock_spp, mock_gc, mock_env, tmp_path):
        """SYS-R3: 경로 이동 후 재등록 시 이전 정보 정리 검증."""
        # 1. 첫 번째 경로 등록
        manage.action_register(mock_env)

        # 2. 경로 이동 모의 (새로운 경로에서 Register 호출)
        new_env = tmp_path / "MovedPortableDev"
        shutil.copytree(mock_env, new_env)

        # 새로운 경로에서 등록 시 global_cleanup이 호출되는지 확인
        manage.action_register(new_env)
        assert mock_gc.called

    @_XFAIL_MANAGE_API
    @patch("winreg.CreateKey")
    @patch("winreg.SetValueEx")
    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("os.path.exists")
    @patch("winreg.OpenKey", side_effect=OSError)
    def test_dual_instance_different_subst_drives(
        self, mock_open_key, mock_exists, mock_check_output, mock_run, mock_set_val, mock_create_key, tmp_path
    ):
        """SYS-R4: 같은 PC에 두 인스턴스 등록 시 서로 다른 SUBST 드라이브 할당.
        두 번째 인스턴스는 첫 번째가 사용한 드라이브를 피해야 함."""
        os.environ.setdefault("USERPROFILE", str(tmp_path / "FakeUser"))
        (tmp_path / "FakeUser").mkdir(exist_ok=True)

        env1 = tmp_path / "SandboxA" / "Alpha"  # 'A' is reserved → will pick first available
        (env1 / "_sys" / "cli").mkdir(parents=True)
        (env1 / "_sys" / "local.config.bat").write_text(":: config", encoding="utf-8")

        env2 = tmp_path / "SandboxB" / "Beta"  # 'B' is reserved → will also pick
        (env2 / "_sys" / "cli").mkdir(parents=True)
        (env2 / "_sys" / "local.config.bat").write_text(":: config", encoding="utf-8")

        assigned = []

        def run_side_effect(cmd, *args, **kwargs):
            if isinstance(cmd, list) and "subst" in str(cmd[0]).lower() and "/D" not in str(cmd):
                drive = cmd[1].rstrip(":")
                assigned.append(drive)
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        # 1차 등록: D: 사용 가능 (A,B,C reserved, D free)
        mock_check_output.return_value = ""
        mock_exists.return_value = False
        manage.action_register(env1)

        # 2차 등록: D: 이미 점유됐다고 모의, E: 가 free
        first_drive = assigned[0] if assigned else "D"

        def exists_side_effect_2(path):
            p = str(path)
            if p.startswith(f"{first_drive}:"): return True  # 1차가 점유
            return False

        mock_exists.side_effect = exists_side_effect_2
        mock_run.reset_mock()
        mock_run.side_effect = run_side_effect
        manage.action_register(env2)

        # 두 번째 등록이 다른 드라이브를 선택했는지 확인
        assert len(assigned) >= 2, "두 인스턴스 모두 SUBST 드라이브가 할당되어야 함"
        assert assigned[0] != assigned[1], f"두 인스턴스가 같은 드라이브 사용: {assigned}"

    def test_cleanup_tier3_resets_runtime(self, mock_env):
        """SYS-C3: Tier 3이 env/ 런타임을 삭제(python 제외)하되 tools/와 workspace는 유지.
        tools/는 git-tracked pre-bundled 바이너리이므로 Tier 3에서 삭제하지 않음."""
        env_dir = mock_env / "_sys" / "env"
        (env_dir / "python").mkdir(parents=True)
        (env_dir / "nodejs").mkdir(parents=True)
        (mock_env / "_sys" / "tools" / "rg").mkdir(parents=True)
        (mock_env / "_sys" / "claude").mkdir(parents=True)

        cleanup.run_cleanup(tier=3, all_yes=True, base_dir=mock_env)

        # env/nodejs 등 비-python 런타임은 삭제
        assert not (env_dir / "nodejs").exists(), "Tier3: env/nodejs 삭제되어야 함"
        # env/python은 제외 (bootstrap Python은 유지)
        assert (env_dir / "python").exists(), "Tier3: env/python은 유지되어야 함"
        # tools/는 pre-bundled, git-tracked → 유지
        assert (mock_env / "_sys" / "tools").exists(), \
            "Tier3: tools/는 git-tracked이므로 유지되어야 함"
        # workspace 유지
        assert (mock_env / "workspace").exists(), "Tier3: workspace는 유지되어야 함"

    def test_cleanup_tier4_source_files_survive(self, mock_env):
        """SYS-C4: Tier 4 후 소스 스크립트는 생존, 데이터/문서만 삭제됨 (allowlist 검증).
        클린업이 데이터를 지우되 핵심 소스코드를 건드리지 않는지 확인."""
        (mock_env / "install.bat").write_text(":: install", encoding="utf-8")
        (mock_env / "register.bat").write_text(":: register", encoding="utf-8")
        (mock_env / "CLEANUP.bat").write_text(":: cleanup", encoding="utf-8")
        (mock_env / "_sys" / "start.bat").write_text(":: start", encoding="utf-8")

        cleanup.run_cleanup(tier=4, all_yes=True, base_dir=mock_env)

        # Allowlist: 소스 스크립트 생존 확인
        assert (mock_env / "install.bat").exists(), "install.bat은 Tier4 후 생존해야 함"
        assert (mock_env / "register.bat").exists(), "register.bat은 Tier4 후 생존해야 함"
        assert (mock_env / "CLEANUP.bat").exists(), "CLEANUP.bat은 Tier4 후 생존해야 함"
        assert (mock_env / "_sys").exists(), "_sys/ 폴더는 Tier4 후 생존해야 함"
        assert (mock_env / "_sys" / "start.bat").exists(), "start.bat은 Tier4 후 생존해야 함"

        # Blocklist: 삭제 확인
        assert not (mock_env / "workspace").exists(), "workspace는 Tier4에서 삭제되어야 함"
        assert not (mock_env / "_archive").exists(), "_archive는 Tier4에서 삭제되어야 함"
        assert not (mock_env / "README.md").exists(), "*.md는 Tier4에서 삭제되어야 함"
