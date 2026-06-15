# General Protocol — Collaboration Model
> Applies to ALL peers. Specific deltas → `specific/{peer}.md`.
> Source: collaboration_protocol.md v4.1

---

## 1. General-Specific Resolution Order

```
default → general → project → room → peer → task
```

Lower layers may only **narrow or add stricter** constraints — never weaken or bypass General invariants.
Peer equality = equal proposal/review/vote rights. Human veto always overrides.

---

## 2. COLLAB_RATE — Collaboration Depth

> Runtime value: `_sys/ai/protocol.json["collab_rate"]["current"]`

| Rate | Mode | Autonomy | Rule |
|:----:|:-----|:--------:|:-----|
| 0 | Solo | 100% | Fully autonomous. |
| 3 | System Guard | 75% | `_sys/` changes and constitutional docs require consensus. |
| 5 | Partner | 50% | Consensus at design start + milestone. |
| 8 | Strict | 25% | All logic changes need consensus. Only typos autonomous. |
| 10 | Brain Sync | 0% | ANY file modification requires prior consensus. No exceptions. |

**Adaptive rate by task risk (session default):**

| Risk | Rate | Applies to |
|------|:----:|:-----------|
| Low | 0 | Read-only, grep, explore, doc reads |
| Med | 3 | `workspace/` code changes |
| High | 5 | `_sys/` script changes |
| Multi-script | 8 | Spans multiple `_sys/` scripts |
| Critical | 10 | `PROTOCOL.md`, `CLAUDE.md`, `GEMINI.md`, `hub.py`, `nodes.json` |

Zero-token local operations (observe/validate/classify) are **exempt** from COLLAB_RATE at all levels.

> **Always zero-token (explicit list):** reading `health.json`, `handoff.md`, `mailbox.json`, `runtime-directives.jsonl`, `user-directives.md` — regardless of COLLAB_RATE. See `general/session.md §7`.

---

## 3. Canonical Feedback Loop

```
observe → classify → decide → sync → act_or_ask → record → handoff → improve
```

- **observe**: read state.json, handoff.md, health, mailbox, runtime-directives.jsonl
- **classify**: map to declared rules (no semantic invention)
- **decide**: local action / connector / peer ask / human escalation
- **sync**: acquire lock, resolve contention
- **act_or_ask**: execute connector, ask peer, or escalate
- **record**: write provenance + classify ask outcome via `_record_ask_success/failure()`
- **handoff**: compact durable state; large content as file refs
- **improve**: resolved ambiguity → Specific rule or General proposal

### Operational Health Sub-Loop (automated, zero-token)

```
ask_outcome → _record_ask_success/failure()
           → health.json updated
           → routing precheck reads health.json
           → RED/gate-closed peers excluded
           → peer-recover → routing restored
```

---

## 4. Durable State Stores (MECE)

| Store | File | Content | TTL |
|-------|------|---------|-----|
| Session blackboard | `.ai/sessions/<room>/handoff.md` | Tasks, decisions, blockers | Until archived |
| Operational directives | `_sys/ai/runtime-directives.jsonl` | Behavioral corrections from failures | TTL-bound (default 6h) |

handoff.md = volatile state (WHAT we're doing).
runtime-directives.jsonl = durable corrections (HOW to behave differently).

---

## 5. Zero-Token Boundary

**Exempt (no COLLAB_RATE gate):**
- `local_observe/read`: file/dir reads and environment state
- `local_validate/schema`: syntax, schema, declared dry checks
- `local_classify/risk routing`: static metadata routing (no edits)

**Governed (subject to COLLAB_RATE):**
- Write operations, workspace edits, command executions with side-effects
- A command is NOT exempt because it's "described as dry" — requires declared connector metadata

**Pre-Consensus Peer Asks:**
- Info gathering (non-binding): permitted without prior consensus
- Binding vote/approval: must follow consensus protocol
- NO implementation may execute based on non-binding gathering

---

## 6. Required Safety Dimensions

Policy schema must cover: versioning · authority · precedence · lifecycle · concurrency/locks · idempotency · observability · failure modes (fail closed) · security/privacy · extension fields (`x-*`).

---

## 7. Ambiguity Contract

Every ambiguity entry records: uncertainty · candidate interpretations · confidence · ask_threshold · escalation_vector · owner · status · resolution_reference.

If confidence < ask_threshold → MUST ask or escalate before acting.
If local records conflict and no rule resolves → fail closed (ask/escalate).
