---
name: context-health
description: "Check Claude context window health. Runs Axis-H (context-health.bat) to measure JSONL size vs GREEN/YELLOW/RED thresholds. Reports status and recommends /compact or new session. Use when: context feels slow, before a heavy multi-file task, or after a long session."
---

# Context Health Skill

## When to Use
- "check context health" / "how full is my context" / "should I /compact"
- Before starting any task touching > 5 files
- After a long session (> 2 hours or any heavy multi-phase task)
- When Claude responses feel slow or repetitive

## Steps

1. Run Axis-H:
   Bash: `_sys\context\context-health.bat`

2. Read _sys/gemini/status.json:
   - context_health.status (GREEN/YELLOW/RED)
   - context_health.jsonl_mb
   - ai_health fields if present (claude_status + gemini_status)

3. Report to user:

   **GREEN** (< 0.6 MB):
   "Context healthy ({X} MB). Continue working."

   **YELLOW** (0.6–1.2 MB):
   "Context at YELLOW ({X} MB). Consider /compact before the next heavy task.
   Heavy task = touching > 5 files, running Axis-A, or rewriting ≥ 3 agent MDs."

   **RED** (> 1.2 MB):
   "Context at RED ({X} MB). Strongly recommend:
   Option 1: /compact — compresses context, preserves recent work
   Option 2: New session — reads _archive/session-handoff.json to resume
   Run context-health.bat --force first to generate the handoff file."

4. If --force or status is RED:
   Bash: `_sys\context\context-health.bat --force`
   Session handoff written to _archive/session-handoff.json. Report path to user.

## AI Health Dashboard (if ai_health field exists)
Also report: "Gemini status: {ai_health.gemini_status}"
If gemini_status = ERROR: "Gemini has 3+ consecutive failures. Run gemini recovery test."
If gemini_status = OFF: "Gemini is OFF ({reason}). Axis calls will return UNKNOWN results."
