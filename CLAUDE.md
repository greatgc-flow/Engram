# Portable Sandbox Dev Environment
> Last updated: 2026-05-31
> This file lets Claude Code resume from where the setup conversation left off.

## What This Project Is

A fully portable Windows development environment that lives in a single folder
(USB drive or cloud). Right-click any folder -> open VS Code + Claude Desktop
with all tools (Python, Node.js, FFmpeg, Git, etc.) pre-configured.

## Final Folder Structure

```
[PortableDev]/              <- ROOT (3 docs + INSTALL.bat + register.bat + unregister.bat + workspace + .claude + _sys + _workspace + _archive)
├── INSTALL.bat             <- double-click entry (calls _sys\setup.ps1)
├── register.bat            <- register this PC: context menu + SUBST drive (once per PC or USB move)
├── unregister.bat          <- permanently remove context menu + SUBST from this PC
├── CLAUDE.md               <- this file
├── README.md               <- user documentation
├── CONVENTION.md           <- coding standards (agents reference this)
├── workspace/              <- default project folder (can also be external)
├── .claude/                <- harness: agents/ + skills/
├── _workspace/             <- agent session workspace (auto-managed, not user content)
│   └── state.json + 02_*.md / 03_*.md / 04_*.md per session
│   (backed up as _archive/workspace_{YYYYMMDD_HHMMSS}/ on new session start)
│
├── _archive/               <- ALL rolling historical data (logs, sessions, workspace backups)
│   ├── logs/               <- start.bat execution logs (LOG_DIR)
│   ├── sessions/           <- ctx-save / ctx-end session files (SESSION_DIR)
│   └── workspace_{YYYYMMDD_HHMMSS}/  <- _workspace backups per session
│
└── _sys/                   <- ALL system files (tools, config, data)
    ├── start.bat           <- main launcher (restores SUBST on reboot; warns if not registered)
    ├── launch.ps1          <- relay: registry -> start.bat (path safety)
    ├── manage.ps1          <- unified manager: Register/Unregister SUBST + context menu (called by register.bat / unregister.bat)
    ├── setup.ps1           <- zerobase bootstrapper (download + install all)
    ├── cleanup.ps1         <- temp/cache/log cleanup (space optimizer)
    ├── local.config.bat.template  <- per-PC config template (copy & edit)
    │
    ├── context/            <- session management scripts
    │   ├── ctx-save.bat    <- mid-session checkpoint (session log -> _archive\sessions\)
    │   ├── ctx-end.bat     <- full session summary + session log to _archive\sessions\
    │   ├── CLAUDE_project.md  <- template for per-project CLAUDE.md
    │   └── CLAUDE_global.md   <- template for _sys\claude\config\CLAUDE.md
    │
    ├── git_config/         <- portable git settings
    │   └── .gitconfig
    │
    ├── env/                <- runtime binaries
    │   ├── python/         <- portable Python (embeddable)
    │   ├── nodejs/         <- portable Node.js + npm-global (Gemini CLI installed here)
    │   ├── ffmpeg/         <- portable FFmpeg (bin/ subfolder)
    │   ├── git/            <- portable Git
    │   ├── vscode/         <- portable VS Code (data/ enables portable mode)
    │   └── venv/           <- Python venv (auto-created by start.bat)
    │
    ├── tools/              <- optional CLI + GUI tools (auto-detected)
    │   ├── ripgrep/ rg.exe    [installed]
    │   ├── fd/      fd.exe    [installed]
    │   ├── jq/      jq.exe    [installed]
    │   ├── bat/     bat.exe   [installed]
    │   ├── delta/   delta.exe [installed]
    │   ├── fzf/     fzf.exe   [installed]
    │   ├── sqlite/  sqlite3.exe [not installed]
    │   ├── oh-my-posh/        [installed]
    │   └── apps/             <- GUI apps (Bruno, etc.)
    │
    ├── claude/             <- Claude Code CLI
    │   ├── config/         <- CLAUDE_CONFIG_DIR (auth + global CLAUDE.md, portable)
    │   └── agent/          <- agent state (CONTEXT.md)
    │
    ├── gemini/             <- Gemini CLI (binary in nodejs/npm-global)
    │   └── config/         <- placeholder; Gemini CLI auth is NOT portable (stored in %USERPROFILE%\.gemini\)
    │
    └── data/               <- persistent data
        ├── temp/           <- isolated temp files
        └── setup-files/    <- installer archives & download links
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

## Key Bugs Fixed (for reference)

1. **HKCR wildcard hang**: `Test-Path` / `Set-ItemProperty` on `HKCR:\*\shell\...`
   treats `*` as wildcard -> enumerated all HKCR keys. Fixed: `-LiteralPath`.
   Same applies to `HKCU:\Software\Classes\*\shell\...`.

2. **for-loop PATH accumulation**: `for %%T in (...) do (set "PATH=...;%PATH%")`
   expands `%PATH%` once before loop. Fixed: individual `if exist` lines.

3. **Korean in .bat call args**: `call :LOG "한글..."` - cmd.exe parser splits
   multi-byte UTF-8 chars into tokens. Fixed: English only in all .bat files.

4. **Registry command quoting**: `cmd.exe /c ""path"" "arg""` -> empty command error.
   Fixed: `launch.ps1` as relay, uses `cmd /c call "bat" "arg"` pattern.

5. **FZF_HISTORY_DIR**: invented env var that fzf doesn't recognize. Removed.

6. **BAT_CONFIG_DIR**: wrong name. Fixed: `BAT_CACHE_PATH`.

7. **`for /f` wmic in for-loop block with `!VAR!`**: needed `setlocal EnableDelayedExpansion`.

## Current State

Last ctx-save: 2026-05-31 (see _archive/sessions/ for snapshot)

2026-06-01 개선 완료:
- VS Code 통합: `npm-global/code.cmd` 래퍼 추가 → /status "code.cmd not found" 경고 해결
- start.bat: `statusline-command.sh` → `~/.claude/` 자동 동기화 (매 시작 시)
- WSB 테스트 인프라: `_sys/test/launch-wsbtest.ps1` + `results/` 폴더 (CONVENTION.md §9)
- CHANGELOG 분리: `CLAUDE.md` 22행 이력 → `_archive/CHANGELOG.md` (~1,600 토큰/세션 절감)
- validator.md step 5b: GEMINI_MODE=ON 시 audit JSON → Gemini 사전 요약 → verifier 토큰 절약
- CONVENTION.md §9: WSB를 기본 테스트 환경으로 공식화

2026-05-31 대규모 개선 완료 (→ `_archive/CHANGELOG.md` 참조)

## Next Steps

1. **WSB 테스트 실행**: `powershell -ExecutionPolicy Bypass -File P:\_sys\test\launch-wsbtest.ps1`
2. **세션 종료**: `ctx-end` 실행 → `_archive\sessions\` 에 오늘 세션 저장
3. **Axis 스크립트 검증**: `gemini-status.bat` → `context-health.bat` → `collab-log-append.bat`
4. **Fresh PC / Zerobase setup**: Run `INSTALL.bat` (double-click) → calls `_sys\setup.ps1`

---

## Gemini CLI 활용 아키텍처

Gemini CLI는 Claude 하네스의 **보조 도구**로 동작한다. 오케스트레이터가 아닌 실행자.

```
[사용자 요청]
     │
     ▼
[Claude Code — Orchestrator + 하네스]  ← 주 루프, 메모리, Human Gate, 헌법적 권위
     │  ▲
     │  │  ← Gemini도 [REQUEST_TO_CLAUDE: TYPE]으로 역요청 가능 (수평 협력)
     ▼  │
[Gemini CLI — 대등한 협력자]
     ├── Axis-A: 대용량 분석    — portability-auditor (실용 한계 500k 토큰)
     ├── Axis-B: 버전/URL 검증  — version-check.bat (Google Search grounding)
     ├── Axis-C: 세션 요약      — ctx-end 후처리 (선택적, Flash)
     ├── Axis-D: 사전 문법 검사 — 저위험 변경 빠른 pass
     ├── Axis-D+: 중간 요약     — ctx-save 훅
     ├── Axis-E: 에이전트 감사  — agent-audit.bat → _archive/agent-audit.json
     ├── Axis-F: 스크립트 의존성 — script-deps.bat → _archive/script-deps.json
     ├── Axis-G: 커밋 초안      — git-draft.bat (콘솔 출력, 사용자 검토 후 커밋)
     ├── Axis-H: Context health — context-health.bat (JSONL size → status.json + session-handoff.json)
     └── Axis-I: Pre-flight risk — risk-scan.bat (Phase 1.5, collab-log patterns → _archive/risk-scan.json)
```

**수평 협력 원칙**: 양측이 요청하고 거절할 수 있다. Claude는 헌법적 사안(정책 파일·GEMINI_MODE·Human Gate)에서만 최종 결정권을 가진다. 자세한 통신 형식은 `CONVENTION.md §3-5` 참조.

### 금지 사항
| 금지 | 이유 |
|------|------|
| Gemini를 하네스 오케스트레이터로 사용 | CLAUDE.md·state.json 인식 불가, 메모리 없음 |
| 하네스 루프 내 반복 호출 | 1,000 req/day 소진, 루프 중단 위험 |
| 무인 자동 실행 (cron/hook) | 인증 비이식성 → 만료 시 조용한 실패 |
| GEMINI_CONFIG_DIR 설정 | v0.44.1 미인식 |
| Flash 모델로 PASS/FAIL 판정 | Claude verifier가 단일 진실 소스 |

### 관련 파일
- `_sys/context/version-check.bat` — Gemini 버전 검색 → `_archive/version-check.json`
- `_sys/context/ctx-end.bat` — 세션 종료 후 Gemini 요약 hook (없으면 건너뜀)
- `_sys/context/context-health.bat` — Axis-H: JSONL 크기 측정 → status.json + session-handoff.json
- `.claude/agents/portability-auditor.md` — Gemini Full-Corpus Scan 단계 포함
- `.claude/agents/proposer.md` — version-check.bat 호출 + 수동 폴백 지시
- `CONVENTION.md §3-4` — Gemini 호출 패턴 및 금지 패턴

---

## 하네스: Portable Dev Environment

**목표:** `_sys/` 스크립트 수정·도구 추가·이식성 감사·구조 정리·시나리오 검토를 4개 역할 + 7개 전문 에이전트 팀(총 11명)으로 처리

**트리거:** Portable Dev Environment 관련 모든 작업 → `portable-env` 스킬 사용.
단순 질문(스크립트 설명, 구조 파악 등)은 직접 응답 가능.

**하네스 스킬 목록:** portable-env, bat-ps1-engineer, add-tool, tidy-structure, audit-portability, scenario-review, propose-improvements, risk-scan, context-health

**변경 이력:** `_archive/CHANGELOG.md` 참조 (최종 업데이트: 2026-06-01)
