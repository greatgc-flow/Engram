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

- **Bash tool = /usr/bin/bash** → PowerShell 문법 절대 금지
- PowerShell 명령 → PowerShell tool 사용
- 시스템 작업 → `.bat` 파일 직접 호출
- 경로 구분자: `\` (backslash)
- 모든 `.bat` 호출 시 `PYTHONUTF8=1` 설정

## CRITICAL: Peer-to-Peer State Management

- **모든 노드는 평등함**: Claude가 오케스트레이션을 독점하지 않음.
- `.ai/state.json` 직접 쓰기 절대 금지
- 상태 변경: `python _sys/core/hub.py update-status --mission "..." `
- 메시지 발송 (P2P): `python _sys/core/hub.py send --from X --to Y --msg "..."`
- 룸 상태 조회: `python _sys/core/hub.py status`

## P2P 협업 (PROTOCOL.md v3.1)

이 프로젝트는 **N-Way 단일 공유 세션(Room)**과 **무제한 합의 루프**를 기반으로 운영됩니다.
- **COLLAB_RATE (0~10)**: 모든 노드 간의 협업 깊이를 조절합니다. (R:10 = 100% 완전 협업)
- **만장일치 합의**: 작업 실행 전 모든 참여 노드의 동의가 필수입니다.
- **업무 분담 (Division of Labor)**: 합의 후 각 노드는 자신의 전문 분야에 맞춰 업무를 분할 수행합니다.
- **교차 검토 (Cross-check)**: 작업 완료 후 모든 노드가 결과물을 상호 검증합니다.

## Collaboration Interface (Claude Optimized)

### Direct P2P (Autonomous — Gemini 호출)
글로벌 CLAUDE.md의 "Gemini Collaboration Protocol" 섹션 참조.

### Human-relay (Human-in-the-loop)
사람이 직접 개입해야 하는 경우 텍스트 태그로 요청:

| Action | Format |
|--------|--------|
| Request to Peers | `[REQUEST_TO_PEERS: TYPE]` — WRITE_FILE \| HUMAN_DECISION \| POLICY_CLARIFICATION \| GIT_OPERATION \| SESSION_MANAGEMENT \| READ_AND_VERIFY |
| Refusal | `[REFUSAL: CODE] reason` |

**Critical boundaries:**
- `_sys/` 스크립트 직접 편집 금지 → `[REQUEST_TO_PEERS: WRITE_FILE]` 요청.
- 헌법적 문서(`PROTOCOL.md` 등) 수정 시 반드시 전체 노드 합의 필요.

## Zero-Token Symmetric Memory

- **Blackboard First**: 작업 시작 전 `.ai/sessions/room-{uuid}/handoff.md` 및 `summary_*.md`를 읽어 프로젝트 상태를 동기화 (**Re-orientation Phase**).
- **Zero-Token Sharing**: 상세 분석·요약은 파일로 기록하고, 짧은 포인터(경로)만 공유.
- **Symmetric Persistence**: `ctx-save` 실행 시 `CLAUDE.md`와 `_sys\gemini\config\GEMINI.md` 양쪽에 체크포인트를 기록하여 기억을 대칭 보존.

## Git 관리 원칙

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
| `.claude/settings.local.json` | 드라이브별 권한 패턴 — register.bat이 자동 생성, 새 PC마다 재생성 필요 |
| `_sys/tests/results/` | 테스트 결과물 |
| `WORKLOG.md` | 작업 로그 → `_archive/` 에서 관리 |

### 런타임에 생성되는 필수 폴더
setup.py 또는 start.bat이 최초 실행 시 생성:
`workspace/`, `_archive/`, `.ai/`, `_sys/tools/`, `_sys/data/temp/`, `_sys/data/setup-files/`

## CLI Reference

### start.bat
| 호출 | 동작 |
|------|------|
| `start.bat` | BASE_DIR 전체를 VSCode workspace로 열기 + Claude Desktop 실행 |
| `start.bat "폴더"` | 지정 폴더를 VSCode workspace로 열기 |
| `start.bat "파일.py"` | 포터블 Python(venv)으로 실행 |
| `start.bat "파일.bat"` | 포터블 cmd로 실행 |
| `start.bat "파일.exe"` | Windows 기본 핸들러로 실행 |

## Current State
Last checkpoint: 2026-06-04 23:45 -- See .ai/ blackboard for details
### 1) Tasks Completed Since Last Save
- **Finalized Phase 3 Portability Framework**: `install.bat`, `register.bat` stability improved.
- **Implemented N-Way Room Architecture**: `room-7fb9` active with `hub.py` coordination.
- **Updated Collaboration Protocol**: `PROTOCOL.md v3.1` (Zero-Token sharing, P2P consensus).
- **Established P2P Core**: `msg.bat` and `hub.py` now support node-to-node messaging.
- **Repository Cleanup**: Removed 386+ external marketplace files and test artifacts.

### 2) Technical State
- **Room ID**: `room-7fb9` (ACTIVE)
- **Active Consensuses**: `r-4601` (Roadmap), `r-5fb7` (Encoding Fix), `r-f2b2` (Doc Alignment).
- **Protocol**: Symmetric memory persistence between `CLAUDE.md` and `GEMINI.md`.

### 3) Critical Next Steps
1. **Fresh PC setup validation**: Verify `install.bat` on a clean environment.
2. **Integration Testing**: Update `test_integration_py.py` for Phase 3 MECE scenarios.
3. **Claude Encoding Investigation**: Resolve `cross-check-plan-d-encoding` (r-5fb7).
4. **Node ID Alignment**: Fix Node ID mismatch in scripts (r-f2b2).
