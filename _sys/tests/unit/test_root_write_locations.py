import os
import sys
import shutil
import subprocess
from pathlib import Path

import pytest
from _sys.core.root import find_root

repo_root = find_root(__file__).parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
sys_dir = repo_root / "_sys"
if str(sys_dir) not in sys.path:
    sys.path.insert(0, str(sys_dir))

pytest.importorskip("tools.winget.build_package")
from tools.winget.build_package import collect_package_files

from core.layout import INSTALL_ROOT_ENTRIES

def test_dynamic_root_write_locations(tmp_path, monkeypatch):
    """
    Build a temp portable root from collect_package_files().
    Stub network, provisioning, process spawns, winreg, and LOCALAPPDATA.
    Run the command sequence and assert no legacy state literals or unexpected root items.
    """
    # 1. Build temp portable root
    portable_root = tmp_path / "portable_root"
    portable_root.mkdir()
    
    files = collect_package_files(repo_root)
    for src_path, arcname in files:
        dest = portable_root / arcname
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest)
        
    # Set LOCALAPPDATA
    local_appdata = tmp_path / "LocalAppData"
    local_appdata.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    
    # Create required runtime mock files
    (portable_root / "_sys" / "env" / "python").mkdir(parents=True, exist_ok=True)
    (portable_root / "_sys" / "env" / "python" / "python.exe").touch()
    
    import json
    (portable_root / "_sys" / "runtimes.json").write_text(json.dumps({"runtimes": {}}))
    (portable_root / "_sys" / "tool-catalog.v1.json").write_text(json.dumps({"tools": {}}))
    
    # 2. Stub network and system dependencies
    
    # urllib.request for updater payload
    import urllib.request
    import hashlib
    
    prebuilt_zip = tmp_path / "dummy_update.zip"
    import zipfile
    with zipfile.ZipFile(prebuilt_zip, "w") as zf:
        zf.writestr("_sys/core/version.json", '{"version": "9.9.9"}')
        zf.writestr("Engram.exe", "dummy")
        
    h = hashlib.sha256()
    with open(prebuilt_zip, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    valid_zip_hash = h.hexdigest().upper() # or lower?

    resolve_calls = 0
    def mock_resolve(*args, **kwargs):
        nonlocal resolve_calls
        resolve_calls += 1
        if resolve_calls == 1:
            return {"status": "ok", "latest_version": "9.9.9", "url": "http://fake.zip", "checksum_algo": "sha256", "checksum_value": valid_zip_hash}
        elif resolve_calls == 2:
            return {"status": "discovery_unavailable", "error_type": "rate_limited"}
        else:
            return {"status": "error", "error_type": "network_error"}
    
    import core.version_resolver as vr
    monkeypatch.setattr(vr, "resolve_latest", mock_resolve)
    
    # provisioner.deploy (one installed, one deferred)
    def mock_deploy(ctx):
        return {"status": "success", "installed": ["dummy_tool"], "failed": [], "deferred": ["deferred_tool"]}
    
    import core.provisioner as provisioner
    monkeypatch.setattr(provisioner, "deploy", mock_deploy)
    
    # subprocess spawns
    class MockPopen:
        def __init__(self, *args, **kwargs):
            pass
        def communicate(self):
            return b"", b""
        def wait(self):
            return 0
        @property
        def returncode(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", MockPopen)
    def mock_run_sub(*args, **kwargs):
        stdout = "Python 3.10.0" if kwargs.get("text") or kwargs.get("encoding") else b"Python 3.10.0"
        stderr = "" if kwargs.get("text") or kwargs.get("encoding") else b""
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr=stderr)
    monkeypatch.setattr(subprocess, "run", mock_run_sub)
    def mock_check_output(*args, **kwargs):
        return "" if kwargs.get("text") or kwargs.get("encoding") else b""
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    if hasattr(os, "startfile"):
        monkeypatch.setattr(os, "startfile", lambda *args: None)
        
    # winreg
    try:
        import winreg
        monkeypatch.setattr(winreg, "OpenKey", lambda *args, **kwargs: None)
        monkeypatch.setattr(winreg, "CreateKey", lambda *args, **kwargs: None)
        monkeypatch.setattr(winreg, "SetValueEx", lambda *args, **kwargs: None)
        monkeypatch.setattr(winreg, "DeleteKey", lambda *args, **kwargs: None)
        monkeypatch.setattr(winreg, "CloseKey", lambda *args, **kwargs: None)
    except ImportError:
        pass
        
    import core.registrar as registrar
    monkeypatch.setattr(registrar, "_hkcu_key_state", lambda *args: "absent")
        
    def mock_urlretrieve(url, filename, *args, **kwargs):
        shutil.copyfile(prebuilt_zip, filename)
    monkeypatch.setattr(urllib.request, "urlretrieve", mock_urlretrieve)
    
    # builtins.input
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    
    # sys.exit (uninstaller calls this)
    class ExitException(Exception):
        pass
    def mock_exit(code=0):
        pass # just return so pipeline finishes normally
    monkeypatch.setattr(sys, "exit", mock_exit)

    # 3. Setup dispatcher
    import core.dispatcher as dispatcher
    import core.updater as updater
    sys_dir = portable_root / "_sys"
    monkeypatch.setattr(dispatcher, "base_dir", portable_root)
    monkeypatch.setattr(dispatcher, "sys_dir", sys_dir)
    monkeypatch.setattr(updater, "_PORTABLE_ROOT", portable_root)
    monkeypatch.setattr(updater, "_SYS_DIR", sys_dir)
    
    # Run the sequence
    dispatcher.run_pipeline("update", ["--check"])
    dispatcher.run_pipeline("update", ["--yes"])
    dispatcher.run_pipeline("start", []) # open
    dispatcher.run_pipeline("doctor", ["--json"])
    dispatcher.run_pipeline("menu-enable", [])
    dispatcher.run_pipeline("menu-status", [])
    dispatcher.run_pipeline("menu-disable", [])
    dispatcher.run_pipeline("menu-clean", [])
    dispatcher.run_pipeline("tidy", [])
    dispatcher.run_pipeline("tidy", ["--apply", "--deep"])
    dispatcher.run_pipeline("uninstall", []) # planner
    
    # 4. Asserts
    # Constant lives in layout.py as INSTALL_ROOT_ENTRIES
    
    # Assert 1: set(os.listdir(root)) <= INSTALL_ROOT_ENTRIES
    actual_root_entries = set(os.listdir(portable_root))
    # We should allow INSTALL_ROOT_ENTRIES case-insensitively, but listdir returns exact case.
    # The requirement says `set(os.listdir(root)) <= {"Engram.exe", "engram.cmd", "README.md", "LICENSE", "_sys", "workspace", ".engram"}`
    # Which IS INSTALL_ROOT_ENTRIES.
    assert actual_root_entries <= INSTALL_ROOT_ENTRIES, f"Unexpected root entries: {actual_root_entries - INSTALL_ROOT_ENTRIES}"
    
    # Assert 2: No path component `.ai` or `_archive` exists anywhere under `root` (os.walk)
    bad_components = {".ai", "_archive"}
    for dirpath, dirnames, filenames in os.walk(portable_root):
        path_parts = Path(dirpath).relative_to(portable_root).parts
        assert not bad_components.intersection(path_parts), f"Found legacy path component in {dirpath}"
