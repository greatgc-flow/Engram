> Status: ACTIVE | Updated: 2026-07-16 (P0+P1 implemented same night, see addendum at end)

# Overnight Mega-Audit — 2026-07-16

Five parallel tracks, all peers (cx.effort/deepthink, ag.effort/deepthink, cc.fable) engaged, one continuous session. Read-only investigation + one uncompromising multi-round debate; no code/config was changed by this audit — this doc is the input to a follow-up implementation pass.

## Meta-finding (spans all 5 tracks)

The dominant recurring defect class, independently rediscovered in every track, is **declared-but-unenforced drift**: a config knob, doc claim, or backlog entry describes behavior that the code does not actually implement (or implements differently). Every existing check (`check_config.py`, `check_docs_mece.py`, `check_backlog.py --freshness`) validates SHAPE/EXISTENCE, never SEMANTIC TRUTH against live code — so this class of defect is structurally invisible to CI and only surfaces via a full manual audit like this one. Track 2 (cx.deepthink) found this pattern is not confined to docs — it reaches into **live routing/dispatch code** (see T2-1 below, an actual production bug, not just a stale comment).

---

## Track 1 — Docs/source/config MECE audit (3-peer, 2 rounds)

Closed at Round 2 (diminishing but non-zero marginal find rate; folded into the larger effort rather than spinning a Round 3). Full finding set: 21 (Round 1) + 8 (Round 2) = 29, one retracted as a false positive after direct code verification (B5: `hub.py:5030-5074`'s "non-fatal" comment does NOT contradict lifecycle.md — it scopes to a different exception branch than the reject-path `sys.exit(1)`, which does match the doc).

Highlights:
- **Two distinct `CLAUDE.md` files exist** — `P:\CLAUDE.md` (root, stale session-handoff snapshot, last touched 2026-07-05, 11+ days/dozens of commits behind) vs `_sys/claude/config/CLAUDE.md` (global prefs, loaded every session). The root one still lists `backlog_reorg_2026_07_04.md` as master SSOT and frames D1 as "older banked backlog" — both superseded. This gap in the audit's own original domain-scoping was itself only caught in Round 2.
- `check_docs_mece.py` iterates `_DOCS_DIR.rglob("*.md")` only — **every** MECE check (CHK-01/04/05/07), not just one, is structurally blind to both CLAUDE.md files and README.md.
- `gc` is listed as an active/equal peer in the global CLAUDE.md (lines 38, 101) while `docs-v2/specific/gc.md` says `SUSPENDED TOMBSTONE` since 2026-06-25.
- `learning.md` describes a "Three-Layer Architecture" citing two knowledge files that don't exist on disk.
- Backlog `next_action` text-hygiene bug confirmed systemic (not isolated): T44, T47, and the earlier A12 all show a "DONE ..." summary prepended without removing the original pre-completion prose, creating an apparent self-contradiction on literal read (evidence_commit/git history is accurate in all cases). Spot-checked T42/T52/T53 clean — not universal, but recurring enough to need a hygiene pass.
- `schemas.md` marked "ACTIVE v2" but its sample uses `gpt-5.4-mini`, superseded by `gpt-5.6-luna`.
- `manual.md` never mentions Token-Load-Balancing or the Final Arbiter — both are live, activated systems.

---

## Track 2 — Peer/model/profile/session management MECE review (cx + ag, split by domain)

### cx.deepthink — routing/profile/model declaration domain (10 findings, all file:line + 5-Whys)

1. **HIGH — live bug, not just docs drift.** Automatic context-gate failover (`hub.py:5047-5059` → `_snapshot_failover_choice()` → `snapshot_failover_target()` at `hub.py:2708-2730`) picks the first eligible **raw-headroom** row (`snapshot.py:1756-1768`) and never receives `routing-config.json`, so it bypasses `arbiter_models` exclusion, reserve clamps, pacing, cost, and terminal exclusion — all of which the normal AUTO path (`select_load_balanced_peer`, `snapshot.py:1914-2122`) enforces correctly. Live proof: `diag` currently names `cc.deepthink` as `NEXT FAILOVER TARGET` even though it's in `arbiter_models` and should never be an automatic bulk target.
2. **HIGH** — `failure_promotion` config (`routing-config.json:75-90`) is unreachable: the router only matches `quality_failure`/`test_failure`/`reasoning_failure`, but the actual failure classifier (`_classify_ask_failure()`, `hub.py:1700-1759`) only ever emits transport/runtime reasons (`auth_error`, `fatal_error`, etc.). `max_tier_increase`, `promotion_resets_on_success`, `fallback.direction/all_blocked/cross_peer_change`, `scope`, `explicit_profile_policy` are all ORPHANED — hardcoded elsewhere or never read.
3. **MEDIUM** — the `effort_score` threshold is only partially authoritative: its medium-score branch falls through to `ambiguous_default` (`hub_profile_router.py:166-178`), so most routing decisions are driven by the default, not the threshold. Empirically probed live.
4. **HIGH** — token-load-balancer: `select="seeded_weighted_random"` knob is ORPHANED (selection is hardcoded, `snapshot.py:2136-2150`); the "live in-flight deductions" doc claim is false in production (`inflight` param never passed at the real call sites, always `{}`); `cost_map` is mischaracterized as a mere "tie-break" when it actually continuously reweights every candidate (`snapshot.py:2058-2062`).
5. **MEDIUM** — shadow routing resolves the terminal identity via a stale helper (`_fresh_active_coordinator()`) different from the live driving path's resolver, corrupting shadow-mode evidence (does not affect real dispatch).
6. **HIGH** — of 3 configured arbiter triggers (`dissent`, `high_risk`, `r10_final`), only `dissent` is reachable — `detect_dissent()` can never classify a round as `high_risk`/`r10_final`. `authority` config key is also ORPHANED (hardcoded elsewhere).
7. **HIGH** — most of `protocol.json`'s declared policy is pure decoration: all 7 `workload.routing_rules` entries are ORPHANED (nothing reads them); of `collab_rate`, only `current` and two review-interval fields are actually consumed; `risk_table`, `r10_semantics`, `zero_token_allowlist`, `operation_classes`, `action_policy`, etc. have zero Python consumers. R:10 unanimity is hardcoded separately (`hub.py:6024-6034`) from the declared `requires_unanimous` field.
8. **MEDIUM** — the 4 advertised session-policy modes (`auto/reuse/fresh/none`) collapse to 2 live behaviors today, because every current peer declares `session_mode="reuse"`, making `auto==reuse` and `fresh==none` universally.
9. **LOW** — profile declarations are mechanically correct but comments/docs actively contradict them (`ag.opus` mislabeled "arbiter/escalation" in a comment despite the same file correctly excluding it two lines later; `routing.md` self-contradicts on the ambiguous-default profile between lines 30 and 44).
10. Confirms a wide baseline of config IS correctly wired — the audit found real gaps, not universal breakage.

### ag.effort — session/lease lifecycle domain

- **Session reuse (context_affinity) is genuinely wired and measurably exercised** — verified via real `session_state.json` entries showing multi-day reuse across turns, not just a code path that exists unused.
- All 5 `LEASE_STATE` values (open/closed/failed/timeout/expired) are reachable and distinct from real execution outcomes.
- **`SOURCE_STALE` 300s threshold is under-calibrated** (`snapshot.py:657`): real successful heavy-reasoning turns take up to 476s+, so the 5-minute staleness threshold false-triggers routinely on normal operation — independently corroborates what this very session's own `diag` output showed (613s/387s stale warnings on ag/cx while both were actively working).
- **Orphaned session-directory leak**: `.ai/sessions/` accumulates dead room folders (`room-26ab`, `room-8aad`, etc.) forever — `_retire_session` prunes the in-memory history list but never deletes the on-disk directory, and `scrubber.py` explicitly preserves `sessions/` until Tier-4 ZeroBase.

---

## Track 3 — Why is cc usage/cost high (self-investigated)

1. **Confirmed bug**: cc.fable's "147% over capacity" CRIT alert in `diag`'s ATTENTION section is a false positive. It fires off ANY historical session row with `utilization_pct > 100` (`diag.py:1161-1166`, no recency/active-only filter), and the triggering row is a 4-day-stale CLOSED session whose stored 200k denominator doesn't match the CURRENT `model-registry.json` declaration of `claude-fable-5` at 1,000,000 context (`model-registry.json:14-22`). Re-derived against the current registry: 294k/1M = 29%, not over capacity at all.
2. The $77.68 COST figure and cx/ag's "-" are not comparable units (metered $ vs subscription %) — not evidence of imbalance by itself, and is almost certainly scoped to this one unusually large session.
3. `C-7D` pacing at 2.25x is real but is not a routing bug (cc isn't dispatched-to by the hub) — it's workload-driven, largely by this very audit's own direct investigation work.

---

## Track 4/5 — uncompromising debate: quota-dependency display + pacing<=1.0 (5-way, 2 rounds, FULLY CONVERGED)

Participants: cx.effort, cx.deepthink, ag.effort, ag.deepthink, cc.fable. Round A = 5 independent blind proposals; Round B = cross-critique against a shared summary, explicitly barred from silently restating Round A. Convergence reached — no unresolved dissent remains.

### Q1 — Display design (near-unanimous from Round A, fully aligned after Round B)

**Converged rule**: group same-pool time-windows (e.g. a peer's own 5H/7D) onto one line/block; compute a real **time-to-exhaustion** (not a pacing/usage heuristic) and foreground whichever bucket actually projects to exhaust before its reset; demote the rest to a parenthetical/secondary. Genuinely separate pools a peer draws from (ag's `G-*` Gemini vs `3P-*` opus/gptoss) stay as separate line-groups — never collapsed together. When a bucket can't be computed from machine-observed inputs, render `absent`/`binding absent` — never guess (DIR-004).

**Reference formula** (converged around cx.deepthink/cc.fable's version):
```
eta_full = (1 - used_frac) * window_hours / pacing_ratio       # or equivalently from elapsed_seconds
binding  = the bucket in a pool-group with the smallest eta_full, but ONLY if eta_full < time_until_reset
         else label the group "SAFE" / "NO BINDING IN WINDOW", still show the highest-pacing bucket as primary
```

**Reference render** (from live 2026-07-16 data):
```
CC   [OK]  ctx 74k/1M 7%
  ↳ C-pool   🔴 BINDS: 7D 35% 2.25x → empty ~07/18   (5H 20% 0.55x 🟢, resets 3h11m)
AG   [OK]  ctx 119k/1M 9%
  ↳ 3P-pool  🔴 BINDS: 5H 95% 10.42x → empty <1h      (7D absent — not measured, do not guess)
  ↳ G-pool   🟢 SAFE  5H 10% 1.05x, 7D 47% 0.75x — neither binds before reset
CX   [OK]  ctx 120k/258k 46%
  ↳ X-pool   🔴 BINDS: 7D 68% 6.29x → empty before reset
```

**Implementation** (all 5 proposals point to the same functions, so this is low-risk to land): add a pure `time_to_exhaustion()` / `eta_full()` helper next to `calculate_pacing()` in `_sys/core/quota.py` (~after line 56) so the math is SSOT, not duplicated in the renderer. Add `_quota_dependency_groups()` / `_binding_bucket()` in `_sys/cli/diag.py` beside `_quota_display_sort_key()` (~line 314). Replace the flat per-bucket loop in `render_summary()` (~lines 340-350) AND `_live_quota_pool_rows()`/`_live_quota_pool_line()` (~lines 719-748) with the same grouped-render call, so SUMMARY and `--live` cannot drift apart from each other (a recurring failure mode this project has hit before).

### Q2 — Pacing ≤ 1.0 enforcement (converged after Round B; two points were contested in Round A, both resolved)

**Converged final design:**

1. **Hard admission gate, default cap = 1.0, applies to AUTO *and* explicit `--to` asks alike** (all 5 ended here after Round B — no exemption for "explicit means deliberate"; the 2026-07-15 incident's own root cause was explicit asks bypassing balancing, so leaving explicit uncapped just reopens the same hole under a different name).
2. **A single human-only "break-glass" override**, e.g. `--force-pacing <reason>`:
   - Available **only** to a genuine human-terminal-origin ask (distinguished today via the existing `HUB_ORIGIN`/PRO-19 mechanism).
   - **Never** available to system-automated explicit callers, worker/IPC relays, or arbiter auto-wiring — closing the loophole where an autonomous agent just learns to always append the flag (explicitly raised by cc.fable as a new Round-B argument: "a warning shown to an AI relay is not a warning delivered to a human").
   - Every use is logged as a high-severity routing-metrics event (`pacing_override_explicit` / `pacing_cap_override`).
3. **No profile-class exemption for premium/manual_only/arbiter profiles** (`cc.fable`, `cc.deepthink`, `ag.opus`) — unanimous, with CC's own live `C-7D` 2.25x CRIT bucket cited by 4 of 5 peers as the direct counter-proof that "premium" doesn't mean "separate budget."
4. **Narrow, budget-bounded last-resort carve-out for genuine DIR-005 arbiter triggers only** (this was the one real Round-A disagreement — ag.effort alone proposed a blanket premium exemption; converged via Round B to a much narrower version everyone accepted): an over-cap premium/arbiter profile may fire **only** when (i) a real DIR-005 dissent/high_risk trigger is active, (ii) every other candidate in the `arbiter_models` fallback chain is also blocked/ineligible (cascade through alternate-pool arbiters first, e.g. try `ag.opus` before conceding `cc.fable` is needed), and (iii) the spend is logged as `pacing_cap_override` and counted against the existing 5-per-5h arbiter budget — not a free pass, a last-resort valve with the same audit trail as the human break-glass.
5. **False-positive guard**: enforcement only activates once `elapsed_frac` clears the existing 0.05 smoothing floor by a margin (proposals ranged 0.10-0.15) AND `used_frac` clears a small floor (~0.05-0.15) — a 10x ratio two minutes into a window with 2% used warns but never blocks. Two independent fresh observations of the same breach (not one single reading) before hard-enforcing, per cx.effort/cx.deepthink, to avoid a single noisy sample triggering a block.

**Implementation** (converged pointers): extend `calculate_pacing()` in `quota.py:29` to also return raw `elapsed_frac`; add a pure `pacing_admission_for_profile()` / `evaluate_pacing_admission()` near `_profile_pacing_max()` in `snapshot.py:1265`; filter candidates in `select_load_balanced_peer()` before weight aggregation (`snapshot.py` ~2021-2071); apply the same predicate inside `select_arbiter()` (`snapshot.py:2184`/1836) with the cascade-then-carve-out behavior from point 4; re-check immediately before spawn in `hub.py::_action_ask_inner()` (~4931-4989) so explicit-target and any telemetry-race bypass is closed too; add a `token_load_balancing.pacing_hard_gate = {enabled: true, max_ratio: 1.0, unknown_policy: "deny", confirmation_count: 2}` block to `routing-config.json`, with `unknown_policy: deny` (an unmeasured profile is never assumed safe, per DIR-004) — this is a **new**, currently-absent knob, not a repeat of the Track-2 "orphaned config" pattern, since it's being proposed together with its enforcement call sites.

---

## Proposed action plan (NOT yet implemented — for review)

Ordered by ratio of (confidence × blast-radius-if-wrong) to (effort):

**P0 — safe, high-confidence, single-file fixes:**
- Track2-cx#1: stop `snapshot_failover_target()` from bypassing `arbiter_models`/pacing/cost/terminal-exclusion (real live bug, currently mis-surfacing `cc.deepthink` as an automatic failover target).
- Track3#1: scope `SESSION_CONTEXT_OVER_CAPACITY` to the active/most-recent session only, and re-derive `utilization_pct` from current `model-registry.json` at render time instead of a value baked in at write time.
- Track2-ag: recalibrate `STALE_THRESHOLD_SEC` (300 → align with actual observed effort/deepthink turn times, e.g. 600s) or link it to the per-profile timeout config instead of a hardcoded constant.

**P1 — design-approved, ready to implement (Track 4/5's converged output):** the quota-dependency display grouping and the pacing≤1.0 hard-admission-gate, exactly as specified above. This is the largest single piece of new work and touches routing-critical code (`hub.py`'s ask dispatch path) — recommend TDD, same as prior `T4x`/`T5x` batches this session.

**P2 — hygiene, low urgency:** backlog `next_action` text scrub (T44/T47 pattern), `check_docs_mece.py` root-file blindspot, the two-CLAUDE.md consolidation, `gc` removal from the global peer list, `schemas.md`/`manual.md` refresh, orphaned `.ai/sessions/` directory cleanup, `protocol.json` dead-declaration pruning (Track2-cx#7 — large surface, needs its own scoping pass before touching).

**P3 — needs a design decision before any code change:** `failure_promotion` (Track2-cx#2) and the effort-threshold fallthrough (Track2-cx#3) are both "config describes an intended behavior that was apparently abandoned mid-build" — worth a deliberate call on whether to finish wiring them or formally deprecate the knobs, rather than a mechanical fix.

---

## Implementation addendum (same night, after this doc's action plan was written)

P0 and P1 (both halves of Track4/5's converged design) were implemented and verified same-session. **P1a's actual rendering wire-up was deliberately deferred** (see below); everything else is live. Unit suite: 1143 passed, 1 xfailed (the deferred P1a wiring, documented in-line) — `_sys/tests/unit/test_at1_transaction.py::test_at1_lease_closed_on_failure` is excluded from that count, see the new finding below.

**P0 shipped** (`_sys/core/hub.py`, `_sys/cli/diag.py`, `_sys/core/snapshot.py`):
- Fixed the live failover bug (Track2-cx #1): `_snapshot_failover_choice()` now excludes `arbiter_models`/`bulk_exclude_profiles`/the terminal peer, via `_load_balancer_config()` (the correctly-unwrapped `token_load_balancing` reader) — the first delegated attempt used `_load_routing_config()` (the raw, un-unwrapped file) and silently never excluded anything; caught by re-testing against live data, not by the delegated peer's own unit tests, which mocked the wrong config shape.
- Fixed the diag.py "NEXT FAILOVER TARGET" display, which turned out to be a SEPARATE, second computation (`_next_target_line`/`render_headroom` → `_next_headroom_target`) that didn't share the hub.py fix at all — same underlying bug, two independent code paths. Both now filter through a shared `_failover_excluded_profile_ids()`.
- Fixed the `SESSION_CONTEXT_OVER_CAPACITY` false positive (Track3 #1): re-derives against current `model-registry.json` and dedupes to one alert per profile. First delegated attempt assumed `model-registry.json`'s `"models"` field is a list of `{"id":...}` objects; it's actually a dict keyed by model id — silently produced an always-empty lookup, so the "fix" didn't fix anything until caught by testing against the real file.
- Fixed `STALE_THRESHOLD_SEC` (Track2-ag): now derived from `protocol.json`'s `communication_policy.zombie_profile_map` (900s for deepthink) instead of a hardcoded 300s.

**P1a (display) — foundation shipped, wiring deferred**: `time_to_exhaustion()` (`_sys/core/quota.py`) and `_quota_dependency_groups()`/`_quota_dependency_group_text()` (`_sys/cli/diag.py`) are built and unit-tested against the exact converged-design examples. Wiring these into `render_summary()`/`render_live_quota_pools()` was deliberately NOT done same-night: it would rewrite the visible format of ~10 existing, passing tests that encode the OLD flat per-bucket assumptions (exact label text, sort order, line-budget/hidden-count arithmetic) on the actual daily-driver operator dashboard. That's a real UX change the operator should see before it ships, not a judgment call to make solo at 3am. `test_summary_and_live_share_one_dependency_group_payload` is marked `xfail(strict=True)` with this reasoning inline as the tracking marker.

**P1b (pacing gate) shipped** (`_sys/core/snapshot.py`, `_sys/core/hub.py`, `_sys/ai/routing-config.json`): `pacing_hard_gate` (enabled, max_ratio=1.0, unknown_policy=deny) added to `routing-config.json`; `pacing_admission_for_profile()` added to `snapshot.py`; wired into `select_load_balanced_peer()` (AUTO), `select_arbiter()` (with the converged DIR-005 last-resort cascade-then-carve-out for genuine dissent/high_risk triggers), and `hub.py::_action_ask_inner()` (explicit `--to`, closing the loophole the 2026-07-15 incident exposed). **Two more instances of the same "row vs raw profile" shape bug were caught and fixed during verification** (not by the delegated peer's own tests): `pacing_admission_for_profile()` needs a raw `snapshot["profiles"][i]`-shaped dict (with `quota.buckets`), matching the pre-existing `_profile_pacing_max()`'s calling convention — but both `select_load_balanced_peer()` and `select_arbiter()` were calling it with a `_derive_headroom_rows()` output row instead, which never carries `quota.buckets`. With `unknown_policy: deny` as the converged default, this meant *every* candidate read as "unknown" and got excluded — confirmed empirically: `select_load_balanced_peer()` returned `no_eligible_candidate` for every call, i.e. **the gate as first delegated would have silently disabled all AUTO routing the moment it was enabled.** Fixed by looking up the raw profile by id at both call sites (and a third instance in `hub.py`'s explicit-ask check) before calling the admission function. Re-verified against live data afterward: AUTO correctly selects `ag` (currently the only peer under 1.0x pacing); `select_arbiter` correctly returns `None` for routine work (both `cc.fable`/`cc.deepthink` are over-cap tonight) and correctly falls through to the carve-out (`cc.deepthink`) when given a `dissent` context.

**Two new findings from verification, not in the original 5-track audit:**
- **Fixed**: `_sweep_stale_ask_temp_dirs()` (`hub.py`, runs on every `action_ask`) called `entry.is_dir()` on every entry in `_sys/data/temp` before checking whether the name even matched its own `"ask_"` filter prefix — with ~5,700+ accumulated entries (mostly stray `pytest` tmp dirs and, until cleaned tonight, over 12,000 auto-generated `__PSScriptPolicyTest_*.ps1` PowerShell policy-check files), each a separate stat() syscall on this portable/cloud-synced drive, this made a routine sweep exceed pytest's 60s timeout. Fixed by reordering the check (cheap name-prefix filter before the expensive stat call) — reduces the real stat-call count from ~5,700 to the handful that actually match `"ask_*"`. The 12,000+ `__PSScriptPolicyTest_*` files were deleted (safe, auto-regenerated PowerShell artifacts).
- **NOT fixed, flagged for priority follow-up**: `_governed_files()` (`hub.py`, the LL-20260703-005 governed-mutation-guard's file-hashing walk, also runs on every `action_ask`) calls `.resolve()` on every file under `_sys/core`/`_sys/checks`/`_sys/ai` — same class of problem (per-file syscall × directory bloat × slow portable filesystem), but this is core safety-guard code (protects against out-of-band peer writes) and deserves a reviewed fix, not a rushed one. Currently causes `test_at1_transaction.py::test_at1_lease_closed_on_failure` to hang past the 60s test timeout; real-world impact on actual `hub.py ask` latency (not just tests) is plausible and worth measuring first.

**Design decisions made under time pressure, worth a second look:** `unknown_policy: deny` (the converged design's own default) is strict — any profile without fresh, correctly-shaped pacing data is refused, not just deprioritized. This surfaced 5 additional pre-existing unit tests (`test_t3_oversized_ask_guard.py`) that didn't account for the new gate at all; fixed by having that test file's shared scaffolding stub out the pacing check (an "unrelated subsystem" for what those tests actually verify, same treatment as the other stubs already there) rather than relaxing the gate's default. Worth confirming this default doesn't cause real friction once live (e.g. a profile that's simply never been measured yet, not over-cap, still reads as "unknown" -> denied under this policy).
