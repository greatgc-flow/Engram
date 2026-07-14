#!/usr/bin/env python3
"""T44b deterministic, shadow-only capability canaries.

This module deliberately accepts an injected invoker.  It never constructs a
peer CLI command: production activation needs a separately authorised caller.
All verdicts are derived from fixture artifacts, never model transcripts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_CHECKS_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CHECKS_DIR.parent
if str(_CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(_CHECKS_DIR))

from canary_budget import (  # noqa: E402
    consume_canary_reservation,
    release_canary_reservation,
    reserve_canary_invocation,
)
from check_peer_capability_canary import (  # noqa: E402
    build_prompt as build_agentic_prompt,
    _profile_node,
    invoke_peer_native_write,
    invoke_peer_native_write_pty,
    prepare_fixture as prepare_agentic_fixture,
    resolve_runtime_fingerprint,
    runtime_fingerprint_valid,
    score_workspace as score_agentic_workspace,
)
from check_cli_canary import _canary_quota  # noqa: E402


CAPABILITY_CORE_ID = "capability-core.v1"
LONG_CONTEXT_PREFIX = "long_context"
SHADOW_ONLY = True
MACHINE_CAPACITY_TAGS = {"app_server", "statusline", "cli_live"}
_MACHINE_USAGE_TAGS = MACHINE_CAPACITY_TAGS
_FALLBACK_BYTES_PER_TOKEN = 2
_REASONING_ANSWERS = {
    "r_modchain": "58",
    "r_avgspeed": "36",
    "r_count_3or5not15": "41",
    "r_hex2dec_2F": "47",
}
_BUGGY_CODE = "def normalize_name(value):\n    return value\n"
_PATCHED_CODE = "def normalize_name(value):\n    return value.strip().lower()\n"

CoreInvoker = Callable[[Path, dict[str, Any]], Any]


def _now(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _normal(value: Any) -> str:
    return " ".join(str(value).strip().split()).casefold()


def _norm_code(value: str) -> str:
    return value.replace("\r\n", "\n").strip() + "\n"


def _profile_config(orch: dict, peer: str, profile: str) -> dict:
    for node in orch.get("hub_nodes", []):
        if node.get("node_id") == peer and node.get("type") == "peer":
            return (node.get("profiles") or {}).get(profile) or {}
    return {}


def _premium_or_arbiter(orch: dict, peer: str, profile: str) -> bool:
    subject = f"{peer}.{profile}"
    cfg = _profile_config(orch, peer, profile)
    arbiters = ((orch.get("final_arbiter") or {}).get("arbiter_models") or orch.get("arbiter_models") or [])
    return cfg.get("cost_tier") == "high" or subject in arbiters or peer in arbiters


def _authorized(orch: dict, peer: str, profile: str, *, execute: bool, allowlist: set[str] | None) -> bool:
    if not _premium_or_arbiter(orch, peer, profile):
        return True
    return bool(execute and f"{peer}.{profile}" in (allowlist or set()))


def _budget_values(budget: dict | None) -> tuple[Any, Any, Any]:
    budget = budget or {}
    return budget.get("cap"), budget.get("window_hours"), budget.get("reserve_floor")


def _reserve(
    ai_root: Path, *, kind: str, peer: str, profile: str, orch: dict,
    budget: dict | None, quota: dict | None, now: datetime,
) -> dict[str, Any]:
    cap, window_hours, reserve_floor = _budget_values(budget)
    quota = quota or {}
    return reserve_canary_invocation(
        ai_root, kind=kind, subject=f"{peer}.{profile}", now=now,
        cap=cap, window_hours=window_hours, reserve_floor=reserve_floor,
        quota_source_tag=quota.get("source_tag", "absent"),
        quota_remaining=quota.get("remaining"), orchestration=orch,
    )


def _machine_usage(result: Any) -> float | None:
    """Accept token usage only when an invoker labels it machine-owned."""
    if not isinstance(result, dict):
        return None
    usage = result.get("machine_usage")
    if not isinstance(usage, dict) or usage.get("source_tag") not in _MACHINE_USAGE_TAGS:
        return None
    tokens = usage.get("tokens")
    return float(tokens) if isinstance(tokens, (int, float)) and not isinstance(tokens, bool) else None


def prepare_core_fixture(workspace: Path) -> dict[str, Any]:
    """Create the deterministic three-axis fixture in a disposable workspace."""
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    code_dir = workspace / "code"
    code_dir.mkdir()
    (code_dir / "buggy_normalizer.py").write_text(_BUGGY_CODE, encoding="utf-8")
    (code_dir / "hidden_tests.json").write_text(
        json.dumps({"cases": [["  Ada ", "ada"], ["BOB", "bob"], ["carol", "carol"]]}, sort_keys=True),
        encoding="utf-8",
    )
    return {
        "reasoning_answers": dict(_REASONING_ANSWERS),
        "expected_code": _PATCHED_CODE,
        "agentic_fixture": prepare_agentic_fixture(workspace / "agentic"),
    }


def build_capability_core_prompt(fixture: dict[str, Any], workspace: Path) -> str:
    """Build the real native-tool prompt; artifact files are the sole oracle."""
    agentic_prompt = build_agentic_prompt(Path(workspace) / "agentic")
    return f"""[CAPABILITY_CORE_V1]
This is an authorized capability canary in the disposable workspace: {workspace}
Use native file tools. ALL writes must stay inside this workspace.

REASONING: write reasoning_answers.json as a JSON object with EXACTLY these
keys and string values. r_modchain: Compute ((7^4 mod 100) * 13 + 45) mod
1000. r_avgspeed: A vehicle travels 60 km at 30 km/h, then 120 km at 40 km/h;
give the average speed for the whole trip in km/h as an integer.
r_count_3or5not15: How many integers from 1 to 100 inclusive are divisible
by 3 or 5 but NOT by 15? r_hex2dec_2F: Give the decimal value of hexadecimal
0x2F. Keys: r_modchain, r_avgspeed, r_count_3or5not15, r_hex2dec_2F.

CODE: edit code/buggy_normalizer.py only as needed so normalize_name(value)
returns value.strip().lower(); it currently returns value unchanged. Preserve
the rest of the file byte-faithfully.

AGENTIC: complete the existing T21 fixture under agentic/. Its full artifact
contract follows; do not write outside this workspace:
{agentic_prompt}
"""


def default_core_invoker(peer: str, profile: str, orch: dict, *, timeout: int | None = None) -> CoreInvoker:
    """Curry T21's native CLI driver into the CoreInvoker interface."""
    use_pty = bool(_profile_node(orch, peer, profile).get("requires_pty"))
    def invoke(workspace: Path, fixture: dict[str, Any]) -> dict[str, Any]:
        prompt = build_capability_core_prompt(fixture, workspace)
        driver = invoke_peer_native_write_pty if use_pty else invoke_peer_native_write
        result = driver(peer, profile, prompt, workspace, orch, timeout)
        return {
            "returncode": result.returncode,
            "stdout": getattr(result, "stdout", ""),
            "stderr": getattr(result, "stderr", ""),
            # No usage is inferred from prompt text or process output.
        }
    return invoke


def _score_reasoning(workspace: Path) -> tuple[int, bool, dict[str, bool]]:
    path = workspace / "reasoning_answers.json"
    try:
        answers = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        answers = {}
    # Valid JSON that is not an object (e.g. a list "[...]") must not crash on
    # .get() (T52). judgeable = the model produced a JSON object; a non-dict is
    # not judgeable and scores 0.
    judgeable = isinstance(answers, dict)
    if not judgeable:
        answers = {}
    matches = {key: _normal(answers.get(key, "")) == _normal(expected) for key, expected in _REASONING_ANSWERS.items()}
    return 25 * sum(matches.values()), judgeable, matches


def _score_code(workspace: Path, fixture: dict[str, Any]) -> tuple[int, bool, dict[str, bool]]:
    path = workspace / "code" / "buggy_normalizer.py"
    actual = path.read_text(encoding="utf-8") if path.exists() else ""
    exact_patch = _norm_code(actual) == _norm_code(fixture["expected_code"])
    # The hidden cases are a deterministic oracle for the sole allowlisted
    # patch.  We do not execute untrusted candidate code to judge it.
    hidden_tests_pass = exact_patch
    return (50 if hidden_tests_pass else 0) + (50 if exact_patch else 0), path.exists(), {
        "hidden_tests_pass": hidden_tests_pass, "exact_normalized_diff": exact_patch,
    }


def score_capability_core(workspace: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    reasoning, reasoning_judgeable, reasoning_detail = _score_reasoning(workspace)
    code, code_judgeable, code_detail = _score_code(workspace, fixture)
    agentic_raw = score_agentic_workspace(workspace / "agentic", fixture["agentic_fixture"])
    # T21's deterministic artifact score is 0..95 (repeatability is excluded
    # for a one-invocation core suite); scale only that fixed denominator.
    agentic = round((agentic_raw["score_without_repeatability"] / 95) * 100)
    agentic_judgeable = bool((workspace / "agentic").exists())
    return {
        "axis_scores": {
            "reasoning_correctness": reasoning,
            "code_fidelity": code,
            "agentic_reliability": agentic,
        },
        "details": {
            "reasoning_correctness": reasoning_detail,
            "code_fidelity": code_detail,
            "agentic_reliability": agentic_raw,
        },
        "judgeable": reasoning_judgeable and code_judgeable and agentic_judgeable,
    }


def aggregate_core_runs(entries: list[dict[str, Any]], *, expected_runtime_fingerprint: dict[str, Any]) -> dict[str, Any]:
    """Aggregate exactly three complete same-runtime runs by per-axis minimum."""
    entries = list(entries[-3:])
    valid = (
        len(entries) == 3
        and runtime_fingerprint_valid(expected_runtime_fingerprint)
        and all(entry.get("judgeable") and entry.get("runtime_fingerprint") == expected_runtime_fingerprint for entry in entries)
    )
    axes = ("reasoning_correctness", "code_fidelity", "agentic_reliability")
    # Every run must carry ALL three axes as real numbers — a run missing an axis
    # is INCOMPLETE and must not certify with a silently-zeroed axis (T52: the old
    # .get(axis, 0) let {"reasoning_correctness": 100} certify with code/agentic 0).
    complete = valid and all(
        isinstance(entry.get("axis_scores"), dict)
        and all(isinstance(entry["axis_scores"].get(axis), (int, float)) for axis in axes)
        for entry in entries
    )
    if not complete:
        return {"valid": False, "axis_scores": {axis: None for axis in axes}}
    return {"valid": True, "axis_scores": {axis: min(entry["axis_scores"][axis] for entry in entries) for axis in axes}}


def _append_record(path: Path | None, record: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def run_capability_core(
    *, peer: str, profile: str, orch: dict, ai_root: Path, workspace: Path,
    invoker: CoreInvoker | None, runtime_fingerprint: dict[str, Any],
    budget: dict | None = None, quota: dict | None = None, now: datetime | None = None,
    execute: bool = False, allowlist: set[str] | None = None, records_path: Path | None = None,
) -> dict[str, Any]:
    """Run one mock/injected capability-core pass, never altering routing."""
    now = _now(now)
    if not _authorized(orch, peer, profile, execute=execute, allowlist=allowlist):
        return {"status": "SKIP", "reason": "premium_not_authorized", "shadow_only": True}
    if invoker is None:
        return {"status": "SKIP", "reason": "invoker_required", "shadow_only": True}
    reservation = _reserve(Path(ai_root), kind="capability_core", peer=peer, profile=profile, orch=orch, budget=budget, quota=quota, now=now)
    if not reservation.get("granted"):
        return {"status": "SKIP", "reason": reservation.get("reason"), "shadow_only": True}
    fixture = prepare_core_fixture(Path(workspace))
    try:
        invocation = invoker(Path(workspace), fixture)
    except Exception as exc:
        release_canary_reservation(Path(ai_root), reservation["reservation_id"], now=now)
        return {"status": "FAIL", "reason": "invoker_failure", "detail": str(exc)[:200], "shadow_only": True}
    actual_tokens = _machine_usage(invocation)
    consume_canary_reservation(Path(ai_root), reservation["reservation_id"], actual_tokens=actual_tokens, now=now)
    scored = score_capability_core(Path(workspace), fixture)
    record = {
        "schema_version": 1, "capability_id": CAPABILITY_CORE_ID, "peer": peer, "profile": profile,
        "runtime_fingerprint": runtime_fingerprint, "axis_scores": scored["axis_scores"],
        "judgeable": scored["judgeable"], "actual_tokens": actual_tokens, "source_tag": "empirical_probe",
        "shadow_only": True, "measured_at": now.isoformat(), "details": scored["details"],
    }
    _append_record(records_path, record)
    return {"status": "PASS" if scored["judgeable"] else "FAIL", **record}


def estimate_tokens(text: str, tokenizer: Callable[[str], int] | None = None) -> int:
    """Use a supplied tokenizer or conservative two UTF-8 bytes per token."""
    if tokenizer is not None:
        try:
            value = tokenizer(text)
            if isinstance(value, int) and value >= 0:
                return value
        except Exception:
            pass
    return math.ceil(len(text.encode("utf-8")) / _FALLBACK_BYTES_PER_TOKEN)


def generate_long_context_fixture(length_tokens: int, *, seed: int = 1, tokenizer: Callable[[str], int] | None = None) -> dict[str, Any]:
    if length_tokens not in {8_000, 32_000, 128_000}:
        raise ValueError("length_tokens must be one of 8000, 32000, 128000")
    marker_values = {"marker_alpha": f"ALPHA-{seed}-17", "marker_beta": f"BETA-{seed}-29"}
    combine = f"{marker_values['marker_alpha']}|{marker_values['marker_beta']}"
    suffix = f"\nMARKER_ALPHA={marker_values['marker_alpha']}\nMARKER_BETA={marker_values['marker_beta']}\nRecall both markers and combine with |."
    unit = f"fact: seed={seed}; stable deterministic filler.\n"
    # The fallback itself is deliberately conservative, so a fixture made
    # under it can never exceed its requested measured-capacity guard.
    available_bytes = max(0, (length_tokens * _FALLBACK_BYTES_PER_TOKEN) - len(suffix.encode("utf-8")))
    base = unit * (available_bytes // len(unit.encode("utf-8")))
    prompt = f"{base}{suffix}"
    return {
        "suite": f"long_context.{length_tokens // 1000}k.v1", "requested_fixture_tokens": length_tokens,
        "seed": seed, "prompt": prompt, "markers": marker_values,
        "answers": {"marker_recall": combine, "combined_answer": combine},
        "tokenizer": "provided" if tokenizer is not None else "byte_fallback_2_bytes_per_token",
    }


def _capacity_allows(capacity: dict | None, requested_tokens: int) -> bool:
    capacity = capacity or {}
    return capacity.get("source_tag") in MACHINE_CAPACITY_TAGS and isinstance(capacity.get("window_tokens"), (int, float)) and capacity["window_tokens"] >= requested_tokens


def _score_long_context(workspace: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    try:
        answers = json.loads((workspace / "long_context_answers.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        answers = {}
    recall = _normal(answers.get("marker_recall", "")) == _normal(fixture["answers"]["marker_recall"])
    combined = _normal(answers.get("combined_answer", "")) == _normal(fixture["answers"]["combined_answer"])
    return {"marker_recall": 50 if recall else 0, "combined_answer": 50 if combined else 0, "score": 50 * (recall + combined), "judgeable": isinstance(answers, dict)}


def run_long_context(
    *, peer: str, profile: str, orch: dict, ai_root: Path, workspace: Path, length_tokens: int,
    capacity: dict | None, invoker: CoreInvoker | None, budget: dict | None = None, quota: dict | None = None,
    now: datetime | None = None, execute: bool = False, allowlist: set[str] | None = None,
    tokenizer: Callable[[str], int] | None = None, records_path: Path | None = None,
) -> dict[str, Any]:
    """Run one guarded, deterministic long-context pass in shadow only."""
    now = _now(now)
    if not _capacity_allows(capacity, length_tokens):
        return {"status": "SKIP", "reason": "capacity_unmeasured_or_insufficient", "shadow_only": True}
    if not _authorized(orch, peer, profile, execute=execute, allowlist=allowlist):
        return {"status": "SKIP", "reason": "premium_not_authorized", "shadow_only": True}
    if invoker is None:
        return {"status": "SKIP", "reason": "invoker_required", "shadow_only": True}
    reservation = _reserve(Path(ai_root), kind="long_context", peer=peer, profile=profile, orch=orch, budget=budget, quota=quota, now=now)
    if not reservation.get("granted"):
        return {"status": "SKIP", "reason": reservation.get("reason"), "shadow_only": True}
    fixture = generate_long_context_fixture(length_tokens, tokenizer=tokenizer)
    workspace = Path(workspace)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    (workspace / "long_context_prompt.txt").write_text(fixture["prompt"], encoding="utf-8")
    try:
        invocation = invoker(workspace, fixture)
    except Exception as exc:
        release_canary_reservation(Path(ai_root), reservation["reservation_id"], now=now)
        return {"status": "FAIL", "reason": "invoker_failure", "detail": str(exc)[:200], "shadow_only": True}
    actual_tokens = _machine_usage(invocation)
    consume_canary_reservation(Path(ai_root), reservation["reservation_id"], actual_tokens=actual_tokens, now=now)
    scored = _score_long_context(workspace, fixture)
    record = {
        "schema_version": 1, "capability_id": fixture["suite"], "peer": peer, "profile": profile,
        "axis_scores": {"long_context_quality": scored["score"]}, "subscores": scored,
        "actual_tokens": actual_tokens, "source_tag": "empirical_probe", "shadow_only": True,
        "measured_at": now.isoformat(),
    }
    _append_record(records_path, record)
    return {"status": "PASS" if scored["judgeable"] else "FAIL", **record}


def _split_subject(value: str) -> tuple[str, str]:
    if "." not in value:
        raise ValueError("--peer must be peer.profile")
    return tuple(value.split(".", 1))  # type: ignore[return-value]


def _load_orchestration(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run shadow-only deterministic capability canaries")
    parser.add_argument("--peer", required=True, help="Target as peer.profile")
    parser.add_argument("--suite", choices=("core", "long_context"), default="core")
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--length", type=int, default=8000, choices=(8000, 32000, 128000))
    parser.add_argument("--budget-cap", type=int)
    parser.add_argument("--budget-window", type=float)
    parser.add_argument("--reserve-floor", type=float)
    parser.add_argument("--allowlist", default="", help="Comma-separated premium subjects")
    parser.add_argument("--quota-remaining", type=float)
    parser.add_argument("--quota-source", choices=("app_server", "statusline", "cli_live", "absent"))
    parser.add_argument("--context-window", type=int)
    parser.add_argument("--context-source", choices=("app_server", "statusline", "cli_live", "absent"))
    parser.add_argument("--artifact-root", type=Path, default=_SYS_DIR / "data" / "capability-core")
    parser.add_argument("--records-path", type=Path, default=_SYS_DIR / "ai" / "knowledge" / "peer-capability-scores.jsonl")
    parser.add_argument("--orchestration", type=Path, default=_SYS_DIR / "ai" / "orchestration.json")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--execute", action="store_true", help="Mandatory: permits a native CLI invocation")
    args = parser.parse_args(argv)
    if not args.execute:
        print("Dry-run: no workspace, ledger, or model invocation. Add --execute to run.")
        return 0
    try:
        peer, profile = _split_subject(args.peer)
        orch = _load_orchestration(args.orchestration)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    budget = {"cap": args.budget_cap, "window_hours": args.budget_window, "reserve_floor": args.reserve_floor}
    quota = (
        {"source_tag": args.quota_source or "absent", "remaining": args.quota_remaining}
        if args.quota_source is not None or args.quota_remaining is not None
        else _canary_quota(peer, profile)
    )
    allowlist = {item.strip() for item in args.allowlist.split(",") if item.strip()}
    fingerprint = resolve_runtime_fingerprint(orch, peer, profile)
    invoker = default_core_invoker(peer, profile, orch, timeout=args.timeout)
    results = []
    for index in range(max(1, args.passes)):
        workspace = args.artifact_root / f"{args.suite}-{peer}-{profile}-{index + 1}"
        if args.suite == "core":
            result = run_capability_core(
                peer=peer, profile=profile, orch=orch, ai_root=args.artifact_root / ".ai",
                workspace=workspace, invoker=invoker, runtime_fingerprint=fingerprint,
                budget=budget, quota=quota, execute=True, allowlist=allowlist,
                records_path=args.records_path,
            )
        else:
            capacity = {"source_tag": args.context_source or "absent", "window_tokens": args.context_window}
            result = run_long_context(
                peer=peer, profile=profile, orch=orch, ai_root=args.artifact_root / ".ai",
                workspace=workspace, length_tokens=args.length, capacity=capacity, invoker=invoker,
                budget=budget, quota=quota, execute=True, allowlist=allowlist, records_path=args.records_path,
            )
        results.append(result)
        if result.get("status") != "PASS":
            break
    print(json.dumps(results[-1], ensure_ascii=False, sort_keys=True))
    return 0 if results[-1].get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
