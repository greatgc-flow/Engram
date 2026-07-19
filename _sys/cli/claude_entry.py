"""claude_entry.py — Claude session entry point (shadow-fix wrapper).

Calls hub.py init-session, shows status, then launches claude.cmd via full path
to prevent recursion when claude.bat is on PATH.
"""
import os
import subprocess
import sys
from pathlib import Path

from peer_console import interactive_profile_banner, peer_default_args

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


def _set_title(peer: str) -> None:
    try:
        import json
        import ctypes
        state_file = _PORTABLE_ROOT / ".ai" / "state.json"
        room_id = ""
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            room_id = data.get("room_id", "")
        title = f"[{room_id}] {peer}" if room_id else peer
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        pass


def main() -> None:
    _set_title("Claude (cc)")
    env = _env()
    subprocess.run([_PYTHON, str(_HUB), "init-session", "--agent", "cc"],
                   capture_output=True, env=env)
    subprocess.run([_PYTHON, str(_HUB), "health-update", "--peer", "cc",
                    "--status", "GREEN"], capture_output=True, env=env)
    fill = subprocess.run([_PYTHON, str(_HUB), "context-fill"],
                          capture_output=True, text=True, env=env)
    if fill.stdout.strip():
        print(fill.stdout)
    subprocess.run([_PYTHON, str(_HUB), "status"], env=env)
    cli_args = peer_default_args("cc", sys.argv[1:])
    banner = interactive_profile_banner("cc")
    if banner:
        print(banner)
    result = subprocess.run(
        ["cmd", "/c", str(_CLAUDE_CMD), *cli_args],
        env=env,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
