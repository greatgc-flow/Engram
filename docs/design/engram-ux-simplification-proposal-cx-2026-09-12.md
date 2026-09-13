# Engram UX simplification — independent Round-1 proposal (cx)

**Status:** proposal only; no implementation is authorized by this document  
**Date:** 2026-09-12  
**Target baseline:** Engram v3.2.6 (`b2e5304`)  
**Design intent:** one obvious entrance, one update story, one private engine folder, no unexplained root state, and no SUBST drive or directory junction in either the steady state or the proposed architecture.

## Executive recommendation

Engram should stop presenting its implementation history as its user interface. The installed product should have one real program, `Engram.exe`, and one optional shell shim, `engram.cmd`, which does nothing except forward all arguments to that program. The eight root `.bat` commands should disappear. First-run bootstrap becomes an internal state of `Engram.exe`, not a command the user must understand.

The canonical surface should be:

```text
engram [open] [path]
engram update [--check] [--yes] [--only component]
engram doctor [--json]
engram menu enable|disable|repair
engram tidy [--apply]
engram uninstall [--purge-data]
engram version
```

There are deliberately no `install`/`setup`, `start`/`launch`, `status`/`doctor`, `cleanup`/`tidy`, or `register`/`unregister` synonym pairs. Running `engram` for the first time bootstraps and opens; running it later opens. `engram update` is the sole user story for keeping Engram, its runtimes, ordinary tools, and AI CLIs current.

Rename `_sys/` to `engine/`, but do not merely perform a cosmetic directory rename. Make it the explicit program boundary, with immutable release generations selected by a small JSON pointer and mutable runtime/state subtrees beneath the same friendly top-level name. The pointer is a regular file, not a link. Keep `.engram/` exactly where it is and exactly what it is: live personal AI-tool state, including credentials and caches. Keep every workspace `.peerhub/` with its workspace. Those two settled boundaries are load-bearing and are not redesigned here ([`docs/engram-dotdir.md:7-17`](../engram-dotdir.md#L7-L17), [`docs/engram-dotdir.md:35-41`](../engram-dotdir.md#L35-L41)).

Finally, retire root `.ai/` as an Engram location. Engram v3.2.6 itself creates it during update discovery, independently of the legacy hub. Move Engram's two update-state files into `engine/state/update/`, delete an unused legacy workspace-config writer, and remove `.ai` from Engram's hygiene and packaging allowlists. Legacy hub state is a second owner and must be handled as such, never swept or silently folded into `.engram/`.

## 1. Verified current state

### 1.1 Root command duplication is complete, although the wrappers differ in weight

`engram.cmd` recognizes all eight names that also exist as root batch files ([`engram.cmd:30-42`](../../engram.cmd#L30-L42)), and every one of those eight handlers calls the corresponding root batch file rather than a shared application entry point ([`engram.cmd:68-98`](../../engram.cmd#L68-L98)). In surface-area terms the overlap is therefore **8 of 8 commands (100%)**.

The implementation overlap is more nuanced:

| Root file | What it actually adds beyond dispatch | Assessment |
|---|---|---|
| `register.bat`, `unregister.bat`, `CLEANUP.bat`, `menu-cleanup.bat` | Each is a three-line `cd` + `dispatch.bat` wrapper ([register](../../register.bat#L1-L3), [unregister](../../unregister.bat#L1-L3), [cleanup](../../CLEANUP.bat#L1-L3), [menu cleanup](../../menu-cleanup.bat#L1-L3)). | Exact redundant transport wrappers. |
| `STATUS.bat`, `UPDATE.bat` | Each adds the same portable-Python presence guard, then dispatches ([status](../../STATUS.bat#L1-L11), [update](../../UPDATE.bat#L1-L17)). | Near-identical bootstrap guards; this belongs in one bootstrapper. |
| `TIDY.bat` | Runs a narrow dry-run cleanup, asks once, then reruns with `--apply` ([`TIDY.bat:1-15`](../../TIDY.bat#L1-L15)). | A real UI, but it should be one canonical `tidy` handler rather than a second command system. |
| `INSTALL.bat` | Reads the Python pin, bootstraps the first interpreter and pip, then enters the dispatcher ([`INSTALL.bat:21-38`](../../INSTALL.bat#L21-L38), [`INSTALL.bat:97-131`](../../INSTALL.bat#L97-L131), [`INSTALL.bat:160-163`](../../INSTALL.bat#L160-L163)). | A necessary bootstrap capability, not a reason for a permanent public `.bat` API. |

The pipeline layer already describes the underlying operations once: install, registration, cleanup, start, update and status are data-driven in `_sys/dispatch.json` ([`_sys/dispatch.json:69-99`](../../_sys/dispatch.json#L69-L99)). The extra root layer does not create a useful abstraction.

There is a third, contradictory entrance. The WinGet manifest aliases `Engram.exe` as the `engram` command ([`greatgc-flow.Engram.installer.yaml:5-13`](../../manifests/g/greatgc-flow/Engram/3.2.6/greatgc-flow.Engram.installer.yaml#L5-L13)), but the shipped wrapper source ignores `args`, waits for `INSTALL.bat`, and does nothing else ([`wrapper.cs:5-20`](../../wrapper.cs#L5-L20)). That does not implement the command table the README promises for the plain `engram` command ([`README.md:67-83`](../../README.md#L67-L83)). This is not cosmetic: the package-manager entry point and the documented CLI entry point have different semantics.

Two smaller truth defects reinforce the same impression:

- `engram.cmd` prints v3.2.0 in both its version and help paths ([`engram.cmd:116-123`](../../engram.cmd#L116-L123)), while the version SSOT says 3.2.6 ([`_sys/core/version.json:1-4`](../../_sys/core/version.json#L1-L4)).
- Its help says registration mounts `P:` and unregistration unmounts it ([`engram.cmd:129-136`](../../engram.cmd#L129-L136)), while the current product documentation says fresh registration mounts no virtual drive ([`README.md:20-25`](../../README.md#L20-L25)).

### 1.2 `cleanup` and `tidy` are not aliases, despite being presented together

The help groups `cleanup / tidy` as if they mean the same thing ([`engram.cmd:134-136`](../../engram.cmd#L134-L136)). They do not. `tidy_temp.py` is dry-run by default and targets allowlisted, regenerable debris ([`_sys/core/tidy_temp.py:1-19`](../../_sys/core/tidy_temp.py#L1-L19)). The scrubber has five escalating tiers, including runtime removal, the whole `workspace/` tree, archives, Markdown files and finally Python ([`_sys/core/scrubber.py:1-11`](../../_sys/core/scrubber.py#L1-L11), [`_sys/core/scrubber.py:179-218`](../../_sys/core/scrubber.py#L179-L218)). These should not share a vague label, and workspace deletion should not be a cleanup tier at all.

The current uninstall has the same unsafe default at a larger scope: its external helper recursively removes the entire portable root ([`_sys/cli/manage.py:94-140`](../../_sys/cli/manage.py#L94-L140)). Because `.engram/` and `workspace/` are children of that root, ordinary uninstall also removes personal AI state and workspace databases. That clashes with the now-settled status of `.engram/` as live personal state and should be a release blocker for the redesigned lifecycle.

### 1.3 Today's update story is several partial stories

There are four distinct mechanisms or non-mechanisms:

| Category | Current path | What really happens |
|---|---|---|
| Engram program itself | Release zip / package manager / Git must be handled outside `engram update`. | `updater.py` only imports `check_tool_updates` and never reads Engram's `version.json` or release feed ([`_sys/core/updater.py:1-27`](../../_sys/core/updater.py#L1-L27)). There is no in-product Core update in this path. |
| Portable Python | Every `INSTALL.bat` invocation queries endoflife.date unless `--skip-update` is supplied ([`INSTALL.bat:62-95`](../../INSTALL.bat#L62-L95)). | A fresh install may rewrite the Python pin. An existing install is told to close tools, manually remove `_sys/env/python`, and rerun ([`INSTALL.bat:43-59`](../../INSTALL.bat#L43-L59), [`INSTALL.bat:71-88`](../../INSTALL.bat#L71-L88)). This is update behavior hidden inside install. |
| Base runtimes | `engram update` discovery enumerates entries that declare a provider ([`_sys/checks/check_tool_updates.py:90-106`](../../_sys/checks/check_tool_updates.py#L90-L106)). | Python, Node.js, Git, VS Code and PowerShell declare versions and URLs but no discovery providers ([`_sys/runtimes.json:3-37`](../../_sys/runtimes.json#L3-L37)); they are therefore reported as not checked. |
| Ordinary tools | `engram update` discovers their provider-backed latest versions. | The nine generic tools do declare providers ([`_sys/runtimes.json:39-66`](../../_sys/runtimes.json#L39-L66), [`_sys/runtimes.json:142-184`](../../_sys/runtimes.json#L142-L184)). The command writes a proposal, confirms, and changes declarations; it only deploys binaries when the optional `--install` flag is also used ([`_sys/core/updater.py:47-73`](../../_sys/core/updater.py#L47-L73), [`_sys/checks/check_tool_updates.py:369-393`](../../_sys/checks/check_tool_updates.py#L369-L393)). |
| AI CLIs | Claude and Codex declare npm discovery; agy is manual ([`_sys/tool-catalog.v1.json:5-19`](../../_sys/tool-catalog.v1.json#L5-L19), [`_sys/tool-catalog.v1.json:35-50`](../../_sys/tool-catalog.v1.json#L35-L50), [`_sys/tool-catalog.v1.json:66-84`](../../_sys/tool-catalog.v1.json#L66-L84)). | Discovery yields catalog entries ([`_sys/checks/check_tool_updates.py:108-134`](../../_sys/checks/check_tool_updates.py#L108-L134)), but `proposed` is only a copy of `runtimes.json`, and mutation is guarded by `section in proposed` ([`_sys/checks/check_tool_updates.py:153-156`](../../_sys/checks/check_tool_updates.py#L153-L156), [`_sys/checks/check_tool_updates.py:212-223`](../../_sys/checks/check_tool_updates.py#L212-L223)). Apply writes only `RUNTIMES_PATH` ([`_sys/checks/check_tool_updates.py:321-393`](../../_sys/checks/check_tool_updates.py#L321-L393)). Therefore a discovered Claude/Codex update cannot advance `tool-catalog.v1.json`; even `--install` redeploys the old catalog pin. |

The README additionally exposes direct per-AI-CLI provisioner commands ([`README.md:85-90`](../../README.md#L85-L90)). They are useful internal diagnostics but create yet another user-visible update path.

The resulting mental model is impossible to summarize honestly as “run X to stay current.” A user must know whether the target is Engram, Python, a base runtime, a generic tool, or an AI CLI; whether the action discovers, rewrites a declaration, deploys, or merely reports; and whether a separate manual deletion is required.

### 1.4 Literal `.ai/` has two verified owners; Engram is one of them

The working hypothesis that all root `.ai/` state comes from legacy `hub.py` is only half right.

**Engram-owned writes.** Update discovery pins its cache to `<portable-root>/.ai/tool_discovery_cache.json` ([`_sys/checks/check_tool_updates.py:22-32`](../../_sys/checks/check_tool_updates.py#L22-L32)) and passes that path into every provider resolution ([`_sys/checks/check_tool_updates.py:181-188`](../../_sys/checks/check_tool_updates.py#L181-L188)). The resolver creates the parent and writes the file ([`_sys/core/version_resolver.py:21-44`](../../_sys/core/version_resolver.py#L21-L44)). This is the exact normal flow:

```text
UPDATE.bat / engram update
  -> dispatch pipeline update.run
  -> updater.run(propose_diff=True)
  -> check_tool_updates.discover_updates()
  -> version_resolver.resolve_latest(..., cache_path=root/.ai/...)
  -> mkdir root/.ai; write tool_discovery_cache.json
```

The installed `D:\tttt` v3.2.6 tree provides a direct empirical reproduction: its `.ai/` contains exactly `tool_discovery_cache.json` (2,664 bytes, modified 2026-09-12 00:09:31 KST), while `D:\t2` has no `.ai/`. The cache's provider records and timestamps correspond to the same resolver schema. This is the specific direct-user scenario; no hub explanation is needed.

Engram also stores deferred tool/runtime retries at `<portable-root>/.ai/tool_deferred_retries.json` and creates the parent on write ([`_sys/core/provisioner.py:198-221`](../../_sys/core/provisioner.py#L198-L221)). Normal lock/lease/npm-failure branches reach that writer ([`_sys/core/provisioner.py:634-644`](../../_sys/core/provisioner.py#L634-L644), [`_sys/core/provisioner.py:729-737`](../../_sys/core/provisioner.py#L729-L737), [`_sys/core/provisioner.py:956-1008`](../../_sys/core/provisioner.py#L956-L1008)).

A third Engram writer exists in `ConfigManager._save_ws()`, which creates `workspace/.ai/config.json` ([`_sys/core/config.py:91-115`](../../_sys/core/config.py#L91-L115)). A repository-wide import search found no production consumer of `ConfigManager`; only `config.py` itself and its two unit-test modules refer to it. It is legacy surface, not the explanation for ordinary launch or update, and should be deleted rather than redirected into a new authority.

**Legacy-hub writes.** The larger schema seen in this source checkout (`ask_history.jsonl`, leases, mailbox, nodes, task registry, sessions, consensus, guards) is explained by the separate deployed hub. Its `find_ai_root()` deliberately chooses `.ai` beside the nearest ancestor `.git` (`D:\Engram&Peerhub\PortableDev (v2.1)\_sys\core\hub.py:146-186`), and `ensure_ai_dir()` creates exactly those directories and files (`...\hub.py:599-627`). Its command entry calls that initializer before almost every action (`...\hub.py:12011-12063`). The checkout's `.ai/ask_history.jsonl` records two `cx.deepthink` asks on 2026-09-05, while its Engram cache file was written later on 2026-09-08. The checkout is thus a mixed-ownership directory, not evidence for a single cause.

**PeerHub and managed AI CLIs.** A literal search over PeerHub's `peerhub/**/*.py` returned no `.ai` reference. Engram launches managed tools with `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `GEMINI_DIR` and `PEERHUB_CONFIG_HOME` rooted under `.engram/` ([`_sys/env.json:9-20`](../../_sys/env.json#L9-L20), [`_sys/core/launcher.py:110-140`](../../_sys/core/launcher.py#L110-L140)). That proves the Engram/PeerHub source-level paths; it does not pretend to prove every behavior of closed third-party binaries. No observed artifact requires one of those binaries to explain it.

### 1.5 Dot-directory consolidation is settled infrastructure

`.engram/` is intentionally a live global root containing credentials and caches, not a clean package directory; it is gitignored and must never be copied wholesale ([`docs/engram-dotdir.md:11-23`](../engram-dotdir.md#L11-L23)). Workspace state remains with the project under `.peerhub/`, while PeerHub-global config inside Engram resolves to `.engram/peerhub/config/` through `PEERHUB_CONFIG_HOME` ([`docs/engram-dotdir.md:7-9`](../engram-dotdir.md#L7-L9), [`docs/engram-dotdir.md:35-37`](../engram-dotdir.md#L35-L37)). The redesign must not move, merge, copy, or reinterpret either tier.

The current launcher still contains legacy SUBST remount behavior when old state carries a drive letter ([`_sys/core/launcher.py:193-223`](../../_sys/core/launcher.py#L193-L223)), and `virtualizer.py` still implements directory-junction creation ([`_sys/core/virtualizer.py:115-151`](../../_sys/core/virtualizer.py#L115-L151)). The new design removes both capabilities after a one-time teardown migration; “unused by default” is weaker than the user's binding requirement of “not anywhere.”

## 2. Proposed experience

### 2.1 The first five minutes

For a release-zip user:

1. Extract Engram.
2. Double-click `Engram.exe`, or run `engram`.
3. Engram explains the components it will bootstrap, asks once, provisions them, opens the default workspace, and optionally offers the Explorer menu at the end.

There is no “install, then register, then launch” command choreography. The current quick start requires separate `INSTALL.bat` and `register.bat` steps ([`README.md:32-59`](../../README.md#L32-L59)); that sequence becomes a single first-run state machine. Menu integration stays optional because the environment works without it.

For every later use, `engram` opens `workspace/` by default, preserving the already-implemented target preference ([`_sys/core/launcher.py:165-179`](../../_sys/core/launcher.py#L165-L179)). `engram path` and `engram open path` are the same parser form, not two documented aliases: `open` is optional grammar for readability.

### 2.2 Canonical command surface

| Command | Contract |
|---|---|
| `engram [open] [path]` | Ensure the declared installation exists, then open VS Code and the Engram environment at the path. First use bootstraps automatically. |
| `engram update` | Compute one plan covering Engram Core, base runtimes, generic tools and AI CLIs; confirm once; apply and verify it. No second `--install` phase. |
| `engram update --check` | Networked, read-only report. It creates no durable proposal directory and changes no pins or binaries. |
| `engram update --only codex` | Advanced narrowing under the same update verb. This replaces documented direct calls into `provisioner.py`. |
| `engram doctor [--json]` | Zero-network, read-only current-health report, preserving the existing doctor's explicit contract ([`_sys/core/doctor.py:1-16`](../../_sys/core/doctor.py#L1-L16)). |
| `engram menu enable\|disable\|repair` | One namespace for Explorer integration. `repair` both reconciles this install and sweeps orphaned Engram entries, replacing register/unregister/menu-cleanup. |
| `engram tidy` | Dry-run preview of safe, regenerable cache/temp cleanup. `--apply` performs exactly the displayed plan. It never removes runtimes, `.engram/`, `workspace/`, or any `.peerhub/`. |
| `engram uninstall` | Remove program files, runtimes/tools, and host integration while preserving `.engram/` and `workspace/` by default. `--purge-data` is a separately confirmed destructive operation that names those roots explicitly. |
| `engram version` | Read the single version source at runtime; no copied literal. |

Internal actions may remain composable Python operations, but they are not accepted as unknown public commands. The current fallback dispatches an unrecognized word directly as a pipeline ([`engram.cmd:44-58`](../../engram.cmd#L44-L58)); the redesigned CLI rejects anything outside its public parser and exposes internal diagnostics only under an explicitly unstable developer entry point.

### 2.3 One entrance, not two implementations

`Engram.exe` becomes a small, stable bootstrapper with three jobs:

1. Parse and preserve the full command line.
2. Select the active engine release from `engine/current.json` and invoke it.
3. Handle states in which Python is absent, being replaced, or cannot safely replace itself.

The executable does not reimplement update policy. It hosts only the minimum native operations required before/after the Python engine runs: verified release staging, child-process handoff, atomic pointer activation, and bootstrap-runtime swap.

During one compatibility release, `engram.cmd` may remain as a tiny quoted forwarder to `Engram.exe %*`. It must contain no routing table, version literal, prompts or policy. New WinGet packages and context-menu entries target `Engram.exe` directly. The eight `.bat` files and `wrapper.cs` are not included in the user package; the current packager explicitly includes all of them ([`tools/winget/build_package.py:109-125`](../../tools/winget/build_package.py#L109-L125)), so the release payload test must assert their absence.

## 3. One update story

### 3.1 User contract

The sentence in the manual should be literally true:

> Run `engram update` to keep Engram and everything it manages current.

Default behavior discovers, shows one categorized plan, asks once, applies, verifies every selected component, and prints one final receipt. `--check` is the only discover-without-apply mode. `--yes` changes confirmation, not scope or semantics. There is no public “apply declarations now, install later” state.

Example output shape:

```text
Engram core       3.2.6  -> 4.0.0
Runtimes
  Python          3.14.5 -> 3.14.6
  VS Code         1.100.2 -> 1.101.1
Tools
  fd              10.4.2 -> 10.5.0
AI CLIs
  Codex           0.144.6 -> 0.145.0
  Antigravity     not checked: vendor has no trusted discovery provider

Update 4 components now? [y/N]
```

“Not checked” is never summarized as “up to date.” Manual-only providers remain visible and actionable, but do not force a separate update command.

### 3.2 One component registry and one transaction receipt

Replace the split `runtimes.json` / `tool-catalog.v1.json` mutation behavior with one typed component-registry abstraction. It may remain physically split for maintainability, but one resolver must emit the same record for every component:

```text
id, category, installed_version, target_version, discovery_source,
artifact, digest/signature policy, install mechanism, canary,
lock/drain policy, rollback generation, update authority
```

Python is no longer an inline batch exception. The native bootstrapper can stop the Python engine, stage the new interpreter beside the old one, run a canary, and rename-swap it. Node's `npm-global` preservation and existing atomic install/canary model remain valuable precedents ([`_sys/core/provisioner.py:628-674`](../../_sys/core/provisioner.py#L628-L674), [`_sys/core/provisioner.py:729-818`](../../_sys/core/provisioner.py#L729-L818)).

Each run writes one bounded receipt under `engine/state/update/receipts/`: candidate set, artifact digests, pre-state, applied generations, canary results, deferrals and rollback result. Discovery caches, proposals and deferred retries also live under `engine/state/update/`, never at root and never in `.engram/`.

### 3.3 Core update authority

Record the installation channel in `engine/state/installation.json`:

- `portable`: Engram's verified release updater owns Core.
- `winget`: `engram update` delegates the Core phase to WinGet, while keeping the same top-level UX and receipt; it does not race WinGet with a second self-updater.
- `git`: the command reports a dirty/diverged checkout as developer-managed; a clean checkout may be fast-forwarded only under an explicit, tested Git policy.

The user always starts with `engram update`; channel ownership is an implementation detail selected from the installation record. A staged Core release is verified before activation and activated by atomically replacing the small `current.json` pointer. No directory junction or SUBST mapping is involved.

Locked components do not trigger manual deletion instructions. The receipt marks them pending, and the stable bootstrapper completes the swap after dependent processes exit or at the next Engram start. An uncertain state is reported as uncertain and retains both generations; it is never called complete.

## 4. Prettier and safer installed layout

### 4.1 Recommendation: rename `_sys` to `engine`, with a real boundary

The underscore is not the main UX failure, but keeping it after removing the command clutter would preserve an opaque name for the one folder users can see. `engine` is short, descriptive, and complies with the existing lowercase-kebab directory rule ([`CONVENTION.md:223-234`](../../CONVENTION.md#L223-L234)). Do not use `.engram/engine`: `.engram/` is personal, credential-bearing live data and must remain independently preservable. Mixing replaceable program files into it would destroy that boundary.

Target release-zip/install layout:

```text
Engram.exe
engram.cmd                 # one-release compatibility shim; no policy
README.md
LICENSE

engine/
  current.json             # ordinary JSON pointer, never a link
  releases/
    4.0.0/                 # immutable Core code + built-in manifests
  runtime/
    python/
    nodejs/
    git/
    vscode/
    pwsh/
    venv/
  tools/
    ripgrep/
    codex/
    ...                    # preserves tools/{tool-name}/{executable}
  state/
    install/
    menu/
    update/
    cache/
    logs/

workspace/                 # user projects; never cleanup fodder
.engram/                   # live personal global state; unchanged
```

This reduces the normal visible root to one executable, one temporary compatibility shim, two documents and three meaningful directories. Build and developer-only material (`docs/`, tests, manifests, `wrapper.cs`) stays in the source repository but not in the portable user archive. The current packager already distinguishes an allowlisted root from the copied system hierarchy ([`tools/winget/build_package.py:154-205`](../../tools/winget/build_package.py#L154-L205)); the proposal tightens that distinction.

The internal rename is deliberately not a blind search-and-replace. A baseline inventory found `_sys` in 255 tracked files and 2,381 matched lines, including documentation/history. Runtime path resolution should be centralized first; historical documents are not rewritten, while active code, configs, tests and package manifests consume the resolver.

### 4.2 Remove SUBST and junction capability, not merely its defaults

The migration bootstrapper has read-only detection and one teardown path for legacy `subst_drive` and saved junction receipts. After successful teardown:

- the launcher never calls `subst`;
- registration is only Explorer-menu registration;
- `managed-links.json` and `virtualizer.py` leave the product;
- doctor treats any remaining Engram-owned mapping/reparse point as a migration error, not a healthy optional mode;
- no new design path uses a filesystem link.

The context menu calls `Engram.exe open "%V."` through a safely quoted relay. The current relay hardcodes `_sys/start.bat` ([`_sys/context_menu.json:7-10`](../../_sys/context_menu.json#L7-L10)), so menu re-registration is a mandatory migration step, not optional polish.

## 5. `.ai/` root-cause fix

### 5.1 Engram changes

1. Resolve both `tool_discovery_cache.json` and `tool_deferred_retries.json` under `engine/state/update/` through one injected state-path resolver.
2. Delete the unused `ConfigManager` workspace `.ai/config.json` feature. Engram has no business creating a second workspace configuration tier; PeerHub's `.peerhub/` remains authoritative.
3. Remove `.ai` from `VENDOR_CACHE_DIRS` and the root-hygiene allowlist. It is currently accepted in both places ([`_sys/checks/_common.py:32-48`](../../_sys/checks/_common.py#L32-L48), [`_sys/checks/check_root_hygiene.py:55-58`](../../_sys/checks/check_root_hygiene.py#L55-L58)), and `.gitignore` explicitly labels it ephemeral IPC ([`.gitignore:12-16`](../../.gitignore#L12-L16)). After the migration, unexpected `.ai` must be visible rather than normalized as Engram state.
4. Add a filesystem-write-location test: install, update, failed/deferred update, launch, doctor, menu changes, tidy and uninstall may write only to declared `engine/state`, `engine/runtime`, `engine/tools`, `.engram`, and explicit workspace destinations. No unclassified root directory may appear.

### 5.2 Existing `.ai` migration and mixed ownership

The upgrader owns exactly two names:

```text
.ai/tool_discovery_cache.json
.ai/tool_deferred_retries.json
```

It moves those files into `engine/state/update/`, verifies content and deletes `.ai/` only if the directory is then empty. This handles the real `D:\tttt` case automatically.

If any other entry exists, the upgrader does not delete, reinterpret, or move it into `.engram/`. It reports “external legacy orchestration state” with the exact remaining names. A separately owned hub migration must pin `HUB_AI_ROOT` explicitly and stop using “nearest `.git` implies create `.ai`” before that data can be archived safely. This ownership boundary is important: automatically sweeping the mixed checkout directory would erase mailbox/session evidence belonging to another system.

The steady-state acceptance rule is therefore precise: normal Engram, PeerHub and managed-AI-CLI use never create root `.ai`; externally invoked legacy hub may still do so until that separate tool is migrated. Engram detects and explains the latter but does not claim ownership.

## 6. Migration plan for v3.2.6 installs

### 6.1 Verified fixtures that the plan must cover

Read-only inspection on 2026-09-12 found:

| Install | Relevant observed state |
|---|---|
| `D:\tttt` | v3.2.6; `.engram/{agy,claude,codex,gh,peerhub}`; PeerHub 0.2.0 in the venv; a registered context-menu receipt with zero junctions; `workspace/smoke-test/.peerhub`; root `.ai` containing only Engram's discovery cache. |
| `D:\t2` | v3.2.6; the same five `.engram` children; PeerHub 0.3.0 in the venv; no registration receipt; no root `.ai`. |

These are migration acceptance fixtures, not disposable test targets. No proposal step writes to them.

### 6.2 Preservation classes

**Preserve byte-for-byte and in place:**

- the entire `.engram/` tree, including files the upgrader does not understand;
- the entire `workspace/` tree;
- every `.peerhub/` directory anywhere in user-selected workspaces;
- user files outside known Engram-owned paths.

The migrator does not use `.engram/` as scratch, does not enumerate it to decide what is “important,” and never copies it wholesale. Pre/post tests compare a path/type/size/digest manifest and fail activation on any change.

**Functionally preserve, but relocation/rebuild is allowed:**

- vendor runtimes and tools;
- VS Code portable data;
- Python venv packages, including manually installed PeerHub;
- menu registration and Engram's installation/update receipts.

**Freely replace after activation succeeds:**

- tracked `_sys` application code and built-in manifests;
- the eight known root `.bat` files, old `engram.cmd`, `Engram.exe` and `wrapper.cs`, but only when their hashes match a known shipped v3.2.6 artifact. Modified files are quarantined/reported, never silently overwritten.

### 6.3 Transactional migration sequence

1. **Preflight without mutation.** Detect version/channel, running Engram tools, disk capacity, root special characters, legacy SUBST/junction receipts, menu entries, `.ai` ownership, venv package inventory and modified shipped files. Print the plan.
2. **Stage independently.** Build `engine.new-<nonce>/` from a verified release. Do not rename `_sys` or touch user data yet.
3. **Prepare runtimes.** Move/copy canary-safe vendor generations into the new layout. Recreate the venv at its new absolute path from an exact package inventory, because a venv can embed its old interpreter path. Preserve unknown packages as well as PeerHub; editable/local packages that cannot be reproduced block activation with an actionable report.
4. **Verify real consumers.** Run runtime/tool canaries, each AI CLI `--version`, `peerhub --version`, and `peerhub config paths --json`; the last must still resolve global config inside the unchanged `.engram/peerhub/config`. Open the existing `D:\tttt\workspace\smoke-test` database read-only as a migration fixture.
5. **Remove prohibited host integration.** Tear down any saved SUBST or junction from the old receipt. If teardown cannot be proven, stop before activation. Register the new Explorer relay against `Engram.exe open` and verify it before removing old Engram registry/relay entries.
6. **Activate with no Python child alive.** The native bootstrapper closes the old engine, atomically installs `engine/` and its `current.json` pointer, swaps the root executable/shim, and retains the complete old `_sys` generation for rollback.
7. **Migrate only Engram-owned `.ai` names.** Apply the exact-name rule in section 5.2.
8. **Postflight.** Repeat canaries, compare the byte-preservation manifest, prove no SUBST/junction exists, prove the old root wrappers are absent, and write a migration receipt. Only then is the old engine generation eligible for bounded cleanup.
9. **Rollback on any failed invariant.** Restore the prior executable, `_sys`, menu receipt and runtime selection. `.engram`, workspaces and `.peerhub` never need rollback because they were never mutated.

This sequence also fixes uninstall semantics before users encounter the new layout: ordinary uninstall preserves the two user-data roots; only an explicit `--purge-data` may remove them.

## 7. Implementation order and release gates

This is a proposed order for a later ratification/TDD round, not permission to begin implementation.

1. **Freeze behavior with characterization tests.** Root wrapper parity, WinGet alias behavior, update category coverage, `.ai` write inventory, and v3.2.6 migration fixtures.
2. **Build the stable bootstrapper and canonical parser.** Make `Engram.exe` argument-complete and source its version dynamically.
3. **Unify component/update resolution.** Fix AI-catalog application, add all base-runtime providers or explicit manual states, add Core authority, and make update apply+verify one transaction.
4. **Centralize paths, then create `engine/`.** Active code consumes one layout resolver before `_sys` is renamed. Do not rewrite historical documents as though they described the new version.
5. **Move Engram `.ai` state and make root hygiene fail on recurrence.**
6. **Replace menu/cleanup/uninstall semantics.** Remove SUBST/junction code, protect user data by default, and update relays.
7. **Ship the measured v3.2.6 migrator.** Validate on disposable byte-for-byte copies of `D:\tttt` and `D:\t2`, never the live installs first.
8. **Remove legacy public files from the package and documentation.**

Release is blocked until all of these are true:

- `Engram.exe`, the WinGet `engram` alias and the temporary `engram.cmd` shim pass the same command-contract suite.
- A clean first run requires one user confirmation and no knowledge of install/register/update internals.
- `engram update` updates Core, Python, base runtimes, generic tools and Claude/Codex in one run; manual-only entries are explicitly reported; a failure cannot leave a new declaration with an old binary presented as success.
- Update tests cover success, locked/deferred component, canary failure, rollback, Core activation interruption, provider unavailable, and an uncertain process state.
- No normal flow creates `.ai`, `_archive`, `_state`, or any unclassified root entry.
- No proposed code invokes `subst`, creates a reparse point, or depends on a drive alias.
- Default tidy and uninstall preserve `.engram`, `workspace`, and all `.peerhub` data. Purge requires a second explicit data-destruction confirmation.
- The v3.2.6 fixtures retain byte-identical `.engram` and workspace trees, their installed PeerHub versions remain callable, and the existing PeerHub database remains readable with the same identity.
- The portable package root contains no standalone lifecycle `.bat` files, no `wrapper.cs`, and no stale version literal.

## 8. Why this is the coherent cut

The visible `.bat` duplication, `_sys` name, update ambiguity and `.ai` folder are not four unrelated blemishes. They are all symptoms of Engram having no single bootstrap/lifecycle boundary:

- batch files own pre-Python behavior;
- Python owns some runtime updates;
- another Python path owns discovery and optional application;
- `Engram.exe` owns only installation despite being the package alias;
- mutable program state spills into root names owned by older orchestration;
- destructive cleanup cannot distinguish program from user data.

A stable `Engram.exe` plus a versioned `engine/` boundary resolves those causes together. It makes first-run bootstrap, self-update, Python replacement, command parsing, rollback, root layout, and data-preserving uninstall parts of one lifecycle. That is the smallest architecture in which the desired simple sentence—“run Engram; run `engram update` to keep it current”—can be true rather than merely advertised.

## Appendix A — reproducible audit notes

The following read-only inventories support quantitative/negative findings above and are included so the ratifier can repeat them:

```powershell
# Root command count and handler comparison
Get-ChildItem -File *.bat
rg -n 'SUBCMD|call' engram.cmd

# Active-code/root-state ownership
rg -n -F '.ai' _sys .gitignore tools
rg -n -F '.ai' peerhub --glob '*.py'   # run in the PeerHub repository; no match

# Rename impact inventory (baseline only; history is not a migration target)
git grep -l '_sys'                     # 255 files
git grep -n '_sys'                     # 2,381 matching lines

# Live installs, read-only
Get-Content D:\tttt\_sys\core\version.json
Get-ChildItem -Force D:\tttt\.engram, D:\tttt\.ai
Get-Content D:\t2\_sys\core\version.json
Get-ChildItem -Force D:\t2\.engram
```
