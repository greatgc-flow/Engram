# General — Lifecycle
> Note: This pillar consolidates session, health, and token-budget/ContextGate policy. Model facts belong in JSON files (e.g., `model-registry.json`), not here.

---

## 1. Session Decision Tree (entry point)

```
Read .ai/state.json
  ├─ room_id exists + this peer in members + updated_at < protocol.json["session"]["resume_window_hours"]?
  │     → RESUME: hub.py init-session (rejoin) + read full handoff.md
  │
  ├─ room_id exists + resume_window_hours ≤ updated_at < protocol.json["session"]["handoff_staleness_hours"]?
  │     → NEW + CONTEXT FILL:
  │       1. hub.py init-session (new join, same room_id)
  │       2. hub.py context-fill → inject into first prompt
  │
  ├─ room_id exists + updated_at ≥ handoff_staleness_hours?
  │     → STALE + FULL FILL:
  │       1. hub.py end-session for stale members
  │       2. hub.py init-session (new session)
  │       3. hub.py context-fill (all fill sections)
  │
  └─ no room_id
        → COLD START: hub.py init-session (empty handoff)
```

---

## 2. Startup Contract (all peers — INV-05)

```
1. hub.py init-session --agent {peer_id}
2. hub.py health-update --peer {peer_id} --status GREEN
3. hub.py context-fill   ← zero-token local read, inject into first prompt
4. hub.py check --target {peer_id}   ← read mailbox
```

---

## 3. Handoff Structure (`handoff.md`)

6 rolling sections, max 12KB total:

| Section | Content | Max Items |
|---------|---------|:---------:|
| `[GOAL]` | Current mission | 1 |
| `[RECENT_COMPLETED]` | Done tasks | 5 |
| `[PENDING_ISSUES]` | Blockers | 3 |
| `[KEY_DECISIONS]` | Architecture choices | 3 |
| `[CONSENSUS_HISTORY]` | Round outcomes | 10 |
| `[ACTIVE_THREADS]` | In-flight threads | 5 |

Context-fill sections controlled by `protocol.json["session"]["context_fill_sections"]`.
`fill_depth_multiplier`: all active peers=1 (equal depth). Historical: ag was 3 before 2026-06-19 equality fix.

---

## 4. Session Expiry

| Rule | Config key |
|------|:-----------|
| Resume window | `protocol.json["session"]["resume_window_hours"]` |
| Staleness threshold | `protocol.json["session"]["handoff_staleness_hours"]` |
| Consensus round timeout | `protocol.json["consensus"]["timeout_minutes"]` |

---

## 5. CLI Session Reuse

`hub.py ask` reuses CLI sessions across calls (scope_key = `room_id`).
Session reuse is governed solely by the config-driven `session_mode` field in `orchestration.json`. The descriptive `memory` field does not control reuse.

- `cc`, `ag`, `cx`: Have reuse configured per `orchestration.json`.
- `gc`: SUSPENDED TOMBSTONE. (tier_suspended).
- `ag`: Reuses via **ambient durable state** (`session_mode: reuse`): `agy -p` natively auto-continues its `conversations/*.db` store WITHOUT continuation/conversation flags (PTY/inline mode, `requires_pty=true`). IPC asks run in a stateless `ipc-config/` home (see `specific/ag.md`) so ambient reuse is scoped, not cross-contaminating.

State file: `_sys/{peer_dir}/session_state.json` (gitignored).
On resume failure: retire old session → retry fresh once.
Topic boundary (`new-topic`, `clear-room`): all peer sessions retired.
Override: `hub.py ask --session-policy fresh` for independent cross-review calls.

---

## 6. Handoff Rolling Rule

When `handoff.md` exceeds **2KB**, trim as follows:
1. Move all items in `[RECENT_COMPLETED]` marked `[DONE]` to `_archive/handoff-{YYYYMMDD}.md` (append).
2. Keep a max of 3 items in `[RECENT_COMPLETED]` after trim.
3. `[CONSENSUS_HISTORY]` — keep last 5 rounds only; archive earlier rounds.
4. Never delete `[GOAL]`, `[PENDING_ISSUES]`, or `[ACTIVE_THREADS]` without human instruction.

Command: `hub.py checkpoint --agent {peer_id} --trim` triggers the rolling trim.

---

## 7. Zero-Token Local Reads (always exempt, all COLLAB_RATE levels)

These reads are **always zero-token** — no COLLAB_RATE gate applies:

| Resource | Why always exempt |
|----------|------------------|
| `_sys/{peer}/health.json` | Health check is a local file read, no model call |
| `.ai/sessions/{room}/handoff.md` | Re-orientation read at session start |
| `.ai/mailbox.json` | Inbox check at session start |
| `_sys/ai/runtime-directives.jsonl` | Active directive injection (observe phase) |
| `_sys/ai/user-directives.md` | Standing rules (observe phase) |

A read is NOT zero-token if it triggers a model call, network request, or side-effect write.

---

## 8. Stable Fingerprint

**Source:** `adapter.session_fingerprint(node)`

A short 8-char SHA-1 hash that identifies the *static* invocation flags for a peer session.
It is **stable across calls** and only changes when permission flags change.

### Canonical Input

```
raw = base_exe + "|" + ",".join(static_flags)
fingerprint = sha1(raw.encode()).hexdigest()[:8]
```

- `base_exe = os.path.basename(exe_name)` — filename only, never a full path.
  This prevents drift when the PATH root changes (e.g., USB drive letter change).
- `static_flags` come from the adapter's normalized stdin arguments, excluding dynamic values like session IDs or resume parameters.

### Drift Detection

On every `hub.py ask` with session reuse:
1. Compute `current_fp = adapter.session_fingerprint(node)`.
2. Load `existing_session = _get_active_session(health_peer, scope_key)`.
3. If `stored_fp` exists and `stored_fp != current_fp`:
   - Log: `[HUB:WARN] {peer} session fingerprint drift ({old} → {new}), retiring for fresh start`
   - Call `_retire_session(peer, scope_key, "fingerprint_drift")`
   - Proceed as if no existing session.

### Scope Key

Session state is keyed by `scope_key = explicit_scope ?? room_id ?? "default"`.
State file: `_sys/{peer_dir}/session_state.json` (gitignored).

---

## 9. Resume Failure Classification

**Source:** `hub.py:_classify_resume_failure(stderr)` → `"transient"` | `"permanent"`

Called when a session-resume attempt exits non-zero (`proc.returncode != 0 and is_resume_attempt`).

### Classification Rules

| Class | Trigger patterns in stderr | Behavior |
|-------|---------------------------|----------|
| **Transient** | `timeout`, `timed out`, `rate limit`, `quota`, `503`, `429`, `connection refused`, `network error`, `unable to reach` | Keep session alive. Report error. Exit. Caller retries later. |
| **Permanent** | Any other content — or empty stderr | Retire session → retry once with fresh session. |

> Empty stderr always maps to **permanent** (default).

### Permanent Failure Flow

```
proc.returncode != 0 AND is_resume_attempt AND fail_type == "permanent"
  → _retire_session(peer, scope_key, "resume_failed")
  → adapter.build_session_cmd(node, query, None)   # fresh
  → subprocess.Popen(fresh_cmd)
  → communicate(query)
  → if success: _set_active_session(new_id, fingerprint=current_fp)
  → if failure: _record_ask_failure + exit
```

### Transient Failure Flow

```
proc.returncode != 0 AND is_resume_attempt AND fail_type == "transient"
  → session NOT retired (still active in session_state.json)
  → [HUB:WARN] ... keeping session for retry
  → _record_ask_failure
  → exit (no auto-retry — caller decides)
```

---

## 10. Health States

| Status | Meaning | Routing effect |
|--------|---------|---------------|
| GREEN | Healthy, recently checked | Routable (preferred) |
| YELLOW | Degraded but usable | Routable as fallback |
| STALE | `checked_at` older than `protocol.json["leader_election"]["health_stale_minutes"]` or active PID died | Avoid for leadership/new tasks |
| RED | Blocked, quarantined, over failure threshold, or `gate_open=false` | NEVER route work |
| UNKNOWN | health.json missing or unreadable | Do not target until initialized |

---

## 11. Health File Location

The canonical health file location is resolved via ONE resolver `resolve_peer_sys_dir(peer_id)` reading `peers.json` (`node_ids` → `sys_subdir`).

`_sys/<sys_subdir>/health.json` — per-peer, updated by `hub.py health-update`.
*Note: raw `health.json` reads are an IMPLEMENTATION/AUDIT detail ONLY, NOT the operator primitive. There are no legacy `_sys/<node_id>/health.json` mirrors.*

```json
{
  "_version": "1.0", "peer_id": "cc",
  "context_health": { "status": "GREEN", "jsonl_mb": 0.0, "checked_at": "20260615T120000", "source": "self" },
  "session_health": { "consecutive_failures": 0, "last_failure_reason": null, "last_success_at": "...", "session_count_today": 0 },
  "availability": { "gate_open": true, "entrypoint_ok": true, "authenticated": true, "rate_limit_state": "ok" }
}
```

---

## 12. State Transitions (from `protocol.json["health"]`)

| Transition | Rule (thresholds in `protocol.json["health"]`) |
|------------|------|
| GREEN | `jsonl_mb < thresholds.green_mb` AND `consecutive_failures < failure_warn` AND `gate_open != false` |
| YELLOW | `thresholds.green_mb ≤ jsonl_mb < thresholds.yellow_mb` OR `consecutive_failures ≥ failure_warn` |
| RED | `jsonl_mb ≥ thresholds.yellow_mb` OR `consecutive_failures ≥ failure_error` OR critical reason OR quarantine |
| STALE | `checked_at` older than `protocol.json["leader_election"]["health_stale_minutes"]` OR recorded PID no longer alive |

Critical failure reasons (immediate gate close):
- `sandbox_spawn_eperm` — fix environment → `peer-recover`
- `rate_or_session_limit` — wait/resolve quota → `peer-recover`
- `cli_not_found` — repair install/PATH → `peer-recover`

---

## 13. Routing Gate

Peer is routable only when:
```
context_health.status in {GREEN, YELLOW}
AND availability.gate_open != false
AND availability.quarantined != true
```

Preference order: GREEN → YELLOW → (avoid STALE) → RED blocked.

---

## 14. Monitoring Events

| Event | Command |
|-------|---------|
| Peer entry start | `hub.py health-update --peer <p> --status AUTO --jsonl-mb <mb> --failures <n>` |
| Before delegation | `hub.py health-precheck --peer <p>` |
| Before peer-to-peer ask | Built-in `_ask_health_precheck()` |
| Session boundary | `hub.py health-sweep` |
| Operator view | `hub.py peer-status` (canonical, non-mutating, orchestration-filtered) |
| Audit / Maintenance view | `hub.py health-check` (read-only + orchestration-filtered by default, excludes disabled; recovery only behind `--recover`) |
| Peer exit | `hub.py health-update --peer <p> --status AUTO ...` |

---

## 15. Recovery Runbooks

**YELLOW**: reduce routing priority → run diagnostic → on success `_record_ask_success()` resets to GREEN.

**STALE**: `hub.py health-sweep` → assign no new leadership → explicit precheck or diagnostic → on success update to GREEN → if no response: `hub.py task-failover`.

**RED** (full sequence):
```
1. Stop routing work
2. hub.py task-checkpoint --id <task_id> --peer <p>
3. hub.py peer-quarantine --peer <p> --reason <reason>
4. Fix root cause (outside model path)
5. Validate repair with smallest safe diagnostic
6. hub.py peer-recover --peer <p> --reason <reason>
7. health-precheck passes → resume/reassign work
```

---

## 16. Zero-Token Health Rule (INV-08 / PRO-07 / PRO-08)

- Terminal/operator peer status = `hub.py peer-status` (canonical, non-mutating, orchestration-filtered).
- Health updates/checks = local `health.json` reads/writes ONLY. Zero model calls. (Raw reads are an IMPLEMENTATION/AUDIT detail).
- Ask outcome piggyback: every real ask exit code + stderr → auto-classifies health via `_record_ask_success/failure()`
- NEVER send dedicated model ping to check health
- NEVER infer health from prose content

**Failure classification (exit code + stderr):**

| Signal | Inference |
|--------|-----------|
| exit_code=0, non-empty response | GREEN |
| exit_code≠0, critical marker in stderr | RED (immediate gate close) |
| exit_code≠0, rate/quota marker | YELLOW → RED after threshold |
| exit_code≠0, unknown | Threshold-based degradation |
| Process alive, zero output | Zombie-killed → timeout failure (configured via `protocol.json["communication_policy"]["zombie_timeout_sec"]`) |

---

## 17. Heartbeat / Lease (crash-safety only)

- Purpose: orphan cleanup when hub process dies mid-ask
- Timings configured in `protocol.json["communication_policy"]`:
  - `heartbeat_sec`
  - `lease_timeout_sec`
  - `zombie_timeout_sec`
- Zombie guard: consecutive silent heartbeats exceeding `zombie_timeout_sec` → force-kill
- `hub.py lease-status` / `hub.py lease-sweep`
- Does NOT: auto-replay/retry tasks, trigger directives

---

## 18. gc Legacy Gate Mirror

gc is a SUSPENDED TOMBSTONE (no live health file). See `specific/gc.md` for legacy tombstone details.

---

## 19. ContextGate v1.0 Design

ContextGate prevents context overflow by estimating token usage before each ask, then pruning or failing over if thresholds are exceeded.

### Algorithm

```
1. Estimate input tokens: len(text) / 3.5 * CJK_multiplier
   - CJK_multiplier = 1.8 if ≥20% CJK chars, else 1.0
2. If estimated >= context_gate_warn_pct (0.80) of model context_limit:
   → prune: remove lowest-priority context blocks until below 0.75
3. If estimated >= context_gate_failover_pct (0.95) of model context_limit:
   → failover: route to smaller model
   → if no smaller model: raise CONTEXT_GATE_REJECT (T2 error)
4. Log CONTEXT_GATE_REJECT to error-log.jsonl with 5-Whys template "context_too_large"
```

### Config Keys

Config keys point to JSON `governance_params.json` and `protocol.json`.
Model context limits are FACTS; they are not tabled here. Reference `model-registry.json` for all effective context limits per model.

| Key | Default | Effect |
|-----|---------|--------|
| `context_gate_enabled` | true | Toggle entire gate |
| `context_gate_warn_pct` | 0.80 | Prune trigger |
| `context_gate_failover_pct` | 0.95 | Failover trigger |

### Implementation

Planned in: `_sys/core/hub_context.py` (Phase 3, impl-plan.md §4)
Traceability: `traceability_map.json` entry `context-gate`

---

## 20. Implementation Priority

| Priority | Item | File | Status |
|----------|------|------|--------|
| P0 | Update profile capacity facts | model-registry.json | **DONE** (2026-06-19) |
| P0 | Replace obsolete Codex profile models | orchestration.json | **DONE** (2026-06-19) |
| P0 | Add 6 missing models to model-registry.json | model-registry.json | **DONE** (2026-06-18) |
| P1 | Implement hub_context.py ContextGate | _sys/core/hub_context.py | **DONE** (v1.0, tested) |
| P1 | Add CJK-aware token estimator | hub_context.py | **DONE** |
| P2 | Calibrate cx reasoning tokens against usage.output_tokens_details | hub_peer.py + hub.py | **DONE** (2026-06-18) |
| P3 | Auto-prune context blocks by priority score | hub_context.py | **DONE** (check_and_prune(), tested) |

