# Protocol Directives — Directive Management & Propagation

> Defines how standing rules, lessons-learned, and operational warnings
> are created, injected into peer context, and retired.

---

## §1 — Two-Layer Directive Model

| Layer | File | Authority | Created by | Never modified by |
|-------|------|-----------|------------|-------------------|
| **User Directives** | `_sys/ai/user-directives.md` | Human-confirmed | User explicitly | Automation |
| **Runtime Directives** | `_sys/ai/runtime-directives.jsonl` | System-generated | hub.py auto-promote | User |

**Both layers are injected into every peer ask** via `_build_ask_query_with_context()` in `hub.py`:
```
[USER DIRECTIVES]
... contents of user-directives.md ...

[RUNTIME DIRECTIVES]
- [RD-20260614-001] CAUTION: gc has repeatedly failed with reason=rate_limit ...
```

---

## §2 — User Directives (`user-directives.md`)

Human-authored standing rules. Examples:
- Per-peer minimum permission flags (DIR-002)
- Communication language rules (DIR-001)
- Architectural invariants

**Rules:**
- Only the user (or cc at user request) may add/remove entries
- Never overloaded with auto-generated operational warnings
- Format: free-form Markdown with numbered directive IDs (DIR-NNN)

---

## §3 — Runtime Directives (`runtime-directives.jsonl`)

Auto-generated temporary rules. One JSON record per line:

```json
{
  "id": "RD-20260614-001",
  "rule": "CAUTION: gc has repeatedly failed with reason=rate_limit. Verify peer health before routing asks to gc. Auto-clears on first successful ask.",
  "source_peer": "gc",
  "trigger_reason": "rate_limit",
  "trigger_detail": "quota exceeded (first 200 chars)",
  "effective": "20260614T125000",
  "expires": "20260614T185000",
  "ttl_hours": 6,
  "trigger_count": 2,
  "clear_condition": "first_success",
  "status": "active"
}
```

### Status values: `active` | `resolved` | `expired` (TTL lapsed)

---

## §4 — Auto-Promotion Trigger

A runtime directive is **automatically created** when:
- The same peer fails with the same `reason` **2+ consecutive times**

Logic in `hub.py` `_record_ask_failure()`:
1. On failure, capture `prev_failure_reason` before overwriting
2. If `consecutive_failures >= 2` and `prev_failure_reason == reason`:
   → call `_auto_promote_runtime_directive(peer_id, reason, detail, ai_root)`
3. If an active directive already exists for this peer+reason: bump `trigger_count` instead of duplicating

---

## §5 — Auto-Clear Trigger

A `first_success` directive is **automatically cleared** when:
- The same peer returns a successful ask (exit_code=0)

Logic in `hub.py` `_record_ask_success()`:
→ calls `_clear_peer_runtime_directives(peer_id, ai_root)` which resolves all `first_success` directives for that peer.

---

## §6 — TTL and Expiry

- Default TTL: **6 hours** (adjustable via `--ttl-hours` on `directive-add`)
- `_get_active_runtime_directives()` filters out entries where `expires < now`
- Expired entries remain in the file (for audit) but are never injected into peer context
- No automatic archiving
- **File type: State Journal** (JSONL-formatted but mutable) — entries are rewritten in-place
  during bump and clear operations. This differs from append-only **Event Logs**
  (e.g. `feedback.jsonl`) where entries are never modified after creation.

---

## §7 — Hub CLI Commands

```bash
# Add a manual runtime directive
python _sys/core/hub.py directive-add \
  --rule "Never call gc before rate limit resets" \
  --peer cc --ttl-hours 4 --clear-condition manual

# List active directives
python _sys/core/hub.py directive-list

# Manually resolve a directive
python _sys/core/hub.py directive-clear --directive-id RD-20260614-001
```

---

## §8 — Prompt Cap

To prevent context bloat, only **active + non-expired** entries are injected.
If the active list grows large, the oldest entries should be resolved or allowed to expire.

Hard caps (enforced in `hub.py _build_ask_query_with_context()`):
- Max active runtime directives injected: **10** (oldest first if exceeded)
- Max chars injected per ask from runtime directives: **2000** (overflow → truncation notice appended)

---

## §9 — Cross-Peer Propagation

Runtime directives propagate to **ALL peers** automatically:
- A gc failure creates a directive that is injected into cc, cx, ag asks as well
- Purpose: prevent cc/cx from also routing to gc while gc is known-degraded

This implements the "一 peer의 실패를 전체 피어에게 전파" principle from the T2 debate.

---

## §10 — What MUST NOT happen

1. **Never write auto-generated rules into `user-directives.md`** — that muddies human authority
2. **Never keep a directive active after the trigger condition is resolved** — clear on first_success
3. **Never inject directive content that is user-shell-injectable** (hub constructs rules from internal strings only)
4. **Never skip injection for a peer** claiming "it already knows" — every peer gets the full context

---

*Ref: `_sys/core/hub.py` `_get_active_runtime_directives` | `_auto_promote_runtime_directive` | `_clear_peer_runtime_directives` | `_build_ask_query_with_context`*
