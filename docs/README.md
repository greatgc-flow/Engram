# Engram Documentation

This directory contains architectural specifications, design decision records, and historical archives for the Engram portable developer runtime.

## Documentation Taxonomy (MECE)

| Directory / File | Category | Description |
| :--- | :--- | :--- |
| **[`cli_reference.md`](cli_reference.md)** | **User Guide** | Complete command reference covering every engram verb, option, example, exit code, and safety guarantee. |
| **[`user_lifecycle_guide.md`](user_lifecycle_guide.md)** | **User Guide** | Personal settings, AI session data, backup, restore, reset, and uninstallation workflows. |
| **[`env_resilience_guide.md`](env_resilience_guide.md)** | **User Guide** | Python/venv repair, root folder relocation, Python updates, and the backup registry. |
| **[`engram-dotdir.md`](engram-dotdir.md)** | **Technical Specification** | Normative specification for `.engram/` dotdir isolation, path resolution, and AI CLI environment redirection. |
| **[`cp949_verification.md`](cp949_verification.md)** | **Technical Specification** | Architecture and test procedures for CP949 Korean-locale and non-ASCII path resilience. |
| **[`release_gate.md`](release_gate.md)** | **Release & Governance** | Policy trust root, clean-room verification gates, candidate packaging, and post-release closure audits. |
| **[`design/`](design/)** | **Architecture Decisions (ADRs)** | Ratified architectural design specifications and decision records (UX simplification, system rename, environment resilience). |
| **[`history/`](history/)** | **Historical Archives** | Historical records, backlog migrations, and audit artifacts preserved from repository milestones. |
| [`history/audit-2026-10.md`](history/audit-2026-10.md) | Historical Audit | October 2026 findings, dispositions, hosted-run lessons, and open maintainer decisions. |

The latest whole-package release review is
[`history/recursive-mece-release-audit-2026-09-28.md`](history/recursive-mece-release-audit-2026-09-28.md).

## Guiding Principles

1. **Normative Separation**: User-facing entrypoints are [`README.md`](../README.md), [`CONTRIBUTING.md`](../CONTRIBUTING.md), and [`CONVENTION.md`](../CONVENTION.md) in the repository root. Technical deep-dives and ADRs live under `docs/`.
2. **Zero-Bloat Packaging**: Files under `docs/` are development and governance references tracked in Git; they are never bundled into the production release archive by `tools/winget/build_package.py`.
3. **Immutability of Ratified Specs**: Ratified documents in `design/` record decisions made at specific milestones. Revisions are proposed via new ADRs rather than silently mutating historical rulings.
