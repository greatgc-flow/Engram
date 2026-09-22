"""
launcher.py - Environment setup and process spawning for Portable Dev Environment.
PATH and env vars driven by env.json. No hardcoding.
Physical root is source of truth.
"""
import os
import re
import sys
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from core import provisioner


def _load_json(path: Path) -> dict:
    return provisioner.load_json_with_fallback(path)


# The only 2 settings _sys/local.config.bat.template documents. Kept as an
# explicit allowlist (not "whatever keys the file happens to set") so a
# local.config.bat can't accidentally override something it was never meant
# to -- these are the only 2 keys build_env()/main() will ever look for.
_LOCAL_CONFIG_OVERRIDE_KEYS = frozenset({"BASE_DIR_WORKSPACE", "NPM_CONFIG_PREFIX"})

_LOCAL_CONFIG_SET_RE = re.compile(
    r'^\s*set\s+"([A-Za-z_][A-Za-z0-9_]*)=(.*)"\s*$', re.IGNORECASE
)


def _load_local_config_overrides(sys_dir: Path) -> dict[str, str]:
    """Parse `local.config.bat`'s `set "KEY=VALUE"` lines as declarative data.

    Deliberately does NOT execute the file (no `cmd /c call`) -- that would
    pollute this process's real environment with whatever a user's
    local.config.bat happens to set, and couldn't distinguish "this key was
    just set by local.config.bat" from "this key coincidentally already
    existed in the parent shell's environment" (a real regression risk: a
    user's own npm install on a different drive could silently shadow the
    portable one). Reading `set "KEY=VALUE"` lines as plain text instead is
    unambiguous and has no such collision risk. `::`-prefixed lines and any
    key outside `_LOCAL_CONFIG_OVERRIDE_KEYS` are ignored. `%VAR%`-style
    references in the value (e.g. `%APPDATA%\\npm`, per the template's own
    example) are expanded against the real process environment.
    """
    config_path = sys_dir / "local.config.bat"
    if not config_path.exists():
        return {}

    overrides: dict[str, str] = {}
    try:
        text = config_path.read_text(encoding="utf-8")
    except Exception:
        return {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("::") or stripped.startswith("@"):
            continue
        m = _LOCAL_CONFIG_SET_RE.match(stripped)
        if not m:
            continue
        key, value = m.group(1).upper(), m.group(2)
        if key not in _LOCAL_CONFIG_OVERRIDE_KEYS:
            continue
        overrides[key] = os.path.expandvars(value)

    return overrides


def _resolve_path_entry(base: str, sub: str, sys_dir: Path, base_dir: Path | None = None) -> Path:
    # "engram" (dotdir consolidation, ratified 2026-09-09, item 6): the
    # consolidated personal/durable-settings root for Engram-managed AI
    # CLIs, at the portable root -- a sibling of _sys/, not under it, so
    # `base_dir` (not `sys_dir`) anchors it. Falls back to sys_dir's parent
    # if base_dir isn't supplied, so existing callers that only pass
    # sys_dir don't break.
    bases = {
        "sys":    sys_dir,
        "env":    sys_dir / "env",
        "tools":  sys_dir / "tools",
        "engram": (base_dir if base_dir is not None else sys_dir.parent) / ".engram",
    }
    return bases.get(base, sys_dir) / sub


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

    # Tool env vars (path-based). A local.config.bat override for a given
    # key wins over the computed portable-path default.
    overrides = _load_local_config_overrides(sys_dir)
    for k, spec in env_cfg.get("tool_env_vars", {}).items():
        if k in overrides:
            env[k] = overrides[k]
        else:
            env[k] = str(_resolve_path_entry(spec["base"], spec["sub"], sys_dir, base_dir))

    # .engram/ subdirs (dotdir consolidation, item 6): created idempotently
    # so a tool redirected there via the env vars above always finds a real
    # directory on first launch, without needing a separate migration step.
    # Derived directly from tool_env_vars (not a separately-hardcoded list)
    # so a new "base": "engram" entry can't silently go uncreated.
    for spec in env_cfg.get("tool_env_vars", {}).values():
        if spec.get("base") == "engram":
            _resolve_path_entry(spec["base"], spec["sub"], sys_dir, base_dir).mkdir(
                parents=True, exist_ok=True
            )

    # PATH from env.json path_entries
    entries = [
        _resolve_path_entry(e["base"], e["sub"], sys_dir, base_dir)
        for e in env_cfg.get("path_entries", [])
    ]
    env["PATH"] = ";".join(str(p) for p in entries if p.exists()) + ";" + env.get("PATH", "")

    # Git config -- retargeted to .engram/git/.gitconfig (item 6). The
    # .exists() guard is deliberately kept: retargeting must not fabricate
    # GIT_CONFIG_GLOBAL pointing at a file nothing has created yet.
    gitconfig = base_dir / ".engram" / "git" / ".gitconfig"
    if gitconfig.exists():
        env["GIT_CONFIG_GLOBAL"] = str(gitconfig)

    # Venv activation marker
    venv_dir = sys_dir / "env" / "venv"
    if (venv_dir / "Scripts").exists():
        env["VIRTUAL_ENV"] = str(venv_dir)
        env.pop("PYTHONHOME", None)

    return env


def _resolve_default_target(base_dir: Path, sys_dir: Path) -> Path:
    """Pick the launch target when no explicit path argument is given.

    Priority: a local.config.bat BASE_DIR_WORKSPACE override; else
    base_dir/workspace if that folder exists; else the portable root
    itself (original behavior, unchanged for anyone using neither
    convention).
    """
    workspace_override = _load_local_config_overrides(sys_dir).get("BASE_DIR_WORKSPACE")
    if workspace_override:
        return Path(workspace_override)
    default_workspace = base_dir / "workspace"
    if default_workspace.is_dir():
        return default_workspace
    return base_dir


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
    """Launch the sandbox: build env, open VS Code."""
    base_dir = ctx["base_dir"]
    sys_dir  = ctx["sys_dir"]
    args     = ctx["args"]

    _relocate(base_dir, sys_dir)

    # Log setup
    import state_paths
    log_dir = state_paths.launcher_log_dir(sys_dir)
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
        caller_cwd = os.environ.get("ENGRAM_CALLER_CWD")
        if caller_cwd:
            raw_target = str((Path(caller_cwd) / raw_target).resolve())
        else:
            raw_target = str(Path(raw_target).resolve())

    if not raw_target:
        target_dir = _resolve_default_target(base_dir, sys_dir)
        run_mode = "DEV"
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
        vscode_exe = provisioner.vscode_exe(sys_dir)
        if vscode_exe.exists():
            (vscode_exe.parent / "data").mkdir(parents=True, exist_ok=True)
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
            python_exe = provisioner.venv_python_exe(sys_dir)
            if not python_exe.exists():
                python_exe = provisioner.portable_python_exe(sys_dir)
            subprocess.run([str(python_exe), str(target_file)], env=env)
        elif ext in (".bat", ".cmd"):
            # Use .\name with cwd= to avoid cmd.exe interpreting "&" in
            # absolute paths as a statement separator (D11 ampersand fix).
            bat_dir = str(target_file.parent)
            bat_name = target_file.name
            subprocess.run(
                ["cmd", "/c", f".\\{bat_name}"], env=env, cwd=bat_dir,
            )
        else:
            os.startfile(str(target_file))

    log("[Done]")
