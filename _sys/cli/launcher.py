"""
launcher.py - Portable Dev Environment Launcher (Python Refactored)
Handles drive mapping, environment variable injection, and process execution.
Replaces start.bat.
"""
import os
import sys
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path

# Add sys path to allow importing core modules
sys_dir = Path(__file__).parent.parent.resolve()
if str(sys_dir) not in sys.path:
    sys.path.insert(0, str(sys_dir))

from core.config import config

def log(msg: str, log_file: Path):
    print(msg)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

def map_subst_drive(base_dir: Path, target_drive: str):
    """Maps the target drive using SUBST if not already mapped."""
    drive_root = f"{target_drive}:\\"
    
    if os.path.exists(drive_root):
        # Verify it's ours
        if not (Path(drive_root) / "_sys" / "cli" / "launcher.py").exists():
            print(f"[Warning] Drive {target_drive}: is mapped to a different path. Remapping...")
            subprocess.run(["subst", f"{target_drive}:", "/D"], capture_output=True)
            res = subprocess.run(["subst", f"{target_drive}:", str(base_dir)], capture_output=True)
            if res.returncode != 0:
                raise RuntimeError(f"Drive {target_drive}: is occupied and cannot be remapped.\nRun 'register' to assign a new drive.")
    else:
        res = subprocess.run(["subst", f"{target_drive}:", str(base_dir)], capture_output=True)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to subst drive {target_drive}: to {base_dir}")
        
        print(f"[Info] Waiting for drive {target_drive}: to stabilize...")
        for _ in range(10):
            if os.path.exists(drive_root):
                time.sleep(0.2)
                print("  [Ready]")
                break
            time.sleep(1)
            print(".", end="", flush=True)

def setup_environment(base_dir: Path, sys_dir: Path) -> dict:
    """Prepares the environment variables for the sandbox."""
    env_dir = sys_dir / "env"
    tools_dir = sys_dir / "tools"
    data_dir = sys_dir / "data"
    claude_dir = sys_dir / "claude"

    # Deep copy current env
    env = os.environ.copy()

    # Paths
    env["BASE_DIR"] = str(base_dir)
    env["SYS_DIR"] = str(sys_dir)
    
    sandbox_temp = data_dir / "temp"
    sandbox_temp.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(sandbox_temp)
    env["TMP"] = str(sandbox_temp)

    # Tool Configs
    env["NPM_CONFIG_PREFIX"] = str(env_dir / "nodejs" / "npm-global")
    env["NPM_CONFIG_CACHE"] = str(env_dir / "nodejs" / "npm-cache")
    env["PIP_CACHE_DIR"] = str(env_dir / "python" / "pip-cache")
    env["PYTHONUSERBASE"] = str(env_dir / "python" / "userbase")
    env["CLAUDE_CONFIG_DIR"] = str(claude_dir / "config")
    env["PYTHONUTF8"] = "1"

    # Apply user overrides from config.json
    overrides = config.get("env_overrides", {})
    for k, v in overrides.items():
        env[k] = str(v)

    # Build PATH
    path_entries = [
        env_dir / "nodejs" / "npm-global",
        env_dir / "venv" / "Scripts",
        env_dir / "python",
        env_dir / "python" / "Scripts",
        env_dir / "nodejs",
        env_dir / "ffmpeg" / "bin",
        env_dir / "pwsh",
        sys_dir / "cli",
        sys_dir / "hooks",
        sys_dir / "checks",
        tools_dir / "ripgrep",
        tools_dir / "fd",
        tools_dir / "jq",
        tools_dir / "bat",
        tools_dir / "delta",
        tools_dir / "fzf",
        tools_dir / "oh-my-posh",
        tools_dir / "sqlite",
        tools_dir / "gh",
        env_dir / "git" / "cmd",
        env_dir / "git" / "usr" / "bin"
    ]

    valid_paths = [str(p) for p in path_entries if p.exists()]
    env["PATH"] = ";".join(valid_paths) + ";" + env.get("PATH", "")

    # Git Global Config
    gitconfig = sys_dir / "git-config" / ".gitconfig"
    if gitconfig.exists():
        env["GIT_CONFIG_GLOBAL"] = str(gitconfig)

    # VENV variables
    venv_dir = env_dir / "venv"
    if (venv_dir / "Scripts").exists():
        env["VIRTUAL_ENV"] = str(venv_dir)
        env.pop("PYTHONHOME", None)

    return env

def main():
    try:
        # Base paths
        sys_dir_phys = config.get_sys_dir()
        base_dir_phys = config.get_base_dir()

        # Target Analysis
        target = sys.argv[1] if len(sys.argv) > 1 else ""

        # Load config
        subst_drive = config.get("SUBST_DRIVE_LETTER")
        no_desktop = config.get("NO_DESKTOP", False)
        
        base_dir = base_dir_phys
        sys_dir = sys_dir_phys

        if subst_drive:
            map_subst_drive(base_dir_phys, subst_drive)
            base_dir = Path(f"{subst_drive}:\\")
            sys_dir = base_dir / "_sys"

            # Translate target to SUBST path if necessary
            if target and str(base_dir_phys) in target:
                target = target.replace(str(base_dir_phys), str(base_dir))

        # Prepare Logs
        log_dir = base_dir / "_archive" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"start_{dt_str}.log"

        log(f"Started : {datetime.now()}", log_file)
        log(f"BASE    : {base_dir}", log_file)

        # Environment
        env = setup_environment(base_dir, sys_dir)

        # Determine Execution Target
        if not target:
            target_dir = base_dir
            run_mode = "DEV"
        elif Path(target).is_dir():
            target_dir = Path(target)
            run_mode = "DEV"
        elif Path(target).is_file():
            target_file = Path(target)
            target_dir = target_file.parent
            run_mode = "APP"
        else:
            raise ValueError(f"Path not found: {target}")

        os.chdir(target_dir)

        if run_mode == "DEV":
            vscode_exe = sys_dir / "env" / "vscode" / "Code.exe"
            if vscode_exe.exists():
                log(f"[OK] Launching VS Code: {target_dir}", log_file)
                subprocess.Popen([str(vscode_exe), "."], env=env)
            else:
                log(f"[Warning] VS Code not found at {vscode_exe}", log_file)

            if not no_desktop:
                claude_exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Claude" / "Claude.exe"
                if claude_exe.exists():
                    subprocess.Popen([str(claude_exe)], env=env)
            
            if not target:
                print(f"[Sandbox] Environment ready at {base_dir}")
                # Drop into interactive shell
                subprocess.run(["cmd", "/k"], env=env)

        elif run_mode == "APP":
            log(f"[OK] Running: {target_file}", log_file)
            ext = target_file.suffix.lower()
            
            if ext == ".py":
                python_exe = sys_dir / "env" / "venv" / "Scripts" / "python.exe"
                if not python_exe.exists():
                    python_exe = sys_dir / "env" / "python" / "python.exe"
                subprocess.run([str(python_exe), str(target_file)], env=env)
            elif ext == ".bat" or ext == ".cmd":
                subprocess.run(["cmd", "/c", str(target_file)], env=env)
            else:
                # Let Windows handle it
                os.startfile(str(target_file))

        log("[Done] Finished", log_file)

    except Exception as e:
        print(f"\n[FATAL ERROR] An unexpected error occurred:")
        print(f"  {e}\n")
        print("--- Stack Trace ---")
        traceback.print_exc()
        print("-------------------")
        print("\nPress any key to exit...")
        os.system("pause >nul")
        sys.exit(1)

if __name__ == "__main__":
    main()
