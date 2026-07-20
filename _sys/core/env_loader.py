import os
import json
import re

class EnvironmentLoader:
    def __init__(self, config_path: str, root_drive: str):
        self.config_path = config_path
        self.root_drive = root_drive.rstrip('\\/')
        if not self.root_drive:
            self.root_drive = root_drive # fallback if it was just "\"
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
            if not isinstance(self.config, dict):
                self.config = {}

        self.paths = {}
        self.env_vars = {}
        
        self._resolve_paths()
        self._resolve_env_vars()

    def _interpolate(self, value: str) -> str:
        # Resolve {ROOT_DRIVE} first
        value = value.replace("{ROOT_DRIVE}", self.root_drive)
        
        # We need to resolve {key} using self.paths
        # If the key isn't in self.paths yet, it might be resolved later, 
        # but typically paths are defined in order.
        for _ in range(5):
            matches = re.findall(r"\{([^}]+)\}", value)
            if not matches:
                break
            for match in matches:
                if match in self.paths:
                    value = value.replace(f"{{{match}}}", self.paths[match])
                
        # Normalize slashes to OS standard (Windows -> \)
        # But ensure P: becomes P:\ if it stands alone or has a trailing slash in the interpolation
        normalized = os.path.normpath(value)
        # normpath("P:") == "P:", we want to keep drive letters valid
        if len(normalized) == 2 and normalized[1] == ':':
            normalized += '\\'
        return normalized

    def _resolve_paths(self):
        raw_paths = self.config.get("paths", {})
        # iterative resolution
        for k, v in raw_paths.items():
            self.paths[k] = self._interpolate(v)
            # Re-interpolate all previously resolved paths just in case they depended on later ones? 
            # Usually top-down is fine.

    def _resolve_env_vars(self):
        raw_env_vars = self.config.get("env_vars", {})
        for k, v in raw_env_vars.items():
            self.env_vars[k] = self._interpolate(v)

    def get_paths(self) -> dict:
        return self.paths

    def get_env_vars(self) -> dict:
        return self.env_vars

    def apply_to_os(self):
        for k, v in self.env_vars.items():
            os.environ[k] = str(v)

def load_json_env(config_path: str):
    """Loads environment configuration directly from JSON and updates os.environ"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        if not isinstance(config, dict):
            config = {}

    paths = config.get("paths", {})
    env_vars = config.get("env_vars", {})
    
    # Resolve {base} recursively
    resolved_paths = {}
    
    def resolve_val(val: str):
        for _ in range(5):
            matches = re.findall(r"\{([^}]+)\}", val)
            if not matches:
                break
            for match in matches:
                if match in resolved_paths:
                    val = val.replace(f"{{{match}}}", resolved_paths[match])
        return val

    for k, v in paths.items():
        resolved_paths[k] = resolve_val(v)
        
    for k, v in env_vars.items():
        os.environ[k] = str(resolve_val(v))
        
    if "sys" in resolved_paths:
        os.environ["SYS_DIR"] = resolved_paths["sys"]
