"""ai_check.py — Gemini availability gate check (replaces ai-check.bat)."""
import json
import os
import sys
from pathlib import Path


def main() -> None:
    override = os.environ.get("_AI_SYS_DIR")
    sys_dir = Path(override) if override else Path(__file__).parent.parent
    status_path = sys_dir / "gemini" / "status.json"
    if status_path.exists():
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
            if data.get("mode") == "ON":
                print("[GATE] gemini=ON")
                sys.exit(0)
        except Exception:
            pass
    print("[GATE] gemini=OFF")
    sys.exit(1)


if __name__ == "__main__":
    main()
