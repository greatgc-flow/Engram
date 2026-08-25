"""agy_entry.py — Antigravity (ag) session entry point.

Calls hub.py init-session, health-update, context-fill, then launches agy.exe via console_runner.
"""
import os
import sys
from pathlib import Path

from console_runner import ConsoleSessionSpec, run_console_session
from _console_helpers import load_peer_env_vars, set_console_title

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

_AGY_EXE = _SYS_DIR / "tools" / "agy" / "agy.exe"


def _env() -> dict:
    """peers.json에서 antigravity env_vars 로드하여 주입."""
    e = {**os.environ, "PYTHONUTF8": "1"}
    venv_scripts = str(_SYS_DIR / "env" / "venv" / "Scripts")
    e["PATH"] = venv_scripts + ";" + e.get("PATH", "")
    e.update(load_peer_env_vars(_SYS_DIR, "antigravity"))
    return e


def main() -> None:
    set_console_title(_PORTABLE_ROOT, "Antigravity (ag)")
    if not _AGY_EXE.exists():
        print(f"[ERROR] agy.exe not found at {_AGY_EXE}")
        sys.exit(1)

    spec = ConsoleSessionSpec(
        peer_id="ag",
        cmd_prefix=[str(_AGY_EXE)],
        env=_env(),
        cwd=Path.cwd().resolve(),
        context_fill_frame=True,
        health_json_path=_SYS_DIR / "antigravity" / "health.json",
        # ag's original pre-migration convention always marked health RED on
        # Ctrl+C (exit 130), unlike cx/cc -- preserve that here (independent
        # cross-verification found this).
        keyboard_interrupt_is_success=False,
    )
    result = run_console_session(spec, sys.argv[1:])
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
