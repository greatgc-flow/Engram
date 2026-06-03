# Portable Dev Environment — Collaboration & Protocol (3TCP v1)
> **단일 진실 출처**: 역할·정책·기술 프로토콜 통합 관리 파일 (구 COLLAB.md 대체)
> 코딩 컨벤션 (bat/ps1/env var 규칙) → CONVENTION.md
> 시스템 구조 → SYSTEM_ARCHITECTURE.md

---

## §P-0 — 노드 특성 (Node Characteristics)

모든 협업 프로토콜은 각 노드의 특성을 배려해야 한다.

| 속성 | CC (Claude Code) | CA (Claude Agent) | GC (Gemini CLI) |
|------|-----------------|-------------------|-----------------|
| **Tier** | 1 (오케스트레이터) | 2 (에이전트) | 3 (센서) |
| **메모리** | 영속 (Memory.md) | 단기 (세션 내) | 세션 (--resume) |
| **도구 접근** | 전체 | 전체 (상속) | 없음 (파일 기반만) |
| **헌법적 권위** | O | X | X |
| **PASS/FAIL 판정** | O | O (verifier 전용) | X (데이터 제공만) |
| **투표 방식** | 직접 파일 쓰기 | 직접 파일 쓰기 | CC 대리 투표 |
| **컨텍스트 한계** | ~1.2MB JSONL | ~1.2MB JSONL | ~500k 토큰 |
| **통신 채널** | hub.py 직접 | hub.py 직접 | subprocess (--query-file) |
| **실패 형식** | — | — | `<failure_report>...</failure_report>` |

**GC 대리 투표 절차** (GC는 외부 프로세스라 직접 파일 쓰기 불가):
1. CC가 `msg ask --to gc --query-file {제안서}` 로 GC 응답 수신
2. CC가 응답 해석 후 `msg consensus-vote --voter gc --vote agree|disagree|abstain` 실행

---

## §P-1 — 노드 등록 (nodes.json)

위치: `.ai/nodes.json` (프로젝트별, `ensure_ai_dir()`이 자동 생성)

```json
{
  "version": "1",
  "nodes": {
    "cc": { "tier":1, "type":"orchestrator", "invoke":"claude",  "invoke_args":["-p","{query}"],          "timeout":0, "memory":"persistent" },
    "ca": { "tier":2, "type":"agent",        "invoke":"claude",  "invoke_args":["-p","{query}"],          "timeout":0, "memory":"short-term" },
    "gc": { "tier":3, "type":"sensor",       "invoke":"gemini",  "invoke_args":["-p","{query}","-o","text","-y"], "timeout":0, "memory":"session" }
  }
}
```

- `timeout=0` → `None` (무제한). GC 쿼리에 120초 제한 없음.
- N번째 노드 추가: nodes.json 항목 1개 + `msg register-node` 또는 직접 편집. hub.py 코드 수정 불필요.

**N-Node 확장 절차 (§P-7 요약)**:
1. `msg register-node --to {id} --tier {n} --invoke {exe} --memory {type}` 실행
2. `msg list-nodes` 로 등록 확인
3. 이후 `consensus-propose --voters` 에 새 ID 포함

---

## §P-2 — 메시지 봉투 (mailbox.json 확장)

기존 필드 유지 + 4개 추가. 모두 `.get("field", default)` 로 하위 호환.

```json
{
  "id": 42,
  "thread_id": "t-a3f2",
  "type": "DIRECTIVE",
  "from": "cc",
  "to": "gc",
  "cc": ["ca"],
  "content": "메시지 내용",
  "status": "unread",
  "timestamp": "2026-06-03T14:30:00",
  "ref": 39
}
```

**타입 MECE:**

| 타입 | 분류 | 설명 |
|------|------|------|
| `MSG` | 일반 | 단순 정보 전달 (기존 send와 동일) |
| `PROPOSE` | 협의 | 만장일치 협의 제안 (본문: 제안서 전문) |
| `VOTE` | 협의 | 투표 결과 (agree/disagree/abstain) |
| `DECISION` | 협의 | 협의 종결 선언 (FINALIZED/ESCALATED) |
| `DIRECTIVE` | 분업 | 작업 지시 (실행자에게) |
| `ARTIFACT` | 분업 | 작업 결과물 (지시자에게) |
| `VERIFY` | 분업 | 검증 결과 (모두에게, cc 활용) |

**cc 필드**: `msg check --target {id}` 는 `to==id` AND `id in cc` 모두 반환.
→ VERIFY 결과를 GC도 열람 가능: `send --type VERIFY --to cc --cc gc`

---

## §P-3 — 만장일치 협의 라운드 (Propose → Vote → Decision)

상태 파일: `.ai/consensus/{round_id}.json`

```
[Initiator]  msg consensus-propose --subject "..." --voters cc,ca,gc
                     ↓  round_id=r-xxxx 자동 발급, status=voting
[각 노드]    msg consensus-vote --round-id r-xxxx --voter {id} --vote agree|disagree|abstain
                     ↓
          전원 agree    → FINALIZED  → handoff.md CONSENSUS_HISTORY 자동 기록
          1명 disagree  → ESCALATED  → Human Gate 필수
          deadline 초과  → 무응답 노드 abstain → 재평가
```

**콘솔 출력:**
```
[HUB] PROPOSE r-c4d1 | subject=Protocol v1 승인 | voters=cc,ca,gc
[HUB] VOTE   r-c4d1  | voter=cc agree | 1/3
[HUB] VOTE   r-c4d1  | voter=ca agree | 2/3
[HUB] VOTE   r-c4d1  | voter=gc agree | 3/3
[HUB] DECISION r-c4d1 FINALIZED | unanimous
```

**GC 투표 흐름 (§P-0 참조)**: CC가 GC에 제안서를 ask로 전달 → 응답 해석 → 대리 투표.

**라운드 규칙:**
- 최대 5라운드 내 합의 못하면 ESCALATED
- `msg consensus-check` 로 전체 라운드 조회
- `msg consensus-check --round-id r-xxxx` 로 특정 라운드 조회
- `msg status` 에 활성 라운드 목록 포함

---

## §P-4 — 분업 프로토콜 (Directive → Artifact → Verify)

```
[CC] msg send --from cc --to gc --type DIRECTIVE --thread-id t-xxxx --msg "..."
[GC] 작업 수행 → msg send --from gc --to cc --type ARTIFACT --thread-id t-xxxx --ref {directive_id} --msg "..."
[CA] 검증 → msg send --from ca --to cc --type VERIFY --thread-id t-xxxx --cc gc --ref {artifact_id} --msg "PASS|FAIL: ..."
```

- `cc=["gc"]` 덕분에 GC도 VERIFY 결과를 `msg check --target gc` 로 열람
- thread_id로 같은 작업의 메시지를 추적
- ref로 메시지 체인 연결

**콘솔 출력:**
```
[HUB] SENT  cc→gc  | thread=t-b5e3 | id=43 type=DIRECTIVE
[HUB] SENT  gc→cc  | thread=t-b5e3 | id=44 type=ARTIFACT ref=43
[HUB] READ  2 messages for ca (ARTIFACT×1 VERIFY×1)
```

---

## §P-5 — 콘솔 출력 표준

모든 hub.py 출력은 아래 접두어를 사용한다.

| 접두어 | 용도 |
|--------|------|
| `[HUB]` | 정상 동작 (SENT, READ, ASK, REPLY, PROPOSE, VOTE, DECISION, REGISTER) |
| `[HUB:ERROR]` | 오류 (예외, 파일 없음, 타임아웃) |
| `[HUB:WARN]` | 경고 (비정상 종료 코드, 이상 상황) |
| `[HUB:GATE]` | 게이트 확인 (gemini=ON/OFF) |

타임스탬프는 콘솔 미포함 (log.jsonl에만). 방향은 `from→to` 고정 형식.

**ask 액션 표준:**
```
[HUB] ASK   cc→gc | chars=234 | timeout=none
[HUB] REPLY gc→cc | chars=1842 | elapsed=47s
```

---

## §P-6 — 업무 연속성 (Session Continuity)

handoff.md에 6개 섹션 (FIFO 관리):

```markdown
## [GOAL]
## [RECENT_COMPLETED]     ← 최대 5개
## [PENDING_ISSUES]       ← 최대 3개
## [KEY_DECISIONS]        ← 최대 3개
## [CONSENSUS_HISTORY]    ← 최대 10개 (만장일치 결과 자동 기록)
## [ACTIVE_THREADS]       ← 최대 5개 (진행 중인 Directive-Artifact 체인)
```

**세션 재개 3-line 복원:**
```
msg status           → ACTIVE_THREADS + 활성 consensus 라운드
msg consensus-check  → 미완료 협의 목록
msg check --target cc → 미읽은 메시지
```

---

## §P-7 — N-Node 확장 절차

새 노드 `n1` 추가 예시:

```bat
msg register-node --to n1 --tier 4 --node-type sensor ^
    --invoke custom-cli --invoke-args "-p,{query}" ^
    --memory session
msg list-nodes
```

이후 consensus에 포함:
```bat
msg consensus-propose --subject "n1 도입 승인" --voters cc,ca,gc,n1
```

hub.py 코드 수정 없음. nodes.json 수정만으로 완료.

---

---

## §C-1 — Claude-Gemini 협업 정책 v2

*(2026-05-31 v1→v2 재수립. 구 COLLAB.md §C-1 이전)*

두 에이전트는 **대등한 협력자**다. 헌법적 사안에서만 Claude가 최종 권위를 가진다.

| | Claude (CC) | Gemini (GC) |
|--|-------------|-------------|
| 주 역할 | 오케스트레이터·정책 수호자 | 도메인 전문 실행자·전략 제안자 |
| 헌법적 권위 | O | X (제안만 가능) |
| 세션 시작권 | O | O (`[REQUEST_TO_CLAUDE: SESSION_MANAGEMENT]`로) |

**Gemini → Claude 요청 타입:**

| 타입 | 설명 |
|------|------|
| `WRITE_FILE` | `_sys/` 스크립트·정책 문서 편집 |
| `HUMAN_DECISION` | 판단 불가한 사안 에스컬레이션 |
| `POLICY_CLARIFICATION` | 컨벤션 예외·엣지 케이스 해석 |
| `GIT_OPERATION` | git commit/push/branch 실행 |
| `SESSION_MANAGEMENT` | /compact, ctx-save, 컨텍스트 플러시 |
| `READ_AND_VERIFY` | 파일 읽기 및 내용 검증 |

**통신 형식 (양측 공통):**

```
[REQUEST_TO_CLAUDE: TYPE] 설명
[REQUEST_TO_GEMINI: AXIS]  설명
[REFERENCE: path/to/artifact]
[REFUSAL: CODE] 사유
```

거절 코드: `OUTSIDE_CAPABILITY` | `AMBIGUOUS_REQUEST` | `POLICY_VIOLATION` | `RESOURCE_EXHAUSTED` | `CONSTITUTIONAL_BOUNDARY`

이견 교착 시: 마지막 거절한 쪽이 `[REQUEST_TO_CLAUDE: HUMAN_DECISION]` 자동 발행.

**헌법적 권위 (Claude 최종 결정):**
`CLAUDE.md` · `CONVENTION.md` · `GEMINI.md` · `GEMINI_MODE 변경` · `Human Gate` · `보안/안전 판단`

**Claude 의무:**

| 원칙 | 내용 |
|------|------|
| 오케스트레이션 주도 | 협업 세션 시작 + 전체 흐름 관리 |
| Gemini 요청 처리 | `[REQUEST_TO_CLAUDE]` 수신 시 수용 또는 `[REFUSAL: CODE]`. 무시 금지 |
| 자기완결 Directive | 파일 경로, 에러 출력, 목표 포함. 중간 질문 기대 금지 |
| JSON 계약 | `_archive/` JSON 출력만 읽기. raw 대화 파싱 금지 |
| 쿼터 보존 | Axis-A 하루 최대 3회 |
| 실패 시 OFF | failure XML → GEMINI_MODE=OFF → 다음 start.bat에서 재확인 |
| 원자 Directive | 하나의 호출에 하나의 논리적 작업만 |

**Gemini 의무:**

| 원칙 | 내용 |
|------|------|
| 시스템 파일 보호 | `_sys/`, `*.bat`, `*.ps1` 직접 편집 금지. `[REQUEST_TO_CLAUDE: WRITE_FILE]`로 요청 |
| 거절 권한 | 원칙 위배 요청 → `[REFUSAL: CODE]`. 이유 명시 |
| 실패 형식 | `<failure_report><reason>CODE</reason><details>...</details></failure_report>` |
| 메모리 경계 | `MEMORY.md`: 기술적 How-To만. What/Why 오케스트레이션 기록 금지 |

실패 코드: `FILE_NOT_FOUND` | `NETWORK_ERROR` | `AMBIGUOUS_DIRECTIVE` | `TEST_VALIDATION_FAILED` | `MISSING_DEPENDENCY`

**실용 수치:**
- GC 컨텍스트 품질 한계: ~500k 토큰
- Axis-A: 100k~2.5M tokens | Axis-B: 1k~5k | Axis-G: 500~3k | Axis-H: 1k~5k
- 쿼터 초과 신호: `429 Too Many Requests`
- CC JSONL Yellow: 600KB / Red: 1.2MB

---

## §C-2 — 3-Tier R&R

| Tier | 구성원 | 권한 | 역할 |
|------|-------|------|------|
| **Tier 1 (CC)** | Claude Code 하네스 | 헌법적 권위 | 최종 오케스트레이터, 메모리, 사용자 게이트 |
| **Tier 1.5** | 스킬 (Skills) | Tier 1 확장 | Tier 2 에이전트 조율; GC 직접 호출 금지 |
| **Tier 2 (CA)** | Claude 에이전트 | PASS/FAIL 판정 | 정책 준수 감사, 구현, 검증 |
| **Tier 3 (GC)** | Gemini CLI (Axis A-I) | 도메인 분석 | 대용량 스캔, 배치 분석; PASS/FAIL 판정 불가 |

핵심 원칙:
- **Sensor vs Judge**: GC는 데이터 제공. PASS/FAIL은 verifier(CA)만.
- **Tier 흐름**: Tier 1 → Tier 2 → Tier 3. 역방향은 `[REQUEST_TO_CLAUDE]` 태그를 통해서만.

**WRITE_FILE 라우팅 (GC → CC → CA):**

| 파일 종류 | 라우팅 에이전트 |
|----------|--------------|
| `_sys/*.bat`, `_sys/*.ps1` | script-engineer |
| `CLAUDE.md`, `CONVENTION.md`, `PROTOCOL.md`, `README.md` | docs-writer (헌법적 검토 후) |
| `.claude/agents/*.md` | docs-writer (헌법적 검토 후) |
| `_archive/*.json` (Axis 출력) | GC 직접 작성 허용 |

**작업 라우팅 테이블:**

| 작업 | 주담당 | GC 지원 (Axis) |
|------|--------|---------------|
| 이식성 감사 | portability-auditor | A |
| 스크립트 수정 | script-engineer | F (전) → D (후) |
| 버전 확인 | proposer | B |
| 에이전트 일관성 | verifier (조건부) | E |
| 세션 요약 | ctx-end.bat | C |
| 커밋 메시지 초안 | Tier 1 | G |
| 컨텍스트 건강 | coordinator | H |
| 문서 동기화 | docs-writer | — |
| 시나리오 감사 | scenario-auditor | — |

---

## §C-3 — Gemini-first Analysis Rule

Axis가 존재하는 분석 필요 AND Gemini ON → **반드시 Axis 먼저 사용.**
CC 인라인 분석은 컨텍스트 창을 소모함. GC Axis는 별도 토큰 풀 사용.

| Analysis Need | Axis | Output |
|---------------|------|--------|
| Pre-flight risk | I | _archive/risk-scan.json |
| Script syntax | D | console |
| Full codebase | A | 03_portability_audit.json |
| Agent consistency | E | _archive/agent-audit.json |
| External versions | B | _archive/version-check.json |
| Script dependencies | F | _archive/script-deps.json |
| Commit message | G | console |
| Context health | H | status.json |

Exception: Zone A (헌법적 사안) 또는 Axis 결과 불충분 시 CC 인라인 가능.

대형 문서 초안 (>100줄): `gemini -p "Draft: ..." -o text -y > _workspace/02_draft_[name].md` → CC 검토/편집.

---

## §C-4 — Collaboration Health Check

*(coordinator Phase 0에서 실행)*

1. `_sys/gemini/status.json` 읽기 → mode=ON AND consecutive_failures < 3
2. `_archive/collab-log/{today}.md` 최근 10개 항목 확인
   - ESCALATED 미해결 → 먼저 처리
   - REFUSED → 재시도 전 근본 원인 파악
3. `msg consensus-check` → 미완료 라운드 확인
4. 판단:
   - 이상 없음 → 진행
   - consecutive_failures ≥ 3 → 복구 테스트: `gemini -p "ok" -y`
   - mode=OFF (비수동) → "Proceeding without Gemini: [reason]" 기록

협업 장애 프로토콜 (예상치 못한 REFUSED, 스키마 불일치):
1. 현재 태스크 즉시 중단
2. collab-log에 전체 상세 기록
3. 근본 원인 진단 후 해결. 추측-재시도 금지.

---

## §C-5 — Session Transition Triggers

### Claude Context Window

| Trigger | 조건 | Action |
|---------|------|--------|
| YELLOW | 0.6–1.2 MB | 페이즈 완료 → ctx-save → /compact 권장 |
| RED | > 1.2 MB | STOP → check-health.bat --force → 필수 /compact |
| PRE-COMPLEX | > 5파일 태스크 전 | context_health.status 확인. YELLOW → /compact 먼저 |

Heavy phase: > 5파일 변경 OR Axis-A OR ≥ 3 agent MD 재작성.

### Gemini Mode Transitions

| Trigger | 조건 | Action |
|---------|------|--------|
| 쿼터 소진 | HTTP 429 | mode=OFF; REFUSED 로그; GC 없이 진행 |
| 자동 실패 | consecutive_failures ≥ 3 | collab-log.bat이 mode=OFF 자동 설정 |
| 복구 테스트 | mode=OFF (비수동) 후 | `gemini -p "ok" -y` 성공 → mode=ON 재설정 |

새 세션 시작: `msg status` + `msg consensus-check` + `msg check --target cc` 로 컨텍스트 복원.

---

## §C-6 — State & CONTEXT.md Update Rules

Human Approval 후:
- coordinator → `_workspace/state.json#system_state` 업데이트
- coordinator → `_sys/claude/agent/CONTEXT.md` 업데이트: 아키텍처 변경 시만
- 루틴 태스크 완료는 CONTEXT.md 업데이트 불필요
- docs-writer는 CONTEXT.md system_state 소유 없음 — coordinator가 state.json에 직접 기록

---

## §C-7 — 에이전트 경로 정책

기본 경로 우선순위: `_workspace/` → `_sys/` → `BASE_DIR`
경로 변수 미설정 시: 워닝 출력 후 계속 진행 (블로킹 아님).

```
[Warning] {VAR_NAME} not set - using default: {default_path}
```

- 스캔 범위: BASE_DIR 기준 최대 2단계 하위
- 변경 범위: 요청 범위 2배 초과 → proposer에게 경고 에스컬레이션
- 드라이브 전체 스캔: 명시적 경로 지시 없으면 금지

---

## §C-8 — Decision Delegation Policy

```
ZONE A — CC decides immediately (no consultation):
  • CLAUDE.md / CONVENTION.md / PROTOCOL.md interpretation
  • GEMINI_MODE changes
  • Security decisions (auth files, USERPROFILE protection)
  • CONVENTION.md rule violations → block immediately
  • Gemini failure XML received → GEMINI_MODE=OFF
  • loop_count ≥ 3 → HALT immediately

ZONE B — Delegate to agent via harness (no CC inline analysis):
  • _sys/*.bat / *.ps1 modification → script-engineer
  • tools/ new tool → tool-integrator
  • Folder structure → organizer → folder-tidier
  • Doc sync → organizer → docs-writer (fast path: single doc → docs-writer direct)
  • Pre-flight risk → risk-scanner (Axis-I)
  • Portability audit → verifier → portability-auditor
  • Scenario audit → verifier → scenario-auditor
  • Agent consistency → verifier (Axis-E, conditional)
  • ROI analysis → proposer (after verifier PASS)

ZONE C — Ask user first:
  • Request scope unclear AND affects > 3 files
  • Axis-A execution planned (≤500k GC tokens) → confirm
  • Deletion scope > 2× requested scope
  • Constitutional boundary conflict
  • risk-scanner returns overall_risk = HIGH
  • loop_count reaches 2 → warn: "Loop 2/3. One more FAIL triggers HALT."
```

---

*3TCP v1 implemented: 2026-06-03. hub.py Phase A~D 완료.*
