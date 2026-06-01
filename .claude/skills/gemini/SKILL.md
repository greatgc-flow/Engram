---
name: gemini
description: "Gemini CLI 통합 관리 — 상태 확인, 사용량 모니터링(토큰 0), 협업 로그 조회, ON/OFF 토글, Axis 실행. Use for: gemini 상태, gemini usage, gemini on/off, axis 실행, 제미나이 모니터링, 사용량 확인, collab-log 조회."
---

# Gemini 통합 관리 스킬

## 트리거 매핑

| 사용자 요청 | 액션 |
|------------|------|
| "gemini 상태", "gemini status", "is gemini on" | → STATUS |
| "gemini 사용량", "usage", "오늘 몇 번", "axis 몇 번" | → USAGE |
| "협업 로그", "collab log", "오늘 axis 내역" | → COLLAB |
| "gemini 켜기/끄기", "on", "off", "disable/enable gemini" | → TOGGLE |
| "axis A 실행", "run axis B", "axis-H" | → AXIS |

---

## ACTION: STATUS

Gemini 현재 상태 확인.

1. Bash: `_sys\gemini\gemini-status.bat`
2. Read `_sys\gemini\status.json`
3. 보고:
   - **ON**: "Gemini ready. 오늘 Axis {calls_today}회 호출."
   - **OFF**: "Gemini OFF — 이유: {reason}"
     - `not_installed` → Gemini CLI 미설치 (`npm i -g @google/gemini-cli`)
     - `not_authenticated` → 인증 필요 (`gemini auth` 실행)
     - `api_error` / `manual_override` → 수동 또는 API 오류

---

## ACTION: USAGE

토큰 0 — 로컬 파일만 파싱.

1. Bash: `_sys\gemini\gemini-usage.bat`
2. Read `_sys\gemini\usage.json`
3. 대시보드 출력:

```
[Gemini 사용 현황] {date}
직접 CLI  : {sessions_today}세션, {messages_today}메시지
Axis 호출 : {calls_today}회 (연속실패 {consecutive_failures})
  A={by_axis.A}  B={by_axis.B}  C={by_axis.C}  D={by_axis.D}  D+={by_axis.D+}
  E={by_axis.E}  F={by_axis.F}  G={by_axis.G}  H={by_axis.H}
마지막    : {axis_calls.last_axis} @ {last_call_ts}
총 상호작용: {total_interactions_today}
```

---

## ACTION: COLLAB

오늘 협업 로그 조회.

1. 오늘 날짜 구하기: `Get-Date -Format yyyy-MM-dd`
2. Read `_archive\collab-log\{YYYY-MM-DD}.md`
   - 파일 없으면: "오늘({date}) 협업 로그 없음 — Axis 호출 없었음."
3. 섹션 헤더 (`## [HH:MM:SS] Axis-X`) 기준으로 요약 보고

---

## ACTION: TOGGLE

### OFF (`NO_GEMINI=1`)

Gemini를 비활성화하려면:

**현재 세션만**: 터미널에서 `set NO_GEMINI=1` 후 `gemini-status.bat` 재실행.

**영구 비활성화** (`local.config.bat`에 추가):
```bat
set "NO_GEMINI=1"
```
위치: `_sys\local.config.bat` (git 추적 안 함, PC 전용)

### ON (활성화)

`local.config.bat`에서 `NO_GEMINI` 줄 제거 또는:
```bat
set "NO_GEMINI=0"
```
재실행 후 `gemini-status.bat`로 확인.

---

## ACTION: AXIS

Axis 실행 전 **항상** STATUS 확인 (`GEMINI_MODE=ON`인지).

| Axis | 스크립트 | 제한 | 설명 |
|------|---------|------|------|
| A | portability-auditor 에이전트 | **최대 3회/일** | Full-Corpus 이식성 검사 |
| B | `_sys\context\version-check.bat` | 제한 없음 | 도구 버전 검증 |
| C | `_sys\context\ctx-end.bat` | 세션 종료 시 | 세션 요약 |
| D | 수동 Gemini 호출 | 제한 없음 | 문법/정책 검사 |
| D+ | `_sys\context\ctx-save.bat` | 제한 없음 | 중간 체크포인트 |
| E | `_sys\context\agent-audit.bat` | 제한 없음 | 에이전트 감사 |
| F | `_sys\context\script-deps.bat` | 제한 없음 | 스크립트 의존성 맵 |
| G | `_sys\context\git-draft.bat` | 제한 없음 | 커밋 메시지 초안 |
| H | `_sys\context\context-health.bat` | 제한 없음 | 컨텍스트 건강 확인 |

**Axis-A 일일 한도 초과 시**: "오늘 Axis-A 3회 이미 사용. 내일 실행 권장."

실행 후 `collab-log-append.bat`가 자동으로 `_archive\collab-log\{date}.md`에 기록.
