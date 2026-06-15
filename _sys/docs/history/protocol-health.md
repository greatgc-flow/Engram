# Protocol: Health Management (v4.2)
> Source: `_sys/ai/protocol.json["health"]` and `_sys/ai/lifecycle_policy.json["health_lifecycle"]` | Part of composable PROTOCOL.md

## 1. Operating Goals

Health management has four jobs:

1. Keep routing away from peers that are known to be blocked.
2. Detect stale or degraded peer state before delegation.
3. Preserve enough handoff state to continue work after a peer fails.
4. Recover peers only through a successful diagnostic path or an explicit manual recovery action.

All routine health reads are zero-token local file reads. A command that contacts a model or external service is not a routine health check unless it is explicitly requested as a diagnostic.

## 2. Health Files

Each peer owns one health manifest:

| Peer | Health file |
|------|-------------|
| cc/ca | `_sys/claude/health.json` |
| gc | `_sys/gemini/health.json` |
| ag | `_sys/antigravity/health.json` |
| cx | `_sys/codex/health.json` |

Minimum schema:

```json
{
  "_version": "1.0",
  "peer_id": "gc",
  "context_health": {
    "status": "GREEN",
    "jsonl_mb": 0.0,
    "checked_at": "20260613T120000",
    "source": "self"
  },
  "session_health": {
    "consecutive_failures": 0,
    "last_success_at": "2026-06-13T12:00:00",
    "last_failure_reason": null,
    "session_count_today": 1,
    "session_date": "20260613"
  },
  "availability": {
    "gate_open": true,
    "entrypoint_ok": true,
    "authenticated": true,
    "rate_limit_state": "ok"
  }
}
```

Status values:

| Status | Meaning | Routing effect |
|--------|---------|----------------|
| GREEN | Healthy and recently checked. | Eligible. |
| YELLOW | Degraded but usable. | Eligible as fallback or lower priority. |
| STALE | Last check is older than `leader_election.health_stale_minutes` or active PID died. | Avoid for leadership and new assignments; explicit peer precheck fails. |
| RED | Known blocked, quarantined, over failure threshold, or gate closed. | Do not route work. |
| UNKNOWN | Health file missing or unreadable. | Do not target explicitly until initialized. |

## 3. Thresholds And State Transitions

Thresholds come from `protocol.json["health"]`:

| Transition | Rule |
|------------|------|
| GREEN | `jsonl_mb < green_mb` and `consecutive_failures < failure_warn` and `gate_open != false`. |
| YELLOW | `green_mb <= jsonl_mb < yellow_mb` or `consecutive_failures >= failure_warn`. |
| RED | `jsonl_mb >= yellow_mb`, `consecutive_failures >= failure_error`, critical failure reason, quarantine, or `gate_open == false`. |
| STALE | `checked_at` older than `leader_election.health_stale_minutes`, or recorded `active_pid` is no longer alive. |

Failure policy comes from `lifecycle_policy.json["ask_failure_classification"]` and `["health_lifecycle"]`.

Critical failure reasons close the gate immediately:

| Reason | Typical cause | Required recovery |
|--------|---------------|-------------------|
| `sandbox_spawn_eperm` | Local sandbox/process policy blocks peer launch. | Fix environment, then `peer-recover`. |
| `rate_or_session_limit` | Provider quota, session limit, or rate limit. | Wait/resolve quota, then `peer-recover`. |
| `cli_not_found` | Peer executable missing from PATH. | Repair install/PATH, then `peer-recover`. |

Transient failures such as timeout increment `consecutive_failures`. At `failure_warn` the peer becomes YELLOW; at `failure_error` it becomes RED.

## 4. Monitoring Cadence

Required checks:

| Event | Command | Purpose |
|-------|---------|---------|
| Peer entry start | `hub.py health-update --peer <peer> --status AUTO --jsonl-mb <mb> --failures <n>` | Refresh self status. |
| Before delegation | `hub.py health-precheck --peer <peer>` or `hub.py health-precheck --needs <capability>` | Block RED, gate-closed, missing explicit, and stale explicit targets. |
| Before peer-to-peer ask | Built-in `_ask_health_precheck()` | Prevent model calls to RED or gate-closed peers. |
| Periodic/session boundary | `hub.py health-sweep` | Persist timestamp-derived STALE state. |
| Human/operator view | `hub.py health-check` or `hub.py peer-status` | Show current local health table. |
| Peer exit/end | `hub.py health-update --peer <peer> --status AUTO --jsonl-mb <mb> --failures <n>` | Leave a fresh handoff signal for the next session. |

`health-sweep` is the durable stale marker. When a peer first becomes STALE, it writes the status and appends a handoff issue so the next coordinator sees the risk without reading logs.

## 5. Routing Gate

A peer is routable only when:

```text
context_health.status in {GREEN, YELLOW}
AND availability.gate_open != false
AND availability.quarantined != true
```

Routing preferences:

1. Prefer GREEN peers.
2. Use YELLOW only when capability, continuity, or cost justifies it.
3. Avoid STALE for new assignments and leadership.
4. Block RED and gate-closed peers.
5. If every suitable peer is RED, gate-closed, missing, or stale, escalate to the human interface peer.

Direct `hub.py ask` still performs its own RED/gate-closed precheck. STALE is treated as an assignment risk, not an absolute invocation ban, because a successful explicit diagnostic call can refresh a stale peer to GREEN.

## 6. Recovery Runbooks

### YELLOW Recovery

Use when the peer is degraded but still gate-open.

1. Reduce routing priority for new work.
2. Record a checkpoint at the next pause if the peer owns active work.
3. Run the smallest relevant diagnostic or normal ask.
4. On success, `_record_ask_success()` resets `consecutive_failures`, clears transient availability flags, and returns the peer to GREEN.
5. If failures continue to `failure_error`, transition to RED.

### STALE Recovery

Use when `checked_at` is old or the recorded PID died.

1. Run `hub.py health-sweep` to persist the STALE status.
2. Do not assign new leadership or task ownership to that peer.
3. If the peer is needed, run an explicit precheck or small diagnostic.
4. On success, update health to GREEN.
5. If the peer does not respond, reassign active tasks with `hub.py task-failover`.

### RED Recovery

Use when the peer is known blocked or quarantined.

1. Stop routing work to the peer.
2. If it owns active work, write a checkpoint with `hub.py task-checkpoint`.
3. Quarantine if not already quarantined: `hub.py peer-quarantine --peer <peer> --reason <reason>`.
4. Repair the root cause outside the model call path.
5. Validate the repair with the smallest safe diagnostic.
6. Reopen only with `hub.py peer-recover --peer <peer> --reason <reason>`.
7. Reassign or resume work only after `health-precheck` passes.

Manual `health-update --status GREEN` is not a substitute for repair. It may refresh a healthy peer's self-report, but RED recovery should use `peer-recover` so the handoff records the event.

## 7. Continuity Requirements

Before a degraded owner yields, is quarantined, or fails over, the coordinator must preserve:

- Task id and owner.
- Files or artifacts currently being edited.
- Last known good decision.
- Pending risks or blocked commands.
- Next concrete action.

Preferred commands:

```text
hub.py task-checkpoint --id <task_id> --peer <peer> --msg <summary>
hub.py checkpoint --agent <peer> --msg <summary>
hub.py task-failover --task-id <task_id> --peer <new_peer> --reason <reason>
```

Recovery must prefer durable state references (`.ai/state.json`, `.ai/sessions/<room>/handoff.md`, `.ai/task_registry.json`) over pasted chat transcripts.

## 8. Operator Quick Checks

```text
hub.py health-check
hub.py peer-status
hub.py health-precheck --needs code
hub.py health-precheck --peer gc
hub.py health-sweep
hub.py peer-quarantine --peer gc --reason quota
hub.py peer-recover --peer gc --reason quota_reset
```

## 9. Anti-Patterns

- Do not call a RED or gate-closed peer hoping the call will fix it.
- Do not clear `gate_open=false` without identifying the root cause.
- Do not use model calls for routine health checks when local files are enough.
- Do not let a stale coordinator keep ownership without a checkpoint.
- Do not route around a failing peer silently; record quarantine, failover, or recovery in handoff.

---

## 9b. Min-Token Health Inference (Ask-Outcome Classifier)

**Principle**: Routine health checks are zero-token (local file reads). A dedicated model-ping ask is forbidden as a default health check.

However, every real ask already returns an exit code + stderr + output — this is a free signal.

### Classification Rules (implemented in `_classify_ask_failure()`)

| Signal | Health inference |
|--------|-----------------|
| exit_code == 0, non-empty response | GREEN (record via `_record_ask_success`) |
| exit_code != 0, known critical marker in stderr | RED (sandbox_spawn_eperm, rate_or_session_limit, cli_not_found) |
| exit_code != 0, rate/quota marker | YELLOW → RED after threshold |
| exit_code != 0, unknown/generic | failure recorded, threshold-based degradation |
| Process alive but zero output for 30 min | Zombie-killed; treated as timeout failure |

### Rules

1. **Local-file-first**: `hub.py health-check` / `hub.py health-precheck` read local `health.json` — 0 model tokens
2. **Piggyback on real asks**: `_record_ask_success/failure()` update health from ask outcomes automatically
3. **MUST NOT**: Send a dedicated model ping just to check health (wastes tokens)
4. **MUST NOT**: Infer health from arbitrary prose content — only from transport signals (exit code, stderr markers)
5. **SHOULD**: Classify stderr patterns into named reasons (`timeout`, `rate_or_session_limit`, `sandbox_spawn_eperm`, etc.)

---

## 10. Heartbeat / Lease Mechanism

### 10.1 — Purpose

The lease mechanism provides orphan-process cleanup when the hub process itself dies mid-ask (e.g., crash, kill). It is **bookkeeping**, not a liveness detector.

### 10.2 — Exact Logic

Config from `protocol.json ["communication_policy"]`:
- `heartbeat_sec` = 30 (poll interval for process-death detection)
- `lease_timeout_sec` = 1800 (initial lease duration; renewed every heartbeat)

During an active ask (`action_ask()` subprocess path):
1. `_lease_open()` records `{peer, pid, expires_at = now + 1800s}` in `leases.json`
2. Every 30s `proc.communicate(timeout=30)` times out → `_lease_renew()` sets `expires_at = now + 1800s`
3. The lease never naturally expires while the hub is alive and renewing

If the **hub process stops** (crash/kill), a later `_lease_sweep()` finds the open lease with a past `expires_at`, kills the recorded PID tree, marks the lease as `expired`, and records a health failure.

### 10.3 — Zombie-Process Guard

Problem: If the subprocess hangs (alive but producing no output), `_lease_renew()` fires every 30s indefinitely.

Solution (implemented in `hub.py`):
```python
_MAX_SILENT_HEARTBEATS = lease_timeout_sec // heartbeat_sec  # = 60 beats = 30 min
_silent_beats = 0

while True:
    try:
        raw_out, raw_err = proc.communicate(input=..., timeout=heartbeat_sec)
        break
    except subprocess.TimeoutExpired:
        _silent_beats += 1
        _lease_renew(...)
        if _silent_beats >= _MAX_SILENT_HEARTBEATS:
            _kill_process_tree(proc)
            raise subprocess.TimeoutExpired(...)
```

After 60 consecutive silent heartbeats (30 min total), the process is force-killed.

### 10.4 — What the Lease Does NOT Do

- Does NOT detect a still-alive zombie (use the zombie guard instead)
- Does NOT auto-replay/retry/reassign tasks after lease expiry (manual failover required)
- Does NOT trigger runtime directives (failure recording does that)

### 10.5 — Recommended Thresholds

| Scenario | Action |
|----------|--------|
| Hub alive, process alive, producing output | Normal heartbeat renewal |
| Hub alive, process alive, NO output for 30 min | Zombie guard kills process |
| Hub crashed/killed, lease expired | `lease-sweep` kills orphan on next invocation |
| Process died normally | `proc.poll() is not None` → loop breaks normally |

### 10.6 — CLI Commands

```bash
python _sys/core/hub.py lease-status   # show open leases
python _sys/core/hub.py lease-sweep    # manually run orphan cleanup
```

---

## 11. gc Legacy Gate Mirror (`status.json`)

gc has a **peer-specific gate file** (`_sys/gemini/status.json`) in addition to the universal `health.json`. This is a legacy compatibility mirror — not a second source of truth.

### Why it exists

`gemini-status.bat` and `gemini-gate.bat` were written before the unified `health.json` schema and read `status.json` directly. Migrating those scripts to read `health.json` is the long-term fix; until then, both files must be kept in sync.

### How sync is maintained

`hub.py _sync_peer_gate_file()` is called by both `peer-quarantine` and `peer-recover`:

```python
# Called after updating health.json gate_open
_sync_peer_gate_file(peer_id, mode_on=False, reason=reason)  # quarantine
_sync_peer_gate_file(peer_id, mode_on=True,  reason=reason)  # recover
```

The gate config is declared in `_sys/ai/peers.json` under `peers.gc.gate`:
```json
{
  "status_file": "gemini/status.json",
  "mode_key": "mode",
  "mode_on_value": "ON"
}
```

### 5 Whys root cause

1. Why two stores? `health.json` added `gate_open`; `status.json` already existed as gc's local gate.
2. Why retained? Legacy batch scripts read `status.json`; changing them risked breaking existing gate flow.
3. Why did they diverge? `peer-recover` only updated `health.json`, leaving `status.json.mode = "OFF"`.
4. Why wasn't this caught earlier? No test verified display consistency across both stores.
5. **Root cause**: Incomplete migration — two readers of the same logical concept (peer availability) with no write-side sync.

### Future consolidation path

Make `gemini-status.bat` read `_sys/gemini/health.json["availability"]["gate_open"]` directly, then remove `peers.gc.gate` config and `_sync_peer_gate_file()` gc branch.

---

## HISTORY

- v4.3 (2026-06-14): Added §10 Heartbeat/Lease mechanism; zombie-guard logic; cc+cx T2 debate findings.
- v4.2 (2026-06-13): Expanded monitoring cadence, state machine, routing gate, and recovery runbooks; aligned with `health-precheck`, `health-sweep`, `peer-quarantine`, `peer-recover`, and task failover behavior.
- v4.1 (2026-06-12): Standardized zero-token health check thresholds.
- v4.0 (2026-06-11): New file; health management system designed with all peers (cc,gc,ag,cx).
