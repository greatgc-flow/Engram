# Portable Dev Environment — Coding Conventions

All source code and scripts in this repository must comply with the rules in this document.

---

## 1. Language Policy (CRITICAL)

- **Internal Source & Artifacts**: All code, JSON artifacts, configuration files, comments, commit messages, and system documentation MUST be in **English only**.
- **User-Facing Output Exception**: User-facing console output (e.g. interactive PowerShell / console prompts delivered directly to the human user) MAY be in Korean.
- **Rationale**: Preserves token efficiency across developer tooling and prevents encoding/parser defects across multi-byte environments.

---

## 2. Batch File (.bat) Rules

### 2.1 Language and Encoding (CRITICAL)
- **Language**: English only for all echo statements, variable names, comments, and paths.
- **Encoding**: Must maintain **UTF-8 (No BOM)** format.
  - Reason: Prevents the `cmd.exe` bug where the first command (`setlocal`) is misinterpreted as `tlocal` due to a byte-order mark.
- **Absolute Prohibition of Korean Strings in .bat**: Even with `chcp 65001`, the `cmd.exe` parser treats multi-byte characters as token delimiters, breaking script execution.
- **No chcp in .bat**: The `chcp` command is prohibited within `.bat` files (use PowerShell `.ps1` if code page switching is required).

### 2.2 PATH Integration
Use individual `if exist` statements. Never expand `%PATH%` inside a parenthesized `for` loop block (in `cmd.exe`, `%PATH%` inside a block expands only once at parse time):
```bat
:: Correct pattern — individual if exist lines
if exist "%TOOLS_DIR%\ripgrep"  set "PATH=%TOOLS_DIR%\ripgrep;%PATH%"
if exist "%TOOLS_DIR%\fd"       set "PATH=%TOOLS_DIR%\fd;%PATH%"

:: Forbidden pattern — %PATH% expansion inside for-loop block
for %%T in (ripgrep fd) do (
    if exist "%TOOLS_DIR%\%%T" set "PATH=%TOOLS_DIR%\%%T;%PATH%"
)
```

### 2.3 Log Function Pattern
All batch output should be recorded simultaneously to file and console via a standard `:LOG` subroutine:
```bat
:LOG
echo %~1
>> "%LOG_FILE%" echo %~1
exit /b 0
```

### 2.4 Timestamps
Use PowerShell `Get-Date` rather than `wmic` (which is deprecated and removed in Windows 11 24H2+):
```bat
for /f "delims=" %%I in (
    'powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"'
) do set "_DT=%%I"
set "LOG_FILE=%LOG_DIR%\start_%_DT:~0,8%_%_DT:~8,6%.log"
```

### 2.5 Path and Special Character Handling (Parenthesis Bug Prevention)
If a path contains parentheses `(` or `)`, expanding `%VAR%` inside an `if (...)` or `for (...)` block will prematurely close the block and crash `cmd.exe`.
- **Avoid Blocks**: Prefer single-line `if condition command` statements.
- **Use Delayed Expansion**: Declare `setlocal EnableDelayedExpansion` and expand variables as `!VAR!`.
- **Safe Conditional Assignment**:
```bat
:: Safe single-line pattern
if not defined BASE_DIR for %%I in ("%~dp0..\..") do set "BASE_DIR=%%~fI"
set "_BASE=%BASE_DIR%"
```

---

## 3. Host Integration & Registry Commands

### 3.1 Registry Command Quoting
- Always wrap registry commands with double quotes: `cmd.exe /c ""<physical_path>\_sys\cli\launch.bat" "%V.""`.
- **Trailing Backslash Escape Fix (CRITICAL)**:
  - Windows passes directory targets (such as `P:\`) with a trailing backslash. In a command like `"%V"`, this becomes `"P:\"`, escaping the closing quote and corrupting arguments.
  - Always append a dot to the argument: `"%V."`.
  - In receiving batch scripts, normalize incoming paths to remove the trailing dot:
    ```bat
    for %%I in ("%~1") do set "TARGET=%%~fI"
    ```

### 3.2 Dispatch Pattern
Root-level batch files (`register.bat`, `unregister.bat`, `INSTALL.bat`, `CLEANUP.bat`) must remain minimal harnesses that delegate execution logic to Python modules under `_sys/core/` or `_sys/cli/`.

---

## 4. Environment Variable Isolation Rules

### 4.1 System Variable Override Prohibition
Never override host-critical user profile variables in system scripts:
```
USERPROFILE    ← Absolute prohibition of override
APPDATA        ← Absolute prohibition of override
LOCALAPPDATA   ← Absolute prohibition of override
```

### 4.2 Dedicated Tool Caches
Each portable tool must isolate its cache and runtime data inside `%ENV_DIR%` or `%DATA_DIR%`:
```bat
set "NPM_CONFIG_PREFIX=%ENV_DIR%\nodejs\npm-global"
set "NPM_CONFIG_CACHE=%ENV_DIR%\nodejs\npm-cache"
set "PIP_CACHE_DIR=%ENV_DIR%\python\pip-cache"
set "PYTHONUSERBASE=%ENV_DIR%\python\userbase"
set "BAT_CACHE_PATH=%TOOLS_DIR%\bat\cache"
set "TEMP=%DATA_DIR%\temp"
set "TMP=%DATA_DIR%\temp"
```

### 4.3 Prohibition of Hardcoded Paths
Do not use literal drive letters (`C:\`, `D:\`). All paths must be dynamically resolved relative to `%BASE_DIR%` or `%SYS_DIR%`.

### 4.4 Robust JSON Parsing in Shell Scripts
When parsing large or untrusted JSON files from PowerShell, avoid `ConvertFrom-Json` (which can fail on encoding anomalies or malformed blocks). Use regex property matching (`Select-String`) for lightweight existence checks.

---

## 5. File and Directory Naming Rules

### 5.1 Directory Names
- Use **lowercase kebab-case**: `setup-files`, `data`, `env`, `tools`.
- Exceptions (standard repository roots): `README.md`, `CONVENTION.md`, `LICENSE`.

### 5.2 Script Files
- **PowerShell**: PascalCase (`Install_Menu.ps1`, `Remove_Menu.ps1`).
- **Batch (root & _sys)**: lowercase kebab-case (`register.bat`, `unregister.bat`, `install.bat`, `cleanup.bat`).

### 5.3 Tools Subfolders
- Fixed layout: `tools/{tool-name}/{executable}.exe` (e.g. `tools/ripgrep/rg.exe`, `tools/jq/jq.exe`).

---

## 6. local.config.bat — Per-PC Configuration Pattern

### 6.1 Purpose
Provides host-specific overrides (e.g. custom workspace directory, proxy settings) without modifying tracked system files.

### 6.2 Loading Rule
**Implemented 2026-09-04** (`_sys/core/launcher.py:_load_local_config_overrides`). `local.config.bat` is read as **data, not executed** — `launcher.py` parses its `set "KEY=VALUE"` lines directly with a regex, never `call`s or sources the file into a real shell environment. This is deliberate: sourcing it as a script would pollute the process environment with anything the file sets and couldn't distinguish "this key came from local.config.bat" from "this key happened to already exist in the parent shell" — a real collision risk (e.g. a host-wide npm install silently shadowing the portable one). Only the 2 documented keys are ever recognized (an explicit allowlist, not "whatever the file sets"):
- `NPM_CONFIG_PREFIX` — checked in `build_env()`; overrides the computed portable path for this one key only.
- `BASE_DIR_WORKSPACE` — checked in `_resolve_default_target()`; used as the default `engram launch`/`engram start` target (ahead of `base_dir/workspace` if that folder exists, ahead of the portable root itself as the final fallback).

`%VAR%`-style references in a value (e.g. the template's own `%APPDATA%\npm` example) are expanded against the real process environment. See `_sys/tests/unit/test_local_config_overrides.py` for the real test coverage (parsing, precedence, and a dedicated test that reading the file never leaks into `os.environ`).

### 6.3 Git Tracking Exclusion
- `local.config.bat` is machine-local and MUST be listed in `.gitignore`.
- Only the tracked template `_sys/local.config.bat.template` is committed to git.
- Never redefine root constants (`SYS_DIR`, `BASE_DIR`, `ENV_DIR`) inside `local.config.bat`.

---

## 7. Testing Environment Policy

### 7.1 Windows Sandbox (WSB)
Script and environment lifecycle tests should run inside Windows Sandbox whenever possible:
- `_sys\tests\run-sandbox-test.bat` (injects `__PORTABLE_ROOT__` into the `.wsb` template — do not launch `sandbox-unit-test.wsb` directly).
- Host repository is mounted read-only at `C:\PortableDev`.
- Test outputs write to host `_archive\test-results\` (writable), mapped at `C:\TestResults` inside the sandbox.
