"""check_policy_ledger.py — policy decision ledger drift guard (CHK-LEDGER).

Task 9 (2026-07-19/20 absent-audit consensus, cx design): a real incident
showed prose docs silently diverging from applied config. intelligence-
scores.md's status banner said the arbiter_models expansion (commit ab3af8f)
was "OPEN and unapplied" for HOURS after it had actually landed -- nobody
re-checked the banner against the real config, and nothing would have caught
it if cx hadn't happened to notice live during an unrelated consensus round.

_sys/ai/policy-decisions.json is a lightweight, git-tracked ledger of policy
decisions. Each decision marked status="applied" carries a `checks` list --
either a JSON pointer into a config file with an expected value, a required
substring in a doc file, or a required JSON array member. This script
re-verifies every one of those checks against the CURRENT file contents on every commit.

Cluster C4 Hardening:
  - Item 6: expected_substring is required non-empty for text_contains checks.
    Schema errors return structured violation strings, never uncaught tracebacks.
  - Item 7: json_array_member check kind added for backlog.json array member verification.

Usage:  python check_policy_ledger.py [--ai-dir DIR] [--json]
Exit:   0 clean (or no ledger present) - 1 at least one violation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_CHECKS_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent
_AI_DIR = _SYS_DIR / "ai"

VALID_STATUSES = {"proposed", "approved", "applied", "superseded"}
VALID_CHECK_KINDS = {"json_value", "text_contains", "json_array_member"}


def _resolve_json_pointer(data: Any, pointer: str) -> Any:
    """Minimal slash-separated pointer resolver (e.g. "/a/b/0"); raises
    KeyError/IndexError/TypeError on a bad path."""
    cur = data
    for part in [p for p in pointer.split("/") if p]:
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def _run_check(decision_id: str, check: dict) -> list[str]:
    kind = check.get("kind")
    rel_path = check.get("path")
    if kind not in VALID_CHECK_KINDS:
        return [f"{decision_id}: unknown check kind {kind!r}"]
    if not isinstance(rel_path, str) or not rel_path:
        return [f"{decision_id}: check missing a 'path'"]

    full_path = _PORTABLE_ROOT / rel_path
    if not full_path.exists():
        return [f"{decision_id}: checked path '{rel_path}' does not exist"]

    if kind == "json_value":
        pointer = check.get("pointer", "")
        try:
            live = json.loads(full_path.read_text(encoding="utf-8"))
            value = _resolve_json_pointer(live, pointer)
        except Exception as exc:
            return [f"{decision_id}: could not resolve '{pointer}' in {rel_path}: {exc}"]
        expected = check.get("expected")
        if value != expected:
            return [
                f"{decision_id}: DRIFT -- {rel_path}{pointer} is {value!r}, "
                f"ledger expects {expected!r} for an 'applied' decision"
            ]
        return []

    if kind == "text_contains":
        expected_substring = check.get("expected_substring")
        if not isinstance(expected_substring, str) or not expected_substring:
            return [
                f"{decision_id}: text_contains check in {rel_path} requires a "
                "non-empty 'expected_substring' string"
            ]
        try:
            text = full_path.read_text(encoding="utf-8")
        except Exception as exc:
            return [f"{decision_id}: could not read text file {rel_path}: {exc}"]

        if expected_substring not in text:
            return [
                f"{decision_id}: DRIFT -- {rel_path} no longer contains the text "
                f"this 'applied' decision's evidence depends on: {expected_substring!r}"
            ]
        return []

    if kind == "json_array_member":
        pointer = check.get("pointer", "")
        match_key = check.get("match_key")
        match_value = check.get("match_value")
        expected_item = check.get("expected")

        try:
            live = json.loads(full_path.read_text(encoding="utf-8"))
            arr = _resolve_json_pointer(live, pointer)
        except Exception as exc:
            return [f"{decision_id}: could not resolve pointer '{pointer}' in {rel_path}: {exc}"]

        if not isinstance(arr, list):
            return [f"{decision_id}: pointer '{pointer}' in {rel_path} did not resolve to a list"]

        if match_key is not None:
            found = any(isinstance(x, dict) and x.get(match_key) == match_value for x in arr)
            if not found:
                return [
                    f"{decision_id}: DRIFT -- {rel_path}{pointer} array missing item where "
                    f"{match_key}=={match_value!r}"
                ]
        else:
            if expected_item not in arr:
                return [
                    f"{decision_id}: DRIFT -- {rel_path}{pointer} array missing expected item {expected_item!r}"
                ]
        return []

    return []


def check_policy_ledger(ai_dir: Path | str | None = None) -> list[str]:
    """Validate ledger schema and re-verify every applied decision's checks
    against live files. Returns a list of human-readable violation strings
    (empty = clean, including the no-ledger-file case)."""
    ai_dir = Path(ai_dir) if ai_dir is not None else _AI_DIR
    ledger_path = ai_dir / "policy-decisions.json"
    if not ledger_path.exists():
        return []

    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"policy-decisions.json: failed to parse - {exc}"]

    decisions = data.get("decisions", [])
    if not isinstance(decisions, list):
        return ["policy-decisions.json: 'decisions' must be a list"]

    errors: list[str] = []
    seen_ids: set[str] = set()
    for entry in decisions:
        if not isinstance(entry, dict):
            errors.append("policy-decisions.json: each decision must be an object")
            continue
        decision_id = entry.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id.strip():
            errors.append("policy-decisions.json: decision missing a non-empty decision_id")
            continue
        if decision_id in seen_ids:
            errors.append(f"policy-decisions.json: duplicate decision_id {decision_id!r}")
        seen_ids.add(decision_id)

        status = entry.get("status")
        if status not in VALID_STATUSES:
            errors.append(
                f"{decision_id}: status must be one of {sorted(VALID_STATUSES)}, got {status!r}"
            )
            continue

        if status != "applied":
            continue

        checks = entry.get("checks", [])
        if not isinstance(checks, list) or not checks:
            errors.append(f"{decision_id}: status='applied' requires a non-empty 'checks' list")
            continue
        for check in checks:
            if not isinstance(check, dict):
                errors.append(f"{decision_id}: each check must be an object")
                continue
            errors.extend(_run_check(decision_id, check))

    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Policy decision ledger drift guard (CHK-LEDGER)")
    ap.add_argument("--ai-dir", default=str(_AI_DIR), help="directory containing policy-decisions.json")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    violations = check_policy_ledger(args.ai_dir)

    if args.json:
        print(json.dumps({
            "check": "CHK-LEDGER",
            "ok": not violations,
            "violations": violations,
        }, ensure_ascii=False, indent=2))
    else:
        if violations:
            print("[CHK-LEDGER] Policy ledger drift:")
            for v in violations:
                print(f"  - {v}")
            print("[CHK-LEDGER] Fix: either restore the file/config to match the ledger's "
                  "'applied' claim, or update the decision (supersede it / fix its checks).")
        else:
            print("[CHK-LEDGER] OK — no policy-decision drift.")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
