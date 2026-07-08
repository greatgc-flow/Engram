# D6 Activation, Profile Taxonomy, and the Whole-Peer-Exclusion Bug (2026-07-08)

> Follow-up to today's D6 implementation (commit feadb3b). ag+cx independently discussed
> D6 activation and a profile-purpose taxonomy in parallel; cc.fable adjudicated where
> they diverged. The discussion surfaced a real, live routing bug (not theoretical),
> which cc verified empirically before handing to cx to fix.

## D6 activation — decided: enable now

Both peers converged: enabling `shared_quota_reserve` now, with zero measured telemetry
so far, is not "guessing" against DIR-004 — it's the only way to start collecting the
`shared_quota_reserve_clamp`/`premium_starvation_warning` events needed to tune it later.
The downside of enabling is low (worst case: a bulk profile is correctly deprioritized
when shared quota is genuinely low — the intended, safe behavior).

**Final settings** (cc.fable's ruling on the one divergence):
- `"3P"`: `reserve_for: ["ag.opus"]`, `reserve_fraction: 0.25` — **unchanged**. ag argued
  for lowering to 0.20 for uniformity with the C family; cc.fable rejected this as
  aesthetic, not functional — 0.25 was declared with a specific rationale (2026-07-07,
  ag.gptoss starving ag.opus) and the two families have different pool shapes with no
  measured evidence that they should match. Changing a declared value with zero benefit
  evidence is exactly what DIR-004 exists to prevent.
- `"C"`: `reserve_for: ["cc.fable", "cc.deepthink"]`, `reserve_fraction: 0.20` — **added
  cc.deepthink**. Both peers independently found this was an oversight: cc.deepthink is
  also in `arbiter_models`, also cost_tier=high, and shares the exact same account-level
  `C-5H`/`C-7D` quota as cc.fable. Protecting only fable left deepthink starvable by the
  same bulk pressure.

The `_doc` field (previously "ENFORCEMENT PENDING") is updated to reflect that
enforcement shipped in feadb3b and was activated today.

## Profile taxonomy — the actual determinant is `routing_state` × `arbiter_models`, not `cost_tier`

Both peers agreed `cost_tier` correlates loosely with purpose but does not determine it
(cc.deepthink and cc.fable are both `cost_tier=high`; `ag.opus` is also `cost_tier=high`
but `manual_only` + `bulk_excluded` — cost tier alone can't distinguish these). Final
table (cc.fable's synthesis of ag's 4 mechanical categories + cx's 5th, demoted to a
lifecycle annotation since it changes no routing behavior by itself):

| Category | Mechanical condition | `--to auto` bulk | Explicit/manual | Current members |
|---|---|---|---|---|
| blocked | `routing_state=blocked` or peer disabled | no | no (recovery only) | ca.* (peer disabled) |
| premium-arbiter | profile ∈ `arbiter_models` | no (per-profile, post-fix) | yes; DIR-005 arbiter pool | cc.fable, cc.deepthink |
| manual-only | `routing_state=manual_only` OR profile ∈ `bulk_exclude_profiles` | no | yes | ag.opus, ag.gptoss |
| bulk-eligible | eligible ∧ not arbiter ∧ not bulk_excluded ∧ measured headroom | yes | yes | cc.standard/effort, cx.*, ag.standard/effort/deepthink |

**Lifecycle annotation** `candidate-not-ready` (applies within manual-only, not a
separate category): declared future-bulk intent + missing required evidence (e.g.
`runtime_context_window` absent). `ag.gptoss` carries this annotation — legitimate
standing state (ag's framing) whose exit criterion is verified evidence landing
(cx's framing); both compatible. `cost_tier` remains weighting-only within
bulk-eligible.

**ag.opus mechanism** (ag's dissent, resolved): keep `bulk_exclude_profiles` as-is for
ag.opus; do NOT consolidate into `arbiter_models`. `arbiter_models` is dual-purpose — it
is simultaneously the bulk-exclusion trigger AND the DIR-005 arbiter candidate pool
consumed by `select_arbiter`/`final_arbiter`. Adding ag.opus would silently expand a
user-ratified (Tier-0, 2026-07-04) arbiter list as a side effect of taxonomy cleanup —
that requires explicit user ratification, not a config refactor. The two mechanisms
encode genuinely different statements (arbiter_models = "DIR-005 arbiter candidate, and
therefore bulk-excluded"; bulk_exclude_profiles = "keep out of bulk without implying
arbiter role or touching siblings") and are not actually split-brain once the bug below
is fixed.

## The whole-peer-exclusion bug (found during this discussion, confirmed live, fixed)

cx raised a concern while discussing the taxonomy; cc reproduced it empirically before
escalating to cc.fable:

**Bug**: `select_load_balanced_peer`'s arbiter exclusion (`snapshot.py:1736-1745`)
excluded an entire PEER from `--to auto` bulk routing if ANY of its profiles was listed
in `arbiter_models` — not just the matching profile. Live test: a candidate batch of
`[cc.standard, cc.fable, cx.standard]` with `arbiter_models=[cc.fable, cc.deepthink]`
resulted in `cc.standard` being silently dropped entirely. This happens whenever a
normal full snapshot includes cc.fable/cc.deepthink alongside cc.standard/cc.effort —
i.e., essentially always in production. Net effect: cc's cheap/mid bulk profiles were
structurally never eligible for `--to auto`.

**cc.fable's verdict**: a real bug, not intentional, despite the old comment explicitly
documenting the whole-peer behavior — it contradicts its own stated rationale ("premium
models must not do routine bulk work" is a per-profile concern), contradicts the
per-profile `bulk_exclude_profiles` mechanism twelve lines earlier in the same function,
and is redundant where harmless (cc is already excluded via `terminal_hard_exclude`
while it's the terminal) and harmful where it's not (any topology where the terminal
moves, or any future `arbiter_models` addition on a bulk-hosting peer).

**Fix** (cx, TDD): the exclusion is now per-row (per-profile), while a bare peer id in
`arbiter_models` (not currently used by any config entry, but supported defensively)
still correctly triggers whole-peer exclusion. Updated: the code comment,
`routing-config.json`'s `_arbiter_doc`, 5 existing tests (one — literally named
`test_profile_level_arbiter_entry_excludes_whole_peer` — codified the bug as passing
behavior, renamed and rewritten to prove the fix), plus 1 new regression test for the
bare-peer-id preservation case. 658/658 tests green (independently re-verified by cc,
not just cx's own claim — cx's sandbox couldn't run the full suite due to a persistent
tempfile create-but-cannot-delete issue, tracked separately as T5).

## Applied today

- `routing-config.json`: `shared_quota_reserve.enabled=true`, C family now
  `reserve_for=["cc.fable","cc.deepthink"]`, stale `_doc`/`_arbiter_doc`/
  `_bulk_exclude_profiles_doc` strings corrected.
- `snapshot.py`: whole-peer-exclusion bug fixed (per-profile now).
- `test_load_balancer.py`: 5 tests fixed/renamed + 1 new regression test.
- New backlog items T5 (cx's recurring tempfile sandbox issue) and T6 (this bug,
  tracking the fix pending commit).
