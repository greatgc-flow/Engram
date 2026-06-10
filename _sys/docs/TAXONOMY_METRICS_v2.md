# TAXONOMY_METRICS_v2.md — Measurement & Completion Framework

> **Companion to**: `_sys/docs/TAXONOMY.md` v5.0
> **Authors**: Claude Code (CC) + Gemini CLI (GC) | R:10 Brain Sync | 2026-06-05
> **Revision**: v2 — 11 defects (D01–D11) + 3 Claude additions (A01–A03) resolved
> **Purpose**: For each taxonomy item, define (1) measurable indicator (2) measurement method (3) "100% complete" judgment criterion.
> **Do NOT modify TAXONOMY.md** — use WinMerge to merge selectively.

---

## 0. Measurement Framework Overview

### 0-1. Hybrid DoD (Definition of Done)

두 가지 항목 유형에 서로 다른 DoD를 적용한다.

#### Type B — Binary/Structural Items
정책·문서·구조의 존재 여부가 핵심인 항목. 연속 모니터링 불필요.

| Tier | 달성 기준 | 완성도 |
|:----:|:---------|:------:|
| T0 | 미정의 | 0% |
| T1 | 정책/문서 초안 작성 완료 | 50% |
| **T2** | **정적 체크 또는 시스템 제약으로 강제 적용** | **100%** ← 목표 |

> **[A01 fix]** 현재 Tier > 목표 Tier인 경우(예: B형 항목이 T3 달성) → Score = min(current/target, 1.0) = **1.00** (상한 고정).

#### Type C — Continuous/Operational Items
지속적 측정·모니터링이 의미 있는 항목.

| Tier | 달성 기준 | 완성도 |
|:----:|:---------|:------:|
| T0 | 미정의 | 0% |
| T1 | 임계값/정의 문서화 완료 | 25% |
| T2 | 구현 존재, 수동 체크 가능 | 50% |
| T3 | 자동화 체크/스크립트 존재 | 75% |
| **T4** | **능동 모니터링 실행 중 + 임계 위반 시 자동 알림/행동** | **100%** ← 목표 |

#### [D06 fix] 항목 유형 재분류 사항

기존 B형으로 잘못 분류된 항목:

| 항목 | 변경 | 이유 |
|:-----|:-----|:-----|
| 3-3 Change Management | B → **C** | Commit 형식은 매 커밋마다 발생, 연속 모니터링 필요 |
| 4-3 Infra Abstraction | B → **C** | hub.py IPC 상태는 시스템 부하에 따라 변동 |
| 2-5 Transparency | B → **C** | §M-2 정책 문서만으로 준수 보장 안됨, 로그 스캔 필요 |

---

### 0-2. 측정 실패 시 collab_rate 연동 행동

| collab_rate | Tier 3/4 지표 실패 시 행동 |
|:-----------:|:--------------------------|
| R:10 | **HALT + ESCALATE** — exit 1, Human Gate 호출 |
| R:5–8 | **WARN + 계속** — `.ai/metrics/health-{date}.log` 기록 |
| R:0–3 | **LOG only** — 조용히 기록, 중단 없음 |

---

### 0-3. 토큰 측정 방식 (Token Proxy)

API 레벨 토큰 카운팅은 로컬 포터블 환경에서 불가.

| 프록시 지표 | 측정 방법 | 환산 기준 |
|:-----------|:---------|:---------|
| Context KB | `check_health.py` JSONL 크기 | 1 KB ≈ 250 tokens |
| Gemini 쿼리 수 | `msg.bat` 호출 횟수/일 | 1 query ≈ 2,000 tokens |
| FINALIZED 합의 수 | handoff.md CONSENSUS_HISTORY 파싱 | 활동량 대리 지표 |

> **[D02 fix]** Token ROI 분자 = `count(FINALIZED_DIRECTIVEs) + count(merged PRs)` (객관적 이벤트만).

---

### 0-4. ZeroBase 환경 기준

> **[D04 fix]** 모든 측정 명령은 드라이브 레터 독립적. `P:\` 대신 상대경로 `.\_sys\...` 또는 `$env:BASE_DIR` 사용.
> PowerShell 5.1 native 명령만 사용. POSIX 도구(grep, wc, awk) 전면 금지.

---

## 1. Level A — Category KPIs

| Cat | 카테고리 | KPI 이름 | 측정 명령 (ZeroBase PS) | 100% 조건 | 자동화 | 현재 Tier |
|:---:|:---------|:---------|:----------------------|:---------|:------:|:---------:|
| **1** | 인지 연속성 | **Context Adherence Rate** (GREEN 체류 비율 %) | `cmd /c ".\_sys\checks\check-health.bat"` → 결과 파싱 | GREEN 95%+; `handoff.md` 항상 <2KB | ✅ 부분 | T2 |
| **2** | 협업 거버넌스 | **Consensus Success Rate** (FINALIZED / 총 라운드 %) | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "FINALIZED"` 카운트 | 총 라운드의 95%+ FINALIZED; 타임아웃(≥`consensus_timeout_min`) <5% | 🔶 부분 | T2 |
| **3** | 시스템 무결성 | **Policy PASS Rate** (전체 실행 중 exit 0 비율 %) | `cmd /c ".\_sys\checks\check-policy.bat"; $LASTEXITCODE` | exit 0 (0 FAIL); P0/P1 발생건 모두 PM 파일 존재 | ✅ | T3 |
| **4** | 환경 이식성 | **Host Isolation Integrity** (유출 건수) | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "hardcoded"` | 0 절대경로; `Get-ExecutionPolicy` = RemoteSigned+ | ✅ 부분 | T2 |
| **5** | 운영 & 제어 | **Token Budget Adherence** (소비/예산 %) | `@(Get-ChildItem ".ai\sessions\*\handoff.md" \| Select-String "msg.bat").Count × 2000 / token_budget_daily` | ≤100% 일일 예산; **예산 소진 직전 경보 발생 0-miss** [D08 fix] | 🔶 미구현 | T1 |

> **[D08 fix]** Cat 5 KPI 100% 조건: "forecast 정확도 100%"는 검증 불가 → **"예산 소진 발생건 중 사전 경보 없는 건 = 0"** 으로 대체.

> **[D11 fix] 카테고리 가중치 조정** (섹션 4에 적용):
> Cat 1: 20% | Cat 2: 25% | **Cat 3: 30%** | Cat 4: 15% | **Cat 5: 10%**
> 근거: Integrity 실패는 실행 차단(생존 조건); Operations 미달은 비효율에 그침.

---

## 2. Level B — Sub-category Metrics

모든 2단계 항목(X-N)에 대한 지표. 모든 명령은 ZeroBase PS 5.1 기준.

### Cat 1: 인지 연속성

| 항목 | 유형 | 목표 Tier | 지표명 | 측정 방법 (PowerShell) | 100% 기준 | 현재 Tier |
|:-----|:----:|:---------:|:-------|:----------------------|:---------|:---------:|
| **1-1** Context Lifecycle | C | T4 | Context KB 추이 | `cmd /c ".\_sys\checks\check-health.bat"` | GREEN 95%+ 유지; RED 진입 0건 (48h 기준) | T2 |
| **1-2** Session Continuity | B | T2 | handoff.md 구조 준수 | `(Get-Item ".ai\sessions\room-*\handoff.md").Length / 1KB` | ≤2KB; 6개 섹션 헤더 모두 존재 (`Select-String "## \[GOAL\]"` 등) | T2 |
| **1-3** Memory Persistence | C | T4 | Memory 신선도 (stale 파일 수) | `python ".\_sys\hooks\memory_compactor.py" 2>&1` 출력에서 "stale" 카운트 [D09 fix: --dry-run 없음] | stale 0건; compactor 최근 실행일 ≤ compactor_interval_days | T2 |
| **1-4** Instruction Design | B | T2 | 글로벌/프로젝트 config 존재 | `Test-Path ".\_sys\claude\config\CLAUDE.md"` AND `Test-Path ".\CLAUDE.md"` | 두 파일 존재 + `R:10` 문자열 포함 | T2 |

### Cat 2: 협업 거버넌스

| 항목 | 유형 | 목표 Tier | 지표명 | 측정 방법 (PowerShell) | 100% 기준 | 현재 Tier |
|:-----|:----:|:---------:|:-------|:----------------------|:---------|:---------:|
| **2-1** Consensus Protocol | C | T3 | 합의 액션 구현 여부 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "hub-consensus-actions"` | "PASS" 포함 | T3 |
| **2-2** Division of Labor | C | T3 | 실제 다중 노드 참여율 [A02 fix] | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "from.*cc\|from.*gc\|from.*ca"` 건수 | ≥2개 노드가 각각 ≥1건 DIRECTIVE 발송 기록; nodes.json 유효 | T2 |
| **2-3** Conflict Resolution | B | T2 | ESCALATE 코드 존재 | `Select-String -Path ".\_sys\core\hub.py" -Pattern "ESCALATE"` [D01 fix] | hub.py에 ESCALATE 처리 존재; §M-3 HALT 코드 존재 | T2 |
| **2-4** Node Management | C | T3 | collab_rate 대칭성 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "collab-rate-symmetry"` | "PASS" 포함 | T3 |
| **2-5** Transparency | **C** [D06] | T3 | Private channel 부재 (로그 스캔) | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "private\|direct.*only\|offchannel"` | 0건 감지 + §M-2 문자열 PROTOCOL.md에 존재 | T2→T3 필요 |
| **2-6** Decision Attribution | C | T4 | Attribution Coverage (%) | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "Proposer:"` 건수 / FINALIZED 총 건 | 100% FINALIZED에 Proposer: 필드 존재; drift 감지 실행 중 | **T0** |

### Cat 3: 시스템 무결성

> **[D03 fix]** 3-2와 3-7은 서로 다른 계층을 측정한다.
> - **3-2 Policy Enforcement**: *정적* 체크 (코드/문서 정합성 — check_policy.py 10개 체크)
> - **3-7 Behavioral Tests**: *런타임* 행동 (실제 R:10 투표 발생 여부 — 로그 파싱)

| 항목 | 유형 | 목표 Tier | 지표명 | 측정 방법 (PowerShell) | 100% 기준 | 현재 Tier |
|:-----|:----:|:---------:|:-------|:----------------------|:---------|:---------:|
| **3-1** Security & Trust | B | T2 | Constitutional 파일 보호 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "r10-files-exist"` | "PASS" [A01: T3 달성 → Score 1.00 capped] | **T3 → Score 1.00** |
| **3-2** Policy Enforcement (Static) | C | T3 | 정적 정책 게이트 PASS율 | `cmd /c ".\_sys\checks\check-policy.bat"; $LASTEXITCODE` → 0=PASS | exit 0; 10/10 체크 PASS (0 FAIL) | T3 |
| **3-3** Change Management | **C** [D06] | T3 | Commit 형식 준수율 (%) | `@(git log --oneline -20 \| Select-String -Pattern "^[0-9a-f]+ (feat\|fix\|docs\|refactor\|test\|chore):").Count / 20 × 100` [D01 fix] | ≥95% 준수 | T2 |
| **3-4** Output Validation | C | T3 | Size guard 위반 건수 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "size-guard\|include-guard"` | 0 위반; confidence 미달 미처리 0건 | T2 |
| **3-5** Error Classification | B | T2 | P0/P1 분류 기준 존재 | `Select-String -Path ".\PROTOCOL.md" -Pattern "§M-3"` [D01 fix] | §M-3 존재 + P0/P1 분류 문서화 | T2 |
| **3-6** Rollback & Recovery | C | T3 | 롤백 가능 체크포인트 수 | `@(git log --grep="ctx-save" --oneline).Count` [D01 fix: wc -l → .Count] | `≥ max_rollback_depth` 개 ctx-save 커밋 존재 | T2 |
| **3-7** Behavioral Tests (Runtime) | C | T3 | **런타임** 합의 준수율 [D03 fix] | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "FINALIZED"` 건 / 전체 DIRECTIVE 건 | ≥95% DIRECTIVE가 FINALIZED 추적 가능; 비인가 직접 수정 0건 | T2→T3 필요 |
| **3-8** Post-Mortem Loop | C | T4 | PM 생성율 + 해결율 [D07 fix] | `@(Get-ChildItem ".ai\postmortems\*.md" -ErrorAction SilentlyContinue).Count` | PM 생성 트리거 = `ESCALATE` 호출 + 3-Strike HALT 횟수 [D07]; Orphan 0건 (48h) | **T0** |

### Cat 4: 환경 이식성

| 항목 | 유형 | 목표 Tier | 지표명 | 측정 방법 (PowerShell) | 100% 기준 | 현재 Tier |
|:-----|:----:|:---------:|:-------|:----------------------|:---------|:---------:|
| **4-1** Runtime Environment | C | T3 | venv 격리 + PYTHONUTF8 준수 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "pythonutf8"` AND `Test-Path ".\_sys\env\venv"` | "PASS"; venv 존재 | T3 |
| **4-2** Installation | C | T3 | install.bat 존재 + 실행 결과 [D09 fix] | `Test-Path ".\_sys\install.bat"` + `(Get-Item ".\_sys\install.bat").LastWriteTime` | 파일 존재; 수동 실행 시 0 오류 (--dry-run 미존재 → 파일 메타데이터로 대체) | T2 |
| **4-3** Infra Abstraction | **C** [D06] | T3 | hub.py IPC 응답 여부 | `cmd /c ".\_sys\cli\msg.bat" hub status; $LASTEXITCODE` | exit 0; nodes.json 유효 JSON (`python -c "import json; json.load(open('.ai/nodes.json'))"`) | T2 |
| **4-4** Version Management | B | T2 | PROTOCOL.md 버전 태그 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "protocol-version"` | "PASS" [A01: T3 달성 → Score 1.00] | **T3 → Score 1.00** |
| **4-5** Platform Independence | C | T3 | 절대경로 미존재 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "no-hardcoded-paths"` | "PASS" | T3 |
| **4-6** Onboarding Protocol | B | T2 | 온보딩 체크리스트 존재 | `Test-Path ".ai\nodes.json"` AND `Select-String -Path ".\PROTOCOL.md" -Pattern "§P-8"` | nodes.json 유효; §P-8 존재 | T2 |

### Cat 5: 운영 & 제어

| 항목 | 유형 | 목표 Tier | 지표명 | 측정 방법 (PowerShell) | 100% 기준 | 현재 Tier |
|:-----|:----:|:---------:|:-------|:----------------------|:---------|:---------:|
| **5-1** Param Registry | C | T3 | config.json 스키마 유효성 | `python -c "import json; d=json.load(open('.\_sys\gemini\config.json')); assert len(d)==14"` (13개 파라미터 + _param_sections) | 13개 파라미터 + `_param_sections` 모두 존재; 범위 내 값 | T1 |
| **5-2** Behavioral Validation | C | T3 | 파라미터 범위 검증 | `cmd /c ".\_sys\checks\check-policy.bat"` (collab-rate-symmetry 포함) | 0 범위 초과; _param_sections 선언 키 = 실제 키 | T2 |
| **5-3** Observability | C | T4 | 건강 모니터링 실행 여부 | `cmd /c ".\_sys\checks\check-health.bat"; $LASTEXITCODE` | exit 0; GREEN/YELLOW/RED 판정 + 로그 생성 | T3 |
| **5-4** Dashboard | C | T3 | 세션 헤더 출력 여부 | `cmd /c ".\_sys\cli\msg.bat" hub status 2>&1 \| Select-String "ROOM:"` | "ROOM:{id} \| RATE: \| HEALTH:" 형식 포함 | T1 |
| **5-5** Active Control Loop | C | T4 | 자동 개입 성공율 (%) | `active_control_enabled` 파라미터 값 확인; 로그에서 "AUTO_CTX_SAVE" 이벤트 카운트 | `active_control_enabled=1` 조건 하: 100% RED → YELLOW/GREEN 복구 | **T0** |
| **5-6** Economic Governance | C | T4 | 일일 예산 준수율 (%) | `@(Get-ChildItem ".ai\sessions\*\handoff.md" \| Select-String "msg.bat").Count × 2000` → token_budget_daily 대비 | ≤100%; 예산 소진 전 경보 0-miss | **T0** |

---

## 3. Level C — 핵심 Leaf 항목 상세 지표

### 3-1. Cat 1-1-3 Context Pruning

| 항목 | 내용 |
|:-----|:-----|
| **지표** | Pruning 적용율 (%) = `[DONE]` 아카이브된 항목 / 전체 항목 |
| **측정** | `@(Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "\[DONE\]").Count` / 총 항목 수 |
| **100% 기준** | `[DONE]` 항목 100% 아카이브; handoff.md ≤ 100줄 (`(Get-Content "...handoff.md").Count`) |
| **자동화** | ✅ 부분 (수동 트리거 + PS 측정) |
| **현재 Tier** | T1 |

### 3-2. Cat 2-4-4 Resilience / Re-sync Protocol [D05 fix — 신규]

| 항목 | 내용 |
|:-----|:-----|
| **지표 1** | 오프라인 노드 감지 시간 (min) = auto-abstain 발생까지 걸린 시간 |
| **지표 2** | Re-sync 성공율 (%) = 복귀 노드가 state diff 요약 후 VOTE 재참여 완료한 비율 |
| **측정** | handoff.md에서 `auto-abstain` 및 `re-sync` 이벤트 파싱: `Select-String -Path ".ai\sessions\*\handoff.md" -Pattern "abstain\|re-sync"` |
| **100% 기준** | 오프라인 감지 < `consensus_timeout_min`분; Re-sync 완료율 100% |
| **자동화** | 🔶 hub.py 이벤트 로깅 확장 필요 |
| **현재 Tier** | T1 (§P-3-QR 정의됨, 로그 없음) |

### 3-3. Cat 2-6-2 Node Voting Bias (G17)

| 항목 | 내용 |
|:-----|:-----|
| **지표** | 노드별 disagree 비율 (%) |
| **측정** | `Select-String -Path ".ai\sessions\*\handoff.md" -Pattern "disagree\|oppose"` → 노드별 집계 |
| **100% 기준** | 단일 노드 disagree율 <60%; drift >60% 시 WARN 자동 발생 |
| **자동화** | 🔶 hub.py 분석 함수 필요 |
| **현재 Tier** | T0 |

### 3-4. Cat 3-4-5 Confidence Threshold

| 항목 | 내용 |
|:-----|:-----|
| **지표** | Low-Confidence Escalation 누락 건수 (0이어야 함) |
| **측정** | `Select-String -Path ".ai\sessions\*\handoff.md" -Pattern "\[LOW_CONFIDENCE\]"` 건수 vs Human Gate 요청 건수 |
| **100% 기준** | `[LOW_CONFIDENCE]` 태그 100%가 Human Gate 요청으로 이어짐; 누락 0건 |
| **자동화** | 🔶 출력 후처리 훅 필요 |
| **현재 Tier** | T1 (임계값 정의됨) |

### 3-5. Cat 3-6-3 State Migration Protocol (G13) [D05 fix — 신규]

| 항목 | 내용 |
|:-----|:-----|
| **지표 1** | Schema version 추적 여부 (Boolean) |
| **지표 2** | 레거시 room 호환성 (%) = 구 버전 room이 신 버전 hub.py에서 오류 없이 로드되는 비율 |
| **측정 1** | `python -c "import json; d=json.load(open('.ai/nodes.json')); print(d.get('version','MISSING'))"` |
| **측정 2** | 수동: 이전 버전 room state.json을 현재 hub.py로 로드 → 오류 카운트 |
| **100% 기준** | version 필드 존재; 모든 레거시 room 오류 없이 로드됨 |
| **자동화** | 🔶 migration_check.py 구현 필요 |
| **현재 Tier** | T1 (절차 정의됨) |

### 3-6. Cat 3-8 Post-Mortem Loop [D07 fix 적용]

| 항목 | 내용 |
|:-----|:-----|
| **지표 1** | PM 생성율 (%) = `postmortems/*.md` 수 / (`ESCALATE` 호출 수 + 3-Strike HALT 수) × 100 [D07] |
| **지표 2** | Orphan PM 수 = 48h 이상 `status: open` 상태인 파일 수 |
| **지표 3** | 평균 해결 시간 (h) |
| **측정** | `@(Get-ChildItem ".ai\postmortems\*.md" -ErrorAction SilentlyContinue \| Where-Object { (Get-Content $_.FullName) -match "status: open" }).Count` |
| **100% 기준** | PM 생성율 100%; Orphan 0건; 평균 해결 <48h |
| **자동화** | 🔶 G16 훅 구현 필요 |
| **현재 Tier** | T0 |

### 3-7. Cat 5-3-2 Async Event Handling (G11) [A03 fix — 신규]

| 항목 | 내용 |
|:-----|:-----|
| **지표** | 미처리 out-of-band 이벤트 건수 |
| **측정** | `Select-String -Path ".ai\sessions\*\handoff.md" -Pattern "ASYNC_EVENT\|OOB_EVENT"` 건수 vs "HANDLED" 건수 |
| **100% 기준** | 감지된 모든 이벤트에 "HANDLED" 또는 "ESCALATED" 태그 존재; 무시된 이벤트 0건 |
| **자동화** | 🔶 이벤트 핸들러 정책 구현 필요 |
| **현재 Tier** | T1 (정책 정의됨, 핸들러 없음) |

### 3-8. Cat 5-5-2 Context RED Trigger

| 항목 | 내용 |
|:-----|:-----|
| **지표** | RED 상태 자동 복구율 (%) |
| **측정** | `active_control_enabled=1` 조건 하: RED 진입 건수 vs GREEN/YELLOW 복구 건수 (hub 로그 파싱) |
| **100% 기준** | 100% RED → 자동 ctx-save → 복구; 0 미처리 RED |
| **자동화** | ✅ (`active_control_enabled=1` 시 자동; default=0이므로 현재 비활성) |
| **현재 Tier** | T0 |

### 3-9. Cat 5-6 Token ROI [D02 fix 적용]

| 항목 | 내용 |
|:-----|:-----|
| **지표** | Token ROI = `(FINALIZED_DIRECTIVEs + merged_PRs) / (daily_query_count × 2000 + context_KB × 4)` |
| **측정** | `@(Select-String -Path ".ai\sessions\*\handoff.md" -Pattern "FINALIZED").Count` + `@(git log --oneline --merges).Count` |
| **100% 기준** | 일일 token_budget_daily 초과 0건; ROI 추세 전주 대비 ≥ -10% (허용 감소폭) |
| **자동화** | 🔶 hub.py 로깅 확장 필요 |
| **현재 Tier** | T0 |

### 3-10. Trade-off Balance Metrics — T3 & T17 [D10 fix — 신규]

> Trade-off는 "존재 여부"가 아니라 **"균형이 유지되는가"** 를 측정해야 한다.

#### T3: 합의 정확성 vs 속도

| 항목 | 내용 |
|:-----|:-----|
| **지표** | Mean Time to Consensus (MTC, 분) vs Rejection Rate (%) |
| **측정** | handoff.md CONSENSUS_HISTORY에서 propose→FINALIZED 시간 차이 평균 |
| **100% 기준** | MTC ≤ `consensus_timeout_min` × 0.5; Rejection Rate (ESCALATE/전체) ≤ 10% |
| **균형 범위** | MTC 상승하면 정확성 ↑; Rejection Rate 상승하면 collab_rate 재검토 필요 |

#### T17: 토큰 경제성 vs 협업 깊이

| 항목 | 내용 |
|:-----|:-----|
| **지표** | Budget Utilization (%) vs Consensus Rounds per Decision (n) |
| **측정** | `daily_tokens / token_budget_daily × 100` vs `avg(rounds_per_FINALIZED)` |
| **100% 기준** | Budget <90%; 결정당 평균 라운드 ≤ 3 |
| **균형 범위** | Budget 높은데 Rounds 낮으면 토큰 낭비; Rounds 높으면 collab_rate 낮추기 고려 |

### 3-11. Cat 4-1-5 Zero-Config Hardening

| 항목 | 내용 |
|:-----|:-----|
| **지표** | Host 유출 건수 |
| **측정 1** | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "hardcoded"` → "PASS" 확인 |
| **측정 2** | `Get-ExecutionPolicy` = `RemoteSigned` 이상 |
| **측정 3** | `if (Test-Path $PROFILE) { Select-String -Path $PROFILE -Pattern "BASE_DIR\|_sys" }` → 0건 또는 합법적 참조만 |
| **100% 기준** | 0 hardcoded path; ExecPolicy ≥ RemoteSigned; $PROFILE 간섭 0건 |
| **자동화** | ✅ 부분 |
| **현재 Tier** | T2 |

---

## 4. Level D — Root Health Formula

### 4-1. 항목별 점수

```
Item Score = min(Current Tier / Target Tier, 1.0)

예시:
  1-1 (C, Target T4, 현재 T2): 2/4 = 0.50
  3-2 (C, Target T3, 현재 T3): 3/3 = 1.00
  3-1 (B, Target T2, 현재 T3): min(3/2, 1.0) = 1.00  ← 상한 고정 [A01]
  2-6 (C, Target T4, 현재 T0): 0/4 = 0.00
```

### 4-2. 카테고리 점수

```
Category Score = mean(Item Scores in category)
```

### 4-3. Root Health Score [D11 fix — 가중치 조정]

```
Root Score = 0.20 × Cat1 + 0.25 × Cat2 + 0.30 × Cat3 + 0.15 × Cat4 + 0.10 × Cat5

근거:
  Cat 3 (Integrity, 30%):  실패 시 실행 차단 — 생존 조건
  Cat 2 (Governance, 25%): 합의 실패 시 잘못된 방향 진행
  Cat 1 (Continuity, 20%): 컨텍스트 손실은 회복 가능
  Cat 4 (Portability, 15%): 환경 문제는 재설치로 해결
  Cat 5 (Operations, 10%): 미달성 시 비효율이지 시스템 중단 아님
```

### 4-4. "100% Complete" 판정 기준 (6조건 동시 충족)

| 조건 | 검증 명령 |
|:-----|:---------|
| ① `check-policy.bat` exit 0 | `cmd /c ".\_sys\checks\check-policy.bat"; $LASTEXITCODE -eq 0` |
| ② `check-health.bat` GREEN | `cmd /c ".\_sys\checks\check-health.bat" 2>&1 \| Select-String "GREEN"` |
| ③ Root Score ≥ 0.95 | Level D 공식 계산 (weighted) |
| ④ Level A KPI 5개 목표 달성 | 섹션 1 표 참조 |
| ⑤ G1–G17 모두 ✅ (G11 제외 🔶 허용) | TAXONOMY.md Gap Log |
| ⑥ Orphan Post-Mortem 0건 | `@(Get-ChildItem ".ai\postmortems\*.md" \| Where-Object {(Get-Content $_) -match "status: open"}).Count -eq 0` |

---

## 5. 현재 상태 스냅샷 (2026-06-05, v2 재계산)

### 5-1. Tier 요약 (v2 수정 반영)

| Cat | 항목 | 유형 | 목표 | 현재 | Score |
|:---:|:-----|:----:|:----:|:----:|:-----:|
| 1 | 1-1 | C | T4 | T2 | 0.50 |
| 1 | 1-2 | B | T2 | T2 | 1.00 |
| 1 | 1-3 | C | T4 | T2 | 0.50 |
| 1 | 1-4 | B | T2 | T2 | 1.00 |
| **1** | **평균** | | | | **0.75** |
| 2 | 2-1 | C | T3 | T3 | 1.00 |
| 2 | 2-2 | C | T3 | T2 | **0.67** ← v2 수정 |
| 2 | 2-3 | B | T2 | T2 | 1.00 |
| 2 | 2-4 | C | T3 | T3 | 1.00 |
| 2 | 2-5 | **C** | **T3** | T1 | **0.33** ← v2 수정 |
| 2 | 2-6 | C | T4 | T0 | 0.00 |
| **2** | **평균** | | | | **0.67** ← v2 하락 |
| 3 | 3-1 | B | T2 | T3→1.00 | 1.00 |
| 3 | 3-2 | C | T3 | T3 | 1.00 |
| 3 | 3-3 | **C** | **T3** | T2 | **0.67** ← v2 수정 |
| 3 | 3-4 | C | T3 | T2 | 0.67 |
| 3 | 3-5 | B | T2 | T2 | 1.00 |
| 3 | 3-6 | C | T3 | T2 | 0.67 |
| 3 | 3-7 | C | T3 | **T2** | **0.67** ← v2 수정 (Runtime 미확인) |
| 3 | 3-8 | C | T4 | T0 | 0.00 |
| **3** | **평균** | | | | **0.71** ← v2 재계산 |
| 4 | 4-1 | C | T3 | T3 | 1.00 |
| 4 | 4-2 | C | T3 | T2 | 0.67 |
| 4 | 4-3 | **C** | **T3** | T2 | **0.67** ← v2 수정 |
| 4 | 4-4 | B | T2 | T3→1.00 | 1.00 |
| 4 | 4-5 | C | T3 | T3 | 1.00 |
| 4 | 4-6 | B | T2 | T2 | 1.00 |
| **4** | **평균** | | | | **0.89** ← v2 재계산 |
| 5 | 5-1 | C | T3 | T1 | 0.33 |
| 5 | 5-2 | C | T3 | T2 | 0.67 |
| 5 | 5-3 | C | T4 | T3 | 0.75 |
| 5 | 5-4 | C | T3 | T1 | 0.33 |
| 5 | 5-5 | C | T4 | T0 | 0.00 |
| 5 | 5-6 | C | T4 | T0 | 0.00 |
| **5** | **평균** | | | | **0.35** |

### 5-2. Root Score v2 (가중치 적용)

```
Root Score = 0.20×0.75 + 0.25×0.67 + 0.30×0.71 + 0.15×0.89 + 0.10×0.35
           = 0.150 + 0.168 + 0.213 + 0.134 + 0.035
           = 0.700  →  70.0%

v1 대비: 71.6%→70.0% (가중치 조정 + 지표 정밀화로 소폭 하락 — 더 정확한 측정)
체감 완성도(문서): ~86%  /  시스템 완성도(Tier): 70.0%
```

### 5-3. 100% 도달 행동 (v2 Tier 기준)

| 우선 | 항목 | 현재 | 목표 | 조치 | Root 기여 |
|:----:|:-----|:----:|:----:|:-----|:--------:|
| **P0** | 5-1 Param Registry | T1 | T3 | config.json 갱신 + 스키마 검증 스크립트 | +0.19% |
| **P0** | 5-6 Economic | T0 | T4 | Token Proxy 집계 스크립트 | +0.33% |
| P1 | 3-8 Post-Mortem | T0 | T4 | PM 템플릿 + G16 훅 | **+0.90%** ← 가중치 30% |
| P1 | 2-6 Attribution | T0 | T4 | handoff 파싱 + 귀속 로깅 | +0.42% |
| P1 | 5-5 Active Control | T0 | T4 | active_control 로직 구현 | +0.35% |
| P2 | 3-3 Change Mgmt | T2 | T3 | git log PS 스크립트 자동화 | +0.45% |
| P2 | 3-7 Behavioral | T2 | T3 | Runtime 로그 파싱 추가 | +0.45% |
| P2 | 2-5 Transparency | T1 | T3 | 로그 스캔 + §M-2 체크 추가 | +0.17% |

**P0+P1 완료 시 예상: ~72%** / **P0~P2 완료: ~75%** / **전체 T0 해소: ~90%**

---

## 6. 결함 해결 현황

| ID | 심각도 | 설명 | 상태 |
|:---|:------:|:-----|:----:|
| D01 | CRITICAL | POSIX 명령 오염 | ✅ 전 항목 PS 대체 |
| D02 | CRITICAL | Token ROI 주관적 분자 | ✅ FINALIZED+PR 카운트로 대체 |
| D03 | CRITICAL | 3-2/3-7 중복 측정 | ✅ 정적/런타임으로 분리 |
| D04 | MAJOR | P:\ 하드코딩 | ✅ 상대경로/.\.sys로 대체 |
| D05 | MAJOR | G13/G15 Level C 누락 | ✅ 3-5, 3-2 추가 |
| D06 | MAJOR | B/C 오분류 (3-3, 4-3, 2-5) | ✅ C형 재분류 |
| D07 | MAJOR | P0/P1 주관적 집계 | ✅ ESCALATE+3-Strike로 대체 |
| D08 | MAJOR | 예측 정확도 100% 불가 | ✅ 0-miss 기준으로 대체 |
| D09 | MINOR | --dry-run 미존재 | ✅ 파일 메타데이터 대체 명시 |
| D10 | MINOR | T1-T17 지표 없음 | ✅ T3/T17 Balance Metric 추가 |
| D11 | MINOR | 균등 가중치 부적합 | ✅ Cat3=30% 조정 |
| A01 | — | Score cap 미표기 | ✅ 0-1 상한 수식 명시 |
| A02 | — | 2-2 측정 약함 | ✅ 실제 다중 노드 참여 카운트 |
| A03 | — | G11 Level C 없음 | ✅ 3-7 항목 추가 |

---

## 7. 측정 명령 Quick Reference (ZeroBase PS)

```powershell
# Policy Gate (Axis-J)
cmd /c ".\_sys\checks\check-policy.bat"

# Context Health (Axis-H)
cmd /c ".\_sys\checks\check-health.bat"

# Hub 상태
cmd /c ".\_sys\cli\msg.bat" hub status

# handoff.md 크기
(Get-Item ".ai\sessions\room-7fb9\handoff.md").Length / 1KB

# config.json 유효성 (13 파라미터 확인)
python -c "import json; d=json.load(open('./_sys/gemini/config.json')); print(len([k for k in d if not k.startswith('_')]), 'params')"

# Commit 형식 준수율 (PS native)
@(git log --oneline -20 | Select-String -Pattern "^[0-9a-f]+ (feat|fix|docs|refactor|test|chore):").Count / 20 * 100

# ctx-save 체크포인트 수
@(git log --grep="ctx-save" --oneline).Count

# PS 실행정책
Get-ExecutionPolicy

# PM 파일 현황
@(Get-ChildItem ".ai\postmortems\*.md" -ErrorAction SilentlyContinue).Count

# Root Score 계산 (미구현 — P2: calc_completion.py)
# python .\_sys\checks\calc_completion.py
```

---

## 8. 지표 거버넌스

- **수정 시**: TAXONOMY.md와 동일하게 R:10 합의 필요
- **TAXONOMY.md 항목 변경 시**: 이 파일의 대응 행 동기화 필수
- **스냅샷(섹션 5)**: 주요 구현 완료 시 또는 분기별 갱신
- **T0 항목**: 자동화 최우선 대상
- **ZeroBase 규칙**: 신규 측정 명령은 반드시 PS native 또는 `.\_sys\` 스크립트만 사용
