# 포터블 샌드박스 개발환경 (Porta-Flow)

Windows 단일 폴더 기반의 완전 격리형 포터블 개발환경입니다.  
USB나 클라우드 드라이브에 담아 어느 PC에서나 **즉시 동일한 환경**을 구축하고 에이전트와 협업할 수 있습니다.

---

## 📂 프로젝트 구조 (Minimalist Core)

이 프로젝트는 **설계와 스크립트**만 깃으로 관리하며, 무거운 바이너리와 데이터는 `install.bat`에 의해 자동 관리됩니다.

```
[PortableDev Root]
├── install.bat               ← ★ 최초 설치 및 환경 재구축 (ZeroBase 지원)
├── register.bat              ← ★ PC 등록 (SUBST 할당 + 우클릭 메뉴)
├── unregister.bat            ← PC 영구 제거 (컨텍스트 메뉴 + SUBST 삭제)
├── cleanup.bat               ← ★ 단계별 공간 최적화 (Level 1~4)
│
├── CLAUDE.md                 ← Claude Code 협업 지침
├── GEMINI.md                 ← Gemini CLI 협업 지침
├── README.md                 ← 본 문서
├── CONVENTION.md             ← 코딩 및 에이전트 규칙
├── PROTOCOL.md               ← P2P 협업 프로토콜 (합의·분업·세션 연속성)
├── WORKLOG.md                ← 변경 이력 및 현재 미션
│
├── workspace/                ← 기본 프로젝트 작업 폴더
├── .claude/                  ← Claude Code 하네스 (agents/, skills/)
├── .ai/                      ← IPC 상태 (hub.py 전용 — 직접 쓰기 금지)
├── _state/                   ← 에이전트 세션 워크스페이스 (자동 관리)
├── _archive/                 ← 로그, 세션, 워크스페이스 백업
└── _sys/                     ← 시스템 레이어 (로직 및 설정)
    ├── core/                 ← 시스템 핵심 로직 (hub.py, setup.py, manage.py)
    ├── cli/                  ← 사용자 진입 도구 (msg.bat, manage.bat, cleanup.bat)
    ├── checks/               ← Axis A~I 정적 분석 스캔
    ├── hooks/                ← 에이전트 라이프사이클 훅
    ├── tests/                ← 유닛/통합/샌드박스 테스트 스위트
    ├── templates/            ← 복사용 파일 템플릿
    ├── data/                 ← 세션·로그 데이터 (로컬)
    ├── env/                  ← Python·Node.js·VS Code·Git 포터블 바이너리
    ├── tools/                ← 보조 CLI 도구 (ripgrep, jq 등)
    ├── claude/               ← Claude Code CLI 설정 및 에이전트 정의
    ├── gemini/               ← Gemini CLI 설정 (Directory Junction 연동)
    └── git-config/           ← 휴대용 깃 환경 설정
```

---

## 🚀 빠른 시작

1. **최초 설치**: `install.bat` 더블 클릭  
   - 인터넷에서 Portable Python, Node.js, Git, VS Code 등을 자동 다운로드하여 환경을 구축합니다.
2. **PC 등록**: `register.bat` 더블 클릭  
   - 윈도우 탐색기 우클릭 메뉴에 **'Open in Sandbox'**를 등록하고 고정 드라이브(SUBST)를 할당합니다.
3. **환경 실행**: 폴더 우클릭 -> **Open in Sandbox** 선택  
   - 격리된 환경에서 VS Code가 실행되며, 모든 도구가 PATH에 자동 등록됩니다.

---

## 🛡️ 에이전트 협업 및 보안 (P2P Peer)

이 환경은 **Claude Code · Gemini CLI · Claude Agent** 등 모든 노드가 **대등한 Peer 권한**으로 협력하도록 설계되었습니다. 수직적 Tier 구조 없이, N-Way Room 세션에서 만장일치 합의 후 분업합니다.

*   **N-Way Room 세션**: `.ai/` 하위 공통 `handoff.md`를 통해 모든 노드가 동일한 컨텍스트를 공유합니다.
*   **만장일치 합의**: 중요한 결정은 `msg.bat consensus`를 통한 전원 합의 과정을 거칩니다. (`PROTOCOL.md §P-3`)
*   **완전 격리**: 모든 캐시와 설정이 폴더 내부에 저장되어 호스트 PC를 오염시키지 않습니다.

---

## 🛠️ 관리 원칙 (Portability)

1. **ZeroBase 아키텍처**: 필수 스크립트만 있다면 `install.bat` 실행만으로 어디서든 100% 동일한 환경 복구가 가능합니다.
2. **깃 관리 최소화**: 바이너리(`env/`, `tools/`), 로그(`_archive/`), 상태(`.ai/`)는 깃 추적에서 제외하여 저장소 무게를 가볍게 유지합니다.
3. **상대 경로 기반**: 모든 경로는 실행 시점에 동적으로 계산되어 드라이브 문자가 바뀌어도 아무런 지장이 없습니다.

---

## 🧪 테스트 및 검증

시스템의 안정성은 다음 3단계 테스트를 통해 보장됩니다.

*   **Unit Tests**: `hub.py`의 IPC 및 합의 로직 검증.
*   **Integration Tests**: 실제 도구(msg.bat, git 등) 간의 연동 검증.
*   **WSB Tests**: Windows Sandbox에서 수행하는 파괴적 라이프사이클(ZeroBase 설치) 검증.

실행: `_sys\tests\run-tests.bat --all`
