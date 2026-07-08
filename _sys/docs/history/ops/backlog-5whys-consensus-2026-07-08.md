# Backlog 5-Whys 끝장토론 (2026-07-08)

> Non-binding peer_ask (collab_rate override=0, pre-consensus fact-gathering). Source backlog: `[[backlog_reorg_2026_07_04]]` memory (2026-07-05 snapshot). Peers: ag.deepthink, cx.deepthink. Terminal: cc (thin router, no code changes).

## 검증된 정정 사항 (memory 스냅샷 vs 실제 repo)

- **A. B6 broker-drain arbiter wiring — 이미 완료됨.** ag는 "여전히 미완료, 최우선"이라 판단했으나, cx가 지적하고 `git show b76c44b -- _sys/core/hub.py` 로 직접 검증한 결과 `action_broker_drain()`이 `_maybe_run_arbiter_on_finalize()`를 이미 호출함 (commit `b76c44b`, 2026-07-05, 이번 세션 push 이전에 이미 반영). **ag의 top-1 추천은 stale — 채택하지 않음.**
- **D1 문서 재구성** — `29f32e3` (MECE doc reconciliation)로 해소. 대규모 50→5 rewrite는 불필요.
- **F/G1 DIR-004** — 이미 실무 적용 중이며 사실상 ratified. 백로그에서 제거.

## 항목별 판정 (Drop / Merge / Promote / Keep)

| ID | 항목 | 판정 | 근거 |
|---|---|---|---|
| A | B6 broker-drain arbiter wiring | **DROP (완료 확인)** | `b76c44b`에서 구현됨 (검증 완료) |
| B | B7 enforcement-behavior probe | **KEEP (정의만)** | 크로스-CLI 머신리더블 sandbox self-report 필드 부재, 근본 조건 미충족. 공격성 프로빙 금지 |
| C | cli-reality-observed.json 갱신 | **PROMOTE (자동화)** | 수동/토큰소모/까먹기 쉬움 → opt-in 스케줄 체크 + fingerprint 캐시 + budget cap으로 전환 |
| D1 | 문서 재구성 | **DROP** | `29f32e3`로 해소 |
| D2 | INV-26 fail-closed | **KEEP (blocked)** | zero-false-positive WOULD-BLOCK soak 증거 필요 |
| D3 | ag V5 Phase 3 리팩터 | **DROP/REPLACE** | 원인(quota 경합)은 context_affinity 스티어링으로 완화됨. `shared_quota_reserve` 게이팅된 좁은 범위 ag 듀얼-패밀리 활성화로 대체 검토 |
| D4 | diag inc-4 failover engine | **KEEP (low)** | 최근 diag 작업(telemetry/watch/freshness)으로 우선순위 낮음 |
| D5 | B1 per-profile health | **PROMOTE** | ag.opus/ag.gptoss 프로필별 eligibility에 필요 — 구조적 의존성 있음 |
| D6 | 5-Whys 잔여 세트 | **SPLIT** | cost/shared-quota tracking 승격, log rotation 유지, hub decomposition Ph2/Linux-Mac/adapter guide 계속 defer |
| D7 | r-9bc7 WS2 제안 | **KEEP+review** | owner/status 불명확, 리프레시 필요 |
| P1 | phantom config 잔여 | **PROMOTE** | drift 감소 |
| P2 | gc/gemini 잔재 제거 | **KEEP (high-risk)** | hub.py 얽힘 — "시한폭탄"이지만 좁은 조율된 제거 필요, 스윕 금지 |
| P3 | `_legacy` 테스트 트리아지 | **PARTIALLY DONE** | `b76c44b`에서 legacy 테스트 다수 이미 제거됨 — 잔여분만 재트리아지 |
| P4 | 거버넌스 문서 정합성 | **MERGE → C+F와 통합** | "Drift & Document Currency" 에픽으로 묶어 `81d3f18` CHK-CONST 가드 활용 |
| P5 | `_archive` 정리 (68M) | **KEEP (blocked)** | 보존정책 합의 먼저 |
| G1 | DIR-004 ratification | **DROP** | 이미 실무 적용/사실상 ratified |
| G2 | PRO-19 문서화 | **KEEP (low urgency)** | 여전히 유효하나 급하지 않음 |
| G(gotcha) | 빈-보터 정체 라운드 2건 | **DROP (수동 스윕 후)** | `consensus-sweep` 한 번으로 제거 가능한 1회성 잔재 |

## 구조적 개선 제안 (양쪽 peer 공통 결론)

**메모리 기반 SSOT 자체가 staleness의 근본 원인이다.** 점-시점 스냅샷(`backlog_reorg_*.md`)은 커밋이 쌓일수록 반드시 드리프트하며, 이번 토론에서만 A/D1/G1 세 항목이 이미 stale로 확인됨.

제안 (양쪽 peer 공통):
1. **Repo-tracked living backlog**로 SSOT 이전: `_sys/docs-v2/ops/BACKLOG.md` 또는 `_sys/ai/backlog.json` (필드: id, status, owner, blocker, evidence_commit, supersedes, next_action). 메모리는 요약만 하고 진실의 소유자가 되지 않음.
2. 코드 근접 `# TODO(ID):` 주석 — P2(hub.py 얽힘), A류 항목처럼 코드에 직접 박아두면 코드가 바뀌는 순간 같이 갱신됨.
3. `check_cli_reality.py` 류의 경량 검증 패스에 "백로그 항목이 최근 커밋으로 해소됐는지" 플래그하는 훅 고려.

## Claude Judgment

- **Adopt**: A/D1/G1 즉시 DROP (검증 완료). C/D5/P1/P4 승격. 구조적 개선안(repo-tracked backlog) 채택 — 다음 액션으로 실행 권장.
- **Refine**: P3은 "미착수"가 아니라 "부분 완료" (레거시 테스트 다수 이미 제거됨) — E 카테고리 판정 수정.
- **Counter**: ag의 top-1 우선순위(A: broker-drain wiring)는 기각 — 실제로는 이미 구현됨. cx의 검증 주도 접근이 이번 라운드에서 더 신뢰할 만했음.
- **Next**: **Top priority = D5 (per-profile health) + P2 안전한 gc/gemini 제거 계획 수립.** 백로그 SSOT를 repo-tracked 파일로 이전하는 것을 이번 정리의 첫 실행 항목으로 제안. 사용자 승인 시 실행.

## Peer 원문 (요약 보존)

<details><summary>cx.deepthink 응답 (elapsed=52s)</summary>

verified against git log (a25b34a/81d3f18/fd40da3/29f32e3/b76c44b landed). A→DROP(implemented), B→keep/define-only, C→promote automation, D1→merge into P4, D2→keep blocked, D3→drop/replace with shared_quota_reserve-gated narrow activation, D4→keep low, D5→promote, D6→split, D7→keep+review, E→promote P1/P3/P4 defer P2/P5, F→promote, G→drop after sweep. Structural: move SSOT to repo-tracked `_sys/docs-v2/ops/backlog.md` or `_sys/ai/backlog.json`. Top priority: per-profile health + shared quota reserve enforcement.

</details>

<details><summary>ag.deepthink 응답 (elapsed=58s) — A 항목 판정은 stale, 참고용으로만 보존</summary>

5-Whys per item A-G; dropped F(G1)/D1/D3; merged C+F(G2)+E(P4) into "Drift & Document Currency" epic; promoted A/E(P2)/G as next priorities; structural recommendation = code-proximity TODOs + single BACKLOG.md + hysteresis validation hook. Top-1 (A: broker-drain arbiter wiring) — **superseded by cx's verified finding that this already shipped in b76c44b; not adopted.**

</details>
