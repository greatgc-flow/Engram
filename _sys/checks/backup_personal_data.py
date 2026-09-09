"""backup_personal_data.py -- copy-based sync/restore for all 3 AI CLIs'
personal/durable data (Claude Code, Codex, Antigravity), consolidated
into one portable folder: `.ais/` at the portable root.

Context (see docs/reviews/p-drive-folder-structure-mece-review-2026-09-09.md
in the peerhub repo for the original investigation): personal/durable AI-CLI
data on this portable dev environment is scattered across 3 separate tool
config directories, and a physical reorganization of any of them was found
too risky to attempt on a live, in-use environment (`_sys/ai/`'s own reorg
alone was blocked on 963 hub.py path references). This script never moves
or restructures anything at the source -- it only COPIES the confirmed-
durable set into `.ais/` on `--backup`, and copies back out to each tool's
live config location on `--restore`. Zero risk to any existing code's path
assumptions; `.ais/` is a portable "shadow copy" alongside the live configs,
not a replacement for them.

Extended 2026-09-09 (originally Claude-Code-only) after moving a copy of
this environment to a second location (D:\\tttt) surfaced the same need
for Codex and Antigravity: each has its own memory/settings/rules that are
just as durable and just as un-backed-up as Claude Code's.

`.ais/` layout:
    .ais/
      MANIFEST.txt
      claude/
        projects/       <- ALL of _sys/claude/config/projects/ (every
                           workspace's session transcripts + memory/)
        CLAUDE.md
        settings.json
      codex/
        CODEX.md
        config.toml
        rules/
        skills/
        memories_1.sqlite
      agy/
        AGY.md
        settings.json
        keybindings.json
        conversation_summaries.db
        knowledge/
        skills/
      ai-config/        <- _sys/ai/'s top-level *.json/*.md (durable
                           orchestration/protocol config; historically
                           hub.py's domain -- see note below)

Every item above is copied by an explicit, itemized allowlist (see ITEMS
below) -- nothing is ever copied via a wholesale directory copy with an
exclude list, so a credential file simply never appears in this list
rather than needing to be actively filtered out every time. Confirmed
excluded by construction: `_sys/claude/config/.credentials.json`,
`_sys/codex/config/auth.json` (Antigravity has no equivalent credential
file at this config-dir level), all 3 tools' caches/logs/queues/crash
dumps/cli internals, and `_sys/ai/`'s untracked runtime-state files
(ask_history.jsonl, leases.json, mailbox.json, nodes.json,
routing_metrics.jsonl, state.json, task_registry.json).

Note on `ai-config/`: this is P:'s frozen `hub.py`'s own orchestration
config (protocol.json, orchestration.json, user-directives.md, etc.).
It is bundled here for reference/portability, but on a target environment
that doesn't also have hub.py (e.g. a fresh Engram+peerhub install), this
data currently has no live consumer -- peerhub does not read this format.
Restoring it is harmless (just files sitting in `_sys/ai/`) but won't by
itself make anything *do* anything on a hub.py-less target.

Usage:
    python _sys/checks/backup_personal_data.py --backup [--out PATH]
    python _sys/checks/backup_personal_data.py --restore PATH [--force]
    python _sys/checks/backup_personal_data.py --list PATH

--backup with no --out targets `.ais/` at the portable root directly
(creating it if absent) -- this is meant to be re-run to refresh a
standing `.ais/` folder, not to produce a fresh timestamped snapshot each
time (that was the old, Claude-Code-only behavior; pass --out to opt back
into a one-off timestamped location instead). Existing content under the
target is overwritten in place (each ITEM's own dest is removed and
re-copied fresh) so repeated runs stay a true mirror of the live source,
not an ever-growing pile of stale files.

--restore copies everything from an existing `.ais/`-shaped folder back to
each tool's live config location. Refuses to overwrite existing live
memory/session data (claude/projects/) unless --force is given -- this is
the one direction that can destroy real, irreplaceable data (a live
environment's own accumulated sessions).

--list shows what a given `.ais/`-shaped folder actually contains, without
touching anything.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# _sys/checks/ -> _sys/ -> the portable root (P:\, D:\tttt\, or wherever
# this script's real root is -- resolved dynamically, never hardcode a
# drive letter, matching this project's own portability convention).
_CHECKS_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

CLAUDE_CONFIG = _SYS_DIR / "claude" / "config"
CODEX_CONFIG = _SYS_DIR / "codex" / "config"
AGY_CONFIG = _SYS_DIR / "antigravity" / "config"
AI_CONFIG_SRC = _SYS_DIR / "ai"

DEFAULT_AIS_DIR = _PORTABLE_ROOT / ".ais"

# _sys/ai/'s top level mixes durable, git-tracked config with untracked,
# purely-ephemeral runtime state in one flat directory -- a bare "*.json"
# glob would silently re-mix them right back into the backup, so this is
# excluded by filename rather than by directory boundary (the one item
# below that still needs a filter, since it's a whole-directory scan
# rather than a named-file allowlist).
AI_CONFIG_RUNTIME_STATE_FILES = frozenset({
    "ask_history.jsonl", "leases.json", "mailbox.json", "nodes.json",
    "routing_metrics.jsonl", "state.json", "task_registry.json",
})


@dataclass(frozen=True)
class SyncItem:
    """One named, itemized thing to copy in each direction.

    `live` is the absolute source-of-truth path a tool actually reads/
    writes; `ais_relpath` is where its mirror lives under `.ais/`. `kind`
    is "dir" (shutil.copytree, replacing the destination wholesale) or
    "file" (shutil.copy2). Never a wildcard/glob -- every real item this
    script touches is named explicitly, here or in AI_CONFIG_RUNTIME_STATE_FILES's exclusion for the one directory-scan exception.
    """

    label: str
    live: Path
    ais_relpath: str
    kind: str  # "dir" | "file"


ITEMS: tuple[SyncItem, ...] = (
    SyncItem("claude/projects", CLAUDE_CONFIG / "projects", "claude/projects", "dir"),
    SyncItem("claude/CLAUDE.md", CLAUDE_CONFIG / "CLAUDE.md", "claude/CLAUDE.md", "file"),
    SyncItem("claude/settings.json", CLAUDE_CONFIG / "settings.json", "claude/settings.json", "file"),
    SyncItem("codex/CODEX.md", CODEX_CONFIG / "CODEX.md", "codex/CODEX.md", "file"),
    SyncItem("codex/config.toml", CODEX_CONFIG / "config.toml", "codex/config.toml", "file"),
    SyncItem("codex/rules", CODEX_CONFIG / "rules", "codex/rules", "dir"),
    SyncItem("codex/skills", CODEX_CONFIG / "skills", "codex/skills", "dir"),
    SyncItem("codex/memories_1.sqlite", CODEX_CONFIG / "memories_1.sqlite", "codex/memories_1.sqlite", "file"),
    SyncItem("agy/AGY.md", AGY_CONFIG / "AGY.md", "agy/AGY.md", "file"),
    SyncItem("agy/settings.json", AGY_CONFIG / "settings.json", "agy/settings.json", "file"),
    SyncItem("agy/keybindings.json", AGY_CONFIG / "keybindings.json", "agy/keybindings.json", "file"),
    SyncItem("agy/conversation_summaries.db", AGY_CONFIG / "conversation_summaries.db", "agy/conversation_summaries.db", "file"),
    SyncItem("agy/knowledge", AGY_CONFIG / "knowledge", "agy/knowledge", "dir"),
    SyncItem("agy/skills", AGY_CONFIG / "skills", "agy/skills", "dir"),
)

# Items whose live/session data is genuinely irreplaceable if clobbered --
# restoring these requires --force if the live copy already exists and
# has real content (as opposed to config/settings files, which are cheap
# to overwrite and re-edit).
_RESTORE_PROTECTED_LABELS = frozenset({"claude/projects"})


def _copy_ai_config_files(dest: Path) -> list[str]:
    """Copy only _sys/ai/'s top-level *.json and *.md files (not subdirs),
    excluding the known ephemeral runtime-state files by name. The one
    directory-scan exception in this script -- see module docstring.
    """
    copied = []
    dest.mkdir(parents=True, exist_ok=True)
    for existing in dest.iterdir():
        if existing.is_file():
            existing.unlink()
    for item in sorted(AI_CONFIG_SRC.iterdir()):
        if (
            item.is_file()
            and item.suffix in (".json", ".md")
            and item.name not in AI_CONFIG_RUNTIME_STATE_FILES
        ):
            shutil.copy2(item, dest / item.name)
            copied.append(item.name)
    return copied


def _sync_item_to_ais(item: SyncItem, ais_dir: Path) -> int | None:
    """Copy one item live -> .ais/. Returns a file count, or None if the
    live source doesn't exist (nothing to copy -- not every tool/item is
    present on every environment, e.g. Antigravity's config dir may not
    exist at all yet)."""
    dest = ais_dir / item.ais_relpath
    if item.kind == "dir":
        if not item.live.is_dir():
            return None
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(item.live, dest)
        return sum(1 for _ in dest.rglob("*") if _.is_file())
    else:
        if not item.live.is_file():
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.live, dest)
        return 1


def _restore_item(item: SyncItem, ais_dir: Path, force: bool) -> str:
    """Copy one item .ais/ -> live. Returns a short status string."""
    src = ais_dir / item.ais_relpath
    if item.kind == "dir":
        if not src.is_dir():
            return "skip (not in .ais/)"
        if item.live.exists():
            if item.label in _RESTORE_PROTECTED_LABELS and not force:
                return f"REFUSED (exists, use --force): {item.live}"
            shutil.rmtree(item.live)
        item.live.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, item.live)
        count = sum(1 for _ in item.live.rglob("*") if _.is_file())
        return f"restored ({count} files) -> {item.live}"
    else:
        if not src.is_file():
            return "skip (not in .ais/)"
        item.live.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, item.live)
        return f"restored -> {item.live}"


def do_backup(out_dir: Path | None) -> Path:
    ais_dir = Path(out_dir).resolve() if out_dir else DEFAULT_AIS_DIR
    ais_dir.mkdir(parents=True, exist_ok=True)

    print(f"Syncing personal AI-CLI data to: {ais_dir}\n")

    manifest_lines: list[str] = []
    for item in ITEMS:
        result = _sync_item_to_ais(item, ais_dir)
        if result is None:
            print(f"  [SKIP] {item.label:<32} source not found: {item.live}")
            manifest_lines.append(f"{item.label}: SKIPPED (source not found)")
        else:
            print(f"  [OK]   {item.label:<32} <- {item.live} ({result} file{'s' if result != 1 else ''})")
            manifest_lines.append(f"{item.label}: {result} file(s) <- {item.live}")

    ai_copied = _copy_ai_config_files(ais_dir / "ai-config")
    print(f"  [OK]   {'ai-config':<32} <- {AI_CONFIG_SRC} ({len(ai_copied)} files, top-level only)")
    manifest_lines.append(f"ai-config: {len(ai_copied)} file(s) <- {AI_CONFIG_SRC} ({', '.join(ai_copied)})")

    manifest = ais_dir / "MANIFEST.txt"
    manifest.write_text(
        "backup_personal_data.py .ais/ snapshot\n"
        f"synced_at: {datetime.now(timezone.utc).isoformat()}\n"
        f"portable_root: {_PORTABLE_ROOT}\n\n"
        + "\n".join(manifest_lines)
        + "\n\n"
        "Deliberately excluded: .credentials.json, auth.json, and any other\n"
        "credential/secret file (excluded by construction -- every item above\n"
        "is an explicit named allowlist entry, never a wholesale directory\n"
        "copy); all 3 tools' caches/logs/queues/crash-dumps/CLI internals;\n"
        "_sys/ai/'s untracked runtime-state files.\n",
        encoding="utf-8",
    )
    print(f"\nDone. Manifest written to {manifest}")
    return ais_dir


def do_restore(src_dir: Path, force: bool) -> None:
    src_dir = Path(src_dir).resolve()
    if not src_dir.is_dir():
        raise SystemExit(f"Not a directory: {src_dir}")

    for item in ITEMS:
        status = _restore_item(item, src_dir, force)
        tag = "REFUSED" if status.startswith("REFUSED") else ("SKIP" if status.startswith("skip") else "OK")
        print(f"  [{tag:>7}] {item.label:<32} {status}")

    ai_src = src_dir / "ai-config"
    if ai_src.is_dir():
        AI_CONFIG_SRC.mkdir(parents=True, exist_ok=True)
        for entry in ai_src.iterdir():
            if entry.is_file():
                shutil.copy2(entry, AI_CONFIG_SRC / entry.name)
        print(f"  [     OK] {'ai-config':<32} restored -> {AI_CONFIG_SRC}")
    else:
        print(f"  [   SKIP] {'ai-config':<32} skip (not in {src_dir})")

    print("\nDone.")


def do_list(src_dir: Path) -> None:
    src_dir = Path(src_dir).resolve()
    if not src_dir.is_dir():
        raise SystemExit(f"Not a directory: {src_dir}")
    manifest = src_dir / "MANIFEST.txt"
    if manifest.is_file():
        print(manifest.read_text(encoding="utf-8"))
    else:
        print(f"(no MANIFEST.txt found in {src_dir}, listing top-level contents)")
        for item in sorted(src_dir.iterdir()):
            print(f"  {item.name}{'/' if item.is_dir() else ''}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backup", action="store_true", help="Sync live data into .ais/ (or --out PATH)")
    group.add_argument("--restore", metavar="PATH", help="Restore from an .ais/-shaped folder back to live locations")
    group.add_argument("--list", metavar="PATH", help="Show what an .ais/-shaped folder contains")
    parser.add_argument("--out", metavar="PATH", help="Target directory for --backup (default: .ais/ at the portable root)")
    parser.add_argument("--force", action="store_true", help="With --restore, overwrite existing live session/project data")
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
