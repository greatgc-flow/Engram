"""ctx_save.py — Local session checkpoint.

Stamps a "Last checkpoint" marker into the project's context files
(CLAUDE.md, GEMINI.md, AGENTS.md) so a later session can see when the
last save happened.

Deliberately local and deterministic: peer coordination (blackboard
summaries, consensus sweeps, cross-peer messaging) is not Engram's
concern -- that belongs to the separately-installed `peerhub` package.
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_SYS_DIR = _SCRIPT_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent


def _update_current_state_marker(md_file: Path, marker: str) -> bool:
    """Replace the first line after '## Current State' with marker."""
    try:
        content = md_file.read_text(encoding="utf-8")
        updated = re.sub(
            r"(## Current State\r?\n)[^\r\n]*",
            lambda m: m.group(1) + marker,
            content,
        )
        if updated != content:
            md_file.write_text(updated, encoding="utf-8")
        return True
    except Exception:
        return False


def main() -> None:
    cwd = Path.cwd()
    claude_md = cwd / "CLAUDE.md"
    if not claude_md.exists():
        print(f"[ctx-save] ERROR: No CLAUDE.md in: {cwd}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now()
    ts_readable = now.strftime("%Y-%m-%d %H:%M")
    marker = f"Last checkpoint: {ts_readable}"

    print(f"[ctx-save] Checkpointing: {cwd}")

    if not _update_current_state_marker(claude_md, marker):
        print("[ctx-save] WARNING: Failed to update marker in CLAUDE.md", file=sys.stderr)

    gemini_md = Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "GEMINI.md"
    if gemini_md.exists():
        if _update_current_state_marker(gemini_md, marker):
            print("[ctx-save] Symmetric Memory updated: CLAUDE.md & GEMINI.md")
    else:
        print("[ctx-save] Notice: GEMINI.md not found at junction. Updated CLAUDE.md only.")

    agents_md = cwd / "AGENTS.md"
    if agents_md.exists():
        if _update_current_state_marker(agents_md, marker):
            print("[ctx-save] Symmetric Memory updated: AGENTS.md (cx session continuity)")

    print("[ctx-save] Checkpoint complete.")


if __name__ == "__main__":
    main()
