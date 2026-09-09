"""One-off migration: the `.ais/` prototype -> the real `.engram/` dotdir.

Item 7 (dotdir consolidation, ratified 2026-09-09, Engram P1): `.ais/` was
this session's first prototype for consolidating AI-CLI personal/durable
settings (D:\\tttt). Item 6 made `.engram/` (env.json-driven, automatic)
the real, permanent mechanism. This script moves an existing `.ais/`
install over to it -- once, explicitly, never automatically from
`launcher.py` (a real launch must never silently rename a directory out
from under whatever else might be reading it).

The one thing this script gets carefully right: `.ais/` plays TWO
different roles depending on how it was used, and treating one as the
other is silent data loss.

  - If `.ais/MANIFEST.txt` exists, `.ais/` is a SNAPSHOT written by
    `backup_personal_data.py --backup` -- a copy taken FROM a separate
    live root, not the live root itself. Moving a snapshot's stale
    content over a genuinely live `.engram/` would silently overwrite
    newer, real state with an old copy. Refused outright.
  - If `.ais/MANIFEST.txt` is absent, `.ais/` IS the live root (D:\\tttt's
    actual case, once its 3 AI CLIs were redirected to read/write there
    directly) -- eligible to move.

Usage:
    python _sys/core/migrate_ais_to_engram.py --base-dir PATH [--apply]

Default is `--dry-run` (report only, mutate nothing). Pass `--apply` to
actually perform the move.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provisioner import _is_peer_leased  # noqa: E402  (private, deliberate reuse -- see module docstring)

# Filenames that look like vendor credentials -- never silently unremarked
# during a move. `.ais/` should never have held these (backup_personal_data.py
# excludes them by construction), but a genuinely-live `.ais/` root at
# D:\tttt DOES accumulate real auth state once redirected there for real
# use, so this is a visibility guard (loudly reported), not a block --
# blocking would defeat the actual point of moving a live root.
_CREDENTIAL_SHAPED_NAMES = frozenset({
    "auth.json", ".credentials.json", "credentials.json", "token.json",
    "hosts.yml",
})


class MigrationRefused(RuntimeError):
    """Raised when migration must not proceed; the message is user-facing."""


def _find_credential_shaped_files(root: Path) -> list[Path]:
    found = []
    for path in root.rglob("*"):
        if path.is_file() and path.name.lower() in _CREDENTIAL_SHAPED_NAMES:
            found.append(path)
    return found


def plan_migration(base_dir: Path, sys_dir: Path) -> dict:
    """Determine what migration (if any) is possible. Never mutates."""

    ais_dir = base_dir / ".ais"
    engram_dir = base_dir / ".engram"

    if not ais_dir.is_dir():
        return {"action": "noop", "reason": f"{ais_dir} does not exist -- nothing to migrate"}

    if (ais_dir / "MANIFEST.txt").is_file():
        raise MigrationRefused(
            f"{ais_dir} is a backup SNAPSHOT (MANIFEST.txt present), not a "
            f"live root -- refusing to move it over {engram_dir}. If you "
            f"want to restore its content, use backup_personal_data.py's "
            f"--restore instead, pointed at the real live locations."
        )

    # A top-level-only any(iterdir()) would wrongly count build_env()'s own
    # idempotently-created empty subdirs (.engram/claude/ etc., item 6) as
    # "real content" -- recurse to actual files.
    engram_has_real_content = engram_dir.is_dir() and any(
        p.is_file() for p in engram_dir.rglob("*")
    )
    if engram_has_real_content:
        raise MigrationRefused(
            f"Both {ais_dir} (live root) and {engram_dir} already have "
            f"real content -- refusing to guess which one wins. Resolve "
            f"the conflict manually (inspect both, decide, then re-run)."
        )

    for tool in ("claude", "codex", "ag"):
        if _is_peer_leased(sys_dir, tool):
            raise MigrationRefused(
                f"{tool} appears to be running against this install -- "
                f"refusing to move files out from under a live process. "
                f"Close it and re-run."
            )

    credential_shaped = _find_credential_shaped_files(ais_dir)

    return {
        "action": "move",
        "source": ais_dir,
        "destination": engram_dir,
        "credential_shaped_files": [str(p) for p in credential_shaped],
    }


def apply_migration(plan: dict) -> None:
    """Execute a plan produced by plan_migration(). Move, never copy."""

    if plan["action"] != "move":
        return
    source: Path = plan["source"]
    destination: Path = plan["destination"]
    if destination.exists():
        # plan_migration already refused a destination with real (file)
        # content; what's left here is at most build_env()'s own
        # idempotently-created empty subdirs (item 6) -- safe to clear so
        # shutil.move() can rename cleanly onto it. rmtree, not rmdir:
        # those subdirs make the top-level dir non-empty even with zero
        # actual files inside.
        shutil.rmtree(destination)
    shutil.move(str(source), str(destination))

    ais_env_bat = source.parent / "ais-env.bat"
    if ais_env_bat.is_file():
        ais_env_bat.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").splitlines()[0]
    )
    parser.add_argument("--base-dir", required=True, help="Portable root (contains .ais/, .engram/, _sys/)")
    parser.add_argument("--apply", action="store_true", help="Actually perform the move (default: dry-run report only)")
    args = parser.parse_args(argv)

    base_dir = Path(args.base_dir).resolve()
    sys_dir = base_dir / "_sys"

    try:
        plan = plan_migration(base_dir, sys_dir)
    except MigrationRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    if plan["action"] == "noop":
        print(plan["reason"])
        return 0

    print(f"Plan: move {plan['source']} -> {plan['destination']}")
    if plan["credential_shaped_files"]:
        print("Credential-shaped files included in this move (reported, not blocked):")
        for name in plan["credential_shaped_files"]:
            print(f"  {name}")

    if not args.apply:
        print("Dry run only -- pass --apply to actually perform this move.")
        return 0

    apply_migration(plan)
    print(f"Moved {plan['source']} -> {plan['destination']}. Removed ais-env.bat if present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
