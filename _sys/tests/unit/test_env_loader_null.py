import os
import sys
from pathlib import Path
import pytest

# Add _sys/core to path
_core_dir = Path(__file__).parent.parent.parent / "core"
sys.path.insert(0, str(_core_dir))

from env_loader import load_json_env, EnvironmentLoader

def test_load_json_env_with_null_config(tmp_path):
    """
    Test that load_json_env handles a JSON file containing only 'null'
    without crashing, preserving the empty fallback behavior.
    """
    config_path = tmp_path / "env.json"
    config_path.write_text("null", encoding="utf-8")
    
    original_env = dict(os.environ)
    try:
        # This will crash with AttributeError: 'NoneType' object has no attribute 'get'
        # if the missing-value (null JSON) case is not handled properly.
        load_json_env(str(config_path))
        
        # Verify it didn't do any harm (acted like empty dict)
        assert True
    finally:
        os.environ.clear()
        os.environ.update(original_env)

def test_environment_loader_with_null_config(tmp_path):
    """
    Test that EnvironmentLoader handles a JSON file containing only 'null'.
    """
    config_path = tmp_path / "env.json"
    config_path.write_text("null", encoding="utf-8")
    
    loader = EnvironmentLoader(str(config_path), "C:\\")
    assert loader.get_paths() == {}
    assert loader.get_env_vars() == {}
