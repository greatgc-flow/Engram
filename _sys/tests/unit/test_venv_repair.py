import os
import sys
import ntpath
import pytest
import shutil
import json
from pathlib import Path

# Fallback in case core.env_ops doesn't exist during test discovery
try:
    from core.env_ops import Step, OpContext
except ImportError:
    class Step:
        def __init__(self, name, do, undo=None, done=None, group="A"):
            self.name = name
            self.do = do
            self.undo = undo
            self.done = done
            self.group = group
    class OpContext:
        def __init__(self, sys_dir, op_id, kind, paths=None, data=None):
            self.sys_dir = Path(sys_dir)
            self.op_id = op_id
            self.kind = kind
            self.paths = paths or {}
            self.data = data or {}

from core.venv_repair import (
    rewrite_pyvenv_cfg,
    regenerate_console_scripts,
    plan_venv_repair,
    restore_packages_step_data,
    rebase_path
)

class FakeRunner:
    def __init__(self, rc=0, out=""):
        self.rc = rc
        self.out = out
        self.calls = []
    def __call__(self, argv, timeout):
        self.calls.append(argv)
        return self.rc, self.out

def test_rewrite_pyvenv_cfg(tmp_path):
    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()
    cfg = venv_dir / "pyvenv.cfg"
    original = b"home = C:\\old\r\nversion = 3.14.7\r\n"
    cfg.write_bytes(original)
    
    managed = tmp_path / "managed"
    managed.mkdir()
    
    changed = rewrite_pyvenv_cfg(venv_dir, managed, python_version="3.14.8")
    assert changed
    
    content = cfg.read_bytes()
    assert b"home = " + str(managed).encode("utf-8") + b"\r\n" in content
    assert b"version = 3.14.8\r\n" in content
    
    changed2 = rewrite_pyvenv_cfg(venv_dir, managed, python_version="3.14.8")
    assert not changed2

def test_regenerate_console_scripts(tmp_path):
    venv_dir = tmp_path / "venv"
    scripts = venv_dir / "Scripts"
    site_packages = venv_dir / "Lib" / "site-packages"
    dist_info = site_packages / "foo-1.0.dist-info"
    dist_info.mkdir(parents=True)
    
    ep = dist_info / "entry_points.txt"
    ep.write_text("[console_scripts]\nfoo = foo:main\n")
    
    def real_runner(argv, timeout):
        import subprocess
        res = subprocess.run(argv, capture_output=True, text=True)
        return res.returncode, res.stdout + res.stderr
        
    real_scripts_dir = Path(sys.prefix) / "Scripts"
    initial_scripts = []
    if real_scripts_dir.exists():
        initial_scripts = sorted([(f.name, f.stat().st_mtime) for f in real_scripts_dir.iterdir()])

    res = regenerate_console_scripts(venv_dir, python_exe=Path(sys.executable), runner=real_runner)
    
    assert res.get("regenerated", 0) >= 1
    assert (scripts / "foo.exe").exists()
    
    if real_scripts_dir.exists():
        final_scripts = sorted([(f.name, f.stat().st_mtime) for f in real_scripts_dir.iterdir()])
        assert initial_scripts == final_scripts

def test_regenerate_script_no_sys_prefix():
    from core.venv_repair import _REGENERATE_SCRIPT
    assert "sys.prefix" not in _REGENERATE_SCRIPT

def test_plan_venv_repair_rebuild(tmp_path):
    findings = [{"name": "venv_interpreter", "level": "error"}]
    steps = plan_venv_repair(tmp_path, findings)
    names = [s.name for s in steps]
    assert names == ["quarantine-venv", "create-venv", "restore-packages", "regenerate-console-scripts"]

def test_plan_venv_repair_patch_skew(tmp_path):
    findings = [{"name": "venv_interpreter_skew", "level": "warning", "detail": "patch-skew"}]
    steps = plan_venv_repair(tmp_path, findings)
    names = [s.name for s in steps]
    assert names == ["backup-interpreter-files", "refresh-interpreter", "record-interpreter-hashes"]

def test_plan_venv_repair_rewrite(tmp_path):
    findings = [{"name": "pyvenv_home", "level": "error"}]
    steps = plan_venv_repair(tmp_path, findings)
    assert steps[0].name == "rewrite-pyvenv-cfg"
    
def test_plan_venv_repair_console(tmp_path):
    findings = [{"name": "console_scripts", "level": "warning", "detail": "stale-launchers: foo"}]
    steps = plan_venv_repair(tmp_path, findings)
    assert steps[0].name == "regenerate-console-scripts"

def test_restore_packages_step_data(tmp_path):
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    import urllib.request
    url = "file:///" + urllib.request.pathname2url(str(pkg_dir)).lstrip("/")
    
    snapshot = {
        "packages": [
            {"name": "filelock", "version": "1.0"},
            {"name": "pytest", "version": "7.0", "requested": True},
            {"name": "my-pkg", "editable": True, "editable_url": url},
            {"name": "skipped-pkg", "editable": True, "editable_url": "file:///D:/does/not/exist"}
        ]
    }
    plan = restore_packages_step_data(snapshot)
    assert plan["t1"] == ["filelock==1.0"]
    assert plan["t2"] == ["pytest==7.0"]
    assert str(pkg_dir) in plan["t3"]
    assert "skipped-pkg" in plan["skipped_editable"]
    assert "pytest==7.0" in plan["constraints_text"]

def test_restore_packages_credential_scrubbing(tmp_path):
    snapshot = {
        "packages": [
            {"name": "my-pkg", "editable": True, "editable_url": "file:///D:/pkg?token=secret"}
        ]
    }
    plan = restore_packages_step_data(snapshot)
    assert "token=secret" not in plan["t3"]
    
def test_rebase_path_cases():
    assert rebase_path(r"D:\old\foo", r"d:\old", r"E:\new") == ntpath.normpath(r"E:\new\foo")
    assert rebase_path(r"D:\other\foo", r"d:\old", r"E:\new") is None
    assert rebase_path(r"D:\old\foo", r"d:\old\\", r"E:\new") == ntpath.normpath(r"E:\new\foo")
    assert rebase_path(r"\\server\share\old\foo", r"\\server\share\old", r"E:\new") == ntpath.normpath(r"E:\new\foo")

def test_rebuild_undo_quarantines(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    venv_dir = sys_dir / "env" / "venv"
    venv_dir.mkdir(parents=True)
    (venv_dir / "test.txt").write_text("old venv")
    
    findings = [{"name": "venv_interpreter", "level": "error"}]
    steps = plan_venv_repair(sys_dir, findings, runner=FakeRunner())
    
    paths = {
        "venv_backup": str(sys_dir / "data" / "backups" / "env" / "venv" / "bkp"),
        "venv_failed_backup": str(sys_dir / "data" / "backups" / "env" / "venv" / "failed"),
    }
    ctx = OpContext(sys_dir, "op-1", "repair", paths, {})
    
    # quarantine
    steps[0].do(ctx)
    assert not venv_dir.exists()
    
    # create
    venv_dir.mkdir(parents=True)
    (venv_dir / "test2.txt").write_text("new venv")
    
    # undo create (moves new venv into a failed-rebuild backup)
    steps[1].undo(ctx)
    assert not (venv_dir / "test2.txt").exists()
    
    # undo quarantine (restores old venv)
    steps[0].undo(ctx)
    assert (venv_dir / "test.txt").exists()

def test_rebuild_undo_quarantines_crash(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    venv_dir = sys_dir / "env" / "venv"
    venv_dir.mkdir(parents=True)
    (venv_dir / "test.txt").write_text("old venv")
    
    findings = [{"name": "venv_interpreter", "level": "error"}]
    steps = plan_venv_repair(sys_dir, findings, runner=FakeRunner())
    
    paths = {
        "venv_backup": str(sys_dir / "data" / "backups" / "env" / "venv" / "bkp"),
        "venv_failed_backup": str(sys_dir / "data" / "backups" / "env" / "venv" / "failed"),
    }
    ctx = OpContext(sys_dir, "op-1", "repair", paths, {})
    
    # quarantine
    steps[0].do(ctx)
    assert not venv_dir.exists()
    
    # create half-built replacement
    venv_dir.mkdir(parents=True)
    (venv_dir / "test2.txt").write_text("half-built venv")
    
    # crash between move and done simulated by empty ctx.data
    from core import backups
    marker_only = sys_dir / "data" / "backups" / "env" / "venv" / "marker-only"
    marker_only.mkdir(parents=True)
    meta = {"schema_version": 1, "kind": "venv", "state": "pending", "created_at": "now", "op_id": "op-1", "label": "broken-venv"}
    (marker_only / backups.MARKER).write_text(json.dumps(meta))
    
    ctx.data = {}
    # undo quarantine directly without undo create to simulate crash logic checking missing payload
    steps[0].undo(ctx)
    
    assert (venv_dir / "test.txt").exists()
    assert not (venv_dir / "test2.txt").exists()
    assert (Path(paths["venv_failed_backup"]) / backups.PAYLOAD / "test2.txt").exists()

def test_refresh_foreign_files(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    venv_dir = sys_dir / "env" / "venv"
    venv_dir.mkdir(parents=True)
    scripts = venv_dir / "Scripts"
    scripts.mkdir(parents=True)
    
    old_dll = scripts / "python3.dll"
    old_dll.write_bytes(b"old")
    foreign = scripts / "user.dll"
    foreign.write_bytes(b"foreign")
    stale_dll = scripts / "stale.dll"
    stale_dll.write_bytes(b"stale")
    
    managed_py = sys_dir / "env" / "python"
    managed_py.mkdir(parents=True)
    (managed_py / "python.exe").touch()
    
    def fake_runner(argv, timeout):
        if "virtualenv" in argv and "venv-probe" not in argv[-1]:
            (scripts / "python3.dll").write_bytes(b"new")
        elif "virtualenv" in argv and "venv-probe" in argv[-1]:
            probe_scripts = Path(argv[-1]) / "Scripts"
            probe_scripts.mkdir(parents=True)
            (probe_scripts / "python3.dll").write_bytes(b"new")
            (probe_scripts / "python.exe").touch()
        return 0, ""
        
    findings = [{"name": "venv_interpreter_skew", "level": "warning", "detail": "patch-skew"}]
    
    import hashlib
    manifest = {
        "venv": {
            "interpreter_hashes": {
                "Scripts/python3.dll": hashlib.sha256(b"old").hexdigest(),
                "Scripts/stale.dll": hashlib.sha256(b"stale").hexdigest()
            }
        }
    }
    
    steps = plan_venv_repair(sys_dir, findings, manifest=manifest, runner=fake_runner)
    paths = {"venv_interp_backup": str(sys_dir / "data" / "backups" / "env" / "venv-interp" / "bkp")}
    ctx = OpContext(sys_dir, "op-1", "repair", paths, {})
    
    steps[0].do(ctx) # backup
    steps[1].do(ctx) # refresh
    
    assert (scripts / "python3.dll").read_bytes() == b"new"
    assert foreign.exists()
    assert "Scripts/user.dll" in ctx.data["kept_foreign_files"]
    assert not stale_dll.exists()

    # Case 2: No baseline recorded -> treat NOTHING as removable
    stale_dll.write_bytes(b"stale")
    old_dll.write_bytes(b"old")
    
    paths2 = {"venv_interp_backup": str(sys_dir / "data" / "backups" / "env" / "venv-interp" / "bkp2")}
    ctx2 = OpContext(sys_dir, "op-2", "repair", paths2, {})
    steps_no_baseline = plan_venv_repair(sys_dir, findings, manifest=None, runner=fake_runner)
    
    steps_no_baseline[0].do(ctx2) # backup
    steps_no_baseline[1].do(ctx2) # refresh
    
    assert foreign.exists()
    assert "Scripts/user.dll" in ctx2.data["kept_foreign_files"]
    assert stale_dll.exists()
    assert "Scripts/stale.dll" in ctx2.data["kept_foreign_files"]

def test_failed_refresh_keeps_files(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    venv_dir = sys_dir / "env" / "venv"
    venv_dir.mkdir(parents=True)
    
    findings = [{"name": "venv_interpreter_skew", "level": "warning", "detail": "patch-skew"}]
    
    def failing_runner(argv, timeout):
        return 1, "failed"
        
    steps = plan_venv_repair(sys_dir, findings, runner=failing_runner)
    paths = {"venv_interp_backup": str(sys_dir / "data" / "backups" / "env" / "venv-interp" / "bkp")}
    ctx = OpContext(sys_dir, "op-1", "repair", paths, {})
    
    steps[0].do(ctx)
    with pytest.raises(RuntimeError, match="failed"):
        steps[1].do(ctx)

def test_lock_probe_abort(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    venv_dir = sys_dir / "env" / "venv"
    scripts = venv_dir / "Scripts"
    scripts.mkdir(parents=True)
    python_exe = scripts / "python.exe"
    python_exe.write_bytes(b"exe")
    
    findings = [{"name": "venv_interpreter_skew", "level": "warning", "detail": "patch-skew"}]
    steps = plan_venv_repair(sys_dir, findings)
    paths = {"venv_interp_backup": str(sys_dir / "data" / "backups" / "env" / "venv-interp" / "bkp")}
    ctx = OpContext(sys_dir, "op-1", "repair", paths, {})
    
    import core.venv_repair
    original_rename = core.venv_repair.os.rename
    def failing_rename(src, dst):
        if "python.exe" in str(src):
            raise PermissionError("locked")
        original_rename(src, dst)
        
    core.venv_repair.os.rename = failing_rename
    try:
        with pytest.raises(PermissionError):
            steps[0].do(ctx)
        assert python_exe.exists()
        assert not (scripts / "python.exe.lockprobe").exists()
    finally:
        core.venv_repair.os.rename = original_rename

def test_lockprobe_leftover_recovery(tmp_path):
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    venv_dir = sys_dir / "env" / "venv"
    scripts = venv_dir / "Scripts"
    scripts.mkdir(parents=True)
    leftover = scripts / "python.exe.lockprobe"
    leftover.write_bytes(b"exe")
    
    findings = [{"name": "venv_interpreter_skew", "level": "warning", "detail": "patch-skew"}]
    steps = plan_venv_repair(sys_dir, findings)
    paths = {"venv_interp_backup": str(sys_dir / "data" / "backups" / "env" / "venv-interp" / "bkp")}
    ctx = OpContext(sys_dir, "op-1", "repair", paths, {})
    
    steps[0].do(ctx)
    assert (scripts / "python.exe").exists()
    assert not leftover.exists()

@pytest.mark.skipif(os.environ.get("ENGRAM_SKIP_REAL_VENV_TESTS") == "1", reason="Skip real venv tests")
def test_real_venv_refresh_and_regen(tmp_path):
    repo_root = Path(__file__).parent.parent.parent.parent
    managed_py = repo_root / "_sys" / "env" / "python" / "python.exe"
    if not managed_py.exists():
        pytest.skip(f"Embedded python not found at {managed_py}")
        
    venv_dir = tmp_path / "venv"
    import subprocess
    # Seeded on purpose: console-script regeneration needs pip's vendored distlib inside the venv.
    subprocess.run([str(managed_py), "-m", "virtualenv", str(venv_dir)], check=True)
    
    venv_py = venv_dir / "Scripts" / "python.exe"
    assert venv_py.exists()
    
    subprocess.run([str(managed_py), "-m", "virtualenv", str(venv_dir)], check=True)
    
    site_packages = venv_dir / "Lib" / "site-packages"
    dist_info = site_packages / "fake-1.0.dist-info"
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "entry_points.txt").write_text("[console_scripts]\nfake-tool = fake:main\n")
    
    def real_runner(argv, timeout):
        res = subprocess.run(argv, capture_output=True, text=True)
        return res.returncode, res.stdout + res.stderr
        
    res = regenerate_console_scripts(venv_dir, python_exe=venv_py, runner=real_runner)
    assert res.get("failed") == [], res
    assert (venv_dir / "Scripts" / "fake-tool.exe").exists()


def test_rebuild_commits_quarantine_backup_on_success(tmp_path):
    from core import backups
    sys_dir = tmp_path / "_sys"
    venv_dir = sys_dir / "env" / "venv"
    venv_dir.mkdir(parents=True)
    (venv_dir / "test.txt").write_text("old venv")
    steps = plan_venv_repair(sys_dir, [{"name": "venv_interpreter", "level": "error"}], runner=FakeRunner(0, json.dumps({"regenerated": 0, "failed": []})))
    paths = {"venv_backup": str(sys_dir / "data" / "backups" / "env" / "venv" / "bkp"),
             "venv_failed_backup": str(sys_dir / "data" / "backups" / "env" / "venv" / "failed")}
    ctx = OpContext(sys_dir, "op-1", "repair", paths, {})
    steps[0].do(ctx)
    states = [r.meta["state"] for r in backups.scan(sys_dir).valid if r.meta.get("op_id") == "op-1"]
    assert states == ["pending"]
    venv_dir.mkdir(parents=True)
    by_name = {s.name: s for s in steps}
    by_name["regenerate-console-scripts"].do(ctx)
    states = [r.meta["state"] for r in backups.scan(sys_dir).valid if r.meta.get("op_id") == "op-1"]
    assert states == ["committed"]


def test_regenerate_reports_missing_distlib_as_failure(tmp_path):
    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()
    res = regenerate_console_scripts(
        venv_dir, python_exe=venv_dir / "python.exe",
        runner=lambda argv, timeout: (0, json.dumps({"error": "distlib.scripts not found"})))
    assert res["regenerated"] == 0 and res["failed"] and "distlib" in res["failed"][0]


def _patch_skew_ctx(tmp_path, runner):
    sys_dir = tmp_path / "_sys"
    scripts = sys_dir / "env" / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_text("ORIGINAL")
    steps = plan_venv_repair(
        sys_dir, [{"name": "venv_interpreter_skew", "level": "warning", "detail": "patch-skew"}], runner=runner)
    paths = {"venv_interp_backup": str(sys_dir / "data" / "backups" / "env" / "venv-interp" / "bkp")}
    return sys_dir, scripts, {s.name: s for s in steps}, OpContext(sys_dir, "op-1", "repair", paths, {})


def test_refresh_undo_restores_original_interpreter_files(tmp_path):
    def failing(argv, timeout):
        return 1, "boom"
    sys_dir, scripts, by_name, ctx = _patch_skew_ctx(tmp_path, failing)
    by_name["backup-interpreter-files"].do(ctx)
    (scripts / "python.exe").write_text("CLOBBERED")
    with pytest.raises(RuntimeError):
        by_name["refresh-interpreter"].do(ctx)
    by_name["refresh-interpreter"].undo(ctx)
    assert (scripts / "python.exe").read_text() == "ORIGINAL"


def test_refresh_undo_fails_loudly_without_backup(tmp_path):
    sys_dir, scripts, by_name, ctx = _patch_skew_ctx(tmp_path, FakeRunner())
    with pytest.raises(RuntimeError, match="backup not found"):
        by_name["refresh-interpreter"].undo(ctx)


def test_regen_failure_raises_and_does_not_commit_backups(tmp_path):
    from core import backups
    sys_dir = tmp_path / "_sys"
    venv_dir = sys_dir / "env" / "venv"
    venv_dir.mkdir(parents=True)
    (venv_dir / "test.txt").write_text("old venv")
    bad = FakeRunner(0, json.dumps({"regenerated": 0, "failed": ["pip.exe"]}))
    steps = plan_venv_repair(sys_dir, [{"name": "venv_interpreter", "level": "error"}], runner=bad)
    paths = {"venv_backup": str(sys_dir / "data" / "backups" / "env" / "venv" / "bkp"),
             "venv_failed_backup": str(sys_dir / "data" / "backups" / "env" / "venv" / "failed")}
    ctx = OpContext(sys_dir, "op-1", "repair", paths, {})
    by_name = {s.name: s for s in steps}
    by_name["quarantine-venv"].do(ctx)
    venv_dir.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="regeneration failed"):
        by_name["regenerate-console-scripts"].do(ctx)
    states = [r.meta["state"] for r in backups.scan(sys_dir).valid if r.meta.get("op_id") == "op-1"]
    assert states == ["pending"]


def test_refresh_undo_fails_on_unreadable_payload(tmp_path, monkeypatch):
    sys_dir, scripts, by_name, ctx = _patch_skew_ctx(tmp_path, FakeRunner())
    by_name["backup-interpreter-files"].do(ctx)
    real_walk = os.walk

    def bad_walk(top, topdown=True, onerror=None, followlinks=False):
        if onerror:
            onerror(OSError("denied"))
        return real_walk(top, topdown, onerror, followlinks)
    monkeypatch.setattr(os, "walk", bad_walk)
    with pytest.raises(OSError):
        by_name["refresh-interpreter"].undo(ctx)


def test_combined_skew_and_stale_commits_only_after_regen(tmp_path):
    from core import backups
    sys_dir = tmp_path / "_sys"
    (sys_dir / "env" / "venv" / "Scripts").mkdir(parents=True)
    (sys_dir / "env" / "venv" / "Scripts" / "python.exe").write_text("X")
    findings = [{"name": "venv_interpreter_skew", "level": "warning", "detail": "patch-skew"},
                {"name": "console_scripts", "level": "warning", "detail": "stale-launchers: 1"}]
    bad = FakeRunner(0, json.dumps({"regenerated": 0, "failed": ["pip.exe"]}))
    steps = plan_venv_repair(sys_dir, findings, runner=bad)
    by_name = {s.name: s for s in steps}
    ctx = OpContext(sys_dir, "op-1", "repair",
                    {"venv_interp_backup": str(sys_dir / "data" / "backups" / "env" / "venv-interp" / "bkp")}, {})
    by_name["backup-interpreter-files"].do(ctx)
    by_name["record-interpreter-hashes"].do(ctx)
    st = lambda: [r.meta["state"] for r in backups.scan(sys_dir).valid if r.meta.get("op_id") == "op-1"]
    assert st() == ["pending"]
    with pytest.raises(RuntimeError):
        by_name["regenerate-console-scripts"].do(ctx)
    assert st() == ["pending"]
