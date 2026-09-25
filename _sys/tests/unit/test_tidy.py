import os
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest

import sys
from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core import tidy_temp

REAL_WORKTREE = find_root(__file__).parent.resolve()


@pytest.fixture(autouse=True)
def guard_real_worktree(monkeypatch):
    """Guard ensuring no test ever targets or deletes anything in the real worktree."""
    orig_rm = tidy_temp._rm

    def guarded_rm(path: Path, apply: bool) -> int:
        resolved = Path(path).resolve()
        if resolved == REAL_WORKTREE or REAL_WORKTREE in resolved.parents:
            raise AssertionError(f"SAFETY VIOLATION: tidy attempted to touch real worktree path: {resolved}")
        return orig_rm(path, apply)

    monkeypatch.setattr(tidy_temp, "_rm", guarded_rm)

    orig_paths = {
        "ROOT": tidy_temp.ROOT,
        "_SYS_DIR": tidy_temp._SYS_DIR,
    }
    yield
    tidy_temp.configure_paths(root=orig_paths["ROOT"], sys_dir=orig_paths["_SYS_DIR"], explicit_sys_dir=False)


@pytest.fixture
def mock_env(tmp_path):
    """Fixture holding both allowlisted debris and populated never-touch set."""
    base_dir = tmp_path / "PortableDev"
    sys_dir = base_dir / "_sys"
    
    # Never-touch set
    (base_dir / ".engram").mkdir(parents=True)
    (base_dir / ".engram" / "config.json").write_text("{}")
    
    workspace = base_dir / "workspace"
    (workspace / ".peerhub").mkdir(parents=True)
    (workspace / ".peerhub" / "state.json").write_text("{}")
    (workspace / "my_project").mkdir()
    (workspace / "my_project" / "main.py").write_text("print('hello')")
    
    (sys_dir / "env" / "python").mkdir(parents=True)
    (sys_dir / "env" / "python" / "python.exe").write_text("dummy")
    
    (sys_dir / "tools" / "rg").mkdir(parents=True)
    (sys_dir / "tools" / "rg" / "rg.exe").write_text("dummy")
    
    (sys_dir / "data" / "state").mkdir(parents=True)
    (sys_dir / "data" / "state" / "register.state.json").write_text("{}")

    (sys_dir / "runtimes.json").write_text('{"runtimes": {}}')
    (sys_dir / "tool-catalog.v1.json").write_text('{"tools": []}')

    (base_dir / ".vscode").mkdir()
    (base_dir / ".vscode" / "settings.json").write_text("{}")
    
    (base_dir / "_state").write_text("{}")
    (base_dir / "WORKLOG.md").write_text("# log")
    (base_dir / "README.md").write_text("# readme")
    
    # Allowlisted debris
    (sys_dir / "tests" / ".pytest_cache").mkdir(parents=True)
    (sys_dir / "tests" / ".pytest_cache" / "v" / "cache").mkdir(parents=True)
    (sys_dir / "tests" / ".pytest_cache" / "v" / "cache" / "lastfailed").write_text("failed")
    
    (sys_dir / "core" / "__pycache__").mkdir(parents=True)
    (sys_dir / "core" / "__pycache__" / "tidy_temp.cpython-314.pyc").write_text("dummy")
    
    # launcher logs (create 7 logs so 2 are beyond 5)
    log_dir = sys_dir / "data" / "logs" / "launcher"
    log_dir.mkdir(parents=True)
    for i in range(7):
        log_file = log_dir / f"start_{i}.log"
        log_file.write_text("log content")
        # Ensure older files are sorted properly by mtime (we can set mtime but sorted by name is also fine if we just want count, but tidy uses st_mtime)
        # Let's adjust mtime so 0 is oldest, 6 is newest.
        os.utime(log_file, (1000 + i, 1000 + i))

    # pip-cache debris (real subdirectories with cached wheel/http entries)
    pip_cache_dir = sys_dir / "env" / "python" / "pip-cache"
    (pip_cache_dir / "http-v2").mkdir(parents=True)
    (pip_cache_dir / "http-v2" / "sample.whl").write_bytes(b"dummy-wheel")
        
    # Configure tidy_temp paths to point entirely within mock_env (fixes finding M-5)
    tidy_temp.configure_paths(root=base_dir, sys_dir=sys_dir)

    # Guard assertion: every planned target must resolve strictly inside mock_env
    for p in _collect_plan(deep=True):
        resolved = p.resolve()
        assert resolved != REAL_WORKTREE and REAL_WORKTREE not in resolved.parents, (
            f"SAFETY VIOLATION: Planned target resolves under real worktree: {resolved}"
        )
        assert resolved.is_relative_to(base_dir), f"Planned target outside mock_env: {resolved}"

    return base_dir

def get_snapshot(base_dir: Path):
    snapshot = {}
    for p in base_dir.rglob("*"):
        if p.is_file():
            snapshot[str(p.relative_to(base_dir))] = p.read_bytes()
    return snapshot

class TestTidy:
    
    def test_tidy_dry_run(self, mock_env):
        with patch.object(tidy_temp, "ROOT", mock_env):
            before = get_snapshot(mock_env)
            
            ctx = {"args": []}
            result = tidy_temp.run(ctx)
            
            assert result["status"] == "success"
            after = get_snapshot(mock_env)
            assert before == after
            
    @pytest.mark.parametrize("flag", ["--help", "-h", "/?"])
    def test_tidy_help_flag_prints_help_and_touches_nothing(self, flag, mock_env, capsys):
        with patch.object(tidy_temp, "ROOT", mock_env):
            before = get_snapshot(mock_env)

            result = tidy_temp.run({"args": [flag]})

            assert result["status"] == "success"
            assert get_snapshot(mock_env) == before  # help must not delete anything
            out = capsys.readouterr().out
            assert "--only" in out
            assert "Examples:" in out

    def test_tidy_apply(self, mock_env):
        with patch.object(tidy_temp, "ROOT", mock_env):
            before = get_snapshot(mock_env)

            ctx = {"args": ["--apply"]}
            result = tidy_temp.run(ctx)

            assert result["status"] == "success"
            after = get_snapshot(mock_env)
            
            # Should have deleted __pycache__ and .pytest_cache
            assert "_sys\\tests\\.pytest_cache\\v\\cache\\lastfailed" not in after
            assert "_sys\\core\\__pycache__\\tidy_temp.cpython-314.pyc" not in after
            assert not any("pip-cache" in k for k in after.keys())
            
            # Should NOT have deleted launcher logs because --deep was not passed
            logs_count = sum(1 for k in after.keys() if "launcher\\start_" in k)
            assert logs_count == 7
            
            # Never-touch set remains identical
            assert after["workspace\\.peerhub\\state.json"] == before["workspace\\.peerhub\\state.json"]
            assert after["workspace\\my_project\\main.py"] == before["workspace\\my_project\\main.py"]
            assert after[".engram\\config.json"] == before[".engram\\config.json"]
            assert after["_sys\\env\\python\\python.exe"] == before["_sys\\env\\python\\python.exe"]
            assert after["_sys\\tools\\rg\\rg.exe"] == before["_sys\\tools\\rg\\rg.exe"]
            assert after["_sys\\data\\state\\register.state.json"] == before["_sys\\data\\state\\register.state.json"]
            assert after["_sys\\runtimes.json"] == before["_sys\\runtimes.json"]
            assert after["_sys\\tool-catalog.v1.json"] == before["_sys\\tool-catalog.v1.json"]
            assert after[".vscode\\settings.json"] == before[".vscode\\settings.json"]
            assert after["_state"] == before["_state"]
            assert after["WORKLOG.md"] == before["WORKLOG.md"]
            assert after["README.md"] == before["README.md"]

    def test_tidy_apply_deep(self, mock_env):
        with patch.object(tidy_temp, "ROOT", mock_env):
            ctx = {"args": ["--apply", "--deep"]}
            result = tidy_temp.run(ctx)
            
            assert result["status"] == "success"
            after = get_snapshot(mock_env)
            
            # Should have deleted logs beyond 5
            logs_count = sum(1 for k in after.keys() if "launcher\\start_" in k)
            assert logs_count == 5
            
            # And caches
            assert "_sys\\tests\\.pytest_cache\\v\\cache\\lastfailed" not in after
            
    def test_defense_in_depth_raises_assertion(self, mock_env):
        with patch.object(tidy_temp, "ROOT", mock_env):
            # Assert that planner fed a path inside never-touch set raises AssertionError
            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected path"):
                tidy_temp._rm(mock_env / "workspace" / "my_project", True)
                
            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected root file"):
                tidy_temp._rm(mock_env / "WORKLOG.md", True)

            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected path"):
                tidy_temp._rm(mock_env / "_sys" / "runtimes.json", True)

            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected path"):
                tidy_temp._rm(mock_env / "_sys" / "tool-catalog.v1.json", True)

            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected path"):
                tidy_temp._rm(mock_env / "_sys" / "env" / "python", True)

            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected path"):
                tidy_temp._rm(mock_env / "_sys" / "env" / "python" / "python.exe", True)

    def test_pip_cache_dry_run_reports_would_delete(self, mock_env, capsys):
        """1. Confirms engram tidy (dry-run, no --apply) does not crash when PIP_CACHE_DIR
        has real subdirectories present, and correctly reports them as 'would delete' items."""
        with patch.object(tidy_temp, "ROOT", mock_env):
            pip_cache = mock_env / "_sys" / "env" / "python" / "pip-cache"
            sub = pip_cache / "http-v2"
            assert sub.is_dir()

            before = get_snapshot(mock_env)
            result = tidy_temp.run({"args": []})
            assert result["status"] == "success"

            # Dry-run must not delete anything
            after = get_snapshot(mock_env)
            assert before == after

            # Output must report pip_cache items as "would delete"
            out = capsys.readouterr().out
            assert "[pip_cache] would delete" in out
            assert "http-v2" in out

    def test_pip_cache_apply_deletes_cache_items(self, mock_env):
        """2. Confirms --apply actually deletes pip-cache items successfully while
        leaving python interpreter and other protected files intact."""
        with patch.object(tidy_temp, "ROOT", mock_env):
            pip_cache = mock_env / "_sys" / "env" / "python" / "pip-cache"
            sub = pip_cache / "http-v2"
            assert sub.exists()

            python_exe = mock_env / "_sys" / "env" / "python" / "python.exe"
            assert python_exe.exists()

            result = tidy_temp.run({"args": ["--apply", "--only", "pip_cache"]})
            assert result["status"] == "success"

            # Cache subdirectory was deleted
            assert not sub.exists()
            # Python interpreter in protected parent was untouched
            assert python_exe.exists()

    def test_defense_in_depth_other_python_paths_still_raise(self, mock_env):
        """3. Confirms other paths under _sys/env/python (not pip-cache) still trigger
        the defense-in-depth AssertionError (exception was not over-widened)."""
        with patch.object(tidy_temp, "ROOT", mock_env):
            python_dir = mock_env / "_sys" / "env" / "python"

            # Python directory itself
            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected path"):
                tidy_temp._rm(python_dir, apply=False)

            # Files directly in python directory
            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected path"):
                tidy_temp._rm(python_dir / "python.exe", apply=False)

            # Non-existent or hypothetical file/dir under python directory
            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected path"):
                tidy_temp._rm(python_dir / "hypothetical_module.py", apply=False)

            # Sibling directories under python directory that are not pip-cache
            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected path"):
                tidy_temp._rm(python_dir / "pip-cache-evil", apply=False)

            with pytest.raises(AssertionError, match="Defense in depth: tidy attempted to delete protected path"):
                tidy_temp._rm(python_dir / "Lib", apply=False)

    def test_tidy_renamed_sys_dir_safe(self, tmp_path: Path):
        """Audit finding H-1: tidy targets resolve correctly under a renamed sys directory."""
        inst = tmp_path / "inst"
        sys_dir = inst / "my_runtime"

        # 1. data/temp debris (older than 5 days)
        data_temp = sys_dir / "data" / "temp" / "pytest_c1_probe"
        data_temp.mkdir(parents=True)
        (data_temp / "debris.txt").write_text("debris")
        old_time = 1000  # long ago
        os.utime(data_temp, (old_time, old_time))

        # 2. __pycache__
        pycache = sys_dir / "core" / "__pycache__"
        pycache.mkdir(parents=True)
        (pycache / "compiled.pyc").write_text("pyc")

        # 3. .pytest_cache
        pytest_cache = sys_dir / "tests" / ".pytest_cache"
        pytest_cache.mkdir(parents=True)
        (pytest_cache / "cache.json").write_text("{}")

        # 4. launcher logs (older than 5 most recent)
        logs_dir = sys_dir / "data" / "logs"
        logs_dir.mkdir(parents=True)
        for i in range(7):
            lf = logs_dir / f"launcher_{i}.log"
            lf.write_text("log")
            os.utime(lf, (old_time + i, old_time + i))

        # 5. package manager caches
        npm_cache = sys_dir / "env" / "nodejs" / "npm-cache"
        npm_cache.mkdir(parents=True)
        (npm_cache / "cache.bin").write_text("cache")

        # Configure paths for renamed sys folder
        tidy_temp.configure_paths(root=inst, sys_dir=sys_dir)

        # Compute the plan
        plan = _collect_plan(deep=True)
        assert len(plan) > 0, "Plan should contain seeded targets"

        # Assert every target path is under inst/my_runtime and none under inst/_sys
        for p in plan:
            resolved = p.resolve()
            assert resolved != REAL_WORKTREE and REAL_WORKTREE not in resolved.parents, (
                f"SAFETY VIOLATION: Planned target resolves under real worktree: {resolved}"
            )
            assert resolved.is_relative_to(sys_dir), f"Target {p} is not under {sys_dir}"
            assert not str(resolved).startswith(str(inst / "_sys")), f"Target {p} under _sys"

        assert not (inst / "_sys").exists()

        # Run dry-run via run(ctx) and verify nothing real is deleted
        before = get_snapshot(inst)
        res = tidy_temp.run({"base_dir": inst, "sys_dir": sys_dir, "args": ["--deep"]})
        assert res["status"] == "success"
        after = get_snapshot(inst)
        assert before == after

    def test_configured_external_sys_dir_survives_planning(self, tmp_path: Path):
        base_dir = tmp_path / "Engram"
        base_dir.mkdir()
        external_sys = tmp_path / "ExternalRuntime"
        external_sys.mkdir()

        # Seed debris in external sys_dir
        pycache = external_sys / "core" / "__pycache__"
        pycache.mkdir(parents=True)
        (pycache / "foo.pyc").write_text("pyc")

        # Explicitly configure an external sys_dir (not a child of base_dir)
        tidy_temp.configure_paths(root=base_dir, sys_dir=external_sys)
        assert tidy_temp.ROOT == base_dir
        assert tidy_temp._SYS_DIR == external_sys

        # build_plan must NOT overwrite _SYS_DIR with base_dir / "_sys"
        plan = _collect_plan(deep=True)
        assert tidy_temp._SYS_DIR == external_sys, "Explicit sys_dir was overwritten during planning"
        assert len(plan) > 0
        for p in plan:
            resolved = p.resolve()
            assert resolved != REAL_WORKTREE and REAL_WORKTREE not in resolved.parents
            assert resolved.is_relative_to(external_sys), f"Target {p} is not under {external_sys}"
            assert not str(resolved).startswith(str(base_dir / "_sys")), f"Target {p} fell back to base_dir/_sys"


def _collect_plan(now=None, deep=False, targets=None):
    """Flat list of planned target Paths (test helper over tidy_temp.build_plan)."""
    items = []
    for _label, key, paths in tidy_temp.build_plan(now=now, deep=deep):
        if targets is None or key in targets:
            items.extend(paths)
    return items
