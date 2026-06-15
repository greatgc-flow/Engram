# Skill: lesson-add
> Status: CANONICAL | Version: 1.0.0

## 1. When to Use
- After encountering a recurring error (e.g., path drift, encoding issues).
- After discovering a new best practice or implementation pattern.

## 2. Procedure
1.  Format the discovery using the `[LESSON_LEARNED:]` template.
2.  Propose the lesson for R:10 consensus:
    `python _sys/core/hub.py lessons-propose --rule "..." --severity HIGH --category ...`
3.  Upon consensus, activate the lesson:
    `python _sys/core/hub.py lessons-activate --lesson-id LL-{id}`

## 3. hub.py Commands
- `python _sys/core/hub.py lessons-propose --rule "<RULE>" --severity <LOW|MED|HIGH|CRITICAL> --category <CAT> --context "<CONTEXT>"`
- `python _sys/core/hub.py lessons-activate --lesson-id <LL-ID>`
