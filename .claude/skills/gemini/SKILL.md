---
name: gemini
description: "Gemini CLI 통합 관리 — 상태 확인, 사용량 모니터링(토큰 0), 협업 로그 조회, ON/OFF 토글, Axis 실행, ratio 조절. Use for: gemini 상태, gemini usage, gemini on/off, axis 실행, 제미나이 모니터링, 사용량 확인, collab-log 조회, gemini rate, gemini ratio, 비율 변경."
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
| "gemini rate", "gemini ratio", "ratio N", "rate N", "비율 변경" | → RATIO |

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
| B | `_sys\scans\scan-env.bat` | 제한 없음 | 도구 버전 검증 |
| C | `_sys\hooks\ctx-end.bat` | 세션 종료 시 | 세션 요약 |
| D | 수동 Gemini 호출 | 제한 없음 | 문법/정책 검사 |
| D+ | `_sys\hooks\ctx-save.bat` | 제한 없음 | 중간 체크포인트 |
| E | `_sys\scans\scan-audit.bat` | 제한 없음 | 에이전트 감사 |
| F | `_sys\scans\scan-deps.bat` | 제한 없음 | 스크립트 의존성 맵 |
| G | `_sys\tools\git-draft.bat` | 제한 없음 | 커밋 메시지 초안 |
| H | `_sys\scans\scan-health.bat` | 제한 없음 | 컨텍스트 건강 확인 |
| Q | `_sys\cli\msg.bat ask --to gemini` | 제한 없음 | 동기 consult — 응답 전 Gemini 먼저 (ratio 5+) |
| R | `_sys\tools\batch-review.bat` | 수동 실행 | 미커밋 diff 일괄 리뷰 |

**Axis-A 일일 한도 초과 시**: "오늘 Axis-A 3회 이미 사용. 내일 실행 권장."

실행 후 `collab-log-append.bat`가 자동으로 `_archive\collab-log\{date}.md`에 기록.

---

## ACTION: RATIO

GEMINI_RATIO 조회 또는 변경. (`_sys\gemini\config.json` 기준)

**인자 없음** (`/gemini ratio`): 현재 ratio와 레벨 설명 표시
**인자 있음** (`/gemini ratio 7`): ratio를 N(0~10)으로 변경

### 조회 (인자 없음)
1. Read `_sys\gemini\config.json`
2. 현재 ratio 값과 아래 표 기준으로 현재 레벨 설명 출력

### 변경 (인자 = N)
1. PowerShell (timeout 10000):
   ```
   cmd /c "P:\_sys\gemini\gemini-set-ratio.bat {N}"
   ```
2. 변경 결과 보고

### Ratio 레벨 표

| ratio | Gemini 호출 트리거 |
|-------|------------------|
| 0 | OFF — 자동 호출 없음 |
| 1 | 명시적 Axis 실행 시에만 |
| 2 | 아키텍처·구조 수준 설계 변경 |
| 3 | 멀티파일 동시 수정 |
| 4 | 단일 파일 주요 변경 (리팩토링·버그 수정) |
| 5 | 모든 코드 편집 (Edit·Write 전) |
| 6 | 코드 편집 + Bash 명령 전 |
| 7 | 코드 편집 + Bash + 파일 읽기(분석 목적) 전 |
| 8 | 코드·분석이 포함된 모든 실질적 응답 전 |
| 9 | 짧은 단답 제외 모든 응답 전 |
| 10 | **모든 채팅** — 길고 짧은 모든 메시지에 Gemini 먼저 |
