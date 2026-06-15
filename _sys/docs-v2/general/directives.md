# General — Directives System
> Source: protocol-directives.md · hub.py `_build_ask_query_with_context()`

---

## 1. Two-Layer Model

| Layer | File | Authority | Created by | Modified by |
|-------|------|-----------|------------|-------------|
| **User Directives** | `_sys/ai/user-directives.md` | Human-confirmed | User (or cc at user request) | User only |
| **Runtime Directives** | `_sys/ai/runtime-directives.jsonl` | System-generated | hub.py auto-promote | Never by user |

Both layers injected into every peer ask by `_build_ask_query_with_context()`.

---

## 2. User Directives (`user-directives.md`)

Human-authored standing rules (DIR-NNN format).
Examples: per-peer minimum permissions (DIR-002), language rules (DIR-001), architectural invariants.

**PRO-09**: NEVER write auto-generated warnings here — muddies human authority.

---

## 3. Runtime Directives (`runtime-directives.jsonl`)

Auto-generated temporary rules. State journal (entries rewritten in-place — NOT append-only).

```json
{
  "id": "RD-20260614-001",
  "rule": "CAUTION: gc has repeatedly failed with reason=rate_limit. Verify peer health before routing.",
  "source_peer": "gc", "trigger_reason": "rate_limit",
  "effective": "20260614T125000", "expires": "20260614T185000",
  "ttl_hours": 6, "trigger_count": 2,
  "clear_condition": "first_success", "status": "active"
}
```

Status: `active` | `resolved` | `expired`

---

## 4. Auto-Promote Trigger

Runtime directive auto-created when: same peer fails with same `reason` **2+ consecutive times**.

Logic in `_record_ask_failure()`:
- If `consecutive_failures ≥ 2` AND `prev_failure_reason == reason` → `_auto_promote_runtime_directive()`
- If active directive already exists for peer+reason → bump `trigger_count` (no duplicate)

---

## 5. Auto-Clear Trigger

`first_success` directive cleared when: same peer returns exit_code=0.
Logic: `_record_ask_success()` → `_clear_peer_runtime_directives(peer_id)`.

---

## 6. TTL & Expiry

- Default TTL: 6h (adjustable via `--ttl-hours`)
- Expired entries stay in file (audit) but never injected
- Injection cap: max 10 active directives, max 2000 chars; overflow → truncation notice

---

## 7. Cross-Peer Propagation

Runtime directives propagate to ALL peers — a gc failure gets injected into cc/cx/ag asks too.
Purpose: prevent other peers from routing to a known-degraded peer.

---

## 8. Hub CLI Commands

```
hub.py directive-add --rule "..." --peer cc --ttl-hours 4 --clear-condition manual
hub.py directive-list
hub.py directive-clear --directive-id RD-20260614-001
```
