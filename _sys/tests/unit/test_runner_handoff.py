"""Runner handoff for the Python swap (design 6.1, review blocker B1).

The process executing `engram update --only python` runs ON env\\python, so it cannot rename that tree.
Protocol: the engine process prepares a runner copy of the interpreter outside both swap targets, writes a
handoff file and EXITS with code 75; dispatch.bat then re-runs the same command line on the runner
interpreter (ENGRAM_IN_RUNNER=1, ENGRAM_ASSUME_YES=1 when the user already confirmed).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

SYS_SRC = find_root(__file__)
sys.path.insert(0, str(SYS_SRC))

from core import dispatcher, env_ops, python_manager, repair  # noqa: E402

DISPATCH = SYS_SRC / "core" / "dispatch.bat"


def tree_hash(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@pytest.fixture
def sys_dir(tmp_path):
    d = tmp_path / "root" / "_sys"
    (d / "data" / "state").mkdir(parents=True)
    py = d / "env" / "python"
    py.mkdir(parents=True)
    (py / "python.exe").write_bytes(b"fake-python")
    (py / "python314.dll").write_bytes(b"fake-dll")
    (d / "runtimes.json").write_text(json.dumps({"runtimes": {"python": {
        "version": "3.14.9", "url": "https://www.python.org/ftp/python/3.14.9/python-3.14.9-embed-amd64.zip"}}}),
        encoding="utf-8")
    return d


# ---- prepare_runner ----------------------------------------------------------------------------------

def test_prepare_runner_copies_the_current_interpreter_outside_both_swap_targets(sys_dir):
    exe = python_manager.prepare_runner(sys_dir, "op-1", confirmed=True)
    runner_dir = sys_dir / "data" / "temp" / "env-op" / "op-1" / "runner"
    assert exe == runner_dir / "python.exe" and exe.read_bytes() == b"fake-python"
    assert (runner_dir / "python314.dll").exists()
    for target in (sys_dir / "env" / "python", sys_dir / "env" / "venv"):
        assert target not in runner_dir.parents


def test_prepare_runner_does_not_touch_env_python(sys_dir):
    before = tree_hash(sys_dir / "env" / "python")
    python_manager.prepare_runner(sys_dir, "op-1", confirmed=False)
    assert tree_hash(sys_dir / "env" / "python") == before


def test_handoff_file_has_the_runner_path_and_the_confirmation_flag(sys_dir):
    exe = python_manager.prepare_runner(sys_dir, "op-1", confirmed=True)
    lines = python_manager.handoff_path(sys_dir).read_text(encoding="utf-8").splitlines()
    assert lines == [str(exe.relative_to(sys_dir)), "1"]
    python_manager.prepare_runner(sys_dir, "op-2", confirmed=False)
    assert python_manager.handoff_path(sys_dir).read_text(encoding="utf-8").splitlines()[1] == "0"


def test_prepare_runner_replaces_a_stale_runner_for_the_same_op(sys_dir):
    python_manager.prepare_runner(sys_dir, "op-1", confirmed=False)
    stale = sys_dir / "data" / "temp" / "env-op" / "op-1" / "runner" / "stale.txt"
    stale.write_text("x")
    python_manager.prepare_runner(sys_dir, "op-1", confirmed=False)
    assert not stale.exists()


def test_prepare_runner_without_a_python_raises_cleanly(tmp_path):
    d = tmp_path / "_sys"
    (d / "data" / "state").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        python_manager.prepare_runner(d, "op-1", confirmed=False)


def test_obsolete_spawner_based_handoff_is_gone():
    assert not hasattr(python_manager, "runner_main")
    assert not hasattr(python_manager, "handoff_to_runner")


# ---- engine decides when a handoff is needed -------------------------------------------------------------------

def _det():
    return {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "stale_registry": [], "journal": None,
            "lock": None}


def _update(sys_dir, monkeypatch, args, in_runner=False, installed="3.14.8"):
    monkeypatch.setattr(repair, "detect", lambda *a, **k: _det())
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: installed)
    if in_runner:
        monkeypatch.setenv("ENGRAM_IN_RUNNER", "1")
    else:
        monkeypatch.delenv("ENGRAM_IN_RUNNER", raising=False)
    monkeypatch.delenv("ENGRAM_ASSUME_YES", raising=False)
    ctx = {"sys_dir": sys_dir, "base_dir": sys_dir.parent, "args": args, "command": "engram update"}
    return repair.update_env_main(ctx, {"python"})


def test_apply_from_the_normal_process_hands_off_and_mutates_nothing(sys_dir, monkeypatch):
    before = tree_hash(sys_dir)
    res = _update(sys_dir, monkeypatch, ["--apply", "--yes"])
    assert res["exit_code"] == 75 and res["handoff"] is True
    assert python_manager.handoff_path(sys_dir).exists()
    assert env_ops.active_journal(sys_dir) is None                 # no journal yet: nothing was started
    after = tree_hash(sys_dir)
    new_files = set(after) - set(before)
    assert all(f.startswith("data/state/env-op/") or f.startswith("data/temp/env-op/") for f in new_files)
    assert all(before[f] == after[f] for f in before)


def test_confirmation_is_carried_into_the_handoff(sys_dir, monkeypatch):
    _update(sys_dir, monkeypatch, ["--apply", "--yes"])
    assert python_manager.handoff_path(sys_dir).read_text(encoding="utf-8").splitlines()[1] == "1"


def test_dry_run_never_hands_off(sys_dir, monkeypatch, capsys):
    res = _update(sys_dir, monkeypatch, [])
    assert res["exit_code"] == 0 and not res.get("handoff")
    assert not python_manager.handoff_path(sys_dir).exists()


def test_inside_the_runner_the_plan_executes_without_another_handoff(sys_dir, monkeypatch):
    ran = []
    monkeypatch.setattr(repair, "steps_from_spec", lambda s, b, spec, **seams: [
        env_ops.Step("swap-stand-in", lambda ctx: ran.append("ran"), group="A")])
    res = _update(sys_dir, monkeypatch, ["--apply", "--yes"], in_runner=True)
    assert res["exit_code"] == 0 and ran == ["ran"] and not res.get("handoff")
    assert not python_manager.handoff_path(sys_dir).exists()


def test_assume_yes_from_the_environment_skips_the_prompt(sys_dir, monkeypatch):
    monkeypatch.setattr(repair, "steps_from_spec", lambda s, b, spec, **seams: [
        env_ops.Step("noop", lambda ctx: None, group="A")])
    monkeypatch.setattr(repair, "detect", lambda *a, **k: _det())
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.8")
    monkeypatch.setenv("ENGRAM_IN_RUNNER", "1")
    monkeypatch.setenv("ENGRAM_ASSUME_YES", "1")
    ctx = {"sys_dir": sys_dir, "base_dir": sys_dir.parent, "args": ["--apply"], "command": "engram update"}
    res = repair.update_env_main(ctx, {"python"})
    assert res["exit_code"] == 0                                    # no prompt, no "non-interactive without --yes"


def test_the_python_plan_allocates_write_ahead_paths(sys_dir, monkeypatch):
    seen = {}
    real_execute = env_ops.execute

    def spy(sd, kind, steps, **kw):
        seen["paths"] = kw.get("paths")
        return real_execute(sd, kind, steps, **kw)

    monkeypatch.setattr(env_ops, "execute", spy)
    monkeypatch.setattr(repair, "steps_from_spec", lambda s, b, spec, **seams: [env_ops.Step("noop", lambda c: None)])
    _update(sys_dir, monkeypatch, ["--apply", "--yes"], in_runner=True)
    assert set(seen["paths"]) == {"python_backup", "venv_backup", "freeze_backup", "venv_failed_backup", "venv_interp_backup"}


def test_resume_of_a_python_operation_also_goes_through_the_runner(sys_dir, monkeypatch):
    monkeypatch.delenv("ENGRAM_IN_RUNNER", raising=False)
    spec = [{"name": "update-python", "group": "A", "kind": "python", "params": {"target_version": "3.14.9", "url": "u"}}]
    det = {**_det(), "journal": {"op_id": "op-x", "kind": "update", "phase": "STEPS_RUNNING", "data": {"spec": spec}}}
    monkeypatch.setattr(repair, "detect", lambda *a, **k: det)
    ctx = {"sys_dir": sys_dir, "base_dir": sys_dir.parent, "args": ["--resume"], "command": "engram repair"}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 75 and res["handoff"] is True


def test_rollback_of_a_python_operation_also_goes_through_the_runner(sys_dir, monkeypatch):
    monkeypatch.delenv("ENGRAM_IN_RUNNER", raising=False)
    spec = [{"name": "update-python", "group": "A", "kind": "python", "params": {"target_version": "3.14.9", "url": "u"}}]
    det = {**_det(), "journal": {"op_id": "op-x", "kind": "update", "phase": "STEPS_RUNNING", "data": {"spec": spec}}}
    monkeypatch.setattr(repair, "detect", lambda *a, **k: det)
    ctx = {"sys_dir": sys_dir, "base_dir": sys_dir.parent, "args": ["--rollback"], "command": "engram repair"}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 75 and res["handoff"] is True


def test_standalone_venv_repair_allocates_backup_paths(sys_dir, monkeypatch):
    seen = {}
    real = repair.env_ops.execute

    def fake(sd, kind, steps, **kw):
        seen["paths"] = kw.get("paths")
        return {"status": "committed", "phase": "COMMITTED"}

    monkeypatch.setattr(repair.env_ops, "execute", fake)
    monkeypatch.setattr(repair, "_cli_result", lambda res, mode: {"exit_code": 0})
    monkeypatch.setattr(repair, "detect", lambda *a, **k: _det())
    monkeypatch.setattr(repair, "build_plan", lambda *a, **k: {"kind": "repair", "steps": [object()], "spec": [{"name": "x", "kind": "venv"}], "summary": []})
    ctx = {"sys_dir": sys_dir, "base_dir": sys_dir.parent, "args": ["--apply", "--yes"], "command": "engram repair"}
    repair.repair_main(ctx)
    assert seen["paths"] and "venv_backup" in seen["paths"] and "venv_failed_backup" in seen["paths"]


def test_resume_of_a_non_python_operation_does_not_hand_off(sys_dir, monkeypatch):
    monkeypatch.delenv("ENGRAM_IN_RUNNER", raising=False)
    spec = [{"name": "repair-venv", "group": "A", "kind": "venv", "params": {}}]
    det = {**_det(), "journal": {"op_id": "op-x", "kind": "repair", "phase": "STEPS_RUNNING", "data": {"spec": spec}}}
    monkeypatch.setattr(repair, "detect", lambda *a, **k: det)
    monkeypatch.setattr(env_ops, "resume", lambda sd, sf, **k: {"status": "success", "phase": "COMMITTED", "detail": "ok"})
    ctx = {"sys_dir": sys_dir, "base_dir": sys_dir.parent, "args": ["--resume"], "command": "engram repair"}
    assert repair.repair_main(ctx)["exit_code"] == 0


# ---- dispatcher: silent exit 75 -----------------------------------------------------------------------------------

def test_a_handoff_result_exits_75_without_an_error_message(monkeypatch, tmp_path, capsys):
    from types import SimpleNamespace
    fake_sys = tmp_path / "_sys"
    fake_sys.mkdir()
    (fake_sys / "dispatch.json").write_text(json.dumps({
        "operations": {"x.run": {"module": "fake.m", "method": "run", "failure_policy": "abort"}},
        "pipelines": {"x": ["x.run"]}}), encoding="utf-8")
    ctx = {"base_dir": tmp_path, "sys_dir": fake_sys, "paths": {"state": fake_sys / "data" / "state"}, "args": [],
           "command": "x", "state": {}}
    monkeypatch.setattr(dispatcher, "sys_dir", fake_sys)
    monkeypatch.setattr(dispatcher, "_build_ctx", lambda *_a: ctx)
    monkeypatch.setattr(dispatcher.importlib, "import_module",
                        lambda _n: SimpleNamespace(run=lambda _c: {"status": "success", "handoff": True, "exit_code": 75}))
    assert dispatcher.main(["dispatcher.py", "x"]) == 75
    assert "[Error]" not in capsys.readouterr().out


# ---- dispatch.bat: re-run on the runner ----------------------------------------------------------------------------

def _cmd(script, args):
    quoted = " ".join(f'"{a}"' if (" " in a or "!" in a) else a for a in args)
    return f'cmd.exe /c ""{script}" {quoted}"' if quoted else f'cmd.exe /c ""{script}""'


def _run_bat(script, args, cwd, env=None):
    return subprocess.run(_cmd(script, args), cwd=str(cwd), capture_output=True, text=True, encoding="mbcs",
                          errors="replace", env={**os.environ, **(env or {})}, timeout=120)


@pytest.fixture
def bat_root(tmp_path):
    r = tmp_path / "a&b root"
    core = r / "_sys" / "core"
    core.mkdir(parents=True)
    shutil.copy(DISPATCH, core / "dispatch.bat")
    py = r / "_sys" / "env" / "python"
    py.mkdir(parents=True)
    shutil.copy(sys.executable, py / "python.exe")
    (r / "_sys" / "data" / "state").mkdir(parents=True)
    # stub dispatcher: first (normal) run prepares a runner copy + handoff file and exits 75; the runner run prints context
    (core / "dispatcher.py").write_text(
        "import os, shutil, sys\n"
        "from pathlib import Path\n"
        "sysdir = Path(__file__).resolve().parent.parent\n"
        "if os.environ.get('ENGRAM_IN_RUNNER') == '1':\n"
        "    print('IN_RUNNER exe=' + sys.executable)\n"
        "    print('ASSUME_YES=' + os.environ.get('ENGRAM_ASSUME_YES', ''))\n"
        "    print('ARGS=' + ' '.join(sys.argv[1:]))\n"
        "    sys.exit(7)\n"
        "runner = sysdir / 'data' / 'temp' / 'env-op' / 'op' / 'runner'\n"
        "runner.mkdir(parents=True)\n"
        "shutil.copy(sys.executable, runner / 'python.exe')\n"
        "handoff = sysdir / 'data' / 'state' / 'env-op' / 'handoff.txt'\n"
        "handoff.parent.mkdir(parents=True, exist_ok=True)\n"
        "handoff.write_text(str((runner / 'python.exe').relative_to(sysdir)) + '\\n1\\n', encoding='utf-8')\n"
        "print('FIRST_RUN')\n"
        "sys.exit(75)\n", encoding="utf-8")
    return r


def test_dispatch_bat_reruns_on_the_runner_after_exit_75(bat_root):
    proc = _run_bat(bat_root / "_sys" / "core" / "dispatch.bat", ["update", "--only", "python", "--yes"], bat_root)
    assert proc.returncode == 7, proc.stdout + proc.stderr
    assert "FIRST_RUN" in proc.stdout and "IN_RUNNER" in proc.stdout
    assert "runner" in proc.stdout.split("IN_RUNNER exe=")[1].splitlines()[0]
    assert "ASSUME_YES=1" in proc.stdout
    assert "ARGS=update --only python --yes" in proc.stdout        # same command line, original arguments intact
    assert not (bat_root / "_sys" / "data" / "state" / "env-op" / "handoff.txt").exists()   # consumed


def test_dispatch_bat_without_exit_75_does_not_rerun(bat_root):
    (bat_root / "_sys" / "core" / "dispatcher.py").write_text("print('PLAIN')\n", encoding="utf-8")
    proc = _run_bat(bat_root / "_sys" / "core" / "dispatch.bat", ["doctor"], bat_root)
    assert proc.returncode == 0 and "PLAIN" in proc.stdout and "IN_RUNNER" not in proc.stdout


def test_dispatch_bat_exit_75_without_a_handoff_file_is_an_error(bat_root):
    (bat_root / "_sys" / "core" / "dispatcher.py").write_text("import sys\nsys.exit(75)\n", encoding="utf-8")
    proc = _run_bat(bat_root / "_sys" / "core" / "dispatch.bat", ["update"], bat_root)
    assert proc.returncode != 0 and "handoff" in proc.stdout.lower()


def test_dispatch_bat_never_loops_when_already_in_the_runner(bat_root):
    (bat_root / "_sys" / "core" / "dispatcher.py").write_text("import sys\nsys.exit(75)\n", encoding="utf-8")
    proc = _run_bat(bat_root / "_sys" / "core" / "dispatch.bat", ["update"], bat_root, {"ENGRAM_IN_RUNNER": "1"})
    assert proc.returncode == 75
