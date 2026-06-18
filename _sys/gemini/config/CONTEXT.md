# Gemini Agent Context
> Last updated: 2026-06-18
> Static topology only. Dynamic state → `.ai/sessions/` blackboard (`hub.py status`).

## Active Room
Room ID: Check `hub.py status` for current active room.
Blackboard: `.ai/sessions/room-{uuid}/handoff.md`

## Key Policy Files (docs-v2 SSOT)
- P2P protocol + consensus: `_sys/docs-v2/general/protocol.md` + `_sys/docs-v2/general/consensus.md`
- COLLAB_RATE runtime SSOT: `_sys/ai/protocol.json` → `collab_rate.current`
- Hard rules: `_sys/docs-v2/10-invariants.md` (INV-01~19, PRO-01~16)
- Full doc index: `_sys/docs-v2/MOC.md`
- Coding conventions: `CONVENTION.md`
- Claude-facing rules: `CLAUDE.md` (project) + `_sys/claude/config/CLAUDE.md` (global)
- gc-specific delta: `_sys/docs-v2/specific/gc.md`

## Collaboration Policy
- Full policy: `_sys/docs-v2/general/protocol.md` (COLLAB_RATE table)
- Adaptive rate: R:0=read-only, R:3=workspace/, R:5=_sys/, R:10=constitutional docs
- IPC compact syntax: ACK/NACK/FC/PROC (see `_sys/docs-v2/general/consensus.md §4`)

## Gemini Axis Map
- A: portability-auditor full-corpus (≤500k tok, max 3/day)
- B: check-versions.bat | C: ctx-end session summary | D: inline syntax check
- D+: ctx-save mid-summary (opt-in) | E: check-agents.bat | F: check-deps.bat
- G: git-draft.bat | H: check-health.bat | I: check-risk.bat (Phase 1.5)
→ Token budgets: `CONVENTION.md §3-4-D`

## Context Health Thresholds (Axis-H)
GREEN <600KB | YELLOW 600KB–1.2MB | RED >1.2MB

## Practical Figures
- Gemini quality limit: ~500k tokens | Quota signal: `429` (not failure XML)
- NumericalClassifierStrategy non-zero on success → use file-exist check, not errorlevel
- fill_depth_multiplier = 3 (gc reads 3× more context-fill sections — see specific/gc.md)
