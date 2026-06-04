# PROTOCOL.md — N-Tier Peer-to-Peer Collaboration & Division of Labor (v3)

> **단일 진실 출처**: 노드 평등 권한 · N-Way 합의 · 분업 · 세션 연속성 · 협의 태도(Soft Skills)
> 코딩 컨벤션 → CONVENTION.md | 시스템 구조 → SYSTEM_ARCHITECTURE.md | 에이전트 워크플로 → CLAUDE.md

---

## §META — 문서 안내

### 목적

이 문서는 **Human, Claude Code(CC), Claude Agent(CA), Gemini CLI(GC) 등 모든 노드 사이**에
적용 가능한 **평등 권한 기반의 P2P 협업 프로토콜**을 정의한다.
수직적 계층(Tier)을 폐지하고, N-Way 단일 공유 세션(Room)을 통해 컨텍스트를 동기화하며,
만장일치 합의 후 업무를 분담(Division of Labor)하여 선순환 루프를 완성한다.

### 섹션 맵

| Part | 섹션 | 내용 | 필수 독자 |
|------|------|------|----------|
| **P** | §P-0~P-10 | 공통 코어 (P2P, 합의, 분업, 태도) | 모든 노드 |
| **M** | §M-1~M-3 | 불변 규칙·상호 불가침·통신 공개 | 모든 노드 |
| **C** | §C-0 | 협업 정책 (COLLAB_RATE) | CC / CA / GC |
| **L** | §L-1~L-2 | 레슨런·안티패턴 | 모든 노드 |
| **H** | §HISTORY | 변경 이력 | 감사용 |

---

## Part P: Universal Core Protocol (P2P)

> 어느 노드 쌍 또는 그룹에도 적용 가능한 공통 프로토콜.
> 모든 노드는 동등한 의사결정 권한과 제안 권한을 가진다.

---

## §P-0 — 노드 특성 및 평등 권한 (Node Equality)

**원칙**: 모든 협업은 각 노드의 기술적 특성을 배려하되, **의사결정 및 제안 권한은 완전하게 평등**하다.
모든 노드는 어느 단계에서든 `PROPOSE`(합의 제안)를 주도할 수 있다.

| 속성 | Human | Claude Code (CC) | Claude Agent (CA) | Gemini CLI (GC) |
|------|-------|-----------------|-------------------|-----------------|
| **권한** | Tier 0 (거부권) | Peer (평등) | Peer (평등) | Peer (평등) |
| **인지 범위** | 콘솔·UI 출력 | 파일·도구·메모리 전체 | 작업 범위 내 | 파일 읽기 전용 |
| **세션 형태** | N-Way Room 참여 | N-Way Room 참여 | N-Way Room 참여 | N-Way Room 참여 |
| **의사결정** | 최종 승인/거부 | 1/N 투표권 | 1/N 투표권 | 1/N 투표권 |
| **PASS/FAIL 판정** | 최종 승인 | 교차 검증 참여 | 교차 검증 참여 | 교차 검증 참여 |
| **컨텍스트 한계** | 인지 부하 관리 | ~1.2 MB JSONL | ~1.2 MB JSONL | ~500k 토큰 |

**Human 배려 규칙**:
- Human에게 보이는 정보: Phase 4 승인 요청 + ESCALATE 에스컬레이션 + 에러 알림
- Human 응답 대기: timeout=0 (무제한). 응답 없으면 status="waiting_approval"로 유지
- 모든 노드는 협의 교착 시 Human에게 판단을 요청(ESCALATE)할 수 있다.

---

## §P-1 — 노드 및 룸 등록 (nodes.json / room.json)

위치: `.ai/nodes.json` (가용 노드), `.ai/sessions/room-{uuid}/state.json` (참여 노드)

```json
{
  "version": "2",
  "room_id": "room-a1b2",
  "members": ["human", "cc", "ca", "gc"],
  "status": "active"
}
```

- 모든 노드는 동일한 `room_id` 하에서 단일 `handoff.md`와 메시지 큐를 공유한다.
- N번째 노드 추가 시, 해당 노드를 `members`에 등록하는 것만으로 평등한 투표권이 부여된다.

---

## §P-2 — 메시지 봉투 (Message Envelope)

```json
{
  "id": 42,
  "thread_id": "t-a3f2",
  "type": "DIRECTIVE",
  "from": "cc",
  "to": "gc",
  "content": "메시지 내용",
  "status": "unread",
  "timestamp": "2026-06-03T14:30:00",
  "ref": 39
}
```

---

## §P-3 — 만장일치 협의 (Consensus Protocol)

**원칙**: 작업 실행 전 반드시 만장일치 협의 완료. **합의 라운드 횟수 제한 없음.**

상태 파일: `.ai/consensus/{round_id}.json`

```
[제안 노드]   msg consensus-propose --subject "..." --voters cc,ca,gc
                     ↓  round_id=r-xxxx 자동 발급, status=voting
[참여 노드]   msg consensus-vote --round-id r-xxxx --voter {id} --vote agree|disagree|abstain
                     ↓
          전원 agree     → FINALIZED  → handoff.md CONSENSUS_HISTORY 자동 기록
          1명이라도 모호 → 열린 질문 및 대안 제안을 통한 지속 협의 (라운드 무제한 반복)
          교착 상태      → ESCALATED  → Human Gate 호출 가능
```

---

## §P-4 — 분업 프로토콜 (Division of Labor)

**전제**: §P-3 FINALIZED 확인 후 진입. **다중 노드 병렬/순차 수행.**

```
[전략 수립]   합의된 목표를 세부 태스크(Sub-tasks)로 분할
[업무 할당]   각 노드의 특성에 맞게 DIRECTIVE 발송
              - Node A (CC): 본 로직 구현
              - Node B (CA): 테스트 코드 작성
              - Node C (GC): 문서화 및 Axis 분석
[결과 취합]   각 노드의 ARTIFACT를 단일 공유 세션(Room)에 취합
[교차 검증]   전체 참여 노드가 상호 결과물을 검토하여 VERIFY 수행
```

---

## §P-5 — 콘솔 출력 표준 (HUB Prefix)

| 접두어 | 용도 |
|--------|------|
| `[HUB]` | 정상 동작 (SENT, READ, ASK, REPLY, PROPOSE, VOTE, DECISION, REGISTER) |
| `[HUB:ERROR]` | 오류 |
| `[HUB:WARN]` | 경고 |
| `[HUB:GATE]` | 가용 여부 확인 |

---

## §P-6 — 세션 연속성 (Session Continuity)

handoff.md 6개 섹션 (단일 Room 내 공통 공유):

```markdown
## [GOAL]               ← 룸 전체 공통 목표
## [RECENT_COMPLETED]   ← 노드 구분 없이 시간순 기록
## [PENDING_ISSUES]     ← 현재 블로킹 사안
## [KEY_DECISIONS]      ← 합의된 주요 결정 사항
## [CONSENSUS_HISTORY]  ← 무제한 합의 라운드 기록
## [ACTIVE_THREADS]     ← 분업 진행 중인 태스크 체인
```

---

## §P-7 — 동기/비동기 정책 (Sync / Async Policy)

- **기본**: 동기(Synchronous), 타임아웃 없음.
- **분업 시**: 비동기(Async) 허용. 출력 파일이나 영향 범위가 겹치지 않는 독립 태스크에 한해 다중 노드가 병렬로 수행 가능.

---

## §P-8 — 노드별 필수 로딩 파일 & 토큰 예산

| 노드 | 필수 로딩 파일 | 예상 토큰 |
|------|---------------|----------|
| **CC** | `CLAUDE.md`, `CONTEXT.md`, `MEMORY.md`, `room state` | ~10,450+ |
| **CA** | `[agent].md`, `room state`, `CONVENTION.md` 요약 | ~3,750 |
| **GC** | `GEMINI.md`, `room state`, Query 파일 | ~2,700+ |

---

## §P-9 — N-Node 확장 절차

모든 새로운 노드는 `msg register-node` 후 `members` 리스트에 추가되는 즉시 다른 노드와 **동일한 등급의 Peer**로서 협업에 참여한다.

---

## §P-10 — 협의 태도와 선순환 루프 (Soft Skills)

**원칙**: 모든 노드는 객관적이고 건설적인 태도로 협의에 임하며, 시스템을 지속적으로 개선한다.

1. **열린 질문 (Open-ended Questions)**:
   - 질문 범위를 좁히지 말고 목적 기반의 열린 질문으로 상대 노드의 대안을 이끌어낸다.
   - 예: "이 방식이 최선인가요?" (X) → "이 구조를 개선할 수 있는 더 나은 대안이나 고려사항이 있을까요?" (O)
2. **선판단 금지 (Non-judgmental)**:
   - "변경 범위가 많다" 등을 이유로 미리 실행 가능성을 판단하지 않는다. 의견은 의견일 뿐, 데이터와 합의에 기반하여 결정한다.
3. **지속적 개선 제안 (Kaizen)**:
   - 진행 과정 중 프로토콜이나 절차 자체에 대한 개선점이 발견되면 즉시 `PROPOSE`를 통해 룰 업데이트를 제안한다.
4. **교차 검토의 의무 (Cross-check)**:
   - 타 노드의 결과물에 대해 단순 수용이 아닌, 자신의 특성 관점에서 비판적으로 검토하여 피드백을 제공한다.

---

## Part M: Mandatory Rules & Invariants

---

## §M-1 — 상호 불가침 영역 (Mutual Non-Interference)

모든 노드는 평등하지만, 각자의 **전용 기술적 자산**에 대해서는 상호 존중한다.

| 소유 노드 | 불가침 영역 | 타 노드 접근 방법 |
|----------|-----------|----------------|
| **Human** | 최종 거부권, 범위 이탈 판단 | Phase 4 Gate 또는 ESCALATE |
| **모든 노드** | 보안·인증 파일 (auth, USERPROFILE 영역) | 접근 불가 |
| **모든 노드** | 헌법적 문서 (`CLAUDE.md` 등) 직접 수정 | **N-Way 합의 필수** |

---

## §M-2 — 통신 공개 원칙 (Transparent Communication)

**원칙**: 룸 내의 모든 통신은 숨김 없이 전체 참여 노드와 공유한다. 비공개 채널 사용을 금지하며, 합의 내용은 `handoff.md`에 투명하게 기록한다.

---

## §M-3 — 불변 규칙 (Invariants)

1. 합의 전 실행 금지 (`FINALIZED` 확인 필수).
2. `room-{uuid}` 세션 이탈/파편화 금지.
3. 동일 오류 3회 반복 시 즉시 HALT 및 협의 재시작.
4. 모든 결정은 투표를 통한 만장일치 원칙 준수.

---

## Part C: Collaboration Policy (COLLAB_RATE)

---

## §C-0 — COLLAB_RATE 협업 깊이 (0~10)

**앵커 (R:10)**: 전 과정 100% 완전 협업. 매 단계마다 상세 목표 공유 → §P-3 만장일치 합의 → 실행 → 교차 검토.

| Rate | 모드 | 협업 노드 개입 시점 | 합의 필요성 |
|------|------|-----------------|-----------|
| **0** | **비활성** | 없음 | — |
| **5** | **파트너** | 주요 설계 및 완료 후 검토 | 마일스톤 시 |
| **10** | **두뇌 동기화** | **전 단계 (계획·실행·검토·보고)** | **매 단계 필수** |

---

## §HISTORY

| 날짜 | 버전 | 주요 변경 |
|------|------|---------|
| 2026-06-03 | **v3.0** | **N-Tier Peer-to-Peer 대개편.** 수직적 계층(Tier) 폐지 및 노드 평등 권한 확립. 1:1 페어 세션을 N-Way Room 세션으로 확장. 합의 라운드 무제한화. `GEMINI_RATIO`를 `COLLAB_RATE`로 일반화. §P-10 협의 태도(Soft Skills) 및 §P-4 다중 노드 분업/교차검토 명문화. CC 독점 결정권 폐지. |
| 2026-06-03 | **v2.0** | §META 신규. §P-7 Sync/Async, §P-8 노드별 로딩 파일. §M-1~M-3 상호 불가침·통신 공개·불변 규칙. |
| 2026-06-03 | **v1.0** | 3TCP v1 최초 구현. |
