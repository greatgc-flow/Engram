# docs-v2 Restructure Blueprint — 5-Whys Consensus (2026-06-26)

> **Status:** HISTORICAL (IMPLEMENTED) — 5 pillars established; status sync active under AT-6.

## Why (root-traced)
Every doc was 5-Whys-validated against `user/requirements.md` (A1 JSON-config/no-code, A2 path-dict, A3 portability, A4 lifecycle, general→specific MECE) + the refined need (thin terminal, predictable routing/health/consensus, durable improvement, trustworthy delegation). Findings: the `general/` layer is **16 fragmented, overlapping docs**; `ops/` mixes living policy with dated point-in-time records; several docs **contradict current code** (Continuity Score, SelfHealer auto-remediation — both DROPPED 2026-06-26) or are **aspirational** ("PENDING pack", "PLANNED alert"); `token-management` hardcodes model facts (violates A1).

## Target structure — 5 MECE general pillars
| Pillar | Absorbs | Owns |
|---|---|---|
| `general/protocol.md` | consensus + communication + tradeoffs | governance, consensus mechanics, terminal-transport rule, **terminal command contract**, GAP-1 invariant |
| `general/routing.md` | resource-governance | peer dispatch, profile/tier routing, leader/role, resource governance |
| `general/lifecycle.md` (NEW) | session + health + ContextGate/token-budget POLICY | session resume, health states, context-gate policy (model FACTS → JSON) |
| `general/learning.md` (NEW) | self-evolution + feedback-loop + directives + knowledge | observe→resolve→propagate loop, lesson graduation, runtime directives (NO SelfHealer auto-remediation) |
| `general/permissions.md` | (standalone) | DIR-002, sandbox bounds, non-interactive minimums |
| `10-invariants.md`, `20-architecture.md` | (KEEP standalone) | invariants index; physical/logical architecture + PathMap (GAP-2) |

## Resolutions (R1-R3, signed)
- **R1 — consensus/design doc lifecycle:** a consensus/design doc stays LIVING/DESIGN while it is the active spec for an unstarted/in-progress Ask-Transaction slice; once the slice lands, its durable rules migrate into the owning pillar, a `superseded-by` footer is added, and the doc is ARCHIVED to `_sys/docs/history/` with a MANIFEST pointer. → keep-living now: `backlog-5whys-consensus-2026-06-26`, `per-profile-health-b1-design` (AT-3), `standard-capability-consensus-2026-06-25` (AT-4/5); archive `terminal-health-misread-consensus` after its residuals fold into lifecycle/protocol + checks.
- **R2 — token-management split:** ContextGate/token-budget **POLICY** stays living in `lifecycle.md`; model/vendor/runtime **FACTS** move to JSON only (`model-registry.json` + `orchestration.json` + `routing-config.json`). No fact tables in docs except examples that defer to JSON. (A1 compliance.)
- **R3 — `_exceptions/README.md`:** KEEP as a tiny LIVING active-ambiguity register only; closed/stale items archived; must not become a second backlog.

## Alignment-gap resolutions → new invariants
- **GAP-1 (PRO-19 terminal=transport vs coordinator framing):** NEW invariant (owner `10-invariants.md` + `protocol.md`): *"The human-interface terminal may frame, route, relay, and summarize worker outputs, but MUST NOT perform substantive task analysis once a worker is selected. 'Coordinator'/'leader' is a task role assigned by protocol, not terminal authority."*
- **GAP-2 (path-dictionary integrity, req A2):** `20-architecture.md` owns the PathMap concept; `lifecycle.md` owns runtime path-integrity. NEEDS CODE: a `check_docs_mece.py --path-check` (or `test_path_dict.py`) statically verifying every `[PATH_DICT:x]` ref resolves to a valid key.
- **GAP-3 (command-contract + doc-status taxonomy homes):** terminal command contract → `protocol.md` + `user/manual.md`; doc-status taxonomy (`living / design / historical / superseded-by`) → `00-MANIFEST.md` + `ops/governance.md`.

## Doc → Config → Check mapping (sets up the upcoming directives/source/config alignment — A1 interface contracts)
| Living pillar | Config surface (SSOT) | Check / test surface |
|---|---|---|
| `protocol.md` | `protocol.json`, `orchestration.json` | `test_contracts.py`, consensus/keystone tests, PRO-19 guard test |
| `routing.md` | `orchestration.json`, `routing-config.json` | routing/dispatch tests, `resolve_peer_sys_dir` tests |
| `lifecycle.md` | `model-registry.json`, health/`protocol.json` thresholds | `test_health*`, context-gate tests, AT-1/AT-3 transaction tests |
| `learning.md` | `user-directives.md` (dynamic), proposals dir | directive-injection test, self-care/graduation e2e (AT-0 A-01) |
| `permissions.md` | `orchestration.json` DIR-002 flags | `test_peer_permissions.py` |
| `10-invariants.md` | `protocol.json`, `user-directives.md` | invariant/contract tests, docs-MECE checks (CHK-01..08) |
| `20-architecture.md` | path dictionary (req A2) | GAP-2 path-check (new) |

## ARCHIVE set → `_sys/docs/history/`
general (after merge): consensus, communication, tradeoffs, resource-governance, session, health, self-evolution, feedback-loop, directives, knowledge, token-management, master-plan, master-refactor-v5.
ops (dated/superseded): automatic-profile-routing-2026-06-20, consistency-audit-2026-06-24, full-audit-2026-06-26, peer-debate-2026-06-19, perf-benchmark-2026-06-19(+full), REMAINING_ACTIONS, remaining-items, TDD_PLAN_HUB_V42, terminal-health-misread-consensus (after fold-in).
specific: statusline_diag_update (after merge into logging + manual).

## Ordered execution (CHK-01 path-refs + CHK-07 MANIFEST gate every step)
1. **PRE-CHECK** — confirm CHK-01/CHK-07 tooling active.
2. **EXTRACT** — move model FACTS token-management → `model-registry.json`; pull durable conclusions from dated ops docs into living contracts BEFORE archiving.
3. **CONSOLIDATE** — build the 5 general pillars preserving EVERY normative rule (per-pillar peer delegation + rule-preservation diff vs sources); embed GAP-1/GAP-3 invariants.
4. **SLIM** — `specific/*` to delta-only; merge `statusline_diag_update` into logging + manual.
5. **ARCHIVE** — move deprecated/extracted docs to `_sys/docs/history/`.
6. **INDEX** — finalize `00-MANIFEST.md` (exhaustive index + path-dict rules + doc-status taxonomy) + `MOC.md` (short load-map).
7. **POST-CHECK** — CHK-01, CHK-07, new GAP-2 path-check.

**Rule-preservation guard:** no general-doc is archived until a diff confirms every MUST/MUST-NOT/INV/PRO rule it held now lives in a pillar. This is the doc-equivalent of the "do not weaken tests" rule.

**CONSENSUS one-liner:** collapse 16 general docs into 5 MECE pillars (+keep invariants/architecture), archive dated/superseded ops + merged sources to history, slim specific to deltas, make MANIFEST the sole exhaustive index, add 3 gap invariants, and wire a doc→config→check map so the next directives/source/config alignment has explicit contracts.
