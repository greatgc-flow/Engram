"""check_risk.py — Axis-I: Pre-flight Risk Assessment via Gemini.

Usage: python check_risk.py "task description" "file1,file2,..."
GEMINI OFF → writes UNKNOWN result, exits 0 (non-blocking).
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    _PORTABLE_ROOT, ai_available, archive_file, gemini_call, is_refusal,
    log_collab, save_raw, write_unknown_json,
)


def _read_collab_tail(collab_log_dir: Path, n: int = 20) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = collab_log_dir / f"{today}.md"
    if not log_file.exists():
        return ""
    lines = log_file.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-n:])


def main() -> None:
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    files = sys.argv[2] if len(sys.argv) > 2 else ""

    archive_dir = _PORTABLE_ROOT / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    out_file = archive_dir / "risk-scan.json"
    collab_log_dir = archive_dir / "collab-log"

    if not ai_available():
        print("[risk-scan] Gemini not available. Skipping risk assessment.")
        write_unknown_json(out_file, task, "Gemini unavailable - proceeding without risk scan")
        print(f"[risk-scan] Output: {out_file} (overall_risk=UNKNOWN)")
        return  # exit 0, non-blocking

    collab_snippet = _read_collab_tail(collab_log_dir)
    schema = (
        '{"agent":"risk-scanner","timestamp":"ISO8601","task_summary":"string",'
        '"risks":[{"level":"HIGH|MED|LOW","category":"scope|mece|convention|requirement|dependency|known_failure",'
        '"description":"string","affected_files":[],'
        '"recommendation":"ask_user|proceed_with_caution|proceed"}],'
        '"overall_risk":"HIGH|MED|LOW","proceed":true}'
    )
    prompt = (
        f"You are a pre-flight risk scanner. Analyze the task below and output ONLY a valid JSON "
        f"object with NO extra text or markdown fences. Schema: {schema}. "
        f"Use overall_risk=HIGH only if there is a critical scope conflict, MECE violation, "
        f"or a known failure pattern that directly matches this task. "
        f"TASK: {task}. FILES: {files}."
    )
    if collab_snippet:
        prompt += f" RECENT COLLAB LOG (last 20 lines - check for known failures): {collab_snippet}"

    print("[risk-scan] Calling Axis-I (Gemini risk assessment)...")
    result = gemini_call(prompt)

    if result.returncode != 0:
        print("[risk-scan] ERROR: Gemini call failed.")
        log_collab("Axis-I", "check-risk.py", "FAIL", "Error: Gemini call failed")
        write_unknown_json(out_file, task, "Gemini call failed")
        sys.exit(1)

    if is_refusal(result.stdout):
        log_collab("Axis-I", "check-risk.py", "REFUSED", "Gemini refused risk scan - proceeding with UNKNOWN")
        write_unknown_json(out_file, task, "Gemini refused - proceeding without risk scan")
        print("[risk-scan] Gemini refused. UNKNOWN result written (non-blocking).")
        return  # exit 0

    out_file.write_text(result.stdout, encoding="utf-8")
    save_raw("Axis-I", out_file)

    # Validate JSON
    try:
        import json
        j = json.loads(out_file.read_text(encoding="utf-8"))
        print(f"[risk-scan] overall_risk={j.get('overall_risk', '?')}")
    except Exception:
        print(f"[risk-scan] WARNING: Output is not valid JSON - check {out_file}")

    log_collab("Axis-I", "check-risk.py", "OK", f"Output: {out_file}")
    print(f"[risk-scan] Done. Output: {out_file}")
    archive_file("scan-risk", out_file)


if __name__ == "__main__":
    main()
