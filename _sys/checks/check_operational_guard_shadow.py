"""check_operational_guard_shadow.py - D2 (INV-26 fail-closed) Gate 3 soak reporter.

Reads .ai/routing_metrics.jsonl's `operational_guard_shadow` events (written by
hub.py's _guard_action on every real invocation, see _record_guard_shadow) and
reports whether the live soak has met cc.fable's Gate 3 bar:
  - >= 100 real evaluations
  - >= 24h wall-clock span between the first and last recorded event
  - zero shadow_match=false events (dry-run decision disagreed with the real
    enforced outcome - would indicate wrapper drift, since _guard_action is
    supposed to be a thin wrapper over _guard_action_dry_run)
  - zero live case_key values absent from the Gate-1 static matrix (a coverage
    gap - cc.fable: this must EXTEND the soak, i.e. add the case to Gate 1/2 and
    rerun, not silently pass Gate 3)

This does not gate anything automatically - it is a manually-run report to
support a human/peer decision on whether INV-26 fail-closed enforcement (which
has been live since commit feadb3b; see hub.py:_guard_action) can be considered
VALIDATED, not just implemented.

Exit codes:
  0 if all four Gate 3 conditions are met
  1 if the soak simply hasn't accumulated enough data yet (not a failure -
    informational; re-run later)
  2 on an actual problem (mismatch or coverage gap found)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub  # noqa: E402
import operational_guard_matrix as ogm  # noqa: E402

MIN_EVENTS = 100
MIN_SPAN_HOURS = 24


def _load_shadow_events(routing_metrics_path: Path) -> list[dict]:
    if not routing_metrics_path.exists():
        return []
    events = []
    for line in routing_metrics_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if item.get("event") == "operational_guard_shadow":
            events.append(item)
    return events


def _static_case_keys() -> set[str]:
    cfg = hub._load_protocol_cfg().get("operational_guard", {})
    orchestration = hub._load_orchestration()
    cases = ogm.enumerate_cases(cfg, orchestration)
    return {c.case_key() for c in cases}


def evaluate_soak(events: list[dict], static_case_keys: set[str]) -> dict:
    mismatches = [e for e in events if e.get("shadow_match") is False]
    coverage_gaps = sorted({e.get("case_key") for e in events if e.get("case_key") not in static_case_keys} - {None})

    span_hours = 0.0
    if len(events) >= 2:
        timestamps = []
        for e in events:
            ts = e.get("ts")
            if not ts:
                continue
            try:
                timestamps.append(datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S"))
            except ValueError:
                continue
        if timestamps:
            span_hours = (max(timestamps) - min(timestamps)) / timedelta(hours=1)

    return {
        "event_count": len(events),
        "span_hours": span_hours,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "coverage_gaps": coverage_gaps,
        "meets_count_bar": len(events) >= MIN_EVENTS,
        "meets_span_bar": span_hours >= MIN_SPAN_HOURS,
        "zero_mismatches": len(mismatches) == 0,
        "zero_coverage_gaps": len(coverage_gaps) == 0,
    }


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai-root", default=str(SYS_DIR.parent / ".ai"))
    args = parser.parse_args(argv)

    ai_root = Path(args.ai_root)
    events = _load_shadow_events(ai_root / "routing_metrics.jsonl")
    static_keys = _static_case_keys()
    report = evaluate_soak(events, static_keys)

    print("[CHK-GUARD-SHADOW] D2 Gate 3 soak report")
    print(f"  events: {report['event_count']} (need >= {MIN_EVENTS})")
    print(f"  span:   {report['span_hours']:.1f}h (need >= {MIN_SPAN_HOURS}h)")
    print(f"  mismatches: {report['mismatch_count']}")
    print(f"  coverage gaps: {len(report['coverage_gaps'])}")

    if report["mismatch_count"] or report["coverage_gaps"]:
        print("[CHK-GUARD-SHADOW] PROBLEM FOUND:")
        for m in report["mismatches"][:20]:
            print(f"  - mismatch: action={m.get('action')} case_key={m.get('case_key')}")
        for gap in report["coverage_gaps"][:20]:
            print(f"  - coverage gap (extend Gate 1/2, do not ignore): {gap}")
        return 2

    if not (report["meets_count_bar"] and report["meets_span_bar"]):
        print("[CHK-GUARD-SHADOW] Soak not yet sufficient - no problems found so far, re-run later.")
        return 1

    print("[CHK-GUARD-SHADOW] Gate 3: PASS (soak bar met, zero mismatches, zero coverage gaps).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
