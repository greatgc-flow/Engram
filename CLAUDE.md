# Claude Code — Project Instructions

> This file is a **pointer only**. All normative content and live state live in _sys/.
> As an AI peer, you MUST read the SSOT immediately upon startup to understand your operating rules.

## 1. Startup Requirements
> **NOTE FOR IPC / SUBAGENT TASKS**: If you are responding to an automated IPC ask or continuing a session, **SKIP THIS ENTIRE SECTION**. Do NOT read these documents. Proceed directly to the user query.

1. **CONDITIONAL**: Read _sys/docs-v2/MOC.md to locate the rules for your current task ONLY if you are starting a fresh interactive session.
2. **CONDITIONAL**: Read _sys/docs-v2/10-invariants.md ONLY if you need to recall the non-negotiable hard rules.
3. **CONDITIONAL**: Read _sys/docs-v2/specific/cc.md for your specific peer configuration ONLY if you encounter configuration issues.
4. **CONDITIONAL**: Read .ai/sessions/room-{uuid}/handoff.md ONLY if instructed to synchronize with the current session state.

## 2. Directory Mappings
- Your local settings and memory are located in _sys/claude/config/.

---

# Current Project State
> This project's live state lives in _sys/docs-v2/ and _sys/ai/backlog.json.
> Do not rely on stale summaries.

- **SSOT Backlog**: _sys/ai/backlog.json
- **Most recent comprehensive audit**: _sys/docs-v2/ops/mega-mece-audit-2026-07-16.md

Always consult the above SSOTs for the authoritative remaining-work list and system state.

---

## Session Handoff (2026-07-18)
> Snapshot only — SSOTs above remain authoritative for anything longer-lived than this handoff.

### Current State
- Branch `main`, up to date with `origin/main`.
- Uncommitted in working tree:
  - `_sys/claude/config/settings.json` — one real change: removed `"model": "claude-fable-5[1m]"` override line (reverts to default model selection). Not yet committed either way.
  - `_sys/ai/knowledge/enforcement/LL-009.json`, `LL-011.json`, `LL-012.json`, `LL-20260703-005.json` — CRLF/LF line-ending touch only, no content diff.
  - Untracked: `_sys/data/sessions/` (new ctx-save/ctx-end session-archive dir) and a stray `Windows PowerShell.lnk` at repo root — neither reviewed/committed yet.
- `_sys/ai/backlog.json` (`updated_at: 2026-07-15`) is stale relative to 5+ commits merged since (through `7477d20`, 2026-07-18) — treat its "done" list as a lower bound, not current.
- Last 5 commits: zombie deep-dive session doc (`7477d20`) → IPC reuse-after-failure warning (`0feb3f3`) → staged-query-file regex fix, broken silently ~4 weeks (`c2f88e4`) → round-2 closure review doc (`9773e02`) → `zombie_timeout_sec` doc correction 7200s→900s (`52fda5d`).

### Decisions Made
- IPC query files are single-use by design; reusing one that already zombied/failed used to fail silently (regex bug, ~4 weeks unnoticed) and now loudly warns instead — `c2f88e4` + `0feb3f3`.
- The mystery paired-zombie incident is resolved for its *origin*: `cx.deepthink` was self-orchestrating (dispatching further asks on its own) rather than a hub defect — confirmed via literal command logs (`7477d20`). Per `[[feedback_multipeer_prompt_scoping]]` memory, dispatched peers must be explicitly told they're one voice among N and must not self-orchestrate further asks.
- `ag`'s own baseline stall/output-batching mechanism is explicitly **not** resolved by the above — two independent forensic passes still haven't nailed the mechanism. Do not report it as fixed.

### Next Steps
1. Decide fate of the uncommitted `settings.json` model-override removal (commit it or restore the line) — currently a dangling local edit with no record of why.
2. Review and clean up `_sys/data/sessions/` (untracked) and the stray `Windows PowerShell.lnk` — confirm neither is accidental/in-progress work before touching.
3. If another zombie/stall incident occurs, resume the `ag` baseline-mechanism investigation — root cause still open after 2 passes.
4. Refresh `_sys/ai/backlog.json` (`updated_at` stuck at 2026-07-15) against the 5 commits merged since, so the SSOT backlog stops undercounting completed work.

### Last updated
2026-07-18
