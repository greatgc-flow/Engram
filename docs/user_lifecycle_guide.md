# [User Guide] Engram & PeerHub 스마트 수명주기(백업/복구/리셋) 사용자 매뉴얼

사용자 입장에서 **"평소에", "PC를 옮길 때", "문제가 생겨 초기화할 때", "완전히 삭제할 때"** 어떻게 명령어를 사용하면 되는지 한눈에 알기 쉽게 정리한 실전 가이드입니다.

복잡한 내부 방어 로직(디스크 검증, Inode 순환 감지, SQLite 원자적 백업, Fail-Closed 안전 가드)은 **시스템이 백그라운드에서 100% 자동 처리**하므로, 사용자는 **단 몇 줄의 간단한 명령어**만 기억하시면 됩니다.

---

## ⚡ 3초 요약 치트시트 (자주 쓰는 핵심 명령어)

| 내가 하고 싶은 일 | 실행할 명령어 | 무엇이 일어나는가? |
| :--- | :--- | :--- |
| **지금 상태 안전하게 백업하기** | `engram backup` | 세션/두뇌/설정/DB 자동 압축 + 미포함 파일 발견 시 대화형 포함 질의 |
| **특정 위치로 백업 파일 저장** | `engram backup --out D:\MyBackup.zip` | 지정한 경로에 단일 `.zip` 압축본 생성 |
| **백업해둔 파일로 복원하기** | `engram restore D:\MyBackup.zip` | 기존 데이터 안전 스냅샷 후 표준+추가 파일 원래 위치로 100% 복원 |
| **깨끗하게 초기화 (리셋)** | `engram reset` | 직전 스냅샷 자동 생성 후 `.engram`/`.peerhub` 완전 삭제 (다음 실행 시 자동 재생성) |
| **Engram 프로그램 완전 삭제** | `engram uninstall --purge-data` | 레지스트리 제거 및 런타임/데이터 완전 정리 |

---

## 🛠️ 실전 시나리오별 사용 가이드

### 시나리오 1: 일상적인 정기 백업 또는 PC 이전 준비
> **"지금까지 나눈 모든 AI 대화, 두뇌 메모리, 프롬프트, 도구 설정을 안전하게 백업하고 싶다!"**

#### 실행 방법:
```powershell
PS D:\PortableDev> engram backup
```

#### 터미널 화면 흐름:
```text
[Engram Backup] Scanning portable workspace for state and configurations...

[Standard Targets] (All included by default):
  [OK] .engram/agy (settings, skills, brain, conversations - 1.4 GB)
  [OK] .engram/claude (settings, projects - 400 MB)
  [OK] .engram/codex (config, rules, sessions - 1.2 GB)
  [OK] .peerhub (workspace database & routing)
  [OK] _sys/local.config.bat

[Uncovered Items Detected] 
The following user-created items are not in standard backup:
  [1] workspace/my-project/.peerhub/ (Sub-project DB, 1.2 MB)
  [2] D:\PortableDev\my_custom_script.py (Custom script, 4 KB)

Include these uncovered items in this backup bundle? [Y/n/select]: y
[OK] 2 extra items appended to backup manifest.

[Pre-flight] Disk space verified: 45.2 GB free (Required: ~1.2 GB).
Packaging streaming backup: D:\PortableDev\_sys\data\backups\engram_backup_20260930_173000.zip (820 MB)
Done! Backup completed safely.
```
- 사용자는 화면을 보고 엔터(`y`)만 치면 끝납니다.
- 만약 사내 보안 정책 등으로 스크립트에서 자동화하고 싶다면:
  - `engram backup --include-uncovered`: 질문 없이 미포함 파일까지 모두 자동 포함
  - `engram backup --ignore-uncovered`: 질문 없이 표준 파일만 가볍게 백업

---

### 시나리오 2: 새 PC로 이전했거나 이전 시점으로 복원할 때
> **"새 노트북을 샀거나 문제가 생겨서 이전 백업본으로 되돌리고 싶다!"**

#### 실행 방법:
```powershell
PS D:\PortableDev> engram restore D:\Backups\engram_backup_20260930_173000.zip
```

#### 터미널 화면 흐름:
```text
[Engram Restore] Inspecting backup archive: D:\Backups\engram_backup_20260930_173000.zip
Manifest Version: 2 (Created at 2026-09-30 17:30 UTC)

Archive Contents:
  - Standard: agy, claude, codex, peerhub_root, local_config
  - Custom Extras: workspace/my-project/.peerhub, my_custom_script.py

[Safety] Creating pre-restore snapshot of current live state...
[OK] Safety snapshot saved: _sys/data/backups/pre_restore_20260930_173500.zip

Restoring items...
  [OK] .engram/agy restored (29,620 files)
  [OK] .engram/claude restored (2,296 files)
  [OK] .engram/codex restored (810 files)
  [OK] .peerhub restored (PeerHub SQLite schema & epoch reconciled)
  [OK] workspace/my-project/.peerhub restored
  [OK] my_custom_script.py restored

Done! All AI personal data and custom items have been restored.
```
- 복원 시 현재 상태를 먼저 안전 스냅샷으로 백업해두므로, 실수로 복원 명령을 내려도 기존 데이터가 날아가지 않습니다.
- 사용자가 백업 시 함께 묶었던 추가 파일(`custom_extras`)도 원래 위치로 자동 복원됩니다.

---

### 시나리오 3: 환경이 꼬여서 깨끗하게 초기화(Clean Reset)하고 싶을 때
> **"도구 설정이나 세션이 꼬여서 공장 초기화 상태로 깨끗하게 다시 시작하고 싶다!"**

#### 실행 방법:
```powershell
PS D:\PortableDev> engram reset
```

#### 터미널 화면 흐름:
```text
[Engram Reset]
Resetting will completely purge .engram/ and .peerhub/ directories.
(Your project source codes in workspace/ will be KEPT SAFE).

[Phase 1: Safety Snapshot]
Creating mandatory safety snapshot before deletion...
[OK] Snapshot created & verified: _sys/data/backups/safety_pre_reset_20260930_174000.zip

[Phase 2: Clean Sweep]
  [OK] Atomic rename & purged: .engram/
  [OK] Atomic rename & purged: .peerhub/

Reset complete. The system is in pristine state.
Next time you run 'engram' or an AI CLI, empty skeletons will be auto-scaffolded instantly.
```
- 사용자는 초기화 전 백업을 깜빡했더라도 걱정할 필요가 없습니다. 삭제 직전의 완벽한 스냅샷이 `safety_pre_reset_*.zip`에 무조건 저장됩니다.
- 초기화 후 사용자가 `engram` 또는 `peerhub status`를 실행하면, **0.001초 만에 깨끗한 빈 폴더 구조가 저절로 복구(Self-Healing)**됩니다.

---

### 시나리오 4: Engram을 완전히 언인스톨(삭제)할 때
> **"이 컴퓨터에서 Engram을 완전히 지우고 레지스트리까지 깨끗하게 정리하고 싶다!"**

#### 실행 방법:
```powershell
PS D:\PortableDev> engram uninstall --purge-data
```
- 윈도우 우클릭 컨텍스트 메뉴("Open in Engram")가 레지스트리에서 말끔히 등록 해제됩니다.
- 실행 중이던 프로세스가 안전 종료되고, `_sys`, `.engram`, `.peerhub`가 안전하게 디스크에서 삭제됩니다.

---

## 📌 요약: 사용자가 기억할 단 한 문장

> **"평소엔 `engram backup`, 되돌릴 땐 `engram restore`, 비우고 싶을 땐 `engram reset`만 입력하세요. 미포함 파일 감지, 사전 용량 체크, 복원 안전망은 시스템이 알아서 다 해줍니다!"**

> Python/venv 복구, 폴더 이동(`engram relocate`), 백업 레지스트리(`engram snapshots`)는 [env_resilience_guide.md](env_resilience_guide.md)를 참고하세요.
