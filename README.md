<div align="center">
  <h1>📦 Engram</h1>
  <p><b>A clean, portable Windows dev environment. Nothing more.</b></p>
  <p>Virtualized Python/Node/Git/VS Code under one drive-letter-free tree — install it, register it, work, uninstall it without a trace.</p>

  [![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078d4.svg)](https://www.microsoft.com/windows)
  [![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
  [![Tests: passing](https://img.shields.io/badge/tests-passing-brightgreen.svg)](_sys/tests/unit)
  [![AI collaboration: peerhub](https://img.shields.io/badge/AI%20collaboration-peerhub-8a2be2.svg)](https://github.com/greatgc-flow/peerhub)
</div>

<br/>

Engram bootstraps a self-contained Windows dev environment — Python, Node.js, Git, VS Code, and a handful of CLI tools — into one portable folder, with no host-machine installs and no registry residue. `register` sets up the right-click context menu; `unregister`/`uninstall` remove every trace, including a background helper that finishes cleanup after the process holding the folder open has exited.

> **Note on scope:** Engram used to also orchestrate AI-to-AI peer collaboration directly. That entire layer has moved to the standalone [**peerhub**](https://github.com/greatgc-flow/peerhub) package — Engram itself no longer knows what a "peer debate" or "consensus round" is. What Engram *does* still do on the AI-tooling side is install, update, and status-check third-party AI CLIs (Claude Code, Codex, etc.) as ordinary managed tools, exactly like it manages ripgrep or Node.js. If you want AI-to-AI collaboration, install peerhub separately on top of an Engram environment (Engram provides an intentional external-tool compatibility bridge via `PEERHUB_CONFIG_HOME` so PeerHub's global config is isolated to `.engram/peerhub/config/`).

## What it does

- **Portable runtime virtualization** — Python, Node.js, Git, VS Code, and PowerShell are downloaded, pinned by version+hash in `_sys/runtimes.json`, and run entirely from inside the portable folder. Nothing touches `C:\Program Files` or the registry.
- **Generic tool catalog** — dev CLI tools (ripgrep, bat, fd, delta, fzf, jq, gh, sqlite, oh-my-posh) install/update through one pinned, hash-verified pipeline (`_sys/runtimes.json`'s `tools` section).
- **AI-CLI lifecycle management** — a separate catalog (`_sys/tool-catalog.v1.json`) tracks Claude Code / Codex / agy the same way: install, version-pin, canary-verify. Engram never talks to these tools' models or protocols — it only manages the binaries.
- **No junctions or SUBST drive** — Engram uses no directory junctions and mounts no virtual drive: AI-CLI personal config is redirected via plain environment variables instead (see `docs/engram-dotdir.md`), and paths are always resolved physical.
- **Real uninstall** — `engram uninstall` computes an installation-scoped ID, writes a journal outside the install directory (survives the directory's own deletion), and hands off to an external helper that waits for the running process to exit before purging the folder — so a running instance never tries to delete the directory it's executing from.
- **On-demand tool updates** — `engram update` discovers newer versions of every catalog entry and applies them through the same pinned, hash-verified install path used for first-time setup.
- **Zero-bloat by construction** — the packaging pipeline (`tools/winget/build_package.py`) only ever bundles an explicit root-file allowlist plus `_sys/`, minus caches/temp/state; nothing accumulates into the distributed archive that wasn't put there on purpose.

## Prerequisites
- Windows 10 or 11
- Git for Windows (only needed if installing via `git clone`; the Winget path is self-contained)

## Quick Start

1. Download the latest `Engram-vX.Y.Z-portable-x64.zip` release.
2. Extract the zip to a folder on your drive.
3. Double-click `Engram.exe` or run `engram` from a terminal. 

The first run will prompt to bootstrap the portable environment (Python, Node, Git, VS Code, tools) and optionally register the Explorer right-click context menu.

**Upgrading an existing install:**
1. Close VS Code and any shell launched from the install.
2. Extract the new zip **into the existing install folder**, choosing *Replace* for conflicts.
3. Run `engram` (or `engram doctor`).

> Run `engram update` to keep Engram and everything it manages current. Anything it cannot check automatically is listed by name under "Not checked" — never counted as up to date.

## Command Reference

`engram.cmd` (or `Engram.exe`) dispatches every lifecycle action. There are no other batch files in the root.

| Verb | Behavior | Exit codes |
|---|---|---|
| `engram` / `open [PATH]` | Open a workspace (default action). On first run (no Python), prints plan and prompts to set up here. If missing, prompts to add right-click menu entry. Otherwise dispatches the `start` pipeline. | 0 ok; 1 not set up / declined / bootstrap failed; launcher errors propagated |
| `update [--check] [--yes] [--only NAME[,NAME...]]` | Discover and apply updates across the catalog. `--check` prints the plan without writing. `--yes` skips confirmation. `--only` restricts to specific components. | 0 success or nothing to do; 1 one or more components failed; 2 usage error; 3 declined |
| `doctor [--json]` | Unchanged zero-network contract reporting environment health. | 0 healthy; 1 broken |
| `menu` / `menu status` | Read-only: check whether context menu entries are present. | 0 |
| `menu enable` | Apply registry entries to add right-click context menu. Idempotent. | 0 / 1 |
| `menu disable` | Remove right-click context menu registry entries. Idempotent. | 0 / 1 |
| `menu clean` | Clean up orphaned context menu entries. | 0 / 1 |
| `tidy [--apply] [--deep]` | Default is a dry run (print plan). `--apply` deletes planned items (pytest/VS Code/npm caches). `--deep` also cleans setup files, old rollback dirs, and `__pycache__`. | 0 |
| `uninstall [--yes] [--purge-data]` | Deletes Engram's program files by allowlist. Leaves `.engram/` (settings/credentials) and `workspace/` untouched by default. `--purge-data` adds `.engram/` and `workspace/` to the deletion plan, requiring un-bypassable typed confirmation. Hands off to a background helper that waits for Engram to exit before deletion. | 0 handed off; 1 failed before hand-off; 3 declined |
| `backup [--out PATH]` | Back up personal AI-CLI data (memory, settings, rules, skills, session transcripts — never credentials, by construction) to a single `.zip` (default: `_sys/data/backups/engram_backup_<timestamp>.zip`). Warns, doesn't refuse, if a managed AI CLI is currently running. | 0 |
| `restore PATH [--force]` | Restore personal AI-CLI data from a `.zip` or legacy folder-shaped bundle. Refuses if a managed AI CLI is running. Takes an automatic pre-restore snapshot unless `--force`. `--force` also allows overwriting existing live session/project data. | 0 success; 1 refused (process running) or invalid path; 2 usage error |
| `reset [--yes] [--all]` | Deletes personal AI-CLI state. Default scope is `.engram/` only, after `[y/N]` confirmation (skippable with `--yes`). `--all` also deletes `workspace/`, gated behind the same typed-folder-name confirmation `uninstall --purge-data` uses. Refuses if a managed AI CLI is running. | 0 success; 1 refused (process running); 3 declined |
| `version` / `--version` / `-v` | Print the current version (e.g. `Engram <version> (Portable Dev Runtime)`). | 0 |
| `help` / `--help` / `-h` / `/?` | List the available commands. | 0 |

`install`, `setup`, `status`, `register`, `unregister`, `menu-cleanup`, `cleanup`, `launch`, and `start` are retired verbs — each prints its replacement and exits 2 rather than silently aliasing.

To install or update an individual AI CLI tool directly, you can use:
```bat
engram update --only claude
engram update --only codex
engram update --only agy
```

## AI-to-AI collaboration → peerhub

Engram's job ends at "the AI CLI binary is installed, current, and reachable." Everything past that — inter-peer messaging, consensus rounds, quota-aware routing, governance directives — lives in the separate [**peerhub**](https://github.com/greatgc-flow/peerhub) package. Engram never installs it, pins its version, or invokes it — that would reintroduce exactly the coupling this separation removed. (For environment isolation, Engram's `_sys/env.json` declares an intentional external-tool compatibility bridge `PEERHUB_CONFIG_HOME`, ensuring that when peerhub runs in an Engram session, its global configuration resides under `.engram/peerhub/config/` rather than the host `%USERPROFILE%`.) Install it yourself, whenever you want it, entirely independently:

```bash
pip install peerhub
peerhub adapter discover   # you can run this yourself to confirm which AI CLIs Engram installed are reachable
```

See [peerhub's own README](https://github.com/greatgc-flow/peerhub#readme) for the full command set.

## AI CLI personal config: `.engram/`

Every AI CLI Engram manages reads and writes its personal, durable data (memory, settings, session history) from one consolidated, automatic root — `.engram/{claude,codex,agy}/`, plus peerhub's own global config at `.engram/peerhub/config/` via the `PEERHUB_CONFIG_HOME` environment compatibility bridge. No `subst` drive, no directory junction, and nothing to run by hand: it's pure environment-variable redirection, applied at every launch. `.engram/` is a **live** root — it accumulates real credentials and caches over time, so it's gitignored and never copied wholesale; [`_sys/checks/backup_personal_data.py`](_sys/checks/backup_personal_data.py) extracts just the safe, durable subset for backup instead. Full detail: [`docs/engram-dotdir.md`](docs/engram-dotdir.md).

## What's next

See [2026-09-03_separation-completion-backlog.md](https://github.com/greatgc-flow/peerhub/blob/main/docs/history/from-engram-repo/sessions/2026-09-03_separation-completion-backlog.md) for the full remaining-work backlog on both sides of the separation (Engram + peerhub), and what's deliberately deferred and why.

## Trust Signals

- **Version SSOT:** [`_sys/core/version.json`](_sys/core/version.json)
- **Tool catalogs:** [`_sys/runtimes.json`](_sys/runtimes.json) (runtimes + generic dev tools), [`_sys/tool-catalog.v1.json`](_sys/tool-catalog.v1.json) (AI CLIs)
- **Conventions:** [`CONVENTION.md`](CONVENTION.md)
- **Validation:** the unit-test suite under [`_sys/tests/unit`](_sys/tests/unit) plus pre-commit consistency checks (`check_encoding`, `check_unreferenced_functions`, `check_root_hygiene`, `check_tool_updates`, `saturation_scan`) under [`_sys/checks`](_sys/checks).
