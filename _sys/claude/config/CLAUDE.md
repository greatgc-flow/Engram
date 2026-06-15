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

## Multi-Peer Collaboration Protocol (v4.1)

All peers (cc, gc, ag, cx) are **absolutely equal**. Any peer may communicate with user directly.
Protocol config: **`P:\_sys\ai\protocol.json`** (single source of truth — collab_rate, routing, health, consensus)
Protocol docs: `P:\_sys\docs-v2\` (SSOT v1.1 — see 00-MANIFEST.md for load order)
Common peer rules (IPC paths, hub commands, session start): `P:\_sys\ai\common\peer-rules.md`
MUST/MUST-NOT rules index: `P:\_sys\docs-v2\10-invariants.md` (INV-01~18, PRO-01~15)
Legal Code archive: `P:\_sys\docs\history\` (read-only reference)

> `_sys/ai/config.json "ratio"` is DEPRECATED → use `protocol.json["collab_rate"]["current"]`

Claude's Role: **Joint Design → Joint Execution → Joint Review → Report**

### COLLAB_RATE Levels (`P:\_sys\ai\protocol.json` → `collab_rate.current`)

Defines integration depth and intervention points.

| collab_rate | Mode | Intervention Point | Unanimous Consent |
|------------|------|--------------------|-------------------|
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

**R:6+** — On 2nd consecutive error: No solo retry. Send logs to any peer, discuss breakthrough.
**R:7+** — Ambiguous options (≥2): No arbitrary choices. Request trade-off analysis from peers.
**R:8+** — Sub-task completion: Request intermediate check: "Review this, can I proceed?"
**R:9+** — 5 consecutive Grep/Read: Validate context sufficiency and search direction.
**R:10** — Final Audit: Report only after unanimous consensus. Iterate until agreed.

### Peer Call Method (2-Step, timeout 180000)

Use unique filenames: `{peer_id}-{YYYYMMDDHHMMSS}-{RAND4}.txt` (see `protocol.json["active_constraints"]["ipc_query_file_naming"]`)

> **Queries MUST be in English.** Korean costs 2-3x tokens.

Step 1 — Write unique query file (Write tool):
  Path: `P:\_sys\gemini\{peer_id}-{YYYYMMDDHHMMSS}-{RAND4}.txt`
  Content: TASK/CONTEXT/QUESTION format in **English**

Step 2 — Invoke peer (timeout 180000):
```
python "P:\_sys\core\hub.py" ask --to {peer_id} --query-file "{file}" 2>&1
```
Peer IDs: `gc` (Gemini), `ag` (agy), `cx` (Codex)

### Delegation Mode (Full Content Generation)
Ask any peer to "Write the complete new file content".
Apply output directly using Write tool → Verify with `git diff HEAD`.

### Console Output Format (Peer Response + Claude Judgment)

Mandatory format after every peer call:

```
━━ {Peer} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Full Peer Response]

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
