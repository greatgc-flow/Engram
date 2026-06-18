"""Benchmark C — End-to-end hub.py pipeline latency breakdown.

Stages timed per call:
  spawn  : Popen() to first byte readable
  run    : communicate() wall time
  total  : full round-trip
"""
from __future__ import annotations

import concurrent.futures
import statistics
import subprocess
import sys
import time
from pathlib import Path

PYTHON = str(Path(__file__).parent.parent / "env" / "venv" / "Scripts" / "python.exe")
HUB    = str(Path(__file__).parent.parent / "core" / "hub.py")

SEQ_RUNS = 40
PAR_RUNS = 40
PAR_WORKERS = 10

CMD_BASE = [PYTHON, HUB, "context-hash", "--msg"]


def run_one(i: int) -> dict:
    cmd = CMD_BASE + [f"pipeline-bench-{i}"]
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    t_spawned = time.perf_counter()
    out, err = proc.communicate()
    t_done = time.perf_counter()
    return {
        "spawn_ms": (t_spawned - t0) * 1000,
        "run_ms":   (t_done - t_spawned) * 1000,
        "total_ms": (t_done - t0) * 1000,
        "rc": proc.returncode,
    }


def percentile(data: list[float], pct: float) -> float:
    s = sorted(data)
    idx = int(len(s) * pct / 100)
    return s[min(idx, len(s) - 1)]


def print_stage_table(label: str, results: list[dict]) -> None:
    for stage in ("spawn_ms", "run_ms", "total_ms"):
        vals = [r[stage] for r in results]
        p50  = percentile(vals, 50)
        p95  = percentile(vals, 95)
        p99  = percentile(vals, 99)
        mx   = max(vals)
        mn   = min(vals)
        name = stage.replace("_ms", "").ljust(6)
        print(f"  {name}  {p50:>8.1f}  {p95:>8.1f}  {p99:>8.1f}  {mx:>8.1f}  {mn:>8.1f}")


# ── Sequential ────────────────────────────────────────────────────────────────

print("=" * 72)
print(f"  BENCHMARK C — hub.py pipeline latency  (action: context-hash)")
print("=" * 72)
print()
print(f"  [warmup] 3 sequential runs...")
for i in range(3):
    run_one(i)
print()

print(f"  Sequential: {SEQ_RUNS} runs")
t_wall = time.perf_counter()
seq_results = [run_one(i) for i in range(SEQ_RUNS)]
seq_wall = time.perf_counter() - t_wall
seq_rps = SEQ_RUNS / seq_wall
seq_failures = sum(1 for r in seq_results if r["rc"] != 0)

print(f"  {'Stage':<8}  {'p50(ms)':>8}  {'p95(ms)':>8}  {'p99(ms)':>8}  {'max(ms)':>8}  {'min(ms)':>8}")
print("-" * 60)
print_stage_table("sequential", seq_results)
print()
print(f"  Throughput : {seq_rps:.1f} RPS  |  Failures: {seq_failures}/{SEQ_RUNS}")

# ── Parallel ──────────────────────────────────────────────────────────────────

print()
print(f"  Parallel: {PAR_RUNS} runs @ {PAR_WORKERS} workers")
t_wall = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=PAR_WORKERS) as exe:
    futs = [exe.submit(run_one, i + 1000) for i in range(PAR_RUNS)]
    par_results = [f.result() for f in concurrent.futures.as_completed(futs)]
par_wall = time.perf_counter() - t_wall
par_rps = PAR_RUNS / par_wall
par_failures = sum(1 for r in par_results if r["rc"] != 0)

print(f"  {'Stage':<8}  {'p50(ms)':>8}  {'p95(ms)':>8}  {'p99(ms)':>8}  {'max(ms)':>8}  {'min(ms)':>8}")
print("-" * 60)
print_stage_table("parallel", par_results)
print()
print(f"  Throughput : {par_rps:.1f} RPS  |  Failures: {par_failures}/{PAR_RUNS}")

# ── Comparison ────────────────────────────────────────────────────────────────

speedup = par_rps / seq_rps
print()
print("=" * 72)
print("  COMPARISON")
print("=" * 72)
print(f"  Sequential RPS : {seq_rps:>8.1f}")
print(f"  Parallel RPS   : {par_rps:>8.1f}  ({PAR_WORKERS} workers)")
print(f"  Speedup factor : {speedup:>8.2f}x")

seq_total = [r["total_ms"] for r in seq_results]
par_total = [r["total_ms"] for r in par_results]
print()
print(f"  Pipeline breakdown (sequential p50):")
for stage in ("spawn_ms", "run_ms", "total_ms"):
    vals = [r[stage] for r in seq_results]
    p50 = percentile(vals, 50)
    pct_of_total = p50 / percentile(seq_total, 50) * 100
    bar = "#" * int(pct_of_total / 2)
    print(f"    {stage.replace('_ms',''):<6} {p50:>8.1f} ms  {pct_of_total:>5.1f}%  |{bar}")

print()
print("  Done.")
