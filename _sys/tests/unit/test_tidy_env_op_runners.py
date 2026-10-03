import datetime
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core import tidy_temp, env_ops

@pytest.fixture
def env(tmp_path):
    base = tmp_path / "Engram"
    sys_dir = base / "_sys"
    (sys_dir / "data" / "temp" / "env-op").mkdir(parents=True)
    tidy_temp.configure_paths(root=base, sys_dir=sys_dir, explicit_sys_dir=True)
    return base, sys_dir

def _iso(days=0.0):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")

def _setup_runner(sys_dir, op_id, age_days):
    op_dir = sys_dir / "data" / "temp" / "env-op" / op_id
    runner_dir = op_dir / "runner"
    runner_dir.mkdir(parents=True)
    (runner_dir / "python.exe").write_text("stub")
    
    import os, time
    now = time.time()
    past = now - (age_days * 86400)
    os.utime(op_dir, (past, past))
    return op_dir

def test_plan_env_op_runners_returns_old_dirs(env):
    base, sys_dir = env
    now = datetime.datetime.now().timestamp()
    
    old_dir = _setup_runner(sys_dir, "op-old", 4)
    new_dir = _setup_runner(sys_dir, "op-new", 1)
    
    candidates = tidy_temp.plan_env_op_runners(now)
    assert len(candidates) == 1
    assert candidates[0] == old_dir

def test_plan_env_op_runners_returns_empty_if_journal_active(env, monkeypatch):
    base, sys_dir = env
    now = datetime.datetime.now().timestamp()
    
    _setup_runner(sys_dir, "op-old", 4)
    
    monkeypatch.setattr(env_ops, "journal_blocks", lambda s: {"kind": "install"})
    
    candidates = tidy_temp.plan_env_op_runners(now)
    assert len(candidates) == 0

def test_build_plan_includes_env_op_runners(env):
    base, sys_dir = env
    _setup_runner(sys_dir, "op-old", 4)
    
    plan = {key: items for _, key, items in tidy_temp.build_plan()}
    assert "env_op_runners" in plan
    assert len(plan["env_op_runners"]) == 1
