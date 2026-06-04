# Portable Sandbox Dev Environment
> Last updated: 2026-06-03
> This file lets Claude Code resume from where the setup conversation left off.

## What This Project Is

A fully portable Windows development environment that lives in a single folder
(USB drive or cloud). Right-click any folder -> open VS Code + Claude Desktop
with all tools (Python, Node.js, FFmpeg, Git, etc.) pre-configured.

## Final Folder Structure

```
[PortableDev]/
├── install.bat / register.bat / unregister.bat
├── README.md / CLAUDE.md / CONVENTION.md / PROTOCOL.md
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

## N-Tier Peer-to-Peer Collaboration (PROTOCOL.md v3)

이 프로젝트는 **N-Way 단일 공유 세션(Room)**과 **무제한 합의 루프**를 기반으로 운영됩니다.
- **COLLAB_RATE (0~10)**: 모든 노드 간의 협업 깊이를 조절합니다. (R:10 = 100% 완전 협업)
- **만장일치 합의**: 작업 실행 전 모든 참여 노드의 동의가 필수입니다.
- **업무 분담 (Division of Labor)**: 합의 후 각 노드는 자신의 전문 분야에 맞춰 업무를 분할 수행합니다.
- **교차 검토 (Cross-check)**: 작업 완료 후 모든 노드가 결과물을 상호 검증합니다.

## Current State
Last updated: 2026-06-03 (P2P 평등 협업 구조 대개편 완료)
- PROTOCOL.md v3.0 적용: Tier 폐지, Room 세션 도입, COLLAB_RATE 일반화.
- SYSTEM_ARCHITECTURE.md v3.0 적용: N-Way Room 아키텍처 반영.
- 3TCP v1 및 P2P 협업 코어 확립.

## Next Steps

1. **Fresh PC setup**: install.bat (double-click) → _sys\setup.ps1
2. **Integration Testing**: Phase 3 MECE 시나리오 검증 (`test_integration_py.py` 업데이트 필요)
