"""_common.py — Shared utilities for _sys/checks/ scripts."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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


def _active_ai_peer() -> str | None:
    """Select the first enabled, healthy review peer from live configuration."""
    try:
        orchestration = json.loads(
            (_SYS_DIR / "ai" / "orchestration.json").read_text(encoding="utf-8")
        )
        peers = json.loads(
            (_SYS_DIR / "ai" / "peers.json").read_text(encoding="utf-8")
        ).get("peers", {})
    except (OSError, json.JSONDecodeError):
        return None

    node_to_sys_dir = {}
    for peer_cfg in peers.values():
        if not isinstance(peer_cfg, dict) or peer_cfg.get("enabled") is False:
            continue
        for node_id in peer_cfg.get("node_ids", []):
            node_to_sys_dir[node_id] = peer_cfg.get("sys_subdir")

    enabled = {
        node.get("node_id")
        for node in orchestration.get("hub_nodes", [])
        if node.get("type") == "peer"
        and node.get("enabled", True) is not False
        and node.get("node_id")
    }
    for node_id in ("ag", "cc", "cx"):
        if node_id not in enabled:
            continue
        sys_subdir = node_to_sys_dir.get(node_id)
        if not sys_subdir:
            continue
        try:
            health = json.loads(
                (_SYS_DIR / sys_subdir / "health.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            continue
        availability = health.get("availability", {})
        if (
            health.get("context_health", {}).get("status") in {"GREEN", "YELLOW"}
            and availability.get("gate_open") is not False
            and availability.get("authenticated") is not False
        ):
            return node_id
    return None


def ai_available() -> bool:
    """Return True when an enabled, healthy review peer is available."""
    return _active_ai_peer() is not None


def gemini_call(
    prompt: str,
    *,
    stdin: Optional[str] = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Compatibility wrapper that routes check analysis through the active peer."""
    peer = _active_ai_peer()
    if peer is None:
        return subprocess.CompletedProcess(
            args=["hub.py", "ask"], returncode=1, stdout="", stderr="no active AI peer"
        )
    content = prompt + (("\n\n[INPUT]\n" + stdin) if stdin else "")
    query_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=f"-{uuid.uuid4().hex[:8]}.txt",
            delete=False,
        ) as query_file:
            query_file.write(content)
            query_path = Path(query_file.name)
        venv_py = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
        python = str(venv_py) if venv_py.exists() else sys.executable
        command = [
            python,
            str(_SYS_DIR / "core" / "hub.py"),
            "ask",
            "--to",
            peer,
            "--query-file",
            str(query_path),
            "--quiet",
            "--session-policy",
            "fresh",
            "--timeout",
            str(timeout),
        ]
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout + 30,
                env=build_env(),
            )
        except subprocess.TimeoutExpired as exc:
            return subprocess.CompletedProcess(
                args=command,
                returncode=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or f"active peer timed out after {timeout + 30}s",
            )
    finally:
        if query_path is not None:
            query_path.unlink(missing_ok=True)


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
    if _active_ai_peer() != "gc":
        return
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
