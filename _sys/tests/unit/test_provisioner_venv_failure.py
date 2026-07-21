"""Regression test for a real NameError introduced and fixed in this repo's
history: deploy()'s venv step referenced a `venv_failed` flag that had been
removed, which only crashed on the path where venv_py doesn't exist AND
creation fails - a path no existing test exercised (test_provisioner_autoinstall
always pre-creates a fake venv_py, so it never reaches this branch)."""
import json
import subprocess
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "core"))
import provisioner as pv  # noqa: E402


def _make_deploy_ctx_no_venv(tmp_path: Path) -> dict:
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    (sys_dir / "runtimes.json").write_text(
        json.dumps({"runtimes": {}, "tools": {}}), encoding="utf-8"
    )
    (sys_dir / "ai").mkdir()
    (sys_dir / "ai" / "peers.json").write_text(json.dumps({"peers": {}}), encoding="utf-8")
    (sys_dir / "tools").mkdir()
    (sys_dir / "data" / "setup-files").mkdir(parents=True)
    # Deliberately no env/venv/Scripts/python.exe - forces deploy() down the
    # "create venv" branch instead of the "already exists" shortcut.
    return {"base_dir": tmp_path, "sys_dir": sys_dir, "args": [], "state": {}}


def test_deploy_reports_venv_creation_failure_without_crashing(monkeypatch, tmp_path):
    ctx = _make_deploy_ctx_no_venv(tmp_path)

    def _failing_run(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(pv.subprocess, "run", _failing_run)

    result = pv.deploy(ctx)  # must not raise NameError

    assert result["status"] == "failed"
    venv_failures = [f for f in result["failed"] if f["component"] == "venv"]
    assert len(venv_failures) == 1
    assert venv_failures[0]["status"] == "error"
