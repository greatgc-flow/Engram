# Proposal: Disposition of `_sys/docs-v2/**` Post-Separation

> **Date:** 2026-09-03  
> **Status:** PROPOSAL ONLY (Design / Analysis — no files moved or deleted)  
> **Context:** Engram v3.0.0 / peerhub v0.1.8 separation completion backlog  
> **Target Repo:** `D:\Engram&Peerhub\engram-main-worktree` (branch `main`)  
> **Reference Sessions:** `2026-09-03_pre-commit-hook-blindspot-and-docsv2-gap.md`, `2026-09-03_separation-completion-backlog.md`, `2026-09-02_engram-diet-plan-v8.md`

---

## 1. Executive Summary & Core Findings

1. **Total Population:** Exactly **47 files** (65,584 words / 8,438 lines) across `_exceptions/`, `general/`, `ops/` (including `ops/cli-baselines/`), `specific/`, `user/`, and root docs-v2.
2. **KEEP-AS-IS = ZERO files (0%):**
   Every single file in `_sys/docs-v2/**` contains AI-governance framing, references to deleted `hub.py` / `_sys/ai/` structures, or pre-separation assumptions. Even the two closest candidates — `user/manual.md` (which covers `INSTALL.bat`, `register.bat`, etc.) and `ops/conventions.md` (which covers `.bat` / UTF-8 rules) — are heavily interwoven with retired concepts (`collab_rate`, `hub.py`, `consensus-propose`, Axis bat scripts, token budgets). Engram's actual clean generic documentation already lives in the post-separation root `README.md`.
3. **MIGRATE-TO-PEERHUB = 8 files (11 files if including baseline text dumps):**
   These files contain hard-won, empirical, execution-tested operational knowledge about AI CLIs (`claude.cmd`, `codex.cmd`, `agy.exe`), JSON output formats, PTY requirements, flag quirks, breaking changes across versions, and adapter-level permission profiles. Because peerhub contains the actual runtime adapters (`RealClaudeAdapter`, `RealCodexAdapter`, `RealAgyAdapter`), this content belongs in peerhub's living documentation tree (`docs/adapters/` and `docs/reference/`).
4. **ARCHIVE = 36 files (39 files if including baseline text dumps):**
   These files represent significant historical and design-record value for the multi-peer collaboration architecture (2026-06 through 2026-08). They match the repository's established archive convention: `_sys/docs/history/engram-peer-governance/` (which already houses 15 pre-separation governance documents).
5. **DELETE = 0 files:**
   No files are recommended for immediate unrecoverable deletion. Even superseded plans (`ops/endgame-general-specific-plan-2026-06-28.md`) provide essential audit provenance for how design decisions converged.

---

## 2. Direct Code Dependency Audit (Live Engram Code References)

Does ANY file in `docs-v2` get referenced by live, still-running Engram code?

**YES — with HARD failure dependencies if `docs-v2` were removed without test/check updates:**

| File / Component | Type | Specific `docs-v2` Target | Impact if Target Disappears |
|---|---|---|---|
| `_sys/tests/unit/test_doc_consistency.py:24-32` | **HARD TEST FAILURE** | `_sys/docs-v2/00-MANIFEST.md`<br>`_sys/docs-v2/10-invariants.md` | `test_ssot_docs_exist` explicitly loops over `mandatory_docs_v2 = ["00-MANIFEST.md", "10-invariants.md"]` and asserts `.exists()`. **Pytest fails immediately.** |
| `_sys/tests/unit/test_doc_consistency.py:79-84` | **HARD TEST FAILURE** | `_sys/docs-v2/10-invariants.md` | `test_pro19_does_not_claim_unimplemented_enforcement` calls `.read_text()` on `10-invariants.md` and splits on `### Transport-Role Enforcement (PRO-19)`. **Raises `FileNotFoundError`.** |
| `_sys/checks/saturation_scan.py:121-137` | **HARD CHECK FAILURE (HIGH)** | `_sys/docs-v2/10-invariants.md` | `_find_invariants_file()` searches `sys_root / "docs-v2" / "10-invariants.md"`. If absent, emits `Finding("HIGH", "invariants", "10-invariants.md", "Invariants file not found in known locations")`. Runs under pre-commit consistency checks. |
| `_sys/checks/check_docs_mece.py` (CHK-01/CHK-02 wired into the pre-commit hook; CHK-07 at lines 407-430) | **PRE-COMMIT HOOK, PARTIALLY SOFT** | `_DOCS_DIR = _sys/docs-v2`<br>`00-MANIFEST.md` | **Terminal correction (2026-09-03): the original draft here cited a non-existent "CHK-06 emits a T1 finding: '00-MANIFEST.md not found in active view'" — verified against the real file: no such string exists anywhere in check_docs_mece.py, and CHK-06 is actually "Proposal TTL," unrelated to docs-v2. The real, closest check is CHK-07 ("Orphaned files," line 407), which does the OPPOSITE of the original claim: `if not active_view.exists(manifest_rel): return findings` — it silently returns zero findings when 00-MANIFEST.md is absent, it does not fail or emit anything. CHK-01/CHK-02 (the two checks the pre-commit hook actually runs) both operate over the whole worktree, not docs-v2 specifically, and were independently confirmed earlier this session (commit `92b9ced`'s notice-banner work) to still pass with 0 findings even after docs-v2's disposition changes -- there is no hard pre-commit dependency on docs-v2 existing.** |
| `CONVENTION.md:2-9` | **ROOT POINTER** | `_sys/docs-v2/ops/conventions.md`<br>`_sys/docs-v2/10-invariants.md` | Stated SSOT pointer for language and script conventions. Points to non-existent location if moved. |
| `_sys/checks/check_encoding.py:42` | Soft reference | `_sys/docs-v2/**/*.md` | Included in `CHECK_SPECS`. Glob simply returns empty if directory is absent. |
| `_sys/tests/unit/test_budget_single_authority.py:3` | Docstring / error message | `_sys/docs-v2/ops/engram-refactor-blueprint-2026-07-20.md` | String mention only in failure message and docstring; does not read file from disk. |

> [!IMPORTANT]
> Any future execution pass that moves or removes `_sys/docs-v2/**` MUST be accompanied by updates to `test_doc_consistency.py`, `saturation_scan.py`, `check_docs_mece.py` (and the git pre-commit hook), and `CONVENTION.md`.

---

## 3. Exhaustive Classification Table (All 47 Files)

### Group A: Living CLI / Adapter Operational Knowledge (MIGRATE-TO-PEERHUB)
*These 8 files (plus 3 baseline captures) contain empirical, verified runtime behaviors of the AI CLI tools and belong in peerhub's living documentation.*

| File | Lines | Words | Proposed Fate | Target in peerhub | Verified Citation & Justification |
|---|---:|---:|---|---|---|
| `ops/peer-cli-reference.md` | 510 | 4,407 | **MIGRATE-TO-PEERHUB** | `docs/adapters/peer-cli-reference.md` | Line 32-33: `"Used as the parse target for peerhub's RealClaudeAdapter (peerhub/adapters/claude_adapter.py)"`. Documents exact `--output-format json` schemas, `--max-budget-usd`, and Codex stdin EOF quirks. |
| `ops/cli-update-checkpoints-agy.md` | 222 | 1,516 | **MIGRATE-TO-PEERHUB** | `docs/adapters/checkpoints/agy.md` | Lines 20-31: Documents agy 1.1.5 breaking change rejecting Title-Case model strings (`"Claude Opus 4.6 (Thinking)"`) in favor of canonical slugs (`claude-opus-4-6-thinking`). |
| `ops/cli-update-checkpoints-cc.md` | 175 | 1,192 | **MIGRATE-TO-PEERHUB** | `docs/adapters/checkpoints/cc.md` | Lines 19-35: Post-update checklist for Claude Code CLI; verifies `--output-format json` schema, `--json-schema` structured outputs, and budget halts. |
| `ops/cli-update-checkpoints-codex.md` | 591 | 2,609 | **MIGRATE-TO-PEERHUB** | `docs/adapters/checkpoints/codex.md` | Lines 35-55: Documents Codex 0.145.0 context window corrections (272k tokens for Sol/Terra/Luna) and `codex exec resume -c sandbox="workspace-write"` override syntax. |
| `specific/ag.md` | 61 | 790 | **MIGRATE-TO-PEERHUB** | `docs/adapters/ag.md` | Lines 8-12, 23-29: Windows Console API PTY requirement, `--print-timeout 60m`, and session reuse capturing newest `conversations/<id>.db` stem for `--conversation`. |
| `specific/cc.md` | 53 | 343 | **MIGRATE-TO-PEERHUB** | `docs/adapters/cc.md` | Lines 22-34: `claude -p {query} --dangerously-skip-permissions`, runtime profile specs (`cc.standard` Haiku, `cc.effort` Sonnet, `cc.deepthink` Opus, `cc.fable`). |
| `specific/cx.md` | 99 | 458 | **MIGRATE-TO-PEERHUB** | `docs/adapters/cx.md` | Lines 31, 49-52, 67: `codex exec -s workspace-write --json`, runtime profile reasoning levels (`gpt-5.6-luna/low`, `terra/high`, `sol/xhigh`), and `-c sandbox="workspace-write"` resume syntax. |
| `general/permissions.md` | 130 | 858 | **MIGRATE-TO-PEERHUB** | `docs/design/peer-permissions.md` | Line 48: Notes peer asks moved to peerhub package; lines 96-113: empirical test refuting agy `--sandbox` filesystem confinement and defining non-interactive bounds for adapters. |
| `ops/cli-baselines/ag-1.1.5-help.txt` | 81 | 354 | **MIGRATE-TO-PEERHUB** (or ARCHIVE) | `tests/fixtures/cli-baselines/ag.txt` | Verbatim `agy.exe --help` capture; referenced by `peer-cli-reference.md:13` as baseline for drift detection. |
| `ops/cli-baselines/cc-2.1.216-help.txt` | 230 | 1,182 | **MIGRATE-TO-PEERHUB** (or ARCHIVE) | `tests/fixtures/cli-baselines/cc.txt` | Verbatim `claude.cmd --help` capture; referenced by `peer-cli-reference.md:13`. |
| `ops/cli-baselines/codex-0.144.6-help.txt` | 998 | 4,363 | **MIGRATE-TO-PEERHUB** (or ARCHIVE) | `tests/fixtures/cli-baselines/codex.txt` | Verbatim `codex.cmd --help` capture; referenced by `peer-cli-reference.md:13`. |

---

### Group B: Core Pre-Separation Invariants, Architecture & Entrypoints (ARCHIVE)
*Foundational specs from the pre-separation era. Move to `_sys/docs/history/engram-peer-governance/`.*

| File | Lines | Words | Proposed Fate | Archive Path | Verified Citation & Justification |
|---|---:|---:|---|---|---|
| `10-invariants.md` | 131 | 1,618 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/10-invariants.md` | Lines 12-15 (INV-01~04 consensus & Final Call), lines 27-31 (INV-08~11 health checks & health.json), line 119 (PRO-19 transport role). All describe retired multi-peer governance. |
| `20-architecture.md` | 194 | 1,236 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/20-architecture.md` | Lines 23-36 (Four-Layer Physical Structure / PathMap), lines 87-109 (pre-separation P:\ layout), lines 151-183 (Brain-inspired layers: Amygdala, Prefrontal Cortex, Neocortex). |
| `00-MANIFEST.md` | 156 | 1,910 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/00-MANIFEST.md` | Lines 7-15 (pre-separation notice), lines 48-93 (living set taxonomy table indexing hub.py routing/governance), lines 144-150 (notices that protocol.json etc. were removed). |
| `MOC.md` | 123 | 990 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/MOC.md` | Lines 7-15 (pre-separation notice), lines 32-37 (lazy load map of 5 pillars including consensus, routing, ContextGate). |
| `_exceptions/README.md` | 77 | 708 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/_exceptions-README.md` | Lines 31-66 (resolutions for EDGE-01 through EDGE-05, tracking active-lessons.jsonl graduation and pre-separation edge cases). |
| `user/requirements.md` | 270 | 2,163 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/user-requirements-2026-06-18.md` | Lines 54-100 (Requirement B: Peer equality, unanimous consensus, health monitoring, minimum permissions, error propagation). |
| `user/manual.md` | 272 | 1,772 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/user-manual-pre-separation.md` | Lines 160-263 (`hub`, `diag`, `collab_rate`, `consensus-propose`, token load balancing). Generic install content (lines 1-159) is already preserved in root `README.md`. |

---

### Group C: Pre-Separation General Pillars & Tombstones (ARCHIVE)
*Pillar documents from the general/ hierarchy describing multi-peer routing, lifecycle, and disabled peers.*

| File | Lines | Words | Proposed Fate | Archive Path | Verified Citation & Justification |
|---|---:|---:|---|---|---|
| `general/lifecycle.md` | 418 | 2,334 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/general-lifecycle.md` | Lines 8-26 (Session decision tree with `hub.py init-session`, `handoff.md`), lines 30-37 (Startup contract INV-05), lines 43-53 (6 rolling sections of handoff.md). |
| `general/routing.md` | 342 | 2,020 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/general-routing.md` | Line 52: Explicit note that hub.py and orchestration.json were removed; lines 86-98 (election score v2 with Quota Margin and AP-20). |
| `specific/gc.md` | 9 | 62 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/specific-gc.md` | Lines 5-9: `"The gc peer (Gemini CLI) is officially suspended and disabled... All gemini routing is now directed to the ag (Antigravity) peer."` |

---

### Group D: Operational Governance, Standards & Communication Schemas (ARCHIVE)
*Operational rules for multi-peer debate, logging, and schemas.*

| File | Lines | Words | Proposed Fate | Archive Path | Verified Citation & Justification |
|---|---:|---:|---|---|---|
| `ops/conventions.md` | 342 | 2,247 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/ops-conventions.md` | Lines 172-186 (§3-4-B Hub script protection for Axis bat files), lines 202-216 (Axis token budgets), lines 218-221 (Collaboration protocol retired). *Action: Extract clean .bat rules to root `CONVENTION.md`.* |
| `ops/anti-patterns.md` | 120 | 899 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/ops-anti-patterns.md` | Lines 9-24 (AP-01 Conditional Agreement, AP-02 Silent Abstain, AP-04 Premature FINALIZED), lines 49-60 (AP-09 Solo Execution without consensus, AP-10 Direct state.json write). |
| `ops/audit-checklist.md` | 151 | 1,647 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/ops-audit-checklist.md` | Lines 38-49 (Domain C: Peer Collaboration, `routing-config.json`, `hub.py ask-all`), lines 58-60 (Domain D: `hub_api.json` and hub.py contracts). |
| `ops/debate.md` | 115 | 576 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/ops-debate.md` | Lines 9-15 (Proposer, Challenger, Synthesizer, Active Coordinator roles), lines 21-26 (`hub.py consensus-propose`, FULL vs ABBREVIATED debate tiers). |
| `ops/templates.md` | 90 | 326 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/ops-templates.md` | Lines 11-18 (`[GOAL_FRAME]`), lines 25-34 (`[CLOSURE_MANIFEST]`), lines 54-60 (`[DEBATE_ROUND]`). |
| `ops/logging.md` | 413 | 1,986 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/ops-logging.md` | Lines 27-38 (`ipc-log.jsonl`, `console-log.jsonl`, `cost-log.jsonl`, `error-log.jsonl`, `reasoning-log.jsonl` written by `hub.py`). |
| `ops/hub-mutation-broker.md` | 104 | 634 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/ops-hub-mutation-broker.md` | Lines 28-35 (Sandbox peer -> broker-submit -> broker-drain -> atomic os.replace commit for `.ai` state). Corresponds to waived LEGACY_CATALOG action. |
| `ops/schemas.md` | 103 | 392 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/ops-schemas.md` | Lines 15-41 (`orchestration.json` schema), lines 47-60 (`memory` vs `session_mode` semantics). |
| `ops/skills.md` | 96 | 487 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/ops-skills.md` | Lines 3, 23-30 (Unimplemented skill system in `hub.py`: `consensus-vote.md`, `context-fill.md`, `lesson-add.md`). |

---

### Group E: Dated Design, Consensus, and Audit Records (ARCHIVE)
*Point-in-time technical records of multi-peer architectural debates and consensus rounds (June-July 2026).*

| File | Lines | Words | Proposed Fate | Archive Path | Verified Citation & Justification |
|---|---:|---:|---|---|---|
| `ops/backlog-5whys-consensus-2026-06-26.md` | 49 | 785 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/backlog-5whys-consensus-2026-06-26.md` | Lines 10-27 (Verdicts for Ask Transaction AT-0..AT-6 roadmap). |
| `ops/endgame-general-specific-plan-2026-06-28.md` | 235 | 1,691 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/endgame-general-specific-plan-2026-06-28.md` | Lines 28-34 (Three-Lane Separation: Directives, Config, Source); marked superseded in 00-MANIFEST:70. |
| `ops/status-consolidation-2026-07-08.md` | 61 | 455 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/status-consolidation-2026-07-08.md` | Lines 8-19 (Table of shipped commits: terminal tier-floor, CHK-ENC, telemetry-config.json). |
| `ops/capability-leveling.md` | 284 | 2,422 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/capability-leveling-framework-2026-07-13.md` | Lines 14-22 (Vector capability leveling: evidence-qualified per axis, bulk_fitness vs arbiter_fitness). |
| `ops/intelligence-scores.md` | 279 | 2,479 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/intelligence-scores-2026-07-13.md` | Lines 9-19 (Update 2026-07-19: arbiter_models expansion to `["cc.fable", "cc.deepthink", "cx.deepthink"]`). |
| `ops/profile-policy.md` | 182 | 1,472 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/profile-policy-2026-07-13.md` | Lines 16-23 (5 dimensions: Taxonomy, Capability, Quota economics, Load balancing, Terminal minimization). |
| `ops/profile-policy-decisions.md` | 230 | 1,765 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/profile-policy-decisions-2026-07-13.md` | Lines 12-25 (P0-1 bulk exclusion bypass and P0-2 terminal exclusion mismatch in `hub.py resolve_auto_target`). |
| `ops/hard-benchmark-decisions.md` | 190 | 1,572 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/hard-benchmark-decisions-2026-07-14.md` | Lines 12-25 (Decision to decouple D1 from measured reasoning edge because Sol/Opus/Gemini tied at ceiling 100/100). |
| `ops/quota-balance-decisions.md` | 114 | 873 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/quota-balance-decisions-2026-07-15.md` | Lines 12-25 (Diagnosis that load balancer was never called because terminal used explicit `--to cx`/`--to ag`). |
| `ops/statusline-quota-display-handoff-2026-07-15.md` | 119 | 700 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/statusline-quota-display-handoff-2026-07-15.md` | Lines 7-18 (Statusline quota display format: used percentage only, never fabricate F-7D). |
| `ops/closure-review-2026-07-17.md` | 38 | 967 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/closure-review-2026-07-17.md` | Lines 18-25 (Findings 1-6: INV-03 voter filtering violation, ungated governed-mutation bypass, directive misclassification). |
| `ops/closure-review-2026-07-17-round2.md` | 56 | 1,764 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/closure-review-2026-07-17-round2.md` | Lines 16-19 (ag zombie diagnosis and 300s post-progress timeout fix in `_effective_zombie_timeout_sec`), lines 24-25 (discovery of 41GB orphaned node/codex process leak). |
| `ops/zombie-deep-dive-2026-07-18.md` | 55 | 1,070 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/zombie-deep-dive-2026-07-18.md` | Lines 18-23 (Finding 2: single-use IPC regex bug where 4-character tag requirement failed to delete 655 files). |
| `ops/external-server-ization-proposal-review-2026-07-19.md` | 27 | 650 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/external-server-ization-proposal-review-2026-07-19.md` | Lines 3-4, 13-16 (Unanimous rejection of third-party proposal to server-ize Engram into a multi-tenant backend). |
| `ops/phase1-docs-audit-open-items-2026-07-22.md` | 84 | 696 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/phase1-docs-audit-open-items-2026-07-22.md` | Lines 10-19 (Open item 1: `check_docs_mece.py` only validates structure, not semantic truth). |
| `ops/phase2-arch-general-specific-2026-07-22.md` | 734 | 20,419 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/phase2-arch-general-specific-2026-07-22.md` | Lines 1-3 (Massive 734-line architectural design doc; §14 demoted per T82 re-scope). |
| `ops/residual-backlog-and-packaging-precheck-2026-07-26.md` | 94 | 1,180 | **ARCHIVE** | `_sys/docs/history/engram-peer-governance/residual-backlog-and-packaging-precheck-2026-07-26.md` | Lines 15-28 (Sweep of backlog.json: closing T85 phantom session and T86 terminal-handoff detection). |

---

## 4. Recommended Step-by-Step Implementation Sequence (For a Future Round)

When the peers and operator ratify this disposition, the mechanical execution should follow these 4 atomic phases:

### Phase 1: Port Living Adapter Docs to Peerhub
1. Copy the 8 living adapter operational docs (`ops/peer-cli-reference.md`, `ops/cli-update-checkpoints-*.md`, `specific/ag.md`, `specific/cc.md`, `specific/cx.md`, `general/permissions.md`) into peerhub's `docs/adapters/` and `docs/reference/`.
2. (Optional) Copy `ops/cli-baselines/*.txt` into peerhub's test fixtures.

### Phase 2: Update Engram Root Conventions
1. Extract the clean, generic `.bat` and PowerShell coding conventions from `ops/conventions.md` (UTF-8 no BOM, no Korean strings in `.bat`, `:LOG` patterns, PATH handling, parenthesis bug prevention, `local.config.bat`) and paste them directly into root `CONVENTION.md`.
2. Remove the pointer line pointing to `_sys/docs-v2/ops/conventions.md`.

### Phase 3: Update Engram Tests & Checks
1. In `_sys/tests/unit/test_doc_consistency.py`:
   - Remove `00-MANIFEST.md` and `10-invariants.md` from `mandatory_docs_v2` (or retire the test method if `docs-v2` is completely archived).
   - Remove `test_pro19_does_not_claim_unimplemented_enforcement` (which reads `10-invariants.md`).
2. In `_sys/checks/saturation_scan.py`:
   - Decouple `_find_invariants_file()` so it points to `CONVENTION.md` or gracefully returns without emitting a HIGH finding when `10-invariants.md` is in the history archive.
3. In `_sys/checks/check_docs_mece.py`:
   - Retire the script or adapt it if a post-separation docs tree is introduced.
   - Remove the `check_docs_mece.py` stanza from the shared git pre-commit hook (`.git/hooks/pre-commit`).

### Phase 4: Move `docs-v2/**` to History Archive
1. Move the 36 (or 39) historical files from `_sys/docs-v2/**` into `_sys/docs/history/engram-peer-governance/`.
2. Update `_sys/docs/history/engram-peer-governance/README.md` to note that the remaining `docs-v2` historical artifacts were archived on 2026-09-03, completing the separation.
3. Remove the now-empty `_sys/docs-v2/` directory tree.
