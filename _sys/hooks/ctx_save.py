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
import uuid
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


def _write_text_atomic(target_path: Path, content: str) -> None:
    """Same-directory atomic replacement with flush, fsync, and os.replace."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.parent / f"{target_path.name}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, target_path)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def main() -> None:
    cwd = Path.cwd()
    claude_md = cwd / "CLAUDE.md"
    if not claude_md.exists():
        print(f"[ctx-save] ERROR: No CLAUDE.md in: {cwd}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now()
    ts_readable = now.strftime("%Y-%m-%d %H:%M")
    marker = f"Last checkpoint: {ts_readable} -- See .ai/ blackboard for details"

    print(f"[ctx-save] Symmetrically checkpointing: {cwd}")

    if not _update_current_state_marker(claude_md, marker):
        print(f"[ctx-save] WARNING: Failed to update marker in CLAUDE.md", file=sys.stderr)

    gemini_md = Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "GEMINI.md"
    if gemini_md.exists():
        if _update_current_state_marker(gemini_md, marker):
            print("[ctx-save] Symmetric Memory updated: CLAUDE.md & GEMINI.md")
    else:
        print("[ctx-save] Notice: GEMINI.md not found at junction. Updated CLAUDE.md only.")

    agents_md = cwd / "AGENTS.md"
    if agents_md.exists():
        if _update_current_state_marker(agents_md, marker):
            print("[ctx-save] Symmetric Memory updated: AGENTS.md (cx session continuity)")

    venv_py = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
    python = str(venv_py) if venv_py.exists() else sys.executable
    env = {**os.environ, "PYTHONUTF8": "1"}

    # Check Gemini environment availability (15s timeout)
    ai_available = False
    try:
        ai_result = subprocess.run(
            [python, str(_SCRIPT_DIR / "ai_check.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            env=env,
        )
        ai_available = (ai_result.returncode == 0)
    except Exception:
        ai_available = False

    blackboard_updated = False
    if ai_available:
        state_file = cwd / ".ai" / "state.json"
        room_id = ""
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
                room_id = state.get("room_id", "")
            except Exception:
                room_id = ""

        if room_id:
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
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="strict",
                    timeout=60,
                    env=env,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    _write_text_atomic(sum_file, proc.stdout)
                    print(f"[ctx-save] Blackboard updated: {sum_file}")
                    blackboard_updated = True
                    try:
                        sys.path.insert(0, str(_SCRIPT_DIR))
                        from collab_log import log_collab  # type: ignore
                        log_collab("Axis-D+", "ctx-save.py", "OK", "Blackboard summary saved.")
                    except Exception:
                        pass
                else:
                    print(f"[ctx-save] Gemini summary skipped (exit code {proc.returncode} or empty stdout).", file=sys.stderr)
            except subprocess.TimeoutExpired:
                print("[ctx-save] Gemini summary timed out (60s). Skipping blackboard summary.", file=sys.stderr)
            except UnicodeDecodeError as exc:
                print(f"[ctx-save] Gemini summary output decode failed ({exc}). Skipping blackboard summary.", file=sys.stderr)
            except Exception as exc:
                print(f"[ctx-save] Gemini summary skipped: {exc}", file=sys.stderr)
            finally:
                if qf_path:
                    try:
                        os.unlink(qf_path)
                    except Exception:
                        pass

    # Auto-sweep stalled consensus rounds (§P-3-QR) - runs best-effort
    try:
        hub_py = _SYS_DIR / "core" / "hub.py"
        if hub_py.exists():
            sweep_result = subprocess.run(
                [python, str(hub_py), "consensus-sweep", "--timeout", "30"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=env,
            )
            sweep_out = sweep_result.stdout.strip()
            if sweep_out and "no stalled rounds" not in sweep_out:
                print(f"[ctx-save] Consensus sweep: {sweep_out}")
    except Exception as exc:
        print(f"[ctx-save] Consensus sweep skipped: {exc}")

    if blackboard_updated:
        print("[ctx-save] Checkpoint complete (state markers & blackboard updated).")
    else:
        print("[ctx-save] Checkpoint complete (state markers updated, blackboard summary skipped).")


if __name__ == "__main__":
    main()
