"""check_health.py — Axis-H: Context Health Check.

Usage: python check_health.py [--force]

Estimates Claude token load via JSONL conversation file size.
Thresholds (JSONL overhead ~3x raw text, so 1.2MB ~ 100k tokens):
  GREEN  : < 600 KB
  YELLOW : 600 KB - 1.2 MB  (consider /compact soon)
  RED    : > 1.2 MB          (recommend /compact or new session)

If RED or --force: calls Gemini to generate _archive/session-handoff.json.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    _PORTABLE_ROOT, _SYS_DIR, ai_available, archive_file, gemini_call, is_refusal,
    log_collab, save_raw,
)


def _find_newest_jsonl(projects_dir: Path) -> Optional[Path]:
    """Return the most-recently-modified JSONL file in projects_dir, or None."""
    files = sorted(projects_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
    return files[-1] if files else None


def _update_status_json(status_file: Path, size_mb: float, status: str) -> None:
    """Update context_health and ai_health fields in status.json."""
    if not status_file.exists():
        return
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        data["context_health"] = {
            "jsonl_mb": size_mb,
            "status": status,
            "checked": ts,
        }
        # Derive gemini_status from current data
        if data.get("mode") == "ON":
            metrics = data.get("gemini_metrics", {})
            gemini_status = "ERROR" if metrics.get("consecutive_failures", 0) >= 3 else "ON"
        else:
            gemini_status = "OFF"
        data["ai_health"] = {
            "claude_status": status,
            "gemini_status": gemini_status,
            "last_session_transition_recommended": None,
            "dashboard_updated": ts,
        }
        status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _mark_status_error(status_file: Path, dt: str) -> None:
    if not status_file.exists():
        return
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        data["last_error"] = f"context_health_failed_{dt}"
        status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


_HANDOFF_PROMPT = (
    "Read this session log and output ONLY a valid JSON object with no extra text, "
    'matching this exact schema: {"version":"1.0","generated_at":"ISO8601_timestamp",'
    '"session_context":{"project_id":"P--","active_axis":"last_axis_mentioned_or_none",'
    '"model_used":"claude-sonnet-4-6"},'
    '"executive_summary":{"narrative":"dense 3-5 sentence summary of what was accomplished",'
    '"milestones_reached":["item1"],"lessons_learned":["item1"]},'
    '"technical_state":{"modified_files":["path1"],'
    '"critical_constants":{"KEY":"VALUE"},"pending_changes":["item1"],"unresolved_bugs":[]},'
    '"strategy_for_next_session":{"immediate_priority":"top 1 next action",'
    '"risks":["risk1"],"suggested_entry_point":"first thing to do on next session"}}. '
    "Be factual and dense. Output ONLY the JSON object, nothing else."
)


def main() -> None:
    force = "--force" in sys.argv

    gemini_dir = _SYS_DIR / "gemini"
    status_file = gemini_dir / "status.json"
    archive_dir = _PORTABLE_ROOT / "_archive"
    sessions_dir = archive_dir / "sessions"
    handoff_file = archive_dir / "session-handoff.json"
    projects_dir = _SYS_DIR / "claude" / "config" / "projects" / "P--"

    ai_available()  # prints [GATE] gemini=ON/OFF for visibility

    # Find newest JSONL
    jsonl = _find_newest_jsonl(projects_dir)
    if jsonl is None:
        print(f"[context-health] No JSONL found in {projects_dir}")
        print("[context-health] Session not yet started or wrong project directory.")
        return

    size_bytes = jsonl.stat().st_size
    size_kb = size_bytes // 1024
    size_mb = round(size_bytes / 1_048_576, 2)

    # Determine status
    if size_kb >= 1200:
        health_status = "RED"
    elif size_kb >= 600:
        health_status = "YELLOW"
    else:
        health_status = "GREEN"
    trigger = health_status == "RED" or force

    print()
    print(f"[context-health] JSONL : {jsonl}")
    print(f"[context-health] Size  : {size_mb} MB  ({size_kb} KB)")
    print(f"[context-health] Status: {health_status}")
    if health_status == "YELLOW":
        print("[context-health] WARNING: Context load elevated. Consider /compact before next heavy task.")
    if health_status == "RED":
        print("[context-health] ALERT: Context near limit. Run /compact or start a new session.")
        print("[context-health] Generating session-handoff.json...")

    # Update status.json
    _update_status_json(status_file, size_mb, health_status)

    if not trigger:
        return

    if not ai_available():
        print("[context-health] Gemini not available. Skipping handoff generation.")
        print("                 Run start.bat first, or check _sys\\gemini\\status.json")
        return

    # Find newest session log
    ses_files = sorted(sessions_dir.glob("*.md"), key=lambda f: f.stat().st_mtime)
    if not ses_files:
        print(f"[context-health] No session log found in {sessions_dir}")
        print("[context-health] Run ctx-save first to create a session checkpoint.")
        print("[context-health] Skipping handoff generation.")
        return

    session_log = ses_files[-1]
    print(f"[context-health] Session log: {session_log}")
    print(f"[context-health] Writing handoff to: {handoff_file}")

    session_content = session_log.read_text(encoding="utf-8", errors="replace")
    dt = datetime.now().strftime("%Y%m%d%H%M%S")
    result = gemini_call(_HANDOFF_PROMPT, stdin=session_content, timeout=180)

    if result.returncode != 0:
        print("[context-health] ERROR: Handoff generation failed. Check Gemini auth.")
        log_collab("Axis-H", "check-health.py", "FAIL", "Error: handoff generation failed")
        _mark_status_error(status_file, dt)
        sys.exit(1)

    if is_refusal(result.stdout):
        handoff_file.unlink(missing_ok=True)
        print("[context-health] Gemini refused handoff generation.")
        log_collab("Axis-H", "check-health.py", "REFUSED", "Gemini refused request")
        sys.exit(1)

    handoff_file.write_text(result.stdout, encoding="utf-8")
    print(f"[context-health] Handoff written: {handoff_file}")
    log_collab("Axis-H", "check-health.py", "OK", f"Handoff: {handoff_file}")
    print("[context-health] Recommended actions:")
    print("[context-health]   1. /compact  - compress current context (loses detail)")
    print("[context-health]   2. New session - read _archive\\session-handoff.json to resume")

    archive_file("scan-health", handoff_file)


if __name__ == "__main__":
    main()
