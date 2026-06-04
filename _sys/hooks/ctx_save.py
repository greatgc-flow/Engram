"""ctx_save.py — Symmetric Zero-Token Checkpoint (PROTOCOL v3.1).

Updates CLAUDE.md and GEMINI.md with current state marker.
Generates blackboard summary via Gemini (Axis-D+) when available.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_SYS_DIR = _SCRIPT_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent


def _update_current_state_marker(md_file: Path, marker: str) -> bool:
    """Replace the first line after '## Current State' with marker."""
    try:
        content = md_file.read_text(encoding="utf-8")
        updated = re.sub(
            r"(## Current State\r?\n)[^\r\n]*",
            lambda m: m.group(1) + marker,
            content,
        )
        if updated != content:
            md_file.write_text(updated, encoding="utf-8")
        return True
    except Exception:
        return False


def main() -> None:
    cwd = Path.cwd()
    claude_md = cwd / "CLAUDE.md"
    if not claude_md.exists():
        print(f"[ctx-save] No CLAUDE.md in: {cwd}")
        sys.exit(1)

    now = datetime.now()
    ts_readable = now.strftime("%Y-%m-%d %H:%M")
    marker = f"Last checkpoint: {ts_readable} -- See .ai/ blackboard for details"

    print(f"[ctx-save] Symmetrically checkpointing: {cwd}")

    _update_current_state_marker(claude_md, marker)

    gemini_md = Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "GEMINI.md"
    if gemini_md.exists():
        _update_current_state_marker(gemini_md, marker)
        print("[ctx-save] Symmetric Memory updated: CLAUDE.md & GEMINI.md")
    else:
        print("[ctx-save] Notice: GEMINI.md not found at junction. Updated CLAUDE.md only.")

    # Gemini blackboard summary (skip if unavailable)
    venv_py = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
    python = str(venv_py) if venv_py.exists() else sys.executable
    env = {**os.environ, "PYTHONUTF8": "1"}

    ai_result = subprocess.run(
        [python, str(_SCRIPT_DIR / "ai_check.py")],
        capture_output=True, text=True, env=env,
    )
    if ai_result.returncode != 0:
        print("[ctx-save] Checkpoint complete.")
        return

    state_file = cwd / ".ai" / "state.json"
    if not state_file.exists():
        print("[ctx-save] No .ai/state.json — skipping blackboard summary.")
        print("[ctx-save] Checkpoint complete.")
        return

    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        room_id = state.get("room_id", "")
    except Exception:
        room_id = ""

    if not room_id:
        print("[ctx-save] No room_id in state.json — skipping blackboard summary.")
        print("[ctx-save] Checkpoint complete.")
        return

    room_dir = cwd / ".ai" / "sessions" / room_id
    room_dir.mkdir(parents=True, exist_ok=True)
    sum_file = room_dir / "summary_session.md"

    qf_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False,
            encoding="utf-8", prefix="ctx-save-query-",
        ) as qf:
            qf.write(
                "Generate a Zero-Token summary (max 4KB) for both Claude and Gemini.\n"
                "1) Tasks completed since last save\n"
                "2) Current technical state\n"
                "3) Critical next steps for the next node to pick up.\n\n"
            )
            qf.write(claude_md.read_text(encoding="utf-8"))
            qf_path = qf.name

        print(f"[ctx-save] Generating Blackboard summary for {room_id}...")
        msg_bat = _SYS_DIR / "cli" / "msg.bat"
        proc = subprocess.run(
            ["cmd", "/c", str(msg_bat), "ask", "--to", "gc", "--query-file", qf_path],
            capture_output=True, text=True, timeout=60, env=env,
        )
        sum_file.write_text(proc.stdout, encoding="utf-8")
        print(f"[ctx-save] Blackboard updated: {sum_file}")

        sys.path.insert(0, str(_SCRIPT_DIR))
        from collab_log import log_collab  # type: ignore
        log_collab("Axis-D+", "ctx-save.py", "OK", "Blackboard summary saved.")
    except Exception as exc:
        print(f"[ctx-save] Gemini summary skipped: {exc}")
    finally:
        if qf_path:
            try:
                os.unlink(qf_path)
            except Exception:
                pass

    print("[ctx-save] Checkpoint complete.")


if __name__ == "__main__":
    main()
