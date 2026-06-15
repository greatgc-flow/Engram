# _sys Restructure Plan — v1.0

> Status: DEBATE_FINAL_R6 — gc+cx 6-round 끝장 교차검토 완료 (2026-06-15)
> Date: 2026-06-14 (updated 2026-06-15 R6)
> Author: cc (coordinator), gc (cross-reviewer R1+R3+R4+R5), cx (independent auditor R2+R3+R5+R6)
> Protocol: R:10 (Brain Sync) — 전체 피어 끝장 플랜
> Review: R4: Root Swap ADOPTED, IPC 설계, 글루파일 slim화 | R5: MECE 통합 (pathmap 제어 평면, managed-links 등) | R6: 트랜잭션 완결 (op journal, SHA256 타이밍 수정, lock schema, bootstrap 시퀀스, quarantine lifecycle, invariant coverage matrix)
> ⚠️ FINAL: ALL MECE INVARIANTS I-01~I-10/N-01~N-08 이행 완료, EXECUTION READY

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
    ├── infra.json                     # ⚠️ 글로벌 매크로 루트만 (R5: 역할 축소)
    │                                  #    paths.json 흡수. ipc_paths → peer.json.ipc 위임
    │                                  #    실제 경로: base_dirs, config_registry 매크로만
    ├── path-map.json                  # 🆕 정션 IaC 선언 (MECE Path_Map.json 역할)
    │                                  #    APP_HARDCODED_EXCEPTIONS: cc/gc/cx/ag 호스트 정션
    │                                  #    BACKUP_POLICY: ipc/, env/, tools/ 제외 명시
    └── hub-config.json                # 허브 한도 설정 (was core/hub_config.json)
```

> **system.json / infra.json / path-map.json 역할 분리 (gc R5: 3-way 분리):**
> - `system.json` = 환경 플래그·변수만 (env_vars, tool_env_vars)
> - `infra.json` = 글로벌 매크로 루트만 (`base_dirs`, `config_registry`). IPC 경로는 각 `peer.json.ipc`로 위임.
> - `path-map.json` = 🆕 정션 IaC 선언 (MECE Path_Map.json). 호스트 정션 desired state SSOT.
>
> **path-map.json 예시 (R5 신규 — MECE §5.1 기반):**
> ```jsonc
> // config/integrations/path-map.json
> {
>   "_schema": "pathmap/v1",
>   "RUNTIME": {
>     "SYS_ROOT": "${AUTO_DETECT}",   // hub.py __file__ 기반 동적 감지 (P:\ 하드코딩 금지)
>     "PEERS_ROOT": "${SYS_ROOT}/peers"
>   },
>   "APP_HARDCODED_EXCEPTIONS": [
>     {
>       "entry_id": "cc-config-junction",
>       "app_required_path": "${USERPROFILE}/.claude",
>       "ssot_origin": "${PEERS_ROOT}/cc/runtime/config",
>       "link_type": "dir_junction",
>       "risk_level": "HIGH",
>       "requires_explicit_apply": true,
>       "description": "Claude Code reads ~/.claude — outward junction to portable SSOT"
>     },
>     {
>       "entry_id": "gc-config-junction",
>       "app_required_path": "${USERPROFILE}/.gemini",
>       "ssot_origin": "${PEERS_ROOT}/gc/runtime/config",
>       "link_type": "dir_junction",
>       "risk_level": "HIGH",
>       "requires_explicit_apply": true,
>       "description": "Gemini CLI reads ~/.gemini — outward junction to portable SSOT"
>     }
>   ],
>   "BACKUP_POLICY": {
>     "include": ["${SYS_ROOT}/peers", "${SYS_ROOT}/config", "${SYS_ROOT}/protocol",
>                 "${SYS_ROOT}/knowledge", "${SYS_ROOT}/common", "${SYS_ROOT}/data"],
>     "exclude": ["${SYS_ROOT}/peers/*/ipc", "${SYS_ROOT}/env", "${SYS_ROOT}/tools",
>                 "${SYS_ROOT}/data/state/pathmap/pathmap.lock"],
>     "junction_traversal": "skip"
>   }
> }
> ```
>
> **peer.json.ipc 경로 (infra.json ipc_paths 대체 — R5):**
> 각 `peers/{id}/peer.json` 의 `ipc.inbox_path` / `ipc.history_path` 가 유일한 권위.
> hub.py는 `_load_peer(id).ipc.inbox_path` 로 동적 해석 (infra.json 중복 제거).

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
│   ├── ipc/                           # 🆕 피어 전용 IPC (was _sys/gemini/ 혼재 → 분리)
│   │   ├── inbox/                     # 수신 쿼리 파일 (hub.py가 여기서 픽업)
│   │   └── history/                   # 처리 완료 쿼리 아카이브 (capture 후 이동)
│   └── runtime/                       # 피어 런타임 설정
│       ├── config/                    # Junction 대상 (was _sys/claude/config/)
│       └── project/                   # 프로젝트 설정 (was _sys/claude/project/)
├── gc/                                # Gemini CLI (was _sys/gemini/)
│   ├── peer.json
│   ├── health.json
│   ├── session_state.json
│   ├── ipc/                           # 🆕 gc 전용 IPC
│   │   ├── inbox/                     # (was _sys/gemini/{gc-timestamp-rand}.txt)
│   │   └── history/
│   └── runtime/
│       ├── config/                    # was _sys/gemini/config/
│       └── project/                   # was _sys/gemini/project/
├── cx/                                # Codex (was _sys/codex/)
│   ├── peer.json
│   ├── health.json
│   ├── session_state.json
│   ├── ipc/                           # 🆕 cx 전용 IPC
│   │   ├── inbox/
│   │   └── history/
│   └── runtime/
│       ├── config/                    # was _sys/codex/config/
│       └── project/                   # was _sys/codex/project/
└── ag/                                # Antigravity (was _sys/antigravity/)
    ├── peer.json
    ├── health.json
    ├── ipc/                           # 🆕 ag 전용 IPC
    │   ├── inbox/
    │   └── history/
    └── runtime/
        ├── config/                    # was _sys/antigravity/config/
        └── project/
```

> **IPC 구조 변경 이유 (As-Is → To-Be):**
> - As-Is: 모든 피어 쿼리 파일이 `_sys/gemini/` 한 폴더에 혼재 → 피어 구분 불가, 청소 어려움
> - To-Be: `peers/{id}/ipc/inbox/` 피어별 전용 inbox → hub.py가 to-peer 기준으로 직접 라우팅
> - 처리 완료 쿼리: inbox/에서 history/로 이동 (cleanup_policy: "archive_on_capture")
> - .gitignore: `_sys/peers/*/ipc/` 전체 무시 (런타임 임시 파일)

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
  "ipc": {
    "inbox_path": "ipc/inbox",                      // peers/gc/ipc/inbox/ — 수신 쿼리 위치
    "history_path": "ipc/history",                  // 처리 완료 쿼리 아카이브
    "cleanup_policy": "archive_on_capture"           // capture 즉시 inbox→history 이동
  },
  "host_junction": {
    "host_env": "USERPROFILE",
    "host_dirname": ".gemini",
    "portable_subpath": "runtime/config"
  },
  "project_junction": { "portable_subpath": "runtime/project" },
  "glue_file": "runtime/config/GEMINI.md",          // slim 운영 stub (sync-glue로 생성)
  "glue_source": "protocol/peer-specific/gc/GEMINI.md", // canonical 원본 문서
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
| `core/` | **내부 API·엔진** — import 가능, side-effect 없음 | `hub.py`, `launcher.py`, `provisioner.py`, `registrar.py`, `relocator.py`, `virtualizer.py`(pathmap 시맨틱: preflight/plan/apply+lock+journal+audit/status/prune/recover/doctor), `scrubber.py`, `dispatcher.py` |
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

### 3-7c. IPC 구조 설계 — 피어 전용 수신함 (R4 신규)

> **As-Is 문제**: 모든 피어 쿼리 파일이 `_sys/gemini/` 단일 폴더에 혼재.
> 피어 구분이 파일명의 `{peer_id}-` 프리픽스에 의존 → 청소 정책 없음 → 누적 오염.

```
infra.json  →  "ipc_paths": {
  "cc_inbox": "peers/cc/ipc/inbox",
  "gc_inbox": "peers/gc/ipc/inbox",
  "cx_inbox": "peers/cx/ipc/inbox",
  "ag_inbox": "peers/ag/ipc/inbox"
}
```

**hub.py 변경 (R4):**
- `action_ask`: 쿼리 파일을 `infra.json["ipc_paths"]["{peer_id}_inbox"]` 경로에 생성
- 응답 capture 후: inbox 파일을 `peers/{id}/ipc/history/` 로 이동 (archive_on_capture)
- 구 경로 `_sys/gemini/{peer}-*.txt` → `peers/{id}/ipc/inbox/{timestamp}-{rand}.txt`

**파일명 규칙 (변경 없음):** `{timestamp}-{rand4}.txt` (peer_id는 경로에 이미 포함)

**IPC .gitignore 패턴 (신규):**
```gitignore
# IPC inbox/history (런타임 임시, 커밋 불필요)
_sys/peers/*/ipc/inbox/
_sys/peers/*/ipc/history/
```

### 3-7d. 글루파일 Slim 설계 — 운영 stub + 정규 문서 분리 (R4 신규)

> **As-Is 문제**: `_sys/gemini/config/GEMINI.md` (또는 `_sys/claude/config/CLAUDE.md`)가
> 실제 지침 전체를 직접 포함 → 경로 하드코딩, 다른 문서와 내용 중복, 수동 유지 drift.

**설계 원칙:**
- **정규 문서** (`protocol/peer-specific/{id}/`): 실제 지침의 단일 진실 소스. 사람이 편집.
- **운영 stub** (`peers/{id}/runtime/config/{PEER}.md`): hub.py가 자동 생성하는 slim 파일.
  피어가 실제로 읽는 파일 = junction 대상 = 정규 문서 참조 + 현재 상태 변수만 포함.

**운영 stub 예시** (`peers/gc/runtime/config/GEMINI.md` — auto-generated):
```markdown
<!-- AUTO-GENERATED by hub.py sync-glue --peer gc. Do not edit manually. -->
<!-- Source: protocol/peer-specific/gc/GEMINI.md -->

{canonical 문서 핵심 내용 포함 또는 직접 include}

<!-- Runtime overrides (hub.py가 주입) -->
SYS_ROOT: P:\_sys
IPC_INBOX: P:\_sys\peers\gc\ipc\inbox
HEALTH_FILE: P:\_sys\peers\gc\health.json
```

**hub.py 명령 (R4 신규):**
```
python core/hub.py sync-glue --peer gc        # gc 글루파일 재생성
python core/hub.py sync-glue --all            # 전 피어 일괄 재생성
python core/hub.py sync-glue --check          # stub가 canonical과 sync된 상태인지 검증
```

**peer.json 연결:**
```jsonc
{
  "glue_file":   "runtime/config/GEMINI.md",         // 운영 stub (junction 대상)
  "glue_source": "protocol/peer-specific/gc/GEMINI.md" // canonical 원본
}
```

> **glue_source 철학**: canonical 문서는 `protocol/peer-specific/{id}/` 에서 사람이 관리.
> stub는 hub.py가 필요 시 재생성 — 수동 편집 금지. verify-all V13에서 sync 확인.

### 3-7e. pathmap 제어 평면 — 정션 IaC + 레지스트리 (R5 신규, gc+cx CRITICAL)

> **MECE 스펙 §2.5 INVARIANT I-03/I-04/I-05/I-09 이행:**
> 모든 관리된 정션은 registry에 등록, 모든 mutating 명령은 lock 후 실행, 완료 후 audit.

**신규 파일 목록:**

```
config/integrations/path-map.json          # 정션 IaC 선언 (desired state SSOT)
data/state/pathmap/
├── managed-links.json                     # 실제 생성된 정션 레지스트리 (actual state + 삭제권)
│   primary key: relative_link_path (드라이브 레터 독립 상대경로)
│   host_specific: true → 다른 호스트에서 orphan 판정 제외
├── pathmap.lock                           # 뮤텍스 잠금 (동시 실행 방지)
└── pathmap-audit.jsonl                    # mutating 명령 감사 로그 (90일/50MB 보존)
data/inbox/                                # 분류 미결정 임시 항목 버퍼 (MECE [00_Inbox] 역할)
```

**managed-links.json 예시 (R5):**
```jsonc
{
  "schema_version": "1.0",
  "drive_root_at_last_write": "P:/",   // 드라이브 레터 변경 감지용
  "entries": {
    "cc-config-junction": {
      "relative_link_path": "EXTERNAL:%USERPROFILE%/.claude",
      "relative_target_path": "peers/cc/runtime/config",
      "link_type": "dir_junction",
      "entry_id": "cc-config-junction",
      "host_specific": true,           // 다른 호스트에서 orphan 제외
      "created_at": "..."
    },
    "gc-config-junction": {
      "relative_link_path": "EXTERNAL:%USERPROFILE%/.gemini",
      "relative_target_path": "peers/gc/runtime/config",
      "link_type": "dir_junction",
      "entry_id": "gc-config-junction",
      "host_specific": true,
      "created_at": "..."
    }
  }
}
```

**virtualizer.py 의무 시맨틱 (pathmap 내재화 — R5+R6):**
```
기존: virtualizer.py mount → 정션 생성 (registry 없음)
신규: virtualizer.py → pathmap 시맨틱 내재화
  preflight: path-map.json 검증 + FS 준비 상태 확인
             entry_id 중복 → ABORT (cx R6: schema validation 필수)
             link_path 중복, APP exception path 중복도 동일하게 거부
  plan:      dry-run (정션별 예상 동작 출력)
  apply:     ① lock 획득
             ② operation journal append: {op_id, state: "planned", entry_id, ...}
             ③ 정션 생성
             ④ journal update: {state: "fs_created"}
             ⑤ managed-links.json 원자적 갱신 (temp 파일 write → rename)
             ⑥ journal update: {state: "registry_committed"}
             ⑦ audit append
             ⑧ journal update: {state: "audit_committed"} → op complete
             ⑨ lock 해제
             ⚠️ 크래시 복구: hub.py 시작 시 journal에서 미완성 op 탐지 → recover 실행
  status:    managed-links.json + FS 실제 상태 비교 출력
  prune:     managed orphan 탐지 (registry에 있고 path-map.json에 없음)
  prune --apply: ① lock + journal planned
                 ② 물리 삭제 확인 (reparse-aware: 정션 내부 재귀 금지)
                 ③ journal: fs_deleted → registry 제거 → audit → lock 해제
                 ④ 물리 삭제 성공 + registry 쓰기 FAIL → managed_orphan_already_absent 상태로 분류 후 재시도
  recover:   journal에서 미완성 op 탐지 → fs_created but registry_not_committed → 정션 롤백 후 audit
  doctor:    full system preflight (managed-links 일관성, lock staleness, journal 무결성)
```

**pathmap.lock 스키마 (R6 cx):**
```jsonc
{
  "pid": 1234,
  "host": "MY-PC",
  "started_at": "2026-06-15T15:33:48.123Z",
  "command": "apply",
  "operation_id": "a1b2c3d4-..."
}
// stale-lock 감지 (hub.py 시작 시):
//   pid 프로세스 부재 AND age > 30분 → auto-release + audit entry "stale_lock_released"
//   pid 부재지만 age < 30분 → 경고 only (crash 직후 가능성)
```

**path-map.json vs managed-links.json 권위 행렬 (R6 cx):**
```
path-map.json (desired state SSOT):
  - 추가/변경 의도 소스 — 이것이 없으면 apply 불가
managed-links.json (actual state + 삭제권):
  - 생성 증거 소스 — 이것이 없으면 prune 불가
충돌 규칙:
  - managed-links에 있고 path-map에 없음 → prune 대상 (의도적 삭제)
  - path-map에 있고 managed-links에 없음 → apply 대상 (미생성)
  - 둘 다 있음 → status 비교 (FS 실재 확인)
  - managed-links에만 있고 FS도 없음 → managed_orphan_already_absent (registry만 제거)
```

**Day-1 Bootstrap 시퀀스 (R6 cx — 신규 머신 최초 실행):**
```
1. SYS_ROOT 감지: hub.py __file__ 기준 (P:\ 하드코딩 절대 금지)
2. data/state/pathmap/ 생성 (없으면)
3. managed-links.json 초기화 (없으면): {"schema_version":"1.0","entries":{}}
4. pathmap.lock 부재 확인 (있으면 staleness 체크)
5. path-map.json 로드 + schema validate + entry_id 중복 검사
6. virtualizer.py doctor (전체 preflight)
7. virtualizer.py plan (dry-run 출력 — 사용자 검토)
8. 사용자 확인 후: virtualizer.py apply (MECE N-07: 자동 적용 금지)
```

**Ghost Junction 방지 (cc CRITICAL 발견):**
- Cut-over Step 9 (rename _sys→backup) 완료 후 Step 11 (virtualizer.py mount) 실패 시:
  `%USERPROFILE%\.gemini` 이 `_sys_old_rollback_.../peers/gc/runtime/config/` 를 여전히 가리킴
- rollback.ps1 필수 로직: 
  ```powershell
  # 1. _sys 삭제 (방금 rename된 _sys_new)
  # 2. _sys_old_rollback_* → _sys 역rename
  # 3. ⚠️ 반드시 junction 재등록!
  python _sys/core/virtualizer.py apply --force  # managed-links.json 기반 재생성
  # 4. pathmap status → 모든 정션 OK 확인
  ```

**Cloud Sync 위험 (MECE N-06 — R5 신규):**
- `_sys/peers/{id}/runtime/config/` 가 OneDrive/Dropbox 동기화 범위에 포함 시:
  정션 내용이 일반 폴더로 처리 → 원본 파일 전체 업로드 또는 무한루프 위험
- `.gitignore` + 클라우드 동기화 제외 설정 모두 필요
- 권고: `.cloudignore` / OneDrive의 "이 폴더는 동기화에서 제외" 설정 필수 확인

### 3-7f. IPC inbox 실패 라이프사이클 (R5 보완)

> §3-7c 보완 — 성공 경로만 있던 IPC 설계에 실패 모드 추가 (cx HIGH).

```
정상 경로: hub.py가 inbox/ 생성 → 피어 읽기 → hub.py capture → history/ 이동
실패 모드:
  F1. hub.py 크래시 후 query 파일 inbox 잔류
      → 대응: hub.py 시작 시 inbox/ 스캔, max_age 초과 파일(기본 24h) → quarantine/
  F2. 피어가 응답 없이 종료 (timeout)
      → 대응: hub.py timeout 후 query 파일 → history/ 이동 (status: timeout)
  F3. capture 부분 성공 (response 파일 있지만 parsing 실패)
      → 대응: response 파일 + query 파일 모두 → history/ 이동 (status: parse_error)
  F4. 동일 query 재전송 (retry)
      → 대응: hub.py content hash로 중복 탐지, 기존 파일 재사용

peers/{id}/ipc/
├── inbox/           # 미처리 쿼리 (volatile, gitignored)
├── history/         # 처리 완료 아카이브 (verbose → quarantine 처리)
│   ├── {id}-{ts}-{ok}.json     # 정상
│   ├── {id}-{ts}-{timeout}.json # 타임아웃
│   └── {id}-{ts}-{error}.json  # 에러
└── quarantine/      # max_age 초과 + 처리 불가 파일 (수동 검토 대기)
```

**peer.json ipc 확장 (R5+R6):**
```jsonc
"ipc": {
  "inbox_path": "ipc/inbox",
  "history_path": "ipc/history",
  "quarantine_path": "ipc/quarantine",
  "cleanup_policy": "archive_on_capture",
  "max_age_hours": 24,             // 초과 시 inbox → quarantine 이동
  "quarantine_policy": {
    "max_count": 100,              // R6 cx: quarantine 무한 성장 방지
    "max_bytes": 10485760,         // 10MB
    "overflow_action": "purge_oldest",
    "review_index": "ipc/quarantine/quarantine-index.jsonl"
  }
}
```

**quarantine/ 라이프사이클 (R6 cx — terminal state → transitions):**
```
quarantine/ 항목 상태 전이:
  [quarantined]
    → reviewed_replay:  사람이 검토 후 재전송 (inbox/에 다시 쓰기)
    → reviewed_drop:    사람이 검토 후 폐기 (history/로 이동, status: manually_dropped)
    → reviewed_archive: 사람이 검토 후 보존 (별도 경로로 이동)
    → expired_purge:    max_age 초과 자동 삭제 (quarantine-index.jsonl에 purge 기록)

quarantine-index.jsonl 스키마:
  {"entry_id": "...", "original_file": "...", "quarantined_at": "...",
   "reason": "max_age|f1_crash|f3_parse_error|...",
   "status": "quarantined|reviewed_replay|reviewed_drop|expired_purge",
   "reviewed_at": "..."}
```

### 3-7g. 글루파일 동기화 트리거 + hash drift 감지 (R5 보완)

> §3-7d 보완 — sync-glue 실행 시점 미정 문제 해소 (cx HIGH), 드리프트 루프 완결 (gc CRITICAL).

**sync-glue 실행 트리거 (우선순위 순):**
```
T1. hub.py 시작 시 (eager, mtime-gate) — canonical 문서의 mtime이 stub보다 최신인 경우만 hash 비교
    → mtime 변경 없으면 hash 비교 생략 (cx R6: 50회/day 시작 최적화)
    → hash drift 감지 시 자동 재생성 (Read-Only stub이므로 사용자 소유 파일 아님 → auto-regen 허용)
T2. action_ask 직전 (lazy) — hash drift 감지 시:
    → 기본 동작: 재생성 시도, 성공 시 ask 진행
    → 재생성 FAIL 시 (cx R6 HIGH):
       --strict 모드: ask ABORT, health warning emit
       기본 모드: 마지막 known-good hash와 현재 stub hash 비교
                  → 일치 → ask 진행 (경고 emit)
                  → 불일치 → ask ABORT
T3. Phase 1+2 PART B 완료 후 (1회) — restructure 완료 후 전 피어 stub 재생성
T4. 수동 실행: hub.py sync-glue --peer {id} / --all
```

**auto-repair vs sync-glue 경계 (R6 cx HIGH — §9 MUST-NOT 충돌 해소):**
```
sync-glue 재생성 = auto-repair 예외 대상:
  조건: ① 대상이 hub.py가 생성한 Read-Only stub 파일
        ② canonical source (protocol/peer-specific/)에서 deterministically 재생성 가능
        ③ 사용자 소유 파일, registry, junction, quarantine은 절대 변경 불가
MUST-NOT "미확인 auto-repair" 적용 범위:
  ✅ 금지: junction 생성/삭제, registry 변경, quarantine 조작, 사용자 파일 수정
  ❌ 비해당(허용): Read-Only glue stub 재생성 (deterministic, reversible, user-invisible)
```

**stub Read-Only 보호 (gc 제안, R5 채택):**
```python
# sync-glue 완료 후:
import stat, os
stub_path = Path("peers/gc/runtime/config/GEMINI.md")
# Read-Only 설정 (Windows: attrib +R, Linux: chmod 444)
os.chmod(stub_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
# 재생성 시: Read-Only 해제 → 쓰기 → Read-Only 재설정
```

**hash drift 감지 메커니즘:**
```jsonc
// peers/{id}/peer.json 에 추가
"glue_state": {
  "canonical_hash": "sha256:...",   // sync-glue 실행 시 canonical 문서의 hash
  "stub_hash": "sha256:...",        // 생성된 stub의 hash
  "synced_at": "2026-06-15T..."
}
// hub.py action_ask: canonical_hash != current_canonical_hash → sync-glue 자동 실행
```

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
| `_sys/peers/cc/peer.json` | cc 피어 식별자 (ipc/glue_source 포함) |
| `_sys/peers/gc/peer.json` | gc 피어 식별자 (ipc/glue_source 포함) |
| `_sys/peers/cx/peer.json` | cx 피어 식별자 (ipc/glue_source 포함) |
| `_sys/peers/ag/peer.json` | ag 피어 식별자 (ipc/glue_source 포함) |
| `_sys/peers/{id}/ipc/inbox/` | 피어 전용 IPC 수신 디렉토리 (was _sys/gemini/ 혼재) |
| `_sys/peers/{id}/ipc/history/` | IPC 처리 완료 쿼리 아카이브 |
| `_sys/protocol/peer-specific/cc/CLAUDE.md` | cc canonical 지침 문서 (glue stub 원본) |
| `_sys/protocol/peer-specific/gc/GEMINI.md` | gc canonical 지침 문서 (glue stub 원본) |
| `_sys/protocol/peer-specific/cx/CODEX.md` | cx canonical 지침 문서 (glue stub 원본) |
| `_sys/protocol/peer-specific/ag/AGY.md` | ag canonical 지침 문서 (glue stub 원본) |
| `_sys/protocol/general/ARCHITECTURE.md` | 신규 아키텍처 문서 |
| `_sys/config/integrations/path-map.json` | 🆕 정션 IaC 선언 (desired state SSOT — MECE Path_Map.json 역할) |
| `_sys/data/state/pathmap/managed-links.json` | 🆕 실제 생성된 정션 레지스트리 (actual state + 삭제권 — MECE I-03) |
| `_sys/data/state/pathmap/pathmap.lock` | 🆕 뮤텍스 잠금 (동시 실행 방지 — MECE I-04) |
| `_sys/data/state/pathmap/pathmap-audit.jsonl` | 🆕 mutating 명령 감사 로그 90일/50MB (MECE I-05) |
| `_sys/data/inbox/` | 🆕 분류 미결정 임시 항목 버퍼 (MECE [00_Inbox] 역할) |
| `_sys/peers/{id}/ipc/quarantine/` | 🆕 IPC max_age 초과 + 처리불가 파일 격리 (F1~F4 실패 모드) |

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
| `_sys/gemini/{peer}-*.txt` (IPC 파일 하드코딩) | `_load_peer(peer_id).ipc.inbox_path` — peer.json 기반 동적 해석 (infra.json ipc_paths 중복 제거) |
| `_sys/ai/runtime-directives.jsonl` 하드코딩 | `infra.json["runtime_state"]["directives"]` |
| `_sys/ai/user-directives.md` 하드코딩 | `common/user-directives.md` → config 참조 |
| `_sys/ai/knowledge/` 하드코딩 | `infra.json["knowledge_root"]` |
| 글루파일 직접 편집 (GEMINI.md 등) | `hub.py sync-glue --peer {id}` 재생성 + `peer.json["glue_source"]` 참조 |
| `virtualizer.py mount` (registry 없음) | pathmap 시맨틱 내재화: preflight→plan→apply(lock+audit)→status→prune (R5 신규 — MECE I-03~I-05) |
| hub.py 시작 시 glue 상태 무확인 | T1 sync-glue 트리거: 시작 시 `peer.json.glue_state.canonical_hash` vs 실제 hash 비교 → drift 감지 시 자동 재생성 |

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

### 마이그레이션 전략 선택 결정 (gc Round-4 재확정 — ⚠️ ROOT SWAP ADOPTED)

> **SUBST 재포인팅 — REJECTED:**
> host junction (`%USERPROFILE%\.claude → P:\_sys\claude\config\`)은 여전히 old 구조 참조.
> P:\ 재마운트로도 junction 재등록 불가피 → 이점 없음.
>
> **Git Branch In-Place — FALLBACK ONLY:**
> git mv로 이력 보존 가능하나 Build/Validate/Cut-over 3단계 분리 불가 → 검증 전 commit 강제 → broken-state 위험.
>
> **ROOT SWAP (병렬 `_sys_new/`) — ✅ ADOPTED (gc Round-4, 디스크 충분 확인):**
> Round-3 기각 이유 재검토:
> - 이유 2 (디스크): 사용자 확인 → 충분함 → **소멸**
> - 이유 1 (git 이력): Junction Stub 해결 — `mklink /J _sys_new\env _sys\env` 로 포인터만 생성,
>   env/+tools/ 물리 복사 없음. git 미추적 파일이므로 이력 문제 자체가 없음.
> - 이유 3 (프로세스 종료): 어떤 방식도 동일 조건. Root Swap이 유일하게 "완전 검증 후 단일 원자 전환" 제공.
>
> **Root Swap 우위:**
> - Build Phase: 피어 실행 중에도 _sys_new/ 구축 가능 (병렬 작업)
> - Validate Phase: 실제 cut-over 전 전체 verify-all 통과 확인
> - Cut-over Phase: 검증 완료 후 단일 이름 변경으로 전환 + 즉시 rollback 경로 보장
>
> **Root Swap 전체 절차 (runtime/recovery/cutover.ps1 담당):**
> ```
> [Build Phase — 피어 실행 중 가능]
>   1. _sys_new/ 신규 디렉토리 생성
>   2. mklink /J _sys_new\env   _sys\env   (junction stub — 복사 없음)
>   3. mklink /J _sys_new\tools _sys\tools (junction stub — 복사 없음)
>   4. 나머지 모든 파일: _sys_new/ 하위에 신규 구조로 생성/복사
>   5. hub.py, configs: _sys_new/ 경로 기준으로 업데이트
>
> [Validate Phase — 피어 실행 중 가능]
>   6. verify-all --sys-dir _sys_new --mode pre-cutover (V1~V10)
>      → PASS 확인 후에만 cut-over 진행 (FAIL 시 _sys_new/ 삭제 후 수정)
>
> [Cut-over Phase — 모든 피어 종료 필수]
>   7. taskkill /f /im node.exe; taskkill /f /im python.exe
>   8. $stamp = Get-Date -Format "yyyyMMddHHmmss"
>   9. ⚠️ Rename-Item _sys "_sys_old_rollback_$stamp"  ← 절대 먼저 삭제 금지
>  10. Rename-Item _sys_new _sys
>  11. python _sys\core\virtualizer.py mount  (junction 재등록)
>  12. verify-all --mode post-cutover (V11~V15 포함)
>  13. PASS → git add + commit; FAIL → .\rollback.ps1
> ```

### Phase 0 — 사전 준비 + _sys_new/ Build Phase 시작 (Root Swap 전략)

```
--- 준비 단계 (피어 실행 중 가능) ---

1. git checkout -b feat/sys-restructure
2. python -m pytest _sys/tests/ -q  → 기준점 93 passed 확인
3. git stash (미커밋 변경 있을 시)

4. 현재 Junction 상태 기록 (복구 기준점):
   fsutil reparsepoint query P:\_sys\claude\config 2>&1 | findstr "Print Name"
   fsutil reparsepoint query P:\_sys\gemini\config 2>&1 | findstr "Print Name"

5. runtime/recovery/ 생성 + 복구 스크립트 작성 (cx: 영구 홈):
   a) _sys/runtime/recovery/rollback.ps1:
      # cut-over 역전:
      #  1) 실패한 _sys (= rename된 _sys_new) 삭제
      #  2) _sys_old_rollback_* → _sys 역rename
      #  3) ⚠️ Ghost Junction 방지 — 반드시 junction 재등록 (§3-7e):
      python _sys/core/virtualizer.py apply --force   # managed-links.json 기반 재생성
      python _sys/core/virtualizer.py status          # 전 정션 OK 확인
      #  4) pytest 통과 확인
   b) _sys/runtime/recovery/cutover.ps1 (Root Swap 전체 실행 스크립트):
      # 상기 §마이그레이션 전략 절차 7~13단계 구현 (프로세스 종료 + rename + mount + verify)

6. .gitignore 피어 경로 패턴 사전 업데이트 (cx HIGH: 이동 전 패턴 교체):
   Old 패턴 → New 패턴 (§Phase 7 목록 참조):
   _sys/gemini/config/**  → _sys/peers/gc/runtime/config/**
   _sys/claude/config/**  → _sys/peers/cc/runtime/config/**
   _sys/*/status.json     → (삭제 — status.json 제거됨)
   _sys/peers/*/ipc/      → (신규 추가 — IPC 디렉토리 무시)

7. 외부 caller 사전 감사 — status.json + check-*.bat 전체 참조:
   python -c "
   import subprocess
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

--- Build Phase 시작 (_sys_new/ 구축 — 피어 실행 중 가능) ---

8. _sys_new/ 최상위 디렉토리 생성

8b. ⚠️ pathmap.lock 초기 생성 (Build Phase 시작 선언 — MECE I-04):
    # lock 스키마: {"pid": $PID, "host": $env:COMPUTERNAME, "started_at": "ISO8601",
    #               "command": "root_swap_build", "operation_id": "UUID"}
    $lockContent = @{pid=$PID; host=$env:COMPUTERNAME; started_at=(Get-Date -Format o);
                     command="root_swap_build"; operation_id=[guid]::NewGuid().ToString()} | ConvertTo-Json
    New-Item -ItemType Directory "_sys_new\data\state\pathmap" -Force | Out-Null
    Set-Content "_sys_new\data\state\pathmap\pathmap.lock" $lockContent
    # stale-lock 감지 (hub.py 시작 시): pid 프로세스 부재 + age > 30분 → auto-release

9. Junction Stub 생성 (env/tools 물리복사 없음):
   cmd /c mklink /J P:\_sys_new\env   P:\_sys\env
   cmd /c mklink /J P:\_sys_new\tools P:\_sys\tools
   ⚠️ git은 junction을 추적하지 않으므로 이력 문제 없음

10. _sys_new/ 하위에 To-Be 구조 전체 구축 (Phase 1~7 내용을 _sys_new/ 대상으로 실행):
    - _sys_new/config/, peers/, knowledge/, protocol/, runtime/, common/, templates/,
      tests/, data/, core/ 신규 구조 생성
    - 원본 _sys/ 파일들을 _sys_new/ 신규 위치로 복사 (git mv 불가 — 후에 git은 rename으로 인식)
    - hub.py, 설정 파일: _sys_new/ 경로 기준으로 업데이트

11. Validate Phase — 커밋 전 전체 검증:
    python _sys_new/runtime/cli/manage.py verify-all \
      --sys-dir _sys_new --mode pre-cutover
    → V1~V10 전항목 PASS 확인
    → FAIL 항목은 즉시 수정 후 재실행 (cut-over 절대 금지)

    ※ pytest도 _sys_new/ 대상으로 실행:
    PORTABLE_SYS_DIR=P:\_sys_new python -m pytest _sys_new/tests/unit -q
    → 93+ passed 확인

    ※ hub.py 부트스트랩 확인:
    python _sys_new/core/hub.py peer-status --json
    → exit 0

11b. ✅ SHA256 manifest 생성 (Validate PASS 직후 — cx R6 CRITICAL 수정: 이 위치만 유효):
    # V1~V10 PASS 확인 완료 후 _sys_new/ 내용이 최종 확정된 시점에서 생성
    # 이 시점 이후 _sys_new/ 변경 시 manifest 무효 → cutover.ps1이 hash 불일치로 거부
    python _sys_new/core/hub.py verify-manifest --sys-dir _sys_new --create \
      --exclude env tools data/temp peers/*/ipc data/state/pathmap/manifest.sha256 \
      --output _sys_new/data/state/pathmap/manifest.sha256
    # manifest 파일 자체는 manifest 계산에서 제외 (self-referential 방지)
    # cutover.ps1 Step 9 실행 전 manifest hash 검증 → 불일치 시 ABORT

12. Validate PASS + manifest 생성 완료 → cutover.ps1 실행 준비 완료 메시지 출력
    (실제 cut-over는 모든 피어 종료 후 별도 PowerShell 세션에서 실행)
```

### Phase 1+2 — _sys_new/ 내 피어 재구성 + 설정 중앙화 (Root Swap Build Phase 핵심)

> **Root Swap 방식에서 Phase 1+2의 위치:**
> Phase 0 Build Phase(단계 10)의 세부 내용 — _sys_new/ 하위에서 실행.
> _sys/ 원본은 그대로 — 피어가 계속 정상 동작하는 상태에서 신규 구조 구축.

> ⚠️ **gc+cx CRITICAL:** 파일 생성/복사(Part A)와 hub.py 경로 업데이트(Part B)는
> _sys_new/ 내에서 모두 완료 후 단일 커밋. 중간 상태 커밋 금지.

> ⚠️ **Cut-over는 Phase 0 단계 12 완료(verify-all PASS) 후에만:**
> Cut-over 이전까지 모든 Phase는 _sys_new/ 대상. _sys/ 원본은 read-only 참조용.

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
> **2-gate 검증 (cx CRITICAL, Root Swap 방식)**:
> - **Gate 1 (pre-cutover)**: cut-over 전 _sys_new/ 대상 실행 — 구조+경로+JSON+테스트 (V1~V10)
> - **Gate 2 (post-cutover)**: cut-over 후 실제 _sys/ 대상 실행 — junction+health+실제 경로 (V11~V15)
>   일부 버그는 실제 `_sys/` 경로에서만 발생 (`Path(__file__).parent.parent` 등)
>   V13 글루파일 sync, V14 IPC gitignore, V15 junction 실재는 cut-over 후에만 확인 가능

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

--- Gate 2 (post-cutover) 전용 체크 — V11~V15 (gc R4 추가) ---

V11. Registry-Dir 패리티 체크:
    - registry.json의 enabled=true 피어 각각에 대해 _sys/peers/{id}/ 존재 확인
    - 존재하지 않는 peer dir → FAIL
    - 명령: python runtime/checks/check_registry_parity.py --sys-dir _sys

V12. 절대경로 퍼지 체크:
    - 모든 *.json, *.py, *.bat, *.md 파일에서 드라이브 문자 포함 하드코딩 절대경로 검색
    - 패턴: [A-Z]:\\ (경로 시작) — infra.json의 "${sys_root}" 등 플레이스홀더는 허용
    - rg "[A-Z]:\\\\" --glob="*.json" --glob="*.py" --glob="*.bat" --glob="*.md"
      --exclude-glob="env/**" --exclude-glob="tools/**" --exclude-glob="data/logs/**"
    - 0건 확인 (ipc_paths 등 모두 상대경로)

V13. 엔트리포인트 + 글루파일 Sync 체크:
    - python runtime/cli/manage.py --help → exit 0
    - python core/hub.py --help → exit 0
    - python core/hub.py sync-glue --check → exit 0
      (각 peer.json glue_source ↔ glue_file 비교 — drift 있으면 FAIL)

V14. .gitignore IPC 커버리지 체크:
    - _sys/peers/*/ipc/ 패턴이 .gitignore에 존재 확인
    - _sys/peers/*/runtime/config/, runtime/project/ 패턴 존재 확인
    - 명령: python runtime/checks/check_gitignore_coverage.py --sys-dir _sys

V15. Junction 실재 + 대상 확인:
    - cc: fsutil reparsepoint query P:\_sys\peers\cc\runtime\config → 출력에 대상 경로 포함
    - gc: fsutil reparsepoint query P:\_sys\peers\gc\runtime\config → 출력에 대상 경로 포함
    - (cc/gc/cx/ag 각각 확인)
    - %USERPROFILE%\.claude → peers/cc/runtime/config/ 매핑 정확성 확인
    - %USERPROFILE%\.gemini → peers/gc/runtime/config/ 매핑 정확성 확인

--- Gate 2 추가 체크 (R6 cx) ---

V16. Bootstrap 공백 상태 체크:
    - managed-links.json 존재 + valid JSON 확인 (없으면 FAIL — Day-1 bootstrap 미실행)
    - pathmap.lock 부재 확인 (있으면 stale-lock 탐지 로직 실행)
    - op-journal.jsonl에 미완성 op 없음 확인 (있으면 FAIL — recover 먼저)
    - data/inbox/ 존재 확인
    - 명령: python runtime/checks/check_bootstrap_state.py --sys-dir _sys

V17. Audit 무결성 + Mutation operation ID 체크:
    - pathmap-audit.jsonl 존재 확인
    - 최근 mutating 명령(apply/prune)에 대응하는 audit entry 존재 확인
    - 각 audit entry에 operation_id, command, entry_id, result 필드 존재 확인
    - 명령: python runtime/checks/check_audit_integrity.py --sys-dir _sys

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

## 8. 리스크 분석 (gc+cx Round 1~4 전체 반영)

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
| MEDIUM | IPC inbox 파일 누적 (처리 안 된 쿼리) | 디스크 스페이스 + 혼란 | hub.py capture 후 archive_on_capture 자동 이동; max_age_hours 초과 시 quarantine/ 이동; V14 커버리지 체크 |
| MEDIUM | 글루파일(stub) ↔ canonical 문서 drift | AI 피어에 오래된 지침 노출 | hub.py sync-glue --all 로 재생성; glue_state hash drift 자동 감지; verify-all V13 sync check |
| CRITICAL | Ghost Junction — cut-over Step 9(rename) 완료 후 Step 11(mount) 실패 | %USERPROFILE%\.gemini 등이 _sys_old_rollback_*/... 을 여전히 가리킴 → 피어 경로 오염 | rollback.ps1에 virtualizer.py apply --force + status 체크 필수 포함 (§3-7e, Phase 0 step 5a) |
| MEDIUM | Cloud Sync 정션 오작동 (MECE N-06) | _sys/peers/{id}/runtime/config/ 가 OneDrive/Dropbox 범위 시 정션→일반폴더 처리 → 무한루프/업로드 | .gitignore + .cloudignore + OneDrive 제외 설정 필수; path-map.json BACKUP_POLICY 제외 확인 |
| MEDIUM | P:\ 드라이브 레터 하드코딩 잔류 (stub/test/스크립트) | USB 이동 시 런타임 경로 파손 | V12 절대경로 퍼지 체크; path-map.json RUNTIME.SYS_ROOT="${AUTO_DETECT}" 기반 동적 감지; stub 내 ${sys_root} 변수 사용 |
| LOW | Phase 7 grep의 archive/garbage 파일 오탐 | "0건" 달성 불가 | --exclude-glob 명시적 제외 목록 |
| LOW | git rename 감지 미신뢰 | blame/log 이력 누락 | Root Swap에서는 git이 rename으로 인식; 이력 중요 파일은 명시적 git mv |
| LOW | 글루파일 glue_source 경로 peer.json 미등록 | sync-glue 실패 | peer.json 스키마 검증 + V3 JSON 무결성 체크 |
| LOW | 브랜치 merge 충돌 | 진행 중 변경과 충돌 | Phase 0에서 브랜치 격리 |

---

## 9. MUST-DO / MUST-NOT 경계 (gc+cx 끝장검토 확정)

### 절대 해야 하는 것 (MUST-DO)

| 우선순위 | 항목 | 근거 |
|---------|------|------|
| P0 | _sys_new/ Build Phase 전 verify-all pre-cutover PASS 확인 | gc R4 CRITICAL |
| P0 | Cut-over 전 cutover.ps1 프리플라이트 process check (claude/gemini 실행 여부) | gc CRITICAL |
| P0 | Phase 0에서 runtime/recovery/rollback.ps1 + cutover.ps1 생성 | cx CRITICAL |
| P0 | Phase 0에서 .gitignore 사전 업데이트 (피어 이동 전 패턴 교체 + ipc/ 추가) | cx HIGH |
| P0 | Phase 0에서 status.json 참조 전수 감사 (모든 파일 타입) | gc HIGH |
| P1 | _sys_new/ 내 파일 생성(Part A) + hub.py 업데이트(Part B) 단일 커밋 — 분리 금지 | gc/cx CRITICAL |
| P1 | Junction 재등록 후 CLI 동작 즉시 검증 (gemini --version, claude --version) | gc CRITICAL |
| P2 | hub.py에 _sys 경로 hardcode bootstrap fallback (__file__ 기준) | cx MEDIUM |
| P2 | hub.py error-visibility.json try-except hardcoded fallback | gc HIGH |
| P3 | status.json 삭제 전 rg 0건 확인 (또는 write-through cache 전략 적용) | gc/cx HIGH |
| P4 | hub.py IPC 쿼리 경로: peer.json.ipc.inbox_path 기반으로 변경 (infra.json ipc_paths 중복 제거) | R4+R5 |
| P4 | peer.json glue_source + glue_file 필드 등록 후 sync-glue 동작 검증 | R4 |
| P4 | virtualizer.py: pathmap 시맨틱 내재화 (preflight→plan→apply→lock+audit→status→prune) | R5 MECE I-03~I-05 |
| P4 | managed-links.json: 정션 apply 시 원자적 갱신 (lock 획득 → 정션 생성 → registry 업데이트 → audit → lock 해제) | R5 MECE I-08/I-09 |
| P4 | pathmap-audit.jsonl: 모든 mutating 명령 완료 후 append (90일/50MB 보존) | R5 MECE I-05 |
| P4 | data/inbox/ 생성: 분류 미결정 항목 임시 버퍼 (MECE [00_Inbox]) | R5 |
| P7 | .gitignore 전면 재작성 후 git status로 unintended changes 없음 확인 | cx HIGH |
| P7 | traceability.json auto-gen 스크립트 실행 | gc/cx MEDIUM |
| P0 | _sys_new/ Build Phase 시작 시 pathmap.lock 생성 (step 8b) | R5 MECE I-04 |
| P0 | _sys_new/ Validate Phase 완료 직전 SHA256 manifest 생성 (step 8c) — cutover 토큰 | R5 MECE CVD |

### 절대 하지 말아야 하는 것 (MUST-NOT)

| 항목 | 결과 | 근거 |
|------|------|------|
| verify-all pre-cutover PASS 없이 cut-over 진행 | _sys_new/ 미검증 상태 전환 → 운영 불능 | gc R4 CRITICAL |
| cut-over에서 _sys/ 먼저 삭제 ("delete then rename") | 실패 시 _sys/ 없음 → 복구 불가 | cx CRITICAL |
| verify-all 단일 gate (pre-cutover만) | post-cutover에서만 나타나는 버그 누락 | cx CRITICAL |
| _sys_new/ 내 파일 생성 + hub.py 업데이트를 별도 커밋으로 분리 | 중간 broken state | gc/cx CRITICAL |
| rollback.ps1 미준비 상태에서 cut-over 실행 | 실패 시 복구 불가 | cx CRITICAL |
| JSON 파일을 naive 문자열 치환으로 경로 업데이트 | 구조 파손 | cx HIGH |
| status.json을 31개 참조 감사 전 삭제 | 다수 스크립트 실행 불능 | gc/cx HIGH |
| IPC 쿼리 파일을 여전히 _sys/gemini/ 에 생성 | 피어 구분 불가 + 청소 어려움 | R4 |
| 글루파일(stub)을 수동 편집 | sync-glue 재실행 시 덮어쓰기 → 수정 소실 | R4 |
| peer.json과 registry.json에 동일 필드 중복 | 유지 drift → MECE 위반 | gc HIGH |
| traceability.json 전체를 수동으로만 유지 | 필연적 drift → 추적성 루프 파손 | gc/cx MEDIUM |
| managed-links.json 없이 정션 생성/삭제 (registry 미등록) | prune이 관리 정션과 수동 정션 구분 불가 → 안전 삭제 불가 | R5 MECE I-03 |
| pathmap.lock 없이 병렬 정션 mutating 명령 실행 | JSON 동시 쓰기 파손 | R5 MECE I-04 |
| pathmap-audit 없이 정션 apply/prune 실행 | 감사 불가 → "누가 언제 만든 정션?" 추적 불가 | R5 MECE I-05 |
| rollback.ps1에서 junction 재등록 생략 | Ghost Junction → 피어 경로 오염 (§3-7e) | R5 CRITICAL |
| _sys/peers/{id}/runtime/config/ 를 클라우드 동기화 범위에 포함 | 정션→일반폴더 처리 → 무한루프 | R5 MECE N-06 |
| path-map.json에 P:\ 드라이브 레터 하드코딩 | USB 이동 시 경로 파손 | R5 MECE N-05 |
| 미확인 auto-repair 자동 적용 | 사용자 인지 없는 파일시스템 변경 | R5 MECE N-07 |

---

## 10. 검토 요청 사항 (피어 교차검토 — gc+cx R1~R4 완료)

1. `config/` General-Specific 분리 구조 — MECE 위반 있는가?
   → ✅ 해결: config/ = 시스템전역 공유 설정, peers/{id}/ = 피어-로컬 운영 매니페스트. 경계 §3-3에 명시.
2. `peers/{id}/peer.json` 식별자 파일 — 중복 필드 있는가? (registry.json과 overlap)
   → ✅ 해결: registry.json = {node_id, sys_subdir, enabled} 3개 필드만. 나머지 전부 peer.json 전용.
3. `runtime/` 통합 (cli+hooks+checks) — 기능 경계가 명확한가?
   → ✅ 유지: cli/=진입점래퍼, hooks/=이벤트훅, checks/=상태검증. 각 독립, bat 래퍼 없음.
4. Phase 실행 순서 — 의존성 위반 있는가?
   → ✅ 해결: Phase 1+2 원자적 통합 (_sys_new/ Build Phase 내). 분리 커밋 절대 금지.
5. status.json 제거 후 `ai_check.py` 역할을 hub.py가 100% 대체하는가?
   → ✅ 확인: hub.py check-gate --peer gc 동일 역할. write-through cache 대안 §Phase 3에 추가.
6. `common/` 스코프 — 교차-워크스페이스 공간으로 충분한가?
   → ✅ 유지: user-directives.md + peer-rules.md + agents/ + skills/ + mcp/ 포함.
7. Root Swap 방식 — git 이력 소멸 위험 없는가? (R4 추가)
   → ✅ 해결: Junction Stub (mklink /J)으로 env/tools 물리복사 없음. git 미추적 파일 = 이력 문제 없음.
     소스코드 파일은 _sys_new/ 내 새 구조로 직접 작성 (이전 파일과 내용 동일하면 git rename 감지).
8. IPC 쿼리 파일 경로 변경 — hub.py 호환성?
   → ✅ 설계: peer.json.ipc.inbox_path 기반 동적 해석. 구 _sys/gemini/ 하드코딩 + infra.json ipc_paths 중복 모두 제거.
9. 글루파일 slim화 — 피어 초기 연결 시 필요한 정보 누락 없는가?
   → ✅ 설계: canonical 문서(protocol/peer-specific/{id}/)가 전체 지침 소유.
     stub는 hub.py sync-glue가 canonical에서 핵심 내용 추출 + 런타임 변수 주입. 완전성 보장.

**R5 추가 검토 (MECE §5 통합):**

10. pathmap 제어 평면 MECE 불변식 이행?
    → ✅ 설계: §3-7e에서 managed-links.json(I-03), pathmap.lock(I-04), pathmap-audit.jsonl(I-05),
      atomic registry write(I-08), delete-before-registry-remove(I-09) 모두 virtualizer.py 시맨틱으로 내재화.
11. IPC 실패 라이프사이클 완결성?
    → ✅ 설계: §3-7f에서 F1~F4 실패 모드 + quarantine/ + max_age_hours + peer.json ipc 확장 완비.
      "성공 경로만 있던 설계 → 실패 종단 상태 명시"로 피드백 루프 완결.
12. 글루 sync 피드백 루프 닫혔는가?
    → ✅ 설계: §3-7g에서 T1~T4 트리거 + Read-Only stub 보호 + glue_state hash drift 감지.
      "push-only → 드리프트 감지 + 재생성" 으로 선순환 피드백 루프 완결.
13. Ghost Junction 복구 경로 존재하는가?
    → ✅ 설계: §3-7e ghost junction 방지 + Phase 0 step 5a rollback.ps1에 virtualizer.py apply --force 포함.
      리스크 테이블 CRITICAL 등록 + MUST-NOT에 롤백 시 junction 재등록 생략 금지 추가.
14. Cloud Sync 위험 문서화?
    → ✅ 설계: §3-7e MECE N-06 명시 + 리스크 테이블 MEDIUM 등록 + MUST-NOT 추가.
15. P:\ 하드코딩 portability 위험 해소?
    → ✅ 설계: path-map.json RUNTIME.SYS_ROOT="${AUTO_DETECT}" + 리스크 테이블 MEDIUM + V12 절대경로 퍼지 체크.
16. MECE 엣지케이스 별도 섹션 존재하는가?
    → ✅ §11 신규 추가 (session_state.json 분류, log 분류, runtime-directives TTL, 아웃바운드 정션 레이어).

**R6 추가 검토 (cx 끝장감사):**

17. apply/prune 트랜잭션 실패 복구 경로 존재하는가?
    → ✅ 설계: §3-7e에 operation journal (planned→fs_created→registry_committed→audit_committed) +
      `virtualizer.py recover` 명령으로 미완성 op 탐지 → 롤백 또는 완료.
18. SHA256 manifest 생성 시점이 올바른가?
    → ✅ 수정: Phase 0 step 8c (너무 이름) → step 11b (Validate PASS 직후)로 이동 (R6 cx CRITICAL).
19. pathmap.lock stale-lock 복구 존재하는가?
    → ✅ 설계: lock 스키마에 pid/host/started_at 포함; hub.py 시작 시 pid 부재 + age > 30분 → auto-release.
20. Day-1 bootstrap 시퀀스 존재하는가?
    → ✅ 설계: §3-7e에 8단계 bootstrap 시퀀스 추가 (SYS_ROOT감지→초기화→doctor→plan→user confirm→apply).
21. quarantine/ lifecycle 완결 (terminal state가 아닌 상태 전이 존재)?
    → ✅ 설계: §3-7f에 quarantine-index.jsonl + reviewed_replay/reviewed_drop/reviewed_archive/expired_purge 전이 추가.
22. T2 sync-glue FAIL 시 hub.py 동작이 정의됐는가?
    → ✅ 설계: §3-7g에 --strict(abort) / 기본(known-good hash 비교 후 판단) 정책 추가.
23. auto-repair vs sync-glue 경계가 명확한가?
    → ✅ 설계: §3-7g에 "auto-repair 예외 대상" 조건 3가지 명시 (Read-Only stub + deterministic + user-invisible).
24. MECE 불변식 I-01~I-10, N-01~N-08 전체 coverage 존재하는가?
    → ✅ §11-8 불변식 coverage matrix 추가 (이행/N/A/verifier 전부 명시).

---

## 11. MECE 엣지케이스 — 분류 애매한 항목 별도 정의 (R5 신규, gc+cx)

> gc/cx R5 공통 지적: "MECE에 넣기 애매한 것들은 별도 섹션에 명시하라."
> 아래 항목들은 기본 12-root 분류로 즉시 귀속되지 않아 의도적으로 결정이 필요한 사례들.

### 11-1. `session_state.json` — 피어 소유 vs 시스템 상태

| 항목 | 결정 | 근거 |
|------|------|------|
| `peers/{id}/session_state.json` | **peers/{id}/ 직하 유지** | 피어 CLI 소유 런타임 상태 (재시작 시 복구용). `data/state/` 이동 시 peer.json 경로 참조 변경 필요 → 피어 CLI 호환성 우선. |
| 예외 조건 | 피어 CLI가 경로를 하드코딩하지 않는다면 `data/state/peers/{id}/session_state.json` 권장 | 시스템 상태 데이터는 data/ 하위가 MECE 원칙상 올바름 — R6 이후 재검토 대상 |

### 11-2. 로그 분류 — `data/logs/` vs `knowledge/logs/`

| 로그 유형 | 위치 | 설명 |
|----------|------|------|
| hub.py 운영 로그 | `data/logs/hub-audit.jsonl` | 시스템 엔진 실행 로그 (hub 소유, raw) |
| IPC 처리 로그 | `data/logs/ipc-events.jsonl` | 수신/처리/실패 이벤트 (hub 소유) |
| pathmap mutating 로그 | `data/state/pathmap/pathmap-audit.jsonl` | 정션 create/delete 감사 (pathmap 소유, 별도 위치) |
| 피어 세션 로그 raw | `peers/{id}/runtime/` | 피어 CLI 소유 (hub가 건드리지 않음) |
| 지식 시스템 에러 요약 | `knowledge/logs/knowledge-errors.jsonl` | hub가 큐레이팅한 학습 이벤트만 (raw 아님) |
| 지식 전달 로그 | `knowledge/logs/delivery-log.jsonl` | 지식 전파 이력 (knowledge 소유) |

> **MECE 원칙**: raw 운영 로그는 항상 `data/logs/` 시작. `knowledge/logs/`는 큐레이팅된 학습 이벤트만.
> `data/logs/`와 `knowledge/logs/` 내용이 겹치면 MECE 위반 → `data/logs/`가 권위.

### 11-3. `runtime-directives.jsonl` — TTL 관리 상태

| 항목 | 결정 | 근거 |
|------|------|------|
| 파일 위치 | `data/state/runtime-directives.jsonl` | 내구성 있는 TTL 거버넌스 상태 (세션 간 유지 필요) |
| 성격 | **상태 (State), not 설정 (Config)** | hub.py가 런타임에 read/write, TTL 만료 시 항목 삭제 |
| 백업 포함 여부 | ✅ 백업 포함 (`data/state/` 전체 포함) | 피어 지시 이력 복구 가능성 |
| gitignore 여부 | ❌ 추적 권장 (변경 추적 가치 있음) | TTL 만료 삭제도 git 이력에 남는 것이 진단에 유용 |

### 11-4. 아웃바운드 정션 — Physical Layer 예외 분류

| 항목 | MECE 분류 | 처리 방식 |
|------|----------|----------|
| `%USERPROFILE%\.claude` → `peers/cc/runtime/config/` | Physical Layer 예외 (APP_HARDCODED_EXCEPTIONS) | path-map.json에 `host_specific: true` + `risk_level: HIGH` 명시 |
| `%USERPROFILE%\.gemini` → `peers/gc/runtime/config/` | Physical Layer 예외 (APP_HARDCODED_EXCEPTIONS) | 동일 |
| `peers/{id}/runtime/config/` (junction 대상) | **Physical Layer SSOT** (논리 레이어 아님!) | 실제 파일이 존재하는 물리 저장소 = junction이 '가리키는' 대상 |
| `%USERPROFILE%\.claude` (junction 자체) | **Logical Layer** (View) | 앱이 읽는 경로 = 물리 SSOT를 가리키는 논리 뷰 |

> **핵심 구분**: 정션 대상(`peers/.../config/`) = Physical. 정션 자체(`~/.claude`) = Logical.
> MECE 스펙 §2.5 I-01: 물리 원본은 하나뿐 (`peers/{id}/runtime/config/`).
> 아웃바운드 정션은 I-02 위반이 아님 — 보기(View)가 물리 원본 '바깥'에 있을 뿐.

### 11-5. `managed-links.json` primary key — 드라이브 레터 독립

| 항목 | 결정 |
|------|------|
| 내부 정션 (relative_link_path) | `peers/cc/runtime/config` — `SYS_ROOT` 상대경로 |
| 외부/아웃바운드 정션 (relative_link_path) | `EXTERNAL:%USERPROFILE%/.claude` — EXTERNAL 프리픽스 + 환경변수 표기 |
| drive_root_at_last_write | `P:/` — 마지막 write 시 드라이브 레터 기록. USB 이동 감지 시 `managed-links.json` stale 경고 |

### 11-7. Operation Journal 임시 파일 분류

| 파일 | 위치 | 성격 | 보존 |
|------|------|------|------|
| `op-journal.jsonl` | `data/state/pathmap/op-journal.jsonl` | 진행 중 op 상태 (planned→fs_created→registry_committed→audit_committed) | 완성 op = 즉시 제거 or 별도 archive; 미완성 op = recover 대상 |
| `managed-links.json.tmp` | `data/state/pathmap/managed-links.json.tmp` | atomic write temp (write → rename) | rename 성공 시 즉시 사라짐; 잔류 시 stale artifact → doctor 탐지 대상 |
| `manifest.sha256` | `data/state/pathmap/manifest.sha256` | cutover 마이그레이션 토큰 | cutover 성공 후 archived 또는 삭제 (cutover.ps1 마지막 단계) |
| `pathmap.lock` | `data/state/pathmap/pathmap.lock` | 뮤텍스 잠금 | op 완료 시 삭제; hub.py 시작 시 stale 탐지 + auto-release |

> 위 파일들은 모두 `.gitignore`에 포함 필수 (이미 §Phase 7 목록에 포함됨을 확인할 것)

### 11-8. MECE 불변식 Coverage Matrix (R6 cx — 명시적 이행/비적용 기록)

| 불변식 | 설명 | 상태 | 이행 위치 | Verifier |
|--------|------|------|----------|---------|
| I-01 | 물리 원본 하나뿐 | ✅ 이행 | §3-7e: peers/{id}/runtime/config/ = 유일 SSOT | V4 |
| I-02 | View는 링크만 | ✅ 이행 | §3-7e: %USERPROFILE%/.claude 등 = junction only | V15 |
| I-03 | 모든 관리 링크 등록 | ✅ 이행 | §3-7e: managed-links.json registry | V11, virtualizer apply |
| I-04 | mutating 명령 lock | ✅ 이행 | §3-7e: pathmap.lock 획득 후 실행 | pathmap.lock schema |
| I-05 | mutating 명령 audit | ✅ 이행 | §3-7e: pathmap-audit.jsonl append | V17 (신규) |
| I-06 | Copy-Verify-Delete | ✅ 이행 | Phase 0: SHA256 manifest (step 11b) | cutover.ps1 hash check |
| I-07 | 백업 View 건너뜀 | ✅ 이행 | path-map.json BACKUP_POLICY junction_traversal: skip | - |
| I-08 | registry write 원자적 | ✅ 이행 | §3-7e: managed-links.json.tmp → rename | op journal state tracking |
| I-09 | 물리 삭제 후 registry 제거 | ✅ 이행 | §3-7e: prune --apply: fs_deleted → then registry | op journal state tracking |
| I-10 | 마이그레이션 commit 재검증 | ✅ 이행 | Phase 0 step 11b manifest + cutover.ps1 검증 | cutover.ps1 |
| N-01 | managed link op은 pathmap만 | ✅ 이행 | virtualizer.py 단일 진입점 | §9 MUST-NOT |
| N-02 | View-in-View 금지 | N/A | _sys/에서 View-in-View 구조 없음 | - |
| N-03 | /MOVE 금지 | N/A | pathmap에 MOVE 명령 없음 | - |
| N-04 | 링크/대상에 마커 파일 금지 | N/A | 마커 파일 패턴 미사용 | - |
| N-05 | Path_Map에 드라이브 레터 금지 | ✅ 이행 | path-map.json ${AUTO_DETECT}; V12 절대경로 퍼지 체크 | V12 |
| N-06 | View의 클라우드 동기화 금지 | ✅ 이행 | §3-7e Cloud Sync 경고; .cloudignore 권고 | 수동 확인 |
| N-07 | 미확인 auto-repair 금지 | ✅ 이행 | §3-7g auto-repair 경계 명시 (glue stub 예외 정의) | §9 MUST-NOT |
| N-08 | CI에서 고위험 outward apply 금지 | N/A | CI 파이프라인 미사용 (포터블 환경) | - |

> N-02/N-03/N-04/N-08: 현재 설계에서 발생 불가한 패턴 → "N/A" 명시로 미검토 오해 방지

### 11-6. `infra.json` vs `path-map.json` 역할 경계 최종 확정

| 파일 | 역할 | 포함 내용 | 제외 내용 |
|------|------|----------|----------|
| `infra.json` | 글로벌 매크로 루트 | `base_dirs` (sys/data/knowledge 루트), `config_registry` (설정 키→경로 맵핑) | ipc_paths (→ peer.json 위임), 정션 선언 (→ path-map.json) |
| `path-map.json` | 정션 IaC 선언 | APP_HARDCODED_EXCEPTIONS, BACKUP_POLICY, RUNTIME 매크로 | 설정 경로 (→ infra.json), 실제 상태 (→ managed-links.json) |
| `managed-links.json` | 실제 생성된 정션 레지스트리 | entries (primary key, created_at, host_specific), drive_root | 선언 의도 (→ path-map.json) |
