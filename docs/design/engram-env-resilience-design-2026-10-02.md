# Engram Environment Resilience: Python/venv Lifecycle, Root Relocation, and Backup Retention

- **Status**: **IMPLEMENTED P0-P4 (v3.6.0)**; design R4.1 (cross-reviewed by cc.deepthink, ag.deepthink, ag.pro, cx.pro). P5 (legacy backup producers) and further review notes are tracked in the approval-gate record. User guide: `docs/env_resilience_guide.md`.
- **Author**: `cc` (Claude Sonnet 5.5), at the user's request
- **Date**: 2026-10-02
- **Reviewers requested**: `ag.deepthink` (Windows/failure modes), `cc.deepthink` (state machine/rollback/idempotency), `ag.pro` (security/retention); `cx` unavailable (usage limit until 2026-10-04 10:35)
- **Target repo**: `workspace/engram` (commit `72e7d15`, v3.5.0). Live install used for fact-finding: `D:\PkgDev\_sys`.
- **Related**: `engram-sys-rename-phase4-batch-entrypoint-design-2026-09-20.md` (the `_sys` folder rename; this doc covers the *root* folder and the interpreter/venv), `docs/engram-dotdir.md`, `docs/user_lifecycle_guide.md`.
- **Language**: English only (CONVENTION.md section 1). User-facing console text may be Korean.

Evidence labels: **[V]** verified by reading code/state in this session, **[I]** inferred from structure, **[U]** unverified - must be proven by a spike before implementation.

---

## 1. Problem statement

Three real failure classes, one shared root cause: Engram keeps **absolute-path, version-coupled artifacts** (the venv, registry keys, state files, editable installs, AI-tool project state) but has **no single record of what it believes the environment is**, so it cannot detect or repair drift.

1. **Python deleted, venv kept -> silent version skew.** *(Corrected in R3: earlier drafts claimed the venv breaks without its base Python; spike S-9 disproved that, section 1a.)* `bootstrap.bat` reinstalls Python, possibly a **different version** (it may auto-bump to latest stable and rewrite `runtimes.json` [V]); `provisioner.py:1499` tests only that `venv\Scripts\python.exe` exists [V], so the venv stays on its own **older interpreter copy** while `env\python` moves on. Nothing detects or reports the skew, `runtimes.json` no longer describes what the venv runs, and a later minor-version change leaves C-extension packages built for the wrong ABI.
2. **Root folder renamed/moved.** `pip.exe`/`pytest.exe`-style **console-script launchers embed the absolute venv path and stop working** (S-1, [V]); `pyvenv.cfg` holds stale absolute paths (cosmetic: the venv interpreter still runs, S-1); editable installs keep absolute paths in their `__editable___*_finder.py`/`.pth` [V]; registry key names are derived from the path (`_registry_key_name`, e.g. `SandboxRun_D_PkgDev_engram_open`) [V], so a rename creates new keys and strands old ones; `data/state/*.state.json` store `base_dir` and relay paths [V]; Claude's per-project state is keyed by path (`.claude.json`, `projects/D--PkgDev-workspace`) [V].
3. **Backups accumulate with no owner.** Producers today: `<name>_old` dirs (`provisioner.py:690`), `core-update/<ver>/{staged,backup,journal}` under `data/temp` (`updater.py:535`), `*.pre-merge.bak` (`layout_migration.py:173`), `Engram.exe.old` (`layout_migration.py:513`), `data/backups`. `tidy_temp.py` knows none of them: it deletes by hard-coded name allowlists + age. The proposed fixes below would add more (python/venv old copies, freeze snapshots), so retention must be solved first-class.

### Non-goals
- Renaming the `_sys` folder (covered by the 2026-09-20 doc; this design must *interoperate*, storing `sys_dir.name` in the manifest).
- User-data backup/restore (`engram backup|restore|reset` = `.engram`/workspace data). Environment snapshots are a separate concept with a separate namespace; naming must not collide (section 8.1).
- Moving the install across machines (different user profile, different OS user). Out of scope; doctor reports.

---

## 1a. Spike findings that shape R3 (all [V], run in a throwaway tree under the session scratchpad on the real embedded Python 3.14.8 + virtualenv 21.14.2)

| ID | Question | Result |
|---|---|---|
| S-1 | Venv after renaming the root | venv `python.exe` **still runs** for plain scripts, but see S-12: `home` is *not* cosmetic. `pip.exe`, `pytest.exe`, other console scripts **fail** (absolute path in the launcher trailer). Patching `pyvenv.cfg` alone does not fix them. |
| S-2 | REQUESTED / editable markers | `REQUESTED` present for explicitly installed packages (pytest, tinypkg), **absent for dependencies** (pluggy, pip). `direct_url.json` carries `{"dir_info":{"editable":true},"url":"file:///..."}` for editable installs. Both reliable. |
| S-3 | Stale `version`/`version_info` lines in `pyvenv.cfg` | Harmless: interpreter and `pip` run normally. |
| S-7 | stdlib `venv` on the embeddable build | **Not available** (`No module named venv`). `virtualenv` is mandatory (as today). |
| S-8 | Staged/copied Python run from outside `env/` | Works: a copied embeddable tree runs `-m pip` and `-m virtualenv` from any directory -> the runner handoff (section 6.1) is feasible. |
| S-9 | Delete the base `env\python` entirely | venv **keeps working** (stdlib, `ssl`, `sqlite3`, `ctypes`, `pip`, editable imports all fine). virtualenv's `copy` mode puts `python.exe`, `python314.dll`, `python314.zip`, `libssl`, ... into `venv\Scripts` (the live venv has the same files). **The venv is self-contained.** |
| S-10 | Repair console scripts after a move | `python -m pip install --force-reinstall --no-deps <pkg>` regenerates `pytest.exe` correctly; editable packages are re-registered by `pip install -e <path> --force-reinstall --no-deps`. Needs network or a wheelhouse (`--no-index` fails with only the HTTP cache). |
| S-11 | Re-run `virtualenv` over an existing venv | **Refreshes in place**: site-packages preserved, interpreter copy and `pyvenv.cfg` (`home`, `version`) updated, `pip.exe` regenerated. Safe for same-minor refresh; a different minor needs a rebuild (ABI). |
| S-12 | Does `pyvenv.cfg home` matter? (cc.deepthink round 2; `sys._base_executable = <home>\python.exe`) | **Yes.** `home` -> existing python: `ProcessPoolExecutor`/spawn works. `home` -> **missing dir: spawn fails** (`FileNotFoundError` WinError 3). `home` -> another existing python: works, `_base_executable` follows it (child `sys.executable` stays the venv python). A stale/missing `home` is therefore a **repair trigger**, fixed by rewriting `pyvenv.cfg` (cheap, text) or by the `virtualenv` refresh. |
| S-13 | Regenerate console scripts **offline** | pip's vendored `distlib.scripts.ScriptMaker` (always present with pip) regenerated all 6 console scripts from installed `entry_points.txt` with the venv python as target; previously failing `pygmentize.exe` and `pytest.exe` ran. No network, no wheels, works for **every** installed package (not only REQUESTED). |
| S-14 | `virtualenv --no-seed` refresh | Refreshes interpreter copy + `pyvenv.cfg` (`home`) and **leaves installed packages and pip untouched** (no pip re-seed/downgrade). |
| S-4 | peerhub workspace DB paths | Only free text (`dispatch_transcripts.transcript_text`); **no structural absolute paths** -> root rename does not break a peerhub workspace. |
| S-5 | Claude path-keyed state | `.claude.json` has `projects` keyed by forward-slash absolute path (`"D:/PkgDev/workspace"`); `projects/<slug>` dir name = path with **every non-alphanumeric character replaced by `-`** (`D:\PkgDev\_sys\data\temp` -> `D--PkgDev--sys-data-temp`). Per-project entry fields include trust, MCP, session metrics. |
| S-6 | Dispatcher conventions | Pipelines are config (`dispatch.json`); failures raise `RuntimeError` -> exit 1; usage errors `sys.exit(1)`. **Only 0/1 exist today**; path/config knobs live in `_sys/config/environment.json` (`paths`, `env_vars`). New discrete exit codes are an extension and need `.bat` handling (the chain is `dispatch.bat` `exit /b %errorlevel%`). |

**Consequences (R4):** (1) the venv *interpreter* is self-contained, but `pyvenv.cfg home` must still resolve to an existing Python or spawn-based multiprocessing breaks (S-12); (2) relocation/skew repair is **in-place and offline-capable**: rewrite `pyvenv.cfg` -> (optional) `virtualenv --no-seed` refresh -> regenerate console scripts with `ScriptMaker` (S-13/S-14) -> re-register editables; no rebuild unless the probe fails or the minor differs; (3) the R2 check "`base_prefix` == `env/python`" was wrong (base_prefix is `venv\Scripts`); the right checks are `home` resolves + version skew; (4) Python replacement does not endanger a healthy venv, but a managed Python is still needed for `virtualenv`, pins, and as `home`.

---

## 2. Design principles

1. **Detect, plan, confirm, apply, verify, commit-or-rollback.** Never mutate during detection. Destructive actions are dry-run by default (`--apply` to execute), consistent with `tidy`, `peerhub backup restore`, `peerhub workspace reset`.
2. **Move, never delete, on replace.** Anything replaced is moved into the backup registry first; deletion is tidy's job after verification and a grace period.
3. **Build the new thing before touching the old thing.** Download+verify+stage first; the swap is two renames.
4. **One source of truth for "expected state"**: an environment manifest (section 3). Everything else is *observed* and compared against it.
5. **Observation is not policy.** The pinned versions in `runtimes.json` remain the policy; manifest records what was *applied*. A newer upstream version is never auto-applied outside `engram update`.
6. **Idempotent and resumable.** Every step can be re-run; an interrupted operation is detected on next start from a journal.
7. **Windows realism.** Locked files, AV scanners, `&`/`!`/`%` in paths, MAX_PATH, drive-letter changes, SUBST. Bounded retry/backoff on renames (existing pattern), no unbounded loops, final failure surfaced.
8. **Batch stays dumb.** `.bat` only ensures the pinned interpreter exists and calls Python; all branching logic lives in Python where it is testable (CONVENTION section 2).

---

## 3. Environment manifest (new)

`_sys/data/state/env.manifest.json`, schema-versioned, written atomically (temp + replace with retry), **only** after a verified successful operation:

```json
{
  "schema_version": 1,
  "engram_version": "3.5.0",
  "sys_dir_name": "_sys",
  "install_id": "uuid4, minted at first adoption/install, never reused by a copy",
  "root": {"logical": "D:\\PkgDev", "physical": "D:\\PkgDev", "volume_serial": "XXXX-XXXX"},
  "python": {"version": "3.14.8", "source_sha256": "...", "installed_at": "..."},
  "venv": {"python_version": "3.14.8", "created_at": "...",
           "baseline_packages": ["filelock","psutil","pydantic","pywinpty"],
           "last_snapshot": "backups/venv-freeze/20261002T0100Z-..."},
  "last_op": {"id": "...", "kind": "repair", "result": "committed", "at": "..."}
}
```

Purpose: (a) detect **root moved** (`manifest.root != current`), (b) detect **python/venv drift** (manifest vs `env\python\python.exe --version` vs `pyvenv.cfg`), (c) point to the latest package snapshot, (d) carry an `install_id` so *copy* and *move* can be told apart. The manifest is **not** the source of user intent: whether the context menu was enabled is derived at plan time from `register.state.json` + live HKCU keys (a stored flag goes stale after `menu disable`, review finding).

**Single writer rule:** only `repair`/`update` (under the env lock, section 9) write the manifest; `doctor` stays read-only. For existing installs without a manifest, `doctor` reports `env_manifest: adoptable`, and `repair` adopts **from evidence**, not from "current = truth".

**Previous-root evidence order** (manifest absent or stale): `pyvenv.cfg home` -> `data/state/*.state.json base_dir` -> registrar sidecars (`*.root.txt`) -> `data/last_base_dir.txt`. **Launcher fix (P0):** `launcher.py:165-182` overwrites `last_base_dir.txt` on *every* launch [V], erasing the move signal before anything reads it. It must be written only by a committed repair or a fresh install.

Root identity comparison: normalize with `os.path.normcase(os.path.realpath())`; store both logical (SUBST/`P:`) and physical roots (the registrar already writes `*.root.txt`/`*.physroot.txt` [V]). Move vs copy is decided by `install_id`, not volume serial: if the old root still exists and carries the same `install_id`, the new location is a **copy** and gets a fresh `install_id` (the old install is untouched; relocation steps that would break it, e.g. registry cleanup, are skipped); if the old root is gone it is a **move**. Volume serial is diagnostic only. Note `registrar.py:323` passes the same value for root and physical root today (review finding), so logical vs physical is not actually recorded yet; P0 records the real values.

---

## 4. Scenario matrix (complete)

`S` = scenario, columns: trigger -> detection signal -> automatic action -> user prompt? -> rollback.

### 4.1 Python

| ID | Scenario | Detection | Action | Notes |
|---|---|---|---|---|
| P1 | Python dir missing, venv present, same pinned version as the venv's interpreter | `env/python/python.exe` absent; `home` unresolvable | Install pinned Python; **rewrite `pyvenv.cfg home`/`executable`/`base-*` to it** (S-12: a missing `home` breaks spawn); venv packages untouched | No rebuild. |
| P2 | Python missing/replaced, pinned differs from the venv's interpreter only in **patch** (3.14.8 -> 3.14.9) | `venv_interpreter_skew` | After installing Python, **refresh the venv interpreter in place** (`virtualenv --no-seed`, S-14; protected by the interpreter-file backup, section 7.4); regenerate console scripts only if the stale-launcher probe says so (launchers do not embed the Python version) | Gate: probe + import checks; `pip check` is informational (consistent with 5.1). |
| P3 | Minor/major change (3.14 -> 3.15) | minor of venv interpreter != minor of `env/python`/pin | Replace Python (section 6), **rebuild venv**, restore packages (section 7) | C-extension ABI changes; packages without wheels for the new minor are reported, not fatal. Venv keeps working on the old minor until the operation commits (graceful rollback target). |
| P4 | Python present but **version != runtimes.json pin** | `bootstrap.bat` consistency check (today: hard error) | `engram update --only python` performs managed replacement; bootstrap prints the exact command instead of "remove the folder by hand" | |
| P5 | `engram update` discovers newer Python | version_resolver | Never auto-apply. `update --only python` (patch/minor needs `--yes`; major needs `--allow-major-runtime-upgrade`) | Matches existing runtime policy. |
| P6 | Python corrupted (python.exe fails / `python3NN.dll` missing / `._pth` lost `import site`) | `python -c` probe fails | Replace with `--force`; venv unaffected (S-9) | `._pth` fix re-applied by staging. |
| P7 | pip/virtualenv missing in embedded Python | `-m pip`/`-m virtualenv` probe | Reinstall via get-pip + `pip install virtualenv` during staging | Today `virtualenv` is installed ad hoc at `provisioner.py:1501` [V]. |
| P8 | Downgrade (pin lower than installed) | version compare | Same flow as P3/P4 but requires `--yes`; venv rebuilt (newer-minor venv cannot run older Python) | |
| P9 | Offline | download fails | Use a cached zip **only if** a sibling `python-<version>-embed-amd64.zip.sha256` matches; else **abort before any mutation** | No such cache exists today: `bootstrap.bat:111,114` always writes an unversioned `python-bootstrap.zip` and never hashes it (review finding). New: versioned cache name + recorded sha256, written by both bootstrap and `python_manager`. |

### 4.2 venv

| ID | Scenario | Detection | Action |
|---|---|---|---|
| V1 | venv missing | `env/venv` absent | Create; restore from newest snapshot, else baseline packages from `runtimes.json` |
| V2 | venv healthy | probe ok, versions match | Nothing (record snapshot if none or stale) |
| V3 | venv truly broken (interpreter copy missing/corrupt, `python314.dll`/zip absent, import probe fails) | health check (5.1) | Quarantine to backup registry (`venv`), rebuild, restore |
| V4 | Venv interpreter on a **different minor** than the managed Python | `venv_interpreter_skew` | Rebuild (as P3); patch skew -> in-place refresh (P2) |
| V5 | Package drift (user installed extras) | snapshot older than venv metadata mtime | Snapshot refreshed after next env-mutating op or `engram snapshots create` |
| V6 | Console-script launchers embed an absolute venv path (**S-1/S-10**) | after any root move, `pip.exe`/`<tool>.exe` fail while `python -m pip` works | **Offline regeneration via `ScriptMaker`** over *all* installed distributions' `console_scripts` and `gui_scripts` (S-13). Fallback if that fails for a package: `pip install --force-reinstall --no-deps <pkg>==<installed-version>` (never an upgrade). Last resort: report; `python -m <tool>` works only for tools with a `__main__` |
| V7 | Editable installs (`-e <path>`, e.g. peerhub) | `direct_url.json` `dir_info.editable` in `*.dist-info` [V: finder holds abs path] | Restore only if path exists (after rebasing old-root prefix to new root); else skip + report |
| V8 | A restore failure for a non-baseline package | per-package result | Continue; list failures; never abort the whole op. Baseline (T1) failure **is** fatal -> rollback |

### 4.3 Root relocation

| ID | Scenario | Notes |
|---|---|---|
| R-a | Rename the root folder, same parent | Registry key name changes (derived from parent+leaf) |
| R-b | Move to another folder, same drive | same |
| R-c | Move to another drive / drive-letter change / removable media / SUBST | Move vs copy decided by `install_id` (section 3), not volume serial; SUBST/drive-letter aliases of the same folder must not trigger relocation (compare physical roots) |
| R-d | Root contains `& ! % ^ ( )` or non-ASCII, or is long | existing `check_root_path` warns [V]; add MAX_PATH budget check before relocating (deepest known path, e.g. node_modules) |
| R-e | `_sys` also renamed | handled by existing rename design; manifest stores `sys_dir_name`; relocate re-derives |
| R-f | Install managed by WinGet (`Engram.exe` location fixed by winget) | doctor reports; relocate does not move winget-owned files |

Components impacted by R-a..R-c and the action for each:

| # | Component | Evidence | Action | Automatic? |
|---|---|---|---|---|
| 1 | venv | S-1/S-9..S-14 [V] | **In-place repair (default), ordered:** (a) rewrite `pyvenv.cfg` paths (atomic temp+replace); (b) optional interpreter refresh (`virtualenv --no-seed`) when skew/`home` demands; (c) regenerate console scripts via `ScriptMaker` (offline); (d) re-register editables. **Rebuild** only if the health probe fails or the minor differs. Launcher binary patching stays **rejected**. Engram itself uses `venv_python_exe`, not console scripts | yes |
| 2 | Editable installs | [V] finder/`.pth` hold absolute paths; `direct_url.json` marks them (S-2) | `pip install -e <rebased-path> --force-reinstall --no-deps --no-build-isolation` for each entry whose path exists after prefix rebasing (old root -> new root); needs the project's build backend already present in the venv, else report (cross-review ag.deepthink: offline editable builds can fail); missing paths skipped + reported | yes |
| 3 | Context-menu: HKCU keys, relay `.bat` in `%LOCALAPPDATA%`, `*.root.txt`/`*.physroot.txt` | [V] | **Export** affected keys first (`registry-export` backup); remove only keys whose sidecar root equals this install's **old root** (`registrar._clean_orphans` sweeps *every* install's `SandboxRun_*` entries [V], too broad for relocation); then `menu-enable` iff intent (from `register.state.json` + HKCU at plan time) says it was enabled. Copy case: skip removal | yes |
| 4 | `data/state/{install,register,menu-enable}.state.json` | [V] store `base_dir`, relay paths | Regenerate with new root after steps 1-3; keep old copies in backup registry (`state`) | yes |
| 5 | `data/last_base_dir.txt` | [V] overwritten every launch today | Written only on committed repair/fresh install (P0 launcher fix) | yes |
| 6 | Launcher env vars (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `GEMINI_DIR`, `VIRTUAL_ENV`, PATH) | [V] computed per launch | none | n/a |
| 7 | Claude path-keyed state: `.engram/claude/.claude.json` `projects` keys (forward-slash abs path) and `projects/<slug>` dirs (S-5 [V]; slug = every non-alphanumeric char -> `-`) | S-5 | **Opt-in** `--remap-ai-state`: backup the file first (restrictive ACL), rewrite only the `projects` keys under the old root (and report absolute old-root paths in per-project `mcpServers`/hook `command` entries without rewriting them), rename/copy matching slug dirs (collisions -> skip + report); skip on unknown schema; refuse while `claude.exe` runs; never touch credential-shaped files (`CREDENTIAL_SHAPED_NAMES` [V]) | no, consent |
| 8 | Codex/Agy trust lists (`config.toml [projects]`, `trustedFolders.json`) | [I]; codex config had no abs path [V]; agy file is under `%USERPROFILE%\.gemini` (outside root) | Report only | no |
| 9 | Git: `.engram/git/.gitconfig` `safe.directory`/`includeIf gitdir:` | [U] | Rebase entries under old root, backup first | yes if present |
| 10 | VS Code: workspaceStorage hashes, settings with abs paths | [I]/[U] | Report only (recent list resets) | no |
| 11 | peerhub workspaces (`.peerhub`) | S-4 [V]: no structural absolute paths (only free-text transcripts) | none | n/a |
| 12 | User-level env / PATH values containing old root (`HKCU\Environment`), Defender exclusion, shortcuts, scheduled tasks, `SUBST` mapping | [I] | Doctor reports each with the exact fix; none auto-applied (admin or user-owned) | no |

Detection order for the relocate plan: manifest root mismatch -> `last_base_dir.txt` mismatch -> `pyvenv.cfg home` mismatch -> stale registry sweep result. Any one triggers a **hint** at start (single line: `Engram root changed; run: engram repair`). The launcher **does not auto-mutate**; it only updates `last_base_dir.txt` after repair commits.

### 4.4 Combined / failure scenarios

| ID | Scenario | Handling |
|---|---|---|
| X1 | Root moved **and** Python missing | One plan: python -> venv -> registry -> state, single journal |
| X2 | Interrupted operation (power loss, Ctrl-C, crash), **including the window with no `env\python\python.exe`** | `engram.cmd`, `bootstrap.bat` and `dispatch.bat` check for a non-terminal journal *before* bootstrapping or dispatching (today `engram.cmd:173-179` blocks doctor/update when python is absent and `:144-146` routes plain `engram` to a bootstrap that would extract a fresh Python over the half-swapped tree; review finding). With a journal present they run `--resume` using the first working interpreter in order: `env\python` -> `env\python.new` -> runner copy -> backed-up python. `--rollback` is the alternative |
| X3 | Concurrent Engram processes/IDE using `env\python` or `env\venv` | Preflight lists holders via `psutil` if importable, else PowerShell `Get-CimInstance Win32_Process` image-path match. Advisory only: `provisioner._is_component_in_use` returns "not in use" when `psutil` is missing (`provisioner.py:1060-1063`, review finding; `psutil` lives in the venv, not the portable Python) and any check is TOCTOU-prone. **The rename itself is the authoritative test**; with the section 6 ordering a rename failure aborts before any irreversible step. No automatic kill; `--wait` polls |
| X4 | Rename blocked by AV/indexer | Bounded retry (5 x, 0.1 x 2^n) per CONVENTION; final failure -> rollback of completed steps |
| X5 | Low disk | Preflight: free space >= 2 x (python + venv sizes) + margin; abort before mutation |
| X6 | Package restore partially fails | V8 |
| X7 | Snapshot unreadable/corrupt | Fall back to scanning the quarantined venv's `*.dist-info` (section 7.2), then baseline only |
| X8 | Manifest corrupted/absent | Adopt/rebuild from disk; never block `doctor` |
| X9 | Verification fails after swap | Automatic rollback to the backed-up Python/venv; manifest unchanged |
| X10 | Two relocations in a row | Registry/state steps are idempotent keyed by current root |

---

## 5. Detection (doctor) - new checks

Added to `doctor.py` alongside `check_python` [V]; all read-only:

| Check | Pass condition |
|---|---|
| `env_manifest` | present, schema ok (else "adoptable") |
| `python_pin` | installed version == `runtimes.json` pin (exists today) |
| `venv_health` | probe (5.1) passes |
| `venv_python_match` | `pyvenv.cfg` `home`/version == current `env/python` |
| `root_moved` | manifest root == current root |
| `registry_stale` | no `SandboxRun_*` entries pointing at nonexistent roots for this install |
| `env_op_journal` | no non-terminal journal |
| `backups_usage` | informational: total size, count by kind, reclaimable |
| `path_keyed_state` | informational: Claude/Codex/Agy entries referencing a different root |

### 5.1 venv health probe (replaces "file exists"; corrected in R3/R4 after S-1/S-9/S-12)
1. `venv\Scripts\python.exe -c "import sys,json;print(json.dumps([list(sys.version_info[:3]),sys.prefix]))"` with a timeout; non-zero/timeout -> **broken**. The venv is self-contained, so no `env/python` dependency is checked here.
2. `sys.prefix` must equal the venv dir (normalized) - catches a venv copied as-is from elsewhere.
2b. A `ProcessPoolExecutor(1)` round trip (spawn) succeeds (S-12).
3. Import probe of baseline packages (`filelock, psutil, pydantic`; `pywinpty` imports as `winpty`).
4. `venv_interpreter_skew` (separate check): venv interpreter version vs `env/python` version vs pin -> `ok` / `patch-skew` (refresh) / `minor-skew` (rebuild).
5. `console_scripts`: for REQUESTED packages with entry points, run each launcher's `--version`/`--help`-free existence probe (launcher path embedded in trailer must point at this venv) -> `stale-launchers` (repair).
6. `pyvenv_home`: `home` must resolve to a directory containing `python.exe` (S-12) -> else **repair trigger** (rewrite `pyvenv.cfg`). `home` pointing at a *different but existing* Python -> `skew` finding.
7. `interpreter_integrity`: sha256 of the venv's interpreter file set (`python.exe`, `pythonw.exe`, `python3*.dll`, `python*.zip`, `*.pyd`, vendored DLLs in `Scripts`) vs the manifest's recorded hashes -> catches zip/pyd drift and AV quarantine that a DLL version probe misses.
8. `pip check` -> warning only.

---

## 6. Python replacement algorithm (managed, crash-consistent)

Entry: `engram update --only python [--force] [--yes]`, `repair`, and bootstrap-after-missing-python. Journal phases: `PLANNED -> STAGED -> QUARANTINED -> SWAPPED -> VENV_READY -> VERIFIED -> COMMITTED` (terminal) or `ROLLING_BACK -> ROLLED_BACK` (terminal). **COMMITTED is the single commit point** (section 9): before it only rollback is legal, after it only roll-forward.

### 6.1 Runner interpreter (cross-review blocker B1)
`dispatch.bat` runs every command on `env\python\python.exe`, and `provisioner.py:921-922` already notes a process cannot swap the interpreter it runs under [V per review]. Therefore the swap phases run in a **runner**: a copy of the *staged* Python placed at `data/state/env-op/<op-id>/runner/` (outside both swap targets). The initiating process re-execs under the runner and exits (same handoff pattern as `core_update_helper.ps1:23-29`, which waits on the parent PID). The venv is created by a short-lived child `env\python\python.exe -m virtualenv <target>` that exits before verification (stdlib `venv` does not exist on the embeddable build, S-7).

### 6.2 Steps (ordering fixed per review B5: quarantine first, install last)
1. **Preflight (no mutation):** env lock acquired; no non-terminal journal; advisory holder list (X3); disk space incl. cross-volume copies (X5); target version resolved (pin, or `--to`); zip downloaded into `data/setup-files/python-<ver>-embed-amd64.zip` and **sha256-verified** (declared hash preferred; computed-and-recorded otherwise) or offline cache per P9.
2. **Stage:** extract to `env/python.new/`; apply `._pth` `import site`; get-pip; install **a pinned `virtualenv`** (pin lives in `runtimes.json`; stdlib `venv` is unavailable, S-7; after every create/refresh assert the venv is self-contained: `python314.dll`/`python314.zip` present in `venv\Scripts`); probe `python.new\python.exe --version`. Copy to the runner dir.
3. **Pre-allocate and journal every path** (backup dirs for python/venv/freeze, runner dir) with their final timestamped names *before* any rename, so resume can always find the old copies (review B4).
4. **Snapshot packages** (healthy venv: `pip freeze --all` + REQUESTED + editable flags (+ interpreter file hashes); else metadata scan, section 7.2) into the registry (`venv-freeze`).
5. **Quarantine (reversible renames, bounded retry):** (a) if the venv will be rebuilt, move `env/venv` -> backup `venv`; (b) move `env/python` -> backup `python`. A holder failure here aborts with nothing irreversible done, and the window with no `env\python` is as short as one rename.
6. **Swap:** rename `env/python.new` -> `env/python`.
7. **Venv:** per the skew check: same version -> keep; patch skew -> in-place `virtualenv` refresh (S-11); minor skew/broken -> create at the final path and restore packages (section 7). Because the venv is self-contained, a failed venv step does **not** require reverting a good Python swap when the old venv is still intact (rollback remains available until COMMITTED).
8. **Verify:** python checks run from the new `env\python`; **venv probes run with the venv's own interpreter** (`venv\Scripts\python.exe`, section 5.1), never the base one (cross-review ag.deepthink).
9. **Commit:** append `COMMITTED` to the journal. Then, idempotently and in this order: write manifest, mark backups `committed` (start ttl clocks), update `last_base_dir`, regenerate state files. Each post-commit step is reconciled on next start via `manifest.last_op.id != journal.op_id`.
10. **Rollback (any failure before COMMITTED):** reverse order using the journaled paths; a failed new venv is **moved** to a quarantine backup, not deleted; Python is moved back; the manifest is untouched. Rollback runs from the runner (the new `env\python` may not be usable).

### 6.3 Combined plans (X1) - journal groups
One journal, two groups: **Group A = {python, venv}** atomic (all-or-rollback). **Group B = {registry, state files, git/AI-state remap}** roll-forward only and idempotent; a Group B failure never undoes a verified Group A swap (review D6). Group B runs only after Group A COMMITTED.

### 6.4 Version policy (bootstrap)
Plain `bootstrap.bat` installs **exactly** the `runtimes.json` pin. Auto-bump to "latest stable" is allowed only on a truly fresh root: none of `env\`, the manifest, or `data\state` exist (D5, strict form). Everything else upgrades only through `engram update`.

## 7. Package continuity

### 7.1 Tiers
- **T1 baseline** (Engram-required): today hard-coded in `provisioner.py:1517` [V] (`filelock, pywinpty, psutil, pydantic`) -> move to `runtimes.json` (`venv.baseline_packages`). Failure is fatal.
- **T2 user-requested**: packages with a `REQUESTED` marker in `*.dist-info` (pip writes it for explicit installs; **[V] S-2**). Restore these only; pip resolves their dependencies, avoiding stale transitive pins.
- **T3 editable**: from `direct_url.json` (`dir_info.editable == true`), restored only if the path exists after prefix rebasing.

### 7.2 Snapshot sources, in order
1. `pip freeze` from a healthy venv (also record REQUESTED + editable flags) - taken after every successful env-mutating op and on `engram snapshots create`.
2. Latest snapshot in the registry.
3. **Metadata scan of the quarantined venv**: parse `Lib/site-packages/*.dist-info/{METADATA,REQUESTED,direct_url.json}` without executing Python - works even when the interpreter is gone. [V: dist-info layout seen for peerhub/pytest; REQUESTED presence S-2]
4. Baseline only.

Snapshots strip credentials: drop URL userinfo and tokenized index/VCS URLs; no `--index-url`/`--extra-index-url` lines persisted.

### 7.3 Restore/upgrade policy
- Python replacement / venv rebuild: **T1 is installed at its pinned baseline version** (no silent upgrade; principle 5); T2 is installed from the REQUESTED set with the snapshot freeze used as a **constraints file** (`-c`), and on failure retried per package unconstrained, then reported; T3 as above.
- `engram update --only packages`: T1 `pip install --upgrade` (explicit user intent).
- `--all-packages` upgrades T2 too (opt-in; never default - user packages can break).
- Optional `--wheelhouse`: `pip download` of the snapshot into `data/cache/wheelhouse` for offline rebuild (size-capped; subject to tidy section 8).
- Result report: `data/logs/env/<op-id>.json` (restored/failed/skipped, versions before/after).

### 7.4 In-place interpreter refresh protocol (answers cc.deepthink round-2 B2)
`virtualenv` overwrites many files non-atomically, and Windows can rename a running exe but not overwrite it. So before a refresh:
1. **Lock probe:** rename-and-back `python.exe`, `pythonw.exe`, `python314.dll` (bounded retry); any holder -> abort with nothing changed.
2. **Back up the interpreter file set** (the same set hashed in 5.1 step 7, plus `pyvenv.cfg`) into the registry as kind `venv-interp`, journaled at `PLANNED`.
3. Refresh with `virtualenv --no-seed` (S-14: packages and pip untouched, so a user-upgraded pip is never downgraded); then regenerate console scripts (S-13).
4. Re-hash and record the new interpreter file set in the manifest. Stale files are removed **only if** they were in the backed-up interpreter set, their hash still equals the backed-up original, and the new build no longer ships them; any other file in `venv\Scripts` (user- or tool-added DLLs/binaries) is left in place and reported (cross-review ag.pro round 3).
5. Failure at any step -> restore the file set from the backup (rollback stays valid until COMMITTED). Known limit (cross-review ag.deepthink): manual edits inside the venv's copied stdlib zip/interpreter files are not preserved; unsupported by design.

---

## 8. Backup registry and tidy

### 8.1 Naming and layout
Namespace `_sys/data/backups/env/<kind>/<UTC-timestamp>-<label>/` with `BACKUP.json`. (User-data `engram backup` keeps its own namespace/format.) Kinds: `python`, `venv`, `venv-interp`, `venv-freeze`, `state`, `registry-export`, `ai-state`, `core-update`, `legacy-old`.

`BACKUP.json`: `{kind, created_at, engram_version, op_id, source_path, reason, size_bytes, state: pending|committed|superseded, ttl_days, min_keep, pinned, restore_hint}`. `pending` backups are **never** deleted (they are the rollback target of an in-flight journal).

### 8.2 Single producer API
New `core/backups.py`: `create(kind, source, reason, op_id, move=True) -> BackupRef`, `commit(ref)`, `list()`, `restore(ref)`, `pin/unpin`. All current producers migrate to it: `provisioner._install_atomic` (`*_old`), `updater` core-update (`staged/backup/journal` stays in temp during the op, then the backup half is registered), `layout_migration` (`.pre-merge.bak`, `Engram.exe.old`).

### 8.3 Retention policy (tidy)
Defaults (all overridable in `_sys/config` [U: exact config file]):

| Kind | min_keep | ttl_days | Notes |
|---|---|---|---|
| python | 1 | 14 | latest committed kept as rollback until ttl |
| venv | 1 | 7 | quarantined venvs are large and rebuildable |
| venv-interp | 2 | 14 | interpreter file set before a refresh |
| venv-freeze | 5 | 180 | tiny; keep several |
| state / registry-export | 3 | 60 | |
| ai-state | 3 | 30 | path-keyed AI config; strict ACL |
| core-update | 1 | 14 | |
| legacy-old | 0 | 14 | adopted `*_old` dirs |

Clocks and floors: **ttl starts at commit, not creation** (review D7); `min_keep` is an absolute floor that **overrides the size cap**; the cap never evicts the only rollback copy of the most recent operation within 72 h of its commit; cap = `min(2 GB, 10% of free space)` on constrained disks. Rules: (1) tidy removes only dirs with a valid `BACKUP.json` (marker-based ownership) or `legacy-old` adopted via `tidy --adopt-legacy`; (2) never remove `pending`, `pinned`, or anything referenced by a non-terminal journal; (3) delete oldest first but never below `min_keep` per kind; (4) soft size cap (default 2 GB): over cap -> oldest committed first, still honoring `min_keep`; (5) skip-and-report locked paths (no retry storm); (6) dry-run default, `--apply` to delete, `--only backups`, `--keep N`, `--max-size`; (7) a committed backup older than ttl is deleted **only if** the manifest's current python/venv verified healthy at last doctor; (8) never operate while the env lock is held; (9) resolve `pending` backups through the op ledger (journal terminal + manifest `last_op`); **write-ahead rule:** the `PLANNED` journal record naming the backup path/op_id is flushed *before* the backup dir or its `BACKUP.json` is created, so a crash can only leave a journaled backup or none; and a `pending` backup whose `op_id` appears in neither the manifest, nor any journal, nor an active lock, and is older than a 24 h grace period is marked `orphaned` and becomes eligible under its kind's ttl (never deleted while younger than ttl after being orphaned) (cross-review ag.pro round 3); (10) every path must resolve under `data/backups/env` and tidy never traverses reparse points (junctions/symlinks); (11) `--adopt-legacy` requires structural verification (expected files for the kind, e.g. a `*_old` dir that contains the component's own binary) in addition to the name match, and lists candidates for confirmation.

Existing allowlist-based debris cleanup in `tidy_temp.py` [V] is unchanged; `core-update` dirs under `data/temp` (currently not matched by any pattern [V]) are migrated to the registry.

### 8.4 Disk-safety and cross-volume
Moves within the same volume are renames. Cross-volume backups fall back to copy -> verify (file list + sizes + sha256 manifest) -> journal `COPIED` -> delete source, so a crash after the copy leaves a *journaled* duplicate that resume finishes, never an unmanaged one (cross-review ag.pro). Copies preserve or reject symlinks/junctions instead of flattening them; preflight estimates real on-disk size and re-checks free space between phases (TOCTOU). Backup paths longer than MAX_PATH are handled with long-path-aware APIs (`\\?\` prefix) or the op aborts in preflight (cross-review ag.deepthink). A root containing junctions is detected in preflight and not recursed through.

---

## 9. Locking and journal (crash-safe)

- **Commit point:** the journal's `COMMITTED` record is the only commit. The manifest, `BACKUP.json` states, `last_base_dir` and state files are written *after* it, idempotently (section 6.2 step 9).
- **Journal format:** append-only JSONL, one record per step transition, each with a CRC; write -> flush -> `fsync` (plain `os.replace` is not durable). Every path (including timestamped backup dirs and the runner dir) is allocated and recorded at `PLANNED` before any rename.
- **Lock:** `data/state/env-op.lock` created with exclusive create (`O_EXCL`), contents `{pid, start_time, op_id}`; stale only if the pid is dead *or* start_time differs, and a stale lock is broken atomically (rename-to-unique then delete). Because the runner handoff makes the lock-owning pid exit by design, a **non-terminal journal blocks all new mutating operations regardless of the lock**.
- **Honoring the lock:** every component that mutates the environment must check it: the `deploy` venv block (`provisioner.py:1499-1519`), `_drain_deferred_lazy`, `updater`, `registrar`, `launcher` (state writes), and `layout_migration` (which `engram.cmd:82-95` runs automatically on any command) [per review]. Enforced by a shared `env_lock.guard()` plus a static test that greps for direct mutators.
- **Entry-point gates:** `engram.cmd`, `bootstrap.bat`, `dispatch.bat` check the journal first (X2). At launch only cheap file checks run (journal present -> refuse to launch mutating flows and print the resume command; root mismatch -> one-line hint); no Python probes at launch (D8).
- **Resume/rollback:** `repair --resume` continues from the last durable record; `--rollback` undoes in reverse using journaled paths. Idempotency: every step has a precondition probe ("already done?").
- `doctor` never takes the lock and never writes. `engram snapshots restore` for `python`/`venv`/`venv-interp` kinds goes through the same lock + journal (cc.deepthink D10).

## 10. Commands and UX

| Command | Behavior |
|---|---|
| `engram doctor` | + new checks (section 5); hints, never mutates |
| `engram repair [--apply] [--yes] [--only python,venv,registry,state,ai-state] [--offline] [--resume\|--rollback]` | Builds the plan from detected drift; **dry-run by default**; one journal for the whole plan |
| `engram update --only python\|venv\|packages [--force] [--all-packages] [--allow-major-runtime-upgrade] [--yes]` | Managed replacement / upgrade (section 6/7). `--force` = replace even if versions match |
| `engram relocate [--from <old-root>]` | Plan builder front-end of `repair` (single engine); `--from` for installs with no manifest. `update --only python|venv` likewise builds its plan through `repair` |
| `engram snapshots` with `list`, `show`, `pin`, `unpin`, `restore`, `create` | Registry front-end (named `snapshots`, not `backups`, to avoid confusion with user-data `engram backup`) |
| `engram tidy --only backups [--apply] [--keep N] [--max-size GB] [--adopt-legacy]` | Section 8.3 |
| `bootstrap.bat [--skip-update]` | Ensure pinned Python only; then `dispatch install` (venv health ensured by provisioner via the same code path); prints `engram repair`/`update` hints instead of "delete the folder" |

Exit codes: a documented, discrete set for repair/update/tidy (today only 0/1 exist (S-6); proposed additions: 0 ok; 2 usage; 10 user declined/aborted; 11 preflight failed (holders/disk/offline) with **zero mutation**; 12 verification failed and rolled back; 13 rollback failed (manual action required); 14 non-terminal journal blocks the request) - numbers to be wired through `dispatcher.py` (RuntimeError -> mapped code) and `dispatch.bat`'s `exit /b %errorlevel%`; unmapped failures stay exit 1. Prompts only when stdin/stdout are attached to a TTY **and** `--interactive` is not forbidden by `CI`/`--yes`; any destructive action without `--yes` in a non-interactive context exits 11 instead of waiting; prompts have a timeout (cross-review ag.pro).

User-facing text may be Korean; all identifiers/logs/JSON English.

---

## 11. Module layout (Engram repo)

| File | Responsibility |
|---|---|
| `_sys/core/env_manifest.py` | read/adopt/write manifest, root identity comparison |
| `_sys/core/env_probe.py` | pure detection (python/venv/registry/state), returns typed findings |
| `_sys/core/env_ops.py` | plan builder, journal, lock, step runner, rollback |
| `_sys/core/python_manager.py` | stage/swap/verify Python (section 6) |
| `_sys/core/venv_manager.py` | health probe, rebuild, package snapshot/restore (section 7) |
| `_sys/core/backups.py` | registry API (section 8) |
| `_sys/core/env_lock.py` | exclusive lock, stale-break, `guard()` used by every mutator (section 9) |
| `_sys/core/relocation.py` | per-component relocate steps (section 4.3) |
| `doctor.py`, `provisioner.py`, `tidy_temp.py`, `updater.py`, `layout_migration.py`, `dispatch.json`, `engram.cmd`, `bootstrap.bat` | edited to call the above; `provisioner.py` venv block delegates to `venv_manager` |

All new code: `_sys/tests` mirrors; injectable seams (`ProcessRunner`, `FileOps` with failure injection, `RegistryOps`, `Clock`, `Downloader`) so no test touches the real registry/network.

---

## 12. Security and privacy

- Snapshots/exports exclude credentials; scrub URLs with userinfo/tokens; `ai-state` backups get restrictive ACLs and are excluded from any user-data bundle (`CREDENTIAL_SHAPED_NAMES` honored [V]).
- AI-state remap reads/writes only path-key fields; unknown schema -> skip and report; values are never logged.
- Downloads: sha256 verified before any mutation; declared hash preferred (existing policy).
- Restrictive ACLs apply to **all** backup kinds, not only `ai-state`: user files placed in `venv`/`state` trees can contain secrets (cross-review ag.pro). Backups are never uploaded or bundled by `engram backup`.
- AI-state remap is refused while the owning tool (e.g. `claude.exe`, `codex.exe`, `agy.exe`) is running.
- Registry edits limited to `HKCU\Software\Classes\...SandboxRun_*` as today; never HKLM; no elevation.

---

## 13. Spikes (executed 2026-10-02; results in section 1a)

All of S-1..S-11 were executed in a throwaway tree and are **[V]** now; none remain blocking. Residual, post-ratification checks:

| ID | Residual question | When |
|---|---|---|
| R-1 | A *real* 3.14.8 -> 3.14.9 embeddable swap and refresh (S-3/S-11/S-14 used a same-version interpreter) incl. multiprocessing child with real version skew | P3b, with the actual zip (cc.deepthink R2 asked to run this earlier; no 3.14.7 zip was fetched in this session) |
| R-2 | Editable re-registration offline when the build backend is absent from the venv | P1 |
| R-3 | Behaviour of `virtualenv` refresh when VS Code/pyright holds a venv file | P3a fault injection |
| R-4 | Whether `claude.exe` rewrites `.claude.json` on exit (race with remap) | P4 |


## 14. Acceptance test matrix (pre-TDD; tests are written after ratification)

Each row becomes a test (unit with fakes unless marked `slow` = real Windows venv/rename).

| ID | Given / When / Then |
|---|---|
| T-P1 | Python missing, venv healthy, same version -> install pinned; venv untouched (self-contained); manifest updated |
| T-P3 | Minor bump -> python backed up, venv quarantined+rebuilt, T1 restored, T2 restored/failed reported |
| T-P9 | Offline + cached zip ok -> success; offline + no cache -> exit nonzero, **zero mutation** |
| T-V3 | venv interpreter copy removed (e.g. `python314.dll` missing) -> detected broken -> quarantine+rebuild; `pyvenv.cfg home` mismatch alone -> **not** broken |
| T-V7 | Editable path under old root -> rebased and restored; nonexistent -> skipped+reported |
| T-R1 | Root renamed -> doctor reports `root_moved`, `stale-launchers`, `registry_stale`; repair dry-run lists steps; apply = in-place venv repair (no rebuild), registry export + clean + conditional re-enable, state/manifest update |
| T-R2 | Repair twice -> second run is a no-op |
| T-X2 | Kill after SWAPPED -> next start reports incomplete; `--rollback` restores original python/venv bit-for-bit (hash of file list) |
| T-X3 | A process holds a file in `env/python` -> abort with holder list, no mutation |
| T-X4 | Rename fails 3x then succeeds -> success; fails 5x -> rollback |
| T-X5 | Insufficient disk -> abort before mutation |
| T-B1 | Tidy: `pending`/`pinned`/journal-referenced never deleted; `min_keep` honored; size cap order oldest-first |
| T-B2 | Tidy dry-run default deletes nothing; `--apply` deletes only marker-bearing dirs |
| T-B3 | `legacy-old` adoption only with `--adopt-legacy`, honors ttl |
| T-S1 | Snapshot file contains no URL userinfo/tokens |
| T-M1 | No manifest + healthy install -> adopt without mutation |
| T-V0 | `pyvenv.cfg home` missing -> `pyvenv_home` fails, spawn probe fails; cfg rewrite fixes both |
| T-V5 | Offline console-script regeneration restores every launcher (REQUESTED and dependency-shipped) without network |
| T-V8 | Interpreter refresh with a held `python.exe` -> aborts before any overwrite; mid-refresh failure restores the backed-up file set |
| T-V4 | Patch skew -> in-place `virtualenv` refresh keeps site-packages; minor skew -> rebuild |
| T-V6 | After a root move, console scripts are detected stale (`stale-launchers`) and regenerated for REQUESTED packages; `python -m pip` works throughout |
| T-F1 | Fault injection: kill the process after each journaled step (PLANNED, STAGED, QUARANTINED, SWAPPED, VENV_READY, VERIFIED) -> resume and rollback both converge; original tree restored bit-for-bit (file-list hash) for rollback |
| T-F2 | Crash with no `env\python`: `bootstrap.bat`/`engram.cmd` detect the journal and resume instead of extracting a fresh Python |
| T-F3 | Crash after COMMITTED before manifest write -> next start rolls forward (manifest rewritten), never rolls back |
| T-F4 | Lock: two concurrent starters -> exactly one wins (`O_EXCL`); stale lock broken atomically; non-terminal journal blocks despite dead lock owner |
| T-B5 | Crash between a `pending` backup's creation and the `PLANNED` flush is impossible (write-ahead order test); orphaned `pending` after 24 h grace becomes ttl-eligible; younger ones never deleted |
| T-V9 | Interpreter refresh removes only stale files whose hash matches the backed-up set; a user-added DLL in `venv\Scripts` survives and is reported |
| T-F5 | Static test: no mutator (`provisioner` venv block, `updater`, `registrar`, `launcher`, `layout_migration`) runs without `env_lock.guard()` |
| T-L1 | Launcher no longer overwrites `last_base_dir.txt` on launch; first launch after a move still detects it |
| T-L2 | Copy detection: same `install_id` at old root still present -> new location gets new id, registry cleanup skipped |
| T-L3 | Registry export precedes removal; only keys whose sidecar equals the old root are removed; other installs' keys untouched |
| T-L4 | Menu intent: after `menu disable` then root move, repair does **not** re-enable the menu |
| T-W1 | Offline: versioned cache zip + matching `.sha256` used; missing/mismatched -> exit 11, zero mutation |
| T-W2 | Backup path > MAX_PATH handled (long-path API) or preflight abort; junction in root not recursed |
| T-W3 | Cross-volume backup crash after copy -> resume completes delete; no unmanaged duplicate |
| T-B4 | Tidy: pending resolved via op ledger; min_keep overrides size cap; 72 h rule; ttl from commit; reparse points not traversed |
| T-C1 | `sys_dir_name` != `_sys` -> all paths derived from manifest/`root.py`, no hardcoded `_sys` |

---

## 15. Phasing (each phase shippable; revised after review)

- **P0** (read-only + signal fixes + `env_lock.py`): `env_lock` (exclusive lock; used by every later mutator) lands here; manifest schema + `install_id`; doctor checks; **launcher stops overwriting `last_base_dir.txt`**; registrar records real logical/physical roots; `bootstrap.bat` strict no-auto-bump; versioned offline cache + sha256. No adoption writes except through `repair`.
- **P1** (strictly read-only + plain snapshot files): `venv_manager` health/`pyvenv_home`/skew/integrity/console-script probes; snapshots (freeze + metadata scan + interpreter hashes) written as plain files under `data/state/venv-freeze/` (the registry does not exist yet; P2 adopts them); baseline moved into `runtimes.json`; doctor prints the exact manual commands. **No file is modified**, so no rollback machinery is needed (cross-review ag.pro round 3).
- **P2** backup registry (`backups.py`) + `tidy --only backups` + migration of legacy `*_old` (adoption).
- **P3a** journal + entry-point gates + fault-injection harness, proven first on the lower-stakes **venv repairs**: `pyvenv.cfg` rewrite, offline console-script regeneration (moved here from P1 so a crash mid-regeneration is journaled and recoverable), interpreter refresh, rebuild (quarantine, restore, rollback).
- **P3b** Python swap with runner handoff (`python_manager`, `update --only python|venv|packages`).
- **P4** relocation (`repair`/`relocate`): registry export/clean/re-enable, state regeneration, git rebase, AI-state remap (opt-in).
- **P5** migrate remaining producers (core-update, pre-merge, `Engram.exe.old`) + docs (`user_lifecycle_guide.md`).

Rationale: detect first (no writes except plain snapshot files), then give old copies a safe home, then add crash-safety machinery and prove it on the least risky mutations (cfg rewrite, launcher regeneration), and only then the Python swap. Gate P3a/P3b on T-F1 fault injection between every rename.

## 16. Decisions (resolved in R2/R4 from cross-review rounds 1-2 and spikes)

| ID | Decision | Resolution | Source |
|---|---|---|---|
| D1 | Venv after relocation / skew | **In-place repair first** (cfg rewrite, optional `virtualenv --no-seed` refresh with file-set backup, offline `ScriptMaker` regeneration, editable re-registration); **rebuild** only when the probe fails or the minor differs; launcher binary patching rejected | spikes S-1..S-14, cc.deepthink R2 |
| D2 | REQUESTED-only vs full freeze | **REQUESTED set + freeze as constraints file (`-c`), per-package unconstrained fallback; T1 pinned** | cc.deepthink, ag.deepthink |
| D3 | Marker ownership vs patterns | **`BACKUP.json` marker + paths under `backups/env` + no reparse traversal**; legacy only via structural adoption | all |
| D4 | AI-state remap | **Opt-in**, refused while tool is running | all |
| D5 | Bootstrap auto-bump | **Only on a truly fresh root** (no `env\`, manifest, or `data\state`) | all |
| D6 | Journal scope | **One journal, groups: A={python,venv} atomic; B={registry,state,remaps} roll-forward only** | cc.deepthink |
| D7 | Retention defaults | venv 7 d, ai-state 30 d, ttl from commit, `min_keep` overrides cap, cap=min(2 GB, 10% free), 72 h rule | cc.deepthink, ag.pro |
| D8 | Where the hint is surfaced | **Launch: cheap file checks only** (journal -> refuse mutating flows; root mismatch -> one line); deep probes in doctor | cc.deepthink |

- **D9** Offline console scripts: **`ScriptMaker` offline regeneration first (S-13)**, pinned `--no-deps` reinstall as fallback, report as last resort. *(cc.deepthink R2; verified by spike.)*
- **D10** `engram snapshots` naming and `engram repair` as the single plan engine; snapshot restores of python/venv take the lock + journal. *(cc.deepthink, ag.deepthink: approved.)*

## 17. Review log

### Round 1 (2026-10-02) via `peerhub ask` (READ_ONLY, workspace = this repo)
| Reviewer | Profile | Result | Notes |
|---|---|---|---|
| cc | `cc.deepthink` | APPROVE-WITH-CHANGES | 5 blocking issues (B1 interpreter self-swap, B2 crash-window recovery, B3 single commit point, B4 journal/lock crash-safety, B5 rename order) + missing scenarios; all incorporated in R2 (sections 3, 4, 6, 9, 15) |
| ag | `ag.deepthink` | APPROVE-WITH-CHANGES | first attempt timed out (`PROCESS_TIMEOUT`, full-repo read); narrowed second attempt succeeded. Added: rename blocked by open handles (reinforces ordering), SUBST/volume-serial thrash (-> `install_id`), MAX_PATH on backup copies, junction recursion, console-script launcher internals, stdlib `venv` vs `virtualenv` (-> spike S-7) |
| ag | `ag.pro` | APPROVE-WITH-CHANGES | first attempt timed out, narrowed second succeeded. Added: size-cap vs min_keep, structural verification for `--adopt-legacy`, ACLs for all backup kinds, cross-volume copy atomicity + TOCTOU + symlink flattening, CI prompt hangs, discrete exit codes, dynamic cap |
| cx | - | **not reviewed** | usage limit reached until 2026-10-04 10:35; request a cx round before ratification |

Reviewer-reported facts the author could not independently confirm (cc.deepthink could not read the live `D:\PkgDev\_sys\env`): `psutil` only in the venv; `engram.cmd`/`bootstrap.bat`/`provisioner.py` line citations. They are marked "per review"/"review finding" and must be re-verified by spikes before TDD.

### Round 2 (R3 delta, 2026-10-02)
| Reviewer | Profile | Result | Notes |
|---|---|---|---|
| cc | `cc.deepthink` | APPROVE-WITH-CHANGES | B1 `home` is not cosmetic (-> spike S-12 confirmed it); B2 non-atomic in-place refresh (-> section 7.4 protocol, `--no-seed`, interpreter hashes, pinned virtualenv); B3 fragile console-script reinstall (-> offline `ScriptMaker`, S-13); R2-text inconsistencies fixed (6.1/6.2 venv builder, 7.1 label, P2 `pip check` gate, section 16 heading, MCP/hook paths in 4.3 row 7); D9/D10 answered |
| ag | `ag.deepthink` | APPROVE-WITH-CHANGES | AV interference (-> post-write verification + bounded retry), stdlib-zip overwrite limit (documented in 7.4), offline editable builds (-> row 2 note, R-2), virtualenv behavior drift (-> pin + self-containment assertion), P2 script-regeneration condition clarified, verify venv with the venv's own interpreter (6.2 step 8) |

Author-verified claims: S-12, S-13, S-14 were executed after the reviews and confirm the cc.deepthink/ag.deepthink concerns on `home` and the offline regeneration proposal.


### Round 3 (R4 sanity pass, 2026-10-02)
| Reviewer | Profile | Result | Notes |
|---|---|---|---|
| ag | `ag.pro` | APPROVE (minor findings) | stale-file deletion could remove user-added files (-> hash-matched, backed-up-set-only deletion, 7.4 step 4); orphaned `pending` backups when a crash precedes the `PLANNED` flush (-> write-ahead rule + 24 h orphan reaping, 8.3 rule 9); P1 should stay read-only and snapshots precede the registry (-> phasing: P1 plain snapshot files, launcher regeneration moved to P3a). No disagreement with D1-D10. |

### Open before ratification
1. `cx` cross-review of R4 (after 2026-10-04 10:35); optional round-3 sanity pass by `ag.pro` on 7.4/8.
2. Residual checks R-1..R-4 (section 13) at their phases.
3. User sign-off on D1-D10 and the P0-P5 order.
