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

> Session handoffs belong in `_sys/data/sessions/YYYY-MM-DD_ProjectName.md` (per
> `ctx-save`/`ctx-end`), never appended here — this file is a pointer only and a
> handoff blob left in it goes stale the moment the next session starts, actively
> misleading whoever reads it next. (A ~230-line stale 2026-07-21 handoff was
> found and removed from this exact spot on 2026-07-22 during a docs MECE audit —
> every item in it was already resolved days earlier in the session that found it.)
