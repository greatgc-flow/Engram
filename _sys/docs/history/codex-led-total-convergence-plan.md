# Codex-Led Total Convergence Plan

Status: COMPLETE
Owner: cx
Created: 2026-06-12
Completed: 2026-06-13

## User Directive

The user requested that Codex with sandbox off lead the remaining work to completion, with all peers participating according to roles. The work must be planned first, communicated to all peers, decided by unanimous agreement where decisions are needed, then implemented, tested, cross-reviewed, committed, and pushed without asking the user for further decisions.

## Operating Rules

- Collabo_RATE is 10: governed decisions require unanimous agreement from active peers.
- Peer participation target for this run: cc, gc, cx.
- ca and ag are standing-inactive peers. They must remain excluded from default routing, consensus, fallback, and peer asks unless the user explicitly names `ca` or `ag` for re-enable.
- cx is active coordinator and implementation lead for this run.
- cc provides architecture and final consistency review.
- cc provides independent verification and regression/risk review while ca is inactive.
- gc provides document and large-context consistency review.
- cx handles shell/Windows workflow checks while ag is inactive.
- Use file references and compact routing envelopes to avoid large repeated messages.
- Use open questions for peer review. Do not bias peers toward a preferred answer.
- Use tags while drafting: ADDED, CHANGED, DELETED, OPEN. Remove draft tags before finalization.
- Prefer no-code, composable, General-Specific, JSON-configured structure.
- Move hardcoded values, ranges, kinds, paths, env vars, and routing bindings into JSON where practical and coherent.
- Preserve unrelated user changes. Do not destructively clean the worktree.

## Scope

### 1. Finish Residual Work

- Reconcile interrupted leader transfer state and set cx as active coordinator.
- Re-enable ca/ag for this total-convergence run unless a runtime health gate blocks them.
- Complete the prior peer-status/model-routing/leader-continuity work.
- Ensure the handoff, task registry, state, and plans reflect the latest authority and work status.

### 2. MECE Consistency Update

- Inventory all changed and untracked source, docs, JSON config, generated artifacts, and runtime state.
- Classify each file as source, durable config, generated artifact, runtime state, plan/archive, or transient.
- Resolve contradictions across:
  - `PROTOCOL.md`
  - `_sys/ai/protocol.json`
  - `_sys/ai/orchestration.json`
  - `_sys/ai/lifecycle_policy.json`
  - `_sys/ai/model_profiles.json`
  - `_sys/ai/status_checks.json`
  - `_sys/ai/collaboration_loop_bindings.json`
  - `_sys/docs/*`
  - root entrypoints and generated dispatch files
  - unit tests
- Fix bugs discovered during consistency review.

### 3. Scattered Request Consolidation

- Review the known request/reference files:
  - `E:\workspace\plans\mece-r10-round1.md`
  - `E:\workspace\DESIGN_REVIEW_MULTI_PEER.md`
  - `E:\workspace\plans\r10-model-routing-consensus.md`
  - `E:\plans\mece-peer-status-and-continuity.md`
- Search for other plan/design/request files under `plans/`, `workspace/`, and `_sys/docs/`.
- For each request:
  - mark implemented if already reflected or superseded;
  - implement if still relevant;
  - ignore if stale or superseded by a higher-compatible design;
  - remove or archive unnecessary documents only when clearly redundant and not needed as audit history.

### 4. Validation

- Validate JSON.
- Run unit tests.
- Run targeted health/dependency/portability checks when relevant and available.
- Run peer cross-review after implementation.
- Repeat review -> fix -> validate until no peer has blocking objections.

### 5. Git Finalization

- Inspect full diff and untracked files.
- Exclude transient/runtime-only files unless intentionally source-controlled.
- Stage only intended files.
- Commit with a scoped Conventional Commit message.
- Push to `origin`.
- If repository/remote supports it and branch policy requires it, open a draft PR; otherwise push the committed branch directly as requested.

## Initial Work Breakdown

### Phase 0: Coordination Bootstrap

- [DONE] Set cx as active coordinator (this session).
- [DONE] Keep ca/ag inactive indefinitely unless explicitly named by the user.
- [DONE] Plan distributed to gc and cx via hub.py ask.

### Phase 1: Inventory

- [DONE] gc performed §2 consistency review: 3 P0, 5 P1, 3 P2 findings.
- [DONE] cx performed §3 implementation review: virtual nodes, model_profiles wiring, profile-validate.

### Phase 2: Peer Review Round 1

- [DONE] gc reviewed all AI config files vs r10 consensus decisions.
- [DONE] cx reviewed hub.py implementation scope and risks.
- [DONE] gc performed §4 final cross-review (ACK, 1 P1 fix applied).

### Phase 3: Implementation (commits a0485a9, 0d2440e, 8844d52, d97acdb)

- [DONE] protocol.json: semi_governed_hub_actions, exempt_actions, provenance_logs.
- [DONE] lifecycle_policy.json: migration_target updated.
- [DONE] status_checks.json: promoted to runtime_active.
- [DONE] collaboration_loop_bindings.json: room hardcoding removed, promoted to runtime_active.
- [DONE] model_profiles.json: promoted to runtime_active.
- [DONE] orchestration.json: cc-deep, gc-plan virtual nodes added.
- [DONE] hub.py: declarative peer-status, semi_governed guard, ask provenance, profile-validate.
- [DONE] gemini-status.bat: GEMINI_DIR collision fix.
- [DONE] collaboration-model-routing.md: marked SUPERSEDED.

### Phase 4: Cross-Validation Loop

- [DONE] JSON validation: all files valid.
- [DONE] hub.py syntax check: OK.
- [DONE] peer-status functional test: all 4 peers show version.
- [DONE] profile-validate: 5 nodes checked, OK.
- [DONE] gc §4 cross-review: ACK with 1 P1 fix applied.

### Phase 5: Commit and Push

- [DONE] 4 commits pushed to origin/main (68ae766..d97acdb).

## Explicit Non-Goals For This Pass

- Do not start detailed implementation of `_sys/docs/TAXONOMY_v10.md`; only ensure current work does not conflict with the future taxonomy implementation step.
- Do not rewrite the whole architecture if a smaller consistency fix completes the requested convergence.
- Do not remove audit documents solely because they are old; remove only duplicated or superseded documents that no longer serve traceability.
