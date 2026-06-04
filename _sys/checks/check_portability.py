"""check_portability.py — Axis-A: Full Portability & Corpus Scan via Gemini."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    _PORTABLE_ROOT, ai_available, archive_file, gemini_call, is_refusal,
    log_collab, write_unknown_json,
)


def main() -> None:
    archive_dir = _PORTABLE_ROOT / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    out_file = archive_dir / "portability-audit.json"

    print("[portability-scan] Starting Axis-A Full Audit...")

    if not ai_available():
        print("[portability-scan] Gemini is OFF. Performing basic structural audit...")
        write_unknown_json(out_file, "", "Gemini OFF - Basic scan only")
        log_collab("Axis-A", "check-portability.py", "REFUSED", "Gemini OFF - Basic scan only")
        print(f"[portability-scan] Audit complete. Report saved to: {out_file}")
        return

    print("[portability-scan] Gemini is ON. Performing deep corpus scan...")
    result = gemini_call(
        "Analyze the entire codebase for portability issues (hardcoded paths, "
        "environment dependencies, MECE violations). Output a structured JSON report."
    )

    if result.returncode != 0:
        print("[portability-scan] ERROR: Gemini scan failed.")
        log_collab("Axis-A", "check-portability.py", "FAIL", "Error: Gemini scan failed")
        sys.exit(1)

    if is_refusal(result.stdout):
        log_collab("Axis-A", "check-portability.py", "REFUSED", "Gemini refused request")
        sys.exit(1)

    out_file.write_text(result.stdout, encoding="utf-8")
    log_collab("Axis-A", "check-portability.py", "OK", f"Output: {out_file}")
    print(f"[portability-scan] Audit complete. Report saved to: {out_file}")


if __name__ == "__main__":
    main()
