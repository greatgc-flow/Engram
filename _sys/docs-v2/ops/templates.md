# Ops — Peer Templates
> Purpose: Standardized schemas for high-fidelity communication.
> All peers MUST use these formats. Deviation = format drift (see anti-patterns.md §4).

---

## 1. [GOAL_FRAME]
> Use: Session start or scope change. Defines the "Success Sandbox."

```markdown
[GOAL_FRAME: {topic-slug}-{YYYYMMDD}-v{n}]
General Goal: {High-level intent}
Specific Goal: {Concrete measurable outcome}
Assumptions: {List critical assumptions}
Non-Goals: {Explicit boundaries - what we are NOT doing}
Success Criteria: {Verification points}
Affected Artifacts: {File paths involved}
```

---

## 2. [CLOSURE_MANIFEST]
> Use: Task completion. Every ledger item must have a terminal sink.

```markdown
[CLOSURE_MANIFEST: {task_id}]
Completed:
- {Action item} (tested via: {test_path/command})
Ledger Sinks:
- ISSUE-{n}: RESOLVED (see: {commit/log_ref})
- RISK-{n}: ACCEPTED (unanimous consensus)
Side Effects: {None | List observed changes}
Residuals: {Open LOWs/DEFERs moved to handoff PENDING_ISSUES}
```

---

## 3. [NODE_DONE] Checklist
> Use: During MECE Requirement Exploration (§3).

```markdown
[NODE_DONE: {node_id}]
Findings: {Summary of discovery}
Evidence: {Cited file, code, or log}
Open Questions: {None | List}
Sign-off: [ ] cc [ ] gc [ ] cx
```

---

## 4. [DEBATE_ROUND]
> Use: Formal consensus rounds (§4).

```markdown
[PEER: {name}] [ROUND: {n}] [PROPOSAL: {proposal_id}]
POSITION: AGREE | DISAGREE | NEED_MORE_INFO
REASONING: {One paragraph technical rationale}
CONCERNS: {Numbered list or NONE}
OPEN_QUESTIONS: {Numbered list or NONE}
```

---

## 5. [LESSON_LEARNED]
> Use: Reflection or error recovery. Auto-parsed by `hub.py lesson-add`.

```markdown
[LESSON_LEARNED: {LL-ID-if-exists | "NEW"}]
Severity: LOW | MED | HIGH | CRITICAL
Category: {shell-dialect | encoding | path-portability | tool-interface | context-cold-start | governance-drift | directive-boundary}
Rule: {Actionable "Do/Don't" statement}
Context: {Triggering error or scenario}
```

---

## 6. [PROPOSAL]
> Use: Async governance proposals (see `_sys/ai/proposals/`).

```markdown
[PROPOSAL: {slug}-v{n}]
Author: {peer_id}
Impact: LOW | MED | HIGH | CRITICAL
Rationale: {Why this change is needed}
Changes:
- {File or component} -> {What changes}
Affected Artifacts: {File paths}
Risks: {Known risks or NONE}
Votes:
- cc: PENDING
- gc: PENDING
- cx: PENDING
```
