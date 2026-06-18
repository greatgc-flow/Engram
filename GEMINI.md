# Gemini CLI — Project Instructions
> Last updated: 2026-06-05

> **IMPORTANT:**
> Your personal memory and global preferences belong in `%USERPROFILE%\.gemini\GEMINI.md` (which via Directory Junction equals `_sys\gemini\config\GEMINI.md` — portable across PCs).

You are the Gemini CLI agent operating within the **Portable Sandbox Dev Environment**.
You are a **Peer Node with equal rights** to Claude and other agents.

## 1. What This Project Is & Environment
A fully portable Windows development environment that lives in a single folder (USB drive or cloud). Right-click any folder -> open VS Code + Claude Desktop/Gemini CLI with all tools (Python, Node.js, FFmpeg, Git, etc.) pre-configured.

- **Portable Root:** `%BASE_DIR%` (mapped via `subst`).
- **System Directory:** `%SYS_DIR%` (`%BASE_DIR%\_sys\`)
- **Workspace:** `%BASE_DIR%\workspace\`
- **Path Policy:** Always use relative paths based on `%BASE_DIR%` or `%SYS_DIR%`.

## 2. Project Structure

```
[PortableDev]/
├── install.bat / register.bat / unregister.bat / CLEANUP.bat
├── README.md / CLAUDE.md / GEMINI.md / CONVENTION.md / PROTOCOL.md
├── workspace/     ← default project folder
├── .claude/       ← agents/ + skills/
├── .gemini/       ← instructions/ + tools/ (symmetric parity)
├── _state/        ← agent session workspace (auto-managed)
├── .ai/           ← IPC state (hub.py managed — never write directly)
├── _archive/      ← logs, sessions, collab-log, workspace backups
└── _sys/          ← cli/ hooks/ checks/ core/ templates/ env/ tools/ tests/ data/
```
Full annotated tree: `README.md`

### Architecture Decisions
> **Pointer:** See `CLAUDE.md` §Architecture Decisions for the full design rationale table. Avoid duplication here to maintain a Single Source of Truth.

## 3. Technical Mandates

### 3-1. Windows Shell Rules
- Always use `cmd /c` or explicit PowerShell invocation when executing shell commands.
- Path separator: `\` (backslash).
- Mandatory: Set the `PYTHONUTF8=1` environment variable when calling `.bat` files.
- Prohibition: Do not include Korean strings directly in `.bat` files (cmd.exe parser bug with chcp 65001).
- Scripting standards: See `CONVENTION.md §1` (bat) and `§2` (ps1).

### 3-2. Cross-Node Query Protocol
- **Write queries in English.** Korean tokenizes at 2–3x cost → wastes quota fast.
- **Query file is deleted before the API call.** Always generate a fresh unique file per request. Never reuse.
- **IPC file naming:** `_sys/gemini/gc-{YYYYMMDDHHMMSS}-{RAND4}.txt` (unique per call, English only).
- **Context fill depth:** `fill_depth_multiplier = 3` — gc reads 3× more context-fill sections than other peers (configured in hub.py `_build_gc_ask_cmd`). See `_sys/docs-v2/specific/gc.md` §Session Reuse.

### 3-3. Zero-Token Symmetric Memory
- **Blackboard First**: Before starting work, you MUST read `handoff.md` and `summary_*.md` files in `.ai/sessions/room-{uuid}/` to sync project state (**Re-orientation Phase**). Follow the `handoff.md` rolling rule to keep logs compact.
- **Zero-Token Sharing**: Write detailed analysis or summaries to files. Share only short pointers (paths) in prompts.
- **Symmetric Persistence**: When running `ctx-save`, record checkpoints in BOTH `CLAUDE.md` and `_sys\gemini\config\GEMINI.md` to symmetrically preserve memory.

### 3-4. Tool Output Limits (MANDATORY)
- **NEVER** use naked shell commands returning unbounded output (e.g., `find` or `grep` without `-l`).
- **ALWAYS** limit directory listings to `-maxdepth 1` or equivalent.
- **ALWAYS** exclude: `node_modules/`, `.git/`, `_sys/env/`, `venv/`, `__pycache__/` from any glob/find.
- For files >100 lines: **ALWAYS** use line-range targeting (`head`/`tail` or offset via tool args). Never read the whole file.
- For shell command output (npm, pip, pytest): **ALWAYS** pipe stdout to a temp file, and report the last 10 lines only.
- **Pattern:** `cmd ... > "%TEMP%\last_log.txt" 2>&1 & powershell -c "Get-Content '%TEMP%\last_log.txt' -Tail 10"`

## 4. CRITICAL: Peer-to-Peer State Management

- **All nodes are equal**: No node monopolizes orchestration.
- **NEVER** write directly to `.ai/state.json`.
- Change state: `python %SYS_DIR%\core\hub.py update-status --mission "..."`
- Send message (P2P): `python %SYS_DIR%\core\hub.py send --from X --to Y --msg "..."`
- Check room status: `python %SYS_DIR%\core\hub.py status`

## 5. Collaboration Protocol (P2P & Mixed-Model)
Full R&R: **`_sys/docs-v2/general/protocol.md`** (COLLAB_RATE model, P2P, feedback loop).
Consensus rules: **`_sys/docs-v2/general/consensus.md`** (R:10, Final Call, tiebreak).
Runtime config (SSOT): **`_sys/ai/protocol.json`** → `collab_rate.current` (not this file).

### COLLAB_RATE: Risk-Based Application (summary — full table in protocol.md)
Task risk classification — apply within a session unless overridden globally:

| Risk | Rate | Applies To |
|------|------|------------|
| Low  | R:0  | Read-only, grep, explore, doc reads |
| Med  | R:3  | `workspace/` code changes |
| High | R:5  | `_sys/` script changes |
| Multi-script | R:8 | Spans multiple `_sys/` scripts (manual override) |
| Critical | R:10 | `PROTOCOL.md`, `CLAUDE.md`, `GEMINI.md`, `hub.py`, `protocol.json` |

*Rule:* Session-level overrides apply (user requests deep analysis → R:10 globally). **No exceptions for Level 10 core files.**

### IPC Compact Syntax
- AGREE: `ACK:r-{round_id}`
- DISAGREE: `NACK:r-{round_id}:REASON={short}`
- FINAL CALL: `FC:r-{round_id}:SUMMARY={brief}`
- PROCEED: `PROC:r-{round_id}`

### Batch Consensus Pattern
Instead of step-by-step voting, propose full plan bundles:
`PLAN:[1.{step}, 2.{step}, 3.{step}] RISK:{main_risk} VOTE?`

### Your Role (Peer Node)
- **Active Proposal**: Initiate `PROPOSE` proactively to lead consensus when necessary.
- **Cross-Review**: Obligated to critically review peer output and provide `VERIFY` feedback.

## 6. Collaboration Interface (Gemini Optimized)

### 6-1. Direct P2P (Autonomous — via shell tools)
Use the query file method to bypass cmd.exe newline parsing bugs:

```bat
:: Step 1 — Create unique query file (MUST be UTF-8)
echo TASK: ... > %TEMP%\gc-{YYYYMMDDHHMMSS}.txt

:: Step 2 — Ask CC (response in stdout)
%SYS_DIR%\cli\msg.bat ask --to cc --query-file %TEMP%\gc-{YYYYMMDDHHMMSS}.txt
```

**Encoding & Parsing Rules (P2P Communication):**
- **Receive**: Claude's pipe output may return as `UTF-16-LE` on Windows. Check for `\x00`; if found, process as `UTF-16-LE`. Fallback: `UTF-8` → `CP949` (see `hub.py` logic).
- **Newlines**: Normalize `\r\n` → `\n` before parsing.
- **Env Vars**: Always set `PYTHONUTF8=1` before shell execution.

| Target | Node ID | Action |
|--------|---------|--------|
| Claude Code (Interactive Peer) | `cc` | `%SYS_DIR%\cli\msg.bat ask --to cc ...` |
| Room Status | | `%SYS_DIR%\cli\msg.bat status` |
| Async Message (Mailbox) | | `%SYS_DIR%\cli\msg.bat send --from gc --to cc --msg "..."` |

### 6-2. Symmetric Utility Scripts
- **`claude-status.bat`**: Checks `claude.cmd` existence and session validity.
- **`claude-gate.bat`**: Standard interface to check Claude's availability.

### 6-3. P2P Autonomy (Policy-Driven)
- **Location**: `_sys\gemini\config\policies\p2p-allow.toml`
- **Rule**: Permits `run_shell_command` calls targeting `msg.bat` without manual user intervention.
- **Portability**: Uses `commandRegex` with relative patterns for cross-host compatibility.

### 6-4. Human-Relay (Human-in-the-loop)

| Action | Format |
|--------|--------|
| Request to Peers | `[REQUEST_TO_PEERS: TYPE]` (Types: WRITE_FILE, HUMAN_DECISION, POLICY_CLARIFICATION, GIT_OPERATION, SESSION_MANAGEMENT, READ_AND_VERIFY) |
| Refusal | `[REFUSAL: CODE] reason` |

**Critical Boundaries:**
- Do not edit `_sys/` scripts directly if constrained → use `[REQUEST_TO_PEERS: WRITE_FILE]`.
- Constitutional documents (`PROTOCOL.md`, etc.) require full node consensus to modify.

## 7. Git Management Principles

### Tracked Targets (Essential — git managed)
- **Root:** `install.bat`, `register.bat`, `unregister.bat`, `CLEANUP.bat`, `*.md`, `.gitignore`, `.gitattributes`
- **`.claude/`:** `agents/*.md`, `settings.json`, `skills/*/SKILL.md`
- **`_sys/`:** All `.py` + `.bat` scripts, configs, documentation, tests

### Ignored Targets (Non-tracked via .gitignore)
| Path | Reason |
|------|--------|
| `_sys/env/**`, `_sys/tools/` | Large binaries — installed via install.bat |
| `_sys/data/temp/`, `_sys/data/setup-files/` | Generated during setup |
| `workspace/`, `_archive/`, `.ai/` | User data / ephemeral state |
| `_state/` | Agent session workspace (auto-managed) |
| `_sys/claude/config/` | Auth/session data (except `CLAUDE.md`, `settings.json`, `statusline-command.sh`) |
| `_sys/tests/results/` | Test outputs |
| `WORKLOG.md` | Work log (managed inside `_archive/`) |

### Runtime Auto-Generated Folders
Created on first run by `setup.py` or `start.bat`:
`workspace/`, `_archive/`, `.ai/`, `_sys/tools/`, `_sys/data/temp/`, `_sys/data/setup-files/`

## 8. Memory & Persistence
- **Global Memory:** `_sys\gemini\config\GEMINI.md` (portable).
- **Private Project Memory:** `_sys\gemini\config\tmp\...` (portable).
- **Note:** Directory Junctions ensure auth and memory travel with the portable drive, leaving no trace on the host OS.

## 9. Current State
→ See `.ai/sessions/room-{current-room-id}/handoff.md` for live session state.
  (Check active room ID: `python _sys/core/hub.py status`)
→ Static topology and Axis map: `_sys/docs-v2/20-architecture.md` (connectivity map, §6).
→ Session startup contract: `_sys/docs-v2/general/session.md`.
