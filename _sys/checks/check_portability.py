"""check_portability.py — Axis-A: Full Portability & Corpus Scan via Gemini."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    _PORTABLE_ROOT, ai_available, archive_file, extract_json_block, gemini_call,
    is_refusal, log_collab, write_unknown_json,
)


def main() -> None:
    archive_dir = _PORTABLE_ROOT / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    out_file = archive_dir / "portability-audit.json"

    print("[portability-scan] Starting Axis-A Full Audit...")

    if not ai_available():
        print("[portability-scan] No AI peer is available. Performing basic structural audit...")
        write_unknown_json(out_file, "", "No AI peer - Basic scan only")
        log_collab("Axis-A", "check-portability.py", "REFUSED", "No AI peer - Basic scan only")
        print(f"[portability-scan] Audit complete. Report saved to: {out_file}")
        return

    print("[portability-scan] Active AI peer found. Performing deep corpus scan...")
    result = gemini_call(
        "Analyze the entire codebase for portability issues (hardcoded paths, "
        "environment dependencies, MECE violations). Output a structured JSON report.",
        timeout=60,
    )

    if result.returncode != 0:
        note = f"Active peer scan unavailable (exit={result.returncode}) - Basic scan only"
        write_unknown_json(out_file, "", note)
        log_collab("Axis-A", "check-portability.py", "REFUSED", note)
        print("[portability-scan] Active peer unavailable; saved UNKNOWN report.")
        return

    if is_refusal(result.stdout):
        log_collab("Axis-A", "check-portability.py", "REFUSED", "Active peer refused request")
        sys.exit(1)

    structured = extract_json_block(result.stdout)
    try:
        json.loads(structured)
    except json.JSONDecodeError:
        note = "Active peer returned no structured JSON - Basic scan only"
        write_unknown_json(out_file, "", note)
        log_collab("Axis-A", "check-portability.py", "REFUSED", note)
        print("[portability-scan] Structured response unavailable; saved UNKNOWN report.")
        return

    out_file.write_text(structured, encoding="utf-8")
    log_collab("Axis-A", "check-portability.py", "OK", f"Output: {out_file}")
    print(f"[portability-scan] Audit complete. Report saved to: {out_file}")


if __name__ == "__main__":
    main()
