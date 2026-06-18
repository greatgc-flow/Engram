# docs-v2 MANIFEST
> Version: 1.4 | Date: 2026-06-18 | Purpose: Workspace redesign SSOT (Active)
> Language: All docs in English (INV-19). Console output to user: Korean only.
> Principles: MECE · General-Specific · Lazy-load (token-efficient) · Doc-as-Code (ops/governance.md §6)
> Status: **ACTIVE SSOT** — `_sys/docs/` archived to `_sys/docs/history/` (Legal Code reference only).

---

## Load Order (peer startup)

```
EAGER (always):
  10-invariants.md      ← FIRST: hard rules (INV-01~19, PRO-01~16)
  20-architecture.md    ← directory layout, brain layers, connectivity map

LAZY (load when domain needed — see MOC.md for keyword index):
  general/protocol.md   ← COLLAB_RATE, P2P, feedback loop
  general/session.md    ← startup contract, resume, handoff
  general/health.md     ← routing gate, recovery
  specific/{peer_id}.md ← delta only (load AFTER general/)
```

For navigation by domain: `MOC.md` (Map of Content — full lazy-load registry)
For human onboarding: `user/manual.md`

---

## Structure Map

| File | Purpose | Updated |
|------|---------|---------|
| **`MOC.md`** | **Master Index: navigation by domain (EAGER/LAZY table, taxonomy diagram, feedback loop map)** | 2026-06-18 |
| `10-invariants.md` | MUST/MUST-NOT hard rules (INV-01~19, PRO-01~16) | 2026-06-18 |
| `20-architecture.md` | Physical/logical dir layout + PathMap + Brain layers | 2026-06-16 |
| `general/protocol.md` | Collaboration model, COLLAB_RATE, feedback loop | 2026-06-16 |
| `general/consensus.md` | Voting lifecycle, R:10, tiebreak, Final Call | 2026-06-16 |
| `general/health.md` | Health states, routing gate, recovery | 2026-06-16 |
| `general/session.md` | Session decision tree, handoff, startup contract | 2026-06-16 |
| `general/communication.md` | Sync/Async, alerting, send vs thread | 2026-06-16 |
| `general/tradeoffs.md` | Parameter registry: COLLAB_RATE, EFFORT, SLIM, SANDBOX | 2026-06-16 |
| `general/permissions.md` | Minimum permission model (all peers), DIR-002 | 2026-06-16 |
| `general/routing.md` | Leader election, failover, first_healthy fallback | 2026-06-16 |
| `general/directives.md` | Runtime + user directives, injection, TTL | 2026-06-16 |
| `general/knowledge.md` | Lesson propagation, pack delivery, active-lessons | 2026-06-16 |
| `general/self-evolution.md` | SelfHealer, DocsSyncer, SaturationDetector | 2026-06-18 |
| `general/master-plan.md` | Unified architecture blueprint (Recovery Journal, Continuity Score) | 2026-06-16 |
| `general/resource-governance.md` | Model inventory · Node arch (§6) · Role taxonomy (§7) · 5-Layer routing (§8) · Cost/quality (§9) · QUALITY_MODE (§10) · Continuous update (§11) | 2026-06-18 |
| `specific/cc.md` | Claude Code: dirs, gate, delta flags | 2026-06-16 |
| `specific/gc.md` | Gemini CLI: dirs, gate, delta flags | 2026-06-16 |
| `specific/cx.md` | Codex: dirs, entry point, delta flags | 2026-06-16 |
| `specific/ag.md` | AntiGravity: INACTIVE state + PRO-15 path | 2026-06-16 |
| `ops/governance.md` | Garbage/, retention, proposal lifecycle (§5), Doc-as-Code (§6) | 2026-06-18 |
| `ops/logging.md` | IPC history · console capture · per-node detail · rolling policy · 5-Whys | 2026-06-18 |
| `ops/skills.md` | Hub skill catalog, invocation, registration | 2026-06-18 |
| `ops/schemas.md` | JSON schema reference: protocol.json, peers.json, model-registry, health.json | 2026-06-18 |
| `ops/debate.md` | Exhaustive work session rules, ROI gate | 2026-06-16 |
| `ops/templates.md` | Goal frame, closure manifest, round templates | 2026-06-16 |
| `ops/anti-patterns.md` | 21 peer failure modes (AP-01~AP-21) | 2026-06-16 |
| `ops/audit-checklist.md` | MECE audit items — bootstrap, SUBST, cleanup, collab, docs | 2026-06-16 |
| `user/manual.md` | Human onboarding, daily workflow, command reference | 2026-06-16 |
| `user/requirements.md` | MECE user requirements (C-series constraints) | 2026-06-18 |
| `_exceptions/README.md` | Non-MECE items, edge cases, noise log (EX-01~06, EDGE-01~04) | 2026-06-18 |

---

## General-Specific Inheritance

```
10-invariants.md  (absolute — no override)
       ↓
general/*.md      (universal rules — ALL peers inherit)
       ↓
specific/{id}.md  (delta only — lists ONLY what differs from general)
```

---

## Root Config Files (MUST NOT be moved)

These files at `P:\` are consumed by AI tools from fixed paths. Content is authoritative at root.

| File | Purpose |
|------|---------|
| `CLAUDE.md` | cc global config + always-on collaboration default (★ Standing Default) |
| `GEMINI.md` | gc global config + collaboration interface |
| `PROTOCOL.md` | Protocol routing index only → delegates to docs-v2 |
| `CONVENTION.md` | Coding conventions (bat, py, naming, language policy §0) |
| `AGENTS.md` | Repo contributor guide (GitHub-facing) |
| `README.md` | Human project entry point |

---

## Key Runtime Config (operational — not docs)

| File | Purpose | Change Level |
|------|---------|-------------|
| `_sys/ai/protocol.json` | collab_rate, r10_voters, timeouts | R:10 |
| `_sys/ai/peers.json` | peer capability registry + model_profiles | R:5 |
| `_sys/ai/model-registry.json` | model measured specs SSOT (planned) | R:8 |
| `_sys/ai/routing-config.json` | QUALITY_MODE + routing weights (planned) | R:3/R:5 |
| `_sys/ai/user-directives.md` | human-authored standing rules (DIR-001~003) | Human only |
| `_sys/ai/runtime-directives.jsonl` | TTL-bound auto-promoted corrections | hub.py auto |
| `_sys/ai/knowledge/general/active-lessons.jsonl` | shared lesson store (all peers) | hub.py auto |
| `_sys/ai/proposals/` | governance proposals (pending peer votes) | any peer |

---

## hub.py Command Reference (key commands)

| Command | Purpose |
|---------|---------|
| `ask --to {peer}` | Route a query to a peer |
| `init-session --agent {id}` | Join P2P room |
| `health-update --peer {id} --status GREEN` | Self-report health |
| `health-check` | View all peer health |
| `context-fill` | Load session context |
| `proposal-add` | Add a governance proposal |
| `proposal-vote` | Vote on a proposal |
| `proposal-list` | List all proposals |
| `lessons-list` | List active lessons |
| `lessons-propose` | Propose a new lesson |
| `thread-new` | Create a shared topic thread |
| `thread-append` | Append to a thread |
| `update-config --key {k} --value {v}` | Update runtime config value |
