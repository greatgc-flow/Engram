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

### 1-5. 에러 처리
```bat
if errorlevel 1 (
    call :LOG "[Error] {description}. Check: %LOG_FILE%"
    pause & exit /b 1
)
```

## 2. PowerShell (.ps1) 규칙

### 2-1. 통합 매니저 (manage.ps1)
모든 환경 등록/해제 및 상태 관리는 `_sys\manage.ps1`을 통해 수행한다.
- `manage.ps1 -Action Register`: SUBST 매핑, 레지스트리 메뉴 등록, `local.config.bat` 상태 저장.
- `manage.ps1 -Action Unregister`: 전역 청소(SUBST 해제, 레지스트리 제거), 상태 초기화.

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

Applies to: agent-audit.bat (merged agent file), portability-auditor corpus scan, any manual call.

### §3-4-B — Gemini Refusal Detection Pattern (MANDATORY in Axis scripts)

After any gemini call (exit code 0) and before the success path, add:
  findstr /i "\[REFUSAL:" "%_OUTPUT%" > nul 2>&1
  if not errorlevel 1 (
      call "%~dp0collab-log-append.bat" "Axis-X" "script.bat" "REFUSED" "Gemini refused request"
      del "%_OUTPUT%" > nul 2>&1
      exit /b 1
  )

Axis scripts requiring this pattern: agent-audit.bat, context-health.bat, version-check.bat,
script-deps.bat, git-draft.bat, risk-scan.bat (risk-scan uses exit /b 0 — non-blocking).

### §3-4-C — Axis Token Budget

| Axis | Script | Max tokens | Claude cost | Trigger |
|------|--------|-----------|-------------|---------|
| A | portability full-corpus | ≤500k | ~0 | max 3/day |
| B | version-check.bat | ≤5k | ~0 | unlimited |
| C | ctx-end session summary | ≤10k | ~0 | 1/session-end |
| D | syntax check (inline) | ≤5k | ~0 | 1/script-edit |
| D+ | ctx-save mid-summary | ≤10k | ~0 | 1/ctx-save (opt-in) |
| E | agent-audit.bat | ≤20k | ~0 | agents/*.md change only |
| F | script-deps.bat | ≤5k | ~0 | 1/script-edit |
| G | git-draft.bat | ≤3k | ~0 | 1/commit |
| H | context-health.bat | ≤2k | ~0 | max 5/session |
| I | risk-scan.bat | ≤10k | ~0 | Phase 1.5 |

### 3-5. Claude-Gemini 협업 프로토콜 v2 (2026-05-31)

v1 (9라운드, 단방향) → **v2 (수평 협력 모델)** 로 재수립.

#### 역할 구조

두 에이전트는 **대등한 협력자**다. 어느 쪽이든 상대에게 요청하고 거절할 수 있다. 헌법적 사안에서만 Claude가 최종 권위를 가진다.

| | Claude | Gemini |
|--|--------|--------|
| 주 역할 | 오케스트레이터·정책 수호자 | 도메인 전문 실행자 |
| 헌법적 권위 | O | X (제안만 가능) |
| 세션 시작권 | O (Claude가 협업 세션 개시) | X (자기 발의 실행 금지) |
| 상대에게 요청 | Axis A-H 요청 가능 | 아래 타입으로 요청 가능 |

#### Claude에게 요청 가능한 타입 (Gemini → Claude)

| 타입 | 설명 |
|------|------|
| `WRITE_FILE` | `_sys/` 스크립트·정책 문서 편집 (Gemini 직접 수정 불가 파일) |
| `HUMAN_DECISION` | 분석 결과에서 판단 불가한 사안 사용자 에스컬레이션 |
| `POLICY_CLARIFICATION` | 컨벤션 예외·엣지 케이스 해석 요청 |
| `GIT_OPERATION` | git commit/push/branch 실행 요청 |
| `SESSION_MANAGEMENT` | /compact, ctx-save, 컨텍스트 플러시 요청 |
| `READ_AND_VERIFY` | 파일 읽기 및 내용 검증 요청 |

#### 통신 형식 (양측 공통)

```
# 요청
[REQUEST_TO_CLAUDE: TYPE] 설명
[REQUEST_TO_GEMINI: AXIS]  설명
[REFERENCE: path/to/artifact]    # 근거 파일 참조 시 함께 명시

# 거절
[REFUSAL: CODE] 사유
```

거절 코드: `OUTSIDE_CAPABILITY` | `AMBIGUOUS_REQUEST` | `POLICY_VIOLATION` | `RESOURCE_EXHAUSTED` | `CONSTITUTIONAL_BOUNDARY`

#### 이견 에스컬레이션 (직접 사용자 문의)

교착 전이라도 합의에 이르기 어렵다고 판단하면 언제든 사용자에게 직접 에스컬레이션할 수 있다.

- **Gemini → 사용자**: `[REQUEST_TO_CLAUDE: HUMAN_DECISION]` 발행 → Claude가 이견 요약과 함께 사용자에게 전달
- **Claude → 사용자**: Gemini의 이견을 요약하여 사용자에게 직접 질문
- **Claude 의무**: Gemini가 이견을 제기한 경우, 반드시 수용·거절(이유 명시)·사용자 에스컬레이션 중 하나를 선택한다. 침묵 무시 금지.

#### 교착 규칙

양측 거절이 교착 상태를 일으킬 경우 → 마지막으로 거절한 쪽이 `[REQUEST_TO_CLAUDE: HUMAN_DECISION]`을 자동 발행한다. Claude가 사용자에게 상황 설명 및 판단 요청.

#### 대화 로그 (아카이브)

Claude-Gemini 간 모든 교환은 `_archive/collab-log/YYYY-MM-DD.md`에 기록된다.

- **자동 기록**: 각 Axis 스크립트는 Gemini 호출 후 `collab-log-append.bat`을 통해 로그를 기록한다.
- **수동 기록**: Claude가 직접 Gemini를 호출하는 정책 논의·협의 라운드는 세션 중 Claude가 기록한다.
- **로그 형식**:
  ```
  ## [HH:MM:SS] Axis-X | scriptname.bat
  Status: OK | FAIL | REFUSED | ESCALATED
  Detail: ...
  ---
  ```
- **정책 논의 형식**:
  ```
  ## [HH:MM:SS] Policy Discussion | Round N
  Topic: ...
  Outcome: Agreed | Disagreement → User escalated
  Summary: ...
  ---
  ```

#### 헌법적 권위 (Claude 최종 결정, 피어 합의로 무효화 불가)

`CLAUDE.md` · `CONVENTION.md` · `GEMINI.md` · `GEMINI_MODE 변경` · `Human Gate` · `보안/안전 판단`

이 영역에서 Gemini의 이의는 **제안**이며, Claude가 수용 여부를 결정한다.

#### Claude의 의무

| 원칙 | 내용 |
|------|------|
| 오케스트레이션 주도 | Claude가 협업 세션을 시작하고 전체 흐름을 관리한다. Gemini는 자기 발의로 실행되지 않는다. |
| Gemini 요청 처리 | `[REQUEST_TO_CLAUDE]` 수신 시 수용하거나 `[REFUSAL: CODE]`로 거절한다. 무시하지 않는다. |
| 자기완결 Directive | 파일 경로, 에러 출력, 목표를 모두 포함한 명령으로 호출한다. 중간 질문을 기대하지 않는다. |
| JSON 계약 | `_archive/`의 JSON 출력만 읽는다. Gemini의 raw 대화 출력은 파싱 대상이 아니다. |
| 쿼터 보존 | Axis-A (Full-Corpus Scan) 하루 최대 3회. Axis-A 실행 중 파일 수정 병행 금지. |
| 실패 시 OFF | Gemini가 failure XML을 출력하면 GEMINI_MODE=OFF 처리 후 다음 start.bat에서 재확인. |
| 원자 Directive | 하나의 호출에 하나의 논리적 작업만 담는다. 무관한 변경 혼합 금지. |

#### Gemini의 의무

| 원칙 | 내용 |
|------|------|
| 시스템 파일 보호 | `_sys/`, `*.bat`, `*.ps1` 하네스 파일을 직접 편집하지 않는다. `[REQUEST_TO_CLAUDE: WRITE_FILE]`로 요청한다. |
| 요청 권한 행사 | Claude에게 `[REQUEST_TO_CLAUDE: TYPE]`로 요청할 수 있다. `[REFERENCE: path]`로 근거 파일을 명시한다. |
| 거절 권한 행사 | 무리하거나 원칙에 위배되는 요청은 `[REFUSAL: CODE]`로 거절한다. 이유를 명시한다. |
| Inquiry vs Directive | 모호한 요청 → Inquiry로 처리 (read-only 분석 + 제안). 명확한 실행 지시 → Directive로 처리. |
| 실패 형식 | 복구 불가 오류 시 XML: `<failure_report><reason>CODE</reason><details>...</details></failure_report>` |
| 메모리 경계 | `_sys\gemini\config\tmp\project\memory\MEMORY.md`: 기술적 How-To만 기록. What/Why 오케스트레이션 내용 기록 금지. |
| `GEMINI.md` 편집 금지 | 수정 필요 시 `[REQUEST_TO_CLAUDE: WRITE_FILE]`로 요청. 개인 메모는 MEMORY.md에. |

#### 실패 코드 목록 (failure XML `CATEGORY_CODE`)
`FILE_NOT_FOUND` | `NETWORK_ERROR` | `AMBIGUOUS_DIRECTIVE` | `TEST_VALIDATION_FAILED` | `MISSING_DEPENDENCY`

#### 실용 수치 (2026-05-31 측정)
- **Gemini 컨텍스트 품질 한계**: ~500k 토큰 (1M 이론치, 고품질은 500k 이내 권장)
- **Axis 토큰 소비**: Axis-A 100k~2.5M | Axis-B 1k~5k | Axis-G 500~3k | Axis-H 1k~5k
- **쿼터 초과 신호**: `429 Too Many Requests` (failure XML 아님, 별도 핸들링 필요)
- **쿼터 확인**: CLI 명령 없음 → Google AI Studio 웹 콘솔에서 수동 확인

#### Axis-H: Claude 컨텍스트 건강 (Claude 200k 토큰 창 기준)
| 수치 | 설명 |
|------|------|
| Claude 이론 한계 | 200,000 tokens (입력), 64,000 tokens (출력) |
| Claude 고품질 실용 한계 | ~80,000–100,000 tokens (장거리 추론 일관성 저하 시작) |
| JSONL Yellow 임계 | 600 KB (~50k 유효 토큰, 오버헤드 3x 기준) |
| JSONL Red 임계 | 1.2 MB (~100k 유효 토큰, /compact 또는 새 세션 권장) |
| 대응 절차 | context-health.bat 실행 → session-handoff.json 생성 → /compact 또는 새 세션 |
| 세션 재개 | 새 세션 시작 후 `_archive/session-handoff.json` 읽어 컨텍스트 재구성 |

### 3-6. 3-Tier R&R 분류 (2026-05-31 Claude-Gemini 2라운드 합의)

#### Tier 구조

| Tier | 구성원 | 권한 | 역할 |
|------|-------|------|------|
| **Tier 1** | Claude Code 하네스 | 헌법적 권위 | 최종 오케스트레이터, 메모리, 사용자 게이트 |
| **Tier 1.5** | 스킬 (Skills) | Tier 1 확장 | Tier 2 에이전트 조율 절차; Gemini 직접 호출 금지 |
| **Tier 2** | Claude 에이전트 (11명) | PASS/FAIL 판정 | 정책 준수 감사, 구현, 검증 |
| **Tier 3** | Gemini CLI (Axis A-H) | 도메인 분석 | 대용량 스캔, 웹 검색, 배치 분석; PASS/FAIL 판정 불가 |

#### 핵심 원칙

- **Sensor vs Judge**: Gemini는 데이터를 제공한다 ("라인 42 이식성 누수 발견"). PASS/FAIL 판정은 validator/verifier만 내린다.
- **Tier 흐름**: Tier 1 (또는 Skill) → Tier 2 에이전트 → Tier 3 Gemini. 역방향은 `[REQUEST_TO_CLAUDE]` 태그를 통해서만.
- **에이전트 내 Gemini 응답 처리**: Tier 2 에이전트가 Gemini를 호출한 경우, JSON 데이터만 소비한다. `[REQUEST_TO_CLAUDE: ...]` 태그 발견 시 즉시 Yield → Tier 1으로 미파싱 패스어스루.
- **Gemini 에스컬레이션**: `[REQUEST_TO_CLAUDE: HUMAN_DECISION]`은 coordinator를 우회하여 Tier 1에 직접 도달한다.

#### WRITE_FILE 라우팅 (Gemini → Claude → Tier 2)

| Gemini가 요청하는 파일 종류 | Tier 1이 라우팅할 에이전트 |
|--------------------------|------------------------|
| `_sys/*.bat`, `_sys/*.ps1` | **script-engineer** |
| `CLAUDE.md`, `CONVENTION.md`, `GEMINI.md`, `README.md` | **docs-writer** (헌법적 검토 후) |
| `.claude/agents/*.md`, `.claude/skills/*` | **docs-writer** (헌법적 검토 후) |
| `_archive/*.json` (Axis 출력) | Gemini 직접 작성 허용 |

#### 작업 라우팅 테이블

| 작업 | 주담당 (Tier 2/1) | Gemini 지원 (Axis) | 비고 |
|------|-----------------|-----------------|------|
| 이식성 감사 | portability-auditor | A (대용량 스캔 데이터) | Gemini 판단 = 데이터. 판정은 에이전트 |
| 스크립트 수정 | script-engineer | F (의존성 전), D (문법 후) | 전→수정→후 순서 |
| 버전 확인 | proposer | B (웹 검색 데이터) | version-check.bat |
| 에이전트 일관성 | verifier (조건부) | E (감사 데이터) | agents/*.md 변경 시만 |
| 세션 요약 | ctx-end.bat (Tier 1) | C | ctx-end가 직접 호출 |
| 커밋 메시지 | 사용자 / Tier 1 | G (초안 생성) | 사용자 검토 필수 |
| 컨텍스트 건강 | coordinator (모니터링) | H (크기 측정) | RED 시 compact/분리 |
| 문서 동기화 | docs-writer | - | Gemini 무관 |
| 시나리오 감사 | scenario-auditor | - | Gemini 무관 |
| 도구 추가 | tool-integrator | - | Gemini 무관 |

#### script-engineer Gemini 통합 워크플로우

```
스크립트 수정 요청 수신
  1. Axis-F (script-deps.bat) 실행 → 수정 대상의 의존성 파악 (impact analysis)
  2. 스크립트 수정 (Edit/Write)
  3. Axis-D 문법 검사 실행 → 수정된 파일 대상
  4. verifier에게 최종 검증 요청
```

#### verifier Axis-E 조건부 트리거

`.claude/agents/*.md` 또는 `.claude/skills/*` 파일이 변경된 경우에만 `agent-audit.bat` (Axis-E) 실행.
Axis-E 결과(`_archive/agent-audit.json`)는 verifier PASS/FAIL 판정의 INPUT으로만 사용됨 (판정 위임 불가).

#### Tier 2 Passthrough Rule for REQUEST_TO_CLAUDE Tags

When a Tier 2 agent receives Gemini output containing [REQUEST_TO_CLAUDE: ...]:
  → Do NOT process or interpret the tag.
  → Emit exactly: [ESCALATE_TO_TIER1: {original tag content}]
  → Halt current task and wait for coordinator response.
coordinator: on receiving [ESCALATE_TO_TIER1: ...], process as Claude-level [REQUEST_TO_CLAUDE: ...].

## §3-7 — Gemini-first Analysis Rule

When Claude needs analysis, route through Gemini via Axis BEFORE performing inline analysis.
Inline Claude analysis consumes the shared context window.
Gemini Axis calls use a separate token pool and preserve Claude's window for orchestration.

| Analysis Need | Axis | Script | Output |
|---------------|------|--------|--------|
| Pre-flight risk | I | risk-scan.bat | _archive/risk-scan.json |
| Script syntax/logic | D | (inline gemini -p) | console |
| Full codebase scope | A | (portability-auditor) | 03_portability_audit.json |
| Agent consistency | E | agent-audit.bat | _archive/agent-audit.json |
| External versions | B | version-check.bat | _archive/version-check.json |
| Script dependencies | F | script-deps.bat | _archive/script-deps.json |
| Commit message | G | git-draft.bat | console |
| Context health | H | context-health.bat | status.json |
| Session handoff | H | context-health.bat --force | _archive/session-handoff.json |

Gemini-first Rule: If an Axis covers the analysis need AND Gemini is ON → use Axis.
Exception: Claude may perform inline analysis ONLY for Zone A (constitutional matters)
or when Axis result is insufficient.

### §3-7-A — Gemini Draft for Large Documents

When generating a document > 100 lines:
  1. Compose requirements as a self-contained prompt (per §3-5)
  2. Run: gemini -p "Draft a [doc type]: [requirements]. Output plain markdown only." -o text -y > _workspace/02_draft_[name].md
  3. Claude reads draft and edits (review, not rewrite from scratch)

Documents < 100 lines: docs-writer writes directly.
Documents > 100 lines: always Gemini draft → Claude review.

## §3-8 — Collaboration Health Check

### Pre-Task Verification (coordinator runs at Phase 0)

Before starting any multi-phase task, verify Claude-Gemini teamwork is operational:

1. Read _sys/gemini/status.json
   → mode == "ON" AND gemini_metrics.consecutive_failures < 3

2. Read _archive/collab-log/{today}.md last 10 entries
   → No ESCALATED entries without coordinator resolution
   → REFUSED entries: check root cause before retrying

3. Evaluate:
   All clear → proceed.
   REFUSED entries → fix directive per §3-4 self-contained directive rules before retrying.
                      If capability gap: proceed without that Axis.
   Unresolved ESCALATED → process escalation first. Never skip.
   consecutive_failures >= 3 → recovery test: gemini -p "ok" -y. Succeed: reset. Fail: set mode=OFF.
   mode=OFF (non-manual) → log "Proceeding without Gemini: [reason]". All Axis calls return UNKNOWN.

### Teamwork-Broken Protocol

If Claude-Gemini collaboration fails mid-task (unexpected REFUSED, schema mismatch, repeated failure):
  1. STOP current task immediately
  2. Log failure in collab-log with full detail
  3. Run: gemini -p "Describe the last request you received and why you refused/failed it." -o text -y
  4. Diagnose root cause:
     - AMBIGUOUS_DIRECTIVE → rewrite prompt per §3-4 self-contained directive rules
     - POLICY_VIOLATION → check collaboration boundary rules
     - RESOURCE_EXHAUSTED → check quota; set mode=OFF if confirmed
     - Schema mismatch → update Axis script JSON schema in prompt
  5. Fix root cause BEFORE resuming main task
  6. If root cause unclear: report to user; do not guess-and-retry

## §3-9 — Session Transition Triggers and Guidance

### Claude Context Window Transitions

| Trigger | Condition | Action |
|---------|-----------|--------|
| YELLOW | 0.6–1.2 MB | Complete phase → ctx-save → recommend /compact before next heavy phase |
| RED | > 1.2 MB | STOP → context-health.bat --force → MUST /compact or new session |
| PRE-COMPLEX | Before task touching > 5 files | Check context_health.status first. YELLOW → /compact first |
| POST-PHASE4 | After Human Approval Gate | Natural pause → /compact before Phase 5 |
| TIME-BASED | After 3h continuous session | Recommend /compact regardless of size |

Heavy phase definition: > 5 files changed, OR Axis-A (full corpus scan), OR ≥ 3 agent MD rewrites.

### Gemini Mode Transitions

| Trigger | Condition | Action |
|---------|-----------|--------|
| Quota exhaustion | HTTP 429 | Set mode=OFF, reason=api_error; log REFUSED; proceed without Gemini |
| Auto-failure | consecutive_failures >= 3 | collab-log-append.bat auto-sets mode=OFF |
| Recovery test | After mode=OFF (non-manual) | Run: gemini -p "ok" -y. Succeed → reset mode=ON, consecutive_failures=0 |

### New Session Handoff
RED → context-health.bat --force → _archive/session-handoff.json
New session reads: session-handoff.json strategy_for_next_session + _workspace/session-primer.md

## 4. 폴더/파일 네이밍 규칙

### 4-1. 폴더
- 소문자 kebab-case: `setup-files`, `data`, `env`, `tools`, `claude`, `agent`
- 예외 (컨벤션 유지): `CONVENTION.md`, `CLAUDE.md`, `README.md`

### 4-2. 스크립트 파일
- PowerShell: PascalCase (`Install_Menu.ps1`, `Remove_Menu.ps1`, `launch.ps1`)
  - `Install_Menu.ps1` 및 `Remove_Menu.ps1`은 `-BaseDir` 파라미터를 받아 호출 위치(register.bat / unregister.bat)에서 BASE_DIR을 명시적으로 전달한다.
- Batch (루트): lowercase (`register.bat`, `unregister.bat`, `INSTALL.bat`는 예외 대문자)
- Batch (_sys/): lowercase (`start.bat`, `ctx-save.bat`, `ctx-end.bat`)

### 4-3. tools/ 하위 폴더
형식: `tools/{tool-name}/{executable}.exe`
예: `tools/ripgrep/rg.exe`, `tools/jq/jq.exe`

## 5. CONTEXT.md and State Update Rules

After Human Approval (state.json human_approval: "approved"):
  coordinator MUST update `_workspace/state.json#system_state`:
    last_completed, known_issues, gemini_mode

coordinator updates `_sys/claude/agent/CONTEXT.md` ONLY when:
  - Architecture changed (new folder structure, new Axis, new agent)
  - NOT for routine task completions

Rationale: CONTEXT.md = static topology. Dynamic session state belongs in state.json.
docs-writer does NOT own CONTEXT.md system_state — coordinator writes system_state directly to state.json.

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

### 7-1. 기본 경로 원칙 (Warning-not-Blocking)
경로가 명시적으로 지정되지 않은 경우, 에이전트는 기본 경로로 작업을 진행하며 실행을 차단하지 않는다.
기본 경로 우선순위: `_workspace/` (산출물) → `_sys/` (시스템 파일) → `BASE_DIR` (루트)

### 7-2. Warning 출력 의무
경로 변수가 미설정이면 작업 전 반드시 워닝을 출력하되 계속 진행한다:
```
[Warning] {VAR_NAME} not set - using default: {default_path}
          Override: set {VAR_NAME}={your_path} in local.config.bat
```

### 7-3. 경로 지정 에스컬레이션
특정 경로가 필요한 구조 변경은 folder-tidier에게 에스컬레이션한다.
folder-tidier가 CONVENTION.md §4 네이밍 규칙으로 경로를 결정하고 coordinator에게 보고한다.

### 7-4. 작업 범위 제한 (성능 원칙)
- 스캔 범위: BASE_DIR 기준 최대 2단계 하위까지
- 변경 범위: 요청 범위 2배 초과 시 Proposer에게 경고 에스컬레이션
- 드라이브 전체 스캔: 명시적 경로 지시 없으면 금지

---

## §8 — Decision Delegation Policy

```
ZONE A — Claude decides immediately (no analysis, no consultation):
  • Constitutional matters: CLAUDE.md / CONVENTION.md / GEMINI.md interpretation
  • GEMINI_MODE changes
  • Security decisions (auth files, USERPROFILE protection)
  • CONVENTION.md rule violations → block immediately
  • Gemini failure XML received → GEMINI_MODE=OFF
  • loop_count ≥ 3 → HALT immediately

ZONE B — Delegate to agent via harness (no Claude inline analysis):
  • _sys/*.bat / *.ps1 modification → script-engineer
  • tools/ new tool → tool-integrator
  • Folder structure → organizer → folder-tidier
  • Doc sync → organizer → docs-writer
  • Pre-flight risk → risk-scanner (Axis-I)
  • Portability audit → validator → portability-auditor
  • Scenario audit → validator → scenario-auditor
  • Agent consistency → verifier (Axis-E, conditional)
  • ROI analysis → proposer (after verifier PASS)

ZONE C — Ask user first:
  • Request scope unclear AND affects > 3 files
  • Axis-A execution planned (≤500k Gemini tokens) → confirm
  • Deletion scope > 2× requested scope
  • Constitutional boundary conflict
  • risk-scanner returns overall_risk = HIGH
  • loop_count reaches 2 → warn: "Loop 2/3. One more FAIL triggers HALT."
```
