"""codex_entry.py — Codex (cx) session entry point.

Calls hub.py init-session, health-update, context-fill, then launches codex.cmd via console_runner.
"""
import os
import sys
from pathlib import Path

from console_runner import ConsoleSessionSpec, run_console_session
from _console_helpers import load_peer_env_vars, set_console_title

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

_CODEX_CMD = _SYS_DIR / "env" / "nodejs" / "npm-global" / "codex.cmd"


def _env() -> dict:
    e = {**os.environ, "PYTHONUTF8": "1"}
    venv_scripts = str(_SYS_DIR / "env" / "venv" / "Scripts")
    e["PATH"] = venv_scripts + ";" + e.get("PATH", "")
    e.update(load_peer_env_vars(_SYS_DIR, "codex"))
    return e


def main() -> None:
    set_console_title(_PORTABLE_ROOT, "Codex (cx)")
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
