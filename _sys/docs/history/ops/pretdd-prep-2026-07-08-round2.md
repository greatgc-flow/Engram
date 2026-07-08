# Pre-TDD Prep — Round 2, remaining 10 items (2026-07-08)

> Follow-up to `pretdd-prep-2026-07-08.md` (D5/P2/backlog-SSOT) and the day's four
> `backlog-5whys-consensus-2026-07-08*.md` rounds. Design/spec only — no code changes.
> Peers: ag.effort+ag.deepthink (2 batches, first 7-item attempt timed out at 900s and
> was split), cx.deepthink (233s). cc.fable did final adjudication (159s) with
> independent empirical verification (read actual code/consensus records, not just
> peer claims) — one peer design was corrected as a result (T2, see below).

## T2 — cc.fable excluded from C-5H/C-7D quota families: PRIORITY ELEVATED, READY FOR TDD

**This is the most consequential finding in this batch — it affects fable's own arbiter role.**

Verified end-to-end (cc.fable empirical_probe): `_quota_family_for_profile('cc','fable')`
returns only `'F-'` (`snapshot.py:932`); `_filter_profile_buckets` then drops every `C-`
bucket; `_quota_remaining` takes the min over the surviving buckets only;
`select_arbiter` (`snapshot.py:1836`) treats fable as usable on that inflated headroom.
Since `C-5H` (session, all models) **and** `C-7D` (week, all models) both actually bind
fable too, an exhausted shared window still shows fable as "available", so DIR-005
selects fable as arbiter and it stalls. This plausibly explains today's 4
`ESCALATED(timeout)` consensus rounds seen in an earlier `consensus-sweep` run.

**Spec (corrected — ag's first draft only added `'F-'`+`'C-5H'` and missed `C-7D`):**
return `{'F-', 'C-'}` as the family-prefix set, so all `C-`-prefixed buckets are
evaluated for fable, not just one.

**Status: READY FOR TDD, sequence BEFORE D6** (D6's clamp is meaningless while fable's
headroom math can't see the shared buckets at all).

## D6 — shared-quota reserve for premium profiles (was: "5-Whys deferred set"): READY FOR TDD, blocked on T2 landing first

Genuinely separate from T2 (T2 fixes visibility; D6 actively protects premium profiles
— `cc.fable`, `ag.opus` — from starvation once a shared window gets low). Design: clamp
bulk-candidate (e.g. `cc.effort`) headroom once remaining shared quota drops below a
`reserve_fraction`.

**cc.fable verdict on ag's proposed 20%:** mechanism yes, hardcoded number no — 20% is
an unmeasured guess, which conflicts with DIR-004 (measured-only claims) and the
just-shipped CHK-CONST no-hardcoding guard (`81d3f18`). Ship it as a `reserve_fraction`
knob in `routing-config.json` defaulting to `0.20`, explicitly tagged as a heuristic
default, with telemetry emitted on every reserve-clamp activation and premium-starvation
event so the number can be tuned from real observation instead of guessed once and
forgotten.

**Status: READY FOR TDD, sequence AFTER T2.**

## D4 — diag inc-4 "failover engine": DEFER (ag + cc.fable unanimous)

D5's per-profile health gating plus the existing pre-dispatch headroom failover ranking
(`hub.py:3925`, r-f291 W4) already cover "don't route to a dead profile". A transparent
runtime auto-retry/re-route engine cannot distinguish "request never executed" from
"executed but response lost", so re-dispatching non-idempotent mutating asks risks
double execution. A narrower version (retry only explicitly read-only/idempotent asks,
fail-fast with clear error surfacing otherwise) is noted but not worth building now
absent measured failure-rate evidence (DIR-004).

**Status: DEFERRED, not worth building as originally scoped.**

## C — refresh `.ai/cli-reality-observed.json`: READY FOR TDD

Opt-in check inside `check_cli_reality.py`, auto-runs on interval expiration (24h
default). SHA256 of the real CLI binary as the fingerprint-cache key — skip the
expensive real-invocation probe when the binary hash hasn't changed. Reuse the existing
budget-cap mechanism already in `check_cli_canary.py` rather than inventing a new one.

**Status: READY FOR TDD.**

## D7 — r-9bc7 WS2 proposal: SUPERSEDED, closed

Verified (ag, re-confirmed independently by cc.fable via `.ai/consensus/`): `r-9bc7`
exists only as an abandoned `.tmp` fragment — a duplicate of the WS2 hub-dispatch
fail-fast proposal that was actually finalized as `r-8b3b` and shipped in commit
`b2b8a14` ("W1-W3 — hub silent-exit fix, r-8b3b model-operand validator, G-bridge
lessons + DIR-004"). A third variant, `r-c042`, was rejected. `r-9bc7` was pure stale
tracking debris for already-shipped work.

**Status: marked `superseded` (evidence: `b2b8a14`). Closed, no further action.**

## P1 — phantom config residue: RE-SCOPED, READY FOR TDD

Both ag and cc.fable agree this is a direct instance of round-3's "source-tree vs
scratchpad boundary collapse" root cause (`backlog-5whys-consensus-2026-07-08-round3.md`)
— not an isolated issue. Kept as its own cross-referenced backlog item (not silently
merged away) so it stays traceable. "Reduce config drift" concretely means: a
root-artifact gate (fail if unexpected files appear at repo root outside an allowlist) +
the closure-hygiene check already recommended in round 3 (`git status --short` + `git
diff --check` + `check_backlog.py` before declaring anything done).

**Edge case:** must not falsely flag legitimate user-driven config changes as phantom
residue.

**Status: READY FOR TDD (re-scoped to reference round-3, not a separate design).**

## G2 — PRO-19 documentation: DONE, closed

Verified independently by both ag and cc.fable by reading `_sys/docs-v2/10-invariants.md`
directly: PRO-19 is extensively documented (core rule, ENFORCED status with all three
controls enumerated, GAP-1 2026-06-26, GAP-2 including the 2026-07-07 cx.standard
mojibake incident). Documentation is current through yesterday's incident — the backlog
item was simply never marked closed after the doc work landed (commit `b1a3caf`).

**Status: marked `done` (evidence: `b1a3caf`). Closed, no further action.**

## B7 — enforcement-behavior probe: READY FOR TDD (narrower scope)

Current source only has declared/argv-parity checks (`_check_flag_parity()` in
`hub.py`); no cross-CLI machine-readable "effective sandbox" self-report field exists,
and cc.fable confirms this isn't achievable without upstream CLI support — don't block
on it. Achievable target instead: an opt-in BEHAVIORAL probe under
`_sys/data/temp/sandbox-probe/<id>/{workspace,outside}` — invoke each real CLI in the
workspace, ask it to write a sentinel outside the workspace, classify by the actual
filesystem result (inspect the sentinel file, never trust reply text — model refusal
≠ sandbox denial). Expected `cx`: denied. Expected `cc`/`ag`: may be
`UNENFORCED/NO_SANDBOX` under declared trusted/skip-permissions policy, not
automatically a failure. Results tagged `empirical_probe` vs `declared, unverified`;
cleanup confined to `_sys/data/temp`.

**Status: READY FOR TDD for the narrow behavioral probe; NOT ready for a cross-CLI
self-report field.**

## D2 — INV-26 fail-closed: READY FOR TDD (dry-run helper + soak harness)

INV-26 requires governance rules enforced programmatically by `hub.py`, not peer
discipline. No `WOULD-BLOCK` dry-run mode exists today (existing `preflight` only
classifies shell commands, not hub actions). Spec: extract/wrap `_guard_action()` with
a pure dry-run path returning structured JSON (`{would_block, reason, code,
matched_rule}`, no `sys.exit`/mutation). Add a soak harness over a fixture matrix:
read-only=allow, terminal-mutating=block, collab-rate≥10 mutating w/o finalized
consensus=block, no-code-phase mutating=block, explicit exemptions=allow. Run repeated
randomized passes. cc.fable confirms the acceptance bar is correct: zero false
positives **and** zero false negatives before flipping to actual fail-closed behavior
— no scope creep detected.

**Status: READY FOR TDD for the dry-run helper + soak harness; policy promotion
(actually flipping fail-closed) stays blocked until that soak evidence exists.**

## P3 — `_legacy` test triage: RE-TRIAGED, split

No remaining `_legacy` directory/file under `_sys/tests`. Remaining "legacy" hits split
into two groups: (a) current compatibility-shim tests still exercised by live code
(`test_checks_common.py`'s `gemini_call()`, `test_model_profiles.py`'s removed-node
regression test, `test_routing_targets.py`'s legacy compat, `test_hub_integration_v42.py`'s
`HubError.report_from_legacy`) — **keep these**; (b) tests tied to gc/Gemini retirement
(`test_migration_phase1.py::TestAiCheck`, session cleanup/archive tests) — **not
independently deletable today**, since `_sys/hooks/ai_check.py`/`ctx_end.py` still
contain live gc/Gemini-specific code. cc.fable confirms this is consistent with gc's
`tier_suspended` status (DIR-002) — no blind deletion.

**Status: READY FOR TDD as split triage — keep group (a) now; migrate/delete group (b)
under P2's hook migration, not as standalone P3 work.**

## Notes on process

- ag's first 7-item attempt (T2, C, D4, D6, D7, P1, G2 all at once) timed out at 900s
  (zombie) — split into two smaller batches (4 + 3 items), both completed normally.
  Lesson for future large delegated design passes: keep individual asks to ~3-4 items.
- cc.fable flagged that INV-31 (independent cross-verification requirement) is already
  satisfied by this round's own structure — ag and cx produced, cc.fable adjudicated
  with independent empirical checks (reading actual code/consensus JSON, not trusting
  peer claims) — no further peer call needed before applying this documentation.
