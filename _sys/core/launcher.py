"""
launcher.py - Environment setup and process spawning for Portable Dev Environment.
PATH and env vars driven by env.json. No hardcoding.
Physical root is source of truth; SUBST drive is an optional alias.
"""
import os
import sys
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _resolve_path_entry(base: str, sub: str, sys_dir: Path) -> Path:
    bases = {
        "sys":   sys_dir,
        "env":   sys_dir / "env",
        "tools": sys_dir / "tools",
    }
    return bases.get(base, sys_dir) / sub


def _map_subst_drive(base_dir: Path, drive: str) -> None:
    """Ensure SUBST drive is mapped; remap if occupied by a different path."""
    drive_root = f"{drive}:\\"
    if os.path.exists(drive_root):
        if not (Path(drive_root) / "_sys" / "core" / "launcher.py").exists():
            subprocess.run(["subst", f"{drive}:", "/D"], capture_output=True)
            res = subprocess.run(["subst", f"{drive}:", str(base_dir)], capture_output=True)
            if res.returncode != 0:
                raise RuntimeError(f"Drive {drive}: occupied and cannot be remapped. Run register.bat.")
    else:
        res = subprocess.run(["subst", f"{drive}:", str(base_dir)], capture_output=True)
        if res.returncode != 0:
            raise RuntimeError(f"subst {drive}: failed")
        for _ in range(10):
            if os.path.exists(drive_root):
                time.sleep(0.2)
                break
            time.sleep(1)


def build_env(base_dir: Path, sys_dir: Path) -> dict:
    """Build the sandboxed environment dict from env.json."""
    env_cfg  = _load_json(sys_dir / "env.json")
    env      = os.environ.copy()

    env["BASE_DIR"] = str(base_dir)
    env["SYS_DIR"]  = str(sys_dir)

    sandbox_temp = sys_dir / "data" / "temp"
    sandbox_temp.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = env["TMP"] = str(sandbox_temp)

    # Static env vars
    for k, v in env_cfg.get("env_vars", {}).items():
        env[k] = str(v)

    # Tool env vars (path-based)
    for k, spec in env_cfg.get("tool_env_vars", {}).items():
        env[k] = str(_resolve_path_entry(spec["base"], spec["sub"], sys_dir))

    # PATH from env.json path_entries
    entries = [
        _resolve_path_entry(e["base"], e["sub"], sys_dir)
        for e in env_cfg.get("path_entries", [])
    ]
    env["PATH"] = ";".join(str(p) for p in entries if p.exists()) + ";" + env.get("PATH", "")

    # Git config
    gitconfig = sys_dir / "git-config" / ".gitconfig"
    if gitconfig.exists():
        env["GIT_CONFIG_GLOBAL"] = str(gitconfig)

    # Venv activation marker
    venv_dir = sys_dir / "env" / "venv"
    if (venv_dir / "Scripts").exists():
        env["VIRTUAL_ENV"] = str(venv_dir)
        env.pop("PYTHONHOME", None)

    return env


def _relocate(base_dir: Path, sys_dir: Path) -> None:
    """Track current base directory."""
    last_file = sys_dir / "data" / "last_base_dir.txt"
    current   = str(base_dir)
    try:
        last_file.parent.mkdir(parents=True, exist_ok=True)
        last_file.write_text(current, encoding="utf-8")
    except Exception:
        pass


def main(ctx: dict) -> None:
    """Launch the sandbox: apply SUBST, build env, open VS Code."""
    base_dir_phys = ctx["base_dir"]
    sys_dir_phys  = ctx["sys_dir"]
    args          = ctx["args"]

    _relocate(base_dir_phys, sys_dir_phys)

    # Read saved SUBST drive (new: state.json, fallback: legacy config.json)
    state_file = ctx["paths"]["state"] / "register.state.json"
    drive      = None
    if state_file.exists():
        try:
            saved = json.loads(state_file.read_text(encoding="utf-8"))
            drive = saved.get("subst_drive")
        except Exception:
            pass
    if drive is None:
        legacy = sys_dir_phys / "config.json"
        if legacy.exists():
            try:
                drive = json.loads(legacy.read_text(encoding="utf-8")).get("SUBST_DRIVE_LETTER")
            except Exception:
                pass

    base_dir = base_dir_phys
    sys_dir  = sys_dir_phys
    if drive:
        _map_subst_drive(base_dir_phys, drive)
        base_dir = Path(f"{drive}:\\")
        sys_dir  = base_dir / "_sys"

    # Log setup
    log_dir = base_dir / "_archive" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"start_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    def log(msg: str) -> None:
        print(msg)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    log(f"Started : {datetime.now()}")
    log(f"BASE    : {base_dir}")

    env = build_env(base_dir, sys_dir)

    # Determine target
    raw_target = args[0] if args else ""
    if raw_target:
        t_path = Path(raw_target).resolve()
        if drive and str(base_dir_phys) in str(t_path):
            target = str(t_path)
            raw_target = target.replace(str(base_dir_phys), str(base_dir))
        else:
            raw_target = str(t_path)

    if not raw_target:
        target_dir = base_dir
        run_mode   = "DEV"
    elif Path(raw_target).is_dir():
        target_dir = Path(raw_target)
        run_mode   = "DEV"
    elif Path(raw_target).is_file():
        target_dir = Path(raw_target).parent
        run_mode   = "APP"
    else:
        raise ValueError(f"Path not found: {raw_target}")

    os.chdir(target_dir)

    if run_mode == "DEV":
        vscode_exe = sys_dir / "env" / "vscode" / "Code.exe"
        if vscode_exe.exists():
            log(f"[OK] VS Code: {target_dir}")
            subprocess.Popen([str(vscode_exe), "."], env=env)
        else:
            log(f"[Warning] VS Code not found: {vscode_exe}")

        if not raw_target:
            print(f"[Sandbox] Ready at {base_dir}")
            subprocess.run(["cmd", "/k"], env=env)

    elif run_mode == "APP":
        target_file = Path(raw_target)
        log(f"[OK] Running: {target_file}")
        ext = target_file.suffix.lower()
        if ext == ".py":
            python_exe = sys_dir / "env" / "venv" / "Scripts" / "python.exe"
            if not python_exe.exists():
                python_exe = sys_dir / "env" / "python" / "python.exe"
            subprocess.run([str(python_exe), str(target_file)], env=env)
        elif ext in (".bat", ".cmd"):
            subprocess.run(["cmd", "/c", str(target_file)], env=env)
        else:
            os.startfile(str(target_file))

    log("[Done]")
