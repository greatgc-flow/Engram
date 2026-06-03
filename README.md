# 포터블 샌드박스 개발환경

Windows 단일 폴더 기반 포터블 개발환경.  
USB 또는 클라우드 드라이브에 넣고 어느 PC에서나 동일하게 사용합니다.

---

## 폴더 구조

```
[PortableDev]/                ← 루트 (docs + install.bat + register.bat + unregister.bat + workspace + .claude + _sys)
│
├── install.bat               ← ★ 최초 1회 더블클릭 → setup.ps1 자동 설치
├── register.bat              ← ★ PC 등록 (SUBST 할당 + 우클릭 메뉴); manage.ps1 호출
├── unregister.bat            ← PC 영구 제거 (컨텍스트 메뉴 + SUBST 삭제); manage.ps1 호출
├── CLAUDE.md                 ← Claude Code 인수인계 (claude 실행 시 자동 읽힘)
├── README.md
├── CONVENTION.md             ← 코딩 규칙 (에이전트 팀 품질 기준)
├── workspace/                ← 기본 작업 폴더 (외부 폴더도 자유롭게 사용 가능)
├── .claude/                  ← Claude Code 하네스 (agents/, skills/)
│
└── _sys/                     ← 시스템 전체 (스크립트 + 런타임 + 데이터)
    ├── start.bat             ← 메인 런처
    ├── manage.ps1            ← ★ 통합 매니저 (등록/해제/상태 관리)
    ├── launch.ps1            ← 레지스트리 중계 (직접 실행 안 함)
    ├── setup.ps1             ← ★ 제로베이스 자동 설치 스크립트
    ├── cleanup.ps1           ← 임시파일/캐시 정리 (용량 최적화)
    ├── local.config.bat.template  ← PC별 설정 템플릿 (복사 후 .template 제거)
    │
    ├── context/
    │   ├── ctx-save.bat         ← 세션 중 체크포인트 (세션 유지)
    │   ├── ctx-end.bat          ← 세션 종료 요약
    │   ├── CLAUDE_project.md    ← 프로젝트 CLAUDE.md 템플릿
    │   └── CLAUDE_global.md     ← 전역 CLAUDE.md 템플릿
    │
    ├── git-config/
    │   └── .gitconfig           ← 포터블 Git 설정 (delta 연동 포함)
    │
    ├── env/                  ← 런타임 바이너리
    │   ├── python/           ← 포터블 Python (Embeddable)
    │   ├── nodejs/           ← 포터블 Node.js
    │   ├── ffmpeg/bin/       ← FFmpeg
    │   ├── git/              ← 포터블 Git
    │   ├── vscode/           ← VS Code 포터블 (data/ 폴더로 포터블 모드 활성화)
    │   └── venv/             ← Python 가상환경 (자동 생성)
    │
    ├── tools/                ← 선택 도구 (폴더 있으면 자동 PATH 추가)
    │   ├── ripgrep/ → rg.exe    [설치됨] — Claude Code 내부 사용
    │   ├── fd/      → fd.exe    [설치됨] — Claude Code 내부 사용
    │   ├── jq/      → jq.exe    [설치됨]
    │   ├── bat/     → bat.exe   [미설치]
    │   ├── delta/   → delta.exe [설치됨]
    │   ├── fzf/     → fzf.exe   [미설치]
    │   ├── sqlite/  → sqlite3.exe [미설치]
    │   ├── oh-my-posh/ → oh-my-posh.exe [설치됨]
    │   └── apps/             ← GUI 앱 (Bruno 등)
    │
    ├── claude/               ← Claude/AI 관련
    │   ├── config/           ← Claude Code CLI 인증 + 전역 CLAUDE.md
    │   └── agent/            ← 에이전트 팀 상태 (CONTEXT.md)
    │
    └── data/                 ← 데이터
        ├── logs/             ← 실행 로그
        ├── temp/             ← 격리된 임시파일
        └── setup-files/      ← 설치 아카이브 & 다운로드 링크
```

> **도구 인식 규칙:** `_sys\tools\<도구명>\` 폴더가 존재하면 start.bat이 자동으로 PATH에 추가합니다.  
> **다중 환경:** `Open in Sandbox: 부모폴더\현재폴더 (물리: -> 가상:)` 형식으로 표시되어, 같은 PC에 여러 개 병렬 운용 가능.

---

## 최초 설정

### 방법 A — install.bat + register.bat (권장, 파일이 없는 경우)

**1단계: 런타임 설치**

루트의 **`install.bat`** 을 더블클릭하면 `_sys\setup.ps1`을 자동으로 실행하여 전부 처리됩니다.
(또는 `_sys\setup.ps1`을 우클릭 → **PowerShell로 실행**)

```
✓ Python 다운로드 + 설치
✓ Node.js 다운로드 + 설치
✓ FFmpeg 다운로드 + 설치
✓ Git 다운로드 + 설치
✓ VS Code 다운로드 + 설치 + 포터블 모드 활성화
✓ Python venv 생성
```

선택 옵션:
```powershell
# VS Code 다운로드 생략 (이미 있거나, 나중에 설치)
.\setup.ps1 -SkipVSCode

# Claude Code CLI 설치 생략
.\setup.ps1 -SkipClaude

# 이미 설치된 항목도 강제 재설치 (복구용)
.\setup.ps1 -Force
```

**2단계: PC 등록**

루트의 **`register.bat`** 을 더블클릭합니다.

```
✓ 고정 가상 드라이브 할당 (SUBST, 폴더명 첫 글자 우선)
✓ 우클릭 메뉴 "Open in Sandbox: 폴더 (원본경로 -> P:)" 등록
✓ local.config.bat 에 모든 등록 상태(SUBST, 레지스트리 키) 저장
```

이후 **재부팅 후에도 start.bat이 SUBST를 자동으로 복원**하므로 추가 조작 없이 즉시 사용 가능합니다.

### 방법 B — register.bat 만 (런타임이 이미 있는 경우)

`_sys\env\` 하위에 런타임이 이미 배치되어 있다면 `register.bat` 더블클릭만으로 충분합니다.

### 수동 컴포넌트 배치

각 컴포넌트를 직접 다운로드해서 `_sys\env\` 하위에 배치합니다.

#### VS Code 포터블 모드 수동 활성화

[code.visualstudio.com](https://code.visualstudio.com/download) → **`.zip`** 다운로드 후 `_sys\env\vscode\` 에 압축 해제.  
그 다음 `data` 폴더를 **직접 생성**합니다.

```
_sys\env\vscode\
└── data\     ← 이 폴더가 없으면 설정이 호스트 PC에 저장됨
```

#### 우클릭 메뉴 + SUBST 드라이브 등록

루트의 **`register.bat`** 을 더블클릭합니다 (관리자 권한 불필요).

> register.bat은 `local.config.bat`에 SUBST_DRIVE_LETTER를 저장합니다.
> 재부팅 후에도 start.bat이 SUBST를 자동 복원하므로 USB 드라이브 문자가 바뀌어도 자동 복구됩니다.

### 최초 로그인 (Claude Code CLI)

```
1. 폴더 우클릭 → "Open in Sandbox (폴더명)"
2. VS Code 실행됨
3. Ctrl+`  (통합 터미널)
4. claude               ← 브라우저 열림 → Anthropic 계정 로그인
   → 인증 토큰이 _sys\claude\config\ 에 저장됨 (포터블)
```

### 전역 설정 생성 (권장)

```
_sys\docs\CLAUDE_global.md 를 _sys\claude\config\CLAUDE.md 로 복사 후 편집
```

---

## 사용

### 기본 실행

```
프로젝트 폴더 우클릭
    → "Open in Sandbox (환경명)"
    → VS Code 실행
    → Ctrl+`  (통합 터미널)
    → 명령어 바로 사용 가능
```

### Claude Code CLI 설치 (최초 1회)

```bash
npm install -g @anthropic-ai/claude-code
# → _sys\env\nodejs\npm-global\ 에 포터블 설치됨
```

### 세션 관리

```bash
ctx-save              # 세션 중 체크포인트 (세션 유지)
ctx-end               # 세션 종료 시 풀 요약
ctx-end --global      # + 전역 CLAUDE.md도 업데이트
```

---

## 도구 설치 가이드

모든 도구는 `_sys\tools\<도구명>\` 에 배치합니다.

### 공통 설치 방법

1. 릴리즈 페이지에서 `*-x86_64-pc-windows-msvc.zip` 또는 `-windows-amd64.zip` 다운로드
2. `_sys\tools\<도구명>\` 폴더에 exe 파일 배치
3. 다음 start.bat 실행 시 자동으로 PATH에 추가됨

---

### Python (Embeddable Package)

**역할:** 스크립트 실행, pip 패키지, 가상환경(venv 자동 생성)

**설치 경로:** `_sys\env\python\`

**수동 설치:**
1. [python.org/downloads](https://www.python.org/downloads/windows/) → **Windows embeddable package (64-bit)** 다운로드
2. `_sys\env\python\` 에 압축 해제
3. `python3xx._pth` 파일에서 `#import site` → `import site` 로 변경 (pip 활성화)

**사용:**
```bash
python --version
pip install requests

# 가상환경은 start.bat 실행 시 자동 생성/활성화 (_sys\env\venv\)
```

---

### Node.js

**설치 경로:** `_sys\env\nodejs\`

**수동 설치:**
1. [nodejs.org](https://nodejs.org/) → **Windows Binary (.zip)** 다운로드
2. `_sys\env\nodejs\` 에 압축 해제

**사용:**
```bash
node --version
npm install express
npm install -g typescript    # _sys\env\nodejs\npm-global\ 에 격리 설치
```

---

### FFmpeg

**설치 경로:** `_sys\env\ffmpeg\`

**수동 설치:**
1. [ffmpeg.org/download.html](https://ffmpeg.org/download.html) → **Windows builds by BtbN** → `ffmpeg-master-latest-win64-gpl.zip`
2. `_sys\env\ffmpeg\` 에 압축 해제 (내부 `bin\ffmpeg.exe` 경로 확인)

**사용:**
```bash
ffmpeg -i input.mp4 -c:v libx264 output.mp4
ffprobe -v quiet -print_format json -show_format input.mp4
```

---

### Git 포터블

**설치 경로:** `_sys\env\git\`

**수동 설치:**
1. [git-scm.com/download/win](https://git-scm.com/download/win) → **64-bit Git for Windows Portable** 다운로드
2. 실행 시 설치 경로 → `_sys\env\git\` 지정

**자동 연동:** `_sys\env\git\cmd\git.exe` 가 있으면 자동으로 PATH 등록.  
`_sys\git-config\.gitconfig` 가 있으면 포터블 전용 설정으로 자동 적용.

**사용:**
```bash
git init
git clone https://github.com/user/repo.git
git add .  &&  git commit -m "메시지"
git push origin main

# 별칭 (gitconfig에 정의됨)
git lg          # 그래프 로그
git st          # 간결한 상태
```

**Git에서 제공되는 추가 도구** (`_sys\env\git\usr\bin\`):
```bash
curl, grep, sed, awk, ssh, tar, gzip, diff, vi, less, make, perl
```

---

### ripgrep — 고속 코드 검색

**설치 경로:** `_sys\tools\ripgrep\rg.exe`  
**Claude Code 내부 사용** → 설치 시 AI 응답 속도 개선

**설치:** [github.com/BurntSushi/ripgrep/releases](https://github.com/BurntSushi/ripgrep/releases)  
→ `ripgrep-*-x86_64-pc-windows-msvc.zip` → `rg.exe`를 `_sys\tools\ripgrep\` 에

**사용:**
```bash
rg "TODO"              # 현재 폴더에서 검색
rg "fetch" -t js       # 특정 확장자만
rg -i "error"          # 대소문자 무시
rg -l "import"         # 파일명만 출력
```

---

### fd — 빠른 파일 탐색

**설치 경로:** `_sys\tools\fd\fd.exe`  
**Claude Code 내부 사용** → 설치 시 AI 파일 탐색 속도 개선

**설치:** [github.com/sharkdp/fd/releases](https://github.com/sharkdp/fd/releases)  
→ `fd-*-x86_64-pc-windows-msvc.zip` → `fd.exe`를 `_sys\tools\fd\` 에

**사용:**
```bash
fd config              # 파일명 검색
fd -e py               # 확장자로 검색
fd -H .env             # 숨김 파일 포함
fd -E node_modules -e js
```

---

### jq — JSON 처리

**설치 경로:** `_sys\tools\jq\jq.exe`

**설치:** [github.com/jqlang/jq/releases](https://github.com/jqlang/jq/releases)  
→ `jq-windows-amd64.exe` → 이름을 `jq.exe`로 변경 후 `_sys\tools\jq\` 에

**사용:**
```bash
curl api.example.com/data | jq .
cat data.json | jq '.users[].name'
cat data.json | jq '.items[] | select(.price > 100)'
```

---

### bat — 더 나은 cat

**설치 경로:** `_sys\tools\bat\bat.exe`

**설치:** [github.com/sharkdp/bat/releases](https://github.com/sharkdp/bat/releases)  
→ `bat-*-x86_64-pc-windows-msvc.zip` → `bat.exe`를 `_sys\tools\bat\` 에

**사용:**
```bash
bat script.py
bat config.json
bat --diff script.py   # Git 변경사항과 함께
```

---

### delta — Git diff 뷰어

**설치 경로:** `_sys\tools\delta\delta.exe`

**설치:** [github.com/dandavison/delta/releases](https://github.com/dandavison/delta/releases)  
→ `delta-*-x86_64-pc-windows-msvc.zip` → `delta.exe`를 `_sys\tools\delta\` 에

**자동 연동:** `_sys\tools\delta\delta.exe` 가 있으면 start.bat이 자동으로 `GIT_PAGER=delta` 설정.

**사용:**
```bash
# 기존 명령어 그대로, delta가 자동 적용됨
git diff
git log -p
git show HEAD
```

---

### fzf — 퍼지 파인더

**설치 경로:** `_sys\tools\fzf\fzf.exe`

**설치:** [github.com/junegunn/fzf/releases](https://github.com/junegunn/fzf/releases)  
→ `fzf-*-windows_amd64.zip` → `fzf.exe`를 `_sys\tools\fzf\` 에

**사용:**
```bash
fzf                        # 파일 대화형 선택
code $(fzf)                # 선택한 파일 열기
rg --files | fzf           # 검색 결과에서 선택
fzf --preview "bat --color=always {}"
```

---

### SQLite

**설치 경로:** `_sys\tools\sqlite\sqlite3.exe`

**설치:** [sqlite.org/download.html](https://sqlite.org/download.html)  
→ `sqlite-tools-win-x64-*.zip` → `sqlite3.exe`를 `_sys\tools\sqlite\` 에

**사용:**
```bash
sqlite3 myapp.db
sqlite3 myapp.db "SELECT * FROM users LIMIT 10;"
```

---

### Oh My Posh — 터미널 프롬프트

**설치 경로:** `_sys\tools\oh-my-posh\oh-my-posh.exe`

**설치:**
1. [ohmyposh.dev](https://ohmyposh.dev/docs/installation/windows) → `posh-windows-amd64.exe`
2. 이름을 `oh-my-posh.exe`로 변경 후 `_sys\tools\oh-my-posh\` 에
3. `_sys\tools\oh-my-posh\themes\` 폴더 생성 후 테마 `.omp.json` 파일 배치

**VS Code 통합 터미널에서 활성화:**

`_sys\env\vscode\data\user-data\User\settings.json` 에 추가:
```json
{
  "terminal.integrated.profiles.windows": {
    "PowerShell (Posh)": {
      "source": "PowerShell",
      "args": ["-NoExit", "-Command",
        "oh-my-posh init pwsh --config '$env:POSH_THEMES_PATH\\jandedobbeleer.omp.json' | Invoke-Expression"
      ]
    }
  },
  "terminal.integrated.defaultProfile.windows": "PowerShell (Posh)"
}
```

---

### Bruno — API 클라이언트

**설치 경로:** `_sys\tools\apps\bruno\`

**설치:**
1. [usebruno.com/downloads](https://www.usebruno.com/downloads) → **Windows Portable** 다운로드
2. `_sys\tools\apps\bruno\` 에 압축 해제

**사용:** `Bruno.exe` 직접 실행 또는 PATH에서 `Bruno`

---

## Claude 연동 종합 가이드

### 아키텍처 한눈에 보기

| 도구 | 설치 위치 | 인증/설정 위치 | 이식성 |
|------|----------|---------------|--------|
| **Claude Code CLI** | `_sys\env\nodejs\npm-global\` | `_sys\claude\config\` | **포터블 ✓** |
| **Claude Desktop** | 호스트 PC (`%LOCALAPPDATA%\Programs\Claude\`) | 호스트 PC | 호스트 종속 |

---

### 시나리오별 사용 가이드

#### A. 최초 설치 (브랜드뉴 PC)

```
1. 포터블 폴더를 PC에 연결 (USB 꽂거나 클라우드 동기화)

2. [권장] install.bat 더블클릭 → 전부 자동 설치
   또는 수동으로 각 도구를 _sys\env\ 에 배치

3. register.bat 더블클릭 → SUBST 드라이브 할당 + 우클릭 메뉴 등록

4. (선택) Claude Desktop 호스트 설치
   https://claude.ai/download → 일반 설치

5. 폴더 우클릭 → "Open in Sandbox (환경명)"
   → VS Code 실행됨

6. VS Code 통합 터미널(Ctrl+`)에서
   npm install -g @anthropic-ai/claude-code

7. 최초 로그인
   claude  →  브라우저 열림  →  Anthropic 계정 로그인
   → 인증 토큰이 _sys\claude\config\ 에 저장됨 (포터블)

8. (권장) 전역 설정 생성
   copy _sys\templates\CLAUDE_global.md _sys\claude\config\CLAUDE.md
```

#### B. 기존 PC 재실행

```
1. 폴더 우클릭 → "Open in Sandbox (환경명)"
2. VS Code + Claude Desktop 자동 실행
   (재부팅 후에도 start.bat이 SUBST 자동 복원)
3. claude 입력 → 즉시 사용 가능 (이미 로그인됨)
```

#### C. USB로 새 PC 이동

```
[USB 꽂기 / 클라우드 동기화 후]
1. register.bat 더블클릭 → 새 PC에 SUBST 드라이브 + 우클릭 메뉴 등록
2. 폴더 우클릭 → "Open in Sandbox (환경명)"
3. claude 입력 → 즉시 사용 (_sys\claude\config\ 인증이 포터블)

[특이사항]
- 드라이브 문자가 바뀌어도 register.bat이 새 문자로 재할당
- 이전 PC에서 제거하려면 unregister.bat 실행 (선택사항)
```

---

### MCP (Model Context Protocol) 설정

#### Claude Code CLI MCP — **포터블 ✓**

설정 위치: `_sys\claude\config\` (CLAUDE_CONFIG_DIR 환경변수)  
→ USB로 이동하면 MCP 설정도 함께 이동.

```bash
claude mcp add my-server -- node /path/to/server.js
claude mcp list
```

#### Claude Desktop MCP — **호스트 종속 ❌**

설정 위치: `%APPDATA%\Claude\claude_desktop_config.json`  
→ 새 PC마다 수동 설정 필요. 백업 보관 권장:
```
_sys\claude\config\desktop_mcp_backup.json  ← 백업 보관
새 PC: %APPDATA%\Claude\ 에 수동 복사
```

---

### 업데이트

```bash
# Claude Code CLI 업데이트
npm update -g @anthropic-ai/claude-code

# Claude Desktop 업데이트
앱 내 자동 업데이트 또는 https://claude.ai/download 재설치
```

---

## 환경 격리 상세

| 변수 | 값 (start.bat 기준) | 목적 |
|------|--------------------|------|
| `TEMP`, `TMP` | `_sys\data\temp` | 임시파일 격리 |
| `NPM_CONFIG_PREFIX` | `_sys\env\nodejs\npm-global` | npm 패키지 격리 |
| `NPM_CONFIG_CACHE` | `_sys\env\nodejs\npm-cache` | npm 캐시 격리 |
| `PIP_CACHE_DIR` | `_sys\env\python\pip-cache` | pip 캐시 격리 |
| `PYTHONUSERBASE` | `_sys\env\python\userbase` | pip 사용자 패키지 격리 |
| `CLAUDE_CONFIG_DIR` | `_sys\claude\config` | Claude Code CLI 인증 격리 |
| `GIT_CONFIG_GLOBAL` | `_sys\git-config\.gitconfig` | Git 설정 격리 |
| `GIT_PAGER` | `delta` | Git diff 뷰어 (delta 설치 시 자동) |
| `BAT_CACHE_PATH` | `_sys\tools\bat\cache` | bat 캐시 격리 |
| `USERPROFILE`, `APPDATA` | **호스트 유지** | Git, SSH, 인증 정상 동작 |

---

## 공간 정리 (cleanup.ps1)

```powershell
# 기본 정리 (임시파일, 캐시, 오래된 로그, _state 백업)
_sys\cleanup.ps1

# 미리보기만 (실제 삭제 안 함)
_sys\cleanup.ps1 -WhatIf

# 전체 일괄 정리 (확인 없이)
_sys\cleanup.ps1 -All

# _state 백업 보존 수 지정 (기본: 최근 3개)
_sys\cleanup.ps1 -KeepWorkspace 5

# 하드 클린 (venv + 설치 아카이브까지 삭제)
_sys\cleanup.ps1 -Hard
```

정리 항목:

| 항목 | 기본 정리 | 재생성 방법 |
|------|----------|-----------|
| temp 임시파일 | ✓ | 자동 |
| 오래된 로그 | ✓ (최근 10개 보존) | 자동 |
| pip cache | ✓ | 자동 |
| npm cache | ✓ | 자동 |
| `__pycache__` | ✓ | 자동 |
| _state 백업 폴더 | 기본 (최근 3개 보존) | 자동 (세션마다 생성) |
| 설치 아카이브 (zip/exe) | 선택 | `setup.ps1 -Force` |
| Python venv | 선택 | `start.bat` 첫 실행 시 |

---

## Context Continuity (Claude Session Memory)

Claude Code CLI는 세션 시작 시 프로젝트 루트의 `CLAUDE.md`를 자동으로 읽습니다.

### 전체 흐름

```
세션 시작  →  claude 가 CLAUDE.md 자동 읽음  →  이전 상태 파악
세션 중    →  ctx-save 로 체크포인트 저장
세션 종료  →  ctx-end 로 풀 요약 + 세션 로그 저장
```

### 파일 구조

```
[project]/
└── CLAUDE.md              ← claude 가 자동으로 읽는 현재 상태 파일

[PortableDev]/_sys/
├── claude/config/
│   └── CLAUDE.md          ← 전역 설정 (모든 프로젝트에 적용)
├── context/
│   ├── ctx-save.bat        ← 세션 중 체크포인트
│   ├── ctx-end.bat         ← 세션 종료 요약
│   ├── CLAUDE_project.md   ← 프로젝트 CLAUDE.md 템플릿
│   └── CLAUDE_global.md    ← 전역 CLAUDE.md 템플릿
└── data/sessions/
    └── 2026-05-29_ProjectName.md  ← 세션 기록 아카이브 (날짜_프로젝트명)
```

### 최초 설정

**1. 세션 로그**: ctx-save / ctx-end 실행 시 `_sys\data\sessions\YYYY-MM-DD_ProjectName.md`에 자동 저장됩니다. 별도 설정 불필요.

**2. 전역 CLAUDE.md 생성**:
```
_sys\docs\CLAUDE_global.md 를 _sys\claude\config\CLAUDE.md 로 복사 후 편집
```

**3. 프로젝트 CLAUDE.md 생성** (프로젝트마다 1회):
```
_sys\docs\CLAUDE_project.md 를 [project]\CLAUDE.md 로 복사 후 편집
```

### 세션 저장

**세션 안에서** (현재 대화 맥락 그대로):
```
> checkpoint - update CLAUDE.md with current state and next steps
```

**별도 터미널에서** (VS Code 분할 터미널 등):
```bash
ctx-save
```

### 세션 종료

```bash
ctx-end              # 현재 프로젝트 풀 요약
ctx-end --global     # + 전역 CLAUDE.md 도 업데이트
```

---

## 동일 PC에서 여러 환경 운용

같은 PC에 폴더명만 다르게 사본을 만들면 각각 독립적으로 동작합니다.

```
D:\PortableDev_Python\   ← Python 작업 전용
D:\PortableDev_Node\     ← Node.js 작업 전용
G:\내드라이브\DevEnv\    ← 범용
```

우클릭 메뉴에 각각 독립된 항목이 생깁니다:

```
Open in Sandbox (PortableDev_Python)
Open in Sandbox (PortableDev_Node)
Open in Sandbox (DevEnv)
```

> **모든 것이 독립적:** env\, tools\, claude\config\, data\ 전부 각자 폴더 안에 있으므로 충돌 없음.

---

## PC 이동 / USB 분리

```
[일반 USB 분리]
1. VS Code 종료
2. USB 안전 제거

[새 PC에서 사용 시작]
1. USB 꽂기 (또는 클라우드 동기화)
2. register.bat 더블클릭 → 새 PC에 SUBST 드라이브 + 우클릭 메뉴 등록
3. 폴더 우클릭 → "Open in Sandbox (환경명)" → 즉시 사용

[이 PC에서 완전 제거]
1. unregister.bat 더블클릭 → 컨텍스트 메뉴 + SUBST 완전 삭제
2. VS Code 종료
3. USB 안전 제거
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `claude` 명령어 못 찾음 | npm-global이 PATH에 없거나 미설치 | `npm install -g @anthropic-ai/claude-code` |
| 매번 로그인 요구됨 | CLAUDE_CONFIG_DIR이 안 잡힘 | start.bat 통해 실행했는지 확인 |
| Claude Desktop 자동 실행 안 됨 | 호스트에 미설치 | https://claude.ai/download 에서 설치 |
| Desktop 자동 실행이 귀찮음 | 기본 동작 | start.bat에서 `set "NO_DESKTOP=1"` |
| 우클릭 메뉴가 안 보임 (Win11) | 축약 메뉴 또는 미등록 | Shift+우클릭; 또는 register.bat 실행 |
| 재부팅 후 우클릭 메뉴 없음 | SUBST 미복원 | register.bat 재실행 (local.config.bat 누락 시) |
| 도구 명령어를 찾을 수 없음 | 폴더 구조 오류 | `_sys\tools\<도구명>\<tool>.exe` 구조 확인 |
| Python pip 오류 | import site 비활성화 | `python3xx._pth`에서 `import site` 주석 제거 |
| Git 커밋 시 작성자 정보 없음 | gitconfig 미설정 | `_sys\git-config\.gitconfig` 에 user 추가 |
| 설치 후 도구가 PATH에 없음 | start.bat 미경유 실행 | 폴더 우클릭 → start.bat 통해 실행 |
| 새 PC에서 MCP 작동 안 함 | Desktop MCP는 호스트 종속 | `%APPDATA%\Claude\` 에 설정 파일 수동 복사 |

---

## 시스템 요구사항

| 항목 | 요구사항 |
|------|---------|
| OS | Windows 10 21H2 이상 |
| PowerShell | 5.1 이상 (기본 내장) |
| 권한 | 일반 사용자 권한으로 모든 기능 동작 (관리자 불필요) |
| 디스크 | 최소 2GB (VS Code + 런타임 포함 약 1.5GB) |
