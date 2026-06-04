"""git_draft.py — Axis-G: Generate conventional commit message draft via Gemini.

Usage: python git_draft.py [--staged]
"""
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "checks"))
from _common import (  # noqa: E402
    _PORTABLE_ROOT, ai_available, gemini_call, is_refusal,
    log_collab, save_raw, update_status_error,
)

import tempfile


def _get_diff(root: Path, staged: bool) -> str:
    mode = "--staged" if staged else "HEAD"
    result = subprocess.run(
        ["git", "-C", str(root), "diff", mode],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def main() -> None:
    staged = "--staged" in sys.argv
    dt = datetime.now().strftime("%Y%m%d%H%M%S")

    if not ai_available():
        print("[git-draft] ERROR: Gemini not available.")
        print("            Run start.bat first, or check _sys\\gemini\\status.json")
        sys.exit(1)

    if not shutil.which("git"):
        print("[git-draft] ERROR: git not found in PATH. Run from sandbox terminal.")
        sys.exit(1)

    diff_content = _get_diff(_PORTABLE_ROOT, staged)
    if not diff_content.strip():
        mode_label = "--staged" if staged else "HEAD"
        print(f"[git-draft] No changes detected (git diff {mode_label} is empty).")
        return

    print("[git-draft] Generating commit message draft...")

    prompt = (
        "Read the git diff and write a conventional commit message. "
        "Format: type(scope): subject. "
        "Body (optional, 1-3 bullets of what/why). "
        "Rules: type is feat, fix, docs, refactor, chore, test, or style. "
        "Subject max 72 chars. English only, imperative mood. "
        "Output ONLY the commit message, nothing else.\n\n"
        + diff_content
    )

    result = gemini_call(prompt, stdin=diff_content)

    if result.returncode != 0:
        print("[git-draft] ERROR: gemini returned non-zero. Check auth or network.")
        log_collab("Axis-G", "git-draft.py", "FAIL", "Error: api_error")
        update_status_error(dt, "git_draft_failed")
        sys.exit(1)

    if is_refusal(result.stdout):
        log_collab("Axis-G", "git-draft.py", "REFUSED", "Gemini refused request")
        sys.exit(1)

    # Write to temp file for raw-log, then print
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False,
        encoding="utf-8", prefix="git-draft-out-",
    ) as f:
        f.write(result.stdout)
        out_path = Path(f.name)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False,
        encoding="utf-8", prefix="git-draft-diff-",
    ) as f:
        f.write(diff_content)
        diff_path = Path(f.name)

    print(result.stdout)
    save_raw("Axis-G", out_path, diff_path)
    out_path.unlink(missing_ok=True)
    diff_path.unlink(missing_ok=True)

    log_collab("Axis-G", "git-draft.py", "OK", "Output: console (commit draft)")
    print()
    print("[git-draft] Review and edit before committing. This is a draft only.")


if __name__ == "__main__":
    main()
