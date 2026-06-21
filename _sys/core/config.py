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
    _global_config: Dict[str, Any] = None
    _shared_config: Dict[str, Any] = None
    _ws_config: Dict[str, Any] = None
    _ws_path: Path = None

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
    def set_workspace(cls, ws_path: Path):
        """Sets the current active workspace and loads its config if present."""
        cls._ws_path = ws_path
        cls._ws_config = None
        cls._lazy_load_ws()

    @classmethod
    def _lazy_load_global(cls):
        if cls._global_config is None:
            path = cls.get_sys_dir() / "config.json"
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cls._global_config = json.load(f)
                except Exception as e:
                    print(f"[Warning] Failed to load global config.json: {e}")
                    cls._global_config = {}
            else:
                cls._global_config = {}

    @classmethod
    def _lazy_load_shared(cls):
        if cls._shared_config is None:
            path = cls.get_base_dir() / "_shared" / "config.json"
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cls._shared_config = json.load(f)
                except Exception as e:
                    print(f"[Warning] Failed to load shared config.json: {e}")
                    cls._shared_config = {}
            else:
                cls._shared_config = {}

    @classmethod
    def _lazy_load_ws(cls):
        if cls._ws_config is None and cls._ws_path:
            # Look for config in workspace/.ai/config.json
            path = cls._ws_path / ".ai" / "config.json"
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cls._ws_config = json.load(f)
                except Exception:
                    cls._ws_config = {}
            else:
                cls._ws_config = {}

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get config value with layering: Workspace -> Shared -> Global -> Default."""
        cls._lazy_load_ws()
        if cls._ws_config and key in cls._ws_config:
            return cls._ws_config[key]
            
        cls._lazy_load_shared()
        if cls._shared_config and key in cls._shared_config:
            return cls._shared_config[key]
        
        cls._lazy_load_global()
        return cls._global_config.get(key, default)

    @classmethod
    def set(cls, key: str, value: Any, scope: str = "global"):
        """Set config value in specified scope ('global' or 'workspace')."""
        if scope == "workspace" and cls._ws_path:
            cls._lazy_load_ws()
            cls._ws_config[key] = value
            cls._save_ws()
        else:
            cls._lazy_load_global()
            cls._global_config[key] = value
            cls._save_global()

    @classmethod
    def _save_global(cls):
        path = cls.get_sys_dir() / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cls._global_config, f, indent=4)

    @classmethod
    def _save_ws(cls):
        if not cls._ws_path: return
        path = cls._ws_path / ".ai" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cls._ws_config, f, indent=4)

    @classmethod
    def get_runtimes_config(cls) -> Dict[str, Any]:
        """Reads _sys/runtimes.json."""
        rt_path = cls.get_sys_dir() / "runtimes.json"
        if rt_path.exists():
            try:
                with open(rt_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("runtimes", {})
            except Exception: pass
        return {}

    @classmethod
    def get_env_config(cls) -> Dict[str, Any]:
        """Reads _sys/env.json."""
        env_path = cls.get_sys_dir() / "env.json"
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception: pass
        return {}

    @classmethod
    def get_peers_config(cls) -> Dict[str, Any]:
        """Reads _sys/ai/peers.json."""
        peers_path = cls.get_sys_dir() / "ai" / "peers.json"
        if peers_path.exists():
            try:
                with open(peers_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("peers", {})
            except Exception: pass
        return {}

    @classmethod
    def get_orchestration_config(cls) -> Dict[str, Any]:
        """Reads _sys/ai/orchestration.json."""
        path = cls.get_sys_dir() / "ai" / "orchestration.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception: pass
        return {}

# Provide a ready-to-use instance/functions for ease of use
config = ConfigManager()
