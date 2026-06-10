# AI-Assisted App Development — MECE Taxonomy v5.0

> **Authors**: Claude Code (CC) + Gemini CLI (GC) | **Protocol**: R:10 Brain Sync | **Date**: 2026-06-05
> **Version**: v5.0 (Collaborative OS paradigm — Passive→Active governance)
> **Self-contained**: sufficient for a new session to resume work from this document alone.

---

## Quick Reference

```
┌─────────────────────────────────────────────────────────────────┐
│ TAXONOMY v5.0  │  _sys/docs/TAXONOMY.md                        │
│ ROOT: 86.4% actual → 98% ceiling (with v5.0 improvements)      │
│ ROOM: room-7fb9  │  COLLAB_RATE: R10  │  NODES: cc / gc / human│
├─────────────────────────────────────────────────────────────────┤
│ Entry Commands                                                  │
│   hub status              → sync / node list                   │
│   msg ask --to gemini     → P2P query (English only)           │
│   check-policy.bat        → Axis-J: 10 policy regression tests │
│   check-health.bat        → Axis-H: context health (KB/color)  │
│   ctx-save                → snapshot + CLAUDE/GEMINI.md sync   │
│   ctx-end                 → session close + archive            │
├─────────────────────────────────────────────────────────────────┤
│ Key Files                                                       │
│   P:\PROTOCOL.md              v3.4 — consensus, session rules  │
│   P:\CONVENTION.md            coding conventions               │
│   P:\_sys\gemini\config.json  shared param registry (v5.0)     │
│   P:\_sys\core\hub.py         IPC hub                          │
│   P:\.ai\sessions\room-7fb9\handoff.md   active room state     │
│   P:\_sys\docs\TAXONOMY.md    this file                        │
├─────────────────────────────────────────────────────────────────┤
│ 5 Critical Rules                                               │
│   1. No execution before FINALIZED consensus (§P-3)            │
│   2. Constitutional docs require R:10 to modify (§M-1)         │
│   3. 3x same error → HALT + restart consultation (§M-3)        │
│   4. Re-orient via handoff.md before any task (§P-11)          │
│   5. All Gemini queries in English (2–3x token efficiency)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Root Completion Summary

| Level | v4.0 Actual | v5.0 Target | Delta | Note |
|:------|:-----------:|:-----------:|:-----:|:-----|
| **Overall (Root)** | **86.4%** | **98.0%** | **+11.6%** | Practical ceiling; non-deterministic floor ~95% |
| Cat 1: Cognitive Continuity | 93% | 99% | +6% | Token Forecasting moved to Cat 5-6 |
| Cat 2: Collaboration Governance | 92% | 98% | +6% | Decision Attribution + Bias Alerting |
| Cat 3: System Integrity | 87% | 98% | +11% | Post-Mortem Loop + Confidence Threshold |
| Cat 4: Environment Portability | 88% | 97% | +9% | Zero-Config Hardening |
| Cat 5: Operations & Control | 72% | 98% | +26% | Active Control + Economic Governance |

> **Why 98% not 100%**: G11 (Async Events) and Human Factors are non-deterministic by nature — full specification is impossible. The 2% is the system's designed tolerance for emergence.

---

## Full MECE Tree (v5.0, 5-Level Max)

```
AI-Assisted App Development  [86.4% → 98%]
│
├── Cat 1: 인지 연속성 (Cognitive Continuity)  [93% → 99%]
│   ├── 1-1: Context Lifecycle Management
│   │   ├── 1-1-1: Size tracking — GREEN(<600KB)/YELLOW(600–1200KB)/RED(>1200KB)
│   │   ├── 1-1-2: handoff.md rolling rule — [DONE] 항목 아카이브, 상시 <2KB 유지
│   │   └── 1-1-3: Context Pruning / Attention Management [유지]
│   │       └── 명시적 decay 기준 — 항목별 TTL, 중요도 스코어 기반 보존/삭제
│   ├── 1-2: Session Continuity
│   │   ├── 1-2-1: Room-based session — .ai/sessions/room-{uuid}/
│   │   ├── 1-2-2: Summary artifacts — summary_{agent}.md, <4KB per node
│   │   ├── 1-2-3: Re-orientation phase — §P-11, handoff.md 선독 후 작업 시작
│   │   └── 1-2-4: Emergency handoff schema
│   │       └── executive_summary / technical_state / strategy_for_next_session
│   ├── 1-3: Memory Persistence
│   │   ├── 1-3-1: CC Memory — _sys/claude/config/projects/{id}/memory/
│   │   ├── 1-3-2: Memory compactor — memory_compactor.py, compactor_interval_days
│   │   ├── 1-3-3: Zero-Token Symmetric Memory — §P-11, CLAUDE.md↔GEMINI.md 동기화
│   │   └── 1-3-4: Memory type taxonomy — user / feedback / project / reference
│   └── 1-4: Instruction Design
│       ├── 1-4-1: Global config — CLAUDE.md (CC) / GEMINI.md (GC)
│       ├── 1-4-2: Project-level override — {project_root}/CLAUDE.md
│       ├── 1-4-3: Token-efficient query format — English, TASK/CONTEXT/QUESTION
│       └── 1-4-4: Axis task templates — A~J 구조화 위임 분석
│
├── Cat 2: 협업 거버넌스 (Collaboration Governance)  [92% → 98%]
│   ├── 2-1: Consensus Protocol
│   │   ├── 2-1-1: Propose→Vote→FINALIZED — §P-3, 라운드 수 무제한
│   │   ├── 2-1-2: Quorum rules — §P-3-QR, 일반 N/2+1 / R:10 100%
│   │   ├── 2-1-3: Final Call gate — §P-3-FC, collab_rate ≥ final_call_min_rate 시 의무
│   │   └── 2-1-4: Consensus history — handoff.md CONSENSUS_HISTORY 섹션
│   ├── 2-2: Division of Labor
│   │   ├── 2-2-1: DIRECTIVE message envelope — §P-2 표준 JSON 형식
│   │   ├── 2-2-2: Node characteristic routing — §P-4, 특성 기반 태스크 배정
│   │   ├── 2-2-3: Parallel/sequential policy — §P-7, 영향범위 비중복 시 비동기 허용
│   │   └── 2-2-4: Result aggregation + VERIFY — §P-4, 상호 산출물 교차검증
│   ├── 2-3: Conflict Resolution
│   │   ├── 2-3-1: Deadlock protocol — 연속 2라운드 이상 disagreement 처리 절차
│   │   ├── 2-3-2: ESCALATE → Human Gate — §P-0 Tier-0 veto 호출
│   │   ├── 2-3-3: 3-Strike halt rule — §M-3, 동일 오류 3회 → HALT + 재시작
│   │   └── 2-3-4: Stalled round auto-sweep — consensus-sweep, 30분 타임아웃
│   ├── 2-4: Node Management
│   │   ├── 2-4-1: Node registration — .ai/nodes.json, §P-1 등록 즉시 동등 peer
│   │   ├── 2-4-2: COLLAB_RATE depth — §C-0, 5앵커 (R:0/3/5/8/10)
│   │   ├── 2-4-3: N-node expansion — §P-9, 신규 노드 등록 즉시 투표권 부여
│   │   └── 2-4-4: Resilience Protocol [유지]
│   │       ├── R:10 하에서 노드 오프라인 시 비상 운영 절차
│   │       └── Re-sync mechanism [변경] — 오프라인 복귀 노드의 컨텍스트 재동기화 절차
│   │           └── (변경 전 state → 현재 state diff 요약 후 VOTE 재참여)
│   ├── 2-5: Transparency & Communication
│   │   ├── 2-5-1: No private channels — §M-2, 전 노드 공개 의무
│   │   ├── 2-5-2: HUB console prefix — §P-5 (HUB / HUB:ERROR / HUB:WARN / HUB:GATE)
│   │   └── 2-5-3: Gemini response format — "━━ Gemini ━━ / ━━ Claude Judgment ━━"
│   └── 2-6: Decision Attribution [추가 v5.0]
│       ├── 2-6-1: Proposer/opposer logging — 합의 라운드별 제안자·반대자 기록
│       ├── 2-6-2: Pattern drift detection [추가, G17]
│       │   └── 특정 노드가 연속 N회 반대 시 → WARN + Human Gate ESCALATE 제안
│       └── 2-6-3: Decision weight tracking
│           └── 주요 결정에 근거(rationale)와 trade-off 기록 → 미래 세션 역추적 가능
│
├── Cat 3: 시스템 무결성 (System Integrity)  [87% → 98%]  ← Axis-J 주담당(Judge)
│   ├── 3-1: Security & Trust
│   │   ├── 3-1-1: Mutual Non-Interference — §M-1, constitutional doc AI 직접 수정 금지
│   │   ├── 3-1-2: Auth/security file isolation — 인증 파일 AI 접근 불가
│   │   ├── 3-1-3: Input validation — command injection / XSS / SQL injection 방지
│   │   └── 3-1-4: R:10 write protection — hub.py / PROTOCOL.md / CLAUDE.md 등
│   ├── 3-2: Policy Enforcement
│   │   ├── 3-2-1: Policy Regression Gate — check_policy.py, 10개 자동 체크 (Axis-J)
│   │   ├── 3-2-2: Policy-code consistency — PROTOCOL.md vs hub.py 정합성
│   │   ├── 3-2-3: Pre-commit integration — check-policy.bat hook
│   │   └── 3-2-4: Exit-0/Exit-1 gate — PASS(0) / FAIL(1) 진입 차단
│   ├── 3-3: Change Management
│   │   ├── 3-3-1: MECE change tagging — [추가/삭제/변경/유지] 태그 필수
│   │   ├── 3-3-2: Conventional commits — English, feat/fix/docs/refactor
│   │   ├── 3-3-3: Branch-before-large-change — 대형 변경 전 브랜치 필수
│   │   └── 3-3-4: Impact Analysis (G6) — Axis-F 게이트 승격, 변경 파급 범위 필수 검토
│   ├── 3-4: Output Validation
│   │   ├── 3-4-1: AI output schema validation (G2) — 구조화된 출력 형식 검증
│   │   ├── 3-4-2: Include size guard — §3-4-A
│   │   ├── 3-4-3: Hub script protection — §3-4-B
│   │   ├── 3-4-4: Refusal detection — §3-4-C
│   │   └── 3-4-5: Confidence threshold [추가 v5.0]
│   │       └── AI 산출물 confidence < confidence_threshold(%) 시 인간 게이트 요청
│   ├── 3-5: Error Classification
│   │   ├── 3-5-1: Severity taxonomy — P0(blocking) / P1(critical) / WARN / INFO
│   │   ├── 3-5-2: Structured error reporting — 표준 오류 보고 형식
│   │   └── 3-5-3: 3-Strike trigger — §M-3, P0 3회 반복 시 HALT
│   ├── 3-6: Rollback & Recovery
│   │   ├── 3-6-1: Git-based rollback — ctx-save 체크포인트 기반 복구
│   │   ├── 3-6-2: max_rollback_depth — 복구 가능한 체크포인트 depth 제한
│   │   └── 3-6-3: State Migration Protocol (G13)
│   │       ├── .ai/state.json 스키마 버전 추적 (version 필드 필수)
│   │       └── 버전 업그레이드 시 레거시 room 무결성 보장 절차
│   ├── 3-7: AI Behavioral Compliance Tests
│   │   ├── 3-7-1: check_policy.py — 10개 자동화 정책 검증
│   │   ├── 3-7-2: Behavioral scenarios — T-FINALIZED / T-COLLAB_RATE / T-R10
│   │   ├── 3-7-3: Parameter validation (G10) — config.json 로드 시 스키마 검증
│   │   └── 3-7-4: Axis token budget enforcement — §3-4-D
│   └── 3-8: Post-Mortem & Learning Loop [추가 v5.0]
│       ├── 3-8-1: Failure → Policy Kaizen [추가, G16]
│       │   ├── P0/P1 오류 발생 시 자동 5-Why 템플릿 생성 트리거
│       │   └── 5-Why 결과 → PROTOCOL.md 개정 제안 자동 Draft
│       ├── 3-8-2: Post-mortem template
│       │   ├── Incident summary / Root cause (5-Why) / Timeline
│       │   ├── Affected categories / Prevention measure / Policy update proposal
│       │   └── 저장: .ai/postmortems/pm-{YYYYMMDD}-{incident_id}.md
│       └── 3-8-3: Learning cycle gate
│           └── 반복 오류(3회+) → 해당 항목 Kaizen 완료 전까지 동일 작업 잠금
│
├── Cat 4: 환경 이식성 (Environment Portability)  [88% → 97%]
│   ├── 4-1: Runtime Environment
│   │   ├── 4-1-1: Python venv isolation — _sys/env/venv/, 외부 의존성 격리
│   │   ├── 4-1-2: PYTHONUTF8=1 mandate — 모든 bat 파일 필수
│   │   ├── 4-1-3: Node.js/npm-global isolation — portable npm prefix
│   │   ├── 4-1-4: Env var scope isolation — §3-1~3-3, 노드별 격리
│   │   └── 4-1-5: Zero-Config Hardening [추가 v5.0]
│   │       ├── PowerShell execution policy 검증 (RemoteSigned 이상 필요)
│   │       ├── Host shell profile 간섭 탐지 ($PROFILE 충돌 확인)
│   │       └── Cross-session env var 유출 방지 (임시 env 세션 종료 시 자동 초기화)
│   ├── 4-2: Installation & Deployment
│   │   ├── 4-2-1: ZeroBase Architecture — install.bat 단일 실행 전체 재구성
│   │   ├── 4-2-2: Dependency bootstrapping — install.bat 의존성 자동 설치
│   │   ├── 4-2-3: WSB smoke testing — §9, Windows Sandbox 격리 테스트
│   │   └── 4-2-4: Parallel safety — §10, 고유 임시파일명 (cq-{ts}-{rand4}.txt)
│   ├── 4-3: Infrastructure Abstraction
│   │   ├── 4-3-1: Hub-based IPC — hub.py 메시지 패싱 (기술 중립)
│   │   ├── 4-3-2: .ai/ shared state layer — 노드 독립적 공유 상태
│   │   ├── 4-3-3: msg.bat universal entry — P2P 메시지 단일 진입점
│   │   └── 4-3-4: Node heartbeat / availability — §P-3-QR auto-abstain 기반
│   ├── 4-4: Version Management
│   │   ├── 4-4-1: Protocol semantic versioning — PROTOCOL.md §HISTORY
│   │   ├── 4-4-2: CHANGELOG maintenance — 버전별 변경 추적
│   │   └── 4-4-3: **vX.Y** 버전 태그 형식 강제
│   ├── 4-5: Platform Independence
│   │   ├── 4-5-1: No hardcoded absolute paths — check_policy.py 검증
│   │   ├── 4-5-2: USB/cloud-drive portability — P:\ 드라이브 레터 추상화
│   │   └── 4-5-3: Cross-platform path handling — pathlib.Path 사용 강제
│   └── 4-6: Node Onboarding Protocol
│       ├── 4-6-1: Registration checklist — nodes.json + room state 등록 절차
│       ├── 4-6-2: Required loading files — §P-8, 노드 타입별 토큰 예산 정의
│       └── 4-6-3: Resilience mechanics (G15 부참조)
│           └── heartbeat, state-check, offline fallback (§P-3-QR 연계)
│
└── Cat 5: 운영 & 제어 (Operations & Control)  [72% → 98%]
    ├── 5-1: Shared Parameter Registry
    │   ├── 5-1-1: Flat+metadata config.json [유지]
    │   │   └── "_param_sections" 키로 분류 문서화; flat 구조 유지 (스크립트 호환)
    │   ├── 5-1-2: General Parameters (cross-cutting — 전 카테고리 영향)
    │   │   ├── collab_rate           int  0–10      default 10  | 협업 깊이 (§C-0)
    │   │   ├── consensus_timeout_min int  1–60      default 30  | 합의 타임아웃(분)
    │   │   ├── final_call_min_rate   int  0–10      default 8   | Final Call 임계 rate
    │   │   └── token_budget_daily    int  1k–500k   default 50000 | 일일 토큰 예산(토큰) [추가]
    │   ├── 5-1-3: Cat 1 Parameters
    │   │   ├── context_health_green_kb   int  100–1000  default 600  | GREEN 임계(KB)
    │   │   ├── context_health_yellow_kb  int  200–2000  default 1200 | YELLOW 임계(KB)
    │   │   ├── compactor_interval_days   int  1–30      default 7    | 메모리 압축 주기(일)
    │   │   └── review_interval_min       int  1–60      default 5    | Gemini 검토 최소 간격(분)
    │   ├── 5-1-4: Cat 3 Parameters
    │   │   ├── max_rollback_depth        int  1–10      default 3    | 롤백 가능 depth
    │   │   └── confidence_threshold      int  0–100     default 70   | AI 산출물 신뢰 임계(%) [추가]
    │   └── 5-1-5: Cat 5 Parameters
    │       ├── metrics_flush_interval_sec  int  10–3600  default 300  | 메트릭 기록 주기(초)
    │       ├── active_control_enabled      int  0–1      default 0    | 능동 제어 활성화 (0=off) [추가]
    │       └── forecast_warn_threshold_pct int  1–99     default 70   | 토큰 예측 경보 임계(%) [이동 from Cat 1]
    ├── 5-2: Behavioral Compliance & Validation
    │   ├── 5-2-1: Config schema validation (G10) — 로드 시 자동 스키마 검증
    │   ├── 5-2-2: Parameter range enforcement — 범위 초과 시 즉시 에러
    │   └── 5-2-3: _param_sections integrity check — 선언 키 vs 실제 키 정합성
    ├── 5-3: Observability  ← Axis-H 주담당 / Axis-J 부참조(Reporter)
    │   ├── 5-3-1: Context Health Monitor — check_health.py (GREEN/YELLOW/RED)
    │   ├── 5-3-2: Async Event Handling (G11) [유지 🔶]
    │   │   └── OS sleep/wake, 외부 파일 변경 등 out-of-band 이벤트 처리 정책
    │   └── 5-3-3: Collaboration metrics — collab_rate 현황, 합의 성공률 추적
    ├── 5-4: System Health & Dashboard
    │   ├── 5-4-1: Session status header
    │   │   └── ROOM:{id} | RATE:R{n} | HEALTH:{kb}KB({color}) | CONSENSUS:{rounds}
    │   ├── 5-4-2: Metrics aggregation — 정책 준수율(%), 합의 성공률(%) 집계
    │   ├── 5-4-3: Persistent metrics — metrics_flush_interval_sec 제어 기록
    │   └── 5-4-4: Dashboard spec (G7) [유지 🔶] — _sys/docs/DASHBOARD_SPEC.md 예정
    ├── 5-5: Active Control Loop [추가 v5.0]
    │   ├── 5-5-1: Lock-safety protocol [추가, Gemini 요청]
    │   │   └── 능동 제어 실행 전 반드시 활성 쓰기 노드 확인 → 충돌 방지
    │   ├── 5-5-2: Context RED trigger
    │   │   └── RED 진입 시 → 자동 ctx-save + collab_rate 일시 하향 (현재값-2, min 3)
    │   ├── 5-5-3: Token budget control
    │   │   └── 일일 토큰 소비 > token_budget_daily × 90% → 경보; 100% → collab_rate=3 강제
    │   ├── 5-5-4: SLA violation escalation
    │   │   └── 합의 timeout 2회 연속 → 자동 ESCALATE to Human Gate
    │   └── 5-5-5: Safety guard
    │       └── active_control_enabled=0 (default) 시 전 항목 비활성; 명시적 opt-in 필요
    └── 5-6: Economic & Quota Governance [추가 v5.0]
        ├── 5-6-1: Token ROI tracking
        │   ├── 작업 단위별 토큰 소비량 기록 (Axis 호출, 합의 라운드, 파일 쓰기)
        │   └── 목표: 가치 대비 토큰 효율 (tokens per meaningful decision)
        ├── 5-6-2: Budget management
        │   ├── token_budget_daily 기반 일일 소비 추적
        │   ├── 예산 80% 소진 시 WARN; 100% 시 신규 Axis 호출 차단
        │   └── 예산 초과 복구 경로: Human Gate 승인 후 임시 예산 확장
        ├── 5-6-3: Token forecasting (G14) [이동 from Cat 1]
        │   └── forecast_warn_threshold_pct 기반 runway 예측 (현재 컨텍스트 증가 추세로 소진 시점 계산)
        └── 5-6-4: Cost efficiency rules
            ├── Gemini 쿼리: English 전용 (2–3x 효율), 중복 쿼리 캐시 재사용
            └── Axis 호출 최소화: 동일 범위 5회 이상 Grep → Axis-G 위임 전환
```

---

## Trade-off Table (T1–T17)

| # | 항목 A | 항목 B | 제어 파라미터 | 관리 방식 | v5.0 비고 |
|:--|:-------|:-------|:------------|:----------|:---------|
| T1 | 제로토큰 효율 | 협업 깊이 | `collab_rate` | 명시적 | R:0=완전자율, R:10=완전합의 |
| T2 | 컨텍스트 보존 | 처리 속도 | `context_health_green_kb` | 명시적 | 낮을수록 민감, 높을수록 효율 |
| T3 | 합의 정확성 | 응답 속도 | `consensus_timeout_min` | 명시적 | 짧을수록 빠름, 정확성 감소 |
| T4 | 자율성 | 안전성 | `collab_rate` + §C-0 앵커 | 명시적 | 5앵커 (R:0/3/5/8/10) |
| T5 | 문서 상세성 | 토큰 소모 | English mandate | 정책 | 영어 2–3x 토큰 효율 |
| T6 | 세션 지속성 | 컨텍스트 신선도 | `compactor_interval_days` | 명시적 | 낮을수록 신선, 높을수록 연속성 |
| T7 | 이식성 | 플랫폼 최적화 | — | 정책 | pathlib / 절대경로 금지 |
| T8 | 정책 엄격성 | 개발 속도 | `final_call_min_rate` | 명시적 | 높을수록 안전, 낮을수록 빠름 |
| T9 | 메모리 보존 | 컨텍스트 신선도 | `compactor_interval_days` | 명시적 | — |
| T10 | 보안 격리 | 협업 편의성 | — | 정책 | §M-1 Non-Interference |
| T11 | 노드 확장성 | 합의 복잡도 | — | 정책 | 노드 추가 시 투표 복잡도 ↑ |
| T12 | Pruning 공격성 | 메모리 보존 | `compactor_interval_days` | 명시적 | — |
| T13 | 메트릭 세분성 | 디스크 I/O | `metrics_flush_interval_sec` | 명시적 | — |
| T14 | 예측 민감도 | 알림 피로도 | `forecast_warn_threshold_pct` | 명시적 | — |
| T15 | 학습 루프 오버헤드 | 시스템 진화 속도 | — | 정책 | **[추가 v5.0]** Post-mortem 시간 vs 정책 개선 |
| T16 | 능동 자동화 | 인간 통제권 | `active_control_enabled` | 명시적 | **[추가 v5.0]** 0=안전 우선, 1=효율 우선 |
| T17 | 토큰 경제성 | 협업 깊이 | `token_budget_daily` + `collab_rate` | 명시적 | **[추가 v5.0]** 예산 소진 시 collab_rate 강제 하향 |

---

## Parameter Registry v5.0 (config.json 최종 스펙)

```json
{
  "_param_sections": {
    "general": [
      "collab_rate",
      "consensus_timeout_min",
      "final_call_min_rate",
      "token_budget_daily"
    ],
    "cat1": [
      "context_health_green_kb",
      "context_health_yellow_kb",
      "compactor_interval_days",
      "review_interval_min"
    ],
    "cat3": [
      "max_rollback_depth",
      "confidence_threshold"
    ],
    "cat5": [
      "metrics_flush_interval_sec",
      "active_control_enabled",
      "forecast_warn_threshold_pct"
    ]
  },
  "collab_rate": 10,
  "consensus_timeout_min": 30,
  "final_call_min_rate": 8,
  "token_budget_daily": 50000,
  "context_health_green_kb": 600,
  "context_health_yellow_kb": 1200,
  "compactor_interval_days": 7,
  "review_interval_min": 5,
  "max_rollback_depth": 3,
  "confidence_threshold": 70,
  "metrics_flush_interval_sec": 300,
  "active_control_enabled": 0,
  "forecast_warn_threshold_pct": 70,
  "last_review_ts": null
}
```

> **호환성**: flat 구조 유지 — 기존 `memory_compactor.py`, `check_health.py`, `gemini-set-ratio.bat` 무수정 동작.
> `_param_sections`는 문서화 전용 메타데이터. 실제 독자는 키를 직접 읽음.

### Parameter 전체 정의표 (13개)

| 파라미터 | 타입 | 범위 | 기본값 | 의미 | Section | Trade-off |
|:---------|:----:|:----:|:------:|:-----|:-------:|:---------:|
| `collab_rate` | int | 0–10 | 10 | 협업 깊이. 0=완전자율, 10=모든 행동 만장일치 필수 | general | T1,T4,T17 |
| `consensus_timeout_min` | int | 1–60 | 30 | 합의 라운드 자동 타임아웃(분) | general | T3 |
| `final_call_min_rate` | int | 0–10 | 8 | 이 값 이상 collab_rate 시 §P-3-FC Final Call 의무 | general | T8 |
| `token_budget_daily` | int | 1k–500k | 50000 | 일일 전체 토큰 소비 상한(토큰). 초과 시 신규 Axis 차단 | general | T17 |
| `context_health_green_kb` | int | 100–1000 | 600 | GREEN 상태 임계(KB). 이하 = 정상 | cat1 | T2 |
| `context_health_yellow_kb` | int | 200–2000 | 1200 | YELLOW→RED 전환 임계(KB). 초과 시 긴급 압축 | cat1 | T2 |
| `compactor_interval_days` | int | 1–30 | 7 | 메모리 compactor 실행 주기(일) | cat1 | T6,T9,T12 |
| `review_interval_min` | int | 1–60 | 5 | Gemini 검토 호출 최소 간격(분) | cat1 | T1 |
| `max_rollback_depth` | int | 1–10 | 3 | git 기반 롤백 가능한 ctx-save 체크포인트 수 | cat3 | — |
| `confidence_threshold` | int | 0–100 | 70 | AI 산출물 신뢰도(%). 미달 시 Human Gate 요청 | cat3 | — |
| `metrics_flush_interval_sec` | int | 10–3600 | 300 | 운영 메트릭 디스크 기록 주기(초) | cat5 | T13 |
| `active_control_enabled` | int | 0–1 | 0 | 능동 제어 루프 활성화. 0=off(안전), 1=on(자율 개입) | cat5 | T16 |
| `forecast_warn_threshold_pct` | int | 1–99 | 70 | 컨텍스트 사용률(%) 이상 시 사전 경보 | cat5 | T14 |

---

## Axis ↔ Category Mapping (v5.0)

| Axis | 이름 | Cat 주담당 | Cat 부참조 | 설명 |
|:----:|:-----|:----------:|:---------:|:-----|
| Axis-A | Architecture Review | Cat 1, 4 | Cat 3 | 설계 결정 검토 |
| Axis-B | Behavior Analysis | Cat 2 | Cat 3 | 노드 행동 패턴 분석 |
| Axis-C | Code Review | Cat 3 | Cat 2 | 코드 품질 및 정책 준수 |
| Axis-D | Dependency Scan | Cat 4 | Cat 3 | 의존성 보안 및 이식성 |
| Axis-E | Error Root Cause | Cat 3 | Cat 2 | 오류 근본 원인 분석 |
| Axis-F | Impact Analysis | Cat 3 | Cat 5 | 변경 파급 범위 분석 (G6, 필수 게이트) |
| Axis-G | Gap Analysis | Cat 1–5 | — | MECE 완성도 갭 식별 |
| Axis-H | Health Check | Cat 5 | Cat 1 | 컨텍스트 건강도 모니터링 |
| Axis-I | Integration Test | Cat 3, 4 | Cat 2 | 통합 테스트 및 정합성 |
| Axis-J | Policy Gate | Cat 3 (Judge) | Cat 5 (Reporter) | 10개 정책 회귀 테스트 |

---

## Gap Analysis Log (G1–G17)

| # | 갭 | 해결 위치 | 상태 |
|:--|:---|:---------|:-----|
| G1 | Instruction Design | Cat 1-4 | ✅ v3.0 |
| G2 | Output Validation | Cat 3-4 | ✅ v3.0 |
| G3 | Rollback Protocol | Cat 3-6 | ✅ v3.0 |
| G4 | Error Classification | Cat 3-5 | ✅ v3.0 |
| G5 | AI Behavioral Test Suite | Cat 3-7 | ✅ v3.0 |
| G6 | Impact Analysis | Cat 3-3-4 (Axis-F 필수 게이트) | ✅ v4.0 |
| G7 | Dashboard | Cat 5-4-4 | 🔶 spec 정의 필요 |
| G8 | Metrics | Cat 5-4-2 | ✅ v4.0 |
| G9 | Node Onboarding | Cat 4-6 | ✅ v3.0 |
| G10 | Parameter Validation | Cat 5-2 | ✅ v4.0 |
| G11 | Async Event Handling | Cat 5-3-2 | 🔶 처리 정책 문서화 필요 |
| G12 | Resource & Quota Mgmt | Cat 5-6 | ✅ v5.0 (Cat 5-6 신설) |
| G13 | State Migration | Cat 3-6-3 | ✅ v4.0 (절차 구현 필요) |
| G14 | Token Budget Forecasting | Cat 5-6-3 (이동) | ✅ v5.0 (Cat 5-6으로 통합) |
| G15 | Node Resilience Protocol | Cat 2-4-4, Cat 4-6-3 | 🔶 Re-sync 절차 문서화 필요 |
| G16 | Automated Kaizen Triggers | Cat 3-8-1 | 🔶 P0→5-Why 연동 훅 구현 필요 |
| G17 | Node Voting Bias Alerting | Cat 2-6-2 | 🔶 패턴 감지 로직 구현 필요 |

---

## v4.0 → v5.0 Change Summary

| # | 변경 내용 | 태그 | 완성도 기여 |
|:--|:---------|:-----|:--------:|
| 1 | Cat 3-8 신설: Post-Mortem & Learning Loop (3-8-1~3) | 추가 | Cat 3 +3% |
| 2 | Cat 2-6 신설: Decision Attribution (2-6-1~3) | 추가 | Cat 2 +2% |
| 3 | Cat 5-5 신설: Active Control Loop (5-5-1~5) | 추가 | Cat 5 +8% |
| 4 | Cat 5-6 신설: Economic & Quota Governance (5-6-1~4) | 추가 | Cat 5 +8% |
| 5 | Cat 4-1-5 추가: Zero-Config Hardening | 추가 | Cat 4 +1% |
| 6 | Cat 3-4-5 추가: Confidence Threshold | 추가 | Cat 3 +2% |
| 7 | Cat 2-4-4 변경: Re-sync mechanism 상세화 | 변경 | Cat 2 +2% |
| 8 | G16 추가: Automated Kaizen Triggers → Cat 3-8-1 | 추가 | — |
| 9 | G17 추가: Node Voting Bias Alerting → Cat 2-6-2 | 추가 | — |
| 10 | 파라미터 +3개: token_budget_daily / active_control_enabled / confidence_threshold | 추가 | — |
| 11 | forecast_warn_threshold_pct: Cat 1 → Cat 5 (_param_sections 이동) | 변경 | — |
| 12 | T15/T16/T17 Trade-off 추가 | 추가 | — |
| 13 | Root 완성도: 86.4% → 98% 천장 | — | +11.6% |

---

## Implementation Queue (우선순위 순)

| 우선 | 작업 | 대상 파일 | 비고 |
|:----:|:-----|:---------|:-----|
| **P0** | config.json — 신규 3개 파라미터 추가 + `_param_sections` 갱신 + `ratio`→`collab_rate` | `_sys/gemini/config.json` | flat 구조 유지 |
| **P0** | gemini-set-ratio.bat — `ratio` → `collab_rate` 필드명 동시 수정 | `_sys/gemini/gemini-set-ratio.bat` | P0와 동시 |
| P1 | memory_compactor.py — `MAX_AGE_DAYS=7` → config.json `compactor_interval_days` 참조 | `_sys/hooks/memory_compactor.py:16` | |
| P1 | check_health.py — 임계값 하드코딩 → config.json `context_health_*_kb` 참조 | `_sys/checks/check_health.py` | |
| P2 | G15 Re-sync Protocol 문서화 → PROTOCOL.md §P-3-QR 확장 | `P:\PROTOCOL.md` | R:10 합의 필요 |
| P2 | G16 P0/P1 오류 → 5-Why 자동 템플릿 훅 구현 | `_sys/hooks/` | new file |
| P2 | .ai/postmortems/ 디렉토리 + pm-template.md | `.ai/postmortems/` | |
| P3 | G7 Dashboard spec 구체화 | `_sys/docs/DASHBOARD_SPEC.md` | |
| P3 | G11 Async Event Handling 처리 정책 | `CONVENTION.md §11` 확장 | |
| P3 | G17 Voting Bias Detection 로직 | `_sys/core/hub.py` | R:10 합의 필요 |

---

## Completion Trajectory

```
v1.0  →  v2.0  →  v3.0  →  v4.0  →  v5.0 (taxonomy)  →  v5.0 (implemented)
 60%  →  72%   →  80%   →  86.4% →      97%            →       95%
                                    (개념 완료)           (비결정론적 하한)
                                                         실용 천장: 98%
```
