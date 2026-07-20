"""operational_guard_matrix.py - independent oracle for INV-26 guard decisions.

D2's promotion bar (cc.fable, ratified 2026-07-08) requires the guard's actual
decision function (hub.py:_guard_action_dry_run) to be cross-checked against an
INDEPENDENTLY-derived expected result - computed straight from protocol.json /
orchestration.json config, without calling hub.py's own logic - so that a bug in
_guard_action_dry_run itself would actually be caught (checking the function
against itself would be tautological).

Cases are bucketed on collab_rate/coordinator_health/worker_tier rather than
enumerating every raw value, because the real guard only branches on the
threshold comparison (>=) and a categorical health-state membership test (see
hub.py's `current >= threshold` and `peer_state not in (...)`) - bucketing
preserves full branch coverage without combinatorial blowup (ag-verified
2026-07-11 against the live operators).
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

TIER_ORDER = {"standard": 0, "effort": 1, "deepthink": 2, "fable": 3}
RECOVERY_COORDINATOR_STATES = ("RED", "STALE", "RATE_LIMITED", "MISSING")

# Mirrors hub.py's _SYSTEM_EXEMPT_ACTIONS exactly (kept as an independent literal,
# not imported from hub.py, so this oracle can't silently inherit a hub.py bug).
SYSTEM_EXEMPT_ACTIONS = {
    "consensus-sweep", "health-sweep", "freshness-sweep", "health-update", "health-check",
    "health-precheck", "transient-scan", "lease-sweep", "lesson-sweep",
    "update-signatures", "init-session", "end-session", "context-fill",
    "context-hash", "context-ack", "peer-recover", "peer-quarantine",
}

ACTION_GROUP_KEYS = (
    "read_only_hub_actions",
    "recovery_hub_actions",
    "semi_governed_hub_actions",
    "mutating_hub_actions",
)


@dataclass(frozen=True)
class GuardCase:
    action: str
    origin: str
    phase_key: str  # "unset" | "default" | "no_code"
    force_tier0: bool
    collab_bucket: str  # "below_threshold" | "at_or_above_threshold"
    finalized_consensus: bool
    coordinator_bucket: str  # "healthy" | "recovery"
    worker_tier: str = "standard"

    def case_key(self) -> str:
        return "|".join([
            f"action={self.action}",
            f"origin={self.origin}",
            f"phase={self.phase_key}",
            f"force={int(self.force_tier0)}",
            f"collab={self.collab_bucket}",
            f"consensus={int(self.finalized_consensus)}",
            f"coord={self.coordinator_bucket}",
            f"worker_tier={self.worker_tier if self.origin == 'worker' else '-'}",
        ])


@dataclass(frozen=True)
class ExpectedDecision:
    would_block: bool
    matched_rule: str | None
    action_group: str | None
    code: int = 0


def action_group(action: str, cfg: dict) -> str:
    for group in ACTION_GROUP_KEYS:
        if action in set(cfg.get(group, [])):
            return group
    return "unknown_actions"


def is_mutating(action: str, cfg: dict) -> bool:
    return action in set(cfg.get("mutating_hub_actions", []))


def _origin_tier(origin: str, worker_tier: str, orchestration: dict) -> str:
    if origin == "terminal":
        return "standard"
    if "." in origin:
        return origin.split(".", 1)[1]
    if origin == "worker":
        return worker_tier
    for node in orchestration.get("hub_nodes", []):
        if node.get("node_id") == origin:
            return node.get("default_profile", "standard")
    return "standard"


def expected_decision(case: GuardCase, cfg: dict, orchestration: dict) -> ExpectedDecision:
    """Independently mirrors _guard_action_dry_run's rule order (hub.py:6174-6313):
    1. disabled/force bypass, 2. terminal-mutating PRO-19, 3. tier floor,
    4. collab-rate finalized-consensus gate, 5. semi-governed healthy-coordinator
    gate, 6. missing-phase policy, 7. phase_action_matrix lookup."""
    if not cfg.get("enabled", False) or case.force_tier0:
        return ExpectedDecision(would_block=False, matched_rule=None, action_group=None, code=0)

    group = action_group(case.action, cfg)

    if case.origin == "terminal" and case.action not in SYSTEM_EXEMPT_ACTIONS:
        if is_mutating(case.action, cfg):
            return ExpectedDecision(would_block=True, matched_rule="pro19_terminal_mutating", action_group=group, code=3)

    if case.action not in SYSTEM_EXEMPT_ACTIONS:
        tier_floor = cfg.get("decision_tier_floor", {})
        if tier_floor.get("enabled", False) and is_mutating(case.action, cfg):
            required_tier = tier_floor.get("mutating_hub_actions_min_tier", "effort")
            origin_tier = _origin_tier(case.origin, case.worker_tier, orchestration)
            if TIER_ORDER.get(origin_tier, 0) < TIER_ORDER.get(required_tier, 1):
                return ExpectedDecision(would_block=True, matched_rule="tier_floor", action_group=group, code=3)

    rate_guard = cfg.get("collab_rate_guard", {})
    exempt = set(rate_guard.get("exempt_actions", []))
    if (
        rate_guard.get("enabled", False)
        and case.collab_bucket == "at_or_above_threshold"
        and case.action not in exempt
        and is_mutating(case.action, cfg)
        and rate_guard.get("require_finalized_consensus", True)
        and not case.finalized_consensus
    ):
        return ExpectedDecision(would_block=True, matched_rule="collab_rate_guard", action_group=group, code=3)

    if group == "semi_governed_hub_actions" and case.coordinator_bucket == "healthy":
        if rate_guard.get("enabled", False) and case.collab_bucket == "at_or_above_threshold" and not case.finalized_consensus:
            return ExpectedDecision(would_block=True, matched_rule="semi_governed_consensus", action_group=group, code=3)

    if case.phase_key == "unset":
        if cfg.get("missing_phase_policy") == "allow_with_warning":
            return ExpectedDecision(would_block=False, matched_rule=None, action_group=group, code=0)
        if not cfg.get("allow_missing_phase", True):
            return ExpectedDecision(would_block=True, matched_rule="missing_phase_policy", action_group=group, code=3)
        return ExpectedDecision(would_block=False, matched_rule=None, action_group=group, code=0)

    matrix = cfg.get("phase_action_matrix", {})
    matrix_key = "no_code" if case.phase_key == "no_code" else "default"
    decision = matrix.get(matrix_key, matrix.get("default", {})).get(group, "allow")
    if decision == "block":
        return ExpectedDecision(would_block=True, matched_rule="phase_action_matrix", action_group=group, code=3)
    if decision == "requires_classification":
        return ExpectedDecision(would_block=True, matched_rule="phase_requires_classification", action_group=group, code=3)

    return ExpectedDecision(would_block=False, matched_rule=None, action_group=group, code=0)


def enumerate_actions(cfg: dict) -> set[str]:
    actions: set[str] = set()
    for group in ACTION_GROUP_KEYS:
        actions.update(cfg.get(group, []))
    actions.update(cfg.get("collab_rate_guard", {}).get("exempt_actions", []))
    actions.update(SYSTEM_EXEMPT_ACTIONS)
    actions.add("__unknown_probe_action__")  # synthetic: not in any declared group
    return actions


def enumerate_origins(orchestration: dict) -> set[str]:
    origins = {"terminal", "worker"}
    for node in orchestration.get("hub_nodes", []):
        node_id = node.get("node_id")
        if node_id:
            origins.add(node_id)
    origins.update({"ag.effort", "ag.deepthink", "cx.effort", "cx.standard", "cc.fable"})
    return origins


def enumerate_cases(cfg: dict, orchestration: dict) -> list[GuardCase]:
    """Full exhaustive case set for Gate 1 (D2). Every declared action x every
    origin x every phase bucket x force-bypass x collab/consensus/coordinator
    buckets. origin="worker" additionally varies worker_tier (the only case
    shape where it's load-bearing, per _origin_tier)."""
    actions = enumerate_actions(cfg)
    origins = enumerate_origins(orchestration)
    phase_keys = ("unset", "default", "no_code")
    force_options = (False, True)
    collab_buckets = ("below_threshold", "at_or_above_threshold")
    consensus_options = (False, True)
    coordinator_buckets = ("healthy", "recovery")
    worker_tiers = ("standard", "effort", "deepthink")

    cases: list[GuardCase] = []
    for action, origin, phase_key, force, collab_bucket, consensus, coord_bucket in product(
        actions, origins, phase_keys, force_options, collab_buckets, consensus_options, coordinator_buckets,
    ):
        if origin == "worker":
            for wt in worker_tiers:
                cases.append(GuardCase(action, origin, phase_key, force, collab_bucket, consensus, coord_bucket, wt))
        else:
            cases.append(GuardCase(action, origin, phase_key, force, collab_bucket, consensus, coord_bucket))
    return cases


def stratified_sample_for_shuffle(cases: list[GuardCase], cfg: dict, orchestration: dict, max_per_bucket: int = 3) -> list[GuardCase]:
    """Gate 2 doesn't need to reshuffle all ~50k Gate-1 cases (expensive with real
    hub.py I/O per case) to meaningfully test order-independence - it needs at
    least one representative per distinct (action_group, matched_rule) outcome.
    Picks up to max_per_bucket cases per outcome bucket, deterministically (by
    case_key sort, not insertion order) so the sample itself doesn't depend on
    enumeration order."""
    buckets: dict[tuple[str | None, str | None], list[GuardCase]] = {}
    for case in sorted(cases, key=lambda c: c.case_key()):
        decision = expected_decision(case, cfg, orchestration)
        bucket_key = (decision.action_group, decision.matched_rule)
        buckets.setdefault(bucket_key, [])
        if len(buckets[bucket_key]) < max_per_bucket:
            buckets[bucket_key].append(case)
    sample: list[GuardCase] = []
    for key in sorted(buckets.keys(), key=lambda k: (k[0] or "", k[1] or "")):
        sample.extend(buckets[key])
    return sample
