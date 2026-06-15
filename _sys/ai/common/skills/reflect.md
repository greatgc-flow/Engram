# Skill: reflect
> Status: CANONICAL | Version: 1.0.0

## 1. When to Use
- Immediately following any task completion or significant milestone.

## 2. Procedure
1.  Generate a `[CLOSURE_MANIFEST]` as defined in `ops/templates.md`.
    - Map every ledger item (ISSUE, RISK, AMBIGUITY) to a terminal sink.
2.  Scan the task output for `[LESSON_LEARNED:]` opportunities.
3.  Perform an adversarial self-audit against `ops/anti-patterns.md`.
    - Did I exhibit solo execution?
    - Did I skip validation?

## 3. Persistence
- Append the reflection to `.ai/sessions/{room}/reflection.md`.
- Report status via `hub.py update-status --mission "Reflected on task X"`.
