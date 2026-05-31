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

2026-05-31 대규모 개선 완료:
- MECE 에이전트 팀 영문화 완료 (11개 에이전트 + 9개 스킬)
- 토큰 효율화: ctx-save.bat AI 서브프로세스 제거, 세션 프라이머 패턴, 루프 델타 프로토콜
- Axis-I (risk-scan.bat) 구현 + risk-scanner 에이전트 추가
- Gemini 건강 메트릭 (gemini_metrics + ai_health) status.json 추가
- 협업 건강 체크 (CONVENTION.md §3-8) + 세션 전환 SOP (§3-9) 추가
- 결정 위임 정책 (CONVENTION.md §8, Zone A/B/C) 수립
- bat-ps1-engineer 스킬 rename, context-health 스킬 신규 추가

## 이전 상태 (2026-05-31 이전):
- Gemini 협업 정책 v2 확정: 수평 협력 모델 (역요청·거절 권한, 교착 규칙, 헌법적 권위 분리)
- 3-Tier R&R 확정: Sensor vs Judge 원칙, 작업 라우팅 테이블, script-engineer/verifier/coordinator 통합
- Axis-D+/E/F/G/H 구현 완료 (collab-log-append.bat, agent-audit/script-deps/git-draft/context-health.bat 신규)
- 전 Axis 스크립트에 대화 로그(collab-log/) 아카이브 추가
- CONVENTION.md §3-5/§3-6, GEMINI.md §4-1 최신화

## Next Steps

1. **세션 종료**: `ctx-end` 실행 → `_archive\sessions\` 에 오늘 세션 저장
2. **Axis 스크립트 실 동작 검증**: `gemini-status.bat` → `context-health.bat` → `collab-log-append.bat` 순서로 실행 확인
3. **Fresh PC / Zerobase setup**: Run `INSTALL.bat` (double-click) → calls `_sys\setup.ps1`
4. **Register this PC**: Run `register.bat` (double-click) → assigns SUBST drive + registers context menu

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

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-05-29 | 초기 구성 | 전체 | 신규 구축 |
| 2026-05-29 | folder-tidier + scenario-auditor 에이전트 추가 | agents/, skills/ | MECE 구조·시나리오 감사 |
| 2026-05-29 | 하네스 전체 구축 완료 | .claude/agents/ × 7, .claude/skills/ × 6 | harness 플러그인 기반 에이전트 팀 |
| 2026-05-29 | Collaboration Loop + verifier + CONVENTION.md | portable-env 스킬, verifier.md | 자율 협업·품질 게이트 프로토콜 |
| 2026-05-29 | 폴더 구조 전면 정리 | 루트 전체 → _sys/ 통합 | MECE 루트, Rust 제거, HKCU, setup.ps1 |
| 2026-05-29 | 하네스 감사 PASS + P1 패치 | start.bat, ctx-save/end.bat, setup.ps1, INSTALL.bat | wmic→Get-Date 교체, -Silent 수정, 루트 INSTALL.bat 추가 |
| 2026-05-29 | P2/P3 개선: 에러 가시성 + 하네스 env | start.bat, setup.ps1, ctx-save/end.bat, local.config.bat.template | CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS, local.config, 컴포넌트별 try/catch, -LiteralPath, 인증 사전 검사 |
| 2026-05-29 | 하네스 4-Role 아키텍처 도입 | organizer, validator, proposer 에이전트 + propose-improvements 스킬 + portable-env 오케스트레이터 전면 업데이트 | MECE 4역할, 루프 3회 한도, Human-in-the-loop, state.json I/O 표준화 |
| 2026-05-30 | 전체 MECE 재구성: register.bat/unregister.bat 추가, SUBST 고정 할당, 자가치유 폐지, ctx 세션 파일 프로젝트명 분리 | CLAUDE.md, README.md, CONVENTION.md, CONTEXT.md, 루트 파일 구조 | 사용자 시나리오 MECE 완결, register/unregister 명시 진입점, 재부팅 후 SUBST 자동 복원 |
| 2026-05-30 | Gemini CLI 통합 (@google/gemini-cli → nodejs/npm-global), _archive 롤링 데이터 통합 (logs+sessions), start.bat LOG_DIR/SESSION_DIR 경로 변경, ctx-save/ctx-end SES_DIR 수정 | start.bat, ctx-save.bat, ctx-end.bat, CLAUDE.md | 롤링 데이터 한 곳 집중, Gemini CLI PATH 자동 포함 |
| 2026-05-30 | Gemini 활용 아키텍처 정의: 4-Axis MECE, version-check.bat, ctx-end 요약 hook, portability-auditor Gemini scan, CONVENTION §3-4 Gemini 호출 패턴 | CLAUDE.md, CONVENTION.md, portability-auditor.md, proposer.md, ctx-end.bat, version-check.bat(신규) | Gemini = 보조 도구(오케스트레이터 아님), Claude 하네스 주 루프 유지 |
| 2026-05-30 | 아키텍처 단순화 및 MECE 강화: 4개 스크립트→manage.ps1 통합, 고아 키 자동 청소, SUBST 경로 치환 버그 수정, 메뉴 레이블 가독성 개선 | _sys/manage.ps1, register/unregister.bat, start.bat, README, CONVENTION | 스크립트 구조 일목요연화, 등록 상태 추적(MENU_REG_KEY), 드라이브 루트 설치 완벽 지원 |
| 2026-05-31 | Gemini 전면 검토: on/off 지표 강화, 문서 정합성 수정, Axis-D+/E/F/G 구현, D2 ping opt-in, D5 보호 지시문 | gemini-status.bat, ctx-save/end.bat, agent-audit/script-deps/git-draft.bat(신규), GEMINI.md, CONVENTION.md | api_error 피드백 루프, 7-Axis 완성 |
| 2026-05-31 | Claude-Gemini 9라운드 협업 정책 수립: 역할 경계, failure XML 형식, 메모리 분리, 쿼터 전략, 실용 수치 | CONVENTION.md §3-5(신규), GEMINI.md §4-1(신규), CLAUDE.md Axis 업데이트 | Claude=오케스트레이터 단독, Gemini=Directive 기반 실행, 500k 토큰 품질 한계 확인 |
| 2026-05-31 | Axis-H 추가: context-health.bat (JSONL 크기 측정, 임계 초과 시 session-handoff.json 생성) | context-health.bat(신규), CLAUDE.md, GEMINI.md §4, CONVENTION.md §3-5 | Claude 200k 컨텍스트 한계 대응 — Gemini 3라운드 협의로 설계 확정 |
| 2026-05-31 | 협업 정책 v2: 수평 협력 모델 (Gemini 역요청·거절 권한, 교착 규칙, 헌법적 권위 분리) | CONVENTION.md §3-5 전면 재작성, GEMINI.md §4-1, CLAUDE.md 아키텍처 다이어그램 | Gemini와 2라운드 협의 후 양측 합의로 수립 |
| 2026-05-31 | 직접 이견 에스컬레이션 + 대화 로그 아카이브: collab-log-append.bat, 전 Axis 스크립트 로그 추가 | collab-log-append.bat(신규), 7개 Axis 스크립트 수정, CONVENTION.md §3-5, _archive/collab-log/ | 사용자 지시: 양측이 언제든 사용자에게 직접 문의 가능, 대화 로그 보존 |
| 2026-05-31 | 3-Tier R&R 확정 (Gemini 2라운드 협의): Sensor vs Judge 원칙, 작업 라우팅 테이블, script-engineer/verifier/coordinator 통합 | CONVENTION.md §3-6(신규), script-engineer.md/verifier.md/coordinator.md/GEMINI.md | 하네스·에이전트·스킬·Gemini 역할 경계 명확화 |
| 2026-05-31 | 토큰 효율화 대규모 개선: 언어 통일(영문화), 결정 위임(§8), 에이전트 MECE 수정, Axis-I 추가, Gemini 건강 메트릭, 세션 전환 SOP, bat-ps1-engineer rename, context-health 스킬 | 전체 .claude/agents/ + skills/ + _sys/context/*.bat + status.json + CONVENTION.md | 세션당 토큰 ~80-85% 절감 목표 |
