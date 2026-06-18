"""Benchmark A — Concurrency stress test: 50 parallel hub.py processes.

Tests race conditions on shared files (health.json, lease files) under
concurrent load. Measures throughput and verifies zero data corruption.
"""
from __future__ import annotations

import concurrent.futures
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PYTHON = str(Path(__file__).parent.parent / "env" / "venv" / "Scripts" / "python.exe")
HUB = str(Path(__file__).parent.parent / "core" / "hub.py")

# Actions that are read-heavy or write lightweight shared state
ACTIONS: list[tuple[str, list[str]]] = [
    ("health-check",  ["health-check"]),
    ("peer-status",   ["peer-status", "--peer", "gc"]),
    ("peer-status",   ["peer-status", "--peer", "cc"]),
    ("context-hash",  ["context-hash", "--msg", "stress-test"]),
    ("lease-status",  ["lease-status"]),
]

CONCURRENCY_LEVELS = [1, 5, 10, 25, 50]
RUNS_PER_LEVEL = 30  # total tasks at each concurrency level


def run_action(action_args: list[str]) -> tuple[str, float, int]:
    """Run one hub.py action. Returns (action_name, elapsed_sec, returncode)."""
    name = action_args[0]
    cmd = [PYTHON, HUB] + action_args
    t0 = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, timeout=15)
    elapsed = time.perf_counter() - t0
    return name, elapsed, result.returncode


def benchmark_concurrency(workers: int, n_tasks: int) -> dict:
    """Run n_tasks hub actions with `workers` parallel threads."""
    import itertools
    task_pool = list(itertools.islice(
        itertools.cycle(ACTIONS), n_tasks
    ))

    results: list[tuple[str, float, int]] = []
    t_wall_start = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as exe:
        futs = [exe.submit(run_action, args) for _, args in task_pool]
        for f in concurrent.futures.as_completed(futs):
            try:
                results.append(f.result())
            except Exception as exc:
                results.append(("ERROR", 0.0, -1))

    wall = time.perf_counter() - t_wall_start
    successes = sum(1 for _, _, rc in results if rc == 0)
    failures  = len(results) - successes
    latencies = sorted(r[1] for r in results)
    p50 = latencies[len(latencies) // 2] * 1000
    p95 = latencies[int(len(latencies) * 0.95)] * 1000
    p99 = latencies[min(int(len(latencies) * 0.99), len(latencies) - 1)] * 1000
    rps = n_tasks / wall

    return {
        "workers":   workers,
        "tasks":     n_tasks,
        "wall_sec":  round(wall, 3),
        "rps":       round(rps, 1),
        "success":   successes,
        "failure":   failures,
        "p50_ms":    round(p50, 1),
        "p95_ms":    round(p95, 1),
        "p99_ms":    round(p99, 1),
        "fail_rate": f"{failures/len(results)*100:.1f}%",
    }


def check_health_json_integrity() -> tuple[bool, str]:
    """Run 20 parallel health-check calls then verify health.json is valid JSON."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
        futs = [exe.submit(run_action, ["health-check"]) for _ in range(20)]
        concurrent.futures.wait(futs)

    # Check each peer's health.json
    ai_dir = Path(HUB).parent.parent / "ai"
    peers_data = json.loads((ai_dir / "peers.json").read_text(encoding="utf-8"))
    sys_dir = Path(HUB).parent.parent

    corrupt = []
    for peer_name in peers_data.get("peers", {}):
        hfile = sys_dir / peer_name / "health.json"
        if not hfile.exists():
            continue
        try:
            json.loads(hfile.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            corrupt.append(f"{hfile.name}: {e}")

    ok = len(corrupt) == 0
    detail = "all valid" if ok else " | ".join(corrupt)
    return ok, detail


# ── Main ─────────────────────────────────────────────────────────────────────

print("=" * 72)
print("  BENCHMARK A — Concurrency stress test")
print(f"  {RUNS_PER_LEVEL} tasks per concurrency level across {len(ACTIONS)} action types")
print("=" * 72)
print()

# Warmup
print("  [warmup] 3 sequential runs...")
for _, args in ACTIONS[:3]:
    run_action(args)
print()

# Main sweep
all_results = []
print(f"  {'Workers':>8}  {'Tasks':>6}  {'Wall(s)':>8}  {'RPS':>7}  "
      f"{'p50ms':>7}  {'p95ms':>7}  {'p99ms':>7}  {'Fail%':>6}  {'OK?':>5}")
print("-" * 72)

for workers in CONCURRENCY_LEVELS:
    r = benchmark_concurrency(workers, RUNS_PER_LEVEL)
    all_results.append(r)
    ok = "YES" if r["failure"] == 0 else f"NO({r['failure']})"
    print(f"  {r['workers']:>8}  {r['tasks']:>6}  {r['wall_sec']:>8.2f}  "
          f"{r['rps']:>7.1f}  {r['p50_ms']:>7.1f}  {r['p95_ms']:>7.1f}  "
          f"{r['p99_ms']:>7.1f}  {r['fail_rate']:>6}  {ok:>5}")

# Integrity check
print()
print("=" * 72)
print("  INTEGRITY CHECK — health.json corruption after 20 concurrent writes")
print("=" * 72)
ok, detail = check_health_json_integrity()
status = "PASS" if ok else "FAIL"
print(f"  Result : {status}")
print(f"  Detail : {detail}")

# Summary
print()
print("=" * 72)
print("  SUMMARY")
print("=" * 72)
total_tasks = sum(r["tasks"] for r in all_results)
total_failures = sum(r["failure"] for r in all_results)
peak_rps = max(r["rps"] for r in all_results)
peak_workers = next(r["workers"] for r in all_results if r["rps"] == peak_rps)
print(f"  Total tasks run   : {total_tasks}")
print(f"  Total failures    : {total_failures}")
print(f"  Overall fail rate : {total_failures/total_tasks*100:.2f}%")
print(f"  Peak throughput   : {peak_rps:.1f} RPS @ {peak_workers} workers")
print(f"  File integrity    : {'OK' if ok else 'CORRUPTED'}")
print()
print("  Done.")
