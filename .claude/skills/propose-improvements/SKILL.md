---
name: propose-improvements
description: "ROI analysis, efficiency proposals, and component version update evaluation for the Portable Dev Environment. Use for: improvement proposals, ROI review, version update check."
---

# Propose Improvements — ROI Analysis and Efficiency Proposal Procedure

## When to Use
- After verifier PASS (before Human Approval Gate)
- When evaluating whether a feature or change is worth doing
- Periodic component version update check

## ROI Evaluation Criteria

| Grade | Examples | Recommendation |
|-------|---------|----------------|
| HIGH | Security patches, bug fixes, major features | Proceed |
| MID | Performance improvements, UX improvements, doc sync | Proceed (in scope) |
| LOW | Style changes, unused features, premature abstraction | Hold |

## Version Update Check

With Gemini ON: Run `_sys\context\version-check.bat` -> read `_archive/version-check.json`
  -> compare with setup.ps1 $V section -> list items needing update

With Gemini OFF: Manual WebFetch to each tool's GitHub releases page:
  ripgrep: BurntSushi/ripgrep/releases/latest
  fd: sharkdp/fd/releases/latest
  Node.js LTS: nodejs.org/en/download/

Components to check: Python, Node.js, Git, VSCode, ripgrep, fd, jq, bat, delta, fzf, oh-my-posh

## Resource Warning Triggers (report to coordinator, do not act independently)

| Condition | Action |
|----------|--------|
| Change scope > 2x requested scope | "Scope warning: {details}" -> coordinator |
| Same bug 3+ occurrences | "Root cause analysis needed" -> coordinator |
| LOW ROI + HIGH cost | "Hold recommendation" -> coordinator |

Note: Loop monitoring is NOT proposer's responsibility. coordinator handles loop_count.

## Efficiency Proposal Checklist

- Repeated manual tasks -> automation opportunity?
- Duplicate code/config -> consolidation?
- Oversized files loading into context -> compression opportunity?
- Gemini Axis not being used for heavy analysis -> route via Axis?

## Output: _workspace/04_proposal.json + 04_proposal.md

JSON format (coordinator reads actions[] only):
```json
{
  "agent": "proposer",
  "task_id": "string",
  "roi_grade": "HIGH|MID|LOW",
  "recommendation": "proceed|hold|scope_reduce",
  "actions": [{"description": "string", "estimated_saving": "string"}],
  "version_updates": [{"component": "string", "current": "string", "recommended": "string"}],
  "warnings": []
}
```

## Process
1. Read session-primer.md (if exists) + state.json for task context
2. Read verifier's 04_verification_result.md for quality baseline
3. Run version check (Gemini ON: version-check.bat, OFF: manual)
4. Evaluate ROI
5. Write 04_proposal.json + 04_proposal.md
6. SendMessage to coordinator: "Proposal complete. ROI: {grade}. Recommendation: {action}"