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


def save_session_log(session_dir: Path, cwd: Path, claude_md: Path, summary_text: str | None = None) -> Path:
    """Append the session handoff summary to the dated session log and return the file path.

    Writes `summary_text` (the LLM-generated Current State/Decisions/Next
    Steps handoff from Phase 2) when available. Never falls back to dumping
    CLAUDE.md's raw content -- CLAUDE.md is explicitly documented as
    pointer-only ("a handoff blob left in it goes stale the moment the next
    session starts"; a stale 2026-07-21 handoff was found and removed for
    exactly this reason), so archiving a snapshot of it here would silently
    reintroduce the same failure mode this policy exists to prevent.
    """
    now = datetime.now()
    ses_date = now.strftime("%Y-%m-%d")
    ses_time = now.strftime("%H:%M")
    project_name = cwd.name or cwd.drive.rstrip(":") or "root"
    ses_file = session_dir / f"{ses_date}_{project_name}.md"
    session_dir.mkdir(parents=True, exist_ok=True)
    is_new = not ses_file.exists() or ses_file.stat().st_size == 0
    with ses_file.open("a", encoding="utf-8") as f:
        if is_new:
            f.write(f"# Sessions {ses_date}\n")
        f.write(f"\n## [ctx-end] {ses_date} {ses_time} - {cwd}\n\n")
        if summary_text and summary_text.strip():
            f.write(summary_text.strip())
        else:
            f.write("(session summary generation failed or produced no output this run)")
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
    session_summary_text: str | None = None
    if not required_failed:
        print(f"[ctx-end] Writing session summary for: {cwd}")
        try:
            # shell=True is required: "claude" resolves to claude.cmd (an npm
            # shim), and Windows CreateProcess cannot launch a .cmd directly
            # without going through the command interpreter -- confirmed live,
            # subprocess.run(["claude", ...]) with shell=False raises
            # FileNotFoundError even though `claude` works fine from a normal
            # shell prompt.
            #
            # This spawns a FRESH, stateless claude -p process -- it has no
            # memory of the actual work session being wrapped up, so it must
            # investigate the repo itself (git log, backlog/memory files)
            # rather than being asked to recount "what I did" as if it had
            # been present. It must also never be told to edit CLAUDE.md:
            # CLAUDE.md is explicitly pointer-only per its own documented
            # policy ("a handoff blob left in it goes stale the moment the
            # next session starts, actively misleading whoever reads it
            # next" -- a stale 2026-07-21 handoff was found and removed for
            # exactly this reason). An earlier version of this prompt did
            # tell it to edit CLAUDE.md, which self-contradicted that policy
            # and produced a confused non-summary response instead of a
            # real handoff.
            # 120s (not the original 60s): a genuine investigation (running
            # `git log`, reading a few files) measurably needs more room
            # than the fast-but-wrong confused-refusal response the old,
            # self-contradicting prompt used to produce. The prompt itself
            # bounds scope explicitly (last ~10 commits, not the whole
            # history) to keep this from growing unboundedly on a very deep
            # repo.
            proc = subprocess.run(
                [
                    "claude", "-p",
                    "You are a fresh, stateless process with no memory of today's actual "
                    "work session. Investigate the current repository state directly -- "
                    "run `git log --oneline -10` and `git status --short`, and skim any "
                    "project memory/backlog files you already know the location of -- to "
                    "construct an accurate handoff summary for whoever picks up the next "
                    "session. Keep your investigation to those bounded checks, do not do a "
                    "deep/open-ended repo exploration. Write your findings as plain "
                    "response text only -- do NOT edit any files, and especially do not "
                    "edit CLAUDE.md (it is pointer-only per its own documented policy; "
                    "session handoffs belong in the dated session log this response will "
                    "be appended to, never in CLAUDE.md). Structure your response: "
                    "1) Current State: what the repo/project looks like right now. "
                    "2) Recent Decisions: notable decisions visible in recent commits, "
                    "with rationale if evident. 3) Next Steps: a clear, prioritized list "
                    "of what remains, based on any backlog/TODO you can find. Be concise.",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=120,
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
                    session_summary_text = proc.stdout.strip()
                    print(session_summary_text)
        except subprocess.TimeoutExpired:
            print("[ctx-end] ERROR: Primary claude summary timed out (120s).", file=sys.stderr)
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
    ses_file = save_session_log(session_dir, cwd, claude_md, session_summary_text)
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
