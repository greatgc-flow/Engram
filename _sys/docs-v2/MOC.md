# MOC — Master Index (Map of Content)

> docs-v2 SSOT v1.5 | Updated: 2026-06-21
> Single navigation root for all peers and human readers.
> Loading strategy: EAGER for invariants/arch; LAZY (search when needed) for everything else.

---

## ★ EAGER LOAD (Always Read at Session Start)

| File | Why Eager | Token Cost |
|------|-----------|-----------|
| `10-invariants.md` | Hard rules — cannot proceed without knowing these | ~3k tokens |
| `20-architecture.md` | Directory layout — required for all file operations | ~4k tokens |

---

## LAZY LOAD REGISTRY (Load when domain is active)

Peer: search this table first. Load only the file(s) relevant to your current task.

### Governance & Collaboration

| Domain | File | Keywords / When to Load |
|--------|------|------------------------|
| Collaboration model | `general/protocol.md` | COLLAB_RATE, P2P sync, feedback loop, virtuous cycle |
| Consensus & voting | `general/consensus.md` | R:10, tiebreak, Final Call, voter list |
| Session lifecycle | `general/session.md` | startup contract, resume, handoff, INV-05/06 |
| Health & routing gate | `general/health.md` | GREEN/YELLOW/RED, zero-token, peer-recover |
| Leader election | `general/routing.md` | elect-leader, failover, AP-20, first_healthy |
| Permissions | `general/permissions.md` | minimum permissions, DIR-002, tool restrictions |
| Directives | `general/directives.md` | standing rules, TTL, runtime-directives.jsonl |
| Communication patterns | `general/communication.md` | send vs thread, alerting, sync/async |
| Knowledge propagation | `general/knowledge.md` | lesson lifecycle, pack delivery, active-lessons |
| Self-evolution | `general/self-evolution.md` | self_care.py, DocsSyncer, SaturationDetector |
| Parameter tradeoffs | `general/tradeoffs.md` | COLLAB_RATE/EFFORT/SLIM/SANDBOX tuning |
| Proposal lifecycle | `ops/governance.md §5` | proposal states, TTL, voting thresholds, template |

### Resource & Cost Management

| Domain | File | Keywords / When to Load |
|--------|------|------------------------|
| AI resource governance | `general/resource-governance.md` | model inventory, node arch, ContextGate, QUALITY_MODE, routing layers, feedback loop |
| **Token & model specs** | **`general/token-management.md`** | **per-peer model inventory, context limits, output limits, Extended Thinking API, ContextGate v1.0 design** |

> **Note:** resource-governance.md is large (739 lines). Load specific sections by keyword:
> §1=model specs, §3=ContextGate, §6=node matrix, §7=role mapping, §8=routing arch, §9=cost tracking, §10=QUALITY_MODE, §11=model updates
>
> **token-management.md** is the corrected per-peer spec source (cc/gc/cx). resource-governance.md provides architecture; token-management.md provides exact numbers.

### Per-Peer Specifics

| Peer | File | Load When |
|------|------|-----------|
| cc (Claude Code) | `specific/cc.md` | Working as or routing to cc |
| gc (Gemini CLI) | `specific/gc.md` | Working as or routing to gc |
| cx (Codex) | `specific/cx.md` | Working as or routing to cx |
| ag (AntiGravity) | `specific/ag.md` | active peer and Gemini CLI successor |

### Operations

| Domain | File | Keywords / When to Load |
|--------|------|------------------------|
| Logging architecture | `ops/logging.md` | IPC history, console capture, rolling policy, 5-Whys investigation |
| Governance & proposals | `ops/governance.md` | Garbage/, retention, proposal lifecycle, Doc-as-Code |
| Skill system | `ops/skills.md` | hub skills, catalog, invocation, registration |
| JSON schemas | `ops/schemas.md` | protocol.json, peers.json, model-registry, routing-config, health.json |
| **Peer architecture decision** | **`ops/peer-debate-2026-06-19.md`** | **Final terminology, topology, lifecycle, context, status, TDD, and benchmarks** |
| **Automatic profile routing** | **`ops/automatic-profile-routing-2026-06-20.md`** | **Terminal defaults, promotion/demotion, fallback, tests, benchmark** |
| Exhaustive work rules | `ops/debate.md` | ROI gate, exhaustive work sessions, DIR-001 |
| Failure modes | `ops/anti-patterns.md` | AP-01~AP-21, peer failure taxonomy |
| Audit checklist | `ops/audit-checklist.md` | MECE audit, release checklist, bootstrap checks |
| Work templates | `ops/templates.md` | goal frame, closure manifest, round templates |

### Human-Facing

| Domain | File | Load When |
|--------|------|-----------|
| Quick start & commands | `user/manual.md` | Human onboarding, command reference |
| MECE requirements | `user/requirements.md` | Feature requirements, C-series constraints |

### Edge Cases & Non-MECE

| Domain | File | Load When |
|--------|------|-----------|
| Exceptions & noise | `_exceptions/README.md` | Debugging classification issues, auditing |

---

## Root Files (NOT in docs-v2 — DO NOT MOVE)

These files live at `P:\` root because AI tools load them from fixed paths.

| File | Purpose | Content Lives In |
|------|---------|-----------------|
| `CLAUDE.md` | cc global config + always-on collab default | Root (user-facing config) |
| `GEMINI.md` | gc global config + collab interface | Root (user-facing config) |
| `PROTOCOL.md` | Protocol routing index → docs-v2 | Root (pointer only) |
| `CONVENTION.md` | Coding conventions (bat, py, naming) | Root (tool-consumed) |
| `AGENTS.md` | Repo contributor guide | Root (GitHub-consumed) |
| `README.md` | Human project entry point | Root (human-facing) |

---

## Operational Files (Not Docs — Runtime State)

| File | Purpose | SSOT |
|------|---------|------|
| `_sys/ai/protocol.json` | Master runtime config | Single source |
| `_sys/ai/peers.json` | Peer capability registry | Derived from model-registry (P2) |
| `_sys/ai/user-directives.md` | Human standing rules (DIR-001~003) | Human-authoritative |
| `_sys/ai/runtime-directives.jsonl` | TTL-bound auto-promoted corrections | hub.py managed |
| `_sys/ai/model-registry.json` | Model measured specs (planned) | R:8 to change |
| `_sys/ai/routing-config.json` | QUALITY_MODE + automatic profile routing + role weights | R:3/R:5 to change |
| `_sys/data/logs/cost-log.jsonl` | Per-ask cost/quality tracking | Observer (gitignored) |

---

## Taxonomy Diagram

```
docs-v2/
├── 00-MANIFEST.md        ← file-level index (load order, table of files)
├── MOC.md                ← THIS FILE: navigation by domain (human + peer)
├── 10-invariants.md      ← EAGER: hard rules (INV/PRO)
├── 20-architecture.md    ← EAGER: directory layout + brain layers
│
├── general/              ← universal rules, all peers inherit
│   ├── protocol.md       ← P2P collab, COLLAB_RATE, feedback loop
│   ├── consensus.md      ← voting, R:10, Final Call
│   ├── session.md        ← startup contract, resume, handoff
│   ├── health.md         ← health states, routing gate, recovery
│   ├── routing.md        ← leader election, failover
│   ├── permissions.md    ← minimum permissions, DIR-002
│   ├── directives.md     ← standing rules, TTL
│   ├── communication.md  ← sync/async, send vs thread
│   ├── knowledge.md      ← lesson propagation
│   ├── self-evolution.md ← self_care, DocsSyncer, SaturationDetector
│   ├── tradeoffs.md      ← parameter registry
│   ├── master-plan.md    ← unified architecture blueprint
│   └── resource-governance.md ← model inventory, node arch, cost/quality
│
├── specific/             ← peer delta only (what differs from general/)
│   ├── cc.md
│   ├── gc.md
│   ├── cx.md
│   └── ag.md
│
├── ops/                  ← operational procedures
│   ├── governance.md     ← Garbage/, retention, proposals, Doc-as-Code
│   ├── logging.md        ← log taxonomy, rolling policy, 5-Whys
│   ├── skills.md         ← hub skill catalog + invocation
│   ├── schemas.md        ← JSON schema reference
│   ├── debate.md         ← exhaustive work session protocol
│   ├── anti-patterns.md  ← AP-01~AP-21 failure modes
│   ├── audit-checklist.md← MECE audit items
│   └── templates.md      ← work templates
│
├── user/                 ← human-readable guides
│   ├── manual.md         ← quick start, daily workflow
│   └── requirements.md   ← MECE feature requirements
│
└── _exceptions/          ← non-MECE items, edge cases, noise
    └── README.md         ← exception log + open edge cases
```

---

## Feedback Loop Closure Map

```
[User Request]
    ↓
[Router: gc::3.5-flash or cc::haiku] → reads MOC.md + 10-invariants.md
    ↓
[Executor: appropriate node per role taxonomy]
    ↓
[Observer: writes cost-log.jsonl, ipc-log.jsonl]
    ↓
[self_care.py: analyzes logs → proposals]
    ↓
[active-lessons.jsonl accumulates patterns]
    ↓ ⚠ OPEN GAP (EDGE-05)
[Phase 6: lesson-frequency graduation → proposal-add to docs-v2]  ← NOT YET IMPLEMENTED
    ↓
[Consensus: R:5 or R:8 ACK]
    ↓
[Apply: routing-config.json + docs-v2 + peers.json updated]
    ↓ (back to top)
[Next request uses improved routing]
```

_Every link in this loop is documented: Resource-Governance §8-§11, ops/logging.md §10, ops/governance.md §5-§6, general/self-evolution.md §4._
_Open gap (EDGE-05): lesson→docs-v2 graduation path not yet automated. See `_exceptions/README.md §EDGE-05`._

---

_MOC v1.5 updated 2026-06-21. cc+ag+cx docs-v2 MECE sync. Invariants and consensus updated. Covers 30 docs-v2 files + 7 root files + 7 operational config files._
