# Portable Sandbox Dev Environment
> Last updated: 2026-06-04
> This file lets Claude Code resume from where the setup conversation left off.

## What This Project Is

A fully portable Windows development environment that lives in a single folder
(USB drive or cloud). Right-click any folder -> open VS Code + Claude Desktop
with all tools (Python, Node.js, FFmpeg, Git, etc.) pre-configured.

## Final Folder Structure

```
[PortableDev]/
├── install.bat / register.bat / unregister.bat
├── README.md / CLAUDE.md / GEMINI.md / CONVENTION.md / PROTOCOL.md
├── workspace/     ← default project folder
├── .claude/       ← agents/ + skills/
├── .gemini/       ← instructions/ + tools/ (symmetric parity)
├── _state/        ← agent session workspace (auto-managed)
├── .ai/           ← IPC state (hub.py managed — never write directly)
├── _archive/      ← logs, sessions, collab-log, workspace backups
└── _sys/          ← cli/ hooks/ checks/ core/ templates/ env/ tools/ tests/ data/
                     SYSTEM_ARCHITECTURE.md  git-config/  claude/  gemini/
```
Full annotated tree: `README.md`

## Architecture Decisions

| Decision | Reason |
|----------|--------|
| Everything under `_sys/` (except docs + workspace) | Root clean: 3 docs + workspace + .claude + _sys only |
| Workspace at root or external | Multiple workspaces, nested or outside BASE_DIR |
| Registry key = `SandboxRun_[FolderName]` | Multiple envs on same PC without conflict |
| N-Way Room Session (`room-{uuid}`) | P2P equality: No node monopoly. Shared context for all nodes. |
| Unified manage.bat (logic: manage.py) | Single Source of Truth for naming, SUBST mapping, and Registry state |
| Symmetric Agent Utilities | `claude-status.bat` / `claude-gate.bat` for parity with Gemini counterparts |
| Division of Labor (Autonomous) | Claude can call `gemini-gate.bat` to decide whether to delegate tasks to Gemini |
| State-aware Cleanup | Registration auto-cleans orphaned keys from previous folder names/paths |
| No USERPROFILE/APPDATA override | Preserves Git, SSH, host credentials |
| Tool-specific env vars (NPM_CONFIG_*, etc.) | Precise isolation without broad side effects |
| `CLAUDE_CONFIG_DIR = _sys\claude\config\` | Claude Code CLI auth/config travels with USB |
| Gemini CLI via npm-global (nodejs/npm-global) | `gemini.cmd` auto-in-PATH via existing npm-global PATH entry |
| Gemini auth in `%USERPROFILE%\.gemini\` (host) | Junctioned to `_sys\gemini\config` for portability |
| `_archive/` for all rolling data | logs + sessions + workspace backups in one place for easy cleanup |
| Individual `if exist` lines (not for-loop) | for-loop expands %PATH% once -> bug |
| `-LiteralPath` in all registry PS1 ops | `HKCU:\Software\Classes\*\shell\...` wildcard hang prevention |
| `launch.bat` as registry intermediary | Direct start.bat from registry breaks on space/Korean paths; uses physical path (not SUBST) |
| Registry relay at `%LOCALAPPDATA%\SandboxRun_*.bat` | Physical path with Korean/parens breaks cmd.exe parser; relay at ASCII path wraps it safely (mbcs encoding) |
| `settings.local.json` for drive-specific permissions | `settings.json` must stay drive-independent (git tracked); manage.py auto-generates local override on register |
| `.bat` files: English only, no Korean | chcp 65001 doesn't fix cmd.exe parser for multi-byte chars |
| `local.config.bat` for per-PC overrides | start.bat auto-loads it before CONFIG defaults |
| WSB (`launch-wsbtest.ps1`) as default test env | True OS isolation; sandbox-test.bat runs unmodified inside WSB |

## CRITICAL: Windows Shell Rules

- **Bash tool = /usr/bin/bash** → Never use PowerShell syntax in Bash tool
- PowerShell commands → use PowerShell tool
- System tasks → call `.bat` files directly
- Path separator: `\` (backslash)
- Always set `PYTHONUTF8=1` when calling `.bat` files

## CRITICAL: Peer-to-Peer State Management

- **All nodes are equal**: Claude does not monopolize orchestration.
- **NEVER** write directly to `.ai/state.json`
- Change state: `python _sys/core/hub.py update-status --mission "..."`
- Send message (P2P): `python _sys/core/hub.py send --from X --to Y --msg "..."`
- Check room status: `python _sys/core/hub.py status`

## Tool Output Limits (MANDATORY)

- **NEVER** glob/Read/PowerShell without bounding the output
- **ALWAYS** exclude `node_modules/`, `.git/`, `_sys/env/`, `venv/`, `__pycache__/` in all glob/find
- **ALWAYS** use `-Depth 1` for `Get-ChildItem`; never use `dir /s` or `ls -R` naked
- For files >100 lines: **ALWAYS** use `offset`/`limit` in Read tool. Never read whole file.
- For shell logs (npm, pip, pytest): pipe to temp, read last 10 lines only
  - Pattern: `cmd ... > "$env:TEMP\last_log.txt" 2>&1; Get-Content "$env:TEMP\last_log.txt" -Tail 10`
- For broad exploration: delegate to `Explore` sub-agent (isolates context blowout)
- **3-strike rule**: 3 consecutive Grep/Read with no useful result → stop, delegate to `Explore` sub-agent

## P2P Collaboration (PROTOCOL.md v3.3)

This project runs on an **N-Way shared Room session** with **unlimited consensus rounds**.
- **COLLAB_RATE (0~10)**: Controls collaboration depth across all nodes. (R:10 = 100% full sync)
- **Unanimous consensus**: All participating nodes must agree before task execution.
- **Division of Labor**: After consensus, each node handles tasks matching its specialty.
- **Cross-check**: All nodes mutually verify outputs after completion.

### Adaptive COLLAB_RATE (task risk-based)

| Risk | Rate | Applies To |
|------|------|------------|
| Low | R:0 | Read-only, grep, explore, doc reads |
| Med | R:3 | `workspace/` code changes |
| High | R:5 | `_sys/` script changes |
| Critical | R:10 | `PROTOCOL.md`, `CLAUDE.md`, `GEMINI.md`, `hub.py`, `nodes.json` |

### IPC Compact Syntax
- AGREE: `ACK:r-{round_id}` / DISAGREE: `NACK:r-{round_id}:REASON={short}`
- FINAL CALL: `FC:r-{round_id}:SUMMARY={brief}` / PROCEED: `PROC:r-{round_id}`
- Batch proposal: `PLAN:[1.{step}, 2.{step}] RISK:{main_risk} VOTE?`

## Collaboration Interface (Claude Optimized)

### Direct P2P (Autonomous — Gemini call)
See global CLAUDE.md "Gemini Collaboration Protocol" section.

### Human-relay (Human-in-the-loop)
Request human intervention via text tags:

| Action | Format |
|--------|--------|
| Request to Peers | `[REQUEST_TO_PEERS: TYPE]` — WRITE_FILE \| HUMAN_DECISION \| POLICY_CLARIFICATION \| GIT_OPERATION \| SESSION_MANAGEMENT \| READ_AND_VERIFY |
| Refusal | `[REFUSAL: CODE] reason` |

**Critical boundaries:**
- Do not edit `_sys/` scripts directly → use `[REQUEST_TO_PEERS: WRITE_FILE]`.
- Constitutional documents (`PROTOCOL.md`, etc.) require full node consensus to modify.

## Zero-Token Symmetric Memory

- **Blackboard First**: Before starting work, read `.ai/sessions/room-{uuid}/handoff.md` and `summary_*.md` to sync project state (**Re-orientation Phase**).
- **Zero-Token Sharing**: Write detailed analysis/summaries to files; share only short pointers (paths).
- **Symmetric Persistence**: On `ctx-save`, write checkpoints to both `CLAUDE.md` and `_sys\gemini\config\GEMINI.md`.

## Git Management

### Tracked Targets (Essential — git managed)
- Root: `install.bat`, `register.bat`, `unregister.bat`, `CLEANUP.bat`, `*.md`, `.gitignore`, `.gitattributes`
- `.claude/`: `agents/*.md`, `settings.json`, `skills/*/SKILL.md`
- `_sys/`: All `.py` + `.bat` scripts, configs, documentation, test sources

### Ignored Targets (Non-tracked)
| Path | Reason |
|------|--------|
| `_sys/env/**` | Large binaries — installed via install.bat |
| `_sys/tools/` | Large binaries — installed via install.bat |
| `_sys/data/temp/`, `_sys/data/setup-files/` | Generated during setup |
| `workspace/`, `_archive/`, `.ai/` | User data / ephemeral |
| `_state/` | Agent session workspace (auto-managed) |
| `_sys/claude/config/` | Auth/session data (except CLAUDE.md, settings.json, statusline-command.sh) |
| `.claude/settings.local.json` | Drive-specific permissions — auto-generated by register.bat, regenerated per PC |
| `_sys/tests/results/` | Test outputs |
| `WORKLOG.md` | Work log — managed in `_archive/` |

### Runtime Auto-Generated Folders
Created on first run by `setup.py` or `start.bat`:
`workspace/`, `_archive/`, `.ai/`, `_sys/tools/`, `_sys/data/temp/`, `_sys/data/setup-files/`

## CLI Reference

### start.bat
| Call | Action |
|------|--------|
| `start.bat` | Open BASE_DIR as VSCode workspace + launch Claude Desktop |
| `start.bat "folder"` | Open specified folder as VSCode workspace |
| `start.bat "file.py"` | Run with portable Python (venv) |
| `start.bat "file.bat"` | Run with portable cmd |
| `start.bat "file.exe"` | Open with Windows default handler |

## Current State
Last checkpoint: 2026-06-05 08:59 -- See .ai/ blackboard for details
→ See `_sys/claude/agent/CONTEXT.md` for static topology and agent team.
