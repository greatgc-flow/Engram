# Engram Documentation

This directory contains architectural specifications, design decision records, and historical archives for the Engram portable developer runtime.

## Documentation Taxonomy (MECE)

| Directory / File | Category | Description |
| :--- | :--- | :--- |
| **[`cli_reference.md`](cli_reference.md)** | **User Guide** | Complete command reference covering every engram verb, option, example, exit code, and safety guarantee. |
| **[`user_lifecycle_guide.md`](user_lifecycle_guide.md)** | **User Guide** | Personal settings, AI session data, backup, restore, reset, and uninstallation workflows. |
| **[`isolation_guide.md`](isolation_guide.md)** | **User Guide** | Optional Windows Sandbox and WSL2 isolation features and setup. |
| **[`env_resilience_guide.md`](env_resilience_guide.md)** | **User Guide** | Python/venv repair, root folder relocation, Python updates, and the backup registry. |
| **[`maintainer_handoff.md`](maintainer_handoff.md)** | **Maintainer Reference** | Release recipe, operational pitfalls, decisions, and the current state. |
| **[`engram-dotdir.md`](engram-dotdir.md)** | **Technical Specification** | Normative specification for `.engram/` dotdir isolation, path resolution, and AI CLI environment redirection. |
| **[`cp949_verification.md`](cp949_verification.md)** | **Technical Specification** | Architecture and test procedures for CP949 Korean-locale and non-ASCII path resilience. |
| **[`release_gate.md`](release_gate.md)** | **Release & Governance** | Policy trust root, clean-room verification gates, candidate packaging, and post-release closure audits. |
| **[`design/`](design/)** | **Architecture Decisions (ADRs)** | Ratified architectural design specifications and decision records (UX simplification, system rename, environment resilience). |
| [`design/plan-update-advice-parity-2026-10-12.md`](design/plan-update-advice-parity-2026-10-12.md) | Implementation Plan | Engram PR-B advice/guard parity, baseline SSOT, 3.9.2 release scope, and audit gates (reference only). |
| [`design/plan-venv-hardening-2026-10-12.md`](design/plan-venv-hardening-2026-10-12.md) | Implementation Plan | Engram PR-B2 unanimous P3 venv hardening, 3.9.3 scope, fault matrix, and recovery contracts (reference only). |
| [`design/blueprint-engram-architecture.md`](design/blueprint-engram-architecture.md) | Architecture Design | Retained Core/Module/Extension classification, invariants, contracts, and G0-G8 gate model with implementation status per rule. |
| [`design/blueprint-method-and-lifecycle.md`](design/blueprint-method-and-lifecycle.md) | Method & Lifecycle Design | Retained method rules and release lifecycle with implementation status. |
| [`design/component-registry.json`](design/component-registry.json) | Component Classification Data | Starting point for the unimplemented component boundary tests. |
| [`design/engram-ux-simplification-RATIFIED-2026-09-12.md`](design/engram-ux-simplification-RATIFIED-2026-09-12.md) | Ratified ADR | UX and structure simplification (round-2 ratification). |
| [`design/engram-sys-rename-phase4-batch-entrypoint-design-2026-09-20.md`](design/engram-sys-rename-phase4-batch-entrypoint-design-2026-09-20.md) | Implemented Design | `_sys` folder renameability and batch-entrypoint discovery (phase 4). |
| [`design/engram-env-resilience-design-2026-10-02.md`](design/engram-env-resilience-design-2026-10-02.md) | Implemented Design | Python/venv lifecycle, root relocation and backup retention (v3.6.1). |
| [`design/plan-deps-latest-2026-10-21.md`](design/plan-deps-latest-2026-10-21.md) | Implementation Plan | Latest validated runtime defaults and dependency PRs (v3.10.0, reference only). |
| **[`history/`](history/)** | **Historical Archives** | Historical records, backlog migrations, and audit artifacts preserved from repository milestones. |
| [`history/audit-2026-10.md`](history/audit-2026-10.md) | Historical Audit | October 2026 findings, dispositions, hosted-run lessons, and maintainer decisions (frozen 2026-10-21). |
| [`history/handoff-2026-10.md`](history/handoff-2026-10.md) | Historical Record | Per-release maintainer handoff notes v3.9.6 to v3.11.7 (frozen 2026-11-09). |
| [`history/recursive-mece-release-audit-2026-09-28.md`](history/recursive-mece-release-audit-2026-09-28.md) | Historical Audit | Whole-package recursive MECE release review (2026-09-28). |
| [`history/migrated-backlog-open-items.md`](history/migrated-backlog-open-items.md) | Historical Record | The two deferred items kept when the backlog moved to PeerHub (2026-09-20). |

## Guiding Principles

1. **Normative Separation**: User-facing entrypoints are [`README.md`](../README.md), [`CONTRIBUTING.md`](../CONTRIBUTING.md), and [`CONVENTION.md`](../CONVENTION.md) in the repository root. Technical deep-dives and ADRs live under `docs/`.
2. **Zero-Bloat Packaging**: Files under `docs/` are development and governance references tracked in Git; they are never bundled into the production release archive by `tools/winget/build_package.py`.
3. **Immutability of Ratified Specs**: Ratified documents and implementation plans in `design/` record decisions made at specific milestones. Revisions are proposed via new ADRs rather than silently mutating historical rulings. The two `blueprint-*.md` files and `component-registry.json` are living status documents: their rules are fixed, their implementation-status columns are updated as code changes.
