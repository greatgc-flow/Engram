# Portable Dev Environment — Collaboration Protocol
> Orchestration policy, session management, and Claude-Gemini teaming rules.
> Coding conventions (bat/ps1/env var rules) → CONVENTION.md
> Gemini-facing rules summary → GEMINI.md §4-1

---

## §C-1 — Claude-Gemini 협업 프로토콜 v2 (2026-05-31)

v1 (9라운드, 단방향) → **v2 (수평 협력 모델)** 로 재수립.

### 역할 구조

두 에이전트는 **대등한 협력자**다. 어느 쪽이든 상대에게 요청하고 거절할 수 있다. 헌법적 사안에서만 Claude가 최종 권위를 가진다.

| | Claude | Gemini |
|--|--------|--------|
| 주 역할 | 오케스트레이터·정책 수호자 | 도메인 전문 실행자 |
| 헌법적 권위 | O | X (제안만 가능) |
| 세션 시작권 | O (Claude가 협업 세션 개시) | X (자기 발의 실행 금지) |
| 상대에게 요청 | Axis A-I 요청 가능 | 아래 타입으로 요청 가능 |

### Claude에게 요청 가능한 타입 (Gemini → Claude)

| 타입 | 설명 |
|------|------|
| `WRITE_FILE` | `_sys/` 스크립트·정책 문서 편집 |
| `HUMAN_DECISION` | 판단 불가한 사안 사용자 에스컬레이션 |
| `POLICY_CLARIFICATION` | 컨벤션 예외·엣지 케이스 해석 요청 |
| `GIT_OPERATION` | git commit/push/branch 실행 요청 |
| `SESSION_MANAGEMENT` | /compact, ctx-save, 컨텍스트 플러시 요청 |
| `READ_AND_VERIFY` | 파일 읽기 및 내용 검증 요청 |

### 통신 형식 (양측 공통)

```
[REQUEST_TO_CLAUDE: TYPE] 설명
[REQUEST_TO_GEMINI: AXIS]  설명
[REFERENCE: path/to/artifact]
[REFUSAL: CODE] 사유
```

거절 코드: `OUTSIDE_CAPABILITY` | `AMBIGUOUS_REQUEST` | `POLICY_VIOLATION` | `RESOURCE_EXHAUSTED` | `CONSTITUTIONAL_BOUNDARY`

### 이견 에스컬레이션

교착 전이라도 언제든 사용자에게 직접 에스컬레이션 가능.
교착 시: 마지막으로 거절한 쪽이 `[REQUEST_TO_CLAUDE: HUMAN_DECISION]` 자동 발행.

### 대화 로그 (_archive/collab-log/YYYY-MM-DD.md)

자동 기록: 각 Axis 스크립트 → `collab-log-append.bat` 경유.
수동 기록: Claude가 직접 호출하는 정책 논의는 Claude가 기록.

```
## [HH:MM:SS] Axis-X | scriptname.bat
Status: OK | FAIL | REFUSED | ESCALATED
Detail: ...
---
```

### 헌법적 권위 (Claude 최종 결정)

`CLAUDE.md` · `CONVENTION.md` · `GEMINI.md` · `GEMINI_MODE 변경` · `Human Gate` · `보안/안전 판단`

### Claude의 의무

| 원칙 | 내용 |
|------|------|
| 오케스트레이션 주도 | Claude가 협업 세션을 시작하고 전체 흐름을 관리 |
| Gemini 요청 처리 | `[REQUEST_TO_CLAUDE]` 수신 시 수용 또는 `[REFUSAL: CODE]` 거절. 무시 금지 |
| 자기완결 Directive | 파일 경로, 에러 출력, 목표 포함. 중간 질문 기대 금지 |
| JSON 계약 | `_archive/` JSON 출력만 읽기. raw 대화 출력 파싱 금지 |
| 쿼터 보존 | Axis-A 하루 최대 3회. 실행 중 파일 수정 병행 금지 |
| 실패 시 OFF | failure XML 수신 → GEMINI_MODE=OFF → 다음 start.bat에서 재확인 |
| 원자 Directive | 하나의 호출에 하나의 논리적 작업만 |

### Gemini의 의무

| 원칙 | 내용 |
|------|------|
| 시스템 파일 보호 | `_sys/`, `*.bat`, `*.ps1` 직접 편집 금지. `[REQUEST_TO_CLAUDE: WRITE_FILE]`로 요청 |
| 거절 권한 | 원칙 위배 요청 → `[REFUSAL: CODE]` 거절. 이유 명시 |
| Inquiry vs Directive | 모호한 요청 → read-only 분석 + 제안. 명확한 지시 → 실행 |
| 실패 형식 | `<failure_report><reason>CODE</reason><details>...</details></failure_report>` |
| 메모리 경계 | `MEMORY.md`: 기술적 How-To만. What/Why 오케스트레이션 기록 금지 |

### 실패 코드 (failure XML `CATEGORY_CODE`)
`FILE_NOT_FOUND` | `NETWORK_ERROR` | `AMBIGUOUS_DIRECTIVE` | `TEST_VALIDATION_FAILED` | `MISSING_DEPENDENCY`

### 실용 수치

- Gemini 컨텍스트 품질 한계: ~500k 토큰
- Axis-A: 100k~2.5M tokens | Axis-B: 1k~5k | Axis-G: 500~3k | Axis-H: 1k~5k
- 쿼터 초과 신호: `429 Too Many Requests` (failure XML과 별도)
- Claude JSONL Yellow: 600KB / Red: 1.2MB

---

## §C-2 — 3-Tier R&R

| Tier | 구성원 | 권한 | 역할 |
|------|-------|------|------|
| **Tier 1** | Claude Code 하네스 | 헌법적 권위 | 최종 오케스트레이터, 메모리, 사용자 게이트 |
| **Tier 1.5** | 스킬 (Skills) | Tier 1 확장 | Tier 2 에이전트 조율; Gemini 직접 호출 금지 |
| **Tier 2** | Claude 에이전트 | PASS/FAIL 판정 | 정책 준수 감사, 구현, 검증 |
| **Tier 3** | Gemini CLI (Axis A-I) | 도메인 분석 | 대용량 스캔, 배치 분석; PASS/FAIL 판정 불가 |

**핵심 원칙:**
- Sensor vs Judge: Gemini는 데이터 제공. PASS/FAIL은 verifier만.
- Tier 흐름: Tier 1 → Tier 2 → Tier 3. 역방향은 `[REQUEST_TO_CLAUDE]` 태그를 통해서만.
- `[REQUEST_TO_CLAUDE: ...]` 태그 수신 시: `[ESCALATE_TO_TIER1: {원본}]` 발행 후 대기.

### WRITE_FILE 라우팅 (Gemini → Claude → Tier 2)

| 파일 종류 | 라우팅 에이전트 |
|----------|--------------|
| `_sys/*.bat`, `_sys/*.ps1` | script-engineer |
| `CLAUDE.md`, `CONVENTION.md`, `GEMINI.md`, `README.md` | docs-writer (헌법적 검토 후) |
| `.claude/agents/*.md`, `.claude/skills/*` | docs-writer (헌법적 검토 후) |
| `_archive/*.json` (Axis 출력) | Gemini 직접 작성 허용 |

### 작업 라우팅 테이블

| 작업 | 주담당 | Gemini 지원 (Axis) |
|------|--------|-----------------|
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

Axis가 존재하는 분석 필요 AND Gemini ON → 반드시 Axis 먼저 사용.
Claude 인라인 분석은 컨텍스트 창을 소모함. Gemini Axis는 별도 토큰 풀 사용.

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

Exception: Zone A (constitutional matters) 또는 Axis 결과 불충분 시 Claude 인라인 가능.

**대형 문서 초안 (>100줄)**: `gemini -p "Draft: [requirements]." -o text -y > _workspace/02_draft_[name].md` → Claude 검토/편집.

---

## §C-4 — Collaboration Health Check (coordinator Phase 0 실행)

1. `_sys/gemini/status.json` 읽기 → mode=ON AND consecutive_failures < 3
2. `_archive/collab-log/{today}.md` 최근 10개 항목 확인
   - ESCALATED 미해결 → 먼저 처리
   - REFUSED → 재시도 전 근본 원인 파악
3. 판단:
   - 이상 없음 → 진행
   - consecutive_failures ≥ 3 → 복구 테스트: `gemini -p "ok" -y`
   - mode=OFF (비수동) → "Proceeding without Gemini: [reason]" 기록

**협업 장애 프로토콜** (예상치 못한 REFUSED, 스키마 불일치):
1. 현재 태스크 즉시 중단
2. collab-log에 전체 상세 기록
3. 근본 원인 진단 후 해결. 추측-재시도 금지.

---

## §C-5 — Session Transition Triggers

### Claude Context Window

| Trigger | 조건 | Action |
|---------|------|--------|
| YELLOW | 0.6–1.2 MB | 페이즈 완료 → ctx-save → 다음 heavy task 전 /compact 권장 |
| RED | > 1.2 MB | STOP → context-health.bat --force → 필수 /compact 또는 새 세션 |
| PRE-COMPLEX | > 5파일 태스크 전 | context_health.status 확인. YELLOW → /compact 먼저 |
| POST-PHASE4 | Human Approval Gate 후 | /compact 전 Phase 5 진행 가능 |

Heavy phase: > 5파일 변경 OR Axis-A OR ≥ 3 agent MD 재작성.

### Gemini Mode Transitions

| Trigger | 조건 | Action |
|---------|------|--------|
| 쿼터 소진 | HTTP 429 | mode=OFF, reason=api_error; REFUSED 로그; Gemini 없이 진행 |
| 자동 실패 | consecutive_failures ≥ 3 | collab-log-append.bat이 mode=OFF 자동 설정 |
| 복구 테스트 | mode=OFF (비수동) 후 | `gemini -p "ok" -y` 성공 → mode=ON 재설정 |

새 세션 시작: `_archive/session-handoff.json` + `_workspace/session-primer.md` 읽어 컨텍스트 재구성.

---

## §C-6 — State & CONTEXT.md Update Rules

Human Approval (state.json human_approval: "approved") 후:
- coordinator → `_workspace/state.json#system_state` 업데이트: last_completed, known_issues, gemini_mode
- coordinator → `_sys/claude/agent/CONTEXT.md` 업데이트: 아키텍처 변경 시만 (새 폴더 구조, 새 Axis, 새 에이전트)
- 루틴 태스크 완료는 CONTEXT.md 업데이트 불필요.
- docs-writer는 CONTEXT.md system_state 소유 없음 — coordinator가 state.json에 직접 기록.

---

## §C-7 — 에이전트 경로 정책

**기본 경로 우선순위**: `_workspace/` → `_sys/` → `BASE_DIR`
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
  • Doc sync → organizer → docs-writer (fast path: single doc → docs-writer direct)
  • Pre-flight risk → risk-scanner (Axis-I)
  • Portability audit → verifier → portability-auditor
  • Scenario audit → verifier → scenario-auditor
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
