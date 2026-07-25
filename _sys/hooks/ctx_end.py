"""ctx_end.py — Session end: full summary + Obsidian backup (replaces ctx-end.bat).

Usage: python ctx_end.py [--global] [--pause-on-error]
  --global         : also update global CLAUDE.md via claude -p
  --pause-on-error : optional TTY pause AFTER all cleanup phases if a required phase fails
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_WATCHDOG_RUNNING = False  # Re-entrancy guard

_SCRIPT_DIR = Path(__file__).parent
_SYS_DIR = _SCRIPT_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent


def run_contract_watchdog(
    ai_root: Path | None = None,
    python_exe: str | None = None,
) -> None:
    """Post-flight contract check — runs check_contracts.py and alerts on failure.

    On success: silent.
    On failure: creates a hub thread with [SYSTEM_ALERT] and failure log tail.
    Re-entrant calls are no-ops (prevents ctx-end recursion).
    """
    global _WATCHDOG_RUNNING
    if _WATCHDOG_RUNNING:
        return
    _WATCHDOG_RUNNING = True
    try:
        py = python_exe or sys.executable
        check_script = _SYS_DIR / "checks" / "check_contracts.py"
        if not check_script.exists():
            return

        result = subprocess.run(
            [py, str(check_script), "--always"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )

        if result.returncode == 0:
            return  # silent on success

        failure_output = (result.stdout + result.stderr).strip()
        tail = "\n".join(failure_output.splitlines()[-20:])

        hub_py = _SYS_DIR / "core" / "hub.py"
        if not hub_py.exists() or ai_root is None:
            print(f"[ctx-end watchdog] ALERT: contract violation:\n{tail}", file=sys.stderr)
            return

        msg = f"[SYSTEM_ALERT] Contract violation at session end.\n\n{tail}"
        subprocess.run(
            [py, str(hub_py), "thread-new",
             "--ai-root", str(ai_root),
             "--topic", "SYSTEM_ALERT: contract violation",
             "--from-peer", "watchdog",
             "--msg", msg],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        print(f"[ctx-end watchdog] ALERT: contract violation — thread created", file=sys.stderr)
        print(tail, file=sys.stderr)
    except Exception as exc:
        print(f"[ctx-end watchdog] Error (non-fatal): {exc}", file=sys.stderr)
    finally:
        _WATCHDOG_RUNNING = False


def _check_prerequisites(claude_config_dir: Path) -> bool:
    if shutil.which("claude") is None:
        print("[ctx-end] ERROR: 'claude' not found in PATH.", file=sys.stderr)
        print("          Run this from a sandbox terminal (via start.bat).", file=sys.stderr)
        print("          Or install: npm install -g @anthropic-ai/claude-code", file=sys.stderr)
        return False
    if not (claude_config_dir / ".credentials.json").exists():
        print("[ctx-end] ERROR: Claude credentials not found.", file=sys.stderr)
        print("          Run 'claude' in the VS Code terminal to log in first.", file=sys.stderr)
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
        if claude_md.exists():
            f.write(claude_md.read_text(encoding="utf-8"))
        else:
            f.write("(CLAUDE.md missing at snapshot time)")
        f.write("\n\n---\n")
    return ses_file


def _gemini_session_keep_days() -> int:
    """GEMINI_SESSION_KEEP as an int, falling back to 7 on an unset/invalid value."""
    try:
        return int(os.environ.get("GEMINI_SESSION_KEEP", "7"))
    except ValueError:
        return 7


def archive_gemini_session(portable_root: Path) -> None:
    """Move active session to history in session-map.json and delete session-id.txt."""
    sys_gemini = portable_root / "_sys" / "gemini"
    sid_file = sys_gemini / "session-id.txt"
    smap_file = sys_gemini / "session-map.json"
    if not sid_file.exists():
        return
    print("[ctx-end] Archiving Gemini session to session-map...")
    now_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    lock_dir = smap_file.with_name(smap_file.name + ".lock")
    acquired = False
    for _ in range(50):
        try:
            lock_dir.mkdir(exist_ok=False)
            acquired = True
            break
        except FileExistsError:
            time.sleep(0.1)

    try:
        history: list = []
        active = None
        if smap_file.exists():
            try:
                data = json.loads(smap_file.read_text(encoding="utf-8"))
                history = list(data.get("history", []))
                active = data.get("active")
            except Exception as exc:
                print(f"[ctx-end] Warning: session-map.json unreadable, starting fresh history: {exc}", file=sys.stderr)
        if active:
            active["ended_at"] = now_ts
            history.append(active)
        out = {"active": None, "history": history}
        smap_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        if acquired:
            try:
                lock_dir.rmdir()
            except OSError:
                pass
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
        try:
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                shutil.move(str(f), archive_dir / f.name)
                moved += 1
        except Exception:
            pass
    if moved:
        print(f"[ctx-end] Gemini session cleanup: {moved} files moved to _archive/gemini-sessions/")


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
    # Add portable paths to os.environ["PATH"]
    paths = [
        str(_SYS_DIR / "env" / "venv" / "Scripts"),
        str(_SYS_DIR / "env" / "nodejs" / "npm-global"),
        os.environ.get("PATH", "")
    ]
    os.environ["PATH"] = os.pathsep.join(paths)

    global_update = "--global" in sys.argv
    pause_on_error = "--pause-on-error" in sys.argv
    cwd = Path.cwd()

    claude_config_dir = Path(
        os.environ.get("CLAUDE_CONFIG_DIR", str(_SYS_DIR / "claude" / "config"))
    )

    env = {**os.environ, "PYTHONUTF8": "1"}
    required_failed = False

    # ── Phase 1: Environment & Prerequisites Check ────────────────────────────
    if not _check_prerequisites(claude_config_dir):
        required_failed = True

    claude_md = cwd / "CLAUDE.md"
    if not claude_md.exists():
        print(f"[ctx-end] ERROR: No CLAUDE.md in: {cwd}", file=sys.stderr)
        print("          Run from project root, or create from template:", file=sys.stderr)
        print(f"          copy _sys\\docs\\CLAUDE_project.md \"{cwd}\\CLAUDE.md\"", file=sys.stderr)
        required_failed = True

    # ── Phase 2: Primary & Global LLM Summaries ───────────────────────────────
    if not required_failed:
        print(f"[ctx-end] Writing session summary for: {cwd}")
        try:
            # shell=True is required: "claude" resolves to claude.cmd (an npm
            # shim), and Windows CreateProcess cannot launch a .cmd directly
            # without going through the command interpreter -- confirmed live,
            # subprocess.run(["claude", ...]) with shell=False raises
            # FileNotFoundError even though `claude` works fine from a normal
            # shell prompt.
            proc = subprocess.run(
                [
                    "claude", "-p",
                    "Session end: Update CLAUDE.md fully. 1) Current State: final state. "
                    "2) Decisions Made: append any new decisions with rationale. "
                    "3) Next Steps: clear prioritized list for next session. "
                    "4) Update Last updated date. Be thorough - this is the handoff for the next session.",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=60,
                env=env,
                shell=True,
            )
            if proc.returncode != 0:
                print(f"[ctx-end] ERROR: claude returned exit code {proc.returncode}.", file=sys.stderr)
                if proc.stderr:
                    print(f"          stderr: {proc.stderr.strip()[:300]}", file=sys.stderr)
                required_failed = True
            else:
                if proc.stdout:
                    print(proc.stdout.strip())
        except subprocess.TimeoutExpired:
            print("[ctx-end] ERROR: Primary claude summary timed out (60s).", file=sys.stderr)
            required_failed = True
        except UnicodeDecodeError as exc:
            print(f"[ctx-end] ERROR: Primary claude stdout output decode failed: {exc}", file=sys.stderr)
            required_failed = True
        except Exception as exc:
            print(f"[ctx-end] ERROR: Primary claude call failed: {exc}", file=sys.stderr)
            required_failed = True

        if global_update:
            global_md = claude_config_dir / "CLAUDE.md"
            if global_md.exists():
                print("[ctx-end] Updating global CLAUDE.md...")
                try:
                    gproc = subprocess.run(
                        [
                            "claude", "-p",
                            f"Update the global CLAUDE.md at {global_md} with new preferences or "
                            "lessons from today. Keep it concise and universal across projects.",
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="strict",
                        timeout=60,
                        env=env,
                        shell=True,
                    )
                    if gproc.returncode != 0:
                        print(f"[ctx-end] WARNING: Global CLAUDE.md update returned exit code {gproc.returncode}.", file=sys.stderr)
                except subprocess.TimeoutExpired:
                    print("[ctx-end] WARNING: Global CLAUDE.md update timed out (60s).", file=sys.stderr)
                except Exception as exc:
                    print(f"[ctx-end] WARNING: Global CLAUDE.md update failed: {exc}", file=sys.stderr)
            else:
                print(f"[ctx-end] Note: no global CLAUDE.md found at {global_md}")

    # ── Phase 3: Raw Session Log Preservation ─────────────────────────────────
    ses_dir_env = os.environ.get("SESSION_DIR")
    session_dir = Path(ses_dir_env) if ses_dir_env else _PORTABLE_ROOT / "_archive" / "sessions"
    ses_file = save_session_log(session_dir, cwd, claude_md)
    print(f"[ctx-end] Session log saved: {ses_file}")

    # ── Phase 4: Optional Gemini Summary (Atomic Replacement) ─────────────────
    venv_py = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
    python = str(venv_py) if venv_py.exists() else sys.executable
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

    if ai_available:
        sum_file = Path(str(ses_file) + ".summary.md")
        qf_path = None
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
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=60,
                env=env,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                _write_text_atomic(sum_file, proc.stdout)
                try:
                    sys.path.insert(0, str(_SCRIPT_DIR))
                    from raw_log import save_raw  # type: ignore
                    from collab_log import log_collab  # type: ignore
                    save_raw("Axis-C", sum_file, ses_file)
                    log_collab("Axis-C", "ctx-end.py", "OK", f"Summary: {sum_file}")
                except Exception:
                    pass
                print(f"[ctx-end] Summary: {sum_file}")
            else:
                print("[ctx-end] Gemini summary skipped (nonzero returncode or empty response).")
                try:
                    sys.path.insert(0, str(_SCRIPT_DIR))
                    from collab_log import log_collab  # type: ignore
                    log_collab("Axis-C", "ctx-end.py", "FAIL", "Error: api_error_or_empty")
                except Exception:
                    pass
        except subprocess.TimeoutExpired:
            print("[ctx-end] Gemini summary timed out (60s). Skipping optional summary.")
        except UnicodeDecodeError as exc:
            print(f"[ctx-end] Gemini summary output decode failed ({exc}). Skipping optional summary.")
        except Exception as exc:
            print(f"[ctx-end] Gemini summary skipped ({exc}).")
        finally:
            if qf_path:
                try:
                    os.unlink(qf_path)
                except Exception:
                    pass

    # ── Phase 5: Independent Cleanup Steps (Best-Effort) ──────────────────────
    try:
        archive_gemini_session(_PORTABLE_ROOT)
    except Exception as exc:
        print(f"[ctx-end] Archive Gemini session skipped: {exc}", file=sys.stderr)

    try:
        cleanup_gemini_sessions(_PORTABLE_ROOT, _gemini_session_keep_days())
    except Exception as exc:
        print(f"[ctx-end] Cleanup Gemini sessions skipped: {exc}", file=sys.stderr)

    try:
        sys.path.insert(0, str(_SCRIPT_DIR))
        from memory_compactor import main as compact_memory  # type: ignore
        compact_memory(_PORTABLE_ROOT)
    except Exception as exc:
        print(f"[ctx-end] Memory compaction skipped: {exc}", file=sys.stderr)

    try:
        ai_root_default = _PORTABLE_ROOT / ".ai"
        run_contract_watchdog(
            ai_root=ai_root_default if ai_root_default.exists() else None,
            python_exe=python,
        )
    except Exception as exc:
        print(f"[ctx-end] Contract watchdog skipped: {exc}", file=sys.stderr)

    try:
        _self_care = _SYS_DIR / "checks" / "self_care.py"
        if _self_care.exists():
            subprocess.Popen(
                [python, str(_self_care), "--trigger", "session_end"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass

    # ── Phase 6: Final Single Exit ────────────────────────────────────────────
    if required_failed:
        print("\n[ctx-end] FAILED: Session end completed with errors in required phases.", file=sys.stderr)
        if pause_on_error and sys.stdin.isatty():
            try:
                input("Press Enter to continue...")
            except (EOFError, KeyboardInterrupt):
                pass
        sys.exit(1)

    print("\n[ctx-end] Session saved. Safe to close.")
    if not global_update:
        print("         Tip: ctx-end --global  also updates global preferences.")
    sys.exit(0)


if __name__ == "__main__":
    main()
