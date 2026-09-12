# Engram UX / Structure Simplification — Round-2 Final Ratification

**Status:** RATIFIED. Supersedes both Round-1 proposals where they conflict. No further design discussion is expected before implementation.
**Date:** 2026-09-12
**Decider:** cc (Round-2 ratifier, final call for this round)
**Scope:** Engram only. PeerHub gets its own independent pass in a later round; nothing here changes PeerHub code or `.peerhub/` semantics.

**Inputs ratified:**

1. `docs/design/engram-ux-simplification-proposal-ag-2026-09-12.md` (ag), narrow scope
2. `docs/design/engram-ux-simplification-proposal-cx-2026-09-12.md` (cx), broad scope

Neither author saw the other's document. Every load-bearing claim in both was re-read against source or measured on disk before ruling. Anything not re-checked is listed in §0.5.

**Source trees consulted.** These are distinct and are named consistently throughout:

| Short name | Path | State | Role |
|---|---|---|---|
| **repo** | `D:\Engram&Peerhub\engram-main-worktree` | `main` @ `fbca05d`, v3.2.6, tags `v3.1.1`…`v3.2.6` | Engram product source |
| **tttt** | `D:\tttt` | v3.2.6 release-zip extraction, **not a git checkout** | Living acceptance fixture (read-only) |
| **t2** | `D:\t2` | v3.2.6 release-zip extraction, **not a git checkout** | Living acceptance fixture (read-only) |
| **v2.1-env** | `D:\Engram&Peerhub\PortableDev (v2.1)` | separate deployed dev environment | Out of scope; mentioned only where it constrains safety |

**Binding constraints (carried in, not reopened):**

- `.engram/` and every workspace `.peerhub/` are settled infrastructure. They are never moved, merged, renamed or reinterpreted.
- tttt and t2 must survive the ratified migration with zero data loss in `.engram/` and `workspace/`.
- No SUBST drive and no directory junction, anywhere.
- Engram only.

---

## 0. Verification summary

### 0.1 Pre-verified by the orchestrator (re-read anyway, all confirmed)

- `_sys/core/version_resolver.py:23` (`_DEFAULT_CACHE = _PORTABLE_ROOT / ".ai" / "tool_discovery_cache.json"`) and `_sys/core/provisioner.py:198-199` (`_get_deferred_path` → `sys_dir.parent / ".ai" / "tool_deferred_retries.json"`) write into a literal root `.ai/`.
- `wrapper.cs:7-21` never reads `args`, runs only `INSTALL.bat`, and also **never propagates the exit code**: `Main` returns `void` and there is no `Environment.Exit(p.ExitCode)`, so `Engram.exe` always exits 0. That second defect is new.
- `_sys/cli/manage.py:127-129` (the generated `EngramUninstallHelper.bat`) runs `rmdir /s /q "!BASE_DIR!"` unconditionally.

### 0.2 New facts neither proposal reported (all measured 2026-09-12)

These carry more weight in the rulings below than anything in either proposal.

| # | Fact | Evidence |
|---|---|---|
| N1 | **Both real installs are release-zip extractions, not git checkouts.** There is no `.git` in tttt or t2. The root `*.bat`, `engram.cmd` and `Engram.exe` in both are byte-identical to repo HEAD (md5 `debd3cb3…` UPDATE.bat, `e9d29c6c…` engram.cmd, `0bd01b6a…` Engram.exe, and so on). | `ls -d D:\tttt\.git` → not found; md5 comparison |
| N2 | **The local declaration files are mutated state, not shipped constants.** tttt's `_sys/runtimes.json` differs from the v3.2.6 shipped file in 6 pins (`python` 3.14.5→3.14.7, `sqlite` 3.53.3→3.53.4, `fd` 10.4.2→10.5.0, `fzf` 0.74.1→0.74.3, `oh-my-posh` 29.33.0→31.2.1, `gh` 2.96.0→2.100.0). t2's differs in 1 pin (`python` →3.14.7). `tool-catalog.v1.json` is still identical to shipped in both (md5 `207e7f99…`). | parsed diff against `git show v3.2.6:_sys/runtimes.json` |
| N3 | **Engram creates a second unexplained root directory, `_archive/`.** `launcher.py:226-228` writes `_archive/logs/start_*.log` on **every launch**, and `check_tool_updates.py:30` writes `_archive/tool-updates/<stamp>/` on every `engram update`. tttt has both. | `D:\tttt\_archive\{logs,tool-updates}` present |
| N4 | **Uninstall has no confirmation prompt at all**, and `engram.cmd:112-114` forwards **no arguments** to it. It also runs through `_sys\env\venv\Scripts\python.exe`, so uninstall fails outright if the venv is missing. | full read of `manage.py:48-159`, `engram.cmd:112-114` |
| N5 | **tttt's `_sys/` holds non-shipped legacy personal data**: `_sys/ai/` (22 files), `_sys/claude/config` (2), `_sys/codex/config` (3), and `_sys/antigravity/config`, all dated 2026-09-09. None of these exist in the v3.2.6 tree. A "delete all of `_sys`" uninstall would destroy them. | `find` counts; `git ls-tree -r v3.2.6` has no `_sys/{ai,claude,codex,antigravity}/` |
| N6 | **The one live SUBST mapping on this host (`P:\ => D:\Engram&Peerhub\PortableDev (v2.1)`) belongs to v2.1-env, not to any Engram install.** Any teardown or doctor logic that treats "a SUBST mapping exists" as Engram's would act on someone else's drive. | `subst` output |
| N7 | **Venvs embed the absolute interpreter path**: `D:\tttt\_sys\env\venv\pyvenv.cfg` has `home = D:\tttt\_sys\env\python`, and likewise for t2. Renaming `_sys` breaks every venv, including the PeerHub each fixture installed. Those installs came from the package index (no `direct_url.json`, `INSTALLER`=`pip`), so they are reproducible but only online. | `pyvenv.cfg`, dist-info |
| N8 | The **release asset name `Engram-v3.2.6-portable-x64.zip` does not contain `win`**, so `version_resolver._pick_windows_asset()` (lines 221-222 require `"win" in name`) rejects it. The generic `github_releases` provider therefore cannot supply the Core download URL. The GitHub API *does* expose `"digest": "sha256:248b1784…"` for the asset, which matches `InstallerSha256` in the 3.2.6 WinGet manifest exactly. | `gh api repos/greatgc-flow/Engram/releases/latest` |
| N9 | **A single provider error aborts the whole update.** `updater.py:29-30` returns `failed` if `payload["errors"]` is non-empty, so one flaky GitHub or npm response blocks every other update. | read |
| N10 | **A third stale version literal**: `_sys/core/version.py:10,13` falls back to `"3.2.0"` if `version.json` is unreadable, and `tools/winget/build_package.py:45` imports that `VERSION`. | `git grep 3\.2\.0` |
| N11 | **Scrubber tiers 3/4/5 already have `[y/N]` confirmations** (`scrubber.py:300,307,314`), but `--all`/`-y` bypasses all of them, and `--dry-run` makes `_confirm` return True. Tier 4 deletes `workspace/`, `_archive/` **and every root `*.md`**, including README.md (`scrubber.py:194-206`). | read |
| N12 | `ConfigManager._save_global()` (`config.py:102-107`) writes `_sys/config.json`. `launcher.py:211-214` still reads that file as a legacy source of `SUBST_DRIVE_LETTER`. Deleting `config.py` also removes the last writer of a SUBST trigger. | read |
| N13 | Test hygiene leak: the real `%LOCALAPPDATA%` on this host contains `SandboxRun_MagicMock_name_CreateKey_…bat` relay files, i.e. some registrar test writes to the real profile. Not a design question, but it is logged as backlog item P2-6. | `ls %LOCALAPPDATA%` |

### 0.3 ag proposal: confirmed and wrong

**Confirmed:**
- `engram.cmd:30-42` routing, and every handler at `:68-98` `call`ing its root wrapper.
- `UPDATE.bat`/`STATUS.bat` = Python guard + `dispatch.bat`.
- `CLEANUP/register/unregister/menu-cleanup.bat` = `cd` + `dispatch.bat`.
- `TIDY.bat` calls `tidy_temp.py` directly, with `choice` (`TIDY.bat:5-15`).
- `dispatch.json` has no `tidy` pipeline (pipelines: `install, register, unregister, cleanup, menu-cleanup, start, init, update, status`).
- `engram.cmd:117,122` hardcode `v3.2.0` while `version.json:2` = `3.2.6`.
- Every `.ai` citation in ag §4(B) (`version_resolver.py:23`, `check_tool_updates.py:31`, `provisioner.py:199`, `config.py:65-66,112`, `saturation_scan.py:231`, `check_root_hygiene.py:57`, `_common.py:37`, `check_backlog.py:113`).
- The CONVENTION.md §5.2 casing contradiction (`CONVENTION.md` §5.2 prescribes `install.bat`/`cleanup.bat`).
- INSTALL.bat's first-install-only Python bump (`INSTALL.bat:62-95`).

**Minor inaccuracies:** the wrapper line counts are each one too high (UPDATE.bat is 17 lines, STATUS.bat 11, the four trampolines 3, TIDY.bat 15). No ruling depends on them.

**Wrong, with the truth:**
1. *"Engram itself: `git pull` (manual)… self-update via git pull."* Neither real install is a git checkout (N1). `git pull` is impossible for every release-zip or WinGet user. The Core update story must not assume git.
2. *`.ai/` state → `.engram/state/`.* This conflicts with the ratified tier model: `.engram/` is the personal AI-CLI global root, one root per tier, and Engram adds no scratch state of its own there (dotdir RATIFIED §3.2, §5.3). Update caches are Engram program state. **Rejected**; see §4.
3. *`config.py` → `workspace/.peerhub/config.json`.* That would make Engram write into PeerHub's workspace tier, which the binding constraint forbids. **Rejected**; the writer is deleted instead (§4.2).
4. *hub.py state → `.engram/hub/`.* hub.py is not in this repo (`git ls-files` has no `hub.py`), and relocating it would change `.engram/` semantics. **Out of scope and rejected.**
5. *§6.1: "root `tools/` is a separate, older convention… if dead, remove it".* The root `tools/` contains exactly one tracked file, `tools/winget/build_package.py`, the release packager. It is a dev-only directory and is never shipped (`ROOT_FILES_ALLOW` only admits root files). Keep it.
6. *§3 root inventory ("18 user-visible items", including `dist/ docs/ manifests/ tools/`).* That is the repo, not an installed root. The installed root (tttt) has 20 entries: `.ai .engram _archive _sys workspace` + 8 `*.bat` + `CONVENTION.md engram.cmd Engram.exe LICENSE README.md wrapper.cs`. Moving `wrapper.cs`/`requirements-dev.txt` "into `_sys/`" would make them *more* shipped, not less, because `_sys/` is packaged wholesale. The fix is to drop them from the package (§3.5).
7. ag never mentions `wrapper.cs` / the WinGet alias defect, uninstall data loss, the catalog-application bug, or `_archive/`.

### 0.4 cx proposal: confirmed and wrong

**Confirmed:**
- 8 of 8 root commands duplicated (`engram.cmd:30-42`, `:68-98`).
- WinGet alias `PortableCommandAlias: engram` → `Engram.exe` (`manifests/.../3.2.6/…installer.yaml:5-9`).
- The help text advertises `P:` mounting (`engram.cmd:132-133`), contradicting README.md:23.
- Unknown words fall through to raw pipelines (`engram.cmd:44-58`).
- `cleanup` ≠ `tidy` (`tidy_temp.py:1-19`; `scrubber.py:1-11,194-218`).
- `updater.py:7` imports only `check_tool_updates` and never reads `version.json`.
- Base runtimes (`python nodejs git vscode pwsh`) have no `discovery_provider`. Exactly **9** tools do: 8 `github_releases` + 1 `sqlite_org_page`.
- `--install` is an optional second phase (`updater.py:12`, `check_tool_updates.py:378-391`).
- `doctor.py:1-16` zero-network contract.
- `launcher.py:165-179` default target.
- `build_package.py:110-125` ships all 8 wrappers and `wrapper.cs`.
- `context_menu.json:9` relay hardcodes `_sys\start.bat` (tttt's live relay file `SandboxRun_D_tttt_sandbox_open.bat` matches).
- `launcher.py:201-223` SUBST remount.
- `virtualizer.py:52-86,115-151` junction creation via `_winapi.CreateJunction`.
- The `_sys` rename impact is exact: `git grep -l/-n '_sys'` = **255 files / 2,381 lines** at `b2e5304`, and at HEAD once the two proposal files are excluded (257/2,485 with them). Restricted to non-doc code (excluding `docs/`, `*.md`, `manifests/`): **100 files / 703 lines**.
- The fixture table in cx §6.1 is exact: tttt `.ai/` contains only `tool_discovery_cache.json`, 2,664 bytes, mtime 2026-09-12 00:09:31 +0900; t2 has no `.ai/`; PeerHub 0.2.0 / 0.3.0; tttt `register.state.json` has `"junctions": []`; t2 has no `_sys/data/state/`; `workspace/smoke-test/.peerhub/peerhub.sqlite3` exists.
- **The catalog-application bug is real.** `check_tool_updates.py:156` builds `proposed` from `runtimes.json` only. `:113-134` yields a synthetic `"catalog"` section for Claude/Codex/agy. The guard at `:221` (`if section in proposed and name in proposed[section]`) is never true for `"catalog"`. `apply_proposal()` writes only `RUNTIMES_PATH` (`:369-371`), and `verify_proposal_still_valid()` hashes only `runtimes.json` (`:267-280`). Net effect: a Claude/Codex bump is displayed, "applied", and even `--install`ed, but the catalog pin never moves, so the old version is redeployed and the same "update available" repeats forever.
- **`ConfigManager` has zero production consumers**: `ConfigManager|core.config` matches only `config.py`, `test_config.py` and `test_config_scoping.py` (plus prose in `_sys/data/backlog.json`).

**Wrong or overstated, with the truth:**
1. *"The pointer is a regular file… atomically install `engine/`… recreate the venv at its new absolute path"*. This is feasible, but N7 shows the rename forces a venv rebuild for **every** existing install, and a rebuild needs network access. cx's own §6.3 step 3 admits this. That cost is real and is the decisive input to §2.
2. *§4.2: "doctor treats any remaining Engram-owned mapping/reparse point as a migration error".* This is correct only if "Engram-owned" means *mapped to this install's own base dir*. A naive "any SUBST mapping" check would flag v2.1-env's `P:` (N6). §7 pins the exact predicate.
3. *§6.2: "Freely replace… tracked `_sys` application code and built-in manifests".* Unsafe. `runtimes.json` is locally mutated state (N2), and a blind replace would silently downgrade 6 of tttt's pins. §5.3 rules a per-entry three-way merge.
4. *§5.1(4) / §7 gate: "install, update, …, uninstall may write only to declared… destinations"*. The rule is right, but cx never names `_archive/` (N3) as a current violator in the diagnosis. It appears only in a release gate. It is covered explicitly in §4.
5. cx §1.1's "three-line" count for the four trampolines is correct.

### 0.5 Not re-checked (explicit, per the task's instruction)

- cx's exact call-site ranges `provisioner.py:634-644/729-737/956-1008` for the deferred-retry writer. `_load/_save_deferred` uses at `:202-255,927,1006` were confirmed. Only the writer's path matters here, and that is confirmed.
- cx's citations into v2.1-env's `hub.py:146-186,599-627,12011-12063`, and the "no `.ai` in PeerHub `*.py`" negative search. Both are outside this Engram-only scope. The tttt evidence (`.ai` = Engram's cache only) is sufficient for every Engram ruling.
- WinGet client behavior on `upgrade`/`uninstall` of a `zip`+`portable` package: whether untracked files in the package directory survive. The channel is not live (README.md:61-65). §8.4 makes Core self-update refuse on the `winget` channel instead of relying on it.
- Whether `AppDomain.CurrentDomain.BaseDirectory` resolves through the WinGet `Links\engram.exe` symlink to the package directory. This is made a required test in P0-2 rather than assumed.
- `_sys/tests/unit/conftest.py:90-131` (`ai_dir`, `patch_ai_root` importing a nonexistent `hub` module): read and confirmed dead. No test requests either fixture (the one `ai_dir` identifier in `test_provisioner_autoinstall.py:721` is a local variable in a regression guard asserting the provisioner does **not** read `.ai/leases.json`). The fixtures are deleted in P2-5.

---

## 1. Scope of the rewrite: RULING (hybrid; cx's surface, ag's structure, no release generations)

**Ruling.** Adopt **cx's user-facing contract**:

- one entrance
- no root `.bat` files at all
- one `update` verb that covers Engram itself
- data-preserving uninstall
- SUBST/junction capability removed, not just defaulted off
- exact-name `.ai` retirement

Adopt **ag's structural economy**:

- keep `_sys/`
- keep `engram.cmd` as the dispatcher and route its handlers straight to `dispatch.bat`
- read the version dynamically

**Reject** cx's native `Engram.exe` bootstrapper rewrite, `engine/releases/<ver>/` immutable generations, the `current.json` activation pointer, the typed component-registry abstraction, and the 9-step staged/rollback migration.

**Reasoning.**

1. **Where the risk actually is.** cx's generation machinery protects against two failure classes: interrupted Core activation, and replacing a running interpreter. In the ratified design neither Core update nor migration replaces the Python interpreter. Python replacement stays an explicit, reported, manual step (§8.3). Program files are plain files that can be overlaid by a helper process after Engram exits. That pattern is already shipped and tested for uninstall (`manage.py:94-159`, `test_uninstall_semantics.py:127-179`). With the interpreter out of the blast radius, a generations/pointer model buys rollback for a failure that a hash-verified overlay with a backup copy also covers, at a fraction of the code and test surface.
2. **Scale.** There are two real installs, both the owner's (N1), and no live WinGet channel (README.md:61-65). There is no third-party compatibility obligation that would justify a new updater framework.
3. **But ag's scope is not enough, because of N1.** Both real installs are release-zip extractions. Today the only way a zip user upgrades is to extract a new zip. By default that lands in a *new* folder (`Engram-vX-portable-x64/`, README.md:36-38), which strands `.engram/` and `workspace/` in the old one. ag's `git pull` answer reaches neither install. So a bounded, in-place Core update (§8.4) is **in scope**. It is the one piece of cx's lifecycle vision that the evidence makes mandatory. The earlier informal "report-only" idea is rejected for the same reason.
4. **The confirmed defects are independent of architecture**: uninstall data loss, `Engram.exe` ignoring args and exit codes, the catalog-application bug, `.ai`/`_archive` leakage, and the stale version. Each gets a targeted fix. None waits for anything else.

Net: this is a bold cut of the *surface* (0 root wrappers, 8 public verbs) and a conservative cut of the *mechanism* (no new directory model, no new registry type).

---

## 2. `_sys` → `engine`: RULING (no rename in this round)

**Ruling: `_sys/` keeps its name.** cx's centralize-path-resolution-then-rename technique is endorsed as *the* method if a rename is ever done. It is not scheduled.

**Reasoning, evidence first:**

- **Every existing install needs a network-dependent venv rebuild.** `pyvenv.cfg` embeds `home = D:\tttt\_sys\env\python` (N7). PeerHub 0.2.0 (tttt) and 0.3.0 (t2) would have to be reinstalled from the index. That makes "installed PeerHub venvs survive" depend on network availability and on PyPI still serving those exact versions. That is a real, avoidable risk against a binding constraint, spent on a name.
- **Blast radius.** The rename touches 100 non-doc files / 703 lines (255 / 2,381 counting docs). This includes the context-menu relay template (`context_menu.json:9`), which is baked into already-written relay files in `%LOCALAPPDATA%`, so every registered install needs re-registration.
- **Payoff.** The payoff is cosmetic, and the declutter in §3.5 already removes most of the discomfort. After this ratification the installed root is exactly **seven entries**: `Engram.exe`, `engram.cmd`, `README.md`, `LICENSE`, `_sys/`, `workspace/`, `.engram/`. `_sys/` becomes the single "program files" folder, with no reason for a user to open it. Every user action is a verb.

**Rejected alternatives:**
- Hiding `_sys` with `attrib +h`: surprising for a dev tool, and zip extraction does not preserve it.
- A dual name via a link: forbidden by the no-junction constraint.
- Renaming for new installs only: that creates two layouts forever.

**Revisit trigger (recorded, not scheduled):** reconsider once §8.4's Core overlay has shipped and has a venv-recreate-from-inventory step proven on disposable fixture copies. The rename could then ride a major version as a purely mechanical change.

---

## 3. Canonical command surface: RULING (the literal build target)

### 3.1 Entrances

| Entrance | Contract |
|---|---|
| `engram.cmd` (repo/install root) | The only dispatcher. It contains the routing table below and nothing else: no prompts, no version literal, no policy. It always starts with `cd /d "%~dp0"` and keeps `setlocal DisableDelayedExpansion`, the `!`-safe design that `test_engram_cmd_cli_entrypoint.py` guards. |
| `Engram.exe` (root; WinGet `engram` alias) | A thin native forwarder built from `wrapper.cs`. It resolves its own **final** image path, following symlinks (`GetFinalPathNameByHandle` on `Process.GetCurrentProcess().MainModule.FileName`), and runs `cmd.exe /d /s /c ""<dir>\engram.cmd" <args>"`. Each arg is quoted with standard Windows `CommandLineToArgvW` escaping (backslashes doubled before a quote, `"` → `\"`). It uses `UseShellExecute=false` and inherits the console. It **exits with the child's exit code**. If `engram.cmd` is missing it prints `engram.cmd not found next to <path>` and exits 1. Double-click = no args = bare `engram`. |
| `_sys\cli\engram.cmd` (new, 3 lines) | `@call "%~dp0..\..\engram.cmd" %*` followed by `@exit /b %ERRORLEVEL%`. `_sys/cli` is already on the sandbox `PATH` (`env.json:23`), so `engram …` works inside a launched Engram shell. |

### 3.2 Public verbs (complete list; nothing else is accepted)

```text
engram                               = engram open
engram open [PATH]
engram update [--check] [--yes] [--only NAME[,NAME...]]
engram doctor [--json]
engram menu [status|enable|disable|clean]
engram tidy [--apply] [--deep]
engram uninstall [--yes] [--purge-data]
engram version | --version | -v
engram help | --help | -h | /?
```

**Parsing rule** (in `engram.cmd`, in this order):
1. No argument → `open`.
2. The first argument is one of the verbs above (case-insensitive) → that verb.
3. The first argument is a retired verb (§3.4) → print the replacement and exit **2**.
4. The first argument is an existing file or directory path → `open <that path>`. A folder that happens to be named like a verb is opened with the explicit `engram open <name>`.
5. Anything else → `[Error] Unknown command: X` plus `Run 'engram help'`, and exit **2**.

The fallback that dispatches unknown words straight into a pipeline (`engram.cmd:44-58`) is **deleted**. Internal pipelines are reachable only through `_sys\core\dispatch.bat <pipeline>`, a developer entry point that is not documented for users.

**"Not set up" rule.** This applies when `_sys\env\python\python.exe` is absent.
- `open` runs the first-run flow (§3.3).
- `update` bootstraps without prompting (it *is* the "make it installed and current" verb).
- `doctor`, `menu`, `tidy` and `uninstall` print `Engram is not set up in <root> yet. Run 'engram' (or 'engram update --yes').` and exit 1.
- `version` and `help` work without Python.

### 3.3 Per-verb contracts

| Verb | Behavior | Exit codes |
|---|---|---|
| `open [PATH]` | **First run** (no Python): print one plan line (components from `runtimes.json` + `tool-catalog.v1.json`, and the target root), then prompt `Set up Engram here now? [Y/n]`. On yes, run `_sys\core\bootstrap.bat` (the former `INSTALL.bat` body, §3.5); on no, exit 1. After a successful bootstrap, create `workspace\` if absent. If `register.state.json` is absent, ask once: `Add "Open in Engram" to the Explorer right-click menu? [y/N]` (yes → `menu enable`). **Every run:** dispatch the `start` pipeline, i.e. `launcher.main` with its existing target rules (`launcher.py:165-179`, `:243-263`). A path is resolved relative to the caller's cwd before `engram.cmd` changes directory: `engram.cmd` captures `%CD%` into `ENGRAM_CALLER_CWD` before `cd /d "%~dp0"`, and `launcher.main` resolves relative `PATH` against it. | 0 ok; 1 not set up / declined / bootstrap failed; launcher errors are propagated |
| `update` | Full contract in §8. `--check`: discover and print the plan; writes nothing except the discovery cache (`_sys/data/state/update/discovery-cache.json`). `--yes`: skip the single confirmation, and nothing else. `--only`: comma-separated component IDs (`engram`, runtime names, `runtimes.json` tool names, catalog `tool_id`s); an unknown ID exits 2 before any network call. | 0 success or nothing to do; 1 one or more components failed (others still applied); 2 usage error; 3 declined at prompt |
| `doctor [--json]` | Unchanged zero-network contract (`doctor.py:1-16`). `check_subst` is replaced by `check_legacy_host_integration` (§7). Every `run INSTALL.bat` / `run register.bat` hint is rewritten to the new verbs. | 0 healthy; 1 broken (as today, `doctor.py:12-16`) |
| `menu` / `menu status` | Read-only: whether this install's entries are present (reusing `doctor.check_registration`) and the number of orphaned `SandboxRun_*` entries found by `registrar.clean_orphans` in a new `dry_run=True` mode. | 0 |
| `menu enable` | Pipeline `menu-enable: ["registry.apply", "state.write"]`. Idempotent. | 0 / 1 |
| `menu disable` | Pipeline `menu-disable: ["registry.remove", "state.prune"]`. Idempotent; no state = no-op success. | 0 / 1 |
| `menu clean` | Pipeline `menu-clean: ["registry.clean_orphans"]`: today's `menu-cleanup` behavior, unchanged. | 0 / 1 |
| `tidy [--apply] [--deep]` | Default is a dry run: print the plan and a final line `Run 'engram tidy --apply' to delete these.` No interactive prompt (TIDY.bat's `choice` flow is retired). `--apply` recomputes the plan and deletes exactly its items. `--deep` adds, only: `_sys/data/setup-files/`, `_sys/tools/*_old` rollback dirs, `__pycache__` under `_sys/`, launcher logs beyond the newest 5, and update proposals beyond the newest 1. The never-touch set is enforced by assertion in the planner, not by convention: `.engram/`, `workspace/`, any `.peerhub/`, `_sys/env/**` except the named pip/npm/VS Code caches `tidy_temp.py` already allowlists, `_sys/tools/**` except `*_old`, `_sys/runtimes.json`, `_sys/tool-catalog.v1.json`, `_sys/data/state/**` except proposals under `--deep`, and every root file. Implemented as a `tidy` pipeline (`tidy.run` → `core.tidy_temp.run(ctx)`); `tidy_temp.main()` stays as a thin CLI over the same function. | 0 |
| `uninstall [--yes] [--purge-data]` | Contract in §6. | 0 handed off; 1 failed before hand-off; 3 declined |
| `version` | Prints `Engram <version> (Portable Dev Runtime)`. Read at runtime by `powershell -NoProfile -Command "(Get-Content -Raw '_sys\core\version.json' \| ConvertFrom-Json).version"`; prints `unknown` if that fails. | 0 |
| `help` | Static usage text listing exactly §3.2; the header version is read the same way as `version`. No mention of `P:`, SUBST, junctions or retired verbs. | 0 |

### 3.4 Retired verbs (a hard error with guidance, never a silent alias)

| Retired | Message says to use |
|---|---|
| `install`, `setup` | `engram` (first run) or `engram update` (repair/re-provision) |
| `status` | `engram doctor` |
| `register` | `engram menu enable` |
| `unregister` | `engram menu disable` |
| `menu-cleanup` | `engram menu clean` |
| `cleanup` | `engram tidy` / `engram tidy --deep` (destructive tiers are gone; see §6.3) |
| `launch`, `start` | `engram open` |

Each prints `'engram X' was renamed: use 'engram Y'.` and exits 2. This table lives in `engram.cmd` permanently. It costs about 10 lines and makes old muscle memory self-correcting.

### 3.5 Files: retired, moved, added

| Path | Fate |
|---|---|
| `UPDATE.bat`, `STATUS.bat`, `CLEANUP.bat`, `TIDY.bat`, `register.bat`, `unregister.bat`, `menu-cleanup.bat` | Deleted. |
| `INSTALL.bat` | Moved to `_sys/core/bootstrap.bat`. First line becomes `cd /d "%~dp0..\.."`; all existing relative paths and the `&`/`!` hardening comments are kept verbatim. Its final line calls `dispatch.bat install` exactly as today. `check_tool_updates._run_install_step()` (`:312-318`) is removed together with `--install` (§8). |
| `wrapper.cs` | Moved to `tools/winget/wrapper.cs` (dev-only, next to the packager). `Engram.exe` stays at root and is rebuilt by new `tools/winget/build_exe.py` (Framework `csc.exe /target:exe /optimize+`). |
| `CONVENTION.md`, `requirements-dev.txt` | Stay in the repo; `CONVENTION.md` leaves the package. |
| `_sys/cli/launch.bat`, `_sys/cli/launch`, `_sys/cli/launcher.py`, `_sys/cli/cleanup.py`, `_sys/cli/manage.bat`, `_sys/cli/manage` (its `_bat-shim` target does not exist), `_sys/cli/manage.py` | Deleted. `manage.py`'s `uninstall()` moves to `_sys/core/uninstaller.py` (§6). Its `register`/`unregister`/`cleanup` actions duplicate dispatch pipelines, and `get_subst_mappings` (`:15-30`) is already listed as unreferenced (`unreferenced_functions_baseline.json:16-17`). |
| `_sys/start.bat` | Kept: it is the context-menu relay's target (`context_menu.json:9`), and existing relay files in `%LOCALAPPDATA%` call it. |
| `_sys/core/scrubber.py`, `_sys/core/virtualizer.py`, `_sys/managed-links.json`, `_sys/core/config.py` | Deleted (§6.3, §7, §4.2). |
| `tools/winget/build_package.py` `ROOT_FILES_ALLOW` | Becomes exactly `{"engram.cmd", "Engram.exe", "README.md", "LICENSE"}`. |
| `_sys/core/release-manifest.json` (new, generated at package time) | `{"version", "files": {relpath: sha256}}` for every packaged file. It is used by migration (§5), Core update (§8.4) and uninstall (§6). |
| `_sys/core/release-manifests/3.2.6.json` (new, committed once) | Generated from the **actual published** `Engram-v3.2.6-portable-x64.zip`, verified first against the API digest `sha256:248b1784…eb52f` (N8). This is how v3.2.6 installs, which have no manifest, are recognized. |

---

## 4. The `.ai/` fix (and `_archive/`, its twin): RULING

### 4.1 Where Engram's own state goes

**Ruling: `_sys/data/state/update/` and `_sys/data/logs/launcher/`.** Not `.engram/state/` (ag; rejected in §0.3 item 2) and not `engine/state/update/` (cx; depends on the rename rejected in §2). `_sys/data/state/` is the existing home for Engram's program state (`register.state.json`, `install.state.json`). It is already gitignored (`.gitignore:29`) and already excluded from packaging (`build_package.py:127-132`, the `state` pattern), so no ignore or packaging rule changes.

| Writer (today) | Today writes | New path |
|---|---|---|
| `version_resolver.py:23` `_DEFAULT_CACHE` | `<root>/.ai/tool_discovery_cache.json` | `_sys/data/state/update/tool_discovery_cache.json` |
| `check_tool_updates.py:31` `DISCOVERY_CACHE_PATH` | same | same as above (one definition, imported) |
| `provisioner.py:198-199` `_get_deferred_path` | `<root>/.ai/tool_deferred_retries.json` | `_sys/data/state/update/tool_deferred_retries.json` |
| `check_tool_updates.py:30` `ARCHIVE_ROOT` | `<root>/_archive/tool-updates/<stamp>/` | `_sys/data/state/update/proposals/<stamp>/` |
| `launcher.py:226` `log_dir` | `<root>/_archive/logs/start_*.log` | `_sys/data/logs/launcher/start_*.log` |
| (new) update receipts | — | `_sys/data/state/update/receipts/<stamp>.json` |

**One path authority.** Add a new `_sys/core/state_paths.py` with pure functions of `sys_dir`: `update_dir`, `discovery_cache`, `deferred_retries`, `proposals_dir`, `receipts_dir`, `launcher_log_dir`. All five writers above import from it. No other module may build these paths. File names are kept unchanged, so the migration is a pure move.

### 4.2 `ConfigManager`: delete, don't redirect

Confirmed zero production consumers (§0.4). Delete `_sys/core/config.py`, `_sys/tests/unit/test_config.py` and `_sys/tests/unit/test_config_scoping.py`. This also removes the last writer of `_sys/config.json` (N12), whose only remaining reader is the SUBST branch removed in §7. The two `.gitignore` lines `_sys/config.json` and `_sys/core/config.json` stay, harmlessly, for old trees.

### 4.3 Allowlists and scanners

| File | Change |
|---|---|
| `_sys/checks/_common.py:37` `VENDOR_CACHE_DIRS` | Remove `".ai"`. This is safe for packaging: the `_sys` walk already skips every dot-directory (`build_package.py:186`), and root entries are file-allowlisted. The same edit applies to the `ImportError` fallback set in `build_package.py:48-52`. |
| `_sys/checks/check_root_hygiene.py:25-58` `ALLOWLIST` | Remove `.ai`, `_archive`, the 8 wrapper names and `wrapper.cs`. Add a **precise** special case for `.ai`: if `<root>/.ai` exists **and contains either Engram-owned name** (`tool_discovery_cache.json`, `tool_deferred_retries.json`), that is an **error** (`Engram-owned state in .ai/ — run 'engram doctor' to migrate`). If it exists with only other names, print `[INFO] .ai/ present: external orchestration state, not Engram-owned` and do not fail. Dev checkouts under the external hub keep passing; an Engram regression fails loudly. |
| `_sys/checks/saturation_scan.py:231` | Delete the `sys_root.parent / ".ai" / "state.json"` candidate. Its own docstring (`:223-227`) says no producer exists. |
| `_sys/checks/check_backlog.py:113` `_REPO_ROOTS` | **No change.** It classifies historical backlog `source_ref` strings; it is not a location policy and creates nothing. |

### 4.4 The acceptance rule, as tests

**Definition.** "Engram creates `.ai` again" means that any shipped Engram code path creates, or writes through, a filesystem path with a component named `.ai` (or `_archive`) anywhere under the portable root. Shipped code is everything the packager collects: root files plus `_sys/**`.

Enforced by two tests, both in the P1 backlog:

1. **Static:** `_sys/tests/unit/test_no_legacy_state_literals.py`. It scans every packaged `*.py`, `*.bat`, `*.cmd`, `*.json` and `*.ps1`, excluding `_sys/tests/**`, `_sys/docs/**` and `_sys/data/**`. It fails on any path-segment literal `.ai` or `_archive` (regex `(^|[\\/"'])\.ai([\\/"']|$)`, and likewise for `_archive`). There is exactly one allowlisted exception: `layout_migration.py`'s legacy-source constants (§5.2), recognized by an explicit `# legacy-source: migration only` marker on the line.
2. **Dynamic:** `_sys/tests/unit/test_root_write_locations.py`. Build a temp portable root from `collect_package_files()`. Stub the network (resolver returns one update, one `discovery_unavailable`, one error), provisioning (`deploy` returns one installed and one deferred entry), process spawns (VS Code, `cmd /k`) and `winreg`, and point `LOCALAPPDATA` into `tmp_path`. Then run in-process, in order: `update --check`, `update --yes`, `open`, `doctor --json`, `menu enable`, `menu status`, `menu disable`, `menu clean`, `tidy`, `tidy --apply --deep`, and the uninstall **planner** (no helper spawn). Assert:
   - `set(os.listdir(root)) ⊆ {"Engram.exe", "engram.cmd", "README.md", "LICENSE", "_sys", "workspace", ".engram"}`. This constant lives in new `_sys/core/layout.py` as `INSTALL_ROOT_ENTRIES` and is imported by the test and by the uninstaller.
   - No path component `.ai` or `_archive` exists anywhere under `root` (`os.walk`).

### 4.5 Existing `.ai`: exact-name ownership

The migration (§5.2, step M2) owns exactly two names in `.ai/`, `tool_discovery_cache.json` and `tool_deferred_retries.json`, and exactly two subtrees in `_archive/`, `logs/start_*.log` and `tool-updates/*`. It moves those and removes the containing directory only if it is then empty. Every other entry is left untouched and reported by name as external. Expected outcomes:
- **tttt:** `.ai/` holds only the cache → moved, and `.ai/` is removed. `_archive/{logs,tool-updates}` → moved, and `_archive/` is removed.
- **t2:** no-op.
- **This repo checkout:** `.ai/` is mixed; only the cache moves and all hub files stay.

---

## 5. Migration for existing installs: RULING (one idempotent layout migration; no staging tree)

### 5.1 The hazard that shapes everything: declarations are live state

Both fixtures carry locally advanced pins (N2). Today the zip ships `_sys/runtimes.json` and `_sys/tool-catalog.v1.json` **at their live paths**. So the natural upgrade gesture, extracting a new zip over the old folder, would silently roll tttt's `python`, `sqlite`, `fd`, `fzf`, `oh-my-posh` and `gh` pins back to the shipped values. cx §6.2 "freely replace `_sys` application code and built-in manifests" has the same flaw.

**Ruling: split shipped defaults from live declarations.**
- The package ships **defaults** at `_sys/defaults/runtimes.json` and `_sys/defaults/tool-catalog.v1.json`. In the repo these become the tracked files (a `git mv`).
- The live files `_sys/runtimes.json` and `_sys/tool-catalog.v1.json` are **never shipped** and are gitignored. They are created from the defaults on first bootstrap (`bootstrap.bat`, before its first read at the old `INSTALL.bat:28-36`: `if not exist "_sys\runtimes.json" copy /y "_sys\defaults\runtimes.json" "_sys\runtimes.json" >nul`, and likewise for the catalog). Afterwards they are merged forward by M3 below.
- Every reader of the live paths stays unchanged: `doctor.py:28,146`, `provisioner`, `check_tool_updates.py:29,87`, `bootstrap.bat`.
- Consequence: **extracting any future zip over an install is safe by construction.** The zip contains nothing that is user data or live state. A packaging test asserts this (P1-10).

### 5.2 The migration: `_sys/core/layout_migration.py`, pipeline `migrate-layout`

**Trigger.** `engram.cmd` runs `dispatch.bat migrate-layout` **automatically, before any verb**, whenever Python exists and `_sys\data\state\layout.json` is missing or its `layout_version` < 2. It is idempotent. `--dry-run` is available via `_sys\core\dispatch.bat migrate-layout --dry-run` for tests and developers.

**Why automatic, when the dotdir ratification (§5.1 there) rejected automatic migration.** That rejection rested on an ambiguous discriminator: the same `.ais/` name meant snapshot in one tree and live root in another. Here every action is gated either by an exact name or by a byte-exact hash of a known shipped artifact. The migration never reads, enumerates or writes `.engram/`, `workspace/` or any `.peerhub/`. Deletions are limited to files byte-identical to a published release.

| Step | Action | Failure behavior |
|---|---|---|
| **M0 Preflight** (read-only) | Refuse if legacy host integration is recorded (§7.3): `register.state.json` has a non-empty `junctions` list or any `subst_drive` key, or `_sys/config.json` has `SUBST_DRIVE_LETTER`. Print the exact manual teardown commands. tttt (`junctions: []`, no `subst_drive`) and t2 (no state file) both pass. | Exit 1; nothing changed; the verb does not run |
| **M1 Retire shipped files** | Candidate old manifests: the one for `layout.json`'s recorded `engram_version` if present (every release commits its manifest under `_sys/core/release-manifests/<ver>.json`), else **all** committed legacy manifests (initially just `3.2.6.json`). The hash is the sole gate, so no version guessing is needed: a file that is byte-identical to a published release artifact is by definition a program file. For every path in a candidate manifest that is **not** in the current `release-manifest.json`: if the file exists and its sha256 equals that manifest's, delete it; if it differs, keep it and report `modified, kept`. Then remove a directory only if it is empty. **Never** considered: `_sys/runtimes.json`, `_sys/tool-catalog.v1.json` (M3 owns them), anything under `.engram/`, `workspace/`, `_sys/env/`, `_sys/tools/`, `_sys/data/`. | A per-file error is reported and the run continues; exit 1 at the end if any |
| **M2 Move Engram-owned state** | Exact names only (§4.5), `os.replace` within the root, destination directories created. If a destination already exists, leave the source in place and report it. Remove `.ai/`, `_archive/logs/`, `_archive/tool-updates/` and `_archive/` only if empty. | Same |
| **M3 Merge declarations** | For each of the two live files: if missing, copy the default. Otherwise do a **three-way merge per component** (key: `section/name` for `runtimes.json`, `tool_id` for the catalog). *Base* = the previous release's shipped default, taken from `_sys/data/state/defaults-base/<file>`, or for v3.2.6 from the committed `_sys/core/release-manifests/3.2.6-defaults/<file>`. *Theirs* = the new default. *Ours* = live. Rules: ours == base → take theirs. Ours ≠ base → keep ours (locally updated) and report it. Component only in theirs → add. Component only in base: remove if ours == base, else keep and report. Non-component keys (`_comment`, `$schema`) → theirs. Write atomically (`_atomic_write_json`) after copying the old file to `_sys/data/state/defaults-base/<file>.pre-merge.bak`, then save theirs as the new base. | Any exception → the live file is untouched; exit 1 |
| **M4 Record** | Write `_sys/data/state/layout.json` = `{"layout_version": 2, "engram_version": …, "migrated_at": …, "report": {retired, kept_modified, moved, external_left, merged}}` and print a one-screen summary. | — |

**Rejected, from cx §6.3:** staging directory, venv recreation, executable swap, dual-generation rollback. Nothing moves `_sys/env`, and the interpreter is never touched, so none of those hazards exist. cx's preflight, byte-preservation manifest, exact-name `.ai` rule, "never test on the live installs first" rule and postflight proof are **kept**.

### 5.3 First hop for v3.2.6 zip installs (tttt, t2)

v3.2.6 has no in-place updater, so the first hop is documented in the release notes and README:

1. Close VS Code and any shell launched from the install.
2. Extract the new zip **into the existing install folder**, choosing *Replace* for conflicts. This is safe by §5.1: the package contains only `Engram.exe`, `engram.cmd`, `README.md`, `LICENSE` and program files under `_sys/`.
3. Run `engram` (or `engram doctor`). M0–M4 run once, then the verb.

Every later version arrives through `engram update` (§8.4), which performs the same overlay and the same migration steps, so there is one code path.

- **Git checkouts:** after `git pull`, the index no longer tracks `_sys/runtimes.json`. M3 recreates it from the defaults, and a developer's local pin edits survive only if uncommitted (git refuses the pull). This is acceptable because dev checkouts carry no user data at those paths.
- **WinGet:** there are no WinGet installs yet (channel not live).

### 5.4 The preservation guarantee that ships, and how it is tested

**Guarantee:** migration, first-hop overlay, `engram update`, `open`, `doctor`, `menu`, `tidy` and default `uninstall` leave every byte, name and mtime under `.engram/` and `workspace/` unchanged, including every `.peerhub/`.

**Release-gating test** (`_sys/tests/fixtures/test_fixture_migration.py`, marked `fixture`, run manually before release):
1. Copy tttt and t2 byte-for-byte with `robocopy <src> <dst> /MIR /COPY:DAT /DCOPY:DAT /R:0` to disposable paths. The copies are about 465 MB / 17,856 files and 382 MB / 15,176 files of `.engram/`. **Never operate on the originals**; the test asserts `dst` is not `D:\tttt` or `D:\t2`.
2. Build manifest A over `.engram/` and `workspace/`: `(relpath, is_dir, size, sha256, mtime_ns)` for every entry.
3. Overlay the candidate package onto the copy (simulating step 2 of §5.3), then run `engram doctor`, `engram update --check`, `engram menu status` and `engram tidy`.
4. Build manifest B and assert **A == B**.
5. Additional asserts:
   - tttt copy's live `runtimes.json` pins equal its pre-overlay pins (the 6 advanced pins survive).
   - `.ai/` and `_archive/` are gone and the moved cache is byte-identical at its new path.
   - no retired root file remains.
   - `Engram.exe version` prints the new version.
   - PeerHub imports at 0.2.0 / 0.3.0 via `<copy>\_sys\env\python\python.exe -B -c "import sys;sys.path.insert(0,r'<copy>\_sys\env\venv\Lib\site-packages');import importlib.metadata as m;print(m.version('peerhub'))"`. This uses the copy's own interpreter with no bytecode writes, because the copied `pyvenv.cfg` still points at the original tree.
   - `workspace/smoke-test/.peerhub/peerhub.sqlite3` opens read-only (`sqlite3.connect('file:…?mode=ro', uri=True)`) and `PRAGMA integrity_check` returns `ok`.
6. Repeat against a copy of this repo checkout's mixed `.ai/`: only the two Engram names move, and every hub file is byte-identical.

---

## 6. Uninstall and tidy safety: RULING (independent fast path, ships first as v3.2.7)

**Agree with cx that this is a release blocker, and go further: it ships alone, as a v3.2.7 hotfix, before anything else in this document.** Today `engram uninstall` deletes `.engram/` (465 MB of real credentials, memory and sessions in tttt) and `workspace/` (including `.peerhub/peerhub.sqlite3`) **with no confirmation prompt** (N4).

### 6.1 Ratified default behavior

New module `_sys/core/uninstaller.py`, pipeline `uninstall: ["uninstall.run"]`. It runs under the base interpreter `_sys\env\python\python.exe` via `dispatch.bat`, **not** the venv, fixing N4's venv dependency. `engram.cmd` forwards all arguments.

1. **Plan (pure function `plan_uninstall(base_dir, sys_dir, purge_data) -> UninstallPlan`).** Deletion is by **allowlist**, never "everything except …". Anything not positively identified as Engram's is kept and listed.
   - Root files: `Engram.exe`, `engram.cmd`, `README.md`, `LICENSE`, plus legacy `*.bat` / `wrapper.cs` / `CONVENTION.md` if present.
   - Under `_sys/`: `env/`, `tools/`, `data/`, `defaults/`, the live declaration files, and every file listed in the current `release-manifest.json`. Then prune empty directories under `_sys/` bottom-up, and remove `_sys/` only if it is empty.
   - In **v3.2.7 only** (no manifest yet), the `_sys/` program set is the constant list of the v3.2.6 package's top-level `_sys` entries (exactly t2's `_sys` listing: `checks cli config context_menu.json core data dispatch.json docs env env.json local.config.bat.template managed-links.json paths.json runtimes.json start.bat tests tool-catalog.v1.json tools`). `local.config.bat` is user-authored and is **kept**.
   - Consequence for tttt: `.engram/`, `workspace/` and the legacy `_sys/{ai,claude,codex,antigravity,common}` (N5) are all **kept**.
   - Base dir: removed only if empty at the end.
   - `--purge-data` adds exactly `.engram/` and `workspace/`, nothing else. Unknown entries are still kept and listed.
2. **Link guard.** If any junction or symlink exists under any delete target (`os.scandir` walk; `DirEntry.is_junction()` or `is_symlink()`), refuse with the list and exit 1. Deletion must never traverse a link into data outside its target.
3. **Confirm.** Print "Will remove" (count and size) and "Will keep" (named: `.engram/  your AI-CLI settings, memory and credentials`, `workspace/  your projects`, then each unknown entry). Then prompt `Uninstall Engram from <root>? [y/N]`. `--yes` skips **this** prompt only. With `--purge-data` a **second prompt is always shown and cannot be bypassed by any flag**: `Type the folder name '<basename>' to also permanently delete .engram/ and workspace/:`. Only an exact match proceeds. EOF, a mismatch or empty input → exit 3, nothing changed.
4. **Host cleanup.** If `register.state.json` exists, call `registrar.remove(ctx)`. There is no virtualizer step (§7). Journal handling at `%LOCALAPPDATA%\Engram\uninstall\<install_id>\journal.json` is unchanged.
5. **Hand-off.** Write `plan.json` (absolute targets, base dir, journal path, parent PID) to `%TEMP%\EngramUninstall\<install_id>\<nonce>\`. Copy the **static, shipped** `_sys/core/uninstall_helper.ps1` there. Spawn `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <helper> -PlanPath <plan>` as an argv list, detached (no `cmd /c` parsing, so `&`, `!` and `%` in paths are inert). The helper:
   - waits for the parent (30 s → `FAILED_FATAL`)
   - re-runs the link guard (`Get-ChildItem -Recurse -Force -Attributes ReparsePoint`; any hit → skip that target and log it)
   - runs `Remove-Item -LiteralPath <t> -Recurse -Force` for each target
   - prunes empty directories and removes the base dir only if it is empty
   - writes `COMPLETED` / `FAILED_RECOVERABLE` (with the remaining paths) to the journal.

   The generated `EngramUninstallHelper.bat` and its `rmdir /s /q "!BASE_DIR!"` (`manage.py:99-139`) are deleted.

### 6.2 Tests (P0; each must fail against today's code first)

All run against `tmp_path` fixtures with `LOCALAPPDATA` and `TEMP` redirected. `.engram/` is populated with `claude/.credentials.json`, `codex/auth.json` and `gh/hosts.yml` stand-ins plus nested dirs. `workspace/proj/.peerhub/peerhub.sqlite3` and `_sys/claude/config/x.json` (legacy) are also populated. Helper execution is real (`powershell.exe`) with the parent-wait bypassed by passing a PID that has already exited.

1. Default uninstall with `--yes`: manifests of `.engram/`, `workspace/` and `_sys/claude/` are byte-identical before and after; every planned program path is gone; the root still exists (it is non-empty).
2. Default uninstall with stdin `n`: nothing is deleted, exit 3.
3. `--purge-data --yes` with stdin = the correct folder name: `.engram/` and `workspace/` are gone; the unknown `notes.txt` at root is kept.
4. `--purge-data --yes` with stdin = a wrong name, or EOF: nothing is deleted (including program files), exit 3.
5. A junction planted at `_sys/env/link → <tmp>/outside`: refused, exit 1, `outside/` untouched.
6. Paths `tmp_path/"a&b!c%d"`: the helper completes. This extends today's `&` test in `test_uninstall_semantics.py:127-179`.
7. `engram.cmd uninstall --yes` reaches the pipeline with its args (a characterization test through `engram.cmd` with a stub `dispatch.bat`, following `test_engram_cmd_cli_entrypoint.py`).

### 6.3 `cleanup` is removed; `tidy` is the only cleanup verb

**Ruling:** delete `scrubber.py`, the `cleanup` pipeline and the `scrub.run` operation.
- Tier 1's safe, regenerable items are folded into `tidy`: pytest caches under `_sys/tests` by default; `__pycache__` under `_sys/` and launcher/system logs beyond 5 under `--deep`.
- Tier 1's root `.vscode`, `_state` and `WORKLOG.md` deletions are **not** carried over. They are user-visible root files, and Engram no longer creates them.
- Tiers 2, 3 and 5 (venv, runtimes, Python) get **no** replacement verb. "Reset my runtimes" is `engram uninstall` (data-preserving now), re-extract, then `engram`.
- Tier 4 (deletes `workspace/`, `_archive/` and every root `*.md`, `scrubber.py:194-206`) is removed permanently. Deleting user projects is never a cleanup operation. The only data-deleting path in the product is `uninstall --purge-data` with its typed confirmation.

`tidy` tests (P0): a fixture holding both allowlisted debris and populated `.engram/`, `workspace/` (with `.peerhub/`), `_sys/env/python`, `_sys/tools/rg`, both live declarations and `_sys/data/state/*`. Assert that `tidy`, `tidy --apply` and `tidy --apply --deep` each delete exactly their documented set and leave the never-touch set (§3.3) byte-identical. Assert also that a planner fed a path inside the never-touch set raises an `AssertionError` (defense in depth).

---

## 7. SUBST and junctions: RULING (remove the capability entirely; this is warranted, not overkill)

### 7.1 Why full removal, not "unused by default"

Independent of the user's hard requirement, the evidence says removal is **lower** risk than keeping the code:
- **No writer exists.** `managed-links.json` ships `"entries": {}`. Nothing in current code writes `subst_drive` (it is only read, at `launcher.py:207` and `registrar.py:336-337`, and listed at `dispatcher.py:63`). The last writer of the legacy `_sys/config.json` `SUBST_DRIVE_LETTER` source is `ConfigManager._save_global`, deleted in §4.2.
- **Both real installs show zero.** tttt has `junctions: []` and no `subst_drive`; t2 has no state file.
- **The code actively misleads.** `doctor.check_subst` tells every healthy install `not mounted (run register.bat to mount the P: drive)` (`doctor.py:89-90`). The help text says `register` mounts `P:` (`engram.cmd:132-133`). `build_package.py:74-88` advertises "virtual drive management (P:)" in the WinGet description.
- **Keeping it is not free.** It carries 18 test files (listed in §7.2), a `_winapi.CreateJunction` path that merges and deletes host directories (`virtualizer.py:72-85`), and SUBST branches in the launcher.
- **Host safety.** The only live SUBST mapping on this host belongs to v2.1-env (N6). Code that probes the host SUBST table can only ever produce false positives or worse.

The residual risk is an older install with a recorded mapping or junction. That is handled by M0 refusing with manual instructions (§7.3), not by keeping creation code.

### 7.2 Removal scope (exact)

| Location | Change |
|---|---|
| `_sys/core/virtualizer.py`, `_sys/managed-links.json` | Delete. |
| `_sys/dispatch.json` | Delete ops `virtual.mount` and `virtual.unmount`. Pipelines per §3.3 (`menu-enable`, `menu-disable`, `menu-clean`). Delete `register`, `unregister`, `menu-cleanup`, `cleanup` and `init`. `init: []` is empty and unused. |
| `_sys/core/launcher.py` | Delete `_map_subst_drive` (`:90-107`), the saved-drive read and remap (`:201-223`) and the physical→drive target rewrite (`:247-249`). `base_dir`/`sys_dir` are always physical. Update the docstring at line 4. |
| `_sys/core/registrar.py` | `:336-337` become `root = phys_root = str(base_dir)`; drop `subst_drive` and the SUBST comments at `:59`, `:152-157`. |
| `_sys/core/dispatcher.py:63` | `_REGISTER_STATE_KEYS = {"registry_entries"}`. |
| `_sys/core/doctor.py` | Replace `check_subst` (`:63-90`) with `check_legacy_host_integration(base_dir, sys_dir)`. It reads **only** this install's `register.state.json` and `_sys/config.json` (no `subst.exe`, no host enumeration). It returns `warning` with the §7.3 instructions if `subst_drive`, a non-empty `junctions` or `SUBST_DRIVE_LETTER` is recorded, and `ok` otherwise. |
| Docs and strings | README.md lines 4, 14, 23, 75, 81-82; `engram.cmd` help; `docs/engram-dotdir.md` final section; CONVENTION.md; `build_package.py:74-88` descriptions. |
| Tests | Delete or rewrite the SUBST/junction parts of the 18 files returned by `git grep -l -i -E "subst\|junction\|virtualizer\|managed-links" -- _sys/tests`: `integration-test.ps1`, `launch-wsbtest.ps1`, `lifecycle_tester.py`, `local-test.bat`, `run-sandbox-test.bat`, `run-tests.bat`, `test-runner.ps1`, `unit/l1_core/test_contracts.py`, `test_dispatch_wiring.py`, `test_doctor.py`, `test_doctor_missing_keys.py`, `test_launcher.py`, `test_launcher_paths.py`, `test_managed_links.py` (delete), `test_path_scenarios.py`, `test_system_lifecycle.py`, `test_uninstall_semantics.py`, `test_version_resolver.py` (the last one matches only "substring" and needs no change). |

### 7.3 Legacy teardown: detection plus manual instructions, no code path that runs `subst`

If M0 or `doctor` finds a recorded integration, print, for this install only:
- `subst X: /D`, preceded by: first run `subst` and confirm the line `X:\: => <this install's path>`; do nothing if it points elsewhere.
- `rmdir "<host>"` for each recorded junction host (`rmdir` on a junction removes the link, not the target).
- Then delete the `subst_drive` key and `junctions` entries from `_sys\data\state\register.state.json`.

**Release gate:** `git grep -n -i -E "\bsubst\b|CreateJunction|_winapi|mklink"` over packaged code returns only lines carrying the marker `# legacy-detect` (in `layout_migration.py` and `doctor.py`), and none of them invokes a process.

---

## 8. One update story: RULING

### 8.1 The user contract (README sentence, literally true)

> Run `engram update` to keep Engram and everything it manages current. Anything it cannot check automatically is listed by name under "Not checked" — never counted as up to date.

### 8.2 Flow (`_sys/core/updater.py` `run(ctx)`)

1. **Discover per component, isolating errors.** One provider failure lands that component in "Could not check" and never blocks the others. This fixes N9 (`updater.py:29-30`).
   - **Engram core:** §8.4.
   - **Runtimes:** Python via a new `endoflife_python` provider in `version_resolver.py`, a port of the query at `INSTALL.bat:68-69`. It is shown as a **manual** item (§8.3). `nodejs`/`git`/`vscode`/`pwsh` stay "Not checked: no discovery provider" until P2-1.
   - **Tools:** `runtimes.json` `tools`, unchanged discovery.
   - **AI CLIs:** catalog discovery, with apply fixed (§8.3).
   - **Repairs:** components that `doctor.check_components` reports missing, planned as reinstall at their current pin.
2. **Print one grouped plan:** `Engram core`, `Runtimes`, `Tools`, `AI CLIs`, `Repairs`, `Not checked`, `Could not check`. If nothing is actionable, print `Everything Engram can check is up to date.` and exit 0.
3. `--check` stops here. Exit 1 if "Could not check" is non-empty, else 0.
4. **Confirm once:** `Apply N changes? [y/N]`, unless `--yes`. Declining exits 3.
5. **Apply declarations.** Write the proposal to `_sys/data/state/update/proposals/<stamp>/` with the base sha256 of **both** live files. Re-verify both hashes, back up both, and replace both atomically (both-or-neither; on a second-replace failure restore the first from backup).
6. **Reconcile** by calling `provisioner.deploy(ctx)` **in-process**. This replaces the `--install` subprocess `.\INSTALL.bat --skip-update` (`check_tool_updates.py:312-318`). `--install` is removed from `updater.py` and `check_tool_updates.py`: the deploy is no longer an optional second phase.
7. **Verify per component** with the provisioner postcondition or canary. For a component that failed or was deferred, **revert only that component's entry** in the live declaration to its backup value, so a failure can never leave a new pin with an old binary presented as success. Record it in the receipt.
8. **Core last:** stage and hand off (§8.4); print `Engram will finish updating to X when this window closes.`
9. **Receipt** at `_sys/data/state/update/receipts/<stamp>.json`: plan, applied, reverted, deferred, errors, core handoff. Exit 0 if everything selected succeeded, else 1.

### 8.3 Fixes inside the flow

- **Catalog-application bug (the confirmed defect, §0.4).**
  - `discover_updates()` also returns `proposed_catalog = copy.deepcopy(catalog)`. For `section == "catalog"` it sets the entry's `version` and `source.url` from the discovery result. It does **not** invent a `digest`; npm-peer entries install by version. Any existing `digest` is left untouched unless the provider returned the same algorithm.
  - `write_proposal_artifacts()` also writes `tool-catalog.proposed.json` and `tool-catalog.diff`; `proposal.json` gains `catalog_base_sha256`.
  - `verify_proposal_still_valid()` checks both hashes.
  - `apply_proposal()` writes both files (both-or-neither).
- **Python:** listed as `Python 3.14.7 -> 3.14.x (manual: close Engram, delete _sys\env\python, then run 'engram update --yes')`. Deleting the interpreter makes `update` bootstrap, and the first-install bump in `bootstrap.bat` (`INSTALL.bat:71-88` logic, unchanged) picks up the latest version. Never auto-applied: that is the running-interpreter hazard §1 keeps out of scope.
- **`--only`** filters the entry iteration in `_iter_discoverable_entries()`, plus the core and repairs phases, before any network call.

### 8.4 Engram core update (bounded in-place overlay; the one piece of cx's lifecycle that N1 makes mandatory)

- **Channel**, computed on every run, with no state file:
  - `git` if `<root>/.git` exists → "Not checked: git checkout — use git pull".
  - `winget` if the root is under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\` → "Not checked: managed by WinGet — run winget upgrade greatgc-flow.Engram".
  - `portable` otherwise.
- **Discovery (portable)** via a new `engram_release` provider in `version_resolver.py`. It calls `GET repos/greatgc-flow/Engram/releases/latest` (the same `gh`/urllib paths as `_resolve_github`, cache under `state_paths.discovery_cache`). The asset must be named **exactly** `Engram-v{version}-portable-x64.zip`, because the generic picker rejects it (N8). The asset's `digest` must be `sha256:<hex>`. **No digest → error "release has no digest; refusing".**
- **Stage** into `_sys/data/temp/core-update/<ver>/`: download the zip, verify sha256 == digest, extract to `staged/`, then verify:
  - `staged/_sys/core/version.json` == tag
  - every staged file's hash == `staged/_sys/core/release-manifest.json`
  - staged root entries ⊆ `INSTALL_ROOT_ENTRIES`
  - no staged path under `.engram/`, `workspace/`, `_sys/env/`, `_sys/tools/`, `_sys/data/`, or at `_sys/runtimes.json` / `_sys/tool-catalog.v1.json`.
- **Hand off** to the static, shipped `_sys/core/core_update_helper.ps1`, copied to the temp dir and launched exactly like §6.1 step 5, **after** Engram exits.
  - Why a helper: `cmd.exe` re-reads a running batch file by byte offset after each `call`, so overwriting `engram.cmd` mid-run corrupts the dispatcher, and the running `Engram.exe` image is locked.
  - The helper backs up each file it will overwrite into `…/backup/`, renames `Engram.exe` → `Engram.exe.old` (renaming a running image is allowed), and copies the staged files.
  - On any failure it restores every backed-up file and journals `FAILED_ROLLED_BACK`; on success, `COMPLETED`.
- **Finish on next start:** the §5.2 trigger also fires when `layout.json.engram_version` ≠ `version.json`. M1 retires files dropped by the new release, M3 merges declarations, and the migration deletes `Engram.exe.old` and the temp dir.
- **Not included:** release generations, pointer files, dual retained engines. The only rollback unit is "the files this overlay overwrote", which the helper keeps until success.

---

## 9. Disagreements between the proposals: one ruling each

| Point | ag | cx | Ruling | Deciding evidence |
|---|---|---|---|---|
| Entrance | `engram.cmd` + keep `INSTALL.bat` | Native `Engram.exe` bootstrapper; `engram.cmd` shim for one release | `engram.cmd` stays the dispatcher; `Engram.exe` becomes a correct thin forwarder; **no** root `.bat` | Forwarding fixes the alias defect in about 40 lines; a native rewrite duplicates the dispatcher (§1) |
| `INSTALL.bat` | Keep at root | Remove (first run bootstraps) | Moved to `_sys/core/bootstrap.bat`; first run and `update` call it | The pre-Python bootstrap is needed; a public file for it is not |
| `cleanup` vs `tidy` | Keep both | `tidy` only | `tidy` only; destructive tiers deleted | Tier 4 deletes `workspace/` and README (N11) |
| Registration verbs | Keep `register`/`unregister`/`menu-cleanup` | `menu enable\|disable\|repair` | `menu [status\|enable\|disable\|clean]` | cx's `repair` conflated two actions; split into `enable` + `clean` |
| Engram self-update | `git pull` | Generations + pointer + native staging | Hash-verified in-place overlay via post-exit helper (§8.4) | N1 (no git in real installs); interpreter untouched (§1) |
| `_sys` name | Keep | Rename to `engine/` | Keep (§2) | N7 venv absolute paths; 100 code files |
| `.ai` destination | `.engram/state/` | `engine/state/update/` | `_sys/data/state/update/` | dotdir tier model; §2 |
| `ConfigManager` | Redirect to `.peerhub/` | Delete | Delete | Zero consumers; binding `.peerhub` constraint |
| Hub `.ai` state | Redirect to `.engram/hub/` | Not Engram's; detect and explain | cx | Out of scope; hub.py is not in this repo |
| Migration | 5-line move script | 9-step transactional | M0–M4 automatic, hash/exact-name gated (§5.2) | No staging needed without rename or interpreter swap; N2 forces the defaults split |
| Uninstall | Not addressed | Preserve `.engram`/`workspace`; `--purge-data` | cx, strengthened: allowlist deletion, link guard, un-bypassable typed purge confirmation, v3.2.7 fast path | N4, N5 |
| SUBST/junction | Not addressed | Remove after teardown | Remove; teardown is manual instructions only (§7.3) | N6; no writer exists |

---

## 10. Implementation backlog (dependency-ordered, TDD: write the listed tests first and see them fail)

### P0: v3.2.7 hotfix (independent of everything below; ship first)

1. **Uninstall safety.** Add `_sys/core/uninstaller.py` (`plan_uninstall`, `run`) and the static `_sys/core/uninstall_helper.ps1`. Add the `uninstall.run` op and `uninstall` pipeline to `dispatch.json`. Change `engram.cmd` `:cmd_uninstall` to `call "_sys\core\dispatch.bat" uninstall %1 %2 %3 %4 %5 %6 %7 %8 %9`. Remove `uninstall()` and the `.bat` helper generation from `_sys/cli/manage.py`. Use the v3.2.7 constant program set from §6.1. *Tests:* §6.2 cases 1–7; replace `test_uninstall_semantics.py`'s helper-shape tests with PowerShell-helper equivalents.
2. **`Engram.exe` forwards args and exit code.** Rewrite `wrapper.cs` per §3.1 and move it to `tools/winget/wrapper.cs`. Add `tools/winget/build_exe.py`. Commit the rebuilt `Engram.exe`. **v3.2.7-only special case:** with no args and `_sys\env\python\python.exe` absent, forward `install`, which preserves today's double-click-to-install behavior. It is deleted in P1-7, when bare `engram` becomes first-run. *Tests (`test_engram_exe.py`, skip if `csc.exe` is absent):*
   - build into `tmp/"a&b!c"`, next to a stub `engram.cmd` that echoes `%*` and exits 7
   - args with spaces, `!`, `&`, a trailing backslash and an embedded `"` arrive intact
   - exit code 7 propagates
   - invocation through a file symlink (if creatable, else skip with reason) resolves to the real directory.
3. **Version truth.** `engram.cmd` `:show_version`/`:show_help` read `version.json` (§3.3); drop the `P:` lines from help. `_sys/core/version.py` loses its `"3.2.0"` literals and yields `"unknown"` on failure; `build_package.py` refuses to package `"unknown"`. *Tests:* `engram version` output == `version.json`; no `\d+\.\d+\.\d+` literal in `engram.cmd` or `version.py`.
4. **Release v3.2.7** with the standard `build_package.py` flow; the WinGet manifest follows.

### P1: v3.3.0 (in this order; each item lists what it depends on)

1. **Surface contract tests first** (no dependency). A table-driven `test_engram_cmd_surface.py` with a stub `dispatch.bat` in an `a&b!` directory covers every §3.2 verb and flag, every §3.4 retired verb (exit 2 plus message), unknown word (exit 2), existing path → `open`, the not-set-up rule, and `!` preservation. Tests stay red until P1-7.
2. **State paths and `.ai`/`_archive` writers** (no dependency). Add `_sys/core/state_paths.py`, retarget the 5 writers in §4.1, delete `ConfigManager` (§4.2), apply the allowlist/scanner edits (§4.3), and add the static test (§4.4 #1). *Tests:* each writer lands at its new path on a clean fixture; hygiene error/info behavior for Engram-owned vs external `.ai`.
3. **SUBST/junction removal** (no dependency). Everything in §7.2 plus `doctor.check_legacy_host_integration`. *Tests:* recorded `subst_drive` / non-empty `junctions` / `SUBST_DRIVE_LETTER` → warning with instructions; clean state → ok; `doctor` never spawns `subst` (assert via a monkeypatched `subprocess`); menu enable/disable round-trips on copies of tttt-shaped and t2-shaped state; the §7.3 grep gate.
4. **Defaults split** (no dependency). `git mv _sys/runtimes.json _sys/tool-catalog.v1.json _sys/defaults/`; gitignore the live paths; add the `bootstrap.bat` copy lines; `layout_migration.merge_declarations()` implements §5.2 M3. *Tests:* the table-driven three-way merge. Cases: ours==base; ours advanced (tttt's 6 pins kept); component added upstream; component removed upstream with ours==base and with ours≠base; `_comment` taken from theirs; atomic write leaves the live file intact when an exception is injected.
5. **Release manifests** (depends on P1-4). `build_package.py` emits `_sys/core/release-manifest.json` and commits `_sys/core/release-manifests/<ver>.json`. A one-time script `tools/winget/import_legacy_manifest.py` downloads `Engram-v3.2.6-portable-x64.zip`, verifies `sha256:248b1784…eb52f`, and writes `release-manifests/3.2.6.json` + `release-manifests/3.2.6-defaults/{runtimes.json,tool-catalog.v1.json}`. *Tests:* the manifest lists every packaged file with the correct hash; the committed 3.2.6 manifest's `engram.cmd` hash equals the fixtures' md5-identical file (sha256 recomputed in-test from the repo's `v3.2.6` blob).
6. **Layout migration M0–M4** (depends on P1-2, P1-4, P1-5) and the `engram.cmd` auto-trigger (layout version, or engram version changed). *Tests* on synthetic fixtures:
   - tttt-shaped: `.ai` holding only the cache, `_archive/{logs,tool-updates}`, legacy `_sys/{ai,claude,codex}`, advanced pins, pristine v3.2.6 wrappers → all retired, moved and kept as specified
   - t2-shaped → wrappers retired, no-op otherwise
   - mixed `.ai` → only the 2 names move
   - a modified `UPDATE.bat` is kept and reported
   - recorded junction → M0 refuses and nothing changes
   - a second run is a no-op
   - `--dry-run` mutates nothing
   - a manifest-diff assertion that `.engram/` and `workspace/` are untouched in every case.
7. **Command surface** (depends on P1-3, P1-6; turns P1-1 green).
   - Rewrite `engram.cmd` per §3.2–§3.4 and add the first-run flow and `ENGRAM_CALLER_CWD`.
   - Move `INSTALL.bat` to `_sys/core/bootstrap.bat`; add `_sys/cli/engram.cmd`.
   - Delete the 7 root wrappers and the `_sys/cli` shims listed in §3.5.
   - Add pipelines `menu-enable`, `menu-disable`, `menu-clean`, `tidy`, and `registrar.clean_orphans(dry_run=True)` for `menu status`.
   - Update `lifecycle_tester.py`, `integration-test.ps1`, `local-test.bat`, `test_launcher_paths.py`, `test_dispatch_wiring.py` (`INSTALL.bat` → `_sys/core/bootstrap.bat`) and `test_check_tool_updates.py:325`.
   - Remove the P0-2 double-click special case.
8. **Tidy** (depends on P1-7). `core.tidy_temp.run(ctx)` with `--apply`/`--deep` per §3.3; delete `scrubber.py`, `_sys/cli/cleanup.py`, `test_scrubber_tier2.py`, `test_scrubber_tier5.py`, and the Tier-4 cases in `test_system_lifecycle.py`. *Tests:* §6.3.
9. **Update flow** (depends on P1-2, P1-4). Implement §8.2–§8.3 in `updater.py` / `check_tool_updates.py` / `version_resolver.py` (`endoflife_python`). *Tests:*
   - a catalog bump is actually written to `tool-catalog.v1.json`, and the next discovery reports it up to date
   - a mixed runtimes+catalog proposal applies both-or-neither (inject a failure on the second replace)
   - a stale check on either file refuses
   - one provider error does not block others
   - `--check` writes nothing but the cache
   - `--only codex` makes exactly one resolver call
   - deploy reports `failed: [fd]` → only fd's pin reverts and exit is 1
   - Python is shown as manual and never applied
   - a missing component appears under Repairs
   - `--install` is rejected as unknown.
10. **Packaging** (depends on P1-4, P1-5, P1-7). `ROOT_FILES_ALLOW` = `{engram.cmd, Engram.exe, README.md, LICENSE}`. *Test* on the built zip:
    - root entries are exactly those 4 files + `_sys/`
    - no `_sys/env|tools|data/state|data/logs|data/temp`, no `_sys/runtimes.json` / `_sys/tool-catalog.v1.json` (only `_sys/defaults/…`), no `.ai`/`_archive` component, no root `*.bat`, no `wrapper.cs`
    - `release-manifest.json` matches the zip content.
11. **Core update** (depends on P1-5, P1-6, P1-9, P1-10). Implement §8.4 (`engram_release` provider, staging, `core_update_helper.ps1`, finish-on-next-start). *Tests:*
    - digest mismatch, missing digest, wrong asset name and staged-path escape each refuse
    - an overlay in an `a&b!` root succeeds, and the next start's migration retires dropped files and deletes `Engram.exe.old`
    - an injected copy failure restores every overwritten file byte-identically
    - `git` and `winget` channels are reported "Not checked".
12. **Dynamic write-location test** (§4.4 #2; depends on everything above).
13. **Docs** (depends on P1-7…P1-11).
    - README: quick start = extract, then double-click `Engram.exe` or run `engram`; the §3.2 command table; the §8.1 sentence; uninstall semantics; the §5.3 first-hop instructions; remove the direct `provisioner.py ensure-peer-cli` commands (README.md:85-90) in favor of `engram update --only`.
    - CONVENTION.md: §3.2 → "the root has no batch files; `engram.cmd` routes to `_sys/core/dispatch.bat`"; §5.2 → batch files (all under `_sys/`) are lowercase kebab-case, which resolves ag's §6.2 contradiction by removing the uppercase files.
    - `docs/engram-dotdir.md` final section.
14. **Fixture migration gate** (§5.4) on disposable copies of tttt and t2, plus this repo's mixed `.ai/`. Run manually. It gates the release.

### P2: after v3.3.0

1. Discovery providers and apply for `nodejs`, `git`, `vscode` and `pwsh` (moving them out of "Not checked").
2. Delete the dead hub-era fixtures `ai_dir` / `patch_ai_root` (`_sys/tests/unit/conftest.py:90-131`).
3. Find and isolate the registrar test that writes `SandboxRun_MagicMock_…` relays into the real `%LOCALAPPDATA%` (N13); then run `engram menu clean` on this host.
4. Optional: split `VENDOR_CACHE_DIRS` into separate hygiene / packaging / scanner sets. Its three roles are documented as conflated at `_common.py:25-31`.
5. Revisit the `_sys` rename only under the trigger in §2.

---

## 11. Release gates

**v3.2.7:** every P0 test is green; §6.2 cases pass with the real PowerShell helper; `Engram.exe version` prints `3.2.7` and propagates exit codes.

**v3.3.0:**
- The P1-1 surface suite passes via `engram.cmd`, via `Engram.exe`, and via `_sys\cli\engram.cmd`.
- The fixture migration gate (§5.4) passes on copies of tttt **and** t2: `.engram/` and `workspace/` manifests identical; tttt's 6 advanced pins preserved; PeerHub 0.2.0 / 0.3.0 importable; `peerhub.sqlite3` `integrity_check = ok`.
- `test_root_write_locations.py` passes: root ⊆ `INSTALL_ROOT_ENTRIES`, no `.ai`/`_archive` anywhere.
- The static legacy-literal test passes, and the §7.3 SUBST/junction grep gate passes.
- A catalog-sourced (Claude/Codex) update is demonstrably written to `tool-catalog.v1.json` and redeployed at the new version, verified against a fixture.
- The packaged zip satisfies P1-10.
- `check_root_hygiene` passes on the repo and `git status` is clean.
- No root `*.bat` and no version literal in shipped code.

---

## 12. Deferred (recorded, not rejected forever)

- cx's release generations / `current.json` pointer / dual-engine rollback. Revisit only if Core-overlay failures are observed in practice.
- cx's typed component-registry record. The two-file proposal with per-component revert (§8.2) covers the confirmed bugs.
- In-place Python replacement.
- The `_sys` → `engine` rename (§2 trigger).
- The PeerHub-side equivalent pass (separate round, independent design).

---

## 13. Summary of rulings

| # | Question | Ruling |
|---|---|---|
| 1 | Scope | **Hybrid.** cx's user contract (no root `.bat`, one `update` including Core, data-preserving uninstall, SUBST/junction removal) on ag's structure (keep `_sys`, `engram.cmd` dispatcher). cx's native bootstrapper, release generations, pointer and 9-step migration are **rejected**. A bounded in-place Core overlay is **in scope**, because both real installs are zip extractions with no update path (N1). |
| 2 | `_sys` → `engine` | **No.** The rename forces a network-dependent venv rebuild in every install (N7) for a cosmetic gain. Root declutter to 7 entries addresses the discomfort. cx's centralize-first method is endorsed for any future rename. |
| 3 | Command surface | `engram [open] [PATH]`, `update [--check] [--yes] [--only]`, `doctor [--json]`, `menu [status\|enable\|disable\|clean]`, `tidy [--apply] [--deep]`, `uninstall [--yes] [--purge-data]`, `version`, `help`. Retired verbs exit 2 with guidance. `Engram.exe` forwards args and exit code. Full contracts in §3. |
| 4 | `.ai/` | Engram's state moves to `_sys/data/state/update/`, and `_archive/` output to `_sys/data/{state/update/proposals,logs/launcher}`. `ConfigManager` is deleted. `.ai` is removed from the allowlists, with an Engram-owned-names hygiene error. The acceptance rule is enforced by one static and one dynamic test (§4.4). |
| 5 | Migration | Split shipped defaults from live declarations (N2), so extracting a zip over an install is safe. One automatic, idempotent, hash/exact-name-gated migration (M0–M4). The byte-identical `.engram/` + `workspace/` guarantee is proven on disposable copies of tttt and t2 before release. |
| 6 | Uninstall/tidy | **v3.2.7 fast path.** Allowlist deletion; `.engram/`, `workspace/` and unknowns are kept by default; a link guard; `--purge-data` needs a typed folder-name confirmation that no flag bypasses. `cleanup` is removed; `tidy` is dry-run by default with an asserted never-touch set. |
| 7 | Errors found | ag: `git pull` self-update is impossible for real installs; `.engram/state/` breaks the tier model; the `.peerhub/` redirect violates a binding constraint; root `tools/` is the packager, not dead; the repo root was mistaken for the install root. cx: a blind `_sys` replace would downgrade local pins (N2); a SUBST check must be scoped to this install (N6); the rename's venv cost was understated. Both missed `_archive/`, the absence of an uninstall prompt, the exit-code swallowing in `Engram.exe`, the digest-bearing but name-mismatched release asset, and the whole-update abort on a single provider error. |

