# General — Knowledge Propagation
> Source: knowledge-propagation-spec.md v1.0 · Status: SPEC_FINAL (implementation pending)

---

## 1. Problem

Mistakes repeat across peers because:
- Observations are not recorded
- Even when recorded, not propagated to other peers
- No closed-loop: observe → normalize → approve → inject → verify

---

## 2. Three-Layer Architecture

```
Layer 1: RAW EVENTS (audit store — never injected directly)
  _sys/ai/knowledge/mistake-events.jsonl
  _sys/ai/knowledge/user-feedback.jsonl
         ↓ triage/normalize
Layer 2: ACTIVE LESSON REGISTRY (approved rules)
  _sys/ai/knowledge/active-lessons.jsonl
         ↓ filter + compile (per-peer)
Layer 3: DELIVERY PACKS (prompt-facing)
  _sys/ai/knowledge/active-pack-index.json → hub.py [PEER LESSONS]
```

---

## 3. Lesson Record Schema

```json
{
  "id": "L-2026-001",
  "scope": "global | workspace",
  "applies_to": ["cc", "gc"],
  "rule": "Always verify path exists before Move-Item.",
  "severity": "HIGH | MEDIUM | LOW",
  "source_event": "mistake-events.jsonl#event_id",
  "approved_by": "user",
  "status": "active | retired",
  "recurrence_count": 0,
  "expires": null
}
```

---

## 4. Closed Feedback Loop

```
observe → raw event written → candidate lesson →
approval (user) → active registry → compiled pack →
injected into peer ask → delivery log →
recurrence check → retire/update → (next cycle)
```

---

## 5. Token Efficiency

- Hash-ACK pack compression: peer ACKs received pack hash → no re-injection if hash unchanged
- Global vs workspace scoping: global lessons shared across all workspaces; workspace lessons scoped to current project
- Never inject entire lesson history — only active, approved, non-expired entries

---

## 6. Implementation Status

| Component | Status |
|-----------|--------|
| Raw event files | Created (empty) |
| active-lessons.jsonl | Created (empty) |
| Triage + approval flow | PENDING |
| Pack compilation | PENDING |
| hub.py injection point | PENDING |
