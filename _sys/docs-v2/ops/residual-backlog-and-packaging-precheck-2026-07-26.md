---
status: living
---

# Residual Backlog Sweep + Engram Packaging Pre-Check (2026-07-26)

User-requested comprehensive close-out after the 2026-07-24 architecture-audit
backlog (47 items, C1-C11/S2/S3) finished shipping: (1) sweep the
repo-tracked SSOT (`_sys/ai/backlog.json`) for anything still open and fix
what's reasonably fixable now, (2) pre-check whether packaging Engram as a
standalone, installable product can proceed.

## 1. Backlog sweep result

`_sys/ai/backlog.json` had exactly 8 non-closed items going into this sweep.

| ID | Was | Now | Notes |
|---|---|---|---|
| D4 | deferred | deferred (unchanged) | Re-affirmed 2026-07-15 (3-way peer consensus): a safe narrow failover engine needs enforced read-only execution or an idempotency key, neither exists. Still correctly not worth building. |
| D7 | superseded | superseded (unchanged) | Purely historical bookkeeping -- the real work landed as `b2b8a14` under a different item ID. |
| P4 | superseded | superseded (unchanged) | Permanently closed 2026-07-20 -- subsumed by CHK-CONST/check_docs_mece/CHK-LEDGER, all of which this session touched further (C4, S2). |
| T82 | deferred | **deferred, re-evaluated** | See §2 below -- this IS the packaging pre-check. |
| T85 | deferred | **done** (`0ef7e7e`) | "Phantom session" / agy interactive-launch cwd bug. Was actually already fixed in v1.5.0 (`0ef7e7e`, predates this session) but backlog.json was never updated to reflect it -- pure staleness, not a real gap. Re-verified live: the fix is intact and was faithfully carried through S3's `console_runner.py` migration (`ee158d5`). |
| T86 | deferred | **done** (`863ad71`) | Terminal-handoff detection re-read an already-`unlink()`'d ephemeral query file, silently failing closed every time (bare `except: pass`), so a real terminal-handoff ask could be wrongly blocked by the pacing/reserve guards. Fixed today exactly per the item's own diagnosed fix direction: the handoff marker is now captured once from `raw_content` before the unlink, not re-read after. New differential test proves a handoff ask is spared while an otherwise-identical non-handoff ask is still correctly blocked under a real over_cap condition. Not independently peer-cross-verified (narrow, already-diagnosed, direct differential test judged sufficient given time budget) -- flagged here in case that's wanted later. |
| T87 | deferred | **deferred (unchanged, re-verified still real)** | `gather_peer()`'s `if not data and not health_data: return info` (snapshot.py) still exits before reaching cx's independent live SQLite/rollout collector, confirmed present at the current line. Left deferred deliberately -- the item's own diagnosis explicitly flags this as shared control flow across every peer, needing careful review of what else depends on the early-return's exact semantics before changing it; not something to fix opportunistically inside a sweep. |
| T88 | deferred | **deferred (unchanged)** | See §3 below -- this is the authoritative answer to "ag.gptoss/ag.opus sometimes no response," re-surfaced this session via a fresh live re-measurement. |

Full suite after T85/T86 closure: **1656 passed / 0 failed / 1 skipped**.

## 2. Engram packaging pre-check (T82)

**Verdict: the activation gate has NOT fired. Packaging should not proceed
as unilateral implementation work.**

`_sys/docs-v2/ops/phase2-arch-general-specific-2026-07-22.md` §14 contains an
extensively pre-designed North Star architecture for packaging Engram as a
standalone product (signed native installer with an embedded private Python
runtime, a full host-distribution lifecycle state machine, a strict
"detect-and-wrap-never-bundle" boundary for vendor AI CLIs, channel tiering
for PyPI/Homebrew/WinGet, etc.) -- genuinely thorough, multi-round
cx.deepthink-audited design work, not a sketch.

But a separate, dedicated 10-round adversarial debate
(`_sys/docs/history/engram-peer-governance/engram-refactor-blueprint-2026-07-20.md`, memory:
`project_engram_refactor_blueprint_2026_07_20`) already asked exactly "should
we build toward this" and converged, then **unanimously reversed itself**
after a mandated round-6 red-team pass found three independently-convergent
objections: no validated second consumer (cx), a speculative
distributed-system tax (ag), and "the refactor answers the wrong category of
pain -- every real operational failure in 30 days was reliability, not
architecture" (fable). The full design was preserved but explicitly shelved
behind a 5-part activation gate, checked here against current reality:

1. **Named accountable owner** -- none named.
2. **Committed delivery intent** -- none recorded.
3. **A concrete unsatisfiable use case** -- none articulated. The entire
   2026-07-24/26 implementation phase (this session's 47-item backlog) was
   internal reliability/correctness hardening of the *existing* portable-dev
   -env architecture -- exactly the category of work the red-team pass said
   was the REAL priority, not evidence of an external packaging need.
4. **Executable conformance fixtures** -- the `PeerAdapter`
   contract/`adapter-conformance/v1` work this needs is still explicitly
   "Phase 3, not yet actioned" per the design doc's own backlog section.
5. **Maintenance/funding commitment** -- none recorded.

**0 of 5 conditions are satisfied.** Separately, the one *concrete* bug the
original debate found as a side effect while modeling a hypothetical
concurrency scenario -- T83, `hub.py`'s peer_id-keyed lease clobbering -- was
correctly filed as its own item independent of the shelved architecture, and
is confirmed fixed and live in the current code (`_lease_open`/
`_lease_renew`/`_lease_close` are uuid4-keyed and pid-checked; the T83
docstrings are still there).

**If packaging is wanted anyway:** the concrete next step is supplying
conditions 1-2 explicitly (who owns this, what's the committed timeline) and
articulating condition 3 -- a real external consumer or use case that
current-form Engram cannot serve -- which would then warrant reopening this
via a fresh R:10 round citing that specific trigger, not starting
implementation directly from this pre-check.

## 3. ag.gptoss/ag.opus "sometimes no response" (T88) -- consolidated answer

This was asked about twice this session. The full history, now in one place:

- **v1.5.0** (`a3741e6`, 2026-07-21) fixed the most common cause: `zombie_profile_map` had no entries for `opus`/`gptoss`, so both fell back to a too-short generic timeout. Widened to 900s. Landed alongside T84's independent fix (`208c26a`) for a real PTY-cleanup deadlock that could make hub.py's own watchdog appear silent.
- **T88's own investigation** (2026-07-22, 4 real tests against live ag.opus/ag.gptoss) found a **third, distinct failure mode** those two fixes don't address: under heavy load (large-file reads + a write task), ag.opus reported a clean `exit 0` success after 279s but the actual reply was only 171 characters -- it announced an intent to delegate to its own internal subagents and never delivered further output. The identically-shaped task sent to ag.gptoss crashed outright (real nonzero exit, triggering an auto-quarantine after crossing the peer's failure-count threshold). Both are silent/uncharacterized failures *inside* Antigravity/agy.exe itself (closed-source, unobservable from hub.py's side) -- not fixable from the hub.py side beyond what's already shipped.
- **This session's fresh re-measurement** (2026-07-26, 6 real dispatches: 3x each to gptoss/opus, one round deliberately heavier than a trivial ping): **6/6 succeeded cleanly**, 15-30s each, correct answers. Consistent with the v1.5.0/T84 timeout fixes holding under light-to-moderate load, and consistent with T88's own finding that trivial/moderate loads were already 100% reliable (2/2) in its own testing -- only *heavy* loads (large multi-file reads + writes) showed the 0/2 reliability T88 documented.

**Net: nothing new to fix.** The pattern is real, already root-caused as far
as it can be from hub.py's vantage point, and the one concrete unshipped
mitigation T88 suggested -- detect a suspiciously short reply on a task that
clearly requested substantial output, and flag/retry it distinctly from a
normal short-but-complete answer -- remains a real, scoped, not-yet-decided
option if the user wants it built.
