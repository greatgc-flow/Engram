"""Offline interrupted-pip contracts; all artifacts use shared scratch."""
import json
import os
import pytest
from conftest import scratch_dir
from core import env_ops, python_manager, repair, venv_manager, backups, doctor


@pytest.fixture
def install():
    with scratch_dir() as root:
        yield root / "_sys"


def distribution(site, dirname, metadata="Name: peerhub\n", payload=True):
    info = site / dirname
    info.mkdir(parents=True)
    (info / "METADATA").write_text(metadata, encoding="utf-8")
    (info / "top_level.txt").write_text("peerhub\n", encoding="utf-8")
    (info / "RECORD").write_text("peerhub/__init__.py,,\n", encoding="utf-8")
    if payload:
        (site / "peerhub").mkdir(exist_ok=True)
        (site / "peerhub/__init__.py").write_text("", encoding="utf-8")
    return info


@pytest.mark.parametrize("case,name,removable", [
    ("duplicate", "peerhub", True), ("only-copy", "peerhub", False),
    ("unknown", None, False), ("malformed", None, False),
    ("missing-payload", "peerhub", False),
])
def test_classification(install, case, name, removable):
    site = install / "env/venv/Lib/site-packages"
    if case == "unknown":
        (site / "~").mkdir(parents=True)
    else:
        distribution(site, "~eerhub.dist-info",
                     "not metadata" if case == "malformed" else "Name: peerhub\n",
                     payload=False)
    if case in ("duplicate", "missing-payload"):
        distribution(site, "peerhub-1.dist-info", payload=case == "duplicate")
    rows = venv_manager.pip_leftovers(site)
    assert len(rows) == 1
    assert rows[0]["real_name"] == name
    assert rows[0]["removable"] is removable
    if not removable:
        assert rows[0]["remedy"] == (
            f"pip install --force-reinstall {name}" if name else
            "unrecognized, inspect manually")


def test_missing_and_link_ignored(install):
    site = install / "env/venv/Lib/site-packages"
    assert venv_manager.pip_leftovers(site) == []
    outside = install / "outside"
    outside.mkdir(parents=True)
    site.mkdir(parents=True)
    try:
        os.symlink(outside, site / "~escape", target_is_directory=True)
    except OSError:
        import subprocess
        subprocess.run(["cmd", "/c", "mklink", "/J", str(site / "~escape"),
                        str(outside)], check=True, capture_output=True)
    assert venv_manager.pip_leftovers(site) == []


def test_preview_apply_idempotent_and_rollback(install, monkeypatch):
    site = install / "env/venv/Lib/site-packages"
    leftover = distribution(site, "~eerhub.dist-info", payload=False)
    distribution(site, "peerhub-1.dist-info")
    (site / "~").mkdir()
    findings = [{"name": "pip_leftovers", "level": "warning"}]
    det = {"manifest": "ok", "drift": {}, "findings": findings}
    before = sorted(str(p) for p in install.rglob("*"))
    plan = repair.build_plan(install, install.parent, det, only={"venv"})
    assert before == sorted(str(p) for p in install.rglob("*"))
    monkeypatch.setattr(python_manager, "default_holders", lambda paths: [])
    result = env_ops.execute(install, "repair", plan["steps"],
                             initial_data={"spec": plan["spec"]})
    assert result["status"] == "success"
    assert not leftover.exists() and (site / "~").exists()
    assert (site / "peerhub-1.dist-info/METADATA").exists()
    assert any(r.meta["source_path"] == str(leftover) for r in backups.scan(install).valid)
    assert not repair.build_plan(install, install.parent, det, only={"venv"})["steps"]


def test_warning_does_not_fail_doctor(install):
    site = install / "env/venv/Lib/site-packages"
    (site / "~").mkdir(parents=True)
    checks = venv_manager.run_checks(install, runner=lambda *a: (1, "offline"))
    warning = next(c for c in checks if c["name"] == "pip_leftovers")
    assert warning["ok"] is True and warning["level"] == "warning"
    assert "engram repair --only venv" in warning["detail"]
    assert "unrecognized, inspect manually" in json.dumps(warning)


def test_busy_and_crash_rollback(install, monkeypatch):
    site = install / "env/venv/Lib/site-packages"
    leftover = distribution(site, "~eerhub.dist-info", payload=False)
    distribution(site, "peerhub-1.dist-info")
    det = {"manifest": "ok", "drift": {}, "findings": [
        {"name": "pip_leftovers", "level": "warning"}]}
    plan = repair.build_plan(install, install.parent, det, only={"venv"})
    monkeypatch.setattr(python_manager, "default_holders", lambda paths: [{"pid": 123}])
    result = env_ops.execute(install, "repair", plan["steps"])
    assert result["status"] == "failed" and leftover.exists()
    assert not backups.scan(install).valid
    monkeypatch.setattr(python_manager, "default_holders", lambda paths: [])
    with pytest.raises(env_ops.SimulatedCrash):
        env_ops.execute(install, "repair", plan["steps"],
                        initial_data={"spec": plan["spec"]},
                        crash_after="quarantine-pip-leftovers")
    assert not leftover.exists()
    result = env_ops.rollback(install, lambda active: repair.steps_from_spec(
        install, install.parent, plan["spec"]))
    assert result["phase"] == "ROLLED_BACK" and leftover.exists()


def test_cli_dry_run_writes_nothing(install, monkeypatch):
    site = install / "env/venv/Lib/site-packages"
    distribution(site, "~eerhub.dist-info", payload=False)
    distribution(site, "peerhub-1.dist-info")
    det = {"manifest": "ok", "drift": {}, "journal": None, "findings": [
        {"name": "pip_leftovers", "level": "warning"}]}
    monkeypatch.setattr(repair, "detect", lambda *a, **kw: det)
    monkeypatch.setattr(repair.layout_migration, "supported_layout", lambda *a, **kw: True)
    before = {str(p): p.read_bytes() for p in install.rglob("*") if p.is_file()}
    result = repair.repair_main({"sys_dir": install, "base_dir": install.parent,
                                "args": ["--only", "venv", "--dry-run", "--apply"]})
    assert result["detail"] == "dry run" and result["exit_code"] == 0
    assert before == {str(p): p.read_bytes() for p in install.rglob("*") if p.is_file()}
    assert not (install / "data").exists()


def test_doctor_overall_unchanged(install, monkeypatch, capsys):
    names = ("check_python", "check_root_path", "check_legacy_host_integration", "check_registration",
             "check_components", "check_env_manifest", "check_root_moved",
             "check_registry_stale", "check_env_lock", "check_env_journal", "check_elevation")
    for name in names:
        if hasattr(doctor, name):
            monkeypatch.setattr(doctor, name, lambda *a, **kw: {"name": "ok", "ok": True})
    monkeypatch.setattr(doctor, "evaluate_limitations", lambda *a, **kw: [])
    monkeypatch.setattr(doctor, "check_venv", lambda *a: [
        {"name": "pip_leftovers", "ok": True, "level": "warning", "detail": "kept"}])
    result = doctor.run({"sys_dir": install, "base_dir": install.parent,
                                 "args": ["--json"], "env": {}})
    assert result["status"] == "success"
    assert result.get("exit_code", 0) == 0
    assert json.loads(capsys.readouterr().out)["checks"]


def test_apply_revalidates_health(install, monkeypatch):
    site = install / "env/venv/Lib/site-packages"
    leftover = distribution(site, "~eerhub.dist-info", payload=False)
    distribution(site, "peerhub-1.dist-info")
    det = {"manifest": "ok", "drift": {}, "findings": [
        {"name": "pip_leftovers", "level": "warning"}]}
    plan = repair.build_plan(install, install.parent, det, only={"venv"})
    (site / "peerhub/__init__.py").unlink()
    (site / "peerhub").rmdir()
    monkeypatch.setattr(python_manager, "default_holders", lambda paths: [])
    result = env_ops.execute(install, "repair", plan["steps"])
    assert result["status"] == "success" and leftover.exists()
    assert not backups.scan(install).valid
