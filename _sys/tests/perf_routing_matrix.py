"""Benchmark G — Routing MECE matrix.

Parses routing-config.json (R01-R12 weight entries) and model-registry.json
to produce a full routing decision breakdown: peer × model × effort × context_mode.
"""
from __future__ import annotations

import json
from pathlib import Path

SYS = Path(__file__).parent.parent

routing_cfg  = json.loads((SYS / "ai" / "routing-config.json").read_text(encoding="utf-8"))
registry     = json.loads((SYS / "ai" / "model-registry.json").read_text(encoding="utf-8"))
MODELS       = registry.get("models", {})

routing_weights  = routing_cfg.get("routing_weights", {})
task_overrides   = routing_cfg.get("task_overrides", {})
current_qmode    = routing_cfg.get("quality_mode", "?")
qmode_override   = routing_cfg.get("quality_mode_override", None)


def parse_route_spec(spec: str) -> dict:
    """Parse 'peer::model::effort::context_mode' into a dict."""
    parts = spec.split("::")
    return {
        "peer":         parts[0] if len(parts) > 0 else "?",
        "model":        parts[1] if len(parts) > 1 else "?",
        "effort":       parts[2] if len(parts) > 2 else "none",
        "context_mode": parts[3] if len(parts) > 3 else "none",
    }


def get_model_ctx(model_id: str) -> str:
    cfg = MODELS.get(model_id, {})
    ctx = cfg.get("context_limit", 0)
    return f"{ctx//1000}k" if ctx else "?"


def get_effort_label(model_id: str, effort: str) -> str:
    cfg = MODELS.get(model_id, {})
    rtype = cfg.get("reasoning_type", "none")
    params = cfg.get("reasoning_params", {})
    if rtype == "adaptive":
        valid = params.get("effort", [])
    elif rtype == "reasoning_effort":
        valid = params.get("effort_levels", [])
    elif rtype == "thinking_budget":
        br = params.get("budget_range", [0, 0])
        return f"budget:{br[0]}-{br[1]}"
    else:
        valid = []
    if effort in valid:
        return effort
    if effort == "none" and not valid:
        return "standard"
    return f"{effort}(?)"


# ── Print ─────────────────────────────────────────────────────────────────────

print("=" * 100)
print("  BENCHMARK G — Routing decision MECE matrix")
print(f"  Current quality_mode: {current_qmode}"
      + (f" (override: {qmode_override})" if qmode_override else ""))
print(f"  Routes: {len(routing_weights)}  |  Task overrides: {len(task_overrides)}")
print("=" * 100)
print()

# Section 1: Route table
print("  ROUTE TABLE (primary/fallback per routing slot)")
print(f"  {'ID':<5}  {'Label':<24}  {'Wt':>4}  {'Primary':^50}  {'Fallback':^40}")
print("-" * 130)

peer_counts: dict[str, int] = {}
model_counts: dict[str, int] = {}
effort_counts: dict[str, int] = {}

for rid, route in sorted(routing_weights.items()):
    label   = route.get("_label", "")
    weight  = route.get("weight", 1.0)
    primary = route.get("primary", "")
    fallback = route.get("fallback", "")

    p = parse_route_spec(primary)
    f = parse_route_spec(fallback)

    ctx_p = get_model_ctx(p["model"])
    eff_p = get_effort_label(p["model"], p["effort"])
    ctx_f = get_model_ctx(f["model"])
    eff_f = get_effort_label(f["model"], f["effort"])

    p_str = f"{p['peer']}::{p['model']}  [{eff_p}, ctx={ctx_p}]"
    f_str = f"{f['peer']}::{f['model']}  [{eff_f}]"

    print(f"  {rid:<5}  {label:<24}  {weight:>4.1f}  {p_str:<50}  {f_str}")

    # Count primaries
    peer_counts[p["peer"]] = peer_counts.get(p["peer"], 0) + 1
    model_counts[p["model"]] = model_counts.get(p["model"], 0) + 1
    effort_counts[p["effort"]] = effort_counts.get(p["effort"], 0) + 1

print()

# Section 2: Primary node distribution
print("=" * 100)
print("  PRIMARY NODE DISTRIBUTION")
print("=" * 100)
total = len(routing_weights)
print(f"\n  By peer:")
for peer, cnt in sorted(peer_counts.items(), key=lambda x: -x[1]):
    bar = "#" * int(cnt / total * 40)
    print(f"    {peer:<8} {cnt:>3}/{total}  ({cnt/total*100:.0f}%)  |{bar}")

print(f"\n  By model:")
for model, cnt in sorted(model_counts.items(), key=lambda x: -x[1]):
    print(f"    {model:<40} {cnt:>3}/{total}  ({cnt/total*100:.0f}%)")

print(f"\n  By effort level (primary):")
for effort, cnt in sorted(effort_counts.items(), key=lambda x: -x[1]):
    print(f"    {effort:<10} {cnt:>3}/{total}  ({cnt/total*100:.0f}%)")

# Section 3: MECE model coverage
print()
print("=" * 100)
print("  MODEL COVERAGE CHECK (which models appear in routing vs registry)")
print("=" * 100)
routed_models: set[str] = set()
for route in routing_weights.values():
    for spec_key in ("primary", "fallback"):
        spec = route.get(spec_key, "")
        if spec:
            routed_models.add(parse_route_spec(spec)["model"])

all_models = set(MODELS.keys())
in_routing_only = routed_models - all_models
in_registry_only = all_models - routed_models
in_both = routed_models & all_models

print(f"  Registry models    : {len(all_models)}")
print(f"  Routed models      : {len(routed_models)}")
print(f"  In both            : {len(in_both)}")
if in_routing_only:
    print(f"  In routing ONLY (not in registry!) : {sorted(in_routing_only)}")
if in_registry_only:
    print(f"  In registry only (not routed)       : {sorted(in_registry_only)}")

# Section 4: Task override matrix
print()
print("=" * 100)
print("  TASK OVERRIDE SCORES (additive to quality_mode routing weight)")
print("=" * 100)
for task, score in sorted(task_overrides.items(), key=lambda x: -x[1]):
    bar = "#" * int(score) if score > 0 else ""
    print(f"  {task:<25} score={score:>3}  |{bar}")

print()
print("  Done.")
