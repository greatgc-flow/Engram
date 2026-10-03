# Engram Documentation

This directory contains architectural specifications, design decision records, and historical archives for the Engram portable developer runtime.

## Documentation Taxonomy (MECE)

| Directory / File | Category | Description |
| :--- | :--- | :--- |
| **[`design/`](design/)** | **Architecture Decisions (ADRs & RFCs)** | Architectural design proposals, peer debate outcomes, and ratified specifications (e.g. UX simplification, system rename). |
| **[`engram-dotdir.md`](engram-dotdir.md)** | **Technical Specifications** | Normative technical specification for `.engram/` dotdir isolation, path resolution, and environment variable redirection for AI CLIs. |
| **[`cli_reference.md`](cli_reference.md)** | **User Guide** | Complete `engram` command reference: command groups, every command's options, examples and exit codes, the safety model (preview by default, move-never-delete, journals) and a "which command do I need" table. |
| **[`env_resilience_guide.md`](env_resilience_guide.md)** | **User Guide** | Python/venv repair, folder relocation, Python updates, and the backup registry (`engram repair`, `relocate`, `snapshots`). |
| **[`history/`](history/)** | **Historical Archives** | Historical records and artifacts preserved from repository separations and backlog migrations (e.g. open items preserved during the PeerHub migration). |

The latest whole-package release review is
[`history/recursive-mece-release-audit-2026-09-28.md`](history/recursive-mece-release-audit-2026-09-28.md).

## Guiding Principles

1. **Normative Separation**: User-facing entrypoints are [`README.md`](../README.md), [`CONTRIBUTING.md`](../CONTRIBUTING.md), and [`CONVENTION.md`](../CONVENTION.md) in the repository root. Technical deep-dives and ADRs live under `docs/`.
2. **Zero-Bloat Packaging**: Files under `docs/` are development and governance references tracked in Git; they are never bundled into the production release archive by `tools/winget/build_package.py`.
3. **Immutability of Ratified Specs**: Ratified documents in `design/` record decisions made at specific milestones. Revisions are proposed via new ADRs rather than silently mutating historical rulings.
