> **Recovered 2026-09-08** from an orphaned, never-pushed commit (`52c8fe8`, 2026-08-19) sitting in a stale local clone at `P:\workspace\Engram` (91 commits behind origin, otherwise identical to this repo's history). The 4 original source files it archives no longer exist anywhere (deleted on the assumption this commit's push had succeeded, which it never did) -- this recovery is the only remaining copy. Item 2 (the Round-1 separation proposal) predates and is superseded by the ratified reconciliation plan the separation was actually executed against; kept here as historical provenance for how that plan's thinking evolved, not as current guidance.

# Workspace Scratch Archive (2026-08-19)

This document archives scratch/proposal/test files migrated from `P:\workspace\` on 2026-08-19.

---

## 1. diag_composition_debate.md

Original path: `P:\workspace\diag_composition_debate.md`

# Diag Composition MECE Debate & Convergence

## 1. 목적 (Purpose)
Failover, Handoff, 로드밸런싱 등 자율 협업의 기반이 되는 시스템 가시성 확보. 각 피어의 상태와 컨텍스트를 MECE(Mutually Exclusive, Collectively Exhaustive)하게 구조화하여 `config_reality` 검증 및 진단에 활용.

## 2. MECE 구조화 상세 (Structure)

### 2.1. Peer & Profile (피어 및 프로필 계층)
- **대상**: CC, CX, AG, CA 등 `orchestration.json`에 정의된 노드
- **상태 (Status)**: ACTIVE, BLOCKED, QUARANTINED
- **Capability Class**: `trusted_ipc_mutation`, `restricted_workspace_mutation` 등 권한 수준 (TDD 및 권한봉쇄 반영)
- **프로필 (Profiles)**: standard, effort, deepthink, 3p 등 (실제 가동 가능한 프로필만 표시)
- **Routing State**: `eligible`, `blocked` (로드밸런서 판단 기준)

### 2.2. Model & Options (모델 및 옵션 계층)
- **선언 모델**: `orchestration.json` 상의 모델 (예: claude-opus-4-8, gpt-5.5, Gemini 3.1 Pro)
- **실측 모델 (Empirical)**: `check_cli_reality.py`에 의해 검증된 실제 가동 모델 및 응답성 (verified_local 등)
- **CLI Options**: 안전모드, 권한 스킵 등 플래그 상태
- **Context Window**: 모델별 최대 런타임 토큰

### 2.3. Usage & Quota (사용량 및 쿼터 계층)
- **Session Usage**: 현재 세션에서 소모된 토큰/비용
- **Daily/Monthly Quota**: Rate limits 및 하드 리밋 도달 여부
- **로드밸런싱 지표**: 비용 효율(Cost Tier) 및 가용성 기반 트래픽 분배 가중치 (Token limits 초과 시 타 피어 자동 Failover)

### 2.4. Session & Context (세션 및 컨텍스트 계층)
- **Session State**: RUNNING, IDLE, ERROR
- **Context Preservation**: 단기/장기 메모리 유지 상태 (`memory` type: session, short-term)
- **Handoff Readiness**: 타 피어로 컨텍스트 이전 가능 여부 및 페이로드 크기
- **Reconciliation Overlay**: 선언(Declaration) vs 실측(Empirical) 간의 drift 내역

## 3. 선순환 닫힌 피드백 루프 (Closed Loop Feedback)
1. **탐지 (Sense)**: `check_cli_reality.py`가 주기적/세션시작 시 4-layer probe 수행 (version, models, permissions, quota)
2. **진단 (Diagnose)**: Diag 구성 방안에 따라 Drift나 에러 탐지 시 Failover 판단.
3. **격리/레슨 (Quarantine/Learn)**: 에러 발생 시 `.ai/lessons/proposals`로 자동 제안 (G 루프)
4. **적용 (Act)**: Handoff 또는 로드밸런싱 수행, 사용자 재가 대기 (H 루프)

## 4. 전체 요약 (Summary)
Diag는 시스템의 **선언적 기대치**와 **실측 현실**의 차이를 좁히는 `Reality Reconciliation`의 뷰어입니다.
General한 시스템 헬스 체크부터 Specific한 토큰 사용량 및 CLI 권한 검증까지 투명하게 제공하며, 쿼터 소진(마치 이번 CC 토큰 고갈 사태처럼) 시 즉각적인 Failover와 Handoff를 가능하게 하는 핵심 인프라입니다.

---

## 2. engram_peerhub_separation_proposal.md

Original path: `P:\workspace\engram_peerhub_separation_proposal.md`

# Engram / Peerhub Full-Separation Proposal (Round 1)

Status: **proposal only — no implementation authorized by this document**  
Prepared: 2026-08-18  
Target boundary: **Engram owns the portable Windows development environment; Peerhub owns peer/profile communication and coordination.**

## 1. Recommended end state

Engram should stop being a second collaboration engine. It should install and expose AI developer CLIs, manage the portable Python/runtime/tool environment, provide environment diagnostics and lifecycle commands, and optionally install the independent `peerhub` package. Peerhub should own all non-interactive peer dispatch, fan-out, adapter/profile configuration, process/session supervision, health/quarantine, routing, and truthful coordination telemetry.

The legacy `_sys/core/hub.py` and `_sys/cli/diag.py` should ultimately be **deleted**, not moved into a live `_archive/` package and not kept with a `DEAD` header. Git history is the appropriate source archive; retaining half a megabyte of importable dead implementation would keep dependency scanners, tests, and future maintainers uncertain about which engine is authoritative. Historical governance documents and a checksum-indexed snapshot of legacy runtime state should be archived separately.

Deletion cannot be the first step. Although `hub.bat` and `diag.bat` now delegate to Peerhub, direct callers still make `hub.py` load-bearing. The safe plan is: fill the few real Peerhub gaps, migrate or retire every direct caller, quiesce legacy state, archive evidence, then delete the legacy cluster and rewrite the Engram documentation/configuration in the same cutover.

The formal `collab_rate`/R:6–R:10/consensus/Final Call/leader/terminal-duty system should **not** be ported. Its removal is an intentional scope decision, not a missing Peerhub feature.

## 2. Verified evidence and limits

| ID | Finding | Evidence | Consequence |
|---:|---|---|---|
| 2.1 | `_sys/cli/hub.bat` and `_sys/cli/diag.bat` delegate to `_sys/cli/peerhub.bat`; they do not call the Python legacy files. | `[empirical_probe: source inspection]` | The branded aliases have already begun the cutover. |
| 2.2 | The installed package reports Peerhub 0.1.7, and `python -m peerhub.cli --help` exposes only `status`, `diag`, `broadcast`, `ask`, and `statusline`. | `[cli_live]` | Legacy actions are not silently handled by Peerhub. |
| 2.3 | `_sys/runtimes.json` declares Peerhub 0.1.7, while `_sys/tools/peerhub/.install_manifest.json` still declares/tag-pins 0.1.0. | `[empirical_probe: file inspection]` | Repair the generated receipt/provenance; do not downgrade the runtime catalog. |
| 2.4 | `_sys/cli/msg.bat`, `console_runner.py`, status wrappers, hooks, and checks invoke `_sys/core/hub.py` directly. | `[empirical_probe: call-site search]` | `hub.py` is still load-bearing even though `hub` itself is narrowed. |
| 2.5 | `.ai/state.json` and `.ai/leases.json` were written on 2026-08-18; mailbox/history files also have August activity. Consensus files exist but the newest observed consensus record is from 2026-07-28. | `[empirical_probe: filesystem metadata]` | Treat leases/session state as active until quiesced; treat voting state as historical, not as a current feature to migrate. |
| 2.6 | OS process and scheduled-task enumeration was denied in this execution context; repository search found no task registration code. | `[empirical_probe]` | Scheduled-task absence is **TEST NEEDED**, not proven. Require a human/admin read-only check before deletion. |
| 2.7 | Peerhub 0.1.7 contains a catalog of legacy actions, but only `ask`, `ask-all`, and `ask-coordinator` translate; other known actions return “not backed.” | `[empirical_probe: Peerhub source inspection]` | Do not mistake name recognition for feature parity. |
| 2.8 | Peerhub has no formal voting/consensus engine. `broadcast` is sequential fan-out with completion dispositions. | `[empirical_probe: Peerhub source inspection]` | This matches the desired simpler boundary; document consensus as intentionally retired. |
| 2.9 | Current Peerhub adapters expose only `ag.standard`, `cc.standard`, and `cx.standard`, accept prompts on argv, and the AG adapter is declared as PIPE-based. | `[empirical_probe: Peerhub source inspection]` | Multi-profile support, safe prompt-file/stdin input, and an AG PTY canary are prerequisites for migrating current Engram callers. AG PTY behavior remains **TEST NEEDED**. |
| 2.10 | Peerhub telemetry/statusline code still searches Engram `_sys` paths (including `P:` and a hard-coded `D:` path) and emits hard-coded room/leader/quota labels in fallback paths. | `[empirical_probe: Peerhub source inspection]` | Peerhub is repo-separated but not yet configuration/telemetry-independent. Fix this in Peerhub before claiming full separation. |

## 3. Peerhub prerequisite actions

These changes belong in `github.com/greatgc-flow/peerhub`, not in Engram. They should be released before the Engram deletion commit. The concurrently modified `peerhub/telemetry/presenter.py` must not be touched until that unrelated work is integrated.

| # | File path | Action | Reasoning | Risk if wrong |
|---:|---|---|---|---|
| 3.1 | `peerhub/config` or a new documented Peerhub-owned adapter/profile config file | **ADD/EXTEND** descriptors for all supported profiles, executable resolution, environment, argv flags, permission mode, and PTY requirement. Do not import Engram's whole `orchestration.json`. | Engram currently knows profiles beyond `*.standard`; communication configuration must have one owner. | Deepthink/effort/premium routes disappear or run with the wrong model/permission mode. |
| 3.2 | `peerhub/cli.py` and application command input types | **ADD** `--prompt-file` and stdin support with explicit UTF-8 handling and size limits; keep positional prompt for small interactive calls. | Current checks/hooks send large prompts; argv-only transport is fragile on Windows and may expose content in process listings. | Long or non-ASCII calls fail during migration, encouraging direct vendor-CLI bypasses. |
| 3.3 | Peerhub adapter implementations | **VERIFY, THEN FIX IF NEEDED** AG PTY execution and cancellation semantics with an empirical Windows canary. Preserve minimum non-interactive permissions per adapter. | Current local policy says AG requires PTY, while inspected Peerhub code declares PIPE. This is not safe to infer. | AG dispatch can hang or behave differently after legacy console code is removed. |
| 3.4 | `peerhub/telemetry/presenter.py` | **REWRITE IN PEERHUB** after the concurrent telemetry fix lands: remove Engram `_sys`, `P:`, and hard-coded `D:` discovery; accept only Peerhub config/providers and measured observations; render unknown as unknown. | A standalone package cannot depend on one host product's private tree or fabricated fallbacks. | Installing Peerhub elsewhere yields false or host-specific status. |
| 3.5 | `peerhub/telemetry/quota_polling.py` | **REWRITE IN PEERHUB** to use adapter/provider-owned discovery and injectable paths, not a derived Engram portable root. | Quota collection is a Peerhub adapter concern. | Quota polling only works inside Engram. |
| 3.6 | `peerhub/telemetry/statusline.py` and `peerhub/cli.py::_run_statusline` | **REWRITE IN PEERHUB** to remove hard-coded `room-efde`, leader/failover text, synthetic quota/pacing values, and writes into Engram `_sys`. Output to stdout by default; use an explicit Peerhub state/output path if persistence is requested. | Statusline is currently an integration leak in both directions. | The “separated” package still mutates Engram and reports unmeasured facts. |
| 3.7 | Peerhub session/lease application API and SQLite schema | **KEEP/EXTEND NARROWLY** so Engram can query “are Peerhub dispatches using this installation active?” through a stable command/exit code. Do not expose Peerhub's internal DB to Engram. | Engram update/cleanup needs a safety interlock but should not parse `.ai/leases.json` or Peerhub SQLite. | Runtime updates can race active child processes, or Engram becomes coupled to Peerhub storage. |
| 3.8 | Peerhub docs/README/roadmap | **DOCUMENT** the ownership boundary and explicitly list retired legacy semantics: no mandatory consensus, collaboration rate, terminal leader, directives/lessons/proposals governance, generic file locks, or mailbox emulation. | “Not ported” must be distinguishable from “forgotten.” | Future contributors rebuild the legacy engine by accident. |
| 3.9 | Peerhub tests | **ADD** clean-machine tests with no `P:` drive and no Engram tree; profile/PTY/prompt-file/unknown-telemetry tests; an assertion that package code contains no Engram absolute path. | This is the proof that repo separation became runtime separation. | Regressions reintroduce host coupling. |
| 3.10 | Peerhub release metadata | **RELEASE** a new tagged version and produce measured install/canary evidence before changing Engram's pin. | Engram should consume a released boundary, not the mutable checkout. | Engram cutover targets behavior that users cannot install reproducibly. |

## 4. Engram command, runtime, and caller actions

| # | File path | Action | Reasoning | Risk if wrong |
|---:|---|---|---|---|
| 4.1 | `_sys/core/hub.py` | **DELETE AFTER rows 4.3–4.24 and 5.x are complete.** Do not archive executable source in-tree. | It is the duplicate coordination engine; git preserves history. | Immediate deletion breaks consoles, hooks, checks, status wrappers, update safety, and `msg.bat`. |
| 4.2 | `_sys/cli/diag.py` | **DELETE** with the legacy snapshot/quota stack after diagnostics are split. | The public `diag.bat` no longer calls it; its remaining value is legacy peer telemetry. | A hidden direct caller could lose diagnostics; final call-site scan is mandatory. |
| 4.3 | `_sys/cli/msg.bat` | **DELETE.** Migrate legitimate non-interactive calls to the installed `peerhub` command first. | It is the generic back door that keeps all ~90 legacy actions reachable. | Any overlooked script loses its command path. |
| 4.4 | `_sys/cli/hub.bat` and `_sys/cli/hub` | **DELETE** the Engram-branded aliases. During one deprecation release they may print a deterministic “use `peerhub`” error, but they must not remain permanent forwarders. | Complete product separation requires a distinct command namespace. | Existing user muscle memory or automation breaks without one release of notice. |
| 4.5 | `_sys/cli/diag.bat` and `_sys/cli/diag` | **DELETE/RENAME.** Peer diagnostics remain `peerhub diag`; if Engram needs diagnostics, create an environment-only `engram doctor`/`engram diag` that never imports Peerhub. | “diag” currently conflates host health and coordination health. | Environment health may become harder to troubleshoot if no replacement is supplied. |
| 4.6 | `_sys/cli/peerhub.bat` | **MOVE OR REDUCE TO AN INSTALLATION SHIM** under `_sys/tools/peerhub/`; it may only resolve Engram's venv and execute `peerhub.exe`/`python -m peerhub.cli`. Do not expose it as `engram peerhub`. | Installing a separate tool is compatible with Engram's environment role; owning its command API is not. | Removing the only PATH bridge could make the pip-installed executable inconvenient or unreachable. |
| 4.7 | `engram.cmd` | **REWRITE** command dispatch/help: remove `hub`, `peerhub`, peer `diag`, `batch-review`, `collab-rate-gate`, and `set-collab-rate`; retain/install/document environment operations. Resolve this currently untracked file's provenance before editing and update its generator if one exists. | Root CLI should describe only the portable environment. | Editing only a generated output causes regeneration drift; deleting environment subcommands damages the product. |
| 4.8 | `_sys/cli/console_runner.py` | **REWRITE AS A PURE INTERACTIVE PROCESS WRAPPER**: launch the selected installed AI CLI, handle terminal title/exit, and stop writing hub session/health/context/terminal-handoff/lease state. If Peerhub-managed non-interactive coordination is requested, call its public API rather than duplicating it here. | Current direct `hub.py` invocations are a major live dependency. | Console lifecycle regressions or orphaned processes. |
| 4.9 | `_sys/cli/agy_entry.py` | **REWRITE** to consume Engram tool-install config only; remove `.ai/state.json`/hub lifecycle coupling. | Interactive AG launch is an environment feature, not peer governance. | Status/title behavior may break if shared assumptions remain. |
| 4.10 | `_sys/cli/claude_entry.py` | **REWRITE** on the same boundary as 4.9. | Same. | Same. |
| 4.11 | `_sys/cli/codex_entry.py` | **REWRITE** on the same boundary as 4.9. | Same. | Same. |
| 4.12 | `_sys/antigravity/agy-status.bat` | **DELETE OR REPOINT** to a vendor-native environment/version check; do not call `hub.py peer-status`. | Peer status belongs to `peerhub status`. | Users may lose a useful installation-health shortcut if it is simply deleted. |
| 4.13 | `_sys/codex/codex-status.bat` | **DELETE OR REPOINT** as in 4.12. | Same. | Same. |
| 4.14 | `_sys/hooks/archive-data.bat` | **REWRITE** to a deterministic local archive helper or retire it; remove `hub.py archive-file`. | Archiving a file is not peer coordination and needs no Hub. | Existing retention workflows may stop archiving. |
| 4.15 | `_sys/hooks/log-write.bat` | **REWRITE** to a local structured logger or retire it; remove `hub.py append-log`. | Local logging is an Engram concern but the Hub dependency is not. | Logs may silently stop. |
| 4.16 | `_sys/hooks/session-end.bat` | **DELETE/REWRITE** with the simplified console runner; no Hub `end-session`. | Legacy session ownership is being retired. | Cleanup may no longer run at console exit. |
| 4.17 | `_sys/hooks/ctx_save.py` | **REWRITE OR RETIRE.** Remove consensus sweeping, mailbox/blackboard state, `msg.bat ask`, and hub session context. Retain only deterministic local editor/session checkpointing that has a portable-environment use case. | It is currently a hidden collaboration client. | Useful local recovery context could be discarded along with governance state. |
| 4.18 | `_sys/hooks/ctx_end.py` | **REWRITE OR RETIRE.** Remove `thread-new`, `msg.bat`, handoff/mailbox behavior, and direct `claude -p`; any requested AI summary must go through Peerhub's public prompt-file API. | The new rule is one communication boundary, including hooks. | End-of-session summaries may disappear or bypass Peerhub. |
| 4.19 | `_sys/hooks/collab_log.py` and `_sys/hooks/collab-log.bat` | **DELETE.** If environment audit logging is still needed, replace it with an environment-named schema and path. | Names and schema encode the retired collaboration governance. | An unrelated audit consumer could be lost; search readers before deletion. |
| 4.20 | `_sys/cli/batch_review.py` and `_sys/cli/batch-review.bat` | **REMOVE FROM ENGRAM.** If batch multi-model review remains valuable, propose it separately as an optional Peerhub workflow after the base split; do not keep a collab-rate gate. | It is a peer workflow, not portable-environment plumbing. | Users relying on this convenience lose it until Peerhub supplies an equivalent. |
| 4.21 | `_sys/cli/collab-rate-gate.bat`, `_sys/cli/collab-rate-gate`, `_sys/cli/set-collab-rate.bat`, `_sys/cli/set-collab-rate` | **DELETE TOGETHER** after all readers are gone. | The governed scale is explicitly retired. | A residual caller may fail; boundary tests must prove none remain. |
| 4.22 | `_sys/checks/_common.py` | **SPLIT/REWRITE.** Keep generic filesystem/index/worktree helpers. Replace vendor/Hub calls with a small Peerhub subprocess client using `--prompt-file` and `READ_ONLY`; replace `archive-file` with a local helper; remove legacy health-file mutation. | This is the shared route for multiple checks and the best place to enforce the new boundary. | A bad split can break otherwise unrelated Engram checks. |
| 4.23 | `_sys/checks/check_agents.py`, `check_deps.py`, `check_health.py`, `check_portability.py`, `check_risk.py`, `check_versions.py`, and `_sys/cli/git_draft.py` | **REVIEW INDIVIDUALLY, KEEP ONLY ENVIRONMENT PURPOSES.** Where peer analysis is genuinely requested, use the new `_common.py` Peerhub client; deterministic checks should remain local. | These are mixed utilities, not automatically legacy just because they called a model. | Deleting them wholesale would remove useful environment verification. |
| 4.24 | `_sys/checks/self_care.py` and `_sys/checks/sync_docs.py` | **DELETE/RETIRE** proposal-add, lesson governance, and consensus-capsule syncing. Keep any deterministic lint as a separately named check only. | They implement the removed governance layer. | An unrelated documentation sync might be lost if not separated first. |
| 4.25 | `_sys/core/provisioner.py` | **REWRITE** the active-use interlock to call the released Peerhub status/lease API when touching Peerhub; otherwise use process ownership appropriate to the specific runtime. Remove `.ai/leases.json` parsing. | Engram owns safe installs/updates, but not Peerhub storage. | Updating a live executable can corrupt an active session. |
| 4.26 | `_sys/core/scrubber.py` | **REWRITE** cleanup tiers around environment-owned caches. Stop preserving/interpreting `.ai` consensus/quarantine/state/leases as Engram governance. Never delete `.peerhub` without an explicit Peerhub-owned command and user scope. | Cleanup ownership must match data ownership. | User coordination history or live Peerhub data could be deleted. |
| 4.27 | `_sys/core/tidy_temp.py` | **REVIEW/RENAME COMMENTS AND RULES** that assume Peerhub-wide temp ownership; retain only paths Engram can prove it owns. | A portable environment may clean its own temp files but not another product's global state. | Cross-product temp deletion. |
| 4.28 | `_sys/manage.py` workspace initialization paths | **REWRITE** to create generic project/environment scaffolding only. Remove creation of `.ai/common`, peer shadows/junctions, rooms, mailbox, or governance files. A future `peerhub init` owns Peerhub workspace state. | Workspace bootstrapping currently leaks collaboration topology into Engram. | Existing workspace initialization may no longer prepare required portable paths. |

## 5. Legacy implementation and configuration actions

| # | File path | Action | Reasoning | Risk if wrong |
|---:|---|---|---|---|
| 5.1 | `_sys/core/hub_context.py` | **DELETE** with `hub.py`. | Hub-only context assembly. | Hidden imports must be removed first. |
| 5.2 | `_sys/core/hub_error.py` | **DELETE** with `hub.py`; move any generally useful error text into its actual owner. | Hub-only error taxonomy/remediation. | Environment diagnostics may reference its codes. |
| 5.3 | `_sys/core/hub_health.py` | **DELETE**; Peerhub owns peer health, Engram doctor owns installation health. | Avoid two health authorities. | Loss of environment checks if concerns are not split. |
| 5.4 | `_sys/core/hub_interceptor.py` | **DELETE.** | Pure collab-rate/consensus interception. | None after gates are removed; residual imports would fail. |
| 5.5 | `_sys/core/hub_logging.py` | **DELETE**; keep only a separately named Engram environment logger if needed. | Logging schema is Hub-specific. | Audit continuity if an external reader exists. |
| 5.6 | `_sys/core/hub_peer.py` | **DELETE** after checks/console adapters stop importing it. | Peer invocation belongs in Peerhub. | Direct CLI capability tests may break until migrated. |
| 5.7 | `_sys/core/hub_profile_router.py` | **DELETE** after Peerhub profile descriptors are released. | One profile/routing owner. | Incorrect model/profile routing if Peerhub prerequisite 3.1 is incomplete. |
| 5.8 | `_sys/core/operational_guard_matrix.py` | **DELETE.** Do not port its collaboration/consensus oracle into Engram. | It enforces removed governance. | A genuine filesystem safety rule might be lost; extract any rule that is independently required before deletion. |
| 5.9 | `_sys/core/snapshot.py` | **DELETE/SPLIT.** Remove peer/session/quota snapshots; retain only independently useful environment inventory in a new environment module. | Current file feeds legacy `diag.py` and `.ai` state. | Engram doctor loses inventory data if not split. |
| 5.10 | `_sys/core/quota.py` and `_sys/core/quota_capabilities.py` | **MOVE CONCEPTUALLY TO PEERHUB OR DELETE FROM ENGRAM.** Peer/provider quota telemetry belongs to Peerhub adapters; Engram may retain only raw installed-version/licensing availability checks. | Quota drives coordination routing, not environment lifecycle. | Users may lose visibility if Peerhub telemetry is not truthful first. |
| 5.11 | `_sys/core/hub_config.json` and `_sys/logging-config.json` | **DELETE** with their only owners. | Dead duplicate configuration should not survive code removal. | A general logger might still load `logging-config.json`; verify readers. |
| 5.12 | `_sys/ai/protocol.json` | **DELETE THE WHOLE FILE, LAST AMONG CONFIG READERS.** Do not merely remove `collab_rate`; `leader_election`, `consensus`, `active_constraints`, communication policy, feedback, artifact governance, model profiles, operational guard, and autonomous maintenance all encode the old Hub product. Move isolated environment constants to feature-specific config only when a live reader proves a need. | This produces a clean boundary and avoids a misleading “protocol” shell. | Removing it early causes missing-key crashes throughout checks/hooks/tests. |
| 5.13 | `_sys/ai/orchestration.json` | **SPLIT THEN REMOVE FROM ENGRAM.** Move adapter/profile/routing/permission declarations to Peerhub-owned config; keep install metadata only in `_sys/runtimes.json`/tool manifests. | Coordination topology has one owner. | Peer profiles or invocation flags are lost if the Peerhub schema is incomplete. |
| 5.14 | `_sys/ai/routing-config.json` | **MOVE SEMANTICS TO PEERHUB, THEN DELETE.** | Routing is Peerhub's responsibility. | Dispatch behavior changes without measured canaries. |
| 5.15 | `_sys/ai/lifecycle_policy.json` | **SPLIT.** Move peer session/quarantine/lease lifecycle to Peerhub; relocate any portable update/cleanup retention rules to an Engram environment config. | This file mixes two ownership domains. | Cleanup or process lifecycle changes unintentionally. |
| 5.16 | `_sys/ai/peers.json` | **SPLIT.** Keep only vendor CLI package/install records in `_sys/runtimes.json` or per-tool manifests; move peer names, profiles, roles, and topology to Peerhub. Then delete `peers.json`. | Installed tools are not the same abstraction as communicating peers. | Provisioner loses package discovery if split mechanically. |
| 5.17 | `_sys/ai/infra.json` | **FULL REWRITE** as an environment-only path/tool registry, or delete if `_sys/runtimes.json` fully replaces it. Remove Hub/msg/collab scripts, protocol registry, IPC, mailbox, and peer topology paths. | Current registry advertises removed surfaces. | Environment path resolution may depend on unrelated entries. |
| 5.18 | `_sys/ai/traceability_map.json` | **REBUILD OR DELETE.** The replacement may trace only living Engram requirements to environment implementation/tests; never preserve stale Hub links. | Traceability must describe the product that exists. | Compliance checks may report false completeness or fail. |
| 5.19 | `_sys/ai/backlog.json` | **PRESERVE HISTORY, RECLASSIFY OPEN ITEMS.** Do not rewrite completed historical narratives. Mark open Hub/collaboration items as `superseded` or export them to Peerhub issues; keep only portable-environment work active. | Backlog is evidence as well as a queue. | Historical audit trail is destroyed or obsolete work remains “active.” |
| 5.20 | `_sys/ai/error-taxonomy.json` | **SPLIT/REWRITE.** Retain environment/install/update failures; move peer dispatch/routing/consensus errors to Peerhub or retire them. | Error ownership follows implementation. | Diagnostics may display codes with no handler. |
| 5.21 | `_sys/ai/room_policy.example.json` | **DELETE OR MOVE TO PEERHUB DOCS/EXAMPLES.** | Rooms are a Peerhub concept. | Peerhub loses a useful example if it is not recreated there. |
| 5.22 | `_sys/ai/common/tool-registry.json` | **SPLIT.** Keep only generic/local development tools if live; move peer/hub tools to Peerhub or delete. | Prevent hidden command routes. | An Engram utility can vanish if all entries are treated as peer-only. |
| 5.23 | `_sys/ai/common/agents/lesson-extractor.json` and `_sys/ai/common/agents/proposer.json` | **DELETE/MOVE OUT OF ENGRAM.** They are governance agents. | Lessons/proposals are retired Hub workflows. | User-authored prompt assets could be lost; preserve their history before deletion. |
| 5.24 | `_sys/ai/snapshots/hub_api.json` and `_sys/ai/unreferenced_functions_baseline.json` | **ARCHIVE AS HISTORICAL EVIDENCE, THEN REMOVE FROM LIVING CONFIG.** | They describe the removed implementation and are useful only for provenance. | A current checker may still require them; retire that check simultaneously. |
| 5.25 | `_sys/ai/model-registry.json` and any remaining model/profile policy file discovered by the final manifest scan | **SPLIT BY OWNERSHIP.** Engram may record installed CLI/package versions; Peerhub owns selectable model/profile/routing policy. | Prevent residual dual authority not named in the original list. | Over-broad deletion could remove installer metadata. |
| 5.26 | `.ai/consensus/`, `.ai/mailbox.json`, `.ai/leases.json`, `.ai/state.json`, `.ai/sessions/`, `.ai/handoff.md`, `.ai/health*`, and Hub-generated ask/routing/credit/proposal/lesson/directive state | **QUIESCE, SNAPSHOT, CHECKSUM, THEN REMOVE FROM ACTIVE WORKSPACE.** Snapshot once under `_archive/legacy-peer-governance-YYYYMMDD/` with a manifest; do not import it into Peerhub SQLite. | Storage schemas and semantics differ; historical evidence is worth retaining once. | Removing live leases/state can corrupt sessions; migrating it can pollute Peerhub with incompatible records. |
| 5.27 | `.peerhub/` | **LEAVE OWNED BY PEERHUB.** Engram may ignore it and must not parse or clean it. | This is the new authority boundary. | Engram cleanup could destroy Peerhub state. |
| 5.28 | `_sys/antigravity/config/brain/**` and other vendor cache/scratch/conversation data containing copied Hub text/code | **DO NOT MASS-EDIT OR DELETE IN THIS CUTOVER.** Treat as generated/user state, exclude it from source-authority scans, and offer a separate explicit cache-clean operation. | These are not product source and may contain user data; residual text is not a live caller. | Data loss or accidental publication of private conversations. |

## 6. Feature disposition: move, keep, or intentionally drop

| # | Legacy capability | Disposition | Reasoning | Risk if wrong |
|---:|---|---|---|---|
| 6.1 | `ask`, `ask-all`/broadcast, target/profile resolution | **PEERHUB OWNS.** | Core standalone coordination purpose. | Two routing authorities if Engram retains a copy. |
| 6.2 | Process launch, cancellation, session reuse, bounded retries, health/quarantine | **PEERHUB OWNS FOR NON-INTERACTIVE DISPATCH; ENGRAM OWNS ONLY USER-LAUNCHED INTERACTIVE CLI PROCESS WRAPPING.** | The boundary follows who initiated and supervises the process. | Double supervision or orphaned children. |
| 6.3 | Truthful adapter/capability/quota/status telemetry | **PEERHUB OWNS.** | Used to route/observe peer work. | Engram becomes coupled to vendor logs and profiles again. |
| 6.4 | Formal rounds, `consensus-propose/-vote/-check/-sweep`, R:6–R:10, Final Call, arbiter, mandatory ACK | **INTENTIONALLY DROP.** | Explicit user direction; no current Peerhub equivalent and no recent observed rounds. | Teams that relied on automatic policy gates must adopt explicit human/Peerhub workflows. |
| 6.5 | Leader election, coordinator role, terminal-duty rotation/handoff | **INTENTIONALLY DROP.** | These are social/governance policy, not required for message dispatch. The current live console writes must be removed deliberately. | Long-lived multi-peer sessions may lose “who is driving” visibility. If later proven necessary, add a small optional Peerhub presence feature—not the old governance engine. |
| 6.6 | Mailbox, threads, handoff, alerts, blackboard | **DROP LEGACY SCHEMAS.** Use Peerhub's own command/result/session store only where it supports the workflow. | Avoid compatibility emulation of `.ai`. | A workflow expecting asynchronous inbox semantics may need a separately designed Peerhub feature. |
| 6.7 | Task registry, role/task assignment | **INTENTIONALLY DROP.** | No external live caller was found; the observed task registry is effectively empty. Repository/project task tools should own task management. | A hidden automation may rely on it; final scan and deprecation log catch this. |
| 6.8 | Generic `file-lock` and task locks | **DO NOT PORT.** Keep Peerhub's internal capability/dispatch leases only. Use Git/worktrees and feature-specific atomic locks for actual mutation safety. | A Hub advisory lock cannot prevent a process from editing the file directly. | Concurrent edits remain possible if teams mistook advisory state for enforcement. |
| 6.9 | Mutation broker/governed manifests | **INTENTIONALLY DROP FROM ENGRAM.** Peerhub may design a narrow host-mutation API later only from a separately approved need. | The broker is tightly coupled to consensus/guard governance. | High-risk automation loses an approval mechanism; user confirmation and normal filesystem safeguards remain. |
| 6.10 | Directives, lessons, feedback, proposals, credits | **DROP AS PRODUCT FEATURES; PRESERVE HISTORICAL DATA ONCE.** | They are not required for a portable development environment or basic peer communication. | Organizational memory becomes harder to query unless the archive is indexed. |
| 6.11 | Local file archive/log append | **KEEP AS SIMPLE ENGRAM UTILITIES ONLY IF A LIVE ENVIRONMENT WORKFLOW NEEDS THEM.** | These are generic operations and should not force Hub retention. | Removing them can break housekeeping; retaining Hub-shaped interfaces preserves confusion. |
| 6.12 | Environment install/update/cleanup/register/doctor | **ENGRAM OWNS.** | This is the product's narrowed purpose. | Moving them to Peerhub reverses the intended boundary. |

## 7. Checks and tests

The execution change should remove tests for deleted behavior rather than keep them passing against dead code. Tests that verify portable installation or vendor CLI reality should be rewritten around the new boundary.

| # | File path | Action | Reasoning | Risk if wrong |
|---:|---|---|---|---|
| 7.1 | `_sys/tests/unit/l1_core/test_contracts.py` | **REPLACE, not signature-edit.** Remove Hub API and `protocol.json` contracts; add Engram boundary contracts (no legacy imports/commands/state, environment-only public CLI). This is the same cutover that deletes the public Hub API, satisfying the intent of DIR-003. | Updating obsolete Hub signatures would bless a dead API. | Contract coverage gap if replacement lands later. |
| 7.2 | `_sys/tests/integration/test_hub_integration_v42.py` and `_sys/tests/unit/l3_mocked/test_hub_enforced_crosscheck.py` | **DELETE.** | They validate the removed engine. | A still-live direct caller would no longer be caught; delete only after migration tests pass. |
| 7.3 | `_sys/tests/unit/test_hub_snapshot_failover.py`, `test_hub_invoke_resolution.py`, `test_hub_error_remediation.py`, `test_snapshot_core.py`, `test_diag_cli.py`, `test_diag_layout.py`, `test_diag_quota_format.py`, and `test_diag_exh_pace_labeling.py` | **DELETE OR REHOME ONLY ENVIRONMENT assertions** in new doctor tests. | Hub/diag implementation contracts are retired. | Useful environment diagnostic cases could be lost. |
| 7.4 | `_sys/tests/unit/test_consensus_c6.py`, `test_protocol_consensus.py`, `test_arbiter.py`, `test_arbiter_invoke.py`, `test_arbiter_wiring.py`, `test_reelect_per_task.py`, and `test_terminal_identity_c5.py` | **DELETE.** | Formal governance is intentionally dropped. | None after code removal; residual policy may go untested if not removed. |
| 7.5 | `_sys/tests/unit/test_operational_guard_matrix.py`, `test_check_operational_guard_matrix.py`, `test_check_operational_guard_shadow.py`, `test_governed_guard.py`, `test_guard_shadow_logging.py`, `test_broker_transaction_safety.py`, and `test_security_contract_parity.py` | **DELETE/SPLIT.** Preserve only independent filesystem safety tests under Engram-owned modules. | These mostly test the consensus mutation broker. | A real path-safety invariant might be discarded; extract it first. |
| 7.6 | `_sys/tests/unit/test_console_runner_s3.py`, `test_terminal_spend_guard.py`, and `test_terminal_quota.py` | **REWRITE** for a pure interactive console wrapper; delete terminal-role/quota governance assertions. | Interactive launching stays, Hub session policy does not. | Console regression. |
| 7.7 | `_sys/tests/unit/test_adapter_usage.py`, `test_auto_profile_routing.py`, `test_auto_route.py`, `test_load_balancer.py`, `l2_policy/test_load_balancing.py`, `test_model_profiles.py`, `test_capability_shadow.py`, `test_check_capability.py`, `test_ag_quota_fallback.py`, `test_quota.py`, and `test_telemetry_config.py` | **MOVE SEMANTIC COVERAGE TO PEERHUB; DELETE FROM ENGRAM after the Peerhub release.** Retain only installed-CLI reality/version tests in Engram. | Routing/capability/quota are Peerhub adapter policy. | Peerhub release may lack equivalent regression coverage. |
| 7.8 | `_sys/tests/unit/test_ap20_directive.py`, `test_feedback_corrupted_line.py`, `test_lesson_propagation.py`, `test_self_care.py`, `test_codex_reset_credits.py`, `test_freshness_sweep.py`, and lesson/proposal/directive tests discovered by the final manifest | **DELETE.** | They validate removed governance stores. | Historical-data tooling might be lost; the archive should need no runtime writer. |
| 7.9 | `_sys/tests/unit/test_ctx_end_gemini_keep_days.py`, `test_ctx_end_session_map_lock.py`, `test_ctx_c9.py`, `test_context_gate_c3.py`, and `test_ag_session_context.py` | **REWRITE OR DELETE WITH THE HOOK DECISION.** | Hooks must stop being a second communication path. | Local session recovery regressions. |
| 7.10 | `_sys/tests/unit/test_peer_mgr_missing_hub_nodes.py`, `test_peer_capability_canary.py`-related tests, `test_cli_dispatch_parity.py`-related tests, and `test_statusline.py` | **MOVE peer semantics to Peerhub; retain only Engram tool-install checks.** | Prevent duplicated adapter/statusline tests. | Missing cross-product compatibility coverage; add an installation contract smoke test instead. |
| 7.11 | `_sys/checks/check_operational_guard_matrix.py`, `check_operational_guard_shadow.py`, `check_lesson_enforcement.py`, and `check_policy.py` | **DELETE OR REWRITE AS ENVIRONMENT POLICY LINTS.** No consensus capsules, Hub snapshots, or collab-rate keys. | Current checks enforce the old product definition. | CI can stay green while docs/config are stale unless new boundary checks replace them. |
| 7.12 | `_sys/checks/canary_budget.py`, `check_capability.py`, `check_cli_canary.py`, `check_cli_dispatch_parity.py`, `check_cli_reality.py`, `check_peer_capability_canary.py`, `check_sandbox_behavior.py`, and `validate_peer_config.py` | **SPLIT OWNERSHIP.** Move peer dispatch/profile/sandbox behavior tests to Peerhub; keep Engram canaries for installed executable/version/auth availability only. Remove imports from Hub/snapshot/quota modules. | Environment reality checks remain valuable but must not become routing policy. | Either no installer validation or continued dual ownership. |
| 7.13 | `_sys/checks/check_contracts.py` and `_sys/tests/unit/test_check_contracts_gate.py` | **REWRITE** to enforce the new boundary contract suite. | CI entry point should survive while its target changes. | Deleted legacy tests may remain required or new tests never run. |
| 7.14 | New `_sys/tests/unit/test_product_boundary.py` | **ADD** assertions that tracked Engram source (excluding history/generated vendor data) contains no `hub.py`/`msg.bat` invocation, collab-rate/consensus config, `.ai` governance path, direct non-interactive vendor ask, or hard-coded Peerhub internals. | A mechanical boundary test prevents slow re-entanglement. | Over-broad text matching can flag historical docs; scopes/exclusions must be explicit. |
| 7.15 | New Engram/Peerhub installation contract smoke test | **ADD**: install declared Peerhub tag in a clean temp venv, assert version/entrypoint, run `--help`, `status`, `diag`, and controlled fake `ask`/`broadcast` without Engram-private paths. | This tests integration without sharing implementation. | A real-provider smoke can consume quota; default to controlled fakes. |

Before execution, generate a checked-in deletion manifest from `rg`/AST import discovery and compare it with this table. Do not wildcard-delete tests solely because their names contain `hub`; split any environment-safety assertion first.

## 8. Documentation actions (`_sys/docs-v2`)

Historical collaboration documents should move to `_sys/docs/history/engram-peer-governance/` (or an equivalent clearly non-normative history tree) with a short index stating that they are superseded. They must not remain linked as living SSOT.

| # | File path | Action | Reasoning | Risk if wrong |
|---:|---|---|---|---|
| 8.1 | `_sys/docs-v2/MOC.md` | **FULL REWRITE.** Index only portable-environment architecture, lifecycle, security, installation, updates, cleanup, and troubleshooting; link Peerhub externally as an optional installed tool. | It is the normative map. | Old collaboration docs remain authoritative through links. |
| 8.2 | `_sys/docs-v2/00-MANIFEST.md` | **FULL REWRITE.** Remove Hub/protocol/config/state ownership and reclassify archived files. | The manifest must match the tree. | Docs checks report false SSOT. |
| 8.3 | `_sys/docs-v2/10-invariants.md` | **FULL REWRITE.** Retain portability/path/install/cleanup/security invariants; remove peer equality, consensus, leader, Hub-only mutation, and `.ai` invariants. | Current invariant set defines the wrong product. | Removed behavior remains normatively required. |
| 8.4 | `_sys/docs-v2/20-architecture.md` | **FULL REWRITE.** Describe toolchain/runtime/provisioner/workspace boundaries and a one-way optional dependency on released Peerhub; no Hub/brain/mailbox/governance layers. | Architecture is the key separation artifact. | Future code reintroduces a hidden collaboration layer. |
| 8.5 | `_sys/docs-v2/user/requirements.md` | **FULL REWRITE.** Make the portable Windows AI development environment the sole product goal; list coordination as out of scope. | Requirements drive tests and design. | CI and roadmap continue optimizing the old system. |
| 8.6 | `_sys/docs-v2/user/manual.md` | **FULL REWRITE.** Retain installation/register/status/doctor/update/cleanup/tool launch; remove Hub/peer/collab-rate/consensus/batch-review. Add a short “install/use Peerhub separately” section. | User-facing commands change substantially. | Users follow commands that no longer exist. |
| 8.7 | `_sys/docs-v2/general/protocol.md` | **ARCHIVE ENTIRELY AS SUPERSEDED.** | It is the legacy collaboration protocol. | Partial edits leave hidden requirements. |
| 8.8 | `_sys/docs-v2/general/routing.md` | **MOVE SEMANTICS TO PEERHUB DOCS, THEN ARCHIVE.** | Model/peer routing is Peerhub-owned. | Peerhub loses necessary adapter policy. |
| 8.9 | `_sys/docs-v2/general/lifecycle.md` | **SPLIT.** Rewrite an Engram environment lifecycle doc; move/archive peer session/lease/quarantine lifecycle. | It mixes environment and peer lifecycle. | Update/cleanup rules may be lost. |
| 8.10 | `_sys/docs-v2/general/permissions.md` | **SPLIT.** Keep Windows/filesystem/tool-install safety; move peer invocation permission profiles to Peerhub docs. | Permission boundaries remain important in both products but have different owners. | Minimum permissions become undocumented. |
| 8.11 | `_sys/docs-v2/general/learning.md` | **ARCHIVE OR MOVE TO PEERHUB.** Remove it from Engram SSOT. | Lessons/feedback governance is not environment scope. | Historical rationale becomes harder to locate. |
| 8.12 | `_sys/docs-v2/specific/ag.md` | **MOVE adapter/profile content to Peerhub; retain only AG CLI installation notes in a newly named Engram tool guide.** | Separate installation from coordination. | AG launch requirements such as PTY are lost. |
| 8.13 | `_sys/docs-v2/specific/cc.md` | **SPLIT as in 8.12.** | Same. | Same. |
| 8.14 | `_sys/docs-v2/specific/cx.md` | **SPLIT as in 8.12.** | Same. | Same. |
| 8.15 | `_sys/docs-v2/specific/gc.md` | **ARCHIVE suspended peer policy; retain vendor installation facts only if still supported.** | Suspended topology is not environment architecture. | Legacy compatibility information may be lost. |
| 8.16 | `_sys/docs-v2/ops/anti-patterns.md` | **ARCHIVE ENTIRELY.** | Its current sections are collaboration/governance-specific. | A generic safety anti-pattern should be extracted first if present. |
| 8.17 | `_sys/docs-v2/ops/audit-checklist.md` | **FULL REWRITE.** Keep bootstrap/SUBST/clean-install/update/cleanup/path/security/docs checks; replace peer/Hub/state/API checks with the product-boundary tests in section 7. | The audit remains useful but its target changes. | Release checklist misses environment regressions. |
| 8.18 | `_sys/docs-v2/ops/conventions.md` | **SUBSTANTIAL REWRITE.** Keep batch/path/install/encoding/test conventions; remove collaboration protocol, session state, Hub protection, collab-rate, and decision-gate sections. | This file contains useful cross-cutting environment rules. | Archiving wholesale would discard valuable Windows conventions. |
| 8.19 | `_sys/docs-v2/_exceptions/README.md` | **FULL AUDIT/REWRITE.** Close/archive `.ai`, consensus, lessons, and Hub exceptions; retain only current environment ambiguities with owners/expiry. | Exceptions must not revive removed architecture. | Genuine environment exceptions get lost. |
| 8.20 | `_sys/docs-v2/ops/backlog-design-consensus-2026-07-24.md` | **ARCHIVE ENTIRELY with superseded marker.** | Historical design of retired governance. | None if history index is preserved. |
| 8.21 | `_sys/docs-v2/ops/t82-engram-rescope-2026-07-27.md` | **ARCHIVE ENTIRELY with an explicit “superseded by Engram/Peerhub separation” note.** | It defines Engram as the collaboration engine—the exact decision now reversed. | Without the note, readers may treat it as current direction. |
| 8.22 | `_sys/docs-v2/ops/architecture-audit-2026-07-24.md` | **ARCHIVE.** | Point-in-time Hub architecture evidence. | Any still-open environment finding should be copied to the new backlog first. |
| 8.23 | `_sys/docs-v2/ops/backlog-5whys-consensus-2026-06-26.md` | **ARCHIVE.** | Governance history. | Same as 8.22. |
| 8.24 | `_sys/docs-v2/ops/closure-review-2026-07-17.md` | **ARCHIVE.** | Point-in-time peer-system closure. | Open environment items can be missed. |
| 8.25 | `_sys/docs-v2/ops/closure-review-2026-07-17-round2.md` | **ARCHIVE.** | Same. | Same. |
| 8.26 | `_sys/docs-v2/ops/debate.md` | **MOVE TO PEERHUB HISTORY OR ARCHIVE.** | Formal debate/consensus protocol is retired in Engram. | Teams may expect an escalation process; replacement is explicit user choice plus optional Peerhub delegation. |
| 8.27 | `_sys/docs-v2/ops/diag-telemetry-architecture.md` | **MOVE relevant adapter telemetry requirements to Peerhub, then archive.** | Peer telemetry owner changes. | Truthfulness/provenance requirements might be lost. |
| 8.28 | `_sys/docs-v2/ops/endgame-general-specific-plan-2026-06-28.md` | **ARCHIVE.** | Historical migration plan. | Copy unresolved environment work first. |
| 8.29 | `_sys/docs-v2/ops/engram-refactor-blueprint-2026-07-20.md` | **ARCHIVE with superseded marker.** | Old architecture blueprint. | Readers may follow it if still indexed. |
| 8.30 | `_sys/docs-v2/ops/external-server-ization-proposal-review-2026-07-19.md` | **MOVE relevant rationale to Peerhub history, then archive.** | It concerns externalizing coordination. | Useful separation rationale could disappear. |
| 8.31 | `_sys/docs-v2/ops/governance.md` | **ARCHIVE ENTIRELY.** | Old Hub governance authority. | A generic repository governance rule must be relocated first. |
| 8.32 | `_sys/docs-v2/ops/hard-benchmark-decisions.md` | **MOVE adapter benchmark evidence to Peerhub history; archive Engram copy.** | Model/profile decisions belong to Peerhub. | Peerhub routing loses evidence. |
| 8.33 | `_sys/docs-v2/ops/health-mgmt-redesign-2026-08-06.md` | **MOVE peer-health design to Peerhub; archive Engram copy.** | Health/quarantine is coordination runtime behavior. | Useful environment process-health portions need extraction. |
| 8.34 | `_sys/docs-v2/ops/hub-mutation-broker.md` | **ARCHIVE ENTIRELY.** | Broker is intentionally retired. | Readers might expect it as a security control; new docs must state its replacement boundaries. |
| 8.35 | `_sys/docs-v2/ops/intelligence-scores.md` | **MOVE TO PEERHUB OR ARCHIVE.** | Profile scoring/routing is Peerhub-owned. | Peerhub profiles lose rationale. |
| 8.36 | `_sys/docs-v2/ops/logging.md` | **FULL SPLIT/REWRITE.** Engram doc covers environment/install/update logs only; move dispatch/session/credit/consensus logging to Peerhub or history. | Logging remains cross-cutting. | Retention/privacy guarantees become ambiguous. |
| 8.37 | `_sys/docs-v2/ops/mega-mece-audit-2026-07-16.md` | **ARCHIVE.** | Point-in-time old-system audit. | Transfer unresolved environment findings first. |
| 8.38 | `_sys/docs-v2/ops/multi-ai-collaboration-accord-2026-08-15.md` | **MOVE TO PEERHUB HISTORY OR ARCHIVE; remove from Engram SSOT.** | Directly collaboration-specific. | Personal/global assistant guidance may continue citing it. |
| 8.39 | `_sys/docs-v2/ops/peer-cli-reference.md` | **SPLIT.** Engram keeps vendor install/version/auth/interactive-launch reference; Peerhub receives adapter invocation/profile behavior. | Both products need different slices. | Duplicate or contradictory CLI facts. |
| 8.40 | `_sys/docs-v2/ops/phase1-docs-audit-open-items-2026-07-22.md` | **ARCHIVE after exporting live environment items.** | Historical audit queue. | Open items disappear. |
| 8.41 | `_sys/docs-v2/ops/phase2-arch-general-specific-2026-07-22.md` | **ARCHIVE after exporting live environment items.** | Historical architecture phase. | Same. |
| 8.42 | `_sys/docs-v2/ops/pretdd-prep-2026-07-21-diag-quota-metrics.md` | **MOVE metric requirements to Peerhub history; archive.** | Peer diagnostics/quota scope. | Peerhub repeats known telemetry mistakes. |
| 8.43 | `_sys/docs-v2/ops/profile-policy.md` | **MOVE TO PEERHUB, THEN ARCHIVE.** | Profiles are Peerhub-owned. | Profile selection loses normative policy. |
| 8.44 | `_sys/docs-v2/ops/profile-policy-decisions.md` | **MOVE TO PEERHUB HISTORY, THEN ARCHIVE.** | Decision provenance follows profile policy. | Same. |
| 8.45 | `_sys/docs-v2/ops/quota-balance-decisions.md` | **MOVE TO PEERHUB HISTORY, THEN ARCHIVE.** | Quota-aware routing is Peerhub-owned. | Same. |
| 8.46 | `_sys/docs-v2/ops/residual-backlog-and-packaging-precheck-2026-07-26.md` | **SPLIT/ARCHIVE.** Copy live packaging findings to Engram backlog; archive collaboration findings. | Packaging remains Engram scope. | Useful release work is lost. |
| 8.47 | `_sys/docs-v2/ops/runtime-drift-reconciliation-pretdd.md` | **SPLIT.** Engram owns installed package/version drift; Peerhub owns runtime-selected model/profile/adapter drift. Archive the original plan after successor docs exist. | “Runtime drift” spans both products. | Either side assumes the other validates it. |
| 8.48 | `_sys/docs-v2/ops/schemas.md` | **FULL REWRITE/SPLIT.** Keep environment configuration schemas; move `.peerhub` schemas to Peerhub and archive `.ai` governance schemas. | Schema authority must follow storage owner. | Tools keep writing obsolete `.ai` files. |
| 8.49 | `_sys/docs-v2/ops/skills.md` | **REWRITE.** Keep portable skill installation/location behavior only; move peer orchestration policy out. | Skills can remain an environment feature. | Useful tool setup is lost or collaboration rules remain. |
| 8.50 | `_sys/docs-v2/ops/templates.md` | **REWRITE/SPLIT.** Keep environment/project templates; archive debate/consensus/handoff/proposal templates. | Templates encode behavior. | New work accidentally recreates old governance. |
| 8.51 | `_sys/docs-v2/ops/status-consolidation-2026-07-08.md` | **ARCHIVE; extract environment doctor requirements.** | Old combined status design. | Environment status becomes incomplete. |
| 8.52 | `_sys/docs-v2/ops/statusline-quota-display-handoff-2026-07-15.md` | **MOVE TO PEERHUB HISTORY, THEN ARCHIVE.** | Peer statusline/quota scope. | Peerhub telemetry loses known constraints. |
| 8.53 | `_sys/docs-v2/ops/capability-leveling.md` | **MOVE TO PEERHUB, THEN ARCHIVE.** | Capability routing is Peerhub-owned. | Permission/capability semantics diverge. |
| 8.54 | `_sys/docs-v2/ops/capability-leveling-decisions.md` | **MOVE TO PEERHUB HISTORY, THEN ARCHIVE.** | Decision provenance follows feature ownership. | Same. |
| 8.55 | `_sys/docs-v2/ops/zombie-deep-dive-2026-07-18.md` | **MOVE process-supervision findings to Peerhub history; archive original.** | Peer dispatch zombie management is Peerhub scope. | Peerhub repeats orphan-process bugs. |
| 8.56 | `_sys/docs-v2/ops/cli-baselines/ag-1.1.5-help.txt` | **KEEP IN ENGRAM only as installation compatibility evidence, or copy to Peerhub adapter fixtures with provenance.** | Raw vendor CLI availability is relevant to the environment. | Stale baseline may be mistaken for live capability. |
| 8.57 | `_sys/docs-v2/ops/cli-baselines/cc-2.1.216-help.txt` | **KEEP under the same rule as 8.56.** | Same. | Same. |
| 8.58 | `_sys/docs-v2/ops/cli-baselines/codex-0.144.6-help.txt` | **KEEP under the same rule as 8.56.** | Same. | Same. |
| 8.59 | `_sys/docs-v2/ops/cli-update-checkpoints-agy.md` | **KEEP/REWRITE as Engram installation-update evidence; move dispatch behavior to Peerhub.** | Tool provisioning is Engram scope. | Mixed ownership persists. |
| 8.60 | `_sys/docs-v2/ops/cli-update-checkpoints-cc.md` | **KEEP/REWRITE as in 8.59.** | Same. | Same. |
| 8.61 | `_sys/docs-v2/ops/cli-update-checkpoints-codex.md` | **KEEP/REWRITE as in 8.59.** | Same. | Same. |

## 9. Root and non-docs-v2 documentation

| # | File path | Action | Reasoning | Risk if wrong |
|---:|---|---|---|---|
| 9.1 | `README.md` | **FULL REWRITE.** Present Engram as a portable Windows AI development environment; remove autonomous collaboration/consensus claims and Hub command examples. Link the standalone Peerhub repository as optional companion software. | This is the human entry point. | Product identity remains contradictory. |
| 9.2 | `PROTOCOL.md` | **DELETE OR REPLACE WITH AN ENVIRONMENT POLICY POINTER.** | A collaboration-protocol root pointer is no longer appropriate. | Contributor rules may lose a valid environment safety reference. |
| 9.3 | `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and `CONVENTION.md` in the repository root | **REWRITE ONLY THE COLLABORATION SECTIONS** as repo contributor/tool instructions without collab-rate, mandatory consensus, handoff, or Hub commands. | Repo-native AI instructions must match the new scope. | Agents continue writing legacy state or demanding obsolete gates. |
| 9.4 | `_sys/claude/config/CLAUDE.md` | **DO NOT EDIT IN THIS WORK.** Terminal/user-owned global config is explicitly out of scope. Recommended replacement concept: use Peerhub for deliberate peer communication; no collab-rate, R-level, formal vote, Final Call, leader/terminal-duty, or automatic unanimity gate; the initiating assistant remains responsible for synthesis and user authorization. | The terminal needs a coherent conceptual handoff without this change crossing repository scope. | If left unchanged after cutover, the assistant will request commands and state that no longer exist. |
| 9.5 | `_sys/docs/history/engram-peer-governance/README.md` (new) | **ADD DURING IMPLEMENTATION** as a non-normative index recording the cutover date, last legacy commit, archive manifest hash, successor Peerhub version, and the explicit dropped-feature list. | Preserves rationale without keeping dead code live. | History becomes hard to audit or is mistaken for current policy. |

## 10. Safe execution sequence

| # | Phase | Exact gate and actions | Why this order matters | Stop/rollback condition |
|---:|---|---|---|---|
| 10.1 | Freeze the plan | Obtain independent critique; resolve findings; generate exact caller/import/config/test/deletion manifests and hash them. Record current dirty/untracked files and exclude unrelated user changes. | Prevents scope drift and accidental edits to concurrent work. | Any unclassified live caller or overlapping edit. |
| 10.2 | Make Peerhub independent | Land rows 3.1–3.9 in the Peerhub repository after the unrelated telemetry change; test in a clean directory without Engram/P:; release a tagged version. | Engram callers need a complete stable destination. | Hard-coded Engram path, synthetic telemetry, missing profile, failed prompt-file or AG PTY canary. |
| 10.3 | Update Engram's package pin/receipt | Change `_sys/runtimes.json` to the released tag, reinstall through the provisioner, and regenerate `_sys/tools/peerhub/.install_manifest.json`; assert declared, installed, and canary versions agree. | Fixes the current 0.1.7/0.1.0 provenance drift and establishes reproducibility. | Version/hash/canary mismatch. |
| 10.4 | Migrate direct callers while Hub remains available | Implement rows 4.8–4.28 and 5.13–5.18. Use Peerhub public commands only for actual peer communication. Add boundary tests but keep legacy files temporarily for comparison. | Avoids a broken intermediate state. | Any migrated workflow still writes legacy `.ai` state or invokes a vendor CLI directly for peer work. |
| 10.5 | Deprecate aliases and workflow commands | Make `hub`, `msg`, old `diag`, batch review, and collab-rate commands fail with a clear migration message for one release; update help and root docs draft. | Gives users/automation a visible migration signal before removal. | A supported automation cannot yet use Peerhub or Engram doctor. |
| 10.6 | Quiesce and prove no legacy writers | Close legacy consoles, wait for or explicitly terminate only known legacy sessions through their normal close path, confirm no fresh writes to `.ai/state.json`, leases, mailbox, or consensus during a controlled session. Run an admin/user read-only scheduled-task and process check because the current probe lacked permission. | Prevents deleting live coordination state. | Any active lease/process/task or timestamp changes. |
| 10.7 | Archive historical evidence once | Copy legacy governance state and selected documents/snapshots to a dated history directory; produce path/size/SHA-256 manifest; verify archive readability. Do not archive executable Hub source outside Git. | Preserves audit history without creating another live implementation. | Hash mismatch, incomplete state inventory, or private data exposure not reviewed by the user. |
| 10.8 | Atomic source/config/test cutover | In one internally consistent change: delete rows 4.1–4.6, 4.14–4.21, and 5.1–5.11; replace/delete their tests/checks; then remove `protocol.json` and collaboration configs only after all readers are gone. Rewrite root CLI/help and living docs in the same branch. | Specifically avoids missing-key crashes from deleting `collab_rate`/`protocol.json` too early. | Import/call-site/boundary test failure. Revert the cutover commit, not user data. |
| 10.9 | Remove active legacy state | After the no-writer gate and verified archive, remove legacy `.ai` governance/session files. Leave `.peerhub` untouched. | Runtime data removal is the only destructive data step. | Any active writer or unverified archive. |
| 10.10 | Fresh-install validation | On a clean temp workspace run Engram install/register/status-or-doctor/update/cleanup and interactive CLI launch tests; independently run Peerhub version/status/diag/controlled-fake ask/broadcast/statusline. Validate no `P:` or Engram path is needed by Peerhub. | Proves both products stand alone. | Either product requires the other's private files. |
| 10.11 | Final residual scan | Search tracked non-history source/config/docs for `collab_rate`, consensus action names, `hub.py`, `msg.bat`, `.ai/consensus`, `.ai/leases`, `.ai/mailbox`, terminal-duty/leader governance, direct non-interactive vendor asks, and hard-coded Peerhub internals. Require zero unexplained hits. | “Full separation” is a negative property and needs a mechanical proof. | Any unexplained hit. |
| 10.12 | Release and observe | Release Engram with migration notes and the minimum supported Peerhub version; monitor one normal update/cleanup/interactive session and one Peerhub session. | Catches packaging/PATH issues not visible in unit tests. | Restore the last known-good Engram release and retain the archived state. |

## 11. Acceptance criteria

The separation is complete only when all of the following are measured:

1. Engram tracked living source has no import or invocation of legacy Hub/diag modules and no non-interactive peer communication that bypasses Peerhub.
2. Engram has no living `collab_rate`, formal consensus, leader/terminal-duty, mailbox, directives/lessons/proposals, credit, broker, or generic peer lock implementation/configuration/documentation.
3. Peerhub starts and passes its controlled-fake suite in a clean path with no Engram tree, `P:` drive, or hard-coded portable-root fallback.
4. Every supported Peerhub profile has measured adapter/executable/permission/input/PTY evidence; unknown values render as unknown.
5. Engram install/update/cleanup/doctor and interactive vendor CLI launches work without `.ai` governance state or Peerhub internals.
6. Peerhub ask/broadcast/status/diag/statusline work through its own public command and state store; Engram neither parses nor cleans `.peerhub`.
7. `_sys/runtimes.json`, the install receipt, installed package metadata, and CLI canary agree on the Peerhub release.
8. The legacy state archive has a verified SHA-256 manifest, while Git history remains the sole archive for deleted executable source.
9. The scheduled-task/process check is completed with sufficient permission and reports no remaining direct `hub.py` caller; until then deletion remains blocked.
10. Living Engram docs uniformly describe the portable-development-environment scope, and historical documents are visibly non-normative.

## 12. Principal risks and decisions for round 2

The independent critique should focus on four points: (a) whether Peerhub profile/PTY/prompt-file prerequisites are sufficient for every current caller; (b) whether any environment-only rule is trapped inside `operational_guard_matrix.py`, `snapshot.py`, or the old docs and must be extracted; (c) whether one deprecation release is necessary for `hub`/`msg` aliases; and (d) the privacy/retention scope of the legacy `.ai` archive.

The proposal does **not** recommend porting the ~85 unreachable actions by default. The only justified Peerhub additions are those needed to make its existing core role production-complete and independent: profiles/adapters, safe prompt transport, PTY correctness, honest telemetry, and a stable active-dispatch interlock. Everything else requires a new user need and a separate design, not compatibility preservation.

---

## 3. engram_peerhub_separation_RATIFIED_scope.md

Original path: `P:\workspace\engram_peerhub_separation_RATIFIED_scope.md`

# Engram/Peerhub Separation — Ratification & Tonight's Scope (2026-08-19)

## Sources reconciled

1. **AG's prior plan** (`_sys/antigravity/config/brain/2c8ac180.../engram_streamlining_and_cleanup_plan.md`, undated, references peerhub v0.1.1): simpler 2-phase framing (isolated test in `P:\output\review_test` -> apply to live P: -> push -> tag v2.2.0). Correctly scoped the file-level DELETE/RETAIN split for Engram's `_sys/core`/`_sys/cli` legacy cluster. Did not address peerhub's own Engram-coupling (presenter.py/quota_polling.py hardcoded paths) since that code didn't exist yet at v0.1.1.
2. **cx.deepthink's round-1 proposal** (`P:\workspace\engram_peerhub_separation_proposal.md`, 2026-08-18/19, ~270 lines, 12-phase safety-gated sequence): independently derived, converges on the same end state as AG's plan (hub.py/diag.py cluster deleted, collab_rate/consensus/leader/terminal-duty/mailbox/lessons/proposals/broker all intentionally dropped, not ported), but is substantially more rigorous: identifies real risks AG's plan didn't (protocol.json must be deleted whole, last, not piecemeal, to avoid missing-key crashes elsewhere; scheduled-task/process caller check is TEST NEEDED not proven; `.ai` governance state needs quiesce+checksum+archive before removal, not just deletion; peerhub itself is repo-separated but NOT yet configuration-independent -- it still reaches into Engram's `_sys`/`P:`/a hard-coded `D:` path).

**Both plans agree on the target architecture.** cx's is adopted as the authoritative execution plan for the Engram-side work (sections 4/5/7/8/9/10 of `engram_peerhub_separation_proposal.md`) given its materially higher rigor. AG's plan is kept as corroborating precedent, not superseded-and-discarded.

## Real, live risk found before any execution: self-undermining sequencing

The terminal (this assistant) is currently delegating ALL of tonight's implementation work via `python core/hub.py ask --to <peer>` (the legacy dispatch mechanism). Deleting `hub.py` before the terminal's own delegation path migrates to `peerhub ask`/`peerhub broadcast` would cut off the terminal's ability to delegate further work mid-execution -- a real, previously-unconsidered risk in both plans' sequencing.

## User decision (2026-08-19, verbatim intent)

Scope for tonight: **Peerhub-side prerequisite work only** (cx proposal section 3, rows 3.1-3.10). The Engram-side deletion/doc-rewrite cluster (sections 4/5/7/8/9/10 of the full proposal) is preserved as a **ratified, staged backlog** for a dedicated future session -- not attempted tonight under quota/time pressure, consistent with the proposal's own Phase 10.1 "freeze the plan" gate and the real self-undermining-sequencing risk above.

## Tonight's concrete deliverables (peerhub repo, P:\workspace\peerhub)

| Row | Item | Status |
|---|---|---|
| 3.4 | `presenter.py`: remove Engram `_sys`/`P:`/hard-coded `D:` path reads; CC/CX pools read real `usage_projections` (migration 0024) with fail-closed staleness, matching the already-correct AG pool's pattern | in progress |
| 3.5 | `quota_polling.py`: provider-owned discovery, injectable paths (no derived Engram portable root) | in progress |
| 3.6 | `statusline.py`/`cli.py::_run_statusline`: remove hard-coded `room-efde`, leader/failover text, synthetic quota values; stdout by default | queued |
| 3.1 | Profile/adapter config descriptors for all supported profiles (not just `*.standard`) | queued |
| 3.2 | `--prompt-file`/stdin support on `peerhub.cli` | queued |
| 3.9 | Add a test asserting package source contains no Engram/P:/D: absolute path | queued |
| 3.10 | Release a new tagged peerhub version once the above lands and tests are green | queued |

Section 4/5/7/8/9/10 (Engram-side deletions, ~150+ files) explicitly **NOT attempted tonight** -- tracked as ratified backlog in `engram_peerhub_separation_proposal.md`.

---

## 4. test_check_cli_reality.py

Original path: `P:\workspace\test_check_cli_reality.py`
> **Note:** Standalone test script for CLI reality validation.

```python
import os
import json
import tempfile
import pytest
from _sys.ai.check_cli_reality import RealityReconciler

def test_reality_reconciler_no_baseline(tmp_path):
    # Setup mock workspace
    workspace = tmp_path
    sys_ai = workspace / "_sys" / "ai"
    sys_ai.mkdir(parents=True)
    dot_ai = workspace / ".ai"
    dot_ai.mkdir(parents=True)
    
    orch = {
        "hub_nodes": [
            {
                "node_id": "test_node",
                "enabled": True,
                "invoke": "test.exe",
                "profiles": {
                    "standard": {"model_id": "test-model"}
                }
            }
        ]
    }
    with open(sys_ai / "orchestration.json", "w") as f:
        json.dump(orch, f)
        
    # Create dummy binary
    with open(workspace / "test.exe", "wb") as f:
        f.write(b"dummy content")
        
    reconciler = RealityReconciler(str(workspace))
    result = reconciler.check_drift_and_reconcile()
    
    assert result["status"] == "DRIFT_DETECTED_AND_UPDATED"
    assert "test_node" in result["reality"]
    assert result["reality"]["test_node"]["models"]["standard"] == "verified_local"

def test_reality_reconciler_no_drift(tmp_path):
    # Setup mock workspace
    workspace = tmp_path
    sys_ai = workspace / "_sys" / "ai"
    sys_ai.mkdir(parents=True)
    dot_ai = workspace / ".ai"
    dot_ai.mkdir(parents=True)
    
    orch = {
        "hub_nodes": [
            {
                "node_id": "test_node",
                "enabled": True,
                "invoke": "test.exe"
            }
        ]
    }
    with open(sys_ai / "orchestration.json", "w") as f:
        json.dump(orch, f)
        
    with open(workspace / "test.exe", "wb") as f:
        f.write(b"dummy content")
        
    reconciler = RealityReconciler(str(workspace))
    # First run creates baseline
    reconciler.check_drift_and_reconcile()
    
    # Second run should have no drift
    result2 = reconciler.check_drift_and_reconcile()
    assert result2["status"] == "NO_DRIFT"
```
