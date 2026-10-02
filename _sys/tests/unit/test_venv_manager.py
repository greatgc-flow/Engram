import json
import os
import shutil
from pathlib import Path

import pytest
from core import venv_manager


class FakeRunner:
    def __init__(self):
        self.mappings = []
        self.calls = []
        
    def add(self, pattern, rc, output):
        self.mappings.append((pattern, rc, output))
        
    def __call__(self, argv, timeout_s):
        self.calls.append(argv)
        cmd = " ".join(argv)
        for pattern, rc, output in self.mappings:
            if pattern in cmd:
                return rc, output
        return -1, "Command not mapped"


def _setup_tree(tmp_path: Path):
    sys_dir = tmp_path / "_sys"
    venv_dir = sys_dir / "env" / "venv"
    python_dir = sys_dir / "env" / "python"
    
    venv_dir.mkdir(parents=True)
    python_dir.mkdir(parents=True)
    
    (python_dir / "python.exe").touch()
    
    scripts = venv_dir / "Scripts"
    scripts.mkdir()
    (scripts / "python.exe").touch()
    (scripts / "pythonw.exe").touch()
    (scripts / "python311.dll").touch()
    (scripts / "python311.zip").touch()
    (scripts / "pip.exe").write_bytes(b"MZ...stub" + b"#!D:\\x\\env\\venv\\Scripts\\python.exe\r\n" + b"PK...")
    
    cfg = venv_dir / "pyvenv.cfg"
    cfg.write_text(f"home = {python_dir}\nversion = 3.11.2\n")
    return sys_dir, venv_dir, python_dir


def test_probe_venv_happy_path(tmp_path):
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    
    runner = FakeRunner()
    runner.add("print(json.dumps([list(sys.version_info", 0, f'[[3,11,2], "{venv_dir.as_posix()}"]')
    runner.add("ProcessPoolExecutor", 0, "")
    runner.add("['filelock', 'psutil'", 0, "[]")
    runner.add("--version", 0, "Python 3.11.2")
    
    scripts = venv_dir / "Scripts"
    (scripts / "pip.exe").write_bytes(b"MZ...stub" + f"#!{scripts / 'python.exe'}\r\n".encode() + b"PK...")
    
    manifest = {"venv": {"interpreter_hashes": {}}}
    manifest["venv"]["interpreter_hashes"] = venv_manager.hash_files(venv_dir, venv_manager.interpreter_file_set(venv_dir))
    
    mtimes_before = {p: p.stat().st_mtime for p in tmp_path.rglob("*") if p.is_file()}
    
    findings = venv_manager.probe_venv(sys_dir, runner=runner, manifest=manifest)
    
    names = {f.name: f for f in findings}
    assert names["venv_interpreter"].level == "ok"
    assert names["venv_prefix"].level == "ok"
    assert names["venv_spawn"].level == "ok"
    assert names["venv_imports"].level == "ok"
    assert names["pyvenv_home"].level == "ok"
    assert names["venv_interpreter_skew"].level == "ok"
    assert names["interpreter_integrity"].level == "ok"
    assert names["console_scripts"].level == "ok"
    
    mtimes_after = {p: p.stat().st_mtime for p in tmp_path.rglob("*") if p.is_file()}
    assert mtimes_before == mtimes_after


def test_probe_venv_interpreter_missing(tmp_path):
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    (venv_dir / "Scripts" / "python.exe").unlink()
    
    findings = venv_manager.probe_venv(sys_dir, runner=FakeRunner())
    names = {f.name: f for f in findings}
    
    assert names["venv_interpreter"].level == "error"
    assert names["venv_interpreter"].detail == "venv interpreter does not run"
    assert names["venv_spawn"].level == "info"
    assert names["venv_spawn"].detail == "skipped: interpreter does not run"


def test_probe_venv_dir_absent(tmp_path):
    sys_dir = tmp_path / "_sys"
    findings = venv_manager.probe_venv(sys_dir, runner=FakeRunner())
    names = {f.name: f for f in findings}
    assert names["venv_interpreter"].level == "info"
    assert names["venv_interpreter"].detail == "venv not present"


def test_probe_venv_spawn_failure(tmp_path):
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    runner = FakeRunner()
    runner.add("print(json.dumps([list(sys.version_info", 0, f'[[3,11,2], "{venv_dir.as_posix()}"]')
    runner.add("ProcessPoolExecutor", -1, "Fail")
    runner.add("--version", 0, "Python 3.11.2")
    runner.add("['filelock', 'psutil'", 0, "[]")
    
    findings = venv_manager.probe_venv(sys_dir, runner=runner)
    names = {f.name: f for f in findings}
    assert names["venv_spawn"].level == "error"
    assert "pyvenv.cfg home may not resolve" in names["venv_spawn"].detail


def test_pyvenv_home_missing_or_different(tmp_path):
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    cfg = venv_dir / "pyvenv.cfg"
    
    cfg.unlink()
    findings = venv_manager.probe_venv(sys_dir, runner=FakeRunner())
    names = {f.name: f for f in findings}
    assert names["pyvenv_home"].level == "error"
    
    other_python = tmp_path / "other"
    other_python.mkdir()
    (other_python / "python.exe").touch()
    cfg.write_text(f"home = {other_python}\nversion = 3.11.2\n")
    
    findings = venv_manager.probe_venv(sys_dir, runner=FakeRunner())
    names = {f.name: f for f in findings}
    assert names["pyvenv_home"].level == "info"
    assert names["pyvenv_home"].detail == "skew"


def test_interpreter_skew(tmp_path):
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    runner = FakeRunner()
    runner.add("print(json.dumps([list(sys.version_info", 0, f'[[3,11,2], "{venv_dir.as_posix()}"]')
    runner.add("ProcessPoolExecutor", 0, "")
    runner.add("['filelock', 'psutil'", 0, "[]")
    runner.add("--version", 0, "Python 3.11.3")
    
    findings = venv_manager.probe_venv(sys_dir, runner=runner)
    names = {f.name: f for f in findings}
    assert names["venv_interpreter_skew"].level == "warning"
    assert names["venv_interpreter_skew"].detail == "patch-skew"
    
    runner.mappings[-1] = ("--version", 0, "Python 3.12.2")
    findings = venv_manager.probe_venv(sys_dir, runner=runner)
    names = {f.name: f for f in findings}
    assert names["venv_interpreter_skew"].level == "warning"
    assert names["venv_interpreter_skew"].detail == "minor-skew"
    
    (python_dir / "python.exe").unlink()
    findings = venv_manager.probe_venv(sys_dir, runner=runner)
    names = {f.name: f for f in findings}
    assert names["venv_interpreter_skew"].level == "info"


def test_integrity_and_console_scripts(tmp_path):
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    runner = FakeRunner()
    
    manifest = {"venv": {"interpreter_hashes": {}}}
    hashes = venv_manager.hash_files(venv_dir, venv_manager.interpreter_file_set(venv_dir))
    manifest["venv"]["interpreter_hashes"] = hashes
    
    (venv_dir / "Scripts" / "python311.dll").write_bytes(b"changed")
    (venv_dir / "Scripts" / "native.exe").write_bytes(b"no embedded path")
    
    findings = venv_manager.probe_venv(sys_dir, runner=runner, manifest=manifest)
    names = {f.name: f for f in findings}
    
    assert names["interpreter_integrity"].level == "warning"
    assert "Scripts/python311.dll" in names["interpreter_integrity"].detail
    
    assert names["console_scripts"].level == "warning"
    assert "native.exe" not in names["console_scripts"].detail
    assert "pip.exe" in names["console_scripts"].detail


def test_console_scripts_native_exes_are_ok(tmp_path):
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    
    scripts = venv_dir / "Scripts"
    (scripts / "pip.exe").unlink()
    
    (scripts / "ruff.exe").write_bytes(b"MZ native exe")
    (scripts / "uv.exe").write_bytes(b"MZ native exe")
    
    findings = venv_manager.probe_venv(sys_dir, runner=FakeRunner())
    names = {f.name: f for f in findings}
    
    assert names["console_scripts"].level == "ok"
    assert names["console_scripts"].detail == "2 native executables ignored"


def test_launcher_embedded_path_variants(tmp_path):
    exe = tmp_path / "test.exe"
    
    exe.write_bytes(b"MZ...stub" + b"#!D:\\some\\path\\python.exe\r\n" + b"PK...")
    assert venv_manager.launcher_embedded_path(exe) == "D:\\some\\path\\python.exe"
    
    exe.write_bytes(b"MZ...stub" + b'#!"D:\\some\\path\\python.exe"\n' + b"PK...")
    assert venv_manager.launcher_embedded_path(exe) == "D:\\some\\path\\python.exe"
    
    exe.write_bytes(b"MZ...stub" + b"D:\\fallback\\python.exe\x00" + b"PK...")
    assert venv_manager.launcher_embedded_path(exe) == "D:\\fallback\\python.exe"
    
    exe.write_bytes(b"MZ...stub" + b"D:\\fallback\\pythonw.exe\x00" + b"PK...")
    assert venv_manager.launcher_embedded_path(exe) == "D:\\fallback\\pythonw.exe"
    
    exe.write_bytes(b"No path here")
    assert venv_manager.launcher_embedded_path(exe) is None


def test_scan_installed_packages(tmp_path):
    sp = tmp_path / "site-packages"
    sp.mkdir()
    
    p1 = sp / "pkg1.dist-info"
    p1.mkdir()
    (p1 / "METADATA").write_text("Name: pkg1\nVersion: 1.0\n")
    (p1 / "REQUESTED").touch()
    
    p2 = sp / "pkg2.dist-info"
    p2.mkdir()
    (p2 / "METADATA").write_text("Name: pkg2\nVersion: 2.0\n")
    (p2 / "direct_url.json").write_text('{"dir_info": {"editable": true}, "url": "file:///C:/dev/pkg2"}')
    (p2 / "INSTALLER").write_text("pip")
    
    p3 = sp / "nopkg.dist-info"
    p3.mkdir()
    
    res = venv_manager.scan_installed_packages(sp)
    
    assert len(res) == 2
    assert res[0]["name"] == "pkg1"
    assert res[0]["requested"] is True
    assert res[0]["editable"] is False
    
    assert res[1]["name"] == "pkg2"
    assert res[1]["requested"] is False
    assert res[1]["editable"] is True
    assert res[1]["editable_url"] == "file:///C:/dev/pkg2"
    assert res[1]["installer"] == "pip"


def test_sanitize_url():
    assert venv_manager.sanitize_url("https://user:token@github.com/repo") == "https://github.com/repo"
    assert venv_manager.sanitize_url("https://host/?token=abc&key=123") == "https://host/"
    assert venv_manager.sanitize_url("file:///C:/dev/pkg") == "file:///C:/dev/pkg"


def test_snapshot_write_latest(tmp_path):
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    
    sp = venv_dir / "Lib" / "site-packages"
    sp.mkdir(parents=True)
    p3 = sp / "nopkg.dist-info"
    p3.mkdir()
    
    snap = venv_manager.build_snapshot(sys_dir, now="2026-10-02T18:58:17Z", python_version="3.11.2")
    assert snap["skipped"] == ["nopkg.dist-info"]
    
    def fake_replace(src, dst):
        shutil.move(src, dst)
        
    path = venv_manager.write_snapshot(sys_dir, snap, replace=fake_replace, sleep=lambda x: None)
    
    latest = venv_manager.latest_snapshot(sys_dir)
    assert latest is not None
    assert latest["created_at"] == "2026-10-02T18:58:17Z"
    
    from core import backups
    entries = backups.scan(sys_dir).valid
    assert [e.kind for e in entries] == ["venv-freeze"]
    leftovers = [p.name for e in entries for p in e.path.rglob("*") if p.name.endswith(".tmp") or ".tmp" in p.suffixes]
    assert leftovers == []


def test_snapshot_replace_retry(tmp_path):
    sys_dir = tmp_path / "_sys"
    snap = {"created_at": "2026-10-02T18:58:17Z"}
    
    attempts = 0
    def failing_replace(src, dst):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("Access denied")
        shutil.move(src, dst)
        
    path = venv_manager.write_snapshot(sys_dir, snap, replace=failing_replace, sleep=lambda x: None)
    assert attempts >= 3          # the first replace needed 3 attempts; the registry writes marker + payload + commit
    assert path.exists() and path.name == "snapshot.json"


def test_snapshot_corrupt_fallback(tmp_path):
    sys_dir = tmp_path / "_sys"
    snapshots_dir = sys_dir / "data" / "state" / "venv-freeze"
    snapshots_dir.mkdir(parents=True)
    
    (snapshots_dir / "20261002T185900Z.json").write_text("corrupt json")
    (snapshots_dir / "20261002T185800Z.json").write_text('{"created_at": "2026-10-02T18:58:00Z"}')
    
    latest = venv_manager.latest_snapshot(sys_dir)
    assert latest is not None
    assert latest["created_at"] == "2026-10-02T18:58:00Z"


def test_run_checks(tmp_path):
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    checks = venv_manager.run_checks(sys_dir, runner=FakeRunner())
    assert isinstance(checks, list)
    assert len(checks) > 0
    assert "ok" in checks[0]


# ---- review additions (found by running probe_venv against a real install) -------------

def _imports_script(sys_dir, tmp_path):
    runner = FakeRunner()
    venv_dir = sys_dir / "env" / "venv"
    runner.add("print(json.dumps([list(sys.version_info", 0, f'[[3,11,2], "{venv_dir.as_posix()}"]')
    runner.add("ProcessPoolExecutor", 0, "")
    runner.add("find_spec", 0, "[]")
    runner.add("--version", 0, "Python 3.11.2")
    venv_manager.probe_venv(sys_dir, runner=runner)
    scripts = [c[2] for c in runner.calls if len(c) >= 3 and "find_spec" in c[2]]
    assert len(scripts) == 1
    return scripts[0]


def test_imports_probe_uses_import_names_not_distribution_names(tmp_path):
    """pywinpty is the distribution; the importable module is `winpty`. Probing the
    distribution name reports a healthy venv as missing a baseline package."""
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    script = _imports_script(sys_dir, tmp_path)
    assert "pywinpty" not in script
    assert "'winpty'" in script


def test_imports_probe_script_semantics(tmp_path):
    """Run the generated script for real: it must list exactly the baseline modules
    that this interpreter cannot import."""
    import importlib.util
    import subprocess
    import sys as _sys
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    script = _imports_script(sys_dir, tmp_path)
    out = subprocess.run([_sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    reported = set(json.loads(out.stdout))
    expected = {m for m in ("filelock", "psutil", "pydantic", "winpty") if importlib.util.find_spec(m) is None}
    assert reported == expected


def test_absent_venv_produces_no_warnings_or_errors(tmp_path):
    sys_dir = tmp_path / "_sys"
    (sys_dir / "env" / "python").mkdir(parents=True)
    findings = venv_manager.probe_venv(sys_dir, runner=FakeRunner())
    assert findings, "absent venv must still be reported"
    assert [f.name for f in findings if f.level in ("warning", "error")] == []
    assert all(f.to_check()["ok"] for f in findings)


def test_sources_do_not_carry_the_peer_reply_marker():
    root = Path(__file__).resolve().parents[2]
    for rel in ("core/venv_manager.py", "tests/unit/test_venv_manager.py"):
        assert not (root / rel).read_text(encoding="utf-8").startswith("# FILE:")


# ---- snapshot pipeline operation (venv.snapshot) ---------------------------------------------

def _ctx(sys_dir):
    return {"base_dir": sys_dir.parent, "sys_dir": sys_dir, "paths": {"state": sys_dir / "data" / "state"},
            "command": "install", "args": []}


def _tree_with_package(tmp_path, version="1.0"):
    sys_dir, venv_dir, python_dir = _setup_tree(tmp_path)
    sp = venv_dir / "Lib" / "site-packages"
    di = sp / "pkg1.dist-info"
    di.mkdir(parents=True, exist_ok=True)
    (di / "METADATA").write_text(f"Name: pkg1\nVersion: {version}\n")
    (di / "REQUESTED").touch()
    return sys_dir, venv_dir


def test_snapshot_op_writes_a_snapshot(tmp_path):
    sys_dir, venv_dir = _tree_with_package(tmp_path)
    res = venv_manager.snapshot_op(_ctx(sys_dir), now="2026-10-02T10:00:00Z")
    assert res["status"] == "success" and res["operation"] == "venv.snapshot"
    snap = venv_manager.latest_snapshot(sys_dir)
    assert [p["name"] for p in snap["packages"]] == ["pkg1"]
    assert snap["packages"][0]["requested"] is True


def test_snapshot_op_is_idempotent_when_nothing_changed(tmp_path):
    sys_dir, venv_dir = _tree_with_package(tmp_path)
    venv_manager.snapshot_op(_ctx(sys_dir), now="2026-10-02T10:00:00Z")
    res = venv_manager.snapshot_op(_ctx(sys_dir), now="2026-10-02T11:00:00Z")
    assert res["status"] == "success" and res.get("skipped") is True
    from core import backups
    assert [r.kind for r in backups.scan(sys_dir).valid] == ["venv-freeze"]


def test_snapshot_op_writes_a_new_one_when_packages_change(tmp_path):
    sys_dir, venv_dir = _tree_with_package(tmp_path, "1.0")
    venv_manager.snapshot_op(_ctx(sys_dir), now="2026-10-02T10:00:00Z")
    (venv_dir / "Lib" / "site-packages" / "pkg1.dist-info" / "METADATA").write_text("Name: pkg1\nVersion: 2.0\n")
    res = venv_manager.snapshot_op(_ctx(sys_dir), now="2026-10-02T11:00:00Z")
    assert not res.get("skipped")
    from core import backups
    assert len(backups.scan(sys_dir).valid) == 2


def test_snapshot_op_without_a_venv_is_a_quiet_noop(tmp_path):
    sys_dir = tmp_path / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    res = venv_manager.snapshot_op(_ctx(sys_dir), now="2026-10-02T10:00:00Z")
    assert res["status"] == "success" and res.get("skipped") is True
    assert not (sys_dir / "data" / "state" / "venv-freeze").exists()


def test_snapshot_op_does_not_fail_the_pipeline_when_the_lock_is_busy(tmp_path):
    from core import env_lock
    sys_dir, venv_dir = _tree_with_package(tmp_path)
    with env_lock.guard(sys_dir, "other-op"):
        res = venv_manager.snapshot_op(_ctx(sys_dir), now="2026-10-02T10:00:00Z")
    assert res["status"] == "success" and res.get("skipped") is True
    assert "busy" in res.get("detail", "").lower()
    assert venv_manager.latest_snapshot(sys_dir) is None
    # and the lock was released by its real owner, not stolen
    assert not env_lock.lock_path(sys_dir).exists()


def test_snapshot_op_takes_and_releases_the_env_lock(tmp_path, monkeypatch):
    from core import env_lock
    sys_dir, venv_dir = _tree_with_package(tmp_path)
    seen = {}
    real = env_lock.guard

    import contextlib

    @contextlib.contextmanager
    def spy(sd, op_id, **kw):
        with real(sd, op_id, **kw) as h:
            seen["held"] = env_lock.lock_path(sd).exists()
            yield h

    monkeypatch.setattr(venv_manager.env_lock, "guard", spy)
    venv_manager.snapshot_op(_ctx(sys_dir), now="2026-10-02T10:00:00Z")
    assert seen["held"] is True
    assert not env_lock.lock_path(sys_dir).exists()


def test_ok_findings_have_a_readable_detail():
    assert venv_manager.Finding("venv_spawn", "ok", "").to_check()["detail"] == "ok"
    assert venv_manager.Finding("venv_spawn", "error", "boom").to_check()["detail"] == "boom"


def test_latest_snapshot_prefers_the_registry_over_legacy_plain_files(tmp_path):
    sys_dir = tmp_path / "_sys"
    legacy = sys_dir / "data" / "state" / "venv-freeze"
    legacy.mkdir(parents=True)
    (legacy / "20261001T000000Z.json").write_text('{"created_at": "legacy"}')
    venv_manager.write_snapshot(sys_dir, {"created_at": "2026-10-02T00:00:00Z", "packages": []})
    assert venv_manager.latest_snapshot(sys_dir)["created_at"] == "2026-10-02T00:00:00Z"


def test_snapshots_are_registered_under_the_retention_policy_kind(tmp_path):
    from core import backups
    sys_dir = tmp_path / "_sys"
    venv_manager.write_snapshot(sys_dir, {"created_at": "2026-10-02T00:00:00Z", "packages": []})
    ref = backups.scan(sys_dir).valid[0]
    assert ref.kind == "venv-freeze" and ref.meta["state"] == "committed"
    assert ref.meta["min_keep"] == 5 and ref.meta["ttl_days"] == 180
