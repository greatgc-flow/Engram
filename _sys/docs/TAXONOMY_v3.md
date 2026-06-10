# MECE Taxonomy v3.0 — AI-Assisted App Development
### Taxonomy + Measurement Framework — Zero-Context Complete

> **Authors**: Claude Code (CC) + Gemini CLI (GC) | R:10 Brain Sync | 2026-06-05
> **Sources merged**: TAXONOMY_v2.md (v5.1) + TAXONOMY_METRICS_v2.md
> **Self-contained**: usable from a zero-context new session — no prior files needed.

---

## §0. Quick Reference

```
┌──────────────────────────────────────────────────────────────────┐
│ TAXONOMY v3.0  │  _sys/docs/TAXONOMY_v3.md                      │
│ Root Score: 70.0% (Tier-based) │ 86.4% (concept-based)          │
│ COLLAB_RATE: R10 │ ROOM: room-7fb9 │ NODES: cc / gc / human     │
├──────────────────────────────────────────────────────────────────┤
│ Entry Commands                                                   │
│   hub status          → sync check, node list                   │
│   msg ask --to gemini → P2P query (English only, 2–3x efficient)│
│   check-policy.bat    → Axis-J: 10 static policy checks         │
│   check-health.bat    → Axis-H: context health (KB / color)     │
│   ctx-save            → snapshot + CLAUDE/GEMINI.md sync        │
│   ctx-end             → session close + archive                 │
├──────────────────────────────────────────────────────────────────┤
│ Key Files                                                        │
│   .\PROTOCOL.md              v3.4 — consensus / session rules   │
│   .\CONVENTION.md            coding conventions                 │
│   .\_sys\gemini\config.json  param registry (18 params, 20 keys)│
│   .\_sys\core\hub.py         IPC hub                            │
│   .\.ai\sessions\room-7fb9\handoff.md  active room state        │
│   .\_sys\docs\TAXONOMY_v3.md this file                          │
├──────────────────────────────────────────────────────────────────┤
│ 5 Critical Rules                                                 │
│   1. No execution before FINALIZED consensus (§P-3)             │
│   2. Constitutional docs require R:10 to modify (§M-1)          │
│   3. 3× same error → HALT + restart consultation (§M-3)         │
│   4. Re-orient via handoff.md before any task (§P-11)           │
│   5. All Gemini queries in English (2–3× token efficiency)      │
└──────────────────────────────────────────────────────────────────┘
```

---

## §1. Measurement Framework

### 1-1. Hybrid DoD (Definition of Done)

모든 항목은 두 유형 중 하나로 분류된다.

#### Type B — Binary / Structural
정책·문서·구조의 **존재 여부**가 핵심. 연속 모니터링 불필요.

| Tier | 달성 기준 | Score |
|:----:|:---------|:-----:|
| T0 | 미정의 | 0% |
| T1 | 정책/문서 초안 작성 완료 | 50% |
| **T2** | **정적 체크 또는 시스템 제약으로 강제 적용** | **100%** |

> 현재 Tier > 목표 Tier 이면 Score = min(current/target, 1.0) = **1.00** (상한 고정).

#### Type C — Continuous / Operational
지속적 측정·모니터링이 의미 있는 항목.

| Tier | 달성 기준 | Score |
|:----:|:---------|:-----:|
| T0 | 미정의 | 0% |
| T1 | 임계값/정의 문서화 완료 | 25% |
| T2 | 구현 존재, 수동 체크 가능 | 50% |
| T3 | 자동화 체크/스크립트 존재 | 75% |
| **T4** | **능동 모니터링 실행 중 + 임계 위반 시 자동 알림/행동** | **100%** |

### 1-2. 측정 실패 행동 (collab_rate 연동)

| collab_rate | Tier 3/4 지표 실패 시 |
|:-----------:|:-------------------|
| R:10 | **HALT + ESCALATE** — exit 1, Human Gate 호출 |
| R:5–8 | **WARN + 계속** — `.ai\metrics\health-{date}.log` 기록 |
| R:0–3 | **LOG only** — 중단 없음 |

### 1-3. Token Proxy (API 직접 카운팅 불가)

| 프록시 | 측정 방법 | 환산 |
|:-------|:---------|:-----|
| Context KB | `check_health.py` JSONL 크기 | 1 KB ≈ 250 tokens |
| Gemini 쿼리 수 | `msg.bat` 호출 횟수/일 | 1 query ≈ 2,000 tokens |
| 활동 이벤트 | FINALIZED 합의 수 | 의사결정 대리 지표 |

Token ROI 분자 = `count(FINALIZED_DIRECTIVEs) + count(merged PRs)` (객관적 이벤트).

### 1-4. ZeroBase 측정 환경 기준

- 모든 측정 명령: **PowerShell 5.1 native** only (POSIX grep/wc/awk 금지)
- 경로: 드라이브 레터 독립적 — `.\` 상대경로 또는 `$env:BASE_DIR` 사용
- 측정 실행 기준: ZeroBase (Windows 11, PS 5.1, Python 3 venv, Node.js)

---

## §2. Root Completion Dashboard

### 2-1. 완성도 개념 구분

| 지표 | 값 | 의미 |
|:-----|:--:|:-----|
| **개념 완성도** | **86.4%** | 모든 항목이 taxonomy에 정의됨 |
| **시스템 완성도** | **70.0%** | Tier 달성 기준 (자동화 검증까지 완료) |
| **실용 천장** | **98%** | G11(Async)/Human Factors 비결정론적 2% 허용 |

두 지표를 함께 보아야 정확한 상태 파악 가능.

### 2-2. 카테고리별 현재 상태 (가중 Root Score)

| Cat | 카테고리 | 가중치 | 현재 Score | 목표 Score | 기여 현재 | 기여 목표 |
|:---:|:---------|:------:|:---------:|:---------:|:--------:|:--------:|
| 1 | 인지 연속성 | 20% | 0.75 | 0.98 | 0.150 | 0.196 |
| 2 | 협업 거버넌스 | 25% | 0.67 | 0.97 | 0.168 | 0.243 |
| 3 | 시스템 무결성 | 30% | 0.71 | 0.98 | 0.213 | 0.294 |
| 4 | 환경 이식성 | 15% | 0.89 | 0.97 | 0.134 | 0.146 |
| 5 | 운영 & 제어 | 10% | 0.35 | 0.95 | 0.035 | 0.095 |
| **Root** | | **100%** | **0.700** | **0.974** | **0.700** | **0.974** |

> **가중치 근거**: Cat 3 실패 = 실행 차단(생존 조건) → 30%. Cat 5 미달 = 비효율(비중단) → 10%.

### 2-3. T0 항목 해소 효과 (Root Score 변화)

| 해소 항목 | 현재→목표 | 가중 기여 |
|:---------|:--------:|:--------:|
| 3-8 Post-Mortem (T0→T4) | +1.00 × 0.30/8 | **+0.038** |
| 2-6 Decision Attribution (T0→T4) | +1.00 × 0.25/6 | +0.042 |
| 5-5 Active Control (T0→T4) | +1.00 × 0.10/6 | +0.017 |
| 5-6 Economic Gov. (T0→T4) | +1.00 × 0.10/6 | +0.017 |
| 5-1 Param Registry (T1→T3) | +0.67 × 0.10/6 | +0.011 |
| 3-3 Change Mgmt (T2→T3) | +0.33 × 0.30/8 | +0.012 |
| 3-7 Behavioral (T2→T3) | +0.33 × 0.30/8 | +0.012 |
| **P0+P1 합계** | | **≈ +0.149 → Root ~85%** |

---

## §3. Full MECE Tree (4-Level)

```
AI-Assisted App Development  [Root: 70.0%→97.4%]
│
├── Cat 1: 인지 연속성 (Cognitive Continuity)
│   [Score: 0.75 | Weight: 20% | Contrib: 0.150 → 0.196]
│   │
│   ├── 1-1: Context Lifecycle Management  [C | T4 | T2 | 0.50]
│   │   ├── 1-1-1: Size tracking — GREEN(<600KB)/YELLOW(600–1200KB)/RED(>1200KB)
│   │   ├── 1-1-2: handoff.md rolling — [DONE] 항목 아카이브, 상시 <2KB
│   │   └── 1-1-3: Context Pruning [범위: 세션 내 임시 상태]
│   │       TTL: resolved 항목 → ttl_resolved_days일 후 아카이브
│   │       score = (priority_level × 2) - age_in_days (priority 1~3)
│   │       score < 0 → 삭제 후보
│   │       [PARTIAL — ttl 파라미터 compactor 연동 필요]
│   │
│   ├── 1-2: Session Continuity  [B | T2 | T2 | 1.00]
│   │   ├── 1-2-1: Room-based session — .ai/sessions/room-{uuid}/
│   │   ├── 1-2-2: Summary artifacts — summary_{agent}.md, <4KB per node
│   │   ├── 1-2-3: Re-orientation — §P-11 handoff.md 선독 후 작업 시작
│   │   └── 1-2-4: Emergency handoff schema
│   │       executive_summary / technical_state / strategy_for_next_session
│   │
│   ├── 1-3: Memory Persistence [범위: 세션 간 장기 지속]  [C | T4 | T2 | 0.50]
│   │   ├── 1-3-1: CC Memory — _sys/claude/config/projects/{id}/memory/
│   │   ├── 1-3-2: Memory compactor — memory_compactor.py, compactor_interval_days
│   │   ├── 1-3-3: Zero-Token Symmetric Memory — §P-11, CLAUDE.md↔GEMINI.md
│   │   └── 1-3-4: Memory type taxonomy — user / feedback / project / reference
│   │
│   └── 1-4: Instruction Design  [B | T2 | T2 | 1.00]
│       ├── 1-4-1: Global config — CLAUDE.md (CC) / GEMINI.md (GC)
│       ├── 1-4-2: Project-level override — {project_root}/CLAUDE.md
│       ├── 1-4-3: Token-efficient query — English, TASK/CONTEXT/QUESTION
│       └── 1-4-4: Axis task templates — A~J 구조화 위임 분석
│
├── Cat 2: 협업 거버넌스 (Collaboration Governance)
│   [Score: 0.67 | Weight: 25% | Contrib: 0.168 → 0.243]
│   │
│   ├── 2-1: Consensus Protocol  [C | T3 | T3 | 1.00]
│   │   ├── 2-1-1: Propose→Vote→FINALIZED — §P-3, 라운드 수 무제한
│   │   ├── 2-1-2: Quorum — §P-3-QR, 일반 N/2+1 / R:10 100%
│   │   ├── 2-1-3: Final Call — §P-3-FC, collab_rate ≥ final_call_min_rate
│   │   └── 2-1-4: Consensus history — handoff.md CONSENSUS_HISTORY
│   │
│   ├── 2-2: Division of Labor  [C | T3 | T2 | 0.67]
│   │   ├── 2-2-1: DIRECTIVE envelope — §P-2 표준 JSON
│   │   ├── 2-2-2: Node routing — §P-4, 특성 기반 태스크 배정
│   │   ├── 2-2-3: Parallel/sequential — §P-7, 영향범위 비중복 시 비동기
│   │   └── 2-2-4: Result aggregation + VERIFY — 상호 교차검증
│   │
│   ├── 2-3: Conflict Resolution  [B | T2 | T2 | 1.00]
│   │   ├── 2-3-1: Deadlock — 연속 2라운드+ disagreement 처리
│   │   ├── 2-3-2: ESCALATE → Human Gate — §P-0 Tier-0 veto
│   │   ├── 2-3-3: 3-Strike halt — §M-3, 동일 오류 3회 → HALT
│   │   └── 2-3-4: Stalled round sweep — 30분 타임아웃 자동 정리
│   │
│   ├── 2-4: Node Management  [C | T3 | T3 | 1.00]
│   │   ├── 2-4-1: Node registration — .ai/nodes.json, §P-1
│   │   ├── 2-4-2: COLLAB_RATE — §C-0, 5앵커 (R:0/3/5/8/10)
│   │   ├── 2-4-3: N-node expansion — §P-9, 등록 즉시 투표권
│   │   └── 2-4-4: Resilience + Re-sync
│   │       diff 도구: git diff --stat .ai/state.json
│   │       복귀 노드: diff 요약 후 VOTE 재참여
│   │       [PARTIAL — diff 자동화 + Re-sync 로직 필요]
│   │
│   ├── 2-5: Transparency & Communication  [C | T3 | T1 | 0.33]
│   │   ├── 2-5-1: No private channels — §M-2, 전 노드 공개 의무
│   │   ├── 2-5-2: HUB prefix — §P-5 (HUB / HUB:ERROR / HUB:WARN / HUB:GATE)
│   │   └── 2-5-3: Gemini response format — "━━ Gemini ━━ / ━━ Claude Judgment ━━"
│   │
│   └── 2-6: Decision Attribution  [C | T4 | T0 | 0.00]
│       ├── 2-6-1: Proposer/opposer logging
│       │   [PARTIAL — handoff.md CONSENSUS_HISTORY에 Proposer 필드 추가 필요 (R:10)]
│       ├── 2-6-2: Pattern drift detection (G17)
│       │   disagree 비율 > voting_drift_threshold_pct% → WARN + ESCALATE
│       └── 2-6-3: Decision weight tracking
│           collab_rate ≥ final_call_min_rate 인 FINALIZED = 주요 결정
│           기록: Proposer, Rationale(1문장), Trade-off(T번호)
│           [T0 — hub.py 2-6 미구현]
│
├── Cat 3: 시스템 무결성 (System Integrity)
│   [Score: 0.71 | Weight: 30% | Contrib: 0.213 → 0.294]  ← Axis-J [Static]
│   │
│   ├── 3-1: Security & Trust  [B | T2 | T3→1.00]
│   │   ├── 3-1-1: Mutual Non-Interference — §M-1, constitutional doc 보호
│   │   ├── 3-1-2: Auth file isolation — 인증 파일 AI 접근 불가
│   │   ├── 3-1-3: Input validation — command injection / XSS 방지
│   │   ├── 3-1-4: R:10 write protection — hub.py / PROTOCOL.md / CLAUDE.md
│   │   └── 3-1-5: Secret Injection Protocol
│   │       API 키 = 환경변수만 허용; .env 커밋 금지; 로그 필터링
│   │
│   ├── 3-2: Policy Enforcement [정적(Static)]  [C | T3 | T3 | 1.00]
│   │   ├── 3-2-1: Policy Regression Gate — check_policy.py 10개 (Axis-J)
│   │   ├── 3-2-2: Policy-code consistency — PROTOCOL.md vs hub.py
│   │   ├── 3-2-3: Pre-commit — check-policy.bat hook
│   │   └── 3-2-4: Exit gate — PASS(0) / FAIL(1)
│   │
│   ├── 3-3: Change Management  [C | T3 | T2 | 0.67]
│   │   ├── 3-3-1: MECE tagging — [추가/삭제/변경/유지] 필수
│   │   ├── 3-3-2: Conventional commits — English, feat/fix/docs/refactor
│   │   ├── 3-3-3: Branch-before-large-change
│   │   └── 3-3-4: Impact Analysis (G6) — Axis-F 필수 게이트
│   │
│   ├── 3-4: Output Validation  [C | T3 | T2 | 0.67]
│   │   ├── 3-4-1: AI output schema (G2) — 구조화 출력 검증
│   │   ├── 3-4-2: Include size guard — §3-4-A
│   │   ├── 3-4-3: Hub script protection — §3-4-B
│   │   ├── 3-4-4: Refusal detection — §3-4-C
│   │   └── 3-4-5: Confidence threshold
│   │       §P-2 envelope에 confidence_score: int(0~100) 포함
│   │       판단: 파일 전체 읽음=100 / 부분 추론=50 / 추측=0~49
│   │       score < confidence_threshold → Human Gate
│   │       [BLOCKED — §P-2 스키마 변경 + hub.py 검증 로직 (R:10 합의)]
│   │
│   ├── 3-5: Error Classification  [B | T2 | T2 | 1.00]
│   │   ├── 3-5-1: Severity — P0(blocking) / P1(critical) / WARN / INFO
│   │   ├── 3-5-2: Structured error reporting — 표준 보고 형식
│   │   └── 3-5-3: 3-Strike trigger — §M-3, P0 3회 → HALT
│   │
│   ├── 3-6: Rollback & Recovery  [C | T3 | T2 | 0.67]
│   │   ├── 3-6-1: Git-based rollback — ctx-save 체크포인트
│   │   ├── 3-6-2: max_rollback_depth — 복구 가능 체크포인트 수 제한
│   │   └── 3-6-3: State Migration (G13)
│   │       .ai/nodes.json + room state.json 에 version 필드 필수
│   │       [PARTIAL — version 필드 + migration_check.py 필요]
│   │
│   ├── 3-7: Behavioral Compliance Tests [런타임(Runtime)]  [C | T3 | T2 | 0.67]
│   │   ├── 3-7-1: Runtime scenarios — 실제 실행 중 R:10 로그 파싱
│   │   ├── 3-7-2: Test scenarios — T-FINALIZED / T-COLLAB_RATE / T-R10
│   │   ├── 3-7-3: Param validation (G10) — config.json 로드 시 검증
│   │   └── 3-7-4: Axis token budget (§3-4-D)
│   │       단순(A/B/C) ≤ 4,000 tok / 심층(D/E/F) ≤ 8,000 tok / 리뷰(G/H/I/J) ≤ 16,000 tok
│   │
│   └── 3-8: Post-Mortem & Learning Loop  [C | T4 | T0 | 0.00]
│       ├── 3-8-1: Failure → Kaizen (G16)
│       │   hub.py try/except → P0/P1 감지 → pm-draft.md 자동 생성
│       │   5-Why 결과 → PROTOCOL.md 개정 제안 Draft
│       │   [BLOCKED — hub.py 예외 훅 + .ai/postmortems/ 필요]
│       ├── 3-8-2: PM template
│       │   Incident / Root Cause (5-Why) / Timeline / Category / Prevention / Policy
│       │   저장: .ai/postmortems/pm-{YYYYMMDD}-{id}.md
│       └── 3-8-3: Learning gate
│           반복 오류 3회+ → Kaizen 완료 전 동일 작업 잠금
│
├── Cat 4: 환경 이식성 (Environment Portability)
│   [Score: 0.89 | Weight: 15% | Contrib: 0.134 → 0.146]
│   │
│   ├── 4-1: Runtime Environment  [C | T3 | T3 | 1.00]
│   │   ├── 4-1-1: Python venv — _sys/env/venv/, 외부 의존성 격리
│   │   ├── 4-1-2: PYTHONUTF8=1 — 모든 bat 파일 필수
│   │   ├── 4-1-3: Node.js/npm-global isolation — portable npm prefix
│   │   ├── 4-1-4: Env var scope — §3-1~3-3 노드별 격리
│   │   └── 4-1-5: Zero-Config Hardening
│   │       PS 실행정책 ≥ RemoteSigned; $PROFILE P:\ 참조 0건
│   │       Cross-session env var 유출 방지
│   │       [PARTIAL — PS 스크립트 존재, install.bat 연동 필요]
│   │
│   ├── 4-2: Installation & Deployment  [C | T3 | T2 | 0.67]
│   │   ├── 4-2-1: ZeroBase — install.bat 단일 실행 전체 재구성
│   │   │   v5.1 부트스트랩 추가: .ai/postmortems/ 생성,
│   │   │   .ai/state.json 초기화, hub.py v5.1 pre-flight 등록
│   │   ├── 4-2-2: Dependency bootstrapping — install.bat
│   │   ├── 4-2-3: WSB smoke testing — §9
│   │   └── 4-2-4: Parallel safety — cq-{ts}-{rand4}.txt
│   │
│   ├── 4-3: Infrastructure Abstraction  [C | T3 | T2 | 0.67]
│   │   ├── 4-3-1: Hub-based IPC — hub.py 기술 중립 메시지 패싱
│   │   ├── 4-3-2: .ai/ shared state — 노드 독립적 공유 상태
│   │   ├── 4-3-3: msg.bat — P2P 메시지 단일 진입점
│   │   └── 4-3-4: Node heartbeat — §P-3-QR auto-abstain 기반
│   │
│   ├── 4-4: Version Management  [B | T2 | T3→1.00]
│   │   ├── 4-4-1: Protocol versioning — PROTOCOL.md §HISTORY
│   │   ├── 4-4-2: CHANGELOG maintenance
│   │   └── 4-4-3: **vX.Y** 버전 태그 형식 강제
│   │
│   ├── 4-5: Platform Independence [범위: 코드 수준]  [C | T3 | T3 | 1.00]
│   │   ├── 4-5-1: No hardcoded paths — check_policy.py 검증
│   │   ├── 4-5-2: USB/cloud portability — P:\ 추상화
│   │   └── 4-5-3: pathlib.Path 강제
│   │
│   └── 4-6: Node Onboarding  [B | T2 | T2 | 1.00]
│       ├── 4-6-1: Registration checklist — nodes.json + room state
│       ├── 4-6-2: Required loading files — §P-8 토큰 예산
│       └── 4-6-3: Resilience mechanics (G15) — heartbeat, fallback
│
└── Cat 5: 운영 & 제어 (Operations & Control)
    [Score: 0.35 | Weight: 10% | Contrib: 0.035 → 0.095]
    │
    ├── 5-1: Shared Parameter Registry  [C | T3 | T1 | 0.33]
    │   ├── 5-1-1: Flat+metadata config.json — _param_sections 메타데이터
    │   ├── 5-1-2~6: 18개 파라미터 (§6 참조)
    │   └── 검증: 20개 키 존재 확인 (_param_sections + 18 params + last_review_ts)
    │
    ├── 5-2: Behavioral Compliance & Validation  [C | T3 | T2 | 0.67]
    │   ├── 5-2-1: Config schema (G10) — 로드 시 자동 검증 (20키)
    │   ├── 5-2-2: Parameter range enforcement
    │   └── 5-2-3: _param_sections integrity check
    │
    ├── 5-3: Observability  [C | T4 | T3 | 0.75]  ← Axis-H
    │   ├── 5-3-1: Context Health — check_health.py (GREEN/YELLOW/RED)
    │   ├── 5-3-2: Async Events (G11) — out-of-band 이벤트 처리 [🔶 정책 필요]
    │   └── 5-3-3: Collab metrics — collab_rate 현황, 합의 성공률
    │
    ├── 5-4: System Health & Dashboard  [C | T3 | T1 | 0.33]
    │   ├── 5-4-1: Session header — ROOM:{id}|RATE:R{n}|HEALTH:{kb}KB({color})
    │   ├── 5-4-2: Metrics aggregation — 정책 준수율%, 합의 성공률%
    │   ├── 5-4-3: Persistent metrics — metrics_flush_interval_sec
    │   └── 5-4-4: Dashboard spec (G7) [🔶 DASHBOARD_SPEC.md 필요]
    │
    ├── 5-5: Active Control Loop [Cross-category Execution Orchestrator]
    │   [C | T4 | T0 | 0.00]
    │   구현: hub.py 모든 액션 진입 시 동기 _sla_preflight_check() 실행
    │   [BLOCKED — hub.py pre-flight + lock 메커니즘 구현 필요]
    │   ├── 5-5-1: Lock-safety — 능동 제어 전 활성 쓰기 노드 확인
    │   ├── 5-5-2: RED trigger — 자동 ctx-save + collab_rate 임시 하향(현재값-2, min 3)
    │   ├── 5-5-3: Token budget control
    │   │   소비 > token_budget_daily × token_budget_warn_pct/100 → 경보
    │   │   소비 ≥ 100% → collab_rate=3 강제
    │   ├── 5-5-4: SLA escalation — timeout 2회 연속 → auto ESCALATE
    │   └── 5-5-5: Safety guard — active_control_enabled=0 (default) 전 항목 비활성
    │
    └── 5-6: Economic & Quota Governance  [C | T4 | T0 | 0.00]
        구현: msg.bat 후처리 len(content)//4 → .ai/state.json 누적
        [BLOCKED — token_tracker 또는 msg.bat 훅 필요]
        ├── 5-6-1: Token ROI — FINALIZED_DIRECTIVEs + merged_PRs / 일일 토큰
        ├── 5-6-2: Budget management — token_budget_warn_pct% 경보; 100% Axis 차단
        ├── 5-6-3: Token forecasting (G14) — forecast_warn_threshold_pct 기반 runway
        └── 5-6-4: Cost rules
            동일 search_pattern + 동일 directory 기준
            axis_delegation_threshold회 이상 Grep → Axis-G 위임
```

**Tree 범례**: `[유형 | 목표Tier | 현재Tier | Score]` — B=Binary, C=Continuous

---

## §4. Measurement Matrix

모든 서브카테고리의 측정 지표, 방법, 100% 기준을 한 곳에서 조회.

### Cat 1: 인지 연속성

| ID | 이름 | 유형 | 목표 | 현재 | Score | 측정 명령 (PS native) | 100% 기준 |
|:---|:-----|:----:|:----:|:----:|:-----:|:---------------------|:---------|
| **1-1** | Context Lifecycle | C | T4 | T2 | 0.50 | `cmd /c ".\_sys\checks\check-health.bat"` | GREEN 95%+; RED 진입 0건/48h |
| **1-2** | Session Continuity | B | T2 | T2 | 1.00 | `(Get-Item ".ai\sessions\room-*\handoff.md").Length / 1KB` | ≤2KB; 6개 섹션 헤더 존재 |
| **1-3** | Memory Persistence | C | T4 | T2 | 0.50 | `python ".\_sys\hooks\memory_compactor.py" 2>&1` 출력 stale 수 | stale 0건; compactor 최근 실행일 ≤ compactor_interval_days |
| **1-4** | Instruction Design | B | T2 | T2 | 1.00 | `Test-Path ".\_sys\claude\config\CLAUDE.md"` AND `Test-Path ".\CLAUDE.md"` | 두 파일 존재 + `R:10` 문자열 포함 |
| **Cat 1** | | | | | **0.75** | | |

### Cat 2: 협업 거버넌스

| ID | 이름 | 유형 | 목표 | 현재 | Score | 측정 명령 (PS native) | 100% 기준 |
|:---|:-----|:----:|:----:|:----:|:-----:|:---------------------|:---------|
| **2-1** | Consensus Protocol | C | T3 | T3 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "hub-consensus-actions"` | "PASS" 포함 |
| **2-2** | Division of Labor | C | T3 | T2 | 0.67 | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "from.*(cc\|gc\|ca)"` | ≥2 노드 각 ≥1건 DIRECTIVE 발송 기록 |
| **2-3** | Conflict Resolution | B | T2 | T2 | 1.00 | `Select-String -Path ".\_sys\core\hub.py" -Pattern "ESCALATE"` | hub.py ESCALATE 코드 존재 |
| **2-4** | Node Management | C | T3 | T3 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "collab-rate-symmetry"` | "PASS" 포함 |
| **2-5** | Transparency | C | T3 | T1 | 0.33 | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "private\|offchannel"` | 0건; §M-2 PROTOCOL.md 존재 |
| **2-6** | Decision Attribution | C | T4 | T0 | 0.00 | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "Proposer:"` | 100% FINALIZED에 Proposer 필드; drift 감지 실행 중 |
| **Cat 2** | | | | | **0.67** | | |

### Cat 3: 시스템 무결성

| ID | 이름 | 유형 | 목표 | 현재 | Score | 측정 명령 (PS native) | 100% 기준 |
|:---|:-----|:----:|:----:|:----:|:-----:|:---------------------|:---------|
| **3-1** | Security & Trust | B | T2 | T3→1.00 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "r10-files-exist"` | "PASS"; Secret 3-1-5 존재 |
| **3-2** | Policy Enforcement (Static) | C | T3 | T3 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat"; $LASTEXITCODE` | exit 0; 0 FAIL |
| **3-3** | Change Management | C | T3 | T2 | 0.67 | `@(git log --oneline -20 \| Select-String -Pattern "^[0-9a-f]+ (feat\|fix\|docs\|refactor\|test\|chore):").Count / 20 * 100` | ≥95% 준수 |
| **3-4** | Output Validation | C | T3 | T2 | 0.67 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "size-guard"` | 0 위반; confidence 미달 0건 |
| **3-5** | Error Classification | B | T2 | T2 | 1.00 | `Select-String -Path ".\PROTOCOL.md" -Pattern "§M-3"` | §M-3 + P0/P1 기준 문서화 |
| **3-6** | Rollback & Recovery | C | T3 | T2 | 0.67 | `@(git log --grep="ctx-save" --oneline).Count` | ≥ max_rollback_depth 건 존재 |
| **3-7** | Behavioral Tests (Runtime) | C | T3 | T2 | 0.67 | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "FINALIZED"` vs 전체 DIRECTIVE | ≥95% DIRECTIVE → FINALIZED 추적; 비인가 수정 0건 |
| **3-8** | Post-Mortem Loop | C | T4 | T0 | 0.00 | `@(Get-ChildItem ".ai\postmortems\*.md" -ErrorAction SilentlyContinue).Count` | PM 생성율 100% (vs ESCALATE+3-Strike 횟수); Orphan 0건/48h |
| **Cat 3** | | | | | **0.71** | | |

### Cat 4: 환경 이식성

| ID | 이름 | 유형 | 목표 | 현재 | Score | 측정 명령 (PS native) | 100% 기준 |
|:---|:-----|:----:|:----:|:----:|:-----:|:---------------------|:---------|
| **4-1** | Runtime Environment | C | T3 | T3 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "pythonutf8"` AND `Test-Path ".\_sys\env\venv"` | "PASS"; venv 존재 |
| **4-2** | Installation | C | T3 | T2 | 0.67 | `Test-Path ".\_sys\install.bat"` AND 수동 실행 결과 | 파일 존재; 0 오류 |
| **4-3** | Infra Abstraction | C | T3 | T2 | 0.67 | `cmd /c ".\_sys\cli\msg.bat" hub status; $LASTEXITCODE` | exit 0; nodes.json 유효 JSON |
| **4-4** | Version Management | B | T2 | T3→1.00 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "protocol-version"` | "PASS" |
| **4-5** | Platform Independence | C | T3 | T3 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "no-hardcoded-paths"` | "PASS" |
| **4-6** | Node Onboarding | B | T2 | T2 | 1.00 | `Test-Path ".ai\nodes.json"` AND `Select-String -Path ".\PROTOCOL.md" -Pattern "§P-8"` | nodes.json 유효; §P-8 존재 |
| **Cat 4** | | | | | **0.89** | | |

### Cat 5: 운영 & 제어

| ID | 이름 | 유형 | 목표 | 현재 | Score | 측정 명령 (PS native) | 100% 기준 |
|:---|:-----|:----:|:----:|:----:|:-----:|:---------------------|:---------|
| **5-1** | Param Registry | C | T3 | T1 | 0.33 | `python -c "import json; d=json.load(open('./_sys/gemini/config.json')); assert len(d)==20"` | 20개 키 존재; _param_sections 정합성 PASS |
| **5-2** | Behavioral Validation | C | T3 | T2 | 0.67 | `cmd /c ".\_sys\checks\check-policy.bat"` (collab-rate-symmetry 포함) | 0 범위 초과; _param_sections 정합 |
| **5-3** | Observability | C | T4 | T3 | 0.75 | `cmd /c ".\_sys\checks\check-health.bat"; $LASTEXITCODE` | exit 0; GREEN/YELLOW/RED 판정 + 로그 생성 |
| **5-4** | Dashboard | C | T3 | T1 | 0.33 | `cmd /c ".\_sys\cli\msg.bat" hub status 2>&1 \| Select-String "ROOM:"` | "ROOM:{id}\|RATE:\|HEALTH:" 형식 포함 |
| **5-5** | Active Control Loop | C | T4 | T0 | 0.00 | `python -c "import json; print(json.load(open('./_sys/gemini/config.json'))['active_control_enabled'])"` | active=1 조건 하: 100% RED → 복구; 0 미처리 |
| **5-6** | Economic Governance | C | T4 | T0 | 0.00 | `@(Get-Content ".ai\sessions\*\handoff.md" \| Select-String "msg.bat").Count * 2000` → token_budget_daily 대비 | ≤100% 예산; 예산 소진 전 경보 0-miss |
| **Cat 5** | | | | | **0.35** | | |

---

## §5. Trade-off Table (T1–T16)

| # | 항목 A | 항목 B | 제어 파라미터 | 관리 | 비고 |
|:--|:-------|:-------|:------------|:-----|:-----|
| T1 | 제로토큰 효율 | 협업 깊이 | `collab_rate` | 명시적 | R:0=완전자율, R:10=완전합의 |
| T2 | 컨텍스트 보존 | 처리 속도 | `context_health_green_kb` | 명시적 | 낮을수록 민감 |
| T3 | 합의 정확성 | 응답 속도 | `consensus_timeout_min` | 명시적 | Balance: MTC vs Rejection Rate |
| T4 | 자율성 | 안전성 | `collab_rate` + §C-0 앵커 | 명시적 | 5앵커 (R:0/3/5/8/10) |
| T5 | 문서 상세성 | 토큰 소모 | English mandate | 정책 | 영어 2–3x 효율 |
| T6 | 세션·메모리 연속성 | 컨텍스트 신선도 | `compactor_interval_days` + `ttl_resolved_days` | 명시적 | handoff TTL + 장기 compactor 통합 |
| T7 | 이식성 | 플랫폼 최적화 | — | 정책 | pathlib / 절대경로 금지 |
| T8 | 정책 엄격성 | 개발 속도 | `final_call_min_rate` | 명시적 | 높을수록 안전 |
| T10 | 보안 격리 | 협업 편의성 | — | 정책 | §M-1 Non-Interference |
| T11 | 노드 확장성 | 합의 복잡도 | — | 정책 | 노드 추가 시 투표 복잡도 ↑ |
| T12 | Pruning 공격성 | 메모리 보존 | `ttl_resolved_days` | 명시적 | |
| T13 | 메트릭 세분성 | 디스크 I/O | `metrics_flush_interval_sec` | 명시적 | |
| T14 | 예측 민감도 | 알림 피로도 | `forecast_warn_threshold_pct` | 명시적 | |
| T15 | 학습 오버헤드 | 시스템 진화 속도 | — | 정책 | Post-mortem 시간 비용 |
| T16 | 능동 자동화 | 인간 통제권 | `active_control_enabled` | 명시적 | 0=안전, 1=효율 |
| T17 | 토큰 경제성 | 협업 깊이 | `token_budget_daily` + `collab_rate` | 명시적 | Balance: Budget vs Rounds per Decision |

> **T9 삭제**: T6에 통합 (동일 파라미터·구조).

### Trade-off Balance Metrics (T3/T17)

**T3: 합의 정확성 vs 속도**

| 지표 | 측정 | 균형 기준 |
|:-----|:-----|:---------|
| MTC (Mean Time to Consensus, 분) | handoff.md propose→FINALIZED 시간 차 평균 | MTC ≤ consensus_timeout_min × 0.5 |
| Rejection Rate (%) | ESCALATE 수 / 전체 라운드 수 | ≤ 10% |
| 균형 신호 | MTC 상승 → 정확성 ↑; Rate 상승 → collab_rate 재검토 | |

**T17: 토큰 경제성 vs 협업 깊이**

| 지표 | 측정 | 균형 기준 |
|:-----|:-----|:---------|
| Budget Utilization (%) | 일일 토큰 / token_budget_daily × 100 | < 90% (token_budget_warn_pct) |
| Rounds per Decision | avg(rounds per FINALIZED) | ≤ 3 |
| 균형 신호 | Budget 높고 Rounds 낮으면 낭비; Rounds 높으면 collab_rate ↓ 고려 | |

---

## §6. Parameter Registry (18개, config.json v3.0)

```json
{
  "_param_sections": {
    "general": ["collab_rate","consensus_timeout_min","final_call_min_rate",
                "token_budget_daily","axis_delegation_threshold"],
    "cat1":    ["context_health_green_kb","context_health_yellow_kb",
                "compactor_interval_days","review_interval_min",
                "ttl_resolved_days","ttl_active_days"],
    "cat2":    ["voting_drift_threshold_pct"],
    "cat3":    ["max_rollback_depth","confidence_threshold"],
    "cat5":    ["metrics_flush_interval_sec","active_control_enabled",
                "forecast_warn_threshold_pct","token_budget_warn_pct"]
  },
  "collab_rate": 10,
  "consensus_timeout_min": 30,
  "final_call_min_rate": 8,
  "token_budget_daily": 50000,
  "axis_delegation_threshold": 5,
  "context_health_green_kb": 600,
  "context_health_yellow_kb": 1200,
  "compactor_interval_days": 7,
  "review_interval_min": 5,
  "ttl_resolved_days": 3,
  "ttl_active_days": 14,
  "voting_drift_threshold_pct": 60,
  "max_rollback_depth": 3,
  "confidence_threshold": 70,
  "metrics_flush_interval_sec": 300,
  "active_control_enabled": 0,
  "forecast_warn_threshold_pct": 70,
  "token_budget_warn_pct": 90,
  "last_review_ts": null
}
```

> 총 키: **20개** (`_param_sections` + 18 파라미터 + `last_review_ts`)
> 검증: `python -c "import json; d=json.load(open('./_sys/gemini/config.json')); assert len(d)==20"`

### Parameter 정의 (18개 전체)

| 파라미터 | 타입 | 범위 | 기본값 | 의미 | Section | Trade-off |
|:---------|:----:|:----:|:------:|:-----|:-------:|:---------:|
| `collab_rate` | int | 0–10 | 10 | 협업 깊이. 0=완전자율, 10=만장일치 | general | T1,T4,T17 |
| `consensus_timeout_min` | int | 1–60 | 30 | 합의 라운드 자동 타임아웃(분) | general | T3 |
| `final_call_min_rate` | int | 0–10 | 8 | §P-3-FC Final Call 임계 rate | general | T8 |
| `token_budget_daily` | int | 1k–500k | 50000 | 일일 전체 토큰 소비 상한 | general | T17 |
| `axis_delegation_threshold` | int | 1–20 | 5 | 동일 범위 Grep N회+ → Axis-G 위임 | general | — |
| `context_health_green_kb` | int | 100–1000 | 600 | GREEN 상태 임계(KB) | cat1 | T2 |
| `context_health_yellow_kb` | int | 200–2000 | 1200 | YELLOW→RED 전환 임계(KB) | cat1 | T2 |
| `compactor_interval_days` | int | 1–30 | 7 | 메모리 compactor 주기(일) | cat1 | T6,T12 |
| `review_interval_min` | int | 1–60 | 5 | Gemini 검토 최소 간격(분) | cat1 | T1 |
| `ttl_resolved_days` | int | 1–30 | 3 | handoff.md [DONE] TTL(일) | cat1 | T6,T12 |
| `ttl_active_days` | int | 1–90 | 14 | handoff.md 미완료 항목 TTL(일) | cat1 | T6 |
| `voting_drift_threshold_pct` | int | 1–99 | 60 | 노드 disagree 비율(%) WARN 임계 | cat2 | — |
| `max_rollback_depth` | int | 1–10 | 3 | git 롤백 체크포인트 수 상한 | cat3 | — |
| `confidence_threshold` | int | 0–100 | 70 | AI 신뢰도 미달 시 Human Gate(%) | cat3 | — |
| `metrics_flush_interval_sec` | int | 10–3600 | 300 | 운영 메트릭 디스크 기록 주기(초) | cat5 | T13 |
| `active_control_enabled` | int | 0–1 | 0 | 능동 제어 루프 활성화(0=off) | cat5 | T16 |
| `forecast_warn_threshold_pct` | int | 1–99 | 70 | 컨텍스트 사용률(%) 경보 임계 | cat5 | T14 |
| `token_budget_warn_pct` | int | 1–99 | 90 | 일일 예산 소진 경보 임계(%) | cat5 | T17 |

---

## §7. Root Health Formula

### 항목 점수

```
Item Score = min(Current Tier / Target Tier, 1.0)

예:  1-1 (C, T4 목표, T2 현재):  2/4 = 0.50
     3-1 (B, T2 목표, T3 현재):  min(3/2, 1.0) = 1.00  ← 상한 고정
     2-6 (C, T4 목표, T0 현재):  0/4 = 0.00
```

### 카테고리 점수

```
Category Score = mean(Item Scores in category)
```

### Root Health Score (가중)

```
Root = 0.20 × Cat1 + 0.25 × Cat2 + 0.30 × Cat3 + 0.15 × Cat4 + 0.10 × Cat5

현재: 0.20×0.75 + 0.25×0.67 + 0.30×0.71 + 0.15×0.89 + 0.10×0.35 = 0.700 (70.0%)
목표: 0.20×0.98 + 0.25×0.97 + 0.30×0.98 + 0.15×0.97 + 0.10×0.95 = 0.974 (97.4%)
```

### "100% 완료" 판정 기준 (6조건 동시 충족)

| # | 조건 | 검증 명령 |
|:--|:-----|:---------|
| ① | check-policy.bat exit 0 | `cmd /c ".\_sys\checks\check-policy.bat"; $LASTEXITCODE -eq 0` |
| ② | check-health.bat GREEN | `cmd /c ".\_sys\checks\check-health.bat" 2>&1 \| Select-String "GREEN"` |
| ③ | Root Score ≥ 0.95 | §7 공식 계산 |
| ④ | Level A KPI 5개 목표 달성 | §4 Measurement Matrix 참조 |
| ⑤ | G1–G17 모두 ✅ (G11 🔶 허용) | §9 Gap Log |
| ⑥ | Orphan Post-Mortem 0건 | `@(Get-ChildItem ".ai\postmortems\*.md" \| Where-Object {(Get-Content $_) -match "status: open"}).Count -eq 0` |

---

## §8. Measurement Quick Reference

```powershell
# ── Policy Gate (Axis-J, Cat 3) ──────────────────────────────────
cmd /c ".\_sys\checks\check-policy.bat"

# ── Context Health (Axis-H, Cat 1/5) ─────────────────────────────
cmd /c ".\_sys\checks\check-health.bat"

# ── Hub 상태 (Cat 2/4/5) ─────────────────────────────────────────
cmd /c ".\_sys\cli\msg.bat" hub status

# ── handoff.md 크기 (Cat 1-2) ─────────────────────────────────────
(Get-Item ".ai\sessions\room-7fb9\handoff.md").Length / 1KB

# ── Commit 형식 준수율 (Cat 3-3) ──────────────────────────────────
@(git log --oneline -20 | Select-String -Pattern `
  "^[0-9a-f]+ (feat|fix|docs|refactor|test|chore):").Count / 20 * 100

# ── ctx-save 체크포인트 수 (Cat 3-6) ──────────────────────────────
@(git log --grep="ctx-save" --oneline).Count

# ── config.json 유효성 — 20키 확인 (Cat 5-1) ──────────────────────
python -c "import json; d=json.load(open('./_sys/gemini/config.json')); assert len(d)==20; print('OK 20 keys')"

# ── PS 실행정책 (Cat 4-1-5) ───────────────────────────────────────
Get-ExecutionPolicy    # → RemoteSigned 이상 필요

# ── Post-Mortem 현황 (Cat 3-8) ────────────────────────────────────
@(Get-ChildItem ".ai\postmortems\*.md" -ErrorAction SilentlyContinue).Count

# ── Memory 파일 수 (Cat 1-3) ──────────────────────────────────────
(Get-ChildItem ".\_sys\claude\config\projects\P--\memory\*.md").Count

# ── Root Score 계산 (미구현 P2) ───────────────────────────────────
# python .\_sys\checks\calc_completion.py
```

---

## §9. Gap Analysis Log

| # | 갭 | 위치 | 상태 |
|:--|:---|:-----|:-----|
| G1 | Instruction Design | 1-4 | ✅ v3.0 |
| G2 | Output Validation | 3-4 | ✅ v3.0 |
| G3 | Rollback Protocol | 3-6 | ✅ v3.0 |
| G4 | Error Classification | 3-5 | ✅ v3.0 |
| G5 | AI Behavioral Test Suite | 3-7 | ✅ v3.0 |
| G6 | Impact Analysis | 3-3-4 (Axis-F) | ✅ v4.0 |
| G7 | Dashboard | 5-4-4 | 🔶 DASHBOARD_SPEC.md 필요 |
| G8 | Metrics | 5-4-2 | ✅ v4.0 |
| G9 | Node Onboarding | 4-6 | ✅ v3.0 |
| G10 | Parameter Validation | 5-2 | ✅ v4.0 |
| G11 | Async Event Handling | 5-3-2 | 🔶 정책 문서화 필요 (비결정론적) |
| G12 | Resource & Quota Mgmt | 5-6 | 🔶 taxonomy-defined, 구현 pending |
| G13 | State Migration | 3-6-3 | 🔶 PARTIAL — version 필드 + migration_check.py |
| G14 | Token Budget Forecasting | 5-6-3 | 🔶 taxonomy-defined, 구현 pending |
| G15 | Node Resilience Protocol | 2-4-4, 4-6-3 | 🔶 Re-sync diff 자동화 필요 |
| G16 | Automated Kaizen Triggers | 3-8-1 | 🔶 hub.py 예외 훅 + postmortems/ 필요 |
| G17 | Node Voting Bias Alerting | 2-6-2 | 🔶 hub.py 분석 함수 필요 |

---

## §10. Implementation Queue

| 우선 | 작업 | 파일 | 비고 |
|:----:|:-----|:-----|:-----|
| **P0** | config.json — 18 params + `_param_sections` + `ratio`→`collab_rate` | `.\_sys\gemini\config.json` | 총 20키 |
| **P0** | gemini-set-ratio.bat — `ratio`→`collab_rate` | `.\_sys\gemini\gemini-set-ratio.bat` | P0 동시 |
| P1 | memory_compactor.py — MAX_AGE_DAYS → config.json 참조 | `.\_sys\hooks\memory_compactor.py:16` | |
| P1 | check_health.py — 임계값 → config.json 참조 | `.\_sys\checks\check_health.py` | |
| P1 | .ai/postmortems/ 디렉토리 생성 + install.bat 등록 | `install.bat` | G16 |
| P1 | hub.py P0/P1 try/except → pm-draft.md 자동 생성 | `.\_sys\core\hub.py` | G16 |
| P2 | §P-2 envelope에 confidence_score 필드 추가 | `PROTOCOL.md` | R:10 합의 필요 |
| P2 | CONSENSUS_HISTORY Proposer 필드 추가 | `PROTOCOL.md` / hub.py | R:10 합의 필요 |
| P2 | msg.bat 후처리: len(content)//4 → .ai/state.json | `.\_sys\cli\msg.bat` | G12, 5-6 |
| P2 | hub.py _sla_preflight_check() 동기 체크 | `.\_sys\core\hub.py` | 5-5 |
| P3 | .ai/nodes.json version 필드 + migration_check.py | `.ai\`, `.\_sys\checks\` | G13 |
| P3 | G15 Re-sync diff 자동화 | `.\_sys\core\hub.py` | |
| P3 | G7 Dashboard spec | `.\_sys\docs\DASHBOARD_SPEC.md` | |
| P3 | G11 Async 처리 정책 | `CONVENTION.md §11` | |
| P3 | G17 Voting Bias Detection | `.\_sys\core\hub.py` | R:10 합의 필요 |

---

## §11. Axis ↔ Category Mapping

| Axis | 이름 | Cat 주담당 | 부참조 | 설명 |
|:----:|:-----|:----------:|:------:|:-----|
| A | Architecture Review | Cat 1, 4 | Cat 3 | 설계 결정 검토 |
| B | Behavior Analysis | Cat 2 | Cat 3 | 노드 행동 패턴 분석 |
| C | Code Review | Cat 3 | Cat 2 | 코드 품질 및 정책 준수 |
| D | Dependency Scan | Cat 4 | Cat 3 | 의존성 보안 및 이식성 |
| E | Error Root Cause | Cat 3 | Cat 2 | 오류 근본 원인 분석 |
| F | Impact Analysis | Cat 3 | Cat 5 | 변경 파급 범위 (G6, 필수 게이트) |
| G | Gap Analysis | Cat 1–5 | — | MECE 완성도 갭 식별 |
| H | Health Check | Cat 5 | Cat 1 | 컨텍스트 건강도 (Reporter) |
| I | Integration Test | Cat 3, 4 | Cat 2 | 통합 테스트 |
| J | Policy Gate | Cat 3 (Static) | Cat 5 | 10개 정책 회귀 (Judge) |

---

## §12. Completion Trajectory

```
Doc:  v1.0 → v2.0 → v3.0 → v4.0 → v5.0 → v5.1 → v3.0(this)
Sys:   60%  →  72% →  80% → 86.4%→  97% →  97%  →   97%
Tier:   —   →   —  →   —  →  —   →   —  →  70%  →   70%
                                                 (Tier-based)
P0+P1 구현 시: ~85%  /  P0~P2: ~90%  /  전체 T0 해소: ~97%
```
