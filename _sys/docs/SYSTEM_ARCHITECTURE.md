# SYSTEM ARCHITECTURE — Portable Dev Environment

> 이 문서는 `_sys/` 시스템 레이어의 설계 결정과 컴포넌트 구조를 설명합니다.
> 최신 변경 이력은 `WORKLOG.md` 참조.

---

## 1. 레이어 구조

```
[사용자 / Gemini CLI]
        ↓
[진입점] _sys/cli/cla.bat  gem.bat  msg.bat
        ↓ (PORTABLE_ROOT + venv PATH 주입)
[코어]  _sys/core/hub.py  ← 모든 IPC 로직의 단일 진입점 (Facade)
        ↓
[상태]  .ai/  ← 프로젝트 로컬 AI 상태 (mailbox.json, state.json, sessions/)
        ↓
[라이프사이클] _sys/hooks/ (session-end, append-log, check-gate, ctx-save, ctx-end)
[분석]  _sys/scans/ (scan-risk, audit, deps, health, env)
[도구]  _sys/tools/ (git-draft, batch-review, archive-data)
```

## 2. hub.py — 11개 액션 (Facade 패턴)

**Raw Data 철학**: `--format llm` 없음. 모든 출력은 손실 없는 Pretty-print Markdown.
**단일 통로**: `msg.bat` → `hub.py %*` (동기 `ask` + 비동기 `send/check`)

### Write 액션 (filelock 적용)

| 액션 | 설명 | Lock |
|------|------|------|
| `init-session --agent A` | SID 발급 (1줄 출력, bat 캡처용), pair 생성/join | state.lock |
| `end-session --agent A` | handoff.md 갱신, mailbox 정리 | state.lock + mailbox.lock |
| `send --from A --to B --msg TEXT` | 비동기 메시지 발송 | mailbox.lock |
| `mark-read --target A [--all\|--id N]` | 읽음 처리 | mailbox.lock |
| `append-log --axis X --script N --status S --detail D` | .ai/log.jsonl 기록 | log.lock |
| `archive-file --name N --file PATH` | _archive/{n}-YYYYMMDD.json + latest | 없음 |
| `update-status --mission T [--blocked B] [--phase P]` | 미션/상태 갱신 | state.lock |

### Read 액션 (Lock-Free)

| 액션 | 설명 |
|------|------|
| `check --target A` | 받은 메시지 전문 Pretty-print |
| `status` | 세션 상태 전체 + handoff 원문 Pretty-print |
| `check-gate [--agent gemini\|claude]` | Gemini 가용 여부 확인 |

### 동기 액션

| 액션 | 설명 |
|------|------|
| `ask --to gemini\|claude --query TEXT` | 동기 질의 (subprocess + ANSI strip) |
| `ask --to gemini\|claude --query-file PATH` | 파일 읽어 질의 후 자동 삭제 |

### Pretty-print 출력 예시

```markdown
### [INBOX] gemini — 2개 미읽음

**[1]** From: **claude** | 2026-06-03T14:32
Phase 1 완료. hub.py 리팩토링 진행해줘.

---

### [SESSION STATUS]
**Pair**: c2b5-g4707
**Mission**: hub.py 리팩토링
**Phase**: 3
**Blocked**: 없음

### [HANDOFF]
## [GOAL]
- Portable Dev Environment AI 협업 구조 완성
```

## 3. .ai/ 폴더 구조

```
.ai/
├── mailbox.json          메시지 큐 (ephemeral)
├── state.json            세션 pair + 미션
├── log.jsonl             Axis 실행 로그
├── .lock/
│   ├── mailbox.lock
│   ├── state.lock
│   └── log.lock
└── sessions/
    └── c{4}-g{4}/
        └── handoff.md    ≤3000토큰 (FIFO)
```

**.ai/ 탐색 순서**: CWD → .git 상향 탐색 → 없으면 CWD에 생성.
**.ai/는 .gitignore에 포함** — 로컬 런타임 상태, 공유 불필요.

## 4. 세션 pair ID 형식

- `c{4}` = Claude 세션 ID (c + UUID 앞 4 hex)
- `g{4}` = Gemini 세션 ID (g + UUID 앞 4 hex)
- pair = `c{4}-g{4}` (예: `c2b5-g4707`)

## 5. handoff.md 구조 (≤3000토큰)

```markdown
## [GOAL]
- (고정, 수동 갱신, 최대 3줄)

## [RECENT_COMPLETED]
- 2026-06-03 claude: hub.py MVP 완성
- ...  (FIFO, 최대 5개)

## [PENDING_ISSUES]
- ⚠ (최대 3개)

## [KEY_DECISIONS]
- Batch ≤5줄, 로직은 hub.py  (최대 3개)
```

## 6. Batch 파일 구조 원칙

모든 배치 파일:
```bat
@echo off
for %%I in ("%~dp0..\..") do set "PORTABLE_ROOT=%%~fI"   :: 또는 적절한 단계
set "PYTHONUTF8=1"
set "PATH=%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PATH%"
python "%~dp0..\core\hub.py" [action] [args]
```

- **≤5줄 원칙**: 로직 없음, hub.py 위임만
- **P:\ 하드코딩 금지**: PORTABLE_ROOT 동적 계산
- **venv PATH 필수**: 호스트 Python 오염 방지

## 7. 스캔 결과 아카이브 패턴

각 scan 스크립트는 완료 후 자동으로:
1. `_archive/{name}.json` (즉시 출력)
2. `_archive/{name}-YYYYMMDD.json` (날짜별 보존, archive-data.bat)
3. `_archive/{name}-latest.json` (항상 최신, agent MD 참조 경로)

## 8. 경로 빠른 참조

| 컴포넌트 | 경로 |
|---------|------|
| 코어 파이썬 | `_sys/core/hub.py` |
| CLI 진입점 | `_sys/cli/cla.bat` `gem.bat` `msg.bat` |
| 라이프사이클 훅 | `_sys/hooks/session-end.bat` `ctx-save.bat` `ctx-end.bat` |
| Axis 스캔 | `_sys/scans/scan-{risk,audit,deps,health,env}.bat` |
| 수동 도구 | `_sys/tools/{git-draft,batch-review,archive-data}.bat` |
| 테스트 | `_sys/test/run-tests.bat` (--unit|--integration|--all) |
| AI 상태 | `.ai/state.json` (hub.py 경유만 쓰기) |
| 아카이브 | `_archive/scan-{name}-latest.json` |
