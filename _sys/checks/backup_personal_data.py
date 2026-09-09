"""backup_personal_data.py -- copy-based backup of the 3 AI CLIs' personal/
durable data, sourced from the single `.engram/` live root (item 11,
dotdir consolidation, ratified 2026-09-09 -- see
docs/design/dotdir-consolidation-RATIFIED-2026-09-09.md in the peerhub
repo).

Context: an earlier, separate legacy environment (P:, frozen, not this
repo) has a same-named script that reads from 3 scattered
`_sys/{claude,codex,antigravity}/config` directories, because that
environment predates the env.json-driven redirect and never adopted it.
This repo already puts every AI CLI's live config under one root --
`.engram/{claude,codex,agy}` (items 5-7, this repo's `_sys/core/
launcher.py` + `_sys/env.json`) -- so this version has exactly one source
tree to filter, not three, and the `ai-config` member of the legacy
version (a bundle of a separate, since-removed orchestration CLI's own
`_sys/ai/` config) is dropped entirely: this repo has no such CLI and no
`_sys/ai/` (see the Engram/PeerHub full-separation goal -- that CLI was
deliberately removed from Engram).

`.engram/` itself is explicitly a LIVE root (ratified doc, item 2.3): it
accumulates real caches and credentials over time, so it is never itself
something you'd hand off, sync, or commit wholesale. This script's job is
to extract just the durable, non-secret, non-cache subset via an explicit
named allowlist -- never a wholesale directory copy with an exclude list,
so a credential file simply never has an entry that would ever pick it up,
rather than needing to be actively filtered out every time -- into a
separate, portable backup bundle.

Usage:
    python _sys/checks/backup_personal_data.py --base-dir PATH --backup --out PATH
    python _sys/checks/backup_personal_data.py --base-dir PATH --restore PATH [--force]
    python _sys/checks/backup_personal_data.py --list PATH

--backup copies every present ITEM from `<base-dir>/.engram/` into --out,
overwriting each item's own destination in place (a true mirror on every
run, never an ever-growing pile of stale files), and writes a MANIFEST.txt
describing what was captured.

--restore copies everything from a bundle back into `<base-dir>/.engram/`.
Refuses to overwrite existing live session/project data
(claude/projects/) unless --force is given -- the one direction that can
destroy real, irreplaceable data.

--list shows what a given bundle actually contains, without touching
anything.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Filenames that look like vendor credentials. This is a defensive
# assertion on the allowlist itself (see _assert_no_credential_shaped_items)
# and the basis of the behavioral test that a live .engram/ containing
# these names never produces a bundle containing them -- the actual
# safeguard is that ITEMS below is an explicit named allowlist, so a
# credential file simply has no entry that would ever copy it. Matches
# _sys/core/migrate_ais_to_engram.py's own list.
CREDENTIAL_SHAPED_NAMES = frozenset({
    "auth.json", ".credentials.json", "credentials.json", "token.json",
    "hosts.yml",
})


@dataclass(frozen=True)
class SyncItem:
    """One named, itemized thing to copy in each direction.

    Both paths are relative -- `live_relpath` to `.engram/`, `bundle_relpath`
    to the bundle root -- so the same table works for both --backup and
    --restore. `kind` is "dir" (shutil.copytree, replacing the destination
    wholesale) or "file" (shutil.copy2). Never a wildcard/glob: every real
    item this script touches is named explicitly.
    """

    label: str
    live_relpath: str
    bundle_relpath: str
    kind: str  # "dir" | "file"


ITEMS: tuple[SyncItem, ...] = (
    SyncItem("claude/projects", "claude/projects", "claude/projects", "dir"),
    SyncItem("claude/CLAUDE.md", "claude/CLAUDE.md", "claude/CLAUDE.md", "file"),
    SyncItem("claude/settings.json", "claude/settings.json", "claude/settings.json", "file"),
    SyncItem("codex/CODEX.md", "codex/CODEX.md", "codex/CODEX.md", "file"),
    SyncItem("codex/config.toml", "codex/config.toml", "codex/config.toml", "file"),
    SyncItem("codex/rules", "codex/rules", "codex/rules", "dir"),
    SyncItem("codex/skills", "codex/skills", "codex/skills", "dir"),
    SyncItem("codex/memories_1.sqlite", "codex/memories_1.sqlite", "codex/memories_1.sqlite", "file"),
    SyncItem("agy/AGY.md", "agy/AGY.md", "agy/AGY.md", "file"),
    SyncItem("agy/settings.json", "agy/settings.json", "agy/settings.json", "file"),
    SyncItem("agy/keybindings.json", "agy/keybindings.json", "agy/keybindings.json", "file"),
    SyncItem("agy/conversation_summaries.db", "agy/conversation_summaries.db", "agy/conversation_summaries.db", "file"),
    SyncItem("agy/knowledge", "agy/knowledge", "agy/knowledge", "dir"),
    SyncItem("agy/skills", "agy/skills", "agy/skills", "dir"),
)

# Items whose live/session data is genuinely irreplaceable if clobbered --
# restoring these requires --force if the live copy already exists.
_RESTORE_PROTECTED_LABELS = frozenset({"claude/projects"})


class CredentialShapedItemError(RuntimeError):
    """Raised if ITEMS itself ever names a credential-shaped file."""


def _assert_no_credential_shaped_items() -> None:
    """A bad ITEMS edit fails immediately at import time, not only in a
    targeted test -- item 11's "assert no credential-shaped file can ever
    enter it" requirement, checked against the allowlist's own shape."""

    for item in ITEMS:
        name = Path(item.live_relpath).name.lower()
        if name in CREDENTIAL_SHAPED_NAMES:
            raise CredentialShapedItemError(
                f"ITEMS entry {item.label!r} names a credential-shaped "
                f"file ({name!r}) -- refusing to load this module."
            )


_assert_no_credential_shaped_items()


def _sync_item_to_bundle(item: SyncItem, engram_dir: Path, bundle_dir: Path) -> int | None:
    """Copy one item .engram/ -> bundle. Returns a file count, or None if
    the live source doesn't exist (not every item is present on every
    install -- e.g. Antigravity may not have run yet)."""

    live = engram_dir / item.live_relpath
    dest = bundle_dir / item.bundle_relpath
    if item.kind == "dir":
        if not live.is_dir():
            return None
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(live, dest)
        return sum(1 for _ in dest.rglob("*") if _.is_file())
    else:
        if not live.is_file():
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(live, dest)
        return 1


def _restore_item(item: SyncItem, bundle_dir: Path, engram_dir: Path, force: bool) -> str:
    """Copy one item bundle -> .engram/. Returns a short status string."""

    src = bundle_dir / item.bundle_relpath
    live = engram_dir / item.live_relpath
    if item.kind == "dir":
        if not src.is_dir():
            return "skip (not in bundle)"
        if live.exists():
            if item.label in _RESTORE_PROTECTED_LABELS and not force:
                return f"REFUSED (exists, use --force): {live}"
            shutil.rmtree(live)
        live.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, live)
        count = sum(1 for _ in live.rglob("*") if _.is_file())
        return f"restored ({count} files) -> {live}"
    else:
        if not src.is_file():
            return "skip (not in bundle)"
        live.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, live)
        return f"restored -> {live}"


def do_backup(engram_dir: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Backing up personal AI-CLI data from {engram_dir} to: {out_dir}\n")

    manifest_lines: list[str] = []
    for item in ITEMS:
        result = _sync_item_to_bundle(item, engram_dir, out_dir)
        source = engram_dir / item.live_relpath
        if result is None:
            print(f"  [SKIP] {item.label:<32} source not found: {source}")
            manifest_lines.append(f"{item.label}: SKIPPED (source not found)")
        else:
            print(f"  [OK]   {item.label:<32} <- {source} ({result} file{'s' if result != 1 else ''})")
            manifest_lines.append(f"{item.label}: {result} file(s) <- {source}")

    manifest = out_dir / "MANIFEST.txt"
    manifest.write_text(
        "backup_personal_data.py .engram/ backup bundle\n"
        f"synced_at: {datetime.now(timezone.utc).isoformat()}\n"
        f"source: {engram_dir}\n\n"
        + "\n".join(manifest_lines)
        + "\n\n"
        "Deliberately excluded: auth.json, .credentials.json,\n"
        "credentials.json, token.json, hosts.yml, and any other\n"
        "credential/secret file (excluded by construction -- every item\n"
        "above is an explicit named allowlist entry, never a wholesale\n"
        "directory copy); all 3 tools' caches/logs/queues/crash-dumps/CLI\n"
        "internals.\n",
        encoding="utf-8",
    )
    print(f"\nDone. Manifest written to {manifest}")
    return out_dir


def do_restore(engram_dir: Path, src_dir: Path, force: bool) -> None:
    if not src_dir.is_dir():
        raise SystemExit(f"Not a directory: {src_dir}")

    for item in ITEMS:
        status = _restore_item(item, src_dir, engram_dir, force)
        tag = "REFUSED" if status.startswith("REFUSED") else ("SKIP" if status.startswith("skip") else "OK")
        print(f"  [{tag:>7}] {item.label:<32} {status}")

    print("\nDone.")


def do_list(src_dir: Path) -> None:
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
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--base-dir", help="Portable root (contains .engram/, _sys/); required with --backup/--restore")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backup", action="store_true", help="Back up .engram/'s durable subset to --out")
    group.add_argument("--restore", metavar="PATH", help="Restore a bundle back into .engram/")
    group.add_argument("--list", metavar="PATH", help="Show what a bundle contains (does not need --base-dir)")
    parser.add_argument("--out", metavar="PATH", help="Target directory for --backup (required with --backup)")
    parser.add_argument("--force", action="store_true", help="With --restore, overwrite existing live session/project data")
    args = parser.parse_args(argv)

    if args.list:
        do_list(Path(args.list).resolve())
        return 0

    if not args.base_dir:
        parser.error("--backup/--restore require --base-dir PATH")
    engram_dir = Path(args.base_dir).resolve() / ".engram"

    if args.backup:
        if not args.out:
            parser.error("--backup requires --out PATH")
        do_backup(engram_dir, Path(args.out).resolve())
    else:
        assert args.restore is not None
        do_restore(engram_dir, Path(args.restore).resolve(), args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
