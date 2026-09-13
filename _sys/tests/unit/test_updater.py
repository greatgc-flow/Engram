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
