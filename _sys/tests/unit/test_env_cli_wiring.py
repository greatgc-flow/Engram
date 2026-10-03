"""Wiring of repair/relocate/update-env into dispatcher, doctor and updater (design sections 9, 10)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from _sys.core.root import find_root

SYS_DIR = find_root(__file__)
sys.path.insert(0, str(SYS_DIR))

from core import dispatcher, doctor, env_ops, updater  # noqa: E402


def _dispatch():
    return json.loads((SYS_DIR / "dispatch.json").read_text(encoding="utf-8"))


# ---- dispatch.json -----------------------------------------------------------------------------------

def test_repair_and_relocate_pipelines_are_declared():
    d = _dispatch()
    assert d["pipelines"]["repair"] == ["repair.run"]
    assert d["pipelines"]["relocate"] == ["relocate.run"]
    assert d["operations"]["repair.run"] == {**d["operations"]["repair.run"], "module": "core.repair", "method": "repair_main"}
    assert d["operations"]["relocate.run"]["method"] == "relocate_main"
    import importlib
    for op in ("repair.run", "relocate.run"):
        spec = d["operations"][op]
        assert callable(getattr(importlib.import_module(spec["module"]), spec["method"]))
        assert spec["failure_policy"] == "abort"


# ---- dispatcher exit codes -----------------------------------------------------------------------------------

def _fake_pipeline(monkeypatch, tmp_path, result):
    fake_sys = tmp_path / "_sys"
    state_dir = fake_sys / "data" / "state"
    fake_sys.mkdir()
    (fake_sys / "dispatch.json").write_text(json.dumps({
        "operations": {"x.run": {"module": "fake.m", "method": "run", "failure_policy": "abort"}},
        "pipelines": {"x": ["x.run"]},
    }), encoding="utf-8")
    ctx = {"base_dir": tmp_path, "sys_dir": fake_sys, "paths": {"state": state_dir}, "args": [], "command": "x", "state": {}}
    monkeypatch.setattr(dispatcher, "sys_dir", fake_sys)
    monkeypatch.setattr(dispatcher, "_build_ctx", lambda *_a: ctx)
    monkeypatch.setattr(dispatcher.importlib, "import_module", lambda _n: SimpleNamespace(run=lambda _c: result))


@pytest.mark.parametrize("code", [11, 12, 13, 14])
def test_a_failed_operation_with_a_cli_exit_code_exits_with_that_code(monkeypatch, tmp_path, capsys, code):
    _fake_pipeline(monkeypatch, tmp_path, {"status": "failed", "detail": "boom", "exit_code": code})
    assert dispatcher.main(["dispatcher.py", "x"]) == code
    assert "boom" in capsys.readouterr().out


def test_other_failures_keep_the_old_behaviour(monkeypatch, tmp_path):
    _fake_pipeline(monkeypatch, tmp_path, {"status": "failed", "detail": "plain"})
    with pytest.raises(RuntimeError, match="failed"):
        dispatcher.main(["dispatcher.py", "x"])


def test_a_usage_error_exits_with_its_code_and_no_traceback(monkeypatch, tmp_path):
    _fake_pipeline(monkeypatch, tmp_path, {"status": "failed", "detail": "usage", "exit_code": 2})
    assert dispatcher.main(["dispatcher.py", "x"]) == 2


def test_a_small_exit_code_that_is_not_a_usage_error_is_not_promoted(monkeypatch, tmp_path):
    _fake_pipeline(monkeypatch, tmp_path, {"status": "failed", "detail": "boom", "exit_code": 2})
    with pytest.raises(RuntimeError):
        dispatcher.main(["dispatcher.py", "x"])


def test_success_returns_zero(monkeypatch, tmp_path):
    _fake_pipeline(monkeypatch, tmp_path, {"status": "success"})
    assert dispatcher.main(["dispatcher.py", "x"]) == 0


def test_missing_command_is_usage_exit_1(capsys):
    assert dispatcher.main(["dispatcher.py"]) == 1


# ---- doctor: journal check -------------------------------------------------------------------------------------

@pytest.fixture
def layout(tmp_path):
    base = tmp_path / "Engram"
    sys_dir = base / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    return base, sys_dir


def test_doctor_journal_check_ok_without_a_journal(layout):
    base, sys_dir = layout
    r = doctor.check_env_journal(sys_dir)
    assert r["name"] == "env_journal" and r["ok"] is True and r["level"] == "ok"


def test_doctor_journal_check_flags_an_active_journal_with_the_recovery_commands(layout):
    base, sys_dir = layout
    j = sys_dir / "data" / "state" / env_ops.JOURNAL_FILENAME
    rec = lambda seq, ev, **kw: json.dumps({"seq": seq, "ts": "t", "event": ev, **kw, "crc": "0"})
    j.write_text("\n".join([rec(1, "PHASE", name="PLANNED"), rec(2, "PHASE", name="STEPS_RUNNING")]) + "\n", encoding="utf-8")
    # use the real writer so the CRC is valid
    import shutil
    shutil.rmtree(sys_dir / "data" / "state")
    (sys_dir / "data" / "state").mkdir(parents=True)
    from core.env_ops import Step
    def boom(ctx):
        raise env_ops.SimulatedCrash()
    with pytest.raises(env_ops.SimulatedCrash):
        env_ops.execute(sys_dir, "repair", [Step("s", boom)], op_id="op-crashed")
    r = doctor.check_env_journal(sys_dir)
    assert r["ok"] is False and r["level"] == "error"
    assert "op-crashed" in r["detail"] and "engram repair --resume" in r["detail"] and "engram repair --rollback" in r["detail"]


def test_doctor_run_includes_the_journal_check(layout, monkeypatch):
    base, sys_dir = layout
    (sys_dir / "runtimes.json").write_text(json.dumps({"runtimes": {"python": {"version": "3.14.5"}}, "tools": {}}), encoding="utf-8")
    monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: "3.14.5")
    monkeypatch.setattr(doctor, "check_legacy_host_integration", lambda b, s: {"name": "legacy_host_integration", "ok": True, "level": "ok", "detail": "x"})
    monkeypatch.setattr(doctor, "check_registration", lambda b, s: {"name": "context_menu", "ok": True, "level": "ok", "detail": "x"})
    monkeypatch.setattr(doctor.registrar, "find_stale_entries", lambda sd, relay_root=None: [])
    res = doctor.run({"base_dir": base, "sys_dir": sys_dir, "args": ["--json"]})
    assert "env_journal" in [c["name"] for c in res["checks"]]


# ---- updater routing -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("args,expected_only,expected_args", [
    (["--only", "python"], {"python"}, []),
    (["--only", "python,venv"], {"python", "venv"}, []),
    (["--only", "venv", "packages", "--yes"], {"venv", "packages"}, ["--apply", "--yes"]),
    (["--only", "packages", "--dry-run"], {"packages"}, []),
    (["--only", "python", "--allow-major-runtime-upgrade", "--yes"], {"python"}, ["--allow-major-runtime-upgrade", "--apply", "--yes"]),
])
def test_update_only_env_components_routes_to_the_repair_engine(monkeypatch, args, expected_only, expected_args):
    seen = {}

    def fake_update_env_main(ctx, only):
        seen["only"], seen["args"] = set(only), ctx["args"]
        return {"status": "success", "operation": "update", "exit_code": 0}

    monkeypatch.setattr("core.repair.update_env_main", fake_update_env_main)
    res = updater.run({"args": args, "sys_dir": SYS_DIR, "base_dir": SYS_DIR.parent})
    assert res["status"] == "success"
    assert seen["only"] == expected_only
    assert seen["args"] == expected_args


def test_mixing_env_components_with_tools_is_rejected(monkeypatch):
    monkeypatch.setattr("core.repair.update_env_main", lambda ctx, only: pytest.fail("must not run"))
    res = updater.run({"args": ["--only", "python", "claude"], "sys_dir": SYS_DIR, "base_dir": SYS_DIR.parent})
    assert res["status"] == "failed" and "cannot be combined" in res["detail"]


def test_tool_only_updates_do_not_touch_the_repair_engine(monkeypatch):
    monkeypatch.setattr("core.repair.update_env_main", lambda ctx, only: pytest.fail("must not run"))
    # an unknown tool still fails the old way (before any network access)
    res = updater.run({"args": ["--only", "definitely-not-a-tool"], "sys_dir": SYS_DIR, "base_dir": SYS_DIR.parent})
    assert res["status"] == "failed" and res.get("exit_code") == 2


@pytest.mark.parametrize("flags", [["--dry-run"], ["--yes", "--dry-run"], ["--dry-run", "--yes"]])
def test_update_dry_run_never_maps_to_apply(flags):
    out = updater._env_update_args(["--only", "python", *flags])
    assert "--apply" not in out and "--yes" not in out


def test_update_yes_still_maps_to_apply():
    assert updater._env_update_args(["--only", "python", "--yes"]) == ["--apply", "--yes"]


def test_plan_with_only_informational_summary_does_not_claim_nothing_to_repair(capsys):
    from core import repair
    repair._print_plan({"steps": [], "summary": ["Python already at 3.14.8"]})
    out = capsys.readouterr().out
    assert "Python already at 3.14.8" in out and "nothing to repair" not in out
    repair._print_plan({"steps": [], "summary": []})
    assert "nothing to repair" in capsys.readouterr().out
