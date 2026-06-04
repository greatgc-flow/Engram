"""gemini_entry.py — Gemini session entry point (shadow-fix wrapper).

Calls hub.py init-session (captures session ID), shows status,
then launches gemini.cmd --resume SESSION_ID to prevent recursion.
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
_GEMINI_CMD = _SYS_DIR / "env" / "nodejs" / "npm-global" / "gemini.cmd"

_PYTHON = str(_VENV_PY) if _VENV_PY.exists() else sys.executable


def _env() -> dict:
    e = {**os.environ, "PYTHONUTF8": "1"}
    npm_global = str(_SYS_DIR / "env" / "nodejs" / "npm-global")
    venv_scripts = str(_SYS_DIR / "env" / "venv" / "Scripts")
    e["PATH"] = npm_global + ";" + venv_scripts + ";" + e.get("PATH", "")
    return e


def main() -> None:
    env = _env()
    sid_result = subprocess.run(
        [_PYTHON, str(_HUB), "init-session", "--agent", "gemini"],
        capture_output=True, text=True, env=env,
    )
    session_id = sid_result.stdout.strip()
    subprocess.run([_PYTHON, str(_HUB), "status"], env=env)

    cmd = ["cmd", "/c", str(_GEMINI_CMD)]
    if session_id:
        cmd += ["--resume", session_id]
    cmd += sys.argv[1:]
    result = subprocess.run(cmd, env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
