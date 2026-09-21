from __future__ import annotations

import json
import sys
from pathlib import Path

from _sys.core.root import find_root

SYS_DIR = find_root(__file__)  # _sys/
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

from core import doctor  # noqa: E402


def _write_runtimes(sys_dir: Path, python_version: str = "3.14.5") -> None:
    sys_dir.mkdir(parents=True, exist_ok=True)
    (sys_dir / "runtimes.json").write_text(json.dumps({
        "runtimes": {"python": {"version": python_version}},
        "tools": {
            "ripgrep": {"bin": "rg.exe"},
            "claude": {"provider": "npm"},
        },
    }), encoding="utf-8")


def test_check_python_match_is_ok(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    _write_runtimes(sys_dir, "3.14.5")
    monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: "3.14.5")
    r = doctor.check_python(sys_dir)
    assert r["ok"] is True and r["level"] == "ok"


def test_check_python_mismatch_is_error(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    _write_runtimes(sys_dir, "3.14.5")
    monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: "3.13.0")
    r = doctor.check_python(sys_dir)
    assert r["ok"] is False and r["level"] == "error"


def test_check_python_missing_is_error(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    _write_runtimes(sys_dir, "3.14.5")
    monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: None)
    r = doctor.check_python(sys_dir)
    assert r["ok"] is False and r["level"] == "error"


def test_check_components_npm_tool_present_via_npm_global(tmp_path):
    sys_dir = tmp_path / "_sys"
    _write_runtimes(sys_dir)
    # claude installed as an npm-global .cmd, ripgrep as a native tool
    (sys_dir / "env" / "nodejs" / "npm-global").mkdir(parents=True)
    (sys_dir / "env" / "nodejs" / "npm-global" / "claude.cmd").write_text("x", encoding="utf-8")
    (sys_dir / "tools" / "ripgrep").mkdir(parents=True)
    (sys_dir / "tools" / "ripgrep" / "rg.exe").write_text("x", encoding="utf-8")
    (sys_dir / "env" / "python").mkdir(parents=True)
    (sys_dir / "env" / "python" / "python.exe").write_text("x", encoding="utf-8")

    r = doctor.check_components(sys_dir)
    # only python runtime path check may miss (postcondition), but claude/ripgrep found;
    # missing (if any) is a WARNING, never fails the check
    assert r["ok"] is True
    assert "tool/claude" not in r.get("missing", [])
    assert "tool/ripgrep" not in r.get("missing", [])


def test_check_components_missing_is_warning_not_failure(tmp_path):
    sys_dir = tmp_path / "_sys"
    _write_runtimes(sys_dir)  # nothing actually installed on disk
    r = doctor.check_components(sys_dir)
    assert r["ok"] is True                 # never a hard failure
    assert r["level"] in ("warning", "ok")


def test_check_legacy_host_integration_clean(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir(parents=True)
    r = doctor.check_legacy_host_integration(tmp_path, sys_dir)
    assert r["ok"] is True and r["level"] == "ok"
    assert "clean" in r["detail"]


def test_check_legacy_host_integration_with_subst_drive(tmp_path):
    sys_dir = tmp_path / "_sys"
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "register.state.json").write_text(json.dumps({"subst_drive": "P"}), encoding="utf-8")
    r = doctor.check_legacy_host_integration(tmp_path, sys_dir)
    assert r["ok"] is True and r["level"] == "warning"
    assert "subst P: /D" in r["detail"]


def test_check_legacy_host_integration_with_junctions(tmp_path):
    sys_dir = tmp_path / "_sys"
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "register.state.json").write_text(json.dumps({
        "junctions": [{"host": "C:\\Users\\user\\.claude"}]
    }), encoding="utf-8")
    r = doctor.check_legacy_host_integration(tmp_path, sys_dir)
    assert r["ok"] is True and r["level"] == "warning"
    assert 'rmdir "C:\\Users\\user\\.claude"' in r["detail"]


def test_check_legacy_host_integration_with_subst_letter_in_config(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir(parents=True)
    (sys_dir / "config.json").write_text(json.dumps({"SUBST_DRIVE_LETTER": "Z"}), encoding="utf-8")
    r = doctor.check_legacy_host_integration(tmp_path, sys_dir)
    assert r["ok"] is True and r["level"] == "warning"
    assert "subst Z: /D" in r["detail"]


def test_doctor_never_spawns_subst(tmp_path, monkeypatch):
    import subprocess
    def no_subst(args, *a, **kw):
        if isinstance(args, (list, tuple)) and args and "subst" in str(args[0]).lower():
            raise AssertionError("doctor must never spawn subst.exe!")
        return subprocess.run(args, *a, **kw)
    monkeypatch.setattr(subprocess, "run", no_subst)
    sys_dir = tmp_path / "_sys"
    _write_runtimes(sys_dir, "3.14.5")
    monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: "3.14.5")
    res = doctor.run({"base_dir": tmp_path, "sys_dir": sys_dir, "args": ["--json"]})
    assert res["status"] == "success"


def test_check_elevation_standard_user_is_ok(monkeypatch):
    # force the non-admin branch deterministically
    import ctypes
    monkeypatch.setattr(ctypes, "windll", type("W", (), {"shell32": type("S", (), {"IsUserAnAdmin": staticmethod(lambda: 0)})()})(), raising=False)
    r = doctor.check_elevation()
    assert r["ok"] is True
    assert "standard user" in r["detail"] or "Administrator" in r["detail"]


def test_run_overall_failed_only_when_python_broken(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    _write_runtimes(sys_dir, "3.14.5")
    monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: None)  # python broken
    monkeypatch.setattr(doctor, "check_legacy_host_integration", lambda b, s: {"name": "legacy_host_integration", "ok": True, "level": "ok", "detail": "x"})
    monkeypatch.setattr(doctor, "check_registration", lambda b, s: {"name": "context_menu", "ok": True, "level": "info", "detail": "x"})
    monkeypatch.setattr(doctor, "check_sessions", lambda b: {"name": "sessions", "ok": True, "level": "ok", "detail": "x"})
    res = doctor.run({"base_dir": tmp_path, "sys_dir": sys_dir, "args": ["--json"]})
    assert res["status"] == "failed"  # python missing is the hard gate


def test_run_healthy_when_python_ok(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    _write_runtimes(sys_dir, "3.14.5")
    monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: "3.14.5")
    monkeypatch.setattr(doctor, "check_legacy_host_integration", lambda b, s: {"name": "legacy_host_integration", "ok": True, "level": "ok", "detail": "x"})
    monkeypatch.setattr(doctor, "check_registration", lambda b, s: {"name": "context_menu", "ok": True, "level": "ok", "detail": "x"})
    monkeypatch.setattr(doctor, "check_sessions", lambda b: {"name": "sessions", "ok": True, "level": "ok", "detail": "x"})
    res = doctor.run({"base_dir": tmp_path, "sys_dir": sys_dir, "args": []})
    assert res["status"] == "success"


def test_check_root_path_clean():
    clean_path = Path("C:/Engram/PortableDev")
    res = doctor.check_root_path(clean_path)
    assert res["ok"] is True
    assert res["level"] == "ok"


def test_check_root_path_warning_on_ampersand(tmp_path):
    bad_path = Path("D:/Engram&Peerhub/PortableDev")
    res = doctor.check_root_path(bad_path)
    assert res["ok"] is True
    assert res["level"] == "warning"
    assert "contains '&'" in res["detail"]
    assert "subst" in res["detail"].lower()


def test_check_root_path_percent():
    bad_path = Path("C:/Users/Test%20User/Engram")
    res = doctor.check_root_path(bad_path)
    assert res["ok"] is True
    assert res["level"] == "warning"
    assert "contains '%'" in res["detail"]


def test_check_root_path_caret():
    bad_path = Path("C:/Engram^Folder/PortableDev")
    res = doctor.check_root_path(bad_path)
    assert res["ok"] is True
    assert res["level"] == "warning"
    assert "contains '^'" in res["detail"]


def test_check_root_path_multiple_special_chars():
    bad_path = Path("C:/Engram&^%Stuff/PortableDev")
    res = doctor.check_root_path(bad_path)
    assert res["ok"] is True
    assert res["level"] == "warning"
    assert "&" in res["detail"]
    assert "%" in res["detail"]
    assert "^" in res["detail"]


def test_doctor_hints_use_canonical_verbs(tmp_path, monkeypatch):
    """Doctor remediation hints must strictly direct to canonical engram verbs, never internal .bat scripts."""
    sys_dir = tmp_path / "_sys"
    _write_runtimes(sys_dir, "3.14.5")

    # 1. Python mismatch
    monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: "3.13.0")
    py_res = doctor.check_python(sys_dir)
    assert "engram" in py_res["detail"].lower()
    assert ".bat" not in py_res["detail"].lower()

    # 2. Missing components
    comp_res = doctor.check_components(sys_dir)
    assert "engram update" in comp_res["detail"].lower()
    assert ".bat" not in comp_res["detail"].lower()

    # 3. Context menu
    reg_res = doctor.check_registration(tmp_path, sys_dir)
    if "detail" in reg_res and "enable" in reg_res["detail"].lower():
        assert "engram menu enable" in reg_res["detail"].lower()
        assert ".bat" not in reg_res["detail"].lower()



