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

_cli_path = Path(__file__).parent.parent.parent / "cli"
_sys_path  = Path(__file__).parent.parent.parent
for p in (_cli_path, _sys_path):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core import virtualizer  # noqa: E402
from core import registrar  # noqa: E402
import cleanup  # noqa: E402


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

    def test_registration_flow_sys_r1_r2(self, mock_env, tmp_path):
        """SYS-R1/R2: mount 이 SUBST 할당하고 unmount 가 해제한다."""
        ctx = _make_ctx(mock_env, tmp_path)

        with patch.object(virtualizer, "_load_peers", return_value={}), \
             patch.object(virtualizer, "_get_subst_mappings", return_value={}), \
             patch("os.path.exists", side_effect=_no_drive_exists), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)):
            mount_result = virtualizer.mount(ctx)

        drive = ctx["state"].get("subst_drive")
        assert drive is not None, "mount 후 state에 subst_drive 가 있어야 함"
        assert mount_result["status"] == "success"

        # unmount — prior_state 를 통해 drive 전달 (unmount는 _load_state → prior_state 사용)
        ctx2 = _make_ctx(mock_env, tmp_path)
        ctx2["prior_state"] = {"subst_drive": drive}
        with patch.object(virtualizer, "_load_peers", return_value={}), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            unmount_result = virtualizer.unmount(ctx2)

        release_calls = [
            c for c in mock_run.call_args_list
            if isinstance(c.args[0], list) and "/D" in c.args[0]
        ]
        assert release_calls, "unmount 후 subst /D 가 호출되어야 함"
        assert unmount_result["status"] == "success"

    def test_mount_reports_failed_when_subst_assignment_is_missing(self, mock_env, tmp_path):
        ctx = _make_ctx(mock_env, tmp_path)
        with patch.object(virtualizer, "_load_peers", return_value={}), \
             patch.object(virtualizer, "_assign_subst", return_value=None):
            result = virtualizer.mount(ctx)

        assert result["status"] == "failed"
        assert "SUBST drive was not assigned" in result["errors"]

    def test_unmount_reports_failed_when_subst_mapping_remains(self, mock_env, tmp_path):
        ctx = _make_ctx(mock_env, tmp_path)
        ctx["prior_state"] = {"subst_drive": "P"}
        with patch.object(virtualizer, "_load_peers", return_value={}), \
             patch.object(virtualizer, "_get_subst_mappings", return_value={"P": mock_env}), \
             patch("subprocess.run", return_value=MagicMock(returncode=5)):
            result = virtualizer.unmount(ctx)

        assert result["status"] == "failed"
        assert "could not release SUBST drive P:" in result["errors"][0]

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

    def test_cleanup_tiers_sys_c1(self, mock_env):
        """SYS-C1: 클린업 티어별 MECE 검증."""
        (mock_env / "_sys" / "data" / "temp").mkdir()
        (mock_env / "_sys" / "data" / "temp" / "junk.tmp").write_text("junk")
        (mock_env / "_sys" / "env" / "venv").mkdir()

        cleanup.run_cleanup(tier=1, all_yes=True, base_dir=mock_env)
        assert not (mock_env / "_sys" / "data" / "temp").exists()
        assert (mock_env / "_sys" / "env" / "venv").exists()

        cleanup.run_cleanup(tier=2, all_yes=True, base_dir=mock_env)
        assert not (mock_env / "_sys" / "env" / "venv").exists()
        assert (mock_env / "workspace").exists()

        cleanup.run_cleanup(tier=4, all_yes=True, base_dir=mock_env)
        assert not (mock_env / "workspace").exists()
        assert not (mock_env / "_archive").exists()
        assert not (mock_env / "README.md").exists()
        # local.config.bat is a source config (not data) — Tier 4 does NOT delete it
        assert (mock_env / "_sys" / "local.config.bat").exists()

    def test_registration_migration_sys_r3(self, mock_env, tmp_path):
        """SYS-R3: 경로 이동 후 새 경로에서 재등록 성공 (기존 SUBST 무시)."""
        ctx1 = _make_ctx(mock_env, tmp_path)
        with patch.object(virtualizer, "_load_peers", return_value={}), \
             patch.object(virtualizer, "_get_subst_mappings", return_value={}), \
             patch("os.path.exists", side_effect=_no_drive_exists), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)):
            virtualizer.mount(ctx1)
        drive1 = ctx1["state"].get("subst_drive")

        # 경로 이동 후 새 위치에서 재등록
        new_env = tmp_path / "MovedPortableDev"
        shutil.copytree(mock_env, new_env)
        ctx2 = _make_ctx(new_env, tmp_path / "state2")

        with patch.object(virtualizer, "_load_peers", return_value={}), \
             patch.object(virtualizer, "_get_subst_mappings", return_value={}), \
             patch("os.path.exists", side_effect=_no_drive_exists), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)):
            virtualizer.mount(ctx2)

        drive2 = ctx2["state"].get("subst_drive")
        assert drive2 is not None, "새 경로에서 드라이브가 할당되어야 함"

    def test_dual_instance_different_subst_drives(self, tmp_path):
        """SYS-R4: 같은 PC에 두 인스턴스 등록 시 서로 다른 SUBST 드라이브."""
        env1 = tmp_path / "SandboxA" / "Alpha"
        (env1 / "_sys" / "ai").mkdir(parents=True)
        env2 = tmp_path / "SandboxB" / "Beta"
        (env2 / "_sys" / "ai").mkdir(parents=True)

        assigned = []

        def run_side_effect(cmd, *args, **kwargs):
            if isinstance(cmd, list) and len(cmd) >= 2 \
                    and "subst" in str(cmd[0]).lower() and "/D" not in cmd:
                letter = cmd[1].rstrip(":")
                assigned.append(letter)
            return MagicMock(returncode=0)

        # 첫 번째 인스턴스: D: 자유 (A,B,C 예약)
        with patch.object(virtualizer, "_get_subst_mappings", return_value={}), \
             patch("os.path.exists", side_effect=_no_drive_exists), \
             patch("subprocess.run", side_effect=run_side_effect):
            r1 = virtualizer._assign_subst(env1, env1 / "_sys")

        # 두 번째 인스턴스: r1: 가 다른 실존 경로로 점유됨 → 다른 드라이브 선택
        other = tmp_path / "other"
        other.mkdir()
        taken = {r1: other} if r1 else {}  # other.exists()=True → r1 skipped

        with patch.object(virtualizer, "_get_subst_mappings", return_value=taken), \
             patch("os.path.exists", side_effect=_no_drive_exists), \
             patch("subprocess.run", side_effect=run_side_effect):
            r2 = virtualizer._assign_subst(env2, env2 / "_sys")

        assert r1 is not None and r2 is not None, "두 인스턴스 모두 드라이브가 할당되어야 함"
        assert r1 != r2, f"두 인스턴스가 동일한 드라이브를 사용함: {r1}"

    def test_cleanup_tier3_resets_runtime(self, mock_env):
        """SYS-C3: Tier 3이 env/ 런타임 삭제(python 제외), tools/와 workspace는 유지."""
        env_dir = mock_env / "_sys" / "env"
        (env_dir / "python").mkdir(parents=True)
        (env_dir / "nodejs").mkdir(parents=True)
        (mock_env / "_sys" / "tools" / "rg").mkdir(parents=True)
        (mock_env / "_sys" / "claude").mkdir(parents=True)

        cleanup.run_cleanup(tier=3, all_yes=True, base_dir=mock_env)

        assert not (env_dir / "nodejs").exists(), "Tier3: env/nodejs 삭제되어야 함"
        assert (env_dir / "python").exists(), "Tier3: env/python은 유지되어야 함"
        assert (mock_env / "_sys" / "tools").exists(), "Tier3: tools/는 유지되어야 함"
        assert (mock_env / "workspace").exists(), "Tier3: workspace는 유지되어야 함"

    def test_cleanup_tier4_source_files_survive(self, mock_env):
        """SYS-C4: Tier 4 후 소스 스크립트 생존, 데이터/문서만 삭제."""
        (mock_env / "install.bat").write_text(":: install", encoding="utf-8")
        (mock_env / "register.bat").write_text(":: register", encoding="utf-8")
        (mock_env / "CLEANUP.bat").write_text(":: cleanup", encoding="utf-8")
        (mock_env / "_sys" / "start.bat").write_text(":: start", encoding="utf-8")

        cleanup.run_cleanup(tier=4, all_yes=True, base_dir=mock_env)

        assert (mock_env / "install.bat").exists(), "install.bat은 Tier4 후 생존해야 함"
        assert (mock_env / "register.bat").exists(), "register.bat은 Tier4 후 생존해야 함"
        assert (mock_env / "CLEANUP.bat").exists(), "CLEANUP.bat은 Tier4 후 생존해야 함"
        assert (mock_env / "_sys").exists(), "_sys/ 폴더는 Tier4 후 생존해야 함"
        assert (mock_env / "_sys" / "start.bat").exists(), "start.bat은 Tier4 후 생존해야 함"

        assert not (mock_env / "workspace").exists(), "workspace는 Tier4에서 삭제되어야 함"
        assert not (mock_env / "_archive").exists(), "_archive는 Tier4에서 삭제되어야 함"
        assert not (mock_env / "README.md").exists(), "*.md는 Tier4에서 삭제되어야 함"
