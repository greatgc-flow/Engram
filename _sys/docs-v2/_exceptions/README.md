# _exceptions — Non-MECE Items, Edge Cases & Noise

This folder holds items that don't cleanly fit the General/Specific/Ops/User taxonomy, or represent extreme edge cases and known noise. Review periodically and reclassify when scope becomes clear.

## Classification Guide

| Situation | Action |
|-----------|--------|
| Doc spans multiple categories | Place canonical content in PRIMARY category; cross-ref note in secondary. No duplication. |
| Workspace state (not rule/spec) | Belongs in `_archive/` or `_sys/docs/history/`, not here. |
| Genuine ambiguity | Place here with a classification note below. |
| Noise / low-signal | Place here with a note; candidate for deletion at next audit. |

---

## Archived Items (Closed)

| ID | Item | Former Location | Archived To | Reason | Date |
|----|------|----------------|-------------|--------|------|
| EX-01 | bivca-architecture-final.md | `general/` | `_sys/docs/history/` | BIVCA cancelled 2026-06-18 | 2026-06-18 |
| EX-02 | bivca-plan-v1.1.md | `general/` | `_sys/docs/history/` | BIVCA cancelled 2026-06-18 | 2026-06-18 |
| EX-03 | peer-rules.md | `_sys/ai/common/` | `_sys/docs/history/` | Fully absorbed by 10-invariants + session.md | 2026-06-18 |
| EX-04 | impl-plan-general.md | `_sys/ai/proposals/` | `_archive/proposals/` | Superseded by docs-v2 SSOT adoption | 2026-06-18 |
| EX-05 | req-analysis-*.md (2 files) | `_sys/ai/proposals/` | `_archive/proposals/` | Pre-docs-v2 analysis, superseded | 2026-06-18 |
| EX-06 | CONTEXT.md | `_sys/claude/agent/` | `_sys/docs/history/` | Stale 3TCP/`.ai/` paths, conflicted with current docs | 2026-06-18 |

---

## Open Edge Cases

### EDGE-01: model-registry.json and routing-config.json not yet created

`general/resource-governance.md §11` and `ops/schemas.md §3-4` reference these as planned files.
**Risk:** Schema docs reference non-existent runtime files.
**Resolution:** Create during P2 implementation (resource-governance.md §4).

### EDGE-02: ~~`.ai/` vs `_sys/ai/` path inconsistency~~ (RESOLVED 2026-06-18)

Verified: `.ai/sessions/` exists at root (`P:\.ai\sessions\room-*`). Path in session.md is correct.
`_sys/ai/` holds config/state files (protocol.json, peers.json, etc.); `.ai/` holds runtime IPC (sessions, mailbox).
**Resolution:** Closed — no fix needed. Paths serve different purposes and are both correct.

### EDGE-03: master-plan.md implementation status unknown

`general/master-plan.md` has 5 roadmap items with no completion tracking.
**Resolution:** Audit each item against hub.py code; mark DONE/PENDING.

### EDGE-04: check_docs_mece.py not yet implemented

Documented in `ops/governance.md §6` as planned. Until it exists, INV-19 and coverage map rely on peer discipline.
**Resolution:** Implement and wire into self_care.py.

### EDGE-05: No automated path from active-lessons.jsonl → docs-v2 (feedback loop open)

**Root cause (gc exhaustive audit, 2026-06-18):** The feedback loop has an open gap at the Directive-to-Normative Graduation step.
- `runtime-directives.jsonl` corrects behavior with TTL. `active-lessons.jsonl` accumulates lessons.
- **Missing:** No automated trigger promotes a high-frequency lesson from `active-lessons.jsonl` into a permanent `docs-v2` rule or `10-invariants.md` entry.
- **Risk:** Directives expire → lessons bloat context without being synthesized into SSOT architecture. Root fixes remain implicit, not structural.
**Current state:** DocsSyncer (self-evolution.md §2.2) handles `consensus_finalize` → docs-v2 sync. But there is no lesson-frequency threshold check that triggers a promotion proposal.
**Resolution:** Extend `self_care.py` to: (1) count lesson occurrence frequency, (2) when a lesson appears ≥ 3 times in 7 days → auto-generate `proposal-add` to graduate it into a docs-v2 rule or invariant. Requires R:10 consensus to apply. Add to Phase 6 of self-evolution.md §5.

---

## Noise Candidates (Review at Next Audit)

| Item | Location | Status |
|------|----------|--------|
| `delightful-imagining-tower.md` | `_sys/claude/config/plans/` | Superseded by resource-governance v3 |
| `glittery-mapping-shore.md` | `_sys/claude/config/plans/` | Unknown state |
| `20260615-adopt-docs-v2-as-ssot-001.md` | `_sys/ai/proposals/` | ~~MOVED~~ → `_archive/proposals/accepted/` (2026-06-18) |

_Last audited: 2026-06-18 (cc+gc cross-link sync audit, collab_rate:10). Round 2._
