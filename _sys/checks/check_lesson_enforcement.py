"""check_lesson_enforcement.py — run lesson enforcement checks and emit G-bridge artifacts.

Consensus 2026-07-03 (W2/W3): every artifact is the output of a REAL check run —
never a hand-written pass marker (DIR-004). Artifacts land in .ai/enforcement/
LL-0XX.json with {"status": "pass"|"fail", ...}, the shape hub.py's
_lesson_activation_blocker accepts. Exit 0 only when every check passes.

Checks:
  LL-009  model operand grammar (r-8b3b)  — hub_peer.model_operand_report()
  LL-011  transport startup contract      — protocol.json startup_profile_map
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
    """LL-011: startup_profile_map exists, covers required profiles, sane values."""
    findings = []
    try:
        protocol = json.loads(
            (_SYS_DIR / "ai" / "protocol.json").read_text(encoding="utf-8-sig"))
    except Exception as exc:
        findings.append(f"protocol.json unreadable: {exc}")
        protocol = {}
    policy = protocol.get("communication_policy") or {}
    profile_map = policy.get("startup_profile_map")
    if not isinstance(profile_map, dict):
        findings.append("communication_policy.startup_profile_map missing")
    else:
        for name in REQUIRED_STARTUP_PROFILES:
            value = profile_map.get(name)
            if not isinstance(value, (int, float)) or value <= 0:
                findings.append(f"startup_profile_map.{name} missing or non-positive: {value!r}")
    if not isinstance(policy.get("startup_timeout_sec"), (int, float)):
        findings.append("communication_policy.startup_timeout_sec missing")
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


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    live = "--no-live" not in argv
    ENFORCEMENT_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        "LL-009": check_ll009(),
        "LL-011": check_ll011(),
        "LL-012": check_ll012(live=live),
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
