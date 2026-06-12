import os
import sys
import json
import subprocess
import importlib
from pathlib import Path

# Add _sys to path
sys_dir = Path(__file__).parent.parent.resolve()
if str(sys_dir) not in sys.path:
    sys.path.insert(0, str(sys_dir))

def run_command(cmd_name, extra_args):
    dispatch_path = sys_dir / "dispatch.json"
    if not dispatch_path.exists():
        print(f"[Error] dispatch.json not found at {dispatch_path}")
        sys.exit(1)

    with open(dispatch_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    cmd_cfg = config.get("commands", {}).get(cmd_name)
    if not cmd_cfg:
        print(f"[Error] Unknown command: {cmd_name}")
        sys.exit(1)

    module_name = cmd_cfg.get("module")
    default_args = cmd_cfg.get("args", [])

    # Combine default args from config with extra args from CLI
    all_args = default_args + extra_args

    # Mock sys.argv for the target module
    # sys.argv[0] should be the module/script name
    sys.argv = [module_name] + all_args

    try:
        # Dynamically import and run the module
        # Note: We expect the modules to have a __main__ block or a main() function
        # For simplicity, we'll use runpy or just import it if it handles its own execution
        import runpy
        runpy.run_module(module_name, run_name="__main__")
    except Exception as e:
        print(f"[Error] Failed to execute {module_name}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: dispatcher.py <command> [args...]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]
    run_command(cmd, args)
