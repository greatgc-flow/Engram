# _sys Restructure Plan — v1.0

> Status: DEBATE_FINAL_R3 — gc+cx 3-round 끝장 교차검토 완료 (2026-06-15)
> Date: 2026-06-14 (updated 2026-06-15 R3)
> Author: cc (coordinator), gc (cross-reviewer R1+R3), cx (independent auditor R2+R3)
> Protocol: R:10 (Brain Sync) — 전체 피어 끝장 플랜
> Review: R1+R2: gc CRITICAL×1/HIGH×4 + cx CRITICAL×2/HIGH×4 | R3: Root Swap REJECTED + verify-all V1~V10
> ⚠️ CRITICAL R3: Root Swap(병렬 _sys_new/)=REJECT, cut-over "rename backup" 방식, 2-gate verify-all, runtime/recovery/

---

## 1. 설계 원칙 (Design Principles)

| # | 원칙 | 설명 |
|---|------|------|
| P-01 | **No-Code / Zero-Code 지향** | 로직은 JSON 설정에. 코드는 설정을 읽는 executor만. |
| P-02 | **Composable + MECE** | 단일 책임, 중복 없음, 누락 없음. 모든 컴포넌트가 조합 가능. |
| P-03 | **General-Specific 분리** | General 레이어(피어·워크스페이스 독립) + Specific 레이어(하위 대응). |
| P-04 | **JSON-Everything** | 하드코딩된 값, 임계값, 경로, 환경변수 전부 JSON 설정. |
| P-05 | **연결자(Connector) JSON화** | General-Specific 연결지점도 JSON으로 명시. `_extends` / `_ref` 패턴. |
| P-06 | **교차-워크스페이스 Commons** | 특정 워크스페이스 외부에서 공통으로 쓸 공간 명시적 분리. |
| P-07 | **Base Template** | 새 워크스페이스 초기화를 위한 Base Template 완비. |
| P-08 | **Workspace-Local Scope** | 워크스페이스 특정 내용은 `.ai/` 하위에만. 상위 오염 금지. |
| P-09 | **공통 인터페이스** | 모든 구성요소는 일반적(peer-agnostic) 인터페이스 통과. Specific은 하위 레이어 대응. |
| P-10 | **연결성·추적성** | 모든 파일(문서/설정/소스)의 참조 관계를 `traceability.json`에 유지. |
| P-11 | **에러 가시성** | 에러·스택트레이스를 사용자가 명확히 인지. 위치 고정, 형식 표준화. |
| P-12 | **유연한 CLI 경로** | AI CLI 바이너리 경로는 설정 파일에서 해석. 코드에 hardcode 없음. |

---

## 2. As-Is 현황 분석

### 2-1. 현재 `_sys/` 루트 항목 (21개 — 혼잡)

```
_sys/
├── ai/              # 프로토콜 설정 + 지식 + 런타임 상태 혼재
├── antigravity/     # ⚠ 피어 디렉토리 루트에 노출
├── chatgpt/         # ⚠ 미사용 (사용 흔적 없음)
├── checks/          # ⚠ .bat + .py 이중구조 (7쌍)
├── claude/          # ⚠ 피어 디렉토리 루트에 노출
├── cli/             # 런처·래퍼 혼재
├── codex/           # ⚠ 피어 디렉토리 루트에 노출
├── common/          # 거의 비어있음
├── core/            # 핵심 엔진 (양호)
├── data/            # 런타임 데이터 (양호)
├── docs/            # 프로토콜 문서 (양호, Garbage 포함)
├── env/             # 런타임 바이너리 (양호)
├── gemini/          # ⚠ 피어 디렉토리 루트에 노출
├── hooks/           # 훅 스크립트
├── mock_peer/       # 테스트용
├── templates/       # 템플릿 (부분)
├── tests/           # 테스트
├── tools/           # 외부 바이너리 (양호)
├── config.json      # ⚠ 루트 파편 파일
├── context_menu.json # ⚠ 루트 파편 파일
├── dispatch.json    # ⚠ 루트 파편 파일
├── env.json         # ⚠ 루트 파편 파일
├── local.config.bat.template # ⚠ 루트 파편 파일
├── paths.json       # ⚠ 루트 파편 파일
├── runtimes.json    # ⚠ 루트 파편 파일
├── start.bat        # 런처 진입점
├── SYSTEM_ARCHITECTURE.md # ⚠ 구식
└── temp_manual_gen.py # ⚠ 가비지
```

### 2-2. 구조적 문제점

| 번호 | 문제 | 영향 |
|------|------|------|
| I-01 | 피어 디렉토리 4개(`gemini/`, `claude/`, `codex/`, `antigravity/`)가 `_sys/` 루트 직하 | 루트 혼잡 |
| I-02 | `_sys/ai/` 하나에 프로토콜 설정 + AI 지식 + 런타임 디렉티브 + 사용자 디렉티브 혼재 | MECE 위반 |
| I-03 | 루트 파편 JSON 7개 (`config.json`, `paths.json`, `env.json`, `dispatch.json`, `context_menu.json`, `runtimes.json`, `local.config.bat.template`) | 루트 혼잡 |
| I-04 | `checks/`에 동일 기능 .bat + .py 이중구조 (7쌍) | 중복 |
| I-05 | `cli/` + `hooks/` + `checks/` 분리되어 있으나 기능상 묶음 | 분산 |
| I-06 | `chatgpt/` 미사용 디렉토리 방치 | 가비지 |
| I-07 | `temp_manual_gen.py` 루트 방치 | 가비지 |
| I-08 | CLI 바이너리 경로가 `env.json`의 PATH에 묻혀있고, `infra.json`, `orchestration.json` 에 분산 | 유연성 없음 |

### 2-3. 레거시 목록 (제거 대상)

| 파일 | 이유 |
|------|------|
| `_sys/gemini/status.json` | health.json으로 대체됨. 31개 파일 참조 — 모두 이주 필요 |
| `_sys/gemini/gemini-status.bat` | hub.py `health-update`가 동일 역할 |
| `_sys/gemini/gemini-gate.bat` | redirect stub → cli/collab-rate-gate.bat |
| `_sys/gemini/gemini-set-ratio.bat` | redirect stub → cli/set-collab-rate.bat |
| `_sys/gemini/gemini-usage.bat` | logs.json 직접 읽기 → usage.json (hub.py 통합) |
| `_sys/claude/claude-gate.bat` | dead code (참조 파일 없음) |
| `_sys/claude/claude-status.bat` | hub.py `health-update`가 동일 역할 |
| `_sys/hooks/ai_check.py` | hub.py `check-gate --peer gc` 로 대체 |
| `_sys/checks/_common.py` | `update_status_error()` → hub.py 경유 |
| `_sys/checks/check_health.py` | health.json 직접 업데이트 → hub.py `health-update` |
| `_sys/checks/check-*.bat` | Python 래퍼 → 직접 Python 호출 또는 hub.py |
| `_sys/ai/infra.json` | `config/integrations/infra.json`으로 통합 (경로 재정의) |
| `_sys/ai/collaboration_loop_bindings.json` | protocol.json 또는 governance.json으로 흡수 |
| `_sys/ai/status_checks.json` | status.json 참조 제거 후 `config/integrations/status-checks.json` |
| `_sys/SYSTEM_ARCHITECTURE.md` | 구식 → 새 ARCHITECTURE.md로 교체 |
| `_sys/temp_manual_gen.py` | 가비지 |
| `_sys/chatgpt/` | 미사용 전체 제거 |
| `_sys/config.json` | `config/general/system.json` 흡수 |

---

## 3. To-Be 구조 설계

### 3-1. `_sys/` 루트 (12개 — 깔끔)

```
_sys/
├── config/          # 📋 모든 JSON 설정 (General + Specific)
├── core/            # ⚙️  런타임 엔진 (hub.py 등)
├── peers/           # 🤖 피어별 운영 데이터
├── knowledge/       # 📚 교차-피어 지식 시스템
├── protocol/        # 📄 프로토콜 문서 (활성)
├── runtime/         # 🔧 CLI래퍼·훅·체크 (코드 실행 계층)
├── common/          # 🌐 교차-워크스페이스 공통 자원
├── templates/       # 📁 Base Template (워크스페이스·피어 초기화)
├── tests/           # 🧪 테스트 (유지)
├── data/            # 💾 런타임 데이터·상태 (유지)
├── env/             # 🐍 Python·Node 런타임 바이너리 (DEEP)
└── tools/           # 🔨 외부 바이너리 (DEEP, 자유 업데이트)
```

### 3-2. `config/` — 모든 설정의 단일 진입점

```
config/
├── general/                          # General 레이어 (peer/workspace 독립)
│   ├── system.json                   # ⚠️ env 플래그·환경변수만 (경로 X)
│   │                                 #    통합: config.json + env.json (env_vars, env_vars_tool)
│   ├── runtimes.json                 # 런타임 버전·URL (was _sys/runtimes.json)
│   ├── cli-resolve.json              # 🆕 CLI 바이너리 경로 해석 설정 (General)
│   ├── health-defaults.json          # 🆕 General 헬스 임계값·정책
│   └── error-visibility.json         # 🆕 에러 표시 설정 (hardcoded fallback 필수)
├── peers/                            # Specific 레이어 (피어별)
│   ├── registry.json                 # ⚠️ 경량 인덱스만: node_id → sys_subdir + enabled
│   │                                 #    (was ai/peers.json — 운영 상세는 peers/{id}/peer.json)
│   └── cli-overrides.json            # 🆕 피어별 CLI 경로 오버라이드
├── protocol/                         # 프로토콜 설정
│   ├── protocol.json                 # 협업 프로토콜 (was ai/protocol.json)
│   ├── lifecycle.json                # 세션 라이프사이클 (was ai/lifecycle_policy.json)
│   ├── knowledge.json                # 지식 전파 설정 (was ai/knowledge/knowledge.config.json)
│   ├── governance.json               # 거버넌스 파라미터 (was ai/governance_params.json)
│   └── model-profiles.json           # 모델 프로필 (was ai/model_profiles.json)
└── integrations/                     # 크로스-커팅 통합 설정 (크로스-피어 성격)
    ├── orchestration.json             # ⚠️ 허브 노드 ID·호출 (was ai/orchestration.json)
    │                                  #    gc 리뷰: peers/X는 특정 피어 전용 — 여기가 맞음
    ├── dispatch.json                  # 파이프라인 오케스트레이션 (was _sys/dispatch.json)
    ├── context-menu.json              # 호스트 통합 (was _sys/context_menu.json)
    ├── status-checks.json             # 헬스 체크 정의 (was ai/status_checks.json)
    ├── traceability.json              # 문서-코드 추적 맵 (was ai/traceability_map.json)
    ├── infra.json                     # ⚠️ 모든 물리적 경로 맵 (단일 경로 진실 소스)
    │                                  #    paths.json 흡수 — system.json과 역할 분리
    └── hub-config.json                # 허브 한도 설정 (was core/hub_config.json)
```

> **system.json vs infra.json 역할 분리 (gc HIGH 수정):**
> - `system.json` = 환경 플래그·변수만 (`PYTHONUTF8`, `CLAUDE_CODE_USE_POWERSHELL_TOOL`, tool_env_vars)
> - `infra.json` = 모든 경로 (`base_dirs`, `path_entries`, `ipc_paths`, `bat_locations`, `config_registry`, `tool_paths`) — 단일 경로 진실 소스

#### General-Specific 연결 패턴

```jsonc
// config/general/cli-resolve.json  [GENERAL]
{
  "_schema": "cli-resolve/v1",
  "resolve_strategy": ["search_paths", "system_path"],
  "peers": {
    "gc": {
      "binary": "gemini",
      "npm_package": "@google/gemini-cli",
      "search_paths": ["${env}/nodejs/npm-global"],
      "fallback": "system_path"
    },
    "cc": { "binary": "claude", "npm_package": "@anthropic-ai/claude-code",
            "search_paths": ["${env}/nodejs/npm-global"], "fallback": "system_path" },
    "cx": { "binary": "codex",  "npm_package": "@openai/codex",
            "search_paths": ["${env}/nodejs/npm-global"], "fallback": "system_path" },
    "ag": { "binary": "agy",    "npm_package": null,
            "search_paths": ["${tools}/agy"],            "fallback": "system_path" }
  }
}

// config/peers/cli-overrides.json  [SPECIFIC connector]
{
  "_schema": "cli-overrides/v1",
  "_extends": "config/general/cli-resolve.json",   // General 참조
  "overrides": {
    "gc": { "search_paths": ["${env}/nodejs/npm-global", "${tools}/gemini-alt"] },
    "ag": { "binary": "agy.exe" }                   // Windows 특정 override
  }
}
```

```jsonc
// config/general/health-defaults.json  [GENERAL]
{
  "_schema": "health-defaults/v1",
  "stale_minutes": 120,
  "critical_reasons": ["auth_failure", "rate_limit_429", "quota_exceeded", "sandbox_blocked", "cli_not_found"],
  "gate_close_on_failures": 3,
  "gate_reopen_on_success": 1
}

// config/peers/registry.json  [SPECIFIC — per-peer overrides]
{
  "_schema": "peer-registry/v2",
  "_extends": "config/general/health-defaults.json",
  "peers": {
    "gc": {
      "node_id": "gc",
      "sys_subdir": "peers/gc",              // NEW 경로
      "health": { "stale_minutes": 60 },     // Specific override
      "cli_ref": "config/general/cli-resolve.json#gc"
    }
  }
}
```

### 3-3. `peers/` — 피어별 운영 데이터

```
peers/
├── cc/                                # Claude Code (was _sys/claude/)
│   ├── peer.json                      # 🆕 피어 식별자·메타데이터
│   ├── health.json                    # 헬스 상태 (was _sys/claude/health.json)
│   ├── session_state.json             # 세션 상태
│   └── runtime/                       # 피어 런타임 설정
│       ├── config/                    # Junction 대상 (was _sys/claude/config/)
│       └── project/                   # 프로젝트 설정 (was _sys/claude/project/)
├── gc/                                # Gemini CLI (was _sys/gemini/)
│   ├── peer.json
│   ├── health.json
│   ├── session_state.json
│   └── runtime/
│       ├── config/                    # was _sys/gemini/config/
│       └── project/                   # was _sys/gemini/project/
├── cx/                                # Codex (was _sys/codex/)
│   ├── peer.json
│   ├── health.json
│   ├── session_state.json
│   └── runtime/
│       ├── config/                    # was _sys/codex/config/
│       └── project/                   # was _sys/codex/project/
└── ag/                                # Antigravity (was _sys/antigravity/)
    ├── peer.json
    ├── health.json
    └── runtime/
        ├── config/                    # was _sys/antigravity/config/
        └── project/
```

#### registry.json — 경량 인덱스 (gc HIGH 수정)

```jsonc
// config/peers/registry.json  [경량 인덱스만]
{
  "_schema": "peer-registry/v2",
  "peers": {
    "gc": { "node_id": "gc", "sys_subdir": "peers/gc", "enabled": true },
    "cc": { "node_id": "cc", "sys_subdir": "peers/cc", "enabled": true },
    "cx": { "node_id": "cx", "sys_subdir": "peers/cx", "enabled": true },
    "ag": { "node_id": "ag", "sys_subdir": "peers/ag", "enabled": false }
  }
}
// 운영 상세(health 오버라이드, cli_ref, host_junction, glue_file) → peers/{id}/peer.json 전용
```

#### 피어 식별자 파일 (`peer.json`) — 모든 운영 상세 (gc HIGH 수정)

```jsonc
// peers/gc/peer.json  [모든 운영 상세 — registry.json과 중복 없음]
{
  "_schema": "peer-identity/v1",
  "_ref": "config/peers/registry.json#gc",          // 인덱스 참조 (node_id, sys_subdir만)
  "display_name": "Gemini CLI",
  "description": "Google Gemini CLI",
  "npm_package": "@google/gemini-cli",
  "cli": {
    "_ref": "config/general/cli-resolve.json#gc"    // CLI 해석 전략 참조
  },
  "health": {
    "_extends": "config/general/health-defaults.json",
    "stale_minutes": 60                              // Specific override
  },
  "host_junction": {
    "host_env": "USERPROFILE",
    "host_dirname": ".gemini",
    "portable_subpath": "runtime/config"
  },
  "project_junction": { "portable_subpath": "runtime/project" },
  "glue_file": "runtime/config/GEMINI.md",
  "workspace_shadow": ".ai/gemini",
  "env_vars": { "GEMINI_CLI_TRUST_WORKSPACE": true },
  "cleanup": {
    "peer_paths": ["usage.json", "session-map.json", "session.lock", "session-id.txt"],
    "peer_globs": ["cq-*.txt"],
    "config_paths": ["tmp/"]
  }
}
```

### 3-4. `knowledge/` — 교차-피어 지식 (was `_sys/ai/knowledge/`)

> **cx MEDIUM 반영:** `knowledge/config.json` 명칭이 `config/protocol/knowledge.json`과 혼용되어 충돌.
> Fix: `knowledge/index.json` (로컬 스토리지 레이아웃·스키마·번들 인덱스) vs `config/protocol/knowledge-policy.json` (거버넌스·주입 정책) 으로 명확히 분리.

```
knowledge/
├── index.json                         # (was knowledge.config.json → renamed) — 로컬 스토리지 레이아웃, 스키마 경로, 번들 인덱스
│                                      # config/protocol/knowledge-policy.json 참조 (정책은 거기서)
├── general/                           # Global — 워크스페이스 독립
│   ├── lesson-taxonomy.json
│   ├── active-lessons.jsonl
│   ├── mistake-events.jsonl
│   └── user-feedback.jsonl
├── peer-specific/
│   └── peer-bindings.json
├── schemas/                           # 기계 계약
│   ├── lesson.schema.json
│   ├── mistake-event.schema.json
│   ├── user-feedback.schema.json
│   └── delivery-pack.schema.json
├── bundles/                           # 컴파일된 팩 캐시
│   └── active-pack-index.json
└── logs/
    ├── approval-log.jsonl
    ├── delivery-log.jsonl
    └── knowledge-errors.jsonl
```

### 3-5. `protocol/` — 활성 프로토콜 문서 (was `_sys/docs/`)

```
protocol/
├── general/                           # 피어·워크스페이스 독립
│   ├── ARCHITECTURE.md                # 🆕 이 문서 기반 전체 구조 설명
│   ├── DEBATE_PROTOCOL.md
│   ├── DEBATE_LOG.md
│   ├── PROTOCOL_INVARIANTS.md
│   ├── collaboration.md               # (was collaboration_protocol.md)
│   ├── health.md                      # (was protocol-health.md)
│   ├── session.md                     # (was protocol-session.md)
│   ├── consensus.md
│   ├── directives.md
│   ├── permissions.md
│   ├── workload.md
│   ├── routing.md
│   └── knowledge-propagation-spec.md
├── peer-specific/                     # 피어별 문서
│   ├── cc/
│   │   └── CLAUDE.md                  # (was protocol-*.md cc 관련)
│   ├── gc/
│   │   └── GEMINI.md
│   ├── cx/
│   │   └── CODEX.md                   # (was protocol-codex.md)
│   └── ag/
│       └── AGY.md                     # (was protocol-antigravity.md)
└── reference/                         # 🆕 참조 문서 (gc MEDIUM 반영: protocol/ 네임스페이스 오염 방지)
    ├── USER_MANUAL.md                 # (was docs/USER_MANUAL.md)
    └── TAXONOMY_v11.md               # (was docs/TAXONOMY_v11.md)
```

> **gc/cx MEDIUM:** USER_MANUAL.md · TAXONOMY_v11.md는 능동적 프로토콜 제약이 아닌 참조 문서.
> `protocol/general/` 오염 방지 → `protocol/reference/` 하위로 분리.

### 3-6. `core/` vs `runtime/` 경계 정의 (gc MEDIUM 반영)

| 계층 | 정의 | 내용 |
|------|------|------|
| `core/` | **내부 API·엔진** — import 가능, side-effect 없음 | `hub.py`, `launcher.py`, `provisioner.py`, `registrar.py`, `relocator.py`, `virtualizer.py`, `scrubber.py`, `dispatcher.py` |
| `runtime/` | **실행 계층** — CLI 래퍼, 진입점 .py, 훅, 체크 | `runtime/cli/`, `runtime/hooks/`, `runtime/checks/` |

> `core/*.py`는 직접 실행하지 않음 — `runtime/` 또는 `hub.py` CLI가 진입점.

### 3-7. `common/` vs `knowledge/` 경계 정의 (gc MEDIUM 반영)

| 공간 | 성격 | 내용 |
|------|------|------|
| `common/` | **정적·규범적** (사용자·프레임워크가 작성) | `user-directives.md`, `peer-rules.md`, `agents/`, `skills/`, `mcp/` |
| `knowledge/` | **동적·서술적** (AI 학습·관찰 결과) | `active-lessons.jsonl`, `mistake-events.jsonl`, `user-feedback.jsonl` |

> 절대 혼용 금지. `user-directives.md`는 common/ 전용 (knowledge/ 오염 금지 — Tier 1.5 규칙).

### 3-7b. MECE 엣지 케이스 배치 결정 (cx Round-3 반영)

| 항목 | 위치 | 근거 |
|------|------|------|
| `rollback.ps1`, `cutover.ps1` | `runtime/recovery/` | 영구 복구 스크립트 — 임시 생성 아님 |
| `manage.py gen-traceability` 출력 | `config/integrations/traceability.json` (커밋된 정책 맵) + `data/state/traceability.generated.json` (런타임 증거) | 둘의 역할이 다름 |
| hub.py 에러 로그 | `data/logs/` | 시스템 실행 로그 |
| knowledge-system 에러 요약 | `knowledge/logs/` (큐레이팅된 경우만) | raw는 `data/logs/` |
| 피어 세션 로그 raw | `peers/{id}/runtime/` | 피어 CLI 소유 |
| hub 정규화 세션 로그 | `data/logs/` | hub.py 소유 |
| workspace `.ai/` 템플릿 | `templates/workspace/.ai/` | Base Template 하위 |
| hub.py 테스트 | `tests/unit/` | 피어별 분리 아님 — hub는 단일 엔진 |
| `verify-all` 검증 설정 | `config/integrations/verify-config.json` | JSON-driven 검증 정책 |

### 3-8. `runtime/` — 코드 실행 계층 (was `cli/` + `hooks/` + `checks/`)

```
runtime/
├── cli/                               # was _sys/cli/
│   ├── msg.bat                        # 허브 진입점 (유지)
│   ├── manage.bat / manage.py         # 파이프라인 러너
│   ├── launch.bat                     # 런처
│   ├── {peer}.bat                     # 피어 런처 (cc.bat, gc.bat, cx.bat, ag.bat)
│   ├── {peer}_entry.py                # 피어 엔트리포인트
│   ├── collab-rate-gate.bat
│   ├── set-collab-rate.bat
│   └── git-draft.bat / git_draft.py
├── hooks/                             # was _sys/hooks/
│   ├── collab_log.py
│   ├── raw_log.py
│   └── ...
├── checks/                            # was _sys/checks/ (bat 래퍼 없이 py만)
│   ├── check_agents.py
│   ├── check_deps.py
│   ├── check_policy.py
│   ├── check_portability.py
│   ├── check_risk.py
│   └── check_versions.py
│   # check_health.py → 제거 (hub.py health-update 통합)
│   # _common.py → 제거 (update_status_error → hub.py 경유)
│   # *.bat → 모두 제거 (불필요 래퍼)
└── recovery/                          # 🆕 복구 스크립트 (cx MECE: 영구 홈 필요)
    ├── cutover.ps1                    # 🆕 원자적 cut-over 실행 (프로세스 종료 + junction 재등록)
    └── rollback.ps1                   # 🆕 cut-over 실패 시 즉시 복구 (was rollback-phase1.ps1)
```

> **cx MECE:** `rollback.ps1`은 `runtime/recovery/`에 영구 보관 (Phase 0 임시 생성 아님).
> `cutover.ps1`도 동일 위치에서 관리 — 단일 double-click 실행으로 전체 cut-over 완료.

### 3-9. `common/` — 교차-워크스페이스 공통 자원

```
common/
├── peer-rules.md                      # was _sys/ai/common/peer-rules.md
├── agents/                            # was _sys/ai/common/agents/
├── skills/                            # was _sys/ai/common/skills/
├── mcp/                               # was _sys/ai/common/mcp/
│   └── catalog.json
└── user-directives.md                 # was _sys/ai/user-directives.md
```

> `common/` = 워크스페이스에 관계없이 항상 적용되는 공유 자원.  
> 각 피어의 `runtime/project/` 에서 symbolic 참조.

### 3-10. `templates/` — Base Template (워크스페이스·피어 초기화)

```
templates/
├── workspace/                         # 새 워크스페이스 초기화
│   ├── profile.template.json          # workspace-profile 기본값
│   ├── knowledge/                     # Knowledge base template
│   │   ├── workspace-profile.template.json
│   │   ├── bindings.template.json
│   │   ├── active-lessons.empty.jsonl
│   │   ├── mistake-events.empty.jsonl
│   │   └── user-feedback.empty.jsonl
│   ├── CLAUDE.md.template             # Glue file 기본값
│   └── GEMINI.md.template
└── peer/                              # 새 피어 등록 템플릿
    ├── peer.template.json             # peer.json 기본값
    ├── health.template.json           # health.json 초기값
    └── workspace.md.template          # 피어 워크스페이스 글루 파일
```

### 3-11. 에러 가시성 설계

```jsonc
// config/general/error-visibility.json
{
  "_schema": "error-visibility/v1",
  "outputs": {
    "stderr": true,
    "error_log_path": "${data}/logs/errors.jsonl",
    "user_notification": true,
    "show_remediation_hint": true
  },
  "format": {
    "include_traceback": true,
    "include_context_vars": true,
    "include_file_line": true,
    "max_traceback_lines": 30,
    "prefix": "[ERROR]"
  },
  "severity": {
    "FATAL": { "exit_code": 1, "write_log": true, "notify_user": true },
    "ERROR": { "exit_code": 2, "write_log": true, "notify_user": true },
    "WARN":  { "exit_code": 0, "write_log": true, "notify_user": false },
    "INFO":  { "exit_code": 0, "write_log": false, "notify_user": false }
  },
  "known_errors": {
    "cli_not_found":    { "severity": "FATAL", "hint": "AI CLI binary not found. Check config/general/cli-resolve.json and run: python runtime/cli/manage.py install" },
    "auth_failure":     { "severity": "ERROR", "hint": "AI peer authentication failed. Re-authenticate with the peer CLI." },
    "health_gate_closed": { "severity": "WARN",  "hint": "Peer gate closed. Run: python core/hub.py peer-recover --peer <id>" },
    "schema_violation": { "severity": "ERROR", "hint": "Config file schema error. Check knowledge/logs/knowledge-errors.jsonl" }
  }
}
```

hub.py의 모든 에러 경로는 이 설정을 읽어 형식·경로·알림 방식을 결정.

> **⚠️ gc HIGH: Catch-22 방지 — Hardcoded Fallback 필수**  
> `error-visibility.json` 자체가 파싱 실패하거나 경로를 찾을 수 없는 경우,  
> hub.py는 설정 로드를 시도하기 전에 Python 기본 `try-except`로 보호해야 함:
> ```python
> # hub.py 내 에러 로딩 헬퍼 (항상 작동 보장)
> def _get_error_cfg() -> dict:
>     try:
>         return _load_config("config/general/error-visibility.json")
>     except Exception:
>         # hardcoded fallback — 설정 로드 실패 시에도 사용자가 오류를 반드시 볼 수 있음
>         return {"outputs": {"stderr": True}, "format": {"include_traceback": True, "prefix": "[ERROR]"}}
> ```
> 에러 로그 경로(`${data}/logs/errors.jsonl`)도 `__file__` 기준 상대경로 fallback 필요.

---

## 4. As-Is → To-Be Gap 분석

### 4-1. 디렉토리 이동/삭제/생성

| 현재 경로 | 처리 | 대상 경로 | 비고 |
|-----------|------|-----------|------|
| `_sys/gemini/` | MOVE | `_sys/peers/gc/` | bat 파일 제거 후 |
| `_sys/claude/` | MOVE | `_sys/peers/cc/` | bat 파일 제거 후 |
| `_sys/codex/` | MOVE | `_sys/peers/cx/` | |
| `_sys/antigravity/` | MOVE | `_sys/peers/ag/` | |
| `_sys/chatgpt/` | DELETE | — | 미사용 |
| `_sys/ai/` | DISSOLVE | → `config/`, `knowledge/`, `data/state/` | |
| `_sys/docs/` | MOVE | `_sys/protocol/` | Garbage/ 제외 |
| `_sys/cli/` | MOVE | `_sys/runtime/cli/` | |
| `_sys/hooks/` | MOVE | `_sys/runtime/hooks/` | |
| `_sys/checks/` | MOVE+REFACTOR | `_sys/runtime/checks/` | bat 모두 제거 |
| `_sys/common/` | MOVE | `_sys/common/` | ai/common/ 흡수 |

### 4-2. 파일별 이동 매핑

| As-Is | To-Be | 처리 |
|-------|-------|------|
| `_sys/config.json` | `_sys/config/general/system.json` | MERGE |
| `_sys/paths.json` | `_sys/config/integrations/infra.json` | MERGE (경로는 infra.json에) |
| `_sys/env.json` | `_sys/config/general/system.json` | MERGE (env_vars만 — 경로 없음) |
| `_sys/runtimes.json` | `_sys/config/general/runtimes.json` | MOVE |
| `_sys/dispatch.json` | `_sys/config/integrations/dispatch.json` | MOVE |
| `_sys/context_menu.json` | `_sys/config/integrations/context-menu.json` | MOVE |
| `_sys/local.config.bat.template` | `_sys/templates/workspace/` | MOVE |
| `_sys/SYSTEM_ARCHITECTURE.md` | DELETE → `_sys/protocol/general/ARCHITECTURE.md` (신규) | REPLACE |
| `_sys/temp_manual_gen.py` | DELETE | GARBAGE |
| `_sys/ai/protocol.json` | `_sys/config/protocol/protocol.json` | MOVE |
| `_sys/ai/peers.json` | `_sys/config/peers/registry.json` | MOVE+RENAME |
| `_sys/ai/orchestration.json` | `_sys/config/integrations/orchestration.json` | MOVE (gc HIGH: 크로스-피어 성격) |
| `_sys/ai/lifecycle_policy.json` | `_sys/config/protocol/lifecycle.json` | MOVE+RENAME |
| `_sys/ai/model_profiles.json` | `_sys/config/protocol/model-profiles.json` | MOVE |
| `_sys/ai/governance_params.json` | `_sys/config/protocol/governance.json` | MOVE+RENAME |
| `_sys/ai/status_checks.json` | `_sys/config/integrations/status-checks.json` | MOVE (status.json ref 제거) |
| `_sys/ai/traceability_map.json` | `_sys/config/integrations/traceability.json` | MOVE+RENAME |
| `_sys/ai/infra.json` | `_sys/config/integrations/infra.json` | MOVE+UPDATE |
| `_sys/ai/knowledge.config.json` | `_sys/config/protocol/knowledge.json` | MOVE |
| `_sys/ai/collaboration_loop_bindings.json` | `_sys/config/protocol/governance.json` | MERGE |
| `_sys/ai/collaboration_policy.schema.json` | `_sys/knowledge/schemas/` | MOVE |
| `_sys/ai/room_policy.example.json` | `_sys/templates/workspace/` | MOVE |
| `_sys/ai/runtime-directives.jsonl` | `_sys/data/state/runtime-directives.jsonl` | MOVE |
| `_sys/ai/user-directives.md` | `_sys/common/user-directives.md` | MOVE |
| `_sys/ai/knowledge/` | `_sys/knowledge/` | MOVE (전체) |
| `_sys/ai/common/peer-rules.md` | `_sys/common/peer-rules.md` | MOVE |
| `_sys/ai/common/agents/` | `_sys/common/agents/` | MOVE |
| `_sys/ai/common/skills/` | `_sys/common/skills/` | MOVE |
| `_sys/ai/common/mcp/` | `_sys/common/mcp/` | MOVE |
| `_sys/docs/*.md` | `_sys/protocol/general/*.md` | MOVE (Garbage 제외) |
| `_sys/docs/protocol-codex.md` | `_sys/protocol/peer-specific/cx/CODEX.md` | MOVE |
| `_sys/docs/protocol-antigravity.md` | `_sys/protocol/peer-specific/ag/AGY.md` | MOVE |
| `_sys/claude/health.json` | `_sys/peers/cc/health.json` | MOVE |
| `_sys/gemini/health.json` | `_sys/peers/gc/health.json` | MOVE |
| `_sys/codex/health.json` | `_sys/peers/cx/health.json` | MOVE |
| `_sys/antigravity/health.json` | `_sys/peers/ag/health.json` | MOVE |
| `_sys/gemini/session_state.json` | `_sys/peers/gc/session_state.json` | MOVE |
| `_sys/codex/session_state.json` | `_sys/peers/cx/session_state.json` | MOVE |
| `_sys/gemini/config/` | `_sys/peers/gc/runtime/config/` | MOVE |
| `_sys/claude/config/` | `_sys/peers/cc/runtime/config/` | MOVE |
| `_sys/codex/config/` | `_sys/peers/cx/runtime/config/` | MOVE |
| `_sys/antigravity/config/` | `_sys/peers/ag/runtime/config/` | MOVE |
| `_sys/gemini/project/` | `_sys/peers/gc/runtime/project/` | MOVE |
| `_sys/claude/project/` | `_sys/peers/cc/runtime/project/` | MOVE |
| `_sys/codex/project/` | `_sys/peers/cx/runtime/project/` | MOVE |
| `_sys/antigravity/project/` | `_sys/peers/ag/runtime/project/` | MOVE |
| `_sys/gemini/templates/workspace.md` | `_sys/templates/peer/gc/workspace.md` | MOVE |
| `_sys/claude/templates/workspace.md` | `_sys/templates/peer/cc/workspace.md` | MOVE |
| `_sys/claude/agent/` | `_sys/peers/cc/runtime/agent/` | MOVE |
| `_sys/core/hub_config.json` | `_sys/config/integrations/hub-config.json` | MOVE |
| `_sys/core/*.py` | `_sys/core/*.py` | 유지 (경로 참조만 업데이트) |
| `_sys/cli/` | `_sys/runtime/cli/` | MOVE |
| `_sys/hooks/` | `_sys/runtime/hooks/` | MOVE |
| `_sys/checks/*.py` | `_sys/runtime/checks/*.py` | MOVE (bat 제거) |
| `_sys/mock_peer/` | `_sys/tests/mock_peer/` | MOVE (테스트 전용) |

### 4-3. 삭제 대상 (레거시)

| 파일 | 이유 |
|------|------|
| `_sys/gemini/status.json` | health.json 대체 |
| `_sys/gemini/gemini-status.bat` | hub.py 통합 |
| `_sys/gemini/gemini-gate.bat` | redirect stub |
| `_sys/gemini/gemini-set-ratio.bat` | redirect stub |
| `_sys/gemini/gemini-usage.bat` | hub.py 통합 |
| `_sys/claude/claude-gate.bat` | dead code |
| `_sys/claude/claude-status.bat` | hub.py 통합 |
| `_sys/hooks/ai_check.py` | hub.py check-gate 대체 |
| `_sys/checks/_common.py` | hub.py 경유로 대체 |
| `_sys/checks/check_health.py` | hub.py health-update 통합 |
| `_sys/checks/check-*.bat` | 모두 제거 (직접 py 호출) |
| `_sys/temp_manual_gen.py` | 가비지 |
| `_sys/chatgpt/` | 미사용 전체 |
| `_sys/SYSTEM_ARCHITECTURE.md` | 구식 |
| `_sys/ai/infra.json` → 이동 후 원본 제거 | |
| `_sys/ai/collaboration_loop_bindings.json` | governance.json 흡수 |

### 4-4. 신규 생성

| 파일 | 목적 |
|------|------|
| `_sys/config/general/cli-resolve.json` | CLI 바이너리 경로 해석 (General) |
| `_sys/config/general/health-defaults.json` | 헬스 임계값 General 기본값 |
| `_sys/config/general/error-visibility.json` | 에러 표시 설정 |
| `_sys/config/general/system.json` | 통합 시스템 설정 |
| `_sys/config/peers/cli-overrides.json` | CLI 경로 Specific 오버라이드 |
| `_sys/config/integrations/hub-config.json` | 허브 설정 (hub_config.json 이동) |
| `_sys/peers/cc/peer.json` | cc 피어 식별자 |
| `_sys/peers/gc/peer.json` | gc 피어 식별자 |
| `_sys/peers/cx/peer.json` | cx 피어 식별자 |
| `_sys/peers/ag/peer.json` | ag 피어 식별자 |
| `_sys/protocol/general/ARCHITECTURE.md` | 신규 아키텍처 문서 |

---

## 5. 코드 변경 범위 (hub.py 기준)

### 5-1. 경로 참조 업데이트 (설정 기반으로 전환)

현재 hub.py가 하드코딩 또는 직접 조합으로 참조하는 경로들:

| 현재 패턴 | To-Be 접근 방식 |
|-----------|----------------|
| `Path(__file__).parent.parent / "ai" / "peers.json"` | `_load_config("config/peers/registry.json")` |
| `Path(__file__).parent.parent / "ai" / "orchestration.json"` | `_load_config("config/integrations/orchestration.json")` |
| `Path(__file__).parent.parent / "ai" / "protocol.json"` | `_load_config("config/protocol/protocol.json")` |
| `_sys/{peer_id}/health.json` 조합 | `_peer_sys_dir(peer_id) / "health.json"` → registry 기반 |
| `_sys/gemini/` (query dir 하드코딩) | `infra.json["ipc_paths"]["query_dir"]` |
| `_sys/ai/runtime-directives.jsonl` 하드코딩 | `infra.json["runtime_state"]["directives"]` |
| `_sys/ai/user-directives.md` 하드코딩 | `common/user-directives.md` → config 참조 |
| `_sys/ai/knowledge/` 하드코딩 | `infra.json["knowledge_root"]` |

### 5-2. status.json 참조 제거 대상

hub.py 내:
- `_sync_peer_gate_file()` → **삭제**
- `action_check_gate()` → `health.json availability.gate_open` 기반으로 재작성
- `action_peer_status()` gate 파일 읽기 코드 → **이미 완료** (live refresh에서 제거됨)
- `_load_peers()` 에서 `gate_cfg` 처리 → **제거**

외부 파일:
- `_sys/checks/check_health.py` → **삭제** (hub.py `health-update` 통합)
- `_sys/checks/_common.py::update_status_error()` → hub.py 경유로 교체
- `_sys/hooks/ai_check.py` → **삭제** (hub.py `check-gate --peer gc`)

---

## 6. 실행 계획

> 총 7개 Phase. 각 Phase 완료 후 pytest 통과 확인 후 다음 단계 진행.  
> ⚠️ gc HIGH 수정: 피어 디렉토리 이동(Phase 1)이 설정 중앙화(Phase 2)보다 먼저 — hub.py가 새 경로를 읽기 전에 실제 파일이 존재해야 함.

### 마이그레이션 전략 선택 결정 (gc+cx Round-3 확정)

> **ROOT SWAP (병렬 _sys_new/ 디렉토리) — REJECTED:**
> 이유 1 (gc CRITICAL): `_sys_new/`를 복사→수정→rename 시 git이 "거대 DELETE+ADD"로 처리 → 전체 파일 이력 소멸.
> 이유 2 (gc CRITICAL): `env/`+`tools/` = 500MB~1.5GB. USB에서 2배 복사 = IOPS 병목 + 공간 부족.
> 이유 3 (gc CRITICAL): cut-over 시 Claude/Gemini 프로세스 종료 필수 — 어떤 방식도 이를 피할 수 없음.
>
> **SUBST 재포인팅 — REJECTED:**
> host junction (`%USERPROFILE%\.claude → P:\_sys\claude\config\`)은 여전히 old 구조 참조.
> P:\ 재마운트로도 junction 재등록 불가피 → 이점 없음.
>
> **Git Branch In-Place (채택된 전략 — 유지):**
> git mv로 이력 보존 + 단일 브랜치 + 완성 후 main merge = conceptual "swap". 가장 안전.
> 개선: cut-over 순서를 "delete" → "rename backup" 방식으로 변경 (cx CRITICAL).

### Phase 0 — 사전 준비 (cx CRITICAL 반영: rollback 준비 필수)
```
1. git checkout -b feat/sys-restructure
2. python -m pytest _sys/tests/ -q  → 기준점 93 passed 확인
3. git stash (미커밋 변경 있을 시)
4. 현재 Junction 상태 기록 (복구 기준점):
   fsutil reparsepoint query P:\_sys\claude\config 2>&1 | findstr "Print Name"
   fsutil reparsepoint query P:\_sys\gemini\config 2>&1 | findstr "Print Name"
5. 피어 런타임 디렉토리 파일시스템 백업 (git이 무시하는 ignored 파일 포함):
   robocopy _sys\gemini _sys\._backup\gemini /E /XD .git
   robocopy _sys\claude _sys\._backup\claude /E /XD .git
   robocopy _sys\codex  _sys\._backup\codex  /E /XD .git
   robocopy _sys\antigravity _sys\._backup\antigravity /E /XD .git
6. runtime/recovery/ 생성 + 복구 스크립트 작성 (cx: 영구 홈):
   a) _sys/runtime/recovery/rollback.ps1:
      # junction 제거 → 디렉토리 역이동 → 원본 junction 재등록 → pytest 통과 확인
   b) _sys/runtime/recovery/cutover.ps1 (cx CRITICAL: rename-backup 방식):
      # 1. taskkill /f /im node.exe, python.exe (모든 피어 프로세스 강제 종료)
      # 2. $stamp = Get-Date -Format "yyyyMMddHHmmss"
      # 3. ⚠️ NEVER delete first — rename backup:
      #    Rename-Item _sys "_sys_old_rollback_$stamp"  (← NOT rm, NOT del)
      # 4. (git branch 방식에서는 이 단계 없음 — git merge main으로 대체)
      # 5. python _sys/core/virtualizer.py mount
      # 6. python _sys/runtime/cli/manage.py verify-all --mode post-cutover
      # 7. 검증 PASS → git commit (단일 커밋 완성)
      # 8. 검증 FAIL → rollback.ps1 실행
7. .gitignore 피어 경로 패턴 사전 업데이트 (cx HIGH: 이동 전 패턴 교체):
   Old 패턴 → New 패턴 (§Phase 7 목록 참조):
   _sys/gemini/config/** → _sys/peers/gc/runtime/config/**
   _sys/claude/config/** → _sys/peers/cc/runtime/config/**
   _sys/*/status.json   → _sys/peers/*/session_state.json (등)
8. 외부 caller 사전 감사 — status.json + check-*.bat 전체 참조:
   python -c "
   import subprocess, json
   r = subprocess.run(['rg', 'status\\.json|check-agents|check-health|ai_check',
     '--glob=*.bat', '--glob=*.json', '--glob=*.md', '--glob=*.py',
     '--glob=*.sh', '--glob=*.txt',
     '--exclude-glob=_sys/env/**', '--exclude-glob=_sys/tools/**',
     '-l', 'P:\\'], capture_output=True, text=True)
   files = r.stdout.strip().splitlines()
   print(f'{len(files)} files with references:')
   [print(' ', f) for f in files]
   "
   → 0건이 될 때까지 대안 경로 준비 후 Phase 3 진행
```

### Phase 1+2 — 피어 디렉토리 재구성 + 설정 중앙화 (gc/cx CRITICAL: 원자적 통합)

> ⚠️ **gc+cx CRITICAL:** Phase 1(파일 이동)과 Phase 2(hub.py 경로 업데이트)를 분리하면
> 중간 상태에서 hub.py가 새 경로 참조 + 파일은 구 경로 → pytest 실패 + 시스템 불능.
> 반드시 단일 세션에서 연속 실행, 하나의 커밋으로 완료할 것.

> ⚠️ **NEXT SESSION START 필수:** 이 Phase는 Claude Code가 시작되기 전 fresh shell에서 실행.
> Claude Code 실행 중에는 `_sys/claude/config/`가 active junction target → 이동 불가.

> ⚠️ **프리플라이트 체크 필수 (gc CRITICAL):**
> ```powershell
> # Claude/Gemini 프로세스 실행 중이면 중단
> if (Get-Process -Name "node","python","cmd" -ErrorAction SilentlyContinue | 
>     Where-Object { $_.CommandLine -match "claude|gemini|hub" }) {
>   Write-Error "ABORT: Active peer processes detected. Close all peers first."; exit 1
> }
> ```

```
--- PART A: 피어 디렉토리 이동 (hub.py 코드 변경 전) ---

1. _sys/peers/{cc,gc,cx,ag}/ 디렉토리 생성

2. _sys/gemini/ 선택적 이동 → _sys/peers/gc/
   이동 대상:  health.json, session_state.json
               config/  → peers/gc/runtime/config/
               project/ → peers/gc/runtime/project/
               templates/workspace.md → _sys/templates/peer/gc/workspace.md
   이동 제외:  gemini-status.bat, gemini-gate.bat, gemini-set-ratio.bat,
               gemini-usage.bat, status.json
               → 원본 _sys/gemini/에 Phase 3까지 보존 (삭제는 Phase 3에서)
   ⚠️ cx HIGH: 루트 문서들(GEMINI.md 등)의 old-path 참조도 이 단계에서 업데이트

3. _sys/claude/  → _sys/peers/cc/ (동일 패턴, claude-gate.bat/claude-status.bat 제외)
4. _sys/codex/   → _sys/peers/cx/
5. _sys/antigravity/ → _sys/peers/ag/

6. 각 peers/{id}/peer.json 신규 생성 (§3-3 peer.json 스키마 기반)

7. 호스트 Junction 재등록 (이동 직후 즉시):
   python _sys/core/virtualizer.py mount
   → %USERPROFILE%\.gemini → peers/gc/runtime/config/
   → %USERPROFILE%\.claude → peers/cc/runtime/config/

8. Junction 동작 확인: gemini --version, claude --version

--- PART B: 설정 중앙화 (파일이 존재한 후에 hub.py 경로 참조 교체) ---

9.  _sys/config/{general,peers,protocol,integrations}/ 생성

10. 신규 파일 생성:
    - config/general/system.json          (env_vars + tool_env_vars만 — 경로 없음)
    - config/general/cli-resolve.json     (§3-2 CLI 해석 설계)
    - config/general/health-defaults.json
    - config/general/error-visibility.json (hardcoded stderr fallback 포함)
    - config/general/runtimes.json
    - config/peers/cli-overrides.json

11. 기존 파일 이동:
    - _sys/config.json + env.json → config/general/system.json (merge)
    - _sys/paths.json → config/integrations/infra.json (경로 항목 병합)
    - _sys/runtimes.json → config/general/runtimes.json
    - _sys/dispatch.json → config/integrations/dispatch.json
    - _sys/context_menu.json → config/integrations/context-menu.json
    - _sys/ai/protocol.json → config/protocol/protocol.json
    - _sys/ai/peers.json → config/peers/registry.json (경량 인덱스만)
    - _sys/ai/orchestration.json → config/integrations/orchestration.json (크로스-피어)
    - _sys/ai/lifecycle_policy.json → config/protocol/lifecycle.json
    - _sys/ai/model_profiles.json → config/protocol/model-profiles.json
    - _sys/ai/governance_params.json + collaboration_loop_bindings.json → config/protocol/governance.json
    - _sys/ai/status_checks.json → config/integrations/status-checks.json
    - _sys/ai/traceability_map.json → config/integrations/traceability.json
    - _sys/ai/infra.json → config/integrations/infra.json (경로 전부 포함)
    - _sys/core/hub_config.json → config/integrations/hub-config.json
    - _sys/ai/knowledge/knowledge.config.json → config/protocol/knowledge-policy.json (cx 명칭 수정)

12. hub.py: 모든 Path(__file__).parent.parent / "ai" / "*.json" 하드코딩
    → _load_config(key) 헬퍼로 교체 (key → infra.json config_registry 참조)
    → ⚠️ cx MEDIUM: _sys 탐색 자체는 __file__ 기준 hardcode (infra.json 로드 전 bootstrap 필요)

13. _peer_sys_dir() → registry.json의 sys_subdir 기반으로 변경

14. pytest 통과 확인 (이 단계에서 실패 시 즉시 중단 + rollback-phase1.ps1 실행)

--- 단일 커밋 (gc CRITICAL: Phase 1+2를 하나의 커밋으로) ---
15. git add -p  (선택적 stage — 민감 파일 제외 확인)
16. git commit -m "feat(restructure): Phase 1+2 — peer dirs + config centralization [atomic]"
```

### Phase 2 — (Phase 1+2 통합으로 이 단계 삭제됨)

> Phase 2 내용은 위의 Phase 1+2 PART B에 통합됨 (gc/cx CRITICAL: 원자적 실행 필수).

### Phase 3 — 레거시 제거 (status.json 생태계)
```
사전 감사 (gc HIGH 반영):
  grep -r "check-agents\|check-deps\|check-health\|check-policy\|check-portability\|check-risk\|check-versions\|ai_check\|status\.json" \
    . --include="*.bat" --include="*.json" --include="*.md" --include="*.py" \
    --exclude-dir=env --exclude-dir=tools | grep -v ".pyc"
  → 모든 외부 caller 목록화 후 대체 경로 업데이트

1. hub.py: _sync_peer_gate_file() 삭제
2. hub.py: _load_peers()의 gate_cfg 처리 코드 제거
3. hub.py: action_check_gate() → health.json availability.gate_open 기반 재작성
4. _sys/hooks/ai_check.py 삭제 → 호출처를 `python core/hub.py check-gate --peer gc`로 교체
5. _sys/checks/check_health.py 삭제 (hub.py health-update 커버 확인)
6. _sys/checks/_common.py 삭제 (update_status_error → hub.py peer-quarantine)
7. _sys/checks/check-*.bat 모두 삭제 (감사 완료 후)
8. _sys/gemini/status.json 삭제:
   ※ status.json은 Phase 1에서 이동하지 않고 _sys/gemini/에 원본 보존됨 → 여기서 삭제
   ※ 삭제 전: rg "status\.json" --glob="*.bat" --glob="*.py" --glob="*.md" --glob="*.json" → 0건 확인
   ※ ⚠️ gc/cx HIGH: 31개 이상 참조가 실제로 있으면 아래 대안 고려:
   
   [대안: gc/cx 권장 — write-through cache 점진적 제거]
   If (rg "status.json" 참조 > 0):
     → hub.py가 health.json 업데이트 시 status.json도 동시에 write (호환 유지)
     → bat/py 참조를 한 파일씩 hub.py 명령으로 교체 후 status.json 의존성 제거
     → 의존성 0건 확인 후 status.json 삭제 (별도 커밋)
9. 레거시 bat 삭제 (아직 _sys/gemini/ _sys/claude/ 위치에 있음):
   - _sys/gemini/gemini-status.bat
   - _sys/gemini/gemini-gate.bat  (redirect stub)
   - _sys/gemini/gemini-set-ratio.bat  (redirect stub)
   - _sys/gemini/gemini-usage.bat
   - _sys/claude/claude-gate.bat  (dead code)
   - _sys/claude/claude-status.bat
10. config/peers/registry.json에서 gate 필드 완전 제거
11. config/integrations/status-checks.json: status.json → health.json 참조 업데이트
12. protocol/, peers/ 내 모든 문서 status.json 참조 → health.json 으로 교체
    grep -r "status\.json" _sys/ --include="*.md" → 0건 확인
13. pytest 통과 확인
```

### Phase 4 — 런타임 계층 재구성 (`runtime/`)
```
1. _sys/runtime/{cli,hooks,checks}/ 생성
2. _sys/cli/ → _sys/runtime/cli/
3. _sys/hooks/ → _sys/runtime/hooks/
4. _sys/checks/*.py (레거시 제외) → _sys/runtime/checks/
5. config/integrations/infra.json path_entries 업데이트:
   sys/cli → sys/runtime/cli
   sys/hooks → sys/runtime/hooks
   sys/checks → sys/runtime/checks
6. config/integrations/dispatch.json 모듈 경로 업데이트
7. pytest 통과 확인
```

### Phase 5 — 문서·지식·공통 재구성
```
1. _sys/ai/knowledge/ → _sys/knowledge/ (knowledge.config.json 제외 — Phase 2 완료)
2. _sys/docs/*.md → _sys/protocol/general/*.md (docs/Garbage/ 제외)
3. _sys/docs/protocol-codex.md → _sys/protocol/peer-specific/cx/CODEX.md
4. _sys/docs/protocol-antigravity.md → _sys/protocol/peer-specific/ag/AGY.md
5. _sys/ai/common/agents/ → _sys/common/agents/
6. _sys/ai/common/skills/ → _sys/common/skills/
7. _sys/ai/common/mcp/ → _sys/common/mcp/
8. _sys/ai/common/peer-rules.md → _sys/common/peer-rules.md
9. _sys/ai/user-directives.md → _sys/common/user-directives.md
10. _sys/ai/runtime-directives.jsonl → _sys/data/state/runtime-directives.jsonl
11. hub.py: knowledge_root, user-directives, runtime-directives 경로 → infra.json 기반
12. _sys/protocol/general/ARCHITECTURE.md 신규 작성
```

### Phase 6 — 가비지 정리
```
1. _sys/chatgpt/ — grep 확인 후 삭제 (참조 없으면):
   grep -r "chatgpt" . --include="*.py" --include="*.bat" --include="*.json" --include="*.md"
2. _sys/temp_manual_gen.py 삭제
3. _sys/SYSTEM_ARCHITECTURE.md 삭제
4. _sys/ai/ 디렉토리 (비어있으면) 삭제
5. _sys/local.config.bat.template → _sys/templates/workspace/
6. _sys/mock_peer/ → _sys/tests/mock_peer/
7. _sys/gemini/ _sys/claude/ _sys/codex/ _sys/antigravity/ 빈 디렉토리 삭제
8. 루트 PROTOCOL.md 경로 참조 업데이트
9. 루트 CLAUDE.md, GEMINI.md 경로 참조 업데이트
```

### Phase 6.5 — 완결적 점검 (verify-all) — cx Round-3 설계

> **목적**: 최종 merge/commit 전 "완전히 완료됨" 여부를 기계적으로 확인.
> **명령**: `python _sys/runtime/cli/manage.py verify-all --sys-dir _sys --mode pre-commit`
> **설정**: `_sys/config/integrations/verify-config.json` (cx: JSON-driven 검증 정책)
> **결과**: 항목별 `[PASS]` / `[FAIL: REASON]`, exit code 0 or 1.
>
> **2-gate 검증 (cx CRITICAL)**:
> - **Gate 1 (pre-commit)**: merge/commit 전 실행 — 구조+경로+JSON+테스트
> - **Gate 2 (post-commit)**: main merge 후 실행 — junction+health+실제 경로 확인
>   일부 버그는 실제 `_sys/` 경로에서만 발생 (`Path(__file__).parent.parent` 등)

```
V1. 디렉토리 구조 체크:
    - _sys/에 정확히 12개 소스 소유 root 디렉토리 (예외: .pytest_cache, __pycache__ 제외)
    - 허용 목록: config, core, peers, knowledge, protocol, runtime, common, templates, tests, data, env, tools
    - 명령: Get-ChildItem _sys -Directory | Select-Object Name

V2. 구 경로 참조 제로 체크:
    - 대상: _sys/gemini, _sys/claude, _sys/codex, _sys/antigravity, _sys/ai, status.json
    - 명령: rg "_sys/(gemini|claude|codex|antigravity|ai)|status\.json" 
            --glob="*.py" --glob="*.bat" --glob="*.json" --glob="*.md"
            --exclude-glob="env/**" --exclude-glob="tools/**" --exclude-glob="data/logs/**"
            --exclude-glob="docs/Garbage/**"
    - 허용 예외: migration-history 문서, DEBATE_LOG.md 내 과거 기록

V3. JSON 무결성 체크:
    - 모든 _ref, _extends, _doc 필드 대상 경로가 실제 파일로 존재
    - 모든 JSON 파일이 valid JSON (json.loads 통과)
    - 명령: python _sys/runtime/checks/check_json_integrity.py --sys-dir _sys

V4. Junction 대상 존재 체크 (pre-commit: 존재 여부만):
    - _sys/peers/cc/runtime/config/ 존재
    - _sys/peers/gc/runtime/config/ 존재
    - _sys/peers/cx/runtime/config/ 존재
    - _sys/peers/ag/runtime/config/ 존재

V5. 테스트 스위트 (Gate 1):
    - PORTABLE_SYS_DIR 환경변수로 경로 주입 가능 여부 확인
    - python -m pytest _sys/tests/unit -q
    - 기준: 93+ passed, 0 failed

V6. hub.py 부트스트랩 체크:
    - python _sys/core/hub.py peer-status --json → exit 0
    - config/integrations/infra.json 로드 확인
    - infra.json 실패 시 __file__ fallback 동작 확인

V7. JSON 스키마 검증:
    - _schema 필드를 가진 모든 JSON을 knowledge/schemas/{schema}.json 으로 검증
    - 스키마 없는 경우: lint만 (valid JSON 확인)

V8. 피어 상태 체크 (Gate 2 only — junction 재등록 후):
    - python _sys/core/hub.py health-update --all
    - python _sys/core/hub.py peer-status
    - 기준: enabled 피어 모두 OPEN 또는 알려진 외부 오류(quota/auth)만

V9. Traceability 일관성:
    - python _sys/runtime/cli/manage.py gen-traceability --check
    - 커밋된 config/integrations/traceability.json과 auto-gen 결과 diff
    - 기준: diff 0줄 (또는 의도적 수동 추가 항목만)

V10. git 상태 클린:
    - git status --porcelain=v1 → 예상치 못한 변경 없음
    - git ls-files --others --exclude-standard → 의도치 않은 untracked 파일 없음
    - .gitignore가 모든 peer runtime 경로 커버 확인

--- verify-all 실패 시 롤백 절차 (cx 설계) ---
Step 1: 상태 파악
  Test-Path _sys
  Get-ChildItem -Directory -Filter "_sys_old_rollback_*"  (root swap 방식의 경우)
  python _sys/core/hub.py peer-status

Step 2: 복구 (git branch 방식)
  git stash (또는 git reset --hard HEAD)
  python _sys/core/virtualizer.py mount (원본 junction 재등록)
  python -m pytest _sys/tests/ -q

Step 3: 검증
  python _sys/core/hub.py peer-status
  git status
```

### Phase 7 — 연결성·추적성 최종화
```
전수 경로 참조 검증:
  rg "_sys/gemini|_sys/claude|_sys/codex|_sys/antigravity|_sys/ai|status\.json" \
    --glob="*.py" --glob="*.bat" --glob="*.md" --glob="*.json" \
    --exclude-glob="_sys/env/**" --exclude-glob="_sys/tools/**" \
    --exclude-glob="_sys/data/sessions/**" --exclude-glob=".git/**"
  → 0건 나올 때까지 수정
  ※ cx LOW: _sys/docs/Garbage/, 구 taxonomy 파일, 마이그레이션 로그는 예외 처리

1. .gitignore 전면 재작성 (cx HIGH — 피어 경로 이동으로 전 패턴 파손):
   제거할 old 패턴:
     _sys/*/project/settings.local.json  →  _sys/peers/*/runtime/project/settings.local.json
     _sys/*/status.json                  →  (삭제됨 — 패턴 제거)
     _sys/*/usage.json                   →  _sys/peers/*/usage.json
     _sys/*/session-id.txt               →  _sys/peers/*/runtime/session-id.txt
     _sys/*/session-map.json             →  _sys/peers/*/runtime/session-map.json
     _sys/*/session.lock                 →  _sys/peers/*/runtime/session.lock
     _sys/*/session_state.json           →  _sys/peers/*/session_state.json
     _sys/*/cq-*.txt                     →  _sys/peers/*/cq-*.txt
     _sys/mock_peer/                     →  _sys/tests/mock_peer/
     _sys/claude/config/**               →  _sys/peers/cc/runtime/config/**
     _sys/gemini/config/**               →  _sys/peers/gc/runtime/config/**
     _sys/codex/config/**                →  _sys/peers/cx/runtime/config/**
     _sys/antigravity/config/**          →  _sys/peers/ag/runtime/config/**
     !_sys/antigravity/config/bin/agentapi.bat  →  !_sys/peers/ag/runtime/config/bin/agentapi.bat
     _sys/gemini/config.json             →  (삭제됨 — peers/gc/runtime/config/에 합류)
   ⚠️ 변경 후 즉시 git status 확인 — 예기치 않게 tracked/untracked된 파일 없는지 검사

2. config/integrations/traceability.json 업데이트:
   ⚠️ gc/cx MEDIUM: 전체 파일 수동 유지 대신 자동 생성 권장:
   python _sys/runtime/cli/manage.py gen-traceability \
     --scan-dirs config/ protocol/ peers/ knowledge/ core/ runtime/ \
     --extract-fields "_schema,_extends,_ref,_doc" \
     --output config/integrations/traceability.json
   → 수동으로 유지할 항목: critical path 매핑 (5~10개) + 나머지는 auto-gen

3. config/integrations/infra.json config_registry 재작성 (모든 경로 최신화)

4. tests/ 내 경로 상수 업데이트:
   - test_hub.py: _peer_sys_dir() 참조 → registry.json 기반
   - TestKnowledgePropagation: knowledge_root 경로 → infra.json 기반

5. pytest 최종 통과 확인 (93+ passed)

6. rollback 백업 삭제: rmdir /s /q _sys\._backup

7. git add + commit (단일 "chore(restructure): Phase 7 — traceability + grep verification")

8. PR 생성 (feat/sys-restructure → main)
```

---

## 7. 연결성·추적성 유지 전략

### 7-1. 단일 진실 소스 체인

```
PROTOCOL.md (루트 인덱스)
  → _sys/protocol/general/ARCHITECTURE.md (구조 설명)
    → _sys/config/integrations/traceability.json (기계 추적)
      → 각 설정 파일의 _schema, _extends, _ref 필드
        → 해당 설정을 읽는 hub.py 함수
          → hub.py 함수를 검증하는 tests/
```

### 7-2. JSON 연결자 패턴 (모든 설정 파일 준수)

```jsonc
{
  "_schema": "schema-name/v1",        // 소속 스키마
  "_extends": "path/to/general.json", // General 레이어 참조
  "_ref": "path/to/other.json#key",   // 다른 설정 키 참조
  "_doc": "protocol/general/X.md",    // 관련 문서 참조
  // ... 실제 내용
}
```

### 7-3. 에러 발생 시 추적 경로

```
에러 발생 → core/hub.py
  → config/general/error-visibility.json (형식·경로 읽기)
  → stderr 출력 (사용자 즉시 인지)
  → data/logs/errors.jsonl (구조화 로그)
  → knowledge/logs/knowledge-errors.jsonl (지식 시스템 에러)
사용자 조치: hint 메시지 → config/integrations/infra.json 또는 config/peers/registry.json
```

---

## 8. 리스크 분석 (gc+cx Round 1~3 전체 반영)

| 심각도 | 리스크 | 영향 | 완화 |
|--------|--------|------|------|
| CRITICAL | Claude Code 실행 중 junction 이동 | _sys/claude/config/ 파손 → 세션 불능 | Phase 1+2는 반드시 next-session fresh start + cutover.ps1 프리플라이트 process check |
| CRITICAL | Phase 1(이동) + Phase 2(hub.py 업데이트) 분리 커밋 | 중간 상태에서 pytest 전면 실패 | Phase 1+2 단일 원자 커밋 (§Phase 1+2 통합) |
| CRITICAL | rollback 미비 — git만으로 불충분 | ignored 런타임 파일 + host junction 복구 불가 | Phase 0에서 filesystem backup + runtime/recovery/rollback.ps1 생성 |
| CRITICAL | cut-over "delete _sys 후 rename" 순서 오류 | 실패 시 _sys 없음 → 복구 불가 | cutover.ps1: rename backup 먼저 (Rename-Item _sys _sys_old_rollback_$stamp) → rename new → 검증 → 실패 시 rollback.ps1 |
| HIGH | verify-all 단일 gate로 일부 버그 미감지 | 실제 경로에서만 나타나는 버그 누락 | 2-gate: pre-commit (V1~V5+V7+V9+V10) + post-commit (V6+V8) |
| HIGH | status.json 31+개 일괄 제거 blast radius | 참조 파일 실행 불능 | write-through cache 전략 (§Phase 3 대안) |
| HIGH | .gitignore 패턴 전면 파손 | tracked/untracked 파일 혼란 | Phase 0에서 사전 업데이트 (§Phase 7 목록) |
| HIGH | CLAUDE.md/GEMINI.md old-path 하드코딩 | AI 피어에 구 경로 노출 → 잘못된 명령 실행 | Phase 1+2에서 루트 문서 동시 업데이트 |
| HIGH | Junction 재등록 누락 | 피어 CLI 실행 불가 | Phase 1+2 PART A step 7 즉시 검증 + verify-all V4/V8 |
| HIGH | hub.py 경로 참조 누락 | 런타임 오류 | Phase별 pytest 통과 게이트 + verify-all V5/V6 |
| MEDIUM | status.json 참조가 skills/agents에도 있음 | Phase 0 감사 범위 미달 | Phase 0 grep에 모든 파일 타입 포함 |
| MEDIUM | traceability.json 수동 유지 drift | 추적성 루프 파손 | auto-gen 스크립트로 대체 + verify-all V9 |
| MEDIUM | knowledge-policy.json vs knowledge/index.json 혼동 | 설정 레이어 오염 | 명칭 분리 + _doc 필드로 역할 명시 |
| MEDIUM | infra.json 자체 로드 실패 시 bootstrap 불능 | hub.py 시작 불가 | __file__ 기준 _sys 경로 hardcode fallback |
| MEDIUM | env/tools (500MB~1.5GB) 백업 시 USB IOPS 병목 | Phase 0 backup이 수분 소요 | 백업에서 env/ tools/ 제외 (git 미추적, 업데이트 자유) |
| LOW | Phase 7 grep의 archive/garbage 파일 오탐 | "0건" 달성 불가 | --exclude-glob 명시적 제외 목록 |
| LOW | git rename 감지 미신뢰 | blame/log 이력 누락 | tracked 파일은 git mv 사용; 생성/런타임 파일은 이력 불필요로 수용 |
| LOW | 브랜치 merge 충돌 | 진행 중 변경과 충돌 | Phase 0에서 브랜치 격리 |

---

## 9. MUST-DO / MUST-NOT 경계 (gc+cx 끝장검토 확정)

### 절대 해야 하는 것 (MUST-DO)

| 우선순위 | 항목 | 근거 |
|---------|------|------|
| P0 | Phase 1+2 시작 전 프리플라이트 process check (claude/gemini 실행 여부) | gc CRITICAL |
| P0 | Phase 0에서 filesystem backup (_sys/._backup/) + rollback-phase1.ps1 생성 | cx CRITICAL |
| P0 | Phase 0에서 .gitignore 사전 업데이트 (피어 이동 전 패턴 교체) | cx HIGH |
| P0 | Phase 0에서 status.json 참조 전수 감사 (모든 파일 타입) | gc HIGH |
| P1 | Phase 1+2 단일 원자 커밋 — 분리 금지 | gc/cx CRITICAL |
| P1 | Junction 재등록 후 CLI 동작 즉시 검증 (gemini --version, claude --version) | gc CRITICAL |
| P2 | hub.py에 _sys 경로 hardcode bootstrap fallback (__file__ 기준) | cx MEDIUM |
| P2 | hub.py error-visibility.json try-except hardcoded fallback | gc HIGH |
| P3 | status.json 삭제 전 rg 0건 확인 (또는 write-through cache 전략 적용) | gc/cx HIGH |
| P7 | .gitignore 전면 재작성 후 git status로 unintended changes 없음 확인 | cx HIGH |
| P7 | traceability.json auto-gen 스크립트 실행 | gc/cx MEDIUM |

### 절대 하지 말아야 하는 것 (MUST-NOT)

| 항목 | 결과 | 근거 |
|------|------|------|
| Claude Code 실행 중 _sys/claude/config/ 이동 | 세션 파괴 (불복구) | cx CRITICAL |
| Phase 1 이동 + Phase 2 hub.py 업데이트를 별도 커밋으로 분리 | 중간 broken state | gc/cx CRITICAL |
| cut-over에서 _sys/ 먼저 삭제 ("delete then rename") | 실패 시 _sys/ 없음 → 복구 불가 | cx CRITICAL |
| verify-all 단일 gate (pre-commit만) | 실제 경로에서만 나타나는 버그 누락 | cx CRITICAL |
| JSON 파일을 naive 문자열 치환으로 경로 업데이트 | 구조 파손 | cx HIGH |
| rollback plan 없이 Phase 1 시작 | 복구 불가 | cx CRITICAL |
| status.json을 31개 참조 감사 전 삭제 | 다수 스크립트 실행 불능 | gc/cx HIGH |
| peer.json과 registry.json에 동일 필드 중복 | 유지 drift → MECE 위반 | gc HIGH |
| traceability.json 전체를 수동으로만 유지 | 필연적 drift → 추적성 루프 파손 | gc/cx MEDIUM |
| env/ tools/ 디렉토리를 Phase 0 filesystem backup에 포함 | USB IOPS 병목 + 공간 부족 | gc Round-3 |

---

## 10. 검토 요청 사항 (피어 교차검토 — gc+cx 완료)

1. `config/` General-Specific 분리 구조 — MECE 위반 있는가?
   → ✅ 해결: config/ = 시스템전역 공유 설정, peers/{id}/ = 피어-로컬 운영 매니페스트. 경계 §3-3에 명시.
2. `peers/{id}/peer.json` 식별자 파일 — 중복 필드 있는가? (registry.json과 overlap)
   → ✅ 해결: registry.json = {node_id, sys_subdir, enabled} 3개 필드만. 나머지 전부 peer.json 전용.
3. `runtime/` 통합 (cli+hooks+checks) — 기능 경계가 명확한가?
   → ✅ 유지: cli/=진입점래퍼, hooks/=이벤트훅, checks/=상태검증. 각 독립, bat 래퍼 없음.
4. Phase 실행 순서 — 의존성 위반 있는가?
   → ✅ 해결: Phase 1+2 원자적 통합 (§Phase 1+2). 분리 커밋 절대 금지.
5. status.json 제거 후 `ai_check.py` 역할을 hub.py가 100% 대체하는가?
   → ✅ 확인: hub.py check-gate --peer gc 동일 역할. write-through cache 대안 §Phase 3에 추가.
6. `common/` 스코프 — 교차-워크스페이스 공간으로 충분한가?
   → ✅ 유지: user-directives.md + peer-rules.md + agents/ + skills/ + mcp/ 포함.
