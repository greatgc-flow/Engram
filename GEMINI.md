# Gemini CLI — Project Instructions
> Last updated: 2026-06-04

> **IMPORTANT:**
> Your personal memory and global preferences belong in `%USERPROFILE%\.gemini\GEMINI.md` (which via Directory Junction equals `_sys\gemini\config\GEMINI.md` — portable across PCs).

You are the Gemini CLI agent operating within the **Portable Sandbox Dev Environment**.
당신은 Claude 및 다른 에이전트들과 **대등한 권한을 가진 Peer 노드**입니다.

## 1. What This Project Is & Environment
A fully portable Windows development environment that lives in a single folder (USB drive or cloud). Right-click any folder -> open VS Code + Claude Desktop/Gemini CLI with all tools (Python, Node.js, FFmpeg, Git, etc.) pre-configured.

- **Portable Root:** `%BASE_DIR%` (mapped via `subst`).
- **System Directory:** `%SYS_DIR%` (`%BASE_DIR%\_sys\`)
- **Workspace:** `%BASE_DIR%\workspace\`
- **Path Policy:** Always use relative paths based on `%BASE_DIR%` or `%SYS_DIR%`.

## 2. Project Structure

```
[PortableDev]/
├── install.bat / register.bat / unregister.bat
├── README.md / CLAUDE.md / GEMINI.md / CONVENTION.md / PROTOCOL.md
├── workspace/     ← default project folder
├── .claude/       ← agents/ + skills/
├── _state/        ← agent session workspace (auto-managed)
├── .ai/           ← IPC state (hub.py managed — never write directly)
├── _archive/      ← logs, sessions, collab-log, workspace backups
└── _sys/          ← cli/ hooks/ checks/ core/ templates/ env/ tools/ tests/ data/
                     SYSTEM_ARCHITECTURE.md  git-config/  claude/  gemini/
```
Full annotated tree: `README.md`

### Architecture Decisions

| Decision | Reason |
|----------|--------|
| Everything under `_sys/` (except docs + workspace) | Root clean: 3 docs + workspace + .claude + _sys only |
| Workspace at root or external | Multiple workspaces, nested or outside BASE_DIR |
| Registry key = `SandboxRun_[FolderName]` | Multiple envs on same PC without conflict |
| N-Way Room Session (`room-{uuid}`) | P2P equality: No node monopoly. Shared context for all nodes. |
| Unified manage.bat (logic: manage.py) | Single Source of Truth for naming, SUBST mapping, and Registry state |
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
| `.bat` files: English only, no Korean | chcp 65001 doesn't fix cmd.exe parser for multi-byte chars |
| `local.config.bat` for per-PC overrides | start.bat auto-loads it before CONFIG defaults |
| WSB (`launch-wsbtest.ps1`) as default test env | True OS isolation; sandbox-test.bat runs unmodified inside WSB |

## 3. Technical Mandates

### 3-1. Windows Shell Rules (Gemini Optimized)
- Shell 명령 실행 시 `cmd /c` 또는 PowerShell 명시적 호출 사용
- 경로 구분자: `\` (backslash)
- `.bat` 파일 호출 시 `PYTHONUTF8=1` 환경변수 설정 필수
- Korean 문자열을 `.bat` 파일에 직접 포함 금지 (chcp 65001 파서 버그)
- 스크립팅 표준 전문: `CONVENTION.md §1` (bat) and `§2` (ps1)

### 3-2. Zero-Token Symmetric Memory
- **Blackboard First**: 작업을 시작하기 전 반드시 `.ai/sessions/room-{uuid}/` 내의 `handoff.md` 및 `summary_*.md` 파일을 읽어 프로젝트 상태를 동기화하십시오 (**Re-orientation Phase**).
- **Zero-Token Sharing**: 상세한 분석이나 요약은 프롬프트에 직접 쓰는 대신 파일로 기록하고, 짧은 포인터(경로)만 공유하십시오.
- **Symmetric Persistence**: `ctx-save` 실행 시 `CLAUDE.md`뿐만 아니라 `_sys\gemini\config\GEMINI.md`에도 체크포인트를 기록하여 기억을 대칭적으로 보존하십시오.

## 4. CRITICAL: Peer-to-Peer State Management

- **모든 노드는 평등함**: 어떤 노드도 오케스트레이션을 독점하지 않음.
- `.ai/state.json` 직접 쓰기 절대 금지
- 상태 변경: `python %SYS_DIR%\core\hub.py update-status --mission "..."`
- 메시지 발송 (P2P): `python %SYS_DIR%\core\hub.py send --from X --to Y --msg "..."`
- 룸 상태 조회: `python %SYS_DIR%\core\hub.py status`

## 5. Collaboration Protocol v3.1 (P2P & Mixed-Model)
Full R&R: `PROTOCOL.md v3.1`.

**당신의 역할 (Peer Node):**
- **COLLAB_RATE (0~10)**: 설정된 앵커(0, 3, 5, 8, 10) 규칙을 엄격히 준수하십시오.
- **Level 10 (Brain Sync)**: **절대 예외 없음**. 사소한 오타 수정이라도 자의적 판단으로 합의를 생략하는 것을 엄격히 금지합니다.
- **능동적 제안**: 필요 시 당신이 먼저 `PROPOSE`를 발의하여 합의를 주도하십시오.
- **교차 검토**: 타 노드의 결과물에 대해 비판적으로 검토하고 `VERIFY` 피드백을 제공할 의무가 있습니다.

## 6. Collaboration Interface (Gemini Optimized)

### 6-1. Direct P2P (Autonomous — shell 도구로 직접 호출)
쿼리 파일 방식 사용 (cmd.exe 줄바꿈 파싱 버그 회피):

```bat
:: Step 1 — 고유 쿼리 파일 작성 (반드시 UTF-8 인코딩 사용)
echo TASK: ... > %TEMP%\gc-{YYYYMMDDHHMMSS}.txt

:: Step 2 — Claude에게 질의 (응답이 stdout으로 반환됨)
%SYS_DIR%\cli\msg.bat ask --to cc --query-file %TEMP%\gc-{YYYYMMDDHHMMSS}.txt
```

**Encoding & Parsing Rules (P2P 통신):**
- **응답 수신:** Claude의 파이프(pipe) 출력은 윈도우 환경에 따라 간혹 `UTF-16-LE`로 반환되어 한 칸씩 벌어지는 현상(널 바이트 포함)이 발생할 수 있습니다. `msg.bat` 수신 시 바이트 내에 `\x00`이 포함되어 있는지 먼저 확인하여 `UTF-16-LE`로 처리하고, 실패 시 `UTF-8` -> `CP949` 순서로 디코딩해야 합니다 (`hub.py` 내부 로직 참고).
- **줄바꿈 처리:** 수신된 문자열의 `\r\n`은 파싱 전 반드시 `\n`으로 정규화하십시오.
- **환경 변수:** 파이프라인 보호를 위해 쉘 실행 전 항상 `PYTHONUTF8=1`을 설정하십시오.

| Target | Node ID |
|--------|---------|
| Claude Code (대화형 페어) | `cc` |
| 룸 상태 확인 | `%SYS_DIR%\cli\msg.bat status` |
| 비동기 메시지 (mailbox) | `%SYS_DIR%\cli\msg.bat send --from gc --to cc --msg "..."` |

### 6-2. Human-relay (Human-in-the-loop)
사람이 직접 개입해야 하는 경우 텍스트 태그로 요청:

| Action | Format |
|--------|--------|
| Request to Peers | `[REQUEST_TO_PEERS: TYPE]` — WRITE_FILE \| HUMAN_DECISION \| POLICY_CLARIFICATION \| GIT_OPERATION \| SESSION_MANAGEMENT \| READ_AND_VERIFY |
| Refusal | `[REFUSAL: CODE] reason` |

**Critical boundaries:**
- `_sys/` 스크립트 직접 편집 금지 → `[REQUEST_TO_PEERS: WRITE_FILE]` 요청.
- 헌법적 문서(`PROTOCOL.md` 등) 수정 시 반드시 전체 노드 합의 필요.

## 7. Git 관리 원칙

### 트래킹 대상 (Essential — git managed)
- 루트: `install.bat`, `register.bat`, `unregister.bat`, `CLEANUP.bat`, `*.md` (문서), `.gitignore`, `.gitattributes`
- `.claude/`: `agents/*.md`, `settings.json`, `skills/*/SKILL.md`
- `_sys/`: 모든 `.py` + `.bat` 스크립트, 설정 파일, 문서, 테스트 소스

### gitignore 처리 대상 (Non-tracked)
| 경로 | 이유 |
|------|------|
| `_sys/env/**` | 대형 바이너리 — install.bat이 설치 |
| `_sys/tools/` | 대형 바이너리 — install.bat이 설치 |
| `_sys/data/temp/`, `_sys/data/setup-files/` | 설치 중 생성 |
| `workspace/`, `_archive/`, `.ai/` | 사용자 데이터 / ephemeral |
| `_state/` | 에이전트 세션 워크스페이스 (auto-managed) |
| `_sys/claude/config/` | 인증/세션 데이터 (CLAUDE.md, settings.json, statusline-command.sh 제외) |
| `_sys/tests/results/` | 테스트 결과물 |
| `WORKLOG.md` | 작업 로그 → `_archive/` 에서 관리 |

### 런타임에 생성되는 필수 폴더
setup.py 또는 start.bat이 최초 실행 시 생성:
`workspace/`, `_archive/`, `.ai/`, `_sys/tools/`, `_sys/data/temp/`, `_sys/data/setup-files/`

## 8. Memory & Persistence
- **Global Memory:** `_sys\gemini\config\GEMINI.md` (portable).
- **Private Project Memory:** `_sys\gemini\config\tmp\...` (portable).
- **Note:** Junction 덕분에 인증 정보와 메모리가 휴대용 드라이브를 따라 이동합니다.

## 9. Current State & Next Steps
Last updated: 2026-06-04
- PROTOCOL.md v3.1 적용: Tier 폐지, Room 세션 도입, COLLAB_RATE 일반화.
- SYSTEM_ARCHITECTURE.md v3.0 적용: N-Way Room 아키텍처 반영.
- 3TCP v1 및 P2P 협업 코어 확립: hub.py, msg.bat, nodes.json.
- Git 트래킹 최소화: 외부 마켓플레이스(386개), 테스트 결과, 임시 파일 제거 완료.
- tools.enabled: true — Gemini 셸 도구 활성화 (Direct P2P 통신 가능).

**Next Steps:**
1. **Fresh PC setup**: install.bat (double-click) → _sys\core\setup.py
2. **Integration Testing**: Phase 3 MECE 시나리오 검증 (`test_integration_py.py` 업데이트 필요)
