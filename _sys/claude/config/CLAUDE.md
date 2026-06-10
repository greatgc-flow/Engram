# Global Claude Preferences
<!-- Copy this file to: [PortableDev]\_sys\claude\config\CLAUDE.md  -->
<!-- CLAUDE_CONFIG_DIR in start.bat points claude here automatically -->
<!-- Update with ctx-end --global                                    -->

---

## Communication
- Respond in Korean
- Explain the plan before making changes
- Ask before large refactors or file deletions
- Keep answers concise; expand only when asked

## Development Environment
- OS: Windows 11, portable sandbox dev env (USB / cloud drive)
- Editor: VS Code (portable) + Claude Code CLI (portable via npm-global)
- Claude Desktop on host PC

## Code Preferences
- Python: type hints, docstrings on public functions
- Commit messages: English, conventional commits format
- Variable names: English; inline comments: Korean OK
- Prefer explicit over clever

## Workflow Rules
- Create a branch before large changes
- Write tests before implementation when practical
- Run ctx-save at natural pause points during a session
- Run ctx-end when done for the day

## Gemini Collaboration Protocol

Claude's Role: **Joint Design → Joint Execution → Joint Review → Report**
Gemini is a full partner, not just an advisor. Integration depth scales with Ratio.

### GEMINI_RATIO Levels (P:\_sys\ai\config.json)

Defines integration depth and intervention points.

| ratio | Mode | Intervention Point | Unanimous Consent |
|-------|------|--------------------|-------------------|
| 0 | **Inactive** | None | — |
| 1 | **Manual** | Explicit Axis execution only | — |
| 2 | **Architecture** | Once before Arch/Structure decisions | — |
| 3 | **Planning** | Once before planning multi-file tasks | — |
| 4 | **Checkpoint** | Before start + After completion (2x) | — |
| 5 | **Code Partner** | Before every Edit/Write + After completion | — |
| 6 | **Error Partner** | R:5 + Immediately on error/failure | — |
| 7 | **Direction** | R:6 + Trade-off analysis if options ≥ 2 | Major direction shifts |
| 8 | **Milestone** | R:7 + Review after every sub-task | Step completion |
| 9 | **Pairing** | R:8 + Verify direction after 5 explores | Direction shifts |
| 10 | **Sync** | **Full Phase** (Plan/Exec/Review/Report) | **Mandatory Every Step** |

> **R:10 Detail**: Share detailed goals → Consensus → Proceed. No solo decision-making. Cross-verify results before reporting. (Ref: PROTOCOL.md §C-0)
> **Final Call (R:8+)**: Proposer sends plan + "Any additional feedback or missed context?" → Finalized only after "ACK/Proceed" from all peers. (Ref: PROTOCOL.md §P-3-FC)

### R:6~10 Trigger Rules

**R:6+** — On 2nd consecutive error: No solo retry. Send logs to Gemini, discuss breakthrough.
**R:7+** — Ambiguous options (≥2): No arbitrary choices. Request trade-off analysis from Gemini.
**R:8+** — Sub-task completion: Request intermediate check: "Review this, can I proceed?"
**R:9+** — 5 consecutive Grep/Read: Validate context sufficiency and search direction.
**R:10** — Final Audit: Report only after unanimous consensus. Iterate until agreed.

### Call Method (2-Step, PowerShell timeout 180000)

Use unique filenames to prevent parallel execution collisions.

> **Queries MUST be in English.** Korean costs 2-3x tokens.
> **Query file is deleted before API call.** Always create a fresh unique file.

Step 1 — Write unique query file (Write tool):
  Path: `P:\_sys\gemini\cq-{YYYYMMDDHHMMSS}-{RAND4}.txt`
  Content: TASK/CONTEXT/QUESTION format in **English**

Step 2 — Invoke Gemini (PowerShell, timeout 180000):
```
cmd /c "P:\_sys\cli\msg.bat" ask --to gemini --query-file "P:\_sys\gemini\cq-{filename}" 2>&1
```
(bat automatically deletes the query file after response)

### Delegation Mode (Full Content Generation)
Ask Gemini to "Write the complete new file content".
Apply output directly using Write tool → Verify with `git diff HEAD`.

### Console Output Format (Gemini Response + Claude Judgment)

Mandatory format after every Gemini call:

```
━━ Gemini ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Full Gemini Response]

━━ Claude Judgment ━━━━━━━━━━━━━━━━━━━━
Adopt: [Agreed parts]
Refine: [Additions/Corrections]
Counter: [Disagreements, skip if none]
Next: [Action based on result]
```

### Collaboration Cycle (R:8~10)
1. **[Plan]** Jointly design approach based on user intent.
2. **[Exec]** Perform tasks with intermediate reviews at sub-task completion.
3. **[Error]** Stop after 2 solo retries → Joint root cause analysis.
4. **[Review]** Final Audit after task completion → Side-effect check.
5. **[Report]** Final report to user incorporating joint findings.

## Context Files
- Project context : [project root]\CLAUDE.md  (auto-read at session start)
- Global context  : [this file]               (applies to all projects)
- Session archive : _sys\data\sessions\YYYY-MM-DD_ProjectName.md  (auto-saved by ctx-save / ctx-end)
