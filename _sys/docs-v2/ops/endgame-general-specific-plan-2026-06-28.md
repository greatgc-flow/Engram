# Endgame General-Specific Plan
> Status: design | Updated: 2026-06-28 | Scope: implementation-ready planning only
> Sources: `user/requirements.md`, `00-MANIFEST.md`, `ops/backlog-5whys-consensus-2026-06-26.md`, local cx audit, ag cross-review 2026-06-28.

## 1. Target Outcome

PortableDev should converge on a no-code, composable, MECE architecture where:

- directives describe behavior and authority;
- JSON config declares all paths, environment variables, constants, ranges, mappings, feature toggles, and General-Specific connection points;
- source implements deterministic input/output engines only;
- specific peer or workspace differences are data-driven deltas behind a common interface;
- runtime state is lazy, visible, bounded, and never confused with normative docs or source.

This plan stops immediately before source implementation. Its completion means the next implementation pass can be executed as small Ask Transaction slices with explicit schemas, file ownership, tests, and traceability already defined.

## 2. Non-Goals

- Do not rewrite `hub.py` or adapters in this planning pass.
- Do not delete active runtime stores such as `.ai/`, `_sys/env/`, peer auth/config homes, or `_archive/`.
- Do not move root config files listed in `00-MANIFEST.md`.
- Do not convert accepted peer permission debt into silent safety claims. The ag filesystem sandbox gap remains explicit until upstream support exists.

## 3. Architecture Contract

### 3.1 Three-Lane Separation

| Lane | Owns | Must not own | Primary files |
|---|---|---|---|
| Directives (historical; `_sys/ai/` removed in Engram/peerhub separation) | human rules, temporary runtime rules, lessons | paths, model facts, executable branching | `user-directives.md`, `runtime-directives.jsonl`, `knowledge/` |
| Config (historical; `_sys/ai/` removed in Engram/peerhub separation) | topology, paths, constants, ranges, schemas, connector maps | prose policy, hidden source defaults | `_sys/ai/*.json`, `config/environment.json`, `_sys/paths.json`, `_sys/runtimes.json` |
| Source | deterministic validation, dispatch, rendering, execution, error surfacing | peer identity policy, magic values, normative prose | `_sys/core/`, `_sys/cli/`, `_sys/checks/` |

Rule: if a value can vary by workspace, peer, platform, model, risk level, timeout, or policy tier, it belongs in JSON. If a behavior has exact input/output and can be tested without model judgment, it belongs in source.

### 3.2 General-Specific Layers

| Layer | Purpose | Storage |
|---|---|---|
| Global common | reusable outside any single workspace | `_sys/ai/common/`, `_sys/templates/`, future `common_registry` config node |
| Workspace base | first workspace creation skeleton | `_sys/templates/workspace-base/` and `_sys/templates/workspace/` |
| Workspace local | resources only valid inside one workspace | `workspace/<name>/specific/`, `workspace/<name>/_state/` |
| Peer specific | peer deltas only, same pattern for every peer | `specific/{peer}.md`, `orchestration.json.hub_nodes[].profiles`, `peers.json` |
| Runtime | generated state, caches, sessions, logs | `.ai/`, `_sys/*/health.json`, peer config caches, `_sys/data/temp/` |

General may define interfaces. Specific may provide values or stricter constraints. Specific must not bypass General invariants.

### 3.3 JSONized Connection Points

Every General-Specific edge needs a JSON declaration:

- `peers.json`: installation/provider/sys-subdir resolution.
- `orchestration.json`: logical node, profile, capability class, session mode, adapter class.
- `routing-config.json`: deterministic profile classification and fallback rules.
- `model-registry.json`: vendor model facts only.
- `protocol.json`: governance, health thresholds, communication policy, runtime directive limits.
- `infra.json` / `environment.json` / `paths.json`: path, env, and portable tool locations.
- New planned schema set: connector registry for workspace common, base-template binding, and workspace-local overlays.

## 4. Endgame Work Plan

### Phase 0: Baseline Freeze

Objective: create a trustworthy inventory before changing behavior.

Deliverables:
- git status snapshot;
- `peer-status`, `profile-validate`, `check_docs_mece.py`, and config validator results;
- runtime cleanup candidate list split into delete, keep, archive, and human-only purge.

Acceptance:
- no tracked file is deleted unless explicitly mapped to a manifest/proposal outcome;
- ignored runtime stores are classified before any cleanup;
- failures are reported with stack trace or exact command output.

### Phase 1: Documentation Truth Reconciliation

Objective: remove ambiguity between living, design, planned, implemented, and historical statements.

Docs to update:
- `00-MANIFEST.md`: every active design doc listed.
- `MOC.md`: lazy-load route to this plan.
- `general/protocol.md`: remove or mark non-existent commands such as `update-config`.
- `general/learning.md`: clarify `consensus_finalize` as planned unless a real connector exists.
- `_exceptions/README.md`: close entries once the source/config/doc evidence is verified.

Acceptance:
- every command referenced in docs exists or is labeled planned;
- every `DONE` claim has code/config/test evidence;
- every `planned` claim has an owning roadmap slice.

### Phase 2: Config Taxonomy and Schema Plan

Objective: define exactly where every variable class belongs before implementation.

Deliverables:
- schema ownership table for `protocol.json`, `orchestration.json`, `peers.json`, `routing-config.json`, `model-registry.json`, `infra.json`, `environment.json`, `paths.json`, and `runtimes.json`;
- duplication matrix showing which fields must not appear in more than one config;
- strict-load policy: normative config parse failures abort loudly; telemetry parse failures may degrade with visible warning.

Acceptance:
- no field category has two authoritative owners;
- every range/type enum has a schema location;
- all defaults are either schema defaults or explicit config values, not source literals.

### Phase 3: Path and Environment Externalization Plan

Objective: remove source-level path/env assembly except bootstrap discovery.

Deliverables:
- path dictionary contract for root, sys, env, tools, state, common, templates, workspace-local, and runtime;
- host-env adapter contract for unavoidable host variables such as `LOCALAPPDATA`;
- relocation test matrix for SUBST drive changes, spaces, parentheses, Unicode paths, and fresh checkout.

Acceptance:
- source may discover the config root, then must resolve paths through config;
- no peer-specific path is assembled from implicit naming conventions;
- junction targets are declared in config and verified by `virtualizer.py`.

### Phase 4: Common Workspace and Template Plan

Objective: support both cross-workspace reuse and first-workspace creation.

Deliverables:
- `common_registry` design for `_sys/ai/common/` agents, skills, MCP catalog, statusline schema, and tool registry;
- base template contract for `_sys/templates/workspace-base/`;
- workspace-local overlay contract for `workspace/<name>/specific/` and `workspace/<name>/_state/`;
- creation flow: select template, apply path map, materialize workspace-local config, register junctions, validate.

Acceptance:
- a new workspace can be described entirely by JSON plus templates;
- common assets are referenced by registry keys, not copied by convention;
- workspace-local state is never promoted to global common without review.

### Phase 5: General-Specific Refactor Plan

Objective: make peer-specific implementations share the same pattern.

Deliverables:
- adapter capability schema: `transport`, `session`, `permissions`, `context_policy`, `status_probe`, `runtime_home`, `mutation_profile`;
- peer delta checklist: every peer must fill the same fields or explicitly declare unsupported;
- exception register for real asymmetry, including ag PTY and filesystem sandbox limitations.

Acceptance:
- no core dispatch branches on peer ID except through adapter registry lookup;
- peer-specific behavior is data plus adapter method, not scattered conditionals;
- exceptions are visible, testable, and documented.

### Phase 6: Traceability and Validation Plan

Objective: make doc-source-config linkage auditable.

Deliverables:
- traceability matrix pattern: requirement ID -> docs section -> config node -> source module -> check/test;
- `traceability_map.json` ownership rules;
- release gate checklist: docs MECE, profile parity, config strictness, path existence, anchor integrity, hardcoded path scan, INV-19 scan.

Acceptance:
- every implementation slice has a row before code changes;
- every row has at least one validation command;
- failures are surfaced to the user with exact file/path/stack context.

### Phase 7: Lazy Resource and Error Visibility Plan

Objective: conserve tokens and resources while making failures obvious.

Deliverables:
- lazy-load policy per store: docs, handoff, mailbox, health, directives, lessons, model facts, peer caches;
- resource cleanup policy: leases, locks, temp dirs, logs, peer runtime caches;
- error visibility contract: fatal exceptions print category, peer, action, root exception, environment snapshot, and 5-Whys prompt.

Acceptance:
- health checks remain zero-token;
- peer asks include only required context sections;
- cleanup never removes active runtime state unless the state has an expiry rule and validation pass.

## 5. Cleanup Policy

### Delete Automatically When Requested

- root-level transient logs (`hub.log`, `pytest.log`, similar);
- `tmp/` children, pytest local temp dirs, and synthetic write-probe files;
- empty untracked accidental peer directories;
- untracked scratch folders with no manifest, no config reference, and no active process lock.

### Keep

- `.ai/` active room state;
- `_archive/` durable history;
- `_sys/env/` reinstallable but currently active runtime;
- peer auth/config homes unless running a full cleanup tier;
- tracked docs, source, configs, templates, and schemas.

### Human-Only Purge

- `Garbage/`;
- accepted/rejected/expired proposal archives;
- any tracked file;
- any runtime cache that may contain auth, conversation continuity, or paid-usage state.

## 6. Known Gaps Found in This Review

| Gap | Impact | Required pre-implementation action |
|---|---|---|
| `general/protocol.md` references `update-config`, but `hub.py` has no such action | doc-command drift | either add a roadmap item or relabel as planned |
| `general/learning.md` references `consensus_finalize`, while protocol docs say no dedicated finalizer exists | lifecycle ambiguity | define connector status and owner |
| Config schemas are described but not uniformly enforced at every entry point | config drift can recur | define strict-load primitive and schema gate |
| `traceability_map.json` exists but is not yet the mandatory planning gate | weak bidirectional linkage | require traceability row before source edits |
| ag lacks enforceable filesystem sandbox flag | safety debt | preserve explicit exception and use review/read-only profiles |
| cleanup commands can hit sandbox permission errors | operator surprise | cleanup tooling must report skipped paths and rerun guidance |

## 7. Acceptable Hardcoding Exceptions

Hardcoding is acceptable only for:

- bootstrap discovery of the repository root and first config file;
- JSON schema draft identifiers and schema version compatibility guards;
- universal encoding defaults such as UTF-8;
- low-level platform constants that cannot be configured safely;
- fail-closed emergency messages when config loading itself is unavailable.

Every exception must include a comment or traceability row explaining why JSON configuration would create a bootstrap loop or safety risk.

## 8. Completion Loop

Repeat until no open gaps remain:

1. Observe: run status, docs, config, path, and git checks.
2. Classify: map every finding to docs, config, source, runtime, template, or archive.
3. Plan: update this design or its successor with exact artifacts and acceptance gates.
4. Cross-review: ask at least one non-author peer for architecture/risk review.
5. Reconcile: convert agreed findings into manifest, MOC, traceability, or backlog updates.
6. Stop line: do not implement source until the affected slice has schemas, tests, and traceability.

This plan is complete when every phase above has explicit artifacts, every known gap has an owner, and the next action is a bounded implementation slice rather than more architecture discovery.
