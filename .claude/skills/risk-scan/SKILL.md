---
name: risk-scan
description: "Trigger procedure for pre-flight risk assessment. Coordinator calls this skill at Phase 1.5 to spawn risk-scanner agent. Required when task affects > 1 file or touches system scripts or agent/skill definitions."
---

# Risk Scan — Trigger Procedure

## When to Use
- Any task affecting > 1 file
- Any task touching _sys/ scripts, agents/*.md, or skills/*
- Optional for single read-only tasks

## Steps
1. coordinator creates risk-scanner agent task (TaskCreate)
2. risk-scanner reads state.json + collab-log
3. risk-scanner calls Axis-I (_sys\checks\check-risk.bat)
4. risk-scanner writes _archive/risk-scan.json
5. coordinator reads overall_risk field from _archive/risk-scan.json
6. Route per CONVENTION.md §8 Zone C (HIGH → ask user, MED → caution_flag=true, LOW → proceed)

## Output Check
Read _archive/risk-scan.json → overall_risk field only for routing decision.
Full risks[] array is available for user presentation if HIGH.

## Gemini OFF behavior
check-risk.bat handles GEMINI_MODE=OFF automatically.
Output: overall_risk = "UNKNOWN", proceed = true (non-blocking).
Coordinator treats UNKNOWN the same as LOW — proceed normally.
