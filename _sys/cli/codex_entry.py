"""codex_entry.py — Codex (cx) session entry point.

Calls hub.py init-session, health-update, context-fill, then launches codex.cmd via console_runner.
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
    _set_title("Codex (cx)")
    if not _CODEX_CMD.exists():
        print(f"[ERROR] codex.cmd not found at {_CODEX_CMD}")
        print("  Install: npm install -g @openai/codex")
        sys.exit(1)

    spec = ConsoleSessionSpec(
        peer_id="cx",
        cmd_prefix=["cmd", "/c", str(_CODEX_CMD)],
        env=_env(),
        health_json_path=_SYS_DIR / "codex" / "health.json",
    )
    result = run_console_session(spec, sys.argv[1:])
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
