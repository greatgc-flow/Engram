# Runtime Drift Reconciliation (RDR) — Pre-TDD Specification

> Status: **design** — R:10 unanimous (`r-ff91`, cc + ag + cx, 2026-07-27). This is a pre-TDD contract: it authorizes neither production code nor test code.
>
> Scope: safely discover, classify, plan, approve, apply, and prove reconciliation of CLI/runtime drift affecting declared peer profiles, model/effort operands, quota semantics, versions, and the configuration and documentation which represent them.

---

## 1. Decision and boundaries

RDR extends the repository's existing mechanisms; it does **not** introduce a parallel service, a new configuration store, or a second provider-argument registry.

| Existing owner | Current responsibility | RDR extension |
|---|---|---|
| `_sys/checks/check_cli_reality.py` | Binary boundary, version/catalog probes, positive canaries, `.ai/cli-reality-observed.json`, reconciliation report | Persist typed observation receipts and derive a drift manifest from its existing observed/declaration boundary. |
| `_sys/checks/check_cli_canary.py` | Profile canary execution and observed capture | Receive provider-owned, minimal safe observation plans and return structured proof/UNKNOWN rather than turning a successful operand into a selected-backend claim. |
| `_sys/checks/check_tool_updates.py` | Update discovery, archive proposal, one-file `runtimes.json` apply/backup | Produce a multi-target change plan and participate in its governed transaction; its existing one-file proposal remains compatible during migration. |
| `_sys/core/hub.py` | Freshness sweep, consensus, broker/CAS write primitives, profile validation, dispatch and handoff | Own R:10 binding, dispatch fence, plan authorization, transaction journal/recovery, and post-apply acceptance. |
| `_sys/core/hub_peer.py` | Normalized nodes and provider adapter command construction | Preserve the exact effective profile tuple and expose adapter-owned observation hooks; it must not infer provider semantics. |
| `_sys/ai/*.json` | Declared policy/configuration SSOT | Remain the only declarations changed by an approved plan. |
| `ops/cli-update-checkpoints-*.md` and `ops/peer-cli-reference.md` | Human operational notes/reference | Remain documentation, never a machine source of runtime truth. |

RDR is not a package manager, scheduler, automatic account-management feature, generic provider abstraction, or permission to update a provider binary. External binary installation is a separate effect: it may be proposed and evidenced, but is never made reversible by claiming that a previously installed binary still exists.

## 2. Terms and non-inference rules

An **exact profile** is the dispatchable tuple, not merely its display name:

```text
peer/node identity + declared profile id + executable/transport + ordered effective argv
+ model operand + effort operand + adapter/parser schema version + authenticated namespace digest
```

The tuple is compared as normalized data while retaining the original ordered argv for execution. A model alias, an omitted effort, a PTY transport, and a different authenticated account are distinct facts. `hub_peer.py` model normalization may assist comparison but cannot collapse this tuple.

The following are absolute rules:

- Never infer effort from a model suffix or family name.
- Never infer a quota family, reset unit, pool sharing, or exhaustion semantics from labels or percentages.
- A command accepting an operand proves only operand acceptance. It does **not** prove which backend model was selected.
- A provider's general status output, a model self-report in a prompt response, or an unrelated prior session is not selected-model proof.
- Missing, stale, partial, unauthenticated, redacted-too-far, or transport-failed evidence is `UNKNOWN`/`TEST_NEEDED`, not a negative fact.

Only a fresh, provider-owned, invocation-correlated contradiction may hard-block the affected exact profile. Correlation must bind the invocation to the selected model through a provider event/receipt, nonce or session identity, bounded timestamps, and an authenticated-namespace digest. If a provider cannot expose that evidence, the selected-model field is `UNKNOWN` and the plan must require a manual/live test rather than fabricate confidence.

Invocation safety and routing-policy safety are independent. A valid manual profile remains usable when quota policy makes it ineligible for automatic routing; quota drift gates automatic selection, not the validity of a manually selected exact profile.

## 3. Evidence contract and storage

Provider adapters own how a safe fact is observed: executable/PTY invocation, safe argv, timeout, output cap, redaction, authentication boundary, parser version, and interpretation of a provider receipt. Generic RDR code owns only schema validation, freshness, provenance, hashing, and state transitions.

No shell string is constructed for a probe. An adapter supplies an argv vector or an explicitly declared PTY invocation; paths are resolved and checked before launch. Captures have a timeout and byte cap, secrets are redacted before persistence, and account identity is retained only as a one-way namespace digest. Per-profile single-flight locking prevents duplicate paid canaries.

The canonical raw observation location stays `.ai/cli-reality-observed.json`, written through the existing observation-store merge path. RDR-derived manifests, plans, receipts, journals, and recovery records live as governed `.ai` transaction artifacts; they do not become another mutable declaration store. Archive copies are immutable evidence, not current policy.

### 3.1 Typed records

All records use a versioned `schema_version`, UTC RFC 3339 timestamps, a SHA-256 hash of canonical UTF-8 JSON, and explicit redaction state. Canonical JSON means recursively sorted object keys, compact separators, UTF-8, no insignificant whitespace, and no hash field included in its own digest. Arrays remain ordered unless their schema explicitly defines them as a sorted set.

| Record | Required purpose and essential fields |
|---|---|
| `ObservationSpec` | What an adapter may observe: `id`, `provider`, `peer`, exact profile tuple, `operation`, safe argv/PTY descriptor, timeout/output limits, required correlation fields, parser/adapter version, budget class, redaction policy. It contains no secret. |
| `ObservationReceipt` | What happened: `spec_hash`, `invocation_id`, started/ended time, executable fingerprint, transport, namespace digest, exit/timeout status, bounded/redacted output hash, parsed facts, freshness, completeness, selected-model proof (`PROVED`/`UNKNOWN`), and provenance. |
| `DriftManifest` | A reproducible comparison: declaration input hashes, receipt hashes, scope, each drift item, exact affected profiles, severity, confidence/completeness, blocking rationale, and disposition. |
| `ChangePlan` | A finite intended transaction: `plan_id`, manifest hash, ordered target files, per-file base and proposed SHA-256, desired semantic diff, tool/binary effects, validation matrix, rollback capability, and `plan_hash`. |
| `ApprovalBinding` | R:10 round id, immutable finalized decision hash, exact plan hash, required voters, decision timestamp, expiry/replay boundary, and approver-independent validation policy. A vote on a manifest or prose does not authorize a different plan. |
| `TransactionJournal` | Durable recovery record: plan/approval hashes, fence generation, stage locations/hashes, per-target CAS and replace progress, backups, external-effect status, receipt hashes, terminal state, and recovery instructions. |

`DriftManifest` must project every root observation to the exact profile ids it affects. A peer-wide catalog fact may therefore affect several exact profiles, while a failed effort-specific canary affects only that tuple. The projection prevents an unrelated profile from being blocked by a broad but non-specific observation.

### 3.2 Observation result states

`POSITIVE`, `NEGATIVE`, `UNKNOWN`, and `NOT_APPLICABLE` are evidence states; they are not plan states. `NEGATIVE` is actionable only when it is fresh, provider-owned, invocation-correlated where selected-backend proof is asserted, complete for its stated claim, and maps to one or more exact profile tuples. A catalog enumeration may establish a complete negative only when the provider adapter declares its namespace completeness. A partial positive-canary fan-out cannot become an exhaustive negative catalog.

Existing `check_cli_reality.py` fields such as `probe_attempt_status`, `evidence_completeness`, `confirmed_models`, binary fingerprint, and provenance remain inputs. RDR extends them; it does not erase their positive-confirmations-only semantics. The current `_declared()` model-only comparison is insufficient for version, effort, transport, and selected-backend proof and is deliberately widened only through the exact-profile contract above.

## 4. Lifecycle and safety gates

```text
DETECTED -> OBSERVING -> MANIFESTED -> RECONCILED_NO_CHANGE | NEEDS_EVIDENCE | PLANNED
PLANNED -> AWAITING_R10 -> REJECTED | STALE | APPROVED
APPROVED -> STAGING -> CAS_VALIDATED -> APPLYING -> VERIFYING -> COMMITTED
APPLYING/VERIFYING -> ROLLING_BACK -> ROLLED_BACK | INCOMPLETE_SAFE
```

| Transition | Owner and hard gate |
|---|---|
| `DETECTED -> OBSERVING` | Freshness sweep or explicit operator request invokes only adapter-approved observation specs after budget/single-flight checks. Existing `action_freshness_sweep` remains detect/propose-only. |
| `OBSERVING -> MANIFESTED` | `check_cli_reality.py` validates receipts, declaration hashes, age, provenance, exact-profile projection, and manifest hash. |
| `MANIFESTED -> RECONCILED_NO_CHANGE` | All applicable declared facts match sufficient evidence. No edit and no canary beyond needed evidence. |
| `MANIFESTED -> NEEDS_EVIDENCE` | Evidence is unknown/partial/stale, selected-model proof is absent, budget is unavailable, or an adapter cannot safely observe the required fact. No destructive conclusion follows. |
| `MANIFESTED -> PLANNED` | A finite plan covers every affected declaration/document/checkpoint target and names any external effect. Uncovered applicable files are a planning error. |
| `PLANNED -> AWAITING_R10` | Plan hash and target base hashes are frozen. The approval request includes semantic diff, receipts, limits, rollback statement, and validation matrix. |
| `AWAITING_R10 -> APPROVED` | Exactly the required unanimous R:10 decision finalizes and is bound to this plan hash. A changed manifest, plan, target, base hash, or expired approval is `STALE`, not implicitly reapproved. |
| `APPROVED -> STAGING` | Governed executor validates paths, obtains transaction and target locks, stages every proposed replacement and journal with hashes, then establishes the reader dispatch fence. |
| `STAGING -> CAS_VALIDATED` | Every target still has its approved base hash. Any mismatch aborts before replacement and clears the fence safely. |
| `CAS_VALIDATED -> APPLYING -> VERIFYING` | Ordered atomic per-file replacements are journaled; then all mandatory live/static validation receipts run. |
| failure -> `ROLLING_BACK` | Reverse only successfully replaced repository targets from verified backups. A binary install/upgrade is separate: roll back only if a verified old binary is retained; otherwise repository rollback plus `INCOMPLETE_SAFE`. |

`COMMITTED`, `REJECTED`, `STALE`, `RECONCILED_NO_CHANGE`, `ROLLED_BACK`, and `INCOMPLETE_SAFE` are terminal. Recovery reads the journal after interruption or power loss and never guesses whether an unjournaled write occurred.

## 5. Approval, dispatch, and transaction model

The pre-apply plan is subject to R:10; this document's R:10 (`r-ff91`) approves the design contract only, not a later configuration change. `ApprovalBinding.plan_hash` must equal the staged plan hash and reference the finalized consensus decision. Replay, altered target ordering, altered base hashes, altered validation, or a plan outside the approved scope is rejected.

The dispatch fence is a generation-aware reader isolation rule in `hub.py`/`hub_peer.py`. Before any replacement it prevents new dispatch from resolving a mixture of old and staged declarations. Readers either finish under their captured generation or receive an explicit retry/unavailable result; they never combine fields from different generations. The fence is released only after commit, safe rollback, or recovery has established one visible generation.

"Atomic" here means **logical failure atomicity**, not physical multi-file atomicity. Filesystem replacement remains per file. The safety claim is limited to: fully stage and hash all replacements; CAS-check every target while fenced; journal and back up each replacement; expose only a consistent generation to new dispatch; and recover deterministically after interruption. No document, command, or UI may claim a physical atomic multi-file filesystem operation.

Target paths are allowlisted, real-path checked, and confined to the repository/config scope declared in the plan. A dirty worktree is never a global failure. Unrelated dirt is recorded and left intact; a target that is dirty is permitted only when its observed content matches that target's explicit CAS base hash, otherwise the transaction is `STALE`. RDR must never reset, delete, overwrite, commit, push, or open a PR for user work.

## 6. Declaration coverage and validation

For every planned change, the planner creates a coverage table. Applicability is explicit: `required`, `not-applicable` with reason, or `blocked`. A plan cannot pass with an omitted row.

| Surface | Required reconciliation question |
|---|---|
| `_sys/runtimes.json` | Does installed-runtime/version declaration match measured binary/update evidence? |
| `_sys/ai/orchestration.json` | Do enabled profiles preserve exact ordered effective operands, transport, and declared routing identity? |
| `_sys/ai/model-registry.json` | Are model facts/declarations aligned without substituting assumptions for measured evidence? |
| `_sys/ai/routing-config.json` | Do automatic-routing policy and quota-family policy reference only validated capabilities; is manual-validity separate? |
| `_sys/ai/status_checks.json` | Are health/status probe policies applicable and not a duplicate provider argv registry? |
| `_sys/ai/capability-declarations.json` | Are declared capabilities consistent with receipts, including `UNKNOWN` where evidence cannot prove a claim? |
| quota parsers, snapshots, and telemetry | Are quota names, reset units, availability, semantics, redaction, and display sourced from evidence rather than inferred? |
| `hub.py`, `hub_peer.py`, `peer_console.py` parity | Do hub and console construct the same approved exact profile and honor the dispatch fence? |
| `ops/peer-cli-reference.md`, provider checkpoints, README/manual/MOC/manifest | Is operational/documentation truth updated only for approved, measured facts with provenance/date and no stale contradiction? |

Post-apply validation is acceptance, not a best-effort log. Required receipts are: adapter observations; selected-model proof or explicit `UNKNOWN`; exact-profile parity; declared config/registry/routing/quota checks; console/hub command parity; targeted automated tests; documentation link, manifest, encoding, and checkpoint checks; diagnostic snapshots; and command/output hashes. A failed, missing, or inconclusive required receipt moves to rollback or `INCOMPLETE_SAFE`, never `COMMITTED`.

## 7. TDD contract (to be implemented later)

No source or tests are changed in this phase. The next phase first turns the following cases into failing, hermetic tests and then makes the smallest compatible implementation change. Live paid/account observations are manual-only fixtures and must not run in CI.

| Test family | Minimum cases |
|---|---|
| Adapter observations | subprocess and PTY; allowlisted argv; timeout/output cap; redaction; authenticated namespace change; parser/adapter version change; single-flight dedupe; paid-canary budget refusal; no-change path does not spend a canary. |
| Evidence truth | complete/partial catalog; stale record; unauthenticated receipt; positive versus hard negative; alias normalization without tuple collapse; operand accepted but backend substitution; selected proof present/absent; effort operand; no suffix inference; exact-profile-only block. |
| Quota policy | unknown family/semantics/reset unit; reserve exhaustion; quota drift blocks automatic routing only; valid manual exact profile remains usable. |
| Planning and approval | each declaration surface; applicability/coverage failure; canonical hashes; hash tamper; stale/replayed approval; changed manifest/plan/base; R:10 binding; no provider argv duplication. |
| Transaction/recovery | lock contention; per-target CAS mismatch; stage corruption; replace failure at every file; power loss before/during/after replacement; journal replay; backup hash failure; rollback; `INCOMPLETE_SAFE`; reader generation/fence behavior; unrelated dirty worktree; dirty target base mismatch. |
| External effects | install succeeds/fails; old binary retained/not retained; repository rollback plus `INCOMPLETE_SAFE`; no claim of binary rollback without retained evidence. |
| Integration | `check_cli_reality` observed-store compatibility and auto-refresh; `check_tool_updates` proposal compatibility; `hub.py` public command/signature contracts; `hub_peer.py` and console parity; diagnostics/telemetry; Windows paths/PTY and Unicode/encoding. |
| Documentation | MOC/manifest coverage; checkpoint provenance; dead links; all docs English; no source/test mutation in documentation-only change. |

## 8. Implementation sequence and acceptance bar

1. Freeze exact schemas, canonicalization routine, state transition table, and status/error vocabulary.
2. Write the hermetic tests in Section 7, including fault injection before any mutator.
3. Extend adapter-owned observation and existing reality-store projection without changing dispatch behavior.
4. Implement manifest/planning/coverage with detect-only output and validate it against current update proposals.
5. Add R:10 plan binding, dispatch fence, staged per-file CAS/journal transaction, rollback/recovery, and public command contract tests.
6. Add post-apply receipts and only then enable an explicitly invoked governed apply path. Automatic freshness remains detect/propose-only unless separately approved.

Pre-TDD acceptance for this document is satisfied only when the R:10 record is finalized, all listed ownership boundaries and non-inference rules are retained, the manifest/MOC index is updated, and repository source/tests remain unchanged. Implementation acceptance requires all applicable TDD cases and post-apply evidence; it is not implied by this design approval.

## 9. Decision record

- Decision: `r-ff91`, finalized unanimous (cc, ag, cx), 2026-07-27.
- Critical-review correction: an earlier round was rejected because it omitted invocation-correlated selected-model proof and the logical-not-physical atomicity limitation. Those omissions are normative blockers in this final specification.
- Deliberate exclusions: `reality.yaml`, an adapter registry file, a new `_sys/drift` service/store, generic provider "gatekeeper" abstractions, automatic Git writes, and automatic provider-binary updates. None is an existing approved integration boundary.
