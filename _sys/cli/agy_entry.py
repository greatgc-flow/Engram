"""agy_entry.py — Antigravity (ag) session entry point.

Launches agy.exe as an interactive console session via console_runner.
"""
import json
import os
import sys
from pathlib import Path

from console_runner import ConsoleSessionSpec, run_console_session

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

_AGY_EXE = _SYS_DIR / "tools" / "agy" / "agy.exe"


def _env() -> dict:
    """peers.json에서 antigravity env_vars 로드하여 주입."""
    e = {**os.environ, "PYTHONUTF8": "1"}
    venv_scripts = str(_SYS_DIR / "env" / "venv" / "Scripts")
    e["PATH"] = venv_scripts + ";" + e.get("PATH", "")
    peers_path = _SYS_DIR / "ai" / "peers.json"
    try:
        peers = json.loads(peers_path.read_text(encoding="utf-8"))
        agy_cfg = peers.get("peers", peers).get("antigravity", {})
        agy_config_dir = _SYS_DIR / "antigravity" / "config"
        for key in agy_cfg.get("env_vars", {}):
            e[key] = str(agy_config_dir)
    except Exception:
        pass
    return e


def _set_title(peer: str) -> None:
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(peer)
    except Exception:
        pass


def main() -> None:
    _set_title("Antigravity (ag)")
    if not _AGY_EXE.exists():
        print(f"[ERROR] agy.exe not found at {_AGY_EXE}")
        sys.exit(1)

    spec = ConsoleSessionSpec(
        peer_id="ag",
        cmd_prefix=[str(_AGY_EXE)],
        env=_env(),
        cwd=Path.cwd().resolve(),
        # ag's original pre-migration convention always marked health RED on
        # Ctrl+C (exit 130), unlike cx/cc -- preserve that here (independent
        # cross-verification found this).
        keyboard_interrupt_is_success=False,
    )
    result = run_console_session(spec, sys.argv[1:])
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
