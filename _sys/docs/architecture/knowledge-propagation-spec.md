# Knowledge Propagation System — Design Specification

> Status: SPEC_FINAL — 구현 대기 중
> Version: v1.0
> Date: 2026-06-14
> Authors: cc (coordinator) + cx (peer review)
> Source: DEBATE_LOG.md#2026-06-14-knowledge-propagation-design
> Scope: Cross-peer mistake prevention + user feedback propagation

---

## 1. 목적 및 문제 정의

### 근본 원인 (5 Whys)
```
왜 실수가 반복되는가?
  → 관찰이 기록되지 않기 때문
    → 기록이 있어도 다른 피어에게 전달되지 않기 때문
      → 전달 경로가 없기 때문
        → 지식 전파 시스템 자체가 없기 때문
          ✓ 근본 원인: 관찰→정규화→승인→주입→검증의 닫힌 루프 부재
```

### 해결 범위
| 문제 | 해결 방법 |
|:-----|:---------|
| 한 피어의 실수가 다른 피어에서 재발 | Cross-peer lesson injection |
| 사용자 피드백이 해당 피어에게만 전달 | Feedback propagation → lesson 변환 |
| 토큰 낭비 (매번 전체 규칙 재전송) | Hash-ACK 기반 팩 압축 |
| 경로/설정 하드코딩 | JSON config 전면화 |
| 워크스페이스 간 공통 지식 공유 | Global/workspace 레이어 분리 |

---

## 2. 아키텍처 개요 (3-Layer)

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: RAW EVENTS (audit store — 절대 직접 주입 X) │
│  mistake-events.jsonl  +  user-feedback.jsonl        │
└──────────────────────────────┬──────────────────────┘
                               ↓ triage/normalize
┌─────────────────────────────────────────────────────┐
│ Layer 2: ACTIVE LESSON REGISTRY (approved rules)     │
│  active-lessons.jsonl  (global + workspace)          │
└──────────────────────────────┬──────────────────────┘
                               ↓ filter + compile
┌─────────────────────────────────────────────────────┐
│ Layer 3: DELIVERY PACKS (prompt-facing, per-peer)    │
│  active-pack-index.json  →  hub.py [PEER LESSONS]    │
└─────────────────────────────────────────────────────┘

닫힌 피드백 루프:
observe → raw event → candidate lesson → approval →
active registry → compiled pack → inject → delivery log →
recurrence check → retire/update → (다음 사이클)
```

---

## 3. 디렉토리 구조

### 3-1. 글로벌 (워크스페이스 외부 공통)

```
_sys/ai/knowledge/
├── knowledge.config.json              # 모든 임계값·필터·경로·승인 규칙
├── schemas/
│   ├── common-record.schema.json      # 공통 envelope
│   ├── mistake-event.schema.json
│   ├── user-feedback.schema.json
│   ├── lesson.schema.json
│   └── delivery-pack.schema.json
├── general/
│   ├── lesson-taxonomy.json           # 카테고리·태그 정의 (global)
│   ├── active-lessons.jsonl           # 전체 워크스페이스 공통 lesson
│   ├── mistake-events.jsonl           # 글로벌 incident 로그
│   └── user-feedback.jsonl            # 글로벌 피드백 로그
├── peer-specific/
│   └── peer-bindings.json             # cc/cx/gc 능력, 툴 컨벤션
├── bundles/
│   └── active-pack-index.json         # 생성된 팩 메타데이터 (캐시)
└── logs/
    ├── approval-log.jsonl
    ├── delivery-log.jsonl
    └── knowledge-errors.jsonl         # 에러 가시성 보장
```

### 3-2. 워크스페이스 로컬

```
{workspace}/.ai/knowledge/
├── workspace-profile.json             # OS, shell, 인코딩, task 태그, repo 규칙
├── bindings.json                      # 글로벌 taxonomy → 로컬 특성 연결
├── active-lessons.jsonl               # 워크스페이스 전용 lesson
├── mistake-events.jsonl               # 로컬 incident
├── user-feedback.jsonl                # 로컬 피드백
└── overrides.json                     # 로컬 억제·추가·만료 재정의
```

### 3-3. Base Template (신규 워크스페이스 기본 제공)

```
templates/workspace/knowledge/
├── workspace-profile.template.json    # 기입 필드: os, shell, encoding, task_types
├── bindings.template.json             # 글로벌 연결 기본값
├── active-lessons.empty.jsonl
├── mistake-events.empty.jsonl
└── user-feedback.empty.jsonl
```

> 신규 워크스페이스는 글로벌 lesson을 복사하지 않는다. `bindings.json`으로 참조만 한다.

---

## 4. 설정 스키마 (`knowledge.config.json`)

```json
{
  "schema_version": 1,
  "roots": {
    "global_knowledge_root": "_sys/ai/knowledge",
    "workspace_knowledge_root_key": "workspace_ai_root"
  },
  "delivery": {
    "enabled": true,
    "block_name": "PEER LESSONS",
    "max_chars": 1200,
    "max_items": 8,
    "critical_always_include": true,
    "hash_ack_enabled": true,
    "inject_full_when_ack_missing": true,
    "overflow_policy": "show_count_and_pointer"
  },
  "filters": {
    "axes": ["peer_id", "os", "shell", "workspace_id", "task_type", "severity", "recency_days"],
    "min_severity_default": "medium",
    "recency_days_default": 90
  },
  "approval": {
    "raw_event":                  "auto_record",
    "non_policy_lesson":          "coordinator_auto_with_audit",
    "cross_peer_behavior":        "t2_consensus",
    "tier_1_or_1_5_directive":    "user_explicit"
  },
  "retirement": {
    "review_after_days": 60,
    "expire_after_days": 180,
    "clean_sessions_to_retire": 20
  },
  "visibility": {
    "show_schema_errors": true,
    "show_delivery_overflow": true,
    "write_error_log": true
  }
}
```

> 모든 수치·범위·타입·경로는 여기 정의. hub.py는 이 파일을 읽어 동작 결정.

---

## 5. General-Specific 분리

### General 레이어 (피어·워크스페이스 독립)
- Taxonomy: `shell-dialect`, `encoding`, `path-portability`, `tool-interface`, `context-cold-start`, `governance-drift`
- 공통 레코드 envelope (schema)
- 승인 라이프사이클
- Delivery-pack 포맷
- 만료 상태 정의
- Severity 정의

### Specific 레이어 (하위에서 대응)
- **피어별**: cc 툴 이름, cx shell 선호, gc 메모리 모드
- **워크스페이스별**: Windows PowerShell, UTF-8 without BOM, 경로 규칙
- **태스크별**: code, docs, shell-ops, governance

### 연결 지점 (JSON keys)
```json
// workspace-profile.json
{
  "os": "windows",
  "shell": "powershell",
  "encoding_default": "utf-8-no-bom",
  "task_types": ["code", "shell-ops", "docs"],
  "taxonomy_imports": ["_sys/ai/knowledge/general/lesson-taxonomy.json"]
}

// bindings.json
{
  "shell_dialect_category": "shell-dialect",
  "local_path_rules": ["no-drive-letter-hardcode", "use-_sys-relative"],
  "peer_tool_overrides": {
    "cx": { "search_tool": "rg" },
    "cc": { "search_tool": "Grep" }
  }
}
```

---

## 6. 스키마

### 6-1. Lesson 스키마

```json
{
  "id": "LESSON-20260614-001",
  "schema_version": 1,
  "status": "candidate|active|retired|rejected|superseded",
  "severity": "critical|high|medium|low",
  "title": "PowerShell 환경에서 Bash 문법 사용 금지",
  "compact_rule": "Windows PowerShell에서 $env:NAME='value' 사용. bash export/&&/2>/dev/null 금지.",
  "category": "shell-dialect",
  "scope": "global|workspace",
  "applies_to": {
    "peer_ids": ["cc", "gc", "cx"],
    "os": ["windows"],
    "shell": ["powershell"],
    "task_types": ["shell-ops", "code"]
  },
  "source_refs": [
    { "type": "mistake|feedback|debate|user", "id": "MISTAKE-xxx", "peer": "cx", "ts": "..." }
  ],
  "approval": {
    "approved_by": "coordinator|t2|user",
    "approved_at": "timestamp",
    "record_ref": "approval-log.jsonl#id"
  },
  "retirement": {
    "expires_at": null,
    "superseded_by": null,
    "review_after": "2026-08-14"
  }
}
```

### 6-2. Feedback 스키마 (User-origin)

```json
{
  "id": "FEEDBACK-20260614-001",
  "schema_version": 1,
  "status": "new|triaged|lesson_candidate|directive_candidate|accepted|rejected|retired",
  "source": {
    "type": "user",
    "room_id": "room-fe18",
    "target_peer": "cx",
    "ts": "timestamp"
  },
  "summary": "cx가 PowerShell에서 Bash 문법 사용. 사용자가 수정 요청.",
  "intent_class": "correction|preference|directive_candidate|bug_report|quality_signal",
  "scope_estimate": "single_response|workspace|global|policy",
  "linked_lesson_ids": ["LESSON-20260614-001"],
  "linked_directive_id": null,
  "trace_refs": ["delivery-log.jsonl#ask_id", "handoff.md#PENDING_ISSUES"]
}
```

> **핵심 구분**:
> - **Feedback**: 사용자 원천 신호, 휘발성, 일반화 전 상태
> - **Lesson**: 검토·승인된 예방 규칙, compact, 주입 대상
> - **Directive**: 사용자 권위 상시 규칙 (Tier 1.5, user-directives.md 전용)
> → 세 레지스트리는 절대 혼용하지 않는다.

---

## 7. 전달 설계

### 7-1. 주입 포맷 (`[PEER LESSONS]` 블록)

```
[PEER LESSONS]
Pack: kp-cx-windows-ps-20260614
Hash: sha256:abc123
Applies: peer=cx; os=windows; shell=powershell
Rules:
- HIGH LESSON-001: Windows PowerShell에서 Bash 문법 금지. $env:VAR='x' 사용.
- HIGH LESSON-002: UTF-8 without BOM만 사용. BOM 포함 파일 쓰기 금지.
Omitted: 3 lower-priority matches. Full pack: _sys/ai/knowledge/bundles/kp-cx-windows-ps.json
```

### 7-2. Hash-ACK (토큰 제로 최적화)

```
1회차: 팩 전체 주입 → peer가 hash 확인 → 암묵적 ACK
2회차+: [PEER LESSONS] Pack: kp-001 Hash: abc123 Status: ACK_CURRENT (규칙 생략)
팩 갱신 시: 새 hash → 다시 전체 주입
Critical lesson 추가 시: critical_always_include=true → 즉시 전체 재주입
```

### 7-3. 오버플로우 가시성

```
max_items(8) 초과 시:
  "Omitted: N lower-priority matches. See: <path>"
  → 사용자가 knowledge-errors.jsonl에서 확인 가능
```

---

## 8. 프로세스 흐름

```
OBSERVE
  ↓  (피어 자가 보고 | 사용자 수정 | 코디네이터 리뷰 | 테스트 실패)
CAPTURE → raw event 기록 (자동, no-approval)
  ↓
PROPOSE → candidate lesson 생성 (compact_rule 초안 포함)
  ↓
TRIAGE  → scope/severity 분류
  ↓ approval 경로
  ├─ 비정책 운영 lesson: 코디네이터 자동 활성화 + audit log
  ├─ 크로스피어 행동/지속성 정책: T-2 합의
  └─ Tier 1/1.5 directive 승격: 사용자 명시 확인
  ↓
ACTIVATE → active-lessons.jsonl 추가, 팩 재빌드
  ↓
INJECT → hub.py [PEER LESSONS] 블록 주입 (hash-ACK 기반)
  ↓
DETECT → 재발 시 source_refs에 추가, severity 재평가
  ↓
RETIRE/UPDATE → clean_sessions 조건 충족 or 환경 변경 시 retired 처리
  ↓ (다음 사이클로)
```

---

## 9. 문서 전략

### 기존 문서 확장
| 문서 | 확장 내용 |
|:-----|:---------|
| `DEBATE_PROTOCOL.md §0` | knowledge stores를 §0 필수 입력으로 추가 |
| `DEBATE_PROTOCOL.md §8` | lesson/feedback stores를 Closure Manifest sink로 추가 |
| `_sys/ai/protocol.json` | `knowledge_config` 경로 참조 추가 |
| `DEBATE_LOG.md` | 정책 레벨 lesson 승인만 기록 (운영 lesson 제외) |

### 신규 문서
| 문서 | 목적 |
|:-----|:-----|
| `_sys/docs/knowledge-propagation-spec.md` | 이 파일 — 전체 설계 스펙 |
| `_sys/ai/knowledge/schemas/*.schema.json` | 기계 계약 |
| `templates/workspace/knowledge/` | Base Template |

### 절대 확장 금지
- `_sys/ai/user-directives.md` — Tier 1.5 사용자 권위 전용. peer 운영 lesson 주입 금지.

---

## 10. 초기 Lesson 시드 (7개)

| ID | Category | Title | Affected |
|:---|:---------|:------|:---------|
| LL-001 | shell-dialect | Windows PowerShell에서 Bash 문법 금지 | all |
| LL-002 | encoding | UTF-8 without BOM 준수, BOM/UTF-16 금지 | all |
| LL-003 | path-portability | 드라이브 경로 하드코딩 금지, pathlib/설정 경로 사용 | all |
| LL-004 | tool-interface | 전용 툴 우선 (rg→Grep, echo→Write, find→Glob) | all |
| LL-005 | context-cold-start | cold-start 시 이전 세션 컨텍스트 가정 금지 | all |
| LL-006 | governance-drift | quorum 불명확 시 binding 결정 금지 → NEED_MORE_INFO | all |
| LL-007 | directive-boundary | peer 운영 lesson을 user-directives.md에 직접 넣지 말 것 | cc (coordinator) |

---

## 11. 구현 단계 (순서, 코드 미포함)

| 단계 | 내용 | 종속성 |
|:-----|:-----|:-------|
| 1 | `knowledge.config.json` + schemas 작성 | 없음 |
| 2 | Base Template 디렉토리 생성 | 1 |
| 3 | 글로벌 `active-lessons.jsonl` 초기 7개로 생성 | 1 |
| 4 | `peer-bindings.json` + `lesson-taxonomy.json` 작성 | 1 |
| 5 | `workspace-profile.json` + `bindings.json` 현재 워크스페이스에 생성 | 1 |
| 6 | hub.py: `_build_ask_query_with_context()`에 `[PEER LESSONS]` 블록 주입 추가 | 3, 5 |
| 7 | hub.py: peer_id 파라미터 전달 + 필터 로직 | 6 |
| 8 | Hub CLI: `hub.py lessons list/propose/activate/retire` | 3 |
| 9 | 테스트: 필터링, compact 렌더링, 오버플로우, 비정상 JSON | 6, 8 |
| 10 | *(Phase 2)* 자동 감지기 (encoding check, bash-in-ps 감지 등) | 9 |

---

## 12. 사용자 결정 필요 사항

| # | 질문 | 기본값 제안 |
|:-:|:-----|:-----------|
| 1 | 코디네이터 단독 lesson 활성화 허용 여부 (비정책) | ✅ 허용 + audit log |
| 2 | 주입 상한: `max_chars=1200`, `max_items=8` 적합한가? | 협의 필요 |
| 3 | Phase 2 자동 감지기 — Phase 1에 포함할지? | ❌ Phase 2 권장 |
| 4 | lesson 승인 기록 — DEBATE_LOG vs approval-log.jsonl | approval-log.jsonl 권장 (DEBATE_LOG는 정책 레벨만) |

---

## 참고

- Source debate: `cx-20260614170001-F2B8.txt`
- Related: `DEBATE_LOG.md#2026-06-14-knowledge-propagation-design`
- Related: `DEBATE_PROTOCOL.md §16` (끝장 작업 거버넌스)
- Related: `_sys/ai/user-directives.md` (Tier 1.5 — 이 시스템과 분리)
