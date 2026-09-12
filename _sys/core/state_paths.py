import os
from pathlib import Path

def update_dir(sys_dir: Path) -> Path:
    return sys_dir / "data" / "state" / "update"

def discovery_cache(sys_dir: Path) -> Path:
    return update_dir(sys_dir) / "tool_discovery_cache.json"

def deferred_retries(sys_dir: Path) -> Path:
    return update_dir(sys_dir) / "tool_deferred_retries.json"

def proposals_dir(sys_dir: Path) -> Path:
    return update_dir(sys_dir) / "proposals"

def receipts_dir(sys_dir: Path) -> Path:
    return update_dir(sys_dir) / "receipts"

def launcher_log_dir(sys_dir: Path) -> Path:
    return sys_dir / "data" / "logs" / "launcher"
