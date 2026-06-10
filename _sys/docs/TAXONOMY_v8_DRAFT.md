# MECE Taxonomy v8.0 — AI-Assisted Development: Governance Framework
### [DRAFT — High-Fidelity Gemini Solo Phase]
### Universal · Scalable · Flexible · Maintainable · Self-Improving (Closed-Loop)

> **Version**: 8.0-DRAFT | **Date**: 2026-06-06
> **Review Status**: [변경됨] Gemini Solo High-Fidelity Pre-Analysis. (Protocol Handshake Complete)
> **Supersedes**: TAXONOMY_v7.md (READ-ONLY)
> **Audience**: AI-인간 협업 시스템을 설계 및 운영하는 시스템 엔지니어링 팀 및 AI 에이전트.

---

## §0. 철학 및 패러다임 전환 (Paradigm Shift)

본 문서는 단순히 "에이전트의 작업을 돕는 도구"를 넘어, **"분산형 휴리스틱 지능의 자율적 거버넌스(Autonomous Governance of Distributed Heuristic Intelligence)"**로 프레임을 전환합니다. 

AI의 확률적(Heuristic) 특성을 인정하면서도, 시스템의 전체적인 진화 궤적은 결정론적(Deterministic)으로 통제하여 **지속 가능하고(Sustainable)** **측정 가능한(Measurable)** 소프트웨어 공학 환경을 구축하는 것이 본 지침의 목적입니다.

### 핵심 설계 원칙:
1. **인간 중심의 폐쇄 루프 (Human-Centric Closed-Loop)**: 모든 지능적 활동은 인간의 의도에서 촉발되며, 최종 가치 판단은 인간에 의해 완료됩니다.
2. **무결성 우선주의 (Integrity First)**: 기능적 구현의 속도보다 시스템의 무결성(Integrity)과 통제 가능성(Controllability)이 상위 가치를 가집니다.
3. **지식의 복리 효과 (Compounding Knowledge)**: 모든 세션은 단순히 코드를 생성하는 것을 넘어, 시스템의 '지침'과 '기억'을 개선하는 카이젠(Kaizen) 데이터를 산출해야 합니다.

---

## §1. 선순환 루프 아키텍처 (The Virtuous Cycle)

거버넌스 항목들은 상호 유기적으로 연결된 7단계의 순환 계층으로 구성됩니다. 모든 단계는 이전 단계의 결과물을 입력값으로 하며, 마지막 단계는 다시 첫 단계의 품질을 높이는 피드백을 제공합니다.

```text
[ Start: Human Gate ]
   │
   ▼
P1: 의도 및 목표 정렬 (Intent Alignment) ──────┐
   │ (Goal ID & Constraints)                 │
   ▼                                         │
P2: 환경 준비도 검증 (Readiness)             │ [데이터 피드백]
   │ (Infra & Node Provisioning)             │
   ▼                                         │
P3: 인지 및 기억 동기화 (Cognition Sync)     │
   │ (Working Memory & Domain Knowledge)     │
   ▼                                         │
P4: 분산 협업 및 오케스트레이션 (Execution)  │
   │ (Consensus & Task Decomposition)        │
   ▼                                         │
P5: 무결성 및 기능 검증 (Integrity Gate)     │
   │ (Policy & Functional Test)              │
   ▼                                         │
P6: 운영 경제성 통제 (Ops & Economy)         │
   │ (Budget & Performance Monitor)          │
   ▼                                         │
P7: 인도 및 카이젠 (Delivery & Kaizen) ──────┘
   │ (Learning & Next Intent Seed)
   ▼
[ End: Human Acceptance ]
```

---

## §2. MECE 거버넌스 트리 (Taxonomy Tree)

*지표: [B] = Binary(유무 판단), [C] = Continuous(수치 모니터링)*
*태그: [추가됨], [변경됨]*

### P1: 의도 및 목표 정렬 (Human Intent & Goal Alignment)
*완성도: 현재 85% → 목표 100% (Δ +15%)*
*전략: 모호한 자연어를 기계가 해석 가능한 제약 조건 집합으로 정제.*

- **P1-1: 구조화된 의도 캡처 (Structured Intent Capture) [B]**
  - `P1-1-1` [변경됨] **목표 ID 및 세션 식별 (Goal ID)**: 모든 작업은 고유한 Goal ID와 매핑되어야 함.
    - *인용 (PROTOCOL.md §P-6)*: "## [GOAL] — Common goal for the entire room"
  - `P1-1-2` [추가됨] **스코프 경계 선언 (Scope Bounding)**: 수정 가능한 파일 범위와 금지 영역을 명시적으로 확정하여 AI의 일탈(Drift) 방지.
- **P1-2: 인수 기준 및 KPI 설정 (Success Criteria) [B]**
  - `P1-2-1` **기능적 UAT 기준**: 인간이 최종 승인 시 확인할 정량적/정성적 체크리스트 정의.
- **P1-3: 모호성 해소 및 락인 (Clarification & Lock-in) [C]**
  - `P1-3-1` **의도 동기화 확인**: AI가 작업을 시작하기 전, 인간의 의도를 제대로 파악했는지 요약하여 확인받는 절차.

### P2: 환경 준비도 검증 (Provisioning & Readiness)
*완성도: 현재 70% → 목표 95% (Δ +25%)*
*전략: 호스트 의존성을 제거하고 멱등한 실행 환경을 즉각적으로 구성.*

- **P2-1: 포터블 인프라 격리 (Portable Isolation) [B]**
  - `P2-1-1` **제로 베이스 부트스트랩**: 외부 라이브러리 없이 단일 명령으로 모든 도구 체인 복원.
    - *인용 (CONVENTION.md §2-2)*: "install.bat: Automatically downloads and configures all runtimes via setup.py. (Supports ZeroBase)"
- **P2-2: 노드 디스커버리 및 등록 (Node Registration) [C]**
  - `P2-2-1` [변경됨] **동적 노드 역량 매핑**: 참여 노드의 토큰 한도, 특화 분야(Axis)를 실시간 인식하여 최적의 노드에 작업 배분.
- **P2-3: 벤더 추상화 (Vendor Abstraction) [B]**
  - `P2-3-1` [추가됨] **표준 토큰 변환 (Token Normalization)**: GPT-4, Claude, Gemini의 서로 다른 비용 체계를 '참조 토큰' 단위로 단일화하여 경제성 통제 기반 마련.

### P3: 인지 및 기억 동기화 (Cognition Sync)
*완성도: 현재 90% → 목표 100% (Δ +10%)*
*전략: 에이전트 간 '공동 인식(Shared Awareness)'의 농도와 선명도 관리.*

- **P3-1: 작업 기억 최적화 (Working Memory Lifecycle) [C]**
  - `P3-1-1` **컨텍스트 헬스 모니터링**: 인지 부하가 임계치를 넘지 않도록 실시간 감시하고 불필요한 이력 가지치기.
    - *인용 (CONVENTION.md §3-8)*: "Collaboration health check → Axis H (_sys/checks/check-health.bat)."
- **P3-2: 제로 토큰 대칭 기억 (Symmetric Memory) [B]**
  - `P3-2-1` [변경됨] **블랙보드 시스템 (Blackboard)**: 채팅 창이 아닌 파일 기반으로 심층 분석 결과를 공유하여 토큰 소모 최소화 및 정밀도 향상.
    - *인용 (PROTOCOL.md §P-11)*: "To prevent Context Decay... a file-based blackboard system is used instead of chat prompts."
- **P3-3: 도메인 및 프로젝트 메모리 (Domain Persistence) [B]**
  - `P3-3-1` **장기 지속 지식 저장**: 세션이 끝나도 사라지지 않는 프로젝트 전용 규칙 저장소(`MEMORY.md` 등) 활용.

### P4: 분산 협업 및 오케스트레이션 (Execution & Consensus)
*완성도: 현재 65% → 목표 95% (Δ +30%)*
*전략: 중앙 집중식 통제가 아닌, 역할 기반의 분산 합의 및 병렬 실행 체계 구축.*

- **P4-1: 역할 기반 작업 분할 (Division of Labor) [B]**
  - `P4-1-1` **가상 역할 할당 (Virtual Roles)**: Architect, Coder, Reviewer 등의 역할을 동적으로 부여하고 이에 따른 권한 및 책임 제어.
- **P4-2: 합의 및 투표 프로토콜 (Consensus) [C]**
  - `P4-2-1` [변경됨] **정족수 기반 의사결정**: 만장일치부터 다수결까지 상황에 맞는 합의 강도(Depth) 조정.
    - *인용 (PROTOCOL.md §P-3)*: "Unanimous consensus must be completed before task execution... No limit on the number of consensus rounds."
- **P4-3: 병렬 실행 및 충돌 방지 (Parallelism Control) [C]**
  - `P4-3-1` **쓰기 잠금(Write Lock) 메커니즘**: 동일 파일에 대한 다중 에이전트의 동시 수정을 원천 차단하여 상태 일관성 유지.

### P5: 무결성 및 기능 검증 (Integrity Gate)
*완성도: 현재 75% → 목표 100% (Δ +25%)*
*전략: AI의 자유로운 창작물을 결정론적(Deterministic) 필터를 통해 검증 및 승인.*

- **P5-1: 정책 강제 (Policy Enforcement) [B]**
  - `P5-1-1` **정적 정책 게이트**: 코드 스타일, 보안 취약점, 거버넌스 규칙 위반 여부를 커밋 전 자동 검사(Axis-J).
- **P5-2: 기능적 정합성 검증 (Functional Test) [C]**
  - `P5-2-1` [추가됨] **자동화된 테스트 게이트**: 신규 코드가 기존 기능(Regression)을 파괴하지 않음을 테스트 코드로 입증한 후 다음 단계 이행.
- **P5-3: 외부 호출 보안 (Invocation Policy) [B]**
  - `P5-3-1` **비가역 작업 승인**: 사이드 이펙트가 있는 외부 명령 실행 시 추가적인 합의 또는 인간 승인 강제.

### P6: 운영 경제성 통제 (Ops & Economy)
*완성도: 현재 50% → 목표 90% (Δ +40%)*
*전략: 자원 소모의 효율성을 추적하고 비정상적 폭주를 시스템적으로 차단.*

- **P6-1: 예산 및 쿼터 관리 (Economic Governance) [C]**
  - `P6-1-1` **실시간 예산 추적**: 일일 토큰 한도 및 비용을 실시간으로 계산하여 `token_budget_warn_pct` 도달 시 경고 발령.
- **P6-2: 시스템 관측성 (Observability) [C]**
  - `P6-2-1` **거버넌스 대시보드**: 에이전트의 상태, 협업 밀도, 시스템 헬스를 인간이 직관적으로 파악할 수 있는 지표 제공.
- **P6-3: 오류 루프 감지 (Error Mitigation) [B]**
  - `P6-3-1` **3-Strike 규칙**: 동일 오류가 3회 반복될 경우 강제 중단 및 인간 개입 요청(ESCALATE).
    - *인용 (PROTOCOL.md §M-3)*: "If the same error repeats 3 times, immediately HALT and restart consultation."

### P7: 인도 및 카이젠 (Delivery & Kaizen)
*완성도: 현재 40% → 목표 95% (Δ +55%)*
*전략: 결과물 인도를 넘어 '지식의 개선'과 '루프 폐쇄'를 최종 산출물로 정의.*

- **P7-1: 공식 인도 절차 (Formal Delivery) [B]**
  - `P7-1-1` **인수 테스트 및 승인 (HitL)**: 인간의 명시적인 승인 절차를 거쳐 작업 종결 처리.
- **P7-2: 사후 분석 및 지침 고도화 (Post-Mortem & Kaizen) [C]**
  - `P7-2-1` [추가됨] **자동화된 실패 분석**: 모든 오류나 비효율 사례는 향후 재발 방지를 위한 규칙(`CONVENTION.md` 등) 업데이트로 전환.
- **P7-3: 연속성 확보 및 루프 클로징 (Session Handoff & Loop Closing) [B]**
  - `P7-3-1` [변경됨] **차기 작업 시드 생성**: 현재 세션 종료 시, 다음 세션(P1)에서 즉시 이어서 작업할 수 있도록 미해결 과제와 맥락을 포함한 요약본 생성.
  - `P7-3-2` [추가됨] **목표 부합성 검증**: 최종 산출물이 P1에서 정의한 Goal ID 및 인수 기준과 100% 일치하는지 대조하여 루프를 닫음.

---

## §3. 시스템 파라미터 및 트레이드오프 (Control Parameters)

### §3.1 조절 가능한 트레이드오프 (Manageable Trade-offs)

| ID | 트레이드오프 (A vs B) | 조절 파라미터 | 설명 및 기준 |
|:---|:----------------------|:--------------|:-------------|
| **T1** | 제로토큰(비용) vs 협업수준 | `collab_rate` | 높을수록 정밀 검증(비용↑), 낮을수록 자율성(속도↑). |
| **T2** | 의사결정 속도 vs 정밀도 | `consensus_timeout` | 대규모 노드 시 타임아웃을 짧게, 정밀 작업 시 길게 설정. |
| **T3** | 기억의 양 vs 신선도 | `resolved_item_ttl` | 짧을수록 메모리 쾌적, 길수록 장기 맥락 유지 유리. |
| **T4** | 보안 엄격도 vs 개발 속도 | `policy_gate_strictness` | 하이 리스크 작업 시 모든 게이트 강제, 로우 리스크 시 일부 생략. |

### §3.2 논리적 모순 (Logical Contradictions - Fixed Constraints)

| ID | 모순 항목 | 대응 전략 (Resolution) |
|:---|:----------|:----------------------|
| **C1** | AI의 비결정론 vs 거버넌스의 결정론 | 생성은 AI(휴리스틱), 검증은 스크립트(결정론)로 층(Layer) 분리. |
| **C2** | 완벽한 로깅 vs 메모리 제한 | 원본 로그는 파일(Disk)에, 요약 정보만 컨텍스트(RAM)에 유지. |
| **C3** | 병렬 실행 속도 vs 데이터 정합성 | 파일 단위 락(Lock)을 통해 간섭 없는 영역만 병렬화 허용. |

---

## §4. 거버넌스 제어 파라미터 명세 (System Parameters)

| 파라미터명 (Variable Name) | 타입 | 범위 | 기본값 | 의미 및 활용 기준 |
|:---------------------------|:----:|:----:|:-------|:------------------|
| `collab_rate` | Int | 0~10 | 8 | 시스템 전반의 AI 협업 강도. R:10은 모든 행동 전 합의 필수. |
| `max_depth_quorum_pct` | Int | 51~100| 100 | 합의 통과를 위한 활성 노드 찬성 비율(%). |
| `consensus_timeout_min` | Int | 1~60 | 30 | 투표 대기 최대 시간. 초과 시 교착 상태로 간주하여 에스컬레이션. |
| `large_payload_threshold` | Int | 1000~∞| 4000 | 메일박스 통신 시 대용량 페이로드 오프로드 기준 길이. |
| `context_health_green_kb` | Int | 100~5000| 600 | 작업 기억 장치의 안전 권장 용량(KB). |
| `token_budget_daily` | Int | 1000~∞| 50000 | 일일 허용 참조 토큰 총량. |
| `governance_review_days` | Int | 7~365 | 30 | 거버넌스 문서의 정기 재검토 주기. |

---

## §5. 재현 가능한 측정 방법 및 지표 (Indicators & KPIs)

### §5.1 공통 측정 방법 (General)
- **완성도 (%)**: `(실제 통과된 항목 수 / 전체 항목 수) * 100`
- **품질 지수**: 각 Phase별 정의된 KPI의 PASS/FAIL 비율 기록.

### §5.2 특정 구현체 측정 (Specific - Windows Sandbox)

| 대상 Phase | 측정 방법 (Shell Command) | 목표 수치 |
|:-----------|:--------------------------|:---------|
| **P1 (의도)** | `Select-String -Path ".ai\sessions\*\handoff.md" -Pattern "## \[GOAL\]"` | 100% 검출 |
| **P3 (기억)** | `_sys\checks\check-health.bat` 실행 후 `GREEN` 상태 확인 | PASS |
| **P5 (무결성)** | `_sys\checks\check-policy.bat` 실행 후 `ERROR` 0건 확인 | 0건 |
| **P6 (경제성)** | `python _sys\cli\manage.py usage --check-budget` | `budget_util < 90%` |
| **P7 (인도)** | `Select-String -Path ".ai\sessions\*\handoff.md" -Pattern "HUMAN_ACK"` | 100% 검출 |

---

## §6. 공통 및 개별 사항의 분리 (General vs. Specific)

### §6.1 공통 원칙 (General Layer - 모든 벤더 및 환경 공통)
1. **단일 진실 공급원(SSOT)**: 모든 설정 파라미터는 하드코딩되지 않고 중앙 집중화된 단일 파일에서 관리되어야 한다.
2. **역할 기반 위임(Role-based Delegation)**: 작업 지시는 특정 노드 ID가 아닌 역할(Architect, Coder 등)에게 할당되어야 한다.
3. **불변의 감사 로그(Immutable Audit Log)**: 에이전트 간의 모든 합의 이력은 삭제되거나 수정될 수 없으며 영구 보관되어야 한다.

### §6.2 개별 사례 (Specific Layer - 현재 포터블 샌드박스 기준)
- **저장소 구조**: `_sys/` (시스템), `workspace/` (작업영역), `.ai/` (상태)
- **핵심 통제 스크립트**: `hub.py` (중앙 브로커), `msg.bat` (통신 인터페이스)
- **메모리 아키텍처**: `handoff.md` (공유 칠판), `MEMORY.md` (장기 기억 저장소)

---
*End of TAXONOMY_v8_DRAFT.md*
