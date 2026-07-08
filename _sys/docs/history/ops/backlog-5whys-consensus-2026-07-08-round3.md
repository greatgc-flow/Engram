# Holistic 7-Lens Adversarial Review — Round 3 (2026-07-08)

Trigger: user asked for a genuinely adversarial ag/cx cross-review (not rubber-stamping),
final arbitration by cc.fable, repeated until unanimous, applied against 7 lenses:
MECE, feedback-loop closure, 5-whys root-cause, alternative perspective, resource
efficiency, must-do/must-not-do boundary clarity, and a catch-all bucket. Scope: all of
today's work (diag.py reorder, hub.py live-state-leak fix, backlog.json restructuring,
Engram cleanup, settings.json revert, D5).

**Process note**: cc.fable was invoked for final arbitration but hit a rate-limit gate
on 3 consecutive attempts (`cc.fable session resume failed`, then `rate-limited until
unknown time`, then explicit `profile 'fable' is currently unavailable`). Per protocol
(peer unavailable → fallback, log the skip, don't silently proceed above R:3), cc served
as the fallback arbiter for the 6 tensions below, reasoning directly from ag's and cx's
full round-1 findings rather than re-deriving them. This is logged transparently, not
hidden — full raw round-1 replies are at
`_sys/ai/ipc/_scratch/holistic-review-round1-raw-20260708.md`.

## ag round-1 (adversarial, did not converge with cx by default)

- MECE: P2+P5 share the same retention-policy blocker, should merge into one epic.
  "Shadow work" (Engram cleanup, settings.json revert, stray-file cleanup) is entirely
  absent from backlog.json — backlog isn't exhaustive of real work performed.
- Feedback loop: T1's fix has no regression test guarding recurrence. Engram cleanup has
  no `.gitignore`/pre-commit rule preventing the same artifacts from reappearing.
- 5-whys: T1's `_is_phantom` exemption is symptom-level — tests should explicitly inject
  `HUB_AI_ROOT` (dependency injection) instead of relying on ascend-and-detect. diag.py's
  print()-sequenced ordering is symptom-level — no declarative layout schema.
- Alt perspective: security/isolation (tests had live write-access to prod state) and
  performance (D5's `_profile_health_gate_open` reparses ISO datetimes every tick).
- Efficiency: cache a unix timestamp instead of reparsing ISO strings; F1 should use
  deterministic CI aggregation, LLM only on-demand; diag.py should batch output instead
  of many `print()` calls.
- Dissent: T1 marked "fixed" was too generous (no regression test); F1's round-2 design
  (continuous LLM ingestion) violates token-efficiency spirit.

## cx round-1 (adversarial, retracted own earlier T1 plan)

- MECE: T1 correctly split from the disproven canonical-path framing. C/P1/F1/P4 could
  be presented as one "drift+feedback" *view* (not schema merge). D3's residual idea
  should fold into D6 later.
- Feedback loop: PHANTOM_WRITE detector only warns/logs, never remediates — open
  enforcement gap. `.ai/sessions/{test-room-123,room-proj-a,stress-room,testroom,
  ext-room-1}` were STILL sitting on disk as leaked debris (empirically verified).
- 5-whys: packaging cleanup has no root-artifact gate; G-VOTER/D7 "hygiene bucket" has
  no actual prevention rule; archive-schema debate reframed as a *view/filter* problem
  (`--active-only`), not a schema problem.
- Alt perspective: the deepest blind spot is the repo doubling as both source tree AND
  runtime scratchpad, with no hard boundary — nearly every incident today is that same
  collapse (temp roots under `_sys`, live `.ai` mutation, root packaging outputs,
  peer-ask debris).
- Efficiency: one closure-hygiene command (status + diff --check + check_backlog + root
  additions) before declaring anything done; F1 as report-only, explicit-input scanner;
  one focused T1 regression test.
- Catch-all: `test_integration_py.py`'s "modified" status was line-ending churn only;
  D5's `_profile_health_gate_open` should also catch `TypeError`, not just `ValueError`.

## Live proof of ag's own critique

While round-1/round-2 review was in flight, cx/ag (separately) added a new diag.py
`render_frame_footer()` ("FRAME") panel *after* `render_summary()` — silently re-breaking
the "SUMMARY is the final panel" invariant this same session had just fixed and gotten
unanimous agreement on, hours earlier. This is exactly ag's 5-whys point: procedural
print()-sequencing has no structural enforcement, so ordering regressions recur. ag was
asked to adjudicate: verdict was that FRAME is legitimately a meta-footer (render
staleness/TTL age, imminent rate-limit resets) distinct from domain-content panels, so
FRAME-after-SUMMARY is correct — but the stale comment needed fixing, and (ag's
recommendation, applied) the panel order should be a single declarative list, not
scattered prints, precisely because this already recurred once today.

## cc (fallback arbiter) — verdicts on the 6 tensions

1. **T1 fix framing**: neither "brittle" nor "done" alone — shipped BOTH: keep the
   `_is_phantom` scratch-exemption (the actual observed-bug fix) AND add ag's proposed
   explicit `HUB_AI_ROOT` injection in the test fixture as defense-in-depth, plus a
   regression assertion that the real `.ai/state.json` is byte-identical before/after
   each test run. Belt-and-suspenders, ships today.
2. **Leaked `.ai/sessions/*` debris**: cleaned up now (low-risk, reversible). Building
   PHANTOM_WRITE auto-remediation into the detector itself: DEFERRED — the cheap
   alternative (a manual closure-hygiene check before declaring done) captures most of
   the value without a new enforcement subsystem.
3. **Archive schema**: cx's "view/filter, not schema" reframing dissolves the
   disagreement — no `"archived"` array, no schema v2, today's status quo stands.
4. **D5 hardening**: the `TypeError` gap was a real crash-risk correctness bug, not
   polish — fixed today (`except (ValueError, TypeError)`), with a fail-safe-not-fail-open
   test. The ISO-reparse perf concern is real but unmeasured and would touch the
   producer side too — DEFERRED pending actual evidence of hot-path cost.
5. **Backlog SSOT scope**: declined to add backlog entries for one-off housekeeping
   (Engram cleanup, settings.json revert) — backlog.json tracks standing/multi-session
   work, not a session activity log; that would be scope creep. This documentation file
   is the record of today's housekeeping instead.
6. **Root-cause unifying theory**: AGREE with cx's framing — source-tree-vs-scratchpad
   boundary collapse (and procedural-vs-declarative structure, surfaced by the FRAME
   incident) is the one thread connecting nearly every distinct-looking bug today. No
   single new subsystem was built for this today (that would be over-engineering for
   what's actually a handful of concrete, already-fixed instances) — but it's flagged
   here explicitly so a future session doesn't have to rediscover the pattern.

## Shipped today (round 3)

- `_sys/tests/unit/test_integration_py.py`: `test_env` now explicit-injects
  `HUB_AI_ROOT` and asserts the repo's real `.ai/state.json` is unchanged after each
  test (regression guard for the live-state-leak class of bug).
- `_sys/core/snapshot.py`: `_profile_health_gate_open` catches `TypeError` in addition
  to `ValueError` for malformed `reset_at` (fail-safe, not a crash).
- `_sys/cli/diag.py`: `render_dashboard()` refactored to a single declarative
  `content_panels` list instead of scattered `print()` calls, so section order is
  structurally fixed, not just documented in a comment. FRAME confirmed correct as the
  true final meta-footer after SUMMARY.
- `.ai/sessions/{test-room-123,room-proj-a,stress-room,testroom,ext-room-1}` deleted
  (confirmed test debris).
- 647/647 tests green after all changes.

## Deferred (explicit, not silently dropped)

- Unified peer/profile resource-governance model (D5+D3+D6 merge) — no measured pain.
- Retired-peer decommission protocol generalization (P2) — n=1, no second customer yet.
- PHANTOM_WRITE auto-remediation — manual closure-check is cheaper for now.
- F1 backlog-refresh automated feedback loop — keep as `proposed` metadata only.
- D5 hot-path ISO-reparse→cached-timestamp optimization — no measured cost evidence.
- P2/P5 merge into one "Retention Policy & Execution" epic — real but not urgent; noted
  for a future backlog pass, not applied today to avoid scope creep on this round.

## Still outstanding

Everything above is uncommitted in the working tree, pending explicit user go-ahead to
commit (repo policy: never commit without being asked).
