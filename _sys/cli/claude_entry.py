"""claude_entry.py — Claude session entry point (shadow-fix wrapper).

Calls hub.py init-session, shows status, then launches claude.cmd via full path
to prevent recursion when claude.bat is on PATH.
"""
import os
import subprocess
import sys
from pathlib import Path

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

_VENV_PY = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
_HUB = _SYS_DIR / "core" / "hub.py"
_CLAUDE_CMD = _SYS_DIR / "env" / "nodejs" / "npm-global" / "claude.cmd"

_PYTHON = str(_VENV_PY) if _VENV_PY.exists() else sys.executable


def _env() -> dict:
    e = {**os.environ, "PYTHONUTF8": "1"}
    venv_scripts = str(_SYS_DIR / "env" / "venv" / "Scripts")
    e["PATH"] = venv_scripts + ";" + e.get("PATH", "")
    return e


def main() -> None:
    env = _env()
    subprocess.run([_PYTHON, str(_HUB), "init-session", "--agent", "claude"],
                   capture_output=True, env=env)
    subprocess.run([_PYTHON, str(_HUB), "status"], env=env)
    result = subprocess.run(
        ["cmd", "/c", str(_CLAUDE_CMD), *sys.argv[1:]],
        env=env,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
