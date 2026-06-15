# SSOT 및 View 분리형 차세대 MECE 디렉토리 아키텍처 — 운영 지침서 v2.6

---

## 0. 문서 개요 및 변경 이력

| 버전 | 날짜 | 주요 변경 내용 |
|---|---|---|
| v1.0 | 2026-06-15 | 초안 작성 |
| v2.0 | 2026-06-15 | 1차 교차검토: CRITICAL 5 + MAJOR 14 해소 |
| v2.1 | 2026-06-15 | 2차 교차검토: CRITICAL 1 + MAJOR 9 해소 |
| v2.1p | 2026-06-15 | 3차 수렴: MAJOR 2 해소 (managed-links.json, /MOVE 제거) |
| v2.2 | 2026-06-15 | MINOR 3 패치: verify-migration CLI, 03_App_State 트리, hash 도구 명세 |
| v2.3 | 2026-06-15 | 4차 교차검토: CRITICAL 2 + MAJOR 9 해소 (Ghost Junction, stale token, managed-links.json 스키마, lockfile, View-in-View 금지, migration-commit 재검증, conflict_policy 매트릭스, hash 결정론 규칙) |
| v2.4 | 2026-06-15 | 5차 교차검토: MAJOR 5 + MINOR 4 해소 (토큰 필드 명확화, managed-links retarget/우선순위, Windows 정션 target 읽기 API, migration-commit 2단계 감사, registry 역방향 GC, rebuild 전손실, manifest_hash 정의, Appendix C 보완) |
| v2.5 | 2026-06-15 | 메타검토 7렌즈: CRITICAL 2 + MAJOR 9 + MINOR 2 해소 (registry 상대경로 portability, bootstrap 설치 경로, §2.5 INVARIANTS 통합, 로그/스냅샷 보존, prune MUST 승격, Lifecycle Trigger Table, CLI 출력 예시, snapshot rename, pathmap_manifest_hash 제거, 클라우드동기화 위험, pathmap move) |
| v2.6 | 2026-06-15 | 목적 중심 최종검토: BLOCKER 1 + MAJOR 7 + MINOR 3 해소 (On-Mount SHOULD 승격, status MUST 승격, move SHOULD 승격, N-09 신설, INVARIANT 집행 레이블, 03_App_State 백업 제외, broken_link 상태 정의, Appendix D 모호케이스, apply/doctor 출력 예시, Bootstrap 개선) |

---

## 1. 설계 개요 및 아키텍처 철학

본 지침서는 SSOT, MECE, 캡슐화, 확장성을 동시에 충족하는 차세대 디렉토리 아키텍처를 정의하고, 안전한 구현·운영 절차를 규정합니다.

기존 단일 계층 구조는 "물리적 저장 위치"와 "논리적 작업 관점"을 강제로 일치시켜야 했기 때문에 다차원 분류 시 중복·누락·상향 참조 링크가 발생했습니다.

본 아키텍처는 **Physical Layer**와 **Logical Layer**를 완전히 분리하고, Key-Path Dictionary 기반의 정션/심볼릭 링크로 매핑하는 IaC 접근 방식을 채택합니다.

---

## 2. 핵심 설계 지침

### 2-1. 단일 진실 공급원(SSOT) 및 링크 최소화
- 모든 원본 파일은 물리 저장 계층의 최하위 경로에 단 하나만 존재합니다.
- 상위 계층은 링크(정션)들의 집합으로만 구성됩니다.

### 2-2. 엄격한 하향식 캡슐화
- 물리 저장 계층 서브 디렉토리는 독립적이며 하위 계층만 참조합니다.
- 상위·횡방향·외부로의 물리 참조는 원천 차단됩니다.
- **[중요]** Outward Junction(§4.3)은 유일한 예외이며 엄격한 조건 하에서만 허용됩니다.

### 2-3. 다차원 MECE 분류 및 버퍼 폴더
- 모든 물리 레이어 루트에 `[00_Inbox]` 버퍼 폴더를 배치합니다.
- 귀속 기준은 §부록-A MECE 결정 테이블을 따릅니다.

### 2-4. Lifecycle 기반 최상위 Root 분리
- `[01_User_Space]` (활성 데이터), `[02_System_Bin]` (바이너리), `[03_Archive_Media]` (cold data), `[04_Volatile_Temp]` (휘발성)을 최상위에서 격리합니다.

### 2-5. Path_Map.json 기반 IaC 및 검증 자동화
- 모든 논리 뷰 매핑은 `Path_Map.json`으로 선언 관리됩니다.
- Path_Map.json은 **알려진 고정 경로**에 위치하여 Bootstrap 역설을 방지합니다.

### 2-6. Verify-First 안전 원칙
- 모든 filesystem 변경은 dry-run 계획 출력 후 `--apply` 명시 시에만 실행됩니다.
- 모든 변경은 감사 로그에 기록됩니다.

### 2-7. 포터빌리티 우선 동적 경로
- 드라이브 레터는 Path_Map.json에 하드코딩하지 않습니다. 런타임 동적 감지합니다.

---

## 2.5. 아키텍처 불변 규칙 (INVARIANTS)

> 이 표는 분산된 모든 MUST/MUST-NOT을 한곳에 통합합니다. 구현체는 이 표를 기준으로 검증합니다.

> **집행 레이블:** `[TOOL]` = pathmap이 코드로 강제 | `[POLICY]` = 사용자 책임, pathmap이 경고만 | `[ADVISORY]` = 권장, 미준수 시 경고 없음

### MUST (필수)

| # | 집행 | 규칙 | 범위 | 적용 계층 |
|---|---|---|---|---|
| I-01 | [POLICY] | 모든 원본 파일은 Physical Layer(01~04)에 단 하나만 존재 | 전체 | 수동 + validate |
| I-02 | [TOOL] | [00_Workspace_Views] 하위에는 정션/심볼릭 링크만 허용, 실제 파일/디렉토리 금지 | views | preflight + apply |
| I-03 | [TOOL] | pathmap apply로 생성된 모든 정션은 managed-links.json에 등록 | apply | apply |
| I-04 | [TOOL] | 모든 mutating 명령은 pathmap.lock 획득 후 실행 | 전체 | apply/prune/repair/restore/migration-commit |
| I-05 | [TOOL] | 모든 mutating 명령은 완료 후 감사 로그에 기록 | 전체 | apply/prune/repair/restore/migration-commit |
| I-06 | [TOOL] | 마이그레이션은 Copy-Verify-Delete 패턴만 허용 | migration | migration-commit |
| I-07 | [ADVISORY] | 백업 도구는 [00_Workspace_Views] 하위를 반드시 제외 (`/XJ` 또는 `--no-dereference`) *(pathmap이 강제 불가; backup-plan 명령이 올바른 명령어를 생성함)* | backup | pathmap backup-plan |
| I-08 | [TOOL] | managed-links.json 갱신은 반드시 원자적(temp→rename) | registry | apply/prune |
| I-09 | [TOOL] | prune --apply 는 물리 삭제 성공 확인 후에만 registry에서 제거 | prune | prune --apply |
| I-10 | [TOOL] | migration-commit은 cleanup 전 src/dst 재검증 + consumed:true 원자 갱신 필수 | migration | migration-commit |

### MUST-NOT (금지)

| # | 집행 | 규칙 | 범위 | 위반 결과 |
|---|---|---|---|---|
| N-01 | [POLICY] | MUST-NOT: pathmap 외부에서 **managed** junction 직접 생성/삭제 *(unmanaged 정션은 허용되나 prune이 "unmanaged"로 보고하고 절대 자동 삭제하지 않음)* | junction ops | registry drift → rebuild 필요 |
| N-02 | [TOOL] | MUST-NOT: target_path가 [00_Workspace_Views] 하위를 가리킴 (View-in-View) | schema | validate에서 차단 |
| N-03 | [TOOL] | MUST-NOT: 마이그레이션에 /MOVE 사용 | migration | 중간 실패 시 데이터 분할 |
| N-04 | [POLICY] | MUST-NOT: 정션 내부 또는 target 폴더에 marker 파일 생성 | apply | SSOT 오염 |
| N-05 | [TOOL] | MUST-NOT: Path_Map.json에 드라이브 레터 하드코딩 (APP_HARDCODED_EXCEPTIONS 제외) | schema | validate에서 경고 |
| N-06 | [ADVISORY] | MUST-NOT: [00_Workspace_Views]를 클라우드 동기화(OneDrive/Dropbox 등) 범위에 포함 *(doctor가 경고 시도하나 OS 설정 감지 한계 있음)* | ops | 정션 내용 무한 업로드 또는 동기화 클라이언트 오작동 |
| N-07 | [TOOL] | MUST-NOT: pathmap이 사용자 확인 없이 자동 apply/heal/repair 실행 | automation | 예기치 않은 FS 변경 |
| N-08 | [POLICY] | MUST-NOT: CI/자동화 스크립트에서 HIGH risk (APP_HARDCODED_EXCEPTIONS) 항목 적용 | CI/ops | 호스트 경로 오염 |
| N-09 | [POLICY] | MUST-NOT: LOGICAL_VIEWS에서 active entry_id가 참조하는 SSOT 경로를 `pathmap move` 없이 이동/삭제 *(위반 시 정션 즉시 broken — status가 사후 감지)* | physical ops | 정션 broken_link 상태 |

---

## 3. 디렉토리 트리 구조 (v2.3)

```text
드라이브 Root (예: D:\ 또는 /home/user/)
│
├── 📂 [00_Workspace_Views]           # [논리 계층] 정션/심볼릭 링크만. 실제 파일 0%
│   ├── 📂 01_Gemini_P2P_Dashboard
│   ├── 📂 02_Project_Alpha_View
│   └── 📂 03_Knowledge_Base_View
│
├── 📂 [01_User_Space]                # [물리 계층] SSOT 원본 (백업 1순위)
│   ├── 📂 [00_Inbox]
│   ├── 📂 01_Development
│   │   ├── 📂 Python_Projects
│   │   └── 📂 Rust_Core
│   ├── 📂 02_Templates_and_Prompts
│   │   └── 📂 Gemini_Prompts
│   ├── 📂 03_App_State               # 앱 State (영구 but 낮은 백업 우선순위)
│   ├── 📂 98_App_Configs             # 앱 고정 경로 설정 SSOT
│   └── 📂 99_Path_Dictionary         # Known Path 진입점
│       ├── Path_Map.json             # IaC 선언 (SSOT)
│       ├── Path_Map.schema.json      # JSON Schema
│       ├── Path_Map.status.json      # 런타임 상태 (IaC 분리)
│       ├── managed-links.json        # managed marker 영속 레지스트리 (백업 대상)
│       ├── pathmap.lock              # 뮤텍스 잠금 파일 (동시 실행 방지)
│       ├── 📂 snapshots
│       └── 📂 logs
│           └── pathmap_audit.jsonl
│
├── 📂 [02_System_Bin]                # [물리 계층] 재설치 가능 바이너리
│   ├── 📂 [00_Staging]
│   ├── 📂 Portable_Apps
│   └── 📂 Automation_Tools
│
├── 📂 [03_Archive_Media]             # [물리 계층] 대용량 cold data
│   ├── 📂 [00_Inbox]
│   ├── 📂 Datasets
│   ├── 📂 Raw_Media
│   └── 📂 ISOs_and_Images
│
└── 📂 [04_Volatile_Temp]             # [물리 계층] 휘발성 데이터 (백업 제외)
    ├── 📂 [00_Quarantine]
    ├── 📂 App_Caches
    └── 📂 Conversation_Logs
```

---

## 4. 레이어별 운영 규칙

### 4.1. [00_Workspace_Views] (Logical Layer)

- **운영 원칙:** 이 디렉토리 이하에는 실제 물리 파일을 생성하지 않습니다.
- **구성 방식:** 물리 레이어 원본을 가리키는 정션 링크로만 구성됩니다.
- **managed marker:** `pathmap apply`로 생성된 정션은 `managed-links.json` 레지스트리에 등록됩니다. 정션 내부 또는 타겟 폴더에 마커 파일을 생성하지 않습니다 (SSOT 오염 방지).
- **백업 제외 필수:** Robocopy `/XJ`, rsync `--no-dereference`.
- **View-in-View 금지:** `link_path`의 `target_path`가 `[00_Workspace_Views]` 하위를 가리치는 것은 금지됩니다 (reparse chain 위험). §5.1 스키마 검증에서 차단합니다.

### 4.2. [01_User_Space] (Physical Layer - Active)

- **운영 원칙:** 사용자가 직접 관리하는 핵심 데이터 자산(SSOT)의 홈입니다.
- **Known Path:** `99_Path_Dictionary/Path_Map.json`은 Bootstrap 진입점입니다. 고정 상대경로: `{DRIVE_ROOT}/[01_User_Space]/99_Path_Dictionary/Path_Map.json`

### 4.3. 앱 고정 경로 예외 처리 — Outward Junction 정책

> **[HIGH RISK 경고]** 다음 조건 모두 충족 시에만 허용:
> 1. 앱이 reparse point를 정상 인식하는지 검증
> 2. 앱 언인스톨러/업데이터가 SSOT를 삭제하지 않는지 확인
> 3. USB 분리 시 호스트 OS에 dead junction 잔류 인지
> 4. `APP_HARDCODED_EXCEPTIONS`에 명시적 선언
> 5. 적용 전 SSOT 백업
> 6. `--force-high-risk --confirm-entry <entry_id>` 이중 확인 토큰 필수

**권장 대안 — On-Mount Sync Script:**
마운트 시 inject, 분리 시 pull-back. 물리 캡슐화 유지, dead junction 없음.

### 4.4. [02_System_Bin], [03_Archive_Media], [04_Volatile_Temp]

- **System_Bin:** 재설치 가능 환경 격리. 사용자 커스텀 설정은 `98_App_Configs`에 귀속.
- **Archive_Media:** 대용량 cold data. 별도 백업 정책 적용.
- **Volatile_Temp:** 백업 제외. 감사 로그는 이 레이어에 두지 않습니다.

---

## 5. Path_Map.json 스키마 v2.3

### 5.1. 스키마 전체 구조

```json
{
  "SCHEMA_VERSION": "2.3.0",
  "METADATA": {
    "created_at": "YYYY-MM-DD",
    "description": "MECE Directory Architecture path mapping declaration"
  },
  "RUNTIME": {
    "DRIVE_ROOT": "${AUTO_DETECT}",
    "USER_SPACE":    "${DRIVE_ROOT}/[01_User_Space]",
    "SYSTEM_BIN":    "${DRIVE_ROOT}/[02_System_Bin]",
    "ARCHIVE_MEDIA": "${DRIVE_ROOT}/[03_Archive_Media]",
    "VOLATILE_TEMP": "${DRIVE_ROOT}/[04_Volatile_Temp]",
    "VIEWS_ROOT":    "${DRIVE_ROOT}/[00_Workspace_Views]"
  },
  "MACRO_RESOLUTION_RULES": {
    "syntax": "${MACRO_NAME}",
    "expansion_model": "topological_single_pass",
    "expansion_model_note": "RUNTIME 매크로를 의존 그래프로 위상 정렬 후 단일 패스 확장. DRIVE_ROOT → USER_SPACE/SYSTEM_BIN/... 순서. 사용자 데이터 내 ${...}는 확장하지 않음.",
    "cycle_detection_phase": "graph_build",
    "cycle_detection_note": "확장 실행 전 의존 그래프 빌드 단계에서 사이클을 탐지. 사이클 발견 시 확장 없이 즉시 오류 출력.",
    "undefined_macro_policy": "error",
    "path_separator": "platform_native",
    "parent_traversal_policy": "block",
    "case_sensitivity": "platform_native",
    "env_var_injection_policy": "runtime_only_never_commit"
  },
  "CONFLICT_POLICY_ENUM": {
    "_doc": "conflict_policy 유효 값. link_path 위치의 기존 오브젝트 상태별 동작 정의.",
    "link_state_matrix": {
      "missing":            { "error_if_exists": "create", "error_if_real_dir_exists": "create", "replace_broken_link": "create", "replace_wrong_link": "create", "skip_if_exists": "create" },
      "correct_link":       { "error_if_exists": "noop",   "error_if_real_dir_exists": "noop",   "replace_broken_link": "noop",   "replace_wrong_link": "noop",   "skip_if_exists": "noop" },
      "broken_link":        { "error_if_exists": "error",  "error_if_real_dir_exists": "create", "replace_broken_link": "replace","replace_wrong_link": "replace", "skip_if_exists": "skip" },
      "wrong_target":       { "error_if_exists": "error",  "error_if_real_dir_exists": "error",  "replace_broken_link": "error",  "replace_wrong_link": "replace", "skip_if_exists": "skip" },
      "wrong_type":         { "error_if_exists": "error",  "error_if_real_dir_exists": "error",  "replace_broken_link": "error",  "replace_wrong_link": "replace", "skip_if_exists": "skip" },
      "real_file":          { "error_if_exists": "error",  "error_if_real_dir_exists": "error",  "replace_broken_link": "error",  "replace_wrong_link": "error",  "skip_if_exists": "skip" },
      "real_dir":           { "error_if_exists": "error",  "error_if_real_dir_exists": "error",  "replace_broken_link": "error",  "replace_wrong_link": "error",  "skip_if_exists": "skip" }
    },
    "_wrong_definition": "상태 정의 (상호 배타적): broken_link = reparse point는 존재하나 target 경로가 FS에 없음 (Terminal State — target 존재 여부가 우선). wrong_target = reparse point가 존재하고 target도 존재하나 Path_Map.json의 선언과 다름. wrong_type = target 존재 여부 무관, reparse tag 자체가 다름(junction vs symlink). 우선순위: broken_link > wrong_type > wrong_target. 즉, target이 없으면 항상 broken_link로 분류."
  },
  "LOGICAL_VIEWS": [
    {
      "entry_id": "gemini-dashboard-prompts",
      "link_path": "${VIEWS_ROOT}/01_Gemini_P2P_Dashboard/prompts",
      "target_path": "${USER_SPACE}/02_Templates_and_Prompts/Gemini_Prompts",
      "link_type": "dir_junction",
      "platform": "windows",
      "target_kind": "directory",
      "create_policy": "create_missing",
      "conflict_policy": "error_if_real_dir_exists",
      "allow_cross_drive": true,
      "allow_network_target": false,
      "expected_target_exists": true,
      "description": "Gemini prompts SSOT (User_Space) → dashboard view"
    },
    {
      "entry_id": "gemini-dashboard-bin",
      "link_path": "${VIEWS_ROOT}/01_Gemini_P2P_Dashboard/bin",
      "target_path": "${SYSTEM_BIN}/Automation_Tools",
      "link_type": "dir_junction",
      "platform": "windows",
      "target_kind": "directory",
      "create_policy": "create_missing",
      "conflict_policy": "error_if_real_dir_exists",
      "allow_cross_drive": true,
      "allow_network_target": false,
      "expected_target_exists": true,
      "description": "Gemini automation tools (System_Bin) → dashboard view"
    },
    {
      "entry_id": "gemini-dashboard-logs",
      "link_path": "${VIEWS_ROOT}/01_Gemini_P2P_Dashboard/logs",
      "target_path": "${VOLATILE_TEMP}/Conversation_Logs",
      "link_type": "dir_junction",
      "platform": "windows",
      "target_kind": "directory",
      "create_policy": "create_missing",
      "conflict_policy": "error_if_real_dir_exists",
      "allow_cross_drive": true,
      "allow_network_target": false,
      "expected_target_exists": false,
      "description": "Gemini conversation logs (Volatile_Temp) → dashboard view"
    }
  ],
  "_LOGICAL_VIEWS_NOTE": "위 3개 항목이 MECE 핵심 패턴을 보여줍니다: 단일 대시보드 뷰(01_Gemini_P2P_Dashboard)가 User_Space·System_Bin·Volatile_Temp 세 물리 레이어의 원본을 각각 정션으로 집약합니다. 물리 레이어에서는 MECE로 격리된 데이터가 논리 뷰에서 단일 작업 공간으로 결합됩니다.",
  "APP_HARDCODED_EXCEPTIONS": [
    {
      "entry_id": "targetapp-config-outward",
      "app_required_path": "C:/Users/User/AppData/Roaming/TargetApp/config",
      "ssot_origin": "${USER_SPACE}/98_App_Configs/TargetApp_Config",
      "link_type": "dir_junction",
      "platform": "windows",
      "target_kind": "directory",
      "create_policy": "verify_only",
      "conflict_policy": "error_if_real_dir_exists",
      "allow_cross_drive": true,
      "allow_network_target": false,
      "expected_target_exists": true,
      "risk_level": "HIGH",
      "requires_explicit_apply": true,
      "rollback_backup_required": true,
      "description": "Outward junction — requires --force-high-risk --confirm-entry targetapp-config-outward"
    }
  ],
  "BACKUP_POLICY": {
    "_enforcement": "advisory — pathmap backup-plan으로 OS별 명령어 생성",
    "include": ["${USER_SPACE}", "${ARCHIVE_MEDIA}"],
    "exclude": ["${VIEWS_ROOT}", "${VOLATILE_TEMP}", "${SYSTEM_BIN}"],
    "junction_traversal": "skip",
    "recommended_tool_windows": "robocopy /MIR /XJ /W:1 /R:1",
    "recommended_tool_linux": "rsync -av --no-dereference"
  }
}
```

> **운영 시 Path_Map.json 정리:** `CONFLICT_POLICY_ENUM`과 `MACRO_RESOLUTION_RULES`의 `_doc`/`_note` 필드는 스펙 예시용입니다. 실제 운영 파일에서는 `_doc`으로 시작하는 키와 `*_note` 키를 제거하여 JSON을 경량화합니다. pathmap은 이 필드들이 없어도 정상 동작합니다.

**스키마 검증 규칙 (pathmap validate가 강제):**
- `entry_id`: 전체 파일 내 유일
- 해석된 `link_path`: 전체 파일 내 유일
- `link_path`는 `${VIEWS_ROOT}` 하위이거나 `APP_HARDCODED_EXCEPTIONS`에 속해야 함
- `target_path`는 `${VIEWS_ROOT}` 하위를 가리킬 수 없음 (View-in-View 금지)
- `app_required_path`: `APP_HARDCODED_EXCEPTIONS` 내 유일

### 5.2. link_type 필드 및 OS 동작

| link_type | OS | 대상 | 권한 | 제약 |
|---|---|---|---|---|
| `dir_junction` | Windows | 디렉토리 | 비관리자 가능 | NTFS/ReFS 필요, 로컬 드라이브만, UNC 불가, 절대경로만 |
| `dir_symlink` | Windows | 디렉토리 | Developer Mode 또는 권한 | 상대경로·네트워크 지원 |
| `file_symlink` | Windows | 파일 | Developer Mode 또는 관리자 | 단일 파일 링크 |
| `file_hardlink` | Windows | 파일 | 동일 볼륨 내 | 다른 드라이브 불가 |
| `symlink` | Linux/macOS | 파일/디렉토리 | 일반 사용자 | `ln -s` |

> 단일 파일(`.json`, `.conf`)을 링크해야 하는 경우 `dir_junction`이 아닌 `file_symlink`를 사용합니다.

### 5.3. DRIVE_ROOT 동적 감지 알고리즘

우선순위 순:
1. `PATHMAP_DRIVE_ROOT` 환경 변수 — 유효하지 않으면 오류 (침묵 fallback 금지)
2. 실행 스크립트 경로에서 `[01_User_Space]/99_Path_Dictionary/` 역산
3. 마운트된 모든 로컬 드라이브 스캔 (최후 수단)

**중복 드라이브 처리:** 탐지 결과 2개 이상 → ambiguity error + 후보 목록 출력. 해소: `PATHMAP_DRIVE_ROOT` 설정. 선택된 루트는 `Path_Map.status.json`에 기록.

### 5.4. managed-links.json 스키마

`managed-links.json`은 `pathmap apply`로 생성·삭제된 정션의 영속 레지스트리입니다.

**Primary key: `relative_link_path`** (DRIVE_ROOT 기준 상대경로)

> **왜 상대경로인가:** 포터블 드라이브는 호스트에 따라 D: → E: 등 드라이브 레터가 달라집니다. 절대경로를 primary key로 쓰면 드라이브 레터 변경 시 전체 레지스트리가 무효화됩니다. 상대경로를 사용하면 registry가 드라이브 레터와 독립적으로 유지됩니다.

```json
{
  "schema_version": "2.5.0",
  "drive_root_at_last_write": "D:/",
  "entries": {
    "[00_Workspace_Views]/01_Gemini_P2P_Dashboard/prompts": {
      "relative_link_path": "[00_Workspace_Views]/01_Gemini_P2P_Dashboard/prompts",
      "relative_target_path": "[01_User_Space]/02_Templates_and_Prompts/Gemini_Prompts",
      "link_type": "dir_junction",
      "entry_id": "gemini-dashboard-prompts",
      "operation_id": "op-20260615-001",
      "created_at": "2026-06-15T13:10:00Z"
    }
  }
}
```

**APP_HARDCODED_EXCEPTIONS 항목은 절대경로 유지:**
```json
{
  "C:/Users/User/AppData/Roaming/TargetApp/config": {
    "relative_link_path": "C:/Users/User/AppData/Roaming/TargetApp/config",
    "host_specific": true,
    "link_type": "dir_junction",
    ...
  }
}
```
`host_specific: true` 항목은 다른 기기에서 "orphaned"로 분류하지 않고 skip합니다.

**드라이브 레터 변경 감지:** pathmap 실행 시 현재 DRIVE_ROOT와 `drive_root_at_last_write`가 다르면 감사 로그에 `drive_root_migrated` 이벤트 기록. 항목은 자동 재해석(relative path → 새 절대경로).

**필드 정의:**
- `relative_link_path`: DRIVE_ROOT 기준 상대경로 (primary key). VIEWS_ROOT 항목은 `[00_Workspace_Views]/...`, 호스트 전용 항목은 절대경로.
- `relative_target_path`: DRIVE_ROOT 기준 상대경로. 호스트 전용은 절대경로.
- `host_specific`: true인 경우 다른 호스트/드라이브에서 orphan 판정 제외.

**운영 규칙:**
- `relative_link_path`가 primary key. `entry_id` rename 시에도 link_path가 동일하면 동일 항목으로 처리.
- apply 실행 시 원자적 갱신: temp 파일 작성 후 rename (atomic swap).
- `pathmap prune`은 `entries`에 없는 정션을 "unmanaged"로 분류 → 절대 삭제 안 함.
- `managed-links.json` 손실 시: `pathmap rebuild`로 audit log + reparse 메타데이터를 대조하여 초안 복구.

**Path_Map.json vs managed-links.json 우선순위 규칙 (충돌 시):**

| 상태 | 분류 | 처리 담당 |
|---|---|---|
| Path_Map에 X 있음, registry에 X 있음, relative_target 동일 | 정상 | noop |
| Path_Map에 X 있음, registry에 X 있음, relative_target 다름 | retarget | `apply`가 `conflict_policy` 에 따라 처리 |
| Path_Map에 X 없음, registry에 X 있음 | managed orphan | `prune`이 처리 |
| Path_Map에 X 있음, registry에 X 없음 | untracked link | `apply`가 신규 생성 후 registry 등록 |
| Path_Map 없음, registry 없음, FS에 X 있음 | unmanaged junction | `prune`이 "unmanaged"로 보고만, 삭제 안 함 |

- **retarget 시 registry 갱신:** apply가 정션을 교체(correct old link → create new link)하면 기존 `resolved_link_path` 항목을 새 `resolved_target_path`·`operation_id`·`created_at`으로 덮어씀 (atomic swap).
- `Path_Map.json`이 desired state의 SSOT. `managed-links.json`은 삭제 권한(deletion authority)과 이력(history)의 SSOT.

### 5.5. Path_Map.status.json

```json
{
  "schema_version": "2.4.0",
  "last_verified": "2026-06-15T13:10:00Z",
  "last_verified_by": "cc",
  "manifest_hash": "sha256:...",
  "resolved_drive_root": "D:/",
  "entries": {
    "gemini-dashboard-prompts": {
      "status": "OK",
      "last_checked": "2026-06-15T13:10:00Z",
      "resolved_link_path": "D:/[00_Workspace_Views]/01_Gemini_P2P_Dashboard/prompts",
      "resolved_target_path": "D:/[01_User_Space]/02_Templates_and_Prompts/Gemini_Prompts"
    }
  }
}
```

---

## 6. Pathmap CLI 및 Verify 파이프라인 v2.4

### 6.1. 명령어 체계

| 명령어 | FS 접근 | 변경 | 설명 |
|---|---|---|---|
| `pathmap validate` | 없음 | 없음 | JSON 문법·스키마·매크로·유일성·View-in-View 금지 검증 |
| `pathmap preflight` | 읽기 | 없음 | FS 준비 상태 확인 (권한, NTFS/ReFS, link_path 충돌) |
| `pathmap status` | 읽기 | 없음 | 전체 링크 현재 상태 보고. 계획 없음. |
| `pathmap plan` | 읽기 | 없음 | dry-run: 변경 계획 + risk + plan_hash 출력 |
| `pathmap apply` | **쓰기** | **있음** | plan을 실제 적용. HIGH risk: `--force-high-risk --confirm-entry <id>` 필요 |
| `pathmap prune` | 읽기 | 없음 | orphan 정션 목록. managed(삭제 가능) vs unmanaged(보고만) 구분 |
| `pathmap prune --apply` | **쓰기** | **있음** | managed orphan만 삭제. 물리 삭제 성공 확인 후 레지스트리 갱신 |
| `pathmap repair` | **쓰기** | **있음** | plan + apply + prune --apply 통합 |
| `pathmap snapshot` | 없음 | 없음 | Path_Map.json 스냅샷 생성 (`backup` 명칭은 사용자 데이터 백업과 혼동 방지를 위해 deprecated) |
| `pathmap restore <snapshot>` | **쓰기** | **있음** | 스냅샷으로 Path_Map.json 복구 |
| `pathmap rebuild` | 읽기 | 없음 | managed 정션에서 Path_Map.json 초안 역산 (§6.4) |
| `pathmap scan-existing` | 읽기 | 없음 | 현재 FS 구조를 inventory.json으로 출력 (마이그레이션 준비) |
| `pathmap verify-migration` | 읽기 | 없음 | src·dst 전체 파일 SHA256 매니페스트 비교, 검증 토큰 발행 |
| `pathmap migration-commit` | **쓰기** | **있음** | 토큰 재검증 + src/dst 재확인 후 원본 정리 (§6.5) |
| `pathmap backup-plan` | 없음 | 없음 | `BACKUP_POLICY`로 OS별 백업 명령어 출력 |
| `pathmap move <id> <new_target>` | **쓰기** | **있음** | SSOT 물리 경로 이동 + Path_Map.json 갱신 + 링크 재적용 (§6.5의 verify-migration 내장) |
| `pathmap doctor` | 읽기 | 없음 | OS 환경 진단 (Developer Mode, 관리자 권한, NTFS, 경로 길이 제한) |

> **apply 확인 모델:** `pathmap plan` = dry-run. `pathmap apply` = execute. `apply` 자체가 확인 행위이므로 별도 `--apply` 플래그는 존재하지 않습니다. HIGH risk 항목만 추가 토큰 필요.

> **잠금:** 모든 mutating 명령(`apply`, `prune --apply`, `repair`, `restore`, `migration-commit`, `move`)은 `pathmap.lock` 획득 후 실행합니다. 잠금 실패 시 오류 출력. 스테일 잠금(프로세스 사망)은 PID 확인 후 자동 해제.

> **노 오토힐 원칙 (INVARIANT N-07):** pathmap은 어떠한 상황에서도 사용자 확인 없이 FS를 변경하지 않습니다. `status`, `preflight`, `doctor`, `plan`은 읽기 전용. mount/unmount 이벤트가 자동으로 apply/repair를 트리거하지 않습니다.

**Lifecycle Trigger Table (권장 통합 지점):**

| 이벤트 | 권장 pathmap 명령 | 비고 |
|---|---|---|
| 드라이브 마운트 (포터블) | `pathmap preflight && pathmap status` | 드리프트 감지. 자동 heal 없음. |
| Path_Map.json 편집 후 | `pathmap validate && pathmap plan` | 커밋 전 검증 (pre-commit hook 권장) |
| `pathmap apply` 실행 전 | `pathmap snapshot` | 자동: mutating 명령이 내부적으로 수행 |
| 주기적 건강검진 | `pathmap status && pathmap prune` | 크론/수동. 마운트 후 첫 실행 시 |
| 신규 호스트 온보딩 | `pathmap doctor && pathmap validate && pathmap preflight && pathmap apply` | §8 참조 |

### 6.2. Verify 파이프라인

**Phase 0: Preflight** (모든 mutating 명령 전 자동 실행)
- `pathmap.lock` 획득 시도. 실패 시 중단.
- Path_Map.json 파싱 + JSON Schema 검증
- Macro 사이클 탐지 (graph_build 단계)
- 각 entry별: 부모 디렉토리 쓰기 권한, 해당 볼륨 NTFS/ReFS 여부(`GetVolumeInformationW` 또는 `fsutil fsinfo volumeinfo`), link_path 현재 상태(missing/real_dir/broken_link/correct_link 등)
- `allow_cross_drive: false` 항목에서 다른 볼륨 타겟 탐지 시 오류

**Step 1: 매크로 파싱 및 DRIVE_ROOT 해석**
- RUNTIME 매크로 의존 그래프 위상 정렬 → 단일 패스 확장
- `${AUTO_DETECT}` 알고리즘(§5.3) 실행
- `..` 경로 순회 차단, 플랫폼 구분자 정규화

**Step 2: SSOT 존재 검증**
- `target_path` 및 `ssot_origin` 물리 경로 존재 확인
- `expected_target_exists: false`는 경고만

**Step 3: Dead Link 검증**
- `link_path`의 정션/링크 동작 상태 확인
- 상태 분류: missing / correct_link / broken_link / wrong_target / wrong_type / real_file / real_dir

**Step 4: 순환 참조 탐지**
- reparse point 메타데이터 + resolved final path 기반 DFS
- 이미 방문한 resolved path 재방문 시 순환 판정
- 정션 내부 순회 금지 (내부 파일 목록 읽기 금지)
- **Windows 정션 target 경로 읽기 (비순회):** `lstat` 또는 `os.lstat`만으로는 reparse target 경로를 알 수 없음. `CreateFileW(FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS)` 후 `DeviceIoControl(FSCTL_GET_REPARSE_POINT)`로 `SubstituteName`/`PrintName` 파싱. Python: `winreg` 불가 → `ctypes` 또는 `pywin32.win32file.DeviceIoControl` 래핑 사용. 구현체는 이 API 레이어를 추상화하여 플랫폼별 분기.

**Step 5: 고아 정션 탐지 (GC)**

*정방향 스캔 (FS → Registry):*
- `[00_Workspace_Views]` 스캔: lstat/reparse metadata, 내부 순회 금지
- `managed-links.json`에 `resolved_link_path`가 있고 `LOGICAL_VIEWS`에 없음 → "orphaned managed"
- `managed-links.json`에 없음 → "unmanaged" → 절대 삭제 안 함
- `prune --apply`: managed orphan 물리 삭제 **성공 확인 후** 레지스트리에서 제거 (Ghost Junction 방지)

*역방향 스캔 (Registry → FS):*
- `managed-links.json`의 모든 `entries`에 대해 `resolved_link_path` 물리 존재 여부 확인
- 물리 경로가 없고 `LOGICAL_VIEWS`에도 없음 → `managed_orphan_already_absent` 분류
  - `prune` (dry-run): 목록에 "이미 삭제됨, registry 항목 제거 예정" 표시
  - `prune --apply`: 감사 로그에 `actual_result: "already_absent_registry_removed"` 기록 후 registry 항목 제거
- 물리 경로가 없지만 `LOGICAL_VIEWS`에 있음 → apply가 재생성해야 할 항목, prune 대상 아님

**Step 6: Apply Phase**
- lockfile 보유 상태에서만 실행
- plan_hash 생성, dry-run 출력
- HIGH risk: `--confirm-entry` 값이 `entry_id`와 정확히 일치하는지 검증
- `conflict_policy`와 현재 link_state 매트릭스(§5.1) 대조
- 실제 디렉토리는 `--force-replace-dir` 없이 덮어쓰기 금지
- 멱등성 보장: 올바른 링크는 건드리지 않음
- apply 완료 후 `managed-links.json` 원자적 갱신 (temp → rename)
- lockfile 해제

### 6.3. 감사 로그

위치: `[01_User_Space]/99_Path_Dictionary/logs/pathmap_audit.jsonl` (백업 대상)

**보존 정책 (기본값):**
- 보존 기간: **최근 90일** 또는 **50MB** 초과 시 롤링 (둘 중 먼저 도달하는 기준)
- 롤링 방식: `pathmap_audit.jsonl` → `pathmap_audit.2026-06.jsonl` 로 rotate, 압축 선택 가능
- `pathmap doctor`가 로그 크기/나이 경고 출력
- mutating 명령만 로그 기록. 읽기 전용 명령(`status`, `plan`, `preflight`, `validate`)은 로그에 기록하지 않음.

```json
{
  "ts": "2026-06-15T13:10:00Z",
  "operation_id": "op-20260615-001",
  "plan_hash": "sha256:...",
  "schema_version": "2.3.0",
  "pathmap_version": "1.0.0",
  "hostname": "DESKTOP-ABC",
  "actor": "cc",
  "resolved_drive_root": "D:/",
  "command": "pathmap apply",
  "manifest_hash": "sha256:abc123",
  "entry_id": "gemini-dashboard-prompts",
  "link_type": "dir_junction",
  "link_path": "D:/[00_Workspace_Views]/01_Gemini_P2P_Dashboard/prompts",
  "previous_state": "missing",
  "intended_target": "D:/[01_User_Space]/02_Templates_and_Prompts/Gemini_Prompts",
  "actual_result": "created_dir_junction",
  "exit_code": 0,
  "duration_ms": 42,
  "snapshot_path": "snapshots/Path_Map.20260615_131000.json",
  "rollback": "pathmap prune --entry gemini-dashboard-prompts --apply"
}
```

### 6.4. pathmap rebuild — 복구 범위

**시나리오별 복구 신뢰도:**

| 상황 | managed 여부 판단 | 신뢰도 |
|---|---|---|
| `managed-links.json` 있음, audit log 있음 | registry + log 대조 | `confidence: high` |
| `managed-links.json` 없음, audit log 있음 | audit log `actual_result` 기준 | `confidence: partial` |
| `managed-links.json` 없음, audit log 없음 | reparse 메타데이터만 | `confidence: low`, `managed: unknown` |

**복구 가능:** `link_path`, `target_path`, `link_type` (reparse tag), managed 여부 (audit log 대조)

**복구 불가능 (수동 입력 필요):** `entry_id`, `description`, `create_policy`, `conflict_policy`, `expected_target_exists`, `risk_level`, 백업 정책

출력: 각 항목에 `"recovered": true`, `"confidence": "<level>"`. `confidence: low` 항목은 `managed: unknown`으로 표기. `pathmap validate` 통과 전까지 `apply` 불가.

> **전손실(managed-links.json + audit log 모두 소실) 시:** reparse 메타데이터에서 link_path·target_path·link_type만 추출 가능. managed 판정 불가 → 사용자가 수동 검토 후 `entry_id` 등 누락 필드 보완 후 validate 통과 시에만 apply.

### 6.5. CLI 출력 형식 예시 (v2.5)

개발자가 구현 시 참고하는 실제 콘솔 출력 형식입니다.

**`pathmap plan` 출력:**
```
[PATHMAP PLAN] 2026-06-15T15:00:00Z
Plan hash: sha256:a1b2c3d4...

  [CREATE] gemini-dashboard-prompts
    link  : D:\[00_Workspace_Views]\01_Gemini_P2P_Dashboard\prompts
    target: D:\[01_User_Space]\02_Templates_and_Prompts\Gemini_Prompts
    type  : dir_junction
    state : missing → create

  [SKIP]   another-view-already-ok
    link  : D:\[00_Workspace_Views]\02_Project_Alpha_View\docs
    state : correct_link (no change)

  [HIGH-RISK] targetapp-config-outward  ← requires --force-high-risk --confirm-entry
    link  : C:\Users\User\AppData\Roaming\TargetApp\config
    target: D:\[01_User_Space]\98_App_Configs\TargetApp_Config
    type  : dir_junction
    state : missing → create

Summary: 1 create, 1 skip, 1 high-risk pending
Run 'pathmap apply' to execute (high-risk items require extra flags).
```

**`pathmap status` 출력 (혼합 상태):**
```
[PATHMAP STATUS] 2026-06-15T15:05:00Z

  OK       gemini-dashboard-prompts
             → D:\[01_User_Space]\02_Templates_and_Prompts\Gemini_Prompts

  BROKEN   project-alpha-docs
             link : D:\[00_Workspace_Views]\02_Project_Alpha_View\docs
             reason: target not found (D:\[01_User_Space]\01_Development\Alpha → missing)

  ORPHANED another-orphaned-view  [managed]
             link : D:\[00_Workspace_Views]\03_Old_View\legacy
             registry: yes | Path_Map.json: no → candidate for prune

  UNMANAGED D:\[00_Workspace_Views]\04_Unknown_Junction
             registry: no → will NOT be auto-deleted

Summary: 1 OK, 1 broken, 1 managed-orphan, 1 unmanaged
```

**`pathmap prune` 출력 (dry-run):**
```
[PATHMAP PRUNE] 2026-06-15T15:10:00Z  (dry-run — use --apply to delete)

  MANAGED-ORPHAN  [00_Workspace_Views]/03_Old_View/legacy
    registered in managed-links.json, not in Path_Map.json
    action: DELETE (safe — pathmap created this)

  MANAGED-ABSENT  [00_Workspace_Views]/04_Gone_View/files
    registered in managed-links.json, physical path MISSING
    action: REMOVE from registry (already_absent_registry_removed)

  UNMANAGED       [00_Workspace_Views]/05_Manual_Junction
    not in managed-links.json
    action: SKIP (not touching — use explicit delete if intended)

Summary: 1 to delete, 1 registry-only cleanup, 1 skipped (unmanaged)
Run 'pathmap prune --apply' to execute.
```

**`pathmap apply` 실행 출력:**
```
[PATHMAP APPLY] 2026-06-15T15:30:00Z
Plan hash: sha256:a1b2c3d4...  (matches last plan)
Acquiring lock: pathmap.lock ... OK
Taking snapshot: snapshots/Path_Map.20260615_153000.json ... OK

  [CREATING] gemini-dashboard-prompts
    mklink /j "D:\[00_Workspace_Views]\01_Gemini_P2P_Dashboard\prompts" "D:\[01_User_Space]\02_Templates_and_Prompts\Gemini_Prompts"
    Result: dir_junction created OK
    Registry: managed-links.json updated (atomic)
    Audit:    op-20260615-001 logged

  [CREATING] gemini-dashboard-bin
    mklink /j "D:\[00_Workspace_Views]\01_Gemini_P2P_Dashboard\bin" "D:\[02_System_Bin]\Automation_Tools"
    Result: dir_junction created OK
    ...

  [SKIP] another-view-already-ok — correct_link, no change

Summary: 2 created, 1 skipped, 0 errors
Lock released: pathmap.lock
```

**`pathmap doctor` 출력:**
```
[PATHMAP DOCTOR] 2026-06-15T15:35:00Z
Drive root: D:\  (via script path detection)

  [OK]   Windows Developer Mode: ENABLED
  [OK]   NTFS filesystem: D:\ confirmed
  [OK]   Admin rights: not required (dir_junction only)
  [WARN] Max path length: registry LongPathsEnabled = 0 (may cause issues >260 chars)
  [OK]   Python: 3.11.4 at D:\[02_System_Bin]\Automation_Tools\python\python.exe
  [OK]   jsonschema: installed (4.21.1)
  [OK]   pathmap.lock: no stale lock detected
  [OK]   Audit log size: 2.3 MB (within 50 MB limit)
  [OK]   Snapshots: 4 files (within 20 limit)
  [WARN] [00_Workspace_Views] cloud sync: unable to detect OneDrive scope automatically.
         Verify manually: [00_Workspace_Views] must NOT be inside a cloud-sync folder (N-06).

Recommendations:
  - Enable LongPathsEnabled registry key to avoid path length issues.
  - Confirm cloud sync exclusion for [00_Workspace_Views].
```

**`[00_Workspace_Views]` apply 후 터미널 트리 (실제 Gemini 대시보드 예시):**
```
D:\[00_Workspace_Views]\
└── 01_Gemini_P2P_Dashboard\
    ├── prompts  [→ D:\[01_User_Space]\02_Templates_and_Prompts\Gemini_Prompts]  (junction)
    ├── bin      [→ D:\[02_System_Bin]\Automation_Tools]                          (junction)
    └── logs     [→ D:\[04_Volatile_Temp]\Conversation_Logs]                     (junction)

    ← 세 물리 레이어(User_Space/System_Bin/Volatile_Temp)가 하나의 뷰에서 결합됩니다.
    ← Explorer에서는 일반 폴더처럼 보임. `dir /AL` 또는 `Get-Item` 로 reparse 확인.
```

### 6.6. Migration Token 포맷 및 migration-commit 재검증

**verify-migration 토큰 생성 규칙:**
1. 대상 디렉토리의 모든 파일을 **상대경로 알파벳 순** 정렬
2. 각 파일: `{"path": "<relative/path>", "sha256": "<hex>", "size": <bytes>}` 생성
3. 이 목록을 key 정렬 + 공백 없는 JSON 직렬화 → UTF-8 바이트로 SHA256 해시
4. 토큰 형식: `sha256:<hex>` (단순 해시. HMAC 키 불필요 — 단일 사용자 환경)
5. 토큰 저장: `[01_User_Space]/99_Path_Dictionary/logs/migration-<YYYYMMDD_HHMMSS>-<src_hash_prefix>.token.json` (백업 대상 포함)

```json
{
  "schema_version": "2.4.0",
  "expected_manifest_hash": "sha256:abcdef...",
  "src_path": "D:/OldGeminiPrompts",
  "dst_path": "D:/[01_User_Space]/02_Templates_and_Prompts/Gemini_Prompts",
  "file_count": 42,
  "total_bytes": 1048576,
  "created_at": "2026-06-15T13:00:00Z",
  "consumed": false
}
```

> **`expected_manifest_hash` 의미:** `verify-migration` 실행 시 dst 디렉토리의 정규화 매니페스트 SHA256. robocopy 완료 후 src==dst이므로 `SHA256(src_manifest) == SHA256(dst_manifest) == expected_manifest_hash`. 이 단일 해시로 src·dst 양방향 불변성을 검증.

**migration-commit 실행 절차 (원자적):**
1. 토큰 파일 로드 및 `consumed: false` 확인 (재사용 방지)
2. **src 재확인:** 현재 src_path 파일 목록 정규화 매니페스트 해시 재계산 → `expected_manifest_hash`와 비교 (src가 verify 이후 변경되지 않았는지 확인)
3. **dst 재확인:** 현재 dst_path 매니페스트 해시 재계산 → `expected_manifest_hash`와 비교 (dst가 변경되지 않았는지 확인)
4. 두 검증 모두 통과 후 감사 로그에 `migration_commit_begin` 이벤트 기록 (crash 복구 앵커)
5. 토큰 `consumed: true`로 원자적 갱신 (temp → rename)
6. src 정리 실행 (Rename-Item 또는 삭제)
7. 감사 로그에 `migration_commit_complete` 이벤트 기록

> **Crash 복구:** 감사 로그에 `migration_commit_begin`은 있으나 `migration_commit_complete`가 없고 토큰 `consumed: true`인 경우 → src 정리 미완료 가능성. 사용자 수동 확인 필요.

> **검증 실패 시:** commit 중단. 원본 보존. 사용자에게 `pathmap verify-migration --mode full-hash`를 다시 실행하도록 안내.

---

## 7. 백업 전략 및 재해 복구

### 7.1. 백업 대상 및 도구 규칙

| 대상 | 백업 | 비고 |
|---|---|---|
| `[01_User_Space]` | **필수 (1순위)** | `/XJ` 필수. managed-links.json·감사 로그 포함 |
| `[03_Archive_Media]` | **별도 정책** | 증분 백업 권장 |
| `[02_System_Bin]` | 선택 | |
| `[00_Workspace_Views]` | **제외 필수** | 순회 시 2중 복사 + 무한루프 위험 |
| `[04_Volatile_Temp]` | **제외 필수** | |

**`pathmap backup-plan` 출력 예시 (Windows):**
```bat
REM [01_User_Space] 전체 백업 (정션 제외, App_State 우선순위 낮음으로 별도 처리)
robocopy "D:\[01_User_Space]" "E:\Backup\User_Space" /MIR /XJ /XD "03_App_State" /W:1 /R:1 /LOG:backup.log

REM [01_User_Space]\03_App_State 별도 백업 (낮은 우선순위 — 선택적 실행)
robocopy "D:\[01_User_Space]\03_App_State" "E:\Backup\App_State" /MIR /XJ /W:1 /R:1 /LOG:app_state_backup.log
```

> **03_App_State 분리 이유:** `[01_User_Space]` 전체가 백업 1순위이지만 `03_App_State`는 대용량 앱 상태(수 GB 가능)로 백업 주기·우선순위가 다릅니다. `backup-plan`이 두 단계로 분리된 명령을 생성합니다. (BACKUP_POLICY.exclude 항목에 `${USER_SPACE}/03_App_State` 추가 가능)

### 7.2. Path_Map.json 보호

1. mutating 명령 전 자동 스냅샷 (`snapshots/Path_Map.{YYYYMMDD_HHMMSS}.json`)
2. 스키마 검증 게이트
3. `pathmap restore <snapshot>` 복구 명령
4. `pathmap rebuild` 최소 복구 경로

**스냅샷 보존 정책 (기본값):** 최근 **20개** 유지. 초과 시 가장 오래된 것부터 삭제. `pathmap snapshot --list`로 목록 확인. `pathmap snapshot --prune`으로 수동 정리.

### 7.3. 재해 복구 시나리오

| 시나리오 | 복구 절차 |
|---|---|
| Path_Map.json 삭제 | `pathmap restore <latest_snapshot>` |
| 뷰 레이어 정션 전체 소멸 | `pathmap apply` (SSOT는 물리 레이어에 그대로) |
| managed-links.json 손실 | `pathmap rebuild` → 수동 검토 → validate 후 apply |
| DRIVE_ROOT 중복 | `PATHMAP_DRIVE_ROOT` 환경 변수 설정 |
| Ghost Junction 탐지 | `pathmap prune` → 수동 확인 → `prune --apply` |
| pathmap.lock 스테일 | PID 확인 후 잠금 해제 → 재실행 |
| 수동 정션 삭제 후 registry stale | `pathmap prune` → `managed_orphan_already_absent` 탐지 → `prune --apply` |
| migration-commit 중 crash | 감사 로그 확인 (begin/complete 쌍) → dst 확인 → src 수동 정리 |
| SSOT 경로 수동 이동 → 정션 깨짐 | `pathmap status` 로 broken 탐지 → `pathmap move <id> <new_actual_path>` |
| 드라이브 레터 변경 | relative_link_path 자동 재해석. drive_root_migrated 감사 로그 확인 |

---

## 8. Host 온보딩 프로토콜

**Phase -1: pathmap 설치 (최초 1회)**

pathmap 자체는 `[02_System_Bin]/Automation_Tools/pathmap/` 에 위치합니다. 새 호스트에 드라이브를 마운트한 직후, pathmap이 없는 상태에서 따르는 제로 의존성 절차:

```bat
REM 1. 드라이브 레터 확인 (예: D:)
REM 2. pathmap CLI 진입점 등록 (PATH 추가)
set PATH=%PATH%;D:\[02_System_Bin]\Automation_Tools\pathmap

REM 3. 의존성 확인
python --version        REM Python 3.9+ 필요
pip install jsonschema  REM 없으면 설치

REM 4. pathmap 자기 검증
python D:\[02_System_Bin]\Automation_Tools\pathmap\pathmap.py --version
```

> **Python이 없는 경우:** `[02_System_Bin]/Automation_Tools/pathmap/` 내에 Python 임베디드 배포본(`python-3.x-embed-amd64.zip` 압축 해제)을 포함하면 호스트 Python 불필요. 또는 PyInstaller로 빌드된 `pathmap.exe` 단일 바이너리 배포 (NICE-TO-HAVE). 최소 대안: `bootstrap.ps1` (순수 PowerShell) 이 정션 생성만 수행, pathmap 없이도 초기 VIEWS_ROOT 구축 가능.

> **[02_System_Bin]이 아직 없는 경우 (완전 신규 드라이브):** 최초 한 번은 수동으로 `[02_System_Bin]\Automation_Tools\pathmap` 폴더를 생성 후 pathmap 파일 복사. 이후 pathmap이 자기 자신의 경로를 관리 가능.

> **pathmap 자체의 Path_Map.json 항목:** pathmap CLI는 `[02_System_Bin]`에 물리적으로 위치하며, 별도의 논리 뷰 링크는 선택 사항입니다.

**Phase 0: 사전 준비**
- 드라이브 마운트 확인. 중복 드라이브 시 `PATHMAP_DRIVE_ROOT` 설정.
- `pathmap doctor` 실행 (Developer Mode, 권한, NTFS, 경로 길이 진단)

**Phase 1: Bootstrap**
```bat
set PATHMAP_DRIVE_ROOT=E:\   REM 필요 시
pathmap validate
pathmap preflight
```

**Phase 2: 뷰 레이어 구성**
```bat
pathmap plan
pathmap apply
```

**Phase 3: 검증**
```bat
pathmap status
pathmap prune
```

**Phase 4: 온보딩 체크리스트**
- [ ] `pathmap validate` 오류 없음
- [ ] `pathmap preflight` 오류 없음
- [ ] `pathmap status` 모든 항목 OK
- [ ] 백업 도구 `[00_Workspace_Views]` 제외 설정
- [ ] `.gitignore` 확인

---

## 9. 마이그레이션 가이드

### Step 1: 현황 인벤토리
```bat
pathmap scan-existing --output inventory.json
```

### Step 2: MECE 분류
§부록-A 결정 테이블 참조.

### Step 3: SSOT 데이터 이동 (Copy-Verify-Delete 패턴)

> **[CRITICAL] `/MOVE` 금지.** 중간 장애 시 데이터가 양쪽에 분할됩니다.

```bat
REM 1단계: 복사 (원본 보존)
robocopy "D:\OldGeminiPrompts" "D:\[01_User_Space]\02_Templates_and_Prompts\Gemini_Prompts" /E /COPY:DAT /DCOPY:DAT /LOG:migrate_copy.log

REM 2단계: 전체 해시 검증 + 토큰 발행
pathmap verify-migration --src "D:\OldGeminiPrompts" --dst "D:\[01_User_Space]\02_Templates_and_Prompts\Gemini_Prompts" --mode full-hash --emit-token

REM 3단계: 토큰 확인 후 원본 정리 (migration-commit이 src/dst 재검증 + 원자적 토큰 소비)
pathmap migration-commit --token "<token-file-path>"
```

**실패 시 안전:** 복사(1단계) 실패 → 원본 그대로. 검증(2단계) 실패 → 원본 그대로. commit(3단계) 재검증 실패 → commit 중단, 원본 보존.

### Step 4: Path_Map.json 작성
```bat
pathmap init  REM 기본 템플릿 생성
```

### Step 5: Dry-run 검증
```bat
pathmap validate && pathmap preflight && pathmap plan
```

### Step 6: 뷰 레이어 구성
```bat
pathmap apply && pathmap status
```

### Step 7: 앱 고정 경로 예외 (선택, 신중하게)
```bat
pathmap backup
pathmap apply --entry targetapp-config-outward --force-high-risk --confirm-entry targetapp-config-outward
```

### Step 8: 롤백
```bat
pathmap prune --all --apply

REM Copy-Verify-Delete 역방향
robocopy "D:\[01_User_Space]\..." "D:\OldGeminiPrompts_RESTORED" /E /COPY:DAT
pathmap verify-migration --src "D:\[01_User_Space]\..." --dst "D:\OldGeminiPrompts_RESTORED" --mode full-hash --emit-token
pathmap migration-commit --token "<token-file-path>"
```

---

## 10. Linux XDG Base Directory 비교 (v2.3)

| 항목 | XDG | 본 아키텍처 v2.3 |
|---|---|---|
| 핵심 초점 | 앱 표준화 | 사용자 워크플로우 표준화 |
| 물리-논리 분리 | 없음 | `[00_Workspace_Views]` 완전 분리 |
| Config vs Data | `XDG_CONFIG_HOME` / `XDG_DATA_HOME` | `[01_User_Space]` 내 `98_App_Configs` |
| State 데이터 | `XDG_STATE_HOME` | `[01_User_Space]/03_App_State` |
| Runtime 데이터 | `XDG_RUNTIME_DIR` | `[04_Volatile_Temp]` |
| 검증 체계 | 런타임 환경 변수 의존 | Path_Map.json IaC + pathmap CLI |
| 예외 앱 대응 | 불가 | Outward Junction + On-Mount Sync |
| 포터빌리티 | 해당 없음 | `${AUTO_DETECT}` 동적 감지 |

---

## 11. 툴링 요건

### 11.1. 지원 OS 및 파일시스템

| 항목 | Windows | Linux/macOS |
|---|---|---|
| 최소 OS | Windows 10 1607+ | 커널 3.0+ |
| 파일시스템 | **NTFS 또는 ReFS** (FAT32/exFAT 정션 불가) | ext4, btrfs, APFS |
| FS 타입 확인 | `GetVolumeInformationW` 또는 `fsutil fsinfo volumeinfo <root>` | `stat -f -c %T` |

### 11.2. pathmap CLI 요건
- Python 3.9+ 또는 PowerShell 5.1+
- Python 패키지: `jsonschema`
- 관리자 권한: `dir_junction` 불필요. `dir_symlink`/`file_symlink` — Developer Mode 또는 권한 필요

### 11.3. Git 연동

```gitignore
[00_Workspace_Views]/
[04_Volatile_Temp]/
[01_User_Space]/99_Path_Dictionary/Path_Map.status.json
[01_User_Space]/99_Path_Dictionary/snapshots/
[01_User_Space]/99_Path_Dictionary/pathmap.lock
```

추적 대상: `Path_Map.json`, `Path_Map.schema.json`, `managed-links.json`, `logs/pathmap_audit.jsonl`

### 11.4. 해시 검증 도구

| OS | 도구 | 명령 |
|---|---|---|
| Windows | `certutil` (기본) | `certutil -hashfile <file> SHA256` |
| Windows | `Get-FileHash` (PowerShell) | `Get-FileHash <file> -Algorithm SHA256` |
| Linux/macOS | `sha256sum` | `sha256sum <file>` |

**결정론적 매니페스트 생성 규칙:**
- 파일 목록: 상대경로 알파벳 순 정렬 (대소문자 구분: platform_native)
- JSON 직렬화: key 알파벳 정렬, 공백 없음, UTF-8 인코딩
- 심볼릭 링크: 링크 자체를 파일로 처리하지 않음 (target 파일만 해시)

---

## 12. MVP 구현 우선순위

단일 사용자 포터블 환경에서 안전한 v1.0 pathmap 구현 로드맵.

**MUST (안전 핵심 — 없으면 운영 불가):**
- `validate`, `preflight`, `plan`, `apply` (dual-token HIGH risk 포함)
- **`status`** ← 현재 링크 상태 전체 보고. prune 실행 전 필수 선행 확인
- `managed-links.json` 레지스트리 (primary key: relative_link_path, DRIVE_ROOT 상대경로)
- `pathmap.lock` (동시 실행 방지)
- Ghost Junction 방지 (물리 삭제 확인 후 registry 갱신)
- 감사 로그 (보존 정책 포함)
- `prune` (읽기 전용 orphan 목록) + `prune --apply` (managed orphan 정리)
- `snapshot` (구 `backup`; mutating 명령 전 자동 실행)

**SHOULD (유지보수 — 없으면 장기 운영 불편):**
- `restore`, `backup-plan`
- `rebuild` (재해 복구)
- `doctor` (온보딩 진단, 로그 크기 경고)
- `repair` (plan + apply + prune --apply; dry-run preview 필수)
- **On-Mount Lifecycle Hook** ← 포터블 드라이브의 핵심 피드백 루프 트리거. 드라이브 마운트 시 `pathmap preflight && pathmap status` 자동 실행. OS별 구현(Windows: autorun 대안 또는 수동 스크립트; 자동 apply는 N-07 금지)
- **`move <id> <new_target>`** ← SSOT 물리 경로 안전 이동. 5 Whys 분석에서 "정션 깨짐"의 #1 원인(수동 이동) 방지 (N-09)

**NICE-TO-HAVE (고급 기능):**
- `verify-migration`, `migration-commit`, `scan-existing`
- `Path_Map.local.json` (팀 환경 per-user override)
- 감사 로그 자동 롤링 명령 (`pathmap log-rotate`)
- per-entry lifecycle 필드 (`disabled: true`, `last_verified` 등) — v2.0 대상

---

## 부록 A: MECE 분류 결정 테이블

| 항목 특성 | 귀속 위치 |
|---|---|
| 사용자 직접 작성·편집 데이터 | `[01_User_Space]` |
| 앱 고정 경로 강제 + 사용자 값 포함 | `[01_User_Space]/98_App_Configs` |
| 앱 State (영구 but 낮은 백업 우선순위) | `[01_User_Space]/03_App_State` |
| 재현 가능한 실행 파일/런타임 | `[02_System_Bin]` |
| pip/npm 글로벌 도구 (설정 없음) | `[02_System_Bin]` |
| pip/npm 글로벌 도구 (설정 포함) | 바이너리 → `[02_System_Bin]`, 설정 → `[01_User_Space]` |
| 대용량 비휘발성 cold data | `[03_Archive_Media]` |
| 시스템 캐시·로그 | `[04_Volatile_Temp]` |
| 세션 바운드 런타임 데이터 | `[04_Volatile_Temp]` |
| 분류 미결정 | 해당 레이어 `[00_Inbox]` |

> 더 복잡한 케이스는 **부록 D: MECE 경계 및 모호 케이스** 참조.

---

## 부록 D: MECE 경계 및 모호 케이스

실제 운영에서 분류가 모호한 항목과 권고 결정 근거. 아키텍처의 자족성(self-containment)을 위해 명시적으로 기록합니다.

| 항목 | 권고 위치 | 결정 근거 | 주의 |
|---|---|---|---|
| **AI 생성 출력 파일** (GPT/Gemini 응답 저장본) | `[01_User_Space]` | 사용자 가치 있음, 재생성 가능하나 원본 컨텍스트 손실 | 대량 누적 시 `03_App_State`나 `[03_Archive_Media]`로 분류 재검토 |
| **다운로드 참조 PDF/전자책** | `[03_Archive_Media]` | cold data, 재다운로드 가능, 대용량 | 직접 편집하는 PDF(어노테이션 포함)는 `[01_User_Space]` |
| **Git 레포 (코드만)** | `[01_User_Space]/01_Development` | 사용자 저작물 | `.git` 오브젝트 DB 포함으로 대용량 가능 — 문제없음 |
| **Git 레포 (대형 바이너리 포함)** | 코드 → `[01_User_Space]/01_Development`, LFS 스토어 → `[03_Archive_Media]` | 분리 권고. 코드 이력은 SSOT, 바이너리 원본은 cold | Git LFS remote 사용 권장 |
| **SSH 키 / API 토큰 / `.env` 파일** | `[01_User_Space]/98_App_Configs` | 앱 설정의 일종. 백업 1순위 | 암호화 필수. 절대 git 추적하지 말 것 |
| **VeraCrypt / BitLocker 컨테이너 파일** | `[03_Archive_Media]` | cold, 대용량, 내부 구조 불투명 | pathmap은 컨테이너 내부를 관리하지 않음 |
| **OneDrive 가상 파일 (placeholder)** | 관리 범위 밖 (out-of-scope) | NTFS reparse point 충돌 가능. pathmap 대상 아님 | OneDrive sync 범위에서 제외 후 별도 관리 |
| **UNC 경로 파일 (`\\server\share`)** | 관리 범위 밖 (out-of-scope) | `dir_junction`은 UNC target 불가 (§5.2 링크 제약) | `dir_symlink` 사용 시 가능하나 portability 저하 |
| **팀 공유 폴더 / 공용 드라이브** | 관리 범위 밖 (out-of-scope) | SSOT 전제(단일 소유자) 붕괴. pathmap은 단일 사용자 포터블 환경 전용 | 팀 환경은 `Path_Map.local.json` + 별도 정책 필요 |
| **자동화 스크립트 (사용자 저작)** | 소스코드 → `[01_User_Space]/01_Development`, 실행 링크 → `[00_Workspace_Views]` 또는 PATH | MECE 분리: 저작(SSOT) vs 런타임(링크). `[02_System_Bin]/Automation_Tools`에 정션으로 노출 권고 | |
| **암호화된 노트 앱 DB (Obsidian vault 등)** | `[01_User_Space]` | 사용자 직접 작성·편집 데이터. 백업 1순위 | 앱이 vault 경로를 고정 요구하면 `98_App_Configs` + Outward Junction |
| **클라우드 전용 데이터 (Google Docs, Notion)** | 관리 범위 밖 (out-of-scope) | 로컬 FS 없음. pathmap 대상 아님 | 로컬 export 파일은 `[03_Archive_Media]` |

**분류 결정 원칙 (Grey Zone 적용 순서):**
1. **소유권:** 내가 직접 만들거나 편집하는가? → `[01_User_Space]`
2. **수명:** cold하고 거의 변경 없는가? → `[03_Archive_Media]`
3. **재현성:** 삭제해도 재설치/재다운로드 가능한가? → `[02_System_Bin]`
4. **휘발성:** 세션이 끝나면 버려도 되는가? → `[04_Volatile_Temp]`
5. **결정 보류:** → 해당 레이어 `[00_Inbox]`에 임시 배치 후 재분류

---

## 부록 B: 알려진 위험 패턴

| 위험 패턴 | 대응 |
|---|---|
| 백업 도구 정션 순회 | `/XJ` 또는 `--no-dereference` 필수 |
| Outward Junction + 드라이브 분리 | On-Mount Sync Script 대안 |
| 앱 Atomic Save → 파일 링크 소멸 | 디렉토리 단위 정션 사용 |
| 앱 언인스톨러 정션 통해 SSOT 삭제 | 적용 전 언인스톨러 동작 검증 |
| 마이그레이션 중 `/MOVE` 사용 | Copy-Verify-Delete 패턴 필수 |
| migration-commit 스테일 토큰 | commit 전 src/dst 재검증 + 원자적 토큰 소비 |
| prune 중 Active Handle | 물리 삭제 성공 확인 후 레지스트리 갱신 |
| Ghost Junction | prune --apply의 2단계 확인으로 방지 |
| managed-links.json race condition | pathmap.lock 으로 방지 |
| View-in-View (target → VIEWS_ROOT) | validate 단계에서 차단 |
| DRIVE_ROOT 중복 드라이브 | ambiguity error + PATHMAP_DRIVE_ROOT |
| Path_Map.json 손상 | 스냅샷 + restore |
| managed-links.json entry_id rename | resolved_link_path primary key로 동일 항목 처리 |
| migration-commit 중 crash | migration_commit_begin 감사 이벤트 → begin있고 complete없으면 src 정리 미완료 감지 |
| 수동 정션 삭제 후 registry stale entry | prune 역방향 스캔 (Registry→FS) → managed_orphan_already_absent 제거 |
| managed-links.json + audit log 전손실 | pathmap rebuild → confidence: low, managed: unknown → 사용자 수동 검토 필수 |
| retarget (같은 link_path, 다른 target) | apply가 conflict_policy에 따라 처리, registry atomically 덮어씀 |
| [00_Workspace_Views] 클라우드 동기화 포함 | MUST-NOT (N-06). 정션이 일반 폴더로 처리되어 원본 파일 전체 업로드 또는 동기화 무한루프 위험 |
| 드라이브 레터 변경 후 registry 불일치 | relative_link_path 사용으로 자동 해소. drive_root_at_last_write 비교로 변경 감지 |
| SSOT 경로 수동 이동 후 정션 깨짐 | `pathmap move <id> <new_target>` 사용. 수동 이동 시 status → 깨진 링크 탐지 → Path_Map.json 갱신 후 apply |

---

## 부록 C: 테스트 케이스 체크리스트

**validate:**
- [ ] 올바른 파일 → PASS
- [ ] 잘못된 JSON → FAIL
- [ ] 미정의 매크로 → FAIL
- [ ] `..` 경로 → FAIL
- [ ] 매크로 사이클 (A→B→A) → FAIL
- [ ] 중복 `entry_id` → FAIL
- [ ] 중복 `link_path` → FAIL
- [ ] `target_path`가 `VIEWS_ROOT` 하위 (View-in-View) → FAIL

**preflight:**
- [ ] 부모 디렉토리 쓰기 권한 없음 → FAIL
- [ ] FAT32 볼륨 + `dir_junction` → FAIL
- [ ] link_path에 실제 디렉토리 존재 + `error_if_real_dir_exists` → FAIL
- [ ] `allow_cross_drive: false` + 다른 드라이브 타겟 → FAIL

**apply:**
- [ ] 동일 명령 2회 (idempotency) → 2회째 NO-OP
- [ ] HIGH risk + `--force-high-risk` 없음 → FAIL
- [ ] HIGH risk + 잘못된 `--confirm-entry` → FAIL
- [ ] 동시 실행 2개 터미널 → 2번째 lockfile 실패
- [ ] 감사 로그 생성 확인
- [ ] managed-links.json 원자적 갱신 확인

**prune:**
- [ ] managed orphan 탐지 → 목록만 출력
- [ ] unmanaged 정션 → "unmanaged" 표시, 삭제 안 함
- [ ] `prune --apply` 중 Active Handle → 삭제 실패 → registry 미갱신 (Ghost Junction 방지)
- [ ] `prune --apply` 성공 → registry에서 제거 확인

**migration:**
- [ ] `verify-migration` 동일 내용 → 동일 토큰 (결정론)
- [ ] `verify-migration` 파일 1개 변경 → 다른 토큰
- [ ] `migration-commit` 토큰 소비 후 재사용 → FAIL
- [ ] `migration-commit` src 변경 후 → 재검증 실패 → commit 중단
- [ ] `migration-commit` 성공 → src 정리 + `migration_commit_begin` + `migration_commit_complete` 감사 이벤트
- [ ] `migration-commit` crash 시뮬레이션 (begin 있고 complete 없음) → 재실행 시 crash 감지 경고 출력
- [ ] 토큰 `expected_manifest_hash` 필드로 src/dst 양방향 검증 확인

**rebuild:**
- [ ] managed-links.json 있음 + audit log 있음 → `confidence: high`
- [ ] managed-links.json 없음 + audit log 있음 → `confidence: partial`, `recovered: true`
- [ ] managed-links.json 없음 + audit log 없음 → `confidence: low`, `managed: unknown`
- [ ] 복구 불가능 필드 누락 → validate FAIL

**prune (추가):**
- [ ] managed-links.json 항목이지만 물리 경로 없음 (수동 삭제) → `managed_orphan_already_absent`
- [ ] `prune --apply` → registry 항목 제거 + 감사 로그 `already_absent_registry_removed`

**registry retarget:**
- [ ] 같은 `link_path` 다른 target → apply가 `conflict_policy: replace_wrong_link`로 처리
- [ ] 성공 시 managed-links.json 해당 항목 new target으로 atomic 갱신

**doctor:**
- [ ] Developer Mode 꺼짐 + `dir_symlink` 항목 존재 → WARNING
- [ ] 경로 길이 260자 초과 가능성 → WARNING
- [ ] 감사 로그 50MB 초과 → WARNING
- [ ] 스냅샷 20개 초과 → WARNING

**portability (v2.5):**
- [ ] 드라이브 레터 D: → E: 변경 후 pathmap 재실행 → drive_root_migrated 이벤트 + 정상 동작
- [ ] managed-links.json primary key가 relative_link_path 형태인지 확인
- [ ] APP_HARDCODED_EXCEPTIONS 항목: host_specific=true 확인
- [ ] 다른 호스트에서 host_specific 항목 prune 대상 제외 확인

**MUST-NOT 경계:**
- [ ] [00_Workspace_Views] 하위에 실제 파일 생성 시도 → apply에서 차단
- [ ] `pathmap status` 실행 → 감사 로그에 기록되지 않음 (읽기 명령)
- [ ] `pathmap plan` 실행 → FS 변경 없음 확인
- [ ] AUTO 모드 없음 확인: mount 이벤트로 자동 apply/repair 없음

**lifecycle trigger:**
- [ ] Lifecycle Trigger Table 참고하여 on-mount 수동 스크립트 실행 시 preflight+status 정상 동작
