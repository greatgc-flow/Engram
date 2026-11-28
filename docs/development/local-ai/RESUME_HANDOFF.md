# Engram implementation handoff

## Baseline

The immutable Rev. 0.6 package is at `c59c0e42bb6584bc873269b7128a1c94ecba3229`. The SHA-256 manifest audit verified eight listed files, 150 acceptance cases, 50 ADRs, 28 risks and nine requirement groups. Keep acceptance execution evidence in development records. Engram main was observed at `61076a4734d691fe917bee562a2e2bec9c7a9148` and PeerHub main at `b1d877d689a9bc79d16054de7371b28b108049fd`. Review and merge ownership is independent of these receipts.

The Windows hosted runner verifies portable runtime and synthetic service behavior. It does not qualify a production GPU workload. [Accelerator profiles](ACCELERATOR_PROFILES.md) qualify devices and backends by measured capacity, placement, context and quality on the target host. The RTX 3060 is one reference configuration.

## Native evidence and scope

| Work | Observed scope | GitHub |
| --- | --- | --- |
| WP3 / T70–T71 | Exact locked application venv reconstruction with the source absolute path unavailable. Different Windows volumes, Unicode paths, native extension, regenerated pip launcher, missing-wheel refusal, preserved project pin and registry. | [#156](https://github.com/greatgc-flow/Engram/pull/156), [#157](https://github.com/greatgc-flow/Engram/pull/157) |
| WP3 / T72 subset | Read-only reference diagnostics for registered environments, consumer bindings, project pin, active series and pending operations. Live processes, external projects and backups remain unknown. | [#158](https://github.com/greatgc-flow/Engram/pull/158), [CI](https://github.com/greatgc-flow/Engram/actions/runs/46131706052/job/140938083784) |
| WP0 / POC-05 / T13 subset | EDB PostgreSQL 17.12 and pgvector 0.8.7 on a restricted Windows token. Exact artifacts, local listener, limited database role, vector order, restart, separate-cluster logical restore and unchanged service inventory. | [#159](https://github.com/greatgc-flow/Engram/pull/159), [Windows job](https://github.com/greatgc-flow/Engram/actions/runs/46132505104/job/140940544080) |
| WP3 / T69 subset | Extra-Python component through the existing Engram update verb. RED observed parser rejection. GREEN verified preview equivalence, isolation from unrelated discovery and invalid-scope refusal. Windows CI passed 2,624 tests and 154 subtests. The real 3.14.8 to 3.14.10 patch preserved the exact pin. | [#160](https://github.com/greatgc-flow/Engram/pull/160), [Windows job](https://github.com/greatgc-flow/Engram/actions/runs/46132633190/job/140940950754) |
| WP0 / POC-03 / T75 subset | Windows x64 Hindsight slim 1.3.0, 186 exact wheels and 394,808,232 compressed bytes. The restricted Windows token passed offline pip, four native imports and the help entrypoint. The closure includes required vendor SDKs. | [#161](https://github.com/greatgc-flow/Engram/pull/161), [Windows job](https://github.com/greatgc-flow/Engram/actions/runs/46133472729/job/140943537909) |
| WP3 / T71 metadata | Byte-exact Python registry and referenced locks through scoped backup and restore. The native job restored missing metadata on a second Windows volume and rebuilt the locked app environment. Same identity, conflict refusal and journal recovery passed. | [#162](https://github.com/greatgc-flow/Engram/pull/162), [Windows job](https://github.com/greatgc-flow/Engram/actions/runs/46143926894/job/140975706616) |
| WP3 / T72 live reference | Opt-in exact executable observation with partial coverage. A real retained 3.14.8 process protected its build while 3.14.10 was active. Two states were observed before and after child exit. Unseen processes and external reference completeness remain unresolved. | [#163](https://github.com/greatgc-flow/Engram/pull/163), [Windows job](https://github.com/greatgc-flow/Engram/actions/runs/46143470926/job/140974316170) |
| WP3 / T71 offline artifacts | Scoped opt-in pack restored the exact interpreter archive and wheel caches and reconstructed the interpreter and native venv on a different Windows volume. | [#164](https://github.com/greatgc-flow/Engram/pull/164), [Windows job](https://github.com/greatgc-flow/Engram/actions/runs/46151045848/job/140997543721) |
| WP3 / T72 backup reference | Explicit same-installation backup observation protects retained builds using bounded metadata. A retained 3.14.8 build stayed protected by an explicit backup after its process exited. The combined Windows suite passed 2,645 tests and 154 subtests. | [#165](https://github.com/greatgc-flow/Engram/pull/165), [Windows job](https://github.com/greatgc-flow/Engram/actions/runs/46151235477/job/140998113997) |

## PeerHub upstream contract check

The separately maintained PeerHub candidate `d1a59383c8f668a7f65585d08b4d29f33c2e2251` passed 42 synthetic activity export, limits, receipts, consumer replay and recovery tests on Linux. Its activity contract version is `peerhub.activity/1.0`. Use explicit `--db` and per-stream scope, keep the record, evidence and outcome channels distinct, preserve lineage, and commit checkpoint and accepted or quarantined events together. The projection omits prompt and response text. Engram deployment of this producer remains open. The compatibility fallback remains the existing approved closed-snapshot reader. Live SQLite readers can materialize WAL/SHM sidecars.

[PeerHub branch contract](https://github.com/greatgc-flow/peerhub/blob/d1a59383c8f668a7f65585d08b4d29f33c2e2251/docs/implementation/activity/CONTRACT.md) · [Synthetic exchange](https://github.com/greatgc-flow/peerhub/blob/d1a59383c8f668a7f65585d08b4d29f33c2e2251/docs/implementation/activity/engram-v1.json).

## Hermes upstream contract check

Hermes v0.23.4 resolves to commit `8fc0374447313e276f6b9a2764bfc750190c966a`. Its developer environment builder exposes `--python` for the build target and first resolves the vendor toolchain, including the vendor-pinned Python. The standard Windows bootstrap publishes the launcher through a persisted user PATH write. That route fails the portable footprint requirement. The Engram decision remains open until a supported launcher and update flow is shown with an external interpreter or the owner approves an isolated vendor-private footprint. No native Hermes installation was run.

[Explicit developer build argument](https://github.com/NousResearch/hermes-agent/blob/8fc0374447313e276f6b9a2764bfc750190c966a/pm/build_env.py#L37-L58) · [Tool resolution](https://github.com/NousResearch/hermes-agent/blob/8fc0374447313e276f6b9a2764bfc750190c966a/pm/environment.py#L279-L303) · [Windows launcher publication](https://github.com/NousResearch/hermes-agent/blob/8fc0374447313e276f6b9a2764bfc750190c966a/scripts/install.ps1#L1429-L1478).

## Cross-validation of backup and process observation

Both feature branches were combined locally for targeted validation.
The 214 tests passed, with one Windows-specific long-path assertion
deselected on Linux. A packaging fixture included the static runtime
backup module and excluded the synthetic registry, dependencies lock,
backup ZIP and personal data. A synchronized pair of Linux exporters
published one complete ZIP and preserved the winning file. Rev. 0.6's eight manifest entries and
package tree remain byte-exact.

## Remaining dependencies

| WP | Status and next gate |
| --- | --- |
| WP0 | **PARTIAL.** Run native Hermes manager footprint and external-interpreter or vendor-private contract. Qualify Hindsight against the verified PostgreSQL pair with explicit local providers and independently verify Knowledge Bank source locators. Measure CPU/GPU context and resource behavior on the intended target configurations. |
| WP1–WP2 | **IMPLEMENTED IN FEATURE BRANCHES.** Registry, provider, selection, child execution, extra install and exact project pins have scoped evidence. Recheck installation and shipped manifests at final integration. |
| WP3 | **PARTIAL.** Compatible app rebinding, bare update and detached coordinator participation, coordinated application-data restore and new-installation adoption, authoritative retirement coverage, and T73 uninstall integration remain open. Keep unresolved references protected. |
| WP4 | **NOT_RUN.** After applicable runtime lifecycle gates, start with legacy/collision/absent-AI invariants, static wrapper packaging, explicit setup plan and shared-lock refusal. AI profiles require their own verified artifact and process contracts. |
| WP5 | **NOT_RUN.** Verify native vendor bindings, local model and separate Memory/Knowledge Bank generations under exact provider and synthetic data fixtures. |
| WP6 / WP6b | **NOT_RUN for Engram integration.** Reuse the installed PeerHub CLI with a selected store and per-stream enrollment. The native-stream fallback has bounded coverage. Feature-branch Activity Export needs an enabled, versioned producer and consumer replay, conflict and restore tests before treating it as integrated. |
| WP7 | **NOT_RUN.** Scope enrollment and ledger idempotency precede source adapters, verified provenance and bank promotion. Use synthetic records. |
| WP8 | **NOT_RUN.** Context capacity, compute admission, sleep fencing and skill promotion depend on measured local profiles and the evidence layer. |
| WP9 | **NOT_RUN.** Cross-store restore, effective egress and write containment, reproducible release and quality-aware token evaluation still need their integration gates. |
| WP10 | **NOT_RUN.** Optional scope follows the measured need and the relevant security and quality gates. |

Use the frozen catalog for ownership and expected outcomes. Keep fixture receipts scoped to their executed assertions. A test on a synthetic service or disposable data directory does not establish behavior on the user's existing local installation.
