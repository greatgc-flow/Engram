import pytest
import os
import json
from pathlib import Path
import sys

# Ensure core is reachable
sys_dir = Path(__file__).parent.parent.parent.resolve()
if str(sys_dir) not in sys.path:
    sys.path.insert(0, str(sys_dir))

from core.config import ConfigManager

def test_config_singleton():
    c1 = ConfigManager()
    c2 = ConfigManager()
    assert c1 is c2

def test_config_lazy_load_and_save(tmp_path):
    # Override config paths for testing
    global_path = tmp_path / "global_config.json"
    ws_path = tmp_path / "workspace"
    ws_path.mkdir()
    ws_config_path = ws_path / ".ai" / "config.json"
    ws_config_path.parent.mkdir()
    
    # Mock ConfigManager paths and reset
    ConfigManager._global_config = None
    ConfigManager._ws_config = None
    ConfigManager._ws_path = None

    # Force the manager to use our temp paths by overriding the save methods or just letting it work with defaults
    # Actually, ConfigManager uses get_sys_dir() which is hardcoded. 
    # For testing, we should probably allow overriding these paths in the class.
    
    # Let's temporarily monkeypatch the internal save/load methods or paths if possible.
    # Since ConfigManager is a singleton class with classmethods, we can override the paths.
    
    original_global_save = ConfigManager._save_global
    original_ws_save = ConfigManager._save_ws
    
    def mock_save_global():
        global_path.parent.mkdir(parents=True, exist_ok=True)
        with open(global_path, "w", encoding="utf-8") as f:
            json.dump(ConfigManager._global_config, f, indent=4)
            
    def mock_save_ws():
        ws_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ws_config_path, "w", encoding="utf-8") as f:
            json.dump(ConfigManager._ws_config, f, indent=4)

    ConfigManager._save_global = mock_save_global
    ConfigManager._save_ws = mock_save_ws
    
    try:
        # Test Global Set/Get
        ConfigManager.set("GLOBAL_KEY", "GLOBAL_VAL")
        assert global_path.exists()
        assert ConfigManager.get("GLOBAL_KEY") == "GLOBAL_VAL"
        
        # Test Workspace Set/Get
        ConfigManager.set_workspace(ws_path)
        ConfigManager.set("WS_KEY", "WS_VAL", scope="workspace")
        assert ws_config_path.exists()
        assert ConfigManager.get("WS_KEY") == "WS_VAL"
        
        # Test Layering (WS wins)
        ConfigManager.set("COMMON_KEY", "GLOBAL_WIN", scope="global")
        ConfigManager.set("COMMON_KEY", "WS_WIN", scope="workspace")
        assert ConfigManager.get("COMMON_KEY") == "WS_WIN"
        
    finally:
        ConfigManager._save_global = original_global_save
        ConfigManager._save_ws = original_ws_save
        ConfigManager._global_config = None
        ConfigManager._ws_config = None
        ConfigManager._ws_path = None
