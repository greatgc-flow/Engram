"""check_lesson_enforcement.py — run lesson enforcement checks and emit G-bridge artifacts.

Consensus 2026-07-03 (W2/W3): every artifact is the output of a REAL check run —
never a hand-written pass marker (DIR-004). Artifacts land in .ai/enforcement/
LL-0XX.json with {"status": "pass"|"fail", ...}, the shape hub.py's
_lesson_activation_blocker accepts. Exit 0 only when every check passes.

Checks:
  LL-009  model operand grammar (r-8b3b)  — hub_peer.model_operand_report()
  LL-011  transport startup contract      — protocol.json zombie_profile_map
  LL-012  declared-vs-actual              — check_cli_reality.run()
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

sys.path.insert(0, str(_SYS_DIR / "core"))
sys.path.insert(0, str(_CHECKS_DIR))

# Knowledge root is FIXED (hub._knowledge_root()), unlike ai_root which depends
# on the invoking process cwd — agy workers proved nondeterministic there
# (LL-20260703-001/002 activation flaked on 2026-07-03). Artifacts live here.
ENFORCEMENT_DIR = _SYS_DIR / "ai" / "knowledge" / "enforcement"
REQUIRED_STARTUP_PROFILES = ("standard", "effort", "deepthink")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_ll009() -> dict:
    """LL-009: model operand must match the orchestration-declared model."""
    from hub_peer import model_operand_report
    return model_operand_report()


def check_ll011() -> dict:
    """LL-011: transport startup contract (revised 2026-07-11) - a peer that is
    streaming output, or hasn't yet emitted its first byte, must never be killed
    by a short profile-scoped pre-output window. The 2026-07-03 fix used a
    separate (shorter) startup_profile_map, which itself proved unsafe: 3
    consecutive real cx failures on 2026-07-11 were killed at exactly the
    "effort" tier's 180s startup bound despite the peer still legitimately
    working. The contract is now enforced via a SINGLE profile-scoped
    zombie_profile_map (no separate kill-capable startup window) plus a
    non-lethal silent_startup_warning_sec telemetry threshold. This check
    verifies the new contract holds and the retired keys are actually gone."""
    findings = []
    try:
        protocol = json.loads(
            (_SYS_DIR / "ai" / "protocol.json").read_text(encoding="utf-8-sig"))
    except Exception as exc:
        findings.append(f"protocol.json unreadable: {exc}")
        protocol = {}
    policy = protocol.get("communication_policy") or {}

    profile_map = policy.get("zombie_profile_map")
    if not isinstance(profile_map, dict):
        findings.append("communication_policy.zombie_profile_map missing")
    else:
        for name in REQUIRED_STARTUP_PROFILES:
            value = profile_map.get(name)
            if not isinstance(value, (int, float)) or value <= 0:
                findings.append(f"zombie_profile_map.{name} missing or non-positive: {value!r}")

    warning_sec = policy.get("silent_startup_warning_sec")
    if not isinstance(warning_sec, (int, float)) or warning_sec < 0:
        findings.append("communication_policy.silent_startup_warning_sec missing or negative")

    if "startup_timeout_sec" in policy or "startup_profile_map" in policy:
        findings.append("retired keys startup_timeout_sec/startup_profile_map still present - "
                         "these must stay removed, a kill-capable pre-output window must not return")

    return {
        "lesson": "LL-011",
        "check": "transport_startup_contract",
        "status": "fail" if findings else "pass",
        "findings": findings,
        "generated_at": _now(),
    }


def check_ll012(live: bool = True) -> dict:
    """LL-012: declared-vs-actual reconciliation via check_cli_reality (real run)."""
    import check_cli_reality
    report = check_cli_reality.run(live=live)
    summary = report.get("drift_summary") or {}
    p0 = summary.get("p0", 0)
    return {
        "lesson": "LL-012",
        "check": "cli_reality_reconciliation",
        "status": "fail" if p0 else "pass",
        "drift_summary": summary,
        "observed_at": report.get("observed_at"),
        "generated_at": _now(),
    }


def check_ll20260703_005() -> dict:
    """LL-20260703-005: no out-of-band mutation of governed files during peer
    asks. Pass requires BOTH (cx review): (a) AST proof the guard is wired into
    hub.action_ask (pre-snapshot + finally post-check), and (b) a LIVE self-test
    that the detector actually fires on a controlled governed-file change. A
    guard that fired on a REAL violation does not fail this artifact."""
    import ast as _ast
    findings = []

    # (a) AST wiring proof: action_ask calls _snapshot_governed_hashes and has a
    #     finally that calls _governed_post_check.
    hub_src = (_SYS_DIR / "core" / "hub.py").read_text(encoding="utf-8")
    try:
        tree = _ast.parse(hub_src)
    except SyntaxError as exc:
        return {"lesson": "LL-20260703-005", "check": "governed_mutation_guard",
                "status": "fail", "findings": [f"hub.py parse error: {exc}"],
                "generated_at": _now()}
    fn = next((n for n in tree.body
               if isinstance(n, _ast.FunctionDef) and n.name == "action_ask"), None)
    if fn is None:
        findings.append("action_ask function not found")
    else:
        calls = {n.func.id for n in _ast.walk(fn)
                 if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)}
        has_finally = any(isinstance(n, _ast.Try) and n.finalbody for n in _ast.walk(fn))
        if "_snapshot_governed_hashes" not in calls:
            findings.append("action_ask does not capture a pre-snapshot (_snapshot_governed_hashes)")
        if "_governed_post_check" not in calls:
            findings.append("action_ask does not invoke _governed_post_check")
        if not has_finally:
            findings.append("action_ask has no finally block wrapping the guard")

    # (b) LIVE self-test: pre-snapshot a temp governed fixture, mutate it,
    #     confirm _governed_post_check reports the change.
    try:
        sys.path.insert(0, str(_SYS_DIR / "core"))
        import hub
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            fixture = tdp / "governed_fixture.txt"
            fixture.write_text("original", encoding="utf-8")
            files = [fixture]
            monkey = hub._governed_files
            hub._governed_files = lambda *a, **k: [fixture.resolve()]  # type: ignore
            try:
                # pre and post BOTH go through _snapshot_governed_hashes so path
                # normalization is identical (the real guard's contract).
                pre = hub._snapshot_governed_hashes()
                fixture.write_text("mutated-by-peer", encoding="utf-8")
                changed = hub._governed_post_check(pre, tdp / ".ai", "test-peer", "selftest")
            finally:
                hub._governed_files = monkey  # type: ignore
            if not changed:
                findings.append("live self-test: detector did NOT report a governed mutation")
            log = (tdp / ".ai" / "operational_errors.jsonl")
            if not log.exists() or "GOVERNED_MUTATION_VIOLATION" not in log.read_text(encoding="utf-8"):
                findings.append("live self-test: violation was not logged to operational_errors.jsonl")
    except Exception as exc:
        findings.append(f"live self-test error: {type(exc).__name__}: {exc}")

    return {
        "lesson": "LL-20260703-005",
        "check": "governed_mutation_guard",
        "status": "fail" if findings else "pass",
        "findings": findings,
        "generated_at": _now(),
    }


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    live = "--no-live" not in argv
    ENFORCEMENT_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        "LL-009": check_ll009(),
        "LL-011": check_ll011(),
        "LL-012": check_ll012(live=live),
        "LL-20260703-005": check_ll20260703_005(),
    }
    failed = []
    for lesson_id, report in results.items():
        out = ENFORCEMENT_DIR / f"{lesson_id}.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        status = report.get("status")
        print(f"[lesson-enforcement] {lesson_id}: {status} -> {out}")
        for finding in report.get("findings") or []:
            print(f"  - {finding}")
        if status != "pass":
            failed.append(lesson_id)
    if failed:
        print(f"[lesson-enforcement] FAILED: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
