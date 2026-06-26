# Portable Dev Environment — Coding Conventions

All source code must comply with the rules in this file.
The verifier agent determines PASS/FAIL based on this file.

## §0 — Language Policy (CRITICAL)
All agent definitions, skill files, policy documents, and JSON artifacts: English only.
Korean permitted ONLY in:
  • Claude's console replies to the user (final text output in conversation)
  • PowerShell Write-Host output visible to user (ps1 files only)
  • Archive logs (_archive/) — historical records, not modified
  • _sys/claude/config/CLAUDE.md (user's private global preferences — excluded)
Rationale: Korean consumes 2–3× more tokens than equivalent English.
Agent MD files are loaded into context on every invocation.

## 1. Batch File (.bat) Rules

### 1-1. Language and Encoding (CRITICAL)
- **Language**: Use **English only** for all echo statements, variable names, comments, and paths.
- **Encoding**: Must maintain **UTF-8 (No BOM)** format.
  - Reason: Prevents the bug where `cmd.exe` misinterprets the first command (`setlocal`) as `tlocal` due to a BOM.
- **ABSOLUTE PROHIBITION of Korean strings** — Even with `chcp 65001`, the `cmd.exe` parser treats multi-byte characters as token delimiters, breaking parsing.
- The `chcp` command itself is prohibited within `.bat` files (use `.ps1` if needed).

### 1-2. PATH Integration
```bat
# Correct pattern — individual if exist lines
if exist "%TOOLS_DIR%\ripgrep"  set "PATH=%TOOLS_DIR%\ripgrep;%PATH%"
if exist "%TOOLS_DIR%\fd"       set "PATH=%TOOLS_DIR%\fd;%PATH%"

# Forbidden pattern — %PATH% expansion inside for-loop block (expands only once)
for %%T in (ripgrep fd) do (
    if exist "%TOOLS_DIR%\%%T" set "PATH=%TOOLS_DIR%\%%T;%PATH%"
)
```

### 1-3. Log Function
```bat
:LOG
echo %~1
>> "%LOG_FILE%" echo %~1
exit /b 0
```
All output must be recorded simultaneously to file and console via `:LOG` calls.

### 1-4. Timestamp (PowerShell Get-Date)
```bat
for /f "delims=" %%I in (
    'powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"'
) do set "_DT=%%I"
set "LOG_FILE=%LOG_DIR%\start_%_DT:~0,8%_%_DT:~8,6%.log"
```
Do not use `wmic os get LocalDateTime` — `wmic` may not be present in Win11 24H2+.
Declare `setlocal EnableDelayedExpansion` if delayed expansion is required.

### 1-6. Path and Special Character Handling (Parenthesis Bug Prevention)
- **Paths with Parentheses**: If a path contains `(` or `)`, `%VAR%` expansion inside an `if (...)` or `for (...)` block can prematurely close the block.
- **Solutions**:
  1. **Avoid Blocks**: Use `if condition command` (single line) format.
  2. **Use Delayed Expansion**: Declare `setlocal EnableDelayedExpansion` and use `!VAR!` format.
  3. **Conditional Assignment**: Use `if not defined VAR for ...` (single line) instead of `if defined VAR (set "VAL=%VAR%") else (for ...)` to prevent parser confusion.
- **Example**:
```bat
# Bad example (Error if path contains ")")
if defined BASE_DIR (
    set "_BASE=%BASE_DIR%"
) else (
    for %%I in ("%~dp0..\..") do set "_BASE=%%~fI"
)

# Good example (Safe)
if not defined BASE_DIR for %%I in ("%~dp0..\..") do set "BASE_DIR=%%~fI"
set "_BASE=%BASE_DIR%"
```

## 2. Integrated Management and Installation Rules

### 2-1. Entry Point Batch Files
Root-level batch files delegate all logic to `_sys\core\dispatch.bat` → `_sys\core\dispatcher.py`.
- `register.bat`: SUBST mapping, registry menu registration, state storage.
- `unregister.bat`: SUBST release, registry removal, state cleanup.
- `CLEANUP.bat`: Tier 1~4 space optimization (via `_sys\cli\cleanup.py`).

### 2-2. Installation and Recovery (install.bat)
- `install.bat`: Automatically downloads and configures all runtimes via `setup.py`. (Supports ZeroBase)

### 2-3. Space Optimization (cleanup.bat)
- `cleanup.bat`: Performs Tier 1~4 step-by-step cleanup via `cleanup.py`.

### 2-3. Registry and Menu Rules
- **Key Naming**: `SandboxRun_[Drive]_[Parent]_[Leaf]` (special characters in paths replaced with `_`)
- **Label**: `Open in Sandbox: [Leaf] ([Full Physical Path] -> [SUBST]:)`
- **Auto-Cleanup**: Automatically removes keys from previously used paths during registration to prevent orphaned keys.
- **Trailing Backslash Escape Fix (CRITICAL)**:
  - **Issue**: Windows passes drive roots (e.g., `P:\`) with a trailing backslash. In a registry command like `"%V"`, this becomes `"P:\"`, where the backslash escapes the closing quote, breaking the command.
  - **Solution**: Always append a dot to the argument: `"%V."`.
  - **Normalization**: `start.bat` must normalize the incoming path using `for %%I in ("%~1") do set "TARGET=%%~fI"` to remove the dot (e.g., `P:\.` → `P:\`) before use.

### 2-4. Maintain launch.bat Middle Layer
Do not execute `start.bat` directly from the registry.
Maintain the `launch.bat → call start.bat %*` pattern.
(Registry command: `cmd.exe /c ""<physical_path>\_sys\cli\launch.bat" "%V""` — use physical path, SUBST prohibited)

## 3. Environment Variable Isolation Rules

### 3-1. Override Prohibition List
```
USERPROFILE    ← Absolute prohibition of override
APPDATA        ← Absolute prohibition of override
LOCALAPPDATA   ← Absolute prohibition of override
```
`HOST_LOCALAPPDATA=%LOCALAPPDATA%` backup is permitted (for running Claude Desktop).

### 3-2. Dedicated env var per Tool
Each tool must use its own dedicated environment variables:
```bat
set "NPM_CONFIG_PREFIX=%ENV_DIR%\nodejs\npm-global"
set "NPM_CONFIG_CACHE=%ENV_DIR%\nodejs\npm-cache"
set "PIP_CACHE_DIR=%ENV_DIR%\python\pip-cache"
set "PYTHONUSERBASE=%ENV_DIR%\python\userbase"
set "CLAUDE_CONFIG_DIR=%CLAUDE_DIR%\config"
set "BAT_CACHE_PATH=%TOOLS_DIR%\bat\cache"
set "SESSION_DIR=%DATA_DIR%\sessions"
set "TEMP=%DATA_DIR%\temp"
set "TMP=%DATA_DIR%\temp"
:: (ENV_DIR=%SYS_DIR%\env, CLAUDE_DIR=%SYS_DIR%\claude, etc.)
```

### 3-3. Prohibition of Hardcoded Paths
Do not use drive letters (`C:\`, `D:\`) directly.
Write all paths as relative paths based on `%BASE_DIR%` or `%SYS_DIR%`.

### 3-4. Gemini CLI Call Pattern

**Gemini availability is determined via the `GEMINI_MODE` env var** (set by `start.bat → gemini-status.bat`).
Do not call `where gemini` directly.

```bat
:: (Existing patterns 1-3 remain unchanged)
```

**Symmetry and Portability (Agent Specifics):**
- **Root Directory (`.gemini/`)**: Projects should maintain a `.gemini/` directory at the root for symmetry with `.claude/`.
  - `.gemini/instructions/`: Detailed behavioral guides for the Gemini agent.
  - `.gemini/tools/`: Custom Python scripts/modules.
- **Tool Registration**: Unlike Claude's skills, Gemini tools are not auto-loaded.
  - **MANDATORY**: When adding a script to `.gemini/tools/`, you MUST update the corresponding file in `.gemini/instructions/` to inform the agent of the new tool's availability and usage (via `run_shell_command`).
- **Policy Management**:
  - Location: `_sys\gemini\config\policies\` (Native path for Gemini CLI; junctioned to host).
  - Portability: Always use `commandRegex` with relative patterns instead of absolute paths (e.g., `commandRegex = ".*_sys[/\\\\]cli[/\\\\]msg\\.bat.*"`).
- **Shared Policies**: Files like `p2p-allow.toml` are shared across sessions. Edits require human consensus.

### §3-6. Robust JSON Parsing (Shell Scripts)
When parsing agent configuration files (like `.claude.json`) which can be very large (>30KB), avoid using `ConvertFrom-Json` in PowerShell as it may fail on character encoding or malformed blocks.
- **Preferred Pattern**: Use `Select-String` (regex) to check for existence of key properties.
- **Example**: `powershell -NoProfile -Command "if (Select-String -Path 'path/to/config' -Pattern '\"property\"' -Quiet) { exit 0 } else { exit 1 }"`
- **Rationale**: Faster, less memory-intensive, and more resilient to partial file corruption.

### §3-4-A — Include-Files Size Guard (MANDATORY)

Before any --include-files call, check total size:
  powershell -NoProfile -Command "(Get-Item 'file1','file2' | Measure-Object Length -Sum).Sum / 1KB"

Thresholds:
  < 200KB  : Safe. Proceed.
  200-400KB: Warning. Consider splitting into two calls.
  > 400KB  : STOP. Split before calling. Large includes degrade Gemini output quality.
             Prefer: summarize large files via Axis-D inline first, then include summary.

Applies to: check-agents.bat (merged agent file), portability-auditor corpus scan, any manual call.

### §3-4-B — Hub Script Protection (DO NOT RENAME OR DELETE)

The following scripts are called by ALL Axis bat files. Renaming or deleting them silently breaks all Axis logging:

| File | Called by |
|------|-----------|
| `_sys\hooks\collab-log.bat` | ctx-save, ctx-end, version-check, agent-audit, script-deps, git-draft |
| `_sys\hooks\raw-log.bat` | same set |
| `_sys\hooks\ai-check.bat` | all Axis bat files (ctx-save, ctx-end, context-health, version-check, agent-audit, script-deps, git-draft, risk-scan) |

Rules:
- Never rename or move these files without updating ALL callers simultaneously.
- Before any script move/rename in `_sys\hooks\`, verify all callers are updated simultaneously.
- Confirmed via Axis-F (check-deps.bat) on 2026-06-01.

Known issue: Gemini CLI may emit `API returned invalid content after all retries` (NumericalClassifierStrategy failure) before producing valid output. This is an internal routing bug — does NOT indicate auth failure. If Axis output is valid JSON, proceed normally. Error files logged to `_sys\data\temp\gemini-client-error-generateJson-*.json`.

### §3-4-C — Gemini Refusal Detection Pattern (MANDATORY in Axis scripts)

After any gemini call (exit code 0) and before the success path, add:
  findstr /i "\[REFUSAL:" "%_OUTPUT%" > nul 2>&1
  if not errorlevel 1 (
      call "%~dp0collab-log.bat" "Axis-X" "script.bat" "REFUSED" "Gemini refused request"
      del "%_OUTPUT%" > nul 2>&1
      exit /b 1
  )

Axis scripts requiring this pattern: check-agents.bat, check-health.bat, check-versions.bat,
check-deps.bat, git-draft.bat, check-risk.bat (risk-scan uses exit /b 0 — non-blocking).

### §3-4-D — Axis Token Budget

| Axis | Script | Max tokens | Claude cost | Trigger |
|------|--------|-----------|-------------|---------|
| A | portability full-corpus | ≤500k | ~0 | max 3/day |
| B | check-versions.bat | ≤5k | ~0 | unlimited |
| C | ctx-end session summary | ≤10k | ~0 | 1/session-end |
| D | syntax check (inline) | ≤5k | ~0 | 1/script-edit |
| D+ | ctx-save mid-summary | ≤10k | ~0 | 1/ctx-save (opt-in) |
| E | check-agents.bat | ≤20k | ~0 | agents/*.md change only |
| F | check-deps.bat | ≤5k | ~0 | 1/script-edit |
| G | git-draft.bat | ≤3k | ~0 | 1/commit |
| H | check-health.bat | ≤2k | ~0 | max 5/session |
| I | check-risk.bat | ≤10k | ~0 | Phase 1.5 |

### 3-5. Collaboration Protocol
→ See **`_sys/docs-v2/general/protocol.md`** (P2P model, COLLAB_RATE levels, feedback loop).
→ Consensus voting rules: **`_sys/docs-v2/general/protocol.md`** §4 Collaboration & Consensus (R:10, Final Call, tiebreak).
→ Runtime config (single source of truth): **`_sys/ai/protocol.json`** (`collab_rate.current`, health thresholds, r10_voters).
→ Full SSOT index: **`PROTOCOL.md`** → **`_sys/docs-v2/MOC.md`**.

## §3-7 — Gemini-first Analysis Rule
When gc should be prioritized as an analysis tool (large corpus, cross-repo scan) → See **`_sys/docs-v2/20-architecture.md §6`** (connectivity map) and **`_sys/docs-v2/general/routing.md §3`** (role taxonomy).

## §3-8 — Collaboration Health Check
Collaboration health check → **Axis H** (`_sys/checks/check-health.bat`). Token budget: See §3-4-D.

## §3-9 — Session Transition Triggers
Collaboration transition timing by COLLAB_RATE level → See **`_sys/docs-v2/general/protocol.md`** (COLLAB_RATE table) and **`_sys/docs-v2/general/session.md`** (session decision tree).

## 4. Folder/File Naming Rules

### 4-1. Folders
- lowercase kebab-case: `setup-files`, `data`, `env`, `tools`, `claude`, `agent`
- Exceptions (maintain convention): `CONVENTION.md`, `CLAUDE.md`, `README.md`

### 4-2. Script Files
- PowerShell: PascalCase (`Install_Menu.ps1`, `Remove_Menu.ps1`)
  - `Install_Menu.ps1` and `Remove_Menu.ps1` receive the `-BaseDir` parameter to explicitly pass BASE_DIR from the calling location (register.bat / unregister.bat).
- Batch (root): lowercase (`register.bat`, `unregister.bat`, `install.bat`, `cleanup.bat`)
- Batch (_sys/): lowercase (`start.bat`, `ctx-save.bat`, `ctx-end.bat`)

### 4-3. tools/ Subfolders
Format: `tools/{tool-name}/{executable}.exe`
Example: `tools/ripgrep/rg.exe`, `tools/jq/jq.exe`

## 5. Session Context and State Update Rules
→ Session context: `_sys/docs-v2/general/session.md` (startup contract, handoff, resume rules).
→ Per-peer config delta: `_sys/docs-v2/specific/cc.md` (cc), `_sys/docs-v2/specific/ag.md` (ag).
→ State changes must go through `hub.py update-status`.

## 6. local.config.bat — Per-PC Configuration Pattern

### 6-1. Purpose
Overrides settings that vary by PC (OBSIDIAN_VAULT, NO_DESKTOP, BASE_DIR_WORKSPACE, etc.) without modifying `start.bat` directly. Basic settings remain intact when moving via USB.

### 6-2. Loading Rules
`start.bat` loads `local.config.bat` immediately after the CONFIG section, before environment variable settings:
```bat
:: [Per-PC overrides] local.config.bat (not tracked, PC-specific)
if exist "%SYS_DIR%\local.config.bat" call "%SYS_DIR%\local.config.bat"
```

### 6-3. Git Tracking Exclusion
- Never commit the untracked `local.config.bat` to Git.
- Specify it in `.gitignore`.
- Only the template `_sys/core/local.config.bat.template` is tracked.

### 6-4. Overridable Variables
- `NO_DESKTOP` — Block automatic execution of Claude Desktop
- `BASE_DIR_WORKSPACE` — Change the default working folder
- `NPM_CONFIG_PREFIX` — Force use of system npm (releases portable isolation)
- `BASE_DIR_PHYS` — Physical absolute path (auto-set by register.bat; do not change manually)
- `SUBST_DRIVE_LETTER` — Fixed drive letter (auto-set by register.bat; do not change manually)

### 6-5. Prohibitions
- Do not redefine path constants (`SYS_DIR`, `BASE_DIR`, `ENV_DIR`, etc.) in `local.config.bat`.
- Use caution when changing tool-specific isolation variables (`PIP_CACHE_DIR`, etc.) as it may break isolation.

## 7. Agent Path Policy
Use relative notation based on `%BASE_DIR%` / `%SYS_DIR%` when referencing paths within agent files.
Hardcoded drive letters are prohibited. Mutual non-interference zone → See **`_sys/docs-v2/10-invariants.md`** (INV-03 Sandbox boundary, INV-06 Session isolation).

---

## §8 — Decision Delegation Policy
For matters requiring unanimous agreement → See **`_sys/docs-v2/general/protocol.md`** §4 Collaboration & Consensus (R:10, Final Call, voter list).
Call Human Gate in case of deadlock → See **`_sys/docs-v2/10-invariants.md`** (INV-07 Human escalation).

## §9 — Testing Environment Policy (2026-06-01)

### Default: Windows Sandbox (WSB)

All script and environment tests MUST run in Windows Sandbox when possible.
Local temp directory simulation (EngramTest_*) is DEPRECATED as primary method.

| Method | Use Case | Command |
|--------|----------|---------|
| WSB (default) | Full env validation, new-PC scenario, install/tool test | `python _sys\tests\launch_wsb.py` |
| Local temp (fallback) | Quick unit checks, WSB feature not enabled | `_sys\tests\run-sandbox-test.bat` (directly) |

### WSB Architecture
- `launch_wsb.py`: resolves physical path (handles SUBST), generates temp `.wsb`, waits for results
- `wsb-entry.bat` runs UNMODIFIED inside WSB — path layout (`C:\PortableDev`, `C:\TestResults`) matches WSB mounts
- Host read-only: physical `<BASE_DIR>` → `C:\PortableDev`
- Host writable: `_sys\tests\results\` → `C:\TestResults` (result survives sandbox exit)
- Sandbox auto-shuts down after tests; result archived as `results\result_{timestamp}.txt`

### When to Run WSB Tests
- Before commit touching `_sys/*.bat` or `_sys/*.py`
- After adding a tool to `tools/`
- Before marking a portable-env harness task COMPLETE
- After `setup.py` or `start.bat` structural changes

### WSB Prerequisites
- Windows Sandbox optional feature: `optionalfeatures.exe → Windows Sandbox`
- Requires Win11 Pro / Enterprise / Pro for Workstations (this system qualifies)

## §10 — Parallel & Multi-Instance Safety (2026-06-02)

To prevent "Vertical" (multi-instance) and "Horizontal" (parallel execution) conflicts:

### 10-1. Session Isolation
- Each `start.bat` instance MUST generate a unique `SESSION_UUID` (or `%RANDOM%`).
- All agent-transient data must reside in `_thoughts/session-%SESSION_UUID%/`.
- All IPC state must be accessed via `hub.py` (`.ai/mailbox.json`, `.ai/state.json`), never written directly.

### 10-2. Axis Script Safety
- ALL scan scripts in `_sys/checks/` writing output MUST use a unique filename.
- Pattern: `%_OUTPUT_DIR%/%AXIS_NAME%-%RANDOM%.json`.
- Never use static filenames like `temp-audit.json` for shared analysis results.

### 10-3. File Naming
- ALL system scripts (.bat) must use `lowercase-kebab-case.bat`.
- No uppercase or mixed-case for system-level automation.
