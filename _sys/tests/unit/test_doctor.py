from __future__ import annotations

import json
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]  # _sys/
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


def test_check_subst_detects_running_from_mount(tmp_path, monkeypatch):
    monkeypatch.setattr("core.virtualizer._get_subst_mappings", lambda: {"P": r"D:\PortableDev"})
    r = doctor.check_subst(Path("P:/"))
    assert r["ok"] is True and r["level"] == "ok"
    assert "P:" in r["detail"]


def test_check_subst_not_mounted_is_info(tmp_path, monkeypatch):
    monkeypatch.setattr("core.virtualizer._get_subst_mappings", lambda: {})
    r = doctor.check_subst(tmp_path)
    assert r["ok"] is True and r["level"] == "info"


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
    monkeypatch.setattr(doctor, "check_subst", lambda b: {"name": "subst_drive", "ok": True, "level": "info", "detail": "x"})
    monkeypatch.setattr(doctor, "check_registration", lambda b, s: {"name": "context_menu", "ok": True, "level": "info", "detail": "x"})
    monkeypatch.setattr(doctor, "check_sessions", lambda b: {"name": "sessions", "ok": True, "level": "ok", "detail": "x"})
    res = doctor.run({"base_dir": tmp_path, "sys_dir": sys_dir, "args": ["--json"]})
    assert res["status"] == "failed"  # python missing is the hard gate


def test_run_healthy_when_python_ok(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    _write_runtimes(sys_dir, "3.14.5")
    monkeypatch.setattr(doctor, "_installed_python_version", lambda sd: "3.14.5")
    monkeypatch.setattr(doctor, "check_subst", lambda b: {"name": "subst_drive", "ok": True, "level": "ok", "detail": "x"})
    monkeypatch.setattr(doctor, "check_registration", lambda b, s: {"name": "context_menu", "ok": True, "level": "ok", "detail": "x"})
    monkeypatch.setattr(doctor, "check_sessions", lambda b: {"name": "sessions", "ok": True, "level": "ok", "detail": "x"})
    res = doctor.run({"base_dir": tmp_path, "sys_dir": sys_dir, "args": []})
    assert res["status"] == "success"
