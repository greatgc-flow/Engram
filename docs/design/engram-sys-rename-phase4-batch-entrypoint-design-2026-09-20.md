# Engram `_sys` Folder Renameability: Batch-Entrypoint Discovery & Phase 4 Design

- **Status**: DESIGN ONLY (Precondition 2 gating Phase 4 per Addendum 4 §4)
- **Author**: `ag.effort`
- **Date**: 2026-09-20
- **Target Repo**: `D:\Engram&Peerhub\engram-main-worktree` (commit `65308a9`)
- **Reference Doc**: `P:\workspace\peerhub\docs\design\engram-sys-folder-rename-feasibility-2026-09-17.md` (Addenda 1–4)
- **Preconditions**:
  1. Full green pytest suite across Phases 1–3: **SATISFIED** (405 passed, 3 skipped, 0 failed at commit `65308a9`).
  2. Concrete design note for batch-entrypoint discovery: **SATISFIED BY THIS DOCUMENT**.

---

## Executive Summary

Phases 1 through 3 centralized 65+ Python-side self-location call sites into `_sys/core/root.py` and decoupled the Python import namespace via `bootstrap_root_package()`. However, the Windows command-line surface is entered through `.cmd` and `.bat` files (`engram.cmd`, `_sys/core/bootstrap.bat`, `_sys/core/dispatch.bat`) that execute *before* Python is loaded. 

This design document conducts a complete, verified audit of all batch-entrypoint hardcodings across the codebase, evaluates discovery mechanisms (environment variable pass-through vs. filesystem heuristics), maps the interface boundary between batch discovery and the Python runtime, details the scope and verification plans for the HIGH RISK Phase 4 modules (`provisioner.py`, `setup.py`, `updater.py`, `uninstaller.py`, and test fixtures), and provides an explicit architectural recommendation on whether Phase 4 should be implemented.

---

## 1. Exhaustive Enumeration & Classification of `_sys` References in Batch Files

A complete filesystem audit was performed across all 19 `.cmd` and `.bat` files in the repository.

### Classification Criteria
- **Class A (Functional Path / Renameability Concern)**: A literal string `_sys` used as a path segment to locate, check, create, or invoke files or directories inside `_sys`. If the folder is renamed on disk, these sites fail.
- **Class B (Non-Path / Unrelated Reference)**: Comments, documentation strings, user-facing terminal messages, URLs, or unrelated identifiers. Renaming the physical folder does *not* functionally break these lines.

### Summary Table by File

| File Path | Total Lines with `_sys` | Total `_sys` Matches | Class A (Path Sites) | Class B (Comments / Messages) |
|---|:---:|:---:|:---:|:---:|
| `engram.cmd` | 29 | 33 | 33 | 0 |
| `_sys\core\bootstrap.bat` | 18 | 26 | 15 | 11 |
| `_sys\core\dispatch.bat` | 3 | 3 | 0 | 3 |
| `_sys\tests\run-tests.bat` | 3 | 3 | 2 | 1 |
| `_sys\tests\wsb-entry.bat` | 7 | 7 | 6 | 1 |
| `_sys\tests\local-test.bat` (legacy) | 29 | 29 | 29 | 0 |
| `_sys\cli\engram.cmd` | 0 | 0 | 0 | 0 |
| `_sys\start.bat` | 0 | 0 | 0 | 0 |
| `_sys\checks\*.bat` (10 files) | 0 | 0 | 0 | 0 |
| **Total** | **89** | **101** | **85** | **16** |

---

### 1.1 Detailed Audit: `engram.cmd` (Repo Root Entrypoint)
`engram.cmd` is the primary public entrypoint. It contains **29 lines** with **33 occurrences** of `_sys`. Every single occurrence is **Class A** (a literal path to find or execute components).

- **Layout Migration & State Checks (5 lines, 7 occurrences)**:
  - `Line 30`: `if exist ".\_sys\env\python\python.exe" (` [Class A]
  - `Line 31`: `if not exist ".\_sys\data\state\layout.json" (` [Class A]
  - `Line 34`: `".\_sys\env\python\python.exe" -c "import json, sys; l=json.load(open(r'.\_sys\data\state\layout.json', encoding='utf-8')); v=json.load(open(r'.\_sys\core\version.json', encoding='utf-8')).get('version', 'unknown'); sys.exit(0 if l.get('layout_version', 0) < 2 or l.get('engram_version', 'unknown') != v else 1)" 2>nul` [Class A - 3 occurrences: python.exe, layout.json, version.json]
  - `Line 39`: `call ".\_sys\core\dispatch.bat" migrate-layout` [Class A]
  - `Line 40`: `if not exist ".\_sys\data\state\layout.json" exit /b 1` [Class A]
- **Subcommand Routing & Execution (18 lines, 18 occurrences)**:
  - `Line 86`: `if not exist ".\_sys\env\python\python.exe" (` [Class A]
  - `Line 90`: `call "_sys\core\dispatch.bat" start %1 %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 94`: `if not exist ".\_sys\env\python\python.exe" (` [Class A]
  - `Line 98`: `call "_sys\core\dispatch.bat" start "%SUBCMD%" %1 %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 106`: `call "_sys\core\bootstrap.bat"` [Class A]
  - `Line 109`: `if exist "_sys\data\state\register.state.json" exit /b 0` [Class A]
  - `Line 112`: `if /i "%MENU_CHOICE%"=="y" call "_sys\core\dispatch.bat" menu-enable` [Class A]
  - `Line 116`: `if not exist ".\_sys\env\python\python.exe" (` [Class A]
  - `Line 126`: `call "_sys\core\dispatch.bat" doctor %1 %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 134`: `call "_sys\core\dispatch.bat" menu-status` [Class A]
  - `Line 138`: `call "_sys\core\dispatch.bat" menu-status %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 142`: `call "_sys\core\dispatch.bat" menu-enable %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 146`: `call "_sys\core\dispatch.bat" menu-disable %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 150`: `call "_sys\core\dispatch.bat" menu-clean %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 160`: `call "_sys\core\dispatch.bat" tidy %1 %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 164`: `call "_sys\core\dispatch.bat" update %1 %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 170`: `call "_sys\core\dispatch.bat" uninstall %1 %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 176`: `call "_sys\core\dispatch.bat" backup %1 %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 182`: `call "_sys\core\dispatch.bat" restore %1 %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
  - `Line 188`: `call "_sys\core\dispatch.bat" reset %1 %2 %3 %4 %5 %6 %7 %8 %9` [Class A]
- **Version Query Handlers (4 lines, 5 occurrences)**:
  - `Line 228`: `if exist "_sys\core\version.json" (` [Class A]
  - `Line 229`: `if exist ".\_sys\env\python\python.exe" (` [Class A]
  - `Line 230`: `for /f "usebackq delims=" %%v in ('... .\_sys\env\python\python.exe ... open(r'_sys\core\version.json' ...)` [Class A - 2 occurrences]
  - `Line 235`: `for /f "usebackq delims=" %%v in ('... Get-Content '_sys\core\version.json' ...)` [Class A]

---

### 1.2 Detailed Audit: `_sys\core\bootstrap.bat` (Python Bootstrapper)
`_sys\core\bootstrap.bat` contains **18 lines** with **26 occurrences** of `_sys`.
Crucially, at `Line 18`, `bootstrap.bat` executes `cd /d "%~dp0..\.."`, which switches the working directory to the portable root. Consequently, all subsequent commands use paths relative to the portable root that hardcode `_sys`.

- **Class A (Functional Path Sites — 10 lines, 15 occurrences)**:
  - `Line 28`: `if not exist "_sys\runtimes.json" copy /y "_sys\defaults\runtimes.json" "_sys\runtimes.json" >nul` (3 occurrences: target, source default, copy destination)
  - `Line 29`: `if not exist "_sys\tool-catalog.v1.json" copy /y "_sys\defaults\tool-catalog.v1.json" "_sys\tool-catalog.v1.json" >nul` (3 occurrences: target, source default, copy destination)
  - `Line 32`: `set "_RT=_sys\runtimes.json"` (1 occurrence: runtime configuration pointer)
  - `Line 42`: `set "PY_DIR=_sys\env\python"` (1 occurrence: Python destination directory)
  - `Line 105`: `if not exist "_sys\data\setup-files" mkdir "_sys\data\setup-files"` (2 occurrences: directory creation)
  - `Line 107`: `set "ZIP_PATH=_sys\data\setup-files\python-bootstrap.zip"` (1 occurrence: bootstrap zip destination)
  - `Line 133`: `curl -L "!GET_PIP_URL!" -o "_sys\data\setup-files\get-pip.py"` (1 occurrence: get-pip target)
  - `Line 134`: `"%PY_EXE%" "_sys\data\setup-files\get-pip.py" --no-warn-script-location` (1 occurrence: get-pip execution)
  - `Line 161`: `"$log='_sys\data\logs\runtimes_drift.jsonl'..."` (1 occurrence: PowerShell logging path)
  - `Line 165`: `call "_sys\core\dispatch.bat" install %* || ...` (1 occurrence: delegation to dispatch pipeline)
- **Class B (Comments & User Messages — 8 lines, 11 occurrences)**:
  - `Line 21`: `:: _sys/core/bootstrap.bat - Portable Dev Environment Bootstrapper` (Comment)
  - `Line 23`: `:: Bootstraps minimal Python, then delegates to _sys\core\setup.py.` (Comment)
  - `Line 24`: `:: Runtime versions/URLs sourced from _sys\runtimes.json (no hardcoding).` (Comment)
  - `Line 31`: `:: -- Runtime config from _sys\runtimes.json (fallback if missing) --` (Comment)
  - `Line 54`: `echo [Error] Could not read the installed Python version from _sys\env\python\python.exe.` (User error message)
  - `Line 61`: `echo Close portable tools, remove _sys\env\python, then rerun _sys/core/bootstrap.bat.` (User recovery message, 2 occurrences)
  - `Line 80`: `echo [i] To upgrade, close portable tools, remove _sys\env\python, then rerun _sys/core/bootstrap.bat.` (User upgrade message, 2 occurrences)
  - `Line 156`: `if exist "%PY_EXE%" echo [Error] Python rollback was incomplete; remove _sys\env\python manually.` (User error message)

---

### 1.3 Detailed Audit: `_sys\core\dispatch.bat`
`_sys\core\dispatch.bat` contains **3 lines** matching `_sys`.
- `Line 5`: `set "SYS_DIR=%~dp0.."` (Dynamic self-location relative to `%~dp0`, containing **zero** literal `_sys` strings!)
- `Line 12`: `:: _sys/core/bootstrap.bat logic will be triggered if we just call it` [Class B - Comment]
- `Line 14`: `:: For now, we'll let the root _sys/core/bootstrap.bat handle the initial bootstrap.` [Class B - Comment]
- `Line 18`: `echo Please run _sys/core/bootstrap.bat first.` [Class B - User error message]
- **Finding**: `_sys\core\dispatch.bat` has **0 Class A references**. It is already structurally rename-safe because it computes `SYS_DIR` dynamically from its own location.

---

### 1.4 Detailed Audit: Other Batch Files
- `_sys\tests\run-tests.bat`:
  - `Line 6`: Comment [Class B].
  - `Line 29`: `set "SYS_DIR=%PORTABLE_ROOT%\_sys"` [Class A].
  - `Line 30`: `set "PATH=%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PATH%"` [Class A].
- `_sys\tests\wsb-entry.bat` (Windows Sandbox runner):
  - `Line 16`: Echo message [Class B].
  - `Lines 20, 29, 34, 39, 48, 53`: Hardcodes `%TGT%\_sys\...` [Class A - 6 occurrences].
- `_sys\tests\local-test.bat` (Legacy test runner):
  - `Lines 29, 45–55, 60–70, 75–80`: Hardcodes `%PD%\_sys\...` [Class A - 29 occurrences].
- `_sys\cli\engram.cmd`:
  - `Line 1`: `@call "%~dp0..\..\engram.cmd" %*` (Zero `_sys` references; walks up 2 levels to root).
- `_sys\start.bat`:
  - `Line 3`: `call "core\dispatch.bat" start %*` (Zero `_sys` references; calls sibling in `core`).
- `_sys\checks\*.bat` (10 batch scripts):
  - Every script in `_sys/checks/` (`check-health.bat`, `check-deps.bat`, etc.) contains:
    `set "SYS_DIR=%~dp0.."`
    `"%SYS_DIR%\env\venv\Scripts\python.exe" ...`
    All 10 scripts have **0 Class A references** and are already dynamically localized.

---

## 2. Proposed Batch-File Discovery Mechanism

### 2.1 The Asymmetry of Discovery
The audit reveals an essential structural asymmetry:
1. **Scripts inside the system directory** (`dispatch.bat`, `start.bat`, `checks\*.bat`):
   These scripts are located inside `<sys_dir>` (or `<sys_dir>\core` or `<sys_dir>\checks`). They already resolve `<sys_dir>` dynamically using `%~dp0..` without needing to know their folder's name.
2. **Scripts outside the system directory** (`engram.cmd` at repo root):
   `engram.cmd` resides at the portable root (`%~dp0`). `<sys_dir>` is a *child* directory. A parent cannot discover an arbitrarily renamed child directory without either:
   - An explicit configuration/environment variable, or
   - An inspection/probing heuristic.

### 2.2 Concrete Design: The 3-Tier Discovery Contract

To achieve full renameability in batch entrypoints without compromising speed or introducing fragile command-line edge cases, `engram.cmd` must implement a **3-tier discovery hierarchy** at its very top (before any subcommands or checks execute):

```cmd
:: ============================================================================
:: Discovery Hierarchy for Engram System Directory
:: ============================================================================
set "ENGRAM_SYS_DIR_NAME="

:: Tier 1: Explicit caller override via environment variable
if defined ENGRAM_SYS_DIR (
    if exist "%~dp0%ENGRAM_SYS_DIR%\core\dispatch.bat" (
        set "ENGRAM_SYS_DIR_NAME=%ENGRAM_SYS_DIR%"
        goto :sys_dir_resolved
    )
    if exist "%ENGRAM_SYS_DIR%\core\dispatch.bat" (
        set "ENGRAM_SYS_DIR_NAME=%ENGRAM_SYS_DIR%"
        goto :sys_dir_resolved
    )
)

:: Tier 2: Zero-cost fast path for standard installations
if exist "%~dp0_sys\core\dispatch.bat" (
    set "ENGRAM_SYS_DIR_NAME=_sys"
    goto :sys_dir_resolved
)

:: Tier 3: Probe immediate subdirectories for the core dispatch anchor
for /d %%D in ("%~dp0*") do (
    if exist "%%D\core\dispatch.bat" (
        set "ENGRAM_SYS_DIR_NAME=%%~nxD"
        goto :sys_dir_resolved
    )
)

:: Failure fallback: Anchor missing
echo [Error] Engram system directory not found under "%~dp0".
echo         Expected a directory containing core\dispatch.bat.
exit /b 1

:sys_dir_resolved
set "ENGRAM_SYS_DIR=%ENGRAM_SYS_DIR_NAME%"
set "SYS_PATH=%~dp0%ENGRAM_SYS_DIR%"
```

### 2.3 Downstream Propagation into `engram.cmd`
Once `SYS_PATH` and `ENGRAM_SYS_DIR` are established:
1. Every occurrence of `.\_sys\...` or `_sys\...` in `engram.cmd` (all 33 Class A sites) is replaced by `"%SYS_PATH%\..."`:
   - `"%SYS_PATH%\env\python\python.exe"`
   - `"%SYS_PATH%\data\state\layout.json"`
   - `call "%SYS_PATH%\core\dispatch.bat"`
   - `call "%SYS_PATH%\core\bootstrap.bat"`
2. Because `call` preserves the environment within `engram.cmd`'s execution scope (`setlocal DisableDelayedExpansion`), `ENGRAM_SYS_DIR` is automatically inherited by any child `.bat` script.

### 2.4 Downstream Propagation into `_sys\core\bootstrap.bat`
In `_sys\core\bootstrap.bat`:
1. Capture `SYS_DIR` **before** switching directories on Line 18:
   ```cmd
   if not defined ENGRAM_SYS_DIR (
       for %%I in ("%~dp0..") do set "ENGRAM_SYS_DIR=%%~nxI"
   )
   cd /d "%~dp0..\.."
   set "SYS_DIR=%ENGRAM_SYS_DIR%"
   ```
2. Replace all 10 Class A lines in `bootstrap.bat` (Lines 28, 29, 32, 42, 105, 107, 133, 134, 161, 165) with paths prefixed by `!SYS_DIR!\` instead of literal `_sys\`.
3. This guarantees that `bootstrap.bat` runs identically whether called via `engram.cmd` (where `ENGRAM_SYS_DIR` is inherited) or run directly by an administrator/developer (where `bootstrap.bat` discovers its parent folder name via `%~dp0..`).

### 2.5 Resolution of the "Chicken-and-Egg" Fresh Install Case
**The Concern**: On a fresh git clone or freshly extracted release zip, Python is not yet installed (`_sys\env\python\python.exe` does not exist), data folders do not exist, and tools are unprovisioned. Does the discovery heuristic fail?

**The Reality**:
- The discovery anchor is `%~dp0<candidate>\core\dispatch.bat`.
- `core\dispatch.bat` is a tracked, static repository file that is **always present** in both source checkouts and release zips from day zero.
- It does **not** depend on Python, venv, or generated state.
- Therefore, when a user clones or extracts Engram, renames `_sys` to `my_runtime`, and executes `engram`:
  1. Tier 1 / Tier 2 miss.
  2. Tier 3 scans `%~dp0*`, finds `my_runtime\core\dispatch.bat`, and sets `ENGRAM_SYS_DIR=my_runtime`.
  3. `engram.cmd` checks `if not exist "%SYS_PATH%\env\python\python.exe"`.
  4. Python is absent, so `engram.cmd` invokes `:do_first_run`, which calls `"%SYS_PATH%\core\bootstrap.bat"`.
  5. `bootstrap.bat` downloads and extracts Python into `my_runtime\env\python`, installs pip into `my_runtime\data\setup-files`, and hands off to `"%SYS_PATH%\core\dispatch.bat" install`.
  6. The initial bootstrap succeeds completely without a chicken-and-egg failure.

---

## 3. Cross-Reference: Batch Discovery vs. Python Bootstrap Boundary

The batch-file discovery mechanism and the Python-side bootstrap (`root.py`) operate at different architectural layers. They solve separate problems and do not conflate responsibilities:

```
[User / CLI Invocations: engram.cmd]
         |
         | (Layer 0: Batch Discovery - OS / Filesystem)
         | Discovers on-disk folder name ('_sys' or 'my_runtime')
         | Exports ENGRAM_SYS_DIR / Sets SYS_PATH
         v
[Batch Execution: _sys/core/dispatch.bat]
         |
         | Launches: "%SYS_DIR%\env\python\python.exe" "%SYS_DIR%\core\dispatcher.py"
         v
[Python Process Startup: dispatcher.py]
         |
         | (Layer 1: Python Import-Namespace Registration)
         | sys_dir = Path(__file__).parent.parent.resolve()
         | bootstrap_root_package(sys_dir, stable_name="_sys")
         |   -> Registers sys_dir in sys.modules["_sys"]
         |
         | (Layer 1.5: Python Filesystem Self-Location)
         | find_root(__file__) -> Walks upward to find root.py / sys_dir
         v
[Python Subsystems: provisioner, updater, uninstaller]
```

### 3.1 Distinct Responsibilities
1. **Batch Discovery (Layer 0)**:
   - **Problem**: Locating `python.exe` and `dispatcher.py` to start the Python process.
   - **Environment**: Windows `cmd.exe`.
   - **Mechanism**: Environment variable `ENGRAM_SYS_DIR` + filesystem probing for `core\dispatch.bat`.
2. **Python Import Registration (Layer 1)**:
   - **Problem**: Allowing Python modules to execute `from _sys.core import ...` without renaming 24 import lines across 12 files.
   - **Environment**: Python runtime (`sys.modules`, `importlib.machinery.ModuleSpec`).
   - **Mechanism**: `root.bootstrap_root_package(actual_root)`.
3. **Python Filesystem Self-Location (Layer 1.5)**:
   - **Problem**: Allowing Python modules to locate configuration, state, and tool directories.
   - **Environment**: Python runtime (`pathlib.Path`).
   - **Mechanism**: `root.find_root(__file__)`.

### 3.2 Handoff & Independence
- Python does **not** require `ENGRAM_SYS_DIR` to be passed to it: any Python script located inside `<sys_dir>` (such as `dispatcher.py`, `version_resolver.py`, `tidy_temp.py`) already locates itself via `Path(__file__).resolve().parent.parent`.
- However, if `ENGRAM_SYS_DIR` is set in `os.environ`, it can serve as a non-breaking hint.
- **Identified Gap in Dispatcher Hand-Off**:
  In `_sys/core/dispatcher.py`:
  - `Line 32`: `config_path = base_dir / "_sys" / "config" / "environment.json"`
  - `Line 41`: `resolved["sys"] = base_dir / "_sys"`
  - In `_sys/config/environment.json`:
    `Line 4`: `"sys": "{base}/_sys"`
  Even though Phase 3 converted `dispatcher.py`'s self-location, `_resolve_paths()` still hardcodes `base_dir / "_sys"` when loading `environment.json`. If `_sys` is renamed on disk, `EnvironmentLoader` will construct broken paths for `{sys}/data`, `{sys}/tools`, etc.
  - **Required Fix**: `dispatcher.py` must pass `sys_dir` directly to `_resolve_paths()` and override `resolved["sys"] = sys_dir`.

---

## 4. Phase 4 Scope & Verification Plan

Phase 4 touches the HIGH RISK core lifecycle modules: `provisioner.py`, `setup.py`, `updater.py`, `uninstaller.py`, and test fixtures.

### 4.1 Module-by-Module Scope

#### A. `_sys/core/setup.py` (Risk: LOW-MEDIUM)
*Role*: Legacy backward-compatibility entrypoint. Modern entrypoints route through `dispatch.bat -> dispatcher.py -> core.provisioner.deploy`.
- **Existing Code**:
  - `Lines 9–11`: `_sys = Path(__file__).parent.parent.resolve()`; `sys.path.insert(0, str(_sys))`
  - `Lines 19–26`: `_base = _sys.parent`; sets `ctx["sys_dir"] = _sys`
- **Required Changes**:
  - Replace Lines 9–11 with canonical Phase 1 bootstrap:
    ```python
    _SYS_DIR = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_SYS_DIR / "core"))
    from root import bootstrap_root_package  # noqa: E402
    bootstrap_root_package(_SYS_DIR)
    ```
  - Standardize `ctx["sys_dir"]` to `_SYS_DIR` and `ctx["base_dir"]` to `_SYS_DIR.parent`.

#### B. `_sys/core/provisioner.py` (Risk: HIGH)
*Role*: Tool installation, runtime verification, canary execution, and deploy pipeline.
- **Existing Code**:
  - `Lines 237–238`:
    ```python
    def _default_sys_dir() -> Path:
        return Path(__file__).resolve().parent.parent
    ```
  - `Lines 552–559` (in `_run_canary_logged`):
    ```python
    curr = tmp_dir.resolve()
    sys_dir = curr
    while curr.name != "_sys" and curr.parent != curr:
        curr = curr.parent
    if curr.name == "_sys":
        sys_dir = curr
    else:
        sys_dir = tmp_dir.parent.parent
    ```
  - `Lines 1440–1444` (in `__main__` standalone deploy):
    ```python
    _sys = Path(__file__).parent.parent.resolve()
    ctx = { "base_dir": _sys.parent, "sys_dir": _sys, ... }
    ```
- **Required Changes**:
  - In `_default_sys_dir()`: delegate to `root.find_root(__file__)`.
  - In `_run_canary_logged()`: replace the hardcoded `while curr.name != "_sys"` directory crawl with `sys_dir = find_root(tmp_dir)`.
  - In `__main__`: insert `bootstrap_root_package(_sys)` before executing `deploy(ctx)`.

#### C. `_sys/core/updater.py` & `core_update_helper.ps1` (Risk: CRITICAL)
*Role*: Tool updates, runtime updates, and core self-update orchestration.
- **Existing Code**:
  - `Lines 15–16`:
    ```python
    _PORTABLE_ROOT = Path(__file__).resolve().parent.parent.parent
    _SYS_DIR = _PORTABLE_ROOT / "_sys"
    ```
    *(Severe Bug: re-appends literal `"_sys"` to `_PORTABLE_ROOT`, breaking immediately if renamed!)*
  - `Lines 353, 377`: `staged_dir / "_sys" / "core" / "version.json"`
  - `Lines 367–368`: `protected = [".engram", "workspace", "_sys/env", "_sys/tools", ...]`
  - `Lines 396–405`: Passes `target_dir` (`_PORTABLE_ROOT`) and `staged_dir` to `core_update_helper.ps1`.
  - `core_update_helper.ps1` `Line 51`:
    `Copy-Item -Path "$StagedDir\*" -Destination $TargetDir -Recurse -Force`
- **Architectural Mismatch in Core Update**:
  Per Addendum 3, official release zip packages internally contain a folder literally named `_sys`. If a user has renamed their local installation folder to `my_sys`:
  1. `updater.py` extracts the update zip into `staged_dir`. Inside `staged_dir`, the folder is named `_sys`.
  2. `core_update_helper.ps1` executes `Copy-Item -Path "$StagedDir\*" -Destination $TargetDir`.
  3. PowerShell copies `$StagedDir\_sys` into `$TargetDir\_sys`!
  4. Result: The user's active `my_sys` is **not updated**, and a redundant, untracked `_sys` directory is created in their installation root, corrupting the layout!
- **Required Changes**:
  - Fix Lines 15–16 in `updater.py` to derive `_SYS_DIR = Path(__file__).resolve().parent.parent`, `_PORTABLE_ROOT = _SYS_DIR.parent`, and call `bootstrap_root_package(_SYS_DIR)`.
  - In `updater.py`: make `protected` list dynamic: replace `"_sys/env"` with `f"{_SYS_DIR.name}/env"`, etc.
  - In `core_update_helper.ps1` & `updater.py`: pass `sys_dir_name` in `plan.json`. If `sys_dir_name != "_sys"`, the helper must map staged `_sys` content to the actual target directory name (`my_sys`), rather than doing a blind root-level copy.

#### D. `_sys/core/uninstaller.py` & `_sys/core/layout.py` (Risk: CRITICAL)
*Role*: Allowlist-based cleanup and full installation purge.
- **Existing Code**:
  - `uninstaller.py` `Line 105`:
    ```python
    if name_lower == "_sys":
        continue  # Handled in detail under _sys
    ```
  - `uninstaller.py` `Line 179`:
    `sys_dir = ctx.get("sys_dir", base_dir / "_sys")`
  - `layout.py` `Line 10`:
    `INSTALL_ROOT_ENTRIES = { ..., "_sys", ... }`
- **Hazard Analysis**:
  If the folder is renamed to `my_sys` and `uninstaller.py` runs:
  1. When scanning `base_dir`, `entry.name.lower()` is `my_sys`.
  2. It does not match `"_sys"` on Line 105.
  3. It does not match `INSTALL_ROOT_ENTRIES` (which hardcodes `"_sys"`).
  4. It falls through to `plan.items_to_keep.append((entry_path, "user-authored or external item"))`!
  5. The uninstaller completely refuses to touch the renamed system folder, leaving the entire installation on disk!
  6. Conversely, if `my_sys` was in `INSTALL_ROOT_ENTRIES`, it would delete `my_sys` wholesale without preserving `local.config.bat` or scanning internal program entries.
- **Required Changes**:
  - In `uninstaller.py` `Line 105`: change to `if name_lower == sys_dir.name.lower(): continue`.
  - In `uninstaller.py` `Line 179`: change fallback to `find_root(__file__)`.
  - In `core/layout.py`: make `INSTALL_ROOT_ENTRIES` a function or set that includes `find_root().name`.

#### E. `_sys/tests/unit/conftest.py` & Test Fixtures (Risk: LOW)
- **Status in `conftest.py`**:
  As ratified in Addendum 4 §3, `conftest.py` was **already migrated in Phase 1a** (commit `dec8df1`). Lines 12–18 already contain `bootstrap_root_package(_SYS_DIR)`.
- **Unit Test Fixture Paths**:
  Unit tests such as `test_uninstall_semantics.py` construct realistic synthetic fixtures using `tmp_path / "engram_test_inst" / "_sys"`. These tests verify behavior under standard naming.
  - If dynamic renameability is tested, new parameterized test fixtures should be added under `_sys/tests/unit/test_renamed_sys_lifecycle.py` rather than altering existing test fixtures.

---

### 4.2 Safest Execution Ordering & Verification Strategy

If Phase 4 is executed, changes must be introduced in strict order of increasing risk, with complete test suite runs at each milestone:

```
[Step 1: Low Risk]
  _sys/core/setup.py
    -> Verification: python setup.py --help; dry-run deploy
         |
         v
[Step 2: Medium Risk]
  _sys/core/provisioner.py (_default_sys_dir & canary crawl)
    -> Verification: pytest test_provisioner_*.py (4 test files)
         |
         v
[Step 3: High Risk - Layout & Allowlist]
  _sys/core/layout.py & _sys/core/uninstaller.py
    -> Verification: pytest test_uninstall_semantics.py (100% pass)
         |
         v
[Step 4: Critical Risk - Update Pipeline & Staging Helper]
  _sys/core/updater.py & core_update_helper.ps1
    -> Verification: pytest test_updater.py test_core_update_helper.py
         |
         v
[Step 5: Shell Entrypoints]
  engram.cmd & _sys/core/bootstrap.bat
    -> Verification: Clean checkout test, custom-name sandbox test
```

---

## 5. Architectural Evaluation & Recommendation

### Question: Is Phase 4 worth implementing, or should the project stop at Phase 1–3?

### 5.1 Risk vs. Benefit Analysis

| Dimension | Phase 1–3 (Current State) | Phase 4 (Proposed Implementation) |
|---|---|---|
| **Python Code Coupling** | **Zero coupling**: Centralized into `root.py`; PEP 420 virtual namespace `_sys` dynamically points to actual disk path. | Identical to Phase 1–3. |
| **Batch Entrypoints** | Standard `_sys` path hardcoded in `engram.cmd` and `bootstrap.bat`. | Dynamic discovery via env var and child folder crawl in `engram.cmd`. |
| **Self-Update Risk** | **Zero risk**: `core_update_helper.ps1` updates `_sys` cleanly. | **HIGH RISK**: Requires path re-mapping from release zip's `_sys` to renamed directory. A bug bricks the self-updater. |
| **Uninstall Risk** | **Zero risk**: Tested allowlist cleans `_sys` while preserving user data. | **HIGH RISK**: Requires dynamic root entry matching. A bug risks either leaving orphaned files or corrupting user data. |
| **Batch Fragility** | Simple, robust, proven cmd.exe commands. | Complex cmd.exe loops with variable expansion and folder probing. |
| **User Demand** | Satisfies all current requirements. | **Zero user requests**: No user has requested renaming `_sys`. |

### 5.2 Key Technical Insights
1. **The Packaging Wall (Addendum 3 & Section 4.1.C)**:
   Engram's binary distribution pipeline (`build_package.py`) packages the product with internal zip path `_sys/...`. If an end-user renames their local folder to `_sys_custom`, applying an official update from GitHub or WinGet via `engram update` extracts `_sys` from the zip. The update helper either duplicates the folder or requires custom translation logic inside a detached PowerShell process.
2. **Batch Script Fragility**:
   Windows `cmd.exe` does not handle complex path indirection, quotes, and metacharacters cleanly. Probing subdirectories on every invocation of `engram.cmd` introduces startup latency and fragility for an edge case that no user needs.
3. **Phases 1–3 Already Delivered the Real Value**:
   The primary goal of this entire effort was eliminating copy-pasted `Path(__file__).resolve().parent.parent` boilerplate across 65+ Python files and making future repository refactorings clean. Phases 1–3 achieved this completely with a 405-test green baseline.

### 5.3 Explicit Recommendation: **STOP AT PHASES 1–3**

> [!IMPORTANT]
> **Recommendation**: **DO NOT IMPLEMENT PHASE 4.**
> 
> The project should treat Phase 1–3 as the permanent, stable architecture:
> 1. Keep `_sys` as the canonical, fixed directory name on disk for Windows batch entrypoints and packaged releases.
> 2. Keep the Python-side dynamic namespace bootstrap (`root.bootstrap_root_package`) and centralized self-location (`root.find_root`) active.
> 3. Preserve this document as the authoritative architectural reference explaining why batch-level dynamic renameability is technically viable but economically and operationally unjustified by its risk profile.
