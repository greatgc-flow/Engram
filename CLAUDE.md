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

## Session Handoff (2026-07-21)
> Snapshot only — SSOTs above remain authoritative for anything longer-lived than this handoff.
> Supersedes the 2026-07-19 handoff below this line; that session's items (orphaned daemon session, `ag` baseline-stall investigation) are addressed — see Decisions Made.

### Current State
- Branch `main`, working tree clean, but **4 commits ahead of `origin/main`, not yet pushed**: `f45b036`, `76e938f`, `4035bce`, `e1330c6` (everything at `99e228a` and earlier is already on `origin/main`).
- Tests: `pytest _sys/tests/unit -q --collect-only` from `P:\` (must run from portable root, not `_sys/`) collects **1294** tests, all green as of the last full run this session. `README.md`'s badge/prose still says `1261/1261` — **stale, needs a reconcile commit** (same pattern as `08b11f9`/`29d25b9`).
- `_sys/ai/backlog.json`: 119 items, `updated_at: 2026-07-20T13:00:00Z`. Only 2 non-terminal: `D4` (diag inc-4 failover engine, deferred) and `T82` (evaluate Engram blueprint activation gate — do NOT implement without the gate itself firing, deferred). The 2026-07-21 MECE-review fixes below were direct chore/fix commits, not backlog items, so they don't appear here.
- `protocol.json.collab_rate.current = 10` (R:10 — unanimous consensus required for governed changes; enforcement is hardcoded in `hub.py`).
- Engram's full peer-collaboration-first architecture refactor is **SHELVED** (not rejected) behind a 5-part activation gate; only a small v1 shipped — T83 lease/session-concurrency fix + PathLayout seed + budget-invariant test (`190fe5f`, closed `8a32872`).
- Canary spend budget is now ratified and live: `budget_cap=4`, `budget_window_hours=12`, `reserve_floor=0.25` (`f1a5c9d`/`93a63c8`) — this unblocks real `check_cli_reality` auto-refresh spend, which previously always reported `skipped_budget_disabled`.

### Decisions Made
- **2026-07-21 MECE cross-review** (docs/config/source/cli+tests, budgeted against diag's URG quota-risk index) shipped 4 commits, all tested (1294/1294 green): `e1330c6` doctor.py + `4035bce` peer_mgr.py — same missing-dict-key-guard bug class as 5 prior commits this window (env_loader/virtualizer/hub_error/version-resolver/check_backlog); `76e938f` — CLAUDE.md's COLLAB_RATE table had drifted into a scheme incompatible with `protocol.md §4.1` (same rate number meant different things in each), fixed by making `protocol.md §4.1` the sole SSOT instead of keeping a second copy; `f45b036` — removed 2 confirmed-fully-dead `governance_params.json` keys, fixed a pre-existing `_key_count` label drift. R:10 unanimous consent (ag+cx both explicitly agreed) obtained before the CLAUDE.md edit, per PRO-12. Full detail: `[[project_full_mece_audit_2026_07_21]]` memory.
- **Deliberately left undone from that review** (flagged, not oversight): ~44 more `governance_params.json` keys have zero *code* references but are named only in an archived historical doc (`TAXONOMY_v11.md`) — mention-in-an-archive was judged not to count as "in use," but the delete list wasn't unilaterally expanded mid-session; needs a real decision next time. Also, this same CLAUDE.md's citation "MUST/MUST-NOT rules index... (INV-01~19, PRO-01~16)" above is stale (current range runs to INV-31/PRO-19) — out of scope of the R:10 round that actually ran, untouched.
- Engram full-architecture refactor (JSONL/JSON-RPC wire protocol, PeerAdapter/UsageProvider split, effect-based governance tiers) went through a mandated 10-round debate: rounds 1-6 converged unanimously on the full architecture, a round-6 red-team pass produced 3 independently-convergent objections (speculative distributed-system tax / no validated second consumer / wrong category of pain — every real 30-day failure was reliability, not architecture), rounds 7-10 unanimously reversed to shelve-behind-gate. Adopted process rule: "deferral must be symmetric with addition" — re-adding scope requires the same explicit consensus that removed it. Full detail: `[[project_engram_refactor_blueprint_2026_07_20]]`.
- H1/H2 canary budget values (`cap=4`, `window=12h`, `floor=0.25`) ratified via 3-way independent review (ag + cx + cc.fable arbitration) + explicit user sign-off; a concrete peer claim (single global `reserve_floor` causes cross-peer starvation) was checked against real code and found wrong before being accepted into the synthesis. Reusable 6-step pattern for future H3-H6 ratifications recorded in `[[project_h1_h2_canary_budget_ratification_2026_07_20]]`.
- Peer-dispatch safety confirmed (recurred 2026-07-21, not a one-off): the governed-mutation-guard revert trigger is "a governed file changes while **any** peer ask is in flight," not specifically "the peer itself wrote it" — a plain vote-only ask to `ag` with zero file-write instruction still triggered a revert of cc's own concurrent doctor.py edit. Standing practice: stop touching governed files (`_sys/core`, `_sys/checks`, `_sys/ai`, `_sys/docs-v2`, `_sys/cli`) for the duration of any in-flight peer ask, even text-only ones, and re-verify with `git diff --stat` after every ask completes. Detail: `[[feedback_no_concurrent_peer_file_writes]]`.
- 2026-07-19's orphaned long-running daemon session was addressed structurally, not just terminated once: `78442e2` "prevent recurrence of orphaned background daemon sessions."
- T70 (diag off-machine snapshot design) dropped by direct user decision — design stays valid for a future reopen, not a technical rejection. D3/P4 backlog items closed as already-shipped-under-a-different-name / subsumed by CHK-LEDGER.

### Next Steps
1. **Push the 4 local commits to `origin/main`** (`f45b036`, `76e938f`, `4035bce`, `e1330c6`) — currently ahead, not pushed; confirm with user before pushing per standing safety rule.
2. Quick doc-drift fix: reconcile `README.md`'s test badge/prose from `1261/1261` to the current `1294/1294` (same pattern as `08b11f9`/`29d25b9`).
3. Get a real decision on `governance_params.json`'s ~44 remaining zero-code-reference keys (named only in archived `TAXONOMY_v11.md`) — delete, keep, or partial.
4. Fix this CLAUDE.md's stale invariant-range citation (`INV-01~19, PRO-01~16` → current range runs to INV-31/PRO-19).
5. `D4` (diag inc-4 failover engine) and `T82` (Engram blueprint activation-gate evaluation) remain intentionally deferred — pull fresh from `_sys/ai/backlog.json` rather than assuming carryover; do not implement T82's blueprint without its 5-part gate actually firing.
6. `ag`'s own baseline stall/output-batching mechanism is still **unresolved** after 2 forensic passes (separate from the now-understood governed-mutation-guard trigger above) — resume investigation if another zombie/stall incident occurs.

### Last updated
2026-07-21
