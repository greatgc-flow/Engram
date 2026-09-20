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
    tidy_temp.configure_paths(root=orig_paths["ROOT"], sys_dir=orig_paths["_SYS_DIR"])


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


def _collect_plan(now=None, deep=False, targets=None):
    """Flat list of planned target Paths (test helper over tidy_temp.build_plan)."""
    items = []
    for _label, key, paths in tidy_temp.build_plan(now=now, deep=deep):
        if targets is None or key in targets:
            items.extend(paths)
    return items
