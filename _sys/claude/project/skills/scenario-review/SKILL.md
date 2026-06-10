---
name: scenario-review
description: "Audit all Portable Dev Environment user scenarios for closed-loop forward cycles. Use for: scenario audit, closed-loop review, user journey check, dead end detection."
---

# Scenario Review — Closed-Loop Scenario Audit Procedure

## When to Use
- After structural changes to _sys/ scripts
- After adding new tools or features
- Periodic scenario health check
- When dead end in user journey is suspected

## Closed-Loop Principle
Every scenario must form a complete loop: Entry -> Action -> Exit -> next Entry.
If Exit does not connect to next Entry = Dead End = scenario audit FAIL.

## 6 Core Scenario Loops

[A] Initial Install: USB copy -> Install_Menu.ps1 -> right-click menu -> [B]
[B] Session Start: right-click -> launch.bat -> start.bat -> IDE -> [C]
[C] Dev Work: terminal -> code/AI -> ctx-save (checkpoint) -> [C] or ctx-end -> [D]
[D] Migration: Remove_Menu.ps1 -> registry cleanup -> new PC [A]
[E] Tool Expansion: need tool -> tools/ add -> start.bat PATH -> session restart -> [B]
[F] Error Recovery: failure -> logs -> root cause -> fix -> [B]

## Audit Procedure

1. **Enumerate current scenario list**
   - Compare with 6 core loops above
   - Check for new scenarios added by recent changes

2. **Trace each scenario flow**
   - Entry: where does this loop start?
   - Action: what scripts/tools are involved?
   - Exit: where does this loop end?
   - Next: does Exit connect to a valid next Entry?

3. **Detect dead ends**
   Failure points that have no recovery path:
   - Install_Menu.ps1 fails -> no rollback
   - launch.bat fails -> IDE doesn't open -> no recovery
   - ctx-end fails -> session data lost -> no recovery
   Check each failure point for explicit recovery path.

4. **Edge cases to check**
   - First PC installation (no existing env)
   - Insufficient permissions (non-admin)
   - Korean path in folder name
   - OS update changes registry behavior
   - Full disk during ctx-save

5. **Script vs. documentation match**
   - README.md steps match actual script behavior?
   - CLAUDE.md scenario descriptions match reality?

## Output
Scenario audit report: _workspace/03_scenario_audit.json (for verifier) + 03_scenario_audit.md
Per-scenario status: OK / Warning / Dead End + remediation proposals.