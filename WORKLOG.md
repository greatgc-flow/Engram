# WORKLOG — Portable Dev Environment

> 1인 개발 환경의 주요 아키텍처 결정 및 변경 이력.
> 상세 커밋 이력은 `git log`; 이전 세션 요약은 `_archive/sessions/` 참조.

---

## 2026-06-03 — MECE + 명칭 일반화 (Gemini 4-round 협의 완료)

**목표**: 전체 파일/폴더 구조 MECE 정리 + 처음 보는 개발자가 이름만으로 목적 파악 가능한 수준으로 일반화.  
Gemini Round 1~4 협의 완료 후 구현.

### Phase A — 구조 정리
| 변경 | 내용 |
|------|------|
| `_sys/tools/git-draft.bat`, `batch-review.bat` | → `_sys/cli/` (사용자 직접 실행 CLI) |
| `_sys/tools/archive-data.bat` | → `_sys/hooks/` (Axis 스크립트 내부 헬퍼) |
| `_state/collab/` | 빈 폴더 삭제 |
| `_archive/scans/` | 신규 생성 + agent-audit.json, script-deps.json 이동 |
| `_archive/workspace-*-legacy-*.json` (6개) | 삭제 |

### Phase B — 폴더/파일명 rename
| 구 이름 | 신 이름 | 기준 |
|---------|---------|------|
| `_sys/scans/` | `_sys/checks/` | "scans"는 보안 스캔 연상; "checks"가 점검 스크립트 의미 명확 |
| `scan-env.bat` | `check-versions.bat` | "env" 모호; "versions" 목적 명확 |
| `scan-audit.bat` | `check-agents.bat` | 무엇을 audit? "agents" 대상 명확 |
| `scan-health/risk/deps.bat` | `check-health/risk/deps.bat` | prefix 일관성 |
| `_sys/docs/` | `_sys/templates/` | 읽는 docs가 아닌 복사용 템플릿 |
| `_sys/git_config/` | `_sys/git-config/` | 디렉토리 관례 (언더스코어 → 하이픈) |
| `_sys/test/` | `_sys/tests/` | 복수형이 업계 관례 |
| `_state/` | **유지** | Gemini Round1 5/5 + Round3 DISAGREE 신호 |
| `cli/cla.bat` | `claude.bat` | "cla"는 프로젝트 전용 약어 |
| `cli/gem.bat` | `gemini.bat` | "gem"은 Ruby gem 연상 |
| `hooks/append-log.bat` | `log-write.bat` | 동사-목적어 패턴 |
| `hooks/check-gate.bat` | `ai-check.bat` | "gate" 불명확; AI 서비스 체크임이 명확 |
| `hooks/collab-log-append.bat` | `collab-log.bat` | "append" 생략해도 맥락 유지 |
| `INSTALL.bat`, `CLEANUP.bat` | `install.bat`, `cleanup.bat` | 소문자가 현대 cross-platform 표준 |

### Phase C/D — 배치파일 + 문서 현행화
- `start.bat` PATH 블록: scans→checks, git_config→git-config 반영
- `check-*.bat` 5개: 새 경로(ai-check, collab-log, archive-data) 반영
- `git-draft.bat`, `batch-review.bat`: 이동 후 훅 경로 수정
- 문서: GEMINI.md, CLAUDE.md, CONVENTION.md, PROTOCOL.md, CONTEXT.md, coordinator.md
- Skills: gemini, portable-env, context-health, risk-scan, propose-improvements
- Agents: risk-scanner, proposer, verifier

---

## 2026-06-03 — 테스트 클린업 (stale refs 제거)

**목표**: `_sys/context/` 삭제 이후 남겨진 stale 테스트 참조 정리.

### 변경 요약

| 파일 | 변경 내용 |
|------|----------|
| `sandbox-test.bat` | xcopy: `context/` → `hooks/+scans/+cli/+tools/`; 스캔 파일 레거시 alias; gemini-consult 8개 `:SK` 대체; ephemeral-session 루프 `scan-*.bat` 경로 수정; `_GEMINI_SESSION_FLAG` → `check-gate` 체크; gemini-session-read 4개 `:SK` 대체 |
| `local-test.bat` | GROUP 16: gemini-consult 7개 `:SK` 대체; ctx-end 경로 `context/→hooks/`; ephemeral/interactive/session-read 동일 정리 |
| `hub.py` | empty-inbox 출력 Korean → English (`inbox empty`) — PS 5.1 CP949/UTF-8 충돌 방지 |
| `test_ipc.ps1`, `test_scenarios.ps1` | `새 메시지 없음` → `inbox empty` |
| `test_hub.py`, `test_hub_edge.py` | 동일 |
| `CONVENTION.md §10-1` | `session-master.json` → `.ai/mailbox.json` (hub.py 경유) |

### 테스트 결과

- **Unit (pytest)**: 74/74 PASS
- **Integration (PS1, pwsh)**: 31/31 PASS (test_ipc×10 + test_scenarios×7 + test_tools_path×8 + test_session_flow×6)
- **총합**: 105 tests ALL PASS

---

## 2026-06-03 — 3TCP v1 프로토콜 (hub.py Phase A-D)

**목표**: N-node 만장일치 협의체 + 분업 협업 프로토콜 설계 및 구현.

### 핵심 아키텍처 결정

| 결정 | 이유 |
|------|------|
| `timeout=None` (무제한) | Gemini 쿼리 120초 타임아웃으로 복잡한 분석 실패 방지 |
| 메시지 봉투 확장 (thread_id/type/cc/ref) | 분업 체인 추적 + 타 노드 메시지 열람(cc) 지원 |
| `nodes.json` N-node 등록 | hub.py 코드 수정 없이 새 노드 추가. `msg register-node` |
| 만장일치 consensus (Propose→Vote→Decision) | 3노드 합의 없이는 진행 불가. GC 대리 투표(CC 경유) |
| PROTOCOL.md 단일 진실 출처 | COLLAB.md 흡수 삭제. §P-0~P-7(3TCP) + §C-1~C-8(정책) 통합 |

### 주요 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `_sys/core/hub.py` | Phase A~D 완전 재작성. 16개 액션 |
| `PROTOCOL.md` | 신규 (COLLAB.md 흡수). 3TCP v1 §P-0~P-7 |
| `COLLAB.md` | 삭제 |
| `_sys/cli/msg.bat` | 한국어 주석 → 영어 (CONVENTION §1-1) |
| `_sys/hooks/ctx-save.bat` | session-master.json 제거 + gemini-mode-check → check-gate |
| `_sys/hooks/ctx-end.bat` | 동일 + context/ → docs/ 경로 수정 |
| `_sys/bridge/` | 삭제 (hub.py로 대체) |

### 테스트 결과

- **Unit (pytest)**: 74/74 PASS — 신규: §P-2 봉투 5개, §P-3 consensus 8개, §P-7 node 3개
- **Integration (PS1)**: 31/31 PASS
- **총합**: 105 tests ALL PASS

---

## 2026-06-03 — Phase 0~9 전면 재편 (Baseline v2)

**목표**: 파일명 혼재, 종횡 경쟁 상태, AI↔AI IPC 부재를 해결하는 전면 재설계.

### 핵심 아키텍처 결정

| 결정 | 이유 |
|------|------|
| `hub.py` — Python Facade 10 액션 | 모든 IPC 로직을 단일 진입점으로 통합. Batch ≤5줄 원칙 |
| `filelock` 라이브러리 (venv) | os.mkdir 뮤텍스는 고아 락 위험. venv 가용으로 안전한 OS-레벨 락 사용 |
| `.ai/` 프로젝트 로컬 상태 폴더 | .git/.vscode 패턴 따름. CWD→.git 상향 탐색, 프로젝트별 격리 |
| `c{4}-g{4}` 세션 pair ID | 1:1 매핑. prefix 포함 UUID 앞 4자리 (예: c2b5-g4707) |
| `handoff.md` FIFO ≤3000토큰 | 세션 간 컨텍스트 연속성. 초과 시 가장 오래된 항목 자동 삭제 |
| `--format llm` Token-Zero | LLM에 raw JSON 절대 금지. 마크다운 요약만 출력 |
| `PYTHONUTF8=1` 전역 | Windows CP949 인코딩 충돌 방지. 모든 배치 파일에 포함 |
| `PORTABLE_ROOT` 동적 계산 | `P:\` 하드코딩 금지. `%~dp0..\..` 기반 상대 경로 |

### 폴더 구조 변경

| 이전 | 이후 | 내용 |
|------|------|------|
| `_sys/context/*.bat` (20개) | `_sys/cli/` + `_sys/hooks/` + `_sys/scans/` + `_sys/tools/` | MECE 역할 분리 |
| `_workspace/*.json` (직접 쓰기) | `.ai/state.json` (hub.py 경유만) | 동시성 안전 |
| `session-master.json` `collab-bridge.json` | hub.py `send/check` 액션 | IPC 표준화 |
| `session-primer.md` | `.ai/sessions/*/handoff.md` (FIFO) | Token-Zero 연속성 |

### 스크립트 통폐합 (22 → 13)

| 삭제/통합 | 대체 |
|----------|------|
| `msg.bat` + `claude-task.bat` + `gemini-task.bat` | `cli/msg.bat` |
| `collab-log-append.bat` + `raw-log.bat` | `hooks/collab-log-append.bat` + `hooks/raw-log.bat` |
| `gemini-gate.bat` + `gemini-mode-check.bat` | `hooks/check-gate.bat` |
| `version-check.bat` + `gemini-usage.bat` + `gemini-set-ratio.bat` | `scans/scan-env.bat` |

### 테스트 결과

- **Unit (pytest)**: 22/22 PASS — hub.py 10 액션, FIFO, Token-Zero
- **Integration (PS1)**: 22/22 PASS — IPC, 세션 흐름, 경로/venv 검증

### 잔여 작업 (다음 세션)

1. `.claude/settings.json` 권한 업데이트 (자동 차단으로 수동 필요)
2. 전역 `P:\_sys\claude\config\CLAUDE.md`의 `context/gemini-consult.bat` → `tools/consult-ai.bat` 경로 수정
3. `setup.ps1` — venv 생성 + filelock 설치 항목 추가
4. WSB(`launch-wsbtest.ps1`) 환경에서 integration 테스트 검증
