# Portable Dev Environment — Coding Conventions

모든 소스 코드는 이 파일의 규칙을 준수해야 한다.
verifier 에이전트는 이 파일을 기준으로 PASS/FAIL을 판정한다.

## §0 — Language Policy (CRITICAL)
All agent definitions, skill files, policy documents, and JSON artifacts: English only.
Korean permitted ONLY in:
  • Claude's console replies to the user (final text output in conversation)
  • PowerShell Write-Host output visible to user (ps1 files only)
  • Archive logs (_archive/) — historical records, not modified
  • _sys/claude/config/CLAUDE.md (user's private global preferences — excluded)
Rationale: Korean consumes 2–3× more tokens than equivalent English.
Agent MD files are loaded into context on every invocation.

## 1. 배치 파일 (.bat) 규칙

### 1-1. 언어 및 인코딩 (CRITICAL)
- **언어**: 모든 echo, 변수 이름, 주석, 경로는 **영어만** 사용한다.
- **인코딩**: 반드시 **UTF-8 (BOM 없음)** 형식을 유지한다.
  - 사유: BOM 존재 시 `cmd.exe`가 파일 첫 명령어(`setlocal`)를 `tlocal` 등으로 오인하는 버그 방지.
- **한국어 문자열 사용 절대 금지** — chcp 65001 포함, 어떤 인코딩 설정으로도 cmd.exe 파서가 다중 바이트 문자를 토큰 구분자로 처리하여 파싱이 깨진다.
- `chcp` 명령 자체도 .bat 파일 내 사용 금지 (필요 시 .ps1로 분리).

### 1-2. PATH 통합
```bat
# 올바른 패턴 — 개별 if exist 라인
if exist "%TOOLS_DIR%\ripgrep"  set "PATH=%TOOLS_DIR%\ripgrep;%PATH%"
if exist "%TOOLS_DIR%\fd"       set "PATH=%TOOLS_DIR%\fd;%PATH%"

# 금지 패턴 — for-loop 블록 내 %PATH% 확장 (한 번만 확장됨)
for %%T in (ripgrep fd) do (
    if exist "%TOOLS_DIR%\%%T" set "PATH=%TOOLS_DIR%\%%T;%PATH%"
)
```

### 1-3. 로그 함수
```bat
:LOG
echo %~1
>> "%LOG_FILE%" echo %~1
exit /b 0
```
모든 출력은 `:LOG` 호출을 통해 파일과 콘솔에 동시 기록한다.

### 1-4. 타임스탬프 (PowerShell Get-Date)
```bat
for /f "delims=" %%I in (
    'powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"'
) do set "_DT=%%I"
set "LOG_FILE=%LOG_DIR%\start_%_DT:~0,8%_%_DT:~8,6%.log"
```
`wmic os get LocalDateTime` 사용 금지 — Win11 24H2+에서 wmic 미탑재 가능.
DelayedExpansion이 필요한 경우 `setlocal EnableDelayedExpansion`을 선언한다.

### 1-6. 경로 및 특수문자 처리 (Parenthesis Bug 방지)
- **괄호 포함 경로**: 경로에 `(`, `)`가 포함될 경우, `if (...)` 또는 `for (...)` 블록 내에서 `%VAR%` 확장이 블록을 조기에 닫아버리는 버그가 있다.
- **해결책**:
  1. **블록 피하기**: `if condition command` (단일 행) 형식을 사용한다.
  2. **지연된 확장 사용**: `setlocal EnableDelayedExpansion` 선언 후 `!VAR!` 형식을 사용한다.
  3. **조건부 할당**: `if defined VAR (set "VAL=%VAR%") else (for ...)` 패턴 대신 `if not defined VAR for ...` (단일 행) 패턴을 사용하여 파서 혼동을 방지한다.
- **예시**:
```bat
# 나쁜 예 (경로에 ) 포함 시 에러)
if defined BASE_DIR (
    set "_BASE=%BASE_DIR%"
) else (
    for %%I in ("%~dp0..\..") do set "_BASE=%%~fI"
)

# 좋은 예 (안전함)
if not defined BASE_DIR for %%I in ("%~dp0..\..") do set "BASE_DIR=%%~fI"
set "_BASE=%BASE_DIR%"
```

## 2. 통합 관리 및 설치 규칙

### 2-1. 통합 매니저 (manage.bat)
모든 환경 등록/해제 및 상태 관리는 `_sys\cli\manage.bat` (Logic: `manage.py`)을 통해 수행한다.
- `manage.bat Register`: SUBST 매핑, 레지스트리 메뉴 등록, `local.config.bat` 상태 저장.
- `manage.bat Unregister`: 전역 청소(SUBST 해제, 레지스트리 제거), 상태 초기화.

### 2-2. 설치 및 복구 (install.bat)
- `install.bat`: `setup.py`를 통해 모든 런타임을 자동 다운로드 및 구성한다. (ZeroBase 지원)

### 2-3. 공간 최적화 (cleanup.bat)
- `cleanup.bat`: `cleanup.py`를 통해 Tier 1~4 단계별 정리를 수행한다.

### 2-2. 레지스트리 및 메뉴 규칙
- **키 명명**: `SandboxRun_[Drive]_[Parent]_[Leaf]` (경로 특수문자는 `_`로 치환)
- **레이블**: `Open in Sandbox: [Leaf] ([Full Physical Path] -> [SUBST]:)`
- **자동 청소**: 등록 시 이전에 사용하던 다른 경로의 키를 자동으로 찾아 제거하여 고아 키 발생을 방지한다.

### 2-3. launch.ps1 중간 계층 유지
레지스트리에서 .bat을 직접 실행하지 않는다.
`launch.ps1 → cmd /c call "start.bat" "arg"` 패턴을 유지한다.

## 3. 환경 변수 격리 규칙

### 3-1. 오버라이드 금지 목록
```
USERPROFILE    ← 절대 오버라이드 금지
APPDATA        ← 절대 오버라이드 금지
LOCALAPPDATA   ← 절대 오버라이드 금지
```
`HOST_LOCALAPPDATA=%LOCALAPPDATA%` 백업은 허용 (Claude Desktop 실행 목적).

### 3-2. 도구별 전용 env var
각 도구는 반드시 자체 전용 환경 변수를 사용한다:
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

### 3-3. 하드코딩 경로 금지
드라이브 문자(`C:\`, `D:\`)를 직접 사용하지 않는다.
모든 경로는 `%BASE_DIR%` 또는 `%SYS_DIR%` 기반 상대 경로로 작성한다.

### 3-4. Gemini CLI 호출 패턴

**Gemini 가용성은 `GEMINI_MODE` 환경변수로 판단한다** (start.bat → gemini-status.bat이 설정).
직접 `where gemini`를 호출하지 않는다.

```bat
:: 올바른 패턴 1: start.bat 세션 내 호출 (GEMINI_MODE 설정됨)
if "%GEMINI_MODE%"=="ON" (
    gemini -p "..." -o text -y > output.txt 2>&1
    if errorlevel 1 ( echo [warn] Gemini call failed - check _sys\gemini\status.json )
)
:: GEMINI_MODE=OFF 이면 조용히 건너뜀 — 파이프라인 중단 없음

:: 올바른 패턴 2: start.bat 밖 독립 실행 시 (GEMINI_MODE 미설정) 폴백
if not defined GEMINI_MODE (
    where gemini > nul 2>&1
    if not errorlevel 1 (set "GEMINI_MODE=ON") else (set "GEMINI_MODE=OFF")
)

:: 올바른 패턴 3: 비대화형 호출 필수 플래그
::   -p "..."              non-interactive prompt
::   -y                    auto-approve all tool calls (자동화 방해 방지)
::   -o text|json          output format
::   -m gemini-2.5-flash   명시적 모델 지정 (필요 시)

:: 금지 패턴: GEMINI_MODE 확인 없이 gemini 직접 호출
:: 금지 패턴: -y 없이 파일 수정 작업 호출 (프롬프트로 중단됨)
:: 금지 패턴: GEMINI_CONFIG_DIR 설정 (v0.44.1 미인식)
:: 금지 패턴: 하네스 루프 내 반복 호출 (1,000 req/day 소진)
:: 금지 패턴: 무인 자동 실행 (cron/hook) — 인증 만료 시 조용한 실패
```

**Gemini Mode env vars (start.bat → gemini-status.bat이 세션 시작 시 설정):**
```bat
set "GEMINI_MODE=ON|OFF"
set "GEMINI_OFF_REASON=ready|not_installed|not_authenticated|api_error|manual_override"
```

**Gemini 인증 관련:**
- auth 파일은 `%USERPROFILE%\.gemini\` → Directory Junction으로 `_sys\gemini\config\`에 포터블 저장
- 새 PC에서 Junction 미생성 시 재인증 필요: `gemini` 대화형 실행 → Google 계정 로그인
- `GEMINI_CONFIG_DIR` env var는 현재 버전(0.44.1)에서 **인식하지 않으므로 설정 금지**
- 수동 비활성화: `local.config.bat`에 `set "NO_GEMINI=1"` 추가 → GEMINI_MODE=OFF (manual_override)
- Gemini Mode 현재 상태 확인: `_sys\gemini\status.json`

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

### 3-5. Claude-Gemini 협업 프로토콜 v2
→ **PROTOCOL.md §C-1** 참조. (역할 구조, 통신 형식, 거절 코드, 교착 규칙, 의무 목록)

### 3-6. 3-Tier R&R
→ **PROTOCOL.md §C-2** 참조. (Tier 구조, 작업 라우팅 테이블, Passthrough Rule)

## §3-7 — Gemini-first Analysis Rule
→ **PROTOCOL.md §C-3** 참조. (Axis 선택 테이블, 대형 문서 초안 패턴)

## §3-8 — Collaboration Health Check
→ **PROTOCOL.md §C-4** 참조. (Phase 0 검증, 협업 장애 프로토콜)

## §3-9 — Session Transition Triggers
→ **PROTOCOL.md §C-5** 참조. (YELLOW/RED 임계값, Gemini Mode 전환)

## 4. 폴더/파일 네이밍 규칙

### 4-1. 폴더
- 소문자 kebab-case: `setup-files`, `data`, `env`, `tools`, `claude`, `agent`
- 예외 (컨벤션 유지): `CONVENTION.md`, `CLAUDE.md`, `README.md`

### 4-2. 스크립트 파일
- PowerShell: PascalCase (`Install_Menu.ps1`, `Remove_Menu.ps1`, `launch.ps1`)
  - `Install_Menu.ps1` 및 `Remove_Menu.ps1`은 `-BaseDir` 파라미터를 받아 호출 위치(register.bat / unregister.bat)에서 BASE_DIR을 명시적으로 전달한다.
- Batch (루트): lowercase (`register.bat`, `unregister.bat`, `install.bat`, `cleanup.bat`)
- Batch (_sys/): lowercase (`start.bat`, `ctx-save.bat`, `ctx-end.bat`)

### 4-3. tools/ 하위 폴더
형식: `tools/{tool-name}/{executable}.exe`
예: `tools/ripgrep/rg.exe`, `tools/jq/jq.exe`

## 5. CONTEXT.md and State Update Rules
→ **PROTOCOL.md §C-6** 참조.

## 6. local.config.bat — PC별 설정 패턴

### 6-1. 목적
PC마다 다른 설정(OBSIDIAN_VAULT, NO_DESKTOP, BASE_DIR_WORKSPACE 등)을
`start.bat` 직접 수정 없이 오버라이드한다. USB 이동 시 기본 설정이 깨지지 않는다.

### 6-2. 로딩 규칙
`start.bat`은 CONFIG 섹션 직후, 환경 변수 설정 전에 `local.config.bat`을 로드한다:
```bat
:: [Per-PC overrides] local.config.bat (not tracked, PC-specific)
if exist "%SYS_DIR%\local.config.bat" call "%SYS_DIR%\local.config.bat"
```

### 6-3. Git 추적 제외
- `_sys\local.config.bat`은 절대 Git에 커밋하지 않는다.
- `.gitignore`에 `_sys/local.config.bat` 명시.
- 템플릿은 `_sys\local.config.bat.template`만 추적한다.

### 6-4. 오버라이드 가능 변수
- `NO_DESKTOP` — Claude Desktop 자동 실행 차단
- `BASE_DIR_WORKSPACE` — 기본 작업 폴더 변경
- `NPM_CONFIG_PREFIX` — 시스템 npm 사용 강제 (포터블 격리 해제)
- `BASE_DIR_PHYS` — 물리적 절대 경로 (register.bat이 자동 설정; 수동 변경 금지)
- `SUBST_DRIVE_LETTER` — 고정 드라이브 문자 (register.bat이 자동 설정; 수동 변경 금지)

### 6-5. 금지
- `local.config.bat`에서 `SYS_DIR`, `BASE_DIR`, `ENV_DIR` 등 경로 상수를 재정의하지 않는다.
- 도구별 격리 변수(`PIP_CACHE_DIR` 등)는 변경 시 격리가 깨질 수 있으므로 신중하게.

## 7. 에이전트 경로 정책
→ **PROTOCOL.md §C-7** 참조.

---

## §8 — Decision Delegation Policy
→ **PROTOCOL.md §C-8** 참조.

## §9 — Testing Environment Policy (2026-06-01)

### Default: Windows Sandbox (WSB)

All script and environment tests MUST run in Windows Sandbox when possible.
Local temp directory simulation (PortaFlowTest_*) is DEPRECATED as primary method.

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

## §10 — Parallel ^& Multi-Instance Safety (2026-06-02)

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
