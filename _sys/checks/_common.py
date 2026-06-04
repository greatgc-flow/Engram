"""_common.py — Shared utilities for _sys/checks/ scripts."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

sys.path.insert(0, str(_SYS_DIR / "hooks"))
from collab_log import log_collab  # noqa: E402
from raw_log import save_raw  # noqa: E402


def build_env() -> dict:
    """Return subprocess env with PYTHONUTF8=1 and npm-global prepended to PATH."""
    e = {**os.environ, "PYTHONUTF8": "1"}
    npm_global = _SYS_DIR / "env" / "nodejs" / "npm-global"
    if npm_global.exists():
        e["PATH"] = str(npm_global) + ";" + e.get("PATH", "")
    return e


def ai_available() -> bool:
    """Return True if Gemini is available (ai_check.py exits 0)."""
    venv_py = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
    python = str(venv_py) if venv_py.exists() else sys.executable
    r = subprocess.run(
        [python, str(_SYS_DIR / "hooks" / "ai_check.py")],
        capture_output=True, env=build_env(),
    )
    return r.returncode == 0


def gemini_call(
    prompt: str,
    *,
    stdin: Optional[str] = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Run gemini CLI with an ephemeral session. stdin is optional piped input."""
    sid = str(uuid.uuid4())
    return subprocess.run(
        ["gemini", "--session-id", sid, "-p", prompt, "-o", "text", "-y"],
        capture_output=True, text=True, input=stdin, timeout=timeout, env=build_env(),
    )


def is_refusal(text: str) -> bool:
    """Return True if Gemini output contains a refusal marker."""
    return "[REFUSAL:" in text.upper()


def write_unknown_json(out_file: Path, task: str, note: str) -> None:
    """Write an UNKNOWN-status JSON result (non-blocking fallback)."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    data = {
        "agent": "check-unknown",
        "timestamp": ts,
        "task_summary": task,
        "risks": [],
        "overall_risk": "UNKNOWN",
        "proceed": True,
        "note": note,
    }
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_status_error(dt: str, error_key: str) -> None:
    """Mark Gemini status.json as OFF with api_error reason."""
    gemini_dir = Path(os.environ.get("GEMINI_DIR", str(_SYS_DIR / "gemini")))
    status_file = gemini_dir / "status.json"
    if not status_file.exists():
        return
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        data["last_error"] = f"{error_key}_{dt}"
        data["mode"] = "OFF"
        data["reason"] = "api_error"
        status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def archive_file(name: str, out_file: Path) -> None:
    """Non-blocking call to hub.py archive-file."""
    venv_py = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
    python = str(venv_py) if venv_py.exists() else sys.executable
    try:
        subprocess.run(
            [python, str(_SYS_DIR / "core" / "hub.py"),
             "archive-file", "--name", name, "--file", str(out_file)],
            capture_output=True, timeout=10, env=build_env(),
        )
    except Exception:
        print("[WARN] Archive failed (non-blocking)")


def extract_json_block(text: str) -> str:
    """Extract the first {...} JSON block from text (strips prose/fences)."""
    start = text.find("{")
    if start < 0:
        return text
    end = text.rfind("}")
    return text[start:end + 1] if end >= start else text
