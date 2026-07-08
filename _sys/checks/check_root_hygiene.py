"""check_root_hygiene.py — validates the repository root against a strict allowlist.

Validates:
  - Immediate children of the repo root are strictly known.
  - In --closure mode, additionally ensures working tree is clean via git, and the backlog is clean.

Exit codes:
  0 on success
  2 on validation errors
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent
PORTABLE_ROOT = SYS_DIR.parent

ALLOWLIST = {
    ".agents",
    ".ai",
    ".claude",
    ".git",
    ".gitattributes",
    ".gitignore",
    ".pytest_cache",
    ".vscode",
    "_archive",
    "_sys",
    "AGENTS.md",
    "CLAUDE.md",
    "CLEANUP.bat",
    "CONVENTION.md",
    "Engram.exe",
    "GEMINI.md",
    "INSTALL.bat",
    "PROTOCOL.md",
    "README.md",
    "register.bat",
    "tmp",
    "unregister.bat",
    "workspace",
    "wrapper.cs"
}

def check_root() -> list[str]:
    errors = []

    if not PORTABLE_ROOT.exists():
        return ["Repository root not found."]

    for child in PORTABLE_ROOT.iterdir():
        if child.name not in ALLOWLIST:
            errors.append(f"Unexpected entry at root: {child.name}")

    return errors

def check_closure() -> list[str]:
    errors = []

    # 1. git status --short
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(PORTABLE_ROOT),
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            errors.append(f"git status failed: {proc.stderr.strip()}")
        elif proc.stdout.strip():
            errors.append(f"git working tree not clean:\n{proc.stdout.strip()}")
    except OSError as e:
        errors.append(f"Failed to run git status: {e}")

    # 2. git diff --check
    try:
        proc = subprocess.run(
            ["git", "diff", "--check"],
            cwd=str(PORTABLE_ROOT),
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            errors.append(f"git diff --check found whitespace errors or failed:\n{proc.stdout.strip()}")
    except OSError as e:
        errors.append(f"Failed to run git diff --check: {e}")

    # 3. check_backlog
    # Let's import it to call check_backlog(live=True)
    try:
        # dynamically add to path if needed, though we are in the same dir
        if str(SYS_DIR / "checks") not in sys.path:
            sys.path.insert(0, str(SYS_DIR / "checks"))
        from check_backlog import check_backlog
        backlog_errors = check_backlog(live=True)
        errors.extend(backlog_errors)
    except Exception as e:
        errors.append(f"Failed to run check_backlog: {e}")

    return errors

def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    closure = "--closure" in argv

    print(f"[CHK-ROOT] Validating root hygiene...")
    errors = check_root()

    if closure:
        print("[CHK-ROOT] Validating closure (git status, git diff --check, backlog)...")
        errors.extend(check_closure())

    if errors:
        print("[CHK-ROOT] Validation failed:")
        for err in errors:
            lines = err.split("\n")
            print(f"  - {lines[0]}")
            for line in lines[1:]:
                print(f"    {line}")
        return 2

    print("[CHK-ROOT] OK. Root is clean" + (" and closure is verified." if closure else "."))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
