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
from datetime import datetime, timezone
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent
PORTABLE_ROOT = SYS_DIR.parent
BACKLOG_PATH = SYS_DIR / "ai" / "backlog.json"

VALID_STATUSES = {"proposed", "active", "blocked", "deferred", "done", "dropped", "superseded"}
OPEN_STATUSES = {"proposed", "active", "blocked", "deferred"}
CLOSED_STATUSES = {"done", "dropped", "superseded"}
# Verification-age thresholds (days) — a HUMAN policy (not a measured value): how
# long an OPEN item may go un-re-verified before F1 nudges a triage sweep.
OVERDUE_DAYS = {"proposed": 30, "active": 30, "blocked": 90, "deferred": 180}


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


def _parse_iso(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


_REPO_ROOTS = ("_sys/", "workspace/", "_archive/", ".ai/", "workspace-base/")


def _is_repo_path_ref(ref: str) -> bool:
    """A source_ref that is a REPO-ROOT-relative path we can reliably check on
    disk. Only refs starting with a known repo top-level dir qualify — a bare
    filename, a partial path (e.g. 'ops/foo.md', relative to some doc base), a
    URL, or free-form prose is 'unverifiable', NOT dangling (avoids false
    positives; cx/ag: don't scream 'missing' on a non-canonical ref)."""
    if not isinstance(ref, str) or "://" in ref or " " in ref.strip():
        return False
    path = ref.split("#", 1)[0].strip()
    return bool(path) and ".." not in path and path.startswith(_REPO_ROOTS)


def freshness_report(data: dict, now: datetime | None = None) -> tuple[list[dict], dict]:
    """READ-ONLY freshness signals (F1). Never mutates the backlog and never
    changes status. Returns (warnings, summary). All signals are advisory (WARN):
    a missing/ambiguous signal is NOT flagged (DIR-004 — don't guess 'stale')."""
    now = now or datetime.now(timezone.utc)
    items = data.get("items", []) if isinstance(data, dict) else []
    ids = {it.get("id") for it in items if it.get("id")}
    status_by_id = {it.get("id"): it.get("status") for it in items if it.get("id")}
    warnings: list[dict] = []
    unverifiable_refs = 0

    def warn(code, item_id, detail):
        warnings.append({"code": code, "id": item_id, "detail": detail})

    for it in items:
        iid, status = it.get("id"), it.get("status")
        # A. verification age (open items only)
        if status in OPEN_STATUSES:
            ts = _parse_iso(it.get("last_verified_at"))
            if ts is None:
                warn("verification_unverifiable", iid, "missing/malformed last_verified_at")
            elif ts > now:
                warn("verification_unverifiable", iid, f"future last_verified_at {it.get('last_verified_at')}")
            elif (now - ts).days > OVERDUE_DAYS.get(status, 90):
                warn("verification_overdue", iid, f"{status} not re-verified in {(now - ts).days}d (> {OVERDUE_DAYS.get(status, 90)}d)")
            # C. empty next_action on proposed/active
            if status in {"proposed", "active"} and not str(it.get("next_action") or "").strip():
                warn("empty_next_action", iid, f"{status} item has empty next_action")
        # B. dangling repo-path source_refs (canonical-looking only)
        for ref in it.get("source_refs", []) or []:
            if _is_repo_path_ref(ref):
                rel = ref.split("#", 1)[0].strip()
                if not (PORTABLE_ROOT / rel).exists():
                    warn("dangling_source_ref", iid, f"source_ref path not found: {rel}")
            else:
                unverifiable_refs += 1
        # D. supersession target still open
        for target in it.get("supersedes", []) or []:
            if status_by_id.get(target) in OPEN_STATUSES:
                warn("supersession_target_still_open", iid, f"supersedes '{target}' which is still {status_by_id.get(target)}")
        # E. blocker hygiene — only treat an ID-LIKE blocker (a single short token,
        # no spaces) as an id reference; a prose blocker is free-text, not an id.
        blocker = it.get("blocker")
        if isinstance(blocker, str) and blocker.strip() and " " not in blocker.strip() and len(blocker.strip()) <= 12:
            b = blocker.strip()
            if b not in ids:
                warn("broken_blocker", iid, f"blocker '{b}' is not a known backlog id")
            elif status_by_id.get(b) in CLOSED_STATUSES:
                warn("stale_blocker", iid, f"blocked by '{b}' which is already {status_by_id.get(b)}")

    # F. circular blocker chains
    for it in items:
        seen, cur = [], it.get("id")
        while cur is not None:
            if cur in seen:
                warn("circular_blocker", it.get("id"), f"blocker cycle: {' -> '.join(seen + [cur])}")
                break
            seen.append(cur)
            nxt = next((x.get("blocker") for x in items if x.get("id") == cur), None)
            cur = nxt if isinstance(nxt, str) and nxt.strip() else None

    return warnings, {"unverifiable_source_refs": unverifiable_refs, "warnings": len(warnings)}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    live = "--no-live" not in argv

    if "--freshness" in argv:
        # READ-ONLY advisory report layered on the blocking integrity check. Base
        # integrity errors still fail (exit 2); freshness signals are WARN + exit 0.
        errors = check_backlog(live=live)
        if errors:
            print("[CHK-BACKLOG] Integrity errors (must fix before a freshness report):")
            for err in errors:
                print(f"  - {err}")
            return 2
        try:
            data = json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[CHK-BACKLOG] Invalid JSON: {e}")
            return 2
        warnings, summary = freshness_report(data)
        if "--json" in argv:
            print(json.dumps({"warnings": warnings, "summary": summary}, ensure_ascii=False, indent=2))
            return 0
        print(f"[CHK-BACKLOG:FRESHNESS] {summary['warnings']} advisory signal(s); "
              f"{summary['unverifiable_source_refs']} non-canonical source refs (not checked).")
        for w in warnings:
            print(f"  ~ [{w['code']}] {w['id']}: {w['detail']}")
        print("[CHK-BACKLOG:FRESHNESS] advisory only — never blocks, never mutates the backlog.")
        return 0

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
