"""Regression tests for findings of the ag.deepthink cross-review of the P0/P1 implementation
(docs/design/engram-env-resilience-review-ag-p0p1-impl-2026-10-02.md)."""
import json
import os
from pathlib import Path

import pytest

from core import env_lock, env_manifest, venv_manager


# ---- 1. install at a drive root: D:\_sys\env\python  ->  root must be "D:\" -------------------------

def test_pyvenv_home_for_an_install_at_a_drive_root():
    assert env_manifest._root_from_pyvenv_home("D:\\_sys\\env\\python") == "D:\\"


def test_drive_root_install_is_not_reported_as_a_move(tmp_path):
    sys_dir = tmp_path / "_sys"
    (sys_dir / "env" / "venv").mkdir(parents=True)
    (sys_dir / "env" / "venv" / "pyvenv.cfg").write_text("home = D:\\_sys\\env\\python\n", encoding="utf-8")
    drift = env_manifest.detect_root_drift(
        None, Path("D:\\"), sys_dir, realpath=lambda p: str(p), path_exists=lambda p: True, localappdata=None)
    assert drift.status == "consistent"


def test_roots_equal_treats_drive_with_and_without_separator_alike():
    assert env_manifest.roots_equal("D:\\", "D:")  # normpath("D:") is "D:", normpath("D:\\") is "D:\\"


# ---- 2. launcher paths: UNC and forward slashes ---------------------------------------------------------------

def test_launcher_path_with_forward_slashes(tmp_path):
    exe = tmp_path / "t.exe"
    exe.write_bytes(b"MZ" + b"#!D:/x/env/venv/Scripts/python.exe\r\n" + b"PK")
    assert venv_manager.launcher_embedded_path(exe) == "D:/x/env/venv/Scripts/python.exe"


def test_launcher_path_on_a_unc_share(tmp_path):
    exe = tmp_path / "t.exe"
    exe.write_bytes(b"MZ" + b"#!\\\\nas\\share\\env\\venv\\Scripts\\python.exe\r\n" + b"PK")
    assert venv_manager.launcher_embedded_path(exe) == "\\\\nas\\share\\env\\venv\\Scripts\\python.exe"


def test_stale_launcher_comparison_ignores_slash_style(tmp_path):
    venv = tmp_path / "_sys" / "env" / "venv"
    scripts = venv / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").touch()
    (venv / "pyvenv.cfg").write_text(f"home = {tmp_path / '_sys' / 'env' / 'python'}\n", encoding="utf-8")
    forward = str(scripts / "python.exe").replace("\\", "/")
    (scripts / "tool.exe").write_bytes(b"MZ" + f"#!{forward}\r\n".encode() + b"PK")

    class R:
        def __call__(self, argv, t):
            return -1, ""

    names = {f.name: f for f in venv_manager.probe_venv(tmp_path / "_sys", runner=R())}
    assert names["console_scripts"].level == "ok"


# ---- 3. breaking a stale lock must never destroy a valid one -----------------------------------------------------------

def _probe(alive):
    return lambda pid: alive.get(pid)


def test_break_stale_restores_a_valid_lock_even_without_hard_links(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    path = env_lock.lock_path(sys_dir)
    valid = {"pid": 1, "start_time": 1.0, "op_id": "new-owner"}
    path.write_text(json.dumps(valid), encoding="utf-8")

    def no_link(a, b):
        raise OSError(1, "hard links unsupported")

    monkeypatch.setattr(env_lock.os, "link", no_link)
    # we *judged* a different (stale) record, but a new owner slipped in before the rename
    env_lock._break_stale(path, {"pid": 99, "start_time": 0.5, "op_id": "stale"})
    assert json.loads(path.read_text(encoding="utf-8"))["op_id"] == "new-owner"
    assert [p.name for p in path.parent.iterdir() if "broken" in p.name] == []


def test_break_stale_discards_the_stale_record_normally(tmp_path):
    sys_dir = tmp_path / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    path = env_lock.lock_path(sys_dir)
    stale = {"pid": 99, "start_time": 0.5, "op_id": "stale"}
    path.write_text(json.dumps(stale), encoding="utf-8")
    env_lock._break_stale(path, stale)
    assert not path.exists()
    assert [p.name for p in path.parent.iterdir() if "broken" in p.name] == []


# ---- 4. pip check (design 5.1 step 8: warning only) -------------------------------------------------------------------------

class _Runner:
    def __init__(self, pip_check):
        self.pip_check = pip_check

    def __call__(self, argv, timeout):
        joined = " ".join(argv)
        if "print(json.dumps([list(sys.version_info" in joined:
            return 0, json.dumps([[3, 14, 8], str(Path(argv[0]).parent.parent)])
        if "pip check" in joined or argv[-2:] == ["pip", "check"]:
            return self.pip_check
        if "ProcessPoolExecutor" in joined:
            return 0, ""
        if "find_spec" in joined:
            return 0, "[]"
        return -1, ""


def _tree(tmp_path):
    sys_dir = tmp_path / "_sys"
    (sys_dir / "env" / "venv" / "Scripts").mkdir(parents=True)
    (sys_dir / "env" / "venv" / "Scripts" / "python.exe").touch()
    (sys_dir / "env" / "python").mkdir(parents=True)
    (sys_dir / "env" / "python" / "python.exe").touch()
    (sys_dir / "env" / "venv" / "pyvenv.cfg").write_text(
        f"home = {sys_dir / 'env' / 'python'}\nversion = 3.14.8\n", encoding="utf-8")
    return sys_dir


def test_pip_check_ok(tmp_path):
    names = {f.name: f for f in venv_manager.probe_venv(_tree(tmp_path), runner=_Runner((0, "No broken requirements found.")))}
    assert names["pip_check"].level == "ok"


def test_pip_check_problems_are_a_warning_not_an_error(tmp_path):
    out = "foo 1.0 requires bar, which is not installed."
    names = {f.name: f for f in venv_manager.probe_venv(_tree(tmp_path), runner=_Runner((1, out)))}
    assert names["pip_check"].level == "warning" and "foo 1.0 requires bar" in names["pip_check"].detail
    assert names["pip_check"].to_check()["ok"] is True


def test_pip_missing_is_info(tmp_path):
    names = {f.name: f for f in venv_manager.probe_venv(_tree(tmp_path), runner=_Runner((1, "No module named pip")))}
    assert names["pip_check"].level == "info"


def test_pip_check_is_skipped_when_the_interpreter_does_not_run(tmp_path):
    sys_dir = tmp_path / "_sys"
    (sys_dir / "env" / "venv" / "Scripts").mkdir(parents=True)   # no python.exe
    names = {f.name: f for f in venv_manager.probe_venv(sys_dir, runner=_Runner((0, "")))}
    assert names["pip_check"].level == "info" and "skipped" in names["pip_check"].detail
