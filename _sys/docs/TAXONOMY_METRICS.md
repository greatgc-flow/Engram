# TAXONOMY_METRICS.md — Measurement & Completion Framework

> **Companion to**: `_sys/docs/TAXONOMY.md` v5.0
> **Authors**: Claude Code (CC) + Gemini CLI (GC) | R:10 Brain Sync | 2026-06-05
> **Purpose**: For each taxonomy item, define (1) measurable indicator (2) measurement method (3) "100% complete" judgment criterion.
> **Do NOT modify TAXONOMY.md** — use WinMerge to merge selectively.

---

## 0. Measurement Framework Overview

### 0-1. Hybrid DoD (Definition of Done)

두 가지 항목 유형에 서로 다른 DoD를 적용한다.

#### Type B — Binary/Structural Items (정책·문서·구조가 존재하느냐)
정책이 있거나 없거나, 문서가 있거나 없거나 — 연속 측정이 의미 없는 항목.

| Tier | 달성 기준 | 완성도 |
|:----:|:---------|:------:|
| **T0** | 미정의 | 0% |
| **T1** | 정책/문서 초안 작성 완료 (접근 가능) | 50% |
| **T2** | 정적 체크 또는 시스템 제약으로 강제 적용됨 | **100%** ← 목표 |

#### Type C — Continuous/Operational Items (지속적으로 측정·모니터링이 필요한 항목)

| Tier | 달성 기준 | 완성도 |
|:----:|:---------|:------:|
| **T0** | 미정의 | 0% |
| **T1** | 임계값/정의 문서화 완료 | 25% |
| **T2** | 구현 존재, 수동 체크 가능 | 50% |
| **T3** | 자동화 체크/스크립트 존재 (실행 시 검증) | 75% |
| **T4** | 능동 모니터링 실행 중 + 임계 위반 시 알림/행동 | **100%** ← 목표 |

### 0-2. 측정 실패 시 collab_rate 연동 행동

| collab_rate | Tier 3/4 지표 실패 시 행동 |
|:-----------:|:--------------------------|
| R:10 | **HALT + ESCALATE** — exit 1, Human Gate 호출 |
| R:5–8 | **WARN + 계속** — `.ai/metrics/health-{date}.log`에 기록 |
| R:0–3 | **LOG only** — 조용히 기록, 중단 없음 |

### 0-3. 토큰 측정 방식 (Token Proxy)

API 레벨 토큰 카운팅은 로컬 포터블 환경에서 불가. 대신:

| 프록시 지표 | 측정 방법 | 환산 기준 |
|:-----------|:---------|:---------|
| Context KB | `check_health.py` JSONL 크기 | 1 KB ≈ 250 tokens |
| Gemini 쿼리 수 | `msg.bat` 호출 횟수 / 일 | 1 query ≈ 2,000 tokens |
| 파일 쓰기 횟수 | Write/Edit 도구 호출 수 | 활동량 대리 지표 |

---

## 1. Level A — Category KPIs

전체 시스템 상태를 한 눈에 파악하는 카테고리 단위 핵심 지표.

| Cat | 카테고리 | KPI 이름 | 측정 명령 / 방법 | 100% 조건 | 자동화 | 현재 Tier |
|:---:|:---------|:---------|:----------------|:---------|:------:|:---------:|
| **1** | 인지 연속성 | **Context Adherence Rate** (세션 중 GREEN 체류 비율 %) | `check-health.bat` 실행; JSONL 크기 추적 | GREEN 95%+ 유지; `handoff.md` 항상 <2KB | ✅ 부분 | T2 |
| **2** | 협업 거버넌스 | **Consensus Success Rate** (FINALIZED / 전체 라운드 %) | `handoff.md` CONSENSUS_HISTORY 파싱 | 100% DIRECTIVE에 합의 이력; 교착 <5% | 🔶 부분 | T2 |
| **3** | 시스템 무결성 | **Zero-Regression Score** (정책 체크 PASS 연속 실행 수) | `check-policy.bat` 실행; exit code 확인 | 0개 policy regression; P0/P1 모두 PM 완료 | ✅ | T3 |
| **4** | 환경 이식성 | **Host Isolation Integrity** (외부 경로/변수 유출 건수) | `check-policy.bat` no-hardcoded-paths; WSB 테스트 | 0 절대경로; 0 host env 유출 | ✅ 부분 | T2 |
| **5** | 운영 & 제어 | **Token Budget Adherence** (일일 소비 / token_budget_daily %) | 쿼리 수 × 2000 / token_budget_daily | ≤100% 일일 예산; forecast 경보 정확도 100% | 🔶 미구현 | T1 |

---

## 2. Level B — Sub-category Metrics

모든 2-단계 항목(1-1, 2-3 등)에 대한 지표. 측정 방법은 현재 환경에서 실행 가능한 명령 기준.

### Cat 1: 인지 연속성

| 항목 | 유형 | 목표 Tier | 지표명 | 측정 방법 | 100% 기준 | 현재 Tier |
|:-----|:----:|:---------:|:-------|:---------|:---------|:---------:|
| **1-1** Context Lifecycle | C | T4 | Context KB 추이 | `check-health.bat` → GREEN/YELLOW/RED | GREEN 95%+, 한 번도 RED 미진입 (48h 기준) | T2 |
| **1-2** Session Continuity | B | T2 | handoff.md 구조 준수율 | `(Get-Item ".ai/sessions/room-*/handoff.md").Length / 1KB` | handoff.md ≤ 2KB; 6개 섹션 모두 존재 | T2 |
| **1-3** Memory Persistence | C | T4 | 메모리 파일 신선도 (마지막 압축 후 경과일) | `memory_compactor.py --dry-run` 실행 후 stale 파일 수 | stale 파일 0개; compactor 주기 내 자동 실행됨 | T2 |
| **1-4** Instruction Design | B | T2 | 글로벌/프로젝트 config 존재 여부 | `Test-Path "P:\_sys\claude\config\CLAUDE.md"` + `Test-Path "P:\CLAUDE.md"` | 두 파일 모두 존재 + R:10 구조 항목 포함 | T2 |

### Cat 2: 협업 거버넌스

| 항목 | 유형 | 목표 Tier | 지표명 | 측정 방법 | 100% 기준 | 현재 Tier |
|:-----|:----:|:---------:|:-------|:---------|:---------|:---------:|
| **2-1** Consensus Protocol | C | T3 | 합의 행동 구현 여부 | `check-policy.bat` → hub-consensus-actions 체크 | 4개 액션(propose/vote/check/sweep) 모두 PASS | T3 |
| **2-2** Division of Labor | B | T2 | DIRECTIVE 형식 준수 | `hub status` + `.ai/nodes.json` 존재 확인 | nodes.json 존재; DIRECTIVE 형식 문서화 완료 | T2 |
| **2-3** Conflict Resolution | B | T2 | 3-Strike 및 ESCALATE 코드 존재 | `grep -r "ESCALATE" P:\_sys\core\hub.py` | hub.py에 ESCALATE 처리 코드 존재 | T2 |
| **2-4** Node Management | C | T3 | 노드 등록 및 collab_rate 적용 | `check-policy.bat` → collab-rate-symmetry | CLAUDE.md / GEMINI.md / PROTOCOL.md 3파일 R:8 행 모두 PASS | T3 |
| **2-5** Transparency | B | T2 | Private channel 금지 정책 문서화 | `grep "§M-2" PROTOCOL.md` | §M-2 조항 존재 | T1→T2 (적용 강제 체크 없음) |
| **2-6** Decision Attribution | C | T4 | 합의 이력 Attribution Coverage (%) | `handoff.md` CONSENSUS_HISTORY 파싱 → Proposer 필드 존재율 | 100% FINALIZED 라운드에 제안자 기록; 패턴 drift 감지 실행 중 | **T0** (미구현) |

### Cat 3: 시스템 무결성

| 항목 | 유형 | 목표 Tier | 지표명 | 측정 방법 | 100% 기준 | 현재 Tier |
|:-----|:----:|:---------:|:-------|:---------|:---------|:---------:|
| **3-1** Security & Trust | B | T2 | Constitutional 파일 보호 여부 | `check-policy.bat` → r10-files-exist | 5개 파일 모두 존재 + PASS | T3 |
| **3-2** Policy Enforcement | C | T3 | Policy Gate PASS율 (%) | `check-policy.bat` exit code; 10개 체크 각 PASS/FAIL/WARN | exit 0 (0 FAIL, 경고 허용) | T3 |
| **3-3** Change Management | B | T2 | Commit 메시지 형식 준수율 | `git log --oneline -20 \| grep -cP "^[0-9a-f]+ (feat|fix|docs|refactor|test|chore):"` | 최근 20개 중 100% conventional commit 형식 | T2 |
| **3-4** Output Validation | C | T3 | Axis 체크 통과율; confidence 임계 위반 건수 | check_policy.py 내 관련 체크; confidence_threshold 미달 건 카운트 | 0 size guard 위반; 0 confidence 미달 미처리 건 | T2 |
| **3-5** Error Classification | B | T2 | P0/P1 정의 및 3-Strike 코드 존재 | `grep -r "P0\|P1\|3.Strike\|HALT" PROTOCOL.md` | §M-3 존재 + P0/P1 분류 기준 문서화 | T2 |
| **3-6** Rollback & Recovery | C | T3 | 롤백 가능 체크포인트 수 | `git log --grep="ctx-save" --oneline \| wc -l` | ≥ max_rollback_depth 개의 ctx-save 커밋 존재 | T2 |
| **3-7** Behavioral Tests | C | T3 | 자동화 정책 체크 통과율 (%) | `check-policy.bat` 전체 실행 → PASS/WARN/FAIL 수 | 10/10 체크 PASS (0 FAIL); WARN 2 이하 | T3 |
| **3-8** Post-Mortem Loop | C | T4 | PM 생성율 + Kaizen 해결율 (%) | `.ai/postmortems/` 파일 수 vs 발생한 P0/P1 수 | 100% P0/P1 → PM 생성; PM 고아 0건 (48h 이내 해결) | **T0** (미구현) |

### Cat 4: 환경 이식성

| 항목 | 유형 | 목표 Tier | 지표명 | 측정 방법 | 100% 기준 | 현재 Tier |
|:-----|:----:|:---------:|:-------|:---------|:---------|:---------:|
| **4-1** Runtime Environment | C | T3 | venv 격리 + PYTHONUTF8 준수 | `check-policy.bat` → pythonutf8-mandate; `Test-Path "_sys\env\venv"` | pythonutf8 PASS; venv 존재 | T3 |
| **4-2** Installation | C | T3 | install.bat 무결성 + WSB 테스트 | `install.bat --dry-run` 존재 여부; WSB 결과 | 0 오류; WSB 연기 <3분 | T2 |
| **4-3** Infra Abstraction | B | T2 | hub.py IPC 동작 | `hub status` → exit 0 | hub.py 실행 가능; nodes.json 유효 JSON | T2 |
| **4-4** Version Management | B | T2 | PROTOCOL.md 버전 태그 | `check-policy.bat` → protocol-version | **vX.Y** 형식 존재 + ≥ v3.3 | T3 |
| **4-5** Platform Independence | C | T3 | 절대경로 미존재 | `check-policy.bat` → no-hardcoded-paths | 0 hardcoded path 감지 (PASS) | T3 |
| **4-6** Onboarding Protocol | B | T2 | 노드 온보딩 체크리스트 존재 | `Test-Path ".ai/nodes.json"`; PROTOCOL.md §P-8 존재 | nodes.json 유효; §P-8 토큰 예산 문서화 | T2 |

### Cat 5: 운영 & 제어

| 항목 | 유형 | 목표 Tier | 지표명 | 측정 방법 | 100% 기준 | 현재 Tier |
|:-----|:----:|:---------:|:-------|:---------|:---------|:---------:|
| **5-1** Param Registry | C | T3 | config.json 스키마 유효성 | `python -c "import json; json.load(open('_sys/gemini/config.json'))"` + 필수 키 존재 확인 | 13개 파라미터 모두 존재 + `_param_sections` 정합성 PASS | T1 (갱신 필요) |
| **5-2** Behavioral Validation | C | T3 | 파라미터 범위 검증 | `check-policy.bat` 실행; config 스키마 체크 통과 | 0 범위 초과 파라미터; _param_sections 정합성 PASS | T2 |
| **5-3** Observability | C | T4 | 컨텍스트 건강 모니터링 실행 여부 | `check-health.bat` 실행 결과 + 로그 생성 확인 | GREEN/YELLOW/RED 판정 정확; 로그 자동 기록 | T3 |
| **5-4** Dashboard | C | T3 | 세션 상태 헤더 출력 가능 여부 | `hub status` 출력에 ROOM/RATE/HEALTH 포함 여부 | `hub status` → ROOM:{id} \| RATE:R{n} \| HEALTH:{kb}KB({color}) 형식 출력 | T1 |
| **5-5** Active Control Loop | C | T4 | 자동 개입 성공율 (%) | `active_control_enabled=1` 시 RED → GREEN 복구율 | 100% RED 상태 → 자동 ctx-save + rate 하향 → YELLOW/GREEN 복구 | **T0** (미구현) |
| **5-6** Economic Governance | C | T4 | 일일 토큰 예산 준수율 (%) | 쿼리 수 × 2000 + KB×4 / token_budget_daily × 100 | ≤100% 일일 예산; forecast 경보 발생 시 정확도 100% | **T0** (미구현) |

---

## 3. Level C — 핵심 Leaf 항목 상세 지표

서브카테고리 측정만으로 불충분한 특히 중요하거나 복잡한 항목.

### 3-1. Cat 1-1-3 Context Pruning

| 항목 | 내용 |
|:-----|:-----|
| **지표** | Pruning 적용율 (%) — 보존/삭제 결정이 있는 handoff.md 비율 |
| **측정** | handoff.md의 `[DONE]` 라벨 항목 수 vs 총 항목 수 |
| **100% 기준** | `[DONE]` 항목 100% 아카이브 이동됨; handoff.md 2KB 이하 |
| **자동화** | `(Get-Content .ai/sessions/room-*/handoff.md \| Measure-Object -Line).Lines` ≤ 100 |
| **현재 Tier** | T1 (기준 정의됨, 수동 확인만) |

### 3-2. Cat 2-6-2 Node Voting Bias (G17)

| 항목 | 내용 |
|:-----|:-----|
| **지표** | 노드별 반대 비율 — 특정 노드의 disagree 비율이 60% 이상인지 |
| **측정** | handoff.md CONSENSUS_HISTORY 파싱 → 노드별 vote 집계 |
| **100% 기준** | 패턴 감지 로직 실행 중; drift >60% 시 WARN 자동 발생 |
| **자동화** | 🔶 hub.py 신규 분석 함수 필요 |
| **현재 Tier** | T0 (미구현) |

### 3-3. Cat 3-4-5 Confidence Threshold

| 항목 | 내용 |
|:-----|:-----|
| **지표** | Low-Confidence Escalation 건수 / 전체 AI 출력 대비 비율 |
| **측정** | AI 출력에 `[LOW_CONFIDENCE]` 태그 포함 시 카운트 |
| **100% 기준** | confidence < confidence_threshold 시 100% 인간 게이트 요청 발생; 0 무시 |
| **자동화** | 🔶 출력 후처리 훅 필요 |
| **현재 Tier** | T1 (임계값 정의됨, 강제 없음) |

### 3-4. Cat 3-8 Post-Mortem Loop

| 항목 | 내용 |
|:-----|:-----|
| **지표 1** | PM 생성율 (%) = `.ai/postmortems/` 파일 수 / P0 오류 발생 수 × 100 |
| **지표 2** | PM 해결 시간 (h) = PM 생성 → PROTOCOL.md 업데이트까지 |
| **지표 3** | Orphan PM 수 = 48h 이상 미해결 PM 파일 수 |
| **측정** | `Get-ChildItem ".ai/postmortems/*.md"` 파일 수; 파일 내 `status: resolved` 확인 |
| **100% 기준** | PM 생성율 100%; Orphan 0건; 평균 해결 <48h |
| **자동화** | 🔶 G16 훅 구현 필요 |
| **현재 Tier** | T0 (미구현) |

### 3-5. Cat 5-5-2 Context RED Trigger

| 항목 | 내용 |
|:-----|:-----|
| **지표** | RED 상태 자동 복구율 (%) |
| **측정** | `active_control_enabled=1` 조건 하에 RED 진입 후 YELLOW/GREEN 복구 건수 / 전체 RED 진입 건수 |
| **100% 기준** | 100% RED → 자동 ctx-save 실행 → GREEN/YELLOW 복구; 0 미처리 RED |
| **자동화** | ✅ (active_control_enabled=1 시 자동, 0이면 비활성) |
| **현재 Tier** | T0 (active_control_enabled=0 기본값으로 비활성) |

### 3-6. Cat 5-6 Token ROI

| 항목 | 내용 |
|:-----|:-----|
| **지표** | Token ROI = (의미 있는 결정 수 × 결정당 가중치) / 일일 토큰 소비 추정치 |
| **측정** | FINALIZED 합의 수 + ctx-save 수 / (쿼리 수 × 2000 + context KB × 4) |
| **100% 기준** | 일일 token_budget_daily 초과 0건; ROI 추세 유지 또는 개선 중 |
| **자동화** | 🔶 hub.py 로깅 확장 필요 |
| **현재 Tier** | T0 (proxy 정의됨, 집계 없음) |

### 3-7. Cat 4-1-5 Zero-Config Hardening

| 항목 | 내용 |
|:-----|:-----|
| **지표** | Host Leakage Count (의도치 않은 외부 상태 변경 건수) |
| **측정 1** | `check-policy.bat` no-hardcoded-paths PASS/FAIL |
| **측정 2** | PS 실행정책: `(Get-ExecutionPolicy)` → RemoteSigned 이상 확인 |
| **측정 3** | `$PROFILE` 간섭: `$PROFILE` 내 P:\ 참조 없음 확인 |
| **100% 기준** | 0 hardcoded path; PS 실행정책 RemoteSigned+; 0 profile 간섭 |
| **자동화** | ✅ 부분 (check_policy.py + PS 명령) |
| **현재 Tier** | T2 (수동 확인 가능) |

---

## 4. Level D — Root Health Formula

### 4-1. 항목별 점수 계산

```
Item Score = min(Current Tier / Target Tier, 1.0)

예시:
  1-1 (C형, Target T4, 현재 T2): 2/4 = 0.50
  3-2 (C형, Target T3, 현재 T3): 3/3 = 1.00
  2-6 (C형, Target T4, 현재 T0): 0/4 = 0.00
```

### 4-2. 카테고리 점수

```
Category Score(catN) = mean( Item Score for all items in catN )
```

### 4-3. Root Health Score

```
Root Score = weighted_mean(Category Scores)

Weight 배분 (동등 가중치):
  Cat 1: 20%
  Cat 2: 20%
  Cat 3: 20%
  Cat 4: 20%
  Cat 5: 20%

Root Score = 0.2 × (Cat1 + Cat2 + Cat3 + Cat4 + Cat5)
```

### 4-4. "100% Complete" 판정 기준

아래 **모든 조건**이 동시에 충족될 때 100% 선언 가능:

| 조건 | 검증 명령 |
|:-----|:---------|
| ① `check-policy.bat` exit 0 (0 FAIL) | `cmd /c check-policy.bat; $LASTEXITCODE -eq 0` |
| ② `check-health.bat` GREEN 상태 | `cmd /c check-health.bat` → GREEN |
| ③ Root Score ≥ 0.95 (95%) | Level D 공식으로 계산 |
| ④ Level A KPI 5개 모두 목표치 충족 | 표 참조 |
| ⑤ G1–G15 모두 ✅ (🔶 없음) | TAXONOMY.md Gap Log 확인 |
| ⑥ Open PM (고아 Post-Mortem) 0건 | `.ai/postmortems/` 미해결 파일 0 |

> **현실적 천장**: G11 (Async Events) / Human Factors는 비결정론적이므로 조건 ⑤에서 G11은 🔶 허용.
> 실용 100% = 조건 ①②③④⑥ 충족 + G11 제외한 G1–G15 모두 ✅

---

## 5. 현재 상태 스냅샷 (2026-06-05)

### 5-1. 항목별 현재 Tier 요약

| Cat | 서브항목 | 유형 | 목표 | 현재 | Score |
|:---:|:---------|:----:|:----:|:----:|:-----:|
| 1 | 1-1 Context Lifecycle | C | T4 | T2 | 0.50 |
| 1 | 1-2 Session Continuity | B | T2 | T2 | **1.00** |
| 1 | 1-3 Memory Persistence | C | T4 | T2 | 0.50 |
| 1 | 1-4 Instruction Design | B | T2 | T2 | **1.00** |
| **1** | **Cat 1 평균** | | | | **0.75** |
| 2 | 2-1 Consensus | C | T3 | T3 | **1.00** |
| 2 | 2-2 Division of Labor | B | T2 | T2 | **1.00** |
| 2 | 2-3 Conflict Resolution | B | T2 | T2 | **1.00** |
| 2 | 2-4 Node Management | C | T3 | T3 | **1.00** |
| 2 | 2-5 Transparency | B | T2 | T1 | 0.50 |
| 2 | 2-6 Decision Attribution | C | T4 | T0 | 0.00 |
| **2** | **Cat 2 평균** | | | | **0.75** |
| 3 | 3-1 Security & Trust | B | T2 | T3 | **1.00** |
| 3 | 3-2 Policy Enforcement | C | T3 | T3 | **1.00** |
| 3 | 3-3 Change Management | B | T2 | T2 | **1.00** |
| 3 | 3-4 Output Validation | C | T3 | T2 | 0.67 |
| 3 | 3-5 Error Classification | B | T2 | T2 | **1.00** |
| 3 | 3-6 Rollback & Recovery | C | T3 | T2 | 0.67 |
| 3 | 3-7 Behavioral Tests | C | T3 | T3 | **1.00** |
| 3 | 3-8 Post-Mortem Loop | C | T4 | T0 | 0.00 |
| **3** | **Cat 3 평균** | | | | **0.79** |
| 4 | 4-1 Runtime Environment | C | T3 | T3 | **1.00** |
| 4 | 4-2 Installation | C | T3 | T2 | 0.67 |
| 4 | 4-3 Infra Abstraction | B | T2 | T2 | **1.00** |
| 4 | 4-4 Version Management | B | T2 | T3 | **1.00** |
| 4 | 4-5 Platform Independence | C | T3 | T3 | **1.00** |
| 4 | 4-6 Onboarding Protocol | B | T2 | T2 | **1.00** |
| **4** | **Cat 4 평균** | | | | **0.94** |
| 5 | 5-1 Param Registry | C | T3 | T1 | 0.33 |
| 5 | 5-2 Behavioral Validation | C | T3 | T2 | 0.67 |
| 5 | 5-3 Observability | C | T4 | T3 | 0.75 |
| 5 | 5-4 Dashboard | C | T3 | T1 | 0.33 |
| 5 | 5-5 Active Control Loop | C | T4 | T0 | 0.00 |
| 5 | 5-6 Economic Governance | C | T4 | T0 | 0.00 |
| **5** | **Cat 5 평균** | | | | **0.35** |

### 5-2. Root Score 계산 (현재)

```
Root Score = 0.2 × (0.75 + 0.75 + 0.79 + 0.94 + 0.35)
           = 0.2 × 3.58
           = 0.716  →  71.6%

실제 체감 완성도(문서/정책 중심): ~86%
시스템 동작 기준 완성도(Tier 달성):  71.6%
```

> **차이의 해석**: 86%는 "모든 항목이 정의되어 있음"을 반영. 71.6%는 "자동화 검증까지 완료됨"을 반영.
> 두 지표를 함께 사용해야 정확한 상태 파악 가능.

### 5-3. 100% 도달을 위한 우선 행동 (Tier 상승 기준)

| 우선 | 항목 | 현재 | 목표 | 조치 | 점수 기여 |
|:----:|:-----|:----:|:----:|:-----|:-------:|
| **P0** | 5-1 Param Registry | T1 | T3 | config.json 갱신 + 스키마 검증 스크립트 | +0.34 × 0.2/6 |
| **P0** | 5-6 Economic Governance | T0 | T4 | Token Proxy 집계 스크립트 | +1.00 × 0.2/6 |
| P1 | 5-5 Active Control Loop | T0 | T4 | active_control 로직 구현 | +1.00 × 0.2/6 |
| P1 | 3-8 Post-Mortem Loop | T0 | T4 | PM 템플릿 + P0 훅 | +1.00 × 0.2/8 |
| P1 | 2-6 Decision Attribution | T0 | T4 | handoff.md 파싱 + 귀속 로깅 | +1.00 × 0.2/6 |
| P2 | 5-4 Dashboard | T1 | T3 | hub status 형식 개선 | +0.67 × 0.2/6 |
| P2 | 1-1 Context Lifecycle | T2 | T4 | 자동 ctx-save 루프 | +0.50 × 0.2/4 |
| P2 | 2-5 Transparency | T1 | T2 | §M-2 check_policy 추가 | +0.50 × 0.2/6 |

**모든 P0/P1 완료 시 예상 Root Score: ~88%**
**모든 P0~P2 완료 시 예상 Root Score: ~93%**
**최종 100% (이론) 조건**: T0 항목 전부 해소 + Active Monitoring 전 항목 실행 중

---

## 6. 측정 명령 Quick Reference

```powershell
# Cat 3: Policy Gate (Axis-J)
cmd /c "P:\_sys\checks\check-policy.bat"

# Cat 1/5: Context Health (Axis-H)
cmd /c "P:\_sys\checks\check-health.bat"

# Cat 2: Hub 상태
cmd /c "P:\_sys\cli\msg.bat" hub status

# Cat 4: 절대경로 확인 (check_policy 내 포함)
cmd /c "P:\_sys\checks\check-policy.bat" 2>&1 | Select-String "hardcoded"

# Cat 1: handoff.md 크기
(Get-Item "P:\.ai\sessions\room-7fb9\handoff.md").Length / 1KB

# Cat 1: Memory 파일 수
(Get-ChildItem "P:\_sys\claude\config\projects\P--\memory\*.md").Count

# Cat 4: PS 실행정책
Get-ExecutionPolicy

# Cat 5: config.json 유효성
python -c "import json; d=json.load(open('P:/_sys/gemini/config.json')); print('OK:', list(d.keys()))"

# Root Score 자동 계산 (미구현 — P2 과제)
# python P:\_sys\checks\calc_completion.py
```

---

## 7. 지표 거버넌스

- **이 파일 수정 시**: TAXONOMY.md와 동일하게 R:10 합의 필요
- **지표 추가/삭제**: TAXONOMY.md의 항목 추가/삭제와 반드시 동기화
- **현재 상태 스냅샷(섹션 5)**: 분기별 또는 주요 구현 완료 후 갱신
- **자동화 우선순위**: T0 항목이 자동화의 최우선 대상
