# Draft interface and data contracts — Rev. 0.6

These are proposed integration contracts for RED-test review, not assertions of implemented APIs. Existing PeerHub/Engram commands are explicitly labeled. Vendor APIs and exact binary support must be probed; adapt only through supported contracts. No real user data in examples.

## 1. Versioning, identities and error semantics

Use UTF-8, timezone-aware UTC ISO 8601 timestamps, positive monotonic revision per mutable aggregate, canonical JSON (UTF-8, normalized structured representation, stable keys; define serialization before hashing), full SHA-256, opaque safe IDs. Record exact raw-byte digest separately from canonical envelope digest. Identity never depends only on text, time, drive letter or model nickname. Unknown field values are `null` plus coverage/reason; zero is measured zero. No raw auth/password/API keys, session secrets or unsafe paths in public envelopes. Reject unsupported future major schemas and unknown security-affecting flags, additive optional fields allowed within negotiated compatible schema. Validate before effects, output JSON one object and redacted stderr when JSON mode supported. Existing Engram and PeerHub exit codes remain unchanged; map new symbolic errors to actual command exit fixtures before RED. Do not allocate arbitrary numeric codes that conflict. Distinguish inventory status, task outcome, delivery certainty, evidence trust, job/projection state, command status and reasons. Never map `delivered`, `accepted`, `exit=0`, or `UNKNOWN` to verified success automatically.

```json
{
  "schema_version": "1.0",
  "request_id": "req-synthetic-001",
  "status": "PARTIAL",
  "data": {},
  "coverage": {"state": "PARTIAL", "reason": "late_outcomes_not_exposed"},
  "warnings": [],
  "errors": [{"code": "CAPABILITY_UNAVAILABLE", "message": "A source lacks an approved interface", "retryable": false}],
  "next_actions": ["Review the source capability report"]
}
```

Command status: `OK`, `NO_CHANGE`, `PREVIEW`, `DECLINED`, `PARTIAL`, `BLOCKED`, `FAILED`, `ROLLED_BACK`, `RECOVERY_REQUIRED`. Inventory: `ABSENT`, `INSTALLED`, `PARTIAL`, `READY`, `STOPPED`, `DEGRADED`, `CORRUPT`, `UNKNOWN`, `LEGACY_COLLISION`. Freshness: `UP_TO_DATE`, `UPDATE_AVAILABLE`, `NOT_CHECKED`, `UNVERIFIABLE`, `PINNED`, `BLOCKED_DEPENDENCY`, `SOURCE_NEWER_NO_BINARY`, `MIGRATION_REQUIRED`. Task status and delivery certainty remain separate; raw vendor values preserved beside canonical mapping. Coverage: `MEASURED`, `ESTIMATED`, `PARTIAL`, `UNKNOWN`, `ABSENT`, `UNSUPPORTED`, `STALE` with source, scope and timestamp. Unknown is not an error in every case, but required unknown blocks applicable gate.

| Code family | Meaning | Required behavior |
|---|---|---|
| `SCHEMA_UNSUPPORTED`, `INVALID_ARGUMENT`, `SCOPE_CONFLICT`, `PATH_COLLISION` | Contract mismatch | Reject before effects; show exact remedy |
| `POLICY_DENIED`, `CONSENT_REVOKED`, `APPROVAL_EXPIRED`, `APPROVAL_MISMATCH` | Denied/revised authorization | No data access/export/effects outside scope |
| `POLICY_ENFORCEMENT_UNAVAILABLE`, `CAPABILITY_UNAVAILABLE` | Cannot enforce required boundary or support interface | Disable affected automation; report limitation |
| `SOURCE_UNAVAILABLE`, `UNSTABLE_SOURCE`, `AMBIGUOUS_LINK`, `RESNAPSHOT_REQUIRED` | Evidence/cursor issue | Preserve provenance and cursor safety; reconcile, not re-execute |
| `INSUFFICIENT_EVIDENCE`, `INSUFFICIENT_CONTEXT`, `CONTEXT_UNVERIFIED` | Hard input/proof limit | No fabricated result; segment, retrieve or request approval/help |
| `QUEUE_FULL`, `GPU_BUSY`, `RESOURCE_PRESSURE`, `THERMAL_UNKNOWN` | Admission cannot safely continue | Backpressure/defer; no silent drop or cloud fallback |
| `UNVERIFIED_RESULT`, `CONFLICTED_MEMORY`, `INDEX_PENDING`, `PROJECTION_UNKNOWN` | Derived record not ready/trustworthy | Exclude from verified retrieval; inspect evidence/reconcile |
| `BINDING_CONFLICT`, `INTERPRETER_MISSING`, `ENV_DRIFT`, `PACKAGE_LOCK_MISMATCH`, `VENDOR_PINNED` | Runtime constraint | Keep previous build; repair or select compatible environment |
| `BLOCKED_OFFLINE_MISSING_ARTIFACT`, `UNSUPPORTED_EOL`, `RUNTIME_IN_USE`, `REFERENCE_UNKNOWN`, `LEGACY_DEFAULT_PROTECTED` | Offline/removal constraints | No download or deletion; report dependency |
| `STORE_REPLACED`, `GENERATION_MISMATCH`, `STALE_LEASE`, `OPERATION_IN_PROGRESS` | Fencing/restore/lifecycle | No effect; resume/rollback or re-snapshot |
| `UNCERTAIN_EXTERNAL`, `TRUNCATED_OUTPUT`, `QUOTA_UNKNOWN`, `QUOTA_EXHAUSTED` | Provider delivery limitations | Preserve receipt; no automatic new call; verified result pending |
| `MIGRATION_REQUIRED`, `DIGEST_MISMATCH`, `ROLLBACK_FAILED` | Upgrade/identity safety | Hold old generation, block or recover from verified backup |

## 2. Registry and plan contracts

### 2.1 Python registry (`_sys/data/state/python-registry.json`)

Draft example. Extra slots only; legacy default path maintained. `version` example placeholder not an actual candidate version. Real version parsed numerically (PEP 440/CPython policy) and validated against source. Registry is atomic revision/CAS manifest, not a junction or global alias.

```json
{
  "schema_version": "1.0", "revision": 7,
  "installation_id": "install-synthetic", "default_binding": "legacy-default",
  "series": {"3.14": {"channel": "stable", "active_build": "build-synthetic", "policy": "compatible_patch"}},
  "builds": {"build-synthetic": {
    "implementation": "cpython", "series": "3.14", "version": "3.14.x", "abi": "cp314", "arch": "win_amd64",
    "provider": "verified-provider", "flavor": "full", "sha256": "<64 hex>", "artifact_ref": "<approved artifact>",
    "executable_rel": "env/python-versions/3.14/build-synthetic/python.exe", "state": "ACTIVE", "owner": "engram"
  }},
  "bindings": {
    "legacy-default": {"kind": "legacy", "executable_rel": "env/venv/Scripts/python.exe"},
    "hermes": {"kind": "app", "build_id": "build-synthetic", "env_id": "env-hermes-1", "constraint_ref": "<verified vendor lock>"}
  },
  "environments": {"env-hermes-1": {"build_id": "build-synthetic", "root_rel": "AI/apps/hermes/envs/env-hermes-1", "lock_ref": "<package-lock>", "owner": "hermes", "generation": 1}},
  "external_refs": [], "vendor_exceptions": [], "rollback_refs": []
}
```

Constraints: unique build/env IDs and canonical paths; valid relative roots; all bindings resolve; default protected; every env has build identity and lock; candidate generation not published until tests; exact pin preserved; `vendor_exceptions` has reason, owner, pin and footprint, not forced repin. Registry discovery is read-only for absent/legacy-only users; adoption persisted only on explicit apply. Resolve exact current executable and `sys.executable`, prefix, base_prefix and package paths. Removal GC requires no references (including backup/pending/live/unknown). Artifacts and cache must be validated independently; no global `py` alias, no junction. No bare pip to change arbitrary environment.

### 2.2 Component and model manifests

`install.json`: installation/root identity, manifest schema/revision, profile, component IDs, installed generation, version, artifact provenance, component paths, runtime binding IDs, dependencies, configured service state, capability/probe receipts, plugin config revision, source policy refs. ABSENT static files not marker. Legacy/corrupt marker does not authorize ownership. `models.lock.json`: role, backend, registry ID, tag, resolved immutable revision and digest, size, quant, architecture/template/tokenizer, advertised and verified context, capabilities, license, pin/channel, consumers, active/previous generation, checked_at, validation ref. `index_generation`: `kind=memory|knowledge`, exact encoder and query/passage revision, dimensions, preprocessing, normalization, corpus watermark, schema, approved bank scopes, source manifest digest, state/active pointer/previous generation. Index generation changes require proof of compatibility, backup and verified publication; equal dimensions do not imply same embedding space.

### 2.3 Lifecycle transaction

```
plan_id, parent_op_id, installation_id, root_identity, scope, registry_revision,
policy_revision, plan_digest, approval_ref, deadline, dependency_groups[],
component_steps[{id, from_generation, to_generation, preconditions, state, receipt_ref}],
pre_service_state[], backup_refs[], pending_job_watermark, failure_reason
```

State sequence: PLAN → APPROVED → STAGED → VERIFIED → DRAINED → APPLYING → COMMITTED → HEALTHY → COMPLETE. Rollback/recovery transitions record actual previous/new generation and commit status; after-commit write failures are not reported as pre-commit rollback. Persist parent plan for detached core self-update. Approval invalid on plan/policy/root/consumer revision mismatch; never reuse approval for altered model family or migration. One global lock then registry then service group then short ledger transaction; no nested inversion. Each effect idempotent or has reconciliation proof. Dry-run: no mutations, no model blob or credential creation, no service stop. Remote metadata only when permitted. `doctor` strictly local/read-only, no inference. Preserve original service run state and no background enablement on recovery.

## 3. Source registry, activity and evidence envelopes

### 3.1 Source consent record

```json
{
  "schema_version": "1.0", "source_instance_id": "source-synthetic-001", "source_kind": "peerhub",
  "owner_scope": "owner-local", "project_scope": "project-example", "locator_ref": "registered-source-1",
  "consent_revision": 1, "state": "ENROLLED", "capture_mode": "redacted_content",
  "historical_range": {"from": null, "to": null}, "enabled_event_kinds": ["prompt", "response", "outcome"],
  "external_export": "deny", "retention_policy_ref": "policy-1", "exclusion_policy_ref": "exclusion-1",
  "adapter_version": "1.0", "credential_ref": null, "capabilities": {}, "source_lineage": null
}
```

Source states: DISCOVERED (no content read), ENROLLED, PAUSED, REVOKED, UNAVAILABLE, UNSUPPORTED. Consent is explicit by root/project/account/type/time/capture level, not inferred from software detection. Scope/consent checked each read, before persistence, and before projection. Revocation immediately denies use and stops queued work. History and cleanup separate actions. Paths in private registry, public envelope uses opaque locator ref. Source native identity/digest/lineage stored where available; different installations may reference same approved original but should not double count.

### 3.2 Normalized event

```json
{
  "schema_version": "1.0", "event_id": "event-synthetic-001", "source_instance_id": "source-synthetic-001",
  "source_event_id": "native-record-id", "source_revision": "1", "source_lineage": "lineage-1",
  "kind": "ai.prompt", "actor": {"id": "hermes-lead", "role": "requester"},
  "scope": {"owner": "owner-local", "project": "project-example", "sensitivity": "internal"},
  "correlation": {"task_id": "task-synthetic", "attempt_id": "attempt-1", "parent_task_id": null,
    "stream_id": "stream-1", "request_id": "req-1", "delivery_id": null, "session_ref": null},
  "occurred_at": "2026-11-28T00:00:00Z", "observed_at": "2026-11-28T00:01:00Z", "ingested_at": "2026-11-28T00:02:00Z",
  "source_ref": {"locator_ref": "native-record-id", "range": null, "sha256": "<64 hex>", "source_version": "pinned-version"},
  "content": {"mode": "reference", "text": null, "truncated": false, "redaction_policy": "policy-1"},
  "coverage": {"state": "MEASURED", "reason": null}, "consent_revision": 1,
  "adapter_version": "1.0", "envelope_sha256": "<64 hex>"
}
```

Source natural event key `(source_instance_id, source_event_id, source_revision)` plus payload hash; same key same digest idempotent; same key different digest quarantined, not silently overwritten. Restore lineage validates cursor; do not make replay of identical immutable records automatically distinct events. If lineage reuses IDs with different content, preserve branch identity and conflict, no overwrite. `event_id` deterministic namespace from key or durable assigned once; exact serialization definition locked pre-TDD. Separate attempts, task identity and physical sources. `kind`: ai.prompt/response, tool.call/result, peer.delivery/evidence/outcome, source.document/revision/tombstone, git.commit, ci.test, owner.feedback, etc.; validate type-specific allowed fields. A failed/partial/unavailable event is still an event, not a successful experience. Metadata-only mode excludes text, not digest/locator where permitted; content ref must not be resolvable by an unauthorized caller. For file locators include page/line/sheet-cell/time range and digest; for git SHA/path/line; for PeerHub DB/store/record/attempt. UTC stamps separate occurred/ingested. Do not fabricate dates or actor; unknown explicitly marked.

### 3.3 Evidence, experience and verification

```yaml
schema_version: '1.0'
experience_id: exp-synthetic
revision: 1
logical_type: episodic
scope: {owner: owner-local, project: project-example, sensitivity: internal}
actor: codex-worker
task_id: task-synthetic
problem: {description: 'Synthetic dependency conflict', symptoms: [], environment: {python_series: '3.14'}}
actions: []
result: {transport: delivered, task_status: VALIDATING, adoption: unknown, execution_proof: null}
claims:
  - claim_id: claim-synthetic
    text: 'A candidate solution was proposed.'
    evidence_refs: [event-synthetic-001]
    applicability: []
    exclusions: []
validation:
  trust: candidate
  lifecycle: active
  methods: []
  verifier: null
  verification_receipt: null
  coverage: UNKNOWN
  last_verified_at: null
policy: {external_export: deny, policy_revision: 1}
validity: {occurred_at: null, valid_from: null, valid_to: null, supersedes: null}
projection: {state: pending, bank_ref: null, unit_refs: [], index_generation: null}
usage: {successful_reuses: 0, failed_reuses: 0, measured_cloud_tokens: null}
```

Evidence validation receipt includes exact subject revision/digest, source refs and locators, verifier/method, actual observed outcome, test command/run/report hash/commit/environment (if tested), constraints, coverage, timestamp, conflicts, authority and approval. Candidate -> verified only when required claims supported; proven requires actual scoped success proof; negative/failure evidence explicitly typed. `accepted` feedback alone not enough. Skill publication separate. Candidate trust and projection state independent. Source revocation invalidates linked derivatives (incl observations, summaries, cache and skill applicability) immediately in broker. Historical access permission separate. Do not claim all Hindsight units can be updated with one native flag; use supported APIs/projection checks.

## 4. Ledger data model (logical schema, no SQL migrations implemented)

SQLite is control/evidence metadata only; Hindsight owns its internal PostgreSQL schemas. Each table below is a proposed logical responsibility, consolidate tables if invariants can still be expressed. FK enforcement, WAL/timeout behavior, transaction boundaries, migrations and indexes must be proven. Avoid unbounded JSON/raw text in ledger. Scoped private archive or source holds allowed content. Keep unique keys and use keyset pagination. Single writer transaction per page/job transition, no vendor call under transaction.

| Entity/table | Primary identity & major fields | Invariant / index |
|---|---|---|
| source | source_instance_id; locator_ref, scope, policy, consent_revision, capabilities, lineage | explicit enrollment; CAS on consent; index state/scope |
| cursor | source_instance_id + partition + filter revision | watermark, opaque cursor, lineage, checked_at; no advance without durable page commit |
| activity_event | event_id; source identity/rev, kind, actor, time, hash, locator, coverage | unique natural key+validated digest; indexes source/occurred_at, task-link |
| source_revision | stable source document/ref + revision | byte hash, locator/format, parse generation, availability, tombstone |
| task | task_id; objective ref/hash, scope, acceptance, state, deadline | state transition guard and revision; no transport-as-success |
| attempt | attempt_id; task, peer/model, execution IDs, state, receipt, usage scope | unique execution ref in source; replay same execution not second attempt |
| correlation_edge | event_id + task/attempt + relation kind | method exact/manual/heuristic, evidence; ambiguous candidates not auto merged |
| claim_revision | claim_id + revision; type, scope, trust/lifecycle, derivative ref/digest | approved iff verification proof exists; append revisions |
| claim_evidence | claim_id + revision + event/source ref + locator | exact proof edges, reverse index for invalidation |
| verification | verification_id; subject/rev, validator, proof refs, result, method/time | measured vs inferred, independent evidence; immutable receipt |
| projection | subject/rev + backend/bank + generation | desired state, external unit/document IDs, digest, ready/failed/unknown; invalidation |
| outbox | outbox_id; idempotency key, target, payload ref/hash, policy and generation | unique logical effect; lease/fence, retries, state, last error, ready time |
| job | job_id; kind, inputs/watermark, scope, dependencies, priority, generation | state/revision/lease/heartbeat; no duplicate committed publication |
| sleep_run | run_id; policy/plan hash, resource/start/stop, watermark, report ref | immutable per-run summary and linked jobs |
| skill_revision | skill_id + revision; manifest/digest, test/approval/owner, state | only exact approved revision executable; rollback ref |
| evaluation | evaluation_id; task/attempt/model/skill, acceptance, measured/unknown usage, time | unique source measurement ID; attributable sums only |
| approval | approval_id; principal, action, request/plan digest, exact scope/peer/budget, expiry/revision | explicit action, no model mint; revocation check |
| audit | event_id; action, principal, scope ref, reason, result, timestamp | redacted metadata; no secret/content default |

Jobs/outbox states: PENDING → LEASED → EXECUTING → ACK_PENDING → DONE; transient → RETRY_WAIT; unknown side effect → RECONCILE_REQUIRED; permanent → QUARANTINED/FAILED; revoked → CANCELLED. Fencing token monotonically changes when job claimed, old worker cannot publish. Lease alone not proof of process liveness. Crash after effect before ack => inspect supported backend operation/document IDs/digest; if uncertain quarantine, not assume retry safe. Cursor commits with page normalized records/outbox; if source can't guarantee page stability, record bounded coverage/overlap and rescan. No external provider side effects from ledger reconciliation. Restore resets/fences leases and reconciles to active source/index generations. Retention can remove expired operational metadata only when not sole provenance or pending work. Protected private content may be encrypted; no casual copy of SQLite DB to public repo.

## 5. PeerHub interfaces

### 5.1 Existing baseline usage (placeholders; not executed)

```powershell
peerhub --db <approved-existing-db> stream list --json
peerhub --db <approved-existing-db> record read --stream <stream> --after 0 --limit 100 --json
peerhub --db <approved-existing-db> session list --json
peerhub --db <approved-existing-db> session show <handle> --json
peerhub --db <approved-existing-db> outcome <ask-record-id> accepted
peerhub --db <approved-existing-db> diag --plan --json
peerhub --db <approved-existing-db> ask cc --prompt-file <approved-packet.md> --profile cc.standard --workspace <approved-review-root> --stream <stable-task-peer-stream> --request-id <stable-request-id> --timeout-seconds 180 --max-output-bytes 65536 --dry-run --json
```

`outcome` is a write only when explicit user/authorized evaluation records actual adoption. All source readers read-only; `--dry-run` provider call/store writes absent per documented contract, validate actual installed CLI. Live invocation only after approval; remove `--dry-run` with same approved packet/flags. Scope `--db` explicit, no arbitrary fallback. `180s`, `65536` bytes example not guaranteed token cap. `--writable` off; current ag read-only fail closed. Existing session/native reuse and request replay invariants preserved. PeerHub current public `profile stats` provides aggregate read, not all late outcome events. A read API can run in existing PeerHub environment, no duplicate import/install into app venv.

### 5.2 Proposed read-only Activity Export

```
peerhub activity export --json [--stream ID] [--cursor TOKEN] [--limit N] [--max-bytes N] [--include-content]
peerhub activity show ASK_ID --json [--include-content]
```

Default metadata-only, explicit approved source policy outside CLI as needed; do not claim CLI alone can enforce same-user access. Scope includes exact store identity, restore lineage/epoch, filter, content mode and schema. Draft response:

```json
{
  "schema_version": "1.0", "source": "peerhub", "store_ref": "store-synthetic",
  "lineage": "generation-1", "coverage": {"state": "PARTIAL", "reason": "provider_internal_trace_not_recorded"},
  "watermark": {"snapshot_ref": "opaque", "record_partitions": "opaque", "evidence_seq": 45, "outcome_seq": 8},
  "events": [{"event_id": "record-event-1", "revision": "1", "kind": "prompt", "record_id": "r1", "stream_id": "s1", "position": 1,
    "request_id": "q1", "author_peer": "user", "target_peer": "cc", "binding_ref": "profile-ref", "body_ref": "r1", "body": null,
    "occurred_at": "2026-11-28T00:00:00Z", "truncated": false}],
  "next_cursor": "<opaque or null>", "has_more": true
}
```

Return normalized records, delivery attempt/evidence revisions, feedback revisions, bounded session/usage summaries; join `reply_to`/record/delivery not guessed text. Separate raw certainty vs settled state and `acked`; terminal may precede response append/ack, later revisions required. Include original vs rendered/catch-up metadata only when known. `show` bundles associated events with bounded output and continuation, not only latest attempt. Evidence/feedback sequence independent; no fake single monotone global cursor. Record partition inventory refreshed each cycle; high-water per snapshot. Restore lineage change invalidates cursor; `RESNAPSHOT_REQUIRED`. Bounded query and short snapshot; if historical scan must hold long WAL snapshot use explicit backup/limited mode and coverage. No update/migration/offset write or provider call from export. Tests prove concurrent writes, late changes, replay, malformed/old/future DB, large fields, no private terminal metadata leakage. Proposed schema frozen only after PeerHub owner review. If exporter requires new projection, use minimal source-owned projection after demonstrating read contract gap, never write memory to core.

### 5.3 Delegation packet and approval

```yaml
schema_version: '1.0'
task_id: task-synthetic
parent_task_id: null
request_id: req-synthetic
objective: 'Review only the unresolved synthetic dependency issue'
constraints: [read_only, no_recursive_delegate]
verified_facts: []
resolved: []
unresolved: []
evidence_refs: []
evidence_excerpt: []
acceptance_criteria: []
export_policy: {decision: approved, approval_ref: approval-synthetic, scope_ref: review-root}
budget: {max_calls: 1, deadline_seconds: 180, max_input_tokens_estimate: null, max_output_tokens_estimate: null, supported_hard_limit: null}
```

Approval must bind exact digest and source scope/cwd, provider/profile, peer/stream/request, policy rev, expiry/calls and available controls; no changed payload under same ID. Source ref access also authorization. Bridge response common envelope + raw status/receipt/session/request/delivery IDs, `transport_status`, `task_status`, attributable usage coverage, truncation and next action. Source uncertainty never triggers automatic fresh request. Proof after integration stored separately. Support cancel only with verified upstream contract; cancellation not refund. No arbitrary shell string generated from LLM; typed allowlisted arguments and safe file handling. Existing direct owner CLI remains available, not automatically intercepted.

## 6. Memory and knowledge gateway

Proposed typed operations, not public vendor names. Every request principal/scope/authorization/policy revision validated at ingress and before returning content. Bank mapping internal, no free-form bank ID privilege. API/MCP endpoint chosen after pinned capability test; reject unsupported scopes instead of relying on tags. Return per-result claim type/trust/lifecycle/projection status, applicability/time, evidence/source refs, content limit, model/index generation and coverage.

| Operation | Request | Response / guard |
|---|---|---|
| `memory.search` | query, task_id, permitted scope, type/filter, time/version, max_tokens | evidence pack; no unapproved/revoked content; bounded fan-out |
| `knowledge.search` | query/media type, approved corpus, token/byte budget | exact passage/media locator, source/revision; no synthesized fact as original |
| `memory.get` | authorized source ref, range, budget | exact scoped excerpt or unavailable, path containment |
| `memory.submit_candidate` | normalized claims/evidence/provenance | candidate ID/rev, pending projection; no approved write |
| `memory.verify` | candidate ID/rev, proof receipt and approval | verified/proven or rejection/conflict; CAS |
| `memory.invalidate` | source/claim ref+revision+reason+approval | immediate deny + downstream invalidation jobs |
| `memory.consolidate` | scoped bank/job plan, watermark | operation ID and coverage; same Sleep Engine admission, no competing writer |
| `memory.reflect` | authorized query + linked scope + context cap | local synthesized answer with refs/unknowns; explicit LLM operation |
| `skills.search/run` | scope/task, exact approved skill rev and typed inputs | searchable description; controlled effects/output/proof |
| `peerhub.plan/consult/review/status/result` | typed delegation above | existing CLI adapter with separate approval |
| `local.status` | resource/scope | read-only telemetry/coverage |

Vendor compatibility checklist: Retain/Recall/Reflect, native world/experience/observation, per-bank automatic consolidation toggle and manual scoped operation, KB document upload/revision/search/linked reflect, IDs/tags, review/curation hooks and deletion/invalidation semantics, index migration/export/attachments, local LLM/embedding/rerank/decision/KB providers, async status/cancel/operation IDs. Native automatic writes never trusted merely because vendor endpoint reports success. Use controlled candidate banks and reviewed approved projection. No direct SQL into Hindsight. If API cannot correlate retain retry or force approval, block autonomous verified writes and reconcile supported read API. Model and version changes invalidate context pack and re-evaluate derivatives; no automatic re-extraction of all memories.

## 7. Context and Sleep contracts

`ContextRequest`: task_id, model/session binding, backend effective context and coverage, policy revision, required instruction/evidence refs, history refs, requested output, memory/source filters, risk, budget. `ContextPlan`: effective capacity, tokenizer/estimator identity, actual serialized input estimate/measurement, reserved output/margin, pinned constraints, selected source ranges, omissions with reasons, cache key, index/model generation, sufficiency status and next_action. Rule: `count(serialized input) + output reserve + safety margin <= verified effective context`; no silent truncation. Token estimate coverage not mislabeled exact. Pinned items must survive compaction or reject. If task exceeds capacity, page documents/outputs, decompose, summarize with refs, or approved alternative; never fake 64K. Profile benchmark receipt records model digest, context, weights/cache quant, backend/driver, actual VRAM/RAM/TTFT/TPS, tool/answer score, test corpus and failures. Unknown profile remains unverified.

`AdmissionRequest`: job_id, priority, scope, model/revision, estimated RAM/VRAM/time, deadline, cancellation handle, parent task; `Lease`: owner/process create time, generation, expiry, resource class, max work unit. Acquire only per compute call; never while holding DB/global lock or waiting another compute. Foreground wins; unknown nonpreemptible work drain. CPU-only jobs still respect CPU/RAM/disk and consent. Lease fencing prevents stale completion. No GPU use by ungoverned local model; CPU or unavailable.

`SleepPolicy`: enabled false default, allowed local quiet windows, idle duration candidate, resource thresholds/hysteresis, max jobs/duration/queue, per-scope inclusion, retention/verification policy, no external calls, auto promotion off except preapproved deterministic low-risk proof, report level. `SleepRun`: source/index/model/policy generation, plan hash, phase/job refs, watermark, trigger, resources, states, lease/cursor, completion receipts and stop reason. `SleepReport`: candidate/verified/proven counts separately, dedup/evidence coverage, conflicts/revocations, jobs deferred/failed, skill candidates, preparation artifacts, actual measured local/cloud usage (unknown if not measured). Wake foreground blocks new background admission; no promised instantaneous preemption. Update/restore/relocate fences runs and revalidates source generations, only resume prior allowed state. Never run after actual PC sleep or force wake. Sleep engine does not publish active code or modify policy, perform external consultations or erase original data. `ai memory consolidate` same coordinator. No native competing writer; native OpenClaw Dreaming remains off for shared banks.

## 8. Command inventory (all `ai` and `engram python` commands proposed)

| Command / namespace | Meaning / side effect |
|---|---|
| `ai`, `ai help`, `ai status [--json]`, `ai doctor [--json]` | Available before AI install; status/diagnostics local/read-only |
| `ai setup [--profile runtime|agent|memory|full] [--dry-run|--apply --yes]` | interactive default preview and confirm; noninteractive explicit apply; no surprise sources/sleep/bot enrollment |
| `ai start`, `ai stop` | owned configured components only; service DAG and drain |
| `ai hermes`, `ai openclaw` | invoke configured agent; validate profile/permissions; no silent install/cloud |
| `ai models [list|check|pull|update]` | list offline; check metadata; approved install/update; migration risk separate |
| `ai update [--check|--dry-run|--yes] [--only COMPONENTS]` | same planner as Engram; approved safe updates; no unrelated scopes |
| `ai backup --out PATH`, `ai restore PATH --dry-run|--apply` | private verified backup/restore; explicit scope and secrets policy |
| `ai relocate/repair/tidy/uninstall --dry-run|--apply` | same coordinator; safe preview/confirmation/recovery; no data purge by default |
| `ai memory status/sources/stats` | metadata and coverage read; no raw transcript by default |
| `ai memory enroll SOURCE`, `import --source SOURCE`, `ingest PATH`, `watch PATH` | explicit approval, preview, source scope/range, bounded asynchronous local jobs; watch registration opt-in |
| `ai memory search QUERY`, `reflect QUERY`, `ai graph [query]` | authorized local query, reflect uses local LLM, graph no separate DB by default |
| `ai memory review`, `consolidate`, `invalidate REF` | review read; explicit approved local job or invalidation; shared Sleep coordinator |
| `ai sleep [status|report|review]` | read only; no surprise processing |
| `ai sleep enable/disable/pause/resume/run` | explicit local config/state/one-pass operations; bounded; no new external service |
| `ai context [status|doctor]`, `ai gpu status` | read-only budget/profile telemetry; no model load in doctor |
| `ai context benchmark` | opt-in local measured tests, not ordinary doctor |
| `engram python list/where/doctor` | offline/read-only inventory and resolved path |
| `engram python install 3.14 [3.13]`, `install --all-supported` | explicit stable compatible plan, `--dry-run`, `--yes`; no auto EOL/new series |
| `engram python check [SERIES] [--refresh]` | remote metadata only when allowed; cache age/unknown |
| `engram python update [SERIES] [--check|--yes]` | installed series only; default via legacy engine; no unrelated apps/models |
| `engram python run 3.14 -- -m pytest`, `use 3.14` | explicit selected child execution/shell, preserve parent and exit code, no implicit install |
| `engram python pin 3.14`, `unpin` | explicit approved project only; preserve user-owned pins |
| `engram python remove 3.13` | plan+confirm, no active/pinned/unknown references or default deletion |

Flag policy: preserve existing Engram update plan+prompt, `-y`, `--check`, `--dry-run`, `--refresh`, `--only python|venv|packages`, `--latest`, `--to`, offline and repair/relocate `--apply`, resume/rollback. Scope of `engram update --only python` remains legacy default; new selectors for extra slots/AI/models only after compatibility tests. `--yes` skips normal confirmation, cannot bypass separate risk approval. No contradiction allowed between check/apply or offline/live. `ai setup --dry-run` no downloads/writes; offline no remote metadata. Document all exits and additive JSON only after comparison with actual legacy fixture. Avoid overloading a new `--json` onto commands whose existing schema/exit contract cannot support it.
