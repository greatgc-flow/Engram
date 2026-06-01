# Global Claude Preferences
<!-- Copy this file to: [PortableDev]\_sys\claude\config\CLAUDE.md  -->
<!-- CLAUDE_CONFIG_DIR in start.bat points claude here automatically -->
<!-- Update with ctx-end --global                                    -->

---

## Communication
- Respond in Korean
- Explain the plan before making changes
- Ask before large refactors or file deletions
- Keep answers concise; expand only when asked

## Development Environment
- OS: Windows 11, portable sandbox dev env (USB / cloud drive)
- Editor: VS Code (portable) + Claude Code CLI (portable via npm-global)
- Claude Desktop on host PC

## Code Preferences
- Python: type hints, docstrings on public functions
- Commit messages: English, conventional commits format
- Variable names: English; inline comments: Korean OK
- Prefer explicit over clever

## Workflow Rules
- Create a branch before large changes
- Write tests before implementation when practical
- Run ctx-save at natural pause points during a session
- Run ctx-end when done for the day

## Gemini Delegation Protocol

Claude의 역할: **위임(delegate) → 검증(verify) → 보고(report)**
Gemini가 실작업을 수행하고, Claude는 방향 설정과 결과 점검을 담당한다.

### GEMINI_RATIO 레벨 (P:\_sys\gemini\config.json)

| ratio | Gemini 호출 트리거 |
|-------|------------------|
| 0     | OFF — 자동 호출 없음 |
| 1     | 명시적 Axis 실행 시에만 |
| 2     | 아키텍처·구조 수준 설계 변경 |
| 3     | 멀티파일 동시 수정 |
| 4     | 단일 파일 주요 변경 (리팩토링·버그 수정) |
| 5     | 모든 코드 편집 (Edit·Write 전) |
| 6     | 코드 편집 + Bash 명령 전 |
| 7     | 코드 편집 + Bash + 파일 읽기(분석 목적) 전 |
| 8     | 코드·분석이 포함된 모든 실질적 응답 전 |
| 9     | 짧은 단답 제외 모든 응답 전 |
| 10    | **모든 채팅** — 길고 짧은 모든 메시지에 Gemini 먼저 호출 |

### 호출 방법 (2단계, PowerShell 도구 timeout 180000)

병렬 실행 충돌 방지를 위해 호출마다 고유 파일명을 사용한다.

Step 1 — 고유 쿼리 파일 작성 (Write 도구):
  파일: `P:\_sys\gemini\cq-{YYYYMMDDHHMMSS}-{RAND4}.txt`
  예시: `P:\_sys\gemini\cq-20260601185504-a3f2.txt`
  내용: TASK/CONTEXT/QUESTION 형식으로 작성

Step 2 — Gemini 호출 (PowerShell 도구, timeout 180000):
```
$env:PATH += ";P:\_sys\env\nodejs\npm-global"
cmd /c "P:\_sys\context\gemini-consult.bat P:\_sys\gemini\cq-{위 파일명}" 2>&1
```
(bat이 응답 후 쿼리 파일 자동 삭제)

### 위임 모드 (파일 내용 생성을 Gemini에게)
쿼리에 "파일의 완전한 새 내용을 작성해줘" 포함 → Gemini가 전체 파일 내용을 텍스트로 출력
→ Claude가 Write 도구로 해당 파일에 그대로 적용 → `git diff HEAD`로 확인 후 보고

### Claude의 역할 순서
1. 사용자 의도 파악 → Gemini에 명확한 지시 전달
2. Gemini 응답 대기 (30~120초 정상 범위)
3. Gemini 결과 검증 (git diff, 로직 확인)
4. 미완성/오류 부분만 Claude가 보완

## Context Files
- Project context : [project root]\CLAUDE.md  (auto-read at session start)
- Global context  : [this file]               (applies to all projects)
- Session archive : _sys\data\sessions\YYYY-MM-DD_ProjectName.md  (auto-saved by ctx-save / ctx-end)
