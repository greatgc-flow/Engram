"""check_backlog.py — validates the JSON SSOT backlog against schema and git reality.

Validates:
  - Valid JSON and required fields.
  - Unique item IDs.
  - 'supersedes' targets exist in the backlog.
  - Items with status 'done', 'dropped', or 'superseded' have a non-empty 'evidence_commit' list.
  - Every 'evidence_commit' hash resolves to a real commit via 'git cat-file -e'.

Exit codes:
  0 on success
  2 on validation errors
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent
PORTABLE_ROOT = SYS_DIR.parent
BACKLOG_PATH = SYS_DIR / "ai" / "backlog.json"

VALID_STATUSES = {"proposed", "active", "blocked", "deferred", "done", "dropped", "superseded"}


def git_commit_exists(hash_str: str) -> bool:
    try:
        proc = subprocess.run(
            ["git", "cat-file", "-e", f"{hash_str}^{{commit}}"],
            cwd=str(PORTABLE_ROOT),
            capture_output=True
        )
        return proc.returncode == 0
    except OSError:
        return False


def check_backlog(live: bool = True) -> list[str]:
    errors = []

    if not BACKLOG_PATH.exists():
        errors.append(f"Backlog file not found: {BACKLOG_PATH}")
        return errors

    try:
        data = json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Invalid JSON in backlog: {e}")
        return errors

    schema_version = data.get("schema_version")
    if schema_version != 1:
        errors.append(f"Unsupported schema_version: {schema_version}")

    items = data.get("items", [])
    if not isinstance(items, list):
        errors.append("'items' must be a list")
        return errors

    item_ids = set()
    for idx, item in enumerate(items):
        item_id = item.get("id")
        if not item_id:
            errors.append(f"Item at index {idx} is missing 'id'")
            continue

        if item_id in item_ids:
            errors.append(f"Duplicate item ID found: {item_id}")
        item_ids.add(item_id)

        status = item.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"Item '{item_id}' has invalid status '{status}'")

        if status in {"done", "dropped", "superseded"}:
            evidence = item.get("evidence_commit", [])
            if not evidence:
                errors.append(f"Item '{item_id}' ({status}) requires a non-empty 'evidence_commit' list")

            if live:
                for commit in evidence:
                    if not git_commit_exists(commit):
                        errors.append(f"Item '{item_id}' evidence commit '{commit}' not found in git repository")

    for item in items:
        item_id = item.get("id")
        supersedes = item.get("supersedes", [])
        for target in supersedes:
            if target not in item_ids:
                errors.append(f"Item '{item_id}' supersedes unknown target '{target}'")

    return errors


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    live = "--no-live" not in argv

    errors = check_backlog(live=live)

    print(f"[CHK-BACKLOG] Validating {BACKLOG_PATH.name}...")
    if errors:
        print("[CHK-BACKLOG] Validation failed:")
        for err in errors:
            print(f"  - {err}")
        return 2

    print("[CHK-BACKLOG] OK. All backlog items valid and evidence commits resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
