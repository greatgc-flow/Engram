# SYSTEM ARCHITECTURE — Portable Dev Environment (P2P Collab v3)

> 이 문서는 `_sys/` 시스템 레이어의 설계 결정과 평등 권한 기반의 P2P 협업 구조를 설명합니다.

---

## 1. 레이어 구조

```
[사용자 / All AI Nodes]
        ↓
[진입점] _sys/cli/claude.bat  gemini.bat  msg.bat  manage.bat  cleanup.bat  install.bat
        ↓ (PORTABLE_ROOT + venv PATH 주입)
[로직]   _sys/core/hub.py  setup.py  manage.py  cleanup.py
        ↓
[상태]  .ai/  ← 프로젝트 로컬 AI 상태 (mailbox.json, state.json, sessions/)
        ↓
[라이프사이클] _sys/hooks/ (session-end, log-write, ai-check, collab-log, ctx-save, ctx-end)
[분석]  _sys/checks/ (check-risk, check-agents, check-deps, check-health, check-versions)
[도구]  _sys/cli/ (git-draft, batch-review) + _sys/hooks/ (archive-data)
```

## 2. hub.py — P2P 메시지 브로커 (Facade 패턴)

**Raw Data 철학**: 모든 출력은 손실 없는 Pretty-print Markdown.
**평등 권한**: 모든 노드는 동등한 권한으로 아래 액션을 호출할 수 있음.

### Write 액션 (filelock 적용)

| 액션 | 설명 | Lock |
|------|------|------|
| `init-session --agent A [--room R]` | Room 생성 또는 참여 (room-{uuid} 발급) | state.lock |
| `end-session --agent A` | handoff.md 갱신, mailbox 정리 | state.lock + mailbox.lock |
| `send --from A --to B --msg TEXT` | N-Way Room 내 메시지 발송 | mailbox.lock |
| `mark-read --target A` | 읽음 처리 | mailbox.lock |
| `append-log --axis X --status S` | .ai/log.jsonl 기록 | log.lock |
| `update-status --mission T` | 미션/상태 갱신 (합의 결과 반영) | state.lock |

### Read 액션 (Lock-Free)

| 액션 | 설명 |
|------|------|
| `check --target A` | 받은 메시지 전문 Pretty-print |
| `status` | Room 상태 전체 + handoff 원문 Pretty-print |

### 동기 액션

| 액션 | 설명 |
|------|------|
| `ask --to NODE --query TEXT` | 특정 노드에 대한 동기 질의 (subprocess) |

---

## 3. .ai/ 폴더 구조 (N-Way Room)

```
.ai/
├── mailbox.json          메시지 큐 (Room 참여자 전체 공유)
├── state.json            Room ID + 참여 노드(members) 리스트
├── log.jsonl             실행 로그
├── .lock/                병렬 접근 제어용 파일 락
└── sessions/
    └── room-{uuid}/      N-Way 단일 공유 세션 컨텍스트
        └── handoff.md    룸 공통 메모리 (FIFO)
```

## 4. Room ID 및 P2P 통신

- **Room ID**: `room-{uuid}` (예: `room-a1b2`).
- **P2P 원칙**: 특정 노드가 오케스트레이션을 독점하지 않으며, 모든 메시지는 `from` 노드에서 `to` 노드(또는 `broadcast`)로 평등하게 전달됨.
- **Context 공유**: 동일 Room에 속한 모든 노드는 동일한 `handoff.md`를 읽고 쓰며 컨텍스트를 동기화함.

## 5. handoff.md 구조 (단일 룸 공통)

```markdown
## [GOAL]               ← 룸 전체 최종 목표
## [RECENT_COMPLETED]   ← 참여 노드 전체의 성과 (FIFO)
## [PENDING_ISSUES]     ← 현재 해결이 필요한 이슈
## [KEY_DECISIONS]      ← 만장일치로 합의된 결정 사항
## [CONSENSUS_HISTORY]  ← 무제한 합의 라운드 이력
```

## 6. Batch 파일 구조 원칙

- **≤5줄 원칙**: 로직 없음. 모든 로직은 `_sys/core/*.py` 또는 전용 `.py` 모듈로 위임.
- **PORTABLE_ROOT**: `%~dp0` 기반 동적 계산 — 드라이브 레터 하드코딩 금지.
- **예외**: `start.bat` — 부모 프로세스 환경변수 설정 필수로 bat 유지 (SUBST 복원 + PATH/VENV 주입).

## 7. Collaborative Axis (일반화된 분석 도구)

| Axis | 트리거 스크립트 | 용도 |
|------|--------------|------|
| A | portability-auditor | 이식성 정밀 감사 (GC 지원) |
| I | `check-risk.bat` | 사전 위험 스캔 (GC 지원) |
| H | `check-health.bat` | 컨텍스트 건강도 점검 (CC/GC 협업) |
| G | `git-draft.bat` | 커밋 메시지 초안 생성 |

---

## 8. 경로 빠른 참조

| 컴포넌트 | 경로 |
|---------|------|
| 코어 파이썬 | `_sys/core/hub.py` |
| CLI 진입점 | `_sys/cli/claude.bat`, `gemini.bat`, `msg.bat` |
| AI 상태 | `.ai/state.json` (hub.py 경유만 쓰기) |
| 룸 세션 | `.ai/sessions/room-*/handoff.md` |
| 테스트 | `_sys/tests/run-tests.bat` |
