---
name: portable-env
description: "Orchestrates the Portable Dev Environment agent team. Use for: _sys/ script fixes, tool integration, portability audits, folder structure cleanup, documentation sync, scenario loop review, ROI proposals. Also use for: re-run, update, supplement, fix previous results, harness check, agent team re-run, structure cleanup, scenario audit."
---

# Portable Dev Environment — Orchestrator Skill

## Team Structure

### Tier 1 (Orchestrator — this skill)
coordinator: request decomposition, task delegation, state management, Human Approval Gate

### Tier 2 Agents (Specialists)
| Agent | Role |
|-------|------|
| script-engineer | bat/ps1 scripts in _sys/ |
| tool-integrator | CLI tools in tools/ |
| organizer | delegates to folder-tidier + docs-writer |
| folder-tidier | physical folder structure |
| docs-writer | README/CLAUDE.md/CONVENTION.md sync |
| portability-auditor | isolation and portability verification |
| scenario-auditor | user journey closed-loop verification |
| ~~validator~~ | deprecated — merged into verifier |
| verifier | sole PASS/FAIL judge |
| proposer | ROI analysis and version management |
| risk-scanner | pre-flight risk identification (Phase 1.5) |

### Tier 3 (Gemini CLI — High-Resolution Imaging)
Called via Axis scripts A-I. Separate token pool. Stateless per call.

## Absolute Prohibitions (Enforced for All Team Members)
- No role boundary crossing — MECE roles, delegate only
- Correction loops max 3 — loop_count ≥ 3 → HALT immediately
- No final merge without Human Approval (human_approval: "approved")
- All inter-agent state exchange via .ai/state.json (hub.py managed) only

## state.json Schema (Full)
```json
{
  "task_id": "<uuid or timestamp>",
  "timestamp": "<ISO8601>",
  "phase": "init",
  "loop_count": 0,
  "max_loops": 3,
  "status": "in_progress",
  "caution_flag": false,
  "artifacts": {
    "risk_scan": "_archive/risk-scan.json",
    "session_primer": "_state/session-primer.md",
    "scenario_audit": null,
    "portability_audit": null,
    "verification_result": null,
    "findings_json": null,
    "proposal": null
  },
  "loop_history": [],
  "validation_result": null,
  "human_approval": null,
  "system_state": {
    "last_completed": null,
    "known_issues": [],
    "gemini_mode": "ON"
  }
}
```

State.json safety rule: If state.json exists with status != "done"/"halted", backup to `_archive/workspace_{ts}/state.json.bak` before reinitializing.

## Workflow Pipeline

```
Phase 0:  Context health check (Axis-H → status.json)
           Check collaboration health (§3-8: mode=ON, consecutive_failures < 3, no unresolved ESCALATED)
           YELLOW → ctx-save recommendation
           RED → check-health.bat --force → handoff → /compact required

Phase 1:  Request analysis
           coordinator reads session-primer.md (if exists) + state.json + CONVENTION.md §0,§1,§3-3
           state.json initialized (loop_count=0, caution_flag=false)
           coordinator writes _workspace/session-primer.md (max 10 lines, current task context)

Phase 1.5: Risk scan [Axis-I]
           risk-scanner agent → _sys\checks\check-risk.bat
           reads: collab-log last 20 entries + affected files from state.json
           outputs: _archive/risk-scan.json
           HIGH → coordinator asks user (Zone C, §8)
           MED  → caution_flag = true in state.json, proceed
           LOW / UNKNOWN → proceed normally
           Skip if: single file change AND no structural/scenario impact

Phase 2:  Team setup + TaskCreate
           If scripts involved → Axis-F pre-map (script-deps.bat)
           If agents/*.md planned → note for Axis-E in verifier Phase 3

Phase 3:  Collaboration Loop (MAX 3)
  [Dev]    script-engineer (Axis-F pre → edit → Axis-D post → verifier request)
           tool-integrator
  [Organize] organizer → folder-tidier | docs-writer (organizer NEVER executes directly)
             Fast path: single doc update (no structural change) → coordinator → docs-writer directly
  [Audit+Judge]  verifier (spawns auditors AND issues PASS/FAIL) →
             portability-auditor → _state/03_portability_audit.json
             scenario-auditor    → _state/03_scenario_audit.json
             reads 03_*.json critical[] only (not full prose)
             compliance check via inline rules (not full CONVENTION.md)
             Axis-E if agents/*.md changed
             → PASS or FAIL (verifier only)
  [Propose] proposer → _state/04_proposal.json (ROI + versions + improvements)
  loop_count == 2 → coordinator warns user: "Loop 2/3. One more FAIL triggers HALT."

  Loop Restart Delta Protocol (when FAIL):
    coordinator sends DELTA message to affected agents only:
      {loop: N+1, retry_for: [critical[] from 04_findings.json], delta_changes: [...], agents_needed: [...]}
    Agents read ONLY: delta message + 04_findings.json critical[] + listed files
    NOT: full CONTEXT.md, full CONVENTION.md, full verification_result prose

Phase 4:  Human Approval Gate
           Auto-generate commit draft: Axis-G (_sys\cli\git-draft.bat)
           Present: session-primer.md + changes + risk scan + verification + proposal
           APPROVE → Phase 5 | REJECT → loop | no response → waiting
           Note: Run check-health.bat before presenting (per §3-9 POST-PHASE4 trigger)

Phase 5:  Final cleanup
           coordinator updates state.json system_state (last_completed, known_issues)
           coordinator updates session-primer.md: phase=done
           CONTEXT.md updated ONLY if architecture changed
           ctx-save → archive snapshot (no claude subprocess)
           Axis-D+ mid-summary (if Gemini ON, opt-in)
```

Fast path: Single-file change, no structural/scenario impact → skip Phase 1.5 + Phase 3 audit loop; coordinator → verifier directly.

## Data Flow
```
Phase 1.5: check-risk.bat → _archive/risk-scan.json
Phase 3 Dev: (edit files) → _state/02_*.md
Phase 3 Audit: portability-auditor → 03_portability_audit.json
               scenario-auditor → 03_scenario_audit.json
Phase 3 Judge: verifier reads 03_*.json → writes 04_findings.json (JSON-first)
               verifier writes 04_verification_result.md (human readable)
Phase 3 Propose: proposer → 04_proposal.json
Phase 4: Git draft (Axis-G) + Human Gate
Phase 5: state.json system_state update
```

## Autonomous Execution Policy

When user authorizes unattended run ("execute while I sleep", "proceed autonomously"):

### Items requiring user confirmation (batch at session start):
1. Plan approval before implementation begins
2. Axis-A execution (full corpus scan ≤500k Gemini tokens) — confirm scope
3. File deletions > 2× requested scope — list and confirm
4. Constitutional changes (core sections of CLAUDE.md or CONVENTION.md)
5. Phase 4 Human Approval Gate — present summary, wait for APPROVE/REJECT

### Items that execute autonomously:
- All file creation/editing within approved plan scope
- All Gemini Axis calls (B, C, D, D+, E, F, G, H, I)
- ctx-save at natural pause points
- state.json and session-primer.md updates
- CONVENTION.md section additions
- Agent MD rewrites and English conversions
- Skill file updates and new skill creation
- collab-log and status.json updates

### Batching procedure:
Phase 0: Present ALL confirmation items as numbered list → wait for one approval
Execute phases 1-3 autonomously with Gemini collaboration at each step
Phase 4: Present results → wait for APPROVE/REJECT
Phase 5: Execute autonomously after approval

## Error Handling
- Team member failure: SendMessage status check → 1 restart → if still failing, route to coordinator for human intervention
- loop_count ≥ 3: HALT immediately (verifier executes HALT path), Human intervention required
- Role boundary violation: stop offending agent, re-delegate to correct agent
- Human approval absent: maintain status "waiting_approval", no further action
- ESCALATE_TO_TIER1 received: coordinator processes immediately (see coordinator.md for routing)
- Collaboration failure (REFUSED/schema mismatch): invoke §3-8 Teamwork-Broken Protocol
