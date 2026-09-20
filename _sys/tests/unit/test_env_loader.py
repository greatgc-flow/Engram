import os
import json
import pytest
from pathlib import Path
import sys

from _sys.core.root import find_root

# Add _sys to path so we can import core
sys.path.insert(0, str(find_root(__file__)))

try:
    from core.env_loader import EnvironmentLoader
except ImportError:
    # For initial TDD run
    EnvironmentLoader = None

@pytest.fixture
def mock_env_json(tmp_path):
    config_path = tmp_path / "environment.json"
    config_data = {
        "paths": {
            "base": "{ROOT_DRIVE}",
            "sys": "{base}/_sys",
            "shared": "{base}/_shared",
            "workspace_template": "{sys}/templates/workspace-base"
        },
        "env_vars": {
            "PYTHONUTF8": "1",
            "NPM_CONFIG_PREFIX": "{sys}/env/nodejs/npm-global"
        }
    }
    config_path.write_text(json.dumps(config_data))
    return config_path

def test_environment_loader_resolves_paths(mock_env_json):
    if EnvironmentLoader is None:
        pytest.fail("EnvironmentLoader not implemented yet")
        
    loader = EnvironmentLoader(config_path=str(mock_env_json), root_drive="P:\\")
    
    paths = loader.get_paths()
    
    assert paths["base"] == "P:\\"
    assert paths["sys"] == "P:\\_sys"
    assert paths["shared"] == "P:\\_shared"
    assert paths["workspace_template"] == "P:\\_sys\\templates\\workspace-base"

def test_environment_loader_resolves_env_vars(mock_env_json):
    if EnvironmentLoader is None:
        pytest.fail("EnvironmentLoader not implemented yet")
        
    loader = EnvironmentLoader(config_path=str(mock_env_json), root_drive="P:\\")
    
    env_vars = loader.get_env_vars()
    
    assert env_vars["PYTHONUTF8"] == "1"
    assert env_vars["NPM_CONFIG_PREFIX"] == "P:\\_sys\\env\\nodejs\\npm-global"

def test_environment_loader_applies_to_os(mock_env_json):
    if EnvironmentLoader is None:
        pytest.fail("EnvironmentLoader not implemented yet")
        
    loader = EnvironmentLoader(config_path=str(mock_env_json), root_drive="P:\\")
    loader.apply_to_os()
    
    assert os.environ.get("PYTHONUTF8") == "1"
    assert os.environ.get("NPM_CONFIG_PREFIX") == "P:\\_sys\\env\\nodejs\\npm-global"

def test_real_environment_json():
    real_config_path = find_root(__file__) / "config" / "environment.json"
    if not real_config_path.exists():
        pytest.skip("environment.json not found")
        
    loader = EnvironmentLoader(config_path=str(real_config_path), root_drive="P:\\")
    paths = loader.get_paths()
    
    assert "P:\\_sys" in paths["sys"]
    assert "P:\\_sys\\env\\nodejs" in paths["nodejs"]
    assert "P:\\_shared" in paths["shared"]
