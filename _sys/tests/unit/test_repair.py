import json
import pytest
import os
from pathlib import Path
from core import env_ops, env_manifest, venv_manager, python_manager, relocation
import core.repair as repair

def test_detect_healthy(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    base_dir = tmp_path
    (sys_dir / "data" / "state").mkdir(parents=True)
    manifest = {"schema_version": 1, "install_id": "1", "root": {"logical": str(base_dir), "physical": str(base_dir)}}
    env_manifest.write_manifest(sys_dir, manifest)
    
    det = repair.detect(sys_dir, base_dir)
    assert det["manifest"] == "ok"
    assert det["drift"]["status"] == "consistent"
    assert not det["journal"]

def test_build_plan_healthy(tmp_path):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "stale_registry": []}
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det)
    assert not plan["steps"]
    assert plan["summary"] == ["nothing to repair"]

def test_build_plan_no_manifest(tmp_path):
    det = {"manifest": "absent", "drift": {"status": "consistent"}, "findings": [], "stale_registry": []}
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det)
    assert len(plan["steps"]) == 1
    assert plan["steps"][0].name == "adopt-manifest"
    assert plan["steps"][0].group == "B"
    assert plan["spec"][0]["kind"] == "manifest"

def test_build_plan_drift_moved(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "moved", "previous_root": "C:\\old"}, "findings": [], "stale_registry": []}
    def mock_relocation(*a, **kw):
        return [env_ops.Step("export-registry-keys", lambda c: None),
                env_ops.Step("write-manifest", lambda c: None, group="B")]
    monkeypatch.setattr(relocation, "plan_relocation", mock_relocation)
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det)
    names = [s.name for s in plan["steps"]]
    assert "export-registry-keys" in names
    assert "write-manifest" in names

def test_build_plan_drift_copied(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "copied", "previous_root": "C:\\old"}, "findings": [], "stale_registry": []}
    def mock_relocation(*a, **kw):
        return [env_ops.Step("write-manifest", lambda c: None, group="B")]
    monkeypatch.setattr(relocation, "plan_relocation", mock_relocation)
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det)
    names = [s.name for s in plan["steps"]]
    assert "export-registry-keys" not in names
    assert "remove-stale-registry-entries" not in names
    assert "write-manifest" in names

def test_build_plan_stale_launchers(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [{"name": "stale-launchers", "level": "warning"}], "stale_registry": []}
    def mock_venv(*a, **kw): return [env_ops.Step("regenerate-console-scripts", lambda c: None)]
    monkeypatch.setattr(repair.venv_repair, "plan_venv_repair", mock_venv)
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det)
    names = [s.name for s in plan["steps"]]
    assert "regenerate-console-scripts" in names

def test_build_plan_venv_spawn_error(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [{"name": "venv_spawn", "level": "error"}], "stale_registry": []}
    def mock_venv(*a, **kw): 
        return [
            env_ops.Step("quarantine-venv", lambda c: None),
            env_ops.Step("create-venv", lambda c: None),
            env_ops.Step("restore-packages", lambda c: None),
            env_ops.Step("regenerate-console-scripts", lambda c: None)
        ]
    monkeypatch.setattr(repair.venv_repair, "plan_venv_repair", mock_venv)
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det)
    names = [s.name for s in plan["steps"]]
    assert "quarantine-venv" in names
    assert "create-venv" in names
    assert "restore-packages" in names
    assert "regenerate-console-scripts" in names

def test_build_plan_pyvenv_home_error(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [{"name": "pyvenv_home", "level": "warning"}], "stale_registry": []}
    def mock_venv(*a, **kw): return [env_ops.Step("rewrite-pyvenv-cfg", lambda c: None)]
    monkeypatch.setattr(repair.venv_repair, "plan_venv_repair", mock_venv)
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det)
    names = [s.name for s in plan["steps"]]
    assert "rewrite-pyvenv-cfg" in names
    
def test_build_plan_stale_registry_alone(tmp_path):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "stale_registry": ["old_key"]}
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det)
    names = [s.name for s in plan["steps"]]
    assert not any("venv" in s.name or "console-scripts" in s.name for s in plan["steps"])

def test_build_plan_only_validation(tmp_path):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": []}
    with pytest.raises(ValueError, match="Unknown only values"):
        repair.build_plan(tmp_path / "_sys", tmp_path, det, only={"invalid"})

def test_build_plan_only_filtering(tmp_path):
    det = {"manifest": "absent", "drift": {"status": "consistent"}, "findings": [{"name": "venv_spawn", "level": "error"}],
           "stale_registry": []}
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det, only={"manifest"})
    assert [s.name for s in plan["steps"]] == ["adopt-manifest"]


def test_adoption_is_refused_while_the_root_has_moved(tmp_path):
    # adopting "current = truth" after a move would erase the only evidence of the move
    det = {"manifest": "absent", "drift": {"status": "moved", "previous_root": "C:\old"}, "findings": [], "stale_registry": []}
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det, only={"manifest"})
    assert plan["steps"] == []

def test_repair_main_dry_run(tmp_path, monkeypatch):
    det = {"manifest": "absent", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": []}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 0
    assert res["detail"] == "dry run"

def test_repair_main_no_tty_no_yes(tmp_path, monkeypatch):
    det = {"manifest": "absent", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--apply"]}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 11
    assert res["detail"] == "non-interactive without --yes"

def test_repair_main_yes_executes(tmp_path, monkeypatch):
    det = {"manifest": "absent", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    executed = []
    def fake_exec(*a, **kw):
        executed.append(True)
        return {"status": "success", "exit_code": 0}
    monkeypatch.setattr(env_ops, "execute", fake_exec)
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--apply", "--yes"]}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 0
    assert executed

def test_repair_main_tty_prompt_yes(tmp_path, monkeypatch):
    det = {"manifest": "absent", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(env_ops, "execute", lambda *a, **kw: {"status": "success", "exit_code": 0})
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--apply"], "seams": {"input_fn": lambda p: "y"}}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 0

def test_repair_main_tty_prompt_no(tmp_path, monkeypatch):
    det = {"manifest": "absent", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--apply"], "seams": {"input_fn": lambda p: "n"}}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 10

def test_repair_main_journal_blocks(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": {"op_id": "123"}}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": []}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 14
    assert "123" in res["detail"]

def test_repair_main_resume(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": {"op_id": "123", "data": {"spec": []}}}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    monkeypatch.setattr(env_ops, "resume", lambda *a, **kw: {"status": "success", "exit_code": 0})
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--resume"]}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 0

def test_repair_main_rollback(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": {"op_id": "123", "data": {"spec": []}}}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    monkeypatch.setattr(env_ops, "rollback", lambda *a, **kw: {"status": "success", "exit_code": 0})
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--rollback"]}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 0

def test_relocate_main_from(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--from", "C:\\old"]}
    def fake_build_plan(s, b, d, **kw):
        assert d["drift"]["status"] == "moved"
        assert d["drift"]["previous_root"] == "C:\\old"
        assert d["drift"]["source"] == "--from"
        return {"steps": [], "spec": [], "summary": ["test"], "kind": "repair"}
    monkeypatch.setattr(repair, "build_plan", fake_build_plan)
    res = repair.relocate_main(ctx)
    assert res["exit_code"] == 0

def test_update_env_main_python_path(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    monkeypatch.setattr(python_manager, "plan_python_update", lambda *a, **kw: [])
    monkeypatch.setattr(python_manager, "classify_change", lambda *a, **kw: "same")
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--to", "3.15.0"]}
    res = repair.update_env_main(ctx, {"python"})
    assert res["exit_code"] == 0

def test_update_env_main_python_blocked(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    monkeypatch.setattr(python_manager, "classify_change", lambda *a, **kw: "major")
    monkeypatch.setattr(python_manager, "plan_python_update", lambda *a, **kw: [])
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--to", "4.0.0"]}
    res = repair.update_env_main(ctx, {"python"})
    assert res["exit_code"] == 11
    assert "Blocked major update" in res["detail"]

def test_update_env_main_python_allowed(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    monkeypatch.setattr(python_manager, "classify_change", lambda *a, **kw: "major")
    monkeypatch.setattr(python_manager, "plan_python_update", lambda *a, **kw: [])
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--to", "4.0.0", "--allow-major-runtime-upgrade"]}
    res = repair.update_env_main(ctx, {"python"})
    assert res["exit_code"] == 0

def test_update_env_main_packages(tmp_path, monkeypatch):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--all-packages"]}
    res = repair.update_env_main(ctx, {"packages"})
    assert res["exit_code"] == 0

def test_repair_json_output(tmp_path, monkeypatch, capsys):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": None}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--json"]}
    repair.repair_main(ctx)
    out = capsys.readouterr().out
    assert json.loads(out)["status"] == "success"

def test_repair_help_flag(tmp_path):
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--help"]}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 0
    assert res["detail"] == "usage"

def test_repair_unknown_flag(tmp_path):
    ctx = {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "args": ["--badflag"]}
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 2

def test_steps_from_spec_roundtrip(tmp_path):
    spec = [{"name": "adopt-manifest", "group": "B", "kind": "manifest", "params": {}}]
    steps = repair.steps_from_spec(tmp_path / "_sys", tmp_path, spec)
    assert len(steps) == 1
    assert steps[0].name == spec[0]["name"]
    assert steps[0].group == spec[0]["group"]

def test_detect_read_only_tree(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    det1 = repair.detect(sys_dir, tmp_path)
    import hashlib
    def get_hash():
        return hashlib.md5("".join(str(p) for p in sys_dir.rglob("*")).encode()).hexdigest()
    h1 = get_hash()
    repair.detect(sys_dir, tmp_path)
    assert get_hash() == h1

def test_e2e_repair_venv_apply(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    (sys_dir / "data" / "state").mkdir(parents=True)
    manifest = {"schema_version": 1, "install_id": "1", "root": {"logical": str(tmp_path), "physical": str(tmp_path)}}
    env_manifest.write_manifest(sys_dir, manifest)
    
    ctx = {"sys_dir": sys_dir, "base_dir": tmp_path, "args": ["--apply", "--yes"]}
    
    def fake_detect(*a, **kw):
        return {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [{"name": "venv_spawn", "level": "error"}], "stale_registry": [], "journal": None}
    
    def mock_venv(*a, **kw):
        return [env_ops.Step("create-venv", lambda c: None)]
    
    monkeypatch.setattr(repair, "detect", fake_detect)
    monkeypatch.setattr(repair.venv_repair, "plan_venv_repair", mock_venv)
    
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 0

def test_e2e_repair_rollback(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    (sys_dir / "data" / "state").mkdir(parents=True)
    
    # We will simulate a crash in env_ops by creating a fake plan and executing it with crash_after
    step = env_ops.Step("fail", lambda c: Path(c.sys_dir / "test.txt").write_text("x"), lambda c: Path(c.sys_dir / "test.txt").unlink())
    try:
        env_ops.execute(sys_dir, "repair", [step], crash_after="fail")
    except env_ops.SimulatedCrash:
        pass
    
    assert (sys_dir / "test.txt").exists()
    
    ctx = {"sys_dir": sys_dir, "base_dir": tmp_path, "args": ["--rollback"]}
    
    def mock_steps_from_spec(*a, **kw):
        return [step]
    
    monkeypatch.setattr(repair, "steps_from_spec", mock_steps_from_spec)
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 0
    assert not (sys_dir / "test.txt").exists()

def test_e2e_repair_resume(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    (sys_dir / "data" / "state").mkdir(parents=True)
    
    # Simulate a crash
    def setup_fake_done(c): Path(c.sys_dir / "test.txt").write_text("x")
    step = env_ops.Step("fail", setup_fake_done, done=lambda c: Path(c.sys_dir / "test.txt").exists())
    try:
        env_ops.execute(sys_dir, "repair", [step], crash_after="fail")
    except env_ops.SimulatedCrash:
        pass
    
    assert (sys_dir / "test.txt").exists()
    
    ctx = {"sys_dir": sys_dir, "base_dir": tmp_path, "args": ["--resume"]}
    def mock_steps_from_spec(*a, **kw): return [step]
    monkeypatch.setattr(repair, "steps_from_spec", mock_steps_from_spec)
    
    res = repair.repair_main(ctx)
    assert res["exit_code"] == 0


def test_build_plan_ignores_ok_and_info_findings(tmp_path):
    det = {"manifest": "ok", "drift": {"status": "consistent"}, "stale_registry": [],
           "findings": [{"name": "venv_spawn", "level": "ok", "ok": True},
                        {"name": "x", "level": "info", "ok": True}]}
    plan = repair.build_plan(tmp_path / "_sys", tmp_path, det)
    assert not plan["steps"]
    assert plan["summary"] == ["nothing to repair"]
