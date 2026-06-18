"""Benchmark H — Effort × token cost projection matrix (MECE).

Uses actual model-registry.json field structure:
  reasoning_type: adaptive | reasoning_effort | thinking_budget | none
  reasoning_params: { effort:[], effort_levels:[], budget_range:[] }
  pricing: { input_per_1m, output_per_1m }
"""
from __future__ import annotations

import json
from pathlib import Path

SYS = Path(__file__).parent.parent
registry = json.loads((SYS / "ai" / "model-registry.json").read_text(encoding="utf-8"))
MODELS = {mid: cfg for mid, cfg in registry["models"].items()
          if cfg.get("status") not in ("EOL",)}

INPUT_TOKENS = 1000  # base for projections

# Reasoning token multipliers (empirical estimates, relative to 1k input)
# (min_reasoning_tokens, max_reasoning_tokens)
EFFORT_RANGES: dict[str, dict[str, tuple[int, int]]] = {
    "adaptive": {  # Claude extended thinking
        "low":    (200,   2000),
        "medium": (1000,  8000),
        "high":   (4000,  20000),
        "xhigh":  (10000, 40000),
        "max":    (20000, 80000),
    },
    "reasoning_effort": {  # OpenAI o-series / GPT-5
        "none":   (0,     0),
        "low":    (100,   1000),
        "medium": (500,   4000),
        "high":   (2000,  16000),
        "xhigh":  (6000,  40000),
    },
}

# Fallback pricing when registry has null
FALLBACK_PRICING: dict[str, tuple[float, float]] = {
    "claude-fable-5":              (3.0,   15.0),
    "claude-haiku-4-5-20251001":   (0.8,   4.0),
    "claude-mythos-5":             (15.0,  75.0),
    "claude-opus-4-7":             (15.0,  75.0),
    "claude-opus-4-8":             (15.0,  75.0),
    "claude-sonnet-4-6":           (3.0,   15.0),
    "gemini-2.5-pro":              (1.25,  10.0),
    "gemini-3-flash":              (0.1,   0.4),
    "gemini-3-pro":                (1.25,  5.0),
    "gemini-3.1-flash-lite":       (0.05,  0.2),
    "gemini-3.1-pro":              (1.25,  5.0),
    "gpt-5.4":                     (2.0,   8.0),
    "gpt-5.4-mini":                (0.15,  0.6),
    "gpt-5.5":                     (2.0,   8.0),
    "o3":                          (2.0,   8.0),
    "o3-pro":                      (10.0,  40.0),
}


def get_pricing(mid: str, cfg: dict) -> tuple[float, float]:
    p = cfg.get("pricing", {})
    inp = p.get("input_per_1m")
    out = p.get("output_per_1m")
    if inp is not None and out is not None:
        return float(inp), float(out)
    return FALLBACK_PRICING.get(mid, (1.0, 4.0))


def get_effort_entries(mid: str, cfg: dict) -> list[tuple[str, int, int]]:
    """Return (effort_label, min_reasoning_tokens, max_reasoning_tokens)."""
    rtype = cfg.get("reasoning_type", "none")
    params = cfg.get("reasoning_params", {})
    entries = []

    if rtype == "adaptive":
        efforts = params.get("effort", ["low", "medium", "high", "max"])
        ranges = EFFORT_RANGES["adaptive"]
        for e in efforts:
            lo, hi = ranges.get(e, (0, 0))
            entries.append((e, lo, hi))

    elif rtype == "reasoning_effort":
        efforts = params.get("effort_levels", ["low", "medium", "high"])
        ranges = EFFORT_RANGES["reasoning_effort"]
        for e in efforts:
            lo, hi = ranges.get(e, (0, 0))
            entries.append((e, lo, hi))

    elif rtype == "thinking_budget":
        br = params.get("budget_range", [0, 0])
        budget_min, budget_max = br[0], br[1]
        # Show 5 representative points across the range
        points = [0, budget_max // 4, budget_max // 2, budget_max * 3 // 4, budget_max]
        points = sorted(set(p for p in points if p <= budget_max))
        for bp in points:
            # thinking tokens ≈ budget_point (it's the cap, actual may be lower)
            entries.append((f"budget={bp}", int(bp * 0.3), bp))

    else:  # none / standard
        entries.append(("no-thinking", 0, 0))

    return entries


def cost_millicents(tokens: int, price_per_1m: float) -> float:
    return tokens / 1_000_000 * price_per_1m * 100_000  # millichoice: ¢ × 1000


# ── Main ─────────────────────────────────────────────────────────────────────

all_rows = []
for mid in sorted(MODELS.keys()):
    cfg = MODELS[mid]
    inp_price, out_price = get_pricing(mid, cfg)
    entries = get_effort_entries(mid, cfg)

    for effort_label, min_r, max_r in entries:
        avg_r = (min_r + max_r) / 2
        multiplier = avg_r / INPUT_TOKENS if avg_r > 0 else 0
        # Cost = input cost + output cost + reasoning cost (reasoning billed as output)
        base_cost = (INPUT_TOKENS / 1_000_000 * inp_price +
                     INPUT_TOKENS / 1_000_000 * out_price) * 1000  # millicents
        reason_cost_min = min_r / 1_000_000 * out_price * 1000
        reason_cost_max = max_r / 1_000_000 * out_price * 1000
        total_min = base_cost + reason_cost_min
        total_max = base_cost + reason_cost_max

        all_rows.append({
            "model": mid,
            "rtype": cfg.get("reasoning_type", "none"),
            "effort": effort_label,
            "min_r": min_r,
            "max_r": max_r,
            "multiplier": multiplier,
            "total_min_mc": total_min,
            "total_max_mc": total_max,
            "inp_price": inp_price,
            "out_price": out_price,
        })

# ── Print by model ────────────────────────────────────────────────────────────

print("=" * 110)
print("  BENCHMARK H — Effort × Token Cost Projection Matrix (MECE)")
print(f"  Base input: {INPUT_TOKENS} tokens | Costs in millicents (¢/1000)")
print(f"  Models: {len(MODELS)}  |  Total (model × effort) combinations: {len(all_rows)}")
print("=" * 110)
print()

GROUP_BY_RTYPE: dict[str, list] = {}
for row in all_rows:
    GROUP_BY_RTYPE.setdefault(row["rtype"], []).append(row)

RTYPE_LABELS = {
    "adaptive":         "Claude adaptive thinking (extended thinking API)",
    "reasoning_effort": "OpenAI reasoning effort (o-series + GPT-5)",
    "thinking_budget":  "Gemini thinking budget (budget_range param)",
    "none":             "No reasoning (standard output only)",
}

for rtype, rows in sorted(GROUP_BY_RTYPE.items()):
    print(f"  ── {RTYPE_LABELS.get(rtype, rtype)} ──")
    print(f"  {'Model':<40}  {'Effort':<15}  {'Reas-min':>9}  {'Reas-max':>9}  {'Mult':>6}  {'Cost-min(mc)':>12}  {'Cost-max(mc)':>12}")
    print(f"  {'-'*112}")

    current_model = None
    for row in rows:
        if row["model"] != current_model:
            current_model = row["model"]
            cfg = MODELS[current_model]
            ctx = cfg["context_limit"] // 1000
            out = cfg["output_limit"] // 1000
            status = cfg.get("status", "GA")
            inp_p, out_p = row["inp_price"], row["out_price"]
            print(f"\n  {current_model:<40}  [ctx={ctx}k out={out}k {status} | in=${inp_p:.2f} out=${out_p:.2f} /1M]")

        bar = "#" * min(int(row["multiplier"] * 3), 25)
        print(f"  {'':40}  {row['effort']:<15}  {row['min_r']:>9,}  {row['max_r']:>9,}  "
              f"{row['multiplier']:>6.1f}x  {row['total_min_mc']:>12.4f}  {row['total_max_mc']:>12.4f}  |{bar}")
    print()

# ── Effort ceiling ranking ────────────────────────────────────────────────────

print("=" * 110)
print("  REASONING CEILING RANKING (max effort, max reasoning tokens)")
print("=" * 110)
ceiling: dict[str, dict] = {}
for row in all_rows:
    mid = row["model"]
    if mid not in ceiling or row["max_r"] > ceiling[mid]["max_r"]:
        ceiling[mid] = row

sorted_ceiling = sorted(ceiling.items(), key=lambda x: -x[1]["max_r"])
print(f"  {'Model':<40}  {'Max Effort':<15}  {'Max Reas':>10}  {'Max Cost(mc)':>13}  {'Pricing'}")
print("-" * 105)
for mid, row in sorted_ceiling:
    stars = "★" * min(int(row["max_r"] / 10000), 5)
    print(f"  {mid:<40}  {row['effort']:<15}  {row['max_r']:>10,}  {row['total_max_mc']:>13.4f}  "
          f"in=${row['inp_price']:.2f} out=${row['out_price']:.2f}  {stars}")

# ── MECE check ────────────────────────────────────────────────────────────────

print()
print("  MECE CHECK")
covered = {row["model"] for row in all_rows}
all_model_ids = set(MODELS.keys())
missing = all_model_ids - covered
print(f"  Models with effort data  : {len(covered)}/{len(all_model_ids)}")
if missing:
    print(f"  Missing                  : {sorted(missing)}")
else:
    print(f"  All {len(all_model_ids)} models covered — MECE complete")
print(f"  Total (model×effort) rows: {len(all_rows)}")
print()
print("  Done.")
