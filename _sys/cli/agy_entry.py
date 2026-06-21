"""agy_entry.py — Antigravity (ag) session entry point.

Calls hub.py init-session, health-update, context-fill, then launches agy.exe.
try-finally 보장으로 비정상 종료 시에도 health.json을 RED로 갱신.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from peer_console import peer_default_args

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

_VENV_PY = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
_HUB = _SYS_DIR / "core" / "hub.py"
_AGY_EXE = _SYS_DIR / "tools" / "agy" / "agy.exe"

_PYTHON = str(_VENV_PY) if _VENV_PY.exists() else sys.executable


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


def _health(env: dict, status: str, pid: int | None = None) -> None:
    subprocess.run(
        [_PYTHON, str(_HUB), "health-update", "--peer", "ag", "--status", status],
        capture_output=True, env=env,
    )
    # PID는 health.json에 직접 기록
    if pid is not None:
        health_path = _SYS_DIR / "antigravity" / "health.json"
        try:
            data = json.loads(health_path.read_text(encoding="utf-8")) if health_path.exists() else {}
            data.setdefault("availability", {})["active_pid"] = pid
            health_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def main() -> None:
    env = _env()
    subprocess.run([_PYTHON, str(_HUB), "init-session", "--agent", "ag"],
                   capture_output=True, env=env)
    fill = subprocess.run([_PYTHON, str(_HUB), "context-fill", "--frame"],
                          capture_output=True, text=True, env=env)
    if fill.stdout.strip():
        print(fill.stdout)
    subprocess.run([_PYTHON, str(_HUB), "status"], env=env)

    if not _AGY_EXE.exists():
        print(f"[ERROR] agy.exe not found at {_AGY_EXE}")
        sys.exit(1)

    proc = None
    exit_code = 1
    try:
        _health(env, "GREEN")
        cli_args = peer_default_args("ag", sys.argv[1:])
        proc = subprocess.Popen([str(_AGY_EXE), *cli_args], env=env)
        _health(env, "GREEN", pid=proc.pid)
        proc.wait()
        exit_code = proc.returncode
        _health(env, "GREEN")
    except KeyboardInterrupt:
        exit_code = 130
    except Exception as e:
        print(f"[agy_entry] error: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        # 비정상 종료(exit_code != 0) 시 RED로 표시, PID 정리
        final_status = "GREEN" if exit_code == 0 else "RED"
        _health(env, final_status, pid=None)
        health_path = _SYS_DIR / "antigravity" / "health.json"
        try:
            data = json.loads(health_path.read_text(encoding="utf-8")) if health_path.exists() else {}
            data.setdefault("availability", {}).pop("active_pid", None)
            health_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
