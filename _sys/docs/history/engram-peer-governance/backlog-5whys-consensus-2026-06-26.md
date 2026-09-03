# Backlog 5-Whys + Ask-Transaction Roadmap — Consensus (2026-06-26)

> **Status:** ACTIVE ROADMAP (AT-0 through AT-5 implemented; AT-6 reconciliation active). Validates the full-audit backlog against ROOT intent via 5-Whys, DROPs gold-plating, and unifies the KEEP items under one phased **Ask Transaction** primitive. This is the authoritative roadmap; supersedes scattered backlog ledgers. Terminal relayed only.

## Root need (agreed)
NOT "finish every planned feature." A portable multi-peer AI dev environment where the **terminal stays thin** (routes, never ad-hoc-analyzes), **routing/health/consensus are predictable**, **failures become durable improvements** (not repeated manual archaeology), and the user can **delegate real work and trust the result**. Every item is justified against this; items that don't serve it are dropped.

## Verdicts (5-Whys distilled)

### KEEP — direct root-leverage
A-01 self-care CLI (`--title`→`--subject`; broken self-improvement loop), A-02 routing `ag::default`→valid profile, A-03 `ag` double-voter contradiction, `HUB_PEER_TIER` correctness, ask-termination cleanup (stale lock / orphan / RED), timeout-unit cap, T4 outcome ordering, PTY mocking (ag active — needed by AT-1/4/5).

### KEEP-BUT-IMPROVE — consolidate, don't point-fix
- A-04..A-06 + manifest/MOC/doc-status drift → ONE docs-status reconciliation pass (AT-6).
- config dup-keys / stale paths (gemini.bat, agentapi.bat) / invalid refs / active-inactive voter overlap → ONE strict config validator (AT-2).
- `except Exception: pass` in normative config/resolver → ONE strict-load primitive (AT-2). Tolerate silence only for non-normative telemetry.
- B1 per-profile health → implemented as AT-3 (visible fallback, no silent tier degradation).
- standard-capability → AT-4 (relay frame + classifier) then AT-5 (bounded `[ESCALATE]`).
- knowledge loop → minimal active-lessons injection + graduation; defer pack compilation.
- self-care → observe → validate → propose only (no autonomous mutation).

### DROP — gold-plating / trust-risk / obsoleted (both peers)
web/usage/model-drift dashboards, async logging, dynamic reasoning budget, cross-peer/multi-turn failover as router default, `health-reset` (use peer-recover), build_cmd changelog, 5-Whys customization, rollback_swap housekeeping, **Continuity Score** (hard windows adequate), **SelfHealer autonomous remediation** (trust risk — failures must hard-stop + surface), **context-pruning "missing prune"** (obsolete: `check_and_prune()` exists).

### DEFER — serves root, low ROI now (explicit trigger)
context pruning behavior (trigger: first live 429), dispatcher/provisioner/registrar/launcher/relocator/scrubber tests (trigger: touch those modules), log rotation (trigger: logs near cap), hub decomposition Phase 2 (trigger: functional work in health/send), cost tracking (trigger: budget incident / paid expansion), Linux/Mac (trigger: target platform changes), adapter authoring guide (trigger: new provider), CHK-08 traceability gate (trigger: traceability map actively maintained).

## Unifying primitive: **Ask Transaction**
One owner for the lifecycle of a single routed ask (AFTER target/profile resolution): health gate → context gate → spawn (correct env/tier) → lease open/renew/close → transactional outcome classification → `finally`: release lease, reap process tree, write final health, surface `[HUB:FALLBACK]`.
**Out of scope:** profile-scoring policy, cross-peer failover, adapter CLI syntax, consensus voting, docs reconciliation, autonomous remediation.
**Fold-in:** implements (does NOT replace) `per-profile-health-b1-design.md` (=AT-3 spec); splits `standard-capability-consensus-2026-06-25.md` into AT-4/AT-5; `terminal-health-misread-consensus` already landed (residual → AT-2/AT-6); `full-audit-2026-06-26.md` feeds AT-0/AT-2/AT-6.

## Phased plan (ordered; each slice = subprocess+PTY tests + DIR-003 contract test on signature change)
| Slice | Scope | Anchor | Test gate |
|---|---|---|---|
| **AT-0** correctness preflight | A-01 self-care CLI, A-02 routing, A-03 voter, HUB_PEER_TIER | full-audit A-01/02/03 + std-cap | config validator + self-care proposal e2e + env-tier unit |
| **AT-1** outcome-finally guard | wrap subprocess+PTY ask in try/finally: lease close, process-tree reap, final health write, no swallowed T4 | b1 cleanup follow-up + remaining-items T4 | subprocess-failure + PTY-timeout-kill + T4-ordering |
| **AT-2** strict config validator + strict-load | dup keys, invalid peer/profile refs, active/inactive voter overlap, stale routing refs, malformed peers.json | full-audit P2 + A-04 | validator fixtures (dup/invalid-ref/overlap/malformed) |
| **AT-3** per-profile health | B1 inside Ask Transaction; profile-scoped vs peer-wide; visible same-peer downward | per-profile-health-b1-design.md | B1 fallback / peer-wide-drop / aggregation / `[HUB:FALLBACK]` |
| **AT-4** standard terminal slice | relay frame + explicit-profile immutability + classifier boundary (NO `[ESCALATE]` yet) | standard-capability-consensus | subprocess+PTY routing-frame + fail-visible + no-terminal-analysis |
| **AT-5** runtime escalation | bounded parsed-output `[ESCALATE]` after AT-4 | standard-capability-consensus | parsed-marker subprocess+PTY + depth ceiling + final-output-only + no failure-promotion |
| **AT-6** docs-status reconciliation | supersede stale audit/consensus/session/knowledge docs + MOC/manifest | full-audit A-05/A-06 + doc drift | docs-MECE: manifest/MOC status, canonical peer-status, implemented/pending labels |

## Do-first (top-3, agreed)
1. **AT-0** — broken route IDs + contradictory voter state + broken self-care proposal directly undercut trustworthy delegation. Highest root-leverage, smallest blast radius.
2. **AT-1** — reliability win (no stale lock / orphan / lying health) WITHOUT rewriting action_ask.
3. **AT-2** — prevents recurrence of the A-02/A-03 config-drift class.

**CONSENSUS one-liner:** a phased **Ask Transaction** reliability primitive — start with the routing/consensus/self-care correctness trio, then finally-cleanup, strict config validation, B1 per-profile health, terminal relay/classifier, and only later bounded runtime `[ESCALATE]`; drop autonomous SelfHealer + Continuity Score from the active backlog.
