<div align="center">
  <h1>📦 Engram</h1>
  <p><b>A clean, portable Windows dev environment. Nothing more.</b></p>
  <p>Virtualized Python/Node/Git/VS Code under one drive-letter-free tree — install it, register it, work, uninstall it without a trace.</p>

  [![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078d4.svg)](https://www.microsoft.com/windows)
  [![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
  [![Tests: 301 green](https://img.shields.io/badge/tests-301%20green-brightgreen.svg)](_sys/tests/unit)
  [![AI collaboration: peerhub](https://img.shields.io/badge/AI%20collaboration-peerhub-8a2be2.svg)](https://github.com/greatgc-flow/peerhub)
</div>

<br/>

Engram bootstraps a self-contained Windows dev environment — Python, Node.js, Git, VS Code, and a handful of CLI tools — into one portable folder, with no host-machine installs and no registry residue. `register` links it into your user profile via directory junctions; `unregister`/`uninstall` remove every trace, including a background helper that finishes cleanup after the process holding the folder open has exited.

> **Note on scope:** Engram used to also orchestrate AI-to-AI peer collaboration directly. That entire layer has moved to the standalone [**peerhub**](https://github.com/greatgc-flow/peerhub) package — Engram itself no longer knows what a "peer debate" or "consensus round" is. What Engram *does* still do on the AI-tooling side is install, update, and status-check third-party AI CLIs (Claude Code, Codex, etc.) as ordinary managed tools, exactly like it manages ripgrep or Node.js. If you want AI-to-AI collaboration, install peerhub separately on top of an Engram environment.

## What it does

- **Portable runtime virtualization** — Python, Node.js, Git, VS Code, and PowerShell are downloaded, pinned by version+hash in `_sys/runtimes.json`, and run entirely from inside the portable folder. Nothing touches `C:\Program Files` or the registry.
- **Generic tool catalog** — dev CLI tools (ripgrep, bat, fd, delta, fzf, jq, gh, sqlite, oh-my-posh, peerhub) install/update through one pinned, hash-verified pipeline (`_sys/runtimes.json`'s `tools` section).
- **AI-CLI lifecycle management** — a separate catalog (`_sys/tool-catalog.v1.json`) tracks Claude Code / Codex / agy the same way: install, version-pin, canary-verify. Engram never talks to these tools' models or protocols — it only manages the binaries.
- **Junction-based registration, not drive-letter SUBST** — `register` creates directory junctions (host config → portable config, host project dir → portable project dir) driven by `_sys/managed-links.json`; `unregister` tears them down cleanly. No virtual drive letter to leak across reboots.
- **Real uninstall** — `engram uninstall` computes an installation-scoped ID, writes a journal outside the install directory (survives the directory's own deletion), and hands off to an external helper that waits for the running process to exit before purging the folder — so a running instance never tries to delete the directory it's executing from.
- **On-demand tool updates** — `UPDATE.bat` discovers newer versions of every catalog entry and applies them through the same pinned, hash-verified install path used for first-time setup.
- **Zero-bloat by construction** — the packaging pipeline (`tools/winget/build_package.py`) only ever bundles an explicit root-file allowlist plus `_sys/`, minus caches/temp/state; nothing accumulates into the distributed archive that wasn't put there on purpose.

## Prerequisites
- Windows 10 or 11
- Git for Windows (only needed if installing via `git clone`; the Winget path is self-contained)

## Quick Start

### Option A: Download the release zip (recommended right now)
```powershell
# Download & extract Engram-v3.0.0-portable-x64.zip from the release, then:
cd Engram-v3.0.0-portable-x64
.\INSTALL.bat
.\register.bat
```
[Latest release](https://github.com/greatgc-flow/Engram/releases/latest) — this is the exact archive the Winget submission below packages, so it's already validated (`winget validate` passes clean).

### Option B: Git clone
```bat
:: 1. Clone the repository
git clone https://github.com/greatgc-flow/Engram.git
cd Engram

:: 2. Bootstrap the portable environment (Python, Node, Git, VS Code, tools)
.\INSTALL.bat

:: 3. Register it — creates the host-profile junctions
.\register.bat

:: 4. (Optional) Preview/clean temporary workspace files (dry-run + confirm)
.\TIDY.bat
```

> Once registered, `.\STATUS.bat` reports environment health, and `.\UPDATE.bat` checks every catalog entry for newer pinned versions.

### Option C: Winget (submitted, not yet live)
```powershell
winget install greatgc-flow.Engram
```
This does **not work yet** — the manifest was submitted as [microsoft/winget-pkgs#428737](https://github.com/microsoft/winget-pkgs/pull/428737) and is pending Microsoft's review/merge (validated locally with `winget validate` first, passes clean). Once merged, this command will bootstrap the same v3.0.0 archive as Option A automatically, and the `engram` command becomes available system-wide without a manual clone.

## Command Reference

`engram.cmd` (or the plain `engram` command after a Winget install) dispatches every lifecycle action:

| Command | Does |
|---|---|
| `engram install` / `setup` | Bootstrap the portable runtime and tool catalog |
| `engram status` / `doctor` | Report environment health (runtimes, tools, junction state) |
| `engram register` | Create the host-profile junctions (equivalent to `register.bat`) |
| `engram unregister` | Remove the junctions, leaving the portable folder itself intact |
| `engram update` | Discover and apply pinned-version updates across the catalog |
| `engram cleanup` | Tiered cache/temp reclamation (`_sys/core/scrubber.py`) |
| `engram tidy` | Interactive, dry-run-first temp-file cleanup preview |
| `engram launch` / `start` | Open the registered environment (VS Code + shell) |
| `engram uninstall` | Full removal: registry/junction teardown, then a background helper purges the folder once this process exits |
| `engram version` / `--version` / `-v` | Print the current version (`_sys/core/version.json`) |

To install or update an individual AI CLI tool directly:
```bat
python _sys\core\provisioner.py ensure-peer-cli claude
python _sys\core\provisioner.py ensure-peer-cli codex
python _sys\core\provisioner.py ensure-peer-cli agy
```

## AI-to-AI collaboration → peerhub

Engram's job ends at "the AI CLI binary is installed, current, and reachable." Everything past that — inter-peer messaging, consensus rounds, quota-aware routing, governance directives — lives in the separate [**peerhub**](https://github.com/greatgc-flow/peerhub) package, installed independently on top of an Engram environment:

```bash
pip install "git+https://github.com/greatgc-flow/peerhub.git@v0.1.8"
peerhub adapter discover   # confirms which AI CLIs Engram installed are reachable
```

See [peerhub's own README](https://github.com/greatgc-flow/peerhub#readme) for the full command set.

## What's next

See [`_sys/data/sessions/2026-09-03_separation-completion-backlog.md`](_sys/data/sessions/2026-09-03_separation-completion-backlog.md) for the full remaining-work backlog on both sides of the separation (Engram + peerhub), and what's deliberately deferred and why.

## Trust Signals

- **Version SSOT:** [`_sys/core/version.json`](_sys/core/version.json)
- **Tool catalogs:** [`_sys/runtimes.json`](_sys/runtimes.json) (runtimes + generic dev tools), [`_sys/tool-catalog.v1.json`](_sys/tool-catalog.v1.json) (AI CLIs)
- **Conventions:** [`CONVENTION.md`](CONVENTION.md)
- **Validation:** the unit-test suite under [`_sys/tests/unit`](_sys/tests/unit) plus pre-commit consistency checks (`check_encoding`, `check_unreferenced_functions`, `check_backlog`, `check_root_hygiene`, `check_tool_updates`, `saturation_scan`) under [`_sys/checks`](_sys/checks).
