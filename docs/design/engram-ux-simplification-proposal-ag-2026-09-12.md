# Engram UX Simplification Proposal (ag, Round-1)

**Author**: ag.opus (independent voice 1 of 2)
**Date**: 2026-09-12
**Status**: Proposal (design only, no implementation)
**Repo**: `D:\Engram&Peerhub\engram-main-worktree` (branch `main`, v3.2.6)

---

## Executive Summary

This proposal addresses the user's core complaint: *"The batch files and engram.cmd seem to overlap. The update path is unintuitive. Can the `_sys` folder get a prettier name? Polish it until it's a masterpiece."*

After investigating every file at the repo root, the dispatch pipeline, update mechanism, and the `.ai` folder mystery, I propose:

1. **Eliminate 6 of 8 standalone `.bat` files** — collapse to `engram.cmd`/`Engram.exe` as the single public CLI, keeping only `INSTALL.bat` (pre-Python bootstrap).
2. **One update command** — `engram update` as the single, intuitive "keep everything current" flow.
3. **Don't rename `_sys/`** — instead, reduce visible root clutter so users never need to look at it.
4. **Consolidate `.ai/` into `.engram/state/`** — eliminate the mystery dot-folder entirely.
5. **Fix the stale version display** — `engram.cmd` hardcodes "v3.2.0" instead of reading `version.json`.

---

## 1. Root-Level Command Surface: Quantified Redundancy Analysis

### Current State: 8 standalone batch files + `engram.cmd` + `Engram.exe`

| Standalone file | Lines | What it does | `engram.cmd` equivalent | Verdict |
|---|---|---|---|---|
| [`INSTALL.bat`](../../INSTALL.bat) (165 lines) | 165 | Pre-Python bootstrap: downloads embedded Python, installs pip, then calls `_sys/core/dispatch.bat install` ([line 161](../../INSTALL.bat#L161)) | `engram install` → calls `INSTALL.bat` ([engram.cmd:69](../../engram.cmd#L69)) | **KEEP** — only entry point that works before Python exists. The `engram.cmd` install subcommand literally delegates to this file. |
| [`UPDATE.bat`](../../UPDATE.bat) (18 lines) | 18 | Python-exists guard + `_sys/core/dispatch.bat update` ([line 16](../../UPDATE.bat#L16)) | `engram update` → calls `UPDATE.bat` ([engram.cmd:85](../../engram.cmd#L85)) | **ELIMINATE** — 100% identical to `engram update`. The 3-line Python guard is already in `dispatch.bat` ([dispatch.bat:9-20](../../_sys/core/dispatch.bat#L9)). |
| [`STATUS.bat`](../../STATUS.bat) (12 lines) | 12 | Python-exists guard + `_sys/core/dispatch.bat status` ([line 10](../../STATUS.bat#L10)) | `engram status` → calls `STATUS.bat` ([engram.cmd:73](../../engram.cmd#L73)) | **ELIMINATE** — 100% identical. |
| [`CLEANUP.bat`](../../CLEANUP.bat) (4 lines) | 4 | `cd` + `_sys/core/dispatch.bat cleanup` ([line 3](../../CLEANUP.bat#L3)) | `engram cleanup` → calls `CLEANUP.bat` ([engram.cmd:89](../../engram.cmd#L89)) | **ELIMINATE** — 100% identical. |
| [`TIDY.bat`](../../TIDY.bat) (16 lines) | 16 | Calls `tidy_temp.py` directly with interactive dry-run preview + `choice` confirmation ([lines 6-12](../../TIDY.bat#L6)) | `engram tidy` → calls `TIDY.bat` ([engram.cmd:93](../../engram.cmd#L93)) | **ELIMINATE** — 100% identical routing through `engram.cmd`. Note: `TIDY.bat` bypasses `dispatch.bat` and calls `tidy_temp.py` directly, but `engram tidy` just calls `TIDY.bat`, so the user experience is identical. Should be folded into a `tidy` pipeline in `dispatch.json`. |
| [`register.bat`](../../register.bat) (4 lines) | 4 | `cd` + `_sys/core/dispatch.bat register` | `engram register` → calls `register.bat` ([engram.cmd:77](../../engram.cmd#L77)) | **ELIMINATE** — 100% identical. |
| [`unregister.bat`](../../unregister.bat) (4 lines) | 4 | `cd` + `_sys/core/dispatch.bat unregister` | `engram unregister` → calls `unregister.bat` ([engram.cmd:81](../../engram.cmd#L81)) | **ELIMINATE** — 100% identical. |
| [`menu-cleanup.bat`](../../menu-cleanup.bat) (4 lines) | 4 | `cd` + `_sys/core/dispatch.bat menu-cleanup` | `engram menu-cleanup` → calls `menu-cleanup.bat` ([engram.cmd:97](../../engram.cmd#L97)) | **ELIMINATE** — 100% identical. |

**Summary**: Every standalone `.bat` except `INSTALL.bat` is a 4-18 line trampoline that does nothing `engram.cmd` doesn't already do. `engram.cmd`'s subcommand handlers ([lines 68-98](../../engram.cmd#L68)) literally `call` these batch files verbatim. The indirection is pure redundancy.

### Proposed Public API

After cleanup, the visible root should have exactly **2 entry points**:

| Entry point | Purpose |
|---|---|
| `INSTALL.bat` | First-time bootstrap (required: runs before Python exists). Retained as-is. |
| `engram.cmd` / `Engram.exe` | Every other command: `install`, `update`, `status`, `register`, `unregister`, `cleanup`, `tidy`, `menu-cleanup`, `launch`, `uninstall`, `version`, `help`. |

The 6 eliminated `.bat` files should be replaced by **`engram.cmd` subcommand handlers that call `_sys/core/dispatch.bat` directly** instead of bouncing through the now-deleted wrappers. This is trivial — e.g., `:cmd_update` changes from:

```bat
:: Before (engram.cmd:84-86)
:cmd_update
call ".\UPDATE.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%
```

to:

```bat
:: After
:cmd_update
call "_sys\core\dispatch.bat" update %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%
```

**`CONVENTION.md` §3.2** ([line 186](../../CONVENTION.md#L186)) says "Root-level batch files must remain minimal harnesses that delegate to Python modules under `_sys/core/`." This proposal fulfills that intent more completely: `engram.cmd` IS the minimal harness; the individual `.bat` wrappers added an unnecessary second layer of indirection.

### TIDY.bat Special Case

`TIDY.bat` ([lines 5-15](../../TIDY.bat#L5)) calls `tidy_temp.py` directly rather than going through `dispatch.bat`, because it implements an interactive dry-run + `choice` confirmation flow. This flow should be migrated into a proper `tidy` pipeline operation in `dispatch.json` (currently `dispatch.json` has no `tidy` pipeline at all — `engram tidy` routes to `TIDY.bat` which routes to `tidy_temp.py` outside the pipeline system). Implementation detail: `tidy_temp.py` already supports `--apply`; the interactive prompt can move into the Python code.

---

## 2. One Clear, Intuitive Update Story

### Current State: 3 Distinct Update Paths

| # | What gets updated | How | Entry point |
|---|---|---|---|
| 1 | **Tools** (ripgrep, bat, fd, delta, fzf, jq, oh-my-posh, gh) | GitHub Releases discovery via `version_resolver.py`, proposal diff via `check_tool_updates.py`, apply via `provisioner.py` | `engram update` / `UPDATE.bat` → `updater.py` ([updater.py:17-90](../../_sys/core/updater.py#L17)) |
| 2 | **Python runtime** | `endoflife.date` API check at install time only | `INSTALL.bat` ([lines 62-95](../../INSTALL.bat#L62)): auto-upgrade on FIRST install only, never on subsequent runs. If already installed, prints "newer available" info but explicitly says "not auto-applied" ([line 75](../../INSTALL.bat#L75)). |
| 3 | **Engram itself** | `git pull` (manual) | No built-in mechanism. User must know to `git pull` the repo. |

### Problems

1. **Python update is install-time-only, not rerunnable.** A user who runs `engram update` expecting it to update Python gets... nothing about Python. The Python check only happens in `INSTALL.bat` ([line 62](../../INSTALL.bat#L62)), and even then it explicitly declines to auto-apply if Python is already installed ([line 73-76](../../INSTALL.bat#L73)).

2. **No self-update.** `engram update` updates tools but not Engram's own code. There's no `git pull` or release-check mechanism. The user must manually pull from GitHub.

3. **`runtimes.json` vs `tool-catalog.v1.json`** — two separate JSON registries exist: `runtimes.json` (204 lines, covers runtimes + tools) and `tool-catalog.v1.json` (77 lines, covers tools). It's unclear which is authoritative.

4. **Version display is stale.** `engram.cmd` hardcodes `"Engram v3.2.0"` at [lines 117](../../engram.cmd#L117) and [122](../../engram.cmd#L122), while `version.json` says `"3.2.6"` ([version.json:2](../../_sys/core/version.json#L2)). Users see the wrong version.

### Proposed: Single `engram update` Flow

`engram update` should become the ONE command that checks and proposes updates for EVERYTHING:

```
> engram update

>>> Discovering updates...

Engram:
  engram: v3.2.6 -> v3.3.0 (GitHub release)    [self-update via git pull]

Runtimes:
  Python: 3.14.5 (current, latest stable)       [no update needed]
  Node.js: 22.22.3 -> 22.23.0                   [update available]
  VS Code: 1.100.2 (current)                    [no update needed]

Tools:
  ripgrep: 15.2.0 (current)
  fd: 10.4.2 -> 10.5.0                          [update available]

Not checked (manual):
  - git (no discovery_provider)

Apply these updates? [y/N]
```

Implementation requires:
- Adding a self-update check to `updater.py` (compare local `version.json` against GitHub Releases API for `greatgc-flow/Engram`, then `git pull` if behind).
- Adding runtime version discovery to `updater.py` for Node.js and other runtimes that have `discovery_provider` metadata (Python's endoflife.date check from `INSTALL.bat` should be extracted into a Python function and integrated here).
- Fixing the version display: `engram.cmd` should read from `version.json` instead of hardcoding. Since `engram.cmd` runs before Python exists, use PowerShell JSON parsing (already demonstrated in `INSTALL.bat` [line 33](../../INSTALL.bat#L33)).

---

## 3. `_sys/` Naming Recommendation: Don't Rename

### Analysis

The user asked: *"Can the `_sys` folder itself get a prettier name?"*

After investigating, I recommend **not renaming `_sys/`**, for these reasons:

1. **Users should never need to look inside `_sys/`.** With a clean `engram.cmd`-only CLI surface, `_sys/` is implementation detail — like `node_modules/` or `.git/`. The problem the user perceives isn't the name; it's that the root has too much visible clutter that makes `_sys/` seem like something they need to understand.

2. **`_sys` is already the least ugly option under CONVENTION.md §5** ([line 226](../../CONVENTION.md#L226)): "lowercase kebab-case" for directories. The underscore prefix sorts it before alphabetic entries, marking it as internal — a Unix/Python convention that users of dev tools widely understand.

3. **Renaming is high-cost, low-value.** `_sys` appears in:
   - Every `.bat` file at the root
   - `engram.cmd` ([line 56](../../engram.cmd#L56), [103](../../engram.cmd#L103), [113](../../engram.cmd#L113))
   - `dispatch.bat` ([line 5](../../_sys/core/dispatch.bat#L5))
   - Every Python module under `_sys/` that uses relative-to-parent paths
   - `CONVENTION.md` (multiple references)
   - `.gitignore`, `.gitattributes`
   - README.md
   - All test files

   Renaming would touch dozens of files for no functional benefit.

4. **Alternative names are worse.** `engine/`, `runtime/`, `system/`, `.system/` — none is clearly better, and some collide with standard tool names. `.sys/` would be hidden on macOS/Linux but invisible in Windows Explorer by default (dot-prefix convention doesn't work the same way). `_internal/` is longer without being clearer.

### Instead: Reduce Root Clutter

The real fix is to reduce the VISIBLE root to just what a user needs:

**Before** (current root, 18 user-visible items):
```
CLEANUP.bat        INSTALL.bat       STATUS.bat      TIDY.bat
UPDATE.bat         engram.cmd        Engram.exe      register.bat
unregister.bat     menu-cleanup.bat  CONVENTION.md   README.md
LICENSE            wrapper.cs        requirements-dev.txt
_sys/              dist/             docs/           manifests/
tools/             workspace/        .ai/            .engram/
```

**After** (proposed, 8-9 user-visible items):
```
INSTALL.bat        engram.cmd        Engram.exe      README.md
CONVENTION.md      LICENSE
_sys/              workspace/        .engram/
```

Moved inside `_sys/`:
- `wrapper.cs` → `_sys/wrapper.cs` (build artifact, not user-facing)
- `requirements-dev.txt` → `_sys/requirements-dev.txt` (developer-only)
- `dist/` → `_sys/dist/` or removed from git (build output)
- `manifests/` → `_sys/manifests/` (winget manifests, not user-facing)
- `docs/` → stays or moves to `_sys/docs/` (debatable — keep at root if README links there)
- `tools/` → already has portable binaries; could stay if `path_entries` use it

Eliminated:
- 6 standalone `.bat` files (folded into `engram.cmd`)
- `.ai/` folder (consolidated into `.engram/state/`, see §4)

With this cleanup, a user opening the portable root in Explorer sees **the 3 things they actually interact with** (`INSTALL.bat`, `engram.cmd`/`Engram.exe`, `workspace/`) plus `_sys/` which they can safely ignore — like a `.git/` folder.

---

## 4. The `.ai/` Folder: Root Cause and Fix

### Root Cause (confirmed by code inspection)

`.ai/` is created by **TWO separate, unrelated systems** — this is the real surprise:

#### (A) Peerhub's `hub.py` orchestration (IPC/session state)

The `.ai/leases.json` file at the root ([.ai/leases.json](../../.ai/leases.json)) contains entries like:
```json
{
  "8d18197b-...": {
    "peer_id": "cx.deepthink",
    "ask_query_file": "D:\\Engram&Peerhub\\PortableDev (v2.1)\\_sys\\ai\\ipc\\arbiter-399f3d9c.txt"
  }
}
```

This is peerhub's `hub.py` orchestration — it creates `.ai/` relative to CWD when dispatching multi-peer asks. The test infrastructure confirms this: [`_sys/tests/unit/conftest.py:90-92`](../../_sys/tests/unit/conftest.py#L90) creates a temporary `.ai/` dir, and [`conftest.py:125-131`](../../_sys/tests/unit/conftest.py#L125) patches `hub.find_ai_root()` and `hub.ensure_ai_dir()`.

**How the user triggers it**: Running any peerhub AI-CLI command (e.g., launching Claude/Codex through Engram's environment) in a directory where `hub.py` is invoked with CWD set to the Engram root. The `.ai/state.json` with `room_id`, `members`, `mission`, `phase` fields ([.ai/state.json](../../.ai/state.json)) is hub.py's session coordination state.

#### (B) Engram's OWN tool management code (caches and config)

**This is the more important finding**: Engram's own `_sys/` code writes to `.ai/` too:

| Code location | What it writes to `.ai/` |
|---|---|
| [`_sys/core/version_resolver.py:23`](../../_sys/core/version_resolver.py#L23) | `_DEFAULT_CACHE = _PORTABLE_ROOT / ".ai" / "tool_discovery_cache.json"` |
| [`_sys/checks/check_tool_updates.py:31`](../../_sys/checks/check_tool_updates.py#L31) | `DISCOVERY_CACHE_PATH = _PORTABLE_ROOT / ".ai" / "tool_discovery_cache.json"` |
| [`_sys/core/provisioner.py:199`](../../_sys/core/provisioner.py#L199) | `return sys_dir.parent / ".ai" / "tool_deferred_retries.json"` |
| [`_sys/core/config.py:65-66`](../../_sys/core/config.py#L65) | `path = cls._ws_path / ".ai" / "config.json"` |
| [`_sys/checks/saturation_scan.py:231`](../../_sys/checks/saturation_scan.py#L231) | Reads `sys_root.parent / ".ai" / "state.json"` |
| [`_sys/checks/check_root_hygiene.py:57`](../../_sys/checks/check_root_hygiene.py#L57) | Lists `.ai` as an allowed root-level directory |
| [`_sys/checks/_common.py:37`](../../_sys/checks/_common.py#L37) | Lists `.ai` as recognized |
| [`_sys/checks/check_backlog.py:113`](../../_sys/checks/check_backlog.py#L113) | Lists `.ai/` as a repo root |

So `.ai/` is not purely a hub.py artifact — **Engram's own shipped code actively creates and maintains files there**. This is the root cause of the user's confusion: they see a mysterious `.ai/` folder appearing while using Engram, because Engram itself puts tool discovery caches, deferred retry state, and workspace config there.

### Proposed Fix: Consolidate `.ai/` into `.engram/state/`

The `.engram/` root ([`docs/engram-dotdir.md`](../../docs/engram-dotdir.md)) was established as the consolidation point for all Engram-managed persistent state. `.ai/` predates that consolidation and was never migrated. Fix:

1. **Engram's own tool state** → `.engram/state/`:
   - `tool_discovery_cache.json` → `.engram/state/tool_discovery_cache.json`
   - `tool_deferred_retries.json` → `.engram/state/tool_deferred_retries.json`
   - Change `version_resolver.py:23`, `check_tool_updates.py:31`, `provisioner.py:199`

2. **Workspace config** (if any) → keep at `.peerhub/` per the ratified dotdir consolidation. The `config.py:65-66` path `workspace/.ai/config.json` should become `workspace/.peerhub/config.json` per the established convention.

3. **Hub.py session state** → `.engram/hub/` or `.peerhub/hub/`:
   - `leases.json`, `state.json`, `sessions/`, `mailbox/`, etc. → redirect via `hub.py`'s `find_ai_root()` to `.engram/hub/` (or better: make hub.py use `PEERHUB_CONFIG_HOME` which already points to `.engram/peerhub/config/`).

4. **Update all allowlists**: `_common.py:37`, `check_root_hygiene.py:57`, `check_backlog.py:113` — remove `.ai` from known directories, add `.engram/state/` references where needed.

5. **Migration**: Add a one-time migration that moves `.ai/tool_discovery_cache.json` and `.ai/tool_deferred_retries.json` to `.engram/state/`, then deletes the emptied `.ai/` directory. Similar to `migrate_ais_to_engram.py` ([`_sys/core/migrate_ais_to_engram.py`](../../_sys/core/migrate_ais_to_engram.py)).

> [!IMPORTANT]
> This does NOT contradict the ratified dotdir consolidation. `.engram/` was designed for exactly this purpose — "the AI CLI personal-config root" per [`docs/engram-dotdir.md:1`](../../docs/engram-dotdir.md#L1). Engram's own tool management state is a natural fit for `.engram/state/`.

---

## 5. Version Display Bug

`engram.cmd` hardcodes `"Engram v3.2.0"` at two locations:
- [Line 117](../../engram.cmd#L117): `:show_version` handler
- [Line 122](../../engram.cmd#L122): `:show_help` header

Meanwhile, [`_sys/core/version.json:2`](../../_sys/core/version.json#L2) says `"version": "3.2.6"`.

**Fix**: Read from `version.json` at runtime using the same PowerShell JSON parsing pattern already used in `INSTALL.bat` ([line 33](../../INSTALL.bat#L33)):

```bat
:show_version
for /f "usebackq delims=" %%v in (`powershell -NoProfile -Command "((Get-Content '_sys\core\version.json')|ConvertFrom-Json).version"`) do set "_VER=%%v"
echo Engram v%_VER% (Portable Dev Runtime)
exit /b 0
```

This has a minor cold-start cost (PowerShell invocation) but is correct and avoids version drift permanently.

---

## 6. Additional Findings

### 6.1 `tools/` at root AND `_sys/tools/`

The repo has BOTH a root-level `tools/` directory and `_sys/tools/`. The `env.json` `path_entries` reference `{"base": "tools", "sub": "..."}` which resolves to `_sys/tools/` ([`launcher.py:84`](../../_sys/core/launcher.py#L84): `"tools": sys_dir / "tools"`). The root-level `tools/` appears to be a separate, older convention. This should be investigated — if `tools/` at root is dead/unused, remove it.

### 6.2 `CONVENTION.md` §5.2 inconsistency

§5.2 ([line 231](../../CONVENTION.md#L231)) says "Batch (root & _sys): lowercase kebab-case (`register.bat`, `unregister.bat`, `install.bat`, `cleanup.bat`)." But the actual files are UPPERCASE: `INSTALL.bat`, `UPDATE.bat`, `STATUS.bat`, `CLEANUP.bat`, `TIDY.bat`. The convention doc contradicts the actual naming. Since Windows filesystems are case-insensitive this is cosmetic, but the inconsistency should be resolved one way or the other.

### 6.3 `workspace/` semantics

The root has a `workspace/` directory used as the default launch target ([`launcher.py:178-181`](../../_sys/core/launcher.py#L178)). This is clean and intuitive — keep it.

---

## 7. Migration Plan for Existing Installs

Existing installs at `D:\tttt` and `D:\t2` (both v3.2.6) must survive this restructuring.

### Byte-for-byte preserved (NEVER touch)

| Path | Reason |
|---|---|
| `.engram/` (entire tree) | Personal AI-CLI config, credentials, memory. The whole point of dotdir consolidation. |
| `workspace/` and any workspace `.peerhub/` folders | User project data and peerhub workspace state. |
| `_sys/env/` | Installed Python, Node.js, git, venv — rebuilt only by explicit `engram install`. |
| `_sys/data/state/` | Registration state, logs. |

### Safely reshapable

| What | Migration step |
|---|---|
| 6 standalone `.bat` files | Delete them. `engram.cmd` takes over. Users who have shortcuts/scripts pointing to e.g. `UPDATE.bat` get a clear error from Windows ("file not found"), with an obvious fix ("use `engram update`"). |
| `.ai/` contents | Run one-time migration script: move `tool_discovery_cache.json` and `tool_deferred_retries.json` to `.engram/state/`, delete `.ai/` if empty. |
| `engram.cmd` | Replace in-place (it's tracked in git — `git pull` delivers the update). |
| Root-level files moved into `_sys/` | `wrapper.cs`, `requirements-dev.txt`, etc. — these are developer-facing, not user-facing. Moving them doesn't affect any user workflow. |

### Migration script outline

```python
# migrate_v4.py (sketch, not implementation)
# 1. Move .ai/tool_discovery_cache.json -> .engram/state/tool_discovery_cache.json
# 2. Move .ai/tool_deferred_retries.json -> .engram/state/tool_deferred_retries.json
# 3. If .ai/ contains only hub.py state (leases, sessions, etc.), leave a note
#    or delete if hub.py is configured to use .engram/hub/ going forward
# 4. Delete empty .ai/ if nothing else remains
# 5. Update engram.cmd's subcommand handlers to call dispatch.bat directly
#    (this is a git-tracked file change, not a runtime migration)
```

---

## 8. Summary of Proposed Changes

| Area | Before | After | Effort |
|---|---|---|---|
| Root `.bat` files | 8 standalone files | 1 (`INSTALL.bat`) | Low: delete 6 files, update 6 `engram.cmd` handlers |
| CLI surface | `engram.cmd` + 8 `.bat` aliases | `engram.cmd` only | Low |
| Update story | 3 separate paths (tools only, Python install-time only, git-pull for Engram) | 1 unified `engram update` | Medium: add self-update + runtime discovery to `updater.py` |
| `_sys/` naming | `_sys/` | `_sys/` (unchanged) | Zero |
| Root clutter | 18 visible items | 8-9 visible items | Low: move dev files into `_sys/` |
| `.ai/` folder | Mystery dot-folder created by both Engram and hub.py | Consolidated into `.engram/state/` | Medium: update 6-8 path references + migration script |
| Version display | Hardcoded "v3.2.0" | Dynamic from `version.json` | Low: 5-line fix |

---

## Appendix: File/Line Citation Index

All citations in this document reference files in `D:\Engram&Peerhub\engram-main-worktree` (the Engram repo, branch `main`, v3.2.6). Every claim was verified by direct file inspection on 2026-09-12.

| Citation | File | Line(s) | What it proves |
|---|---|---|---|
| engram.cmd routing | `engram.cmd` | 30-42 | All subcommand dispatch |
| engram.cmd -> .bat delegation | `engram.cmd` | 68-98 | Each handler `call`s the standalone .bat |
| UPDATE.bat full content | `UPDATE.bat` | 1-18 | Python guard + dispatch.bat call, nothing else |
| CLEANUP.bat full content | `CLEANUP.bat` | 1-4 | cd + dispatch.bat, nothing else |
| register.bat full content | `register.bat` | 1-4 | cd + dispatch.bat, nothing else |
| unregister.bat full content | `unregister.bat` | 1-4 | cd + dispatch.bat, nothing else |
| menu-cleanup.bat full content | `menu-cleanup.bat` | 1-4 | cd + dispatch.bat, nothing else |
| STATUS.bat full content | `STATUS.bat` | 1-12 | Python guard + dispatch.bat, nothing else |
| TIDY.bat direct call | `TIDY.bat` | 6-12 | Calls tidy_temp.py directly, not dispatch.bat |
| INSTALL.bat Python bootstrap | `INSTALL.bat` | 62-95 | endoflife.date API check, first-install only |
| INSTALL.bat final delegation | `INSTALL.bat` | 161 | Delegates to dispatch.bat install |
| dispatch.bat Python guard | `_sys/core/dispatch.bat` | 9-20 | Same guard as standalone .bat files |
| dispatch.json pipelines | `_sys/dispatch.json` | 69-100 | update, status, cleanup all defined |
| updater.py flow | `_sys/core/updater.py` | 17-90 | Tools-only update |
| version.json | `_sys/core/version.json` | 2 | "3.2.6" |
| engram.cmd stale version | `engram.cmd` | 117, 122 | Hardcoded "v3.2.0" |
| version_resolver .ai cache | `_sys/core/version_resolver.py` | 23 | `.ai/tool_discovery_cache.json` |
| check_tool_updates .ai cache | `_sys/checks/check_tool_updates.py` | 31 | Same cache path |
| provisioner .ai deferred | `_sys/core/provisioner.py` | 199 | `.ai/tool_deferred_retries.json` |
| config.py .ai config | `_sys/core/config.py` | 65-66 | `.ai/config.json` |
| saturation_scan .ai state | `_sys/checks/saturation_scan.py` | 231 | reads `.ai/state.json` |
| _common.py .ai allowlist | `_sys/checks/_common.py` | 37 | `.ai` in known dirs |
| check_root_hygiene .ai | `_sys/checks/check_root_hygiene.py` | 57 | `.ai` in allowed dirs |
| check_backlog .ai | `_sys/checks/check_backlog.py` | 113 | `.ai/` as repo root |
| conftest hub.py patches | `_sys/tests/unit/conftest.py` | 90-131 | `find_ai_root`, `ensure_ai_dir` |
| leases.json hub.py evidence | `.ai/leases.json` | 4, 11 | "cx.deepthink", IPC arbiter paths |
| CONVENTION.md §3.2 | `CONVENTION.md` | 186 | Root .bat delegation rule |
| CONVENTION.md §5.1 | `CONVENTION.md` | 226 | lowercase kebab-case dirs |
| engram-dotdir.md | `docs/engram-dotdir.md` | 1-42 | .engram/ ratified design |
| env.json tool_env_vars | `_sys/env.json` | 16-21 | CLAUDE_CONFIG_DIR etc -> .engram/ |
| launcher.py build_env | `_sys/core/launcher.py` | 108-148 | Environment construction |
| launcher.py _resolve_path_entry | `_sys/core/launcher.py` | 78-86 | engram base resolves to .engram/ |
