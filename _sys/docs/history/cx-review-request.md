# Codex Review Request — P:\ Porta-Flow Exhaustive Review
> Created by cc | 2026-06-14 | collab_rate=10 shared session

## Context
This is a joint exhaustive review (끝장 교차검토). cc has already analyzed docs/config.
Codex (cx) is asked to review Python source and test code only.

## Pre-Analysis by cc (already decided)
The following will be DELETED/ARCHIVED regardless of cx review:
- _sys/docs/gc-analysis-phase0.md (DONE planning doc)
- _sys/docs/gc-review-v11.md (DONE review)
- _sys/docs/MASTER_PLAN_v1.md (Status: COMPLETE)
- plans/codex-led-total-convergence-plan.md (Status: COMPLETE)
- _sys/docs/collaboration-improvement-backlog.md (all items Done)
- _sys/docs/TAXONOMY_v10.md → move to _archive/

## Codex Review Scope
Review ONLY these files for bugs and inconsistencies:

### 1. _sys/core/hub.py
Check for:
a) Any remaining references to `_sys/ai/config.json` "ratio" field (deprecated)
b) Dead functions or unused imports
c) `action_ask` for cx: uses `codex exec - --json --ephemeral --ignore-rules --dangerously-bypass-approvals-and-sandbox` with stdin. Is this the right pattern for cx session reuse?
d) `_build_session_cmd` for cx: does it work correctly?
e) Any async/timeout issues

### 2. _sys/tests/unit/test_hub.py and related test_*.py
Check for:
a) Tests still patching `subprocess.run` instead of `subprocess.Popen` (lease-test-fix-plan.md issue — should be fixed per commit "fix 14 broken tests")
b) Any tests referencing config.json "ratio" (should use protocol.json collab_rate.current)
c) Any test importing from deprecated paths
d) Run: python -m pytest _sys/tests/unit/ -x --tb=short -q and report failures

### 3. _sys/core/dispatcher.py, config.py, setup.py
Check for:
a) Hardcoded paths that should come from infra.json or paths.json
b) Any references to old `_state/` directory
c) Import errors or dead code

## Expected Output Format
Return a JSON structure:
```json
{
  "python_bugs": [
    {"file": "path", "line": N, "severity": "HIGH|LOW", "description": "...", "fix": "..."}
  ],
  "test_failures": ["list of failing test names"],
  "deprecated_refs": ["file:line - description"],
  "ok": ["list of files with no issues"]
}
```

HIGH = must fix before commit
LOW = cosmetic/nice-to-have
