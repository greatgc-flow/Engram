"""Benchmark F — IPC filename collision probability.

Naming scheme: {peer_id}-{YYYYMMDDHHMMSS}-{RAND4}.txt
Analyzes collision risk via birthday paradox math + Monte Carlo simulation.
"""
from __future__ import annotations

import math
import random
import string
import time
from collections import defaultdict

PEER_IDS = ["gc", "cx", "ag", "cc"]
RAND_CHARS = string.ascii_lowercase + string.digits  # 36 chars
RAND_LEN = 4
RAND_SPACE = len(RAND_CHARS) ** RAND_LEN  # 36^4 = 1,679,616

CALLS_PER_SEC_SCENARIOS = [1, 5, 10, 25, 50, 100]
MONTE_CARLO_TRIALS = 100_000


def birthday_collision_prob(n: int, space: int) -> float:
    """P(at least one collision) among n draws from uniform space."""
    if n > space:
        return 1.0
    log_p_no_coll = sum(math.log(1 - k / space) for k in range(n))
    return 1.0 - math.exp(log_p_no_coll)


def gen_filename(peer_id: str, ts_sec: int) -> str:
    rand = "".join(random.choices(RAND_CHARS, k=RAND_LEN))
    return f"{peer_id}-{ts_sec:014d}-{rand}.txt"


def monte_carlo_collision_rate(calls_per_sec: int, window_sec: int = 1,
                               trials: int = MONTE_CARLO_TRIALS) -> float:
    """Simulate `trials` batches of `calls_per_sec` calls in one second window."""
    collisions = 0
    for _ in range(trials):
        ts = 20260619120000  # fixed timestamp (same second)
        seen = set()
        hit = False
        for _ in range(calls_per_sec):
            peer = random.choice(PEER_IDS)
            fn = gen_filename(peer, ts)
            if fn in seen:
                hit = True
                break
            seen.add(fn)
        if hit:
            collisions += 1
    return collisions / trials


# ── Main ─────────────────────────────────────────────────────────────────────

print("=" * 70)
print("  BENCHMARK F — IPC filename collision probability")
print(f"  Scheme: {{peer_id}}-{{YYYYMMDDHHMMSS}}-{{RAND4}}.txt")
print(f"  RAND4 space: {len(RAND_CHARS)}^{RAND_LEN} = {RAND_SPACE:,} combinations")
print(f"  Peers: {PEER_IDS}  (per-peer space = {RAND_SPACE:,})")
print("=" * 70)
print()

# Section 1: Birthday paradox math
print("  1. Birthday paradox — P(collision) per second window")
print(f"  {'Calls/sec':>10}  {'Math P(coll)':>14}  {'Per-peer space':>16}  {'1-in-N':>10}")
print("-" * 60)

for cps in CALLS_PER_SEC_SCENARIOS:
    # Each peer gets ~cps/4 calls; per-peer same-second collision
    per_peer = max(1, cps // len(PEER_IDS))
    p = birthday_collision_prob(cps, RAND_SPACE)  # all peers, shared same-second window
    p_per_peer = birthday_collision_prob(per_peer, RAND_SPACE)
    one_in_n = f"1 in {int(1/p):,}" if p > 0 else "never"
    print(f"  {cps:>10}  {p:>13.2e}  {per_peer:>6} calls/peer  {one_in_n:>10}")

print()

# Section 2: Monte Carlo validation
print("  2. Monte Carlo simulation (same-second burst)")
print(f"  Trials per scenario: {MONTE_CARLO_TRIALS:,}")
print(f"  {'Calls/sec':>10}  {'Simulated P':>12}  {'Agreement':>10}")
print("-" * 45)

for cps in [1, 5, 10, 25, 50]:
    t0 = time.perf_counter()
    sim_p = monte_carlo_collision_rate(cps)
    elapsed = time.perf_counter() - t0
    math_p = birthday_collision_prob(cps, RAND_SPACE)
    agree = "OK" if abs(sim_p - math_p) < max(math_p * 2, 1e-5) else "DRIFT"
    print(f"  {cps:>10}  {sim_p:>11.2e}  {agree:>10}   ({elapsed*1000:.0f}ms)")

print()

# Section 3: Practical recommendation
print("  3. Practical risk assessment")
print("-" * 70)

safe_threshold = 1e-9  # 1-in-billion
risky_threshold = 1e-6  # 1-in-million

for cps in CALLS_PER_SEC_SCENARIOS:
    p = birthday_collision_prob(cps, RAND_SPACE)
    if p < safe_threshold:
        verdict = "SAFE (< 1 in 10^9)"
    elif p < risky_threshold:
        verdict = "ACCEPTABLE (< 1 in 10^6)"
    elif p < 1e-3:
        verdict = "MONITOR (< 1 in 1000)"
    else:
        verdict = "RISKY"
    print(f"  {cps:>4} calls/sec  p={p:.2e}  → {verdict}")

print()

# Section 4: Time granularity analysis
print("  4. Sub-second burst analysis (calls within same timestamp)")
print("  If 2 calls happen within the same second (ts identical):")
p2 = birthday_collision_prob(2, RAND_SPACE)
print(f"  P(collision | 2 simultaneous calls) = {p2:.2e}")
print(f"  → 1 in {int(1/p2):,} — acceptable for production use")
print()

# Section 5: Current load estimate
print("  5. Estimated real-world load")
print("  Typical R:10 session: 4 peers × 3 actions/phase × 4 phases/hr = 48 calls/hr")
print(f"  = 0.013 calls/sec average — essentially never collide")
p_typical = birthday_collision_prob(1, RAND_SPACE)
print(f"  Peak burst (all 4 peers simultaneous): p = {birthday_collision_prob(4, RAND_SPACE):.2e}")
print()
print("  Conclusion: RAND4 provides adequate collision resistance for Engram's")
print(f"  load profile. Upgrade to RAND6 (36^6 = 2.2 billion) if calls/sec > 100.")
print()
print("  Done.")
