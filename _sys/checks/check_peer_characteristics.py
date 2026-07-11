"""check_peer_characteristics.py - validates the peer/model characteristics registry.

This registry (_sys/ai/knowledge/peer-characteristics.jsonl) tracks known behavioral
quirks/bugs/capability limits of specific peers or peer/tier profiles, separately from
whatever config/code currently works around them, so that a future update to a peer's
CLI or model can be checked against the ORIGINAL problem instead of just trusting the
workaround is still needed forever.

Validates:
  - Valid JSONL, one object per line, required fields present.
  - 'status' and 'confidence' are within their known value sets.
  - 'mitigation.workaround_refs' entries look like real file paths that exist on disk
    (best-effort: only checks the file part before any ':' section/attribute suffix).
  - Flags (warning, not failure) any entry whose 'review_after' date has passed - a
    schedule-based nudge to go re-run the entry's recheck_contract.required_probe.

Exit codes:
  0 on success (schema valid; review-due entries are printed as warnings, not failures)
  2 on validation errors
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent
PORTABLE_ROOT = SYS_DIR.parent
REGISTRY_PATH = SYS_DIR / "ai" / "knowledge" / "peer-characteristics.jsonl"

VALID_STATUSES = {"open", "mitigated", "recheck-due", "resolved-upstream"}
VALID_CONFIDENCE = {"confirmed", "probable", "needs_probe"}
REQUIRED_FIELDS = ("id", "peer", "description", "diagnostics", "mitigation", "status", "recheck_contract", "review_after")


def _resolve_ref_path(ref: str) -> Path:
    # Refs may be "path/to/file.py" or "path/to/file.py:some.dotted.attr" - only the
    # file part before the first ':' (Windows drive colons aside, refs are repo-relative).
    file_part = ref.split(":", 1)[0]
    return PORTABLE_ROOT / file_part


def check_peer_characteristics() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not REGISTRY_PATH.exists():
        errors.append(f"Registry file not found: {REGISTRY_PATH}")
        return errors, warnings

    seen_ids: set[str] = set()
    today = date.today()

    for line_no, raw_line in enumerate(REGISTRY_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception as e:
            errors.append(f"Line {line_no}: invalid JSON ({e})")
            continue

        entry_id = entry.get("id")
        if not entry_id:
            errors.append(f"Line {line_no}: missing 'id'")
            continue

        if entry_id in seen_ids:
            errors.append(f"Duplicate entry id: {entry_id}")
        seen_ids.add(entry_id)

        for field in REQUIRED_FIELDS:
            if field not in entry:
                errors.append(f"'{entry_id}': missing required field '{field}'")

        status = entry.get("status")
        if status is not None and status not in VALID_STATUSES:
            errors.append(f"'{entry_id}': invalid status '{status}' (expected one of {sorted(VALID_STATUSES)})")

        confidence = entry.get("confidence")
        if confidence is not None and confidence not in VALID_CONFIDENCE:
            errors.append(f"'{entry_id}': invalid confidence '{confidence}' (expected one of {sorted(VALID_CONFIDENCE)})")

        recheck = entry.get("recheck_contract", {})
        if isinstance(recheck, dict):
            if not recheck.get("trigger"):
                errors.append(f"'{entry_id}': recheck_contract missing 'trigger'")
            if not recheck.get("required_probe"):
                errors.append(f"'{entry_id}': recheck_contract missing 'required_probe'")

        mitigation = entry.get("mitigation", {})
        if isinstance(mitigation, dict):
            for ref in mitigation.get("workaround_refs", []):
                if not _resolve_ref_path(ref).exists():
                    warnings.append(f"'{entry_id}': workaround_ref does not resolve to a file on disk: {ref}")

        review_after = entry.get("review_after")
        if review_after:
            try:
                if date.fromisoformat(review_after) < today:
                    warnings.append(
                        f"'{entry_id}' is past its review_after date ({review_after}) - "
                        f"re-run its recheck_contract.required_probe and update status."
                    )
            except ValueError:
                errors.append(f"'{entry_id}': review_after is not a valid ISO date: {review_after}")

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    errors, warnings = check_peer_characteristics()

    print(f"[CHK-PEER-CHR] Validating {REGISTRY_PATH.name}...")
    for w in warnings:
        print(f"  [warn] {w}")
    if errors:
        print("[CHK-PEER-CHR] Validation failed:")
        for err in errors:
            print(f"  - {err}")
        return 2

    print("[CHK-PEER-CHR] OK. Registry structure valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
