# MOC — Master Index (Map of Content)

> docs-v2 SSOT v2.0 | Updated: 2026-06-26
> Short keyword load-map. The exhaustive file index + doc-status taxonomy live in `00-MANIFEST.md`.
> Loading strategy: EAGER for invariants/arch; LAZY (search this map) for everything else.

---

## ★ EAGER LOAD (always, at session start)

| File | Why Eager |
|------|-----------|
| `10-invariants.md` | Hard rules (INV-01~30, PRO-01~19, GAP-1 clause) — cannot proceed without these |
| `20-architecture.md` | Directory layout + PathMap — required for file operations |

---

## LAZY LOAD — 5 general pillars (load the one matching your domain)

| Domain | Pillar | Keywords / When to Load |
|--------|--------|------------------------|
| Governance · consensus · communication · command contract | `general/protocol.md` | COLLAB_RATE, R:10/tiebreak/Final Call (INV-28/02), terminal-transport (GAP-1/PRO-19), zero-token IPC, terminal command contract (GAP-3), tunable params |
| Routing · leader election · resource governance | `general/routing.md` | peer/model routing, elect-leader, failover, AP-20, same-peer fallback, node arch, cost/quality, QUALITY_MODE |
| Session · health · ContextGate | `general/lifecycle.md` | startup (INV-05), resume/handoff, health states/gate (INV-08/PRO-07/08), peer-status vs health-check, heartbeat/lease, ContextGate policy |
| Learning loop · directives · knowledge | `general/learning.md` | 5-Whys virtuous cycle, directives + TTL (PRO-09), lesson schema/propagation, self-care & autonomy bounds (SelfHealer=observe/propose only) |
| Permissions | `general/permissions.md` | minimum permissions, DIR-002, tool restrictions |

> **Model FACTS** (per-peer context/output limits, multipliers) live in JSON (`model-registry.json`, `orchestration.json`, `routing-config.json`) per requirement A1 — pillars hold POLICY only.

## LAZY LOAD — per-peer deltas

| Peer | File | Load When |
|------|------|-----------|
| cc (Claude Code) | `specific/cc.md` | working as / routing to cc |
| cx (Codex) | `specific/cx.md` | working as / routing to cx |
| ag (AntiGravity) | `specific/ag.md` | active peer (Gemini CLI successor) |
| gc (Gemini) | `specific/gc.md` | SUSPENDED tombstone (identity/history only) |

## LAZY LOAD — operations (living)

| Domain | File | Keywords |
|--------|------|----------|
| Governance & proposals | `ops/governance.md` | Garbage/, retention, proposal lifecycle, Doc-as-Code |
| Coding & conventions | `ops/conventions.md` | bat, py, naming, shell rules, script safety, tests |
| Logging architecture | `ops/logging.md` | IPC history, console capture, rolling policy, 5-Whys |
| Skill system | `ops/skills.md` | hub skills, catalog, invocation, registration |
| JSON schemas | `ops/schemas.md` | protocol.json, peers.json, model-registry, routing-config, health.json |
| Exhaustive work rules | `ops/debate.md` | ROI gate, exhaustive sessions, DIR-001 |
| Failure modes | `ops/anti-patterns.md` | AP-xx peer failure taxonomy |
| Audit checklist | `ops/audit-checklist.md` | MECE audit, release checklist, bootstrap checks |
| Work templates | `ops/templates.md` | goal frame, closure manifest, round templates |

## LAZY LOAD — design/roadmap (active specs; see MANIFEST doc-status)

| Domain | File |
|--------|------|
| **Authoritative roadmap** (Ask Transaction AT-0..AT-6) | `ops/backlog-5whys-consensus-2026-06-26.md` |
| **Docs restructure plan** | `ops/docs-restructure-blueprint-2026-06-26.md` |
| B1 per-profile health (AT-3 spec) | `ops/per-profile-health-b1-design.md` |
| Standard capability (AT-4/5 spec) | `ops/standard-capability-consensus-2026-06-25.md` |
| Terminal health-misread (AT-2/6 residuals) | `ops/terminal-health-misread-consensus-2026-06-25.md` |
| Full cross-audit (feeds AT-0/2/6) | `ops/full-audit-2026-06-26.md` |

## Human-facing & exceptions

| Domain | File |
|--------|------|
| Quick start & commands | `user/manual.md` |
| Root requirements | `user/requirements.md` |
| Active ambiguity register | `_exceptions/README.md` |

> Archived/superseded docs (merged pillars, dated debates/benchmarks/audits) live in `_sys/docs/history/` — see MANIFEST "Archived" section. Not loaded.

---

## Root Files (NOT in docs-v2 — DO NOT MOVE)

| File | Purpose |
|------|---------|
| `CLAUDE.md` | cc global config + always-on collab default |
| `GEMINI.md` | gc global config (suspended peer; retained) |
| `PROTOCOL.md` | Protocol routing index → docs-v2 |
| `CONVENTION.md` | Coding conventions |
| `AGENTS.md` | Repo contributor guide |
| `README.md` | Human project entry point |

---

## Taxonomy Diagram

```
docs-v2/
├── 00-MANIFEST.md        ← exhaustive file index + doc-status taxonomy + doc→config→check map
├── MOC.md                ← THIS FILE: short keyword load-map
├── 10-invariants.md      ← EAGER: INV/PRO/GAP hard rules
├── 20-architecture.md    ← EAGER: directory layout + PathMap
│
├── general/              ← 5 MECE pillars (all peers inherit)
│   ├── protocol.md       ← governance, consensus, communication, IPC, command contract
│   ├── routing.md        ← peer/model routing, leader election, resource governance
│   ├── lifecycle.md      ← session, health, ContextGate policy
│   ├── learning.md       ← 5-Whys loop, directives, knowledge, self-care bounds
│   └── permissions.md    ← minimum permissions, DIR-002
│
├── specific/             ← peer delta only (cc, cx, ag, gc-tombstone)
├── ops/                  ← living contracts + active design/roadmap docs
├── user/                 ← manual, requirements
└── _exceptions/          ← active ambiguity register
```
