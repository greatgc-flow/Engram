"""ContextGate Performance Benchmark — 16 models × text size × CJK ratio."""
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from hub_context import estimate_tokens, ContextGate

# ── Text generators ──────────────────────────────────────────────────────────

_KO = chr(0xAC00)  # avoid encoding issues regardless of shell/pipe context

def make_text(size: int, cjk_ratio: float) -> str:
    ko_count = int(size * cjk_ratio)
    return _KO * ko_count + "a" * (size - ko_count)

# ── Config ───────────────────────────────────────────────────────────────────

SIZES      = [1_000, 10_000, 50_000, 100_000, 500_000]
CJK_RATIOS = [0.0, 0.20, 0.50, 1.0]
ITERS      = 300

registry = json.loads((Path(__file__).parent.parent / "ai" / "model-registry.json").read_text(encoding="utf-8"))
MODELS   = {mid: cfg for mid, cfg in registry["models"].items() if cfg.get("status") not in ("EOL",)}
MODEL_IDS = sorted(MODELS.keys())

gate = ContextGate()

# ── 1. Throughput benchmark: estimate_tokens() ───────────────────────────────

print("=" * 70)
print("  BENCHMARK 1 — estimate_tokens() throughput")
print("=" * 70)
print(f"  {'CJK%':>5}  {'Size':>8}  {'Chars/sec':>14}  {'Tokens/sec':>12}  {'ms/call':>8}")
print("-" * 70)

for cjk in CJK_RATIOS:
    for sz in [10_000, 100_000, 500_000]:
        text = make_text(sz, cjk)
        t0 = time.perf_counter()
        for _ in range(ITERS):
            estimate_tokens(text)
        elapsed = time.perf_counter() - t0
        chars_sec = int(sz * ITERS / elapsed)
        toks = estimate_tokens(text)
        toks_sec = int(toks * ITERS / elapsed)
        ms_call = elapsed / ITERS * 1000
        print(f"  {int(cjk*100):>4}%  {sz:>8,}  {chars_sec:>14,}  {toks_sec:>12,}  {ms_call:>7.4f}")
    print()

# ── 2. ContextGate check() across 16 models ─────────────────────────────────

print("=" * 70)
print("  BENCHMARK 2 — ContextGate.check() utilization matrix")
print(f"  Text: 500k chars English | warn=80% failover=95%")
print("=" * 70)

text_en = make_text(500_000, 0.0)   # ~142k tokens
text_ko = make_text(500_000, 1.0)   # ~450k tokens

ZONE = {
    "pass":     "  ·  ",
    "prune":    " WARN",
    "failover": " FOVR",
    "reject":   " RJCT",
}

print(f"\n  {'Model':<35}  {'Limit':>9}  {'EN-500k':>8}  {'KO-500k':>8}  {'EN util':>8}  {'KO util':>8}")
print("-" * 90)

def _safe_check(g, text, mid):
    try:
        return g.check(text, mid)
    except Exception:
        est = estimate_tokens(text)
        lim = g.context_limit(mid)
        return {"action": "reject", "estimated_tokens": est, "utilization": est / lim if lim else 0}

for mid in MODEL_IDS:
    cfg = MODELS[mid]
    limit = cfg["context_limit"]
    r_en = _safe_check(gate, text_en, mid)
    r_ko = _safe_check(gate, text_ko, mid)
    en_tok = r_en["estimated_tokens"]
    ko_tok = r_ko["estimated_tokens"]
    en_pct = r_en["utilization"] * 100
    ko_pct = r_ko["utilization"] * 100
    en_act = ZONE.get(r_en["action"], "  ?  ")
    ko_act = ZONE.get(r_ko["action"], "  ?  ")
    print(f"  {mid:<35}  {limit:>9,}  {en_tok:>7,}{en_act}  {ko_tok:>7,}{ko_act}  {en_pct:>7.1f}%  {ko_pct:>7.1f}%")

# ── 3. Speed of gate.check() across all 16 models ───────────────────────────

print()
print("=" * 70)
print("  BENCHMARK 3 — gate.check() latency per model (10k en text, 500 iters)")
print("=" * 70)
text_sm = make_text(10_000, 0.0)
print(f"  {'Model':<35}  {'µs/call':>8}  {'calls/sec':>10}")
print("-" * 70)

for mid in MODEL_IDS:
    t0 = time.perf_counter()
    for _ in range(500):
        try:
            gate.check(text_sm, mid)
        except Exception:
            pass
    elapsed = time.perf_counter() - t0
    us = elapsed / 500 * 1_000_000
    cps = int(500 / elapsed)
    print(f"  {mid:<35}  {us:>7.1f}  {cps:>10,}")

print()
print("  Done.")
