"""doctor: read-only environment-resilience checks (design section 5).

New checks: env_manifest, root_moved, registry_stale, env_lock. All are read-only and
never turn the overall status into 'failed' (warnings/info only); python_pin stays the
hard gate. doctor must never create the manifest, take the lock, or touch the registry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

SYS_DIR = find_root(__file__)
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

from core import doctor, env_manifest, env_lock  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic_localappdata(tmp_path, monkeypatch):
    local = tmp_path / "localappdata"
    local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    return local


@pytest.fixture
def layout(tmp_path):
    base = tmp_path / "Engram"
    sys_dir = base / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    return base, sys_dir


def _manifest(root):
    return {"schema_version": 1, "install_id": "i" * 36,
            "root": {"logical": str(root), "physical": str(root)}}


# ---- env_manifest ---------------------------------------------------------------

def test_env_manifest_absent_is_adoptable_info(layout):
    base, sys_dir = layout
    r = doctor.check_env_manifest(sys_dir)
    assert r["name"] == "env_manifest" and r["ok"] is True and r["level"] == "info"
    assert "adoptable" in r["detail"]


def test_env_manifest_ok(layout):
    base, sys_dir = layout
    env_manifest.write_manifest(sys_dir, _manifest(base))
    r = doctor.check_env_manifest(sys_dir)
    assert r["ok"] is True and r["level"] == "ok"


def test_env_manifest_corrupt_is_warning_not_failure(layout):
    base, sys_dir = layout
    env_manifest.manifest_path(sys_dir).write_text("{bad", encoding="utf-8")
    r = doctor.check_env_manifest(sys_dir)
    assert r["ok"] is True and r["level"] == "warning"


def test_env_manifest_unsupported_schema_is_warning(layout):
    base, sys_dir = layout
    env_manifest.manifest_path(sys_dir).write_text(
        json.dumps({"schema_version": 99, "install_id": "x", "root": {}}), encoding="utf-8")
    assert doctor.check_env_manifest(sys_dir)["level"] == "warning"


# ---- root_moved ------------------------------------------------------------------

def test_root_moved_ok_when_consistent(layout):
    base, sys_dir = layout
    env_manifest.write_manifest(sys_dir, _manifest(base))
    r = doctor.check_root_moved(base, sys_dir)
    assert r["ok"] is True and r["level"] == "ok"


def test_root_moved_warns_with_previous_root_and_canonical_verb(layout, tmp_path):
    base, sys_dir = layout
    gone = tmp_path / "OldEngram"
    env_manifest.write_manifest(sys_dir, _manifest(gone))
    r = doctor.check_root_moved(base, sys_dir)
    assert r["ok"] is True and r["level"] == "warning"
    assert str(gone) in r["detail"]
    assert ".bat" not in r["detail"].lower()


def test_root_moved_copy_is_distinguished(layout, tmp_path):
    base, sys_dir = layout
    old = tmp_path / "StillThere"
    old.mkdir()
    env_manifest.write_manifest(sys_dir, _manifest(old))
    r = doctor.check_root_moved(base, sys_dir)
    assert r["level"] == "warning" and "copy" in r["detail"].lower()


def test_root_moved_unknown_is_info(layout):
    base, sys_dir = layout
    r = doctor.check_root_moved(base, sys_dir)
    assert r["ok"] is True and r["level"] == "info"


# ---- env_lock ---------------------------------------------------------------------------

def test_env_lock_free_is_ok(layout):
    base, sys_dir = layout
    r = doctor.check_env_lock(sys_dir)
    assert r["ok"] is True and r["level"] == "ok"


def test_env_lock_stale_is_warning_and_not_broken_by_doctor(layout):
    base, sys_dir = layout
    env_lock.lock_path(sys_dir).write_text(
        json.dumps({"pid": 2**31 - 11, "start_time": 1.0, "op_id": "dead"}), encoding="utf-8")
    r = doctor.check_env_lock(sys_dir)
    assert r["ok"] is True and r["level"] == "warning"
    assert env_lock.lock_path(sys_dir).exists()  # doctor never mutates


def test_env_lock_held_is_info(layout):
    base, sys_dir = layout
    with env_lock.guard(sys_dir, "op-held"):
        r = doctor.check_env_lock(sys_dir)
    assert r["ok"] is True and r["level"] == "info" and "op-held" in r["detail"]


# ---- registry_stale -----------------------------------------------------------------------

def test_registry_stale_reports_without_removing(layout, monkeypatch):
    base, sys_dir = layout
    monkeypatch.setattr(doctor.registrar, "find_stale_entries", lambda sd, relay_root=None: ["SandboxRun_D_ghost"])
    r = doctor.check_registry_stale(sys_dir)
    assert r["ok"] is True and r["level"] == "warning" and "SandboxRun_D_ghost" in r["detail"]
    assert "engram menu clean" in r["detail"].lower()


def test_registry_stale_none_is_ok(layout, monkeypatch):
    base, sys_dir = layout
    monkeypatch.setattr(doctor.registrar, "find_stale_entries", lambda sd, relay_root=None: [])
    assert doctor.check_registry_stale(sys_dir)["level"] == "ok"


def test_registry_stale_errors_degrade_to_info(layout, monkeypatch):
    base, sys_dir = layout
    def boom(sd, relay_root=None):
        raise OSError("registry unavailable")
    monkeypatch.setattr(doctor.registrar, "find_stale_entries", boom)
    r = doctor.check_registry_stale(sys_dir)
    assert r["ok"] is True and r["level"] == "info"


# ---- run() integration ------------------------------------------------------------------------

def _patch_other_checks(monkeypatch):
    monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: "3.14.5")
    monkeypatch.setattr(doctor, "check_legacy_host_integration",
                        lambda b, s: {"name": "legacy_host_integration", "ok": True, "level": "ok", "detail": "x"})
    monkeypatch.setattr(doctor, "check_registration",
                        lambda b, s: {"name": "context_menu", "ok": True, "level": "ok", "detail": "x"})
    monkeypatch.setattr(doctor.registrar, "find_stale_entries", lambda sd, relay_root=None: [])


def test_run_includes_new_checks_and_stays_healthy(layout, monkeypatch, capsys):
    base, sys_dir = layout
    (sys_dir / "runtimes.json").write_text(json.dumps(
        {"runtimes": {"python": {"version": "3.14.5"}}, "tools": {}}), encoding="utf-8")
    _patch_other_checks(monkeypatch)
    res = doctor.run({"base_dir": base, "sys_dir": sys_dir, "args": ["--json"]})
    names = [c["name"] for c in res["checks"]]
    for expected in ("env_manifest", "root_moved", "registry_stale", "env_lock"):
        assert expected in names
    assert res["status"] == "success"  # warnings/info never fail doctor


def test_run_is_read_only(layout, monkeypatch):
    base, sys_dir = layout
    (sys_dir / "runtimes.json").write_text(json.dumps(
        {"runtimes": {"python": {"version": "3.14.5"}}, "tools": {}}), encoding="utf-8")
    _patch_other_checks(monkeypatch)
    before = sorted(str(p.relative_to(base)) for p in base.rglob("*"))
    doctor.run({"base_dir": base, "sys_dir": sys_dir, "args": ["--json"]})
    after = sorted(str(p.relative_to(base)) for p in base.rglob("*"))
    assert before == after
    assert not env_manifest.manifest_path(sys_dir).exists()
    assert not env_lock.lock_path(sys_dir).exists()


# ---- venv checks wired into doctor ---------------------------------------------------------------

def test_check_venv_returns_doctor_format_findings(layout):
    base, sys_dir = layout
    findings = doctor.check_venv(sys_dir)  # no venv at all -> info only
    assert findings and all({"name", "ok", "level", "detail"} <= set(f) for f in findings)
    assert all(f["ok"] for f in findings)


def test_check_venv_never_raises(layout, monkeypatch):
    base, sys_dir = layout
    def boom(*a, **k):
        raise RuntimeError("probe bug")
    monkeypatch.setattr(doctor.venv_manager, "run_checks", boom)
    res = doctor.check_venv(sys_dir)
    assert len(res) == 1 and res[0]["ok"] is True


def test_run_includes_venv_findings_and_venv_errors_fail_doctor(layout, monkeypatch):
    base, sys_dir = layout
    (sys_dir / "runtimes.json").write_text(json.dumps(
        {"runtimes": {"python": {"version": "3.14.5"}}, "tools": {}}), encoding="utf-8")
    _patch_other_checks(monkeypatch)
    monkeypatch.setattr(doctor.venv_manager, "run_checks", lambda sd, manifest=None: [
        {"name": "venv_interpreter", "ok": False, "level": "error", "detail": "venv interpreter does not run"}])
    res = doctor.run({"base_dir": base, "sys_dir": sys_dir, "args": ["--json"]})
    assert "venv_interpreter" in [c["name"] for c in res["checks"]]
    assert res["status"] == "failed"
