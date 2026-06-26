# Ops — Logging Architecture

> Status: ACTIVE v1.0 | Created: 2026-06-18
> Purpose: Full observability — per-peer/model/node detail logging, IPC send/receive history, console output capture, rolling policy, and 5-Whys investigation integration.
> Cross-ref: `general/routing.md §6` (cost-log); `general/learning.md` (self-care triggers, pending Pillar 4)

---

## 1. Why This Document Exists (5-Whys Root Cause)

**Problem:** AI peer interactions are opaque — debugging failures requires reconstructing what was sent/received.

| Why | Finding |
|-----|---------|
| Why 1 | We can't reproduce peer failures → logs were incomplete or missing |
| Why 2 | Logs were incomplete → only cost-log existed; IPC content was discarded |
| Why 3 | IPC content was discarded → hub.py wrote query files then deleted them |
| Why 4 | Query files were deleted → `qf.unlink()` ran after first read (single-use design) |
| Why 5 | Single-use design → original design assumed queries were ephemeral and private |

**Root fix:** Separate the query lifecycle from the audit log lifecycle. Query files remain ephemeral (deleted after send); a structured audit log captures full content before deletion. No overlap, no data loss.

---

## 2. Log Taxonomy (MECE)

All logs live under `_sys/data/logs/`. All are gitignored (runtime state, not source).

| Log File | Content | Written By | Format |
|----------|---------|------------|--------|
| `ipc-log.jsonl` | All hub.py IPC send/receive with full content | hub.py | JSONL |
| `console-log.jsonl` | All user-facing console output | hub.py + ctx hooks | JSONL |
| `cost-log.jsonl` | Per-ask token counts, cost, quality signals | hub.py Observer | JSONL |
| `error-log.jsonl` | Errors, failures, timeouts, exit codes | hub.py + self_care.py | JSONL |
| `reasoning-log.jsonl` | cx reasoning token traces (when measurable) | hub.py (cx path) | JSONL |
| `model-drift.jsonl` | Measured vs. registered spec divergences | hub.py Observer | JSONL |
| `self-care-log.jsonl` | Self-care pipeline step results | self_care.py | JSONL |

**Invariant:** Every log entry MUST have `ts` (ISO-8601 UTC), `session_id`, and `peer` fields. All other fields are log-type-specific.

---

## 3. IPC Log — Full Send/Receive History

### 3.1 Entry Schema

```jsonc
// ipc-log.jsonl — one line per hub.py ask/response cycle
{
  "ts":           "2026-06-18T10:30:00.123Z",  // send timestamp
  "session_id":   "cc-20260618-ABC1",
  "peer":         "gc",
  "model":        "gemini-3.5-flash",
  "thinking_config": "thinking_level:minimal",
  "sandbox":      "none",
  "query_file":   "gc-20260618103000-XY7Z.txt", // filename only (content captured below)
  "query_text":   "TASK: ...\nCONTEXT: ...\nQUESTION: ...",  // full content
  "response_text": "...",                        // full response (truncated at 64k if larger)
  "response_truncated": false,
  "exit_code":    0,
  "latency_ms":   2340,
  "tokens_in":    1820,
  "tokens_out":   620,
  "reasoning_tokens": 0,
  "outcome":      "success"   // "success" | "timeout" | "error" | "truncated"
}
```

### 3.2 hub.py Instrumentation Points

```python
# BEFORE query file deletion — capture full content
def _log_ipc_send(session_id, peer, model, query_text, query_file):
    entry = {
        "ts": utcnow(),
        "session_id": session_id,
        "peer": peer,
        "query_file": query_file,
        "query_text": query_text,
        ...
    }
    _append_log("ipc-log.jsonl", entry)
    # THEN delete query file (existing behavior unchanged)
    Path(query_file).unlink(missing_ok=True)

# AFTER response received
def _log_ipc_response(entry, response_text, exit_code, latency_ms, usage):
    entry.update({
        "response_text": response_text[:65536],
        "response_truncated": len(response_text) > 65536,
        "exit_code": exit_code,
        "latency_ms": latency_ms,
        "tokens_in": usage.get("tokens_in", 0),
        "tokens_out": usage.get("tokens_out", 0),
        "reasoning_tokens": usage.get("reasoning_tokens", 0),
        "outcome": "success" if exit_code == 0 else "error",
    })
    _update_log("ipc-log.jsonl", entry)
```

---

## 4. Console Log — User-Facing Output Capture

### 4.1 Entry Schema

```jsonc
// console-log.jsonl — all output visible to user in terminal
{
  "ts":           "2026-06-18T10:30:05Z",
  "session_id":   "cc-20260618-ABC1",
  "peer":         "cc",               // which peer generated this output
  "channel":      "user",             // "user" | "system" | "debug"
  "message_type": "RESPONSE",         // "RESPONSE" | "STATUS" | "ERROR" | "GATE_EVENT"
  "text":         "...",              // full text as displayed
  "context_ref":  "ipc-20260618-XY7Z" // link to IPC entry if applicable
}
```

### 4.2 Channel Definitions

| Channel | Description | Visible to User |
|---------|-------------|----------------|
| `user` | Primary user-facing responses | Always (Korean) |
| `system` | Gate events, routing decisions, self-care | Always (English OK) |
| `debug` | Internal state transitions, token estimates | Only when DEBUG=1 |

### 4.3 Special Event Types

| message_type | When Written |
|-------------|--------------|
| `RESPONSE` | After every peer response delivered to user |
| `STATUS` | Health checks, QUALITY_MODE changes, peer status |
| `ERROR` | Errors shown to user (not internal-only errors) |
| `GATE_EVENT` | ContextGate fires (reroute, prune, block) |
| `ROI_REPORT` | Session ROI summary at ctx_end |

---

## 5. Per-Node/Model/Peer Detail Logging

### 5.1 Node Activity Summary (aggregated in cost-log.jsonl)

Each entry in `cost-log.jsonl` already captures the full node identity:

```
node_id = f"{peer}::{model}::{thinking_config}::{sandbox}"
```

This enables per-node aggregation queries:
```python
# Example: cost_per_success by node
from collections import defaultdict
import json

node_stats = defaultdict(lambda: {"cost": 0.0, "success": 0, "total": 0})
with open("cost-log.jsonl") as f:
    for line in f:
        e = json.loads(line)
        node = f"{e['peer']}::{e['model']}::{e['thinking_config']}"
        node_stats[node]["cost"] += e["cost_usd"]
        node_stats[node]["total"] += 1
        if e["outcome"] == "success":
            node_stats[node]["success"] += 1
```

### 5.2 Per-Model Spec Drift (model-drift.jsonl)

```jsonc
// model-drift.jsonl — written when observed values differ from registry
{
  "ts":            "2026-06-18T14:22:00Z",
  "peer":          "cx",
  "model":         "gpt-5.5",
  "field":         "output_limit",
  "registered":    128000,
  "observed":      131072,
  "delta_pct":     2.4,
  "sample_count":  3,
  "action":        "flag_for_validation"  // "flag" | "auto_correct" | "proposal_sent"
}
```

---

## 6. Error Log

### 6.1 Entry Schema

```jsonc
// error-log.jsonl
{
  "ts":            "2026-06-18T10:31:00Z",
  "session_id":    "cc-20260618-ABC1",
  "peer":          "cx",
  "error_type":    "SANDBOX_FLAG_INVALID",  // see §6.2
  "message":       "error: invalid value 'full' for '--sandbox'",
  "stderr":        "...",                   // full stderr
  "exit_code":     1,
  "consecutive":   1,                       // consecutive failures for this peer
  "action_taken":  "retry_with_fallback",   // see §6.3
  "ipc_ref":       "ipc-20260618-XY7Z"
}
```

### 6.2 Error Type Taxonomy (MECE)

| error_type | Description | Auto-Action |
|-----------|-------------|-------------|
| `TIMEOUT` | Peer did not respond within 180s | retry once → failover |
| `SANDBOX_FLAG_INVALID` | Unknown --sandbox value | update hub.py, stop |
| `MODEL_NOT_FOUND` | 404 from API | flag in model-drift, failover |
| `PARAM_REJECTED` | 400 from API (bad param) | log + escalate to R:6 |
| `CONTEXT_OVERFLOW` | Token estimate exceeds all peer limits | hard block (sys.exit 2) |
| `CONSENSUS_DEADLOCK` | No ACK within R:8 timeout | escalate to R:11 |
| `HEALTH_RED` | Peer health = RED, gate_open = false | route to fallback |
| `QUERY_FILE_COLLISION` | Duplicate filename in IPC dir | abort + regenerate UUID |

### 6.3 5-Whys Integration for Consecutive Errors

When `consecutive >= 2` (per INV-15 / R:6 rule):

```
STOP solo retry.

5-Whys Analysis Template (written to error-log.jsonl "analysis" field):
  Why 1: What failed? (exact error message)
  Why 2: Why did that fail? (configuration / environment / API change)
  Why 3: Why did that configuration exist? (design decision)
  Why 4: Why wasn't this caught earlier? (missing test / validation)
  Why 5: What systemic change prevents recurrence? (invariant / auto-check)

→ Result: proposal-add with Why 5 fix
→ Notify all peers via thread-new "[R6-BLOCK] {error_type}: {peer}"
```

---

## 7. Reasoning Log (cx-specific)

```jsonc
// reasoning-log.jsonl — cx reasoning token traces
{
  "ts":               "2026-06-18T10:35:00Z",
  "session_id":       "cc-20260618-ABC1",
  "peer":             "cx",
  "model":            "gpt-5.5",
  "reasoning_effort": "high",
  "reasoning_budget": 30000,
  "reasoning_actual": 18420,
  "efficiency":       0.614,   // actual / budget
  "task_type":        "DEBUG",
  "outcome":          "success"
}
```

Aggregation rule: after 10+ samples per (model, effort) combination, compute rolling average → update `peers.json reasoning_budget` via proposal.

---

## 8. Log Rolling Policy

### 8.1 Retention by Log Type

| Log File | Max Size | Retention | Action on Trigger |
|----------|---------|-----------|------------------|
| `ipc-log.jsonl` | 50 MB | 7 days | Rotate → archive |
| `console-log.jsonl` | 20 MB | 30 days | Rotate → archive |
| `cost-log.jsonl` | unlimited | forever | Annual archive (needed for ROI trends) |
| `error-log.jsonl` | 10 MB | 90 days | Rotate → archive |
| `reasoning-log.jsonl` | 20 MB | 14 days | Rotate → archive |
| `model-drift.jsonl` | 5 MB | until resolved | Rotate only if stale (entry age > 30d + no open proposal) |
| `self-care-log.jsonl` | 10 MB | 60 days | Rotate → archive |

### 8.2 Rotation Mechanics

Trigger: file size > max OR age > retention period (checked at every self_care.py session_end run).

```
_sys/data/logs/{name}.jsonl          ← active
_sys/data/logs/archive/{name}-{YYYYMMDD}.jsonl.gz  ← rotated (gzip)
```

Rotation steps:
1. Rename active → `archive/{name}-{date}.jsonl`
2. Compress with gzip
3. Create new empty `{name}.jsonl`
4. Delete archives older than 2× retention period

### 8.3 Annual Archive (cost-log.jsonl)

Because `cost-log.jsonl` is retained forever for ROI trend analysis:

```
_sys/data/logs/cost-log.jsonl              ← current year rolling
_sys/data/logs/archive/cost-log-{YYYY}.jsonl.gz  ← annual snapshot
```

Annual archive: triggered manually at year boundary via `self_care.py --trigger annual_archive`.

### 8.4 Gitignore Policy

All `_sys/data/logs/` content is gitignored (runtime state). Rotation script and schemas are source-controlled. Archives are local-only and not synced.

```gitignore
# _sys/data/logs/ — all runtime logs (local only)
_sys/data/logs/*.jsonl
_sys/data/logs/archive/
```

---

## 9. Self-Care Integration

self_care.py Step 3 (Cleanup) handles log rotation automatically:

```
Step 3 [Cleanup]:
  for each log_file in LOG_FILES:
    if size > max_size or age > retention:
      rotate(log_file)  → archive/{name}-{date}.jsonl.gz
  
  # Stale model-drift entries: close if proposal was sent + 30 days passed
  prune_resolved_drift_entries()
  
  # Record cleanup summary in self-care-log.jsonl
  record_cleanup_summary(rotated_files, pruned_entries)
```

---

## 10. Virtuous Feedback Loop

```
┌─────────────────────────────────────────────────────────────────┐
│  1. OBSERVE  (logging layer — this document)                    │
│     ipc-log: full query/response content                        │
│     cost-log: tokens, latency, quality signals                  │
│     error-log: failures + 5-Whys analysis                       │
│     reasoning-log: cx budget efficiency                         │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌────────────────────────▼────────────────────────────────────────┐
│  2. ANALYZE  (self_care.py Step 4 — Scan)                       │
│     Aggregate cost_per_success by node                          │
│     Identify nodes with failover_rate > 5%                      │
│     Flag reasoning_efficiency outliers                          │
│     Detect model-drift.jsonl entries pending action             │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌────────────────────────▼────────────────────────────────────────┐
│  3. PROPOSE  (self_care.py Step 5 — Propose)                    │
│     ROUTING_UPDATE: adjust node weights in routing-config.json  │
│     MODEL_REGISTRY_UPDATE: update caps in model-registry.json   │
│     INVARIANT_ADD: new R:6 trigger from 5-Whys Why-5 fix        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌────────────────────────▼────────────────────────────────────────┐
│  4. CONSENSUS  (proposal-vote — R:5 or R:8)                     │
│     R:5: routing weights, peer operational config               │
│     R:8: model-registry entries, new invariants                 │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌────────────────────────▼────────────────────────────────────────┐
│  5. APPLY  (auto after ACK)                                     │
│     routing-config.json updated → Router uses new weights        │
│     model-registry.json updated → peers.json re-derived         │
│     invariants.md updated → all peers reload on next session    │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
                    back to 1 (OBSERVE)
```

**Loop triggers:**
- Every 10 commits (SaturationDetector)
- Every session_end (ctx_end.py → self_care.py)
- On R:6 block (consecutive_failures ≥ 2)
- Manual: `python _sys/checks/self_care.py --trigger manual`

---

## 11. Debug Mode

Set `DEBUG=1` in environment to enable verbose logging:

```bash
set DEBUG=1
python _sys/core/hub.py ask --to gc --query-file ...
```

Effects when DEBUG=1:
- console-log.jsonl receives `channel: "debug"` entries (token estimates, gate decisions, routing scores)
- ipc-log.jsonl includes response_text in full (no 64k truncation)
- reasoning-log.jsonl includes per-token timestamps (if available)
- Print `[GATE:{gate_name}]` events to stderr in real-time

Debug log retention: 3 days (shorter than normal — typically high volume).

---

_v1.0 completed 2026-06-18. Covers full log taxonomy (MECE), per-node/model detail capture, IPC send/receive history, 5-Whys root cause integration, rolling policy, and virtuous feedback loop connection to routing.md §6–§7._
