"""raw_log.py — Save raw Gemini I/O to _archive/raw-log/ (replaces raw-log.bat).

Usage: python raw_log.py <AXIS> <RESPONSE_FILE> [DIRECTIVE_FILE]
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path


def save_raw(axis: str, response_file: Path, directive_file: Path | None = None) -> None:
    """Copy Gemini response and optional directive to timestamped archive files."""
    base_dir = Path(__file__).parent.parent.parent
    raw_dir = base_dir / "_archive" / "raw-log"
    raw_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d%H%M%S")

    if response_file.exists():
        shutil.copy2(response_file, raw_dir / f"{ts}_{axis}_response.txt")

    if directive_file and directive_file.exists():
        shutil.copy2(directive_file, raw_dir / f"{ts}_{axis}_directive.txt")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: raw_log.py <AXIS> <RESPONSE_FILE> [DIRECTIVE_FILE]", file=sys.stderr)
        sys.exit(1)

    axis = sys.argv[1]
    response_file = Path(sys.argv[2])
    directive_file = Path(sys.argv[3]) if len(sys.argv) >= 4 else None

    save_raw(axis, response_file, directive_file)


if __name__ == "__main__":
    main()
