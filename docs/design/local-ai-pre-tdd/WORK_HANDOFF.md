# Engram Cognitive AI Platform — Work handoff

## Resume prompt

Act as the lead engineer, architect, and TDD reviewer for `greatgc-flow/Engram`.

Repository: https://github.com/greatgc-flow/Engram
Design branch: `design/local-ai-pre-tdd-20261128`
Design baseline main: `61076a4734d691fe917bee562a2e2bec9c7a9148`
Package: `docs/design/local-ai-pre-tdd/rev06/`

Restore the project from the complete English Rev. 0.6 package, not from a summary. Read README, SPECIFICATION, CONTRACTS, DECISIONS, IMPLEMENTATION_PLAN, REQUIREMENTS, TEST_CATALOG, SOURCES and MANIFEST.sha256. Verify all eight manifest entries against the committed bytes (beware checkout line-ending conversion). The package is unchanged from its pre-TDD state; this handoff file is outside the manifest.

### 1. Re-establish the source of truth

- Fetch the actual current remote main, design branch, relevant open PRs/issues and CI results. The design baseline is historical, not a claim about the current main.
- Verify the design branch and package integrity. Review repo conventions, existing runtime catalog, CLI dispatcher, lifecycle, environment isolation, packaging, backup and tests. Do not overwrite newer upstream changes.
- Validate the 150 acceptance cases, nine requirement groups, 50 ADRs, 28 risks and the dependency/release gates against the actual code and upstream APIs. Report inconsistencies explicitly; keep stable IDs and record any amendment in a new revision.
- Inspect the current PeerHub repo/README and public upstream docs at pinned versions where relevant. Do not invent APIs or claim local support from feature names alone.

### 2. Non-negotiable architecture

- Existing Engram remains functional without AI; optional `ai setup` installs only the approved profile under `_sys/AI/`. No root clutter, host-global PATH/registry changes, SUBST or junctions.
- Multi-Python belongs to Engram, not the AI extension. Preserve the legacy default paths/CLI; install extra stable, compatible minor-series runtimes on demand; isolate application dependencies and preserve rollback. Reuse Engram CLI/tools/workspace and existing authorized login state; private vendor runtime only when proven necessary.
- Reuse existing independent PeerHub install/store. No SecondBrain installation; no default additional vector/graph/cache server. Hermes, OpenClaw, Ollama, Hindsight and PostgreSQL/pgvector are conditional on actual compatibility and verification.
- Capture approved AI activity, PeerHub input/output and outcomes, historical documents, Git and tests with provenance and deduplication. Separate raw evidence, knowledge, candidate memories, verified/proven experience, approved skills and evaluation. Native sessions remain separate; use scoped Hindsight banks and APIs, not direct competing DB writes.
- Local-first; protect permissions, credentials, confidential data and source boundaries. No hidden chain-of-thought capture, unapproved remote calls, automatic cloud fallback or arbitrary remote shell. Keep delivery success separate from task success. PeerHub request identity, replay and uncertain execution must be preserved.
- Context Manager, shared GPU admission and sleep-time consolidation coordinate a single GPU; foreground work wins. Reuse upstream functions and prevent competing consolidation writers. No weight retraining in MVP.
- Integrate installed AI and models into Engram update/relocate/doctor/repair/backup/restore/tidy/uninstall. Compatible staged model updates, shadow reindex for encoder changes, explicit approval for risky migrations/deletions, offline/unknown states and crash-safe recovery. Keep raw sources and user data safe.

### 3. Execute in dependency order

- Start at WP0: technical feasibility and contract freeze, using the exact POC-01–10 and G0–G7 gates in IMPLEMENTATION_PLAN.md. Use disposable synthetic data and standard-user Windows checks. Establish real upstream artifact, version, license, hash, dependency and capability evidence.
- Target hardware: Windows x64, RTX 3060 12 GB VRAM, Ryzen 5 5600X, 32 GB RAM. Do not assume cloud/CI runners have this GPU. If the actual target cannot be accessed, record BLOCKED/NOT_RUN and supply reproducible commands; never fabricate measurements.
- Resolve or explicitly disable unsupported capabilities: portable Python provider; Hermes PM and isolated Python; actual Hermes context requirement and tool quality; PostgreSQL/pgvector; Hindsight local Memory/Knowledge Banks; hooks and scoped capture; PeerHub history/dry-run; egress/ACL enforcement; model/encoder migration; GPU/sleep cancellation.
- After relevant gates are established, begin pure-contract RED tests and then RED–GREEN–REFACTOR in the specified work-package order. Implement WP1–WP3 Multi-Python first; WP4 runtime; WP5 agents/memory; WP6 PeerHub; WP7 experience pipeline; WP8 context/sleep/skills; WP9 integrated validation; WP10 optional extensions. Work in small independently reviewable commits/PRs. WP6b PeerHub export is optional and a separate repository change requiring owner approval.
- Re-run existing regression tests and new mapped acceptance tests with actual logs, including concurrency, restoration, negative cases, packaging and security. Distinguish documentation checks, mocked tests, integration tests and real hardware tests. Score readiness from evidence, not aspiration.
- Record progress, blockers, decisions, command outputs, artifact hashes, test status and next action in a separate versioned work ledger/handoff document. Keep the nine-file Rev. 0.6 baseline immutable; add revisions or errata rather than silently editing it.

### 4. Git and safety limits

Use the design branch as a read-only baseline and create feature branches for implementation, based on the verified current main with the reviewed design available. Do not merge, push to, or alter main. No release publication without separate approval. Do not change PeerHub without explicit approval; propose a generic read-only Activity Export extension rather than a Hindsight dependency or core rewrite. Use no real sensitive histories, secrets or credentials in public GitHub. Do not perform paid/cloud model calls, enroll private folders, activate remote bots, change system-wide settings, or delete user data without specific authorization. Use mock/dry-run fixtures where possible. Avoid irreversible operations.

### 5. First deliverable

Report the current repository and design branch SHAs, manifest verification, baseline/contract differences, POC and gate status, risks and the exact first actionable RED test or feasibility spike. Then proceed with authorized safe work, rather than returning only a plan. Commit English documentation and code/tests in feature branches as evidence warrants. Report any unverified or blocked work explicitly and preserve main.
