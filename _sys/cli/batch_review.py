"""batch_review.py — Axis-R: Batch review of uncommitted changes via Gemini.

Called by: Stop hook or manually.
Requires: collab_rate >= 7, time gate, git changes present.
Output: _archive/gemini-reviews/YYYYMMDD_HHMMSS.md + latest.md
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "checks"))
from _common import (  # noqa: E402
    _PORTABLE_ROOT, _SYS_DIR, ai_available, gemini_call, is_refusal, log_collab,
)

_CFG_FILE = _SYS_DIR / "ai" / "config.json"
_PROTOCOL_FILE = _SYS_DIR / "ai" / "protocol.json"


def _ratio_ok(threshold: int) -> bool:
    # protocol.json 우선, fallback → config.json (deprecated)
    try:
        if _PROTOCOL_FILE.exists():
            rate = json.loads(_PROTOCOL_FILE.read_text(encoding="utf-8"))
            val = rate.get("collab_rate", {}).get("current", 0)
            return int(val) >= threshold
    except Exception:
        pass
    try:
        if _CFG_FILE.exists():
            return int(json.loads(_CFG_FILE.read_text(encoding="utf-8")).get("ratio", 0)) >= threshold
    except Exception:
        pass
    return False


def _time_gate_ok() -> bool:
    if not _CFG_FILE.exists():
        return True
    try:
        cfg = json.loads(_CFG_FILE.read_text(encoding="utf-8"))
        interval = int(cfg.get("review_interval_min", 5))
        last = cfg.get("last_review_ts")
        if not last or last == "null":
            return True
        last_dt = datetime.fromisoformat(last)
        return (datetime.now() - last_dt).total_seconds() / 60 >= interval
    except Exception:
        return True


def _update_last_review_ts() -> None:
    try:
        cfg = json.loads(_CFG_FILE.read_text(encoding="utf-8")) if _CFG_FILE.exists() else {}
    except Exception:
        cfg = {}
    cfg["last_review_ts"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    _CFG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_diff(root: Path) -> str:
    stat = subprocess.run(
        ["git", "-C", str(root), "diff", "HEAD", "--stat"],
        capture_output=True, text=True, timeout=10,
    )
    diff = subprocess.run(
        ["git", "-C", str(root), "diff", "HEAD"],
        capture_output=True, text=True, timeout=30,
    )
    content = stat.stdout + diff.stdout
    if len(content) > 8000:
        content = content[:8000] + "\n...(truncated)"
    return content


def main() -> None:
    if not _ratio_ok(7):
        print("[Axis-R] SKIP: ratio < 7")
        return

    if not ai_available():
        print("[Axis-R] SKIP: Gemini not available")
        return

    if not _time_gate_ok():
        print("[Axis-R] SKIP: review interval not elapsed")
        return

    diff_content = _get_diff(_PORTABLE_ROOT)
    if not diff_content.strip():
        print("[Axis-R] SKIP: no uncommitted changes")
        return

    prompt = (
        "Review the following uncommitted git diff. Report in English:\n"
        "1) Bugs or risky patterns\n"
        "2) Improvements or simplification opportunities\n"
        "3) One-line summary of changes\n"
        "Be concise (max 400 words).\n\n"
        "--- git diff ---\n" + diff_content
    )

    out_dir = _PORTABLE_ROOT / "_archive" / "gemini-reviews"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"{ts}.md"

    print("[Axis-R] Requesting Gemini review...")
    result = gemini_call(prompt)

    if result.returncode != 0:
        print("[Axis-R] ERROR: Gemini call failed")
        out_file.unlink(missing_ok=True)
        log_collab("Axis-R", "batch-review.py", "FAIL", "Error: gemini call failed")
        return

    if is_refusal(result.stdout):
        print("[Axis-R] Gemini refused request")
        out_file.unlink(missing_ok=True)
        log_collab("Axis-R", "batch-review.py", "REFUSED", "Gemini refused review")
        return

    out_file.write_text(result.stdout, encoding="utf-8")
    (out_dir / "latest.md").write_text(result.stdout, encoding="utf-8")
    _update_last_review_ts()
    log_collab("Axis-R", "batch-review.py", "OK", f"Review: {out_file}")
    print(f"[Axis-R] Review complete: {out_file}")


if __name__ == "__main__":
    main()
