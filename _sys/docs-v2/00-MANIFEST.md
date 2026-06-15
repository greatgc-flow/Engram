# docs-v2 MANIFEST
> Version: 1.1 | Date: 2026-06-15 | Purpose: Workspace redesign SSOT (Active)
> Synthesized from _sys/docs/ originals (archived). Principles: MECE · General-Specific · Lazy (token-zero).
> Status: **ACTIVE SSOT** — _sys/docs/ is archived to _sys/docs/history/ (Legal Code reference only).

## Load Order (peer startup)

```
10-invariants.md      ← always load first (hard rules)
general/protocol.md   ← COLLAB_RATE + feedback loop
general/session.md    ← session decision tree
general/health.md     ← routing gate + recovery
specific/{peer_id}.md ← delta only (SKIP general already loaded)
```

For human onboarding: `user/manual.md` → then `00-MANIFEST.md`

## Structure Map

| File | Purpose | Source |
|------|---------|--------|
| `10-invariants.md` | MUST/MUST-NOT hard rules (INV-01~18, PRO-01~15) | PROTOCOL_INVARIANTS.md |
| `20-architecture.md` | Physical/logical dir layout + PathMap design | MECE_Spec + TAXONOMY_v11 |
| `general/protocol.md` | Collaboration model, COLLAB_RATE, feedback loop | collaboration_protocol.md |
| `general/consensus.md` | Voting lifecycle, R:10, tiebreak | protocol-consensus.md |
| `general/health.md` | Health states, routing gate, recovery | protocol-health.md |
| `general/session.md` | Session decision tree, handoff, startup contract | protocol-session.md |
| `general/permissions.md` | Minimum permission model (all peers) | protocol-permissions.md |
| `general/routing.md` | Leader election, role assignment | protocol-routing.md |
| `general/directives.md` | Runtime + user directives, injection, TTL | protocol-directives.md |
| `general/knowledge.md` | Lesson propagation, pack delivery | knowledge-propagation-spec.md |
| `specific/cc.md` | Claude Code: dirs, gate, delta flags | PEER_MANAGEMENT §2-1 |
| `specific/gc.md` | Gemini CLI: dirs, gate, delta flags | PEER_MANAGEMENT §2-2 |
| `specific/cx.md` | Codex: dirs, entry point, delta flags | PEER_MANAGEMENT §2-3 |
| `specific/ag.md` | AntiGravity: INACTIVE state + PRO-15 path | PEER_MANAGEMENT §2-4 |
| `ops/debate.md` | Exhaustive work session rules (끝장 작업) | DEBATE_PROTOCOL v0.10 |
| `ops/templates.md` | Goal frame, closure manifest, round templates | — |
| `ops/anti-patterns.md` | 21 peer failure modes (adversarial review) | — |
| `user/manual.md` | Human onboarding + daily workflow | USER_MANUAL.md |
| `_exceptions/` | Non-MECE items pending reclassification | — |

## General-Specific Inheritance

```
10-invariants.md  (absolute, no override)
       ↓
general/*.md      (universal rules — ALL peers inherit)
       ↓
specific/{id}.md  (delta only — lists ONLY what differs from general)
```

## Root Config Files (functional, not doc SSOT)

These files at `P:\` MUST NOT be moved (consumed by AI tools / check_policy.py):
- `CLAUDE.md` · `GEMINI.md` · `AGENTS.md` · `PROTOCOL.md` · `CONVENTION.md`
→ Copies in `_sys/docs/etc/` for reference only.

## Key Runtime Config (not docs)

| File | Purpose |
|------|---------|
| `_sys/ai/protocol.json` | collab_rate, r10_voters, timeouts — **single runtime SSOT** |
| `_sys/ai/peers.json` | peer capability registry |
| `_sys/ai/lifecycle_policy.json` | health thresholds, failure classification |
| `_sys/ai/governance_params.json` | 45 risk/budget/autonomy parameters |
| `_sys/ai/runtime-directives.jsonl` | active runtime directive log |
| `_sys/ai/knowledge/general/active-lessons.jsonl` | shared lesson store (all peers) |
| `_sys/ai/common/tool-registry.json` | versioned common agent/skill/tool index |
| `_sys/ai/proposals/` | async governance proposals (pending peer votes) |

## New Commands (hub.py additions — 2026-06-15)

| Command | Purpose |
|---------|---------|
| `lessons-list` | List active lessons (filterable by peer) |
| `lessons-propose` | Propose a new candidate lesson |
| `lessons-activate` | Approve and activate a candidate lesson |
| `lessons-retire` | Retire an active lesson |
| `lesson-broadcast` | Broadcast a lesson to all peers' mailboxes |
| `lesson-sweep` | Auto-promote high-frequency lessons to runtime-directives |
| `lesson-inject` | Print [PEER LESSONS] block for peer startup context |
| `thread-new` | Create a shared topic thread (freer communication) |
| `thread-append` | Append a message to a topic thread |
| `thread-react` | Add a compact reaction (ACK/NACK/BLOCKED/IDEA) to a message |
| `proposal-add` | Add a governance proposal to _sys/ai/proposals/ |
| `proposal-vote` | Vote on a governance proposal |
| `proposal-list` | List all proposals with vote status |
