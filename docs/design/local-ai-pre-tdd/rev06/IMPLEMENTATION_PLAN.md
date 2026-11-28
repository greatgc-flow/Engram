# Implementation readiness, pre-TDD plan and operating runbooks

**Status: design only.** This is the stopping point requested by the owner. No RED test code, production code, Windows installation, GitHub write, live model request or actual source import has been performed. The catalog is an acceptance specification; all tests NOT_RUN. The team can start contract review and isolated feasibility spikes; dependent implementation is blocked until its required gates are resolved.

## 1. Entry/exit gates

| Gate | Entry | Required exit evidence | State |
|---|---|---|---|
| G0 design/traceability | Rev.05 + follow-up decisions | English package, stable requirement/test/ADR IDs, no contradictions; owner review and baseline recheck | DOCUMENTED; owner review pending |
| G1 technical feasibility | Exact upstream pins and disposable test environment | Actual standard-user Windows artifacts/provider footprints, local GPU/64K quality, native PG/pgvector, Hindsight local KB/Memory, tool and plugin contracts | NOT_RUN / blockers open |
| G2 baseline/runtime RED+GREEN | G0 and relevant G1 provider facts | Legacy Engram regression, Multi-Python registry/CLI/isolated envs; no default changes | NOT_RUN |
| G3 functional integration | G1+G2 for dependent components | Scoped source capture, PeerHub dry-run/import/export contract, evidence/KB/Memory, context, sleep jobs and skills | NOT_RUN |
| G4 lifecycle/recovery | Applicable integration | Fault injection, versioned update, coherent encoder migration, quiesced backup/restore, relocation and old archives, clone, package | NOT_RUN |
| G5 safety | Authorized synthetic scope; effective boundary | No unauthorized source access/egress/effects, secret/package sentinel, verified writes, skill and bot controls | NOT_RUN / blocker for automation |
| G6 performance/quality | Safe validated profiles, fixed test set | Actual context/GPU/latency, quality-adjusted token A/B, coverage and idle compute tradeoff | NOT_RUN |
| G7 release | Applicable G1–G6 PASS and existing repo CI PASS | Reviewed release artifact, hashes/licenses, support matrix, user guides and recovery drill, no open P0 in released scope | NOT_RUN |

Optional features can be withheld/disabled instead of blocking independent Engram functions; document actual supported profiles. No release/merge without separate owner approval. `UNKNOWN`, `BLOCKED`, `NOT_RUN`, partial coverage are not PASS. If baseline changed, refresh relevant evidence rather than blindly applying this plan.

## 2. WP0 — isolated pre-RED feasibility and contract freeze

Use disposable Windows x64 standard-user root, synthetic repo/store/KB/documents/test data, no real sensitive content. No destructive production operations. Record OS build, driver, free VRAM/RAM/committed memory/pagefile/disk, existing ports/PATH, exact binary and dependencies. Do not consume provider quotas; actual external and bot tests require separate opt-in. Capture hashes and logs of supported checks. Do not assume GitHub Windows hosted runners provide RTX 3060.

| Spike | Question | Required procedure / evidence | Tests | Status |
|---|---|---|---|---|
| POC-01 | Current repos and parser contracts | Re-fetch main HEAD; compare file/CLI contract; run existing help/JSON/exit fixtures in isolated baseline | T01,T33,T46,T58,T141 | NOT_RUN |
| POC-02 | Extra Python provider | Verified full portable artifact and legacy embed, SSL/SQLite/venv/pip/native wheels, no registry/junction/host changes; offline restore and path move | T60,T62,T65,T66,T71 | NOT_RUN |
| POC-03 | Hermes PM / Hindsight dependency | Pinned PM launch/update and external interpreter probe, approved private exception; Hindsight wheel/slim metadata and native driver | T74,T75,T76 | NOT_RUN |
| POC-04 | Local model capacity | Ollama standalone, driver, exact context allocation and 4B/9B tool/JSON/long-context tests; compare cache formats and offload | T09,T10,T12,T120,T124 | NOT_RUN |
| POC-05 | PG/pgvector and KB | Compatible binaries, role isolation, local-only Hindsight provider, memory retain/recall, text KB source/locator, backup restore, optional multimedia profile | T13,T14,T53,T110,T137 | NOT_RUN |
| POC-06 | Hooks/native memory | Per-harness install and undo, approved `.engram` paths, local endpoint, candidate/approved bank constraints, no competing auto-write | T15,T87–T91,T113,T129,T130 | NOT_RUN |
| POC-07 | PeerHub actual read/consult | Existing approved synthetic DB, CLI discovery and dry-run; read-only snapshot coverage, request/delivery/feedback mapping; no offset/store mutation | T20,T77–T79,T92–T99 | NOT_RUN |
| POC-08 | Security boundary | Explicit env/cwd/ACL/auth/egress, direct endpoint and shell bypass probes; untrusted source fixture; no credentials leaked | T23,T24,T80,T81,T104,T113,T136 | NOT_RUN |
| POC-09 | Staging/update and migration | Backend candidate model preservation, supported Hindsight reembed/KB generation, interrupted stage, old rollback | T49–T53,T137 | NOT_RUN |
| POC-10 | Scheduler and cancellation | Native async operations, foreground arrival during sleep, measured nonpreemptible work, CPU/GPU admission | T125–T130,T140 | NOT_RUN |

Freeze exact proposed CLI syntax, schema version/digest serialization, typed enums and error mapping after the corresponding spike. Use exact pinned commands and capabilities; do not write executable tests against invented API fields. If a required POC fails, document unsupported feature and redesign or disable. Proof-of-concept is not production implementation. A later implementation may begin pure contract RED tests while unrelated hardware spikes remain open; dependent tests wait for facts.

### 2.1 Required baseline artifacts (not yet produced)

- `artifact-lock` with upstream version, URL, digest/signature evidence, arch/ABI, license, dependencies, release channel, exact capability result and managed footprint; separate software/model and index fingerprints.
- `runtime-profile` with exact GPU/model/cache/context, resource limits, benchmark dataset and threshold; no generic VRAM claims.
- `source-capability` per source/harness: version, allowed paths, read/import mode, event types, stable ID, cursor/lineage, coverage, known gaps, consent model, rollback of hook install.
- `vendor-contract` pinned API/CLI request/response examples from synthetic fixture, operation status/idempotency, supported scopes, permissions and failure semantics; no real credentials.
- `baseline-regression` existing command behavior and CI result, package manifest and root/environment footprint, before/after hashes.
- `security-policy` approved principal/scope/capture/retention/egress and actual enforcement evidence, default deny. No broad user files enrolled yet.

## 3. Dependency and PR plan

| WP | Repository / proposed code | Prerequisites | Output | Test groups |
|---|---|---|---|---|
| WP0 | Design/isolated PoC; no production changes | G0 review | Pins, feature support, evidence, contract fixture | T10,T13,T74,T75,T141 + spikes |
| WP1 | Engram core registry, version discovery, legacy adapter | POC-01/02 | Pure registry and selection planning, state schema, discovery | T58–T60,T64 |
| WP2 | Engram `engram python` CLI, provider/install/run/use/pin | WP1 | Additional optional interpreter/venv binding, no host effects | T61–T66 |
| WP3 | Engram runtime transactions, references and relocation | WP2 | Update/repair/rollback/backup/remove integration | T37,T67–T73 |
| WP4 | Engram AI wrapper/profile/manifest/supervisor/model planner | WP3 (legacy unaffected) | Optional installation and integrated lifecycle, Ollama inventory | T01–T08,T33,T38–T49 |
| WP5 | Engram local agents, Hindsight/PG, model and bank adapter | WP4 + POC-03/04/05/06 | Validated native runtime, memory and model generations | T09–T19,T34–T35,T50–T53 |
| WP6 | Engram tool bridge and PeerHub existing CLI importer | WP5 + POC-07 | Approved delegation and read-only historical capture | T20–T22,T36,T76–T80,T82,T92–T99,T149 |
| WP6b | PeerHub (separate optional PR) generic Activity Export | Owner review + read-interface gap proof | Versioned scoped cursor/read-only export, no Hindsight deps | T94–T98,T99; existing PeerHub CI |
| WP7 | Engram source registry/collector/ledger/KB/proof/invalidation | WP5/6 | Authorized source import, cross-source linkage, memory trust | T87–T91,T100–T119,T142,T143,T146,T147 |
| WP8 | Engram Context Manager, admission, Sleep Engine and skill lifecycle | WP7 + POC-10 | Budget/compaction, one consolidation writer, local idle jobs | T120–T134,T144,T148 |
| WP9 | Engram cross-cutting security, lifecycle, telemetry and release | WP1–WP8 | Recovery, scope safety, measurements and final artifacts | T23,T24,T26–T32,T54–T57,T81,T83–T86,T113,T135–T140,T145,T150 |
| WP10 | Optional media, messenger, extra graph projection | Measured need and G5/G6 | Explicit opt-in, no core dependency | T25,T108 plus feature-specific gates |

WP6b is not a prerequisite for useful Phase A collection, but production claims of complete late-event incremental PeerHub coverage require proven contract. A separate repository/branch must be approved; no changes to PeerHub core/bridge state machine merely for export. Engram main must remain untouched during feature development. Proposed branch names `design/local-ai-pre-tdd`, `feat/multi-python`, `feat/local-ai-runtime`, `feat/activity-memory`, `feat/context-sleep`, PeerHub `feat/activity-export`; illustrative only, no branches created. Avoid a single giant PR. Use synthetic fixtures and pin inter-repo contract versions. Release number follows existing repository SSOT, not an invented bump.

## 4. Ordered RED sequence (plan, not executed)

1. **Invariants first:** absent optional modules, schema validation, root containment, legacy command parser, no writes or downloads on read-only paths (T01–T06, T38–T44, T58–T60, T64). Preserve existing tests byte/exit semantics where contractual.
2. **Runtime and lifecycle pure planning:** selection conflicts, dependency DAG, artifact identity, ownership, immutable generations, lock order, parent/child state, plan and approval hash (T37, T45–T49, T61–T73). Then fault seams and Windows probes. No actual provider in unit tests.
3. **Service and adapter boundaries:** fake Ollama/Hindsight/PeerHub and typed tool runner, deterministic outputs, timeout, no host fallback; actual local dry-run and GPU gates later (T08–T22, T33–T36, T74–T82). Validate native plugin interoperability and explicit local providers.
4. **Data contracts:** enrollment, event natural keys, exact correlation, per-stream/sequence watermarks, late settlement/outcome, restore lineage, page and outbox crash seams, consent and source coverage (T87–T106,T146,T149). Synthetic SQLite fixture only. For proposed PeerHub export use source-owned read interfaces and compare DB before/after. Do not fake proof of unimplemented export.
5. **Knowledge and memory:** original locators, KB revision, parser bounds, independent trust/verification, conflict/temporal semantics, scoped bank and candidate/approved filter, hybrid recall and invalidation/rebuild (T107–T119,T137,T142,T143,T147). Real provider contract after POC. Scope-specific adversarial fixtures.
6. **Context/resource:** capacity versus advertised max, token budget, reserve and pinned facts, cache namespace, lease dependency and foreground admission (T120–T125). Use deterministic fake tokenizer/backend first, actual GPU after validated model profile.
7. **Sleep and skills:** disabled/eligible state, manual run, interrupt/checkpoint, retry and ambiguous effect, consolidation toggle and single writer, proof/skill promotion, stale candidate, local-only preparation (T126–T136,T144,T148). Fault injection at each durable boundary. Native async operations tested with synthetic docs.
8. **Cross-product and recovery:** mixed lifecycle, copy vs move, backup cut, old archive, DB/index generation, package secret sentinels, security bypass, quality/usage coverage, end-to-end local task/approved fake external/recall (T23–T32,T50–T57,T83–T86,T135–T140,T145,T150). Existing Engram CI full suite and separate PeerHub CI if exporter changes.
9. **Opt-in live and optional:** real RTX 3060 resource benchmark, actual provider calls only when authorized, messenger test bots and supported multimedia. No actual user credentials in fixtures; no unsupported feature labeled passing.

For each RED: define Given/When/Then from catalog, explicit fixture and oracle, negative cases and fault injection, expected fail for missing behavior, then smallest implementation, refactor without loosening invariants. No copying code into tests to mirror bugs. Compare source/manifest/DB hashes and authoritative rows, not just exit 0. Test matrix is a minimum; add tests for discovered behavior with unique IDs and requirement mapping. Test state records `NOT_RUN/PASS/FAIL/BLOCKED/SKIPPED_WITH_REASON` and environment/version/receipt; NOT_RUN not PASS. Fault harness uses fake clock/process/tokenizer and local temporary SQLite/PG where applicable, no real account or network. Avoid relying on wall-clock sleeps for unit tests; injectable time/lease/fault seams. For concurrency repeat deterministic barriers then bounded stress. No actual test file is included to honor pre-TDD stop.

## 5. Recursive MECE and interaction matrix

Separate orthogonal axes rather than explode all combinations. Cover pairwise plus high-risk Cartesian combinations with explicit oracles. Review each row both vertically (requirement → ADR/contract → tests → owner) and horizontally (component responsibilities, shared state and lifecycle interactions). Requirements.csv links each acceptance case to primary R ID; secondary cross-cutting links are in this document and ADRs. Test IDs T01–T86 retain earlier scope; new T87–T150 extend it, not replace earlier tests.

| Axis | Partition | Required interaction tests |
|---|---|---|
| Install/profile | absent / partial / runtime / agent / memory / full / corrupt / legacy collision | Every lifecycle operation × absent/installed/corrupt; no optional downloads |
| Runtime | default / extra / exact pin / vendor-private / missing / incompatible | update, move, remove, app vs task, rollback |
| Source | disabled / approved metadata / approved content / revoked / inaccessible / unsupported | source revision, replay, restore, scope, parser failures |
| Collection | new / replay / revised / late / conflicting / ambiguous / lost watch / restored | no omission/duplicate, correction and coverage |
| Memory | type and scope independent; trust candidate/verified/proven; active/quarantined/revoked/superseded/conflict; projection pending/ready/unknown | each trust × scope × query and invalidation, observation/skill gating |
| Context | exact capacity / conservative estimate / unknown; within / over budget | preserve instructions, required refs, no hidden truncation |
| Resource | foreground / background / queued / exhausted / unknown / suspended | priority, nested calls, wake, cancellation, crash |
| Job | pending / executing / ack pending / done / retry / reconcile / failed / revoked | lease expiration, crash and restore fence |
| External | offline / connected-local / cloud-assisted; authorized / denied / stale approval; delivered / partial / uncertain / refused | no bypass, no automatic repeat, no false success |
| Lifecycle | preview / apply / partial commit / rollback / resume; move / clone / restore | each permanent data asset protected, no false success, only prior services restart |
| Data | original / derivative / ephemeral / secret; local / external | backup/restore/export/GC and retention policy, source availability |

High-risk must test explicitly: revoked scope × stale approved cache × linked KB; PeerHub restore × late outcome × page retry; model update × pending sleep/retain × crash; encoder migration × old writer × backup restore; vendor PM × selected project Python × PeerHub credentials; absent AI × legacy update/repair/uninstall; partial profile × unsupported Hermes 64K × memory outage; cloned install × copied bot/schedule; malformed source × parser limits × GPU pressure. No state transitions omitted merely because rare. Use coverage report, not claim all Cartesian cases tested before implementation.

## 6. Benchmark/evaluation protocol

| Metric | Baseline/threshold to freeze | Status |
|---|---|---|
| External requests without approval | 0 in adversarial instrumented suite | NOT_RUN |
| Original / selected verified-memory data loss | 0 in update/move/restore fault suite | NOT_RUN |
| Required evidence and approved memory provenance | 100% for hard-required cases | NOT_RUN |
| Retrieval gold Recall@k | initial ≥90% goal, stratified language/exact/graph | NOT_RUN |
| Local/context correctness | no hard constraint dropped; 64K Hermes actual and acceptable quality | NOT_RUN |
| Interactive GPU stability | no OOM/deadlock in supported profiles, measure P50/P95 | NOT_RUN |
| Foreground delay during sleep | choose measured P95 bound with owner before release | NOT_RUN |
| Source coverage and lag | by source/range and gap; no fabricated completeness | NOT_RUN |
| Idempotency and correction | duplicate approved logical effects 0 in suite, late outcome reflected | NOT_RUN |
| Verified task success | baseline minus at most 5 percentage points initial proposal, no hard safety loss | NOT_RUN |
| External token savings per verified success | 30% initial, 50% target, 70% stretch hypotheses; coverage required | NOT_RUN |
| Sleep on/off | matched repeated workloads, local compute cost, memory usefulness, foreground overhead | NOT_RUN |

Prepare 60 task gold set (15 factual, 15 document, 15 code/test, 10 memory/conflict, 5 high-risk). Expand with 100–300 tasks, bilingual, mixed code, difficult contexts, new/repeated, cold/warm. Record exact Git/model/tokenizer/index/skill versions and data scope. Use source-grounded pass criteria independent of model answer. Include failed tasks and retries in external token totals; normalize provider usage using attributable measurement only, unknown coverage explicit. Provider quota/price not converted one-to-one. Sleep baseline off vs on uses same source corpus and policy; measure processing cost, error propagation, actual reuse and foreground delay, no sleep benefit asserted in advance. Report confidence intervals, sample sizes, failed cases and limitations; thresholds agreed before observing optimization results. External tests only opt-in and budgeted. Actual hardware local, not fake CI GPU. Release must show regression, security, restore and supported profiles, not just aggregate score.

## 7. Operator runbooks (proposed behavior)

| Scenario | Procedure | Never do |
|---|---|---|
| First setup | Existing Engram terminal `ai setup`; review selected profile, approved artifacts, space; confirm. Validate `ai doctor`, then explicitly enroll sources, enable sleep/bot if desired. | Install all histories or other runtimes automatically. |
| Routine updates | `engram update --check`; review installed component/model and Python series, source freshness; `engram update` confirmation or `-y` safe changes only. Review partial/migration plans. | Pull mutable tag over only recoverable model or replace encoder without migration. |
| Python change | `engram python list/check`, install selected series, `use` child shell or `run`; keep project pin explicit. | Global PATH/py registry or overwrite existing user pin. |
| Collector gap | `ai memory status/sources`; inspect source coverage and consent; pause affected adapter, resnapshot/reconcile explicit cursor, replay idempotently. | Re-run external AI to recover missing transcript or advance PeerHub Offset. |
| Wrong memory | Review source and scope; invalidate claim/revision and dependent cache/projections; correct from evidence; verify new revision. | Delete originals or auto-promote conflicting observation. |
| Sleep backlog / interactive delay | `ai sleep status`, pause, observe GPU queue, reduce batch or CPU-only safe profile; resume after approved checks. | Force kill unrelated process or claim preemption if unsafe. |
| Hindsight unavailable | Continue ordinary local chat; show memory-dependent limitation; retain durable queue; repair exact generation, verify DB and source before resume. | Treat absent result as personal fact or cloud fallback. |
| Move/restore | Quiesce, verify backup manifest and offline pack; move full tree; `engram relocate` preview/`--apply`; verify path, DB, models, cursor lineage, no duplicated bot. | Copy active database or bulk rewrite past conversation paths. |
| Ambiguous external call | Inspect original PeerHub receipt and request ID, reconcile using supported flow; ask owner if another execution required. | Auto issue new ID / duplicate charge. |
| Uninstall | Plan owned program removal, keep memories/models/skills/backups by default, verify data export; purge only distinct approved scope. | Remove whole AI root or shared PeerHub/user project. |
| Security incident | Stop affected owned service/jobs, revoke scope and credentials through appropriate vendor, preserve protected evidence, review egress and derived invalidation, restore verified generation. | Publish raw logs or overwrite source evidence; resume unsafe automation. |

## 8. Final pre-TDD checklist

- [x] Existing Rev.05 source reopened; prior IDs retained and all follow-up decisions incorporated into English spec.
- [x] Separate native source records, knowledge, memory, skills, policy/verification metadata, context and resource control; no mandatory additional graph/vector DB or SecondBrain.
- [x] Define proposal CLI/API contracts, scope/consent, event/lineage/idempotency, failure and rollback, ownership and test acceptance.
- [x] Document PeerHub current vs proposed extension, independent deployment and no core Hindsight dependency.
- [x] Define 150 acceptance cases and mapped top-level requirements; all NOT_RUN; no claims of implementation.
- [ ] Owner review and confirm unresolved policy/CLI and actual sources.
- [ ] Revalidate repository HEAD and exact version/hash/license/artifact locks.
- [ ] Resolve applicable POC blockers on actual standard-user Windows/RTX 3060; freeze measured thresholds.
- [ ] Freeze contract fixtures and begin RED for the relevant work package.

Status: specification ready for design review and pre-TDD feasibility, not ready for unconditional implementation of all profiles. This package stops before test-code authoring and does not initiate repository changes.
