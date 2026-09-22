import pytest
from pathlib import Path
import json
import sys

from _sys.core.root import find_root

_SYS_DIR = find_root(__file__)
if str(_SYS_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS_DIR))

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
    def mock_secure_download(url, dest_path):
        with open(dest_path, 'wb') as f:
            f.write(b'badcontent')
        return {}
    monkeypatch.setattr(provisioner, '_secure_download', mock_secure_download)
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
    
    def mock_secure_download(url, dest_path):
        shutil.copyfile(prebuilt_zip, dest_path)
        return {}
    monkeypatch.setattr(provisioner, '_secure_download', mock_secure_download)
    monkeypatch.setattr(updater.check_tool_updates, '_atomic_write_json', lambda *args: None)
    
    with pytest.raises(SystemExit) as exc:
        updater.run({'args': []})

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "falls under protected area '_sys/env'" in out


def test_updater_core_update_rejects_zip_slip_traversal(monkeypatch, capsys, tmp_path):
    """Regression test for the real zip-slip vulnerability this session
    found and fixed: _download_and_stage_core_update() must reject an
    archive member whose relative path escapes the staging directory
    (e.g. '../evil.txt') during extraction itself -- not merely flag it
    after the fact via the '_sys/env'-style protected-area walk above,
    which only ever inspects staged_dir's own contents and would never
    see a file that a zip-slip write placed OUTSIDE staged_dir in the
    first place. Before the fix, this called zipfile.ZipFile.extractall()
    directly with no path validation; now it calls provisioner._extract(),
    which raises ValueError via _validate_archive_members()."""

    import core.updater as updater
    import core.version_resolver as version_resolver
    import zipfile
    import shutil

    monkeypatch.setattr(updater, '_PORTABLE_ROOT', tmp_path)
    monkeypatch.setattr(updater, '_SYS_DIR', tmp_path / '_sys')
    (tmp_path / '_sys' / 'core').mkdir(parents=True)
    (tmp_path / '_sys' / 'core' / 'version.json').write_text('{"version": "1.0.0"}')

    malicious_zip = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious_zip, 'w') as zf:
        zf.writestr('_sys/core/version.json', '{"version": "9.9.9"}')
        # A real zip-slip entry: escapes the staging directory entirely.
        zf.writestr('../../escaped_evil.txt', 'malicious payload')

    import hashlib
    h = hashlib.sha256()
    with open(malicious_zip, 'rb') as f:
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

    def mock_secure_download(url, dest_path):
        shutil.copyfile(malicious_zip, dest_path)
        return {}
    monkeypatch.setattr(provisioner, '_secure_download', mock_secure_download)
    monkeypatch.setattr(updater.check_tool_updates, '_atomic_write_json', lambda *args: None)

    with pytest.raises(SystemExit) as exc:
        updater.run({'args': []})

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "escapes extraction root" in out
    # The critical assertion: the malicious entry must never have been
    # written to disk anywhere outside the staging directory.
    assert not (tmp_path.parent / "escaped_evil.txt").exists()
    assert not (tmp_path / "escaped_evil.txt").exists()


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
    
    def mock_secure_download(url, dest_path):
        shutil.copyfile(prebuilt_zip, dest_path)
        return {}
    monkeypatch.setattr(provisioner, '_secure_download', mock_secure_download)
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


def test_updater_core_staging_renamed_sys_dir(monkeypatch, capsys, tmp_path):
    """Core update staging correctly passes sys_dir_name in plan.json for renamed installations."""
    import core.updater as updater
    import core.version_resolver as version_resolver
    import zipfile
    import subprocess
    import shutil

    special_root = tmp_path / "custom_install"
    special_root.mkdir()
    renamed_sys = special_root / "my_runtime"

    monkeypatch.setattr(updater, '_PORTABLE_ROOT', special_root)
    monkeypatch.setattr(updater, '_SYS_DIR', renamed_sys)
    (renamed_sys / 'core').mkdir(parents=True)
    (renamed_sys / 'core' / 'version.json').write_text('{"version": "1.0.0"}')
    (renamed_sys / 'core' / 'core_update_helper.ps1').write_text('# dummy ps1')

    # Release zip has standard _sys internal naming per packaging convention
    prebuilt_zip = tmp_path / "release_v2.zip"
    with zipfile.ZipFile(prebuilt_zip, 'w') as zf:
        zf.writestr('_sys/core/version.json', '{"version": "2.0.0"}')
        zf.writestr('Engram.exe', 'dummy exe')

    import hashlib
    h = hashlib.sha256()
    with open(prebuilt_zip, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    zip_hash = h.hexdigest()

    monkeypatch.setattr(updater.check_tool_updates, 'run', lambda propose_diff=False: {
        'artifact_dir': 'mock_dir', 'updates_discovered': [], 'not_checked': [], 'could_not_check': []
    })
    monkeypatch.setattr(updater, 'check_components', lambda sys_dir: {})
    monkeypatch.setattr(version_resolver, 'resolve_latest', lambda *args, **kwargs: {
        'status': 'ok', 'latest_version': '2.0.0', 'url': 'http://fake/v2.zip',
        'checksum_algo': 'sha256', 'checksum_value': zip_hash
    })
    monkeypatch.setattr('builtins.input', lambda prompt: 'y')
    monkeypatch.setattr(updater.check_tool_updates, 'apply_proposal', lambda *args, **kwargs: (0, {'applied': True}))

    import core.provisioner as provisioner
    monkeypatch.setattr(provisioner, 'deploy', lambda ctx: {'status': 'success', 'installed': [], 'failed': [], 'deferred': []})
    monkeypatch.setattr(provisioner, '_secure_download', lambda url, dest_path: shutil.copyfile(prebuilt_zip, dest_path))
    monkeypatch.setattr(updater.check_tool_updates, '_atomic_write_json', lambda *args: None)

    popen_args = []
    class DummyPopen:
        def __init__(self, args, **kwargs):
            popen_args.append((args, kwargs))
    monkeypatch.setattr(subprocess, 'Popen', DummyPopen)

    import core.layout
    monkeypatch.setattr(core.layout, 'INSTALL_ROOT_ENTRIES', ['_sys', 'Engram.exe', 'my_runtime'])

    res = updater.run({'args': []})
    assert res['status'] == 'success'
    assert len(popen_args) == 1

    # Verify plan.json contains the custom sys_dir_name
    plan_file = renamed_sys / "data" / "temp" / "core-update" / "2.0.0" / "plan.json"
    assert plan_file.exists()
    plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
    assert plan_data["sys_dir_name"] == "my_runtime"
    assert plan_data["target_dir"] == str(special_root)


def test_updater_core_staging_renamed_sys_dir_protected_guard(monkeypatch, capsys, tmp_path):
    """Core update staging rejects archives attempting to overwrite protected paths under either _sys or renamed sys."""
    import core.updater as updater
    import core.version_resolver as version_resolver
    import zipfile
    import shutil

    special_root = tmp_path / "custom_install2"
    special_root.mkdir()
    renamed_sys = special_root / "my_runtime"

    monkeypatch.setattr(updater, '_PORTABLE_ROOT', special_root)
    monkeypatch.setattr(updater, '_SYS_DIR', renamed_sys)
    (renamed_sys / 'core').mkdir(parents=True)
    (renamed_sys / 'core' / 'version.json').write_text('{"version": "1.0.0"}')

    # Malicious archive containing a file under my_runtime/env
    malicious_zip = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious_zip, 'w') as zf:
        zf.writestr('_sys/core/version.json', '{"version": "2.0.0"}')
        zf.writestr('my_runtime/env/evil.txt', 'evil')
        zf.writestr('Engram.exe', 'dummy exe')

    import hashlib
    h = hashlib.sha256()
    with open(malicious_zip, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    zip_hash = h.hexdigest()

    monkeypatch.setattr(updater.check_tool_updates, 'run', lambda propose_diff=False: {
        'artifact_dir': 'mock_dir', 'updates_discovered': [], 'not_checked': [], 'could_not_check': []
    })
    monkeypatch.setattr(updater, 'check_components', lambda sys_dir: {})
    monkeypatch.setattr(version_resolver, 'resolve_latest', lambda *args, **kwargs: {
        'status': 'ok', 'latest_version': '2.0.0', 'url': 'http://fake/malicious.zip',
        'checksum_algo': 'sha256', 'checksum_value': zip_hash
    })
    monkeypatch.setattr('builtins.input', lambda prompt: 'y')
    monkeypatch.setattr(updater.check_tool_updates, 'apply_proposal', lambda *args, **kwargs: (0, {'applied': True}))

    import core.provisioner as provisioner
    monkeypatch.setattr(provisioner, 'deploy', lambda ctx: {'status': 'success', 'installed': [], 'failed': [], 'deferred': []})
    monkeypatch.setattr(provisioner, '_secure_download', lambda url, dest_path: shutil.copyfile(malicious_zip, dest_path))
    monkeypatch.setattr(updater.check_tool_updates, '_atomic_write_json', lambda *args: None)

    import core.layout
    monkeypatch.setattr(core.layout, 'INSTALL_ROOT_ENTRIES', ['_sys', 'Engram.exe', 'my_runtime'])

    with pytest.raises(SystemExit) as exc:
        updater.run({'args': []})

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "falls under protected area" in out


def test_updater_fallback_when_section_missing(monkeypatch, capsys):
    """When updates_discovered entries lack 'section', updater falls back to runtimes.json inspection."""
    def mock_run(propose_diff=False, only=None):
        return {
            "artifact_dir": "mock_dir",
            "updates_discovered": [
                {"tool": "ripgrep", "current_version": "1.0", "latest_version": "2.0"}  # NO section key!
            ],
            "not_checked": [],
            "could_not_check": []
        }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})

    res = updater.run({"args": ["--dry-run"]})
    # Must NOT report "Everything Engram can check is up to date."
    assert res.get("status") == "success"
    out = capsys.readouterr().out
    assert "Tools:" in out
    assert "ripgrep" in out


def test_updater_accepts_only_flag(monkeypatch):
    """updater parses --only and passes it down to check_tool_updates.run."""
    captured_only = None
    def mock_run(propose_diff=False, only=None):
        nonlocal captured_only
        captured_only = only
        return {
            "artifact_dir": "mock_dir",
            "updates_discovered": [],
            "not_checked": [],
            "could_not_check": []
        }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})

    res = updater.run({"args": ["--only", "ripgrep", "bat"]})
    assert res.get("status") == "success"
    assert captured_only == ["ripgrep", "bat"]


def test_updater_only_comma_separated_normalization(monkeypatch):
    """updater normalizes comma-separated --only arguments."""
    captured_only = None
    def mock_run(propose_diff=False, only=None):
        nonlocal captured_only
        captured_only = only
        return {"artifact_dir": "mock_dir", "updates_discovered": []}
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})

    res = updater.run({"args": ["--only", "ripgrep,bat", "fd"]})
    assert res.get("status") == "success"
    assert captured_only == ["ripgrep", "bat", "fd"]


def test_updater_only_unknown_name_exits_2(capsys):
    """An unknown component name in --only fails with exit_code 2 before any network calls."""
    res = updater.run({"args": ["--only", "completely_unknown_xyz"]})
    assert res.get("status") == "failed"
    assert res.get("exit_code") == 2
    assert "Unknown component in --only" in res.get("detail", "")
    out = capsys.readouterr().out
    assert "[Error] Unknown component: completely_unknown_xyz" in out


def test_updater_only_excludes_core_when_not_requested(monkeypatch, capsys):
    """When --only is passed and does NOT contain engram/core, core discovery is skipped."""
    mock_run = lambda propose_diff=False, only=None: {
        "artifact_dir": "mock_dir",
        "updates_discovered": [{"tool": "ripgrep", "section": "tools", "current_version": "1.0", "latest_version": "2.0"}],
    }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})

    core_resolved = False
    import core.version_resolver as vr
    def mock_resolve(tool_name, **kwargs):
        nonlocal core_resolved
        if tool_name == "Engram core":
            core_resolved = True
        return {"status": "ok", "latest_version": "99.0"}
    monkeypatch.setattr(vr, "resolve_latest", mock_resolve)

    res = updater.run({"args": ["--only", "ripgrep", "--dry-run"]})
    assert res.get("status") == "success"
    assert core_resolved is False
    out = capsys.readouterr().out
    assert "Engram core" not in out


def test_updater_only_filters_repairs_needed(monkeypatch, capsys):
    """When --only is passed, repairs_needed only keeps components that were requested."""
    mock_run = lambda propose_diff=False, only=None: {
        "artifact_dir": "mock_dir",
        "updates_discovered": [],
    }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    # Simulate missing components
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {"missing": ["tool/ripgrep", "tool/bat", "runtime/python"]})

    res = updater.run({"args": ["--only", "ripgrep", "--dry-run"]})
    assert res.get("status") == "success"
    out = capsys.readouterr().out
    assert "Repairs" in out
    assert "tool/ripgrep" in out
    assert "tool/bat" not in out
    assert "runtime/python" not in out


def test_updater_unknown_category_fallback_skipped(monkeypatch, capsys):
    """Updates with missing section and unknown name are warned and skipped."""
    mock_run = lambda propose_diff=False, only=None: {
        "artifact_dir": "mock_dir",
        "updates_discovered": [{"tool": "mysterious_mystery_tool", "current_version": "1.0", "latest_version": "2.0"}],
    }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})

    res = updater.run({"args": ["--dry-run"]})
    assert res.get("status") == "success"
    out = capsys.readouterr().out
    assert "Unknown component section" in out
    assert "mysterious_mystery_tool" in out


def test_updater_only_alias_repair_codex(monkeypatch, capsys):
    """When --only cx is passed, missing tool/codex is recognized and retained as a repair target."""
    mock_run = lambda propose_diff=False, only=None: {
        "artifact_dir": "mock_dir",
        "updates_discovered": [],
    }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {"missing": ["tool/codex", "tool/bat"]})

    res = updater.run({"args": ["--only", "cx", "--dry-run"]})
    assert res.get("status") == "success"
    out = capsys.readouterr().out
    assert "Repairs" in out
    assert "tool/codex" in out
    assert "tool/bat" not in out


def test_updater_core_update_display_renders_engram_core_not_none(tmp_path, monkeypatch, capsys):
    """Core update display rendering must show 'Engram core:' and never 'None:'."""
    mock_run = lambda propose_diff=False, only=None: {
        "artifact_dir": "mock_dir",
        "updates_discovered": [],
    }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})

    # Mock core discovery returning a newer version in a non-git installation
    from core import version_resolver
    monkeypatch.setattr("core.updater._PORTABLE_ROOT", tmp_path / "mock_install")
    monkeypatch.setattr(
        version_resolver,
        "resolve_latest",
        lambda **kwargs: {
            "status": "ok",
            "latest_version": "99.0.0",
            "url": "https://example.com/Engram.zip",
            "checksum_algo": "sha256",
            "checksum_value": "abc"
        }
    )

    res = updater.run({"args": ["--dry-run"]})
    assert res.get("status") == "success"
    out = capsys.readouterr().out
    assert "Engram core:" in out
    assert "Engram core: 3." in out or "Engram core:" in out
    assert "None:" not in out


def test_updater_invalid_section_and_non_dict_update_handling(monkeypatch, capsys):
    """Updates with explicit invalid section or non-dict items are cleanly handled without crashing."""
    mock_run = lambda propose_diff=False, only=None: {
        "artifact_dir": "mock_dir",
        "updates_discovered": [
            "not-a-dict-string",
            {"tool": "ripgrep", "section": "invalid_section_foo", "current_version": "1.0", "latest_version": "2.0"},
            {"tool": "completely_bogus", "section": "invalid_section_bar", "current_version": "1.0", "latest_version": "2.0"},
        ],
    }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda sys_dir: {})

    res = updater.run({"args": ["--dry-run"]})
    assert res.get("status") == "success"
    out = capsys.readouterr().out
    assert "Malformed update item in payload" in out
    assert "Unknown component section 'invalid_section_bar'" in out
    # ripgrep was recognized via tools fallback despite invalid section
    assert "ripgrep: 1.0 -> 2.0" in out


def test_updater_reverts_failed_and_deferred_dict_components(tmp_path, monkeypatch, capsys):
    """When deploy returns failed/deferred items as dicts, updater safely parses component names
    and reverts runtimes.json without raising TypeError (unhashable type: 'dict')."""
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir(parents=True)
    monkeypatch.setattr(updater, "_SYS_DIR", sys_dir)

    backup_runtimes = {
        "tools": {"gh": {"version": "2.96.0"}}
    }
    backup_file = tmp_path / "runtimes.json.bak"
    backup_file.write_text(json.dumps(backup_runtimes), encoding="utf-8")

    live_runtimes = {
        "tools": {"gh": {"version": "2.101.0"}, "ripgrep": {"version": "14.1.0"}}
    }
    live_file = sys_dir / "runtimes.json"
    live_file.write_text(json.dumps(live_runtimes), encoding="utf-8")

    mock_run = lambda propose_diff=False, only=None: {
        "artifact_dir": str(tmp_path / "proposal"),
        "updates_discovered": [{"tool": "gh", "section": "tools", "current_version": "2.96.0", "latest_version": "2.101.0"}],
        "not_checked": [],
    }
    monkeypatch.setattr(check_tool_updates, "run", mock_run)
    monkeypatch.setattr("core.updater.check_components", lambda s: {})

    apply_result = {
        "applied": True,
        "backup_path": str(backup_file),
    }
    monkeypatch.setattr(check_tool_updates, "apply_proposal", lambda *a, **kw: (0, apply_result))

    import core.provisioner as provisioner
    deploy_result = {
        "status": "incomplete",
        "installed": [],
        "failed": [{"component": "gh", "status": "error", "detail": "Swap to active failed"}],
        "deferred": [],
    }
    monkeypatch.setattr(provisioner, "deploy", lambda ctx: deploy_result)

    with pytest.raises(SystemExit) as exc:
        updater.run({"args": ["--yes"]})
    assert exc.value.code == 1

    # Verify runtimes.json was reverted back to 2.96.0 for gh
    reverted_runtimes = json.loads(live_file.read_text(encoding="utf-8"))
    assert reverted_runtimes["tools"]["gh"]["version"] == "2.96.0"
    assert reverted_runtimes["tools"]["ripgrep"]["version"] == "14.1.0"

    out = capsys.readouterr().out
    assert "Reverting 1 failed/deferred component(s)..." in out
    assert "Failed to revert runtimes.json: cannot use 'dict'" not in out



