"""codex_entry.py — Codex (cx) session entry point.

Launches codex.cmd as an interactive console session via console_runner.
"""
import os
import sys
from pathlib import Path

from console_runner import ConsoleSessionSpec, run_console_session

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

_CODEX_CMD = _SYS_DIR / "env" / "nodejs" / "npm-global" / "codex.cmd"


def _env() -> dict:
    e = {**os.environ, "PYTHONUTF8": "1"}
    venv_scripts = str(_SYS_DIR / "env" / "venv" / "Scripts")
    e["PATH"] = venv_scripts + ";" + e.get("PATH", "")
    codex_config = _SYS_DIR / "codex" / "config"
    if codex_config.exists():
        e["CODEX_HOME"] = str(codex_config)
    return e


def _set_title(peer: str) -> None:
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(peer)
    except Exception:
        pass


def main() -> None:
    _set_title("Codex (cx)")
    if not _CODEX_CMD.exists():
        print(f"[ERROR] codex.cmd not found at {_CODEX_CMD}")
        print("  Install: npm install -g @openai/codex")
        sys.exit(1)

    spec = ConsoleSessionSpec(
        peer_id="cx",
        cmd_prefix=["cmd", "/c", str(_CODEX_CMD)],
        env=_env(),
    )
    result = run_console_session(spec, sys.argv[1:])
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
