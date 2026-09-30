<div align="center">
  <h1>📦 Engram</h1>
  <p><b>A clean, portable Windows dev environment. Nothing more.</b></p>
  <p>Virtualized Python/Node/Git/VS Code under one drive-letter-free tree — install it, register it, work, uninstall it without a trace.</p>

  [![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078d4.svg)](https://www.microsoft.com/windows)
  [![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
  [![CI](https://github.com/greatgc-flow/Engram/actions/workflows/ci.yml/badge.svg)](https://github.com/greatgc-flow/Engram/actions/workflows/ci.yml)
  [![AI collaboration: peerhub](https://img.shields.io/badge/AI%20collaboration-peerhub-8a2be2.svg)](https://github.com/greatgc-flow/peerhub)
</div>

<br/>

Engram bootstraps a self-contained Windows dev environment — Python, Node.js, Git, VS Code, and a handful of CLI tools — into one portable folder, with no host-machine installs and no registry residue. `menu enable`/`menu disable` add/remove the right-click context menu; `uninstall` removes every trace, including a background helper that finishes cleanup after the process holding the folder open has exited.

> **Note on scope:** Engram used to also orchestrate AI-to-AI peer collaboration directly. That entire layer has moved to the standalone [**peerhub**](https://github.com/greatgc-flow/peerhub) package — Engram itself no longer knows what a "peer debate" or "consensus round" is. What Engram *does* still do on the AI-tooling side is install, update, and status-check third-party AI CLIs (Claude Code, Codex, etc.) as ordinary managed tools, exactly like it manages ripgrep or Node.js. PeerHub is installed, configured, discovered, and run independently; neither product requires the other.

## What it does

- **Portable runtime virtualization** — Python, Node.js, Git, VS Code, and PowerShell are downloaded, pinned by version+hash in `_sys/runtimes.json`, and run entirely from inside the portable folder. Nothing touches `C:\Program Files` or the registry.
- **Generic tool catalog** — dev CLI tools (ripgrep, bat, fd, delta, fzf, jq, gh, sqlite, oh-my-posh) install/update through one pinned, hash-verified pipeline (`_sys/runtimes.json`'s `tools` section).
- **AI-CLI lifecycle management** — a separate catalog (`_sys/tool-catalog.v1.json`) tracks Claude Code / Codex / agy the same way: install, version-pin, canary-verify. Engram never talks to these tools' models or protocols — it only manages the binaries.
- **No junctions or SUBST drive** — Engram uses no directory junctions and mounts no virtual drive: AI-CLI personal config is redirected via plain environment variables instead (see `docs/engram-dotdir.md`), and paths are always resolved physical.
- **Real uninstall** — `engram uninstall` computes an installation-scoped ID, writes a journal outside the install directory (survives the directory's own deletion), and hands off to an external helper that waits for the running process to exit before purging the folder — so a running instance never tries to delete the directory it's executing from.
- **On-demand tool updates** — `engram update` discovers newer versions of every catalog entry and applies them through the same pinned, hash-verified install path used for first-time setup.
- **Zero-bloat by construction** — the packaging pipeline (`tools/winget/build_package.py`) only bundles an explicit root-file allowlist plus the runtime-owned subset of `_sys/`; source-only tests, maintainer tools, caches, temporary files, and mutable state are excluded.

## Prerequisites
- Windows 10 or 11
- Git for Windows (only needed if installing via `git clone`; the Winget path is self-contained)

## Quick Start

**Option A (Portable Zip):**
1. Download the latest `Engram-vX.Y.Z-portable-x64.zip` release.
2. Extract the zip to a folder on your drive (recommended: a clean path without `&`, `%`, or `^` characters, e.g. `C:\Engram`).
3. Double-click `Engram.exe` or run `engram` from a terminal. 

**Option B (WinGet):**
```powershell
winget install greatgc-flow.Engram
```

WinGet publication can lag a GitHub release while Microsoft reviews the community
manifest. Confirm availability with `winget search greatgc-flow.Engram`; if the
current version is not listed yet, use the portable ZIP above. A manifest in this
source repository alone does not make the command installable.

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
| `update [--check] [--dry-run] [--yes] [--refresh] [--only NAME[,NAME...]] [--allow-major-runtime-upgrade]` | Discover and apply updates across the catalog. `--check` prints the plan without modifying runtimes/tools (saves proposal artifacts under `_sys/data/state/update/proposals/`) and exits 1 if anything couldn't be checked. `--dry-run` discovers and shows the proposal but applies nothing. `--yes`/`-y` skips confirmation. `--refresh`/`-r` bypasses discovery cache to force a fresh network check. `--only` restricts to specific components (supports comma-separated names and aliases: `cc`, `cx`, `ag`). `--allow-major-runtime-upgrade` permits a base runtime (e.g. Node.js) to jump a major version; without it, major-version updates are discovered but not auto-applied. Run `engram update --help` for the authoritative, always-current flag list. | 0 success or nothing to do; 1 one or more components failed / `--check` found an issue; 2 usage error; 3 declined |
| `doctor [--json]` | Zero-network health check: verifies Python consistency, components, context menu registration, and root path hygiene (warns if path contains `&`, `%`, `^`, or `!`). | 0 healthy; 1 broken |
| `menu` / `menu status` | Read-only: check whether context menu entries are present. | 0 |
| `menu enable` | Apply registry entries to add right-click context menu. Idempotent. | 0 / 1 |
| `menu disable` | Remove right-click context menu registry entries. Idempotent. | 0 / 1 |
| `menu clean` | Clean up orphaned context menu entries. | 0 / 1 |
| `tidy [--apply] [--deep] [--only NAME[,NAME...]]` | Default is a dry run (print plan). `--apply` deletes planned items: temp dirs, `__pycache__`, pytest/npm/pip/winget/VS Code caches, and AG brain logs. `--deep` additionally cleans old launcher logs. `--only` restricts to specific categories (run `engram tidy --help` for the full list). | 0 |
| `uninstall [--yes] [--purge-data] [--dry-run] [--apply]` | Deletes Engram's program files by allowlist. Leaves `.engram/` (settings/credentials) and `workspace/` untouched by default. `--purge-data` adds `.engram/`, `.peerhub/`, and discovered dotdirs to the deletion plan, requiring un-bypassable typed confirmation. Hands off to a background helper that waits for Engram to exit before deletion. `--dry-run` displays preview without deleting anything. | 0 handed off / dry-run; 1 failed before hand-off; 3 declined |
| `backup [--out PATH] [--include-uncovered]` | Back up personal AI-CLI data (memory, settings, rules, skills, session transcripts — never credentials, by construction) to a single `.zip` (default: `_sys/data/backups/engram_backup_<timestamp>.zip`). Discovers uncovered project configs (`.peerhub`, etc.) and packages them as `custom_extras`. Warns, doesn't refuse, if a managed AI CLI is currently running. | 0 |
| `restore PATH [--apply] [--force]` | Restore personal AI-CLI data from a `.zip` or legacy folder-shaped bundle. Dry-run preview by default; pass `--apply` to execute restoration. Refuses if a managed AI CLI is running. Takes an automatic pre-restore snapshot unless `--force`. Restores custom extras to original relative locations. | 0 success / dry-run; 1 refused (process running) or invalid path; 2 usage error |
| `reset [--apply] [--yes] [--all]` | Deletes personal AI-CLI state. Dry-run preview by default; pass `--apply` to execute. Gated behind mandatory fail-closed pre-reset safety snapshot (`safety_pre_reset_*.zip`). Default scope is `.engram/` and `.peerhub/` only. `--all` also deletes `workspace/`. Refuses if a managed AI CLI is running. See [User Lifecycle Guide](docs/user_lifecycle_guide.md) for details. | 0 success / dry-run; 1 refused (process running); 3 declined |
| `version` / `--version` / `-v` | Print the current version (e.g. `Engram <version> (Portable Dev Runtime)`). | 0 |
| `help` / `--help` / `-h` / `/?` | List the available commands. Every verb above also accepts its own `--help`/`-h`/`/?` (e.g. `engram update --help`) for that verb's full, authoritative option list. | 0 |

`install`, `setup`, `status`, `register`, `unregister`, `menu-cleanup`, `cleanup`, `launch`, and `start` are retired verbs — each prints its replacement and exits 2 rather than silently aliasing.

To install or update individual tools or runtimes directly:
```bat
# Single component:
engram update --only claude
engram update --only codex
engram update --only agy

# Multiple components using comma-separated names or aliases:
engram update --only cc,cx,ag
engram update --only nodejs,vscode
```

## AI-to-AI collaboration → peerhub

Engram's job ends at "the AI CLI binary is installed, current, and reachable." Everything past that — inter-peer messaging, consensus rounds, quota-aware routing, governance directives — lives in the separate [**peerhub**](https://github.com/greatgc-flow/peerhub) package. Engram never installs it, pins its version, invokes it, or injects PeerHub-specific environment variables. PeerHub owns its installation, configuration, CLI discovery, and runtime state, and works without Engram:

```bash
pip install peerhub
peerhub adapter discover   # you can run this yourself to confirm which AI CLIs Engram installed are reachable
```

See [peerhub's own README](https://github.com/greatgc-flow/peerhub#readme) for the full command set.

## AI CLI personal config: `.engram/`

Every AI CLI Engram manages reads and writes its personal, durable data (memory, settings, session history) from one consolidated, automatic root — `.engram/{claude,codex,agy}/`. PeerHub is never configured or selectively handled by Engram and is absent from Engram's backup/reset schema. Explicit whole-tree operations such as `reset --all` or `uninstall --purge-data` still delete the user-confirmed `workspace/` tree regardless of which external tools wrote files there. No `subst` drive, no directory junction, and nothing to run by hand: AI-CLI redirection uses ordinary environment variables applied at every launch. `.engram/` is a **live** root — it accumulates real credentials and caches over time, so it is gitignored and never copied wholesale; [`_sys/checks/backup_personal_data.py`](_sys/checks/backup_personal_data.py) extracts just the safe, durable subset for backup instead. Full detail: [`docs/engram-dotdir.md`](docs/engram-dotdir.md).

## What's next

See [2026-09-03_separation-completion-backlog.md](https://github.com/greatgc-flow/peerhub/blob/main/docs/history/from-engram-repo/sessions/2026-09-03_separation-completion-backlog.md) for the full remaining-work backlog on both sides of the separation (Engram + peerhub), and what's deliberately deferred and why.

## Contributing / Reporting issues

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for local dev setup, testing, and branch/commit conventions, or report bugs and suggest features on the [GitHub Issues](https://github.com/greatgc-flow/Engram/issues) tracker.

For a useful feedback report, run `engram doctor --json` and include its output,
the failing command, exit code, and any applicable file under
`_sys/data/logs/` or `_sys/data/state/update/`. Do **not** upload `.engram/`
wholesale because it can contain credentials and session history. Maintainers
close the loop by turning confirmed failures into regression tests, declarative
catalog/config changes where possible, or an explicit README warning when the
constraint belongs to Windows or a third-party tool.

## Test tiers

```cmd
python -m pytest _sys/tests/unit
_sys\tests\run-tests.bat --all
_sys\tests\run-sandbox-test.bat
```

The first two commands are deterministic source tests. The Sandbox gate performs
a from-scratch bootstrap, real downloads, `doctor`, and fresh online update
discovery, so it is required before release. It also runs every Saturday at
03:00 Asia/Seoul on a dedicated Windows machine registered with the
`engram-sandbox` self-hosted-runner label; evidence is retained as a workflow
artifact for 30 days. Engram
does not call AI models; therefore no Engram test spends model tokens. Model-call
and quota tests belong to PeerHub's separate `slow`/`e2e` tiers.

The Sandbox runner must run in a logged-in interactive Windows session via the
Actions runner's `run.cmd`; a runner installed as a Windows service executes in
Session 0 and cannot host Windows Sandbox. The workflow checks this before it
starts the 30-minute Sandbox wait.

## Trust Signals

- **Version SSOT:** [`_sys/core/version.json`](_sys/core/version.json)
- **Tool catalogs:** [`_sys/runtimes.json`](_sys/runtimes.json) (runtimes + generic dev tools), [`_sys/tool-catalog.v1.json`](_sys/tool-catalog.v1.json) (AI CLIs)
- **Conventions:** [`CONVENTION.md`](CONVENTION.md)
- **Contributing:** [`CONTRIBUTING.md`](CONTRIBUTING.md)
- **Validation:** the unit-test suite under [`_sys/tests/unit`](_sys/tests/unit) plus pre-commit consistency checks (`check_encoding`, `check_unreferenced_functions`, `check_root_hygiene`, `check_tool_updates`, `saturation_scan`) under [`_sys/checks`](_sys/checks).
