import sys
from pathlib import Path

from _sys.core.root import find_root

# Add _sys/core to path
_core_dir = find_root(__file__) / "core"
sys.path.insert(0, str(_core_dir))

from env_loader import EnvironmentLoader

def test_environment_loader_with_null_config(tmp_path):
    """
    Test that EnvironmentLoader handles a JSON file containing only 'null'.
    """
    config_path = tmp_path / "env.json"
    config_path.write_text("null", encoding="utf-8")
    
    loader = EnvironmentLoader(str(config_path), "C:\\")
    assert loader.get_paths() == {}
    assert loader.get_env_vars() == {}
