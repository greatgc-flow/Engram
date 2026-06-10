---
name: gemini
description: "Gemini CLI integration manager — status check, usage monitoring (zero token), collab log view, ON/OFF toggle, Axis execution, ratio adjustment. Use for: gemini status, gemini usage, gemini on/off, axis run, gemini monitoring, usage check, collab-log view, gemini rate, gemini ratio, ratio change, 제미나이 상태, 사용량, 협업 로그, 비율."
---

# Gemini Integration Management Skill

## Trigger Mapping

| User Request | Action |
|-------------|--------|
| "gemini status", "is gemini on", "gemini 상태" | → STATUS |
| "gemini usage", "how many today", "axis count", "gemini 사용량" | → USAGE |
| "collab log", "today's axis history", "협업 로그" | → COLLAB |
| "gemini on/off", "enable/disable gemini", "gemini 켜기/끄기" | → TOGGLE |
| "run axis A", "axis-H", "axis 실행" | → AXIS |
| "gemini rate", "gemini ratio", "ratio N", "rate N", "비율 변경" | → RATIO |

---

## ACTION: STATUS

Check current Gemini status.

1. PowerShell: `cmd /c "P:\_sys\gemini\gemini-status.bat"`
2. Read `_sys\gemini\status.json`
3. Report:
   - **ON**: "Gemini ready. Axis calls today: {calls_today}."
   - **OFF**: "Gemini OFF — reason: {reason}"
     - `not_installed` → Gemini CLI not installed (`npm i -g @google/gemini-cli`)
     - `not_authenticated` → Auth required (`gemini auth`)
     - `api_error` / `manual_override` → Manual or API error

---

## ACTION: USAGE

Zero token — local file parsing only.

1. PowerShell: `cmd /c "P:\_sys\gemini\gemini-usage.bat"`
2. Read `_sys\gemini\usage.json`
3. Dashboard output:

```
[Gemini Usage] {date}
Direct CLI : {sessions_today} sessions, {messages_today} messages
Axis calls : {calls_today} (consecutive failures: {consecutive_failures})
  A={by_axis.A}  B={by_axis.B}  C={by_axis.C}  D={by_axis.D}  D+={by_axis.D+}
  E={by_axis.E}  F={by_axis.F}  G={by_axis.G}  H={by_axis.H}
Last call  : {axis_calls.last_axis} @ {last_call_ts}
Total today: {total_interactions_today}
```

---

## ACTION: COLLAB

View today's collaboration log.

1. Get today's date: `Get-Date -Format yyyy-MM-dd`
2. Read `_archive\collab-log\{YYYY-MM-DD}.md`
   - If file missing: "No collab log for today ({date}) — no Axis calls made."
3. Summarize by section header (`## [HH:MM:SS] Axis-X`)

---

## ACTION: TOGGLE

### OFF (`NO_GEMINI=1`)

**Current session only**: Run `set NO_GEMINI=1` in terminal, then re-run `gemini-status.bat`.

**Permanent** (add to `local.config.bat`):
```bat
set "NO_GEMINI=1"
```
Location: `_sys\local.config.bat` (not git-tracked, PC-specific)

### ON (enable)

Remove `NO_GEMINI` line from `local.config.bat` or:
```bat
set "NO_GEMINI=0"
```
Re-run then verify with `gemini-status.bat`.

---

## ACTION: AXIS

**Always** check STATUS first (`GEMINI_MODE=ON` required).

| Axis | Script | Limit | Description |
|------|--------|-------|-------------|
| A | portability-auditor agent | **Max 3/day** | Full-corpus portability scan |
| B | `_sys\checks\check-versions.bat` | Unlimited | Tool version verification |
| C | `_sys\hooks\ctx-end.bat` | Session end | Session summary |
| D | Manual Gemini call | Unlimited | Syntax/policy check |
| D+ | `_sys\hooks\ctx-save.bat` | Unlimited | Mid-session checkpoint |
| E | `_sys\checks\check-agents.bat` | Unlimited | Agent audit |
| F | `_sys\checks\check-deps.bat` | Unlimited | Script dependency map |
| G | `_sys\cli\git-draft.bat` | Unlimited | Commit message draft |
| H | `_sys\checks\check-health.bat` | Unlimited | Context health check |
| Q | `_sys\cli\msg.bat ask --to gemini` | Unlimited | Sync consult — Gemini first (ratio 5+) |
| R | `_sys\cli\batch-review.bat` | Manual | Uncommitted diff batch review |

**Axis-A daily limit exceeded**: "Axis-A already used 3 times today. Recommend running tomorrow."

After execution, `collab-log.bat` automatically records to `_archive\collab-log\{date}.md`.

---

## ACTION: RATIO

Query or change GEMINI_RATIO. (Based on `_sys\gemini\config.json`)

**No arg** (`/gemini ratio`): Show current ratio and level description.
**With arg** (`/gemini ratio 7`): Change ratio to N (0~10).

### Query (no arg)
1. Read `_sys\gemini\config.json`
2. Output current ratio value and level description based on table below.

### Change (arg = N)
1. PowerShell (timeout 10000):
   ```
   cmd /c "P:\_sys\gemini\gemini-set-ratio.bat {N}"
   ```
2. Report change result.

### Ratio Level Table

| ratio | Gemini Call Trigger |
|-------|---------------------|
| 0 | OFF — no auto calls |
| 1 | Explicit Axis execution only |
| 2 | Architecture/structure-level design changes |
| 3 | Multi-file simultaneous modification |
| 4 | Single file major change (refactor/bugfix) |
| 5 | All code edits (before Edit/Write) |
| 6 | Code edits + before Bash commands |
| 7 | Code edits + Bash + before file reads (analysis) |
| 8 | Before all substantive responses involving code/analysis |
| 9 | Before all responses except short one-liners |
| 10 | **All chat** — Gemini consulted before every message |
