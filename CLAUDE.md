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
> Supersedes the earlier same-day handoff below this line: that snapshot captured only the first 4 commits of this session; the session then continued into an 11-round stabilization sweep (see Decisions Made). The 2026-07-19 handoff items (orphaned daemon session, `ag` baseline-stall investigation) were already addressed and remain so.

### Current State
- Branch `main`, working tree clean and **fully pushed** — `origin/main` up to date, no local-only commits remain (the previously-pending `f45b036`..`e1330c6` are long since on `origin`, plus 14 more commits landed and pushed the same session). Only untracked item: `_sys/ai/proposals/` (see below — a real open item, not a build artifact).
- Tests: `pytest _sys/tests/unit -q --collect-only` from `P:\` (must run from portable root, not `_sys/`) collects **1313** tests, all green. `README.md`'s badge/prose is already reconciled to `1313/1313` (`540183c`) — no drift remaining.
- `_sys/ai/backlog.json`: still 119 items, `updated_at: 2026-07-20T13:00:00Z` — unchanged this session (everything shipped today was direct chore/fix commits, not backlog items). Only 2 non-terminal: `D4` (diag inc-4 failover engine, deferred) and `T82` (Engram blueprint activation-gate evaluation, deferred).
- `protocol.json.collab_rate.current = 10` (unchanged; R:10 — unanimous consensus required for governed changes).
- Session total: **18 commits** (`99e228a`..`540183c`) — the original 4-commit MECE cross-review plus an 11-round `ag`-delegation stabilization sweep run afterward at explicit user request. Full suite went 1294→1313 green throughout, zero regressions left in the tree.
- **New open item surfaced mid-session**: `_sys/ai/proposals/20260721-auto--saturation-detected-001.md` — a real auto-generated governance proposal (1021 "saturation-scan" findings), triggered when `self_care.py`'s session_end hook fired during an earlier accidental full `ctx-end` run this same session. Votes still **PENDING from cc/ag/cx**, untracked in git, not reviewed. Distinct from the stabilization sweep's own scope — genuinely open work.
- Engram's full peer-collaboration-first architecture refactor remains **SHELVED** (not rejected) behind a 5-part activation gate; only the small v1 shipped (T83 lease/session-concurrency fix + PathLayout seed + budget-invariant test).
- Canary spend budget remains ratified and live: `budget_cap=4`, `budget_window_hours=12`, `reserve_floor=0.25`.

### Decisions Made
- **2026-07-21 MECE cross-review** (docs/config/source/cli+tests, budgeted against diag's URG quota-risk index) shipped its first 4 commits, all tested (1294/1294 green at that point): `e1330c6` doctor.py + `4035bce` peer_mgr.py — same missing-dict-key-guard bug class as 5 prior commits this window; `76e938f` — CLAUDE.md's COLLAB_RATE table had drifted into a scheme incompatible with `protocol.md §4.1`, fixed by making `protocol.md §4.1` sole SSOT; `f45b036` — removed 2 confirmed-dead `governance_params.json` keys, fixed a `_key_count` label drift. R:10 unanimous consent (ag+cx) obtained before the CLAUDE.md edit, per PRO-12.
- **Extended into an 11-round stabilization sweep** (same day, follow-up user request: burn `ag`/`cx` quota up to URG 0.9 with real — "no new features" — work, cc conserving its own tokens). Ran sequential `ag` delegation rounds (mix of fresh bug-hunting and "QA the QA" — `ag` independently re-auditing cc's own just-applied fixes every ~2-3 rounds) until `ag`'s G-pool reached 🟡0.82x with ~1h to reset. `cx` stayed excluded from bulk work all session (started 🔴1.03x, already over budget), vote-only throughout. 14 more commits landed on top of the initial 4.
- Found and fixed a **severe, real, previously unnoticed bug**: 4 `.bat` wrapper scripts (`self-care.bat`, `check-docs-mece.bat`, `saturation-scan.bat`, `sync-docs.bat`) had byte-level control-character corruption in their python.exe path (`\venv` → ESC(0x1b)+`nv`+VT(0x0b)+`env`), meaning these checks could never run via their `.bat` entry point. `CHK-ENC` didn't catch it — it only guards CJK/UTF-8 mojibake, not stray control characters (`2a19932`).
- Adopted **"QA the QA" as a standing practice** inside multi-round delegation loops: an independent peer re-audit of cc's own just-applied diff (not just fresh bug-hunting) caught 2 real same-session regressions cc itself introduced — a lock-directory race in `ctx_end.py` (round 5) and a `NameError` in `provisioner.py` (round 10) — neither caught by the full test suite since no existing test covered that exact path; both fixed with new regression tests.
- **Rejected without applying** a destructive cleanup `ag` proposed mid-sweep (overwrite `governance_params.json` down to 2 keys, which would have deleted live config `check_docs_mece.py`/`self_care.py` actually read); corrected explicitly in the next round's prompt so it wasn't re-proposed. Lesson: verify by usage-grep before applying any deletion proposal against a *config* file, regardless of how accurate that peer's prior rounds were.
- Cleaned up 3 untracked scratch artifacts `ag` left behind (`_sys/tests/unit/scratch/*`, `_sys/antigravity/config/exceptions_dump.txt`) — safe, no lasting value. Deliberately left `_sys/ai/proposals/20260721-auto--saturation-detected-001.md` alone (see Current State) as genuinely open work, out of this sweep's scope.
- Full detail of the whole session: `[[project_full_mece_audit_2026_07_21]]` memory.
- Engram full-architecture refactor (JSONL/JSON-RPC wire protocol, PeerAdapter/UsageProvider split, effect-based governance tiers) went through a mandated 10-round debate: rounds 1-6 converged unanimously on the full architecture, a round-6 red-team pass produced 3 independently-convergent objections, rounds 7-10 unanimously reversed to shelve-behind-gate. Adopted process rule: "deferral must be symmetric with addition." Full detail: `[[project_engram_refactor_blueprint_2026_07_20]]`.
- H1/H2 canary budget values (`cap=4`, `window=12h`, `floor=0.25`) ratified via 3-way independent review + explicit user sign-off; reusable 6-step pattern recorded in `[[project_h1_h2_canary_budget_ratification_2026_07_20]]`.
- Peer-dispatch safety reconfirmed (recurred again this session): the governed-mutation-guard revert trigger is "a governed file changes while **any** peer ask is in flight," not specifically "the peer itself wrote it." Standing practice: stop touching governed files (`_sys/core`, `_sys/checks`, `_sys/ai`, `_sys/docs-v2`, `_sys/cli`) for the duration of any in-flight peer ask, even text-only ones, and re-verify with `git diff --stat` after every ask completes. Detail: `[[feedback_no_concurrent_peer_file_writes]]`.

### Next Steps
1. **Vote on `_sys/ai/proposals/20260721-auto--saturation-detected-001.md`** (cc/ag/cx all PENDING) — 1021 saturation-scan findings from an accidentally-triggered mid-session hook; review before treating as noise or real signal.
2. Get a real decision on `governance_params.json`'s ~44 remaining zero-code-reference keys (named only in archived `TAXONOMY_v11.md`) — delete, keep, or partial; deliberately not expanded this session to stay in scope/budget.
3. The **global** `_sys/claude/config/CLAUDE.md` still cites a stale invariant range ("MUST/MUST-NOT rules index... INV-01~19, PRO-01~16") — verified current range is **INV-31/PRO-19** (`_sys/docs-v2/10-invariants.md`). One-line fix, still not done — out of scope of the R:10 rounds run this session.
4. `D4` (diag inc-4 failover engine) and `T82` (Engram blueprint activation-gate evaluation) remain intentionally deferred — pull fresh from `_sys/ai/backlog.json` rather than assuming carryover; do not implement T82's blueprint without its 5-part gate actually firing.
5. `ag`'s own baseline stall/output-batching mechanism is still **unresolved** after 2 forensic passes (separate from the governed-mutation-guard trigger above) — resume investigation if another zombie/stall incident occurs.

### Last updated
2026-07-21
