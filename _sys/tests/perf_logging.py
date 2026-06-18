"""Benchmark D — hub_logging.py rolling I/O: 10,000 records, gzip roll detection."""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from hub_logging import HubLogger  # noqa: E402

TOTAL_RECORDS = 10_000
ROLL_TRIGGER_KB = 50  # small so we see multiple rolls


def make_config(log_dir: Path) -> Path:
    cfg = {
        "log_dir": str(log_dir),
        "types": {
            "ipc-log":      {"file": "ipc.jsonl"},
            "cost-log":     {"file": "cost.jsonl"},
            "error-log":    {"file": "error.jsonl"},
            "reasoning-log":{"file": "reasoning.jsonl"},
        },
        "rolling": {
            "max_size_kb": ROLL_TRIGGER_KB,
            "compress": True,
        },
    }
    p = log_dir / "logging-config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def count_gz(log_dir: Path) -> int:
    return len(list(log_dir.glob("*.gz")))


def write_record(logger: HubLogger, i: int) -> None:
    mod = i % 4
    if mod == 0:
        logger.log_ipc(peer_id="gc", direction="send",
                       query_file=f"ipc-{i}.txt", query_preview="benchmark query")
    elif mod == 1:
        logger.log_cost(peer_id="cx", model_id="gpt-5.5",
                        input_tokens=500, output_tokens=200,
                        reasoning_tokens=80, latency_sec=1.2)
    elif mod == 2:
        logger.log_error(error_type="PEER_TIMEOUT", tier="T2",
                         peer="gc", message=f"timeout #{i}")
    else:
        logger.log_reasoning(peer_id="cc", model_id="claude-sonnet-4-6",
                             reasoning_tokens=1024, effort_level="high")


# ── Main ─────────────────────────────────────────────────────────────────────

tmp = Path(tempfile.mkdtemp(prefix="perf_logging_"))
cfg_path = make_config(tmp)
logger = HubLogger(config_path=cfg_path)

latencies_us: list[float] = []
roll_events: list[tuple[int, float]] = []  # (record_idx, elapsed_ms)
gz_seen = 0

t_start = time.perf_counter()

for i in range(TOTAL_RECORDS):
    t0 = time.perf_counter()
    write_record(logger, i)
    elapsed_us = (time.perf_counter() - t0) * 1_000_000
    latencies_us.append(elapsed_us)

    gz_now = count_gz(tmp)
    if gz_now > gz_seen:
        elapsed_total_ms = (time.perf_counter() - t_start) * 1000
        roll_events.append((i, elapsed_total_ms))
        gz_seen = gz_now

total_sec = time.perf_counter() - t_start

# ── Stats ─────────────────────────────────────────────────────────────────────

lat_sorted = sorted(latencies_us)
n = len(lat_sorted)
p50 = lat_sorted[n // 2]
p95 = lat_sorted[int(n * 0.95)]
p99 = lat_sorted[int(n * 0.99)]
rps = TOTAL_RECORDS / total_sec

# Histogram (10 buckets)
lo, hi = lat_sorted[0], lat_sorted[-1]
bucket_w = (hi - lo) / 10 or 1
buckets = [0] * 10
for v in lat_sorted:
    idx = min(int((v - lo) / bucket_w), 9)
    buckets[idx] += 1
bar_max = max(buckets)

print("=" * 70)
print(f"  BENCHMARK D — hub_logging.py rolling I/O  ({TOTAL_RECORDS:,} records)")
print(f"  Roll trigger: {ROLL_TRIGGER_KB} KB | mix: ipc/cost/error/reasoning")
print("=" * 70)
print()
print(f"  Total time     : {total_sec*1000:.1f} ms")
print(f"  Throughput     : {rps:,.0f} records/sec")
print(f"  Latency p50    : {p50:.1f} us")
print(f"  Latency p95    : {p95:.1f} us")
print(f"  Latency p99    : {p99:.1f} us")
print(f"  Max latency    : {lat_sorted[-1]:.1f} us")
print(f"  Roll events    : {len(roll_events)}")
print()

print("  Latency histogram (us):")
for i, cnt in enumerate(buckets):
    lo_b = lo + i * bucket_w
    hi_b = lo_b + bucket_w
    bar = "#" * int(cnt / bar_max * 40)
    print(f"  {lo_b:>8.0f}-{hi_b:<8.0f} |{bar:<40}| {cnt}")

if roll_events:
    print()
    print("  Roll events (record idx -> elapsed ms at roll):")
    for idx, ms in roll_events:
        print(f"    record #{idx:>5}  @ {ms:>8.1f} ms total  [gzip roll triggered]")

# Spike detection: records that took >10x p50
spikes = [(i, v) for i, v in enumerate(latencies_us) if v > p50 * 10]
if spikes:
    print()
    print(f"  Latency spikes (>10x p50={p50:.0f}us): {len(spikes)} events")
    for idx, v in spikes[:10]:
        roll_marker = " <-- ROLL" if any(abs(idx - r[0]) < 5 for r in roll_events) else ""
        print(f"    record #{idx:>5}  {v:>10.1f} us{roll_marker}")

# Cleanup
import shutil
shutil.rmtree(tmp, ignore_errors=True)

print()
print("  Done.")
