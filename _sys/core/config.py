import os
import sys
import json
from pathlib import Path
from typing import Any, Dict

# Centralized Constants
DEFAULT_NODEJS_VERSION = "22.22.3"
DEFAULT_PYTHON_VERSION = "3.13.4"
DEFAULT_GIT_VERSION = "2.49.0"

class ConfigManager:
    _instance = None
    _config: Dict[str, Any] = None
    _config_path: Path = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_sys_dir(cls) -> Path:
        return Path(__file__).parent.parent.resolve()

    @classmethod
    def get_base_dir(cls) -> Path:
        return cls.get_sys_dir().parent

    @classmethod
    def _lazy_load(cls):
        if cls._config is None:
            if cls._config_path is None:
                cls._config_path = cls.get_sys_dir() / "config.json"
            if cls._config_path.exists():
                try:
                    with open(cls._config_path, "r", encoding="utf-8") as f:
                        cls._config = json.load(f)
                except Exception as e:
                    print(f"[Warning] Failed to load config.json: {e}")
                    cls._config = {}
            else:
                cls._config = {}

    @classmethod
    def get_peers_config(cls) -> Dict[str, Any]:
        """Reads _sys/ai/peers.json and returns the peers dictionary."""
        peers_path = cls.get_sys_dir() / "ai" / "peers.json"
        if peers_path.exists():
            try:
                with open(peers_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("peers", {})
            except Exception as e:
                print(f"[Warning] Failed to load peers.json: {e}")
        return {}

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        cls._lazy_load()
        return cls._config.get(key, default)

    @classmethod
    def set(cls, key: str, value: Any):
        cls._lazy_load()
        cls._config[key] = value
        cls.save()

    @classmethod
    def save(cls):
        if cls._config_path is None:
            cls._config_path = cls.get_sys_dir() / "config.json"
        
        # Ensure parent exists
        cls._config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(cls._config_path, "w", encoding="utf-8") as f:
                json.dump(cls._config, f, indent=4)
        except Exception as e:
            print(f"[Error] Failed to save config.json: {e}")

# Provide a ready-to-use instance/functions for ease of use
config = ConfigManager()
