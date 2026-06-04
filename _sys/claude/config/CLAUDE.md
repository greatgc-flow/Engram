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

## Gemini Collaboration Protocol

Claude의 역할: **함께 설계 → 함께 실행 → 함께 검토 → 보고**
Gemini는 단순 조언자가 아닌 실질적 파트너다. Rate가 높을수록 더 많은 단계에서 함께 고민한다.

### GEMINI_RATIO 레벨 (P:\_sys\gemini\config.json)

협업 깊이와 개입 시점으로 정의. 숫자가 높을수록 더 많은 단계에서 Gemini와 함께한다.

| ratio | 협업 모드 | Gemini 개입 시점 | 만장일치 합의 필요 |
|-------|----------|-----------------|-----------------|
| 0 | **비활성** | 없음 | — |
| 1 | **수동 전용** | 명시적 Axis 실행 시에만 | — |
| 2 | **설계 자문** | 아키텍처·구조 결정 전 1회 | — |
| 3 | **계획 자문** | 멀티파일 작업 시작 전 계획 수립 1회 | — |
| 4 | **검문소** | 작업 시작 전 + 완료 후 (2회) | — |
| 5 | **코드 파트너** | 모든 Edit·Write 전 + 완료 후 검토 | — |
| 6 | **오류 파트너** | R:5 + 오류/실패 발생 시 즉시 재협의 | — |
| 7 | **방향 파트너** | R:6 + 구현 옵션 ≥ 2 시 트레이드오프 분석 | 주요 방향 전환 시 |
| 8 | **마일스톤 파트너** | R:7 + 하위 태스크 완료마다 중간 검토 | 단계 완료 합의 시 |
| 9 | **페어 프로그래밍** | R:8 + 탐색 5회(Grep/Read) 후 방향 확인 | 방향 전환 시 |
| 10 | **두뇌 동기화** | **전 단계** (계획·실행·검토·보고) 완전 협업 | **매 단계 필수** |

> **R:10 상세**: 매 단계마다 상세 목표 공유 → 양측 만장일치 합의 후 진행.
> 이견 발생 시 합의될 때까지 반복. 단독 결정 금지. 결과도 교차 검증 후 보고. (→ PROTOCOL.md §C-0)

### R:6~10 추가 트리거 규칙

**R:6+** — 동일 오류 2회 연속 발생 시: 단독 재시도 금지, Gemini에게 에러 로그 전달 후 돌파구 협의  
**R:7+** — 구현 옵션이 2개 이상 도출되어 선택 모호할 때: 임의 결정 금지, Gemini에게 트레이드오프 분석 요청  
**R:8+** — 하위 작업(task) 1개 완료 시마다: "여기까지 검토해줘, 다음 단계로 넘어가도 될까?" 협의  
**R:9+** — 탐색 도구(Grep·Read) 연속 5회 사용 후: "지금까지 찾은 컨텍스트가 충분한지, 다른 곳을 봐야 하는지" 확인  
**R:10** — 최종 응답 직전 Gemini Final Audit. 양측 만장일치 확인 후 보고. 이견 시 합의까지 반복

### 호출 방법 (2단계, PowerShell 도구 timeout 180000)

병렬 실행 충돌 방지를 위해 호출마다 고유 파일명을 사용한다.

> **쿼리 파일은 반드시 영어로 작성.** 한국어는 토큰 비용 2~3배 → 쿼터 낭비.
> **쿼리 파일은 API 호출 직전에 삭제됨.** 호출 실패 시에도 파일은 이미 사라짐 → 항상 새 파일 생성.

Step 1 — 고유 쿼리 파일 작성 (Write 도구):
  파일: `P:\_sys\gemini\cq-{YYYYMMDDHHMMSS}-{RAND4}.txt`
  예시: `P:\_sys\gemini\cq-20260601185504-a3f2.txt`
  내용: TASK/CONTEXT/QUESTION 형식, **영어**로 작성

Step 2 — Gemini 호출 (PowerShell 도구, timeout 180000):
```
cmd /c "P:\_sys\cli\msg.bat" ask --to gemini --query-file "P:\_sys\gemini\cq-{위 파일명}" 2>&1
```
(bat이 응답 후 쿼리 파일 자동 삭제)

### 위임 모드 (파일 내용 생성을 Gemini에게)
쿼리에 "파일의 완전한 새 내용을 작성해줘" 포함 → Gemini가 전체 파일 내용을 텍스트로 출력
→ Claude가 Write 도구로 해당 파일에 그대로 적용 → `git diff HEAD`로 확인 후 보고

### 콘솔 출력 형식 (Gemini 응답 + Claude 판단)

Gemini 호출 후 반드시 다음 형식으로 출력한다:

```
━━ Gemini ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Gemini 응답 전문]

━━ Claude 판단 ━━━━━━━━━━━━━━━━━━━━━━━━
채택: [동의하는 부분]
보완: [추가하거나 수정할 부분]
반론: [동의하지 않는 부분, 없으면 생략]
다음: [이 결과를 바탕으로 할 행동]
```

### Claude의 협업 사이클 (R:8~10 기준)
1. **[계획]** 사용자 의도 파악 → Gemini와 접근 방식 함께 설계
2. **[실행]** 각 하위 작업 수행 → 완료마다 Gemini에게 중간 검토
3. **[오류 시]** 단독 재시도 2회 초과 금지 → Gemini와 원인 분석
4. **[검토]** 전체 완료 후 Gemini Final Audit → 사이드 이펙트 확인
5. **[보고]** Gemini 검토 결과 반영하여 사용자에게 최종 보고

## Context Files
- Project context : [project root]\CLAUDE.md  (auto-read at session start)
- Global context  : [this file]               (applies to all projects)
- Session archive : _sys\data\sessions\YYYY-MM-DD_ProjectName.md  (auto-saved by ctx-save / ctx-end)
