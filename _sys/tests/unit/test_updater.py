import pytest
from pathlib import Path
import json

from core import updater
from checks import check_tool_updates

def test_updater_not_checked_in_discover_payload(tmp_path, monkeypatch):
    """not_checked appears in discover payload for the provider-less runtimes."""
    # Create a mock runtimes.json
    mock_runtimes = {
        "runtimes": {
            "node": {
                "version": "18.0.0"
            },
            "python": {
                "version": "3.10",
                "discovery_provider": "manual"
            },
            "tool1": {
                "version": "1.0",
                "discovery_provider": "github_release",
                "discovery_id": "owner/repo"
            }
        }
    }
    runtimes_file = tmp_path / "runtimes.json"
    runtimes_file.write_text(json.dumps(mock_runtimes))
    
    monkeypatch.setattr(check_tool_updates, "RUNTIMES_PATH", runtimes_file)
    monkeypatch.setattr(check_tool_updates, "DISCOVERY_CACHE_PATH", tmp_path / "cache.json")
    
    # Mock version_resolver.resolve_latest to avoid network
    def mock_resolve(*args, **kwargs):
        return {"status": "ok", "latest_version": "1.1"}
    
    import core.version_resolver as version_resolver
    monkeypatch.setattr(version_resolver, "resolve_latest", mock_resolve)
    
    payload, runtimes, proposed, catalog, proposed_catalog = check_tool_updates.discover_updates()
    not_checked = payload.get("not_checked", [])
    
    # Should contain node (no provider) and python (manual)
    components = {x["component"] for x in not_checked}
    assert "node" in components
    assert "python" in components
    assert "tool1" not in components

def test_updater_run_zero_updates(monkeypatch, capsys):
    """updater run() with zero updates returns success + prints up-to-date."""
    def mock_run(propose_diff=False):
        return {
            "artifact_dir": "mock_dir",
            "updates_discovered": [],
            "not_checked": []
        }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})
    
    res = updater.run({"args": []})
    assert res == {"status": "success", "detail": "No updates discovered"}
    out = capsys.readouterr().out
    assert "up to date" in out

def test_updater_run_dry_run(monkeypatch, capsys):
    """run() --dry-run shows proposal but calls apply_proposal ZERO times."""
    def mock_run(propose_diff=False):
        return {
            "artifact_dir": "mock_dir",
            "updates_discovered": [{"tool": "A", "section": "tools", "current_version": "1", "latest_version": "2"}],
            "not_checked": []
        }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})
    
    apply_called = False
    def mock_apply(*args, **kwargs):
        nonlocal apply_called
        apply_called = True
        return 0, {}
    monkeypatch.setattr(check_tool_updates, "apply_proposal", mock_apply)
    
    res = updater.run({"args": ["--dry-run"]})
    assert res == {"status": "success", "detail": "Dry run complete"}
    assert not apply_called
    out = capsys.readouterr().out
    assert "Dry run complete" in out

def test_updater_run_yes_calls_apply(monkeypatch):
    """run() with --yes calls apply_proposal(artifact_dir_exactly_from_payload, yes=True) and maps exit 0->success."""
    def mock_run(propose_diff=False):
        return {
            "artifact_dir": "mock_dir_123",
            "updates_discovered": [{"tool": "A", "section": "tools", "current_version": "1", "latest_version": "2"}],
            "not_checked": []
        }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})
    
    apply_args = None
    def mock_apply(artifact_dir, yes):
        nonlocal apply_args
        apply_args = (artifact_dir, yes)
        return 0, {"applied": True}
    monkeypatch.setattr(check_tool_updates, "apply_proposal", mock_apply)
    
    # We also need to mock provisioner.deploy for this test so it doesn't fail
    import core.provisioner as provisioner
    monkeypatch.setattr(provisioner, "deploy", lambda ctx: {"status": "success"})
    
    res = updater.run({"args": ["--yes"]})
    assert res == {"status": "success", "apply_result": {"applied": True}}
    assert apply_args == ("mock_dir_123", True)

def test_updater_run_deploy_failure(monkeypatch):
    """deploy error -> status 'incomplete'."""
    def mock_run(propose_diff=False):
        return {
            "artifact_dir": "mock_dir",
            "updates_discovered": [{"tool": "A", "section": "tools", "current_version": "1", "latest_version": "2"}],
            "not_checked": []
        }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})
    
    def mock_apply(*args, **kwargs):
        return 0, {"applied": True, "backup_path": "some_backup_path"}
    monkeypatch.setattr(check_tool_updates, "apply_proposal", mock_apply)

    import core.provisioner as provisioner
    monkeypatch.setattr(provisioner, "deploy", lambda ctx: {"status": "error", "detail": "simulated deploy failure"})
    
    res = updater.run({"args": ["--yes"]})
    assert res == {"status": "incomplete", "detail": "applied but deploy failed"}

def test_updater_run_declined_prompt(monkeypatch):
    """a declined prompt (monkeypatch input to 'n') does NOT call apply_proposal and returns success."""
    def mock_run(propose_diff=False):
        return {
            "artifact_dir": "mock_dir",
            "updates_discovered": [{"tool": "A", "section": "tools", "current_version": "1", "latest_version": "2"}],
            "not_checked": []
        }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})
    
    # Mock input
    monkeypatch.setattr('builtins.input', lambda prompt: 'n')
    
    apply_called = False
    def mock_apply(*args, **kwargs):
        nonlocal apply_called
        apply_called = True
        return 0, {}
    monkeypatch.setattr(check_tool_updates, "apply_proposal", mock_apply)
    
    with pytest.raises(SystemExit) as exc:
        updater.run({"args": []})
    assert exc.value.code == 3
    assert not apply_called

def test_updater_core_channel_git(monkeypatch, capsys, tmp_path):
    import core.updater as updater
    monkeypatch.setattr(updater, '_PORTABLE_ROOT', tmp_path)
    (tmp_path / '.git').mkdir()
    def mock_run(propose_diff=False):
        return {'artifact_dir': 'mock_dir', 'updates_discovered': [], 'not_checked': [], 'could_not_check': []}
    monkeypatch.setattr(updater.check_tool_updates, 'run', mock_run)
    monkeypatch.setattr(updater, 'check_components', lambda sys_dir: {})
    updater.run({'args': []})
    out = capsys.readouterr().out
    assert 'Engram core (git checkout' in out

def test_updater_core_discovery_error(monkeypatch, capsys, tmp_path):
    import core.updater as updater
    import core.version_resolver as version_resolver
    monkeypatch.setattr(updater, '_PORTABLE_ROOT', tmp_path)
    def mock_run(propose_diff=False):
        return {'artifact_dir': 'mock_dir', 'updates_discovered': [], 'not_checked': [], 'could_not_check': []}
    monkeypatch.setattr(updater.check_tool_updates, 'run', mock_run)
    monkeypatch.setattr(updater, 'check_components', lambda sys_dir: {})
    def mock_resolve(*args, **kwargs):
        return {'status': 'error', 'error_type': 'missing_digest', 'detail': 'release has no digest; refusing'}
    monkeypatch.setattr(version_resolver, 'resolve_latest', mock_resolve)
    updater.run({'args': []})
    out = capsys.readouterr().out
    assert 'Engram core (missing_digest: release has no digest; refusing)' in out

def test_updater_core_staging_hash_mismatch(monkeypatch, capsys, tmp_path):
    import core.updater as updater
    import core.version_resolver as version_resolver
    monkeypatch.setattr(updater, '_PORTABLE_ROOT', tmp_path)
    monkeypatch.setattr(updater, '_SYS_DIR', tmp_path / '_sys')
    (tmp_path / '_sys' / 'core').mkdir(parents=True)
    (tmp_path / '_sys' / 'core' / 'version.json').write_text('{"version": "1.0.0"}')
    def mock_run(propose_diff=False):
        return {'artifact_dir': 'mock_dir', 'updates_discovered': [], 'not_checked': [], 'could_not_check': []}
    monkeypatch.setattr(updater.check_tool_updates, 'run', mock_run)
    monkeypatch.setattr(updater, 'check_components', lambda sys_dir: {})
    def mock_resolve(*args, **kwargs):
        return {'status': 'ok', 'latest_version': '9.9.9', 'url': 'http://fake', 'checksum_algo': 'sha256', 'checksum_value': 'expectedhash'}
    monkeypatch.setattr(version_resolver, 'resolve_latest', mock_resolve)
    monkeypatch.setattr('builtins.input', lambda prompt: 'y')
    monkeypatch.setattr(updater.check_tool_updates, 'apply_proposal', lambda *args, **kwargs: (0, {'applied': True, 'backup_path': 'fake'}))
    import core.provisioner as provisioner
    monkeypatch.setattr(provisioner, 'deploy', lambda ctx: {'status': 'success', 'installed': [], 'failed': [], 'deferred': []})
    def mock_urlretrieve(url, path):
        with open(path, 'wb') as f:
            f.write(b'badcontent')
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlretrieve', mock_urlretrieve)
    monkeypatch.setattr(updater.check_tool_updates, '_atomic_write_json', lambda *args: None)
    with pytest.raises(SystemExit) as exc:
        updater.run({'args': []})
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert 'Checksum mismatch' in out
def test_updater_core_staged_path_escape(monkeypatch, capsys, tmp_path):
    import core.updater as updater
    import core.version_resolver as version_resolver
    import zipfile
    import shutil
    
    monkeypatch.setattr(updater, '_PORTABLE_ROOT', tmp_path)
    monkeypatch.setattr(updater, '_SYS_DIR', tmp_path / '_sys')
    (tmp_path / '_sys' / 'core').mkdir(parents=True)
    (tmp_path / '_sys' / 'core' / 'version.json').write_text('{"version": "1.0.0"}')
    
    prebuilt_zip = tmp_path / "prebuilt.zip"
    with zipfile.ZipFile(prebuilt_zip, 'w') as zf:
        zf.writestr('_sys/core/version.json', '{"version": "9.9.9"}')
        zf.writestr('README.md', 'dummy')
        zf.writestr('_sys/env/evil.txt', 'malicious')
        
    import hashlib
    h = hashlib.sha256()
    with open(prebuilt_zip, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    zip_hash = h.hexdigest()
    
    def mock_run(propose_diff=False):
        return {'artifact_dir': 'mock_dir', 'updates_discovered': [], 'not_checked': [], 'could_not_check': []}
    monkeypatch.setattr(updater.check_tool_updates, 'run', mock_run)
    monkeypatch.setattr(updater, 'check_components', lambda sys_dir: {})
    
    def mock_resolve(*args, **kwargs):
        return {'status': 'ok', 'latest_version': '9.9.9', 'url': 'http://fake', 'checksum_algo': 'sha256', 'checksum_value': zip_hash}
    monkeypatch.setattr(version_resolver, 'resolve_latest', mock_resolve)
    
    monkeypatch.setattr('builtins.input', lambda prompt: 'y')
    monkeypatch.setattr(updater.check_tool_updates, 'apply_proposal', lambda *args, **kwargs: (0, {'applied': True, 'backup_path': 'fake'}))
    import core.provisioner as provisioner
    monkeypatch.setattr(provisioner, 'deploy', lambda ctx: {'status': 'success', 'installed': [], 'failed': [], 'deferred': []})
    
    def mock_urlretrieve(url, path):
        shutil.copyfile(prebuilt_zip, path)
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlretrieve', mock_urlretrieve)
    monkeypatch.setattr(updater.check_tool_updates, '_atomic_write_json', lambda *args: None)
    
    with pytest.raises(SystemExit) as exc:
        updater.run({'args': []})
    
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "falls under protected area '_sys/env'" in out

def test_updater_core_staging_a_and_b_bang_root(monkeypatch, capsys, tmp_path):
    import core.updater as updater
    import core.version_resolver as version_resolver
    import zipfile
    import subprocess
    import shutil
    
    special_root = tmp_path / "a&b!"
    special_root.mkdir()
    
    monkeypatch.setattr(updater, '_PORTABLE_ROOT', special_root)
    monkeypatch.setattr(updater, '_SYS_DIR', special_root / '_sys')
    (special_root / '_sys' / 'core').mkdir(parents=True)
    (special_root / '_sys' / 'core' / 'version.json').write_text('{"version": "1.0.0"}')
    (special_root / '_sys' / 'core' / 'core_update_helper.ps1').write_text('# dummy ps1')
    
    prebuilt_zip = tmp_path / "prebuilt2.zip"
    with zipfile.ZipFile(prebuilt_zip, 'w') as zf:
        zf.writestr('_sys/core/version.json', '{"version": "9.9.9"}')
        zf.writestr('Engram.exe', 'dummy exe')
        
    import hashlib
    h = hashlib.sha256()
    with open(prebuilt_zip, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    zip_hash = h.hexdigest()

    def mock_run(propose_diff=False):
        return {'artifact_dir': 'mock_dir', 'updates_discovered': [], 'not_checked': [], 'could_not_check': []}
    monkeypatch.setattr(updater.check_tool_updates, 'run', mock_run)
    monkeypatch.setattr(updater, 'check_components', lambda sys_dir: {})
    
    def mock_resolve(*args, **kwargs):
        return {'status': 'ok', 'latest_version': '9.9.9', 'url': 'http://fake', 'checksum_algo': 'sha256', 'checksum_value': zip_hash}
    monkeypatch.setattr(version_resolver, 'resolve_latest', mock_resolve)
    
    monkeypatch.setattr('builtins.input', lambda prompt: 'y')
    monkeypatch.setattr(updater.check_tool_updates, 'apply_proposal', lambda *args, **kwargs: (0, {'applied': True, 'backup_path': 'fake'}))
    
    import core.provisioner as provisioner
    monkeypatch.setattr(provisioner, 'deploy', lambda ctx: {'status': 'success', 'installed': [], 'failed': [], 'deferred': []})
    
    def mock_urlretrieve(url, path):
        shutil.copyfile(prebuilt_zip, path)
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlretrieve', mock_urlretrieve)
    monkeypatch.setattr(updater.check_tool_updates, '_atomic_write_json', lambda *args: None)
    
    popen_called_with = []
    class DummyPopen:
        def __init__(self, args, **kwargs):
            popen_called_with.append(args)
    monkeypatch.setattr(subprocess, 'Popen', DummyPopen)
    
    import core.layout
    monkeypatch.setattr(core.layout, 'INSTALL_ROOT_ENTRIES', ['_sys', 'Engram.exe'])
    
    res = updater.run({'args': []})
    
    assert res['status'] == 'success'
    assert len(popen_called_with) == 1
    args = popen_called_with[0]
    assert "powershell.exe" in args
    assert "-File" in args
def test_updater_core_channel_winget(monkeypatch, capsys, tmp_path):
    import core.updater as updater
    import os
    
    local_appdata = tmp_path / "LocalAppData"
    winget_packages = local_appdata / "Microsoft" / "WinGet" / "Packages"
    engram_root = winget_packages / "greatgc-flow.Engram_1.0.0"
    engram_root.mkdir(parents=True)
    
    monkeypatch.setattr(updater, '_PORTABLE_ROOT', engram_root)
    monkeypatch.setattr(os, 'environ', {'LOCALAPPDATA': str(local_appdata)})
    
    def mock_run(propose_diff=False):
        return {'artifact_dir': 'mock_dir', 'updates_discovered': [], 'not_checked': [], 'could_not_check': []}
    monkeypatch.setattr(updater.check_tool_updates, 'run', mock_run)
    monkeypatch.setattr(updater, 'check_components', lambda sys_dir: {})
    
    updater.run({'args': []})
    out = capsys.readouterr().out
    assert 'Engram core (managed by WinGet — run winget upgrade greatgc-flow.Engram)' in out
