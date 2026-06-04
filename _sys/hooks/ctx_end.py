"""ctx_end.py — Session end: full summary + Obsidian backup (replaces ctx-end.bat).

Usage: python ctx_end.py [--global]
  --global : also update global CLAUDE.md via claude -p
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_SYS_DIR = _SCRIPT_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent


def _check_prerequisites(claude_config_dir: Path) -> bool:
    if shutil.which("claude") is None:
        print("[ctx-end] ERROR: 'claude' not found in PATH.")
        print("          Run this from a sandbox terminal (via start.bat).")
        print("          Or install: npm install -g @anthropic-ai/claude-code")
        return False
    if not (claude_config_dir / ".credentials.json").exists():
        print("[ctx-end] ERROR: Claude credentials not found.")
        print("          Run 'claude' in the VS Code terminal to log in first.")
        return False
    return True


def save_session_log(session_dir: Path, cwd: Path, claude_md: Path) -> Path:
    """Append CLAUDE.md snapshot to dated session log and return the file path."""
    now = datetime.now()
    ses_date = now.strftime("%Y-%m-%d")
    ses_time = now.strftime("%H:%M")
    ses_file = session_dir / f"{ses_date}_{cwd.name}.md"
    session_dir.mkdir(parents=True, exist_ok=True)
    is_new = not ses_file.exists() or ses_file.stat().st_size == 0
    with ses_file.open("a", encoding="utf-8") as f:
        if is_new:
            f.write(f"# Sessions {ses_date}\n")
        f.write(f"\n## [ctx-end] {ses_date} {ses_time} - {cwd}\n\n")
        f.write(claude_md.read_text(encoding="utf-8"))
        f.write("\n\n---\n")
    return ses_file


def archive_gemini_session(portable_root: Path) -> None:
    """Move active session to history in session-map.json and delete session-id.txt."""
    sys_gemini = portable_root / "_sys" / "gemini"
    sid_file = sys_gemini / "session-id.txt"
    smap_file = sys_gemini / "session-map.json"
    if not sid_file.exists():
        return
    print("[ctx-end] Archiving Gemini session to session-map...")
    now_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    history: list = []
    active = None
    if smap_file.exists():
        try:
            data = json.loads(smap_file.read_text(encoding="utf-8"))
            history = list(data.get("history", []))
            active = data.get("active")
        except Exception:
            pass
    if active:
        active["ended_at"] = now_ts
        history.append(active)
    out = {"active": None, "history": history}
    smap_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    sid_file.unlink(missing_ok=True)
    print("[ctx-end] Gemini session archived.")


def cleanup_gemini_sessions(portable_root: Path, keep_days: int = 7) -> None:
    """Move JSONL files older than keep_days days to _archive/gemini-sessions/."""
    chat_dir = portable_root / "_sys" / "gemini" / "config" / "tmp" / "project" / "chats"
    archive_dir = portable_root / "_archive" / "gemini-sessions"
    if not chat_dir.exists():
        return
    archive_dir.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now() - timedelta(days=keep_days)
    moved = 0
    for f in chat_dir.glob("*.jsonl"):
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            shutil.move(str(f), archive_dir / f.name)
            moved += 1
    if moved:
        print(f"[ctx-end] Gemini session cleanup: {moved} files moved to _archive/gemini-sessions/")


def main() -> None:
    global_update = "--global" in sys.argv
    cwd = Path.cwd()

    claude_config_dir = Path(
        os.environ.get("CLAUDE_CONFIG_DIR",
                       str(_SYS_DIR / "claude" / "config"))
    )

    if not _check_prerequisites(claude_config_dir):
        sys.exit(1)

    claude_md = cwd / "CLAUDE.md"
    if not claude_md.exists():
        print(f"[ctx-end] No CLAUDE.md in: {cwd}")
        print("          Run from project root, or create from template:")
        print(f"          copy _sys\\docs\\CLAUDE_project.md \"{cwd}\\CLAUDE.md\"")
        sys.exit(1)

    env = {**os.environ, "PYTHONUTF8": "1"}

    print(f"[ctx-end] Writing session summary for: {cwd}")
    result = subprocess.run(
        [
            "claude", "-p",
            "Session end: Update CLAUDE.md fully. 1) Current State: final state. "
            "2) Decisions Made: append any new decisions with rationale. "
            "3) Next Steps: clear prioritized list for next session. "
            "4) Update Last updated date. Be thorough - this is the handoff for the next session.",
        ],
        env=env,
    )
    if result.returncode != 0:
        print("[ctx-end] ERROR: claude returned non-zero.")
        input("Press Enter to continue...")
        sys.exit(1)

    if global_update:
        global_md = claude_config_dir / "CLAUDE.md"
        if global_md.exists():
            print("[ctx-end] Updating global CLAUDE.md...")
            subprocess.run(
                [
                    "claude", "-p",
                    f"Update the global CLAUDE.md at {global_md} with new preferences or "
                    "lessons from today. Keep it concise and universal across projects.",
                ],
                env=env,
            )
        else:
            print(f"[ctx-end] Note: no global CLAUDE.md found at {global_md}")
            print("          Copy _sys\\docs\\CLAUDE_global.md to create one.")

    ses_dir_env = os.environ.get("SESSION_DIR")
    session_dir = Path(ses_dir_env) if ses_dir_env else _PORTABLE_ROOT / "_archive" / "sessions"
    ses_file = save_session_log(session_dir, cwd, claude_md)
    print(f"[ctx-end] Session log: {ses_file}")

    print()
    print("[ctx-end] Session saved. Safe to close.")
    if not global_update:
        print("         Tip: ctx-end --global  also updates global preferences.")

    # Optional Gemini summary
    venv_py = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
    python = str(venv_py) if venv_py.exists() else sys.executable
    ai_result = subprocess.run(
        [python, str(_SCRIPT_DIR / "ai_check.py")],
        capture_output=True, text=True, env=env,
    )
    if ai_result.returncode != 0:
        archive_gemini_session(_PORTABLE_ROOT)
        cleanup_gemini_sessions(_PORTABLE_ROOT, int(os.environ.get("GEMINI_SESSION_KEEP", "7")))
        return

    sum_file = Path(str(ses_file) + ".summary.md")
    qf_path = None
    sys.path.insert(0, str(_SCRIPT_DIR))
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False,
            encoding="utf-8", prefix="ctx-end-query-",
        ) as qf:
            qf.write(
                "Read the session log below and write a concise summary with exactly 5 bullet points: "
                "1) What was accomplished 2) Key decisions made 3) Files changed "
                "4) Known issues remaining 5) Next actions. Be specific, not generic.\n\n"
            )
            if ses_file.exists():
                qf.write(ses_file.read_text(encoding="utf-8"))
            qf_path = qf.name

        print("[ctx-end] Generating Gemini summary...")
        msg_bat = _SYS_DIR / "cli" / "msg.bat"
        proc = subprocess.run(
            ["cmd", "/c", str(msg_bat), "ask", "--to", "gc", "--query-file", qf_path],
            capture_output=True, text=True, timeout=60, env=env,
        )
        if proc.stdout.strip():
            sum_file.write_text(proc.stdout, encoding="utf-8")
            from raw_log import save_raw  # type: ignore
            from collab_log import log_collab  # type: ignore
            save_raw("Axis-C", sum_file, ses_file)
            print(f"[ctx-end] Summary: {sum_file}")
            log_collab("Axis-C", "ctx-end.py", "OK", f"Summary: {sum_file}")
        else:
            sum_file.unlink(missing_ok=True)
            print("[ctx-end] Gemini summary skipped (auth or network issue).")
            from collab_log import log_collab  # type: ignore
            log_collab("Axis-C", "ctx-end.py", "FAIL", "Error: api_error")
    except Exception as exc:
        sum_file.unlink(missing_ok=True)
        print(f"[ctx-end] Gemini summary skipped ({exc}).")
    finally:
        if qf_path:
            try:
                os.unlink(qf_path)
            except Exception:
                pass

    archive_gemini_session(_PORTABLE_ROOT)
    cleanup_gemini_sessions(_PORTABLE_ROOT, int(os.environ.get("GEMINI_SESSION_KEEP", "7")))


if __name__ == "__main__":
    main()
