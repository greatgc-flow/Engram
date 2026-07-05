# Claude Code — Project Instructions
> This file is a **pointer only**. All normative content lives in `_sys/docs-v2/` (SSOT).
> As an AI peer, you MUST read the SSOT immediately upon startup to understand your operating rules.

## 1. Startup Requirements
> **NOTE FOR IPC / SUBAGENT TASKS**: If you are responding to an automated IPC ask or continuing a session, **SKIP THIS ENTIRE SECTION**. Do NOT read these documents. Proceed directly to the user query.

1. **CONDITIONAL**: Read `_sys/docs-v2/MOC.md` to locate the rules for your current task ONLY if you are starting a fresh interactive session.
2. **CONDITIONAL**: Read `_sys/docs-v2/10-invariants.md` ONLY if you need to recall the non-negotiable hard rules.
3. **CONDITIONAL**: Read `_sys/docs-v2/specific/cc.md` for your specific peer configuration ONLY if you encounter configuration issues.
4. **CONDITIONAL**: Read `.ai/sessions/room-{uuid}/handoff.md` ONLY if instructed to synchronize with the current session state.

## 2. Directory Mappings
- Your local settings and memory are located in `_sys/claude/config/`.

---

# Session Handoff
> Rolling handoff for the next session. This is state, not normative rules (those stay in `_sys/docs-v2/`).
> Master backlog SSOT: memory `backlog_reorg_2026_07_04.md`. Load-balancing/arbiter SSOT: `_sys/docs/history/ops/token-load-balancing-design.md`.

**Last updated: 2026-07-05**

## 1. Current State
- **COLLAB_RATE = 10** (Sync; unanimous consensus + Final Call required for governed decisions). Voters: `cc, ag, cx` (gc tier-suspended 2026-06-19; ag is the replacement).
- **Working tree clean** on `main` (only untracked `_sys/antigravity/config/conversation_summaries.db`). HEAD = `2856943`.
- **Token load-balancing pipeline: ACTIVE.** `token_load_balancing.enabled=true` drives `hub.py ask --to auto` (headroom + pacing + in-flight dedup + premium/terminal exclusion, seeded weighted-random). Explicit `--to` unchanged. (Activated 2026-07-04, r-9aba / 19f688a.)
- **Final Arbiter: ACTIVE + AUTO-WIRED.** `final_arbiter.enabled=true` and, as of 2026-07-05 (`b52e496`, r-ce51), `auto_wire_on_finalize=true` — arbiter (cc.fable, budget 5/5h, single-shot) now fires automatically on consensus finalize, but only under DIR-005 authority (dissent / high_risk). Unanimous rounds spend nothing.
- **A1 (B6 auto-wire) ACTIVATED** — the last dormant gate from the LB/arbiter pipeline is now live.
- **STALE-voter collapse FIXED** 2026-07-05 (`2856943`, r-34dc): `_healthy_peer(allow_stale)` keeps STALE peers eligible as voters so consensus quorum no longer collapses when a peer's health mirror goes stale.
- **B7 security_contract parity: IMPLEMENTED** (`63bc901`, r-f6b5) — declarative per-peer arg-parity; enforcement-behavior probe deferred (see Next Steps).
- **Governance mutation guard (LL-005) live** — `hub._governed_files` hashes governed manifest before/after every peer ask; caught 3 out-of-band peer doc writes in the field. `_sys/cli` now in the manifest (`13a4073`).
- Subprocess reaping without psutil landed (`fce03a6`) — timeout-orphan guard.

## 2. Decisions Made (append-only, newest first)
- **2026-07-05 — Activate B6 arbiter auto-wire** (`auto_wire_on_finalize=true`). Rationale: pipeline was validated dormant; auto-wiring closes the gap where the arbiter only fired via manual `hub.py arbiter-review`. Budget cap (5/5h) + DIR-005 dissent/high_risk trigger keep cc.fable spend bounded, so auto-firing is safe.
- **2026-07-05 — STALE peers stay eligible as voters** (`allow_stale`). Rationale: a stale health *mirror* (clock/refresh lag) was wrongly removing otherwise-reachable peers from the voter set, collapsing R:10 quorum and forcing fail-to-human. Staleness ≠ unreachable, so STALE now abstains-if-truly-silent rather than being pre-excluded.
- **2026-07-05 — Doc/source MECE consistency sweep** (`807d54e`): corrected doc-vs-shipped drift so docs describe reality, not intent.
- **2026-07-04 — DIR-005 ratified**: cc.fable (premium) overrides cheap-peer consensus ONLY on dissent/high_risk (canonical authority); advisory otherwise; premium excluded from bulk routing. Rationale: capture premium judgment on genuinely contested calls without paying premium tokens on routine unanimous ones.
- **2026-07-04 — Activate token load-balancing + final arbiter** (r-9aba). Rationale: shadow-hook validation showed the LB selection matched intended headroom distribution; safe to drive real `auto` routing.

## 3. Next Steps (prioritized)
1. **B6 broker-drain wiring** — remaining piece of the B6 arbiter/broker path; auto-wire-on-finalize is done, broker-drain integration is not.
2. **Enforcement-behavior probe (B7 follow-up)** — BLOCKED on a machine-readable effective-sandbox field; per-peer subprocess model is not observable today. Revisit once peers expose an effective-sandbox/capability field.
3. **Maintenance / zombie-kill cleanup gap** — stale lock, peer-RED, orphan cleanup reliability; `--timeout-seconds` reliability. (From `deferred_p2_cleanup`.)
4. **Older banked backlog D1–D7** — see `backlog_reorg_2026_07_04.md`.
5. **Governance items G1–G2** — see same master backlog.
6. **Docs restructure execution** — 50 docs → 5 MECE pillars blueprint is ratified but execution pending (`docs-restructure-blueprint-2026-06-26.md`).
7. **cc real-enforcement** — `-p` allowlist doesn't actually confine cc; real enforcement mechanism still open (from `wbatch_2026_07_03`).

> When picking up: re-read `collab_rate` from `_sys/ai/protocol.json` first, then consult memory `backlog_reorg_2026_07_04.md` for the authoritative remaining-work list.
