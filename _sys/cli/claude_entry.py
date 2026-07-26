"""claude_entry.py — Claude session entry point (shadow-fix wrapper).

Calls hub.py init-session, shows status, then launches claude.cmd via console_runner.
"""
import os
import sys
from pathlib import Path

from console_runner import ConsoleSessionSpec, run_console_session

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

_CLAUDE_CMD = _SYS_DIR / "env" / "nodejs" / "npm-global" / "claude.cmd"


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
    spec = ConsoleSessionSpec(
        peer_id="cc",
        cmd_prefix=["cmd", "/c", str(_CLAUDE_CMD)],
        env=_env(),
    )
    result = run_console_session(spec, sys.argv[1:])
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
