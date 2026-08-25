"""claude_entry.py — Claude session entry point (shadow-fix wrapper).

Calls hub.py init-session, shows status, then launches claude.cmd via console_runner.
"""
import os
import sys
from pathlib import Path

from console_runner import ConsoleSessionSpec, run_console_session
from _console_helpers import set_console_title

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

_CLAUDE_CMD = _SYS_DIR / "env" / "nodejs" / "npm-global" / "claude.cmd"


def _env() -> dict:
    e = {**os.environ, "PYTHONUTF8": "1"}
    venv_scripts = str(_SYS_DIR / "env" / "venv" / "Scripts")
    e["PATH"] = venv_scripts + ";" + e.get("PATH", "")
    return e


def main() -> None:
    set_console_title(_PORTABLE_ROOT, "Claude (cc)")
    if not _CLAUDE_CMD.exists():
        print(f"[ERROR] claude.cmd not found at {_CLAUDE_CMD}")
        print("  Install: npm install -g @anthropic-ai/claude-code")
        sys.exit(1)

    spec = ConsoleSessionSpec(
        peer_id="cc",
        cmd_prefix=["cmd", "/c", str(_CLAUDE_CMD)],
        env=_env(),
        health_json_path=_SYS_DIR / "claude" / "health.json",
    )
    result = run_console_session(spec, sys.argv[1:])
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
