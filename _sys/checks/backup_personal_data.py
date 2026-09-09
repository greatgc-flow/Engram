"""backup_personal_data.py -- copy-based backup/restore for P:'s personal/durable data.

Context (see docs/reviews/p-drive-folder-structure-mece-review-2026-09-09.md
in the peerhub repo for the full investigation): personal/durable data on
this portable dev environment is scattered across 3 locations, and a real
physical reorganization of one of them (`_sys/ai/`) was found to risk
breaking `hub.py` (963 path references, no confirmed centralized
resolution point) -- too risky to attempt casually. This script is the
recommended safer alternative: it never moves or restructures anything at
the source, it only COPIES the confirmed-durable set into one consolidated
snapshot folder on backup, and copies back on restore. Zero risk to any
existing code's path assumptions.

What gets backed up:
  1. Claude Code's own memory system for this project
     (_sys/claude/config/projects/P--/memory/, ~196 files as of 2026-09-09)
     -- THE critical item. This is NEVER git-tracked (gitignored by
     Claude Code's own convention) and has zero backup otherwise.
  2. _sys/claude/config/{CLAUDE.md,settings.json} -- personal Claude Code
     preferences/settings. Already git-tracked (so already backed up via
     `git push`), bundled here anyway for a convenient, git-independent
     snapshot.
  3. _sys/ai/*.json and *.md (top-level files only, not subdirectories --
     subdirectories under _sys/ai/ hold either untracked runtime state or
     large domain-specific config not part of the "personal settings"
     concern) -- the durable AI-orchestration/backlog/protocol config.
     Also already git-tracked; bundled for the same convenience reason.

What is deliberately NEVER touched:
  - _sys/claude/config/.credentials.json and any other credential/secret
    file -- never bundled into a backup snapshot that might get copied,
    zipped, or shared. If you need to back up credentials, do that
    separately and deliberately, not as a side effect of running this.
  - Everything else under _sys/claude/config/ (history.jsonl, cache/,
    sessions/, telemetry/, etc.) and _sys/ai/'s untracked runtime files
    (ask_history.jsonl, leases.json, mailbox.json, nodes.json,
    routing_metrics.jsonl, state.json, task_registry.json) -- genuinely
    ephemeral/regeneratable, not personal data.

Usage:
    python _sys/checks/backup_personal_data.py --backup [--out PATH]
    python _sys/checks/backup_personal_data.py --restore PATH [--force]
    python _sys/checks/backup_personal_data.py --list PATH

--backup with no --out creates a fresh timestamped folder under
_sys/data/backups/personal-YYYYMMDD-HHMMSS/ (itself gitignored --
`_sys/data/` is already excluded from P:'s own git tracking).
--restore copies everything from an existing backup snapshot back to its
live location. Refuses to overwrite an existing live memory/ directory
unless --force is given (restoring is the one destructive direction here).
--list shows what a given backup snapshot folder actually contains,
without touching anything, so you can sanity-check before restoring.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# _sys/checks/ -> _sys/ -> P:\ (or wherever this script's real root is,
# resolved dynamically -- never hardcode a drive letter, matching this
# project's own portability convention).
_CHECKS_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

MEMORY_SRC = _SYS_DIR / "claude" / "config" / "projects" / "P--" / "memory"
CLAUDE_SETTINGS_SRC = _SYS_DIR / "claude" / "config"
CLAUDE_SETTINGS_FILES = ("CLAUDE.md", "settings.json")
AI_CONFIG_SRC = _SYS_DIR / "ai"

# _sys/ai/'s top level mixes durable, git-tracked config with untracked,
# purely-ephemeral runtime state in one flat directory (the exact mixing
# problem this script exists to work around, documented in the folder-
# structure MECE review). A bare "*.json" glob would silently re-mix them
# right back into the backup -- explicitly excluded by filename instead.
AI_CONFIG_RUNTIME_STATE_FILES = frozenset({
    "ask_history.jsonl", "leases.json", "mailbox.json", "nodes.json",
    "routing_metrics.jsonl", "state.json", "task_registry.json",
})

DEFAULT_BACKUP_ROOT = _SYS_DIR / "data" / "backups"


def _copy_ai_config_files(dest: Path) -> list[str]:
    """Copy only _sys/ai/'s top-level *.json and *.md files (not subdirs),
    excluding the known ephemeral runtime-state files by name.

    Subdirectories hold either untracked runtime state (ipc/, mailbox/,
    sessions/, snapshots/, consensus/, proposals/, common/, config/,
    knowledge/) or large domain config not part of this "personal
    settings" backup's scope -- never recursed into.
    """
    copied = []
    dest.mkdir(parents=True, exist_ok=True)
    for item in sorted(AI_CONFIG_SRC.iterdir()):
        if (
            item.is_file()
            and item.suffix in (".json", ".md")
            and item.name not in AI_CONFIG_RUNTIME_STATE_FILES
        ):
            shutil.copy2(item, dest / item.name)
            copied.append(item.name)
    return copied


def do_backup(out_dir: Path | None) -> Path:
    if out_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_dir = DEFAULT_BACKUP_ROOT / f"personal-{stamp}"
    out_dir = Path(out_dir).resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"Refusing to write into a non-empty directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Backing up to: {out_dir}\n")

    if MEMORY_SRC.is_dir():
        memory_dest = out_dir / "memory"
        shutil.copytree(MEMORY_SRC, memory_dest)
        count = sum(1 for _ in memory_dest.rglob("*") if _.is_file())
        print(f"  [OK] memory/       <- {MEMORY_SRC} ({count} files)")
    else:
        print(f"  [SKIP] memory/     source not found: {MEMORY_SRC}")

    settings_dest = out_dir / "claude-settings"
    settings_dest.mkdir(parents=True, exist_ok=True)
    settings_copied = []
    for name in CLAUDE_SETTINGS_FILES:
        src = CLAUDE_SETTINGS_SRC / name
        if src.is_file():
            shutil.copy2(src, settings_dest / name)
            settings_copied.append(name)
    if settings_copied:
        print(f"  [OK] claude-settings/  <- {', '.join(settings_copied)}")
    else:
        print(f"  [SKIP] claude-settings/  none of {CLAUDE_SETTINGS_FILES} found")

    ai_dest = out_dir / "ai-config"
    ai_copied = _copy_ai_config_files(ai_dest)
    print(f"  [OK] ai-config/    <- {len(ai_copied)} files from {AI_CONFIG_SRC} (top-level only)")

    manifest = out_dir / "MANIFEST.txt"
    manifest.write_text(
        "backup_personal_data.py snapshot\n"
        f"created_at: {datetime.now(timezone.utc).isoformat()}\n"
        f"memory_files: {count if MEMORY_SRC.is_dir() else 0}\n"
        f"claude_settings_files: {settings_copied}\n"
        f"ai_config_files: {ai_copied}\n"
        "\n"
        "Deliberately excluded: .credentials.json and all other secrets,\n"
        "all ephemeral runtime state (session logs, caches, .jsonl queues).\n",
        encoding="utf-8",
    )
    print(f"\nDone. Manifest written to {manifest}")
    return out_dir


def do_restore(src_dir: Path, force: bool) -> None:
    src_dir = Path(src_dir).resolve()
    if not src_dir.is_dir():
        raise SystemExit(f"Not a directory: {src_dir}")

    memory_src = src_dir / "memory"
    if memory_src.is_dir():
        if MEMORY_SRC.exists() and not force:
            raise SystemExit(
                f"Refusing to overwrite existing {MEMORY_SRC} without --force."
            )
        if MEMORY_SRC.exists():
            shutil.rmtree(MEMORY_SRC)
        MEMORY_SRC.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(memory_src, MEMORY_SRC)
        print(f"  [OK] restored memory/ -> {MEMORY_SRC}")
    else:
        print(f"  [SKIP] no memory/ in backup {src_dir}")

    settings_src = src_dir / "claude-settings"
    if settings_src.is_dir():
        for item in settings_src.iterdir():
            if item.is_file():
                shutil.copy2(item, CLAUDE_SETTINGS_SRC / item.name)
        print(f"  [OK] restored claude-settings/ -> {CLAUDE_SETTINGS_SRC}")

    ai_src = src_dir / "ai-config"
    if ai_src.is_dir():
        for item in ai_src.iterdir():
            if item.is_file():
                shutil.copy2(item, AI_CONFIG_SRC / item.name)
        print(f"  [OK] restored ai-config/ -> {AI_CONFIG_SRC}")

    print("\nDone.")


def do_list(src_dir: Path) -> None:
    src_dir = Path(src_dir).resolve()
    if not src_dir.is_dir():
        raise SystemExit(f"Not a directory: {src_dir}")
    manifest = src_dir / "MANIFEST.txt"
    if manifest.is_file():
        print(manifest.read_text(encoding="utf-8"))
    else:
        print(f"(no MANIFEST.txt found in {src_dir}, listing raw contents)")
        for item in sorted(src_dir.rglob("*")):
            if item.is_file():
                print(f"  {item.relative_to(src_dir)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backup", action="store_true", help="Create a new backup snapshot")
    group.add_argument("--restore", metavar="PATH", help="Restore from an existing backup snapshot")
    group.add_argument("--list", metavar="PATH", help="Show what a backup snapshot contains")
    parser.add_argument("--out", metavar="PATH", help="Output directory for --backup (default: timestamped, under _sys/data/backups/)")
    parser.add_argument("--force", action="store_true", help="With --restore, overwrite an existing live memory/ directory")
    args = parser.parse_args(argv)

    if args.backup:
        do_backup(Path(args.out) if args.out else None)
    elif args.restore:
        do_restore(Path(args.restore), args.force)
    elif args.list:
        do_list(Path(args.list))
    return 0


if __name__ == "__main__":
    sys.exit(main())
