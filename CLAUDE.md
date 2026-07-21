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

## Session Handoff (2026-07-21, late)
> Snapshot only — SSOTs above remain authoritative for anything longer-lived than this handoff.
> Supersedes the earlier same-day handoff below this line: that snapshot closed out at commit `540183c` with a clean, fully-pushed tree. The session then continued with 5 more real commits **plus** a working-tree regression discovered just now while auditing current git status (see Current State #1 — this is the headline item, not a footnote). The 2026-07-19 handoff items (orphaned daemon session, `ag` baseline-stall investigation) remain addressed; T84 below is a *new*, more severe data point on the stall investigation, not a reopening of the old item.

### Current State
1. **⚠️ URGENT — uncommitted, live regression in the working tree right now.** `git status` shows 5 modified + 2 untracked scratch files that were never committed:
   - `_sys/antigravity/config/fix_bats.py` (untracked) attempted to harden 4 hook/CLI wrapper scripts — `_sys/cli/msg.bat`, `_sys/hooks/archive-data.bat`, `_sys/hooks/log-write.bat`, `_sys/hooks/session-end.bat` — by adding `setlocal` and calling `python.exe` by absolute path instead of relying on `PATH`. The *intent* was fine, but the script built the file contents as **non-raw** Python triple-quoted strings containing literal Windows paths (e.g. `'...\_sys\env\venv\Scripts...'`). Python silently interprets `\v` as a vertical-tab (0x0b) and `\n` as newline (0x0a) inside those un-raw strings, so all 4 `.bat` files on disk right now contain **byte-level control-character corruption** — e.g. `msg.bat` currently reads `...\_sys\envenv\Scripts;...\_sys\env` then a literal newline, then `odejs`, then another literal newline, then `pm-global...`. Confirmed by direct diff inspection, not just inference.
   - This is the **same bug class** already found and fixed earlier this session in `2a19932` (`self-care.bat`, `check-docs-mece.bat`, `saturation-scan.bat`, `sync-docs.bat`) — but it has now recurred in **4 different files**, meaning it's a systemic authoring-pattern risk (any script that writes `.bat`/path content via non-raw Python strings), not a one-off. `CHK-ENC` still doesn't catch this — it only guards CJK/UTF-8 mojibake, not stray control characters.
   - **None of this is committed.** `git diff` confirms the corruption is sitting in the working tree only. Do not run `git add`/commit these 4 files as-is; if these hooks are invoked (session-end, log-write, archive-data, msg) before this is fixed, they will fail or behave unpredictably.
   - `_sys/antigravity/config/test.py` (untracked) is a separate, harmless, read-only `.bat` quoting-style scanner (no writes) — likely used for recon before `fix_bats.py`, not itself implicated in the corruption.
2. `_sys/checks/self_care.py` has a **real, correct, uncommitted fix** sitting alongside the above: previously, `main()`'s per-step dispatch called `getattr(sc, args.step)()` with no arguments for *every* step including `run`/`record`, silently discarding `--trigger` for those two AND double-recording (once inside the dispatched call via its own default, once again unconditionally afterward). The fix routes `trigger=args.trigger` only into `run`/`record` and skips the redundant second `sc.record()` for those two. This looks good and should be committed independently of the `.bat` regression above.
3. `_sys/tools/{fzf,gh,jq,oh-my-posh,ripgrep,sqlite}_old/` (untracked) are **expected, benign** — the provisioner's atomic-swap rollback backups from the `5c2b0af`/`5ae9df2` tool-version-sync commits, self-cleaning by design per that commit's own message. No action needed.
4. Branch `main`, 5 more commits landed and pushed since the prior handoff's `540183c`: `5ae9df2` (sqlite 3.53.3 sync), `c461313` (provisioner: allow GitHub release-CDN redirect, closing an extras-checksum bypass that had blocked 5 tool updates), `5c2b0af` (ripgrep/fzf/jq/gh/oh-my-posh version sync, completing the drift cx found), `6afb744` (`check_cli_canary --emit-observed` was silently ignoring `--peer`/`--force`), `cc5d72f` (filed T84, see below). All committed/pushed cleanly — only the items in #1/#2 above are uncommitted.
5. `_sys/ai/backlog.json` `updated_at: 2026-07-21T11:15:33Z` (moved since prior handoff via `cc5d72f`). Non-terminal items: `D4` (diag inc-4 failover engine, deferred), `D7` (superseded), `P4` (superseded), `T82` (Engram blueprint activation-gate eval, deferred), **`T84` (new, medium priority, deferred)** — see Decisions Made.
6. `_sys/ai/proposals/20260721-auto--saturation-detected-001.md` (untracked governance proposal, 1021 saturation-scan findings) — carried over from prior handoff, still **PENDING** votes from cc/ag/cx, still not reviewed.
7. `protocol.json.collab_rate.current = 10` (unchanged; R:10 — unanimous consensus required before touching governed paths, which includes `_sys/checks`, `_sys/cli`, `_sys/hooks`-adjacent core scripts). **Fixing item #1 counts as a governed-path change and needs R:10 consensus before committing**, same as the original `2a19932` fix did.
8. Engram's full architecture refactor remains SHELVED behind its 5-part activation gate (unchanged). Canary spend budget remains ratified and live: `budget_cap=4`, `budget_window_hours=12`, `reserve_floor=0.25` (unchanged).

### Decisions Made
- (Carried over, still valid) 2026-07-21 MECE cross-review + 11-round stabilization sweep shipped 18 commits (`99e228a`..`540183c`); "QA the QA" adopted as standing practice; destructive `governance_params.json` cleanup proposal rejected; full detail in `[[project_full_mece_audit_2026_07_21]]`.
- **New this handoff**: filed `T84` — `ag`'s baseline-stall investigation hit a *qualitatively new* failure mode: a dispatched `ag.deepthink` ask hung 20+ minutes with the hub's own zombie-detector (which had reliably fired at 300-458s on ~4 other zombies the same session) **never firing at all**. Had to be force-stopped externally via harness-level `TaskStop`, not any hub mechanism. `ag`'s own health stayed GREEN after the stop, ruling out a simple crash-and-hang theory. This is distinct from (and worse than) the previously-characterized "silence past the kill window" pattern, which *does* get caught. Two prior forensic passes (2026-07-17/18) never specifically tested for the watchdog-itself-not-firing case. Risk noted in the backlog item: a hung ask can block a session indefinitely with zero automatic recovery signal.
- **New this handoff — found, not yet fixed**: the `.bat`-corruption bug class (see Current State #1) is confirmed to recur across *different* files each time it happens, meaning "fix the 4 known-bad files" was treated as sufficient in `2a19932` but the real root cause (non-raw Python strings used to author `.bat` content) was never structurally closed off. Discovered by direct git-diff/byte inspection this handoff, not reported by any peer or check.
- Not yet decided whether to commit the item-#1 fix (properly rewritten with raw strings, verified byte-clean) this session or next — flagged in Next Steps rather than acted on unilaterally, since it touches governed paths under R:10.

### Next Steps
1. **Fix and verify the 4 corrupted `.bat` files before anything else touches them.** Rewrite `fix_bats.py`'s dict values as raw strings (`r'''...'''`) or use `pathlib`/`os.path.join` instead of hand-built path literals, re-run, then byte-inspect the output (e.g. `grep -P '[\x00-\x08\x0b\x0c\x0e-\x1f]'` over the 4 files) to confirm zero control characters before staging. Needs R:10 consensus (ag+cx) before commit since these are governed paths — same process `2a19932` went through.
2. Consider a **structural** guard, not just a re-fix: extend `CHK-ENC` (or add a new check) to reject stray control characters (not just CJK/UTF-8 mojibake) in any `.bat`/`.cmd` file, given this is now a *recurring* bug class across two independent sets of files.
3. Commit the `self_care.py` trigger-passing fix (Current State #2) — looks correct and low-risk, can go independently of #1/#2 above.
4. Decide fate of the two untracked scratch scripts once #1 is resolved: fold `test.py`'s quoting-style scan into a real check if useful, otherwise delete both `fix_bats.py` and `test.py` from `_sys/antigravity/config/` (they were working scratch, not intended to persist).
5. **Vote on `_sys/ai/proposals/20260721-auto--saturation-detected-001.md`** (cc/ag/cx all PENDING) — carried over, still not reviewed.
6. Get a real decision on `governance_params.json`'s ~44 remaining zero-code-reference keys — carried over, still deliberately out of scope.
7. The **global** `_sys/claude/config/CLAUDE.md` still cites a stale invariant range ("INV-01~19, PRO-01~16"); current range is **INV-31/PRO-19**. One-line fix, still not done.
8. `D4` and `T82` remain intentionally deferred — pull fresh from `_sys/ai/backlog.json` rather than assuming carryover.
9. Resume `T84` investigation (hub-watchdog-not-firing, not `ag`'s baseline stall mechanism itself) if another hang occurs — next action per the backlog item is to try to reproduce the specific non-firing condition before another full forensic pass.

### Last updated
2026-07-21 (late session)
