"""collab_log.py — Append structured entry to collab-log (replaces collab-log.bat).

Usage: python collab_log.py <AXIS> <SCRIPT> <STATUS> <DETAIL>
  STATUS: OK | FAIL | REFUSED | ESCALATED
"""
import json
import sys
from datetime import datetime
from pathlib import Path


def log_collab(axis: str, script: str, status: str, detail: str) -> None:
    """Append one structured entry to _archive/collab-log/YYYY-MM-DD.md."""
    sys_dir = Path(__file__).parent.parent
    base_dir = sys_dir.parent
    now = datetime.now()

    log_dir = base_dir / "_archive" / "collab-log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{now.strftime('%Y-%m-%d')}.md"

    entry = (
        f"\n## [{now.strftime('%H:%M:%S')}] {axis} | {script}\n"
        f"Status: {status}\n{detail}\n---"
    )
    with log_file.open("a", encoding="utf-8") as f:
        f.write(entry)

    _update_gemini_metrics(sys_dir, axis, status, detail, now)


def _update_gemini_metrics(
    sys_dir: Path, axis: str, status: str, detail: str, now: datetime
) -> None:
    """Update call counters and consecutive-failure flag in gemini/status.json."""
    status_path = sys_dir / "gemini" / "status.json"
    if not status_path.exists():
        return
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
        today = now.strftime("%Y%m%d")
        ts = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        m = data.get("gemini_metrics", {})
        if m.get("calls_today_date") != today:
            m = {"calls_today": 0, "calls_today_date": today,
                 "last_call_ts": None, "last_axis": None,
                 "consecutive_failures": 0, "last_failure_reason": None}

        if status in ("OK", "REFUSED"):
            m["calls_today"] = m.get("calls_today", 0) + 1
            m["last_axis"] = axis
            m["last_call_ts"] = ts

        if status == "OK":
            m["consecutive_failures"] = 0
            m["last_failure_reason"] = None
        else:
            m["consecutive_failures"] = m.get("consecutive_failures", 0) + 1
            reason = f"REFUSED: {detail}" if status == "REFUSED" else detail
            m["last_failure_reason"] = reason

        if m.get("consecutive_failures", 0) >= 3:
            data["mode"] = "OFF"
            data["reason"] = "api_error"
            data["last_error"] = f"consecutive_failures_{today}"

        data["gemini_metrics"] = m
        status_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass  # metrics update is best-effort; never block the caller


def main() -> None:
    if len(sys.argv) < 5:
        print("Usage: collab_log.py <AXIS> <SCRIPT> <STATUS> <DETAIL>", file=sys.stderr)
        sys.exit(1)
    log_collab(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])


if __name__ == "__main__":
    main()
