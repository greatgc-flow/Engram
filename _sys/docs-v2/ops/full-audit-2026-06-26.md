> **Status:** HISTORICAL — findings resolved/incorporated via AT-0/AT-2/AT-6.

# Full Cross-Audit — Source/Config/Settings + Docs/Guidelines + Backlog (2026-06-26)

> **Method:** parallel MECE audit — ag.deepthink (source/config/settings) + cx (docs/guidelines/backlog), terminal-synthesized + spot-verified. AUDIT ONLY; nothing edited by the audit. Baseline = `consistency-audit-2026-06-24.md` + the 3 consensus docs; reports only NEW/remaining/inconsistent.
> **Roadmap (2026-06-26):** this audit's findings were 5-Whys-validated against root intent and folded into the phased roadmap `ops/backlog-5whys-consensus-2026-06-26.md` — A-01/A-02/A-03 → AT-0, config P2 → AT-2, A-05/A-06 + doc drift → AT-6. See that doc for KEEP/DROP/DEFER verdicts (several items DROPPED as gold-plating).

## P0/P1 — actionable correctness (verified)
| ID | Ref | Problem | Fix |
|---|---|---|---|
| **A-01** | `_sys/checks/self_care.py:145,154+` | Saturation + lesson-graduation call `proposal-add --title`, but the proposal handler reads `--subject` → self-improvement proposals likely created empty / silently fail. (verified: self_care uses `--title`; CLI proposal-add path uses `--subject`.) | Switch self_care to `--subject` (+ correct rationale/impact flags); add an end-to-end graduation test. |
| **A-02** | `_sys/ai/routing-config.json` (8 hits) | Router weights target `ag::default`, but `ag` only has `standard/effort/deepthink` profiles → R02/R04/R06 routing broken. | Repoint to `ag::standard`/`ag::effort`. |
| **A-03** | `_sys/ai/protocol.json` consensus | `ag` is in BOTH `r10_voters [cc,ag,cx]` AND `inactive_default_voters [ca,ag]` → contradicts active-voter state, risks quorum/unanimity miscalc. (verified.) | Remove `ag` from `inactive_default_voters`. |
| **A-04** | `_sys/tests/unit/test_hub_peer.py:27` | `resolve_peer_sys_dir` tested only with mock/absent file; corrupted-`peers.json` path + its `except Exception: pass` untested. | Add malformed-JSON test asserting defined failure behavior. |
| **A-05** | `_sys/docs-v2/general/session.md:69-82` | Session-reuse doc stale (gc-only, ag non-reusable) vs current `session_mode` config where cc/ag/cx reuse. | Rewrite around config-driven `session_mode` + gc suspension. |
| **A-06** | `_sys/docs-v2/general/knowledge.md:2,75-77` | Says injection PENDING but hub has lesson load/inject; mixes implemented vs open. | Split implemented injection from open triage/pack/approval. |

## P2 — hygiene / drift
- **Config dups (protocol.json):** duplicate `ag` keys in `workload.capability_registry` (2nd overwrites) + `fill_depth_multiplier`; `health.thresholds` keyed by install names (claude/gemini) not node_ids.
- **Stale paths:** settings.json grants legacy `cli/gemini.bat`; protocol.json `volatile_outputs` → non-existent `antigravity/config/bin/agentapi.bat`.
- **Error-swallowing `except Exception: pass`:** `config.py:130,141,152,163`, `hub_peer.py:101,127`, `hub.py:3076` — mask config/parse corruption; log instead.
- **Doc-status drift:** MANIFEST/MOC metadata stale (version/date/INV-PRO ranges/doc counts); MOC omits recent consensus docs; `00-MANIFEST.md:132` health-check "view all peer health" contradicts peer-status guidance (→ audit/maintenance); self-evolution Phase 1 + autonomous_maintenance marked pending but enabled; DocsSyncer apply-vs-dry-run conflict; token-management F-03 still names `o4-mini` (now gpt-5.4-mini/5.5); terminal-health + consistency-audit docs need "implemented" supersession footers (commits 56f576f/08d822e/99c7738/cd31543/55fe03f).
- **Residual:** stray `_sys/mock_peer/health.json` (benign test artifact); stale `_sys/ai/common/peer-rules.md` second rule-surface (now also holds the command contract — reconcile with the 2026-06-18 history merge).
- **Invariant enforcement gaps:** INV-05/06/07 + alert lifecycle (`communication.md:37-38`) are discipline-only, not hub-enforced (INV-26 wants programmatic).

## P3 — cosmetic
- `lifecycle_policy.json` `fallback_by_node` lists disabled `ca`; `routing.md:147` duplicate "## 6" heading; `session.md` 12KB vs 2KB handoff cap ambiguity; model-fact freshness (o3-pro GA, etc.); `ca` cleanup across configs.

## Deferred designs (already banked — implement later)
B1 per-profile health; standard-capability 7-phase (parsed `[ESCALATE]`, terminal relay frame, `HUB_PEER_TIER=selected_profile`); robust ask-termination cleanup (stale lock / peer-RED / orphan); timeout-unit cap; Continuity Score; SelfHealer (R:10); knowledge triage/pack; alert lifecycle.

## Pre-existing backlog ledgers (discovered, to reconcile)
`ops/remaining-items.md` + `ops/REMAINING_ACTIONS.md` carry ~20 items (T4 report-error ordering, CHK-06/07 fixtures, dispatcher/provisioner/registrar tests, hub decomposition Phase 2, PTY mocking in CI, async logging, CI/pre-commit automation). Many may be stale — reconcile against current code before actioning.

## Top-5 highest-value (both peers + terminal)
1. **A-01** fix self_care proposal CLI (`--title`→`--subject`) — unblocks the self-improvement loop (P0).
2. **A-02 + A-03** routing `ag::default` + voter-list contradiction — routing/consensus correctness (P1).
3. **A-05/A-06 + MANIFEST/MOC** docs-status reconciliation after this session's health/quorum commits (P1-P2).
4. **B1 per-profile health** implementation (highest-value deferred design).
5. **standard-capability** bounded escalation + terminal relay frame.
