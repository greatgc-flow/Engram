"""codex_entry.py — Codex (cx) session entry point.

Calls hub.py init-session, health-update, context-fill, then launches codex.cmd.
try-finally로 비정상 종료 시에도 health.json 갱신 보장.
availability.authenticated/entrypoint_ok 은 health-update GREEN 성공 시 자동 갱신됨 (hub.py).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from peer_console import interactive_profile_banner, peer_default_args

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

_VENV_PY = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
_HUB = _SYS_DIR / "core" / "hub.py"
_CODEX_CMD = _SYS_DIR / "env" / "nodejs" / "npm-global" / "codex.cmd"

_PYTHON = str(_VENV_PY) if _VENV_PY.exists() else sys.executable


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


def _health(env: dict, status: str, failures: int = 0, duration_ms: int | None = None) -> None:
    cmd = [_PYTHON, str(_HUB), "health-update", "--peer", "cx",
           "--status", status, "--failures", str(failures)]
    subprocess.run(cmd, capture_output=True, env=env)
    # availability.last_invocation_duration_ms 별도 갱신 (hub.py는 availability dict 미지원)
    if duration_ms is not None:
        import json
        health_path = _SYS_DIR / "codex" / "health.json"
        if health_path.exists():
            try:
                data = json.loads(health_path.read_text(encoding="utf-8"))
                data.setdefault("availability", {})["last_invocation_duration_ms"] = duration_ms
                data["availability"]["last_invocation_exit_code"] = 0 if status == "GREEN" else 1
                health_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass


def main() -> None:
    _set_title("Codex (cx)")
    env = _env()
    subprocess.run([_PYTHON, str(_HUB), "init-session", "--agent", "cx"],
                   capture_output=True, env=env)
    fill = subprocess.run([_PYTHON, str(_HUB), "context-fill"],
                          capture_output=True, text=True, env=env)
    if fill.stdout.strip():
        print(fill.stdout)
    subprocess.run([_PYTHON, str(_HUB), "status"], env=env)

    if not _CODEX_CMD.exists():
        print(f"[ERROR] codex.cmd not found at {_CODEX_CMD}")
        print("  Install: npm install -g @openai/codex")
        sys.exit(1)

    exit_code = 1
    t_start = time.time()
    try:
        _health(env, "GREEN")
        cli_args = peer_default_args("cx", sys.argv[1:])
        banner = interactive_profile_banner("cx")
        if banner:
            print(banner)
        result = subprocess.run(["cmd", "/c", str(_CODEX_CMD), *cli_args], env=env)
        exit_code = result.returncode
        duration_ms = int((time.time() - t_start) * 1000)
        final_status = "GREEN" if exit_code == 0 else "RED"
        _health(env, final_status, failures=0 if exit_code == 0 else 1, duration_ms=duration_ms)
    except KeyboardInterrupt:
        exit_code = 130
    except Exception as e:
        print(f"[codex_entry] error: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        if exit_code not in (0, 130):
            _health(env, "RED", failures=1)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
