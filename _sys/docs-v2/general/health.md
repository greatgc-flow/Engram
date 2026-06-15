# General — Health Management
> Source: protocol-health.md v4.3

---

## 1. Health States

| Status | Meaning | Routing effect |
|--------|---------|---------------|
| GREEN | Healthy, recently checked | Routable (preferred) |
| YELLOW | Degraded but usable | Routable as fallback |
| STALE | `checked_at` older than `health_stale_minutes` or active PID died | Avoid for leadership/new tasks |
| RED | Blocked, quarantined, over failure threshold, or `gate_open=false` | NEVER route work |
| UNKNOWN | health.json missing or unreadable | Do not target until initialized |

---

## 2. Health File Location

`_sys/{peer_dir}/health.json` — per-peer, updated by `hub.py health-update`.

```json
{
  "_version": "1.0", "peer_id": "gc",
  "context_health": { "status": "GREEN", "jsonl_mb": 0.0, "checked_at": "20260615T120000", "source": "self" },
  "session_health": { "consecutive_failures": 0, "last_failure_reason": null, "last_success_at": "...", "session_count_today": 0 },
  "availability": { "gate_open": true, "entrypoint_ok": true, "authenticated": true, "rate_limit_state": "ok" }
}
```

---

## 3. State Transitions (from `protocol.json["health"]`)

| Transition | Rule |
|------------|------|
| GREEN | `jsonl_mb < green_mb` AND `consecutive_failures < failure_warn` AND `gate_open != false` |
| YELLOW | `green_mb ≤ jsonl_mb < yellow_mb` OR `consecutive_failures ≥ failure_warn` |
| RED | `jsonl_mb ≥ yellow_mb` OR `consecutive_failures ≥ failure_error` OR critical reason OR quarantine |
| STALE | `checked_at` older than `health_stale_minutes` OR recorded PID no longer alive |

Critical failure reasons (immediate gate close):
- `sandbox_spawn_eperm` — fix environment → `peer-recover`
- `rate_or_session_limit` — wait/resolve quota → `peer-recover`
- `cli_not_found` — repair install/PATH → `peer-recover`

---

## 4. Routing Gate

Peer is routable only when:
```
context_health.status in {GREEN, YELLOW}
AND availability.gate_open != false
AND availability.quarantined != true
```

Preference order: GREEN → YELLOW → (avoid STALE) → RED blocked.

---

## 5. Monitoring Events

| Event | Command |
|-------|---------|
| Peer entry start | `hub.py health-update --peer <p> --status AUTO --jsonl-mb <mb> --failures <n>` |
| Before delegation | `hub.py health-precheck --peer <p>` |
| Before peer-to-peer ask | Built-in `_ask_health_precheck()` |
| Session boundary | `hub.py health-sweep` |
| Operator view | `hub.py health-check` / `hub.py peer-status` |
| Peer exit | `hub.py health-update --peer <p> --status AUTO ...` |

---

## 6. Recovery Runbooks

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

## 7. Zero-Token Health Rule (INV-08 / PRO-07 / PRO-08)

- Health checks = local `health.json` reads ONLY. Zero model calls.
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
| Process alive, zero output for 30 min | Zombie-killed → timeout failure |

---

## 8. Heartbeat / Lease (crash-safety only)

- Purpose: orphan cleanup when hub process dies mid-ask
- `heartbeat_sec` = 30, `lease_timeout_sec` = 1800 (from `protocol.json`)
- Zombie guard: 60 consecutive silent heartbeats (30 min) → force-kill
- `hub.py lease-status` / `hub.py lease-sweep`
- Does NOT: auto-replay/retry tasks, trigger directives

---

## 9. gc Legacy Gate Mirror (gc-specific, see also `specific/gc.md`)

`_sys/gemini/status.json` is a legacy compat mirror of `health.json["availability"]["gate_open"]`.
Kept in sync by `hub.py _sync_peer_gate_file()` on quarantine/recover.
Future: migrate `gemini-*.bat` to read `health.json` directly → remove mirror.
