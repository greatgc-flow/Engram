import json
import pytest
from pathlib import Path
import sys
import os

# Add _sys to path so we can import core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from core.config import ConfigManager

@pytest.fixture
def mock_scoping_env(tmp_path):
    sys_dir = tmp_path / "_sys"
    shared_dir = tmp_path / "_shared"
    ws_dir = tmp_path / "workspace"
    
    # Create structure
    sys_dir.mkdir()
    shared_dir.mkdir()
    (ws_dir / ".ai").mkdir(parents=True)
    
    # 1. Sys Global Config
    (sys_dir / "config.json").write_text(json.dumps({
        "theme": "dark",
        "api_endpoint": "https://api.example.com",
        "timeout": 30
    }))
    
    # 2. Shared Config
    (shared_dir / "config.json").write_text(json.dumps({
        "theme": "light",
        "team_name": "Antigravity Team"
    }))
    
    # 3. Workspace Config
    (ws_dir / ".ai" / "config.json").write_text(json.dumps({
        "api_endpoint": "https://local.dev",
        "project_specific": "true"
    }))
    
    return tmp_path, sys_dir, shared_dir, ws_dir

def test_config_scoping_precedence(mock_scoping_env, monkeypatch):
    base_dir, sys_dir, shared_dir, ws_dir = mock_scoping_env
    
    # We need to monkeypatch ConfigManager's get_sys_dir to point to our mock
    monkeypatch.setattr(ConfigManager, "get_sys_dir", classmethod(lambda cls: sys_dir))
    monkeypatch.setattr(ConfigManager, "get_base_dir", classmethod(lambda cls: base_dir))
    
    # Reset singletons
    ConfigManager._global_config = None
    ConfigManager._shared_config = None
    ConfigManager._ws_config = None
    
    # Set workspace
    ConfigManager.set_workspace(ws_dir)
    
    # Workspace should override everything
    assert ConfigManager.get("api_endpoint") == "https://local.dev"
    assert ConfigManager.get("project_specific") == "true"
    
    # Shared should override global but yield to workspace
    assert ConfigManager.get("theme") == "light"
    assert ConfigManager.get("team_name") == "Antigravity Team"
    
    # Global should act as final fallback
    assert ConfigManager.get("timeout") == 30
