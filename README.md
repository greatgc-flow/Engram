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

- **Portable runtime virtualization** — Python, Node.js, Git, VS Code, and PowerShell are downloaded, pinned by version+hash in the tracked [`_sys/defaults/runtimes.json`](_sys/defaults/runtimes.json), and run entirely from inside the portable folder. Setup materializes the operational copy at `_sys/runtimes.json`. Nothing touches `C:\Program Files` or the registry.
- **Generic tool catalog** — dev CLI tools (ripgrep, bat, fd, delta, fzf, jq, gh, sqlite, oh-my-posh, exiftool, yq, sd, hyperfine, dust, ouch) install/update through one pinned, hash-verified pipeline (the `tools` section of tracked [`_sys/defaults/runtimes.json`](_sys/defaults/runtimes.json)); setup materializes the operational copy at `_sys/runtimes.json`.
  Existing installations adopt newly shipped tool entries with `_sys\core\dispatch.bat migrate-layout`, then install them with `engram update`. ExifTool is manually pinned: version discovery is disabled and its SHA-256 must be recomputed by hand on each bump. Ouch provides archive operations with its own CLI; it does not provide `7z.exe` compatibility. `required_paths` declares companion payload directories checked before activation and by doctor; it detects missing directories, not corruption of individual files.

- **AI-CLI lifecycle management** — a separate tracked catalog ([`_sys/defaults/tool-catalog.v1.json`](_sys/defaults/tool-catalog.v1.json)) tracks Claude Code / Codex / agy the same way: install, version-pin, canary-verify. Setup materializes the operational copy at `_sys/tool-catalog.v1.json`. Engram never talks to these tools' models or protocols — it only manages the binaries.
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
3. Double-click `Engram.exe` or run `engram` from a terminal. `engram open PATH` opens the folder in the managed VS Code and exits 1 if VS Code is missing.

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
Run `engram update` (or `engram update --yes`) to discover and apply updates for Engram, runtimes, and managed tools. Core updates stage and execute detached replacement with verified automatic rollback on failure (`FAILED_ROLLED_BACK`), while environment updates take safety snapshots manageable via `engram snapshots` or reversible via `engram repair --rollback` if interrupted. Anything that cannot be checked automatically is listed under "Not checked" — never counted as up to date. The supported update/repair boundary is stated in [`docs/user_lifecycle_guide.md`](docs/user_lifecycle_guide.md).

## Quick start for AI agents

To inspect and operate Engram with minimum token consumption:
1. **CLI discovery**: Run `engram help` for the verb index, then `engram help <verb>` for options, defaults, and exit codes; [`docs/cli_reference.md`](docs/cli_reference.md) is generated verbatim from these help files.
2. **Health & limitations**: Run `engram doctor --json` for a zero-network structured report; declarative limitations are defined in [`_sys/limitations.json`](_sys/limitations.json).
3. **Evidence & gates**: Policy root is [`tools/release_gate/release_policy.json`](tools/release_gate/release_policy.json), canonical gate specifications live in [`docs/release_gate.md`](docs/release_gate.md), and verification evidence is written to `release/` and `evidence/`.

## Command Reference

`engram.cmd` (or `Engram.exe`) dispatches every lifecycle action. There are no other batch files in the root. Every
command has its own `--help` (also `engram help <command>`) with options and their defaults, examples and exit codes;
the complete reference is [`docs/cli_reference.md`](docs/cli_reference.md).

| Group | Command | Purpose |
|---|---|---|
| Daily use | `engram` / `open [PATH]` | Open a workspace (the default action). First run offers to set Engram up here. |
| | `update` | Check for and apply updates (runtimes, tools, AI CLIs, `--only python` for the embedded Python). |
| | `doctor [--json]` | Read-only, zero-network health report. |
| | `menu [status\|enable\|disable\|clean]` | Manage the Explorer right-click entry. |
| | `version` | Print the version (`--version`, `-v`). |
| Health & repair | `isolation check` | Report whether optional Windows Sandbox / WSL2 isolation is available (read-only). |
| | `repair` | Detect and fix a broken Python/venv, launchers or manifest (previews until `--apply`). |
| | `relocate` | Re-anchor the install after the folder was moved or renamed. |
| | `tidy` | Clean temp files, caches and expired environment backups (previews until `--apply`). |
| Backups & state | `backup` | Back up personal AI data (`.engram/`) to a zip. |
| | `restore PATH` | Restore personal AI data (previews until `--apply`). |
| | `snapshots` | List, pin and restore environment backups (Python and venv backups are not restorable yet). |
| Removal | `reset` | Delete personal AI data after a safety snapshot (previews until `--apply`). |
| | `uninstall` | Remove Engram's program files; your data is kept unless `--purge-data`. |

Shared flags mean the same everywhere: `--apply` executes (the commands marked above preview first), `--dry-run`
previews, `--yes`/`-y` skips a prompt, `--json` gives machine-readable output (`doctor`, `isolation check`, `repair`,
`relocate`, `snapshots list`). Which commands ask before executing, and how recovery differs, is stated once in the
Safety model of `engram help` ([`docs/cli_reference.md`](docs/cli_reference.md#safety-model)). Replaced Python/venv
copies are moved into a backup registry, never deleted outright.

Common workflows:

```bat
engram update --yes                     :: keep everything current
engram update --only python --yes       :: update just the embedded Python
engram doctor                           :: something feels broken ...
engram repair --apply                   :: ... fix it (plain 'engram repair' previews)
engram relocate --apply                 :: after moving or renaming the folder
engram snapshots list                   :: see environment backups; 'snapshots pin NAME' keeps one
engram tidy --apply                     :: reclaim disk space
engram tidy --adopt-legacy --apply      :: file leftover _sys\env\<name>_old folders as backups (14 days)
engram tidy --purge-legacy --apply      :: ... or delete them right now (asks first)
engram backup                           :: save your AI data to a zip
engram restore D:\backups\my.zip --apply
engram reset --apply                    :: start over, keep the programs
engram uninstall --dry-run              :: preview removal, then run 'engram uninstall'
```

Exit codes and the retired verbs (each prints its replacement and exits 2) are listed once in
[`docs/cli_reference.md`](docs/cli_reference.md#exit-codes).

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

Claude Code, Codex and the GitHub CLI read and write their personal, durable data (memory, settings, session history) from one consolidated, automatic root — `.engram/{claude,codex,gh}/`; Antigravity (`agy`) keeps its state in the user profile and is not redirected. Backup and reset operate on a fixed allowlist of durable `.engram/` data plus discovered dot-folders (such as `.peerhub`, packaged in backup via `--include-uncovered` and cleared under a verified safety snapshot in reset) while strictly excluding credentials and secrets per [`docs/user_lifecycle_guide.md`](docs/user_lifecycle_guide.md). Whole-tree operations such as `uninstall --purge-data` still delete the user-confirmed `workspace/` tree regardless of which external tools wrote files there. No `subst` drive, no directory junction, and nothing to run by hand: AI-CLI redirection uses ordinary environment variables applied at every launch. `.engram/` is a **live** root — it accumulates real credentials and caches over time, so it is gitignored and never copied wholesale; `engram backup` extracts just the safe, durable subset instead. Full detail: [`docs/engram-dotdir.md`](docs/engram-dotdir.md).

## Known limitations

- Pip's 'Ignoring invalid distribution' can mean interrupted-upgrade ~* leftovers; run `engram doctor` and `engram repair --only venv --apply` (unproven copies are kept).

`engram doctor` evaluates declarative environment limitation warnings (reported, non-fatal):
- **Path characters**: Root paths with `&`, `%`, `^`, `!`, `(`, `)`, `'` or non-ASCII characters may break batch wrappers, PowerShell, or Node.js AI CLIs.
- **Console code page**: Non-UTF-8 code pages (e.g. 949) may garble console output (`PYTHONUTF8` is set for Engram's own processes).
- **Cloud-sync folders**: Placing Engram in OneDrive, Dropbox, or Google Drive risks sync/AV locks (backup, restore, and reset fail closed on locked files).
- **Path length**: Paths approaching Windows `MAX_PATH` (260 characters) may cause nested tool or dependency installation failures.

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
discovery, so it is required before release. The release workflow also runs it
weekly; the self-hosted Windows Sandbox job is opt-in and runs only when an
interactive `engram-sandbox` runner is registered, otherwise a hosted clean-room
job provides the evidence (see [`docs/release_gate.md`](docs/release_gate.md)).
Engram does not call AI models; therefore no Engram test spends model tokens.
Model-call and quota tests belong to PeerHub's separate `slow`/`e2e` tiers.

## Trust Signals

- **Version SSOT:** [`_sys/core/version.json`](_sys/core/version.json)
- **Tool catalogs:** tracked [`_sys/defaults/runtimes.json`](_sys/defaults/runtimes.json) (runtimes + generic dev tools; setup materializes `_sys/runtimes.json`) and [`_sys/defaults/tool-catalog.v1.json`](_sys/defaults/tool-catalog.v1.json) (AI CLIs; setup materializes `_sys/tool-catalog.v1.json`)
- **Conventions:** [`CONVENTION.md`](CONVENTION.md)
- **Contributing:** [`CONTRIBUTING.md`](CONTRIBUTING.md)
- **Validation:** the unit-test suite under [`_sys/tests/unit`](_sys/tests/unit) plus pre-commit consistency checks (`check_encoding`, `check_unreferenced_functions`, `check_root_hygiene`, `check_tool_updates`, `saturation_scan`) under [`_sys/checks`](_sys/checks).

Optional Windows features: [Sandbox and WSL2 isolation guide](docs/isolation_guide.md).
