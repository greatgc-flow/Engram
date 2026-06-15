# DEBATE_LOG — Consensus Decision History

> append-only — do not edit existing entries
> Format per DEBATE_PROTOCOL §7

---

## [2026-06-14] T2-debate-system-audit-phase2-implementation

- Proposal: T2-끝장토론 Phase 2 (cc solo + cx async audit, gc quota exhausted)
- Participants: cc (implementer), cx (T2 auditor — 6 topic exhaustive review)
- Decision: IMPLEMENTED — All HIGH/MEDIUM cx findings from T2 audit applied

### cx T2 Audit Findings → Actions

| Topic | cx Severity | cc Action |
|-------|-------------|-----------|
| Q1 Lease/Zombie gap | HIGH | Zombie guard: `_MAX_SILENT_HEARTBEATS=60`, force-kill after 30 min silence |
| Q2 Min-token health | MEDIUM | Codified in `protocol-health.md §9b` — no model-ping; piggyback on ask outcomes |
| Q3 Feedback propagation | HIGH | `runtime-directives.jsonl` system: auto-promote after 2 failures; auto-clear on first_success |
| Q4a cx session resume | HIGH | Session fingerprint: hash(exe+flags); auto-retire on drift before resume |
| Q4b vote typos | HIGH | Already fixed in Phase 1; regression tests added |
| Q4c blat files | MEDIUM | Popen cwd fix (ai_root.parent); attribution deferred to recurrence |
| Q4d tests vs behavior | LOW | Tests updated in Phase 1 |
| Q5 MECE enforcement | HIGH | `protocol-permissions.md` (canonical model); parity validator exists (`profile-validate`) |
| Q6 NEVER boundaries | HIGH | `protocol-permissions.md §4` MUST-NEVER list; docs-only items promoted to docs |

### Key Architectural Decisions

- **Two-layer directive model**: `user-directives.md` (human-confirmed, never auto-written) + `runtime-directives.jsonl` (machine-generated, TTL-based, auto-cleared)
- **Cross-peer propagation**: A gc failure creates a directive injected into ALL peer asks — prevents same-peer routing while degraded
- **Session fingerprint invalidation**: Prevents silent session resume failures after flag changes (was causing cx exit=2 errors)
- **Protocol MECE**: 3 stale docs archived; 2 new canonical docs added (protocol-permissions.md, protocol-directives.md)

- Risk Class: HIGH_RISK (hub.py core modified, session reuse path changed)
- Promoted To Constitutional Layer: NO
- gc T2 participation: DEFERRED (quota reset needed; will run separately)

- Affected Artifacts:
  - P:\_sys\core\hub.py (directive system, session fingerprint, zombie guard, cwd fix)
  - P:\_sys\ai\runtime-directives.jsonl (NEW — auto-generated peer runtime rules)
  - P:\_sys\docs\protocol-permissions.md (NEW — minimum permission model)
  - P:\_sys\docs\protocol-directives.md (NEW — directive management spec)
  - P:\_sys\docs\protocol-health.md (§9b min-token health, §10 lease/heartbeat)
  - P:\PROTOCOL.md (new docs registered)
  - Garbage: 3 stale collaboration docs archived

---

## [2026-06-14] knowledge-propagation-design

- Proposal: knowledge-propagation-design-20260614 (cc+cx, §16 exhaustive planning session)
- Participants: cc (coordinator), cx (peer review — READY_FOR_SPEC)
- Decision: Design specification complete — 구현 대기 (사용자 결정 4개 확인 후 착수)
- Key decisions:
  - 3-Layer 구조: Raw Events → Active Lesson Registry → Compiled Delivery Packs
  - Feedback ≠ Lesson ≠ Directive: user-directives.md(Tier 1.5)는 절대 오염 금지
  - Hash-ACK: 동일 세션 내 재전송 시 hash만 전송 (토큰 제로 달성)
  - Config-driven: knowledge.config.json이 모든 임계값·경로·승인규칙 소유
  - Global/Workspace 2-레이어 분리; workspace-profile.json이 General-Specific 연결점
  - Base Template: 신규 워크스페이스 자동 시작 지원
  - 초기 lesson 7개 정의 (LL-001~007)
  - 구현 10단계 정의 (Phase 1: hub.py 주입까지, Phase 2: 자동 감지기)
  - 문서 전략: DEBATE_PROTOCOL.md §0/§8 확장; user-directives.md 비확장
- Risk Class: NORMAL (설계 문서만, 구현 미착수)
- Promoted To Constitutional Layer: NO
- Affected Artifacts:
  - P:\_sys\docs\knowledge-propagation-spec.md (신규 — 전체 설계 스펙)
  - P:\_sys\docs\DEBATE_LOG.md (this file)

---

## [2026-06-14] debate-protocol-peer-reinclude-review

- Proposal: peer-reinclude-review-20260614 (cc+cx, §16 exhaustive work session)
- Participants: cc (coordinator), cx (peer review — 0 HIGH immediately applicable; 3 DEFER)
- Decision: DEFER_TO_T2 — Peer re-inclusion and solo-operation prohibition require T-2 amendment
- Key decisions:
  - Peer re-inclusion (ABSENT→REINCLUDED lifecycle) → DEFER D-1: affects quorum/consensus validity
  - Solo coordinator prohibition (explicit no-quorum hold) → DEFER D-2: affects abort behavior
  - v0.10 constitutional provenance → DEFER D-3: §13-1/§16-2 vs v0.10 applied-via-§16 retroactive conflict
  - §15 DEFERRED table updated with D-1/D-2/D-3 entries + prior deferred items
  - handoff.md PENDING_ISSUES updated with T-2 task entries and cx candidate text reference
  - ROI gate met: 0 HIGH (§16-applicable), 0 LOW — EXHAUSTIVE_COMPLETE declared
- Risk Class: NORMAL (no immediate implementation; deferred to T-2)
- Promoted To Constitutional Layer: NO (deferred)
- Affected Artifacts:
  - P:\_sys\docs\DEBATE_PROTOCOL.md (§15 DEFERRED table updated)
  - P:\_sys\docs\DEBATE_LOG.md (this file)
  - P:\.ai\sessions\room-fe18\handoff.md (PENDING_ISSUES updated)

---

## [2026-06-14] debate-protocol-exhaustive-review-v0.10

- Proposal: exhaustive-review-v0.10-20260614 (cc+cx, §16 work session — HIGH findings implementation)
- Participants: cc (coordinator), cx (peer review — 5 HIGH findings applied)
- Decision: DEBATE_PROTOCOL v0.9 → v0.10 (HIGH findings from prior cx exhaustive review applied)
- Key decisions:
  - §12 NEW Tier 1.5: User Directives now formally listed between Tier 1 and Tier 2 with conflict rules
  - §13-1 NEW: Expedited amendment clause for §16 sessions; Tier 1 findings still require T-2
  - §14-5 NEW: CRITICAL severity defined (above HIGH) — invalidates goal frame → ABORT(A-3) + new T-2
  - §16-2 UPDATED: Constitutional constraint added — Tier 1 HIGH findings from §16 → DEFER to T-2
  - §16/§17 REORDERED: §16 (Exhaustive Work Session) now physically precedes §17 (User Directives)
  - §17 FIXED: Tier precedence text corrected — references §12; "above Tier 2 for operational matters"
  - Appendix D NEW: Closure Manifest template section added (required before VERIFY_PASS)
- Risk Class: HIGH_RISK (constitutional tier model modified; §14 severity schema changed)
- Promoted To Constitutional Layer: YES (DEBATE_PROTOCOL.md itself is Tier 1)
- Affected Artifacts:
  - P:\_sys\docs\DEBATE_PROTOCOL.md (updated to v0.10)
  - P:\_sys\docs\DEBATE_LOG.md (this file)

---

## [2026-06-14] debate-protocol-exhaustive-review-v0.9-amendment

- Proposal: exhaustive-review-amendment-20260614 (cc+cx, §16 work session)
- Participants: cc (coordinator), cx (peer review — GAPS_FOUND 4 HIGH, 3 LOW)
- Decision: DEBATE_PROTOCOL v0.9 amended (pending T-2 for v0.10 formal version bump)
- Key decisions:
  - §17 NEW: User Directives — first-class artifact, Tier 1.5, hub.py auto-injection (every peer ask)
  - hub.py: `_build_ask_query_with_context` now injects `_sys/ai/user-directives.md` as `[USER DIRECTIVES]` block
  - `_sys/ai/user-directives.md`: created with DIR-001 (ROI termination) and DIR-002 (full permissions)
  - §8 feedback loop diagram: §17 injection path added, NEXT CYCLE carry-forward documented
  - §14 scope boundary vs §16 explicitly stated
  - §16-3 termination authority: "active coordinator" (not cc-specific)
  - §16-4 finding ledger rules added
  - cx DEFER findings: §6/§14-5 R:10 voter unification (needs T-2) + §8 sinks-as-inputs (needs T-2)
- Risk Class: HIGH_RISK (hub.py core context injection modified)
- Promoted To Constitutional Layer: YES (§17 is Tier 1 addition)
- Affected Artifacts:
  - P:\_sys\docs\DEBATE_PROTOCOL.md (v0.9 amended)
  - P:\_sys\docs\DEBATE_LOG.md (this file)
  - P:\_sys\core\hub.py (_build_ask_query_with_context)
  - P:\_sys\ai\user-directives.md (new)

---

## [2026-06-14] debate-protocol-exhaustive-review-v0.9

- Proposal: exhaustive-review-20260614
- Participants: cc (단독 끝장검토 — gc ABSENT quota, ROI 기준 cx 호출 불필요)
- Lenses: MECE, 선순환 피드백 루프, 5 Whys, 다른 관점, 자원 효율
- Decision: DEBATE_PROTOCOL v0.9 채택
- Key decisions:
  - §16 신규: Exhaustive Work Session Governance (끝장 작업) — ROI 종료 게이트, 5개 표준 렌즈, 2026-06-14 standing rule
  - §4-2: 전체 권한 부여 (cc/cx/gc) 공식화; §14 교차검토에 `--session-policy fresh` 필수
  - §1: Debate Tier (FULL/ABBREVIATED) — T-5 경량 토론 경로
  - §3: 전문성 라우팅 (cx→기술/제약, gc→리서치, cc→구조/정책); 2-5↔6 범위 경계 명확화
  - §15: DEFERRED 항목 상태 업데이트 (resolved 2개 표시)
  - Anti-patterns #20, #21 추가
  - Appendix A Step 6-B: --session-policy fresh 추가
  - 5 Whys 근본 원인: "끝장작업 거버넌스 섹션 부재" → §16으로 해소
- Risk Class: NORMAL
- Promoted To Constitutional Layer: YES (DEBATE_PROTOCOL.md itself is Tier 1)
- Affected Artifacts:
  - P:\_sys\docs\DEBATE_PROTOCOL.md (updated to v0.9)
  - P:\_sys\docs\DEBATE_LOG.md (this file)

---

## [2026-06-13] peer-full-permissions

- Proposal: peer-full-permissions-20260613
- Participants: cc (단독 — 사용자 명시적 권한 위임, T-0)
- Decision: 모든 피어에 최대 자율 권한 부여 (사용자 명시 지시)
- Key decisions:
  - gc (`--approval-mode yolo --skip-trust`): 이미 YOLO 모드 적용 중 → 변경 없음
  - cc: `--dangerously-skip-permissions` 추가 (cc-deep 포함)
  - cx: `--dangerously-bypass-approvals-and-sandbox` 추가 (orchestration.json + hub.py `_build_session_cmd`)
  - 배경: hub.py가 `-p`/stdin 비대화형으로 피어를 호출하므로 승인 프롬프트가 없으면 작업이 묵시적 실패; 사용자가 포터블 샌드박스 환경에서 전권 위임을 명시적으로 요청
- Risk Class: ACCEPTED (사용자 명시 승인)
- Affected Artifacts:
  - P:\_sys\ai\orchestration.json (cc, cc-deep, cx invoke_args)
  - P:\_sys\core\hub.py (`_build_session_cmd` cx 플래그)
  - P:\_sys\tests\unit\test_hub_session.py (cx arg 기대값 업데이트)
  - P:\_sys\docs\protocol-codex.md (v4.2)
  - P:\_sys\docs\protocol-session.md (v4.2 §6 추가)

---

## [2026-06-13] hub-session-reuse-T2

- Proposal: hub-session-reuse-20260613
- Participants: cc, cx (gc ABSENT — quota exhaustion)
- Rounds: 2 (T-2 구조적 결정 토론)
- Decision: CONSENSUS_OK — hub.py 피어 세션 재사용 메커니즘 구현
- Key decisions:
  - `session_state.json` per-peer 파일 (`_sys/{peer}/session_state.json`) — active/history 구조
  - scope_key = explicit_scope > room_id > "default"
  - cx: `thread.started` JSONL 이벤트에서 `thread_id` 추출 후 `codex exec resume <id>`
  - gc: `--session-id <uuid>` 신규 / `--resume <uuid>` 재개
  - resume 실패 시 기존 세션 retire → fresh 1회 retry → 새 thread_id 저장
  - `new-topic` / `clear-room` 시 전 피어 세션 일괄 retire
  - `--session-policy auto|reuse|fresh|none` CLI 플래그 추가
  - 교차검토(§4 독립성) 시 `session_policy="fresh"` 사용
- Risk Class: NORMAL
- Promoted To Constitutional Layer: NO
- Affected Artifacts:
  - P:\_sys\core\hub.py (세션 관리 함수 9개 + action_ask 수정 + argparse)
  - P:\_sys\ai\orchestration.json (`session_mode: reuse` cx/gc 노드)
  - P:\.gitignore (`_sys/*/session_state.json` 추가)
  - P:\_sys\tests\unit\test_hub_session.py (신규, 22 tests 전부 통과)
- Full Log: (세션 내 토론, 아카이브 없음)

---

## [2026-06-13] debate-protocol-structural-closure-v0.8

- Proposal: protocol-structural-closure-20260613-v1
- Participants: cc, gc, cx
- Rounds: 4 (Exhaustive Cross-Review Debate on MECE and Closed Loop)
- Decision: DEBATE_PROTOCOL v0.8 adopted — §8 Closure Manifest added, §14-5 R:10 Voting Override added.
- Rationale: A 5-turn exhaustive cross-review was initiated to test the entire protocol ecosystem for Recursive MECE properties and a Closed Virtuous Feedback Loop. The review revealed that feedback items could be lost before `VERIFY_PASS`, and that operational `active_peers` could improperly dilute `protocol.json.consensus.r10_voters` quorum. The adopted changes mechanically close the feedback loop (Closure Manifest) and rigorously separate operational and constitutional voter boundaries (R:10 Voting Override).
- Risk Class: HIGH_RISK
- Promoted To Constitutional Layer: YES (DEBATE_PROTOCOL.md itself is Tier 1)
- Affected Artifacts:
  - P:\_sys\docs\DEBATE_PROTOCOL.md (updated to v0.8)
  - P:\_sys\docs\DEBATE_LOG.md (this file)
- Full Log: (Ephemeral session log for MECE & Feedback Loop review)

---

## [2026-06-13] debate-protocol-amendment-crossreview-v0.7 (CORRECTION: actual final = v14)

- Proposal: crossreview-amendment-20260613-v14 (final; prior entry incorrectly cited v13)
- Participants: cc, gc (ABSENT Round 14 — TerminalQuotaError), cx
- Rounds: 14 (v7 → v14; gc ABSENT Round 14, N-1 quorum satisfied by cc+cx)
- Decision: DEBATE_PROTOCOL v0.7 adopted — §14-5 Finding Handling fully expanded.
  - v14 change 42 (final): empty-pool H-2 option(ii) — all non-ABSENT active peers (including
    challenger) must accept as Accepted Risk after LOW classification; scope-narrowing creates
    revised ledger entry requiring fresh assent; returning ABSENT peer must accept within one
    cross-review round.
- §14 Cross-Review: Round 1 (v14 lineage) — cx found CRv14-A/B (HIGH).
  H-2 directed closure: CRv14-A and CRv14-B reclassified to LOW and accepted as Accepted Risk.
  §14 COMPLETE.
- Accepted Risks (all lineages, final): CRv14-A, CRv14-B, CRv13-B, CRv13-C, CRv10-B~H, CRv9-D/E,
  CR-10, CR-21~28.
- Risk Class: NORMAL
- Promoted To Constitutional Layer: YES (DEBATE_PROTOCOL.md itself is Tier 1)
- Affected Artifacts:
  - P:\_sys\docs\DEBATE_PROTOCOL.md (updated to v0.7; §14-5 path(a)/(b) complete)
  - P:\_sys\docs\DEBATE_LOG.md (this file)
- Full Log: P:\.ai\debate\crossreview-amendment-round14.md

---

## [2026-06-13] debate-protocol-definition (SUPERSEDED by v0.4 below)

---

## [2026-06-13] debate-protocol-definition-v0.4

- Proposal: debate-protocol-20260613-v0.4
- Participants: cc, gc, cx
- Rounds: 4 (+ cross-review SEE/VERIFY phase)
- Decision: DEBATE_PROTOCOL v0.4 adopted as the standard multi-peer thorough debate protocol
- Rationale: 3-round design phase + SEE/VERIFY cross-review (gc reviewed cx, cx reviewed gc); cross-review found 8 gaps (VERIFY_FAIL); v0.4 patch addressed all gaps; Round 4 unanimous consensus
- Key decisions: Constitutional tier model (§12); no majority fallback (§5 H-2); context bounding (§4-5); canonical proposal must be full text (§9); H-4 risk gate; Ledger-based tracking (§10); Amendment rule (§13)
- Risk Class: NORMAL
- Promoted To Constitutional Layer: YES (DEBATE_PROTOCOL.md itself is Tier 1)
- Affected Artifacts:
  - P:\_sys\docs\DEBATE_PROTOCOL.md (canonical — always current)
  - P:\.ai\debate\debate-protocol-v0.4.md (source)
  - P:\_sys\docs\DEBATE_LOG.md (this file)
  - handoff.md [PROMOTED_RULES] PR-001 updated
- Full Log: P:\.ai\debate\debate-protocol-full.md

---

## [2026-06-13] debate-protocol-amendment-crossreview

- Proposal: crossreview-amendment-20260613-v3
- Participants: cc, gc, cx
- Rounds: 3 (amendment debate)
- Decision: DEBATE_PROTOCOL v0.6 adopted — §14 Exhaustive Cross-Review Phase (끝장 교차검토) added
- Rationale: Protocol lacked a formal adversarial cross-review loop post-CONSENSUS_OK. Amendment adds §14 with peer self-summaries (coordinator-bias prevention), exhaustive MISSED_BY/WRONG_BY/PREMATURE_CONSENSUS format, CLEAN termination requiring ALL fields NONE, severity classification with 3-peer vote (fail-safe HIGH), LOW finding Accepted Risk path (no extra CLEAN round), and loop limit (debate rounds × 3 → H-2). Round 1→2 iterated on coordinator-bias, severity challenge voting edge cases, MISSED_BY_ALL naming; Round 2→3 fixed vote outcome exhaustiveness (1H/2L → HIGH fail-safe) and Appendix A Step 6-B LOW exception.
- Risk Class: NORMAL
- Promoted To Constitutional Layer: YES (DEBATE_PROTOCOL.md itself is Tier 1)
- Affected Artifacts:
  - P:\_sys\docs\DEBATE_PROTOCOL.md (updated to v0.6)
  - P:\.ai\debate\crossreview-amendment-round1.md (source)
  - P:\.ai\debate\crossreview-amendment-round2.md (source)
  - P:\.ai\debate\crossreview-amendment-round3.md (source)
  - P:\_sys\docs\DEBATE_LOG.md (this file)
- Full Log: P:\.ai\debate\crossreview-amendment-round3.md

---

## [2026-06-13] debate-protocol-v0.5-examples

- Proposal: debate-protocol-20260613-v0.5
- Participants: cc, gc, cx
- Rounds: 5 (examples review + approval)
- Decision: DEBATE_PROTOCOL v0.5 finalized — implementation-ready with full examples and quick reference
- Rationale: SEE/VERIFY cross-review (v0.4) found base protocol gaps; v0.5 adds Appendix A-D (Quick Start, 12 filled examples including failure paths, 16 anti-patterns, full debate template) + base fixes (§3 NODE_DONE format, §8 VERIFY_PASS/FAIL definitions, §3→§9 transition rule)
- Risk Class: NORMAL
- Promoted To Constitutional Layer: YES (supersedes v0.4 as canonical DEBATE_PROTOCOL.md)
- Affected Artifacts:
  - P:\_sys\docs\DEBATE_PROTOCOL.md (updated to v0.5)
  - P:\.ai\debate\debate-protocol-v0.5.md (source)
- Known issues deferred: encoding/mojibake remediation (v0.6); ledger compaction strategy (v0.6)
- Full Log: P:\.ai\debate\debate-protocol-full.md


---

## [2026-06-15] sys-restructure-plan-R4-root-swap-ipc-glue

- Proposal: sys-restructure-R4-20260615 (cc solo, 사용자 Round-4 지시 — 디스크 충분 확인)
- Participants: cc (coordinator + 사용자 확인 반영), gc (Round-4 VIABLE & SUPERIOR 결정 반영)
- Decision: ROOT SWAP ADOPTED + IPC 구조 설계 + 글루파일 slim화 설계 → sys-restructure-plan.md R4 업데이트 완료

### R4 주요 아키텍처 결정 (LOCKED)

1. **Root Swap ADOPTED (디스크 충분 확인):**
   - Round-3 기각 이유 2(디스크) 소멸 → Round-3 이유 1(git 이력)은 Junction Stub으로 해결
   - Junction Stub: `mklink /J _sys_new\env _sys\env` (물리복사 없음, git 미추적)
   - 3단계: Build Phase(_sys_new/ 구축) → Validate(verify-all pre-cutover) → Cut-over(rename backup)

2. **IPC 구조 per-peer 분리:**
   - As-Is: `_sys/gemini/{peer}-*.txt` 혼재 → To-Be: `peers/{id}/ipc/inbox/` 전용
   - infra.json `ipc_paths` 섹션으로 hub.py 경로 동적 해석
   - archive_on_capture: inbox → history 자동 이동; .gitignore `_sys/peers/*/ipc/` 전체 무시

3. **글루파일 slim 설계:**
   - canonical: `protocol/peer-specific/{id}/{PEER}.md` (사람이 편집)
   - stub: `peers/{id}/runtime/config/{PEER}.md` (hub.py sync-glue 자동 생성)
   - peer.json: glue_file + glue_source 양쪽 등록; verify-all V13 sync 확인

4. **verify-all V11~V15 추가 (gc R4):**
   - V11: Registry-Dir 패리티
   - V12: 절대경로 퍼지 체크
   - V13: 엔트리포인트 + glue sync
   - V14: .gitignore IPC 커버리지
   - V15: Junction 실재 확인 (Gate 2 전용)

- Risk Class: HIGH_RISK (마이그레이션 전략 재결정, Phase 절차 재설계)
- Promoted To Constitutional Layer: NO (구현 계획 문서)
- Affected Artifacts:
  - P:\_sys\docs\sys-restructure-plan.md (DEBATE_FINAL_R4 — 마이그레이션 전략 + IPC + 글루파일 + V11~V15)
  - P:\_sys\docs\DEBATE_LOG.md (this file)

---

## [2026-06-15] sys-restructure-plan-exhaustive-cross-review

- Proposal: sys-restructure-끝장교차검토-20260615 (cc+gc+cx R:10, 5-Lens Debate)
- Participants: cc (coordinator + self-review), gc (5-lens exhaustive), cx (independent audit)
- Decision: DEBATE_FINAL — 총 CRITICAL×3/HIGH×8/MEDIUM×7/LOW×3 발견, 전부 sys-restructure-plan.md에 반영 완료
- Review Target: P:\_sys\docs\sys-restructure-plan.md (v1.0 → DEBATE_FINAL)

### Lens 1 — MECE
- peer.json vs config/ 단일진실소스 충돌 [HIGH/gc] → 경계 재정의: config/=전역, peers/=피어로컬
- USER_MANUAL.md/TAXONOMY_v11.md protocol/ 오염 [MEDIUM/gc+cx] → protocol/reference/ 분리
- knowledge/config.json 명칭 충돌 [MEDIUM/cx] → index.json + knowledge-policy.json 분리
- 섹션번호 3-7·3-8 중복 / 파일매핑 불일치 [LOW/cc] → 수정 완료

### Lens 2 — 선순환 피드백 루프
- traceability.json 수동유지 drift [HIGH/gc+cx] → manage.py gen-traceability 자동생성
- Phase 1+2 사이 broken-state 복구 루프 없음 [HIGH/gc+cx] → rollback-phase1.ps1 Phase 0 생성 의무
- infra.json 로드실패 → hub.py bootstrap 루프 파손 [MEDIUM/cx] → __file__ hardcode fallback

### Lens 3 — 5 Whys
- Junction 파손 근본원인: 프로세스 잠금 없음 → fresh-session + 프리플라이트 process check
- pytest Phase간 실패 근본원인: atomic 변경 분리 커밋 → Phase 1+2 단일 원자 커밋 (CRITICAL)
- status.json 참조 누락 근본원인: 감사 범위 미달 → ALL 파일타입 grep
- registry↔peer.json drift 근본원인: 스키마 강제 없음 → _ref 필수 + hub.py validation

### Lens 4 — 다른 관점
- 피어 dir 이동 생략: REJECT (clean root = 핵심 이득)
- status.json write-through cache: ADOPT (31+개 참조 blast radius 최소화)
- 7→4 Phase: REFINE (Phase 1+2 통합; 나머지 5개 안전 게이트 유지)

### Lens 5 — 자원 효율
- traceability.json 수동유지: auto-gen 대체
- Phase 1+2 분리 커밋: 단일 커밋으로
- cli-resolve.json: 필요성 확인 유지

### 핵심 아키텍처 결정 (LOCKED)
1. Phase 1+2 원자적 통합: 파일이동 + hub.py 경로업데이트 = 단일커밋 (MUST-NOT: 분리)
2. status.json write-through cache: hub.py dual-write → 점진적 제거
3. rollback-phase1.ps1: Phase 0 생성 의무 (filesystem backup 포함)
4. traceability.json auto-gen: manage.py gen-traceability 명령으로 대체
5. config/ 경계: 시스템전역 / peers/{id}/ = 피어-로컬 (MECE 성립)

- Risk Class: HIGH_RISK (CRITICAL×3 발견 — Phase 실행 전 모두 해소 필수)
- Promoted To Constitutional Layer: NO (구현 계획 문서)
- Affected Artifacts:
  - P:\_sys\docs\sys-restructure-plan.md (DESIGN_FINAL → DEBATE_FINAL)
  - P:\_sys\docs\DEBATE_LOG.md (this file)

---

## [2026-06-15] sys-restructure-plan-R5-MECE-integration

- Proposal: MECE_Directory_Architecture_Specification_v2.md 전면 통합 — R5 끝장교차검토 (cc+gc+cx, 5-Lens × 7-Criteria)
- Participants: cc (coordinator), gc (5-lens 끝장검토), cx (7-criteria independent audit — ag 비활성화)
- Decision: DEBATE_FINAL_R5 — CRITICAL×4/HIGH×12/MEDIUM×9/LOW×4 발견, 전부 sys-restructure-plan.md R5에 반영

### CRITICAL 발견 → 즉시 해소

| 발견 | 심각도 | 출처 | 해소 |
|------|--------|------|------|
| managed-links.json 미존재 (MECE I-03 위반) | CRITICAL | gc+cx | §3-7e에 spec 추가; §4-4 신규 생성; virtualizer.py 시맨틱 내재화 |
| Ghost Junction — rollback 시 junction 미재등록 | CRITICAL | cc | §3-7e ghost junction 방지; Phase 0 step 5a rollback.ps1 명시; 리스크 CRITICAL 등록 |
| infra.json desired/actual state 혼용 (MECE CVD 위반) | CRITICAL | gc+cx | infra.json → 매크로루트만; path-map.json(desired) + managed-links.json(actual) 3-way 분리 |
| IPC 피드백 루프 미완결 (성공 경로만) | CRITICAL | cx | §3-7f F1~F4 실패 모드 + quarantine/ + max_age_hours 완비 |

### HIGH 발견 → 설계 보완

| 발견 | 출처 | 해소 |
|------|------|------|
| pathmap.lock 없음 (MECE I-04 위반) | gc+cx | §3-7e + §4-4 + Phase 0 step 8b 추가 |
| pathmap-audit.jsonl 없음 (MECE I-05 위반) | gc+cx | §3-7e + §4-4 추가 |
| 글루 sync 피드백 루프 파손 (push-only) | gc+cx | §3-7g T1~T4 트리거 + Read-Only stub + glue_state hash drift |
| virtualizer.py pathmap 시맨틱 미내재화 | gc+cx | §3-7e virtualizer.py 의무 시맨틱 명시 + §5-1 업데이트 |
| hub.py T1 sync-glue 트리거 없음 | cx | §3-7g T1 eager 트리거 + §5-1 업데이트 |
| SHA256 manifest (Copy-Verify-Delete 토큰) 없음 | gc | Phase 0 step 8c manifest 생성 추가 |
| peer.json.ipc vs infra.json ipc_paths 이중 권위 | gc+cx | infra.json ipc_paths 완전 제거 → peer.json.ipc 단일 권위 |
| V4/V8/V15 FAIL 시 repair 경로 없음 | cx | virtualizer.py prune/repair 시맨틱으로 대응 연결 |
| data/inbox/ 없음 (MECE [00_Inbox] 없음) | gc+cx | §3-7e + §4-4 추가 |
| P:\ 하드코딩 portability 위험 | gc | 리스크 MEDIUM 등록 + V12 절대경로 퍼지 강화 + path-map.json AUTO_DETECT |

### MEDIUM/LOW 발견 → 문서화

- Cloud Sync 위험 (MECE N-06) → §3-7e + 리스크 MEDIUM 등록
- session_state.json 분류 애매함 → §11-1 결정 (현재 위치 유지, R6 재검토)
- log 이중 위치 혼용 → §11-2 명확 분류 (raw→data/logs/, curated→knowledge/logs/)
- runtime-directives.jsonl TTL 성격 → §11-3 data/state/로 확정
- 아웃바운드 정션 Physical/Logical 구분 → §11-4 명시
- managed-links.json primary key 드라이브 독립 → §11-5 EXTERNAL 프리픽스 결정
- infra.json vs path-map.json 최종 경계 → §11-6 확정

### 핵심 아키텍처 결정 (LOCKED — R5)

1. **3-way 설정 분리**: `infra.json`(매크로루트) + `path-map.json`(desired state) + `managed-links.json`(actual state) — SSOT 분리 완결
2. **virtualizer.py pathmap 내재화**: preflight→plan→apply(lock+audit)→status→prune — registry 없는 "생성만 하는" 도구 금지
3. **IPC 실패 종단 상태**: quarantine/ + max_age_hours — "성공 경로만" 설계 탈피
4. **글루 드리프트 피드백 루프**: T1(eager)/T2(lazy)/T3(post-restructure)/T4(manual) + Read-Only stub
5. **§11 엣지케이스 섹션**: MECE 분류 불확실 항목은 결정을 여기에 명시 — 분류 미정 방치 금지

- Risk Class: HIGH_RISK (Ghost Junction CRITICAL 새로 발견 — rollback.ps1 배포 전 필수 해소)
- Promoted To Constitutional Layer: NO (구현 계획 문서)
- Affected Artifacts:
  - P:\_sys\docs\sys-restructure-plan.md (DEBATE_FINAL_R4 → DEBATE_FINAL_R5)
  - P:\_sys\docs\DEBATE_LOG.md (this file)

---

## [2026-06-15] sys-restructure-plan-R6-transaction-closure

- Proposal: R5 결과 재귀적 끝장교차검토 R6 — 트랜잭션 완결 + invariant coverage matrix
- Participants: cc (coordinator), cx (7-criteria R6 audit — full response), gc (응답 단절 — cx로 대체)
- Decision: DEBATE_FINAL_R6 — CRITICAL×2/HIGH×8/MEDIUM×5 발견, 전부 sys-restructure-plan.md R6에 반영

### CRITICAL 발견 → 즉시 해소

| 발견 | 해소 |
|------|------|
| apply → junction created → registry write FAIL: 미복구 상태 (MECE I-08 위반) | §3-7e: operation journal (planned→fs_created→registry_committed→audit_committed) + virtualizer.py recover 명령 |
| prune → physical delete → registry write FAIL: managed_orphan_already_absent 상태 미정의 | §3-7e: prune 역복구 로직 명시 + audit entry |

### HIGH 발견 → 설계 보완

| 발견 | 해소 |
|------|------|
| SHA256 manifest step 8c (너무 이름 — build 전) → 토큰 무효화 위험 | Phase 0 step 8c 삭제 → step 11b (Validate PASS 직후)로 이동 |
| pathmap.lock schema 없음 → stale-lock 탐지/복구 불가 | §3-7e: lock schema (pid/host/started_at/command/op_id) + 30분 TTL auto-release |
| Day-1 bootstrap sequence 미정의 | §3-7e: 8단계 bootstrap 시퀀스 추가 |
| path-map.json vs managed-links.json 권위 충돌 규칙 없음 | §3-7e: 권위 행렬 (desired/actual/orphan/missing 4가지 케이스) |
| entry_id 중복 → apply 시 충돌 미처리 | §3-7e: preflight에서 entry_id/link_path/exception_path 중복 → ABORT |
| T2 sync-glue FAIL 시 hub.py 동작 미정의 | §3-7g: --strict(abort) / 기본(known-good hash 비교) 정책 |
| auto-repair vs T1/T2 sync-glue 경계 모호 | §3-7g: auto-repair 예외 조건 3가지 명시 (MUST-NOT 충돌 해소) |
| rollback이 junction 내부 재귀 삭제할 수 있음 | §3-7e prune rollback: reparse-aware delete 명시 |

### MEDIUM 발견 → 문서화

- quarantine/ terminal state → 상태 전이 추가 (§3-7f: quarantine-index.jsonl + 4가지 outbound transition)
- pathmap-audit.jsonl 위치 분류 모호 (state vs log) → §11-2/§11-7에 "stateful journal" 명시
- data/inbox/ 소비자/보존 정책 미정 → §11-1 "human classification buffer only" 명시
- §3-6 virtualizer.py 설명 구식 → pathmap 전체 명령 목록으로 업데이트
- MECE 불변식 coverage matrix 없음 → §11-8 I-01~I-10/N-01~N-08 전체 coverage 표 추가

### verify-all 확장

- V16: Bootstrap 공백 상태 체크 (managed-links.json/lock/journal)
- V17: Audit 무결성 + mutation operation_id 체크

### 핵심 아키텍처 결정 (LOCKED — R6)

1. **Operation Journal**: apply/prune은 4-phase commit (planned→fs_created→registry_committed→audit_committed); crash recovery 의무
2. **SHA256 manifest timing**: Validate PASS 직후만 유효 (step 11b) — build 중 생성 금지
3. **pathmap.lock**: pid+host+started_at 스키마; 30분 TTL stale-lock auto-release
4. **auto-repair 경계**: Read-Only stub 재생성만 허용; junction/registry/quarantine은 항상 explicit confirm
5. **불변식 coverage**: I-01~I-10 모두 이행, N-01~N-08 중 N-02/N-03/N-04/N-08은 N/A (발생 불가)

- Risk Class: MEDIUM (CRITICAL 2개 해소 완료; 남은 위험 = 실행 시 운영 실수)
- Promoted To Constitutional Layer: NO (구현 계획 문서)
- Affected Artifacts:
  - P:\_sys\docs\sys-restructure-plan.md (DEBATE_FINAL_R5 → DEBATE_FINAL_R6)
  - P:\_sys\docs\DEBATE_LOG.md (this file)
