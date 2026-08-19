"""claude_entry.py — Claude session entry point (shadow-fix wrapper).

Launches claude.cmd as an interactive console session via console_runner.
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
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(peer)
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
