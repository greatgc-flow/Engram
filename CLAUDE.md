# Portable Sandbox Dev Environment
> Last updated: 2026-06-03
> This file lets Claude Code resume from where the setup conversation left off.

## What This Project Is

A fully portable Windows development environment that lives in a single folder
(USB drive or cloud). Right-click any folder -> open VS Code + Claude Desktop
with all tools (Python, Node.js, FFmpeg, Git, etc.) pre-configured.

## Final Folder Structure

```
[PortableDev]/              <- ROOT (docs + INSTALL.bat + register.bat + unregister.bat + workspace + .claude + _sys + _state + .ai + _archive)
????? INSTALL.bat             <- double-click entry (calls _sys\setup.ps1)
????? register.bat            <- register this PC: context menu + SUBST drive (once per PC or USB move)
????? unregister.bat          <- permanently remove context menu + SUBST from this PC
????? CLAUDE.md               <- this file
????? README.md               <- user documentation
????? CONVENTION.md           <- coding standards (agents reference this)
????? workspace/              <- default project folder (can also be external)
????? .claude/                <- harness: agents/ + skills/
????? _state/                 <- agent session workspace (auto-managed, not user content)
??  ?遺??? 02_*.md / 03_*.md / 04_*.md per session
????? .ai/                    <- project-local IPC state (hub.py managed, never write directly)
??  ????? state.json          <- hub.py state (write via hub.py only)
??  ????? mailbox.json        <- inter-agent messages
??  ????? sessions/           <- handoff.md FIFO per session
??  ?遺??? nodes.json          <- N-node consensus registry
??????? _archive/               <- ALL rolling historical data (logs, sessions, workspace backups)
??  ????? logs/               <- start.bat execution logs (LOG_DIR)
??  ????? sessions/           <- ctx-save / ctx-end session files (SESSION_DIR)
??  ????? collab-log/         <- Claude-Gemini collaboration logs (YYYY-MM-DD.md per day)
??  ????? CHANGELOG.md        <- full change history (moved from CLAUDE.md for token efficiency)
??  ?遺??? workspace_{YYYYMMDD_HHMMSS}/  <- _workspace backups per session
???遺??? _sys/                   <- ALL system files (tools, config, data)
    ????? start.bat           <- main launcher (restores SUBST on reboot; warns if not registered)
    ????? launch.ps1          <- relay: registry -> start.bat (path safety)
    ????? manage.ps1          <- unified manager: Register/Unregister SUBST + context menu (called by register.bat / unregister.bat)
    ????? setup.ps1           <- zerobase bootstrapper (download + install all)
    ????? cleanup.ps1         <- temp/cache/log cleanup (space optimizer)
    ????? local.config.bat.template  <- per-PC config template (copy & edit)
    ??    ????? cli/                <- user-facing CLI entry points
    ??  ????? cla.bat         <- Claude agent launcher
    ??  ????? gem.bat         <- Gemini direct channel
    ??  ?遺??? msg.bat         <- inter-agent message bus (3TCP)
    ??    ????? hooks/              <- lifecycle hooks
    ??  ????? ctx-save.bat    <- mid-session checkpoint
    ??  ????? ctx-end.bat     <- session end + summary
    ??  ????? check-gate.bat  <- Gemini mode gate
    ??  ?遺??? collab-log-append.bat <- collaboration log writer
    ??    ????? scans/              <- audit & scan scripts (Axis-B/E/F/H/I)
    ??  ????? scan-env.bat    <- version/env check (Axis-B)
    ??  ????? scan-health.bat <- context health (Axis-H)
    ??  ????? scan-risk.bat   <- pre-flight risk (Axis-I)
    ??  ????? scan-audit.bat  <- agent consistency (Axis-E)
    ??  ?遺??? scan-deps.bat   <- script dependency map (Axis-F)
    ??    ????? core/               <- Python IPC engine
    ??  ?遺??? hub.py          <- hub: 16 actions, filelock, 3TCP v1
    ??    ????? docs/               <- template documents
    ??  ????? CLAUDE_project.md  <- template for per-project CLAUDE.md
    ??  ?遺??? CLAUDE_global.md   <- template for _sys\claude\config\CLAUDE.md
    ??    ????? git_config/         <- portable git settings
    ??  ?遺??? .gitconfig
    ??    ????? env/                <- runtime binaries
    ??  ????? python/         <- portable Python (embeddable)
    ??  ????? nodejs/         <- portable Node.js + npm-global (Gemini + Claude CLI here)
    ??  ??  ?遺??? npm-global/ <- code.cmd (VS Code wrapper), claude.cmd, gemini.cmd
    ??  ????? ffmpeg/         <- portable FFmpeg (bin/ subfolder)
    ??  ????? git/            <- portable Git
    ??  ????? vscode/         <- portable VS Code (data/ enables portable mode)
    ??  ????? pwsh/           <- portable PowerShell 7 (optional, setup.ps1 installs)
    ??  ?遺??? venv/           <- Python venv (auto-created by start.bat)
    ??    ????? tools/              <- optional CLI + GUI tools (auto-detected)
    ??  ????? ripgrep/ rg.exe    [installed]
    ??  ????? fd/      fd.exe    [installed]
    ??  ????? jq/      jq.exe    [installed]
    ??  ????? bat/     bat.exe   [installed]
    ??  ????? delta/   delta.exe [installed]
    ??  ????? fzf/     fzf.exe   [installed]
    ??  ????? sqlite/  sqlite3.exe [not installed]
    ??  ????? oh-my-posh/        [installed]
    ??  ?遺??? apps/             <- GUI apps (Bruno, etc.)
    ??    ????? claude/             <- Claude Code CLI
    ??  ????? config/         <- CLAUDE_CONFIG_DIR (auth + global CLAUDE.md, portable)
    ??  ?遺??? agent/          <- agent state (CONTEXT.md)
    ??    ????? gemini/             <- Gemini CLI (binary in nodejs/npm-global)
    ??  ?遺??? config/         <- placeholder; Gemini CLI auth portable via Junction ??%USERPROFILE%\.gemini\
    ??    ????? test/               <- test suite
    ??  ????? sandbox-test.bat   <- unit tests (~100 cases, WSB-ready)
    ??  ????? host-test.ps1      <- host-side tests (31 cases: settings, statusline, VS Code, npm)
    ??  ????? test-runner.ps1    <- orchestrator (Layer 1+2, WSB auto-detect, report)
    ??  ????? launch-wsbtest.ps1 <- WSB launcher (SUBST-aware, maps P:\ ??C:\PortableDev)
    ??  ?遺??? results/           <- test reports (last-run.txt + timestamped archives)
    ??    ?遺??? data/               <- persistent data
        ????? temp/           <- isolated temp files
        ?遺??? setup-files/    <- installer archives & download links
```

## Architecture Decisions

| Decision | Reason |
|----------|--------|
| Everything under `_sys/` (except docs + workspace) | Root clean: 3 docs + workspace + .claude + _sys only |
| Workspace at root or external | Multiple workspaces, nested or outside BASE_DIR |
| Registry key = `SandboxRun_[FolderName]` | Multiple envs on same PC without conflict |
| HKCU for context menu (not HKCR) | No admin required; register.bat handles initial and re-registration |
| register.bat for explicit PC registration | Assigns fixed SUBST drive; calls manage.ps1 to store state and register menu |
| unregister.bat for permanent removal | Calls manage.ps1 for global cleanup (SUBST + Registry + State) |
| Unified manage.ps1 manager | Single Source of Truth for naming, SUBST mapping, and Registry state |
| State-aware Cleanup | Registration auto-cleans orphaned keys from previous folder names/paths |
| No USERPROFILE/APPDATA override | Preserves Git, SSH, host credentials |
| Tool-specific env vars (NPM_CONFIG_*, etc.) | Precise isolation without broad side effects |
| `CLAUDE_CONFIG_DIR = _sys\claude\config\` | Claude Code CLI auth/config travels with USB |
| Gemini CLI via npm-global (nodejs/npm-global) | `gemini.cmd` auto-in-PATH via existing npm-global PATH entry; no separate PATH line needed |
| Gemini auth in `%USERPROFILE%\.gemini\` (host) | Gemini CLI v1.x does not support `GEMINI_CONFIG_DIR` override; re-auth required per PC |
| `_archive/` for all rolling data | logs + sessions + workspace backups in one place for easy cleanup |
| `LOG_DIR = BASE_DIR\_archive\logs` | Logs beside workspace backups, not buried under _sys |
| `SESSION_DIR = BASE_DIR\_archive\sessions` | Session files beside logs; ctx-save/end fallback-derives from script location if SESSION_DIR unset |
| `ENV_DIR`, `TOOLS_DIR`, `CLAUDE_DIR`, `DATA_DIR` in start.bat | All paths relative to SYS_DIR |
| Individual `if exist` lines (not for-loop) | for-loop expands %PATH% once -> bug |
| `-LiteralPath` in all registry PS1 ops | `HKCU:\Software\Classes\*\shell\...` wildcard hang prevention |
| `launch.ps1` as registry intermediary | Direct bat execution from registry breaks on space/Korean paths |
| `.bat` files: English only, no Korean | chcp 65001 doesn't fix cmd.exe parser for multi-byte chars |
| No Rust toolchain | Removed; not used |
| `local.config.bat` for per-PC overrides | start.bat auto-loads it before CONFIG defaults; not tracked in Git |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` auto-set | Harness (agent teams) requires this env var; start.bat sets it on every launch |
| `setup.ps1` component-level try/catch (Run-Component) | One component failing does not abort the whole bootstrap; failures listed in summary |
| `INSTALL.bat` at root | Single double-click entry for first-time setup; relays to `_sys\setup.ps1` |
| `code.cmd` in `npm-global/` | VS Code portable wrapper; Claude Code IDE integration requires `code.cmd` in PATH |
| `start.bat` syncs `statusline-command.sh` to `~/.claude/` | statusline script must be at `~/.claude/` on every host PC; start.bat copies it on each launch |
| WSB (`launch-wsbtest.ps1`) as default test env | True OS isolation; sandbox-test.bat runs unmodified inside WSB; local fallback for CI |
| `_archive/CHANGELOG.md` for change history | Keeps CLAUDE.md stable (better prompt-cache hits); history accessible but not loaded every session |
| `pwsh/` in `env/` | Portable PowerShell 7; optional component via `setup.ps1 -Pwsh` |

## Key Bugs Fixed (for reference)

1. **HKCR wildcard hang**: `Test-Path` / `Set-ItemProperty` on `HKCR:\*\shell\...`
   treats `*` as wildcard -> enumerated all HKCR keys. Fixed: `-LiteralPath`.
   Same applies to `HKCU:\Software\Classes\*\shell\...`.

2. **for-loop PATH accumulation**: `for %%T in (...) do (set "PATH=...;%PATH%")`
   expands `%PATH%` once before loop. Fixed: individual `if exist` lines.

3. **Korean in .bat call args**: `call :LOG "???..."` - cmd.exe parser splits
   multi-byte UTF-8 chars into tokens. Fixed: English only in all .bat files.

4. **Registry command quoting**: `cmd.exe /c ""path"" "arg""` -> empty command error.
   Fixed: `launch.ps1` as relay, uses `cmd /c call "bat" "arg"` pattern.

5. **FZF_HISTORY_DIR**: invented env var that fzf doesn't recognize. Removed.

6. **BAT_CONFIG_DIR**: wrong name. Fixed: `BAT_CACHE_PATH`.

7. **`for /f` wmic in for-loop block with `!VAR!`**: needed `setlocal EnableDelayedExpansion`.

## CRITICAL: Windows Shell Rules

- **Bash tool = /usr/bin/bash** → PowerShell 문법 절대 금지 (backslash path, `$env:`, `-ErrorAction` 등)
- PowerShell 명령 → PowerShell tool 사용
- 시스템 작업 → `.bat` 파일 직접 호출
- 경로 구분자: `\` (backslash)
- 모든 `.bat` 호출 시 `PYTHONUTF8=1` 환경변수 설정 또는 내부에 포함

## CRITICAL: State Management

- `.ai/state.json` 직접 쓰기 절대 금지
- 상태 변경: `python _sys/core/hub.py update-status --mission "..." ` 호출
- 메시지 발송: `python _sys/core/hub.py send --from X --to Y --msg "..."`
- 세션 조회: `python _sys/core/hub.py status --format llm`
- 배치 진입점: `_sys/cli/cla.bat`, `_sys/cli/gem.bat`, `_sys/cli/msg.bat`

## Gemini Consultation (Axis-Q)

이 프로젝트에서 Gemini consult 스크립트 위치: `_sys\cli\msg.bat ask --to gemini`
복잡한 작업 전 Gemini를 먼저 호출하고 응답을 기다린 후 진행할 것. (전역 CLAUDE.md 참조)

## Current State
Last updated: 2026-06-03 (3TCP v1 완료)
2026-06-03 3TCP v1 완료:
- Phase 0: _workspace/ 구 산출물 12개 삭제
- Phase 1: _sys/core/hub.py 작성 (10 액션, filelock 3.29.0, Token-Zero)
- Phase 2: _sys/cli/ (cla/gem/msg.bat) + _sys/hooks/ 작성
- Phase 3~4: .ai/ 초기화, agents/*.md session-primer, CLAUDE.md hard rules
- 3TCP v1: hub.py Phase A~D (timeout=None, 메시지 봉투, N-node, consensus)
- PROTOCOL.md 신규 생성 (COLLAB.md 흡수 및 삭제, 3TCP v1 §P-0~P-7 추가)
- CONVENTION.md, GEMINI.md 참조 COLLAB.md → PROTOCOL.md 업데이트

## Next Steps

1. **Fresh PC setup**: INSTALL.bat (double-click) → _sys\setup.ps1 (사용자 직접 수행)

---
## Gemini CLI Collaboration Model (3TCP v1)

Gemini CLI operates as a **Tier 3 Sensor** and Domain Specialist within the 3-Tier architecture.
Protocol details → **PROTOCOL.md §P-0, §C-1, §C-2**

**Axes (GC Specializations):**
- **Axis-A**: Full codebase analysis — portability-auditor (up to 500k tokens)
- **Axis-B**: External version checks — version-check.bat (Google Search grounding)
- **Axis-C**: Session summarization — ctx-end.bat (optional, Flash model)
- **Axis-D**: Script syntax pre-check — inline pass
- **Axis-D+**: Mid-session checkpoint — ctx-save
- **Axis-E**: Agent consistency audit — agent-audit.bat → _archive/agent-audit.json
- **Axis-F**: Script dependency map — script-deps.bat → _archive/script-deps.json
- **Axis-G**: Commit message draft — git-draft.bat (user reviews before commit)
- **Axis-H**: Context health — context-health.bat (JSONL size → status.json + session-handoff.json)
- **Axis-I**: Pre-flight risk — risk-scan.bat (Phase 1.5, collab-log patterns → _archive/risk-scan.json)

**Constraints:**
| Constraint | Detail |
|-----------|--------|
| No direct edit of `_sys/` or `*.bat/*.ps1` | Use `[REQUEST_TO_CLAUDE: WRITE_FILE]` instead |
| 1,000 req/day quota | Axis-A max 3/day; others as needed |
| No cron/hook auto-invocation | Auth expiry causes silent failure |
| `GEMINI_CONFIG_DIR` not supported | v0.44.1 limitation |
| No PASS/FAIL authority | Sensor only; verifier (CA) is the sole judge |

**Related files:**
- `_sys/scans/scan-env.bat` → version check → `_archive/version-check.json`
- `_sys/hooks/ctx-end.bat` → session summary hook (optional, Flash)
- `_sys/scans/scan-health.bat` → Axis-H: JSONL size → status.json + session-handoff.json
- `.claude/agents/portability-auditor.md` → Gemini Full-Corpus Scan agent
- `.claude/agents/proposer.md` → version-check.bat trigger + improvement proposal
- `CONVENTION.md §3-4` → Gemini call patterns and constraints

---

## Portable Dev Environment

**Summary:** `_sys/` system files are centralized; architecture supports multi-instance parallel execution; test coverage is 4 layers + 7 agents with full audit/task tracking (89 tests total).
**Tag:** Portable Dev Environment work is tagged `portable-env`.
See `_archive/CHANGELOG.md` for full change history (last updated: 2026-06-03).