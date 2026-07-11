"""check_operational_guard_matrix.py - D2 (INV-26 fail-closed) Gate 1 + Gate 2.

Gate 1: cross-checks operational_guard_matrix.py's INDEPENDENTLY-derived expected
decision against hub.py's real _guard_action_dry_run(), for every case in the
full exhaustive matrix (action x origin x phase x force x collab/consensus/
coordinator buckets - see operational_guard_matrix.enumerate_cases). Zero
mismatches required.

Gate 2: takes a stratified sample (one representative per distinct outcome
bucket - the full ~55k-case matrix is too expensive to reshuffle against the
real hub.py function, which does file I/O per call) and re-evaluates it against
the real function across N deterministically-shuffled orderings (fixed seed),
asserting the result never depends on evaluation order.

Neither gate flips any enforcement switch - INV-26 enforcement (_guard_action's
sys.exit on block) is already live (commit feadb3b). These gates build the
empirical confidence cc.fable's promotion bar requires before the policy is
considered validated; Gate 3 (live shadow soak, >=24h/>=100 real evaluations)
is a separate script (check_operational_guard_shadow.py).

Exit codes:
  0 on success
  2 on any mismatch
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub  # noqa: E402
import operational_guard_matrix as ogm  # noqa: E402

AI_ROOT = SYS_DIR / "ai"


def _phase_string_for_bucket(phase_key: str, cfg: dict) -> str | None:
    if phase_key == "unset":
        return None
    if phase_key == "no_code":
        no_code_phases = cfg.get("no_code_phases", [])
        return no_code_phases[0] if no_code_phases else "no_code"
    return "active"  # any phase not in no_code_phases maps to the "default" matrix key


class _RealGuardHarness:
    """Monkeypatches hub.py's state-getters so _guard_action_dry_run can be
    evaluated per-case without real file I/O (54k+ cases would be far too slow
    otherwise) - matches cx's D2 design (2026-07-11)."""

    def __init__(self, cfg: dict, orchestration: dict):
        self._cfg = cfg
        self._orchestration = orchestration
        self._case: ogm.GuardCase | None = None
        self._originals: dict[str, object] = {}
        self._orig_env_tier: str | None = None

    def __enter__(self) -> "_RealGuardHarness":
        self._originals["_load_protocol_cfg"] = hub._load_protocol_cfg
        self._originals["_current_phase"] = hub._current_phase
        self._originals["_has_finalized_consensus"] = hub._has_finalized_consensus
        self._originals["_current_coordinator_health"] = hub._current_coordinator_health
        self._orig_env_tier = os.environ.get("HUB_PEER_TIER")

        hub._load_protocol_cfg = self._fake_load_protocol_cfg
        hub._current_phase = self._fake_current_phase
        hub._has_finalized_consensus = self._fake_has_finalized_consensus
        hub._current_coordinator_health = self._fake_current_coordinator_health
        return self

    def __exit__(self, *exc_info) -> None:
        hub._load_protocol_cfg = self._originals["_load_protocol_cfg"]
        hub._current_phase = self._originals["_current_phase"]
        hub._has_finalized_consensus = self._originals["_has_finalized_consensus"]
        hub._current_coordinator_health = self._originals["_current_coordinator_health"]
        if self._orig_env_tier is None:
            os.environ.pop("HUB_PEER_TIER", None)
        else:
            os.environ["HUB_PEER_TIER"] = self._orig_env_tier

    def _fake_load_protocol_cfg(self) -> dict:
        threshold = int(self._cfg.get("collab_rate_guard", {}).get("threshold", 10) or 10)
        current = threshold if self._case.collab_bucket == "at_or_above_threshold" else max(0, threshold - 1)
        return {"operational_guard": self._cfg, "collab_rate": {"current": current}}

    def _fake_current_phase(self, ai_root: Path) -> str | None:
        return _phase_string_for_bucket(self._case.phase_key, self._cfg)

    def _fake_has_finalized_consensus(self, ai_root: Path) -> bool:
        return self._case.finalized_consensus

    def _fake_current_coordinator_health(self, ai_root: Path) -> str:
        return "GREEN" if self._case.coordinator_bucket == "healthy" else "RED"

    def real_decision_for(self, case: ogm.GuardCase) -> dict:
        self._case = case
        if case.origin == "worker":
            os.environ["HUB_PEER_TIER"] = case.worker_tier
        else:
            os.environ.pop("HUB_PEER_TIER", None)
        return hub._guard_action_dry_run(
            AI_ROOT, case.action, force_tier0=case.force_tier0, origin=case.origin, target_peer=None,
        )


def _mismatches(cases: list[ogm.GuardCase], cfg: dict, orchestration: dict) -> list[str]:
    problems: list[str] = []
    with _RealGuardHarness(cfg, orchestration) as harness:
        for case in cases:
            expected = ogm.expected_decision(case, cfg, orchestration)
            real = harness.real_decision_for(case)
            real_would_block = bool(real.get("would_block"))
            if real_would_block != expected.would_block:
                problems.append(
                    f"MISMATCH {case.case_key()}: expected would_block={expected.would_block} "
                    f"(rule={expected.matched_rule}), real would_block={real_would_block} "
                    f"(rule={real.get('matched_rule')})"
                )
            elif expected.would_block and real.get("matched_rule") != expected.matched_rule:
                problems.append(
                    f"RULE MISMATCH {case.case_key()}: expected matched_rule={expected.matched_rule}, "
                    f"real matched_rule={real.get('matched_rule')}"
                )
    return problems


def gate1(cfg: dict, orchestration: dict) -> tuple[list[ogm.GuardCase], list[str]]:
    cases = ogm.enumerate_cases(cfg, orchestration)
    return cases, _mismatches(cases, cfg, orchestration)


def gate2(cases: list[ogm.GuardCase], cfg: dict, orchestration: dict, passes: int, seed: int) -> list[str]:
    sample = ogm.stratified_sample_for_shuffle(cases, cfg, orchestration)
    problems: list[str] = []
    rng = random.Random(seed)
    for i in range(passes):
        shuffled = sample[:]
        rng.shuffle(shuffled)
        pass_problems = _mismatches(shuffled, cfg, orchestration)
        if pass_problems:
            problems.append(f"shuffle pass {i}: {len(pass_problems)} mismatch(es)")
            problems.extend(pass_problems)
    return problems


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--shuffle-passes", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260711)
    args = parser.parse_args(argv)

    cfg = hub._load_protocol_cfg().get("operational_guard", {})
    orchestration = hub._load_orchestration()

    print("[CHK-GUARD-MATRIX] Gate 1: exhaustive matrix cross-check...")
    cases, gate1_problems = gate1(cfg, orchestration)
    print(f"[CHK-GUARD-MATRIX] Gate 1: {len(cases)} cases evaluated.")
    if gate1_problems:
        print("[CHK-GUARD-MATRIX] Gate 1 FAILED:")
        for p in gate1_problems[:50]:
            print(f"  - {p}")
        if len(gate1_problems) > 50:
            print(f"  ... and {len(gate1_problems) - 50} more")
        return 2
    print("[CHK-GUARD-MATRIX] Gate 1: PASS (zero mismatches).")

    print(f"[CHK-GUARD-MATRIX] Gate 2: {args.shuffle_passes}-pass shuffle (seed={args.seed})...")
    gate2_problems = gate2(cases, cfg, orchestration, args.shuffle_passes, args.seed)
    if gate2_problems:
        print("[CHK-GUARD-MATRIX] Gate 2 FAILED:")
        for p in gate2_problems[:50]:
            print(f"  - {p}")
        return 2
    print("[CHK-GUARD-MATRIX] Gate 2: PASS (order-independent across all passes).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
