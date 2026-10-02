"""Glue-level guarantees of core.repair that the ag-drafted suite did not pin down
(placeholder URL/version, fictional package names, exit-code mapping, pin handling)."""
import json
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core import env_ops, repair  # noqa: E402


def _tree(tmp_path, pin_version="3.14.8", sha=None, installed=None):
    sys_dir = tmp_path / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    py = {"version": pin_version, "url": f"https://www.python.org/ftp/python/{pin_version}/python-{pin_version}-embed-amd64.zip"}
    if sha:
        py["sha256"] = sha
    (sys_dir / "runtimes.json").write_text(json.dumps({"runtimes": {"python": py}}), encoding="utf-8")
    if installed:
        (sys_dir / "env" / "python").mkdir(parents=True)
        (sys_dir / "env" / "python" / "python.exe").write_text("x")
    return sys_dir


def _update(tmp_path, args, only, installed="3.14.8", **tree):
    sys_dir = _tree(tmp_path, installed=installed, **tree)
    def runner(argv, timeout):
        return (0, f"Python {installed}") if "--version" in argv else (0, "")
    # dry run: build the plan only
    captured = {}
    orig = repair._repair_engine_main

    ctx = {"sys_dir": sys_dir, "base_dir": tmp_path, "args": list(args), "command": "engram update"}
    import types
    res = repair.update_env_main(ctx, only) if False else None
    return sys_dir, runner


# ---- result mapping (design section 10 exit codes) -------------------------------------------------

@pytest.mark.parametrize("res,mode,code,status", [
    ({"status": "success", "phase": "COMMITTED", "detail": "ok"}, "apply", 0, "success"),
    ({"status": "failed", "phase": "ROLLED_BACK", "detail": "verify failed"}, "apply", 12, "failed"),
    ({"status": "failed", "phase": "ROLLBACK_FAILED", "detail": "undo failed"}, "apply", 13, "failed"),
    ({"status": "failed", "phase": None, "detail": "environment lock busy"}, "apply", 11, "failed"),
    ({"status": "failed", "phase": None, "detail": "non-terminal journal blocks"}, "apply", 14, "failed"),
    ({"status": "failed", "phase": "ROLLED_BACK", "detail": "x"}, "rollback", 0, "success"),
    ({"status": "failed", "phase": "ROLLBACK_FAILED", "detail": "x"}, "rollback", 13, "failed"),
    ({"status": "success", "phase": "COMMITTED", "detail": "x"}, "resume", 0, "success"),
    ({"status": "failed", "phase": "ROLLED_BACK", "detail": "x"}, "resume", 12, "failed"),
])
def test_cli_result_mapping(res, mode, code, status):
    out = repair._cli_result(res, mode=mode)
    assert out["exit_code"] == code and out["status"] == status and out["operation"] == "repair"


# ---- python pin / installed version ----------------------------------------------------------------------

def test_python_pin_is_read_from_runtimes_json(tmp_path):
    sys_dir = _tree(tmp_path, pin_version="3.14.9", sha="ab" * 32)
    pin = repair._python_pin(sys_dir)
    assert pin["version"] == "3.14.9" and pin["sha256"] == "ab" * 32
    assert pin["url"].endswith("python-3.14.9-embed-amd64.zip")


def test_missing_runtimes_json_gives_an_empty_pin(tmp_path):
    assert repair._python_pin(tmp_path / "nope") == {"version": "", "url": "", "sha256": None}


def test_installed_python_prefers_the_manifest(tmp_path):
    from core import env_manifest
    sys_dir = _tree(tmp_path)
    env_manifest.write_manifest(sys_dir, {"schema_version": 1, "install_id": "i" * 36,
                                          "root": {"logical": "x", "physical": "x"},
                                          "python": {"version": "3.14.7"}})
    assert repair._installed_python(sys_dir, {"runner": lambda a, t: (0, "Python 9.9.9")}) == "3.14.7"


def test_installed_python_falls_back_to_probing_the_interpreter(tmp_path):
    sys_dir = _tree(tmp_path, installed="3.14.8")
    assert repair._installed_python(sys_dir, {"runner": lambda a, t: (0, "Python 3.14.8\n")}) == "3.14.8"


def test_installed_python_absent_is_none(tmp_path):
    assert repair._installed_python(_tree(tmp_path), {}) is None


# ---- update plan: no placeholders ---------------------------------------------------------------------------

def _plan(tmp_path, args, only, installed="3.14.8", **tree):
    sys_dir = _tree(tmp_path, installed=installed, **tree)
    ctx = {"sys_dir": sys_dir, "base_dir": tmp_path, "args": list(args), "command": "engram update"}
    out = repair.update_env_main(ctx, set(only))
    return out


def test_update_python_dry_run_uses_the_pin_not_a_placeholder(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.7")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {"manifest": "ok", "drift": {"status": "consistent"},
                                                           "findings": [], "stale_registry": [], "journal": None, "lock": None})
    out = _plan(tmp_path, [], {"python"}, pin_version="3.14.8")
    text = capsys.readouterr().out
    assert out["exit_code"] == 0 and "example.com" not in text
    assert "3.14.7 -> 3.14.8" in text and "patch" in text


def test_update_python_to_a_major_version_is_blocked_without_the_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.8")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {"manifest": "ok", "drift": {"status": "consistent"},
                                                           "findings": [], "stale_registry": [], "journal": None, "lock": None})
    out = _plan(tmp_path, ["--to", "4.0.0"], {"python"})
    assert out["exit_code"] != 0 and "allow-major-runtime-upgrade" in out["detail"]


def test_update_python_same_version_is_a_noop_unless_forced(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.8")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {"manifest": "ok", "drift": {"status": "consistent"},
                                                           "findings": [], "stale_registry": [], "journal": None, "lock": None})
    out = _plan(tmp_path, [], {"python"})
    assert out["exit_code"] == 0 and "already at 3.14.8" in capsys.readouterr().out


# ---- packages: real names, venv interpreter, snapshot first -------------------------------------------------------

def test_package_upgrade_steps_use_real_baseline_names_and_the_venv_python(tmp_path):
    sys_dir = _tree(tmp_path)
    calls = []
    steps = repair.steps_from_spec(sys_dir, tmp_path, [{"name": "upgrade-packages", "group": "A", "kind": "packages",
                                                       "params": {"all_packages": False}}],
                                   runner=lambda argv, t: calls.append(argv) or (0, ""))
    assert [s.name for s in steps] == ["snapshot-packages", "upgrade-packages"]
    ctx = env_ops.OpContext(sys_dir, "op", "update", {}, {})
    steps[1].do(ctx)
    argv = calls[0]
    assert argv[0].endswith("python.exe") and "venv" in argv[0]
    assert argv[1:5] == ["-m", "pip", "install", "--upgrade"]
    assert set(argv[5:]) == {"filelock", "psutil", "pydantic", "pywinpty"}
    assert not any("engram" in a for a in argv)


def test_all_packages_adds_requested_non_editable_packages(tmp_path):
    from core import venv_manager
    sys_dir = _tree(tmp_path)
    venv_manager.write_snapshot(sys_dir, {"created_at": "2026-10-02T00:00:00Z", "packages": [
        {"name": "pytest", "requested": True, "editable": False},
        {"name": "peerhub", "requested": True, "editable": True},
        {"name": "pluggy", "requested": False, "editable": False},
        {"name": "psutil", "requested": True, "editable": False}]})
    calls = []
    steps = repair.steps_from_spec(sys_dir, tmp_path, [{"name": "upgrade-packages", "group": "A", "kind": "packages",
                                                       "params": {"all_packages": True}}],
                                   runner=lambda argv, t: calls.append(argv) or (0, ""))
    steps[1].do(env_ops.OpContext(sys_dir, "op", "update", {}, {}))
    names = set(calls[0][5:])
    assert "pytest" in names and "peerhub" not in names and "pluggy" not in names
    assert {"filelock", "psutil", "pydantic", "pywinpty"} <= names


def test_package_upgrade_failure_raises_so_the_engine_reports_it(tmp_path):
    sys_dir = _tree(tmp_path)
    steps = repair.steps_from_spec(sys_dir, tmp_path, [{"name": "upgrade-packages", "group": "A", "kind": "packages",
                                                       "params": {}}], runner=lambda argv, t: (1, "boom"))
    with pytest.raises(RuntimeError, match="pip upgrade failed"):
        steps[1].do(env_ops.OpContext(sys_dir, "op", "update", {}, {}))


# ---- adoption is group B and idempotent -------------------------------------------------------------------------

def test_adopt_manifest_describes_the_current_root_and_records_last_base_dir(tmp_path):
    from core import env_manifest
    sys_dir = _tree(tmp_path)
    steps = repair.steps_from_spec(sys_dir, tmp_path, [{"name": "adopt-manifest", "group": "B", "kind": "manifest", "params": {}}])
    assert steps[0].group == "B"
    steps[0].do(env_ops.OpContext(sys_dir, "op", "repair", {}, {}))
    data = env_manifest.read_manifest(sys_dir).data
    assert data["root"]["logical"] == str(tmp_path)
    assert (sys_dir / "data" / "last_base_dir.txt").read_text(encoding="utf-8") == str(tmp_path)
    assert steps[0].done(env_ops.OpContext(sys_dir, "op", "repair", {}, {})) is True
