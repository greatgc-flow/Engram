import os
import zipfile
import pytest
from pathlib import Path
from core.python_manager import classify_change, new_pin_text, plan_python_update, allocate_paths
from core import env_ops, provisioner

def test_classify_change():
    assert classify_change("3.14.8", "3.14.9") == "patch"
    assert classify_change("3.14.8", "3.15.0") == "minor"
    assert classify_change("3.14.8", "4.0.0") == "major"
    assert classify_change("3.14.8", "3.14.7") == "downgrade"
    assert classify_change(None, "3.14.8") == "fresh"
    assert classify_change("3.14.8", "3.14.8") == "same"

def test_new_pin_text():
    orig = "{\r\n    \"runtimes\": {\r\n        \"python\": {\r\n            \"version\": \"3.14.8\",\r\n            \"url\": \"http://old\",\r\n            \"sha256\": \"oldhash\"\r\n        },\r\n        \"nodejs\": {}\r\n    }\r\n}"
    new = new_pin_text(orig, "3.14.9", "http://new", "newhash")
    assert '"version": "3.14.9"' in new
    assert '"url": "http://new"' in new
    assert '"sha256": "newhash"' in new
    assert "nodejs" in new
    assert "\r\n" in new

def test_blocked_changes(tmp_path):
    py_dir = tmp_path / "env" / "python"
    py_dir.mkdir(parents=True)
    (py_dir / "python.exe").write_text("")
    with pytest.raises(ValueError, match="downgrade blocked"):
        plan_python_update(tmp_path, "3.14.7", url="x", installed="3.14.8")
    with pytest.raises(ValueError, match="major upgrade blocked"):
        plan_python_update(tmp_path, "4.0.0", url="x", installed="3.14.8")

def _setup_tree(tmp_path):
    env = tmp_path / "env"
    py = env / "python"
    venv = env / "venv"
    py.mkdir(parents=True)
    venv.mkdir(parents=True)
    (py / "python.exe").write_text("py")
    (venv / "env.txt").write_text("venv")
    return env, py, venv

def _make_zip(path, members):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w') as zf:
        for m, data in members.items():
            zf.writestr(m, data)

def test_cache_reuse_matching_sha(tmp_path):
    zip_path = tmp_path / "data" / "setup-files" / "python-3.14.9-embed-amd64.zip"
    _make_zip(zip_path, {"python.exe": b"exe"})
    c_sha = provisioner._hash_file(zip_path, "sha256")
    Path(str(zip_path) + ".sha256").write_text(c_sha)
    
    called = []
    def dl(u, d): called.append(u)
    
    steps = plan_python_update(tmp_path, "3.14.9", url="http://x", sha256=c_sha, downloader=dl, force=True)
    ctx = env_ops.OpContext(tmp_path, "123", "up", {}, {})
    next(s for s in steps if s.name == "download-verify").do(ctx)
    assert not called

def test_cache_sha_mismatch_redownload(tmp_path):
    zip_path = tmp_path / "data" / "setup-files" / "python-3.14.9-embed-amd64.zip"
    _make_zip(zip_path, {"python.exe": b"bad"})
    Path(str(zip_path) + ".sha256").write_text("badhash")
    
    def dl(u, d): 
        _make_zip(d, {"python.exe": b"good"})
    
    steps = plan_python_update(tmp_path, "3.14.9", url="http://x", downloader=dl, force=True)
    ctx = env_ops.OpContext(tmp_path, "123", "up", {}, {})
    next(s for s in steps if s.name == "download-verify").do(ctx)
    assert zip_path.exists()
    assert provisioner._hash_file(zip_path, "sha256") == Path(str(zip_path) + ".sha256").read_text()

def test_downloader_failure_leaves_no_zip(tmp_path):
    def dl(u, d): raise RuntimeError("dl fail")
    steps = plan_python_update(tmp_path, "3.14.9", url="http://x", downloader=dl, force=True)
    ctx = env_ops.OpContext(tmp_path, "123", "up", {}, {})
    with pytest.raises(RuntimeError):
        next(s for s in steps if s.name == "download-verify").do(ctx)
    zip_path = tmp_path / "data" / "setup-files" / "python-3.14.9-embed-amd64.zip"
    assert not zip_path.exists()
    assert not Path(str(zip_path) + ".sha256").exists()

def test_offline_verified_cache_works(tmp_path):
    zip_path = tmp_path / "data" / "setup-files" / "python-3.14.9-embed-amd64.zip"
    _make_zip(zip_path, {"python.exe": b"exe"})
    c_sha = provisioner._hash_file(zip_path, "sha256")
    Path(str(zip_path) + ".sha256").write_text(c_sha)
    
    steps = plan_python_update(tmp_path, "3.14.9", url="http://x", offline=True, force=True)
    ctx = env_ops.OpContext(tmp_path, "123", "up", {}, {})
    next(s for s in steps if s.name == "download-verify").do(ctx)

def test_offline_without_cache_raises_before_mutation(tmp_path):
    _setup_tree(tmp_path)
    
    def hash_tree():
        return {str(p.relative_to(tmp_path)): provisioner._hash_file(p, "sha256") for p in tmp_path.rglob("*") if p.is_file()}
        
    before = hash_tree()
    with pytest.raises(RuntimeError, match="Offline mode"):
        steps = plan_python_update(tmp_path, "3.14.9", url="http://x", offline=True, force=True)
        ctx = env_ops.OpContext(tmp_path, "123", "up", {}, {})
        next(s for s in steps if s.name == "download-verify").do(ctx)
    assert hash_tree() == before

def test_zip_slip_rejected(tmp_path):
    zip_path = tmp_path / "data" / "setup-files" / "python-3.14.9-embed-amd64.zip"
    _make_zip(zip_path, {"../evil.txt": b"evil"})
    Path(str(zip_path) + ".sha256").write_text(provisioner._hash_file(zip_path, "sha256"))
    
    steps = plan_python_update(tmp_path, "3.14.9", url="x", force=True)
    ctx = env_ops.OpContext(tmp_path, "123", "up", {}, {})
    with pytest.raises(RuntimeError, match="zip-slip attempt"):
        next(s for s in steps if s.name == "stage").do(ctx)

def test_pth_edit(tmp_path):
    zip_path = tmp_path / "data" / "setup-files" / "python-3.14.9-embed-amd64.zip"
    _make_zip(zip_path, {"python311._pth": b"#import site\nother"})
    Path(str(zip_path) + ".sha256").write_text(provisioner._hash_file(zip_path, "sha256"))
    
    steps = plan_python_update(tmp_path, "3.14.9", url="x", force=True, runner=lambda a, t: (0, "3.14.9"))
    ctx = env_ops.OpContext(tmp_path, "123", "up", {"runner_dir": tmp_path / "runner"}, {})
    next(s for s in steps if s.name == "stage").do(ctx)
    assert (tmp_path / "env" / "python.new" / "python311._pth").read_text() == "import site\nother"

def test_stage_version_probe_mismatch_rolls_back(tmp_path):
    zip_path = tmp_path / "data" / "setup-files" / "python-3.14.9-embed-amd64.zip"
    _make_zip(zip_path, {"python.exe": b""})
    Path(str(zip_path) + ".sha256").write_text(provisioner._hash_file(zip_path, "sha256"))
    
    steps = plan_python_update(tmp_path, "3.14.9", url="x", force=True, runner=lambda a, t: (0, "3.14.8"))
    ctx = env_ops.OpContext(tmp_path, "123", "up", {"runner_dir": tmp_path / "runner"}, {})
    with pytest.raises(RuntimeError, match="mismatch"):
        next(s for s in steps if s.name == "stage").do(ctx)

def test_low_disk_raises(tmp_path):
    _setup_tree(tmp_path)
    steps = plan_python_update(tmp_path, "3.14.9", url="x", free_space=lambda p: 0, force=True)
    with pytest.raises(RuntimeError, match="Low disk space"):
        next(s for s in steps if s.name == "preflight").do(env_ops.OpContext(tmp_path, "123", "up", {}, {}))

def test_holders_listed(tmp_path):
    _setup_tree(tmp_path)
    steps = plan_python_update(tmp_path, "3.14.9", url="x", holders=lambda p: [{"pid": 123}], force=True)
    with pytest.raises(RuntimeError, match="Holders active:.*123"):
        next(s for s in steps if s.name == "preflight").do(env_ops.OpContext(tmp_path, "123", "up", {}, {}))

def test_rename_retries_success(tmp_path):
    attempts = [0]
    def failing_rename(src, dst):
        attempts[0] += 1
        if attempts[0] <= 3:
            raise PermissionError("in use")
        
    _setup_tree(tmp_path)
    steps = plan_python_update(tmp_path, "3.14.9", url="x", rename=failing_rename, sleep=lambda t: None, force=True)
    (tmp_path / "env" / "python.new").mkdir()
    next(s for s in steps if s.name == "swap").do(env_ops.OpContext(tmp_path, "123", "up", {}, {}))
    assert attempts[0] == 4

def test_rename_retries_failure(tmp_path):
    attempts = [0]
    def failing_rename(src, dst):
        attempts[0] += 1
        raise PermissionError("in use")
        
    _setup_tree(tmp_path)
    steps = plan_python_update(tmp_path, "3.14.9", url="x", rename=failing_rename, sleep=lambda t: None, force=True)
    (tmp_path / "env" / "python.new").mkdir()
    with pytest.raises(PermissionError):
        next(s for s in steps if s.name == "swap").do(env_ops.OpContext(tmp_path, "123", "up", {}, {}))
    assert attempts[0] == 5

def test_first_quarantine_failure_byte_identical(tmp_path):
    _setup_tree(tmp_path)
    def hash_non_backups():
        res = {}
        for p in tmp_path.rglob("*"):
            if p.is_file() and "data\\backups" not in str(p.relative_to(tmp_path)) and "data/backups" not in str(p.relative_to(tmp_path)):
                res[str(p.relative_to(tmp_path))] = provisioner._hash_file(p, "sha256")
        return res
    before = hash_non_backups()
    
    def failing_rename(src, dst):
        raise PermissionError("no")
        
    steps = plan_python_update(tmp_path, "3.14.9", url="x", rename=failing_rename, sleep=lambda t: None, force=True)
    with pytest.raises(PermissionError):
        next(s for s in steps if s.name == "quarantine-python").do(env_ops.OpContext(tmp_path, "123", "up", {}, {}))
    
    assert hash_non_backups() == before
    backups_dir = tmp_path / "data" / "backups"
    if backups_dir.exists():
        for p in backups_dir.rglob("*"):
            if p.is_file():
                assert p.name == "BACKUP.json"
        for p in backups_dir.rglob("payload"):
            assert not p.exists() or not any(p.iterdir())

def test_venv_policy(tmp_path):
    _setup_tree(tmp_path)
    steps_keep = plan_python_update(tmp_path, "3.14.9", url="x", venv_policy="keep", force=True)
    assert "quarantine-venv" not in [s.name for s in steps_keep]
    steps_rebuild = plan_python_update(tmp_path, "3.14.9", url="x", venv_policy="rebuild", force=True)
    assert "quarantine-venv" in [s.name for s in steps_rebuild]

def test_allocate_paths(tmp_path):
    paths = allocate_paths(tmp_path, "op123", lambda: "2026-10-02T12:00:00Z")
    assert set(paths.keys()) == {"python_backup", "venv_backup", "freeze_backup", "venv_failed_backup", "venv_interp_backup"}

@pytest.mark.parametrize("fail_step", ["stage", "quarantine-python", "swap", "verify"])
def test_plan_execution_rollback(tmp_path, fail_step, monkeypatch):
    from core import venv_manager
    monkeypatch.setattr(venv_manager, "probe_venv", lambda s, runner: [])
    monkeypatch.setattr(venv_manager, "build_snapshot", lambda s, now, python_version: {})
    monkeypatch.setattr(venv_manager, "write_snapshot", lambda s, snap, replace, sleep: None)
    
    env, py, venv = _setup_tree(tmp_path)
    
    zip_path = tmp_path / "data" / "setup-files" / "python-3.14.9-embed-amd64.zip"
    _make_zip(zip_path, {"python.exe": b"newexe"})
    Path(str(zip_path) + ".sha256").write_text(provisioner._hash_file(zip_path, "sha256"))
    
    def hash_tree(d): return {str(p.relative_to(d)): provisioner._hash_file(p, "sha256") for p in d.rglob("*") if p.is_file()}
    py_before = hash_tree(py)
    venv_before = hash_tree(venv)
    
    def dl(u, d): pass
    def run(a, t): 
        if "--version" in a: return 0, "3.14.9"
        return 0, ""
        
    steps = plan_python_update(tmp_path, "3.14.9", url="x", downloader=dl, runner=run, force=True, sleep=lambda x: None)
    
    for s in steps:
        if s.name == fail_step:
            orig_do = s.do
            def failing_do(ctx, orig=orig_do):
                orig(ctx)
                raise RuntimeError("Injected failure")
            s.do = failing_do
            break
            
    paths = allocate_paths(tmp_path, "op123", lambda: "now")
    
    res = env_ops.execute(tmp_path, "update", steps, paths=paths, op_id="op123")
    assert res["status"] == "failed"
    
    assert py.exists() and hash_tree(py) == py_before
    assert venv.exists() and hash_tree(venv) == venv_before
    
    if fail_step in ["quarantine-python", "swap", "verify"]:
        assert any((tmp_path / "data" / "backups").rglob("*"))

def test_plan_execution_success(tmp_path, monkeypatch):
    from core import venv_manager
    monkeypatch.setattr(venv_manager, "probe_venv", lambda s, runner: [])
    monkeypatch.setattr(venv_manager, "build_snapshot", lambda s, now, python_version: {})
    monkeypatch.setattr(venv_manager, "write_snapshot", lambda s, snap, replace, sleep: None)
    
    env, py, venv = _setup_tree(tmp_path)
    
    zip_path = tmp_path / "data" / "setup-files" / "python-3.14.9-embed-amd64.zip"
    _make_zip(zip_path, {"python.exe": b"newexe", "python3._pth": b"#import site"})
    Path(str(zip_path) + ".sha256").write_text(provisioner._hash_file(zip_path, "sha256"))
    
    def run(a, t): 
        if "--version" in a: return 0, "3.14.9"
        return 0, ""
        
    steps = plan_python_update(tmp_path, "3.14.9", url="x", runner=run, force=True, sleep=lambda x: None)
    paths = allocate_paths(tmp_path, "op123", lambda: "now")
    
    res = env_ops.execute(tmp_path, "update", steps, paths=paths, op_id="op123")
    assert res["status"] == "success"
    assert (py / "python.exe").read_text() == "newexe"
    assert (py / "python3._pth").read_text() == "import site"
