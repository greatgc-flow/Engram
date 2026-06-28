# docs-v2 MANIFEST
> Version: 2.0 | Date: 2026-06-26 | Purpose: Workspace SSOT (Active) — sole exhaustive index
> Language: All docs in English (INV-19). Console output to user: Korean only.
> Principles: MECE · General-Specific · Lazy-load (token-efficient) · Doc-as-Code (ops/governance.md §6)
> Status: **ACTIVE SSOT** — superseded/dated docs archived to `_sys/docs/history/` (reference only).

---

## Doc-status taxonomy (GAP-3)
Every doc carries one status. The MANIFEST is the single exhaustive index; `MOC.md` is a short keyword load-map only.

| Status | Meaning |
|--------|---------|
| **living** | Active contract — the current rule of record. |
| **design** | Signed consensus/design spec for an unstarted/in-progress Ask-Transaction slice; migrates into a living pillar + archives once its slice lands (per `ops/backlog-5whys-consensus-2026-06-26.md` R1). |
| **historical** | Point-in-time record (dated debate/benchmark/audit) in `_sys/docs/history/`; provenance only. |
| **superseded-by** | Replaced; pointer to the doc that absorbed it. |

---

## Load Order (peer startup)

```
EAGER (always):
  10-invariants.md      ← FIRST: hard rules (INV-01~30, PRO-01~19, +GAP-1 clause)
  20-architecture.md    ← directory layout, PathMap, brain layers, connectivity map

LAZY (load when domain needed — see MOC.md for keyword index):
  general/protocol.md   ← governance/roles (GAP-1), COLLAB_RATE, consensus, communication/IPC, command contract (GAP-3)
  general/routing.md    ← peer/model routing, leader election, failover, resource governance
  general/lifecycle.md  ← session resume/handoff, health states, ContextGate policy
  general/learning.md   ← 5-Whys loop, directives, knowledge propagation, self-care bounds
  general/permissions.md← minimum permission model, DIR-002
  specific/{peer_id}.md ← delta only (load AFTER general/)
```

For navigation by domain: `MOC.md`. For human onboarding: `user/manual.md`.

---

## Structure Map (living set — exhaustive)

| File | Status | Purpose | Updated |
|------|--------|---------|---------|
| `00-MANIFEST.md` | living | THIS FILE — sole exhaustive index + doc-status taxonomy + doc→config→check map | 2026-06-26 |
| `MOC.md` | living | Keyword load-map (lazy-load registry) | 2026-06-26 |
| `10-invariants.md` | living | MUST/MUST-NOT hard rules (INV-01~30, PRO-01~19, GAP-1 clause) | 2026-06-26 |
| `20-architecture.md` | living | Physical/logical dir layout + PathMap (req A2) + Brain layers | 2026-06-16 |
| `general/protocol.md` | living | **Pillar 1** — governance/roles (GAP-1), trade-offs/params, task-execution+feedback, collaboration+consensus (R:10, INV-28, INV-02), communication+IPC, state+handoff, terminal command contract (GAP-3). Absorbs {consensus, communication, tradeoffs}. | 2026-06-26 |
| `general/routing.md` | living | **Pillar 2** — separation/node-arch, peer+model routing, leader election+roles, challenge window+handoff+AP-20, forwarding+failover, cost/quality/context, governance/permissions/acceptance. Absorbs {resource-governance}. | 2026-06-26 |
| `general/lifecycle.md` | living | **Pillar 3** — session decision/startup(INV-05)/handoff/resume, health states/file-location/gate/runbooks(INV-08,PRO-07/08), heartbeat/lease, ContextGate policy. Absorbs {session, health, token-budget policy}. Model facts → JSON. | 2026-06-26 |
| `general/learning.md` | living | **Pillar 4** — 5-Whys learning loop, directives system (PRO-09), knowledge propagation + lesson schema, self-care & autonomy bounds (SelfHealer=observe/propose only), implementation status. Absorbs {self-evolution, feedback-loop, directives, knowledge}. | 2026-06-26 |
| `general/permissions.md` | living | **Pillar 5** — minimum permission model (all peers), DIR-002, non-interactive bounds | 2026-06-16 |
| `specific/cc.md` | living | Claude Code delta (dirs, gate, flags) | 2026-06-26 |
| `specific/cx.md` | living | Codex delta (dirs, entry point, flags) | 2026-06-16 |
| `specific/ag.md` | living | AntiGravity delta (ACTIVE, PTY, stateless-home) | 2026-06-19 |
| `specific/gc.md` | living | Gemini — SUSPENDED TOMBSTONE | 2026-06-25 |
| `ops/governance.md` | living | Garbage/, retention, proposal lifecycle (§5), Doc-as-Code (§6) | 2026-06-18 |
| `ops/conventions.md` | living | Coding conventions, shell rules, script safety, testing policy | 2026-06-26 |
| `ops/logging.md` | living | IPC history · console capture · per-node detail · rolling policy · 5-Whys | 2026-06-26 |
| `ops/skills.md` | living | Hub skill catalog, invocation, registration | 2026-06-18 |
| `ops/schemas.md` | living | JSON schema reference: protocol.json, peers.json, model-registry, health.json | 2026-06-18 |
| `ops/debate.md` | living | Exhaustive work session rules, ROI gate | 2026-06-26 |
| `ops/templates.md` | living | Goal frame, closure manifest, round templates | 2026-06-16 |
| `ops/anti-patterns.md` | living | Peer failure modes (AP-01~) | 2026-06-16 |
| `ops/audit-checklist.md` | living | MECE audit items — bootstrap, SUBST, cleanup, collab, docs | 2026-06-16 |
| `ops/backlog-5whys-consensus-2026-06-26.md` | design | **AUTHORITATIVE ROADMAP** — Ask Transaction AT-0..AT-6; KEEP/DROP/DEFER verdicts | 2026-06-26 |
| `user/manual.md` | living | Human onboarding, daily workflow, command reference | 2026-06-26 |
| `user/requirements.md` | living | Root requirement contract (A1-A5...) — source of intent | 2026-06-26 |
| `_exceptions/README.md` | living | Active ambiguity register (small; not a backlog) | 2026-06-26 |

### Archived (`_sys/docs/history/`) — superseded/historical, not loaded
general (merged into pillars): `consensus`,`communication`,`tradeoffs` → protocol.md; `resource-governance` → routing.md; `session`,`health`,`token-management` → lifecycle.md; `self-evolution`,`feedback-loop`,`directives`,`knowledge` → learning.md; `master-plan`,`master-refactor-v5` → dropped (5-Whys).
specific: `statusline_diag_update` → merged into ops/logging.md §12 + user/manual.md.
ops (dated/superseded): `peer-debate-2026-06-19`,`automatic-profile-routing-2026-06-20`,`perf-benchmark-2026-06-19(+full)`,`consistency-audit-2026-06-24`,`TDD_PLAN_HUB_V42`,`REMAINING_ACTIONS`,`remaining-items`.
ops (AT-implemented specs, archived under AT-6): `docs-restructure-blueprint-2026-06-26`,`per-profile-health-b1-design`(→AT-3),`standard-capability-consensus-2026-06-25`(→AT-4/AT-5),`terminal-health-misread-consensus-2026-06-25`(→AT-2/AT-6),`full-audit-2026-06-26`(→AT-0/AT-2/AT-6).

---

## General-Specific Inheritance

```
10-invariants.md  (absolute — no override)
       ↓
general/*.md      (5 MECE pillars — ALL peers inherit)
       ↓
specific/{id}.md  (delta only — lists ONLY what differs from general)
```

---

## Doc → Config → Check map (A1 interface contracts — sets up directives/source/config alignment)

| Pillar | Config SSOT | Check/test |
|--------|-------------|-----------|
| `protocol.md` | `protocol.json`, `orchestration.json` | `test_contracts.py`, keystone/consensus tests, PRO-19 guard |
| `routing.md` | `orchestration.json`, `routing-config.json` | routing/dispatch + `resolve_peer_sys_dir` tests |
| `lifecycle.md` | `model-registry.json`, health thresholds in `protocol.json` | `test_health*`, context-gate, AT-1/AT-3 |
| `learning.md` | `user-directives.md`, proposals dir | directive-injection, self-care/graduation e2e (AT-0) |
| `permissions.md` | `orchestration.json` DIR-002 flags | `test_peer_permissions.py` |
| `10/20` | `protocol.json`; path dictionary (A2) | invariant tests, CHK-01..08, GAP-2 path-check (new) |

---

## Root Config Files (MUST NOT be moved)
| File | Purpose |
|------|---------|
| `CLAUDE.md` | cc global config + always-on collaboration default |
| `GEMINI.md` | gc global config (suspended peer; retained) |
| `PROTOCOL.md` | Protocol routing index only → delegates to docs-v2 |
| `CONVENTION.md` | Coding conventions (bat, py, naming, language policy) |
| `AGENTS.md` | Repo contributor guide (GitHub-facing) |
| `README.md` | Human project entry point |

---

## Key Runtime Config (operational — not docs)
| File | Purpose | Change Level |
|------|---------|-------------|
| `_sys/ai/protocol.json` | collab_rate, r10_voters, timeouts, health thresholds | R:10 |
| `_sys/ai/peers.json` | installation/provider registry; node_ids→sys_subdir (SSOT resolver) | R:5 |
| `_sys/ai/orchestration.json` | logical peers + nested runtime profiles | R:8 |
| `_sys/ai/model-registry.json` | model measured specs SSOT (model FACTS per A1) | R:8 |
| `_sys/ai/routing-config.json` | QUALITY_MODE + automatic profile routing + role weights | R:3/R:5 |
| `_sys/ai/user-directives.md` | human-authored standing rules (DIR-001~003); PRO-09: no auto-rules | Human only |
| `_sys/ai/runtime-directives.jsonl` | TTL-bound auto-promoted corrections | hub.py auto |
| `_sys/ai/knowledge/general/active-lessons.jsonl` | shared lesson store (all peers) | hub.py auto |
| `_sys/ai/proposals/` | governance proposals (pending peer votes); lazily created by hub.py `_proposals_dir()` on first proposal | any peer |

---

## hub.py Command Reference (terminal command contract — see protocol.md §7)
| Command | Purpose |
|---------|---------|
| `peer-status` | **Canonical** peer status (non-mutating, orchestration-filtered) |
| `status` | Room/session status |
| `health-precheck --peer {id}` | Routability check before an ask |
| `model-status` / `profile-validate` | Model inventory / profile parity |
| `health-check` | Audit/maintenance health view (read-only by default; `--recover` mutates) |
| `ask --to {peer}` | Route a query to a peer |
| `init-session --agent {id}` | Join P2P room |
| `health-update --peer {id} --status GREEN` | Self-report health (refused for disabled peers) |
| `proposal-add` / `proposal-vote` / `proposal-list` | Governance proposals |
| `lessons-list` / `lessons-propose` | Active lessons |
| `thread-new` / `thread-append` | Shared topic threads |
| `lease-status` / `lock-status` / `task-status` / `role-status` | State views |

> Terminal reads raw `_sys/` state files ONLY for explicit audit or when the canonical command is missing/broken — and must say so (GAP-3 / PRO-19).
