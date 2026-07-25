# Ops — Full Backlog Triage + Design Consensus (2026-07-24, autonomous session)

> Scope: every item from `architecture-audit-2026-07-24.md` (47 bugs) not yet
> applied, plus 2 new items found during the terminal-freshness investigation
> the same day. Process: cluster related items, run peer design rounds
> (ag.deepthink + cx.deepthink via `--to auto`, EXH/headroom-weighted
> routing per user instruction) until mutual-critical unanimous convergence,
> stop at pre-TDD design (no code applied here). cc (terminal) stays lean:
> drafts only where it already has verified facts from direct investigation,
> otherwise delegates round 1 to peers.
>
> **Operational safety note**: per this doc's sibling audit's own meta-note
> (Top-5 #2 self-demonstrated against that exact file, twice), this doc is
> only written/extended when NO peer ask is in flight, to avoid the
> governed-mutation-guard reverting our own concurrent progress.
>
> Status legend: `[ ]` not started · `[~]` round in progress · `[R1]`/`[R2]`/`[R3]`
> round N done · `[DONE]` unanimous design converged, documented below ·
> `[SKIP]` deliberately deferred (noted why) · `[N/A]` confirmed non-bug/already fixed.

---

## Tier 3 — already designed/applied, status-only (no new work)

- Top-5 #3 Arbiter override — APPLIED `feb7d22`
- Top-5 #4 Handoff race — APPLIED `28b4d67`
- Top-5 #5 Error classification — APPLIED `28b4d67`
- Health-gate profile-blindness — APPLIED `28b4d67`
- diag.py Fix 1 (sort/display EXH mismatch) — APPLIED `cde0b40`
- diag.py Fix 2 (urgency-weighted coupon EXH) — APPLIED `10b5567`
- Terminal-duty-sweep field-mismatch (2-layer bug) — APPLIED `91a7b0b`
- Top-5 #1 Broker transaction safety — **APPLIED + TESTED (2026-07-25)**.
  `_try_broker_fallback()` deleted (`_write_json_atomic` now raises
  `SandboxRenameDeniedError` directly on sandbox-denied replace — no more
  silent queue-and-pretend-success). `HubMutationRequest.expected_revision`
  (sha256, captured at `action_broker_submit()` queue time) + real CAS in
  `_commit_hub_mutation_request()` (mismatch -> `RuntimeError`, request
  routed to `.ai/broker/error/`, target left untouched). Broker request
  files written crash-safely (temp file + `os.replace`). New test file
  `_sys/tests/unit/test_broker_transaction_safety.py` (9 tests).
  ag drafted the implementation (task `bfh2zqngc`); cc's independent
  cross-check against the REAL current hub.py (not ag's stale scratch
  mirror — same pattern flagged repeatedly earlier in C1) found and fixed
  3 real issues before applying:
  1. ag's `_normalize_runtime_files()` leases-filtering rewrite silently
     reverted the T83 fix (matching on the leases dict KEY instead of
     `entry["peer_id"]`, dropping the `isinstance(value, dict)` guard) —
     would have re-broken lease reclaim for every real lease.
  2. ag's `action_broker_submit()` rewrite dropped the existing
     `try/except json.JSONDecodeError` clean-error handling, letting a
     malformed payload crash instead of exiting cleanly — restored.
  3. ag used the newer C1 `_mutation_lock_resource()` naming for the
     `_normalize_runtime_files()`/`action_thread_promote()` locks; the
     codebase's existing convention for these exact files is plain
     resource names (`"state"`/`"nodes"`/`"leases"`/`"mailbox"`, already
     used by ~15 other call sites incl. `action_init_session`). Using the
     newer/different name meant the new locks did NOT actually serialize
     against those other writers — live-reproduced as 3-of-4 members lost
     under `test_locking_stress.py::test_parallel_init_session` (4 parallel
     `init-session` processes). Fixed by matching the established names.
  Also found and fixed, while chasing that same test failure: a real
  Windows-only race in `_get_lock()` itself — concurrent first-time lock
  FILE creation (`os.open(..., O_CREAT)`) on the same `.lock` path can
  transiently raise `PermissionError` even though nothing is actually
  access-restricted; added a short bounded retry (matches the existing
  backoff pattern in `_write_json_atomic`). `test_parallel_init_session`
  itself was also adjusted: it used synthetic agent names never present in
  the live routing config's active-root set, which `_normalize_runtime_files`
  legitimately purges by design — previously masked by that block running
  unlocked (fast enough to rarely interleave with real writes), now
  reliably exposed once genuinely lock-protected. Not a broker bug; the
  test now exercises the same 4-way OS-lock contention with a real root
  peer id instead. Full unit suite: 1420 passed, 4 pre-existing unrelated
  failures (verified identical on the pre-change baseline via `git stash`),
  1 skipped.

  **Cross-verification**: cx zombied 3 consecutive dispatch attempts
  (recovered via `peer-recover` each time, fresh IPC file each retry per
  session policy, third failure was an environment-side `ImportError` in
  cx's own tool invocation — hub.py itself ran fine directly); switched to
  ag per the established cx-instability fallback. ag confirmed cc's 3 fixes
  against the real source (leases peer_id-matching, JSONDecodeError
  handling, lock-name alignment), produced a full lock-name catalog via its
  own grep (24 call sites across state/nodes/leases/mailbox, no fourth
  naming variant — cc independently re-grepped and got a matching count),
  and confirmed the CAS/deleted-fallback-caller analysis holds. However
  ag's cited pytest run ("82 passed") listed test names from BEFORE cc's
  own later renames (`test_normalize_runtime_files_acquires_mutation_resource_locks`
  vs the real current `test_normalize_runtime_files_acquires_locks_and_preserves_t83_lease_matching`)
  — the same stale-scratch-mirror pattern flagged repeatedly earlier this
  session for ag's test-execution claims specifically (its file-reading/
  grepping tool and its pytest-execution tool appear to resolve against
  different copies of the repo). Treated as unverified; cc's own direct
  runs are the trusted evidence.

  Chasing the `test_parallel_init_session` fix to full stability (ran it
  20x in a loop, not just once) surfaced ONE MORE genuine race, found by cc
  directly (not by either peer): `_read_json()` had no protection against a
  transient Windows `PermissionError` when reading a file mid- (or just
  after) another process's concurrent `os.replace()` on the exact same
  path — rare enough that 15 clean trials on the pre-Top-5-#1 baseline
  never hit it, but real (reproduced directly). Fixed with the same bounded
  retry pattern already used in `_write_json_atomic`/`_get_lock`; unlike
  those two, a persistent failure after retries is re-raised rather than
  silently swallowed to `{}`, since `_read_json`'s existing `{}`-on-error
  contract is for "file doesn't exist yet" / "corrupt content", not for
  "we couldn't get permission to read a file that's actually fine" — the
  latter should surface loudly. Re-verified: 20/20 clean runs of
  `test_locking_stress.py`, full suite re-run clean (1420 passed, same 4
  pre-existing unrelated failures, 1 skipped).

  **Status: fully applied, cc-tested (repeatedly, including deliberate
  stress-repetition beyond a single green run), ag cross-verified (source
  analysis trusted, test-execution claim not) — ready to commit.**

## Tier 4 — confirmed non-bug / zero runtime impact / cosmetic (no round)

- §1.1 session-retirement disk-hygiene gap (ag-confirmed zero runtime impact)
- §2.2 session ID/resume — CONFORMS
- §2.5 profile/flag translation — corrected as non-bug (legitimate data-driven passthrough)
- §4.3 governance systems — mostly conforms, 1 write-only stub (folded into C11)
- §7.3 artifact-claim/status/finalize/discover — LOOKS CORRECT
- §8C LOOKS-CORRECT note (threshold arithmetic itself is right once given correct capacity)
- Coupon-urgency-weight 0.001 boundary discontinuity — display-invisible, flagged not worth a round (from prior session)

---

## Tier 1 — full 3-round mutual-critical design (this session's main work)

### C1. Governed-mutation guard concurrency [Top-5 #2] — `[DESIGN DONE, IMPL PASS 1 APPLIED (8ea6556), PASS 2 BLOCKED]`
No design exists. Highest-severity confirmed-unfixed item; self-demonstrated
3x this session (twice against the audit doc itself). Needs: global
dispatch-scoped attribution (not just a lock — must identify WHICH in-flight
ask legitimately owns a change) so an innocent concurrent ask is never
blamed, the real culprit never escapes, and authorized concurrent output
(§5.6) is never wrongly reverted. Also covers §5.7 (TOCTOU in the "race
guard" itself: rehash-then-checkout with a gap) and §5.8 (guard failures
fail OPEN — note: an existing test currently REQUIRES fail-open; any fix
must explicitly decide whether to flip that contract, not silently break it).

### C2. ContextGate capacity/model-resolution cluster — `[DONE, unanimous R3, scope expanded to include §3.1]`
- Top-5 contender: all `ag.*` profiles hit ContextGate as fake model id
  `"ag"` → fabricated 200k limit instead of real 1M+ (`hub.py:5466,5468`,
  `hub_context.py:117`). Live-confirmed via real dispatch probe (§9).
- §8C.1 CJK token-estimate formula wrong (`len/2×1.8` vs documented `len/3.5×1.8`)
- §8C.3 malformed/missing registry silently guesses 200k instead of failing closed

### C3. ContextGate failover-chain cluster — `[DONE, unanimous R2, absorbs §3.1+§3.2, composes with C2+C5]`
- §8C.4 static failover chain can't fit the overflow it exists to handle
  (Sonnet 1M → Haiku 200k; returns a bare model slug, not a routable node)
- §8C.5 constructor-injected registry ignored for failover (module-global load at import time)
- §8C.6 utilization telemetry always reports 0% (`ratio` field doesn't exist, test mocks it)
- §8C.7 error message hardcodes "95%" regardless of real configured threshold

### C4. Pre-commit check-script hardening cluster (§8K, 7 items) — `[DONE, unanimous R3]`
- staged-blob vs worktree gap (biggest: a staged violation can be masked by
  restoring the worktree copy post-stage; CHK-ENC already reads staged
  blobs correctly and is the reference pattern)
- CHK-01 misses ordinary Markdown-link syntax (backtick-only)
- CHK-02 INV-19 Korean-scan only checks `*.md`, not the declared in-scope `core`/`checks`/`ai` dirs
- CHK-03 checks stale HEAD not pending commit, fails open, not even wired into the real hook
- CHK-CONST is a bare substring check (comment text satisfies it), only checks first match
- CHK-LEDGER: empty `expected_substring` defaults to `""` which always matches
- CHK-LEDGER: blueprint-mention check doesn't verify the specific backlog item still exists

### C5. Terminal-identity/freshness unification — `[DONE, unanimous R3, cc's own draft substantively corrected]`
cc already has verified facts from direct investigation this session (no
peer round-1 needed for fact-finding — sent straight to peer critique).
Unifies 3 findings into one coherent design target:
- NEW: `_fresh_active_coordinator()` exists, has zero callers anywhere; the
  two REAL raw-field consumers (`hub.py:2824` LB-failover-exclude,
  `hub.py:5455` pacing/reserve dispatch gate) read
  `state.get("human_interface_peer")` directly, unchecked for freshness —
  right now they protect a peer (`cx`) that is 8+ days stale instead of the
  peer actually acting as terminal.
- NEW: freshness model design gap — terminal role requires BOTH
  assignment-freshness AND health-freshness in the same 30-min window, but
  health only refreshes via hub-tracked ask/heartbeat, not by a human
  quietly chatting through a session — so the ACTIVE terminal peer
  structurally drifts to `health_stale` within ~30 quiet minutes.
- diag.py terminal-priority EXH reserve/discount — ag's earlier draft had
  unverified assumptions (`human_interface_peer` vs `active_console_peer`
  signal ambiguity never disambiguated; `active_delegations` counted from
  `.ai/leases.json` never checked against the real schema).
cc's draft sent for critique: see §C5 result section below once round 2/3 land.

### C6. Consensus voter-health live-recheck race (§1.3) — `[DONE, unanimous R2]`
`_decide_consensus()` re-reads voter health LIVE at check-time instead of a
round-start snapshot — a voter who validly agreed while healthy can
retroactively force `escalated`/`human_gate` if it goes RED afterward,
breaking the "a previously cast agree remains valid" invariant. Bundle with
C1 if the peers find the dispatch-lock design naturally covers a
round-start health snapshot too; otherwise design separately.

### C7. Process/lease supervision cluster — `[DONE, unanimous R3]`
- §3.3 Pipe transient failures report `sys.exit(0)` (indistinguishable from
  success); PTY's distinct `SOFT_SKIP_EXIT=7` is confirmed unconsumed by
  EVERY caller (`action_ask_all`, `_real_arbiter_invoker`, `ctx_save.py`,
  `ctx_end.py`). NOTE: audit doc claims "fully designed fix in §6" but no
  such design section exists in the current doc — peers must verify this
  claim against real source/history or treat it as undesigned.
- §3.4 PTY lease left "open" during tier escalation (completed lower-tier
  lease never marked closed, later killed by the expiry sweep)
- §3.5 Pipe supervision misses small flushed chunks before a long gap on
  Windows (blocking read + buffer-growth-only zombie tracking)
- §7.2 `_lease_sweep` silently swallows timezone-comparison exceptions via
  bare `except Exception: pass` — naive-vs-aware datetime mismatch means a
  zombie lease NEVER gets marked expired

### C8. peer_console.py security cluster — `[ ]`
- §9.1 Codex `exec`/`review`/`resume` bypass workspace-write/profile security
  defaults entirely (real gap, confirmed via live `codex --help`)
- §9.2 `apply_security_semantics()` has zero production callers — declarative
  `security_contract.sandbox_semantics` doesn't drive any real behavior
  (same "designed but never wired" pattern as C5's `_fresh_active_coordinator`
  and the arbiter-override precedent)
- §9.3 profile banner can report a model that isn't actually launched
- §9.4 `_append_missing()` mishandles a flag already present positionally

### C9. User-facing ctx_*.py robustness — `[ ]`
- §6.5 `ctx_end.py:228-231` hangs indefinitely on `input()` when `claude -p`
  fails — a script the user runs directly per CLAUDE.md workflow rules,
  elevated priority (this is the "user-facing" item flagged repeatedly in
  backlog notes across the whole session, never yet designed)
- §6.6 `ctx_save.py:114-118` doesn't check subprocess returncode before
  unconditionally overwriting `summary_session.md`

---

## Tier 2 — lighter single-pass design (time/token-budget triage, noted as reduced rigor)

### C10. Misc correctness grab-bag — `[ ]`
- §1.2 `snapshot.py`/`hub.py:7190-7192` hardcode peer identity
  (`peer != "cx"` string compare for credit-consume) instead of a capability flag
- §1.5 `action_init_session`/`action_send` — no validation peer identity is registered/routable
- §2.1 oversized-PTY-prompt staging mutates `cmd` directly in core dispatch loop (should be an adapter `prepare_input()` hook per cx's refinement)
- §6.1 `peer_mgr.py:_save()` fixed `.tmp` path, no lock (concurrent admin collision)
- §6.2 `peer_mgr.py` multi-file mutations non-atomic (crash mid-sequence desyncs 3 registries)
- §6.3 `provisioner.py:_install_extra()` doesn't guard `_extract()` against a checksum-incomplete download
- §6.4 `quota.py:get_remaining_seconds()` naive-ISO timezone bug — downgraded to latent/defensive, no naive timestamp observed in practice
- §7.1 `context-ack` lockless RMW + 100% unconsumed (write-only stub, same pattern class)
- §9.5 `quota.py` defensive gaps: `reset_in_seconds` ValueError outside try/except; `calculate_pacing()` treats `NaN` used_frac as `"safe"`
- §5.9 (test-suite blind spots, 6 items) — these are test-quality gaps that should be fixed ALONGSIDE whichever real-bug fix they were masking (C1, C7), not as standalone design items; tracked here as a reminder, closed automatically when the parent bug's fix lands with real regression tests.
- §8C.8 traceability references point at nonexistent doc/test paths — doc hygiene, fix opportunistically when touching C2/C3.

---

## Results (filled in as clusters converge)

### C1 — FINAL DESIGN (unanimous, 3 rounds: cx draft → ag critique → cx reconciliation)

**Rejected**: cx's round-1 "GuardCohort" (group overlapping asks, stage
stdout/success until the whole cohort seals, one verification per cohort).
ag killed this in round 2 with 2 points cx accepted as fatal: (a) staging
stdout until cohort-close breaks real-time P2P log streaming/progress
visibility, (b) a fast ask gets latency-coupled behind the slowest
overlapping ask before it can report success. Also: cascading
indeterminate-failure blast radius under continuous overlap, and
process-tree quiescence is much less bounded than cx's original design
assumed.

**Adopted**: per-ask staging workspace → clean guard verification → short
host-side CAS commit → immutable receipt, PLUS a mandatory non-destructive
live-tree sentinel kept as defense-in-depth (scratch-dir isolation is not a
PROVEN security boundary for `ag`/`cc` today — they could still address the
live repo directly by absolute path; the sentinel is what catches that).

Flow:
1. **Admission**: durable `AskGuardLease` (ask_id, peer/profile+process
   identity, live governed-tree baseline digests, phantom-namespace
   baseline, starting mutation epoch, state=running) created before
   dispatch; failure here is fail-closed (don't spawn the peer).
   `.ai/scratch/<ask_id>` becomes the peer's working dir. Streaming/progress
   unaffected — no ask waits on another ask. Any proposed governed change is
   written as a scratch artifact + `StagedMutationProposal` manifest
   (ask_id, canonical_target_path, expected_revision, staged_blob_digest,
   requested_operation, reason) — peers never submit directly as a live
   mutation.
2. **Per-ask guard verification** (after the full child process tree is
   confirmed closed — addresses the earlier "process-tree quiescence"
   concern directly): re-snapshot the live governed tree, fold in immutable
   `MutationReceipt`s committed since the ask's starting epoch; a digest
   transition fully explained by those receipts = legitimate concurrent
   output; anything left over = `UNATTRIBUTED_GOVERNED_CHANGE`. On
   unattributed change: never name a peer as culprit, never `git checkout`
   /unlink/overwrite, preserve live bytes, quarantine baseline+current bytes
   +metadata, mark THIS ask `guard_integrity_indeterminate`, close governed
   admission pending reconciliation, withhold normal success. Only the
   final completion notification is held for this — not streaming.
3. **Host commit**: on a clean `GuardVerificationReceipt`, host converts the
   staged proposal to a `MutationIntent`, acquires
   `_mutation_lock_resource(path)` (SHARED with the Top-5 #1 broker design —
   explicitly not a second lock/CAS system), CAS-checks the raw-byte
   `expected_revision`, atomically commits, writes an immutable
   `MutationReceipt`. Only then is the ask reported fully successful. Two
   proposals from the same revision: first wins, second gets
   `revision_conflict`.

**Fail-open → fail-closed, explicitly flipped**: `test_guard_post_check_error_never_breaks_ask`
must be REPLACED (not silently altered) with real fail-closed tests;
`test_clean_at_dispatch_tracked_auto_reverted` (currently mocks `git
checkout`, never verifies actual byte restoration) must be replaced with a
real-filesystem assertion that NO destructive rollback occurs (checkout is
deleted from the design entirely — ag confirmed via codebase-wide search
that nothing else depends on the auto-revert actually happening, no
dispute). New `guard-reconcile` recovery action required so a transient
guard fault doesn't permanently brick dispatch.

**9-scenario test-plan reconciliation** (all real, non-mocked — temp git
repo + real OS processes + filesystem barrier files): two-ordinary-asks-one-writer,
authorized-commit-during-another-ask, human/editor-write-during-ask,
old-TOCTOU-repro, two-authorized-asks-same-file, guard-infrastructure-failure,
ask/process-crash, recursive-failover/escalation (all attempts share one
ask_id/scratch-root/baseline/lease), add/delete/rename/dirty-baseline
(`ABSENT` sentinel, canonicalized+containment-checked paths, Windows
case-only rename, pre-existing-dirty-file-is-a-valid-baseline). All 9 pass
under the final design per cx's scenario-by-scenario walkthrough.

**C6 interaction (new finding, both peers agree)**: a queued vote merge
must carry `source_ask_id`; broker drain rejects/postpones it while the
source ask is `running`, quarantines it if the source becomes
`guard_integrity_indeterminate`; `_decide_consensus()` must not finalize on
a vote whose source ask lacks a clean `GuardVerificationReceipt` yet.
Terminal/host-originated votes (not from a peer ask) are unaffected.

**Also required for TDD stage** (not done here, noted for later): update
`_sys/checks/check_lesson_enforcement.py` (currently asserts the OLD
`_governed_post_check()` shape) and `test_contracts.py` (per DIR-003, if
`action_ask()`'s signature/defaults change) to match the new receipt-backed
contract; extend the same cohort-free receipt model to `_phantom_scan()`
(ag's round-2 finding, cx didn't dispute) so authorized concurrent creation
can't still be falsely reported through the parallel phantom-write path.

**Status**: design complete, unanimous, ready for TDD/implementation. NOT
applied this session (pre-TDD only per user instruction). This is now the
natural next fix to pick up, ranked above Top-5 #1 (broker) since broker
should be implemented using C1's shared `_mutation_lock_resource()`/
`expected_revision` primitives, not the other way around.

### C2 — FINAL DESIGN (unanimous, 3 rounds: ag draft → cx empirical critique → ag reconciliation)

**Rejected**: ag's round-1 4-tier fallback chain (model_id → extracted CLI
`--model` operand → `runtime_context_window` → parent-node model_id). cx
empirically probed all 5 real `ag.*` profiles and proved the core flaw: a
CLI invocation operand (e.g. `gemini-3.5-flash-low`) is NOT the same thing
as a `model-registry.json` capacity key — none of the 5 live ag operands is
an exact registry key, so "extract the operand" (ag's Tier 2, which DOES
exist as `hub_peer.extract_model_operand()` — that part was real) still
can't answer "how big is this model's context window." Tier 3 (feeding a
raw number into a registry *lookup*) was a category error. Tier 4 (parent
`ag` node fallback) was unsafe — the parent node reflects its DEFAULT
profile (`deepthink`), so `ag.opus` falling through to it would silently
inherit Gemini Deepthink's window instead of Opus's. ag conceded all three
points in round 3 without a 4th round needed.

**Adopted** — strict-priority `ResolvedContextTarget` resolution (no
guessing, no CLI-operand-as-registry-key, fail-closed on no match):
```python
@dataclass(frozen=True)
class ResolvedContextTarget:
    profile_id: str
    admission_limit: int
    limit_basis: str  # "profile_declared_limit" | "registry_model_id" | "exact_registry_model_id"
    registry_model_id: str | None
    context_window_kind: str  # "ceiling" | "proven_lower_bound"
```
1. **Priority 1**: profile node declares `runtime_context_window` directly
   (e.g. 1,048,576 for `ag.standard`/`.effort`/`.deepthink`) → use as-is, no
   registry lookup (`limit_basis="profile_declared_limit"`).
2. **Priority 2**: profile node declares an explicit `registry_model_id`
   (e.g. `ag.opus` → `claude-opus-4-6`) → exact-key registry lookup.
3. **Priority 3**: `profile_data["model_id"]` present AND an exact
   registry-key match → use it.
4. **Priority 4**: none of the above → `UnknownModelCapacityError` (new
   `ContextGateError` subclass, since the existing one assumes an integer
   capacity for its arithmetic formatting — an unknown/None capacity would
   break that). NEVER infer from `--model`/`profile_args`/`runtime_model`/
   root peer id, NEVER default to 200k.
- `ag.gptoss` gets `context_window_kind="proven_lower_bound"` (its only
  known number, 8000, is a measured floor, not its true ceiling — must
  never be reported/telemetered as the model's real capacity).

**Bug 2 (CJK formula)**: unanimous from round 1, no dispute — change
`hub_context.py:65`'s `int(len(text)/2*1.8)` to `int(len(text)/3.5*1.8)`,
matching the documented contract (`docs-v2/general/lifecycle.md:379`).
241,778-Hangul-char regression target: exactly 124,342 tokens (was
217,600 — a 75% overestimate that was triggering false pruning on Korean
workflows).

**Bug 3 + scope-expansion (critical finding)**: cx confirmed via direct
source read that the SAME `except Exception: pass` block that the original
architecture audit flagged as §3.1 ("ContextGate rejection is swallowed")
would ALSO swallow the new `UnknownModelCapacityError` — meaning shipping
C2's fail-closed change alone would change NOTHING in production. **C2 and
§3.1 must ship as one atomic commit.** `hub.py`'s exception handler around
the dispatch path must be updated so ContextGate rejections (both the
existing kind and the new `UnknownModelCapacityError`) surface a clean
pre-dispatch error and stop BEFORE process spawning — not get caught and
ignored. `_load_json()` gets strict schema validation (missing/non-object
`models`, non-positive/non-numeric `context_limit` → `ContextGateConfigError`,
not silent `{}`). `check_and_prune()` (a second, separate caller of
`context_limit()`) must get the same fail-closed treatment, not just
`ContextGate.check()`.

**Test plan** (both peers agreed no non-spawning `action_ask` dry-run mode
currently exists — ag's round-1 assumption was wrong, conceded): pure unit
tests directly against the resolver for all 5 live `ag.*` profiles + `cc.*`/
`cx.*`, the exact 241,778-char CJK regression, schema-corruption and
unknown-model-id fail-closed unit tests, plus ONE real integration test
asserting `subprocess.Popen`/CLI execution is never reached when
`action_ask` dispatches against an unmapped model.

**Sequencing** (single atomic commit, no intermediate broken state): (1)
resolver + unit tests for every live profile, (2) CJK formula fix + remove
200k fallback, (3) strict registry validation + `UnknownModelCapacityError`,
(4) fix the exception handler so rejections halt dispatch, (5) integration
test proving zero process invocation on rejection. ag's round-1 idea of a
temporary allowlist-during-migration was explicitly rejected by cx (would
preserve the exact prohibited guessing behavior and add cleanup debt) — no
objection from ag in round 3.

**Status**: **APPLIED + TESTED (2026-07-25)**. `ResolvedContextTarget`
(frozen dataclass) + `resolve_context_target()` implemented in
`hub_context.py` with the exact strict Priority 1-4 order from the design.
`_FAILOVER_CHAIN`/`_load_failover_chain()` deleted. CJK formula fixed
(`len/3.5*1.8`). `ContextGateConfigError` (strict registry schema
validation) and `UnknownModelCapacityError` (Priority 4, no 200k default
anywhere) added. `hub.py`'s dispatch-path exception handler around the
ContextGate block now narrowly catches `ContextGateError` (and its
subclasses) to surface a clean pre-dispatch failure and `sys.exit(1)`
*before* any subprocess spawn, instead of the old bare `except Exception: pass`
that silently swallowed rejections (§3.1, confirmed live: `ContextGateError`
is a `RuntimeError` subclass raised *inside* `ContextGate.check()` itself,
not returned as a dict value, so the old bare except caught it every time)
— genuinely unrelated exceptions still fail open with a warning, narrower
than before but not zero-tolerance, per the design's own distinction.
`check_and_prune()` routes through the same resolver, no separate silent
default. `ag.gptoss` gets `context_window_kind="proven_lower_bound"` via a
general schema check (`validation_method`/`context_window_kind` markers),
not solely a hardcoded profile-id special case (confirmed by cross-
verification). 15 tests in new `test_context_gate_c2.py`, including 2 real
integration tests that monkeypatch `subprocess.Popen` to prove zero-spawn on
rejection.

**Origin of this implementation**: same pattern as C5 — ag's dispatch wrote
files directly and crashed before returning explanatory text. Unlike C5's
first draft, this one was substantially solid on cold review: all of ag's
own 14 tests passed unmodified against the real source. cc still found and
fixed 2 real issues before trusting it:
1. **Dead code from the `_FAILOVER_CHAIN` deletion**: `_action_ask_inner`
   still had a ~38-line `elif action == "failover":` block (including a
   recursive dispatch call) and an 8-line `elif action == "reject":` block —
   both permanently unreachable, since `check()` never returns those action
   values (raises `ContextGateError` directly instead). Deleted; the real
   rejection handling is entirely in the new `except` clause.
2. **A pre-existing test broke for a legitimate reason, not a C2 bug**:
   `test_at1_transaction.py::test_at1_terminal_timeout_not_permanent_red`
   mocks a minimal, profile-less `orchestration.json` and dispatches to bare
   `"cc"` — before C2 this silently passed via the old 200k default; under
   C2's strict resolver it correctly raises `UnknownModelCapacityError`
   (real peers always have real profile nodes — `_resolve_profile_id("cc")`
   against the REAL orchestration.json correctly resolves to `"cc.deepthink"`,
   confirmed live). Fixed by disabling `_CONTEXT_GATE_AVAILABLE` for that one
   test, since it's validating unrelated terminal-timeout/health-RED logic,
   not ContextGate.

**Cross-verification** (ag, same-peer re-dispatch, explicitly told to attack
its own leftover code): confirmed both of cc's fixes, swept for and found no
other test with the same profile-less-orchestration collision, probed
`resolve_context_target()`'s fail-closed guarantee with type-confusion/
case-sensitivity/contradictory-priority inputs (all correctly fail-closed or
resolve per the documented priority order), confirmed the CJK formula has no
disagreeing second implementation elsewhere in the codebase, ran the real
test suite directly (matched cc's own count) — and found **one more real
gap**: `_load_strict_json()`'s registry validation accepted a fractional
`context_limit` (e.g. `0.5`) since it only checked `> 0`, but the resolver
then computes `admission_limit=int(clim)`, silently truncating to `0` —
every query to that model would then fail closed for a confusing reason
(0-token failover threshold) instead of a clear config error at load time.
Fixed by requiring a genuine positive `int` (not just any positive number)
everywhere `context_limit`/`runtime_context_window` is consumed (registry
validation, all 3 registry-lookup branches, and the profile-declared-limit
Priority 1 check itself, which had the identical float-truncation exposure
for `runtime_context_window`). New regression test
`test_fractional_context_limit_raises_context_gate_config_error`.

Full suite: 1456 passed, 4 pre-existing unrelated failures (identical to
baseline), 1 skipped.

### C5 — FINAL DESIGN (unanimous, 3 rounds: cc draft → cx real-empirical refutation → ag independent verification+reconciliation)

**cc's round-1 draft was substantively wrong in 2 places, both caught by
cx's real source verification (not just review) and independently
re-confirmed by ag before adoption — the same "design review isn't enough,
verify the applied/real thing" pattern this whole session keeps hitting**:

1. **"The 4 identity fields always stay in sync" — FALSE.**
   `action_terminal_handoff()` (hub.py:~7085-7107) does set
   `human_interface_peer`/`active_console_peer`/`leader`/`active_coordinator`
   together atomically — but that only proves equality AT THAT INSTANT.
   `action_leader_claim()` (~7059) and `action_leader_yield()` (~6997) later
   mutate `leader`/`active_coordinator` alone, WITHOUT touching either
   terminal field — so in real production paths they genuinely diverge over
   time. Treating them as interchangeable would have been a second,
   different bug hiding behind the "coincidentally correct today" observation.
2. **Reusing/patching `_fresh_active_coordinator()` was rejected, not just "unwired."**
   Even wired in, it would still be broken for this purpose: a real terminal
   handoff writes neither `leadership.challenge_until` nor
   `role_assignments.coordinator.assigned_at` (confirmed: live state has
   neither, function empirically returns `None`), AND it never verifies
   `role_assignments.coordinator.peer == active_coordinator` — a fresh
   assignment for peer A could incorrectly validate a stale record for peer
   B. Both peers explicitly rejected cc's fallback idea of just adding
   `human_interface_assignment_time` to this function too — that would
   further conflate coordinator/leadership with terminal ownership, two
   roles that must stay separate.
3. **cc's "just decouple assignment-freshness from health-freshness" lean was
   INSUFFICIENT, not just risky.** `human_interface_assignment_time` is only
   ever set at handoff and never renewed by ongoing activity; the
   `terminal-duty-sweep` watchdog meant to periodically re-validate it isn't
   scheduled anywhere (on-demand CLI action only) — so even with health
   removed from the equation, every legitimate terminal assignment would
   still hard-expire 30 minutes after handoff, regardless. A "have the sweep
   just re-touch the timestamp periodically" alternative was explicitly
   evaluated in round 3 and rejected too: a background sweep has no real
   process visibility, so if the actual interactive terminal process
   crashed, blindly re-touching the timestamp would extend a DEAD terminal's
   assignment indefinitely — defeating the watchdog's entire purpose.

**Adopted — a renewable terminal-session lease, not a freshness-check tweak**:
```json
"human_interface_assignment": {
    "peer": "ag", "profile": "deepthink", "lease_id": "term-lease-uuid-1234",
    "assigned_at": "2026-07-24T10:00:00+09:00",
    "last_heartbeat_at": "2026-07-24T17:50:00+09:00",
    "expires_at": "2026-07-24T18:20:00+09:00", "owner_pid": 12345
}
```
- The interactive console wrapper claims terminal duty on launch and renews
  the lease periodically WHILE ITS OWN PROCESS IS ALIVE (real liveness
  signal, not a proxy). Handoff mints a new `lease_id`/epoch, invalidating
  the old one; heartbeat/close operations CAS on `lease_id` so a resurrected
  stale process can't clobber a newer assignment. Crash/death stops
  renewal → the lease naturally expires within its window → next sweep
  observes expiry and can select a replacement. `assigned_at` becomes pure
  audit history; `last_heartbeat_at`/`expires_at` carry actual liveness.
- New pure, O(1), state-only resolver replaces BOTH real raw-field gate
  sites (`hub.py:~2824` LB-exclude, `~5455` pacing/reserve dispatch):
  `resolve_terminal_identity(state, now) -> {peer, lease_id, status: FRESH|EXPIRED|VACANT|MISMATCH, is_active_terminal, reason}`.
  No health/capability/snapshot/quota I/O (must stay cheap — line ~5455 runs
  on every single ask dispatch). Missing/malformed/expired evidence →
  `UNKNOWN`/not-fresh, NEVER implicitly treated as fresh (explicitly does
  NOT reuse `_human_interface_assignment_fresh()` as-is for this purpose,
  since ITS own no-timestamp-found path intentionally returns `True`,
  assuming a separate health check follows elsewhere — reused bare in these
  cheap gates, that exact behavior would recreate the bug being fixed).
- **Eligibility now explicitly SPLIT into two different questions**:
  (a) RETENTION of the current terminal — fresh lease + enabled profile +
  not hard-quarantined/gate-closed. Ordinary general-health `STALE` does
  **NOT** evict it (directly fixes the "actively-used terminal drifts stale
  within 30 quiet minutes" problem). (b) REPLACEMENT selection — full
  health/capability/profile-gate/tier/pacing checks still apply exactly as
  today. Hard RED/quarantine or a genuinely expired lease can still trigger
  replacement either way.
- **Signal ambiguity resolved**: `human_interface_peer` is canonical, full
  stop. `active_console_peer` is a compatibility mirror only (currently
  written to the same value at handoff time but is unvalidated/unnormalized
  elsewhere) — a mismatch between them should surface as diagnostic
  evidence, not be silently resolved by "whichever field is nonempty."
- **`active_delegations`/`leases.json` question resolved (empirically, not
  assumed)**: real schema directly inspected — a UUID-keyed dict of
  `{ask_id, peer_id, pid, room_id, started_at, expires_at, heartbeat_at,
  status, ask_query_file}` (220 historical + 1 open entry at probe time).
  There is NO delegation-origin field, no requester-peer field, no
  terminal-lease-id-at-dispatch, no interactive-vs-background
  classification. This file can only support a DERIVED "in-flight asks
  currently targeting peer X" count (after filtering open + not-expired +
  PID/heartbeat-alive + profile-normalized-to-root) — that's target
  workload, not causal delegation attribution; naively counting all "open"
  records would be wrong since the file retains closed/failed/timeout/
  unreconciled entries too. Decision: apply terminal-priority policy off the
  fresh lease alone, do NOT invent an `active_delegations` count the data
  can't actually support; if delegation-aware policy is genuinely needed
  later, the schema needs new fields first (`origin`, `requester_peer`,
  `dispatch_kind`, `terminal_lease_id_at_dispatch`) — not designed here,
  explicitly deferred.
- **diag.py terminal-priority EXH**: raw EXH stays the visible resource
  forecast; any terminal-priority adjustment renders as a SEPARATELY named
  `effective_EXH`, never silently overwriting the raw number (same
  raw-vs-effective transparency principle already used for the coupon-EXH
  discount work earlier this session).

**Status**: **APPLIED + TESTED (2026-07-25)**. `resolve_terminal_identity(state, now)`
implemented as designed (pure, O(1), fail-closed). `human_interface_assignment`
lease object added; `action_terminal_handoff()` mints a fresh `lease_id` on
every handoff; new `action_terminal_heartbeat()`/`action_terminal_close()`
(+ new CLI actions `terminal-heartbeat`/`terminal-close`) provide CAS-protected
renewal/release keyed on `lease_id`. The two raw-field consumer sites
(`_snapshot_failover_choice`'s LB-exclude, the pacing-gate's dispatcher
terminal self-check) now call the new resolver instead of reading
`human_interface_peer` directly. `action_terminal_duty_sweep()` now checks
lease expiry via the resolver instead of the old `_human_interface_assignment_fresh()`.
diag.py's `_current_terminal_peer()` tries the new resolver first, falling
back to the pre-existing `_active_terminal_profile()` logic.

**Origin of this implementation**: ag's dispatch used file-write tools
directly on `hub.py`/`diag.py`/`test_contracts.py` (triggering C1's governed-
mutation guard, which correctly quarantined evidence non-destructively and
did not revert anything or blame ag) and then crashed before returning any
explanatory text — so nobody, including ag, had reviewed the result. cc
audited the leftover code cold and found 2 real bugs before it was even
testable end-to-end (dead CLI wiring: `--lease-id`/`--pid` argparse args
were never added despite the dispatch code reading them; diag.py's
`_current_terminal_peer()` used `from core import hub` — a guaranteed
`ModuleNotFoundError` — and a cwd-relative `Path(".ai")` instead of
`PORTABLE_ROOT / ".ai"`, both errors silently swallowed by a bare
`except Exception: pass`, making the new fast-path 100% dead code). Both
fixed. The core resolver/lease logic itself (`resolve_terminal_identity`,
`action_terminal_handoff`, `action_terminal_heartbeat`, `action_terminal_close`)
was correct on first read — ag's own 15 unit tests for it all passed
unmodified against the real source.

**Cross-verification** (ag, same-peer re-dispatch — cx's EXH was red (X-pool
1.78x) at the time, ag's was green (G-pool 0.76x, 3P-pool 0.62x), so ag was
used again per the user's EXH-based routing instruction, explicitly told to
attack its own leftover code rather than re-approve it): found **4 more real
bugs**, all independently verified by cc via direct reproduction before
fixing, none fabricated:
1. **Timezone offset silently dropped** (the highest-severity finding):
   `_parse_human_interface_ts()`'s `_parse_compact_ts()` fast path matches
   the first 19 characters of a timestamp against a naive
   `"%Y-%m-%dT%H:%M:%S"` format BEFORE a real ISO-8601 parse ever runs,
   discarding any `+HH:MM` offset — confirmed live: `"...13:10:48+09:00"`
   parses as naive `13:10:48`, later stamped UTC by `resolve_terminal_identity`.
   Since `expires_at` is always written via `.isoformat()` on an
   `_ensure_aware()` datetime (i.e. carrying the real local offset, `+09:00`
   on this machine), this was not a rare edge case — it silently mis-evaluated
   the expiry of every single lease ever written on a non-UTC machine by
   exactly the local UTC offset. Fixed by parsing `expires_at` directly via
   `datetime.fromisoformat()` inside `resolve_terminal_identity()` instead of
   routing through the lossy shared helper (which is left untouched — fixing
   it would have wider, unreviewed blast radius across its other call sites,
   out of scope here).
2. **Falsy `close_reason` bypass**: `if assignment.get("close_reason"):`
   skips on `close_reason=""`. `action_terminal_close()` itself also
   overwrites `expires_at` to "now" in the same write, so this was mostly
   inert for that specific call path — but a lease closed via any other
   direct/external state mutation that set an empty `close_reason` without
   also updating `expires_at` would resolve as still-FRESH. Fixed: check key
   presence (`"close_reason" in assignment and ... is not None`), not
   truthiness.
3. **Disabled-peer orphaned-lease bypass**: `_normalize_runtime_files()`
   clears `state["human_interface_peer"]` to `None` for a disabled/retired
   peer but does not touch `human_interface_assignment` — the old mismatch
   check (`if legacy_peer and legacy_peer.lower() != ...`) short-circuited on
   a falsy `legacy_peer`, letting the orphaned lease resolve FRESH for a
   peer the canonical pointer no longer names. Fixed: a `None`/empty legacy
   pointer now disagrees with a present `lease_peer` too (matches the
   design's "`human_interface_peer` is canonical, full stop").
4. **Permanent mismatch loop in `action_terminal_duty_sweep()`**: compared
   the replacement pick against `term_info["peer"]` (the LEASE's peer) rather
   than the actual stale recorded pointer (`state["human_interface_peer"]`)
   — in a MISMATCH where the lease's peer happens to already be the eligible
   replacement, `next_peer != current_terminal` was trivially false, so the
   handoff that would have fixed the mismatch was skipped forever. Fixed to
   compare against the recorded pointer.

All 4 have real regression tests (`test_timezone_offset_not_silently_dropped`,
`test_falsy_close_reason_still_treated_as_closed`,
`test_cleared_legacy_pointer_with_orphaned_lease_is_not_fresh`,
`test_sweep_resolves_a_mismatch_even_when_lease_peer_is_the_eligible_pick`),
19 tests total in `test_terminal_identity_c5.py`. Full suite: 1438 passed,
4 pre-existing unrelated failures (identical to baseline), 1 skipped.

**Also flagged by ag's cross-verification, NOT fixed (pre-existing, broader
than C5, documented not silently ignored)**: `action_terminal_handoff`/
`_heartbeat`/`_close` lock `state.json` under the plain resource name
`"state"` (matching ~16 existing direct writers, per Top-5 #1's established
convention) — but `_commit_hub_mutation_request()` (the broker-commit path,
which also treats `state.json` as a whitelisted target) locks it under
`_mutation_lock_resource(target_path)`, a DIFFERENT name. This is a
pre-existing split between the two lock-naming conventions for `state.json`
specifically that predates both C5 and Top-5 #1 (every one of the ~16
existing direct "state" writers already had this exact gap against the
broker path, not something newly introduced here) — unifying them would be
a separate, wider-blast-radius refactor. Not exploitable today in practice
(no current caller submits `state.json` broker requests in production), but
worth tracking; not undertaken in this pass.

**Also NOT wired (explicitly deferred, not silently claimed done)**: nothing
currently calls `terminal-heartbeat` periodically. ag's cross-verification
investigated and confirmed this IS feasible — `claude_entry.py`/`agy_entry.py`/
`codex_entry.py` under `_sys/cli/` are the real interactive-session launchers
and stay alive (blocking on the child process) for the session's duration, so
a daemon thread periodically calling `action_terminal_heartbeat`/
`hub.py terminal-heartbeat` while the child is alive is architecturally
sound. Not implemented this pass: `claude_entry.py` is the live launcher for
the session doing this work right now, and modifying it carries real risk of
breaking the ability to launch Claude Code at all — left as a well-specified,
ready-to-implement follow-up rather than risked without separate explicit
sign-off. Until wired, a terminal assignment simply expires
`human_interface_peer_freshness_minutes` (default 30) after the last handoff
or manual heartbeat, same practical limitation as the pre-C5 code just via
the new fail-closed resolver instead of the old implicitly-fresh-on-missing-
timestamp path.

### C3 — FINAL DESIGN (unanimous, 2 rounds: cx draft → ag verification+reconciliation) — composes with C2, C5, absorbs §3.1 and §3.2

**Rejected**: the static Sonnet→Haiku model-slug failover chain entirely —
Haiku's 200k can never fit real Sonnet-class overflow, and the chain
returns a bare model slug where a routable node/profile is required
(confirmed real: a 950k-token probe against the live chain resolved to
`claude-haiku-4-5-20251001`, which is neither a node nor an alias, then
silently `reject`s).

**Adopted — split ContextGate (pure evaluator) from a new Hub-owned capacity planner**:
- `ContextGate.check()` returns an immutable `ContextDecision` (profile_id,
  estimated_tokens, context_limit, context_window_kind, warn/failover
  pct+threshold, utilization, `action: PASS|PRUNE_REQUIRED|FAILOVER_REQUIRED`)
  — it knows NOTHING about routing, alternatives, or model slugs anymore.
  `_FAILOVER_CHAIN`/`_load_failover_chain()` and the registry's `failover_to`
  field are deleted — model-registry facts shouldn't encode routing policy.
- The **hub** owns a capacity-aware planner that only runs on
  `FAILOVER_REQUIRED`: explicit user-picked profile → reject with a
  diagnostic (never silently reroute); otherwise build candidates from
  CANONICAL ROUTABLE PROFILE IDS ONLY (never a model slug/root id), apply
  every existing routing exclusion (disabled/non-routable,
  current+visited, manual-only, arbiter/bulk-excluded, health/pacing/quota/
  reserve gates, **plus C5's `resolve_terminal_identity()` to exclude the
  active human-interface terminal from being auto-selected as a background
  failover dump** — explicitly cross-checked and confirmed aligned with C5's
  actual mechanism, not just assumed compatible), resolve every candidate
  through C2's `ResolvedContextTarget` (unknown capacity excluded with an
  audited reason, never guessed), evaluate the SAME query against each
  candidate via `ContextGate`, prefer PASS, admit `PRUNE_REQUIRED` ONLY
  after real pruning re-validates as PASS, produce one immutable
  `ContextFailoverPlan` audit record, dispatch exactly once — no blind
  multi-hop chains (evaluate all candidates in one pass instead; hopping
  through invalid targets adds latency/cycle risk with no informational
  benefit).
- **Automatic failover targets always start `session_policy="fresh"`**
  (a nominally-large-window target might be resuming a nearly-full hidden
  vendor session, invalidating the fit proof). If the caller explicitly
  required `session_policy="reuse"`, **fail closed by default**
  (`CONTEXT_FAILOVER_REQUIRES_FRESH_SESSION`) with an explicit opt-in escape
  hatch (`allow_fresh_failover_on_session_reuse=True`) rather than silently
  breaking the caller's request. Explicitly notes a separate, NOT-solved-here
  adjacent gap: the SOURCE profile's own already-resumed hidden context
  still isn't accounted for — flagged as distinct future work, not silently
  claimed fixed.
- **Cross-peer capability equivalence gate, new in round 2 (ag), agreed**: a
  file-writing or high-tier task must never failover to a read-only or
  under-tiered candidate — capability equivalence (direct_file_write, PTY
  requirements, tier floor) is now a hard exclusion criterion alongside the
  existing ones.
- **§3.2 (prune-path-always-a-no-op) formally absorbed into C3**, not left
  as a separate item — because "PRUNE_REQUIRED admissible after real
  pruning" is hollow if pruning is fake. Root cause: the whole query is
  currently passed as ONE removable block, so pruning it returns `[]`, the
  caller's `if pruned:` check is then false, yet the code logs "prune
  applied" regardless. Fix: separate mandatory user content from droppable
  context blocks, never drop the mandatory block, re-estimate exact pruned
  bytes, require the result strictly below target (`<`, not `<=` — this
  also fixes the audit's cosmetic 75%-boundary note, but only bundled with
  the real fix, not as a standalone cosmetic patch, since fixing just the
  operator without the monolithic-block behavior would be misleading), fail
  closed if pruning can't achieve that.
- **§3.1 (swallowed rejection) dependency carried over from C2** — same
  atomic-landing requirement applies here too, since this design also
  depends on `FAILOVER_REQUIRED`/rejection actually reaching the caller
  instead of being silently caught and ignored.
- **Telemetry/error fixes (bugs 3+4)**: `utilization` becomes the sole
  canonical field (dataclass, not a loose dict, so `ratio` can't silently
  reappear — confirmed live: `hub.py:5435` currently reads a `ratio` key
  that `ContextGate.check()` never sets, `hub_context.py:147` only ever
  returns `utilization`, so every failover log line has always printed
  "0% full"). Failover telemetry logs BOTH source and target sides. Missing
  utilization renders as `absent`/fails validation, never defaults to 0.
  Error messages carry the ORIGINAL `ContextDecision` instead of
  recomputing thresholds (fixes the "60 exceeds 95" wrong-number-in-a-
  50%-configured-system bug) — uses "reached" not "exceeds" since the
  comparison is `>=`.
- **Registry-injection fix (bug 2)**: delete the split entirely rather than
  building a second instance-local failover chain — one instance-local
  immutable config snapshot per dispatch governs capacity, thresholds, AND
  profile-candidate selection together; no import-time registry state
  survives; the same gate instance evaluates source and every candidate.
  Neither peer found evidence the original capacity/failover split was an
  intentional caching decision — treated as a plain bug, not a tradeoff to
  preserve.

**Live-numbers sanity check** (cx, using DECLARED not freshly-probed
capacities — flagged as such): for a 950k-token query, `cc.effort`
(1,000,000) sits exactly at its 95% failover threshold; `ag.*` (1,048,576)
is below its ~996,147 failover threshold but above its ~838,860 warn
threshold, landing on `PRUNE_REQUIRED` not a clean `PASS`. Under the new
strict design, there is currently NO clean-PASS failover target for that
example — it only works via real prune-and-recheck, or the honest answer is
`NO_VALID_CONTEXT_FAILOVER_TARGET`. This is presented as the current real
state, not a flaw in the new design — the OLD design would have silently
"succeeded" by routing to Haiku's 200k, which can't actually hold the query
at all; the new design's honesty here is the point.

**Landing order (C2+C3 as one atomic series, both peers agreed)**: (1) C2's
resolver + strict config errors, (2) typed `ContextDecision`, (3) real
structured pruning + exact revalidation (absorbed §3.2), (4) the
capacity-aware hub planner, (5) replace `_snapshot_failover_choice()` for
context-overflow specifically — no fail-open model/root fallback, (6) fix
utilization/error/CLI rendering, (7) delete `_FAILOVER_CHAIN` + stale
`failover_to`, (8) replace the mock-only `test_hub_integration_v42.py`
assertion + repair stale traceability paths. Shipping only a subset first
was explicitly rejected by both peers as creating another inconsistent
intermediate state.

**Status**: design complete, unanimous, ready for TDD/implementation. Not
applied this session.

### C4 — FINAL DESIGN (unanimous, 3 rounds: ag draft → cx empirical critique → ag reconciliation)

cx caught 2 factual errors in ag's round-1 draft that would have shipped
actively-broken checks against real data — both confirmed and conceded:

- **CHK-CONST**: ag's round-1 rule ("RHS must be `ast.Call`") would have
  REJECTED all 5 real live constants, whose actual shape is
  `NAME = telemetry_config()["key"]["subkey"]` (an `ast.Subscript` chain,
  not a bare Call). Fixed rule: RHS must be a subscript chain whose
  innermost value is a zero-argument `telemetry_config()` call; rejects
  hardcoded values, comment-spoofing, duplicate/conditional reassignment,
  `AugAssign`.
- **Bug 7 (blueprint backlog check)**: ag's round-1 fix checked the wrong
  artifact — the blueprint DOC's own text, not the actual backlog item.
  cx found the real item lives in `_sys/ai/backlog.json`, id `T82`. Fixed:
  new `json_array_member`-style ledger check querying `backlog.json`'s
  `/items` for `id=="T82"`, kept alongside (not replacing) the existing
  SHELVED-banner check.

**Adopted design** (all 7 bugs):
1. **Staged-vs-worktree (biggest)**: `IndexView`/`WorktreeView` abstractions
   (not a boolean flag — a bare `git show :path` can't distinguish "staged
   deletion" from "git failure", loses mode/symlink/submodule info, and
   mishandles unmerged-index stage-0-absent cases). `IndexView` loads via
   `git ls-files --stage -z` (mode+OID+path), reads blobs by OID, rejects
   unmerged entries. Hook passes `--source=index`; audit CLI uses
   `--source=worktree`. CHK-01/02 must enumerate the STAGED INDEX, not
   `rglob()` the worktree (catches the reverse-direction case too: a staged
   deletion breaking a reference while an unstaged worktree copy masks it).
   Missing check scripts BLOCK, never silently skip. "<10ms" batching
   target flagged `TEST NEEDED`, not assumed.
2. **CHK-01/CHK-04 links**: one shared `extract_local_markdown_links()`
   parser (inline, angle-bracket, reference-style links; strips
   query/fragment) used by both checks, resolved against the staged view.
3. **CHK-02 INV-19 scope**: extended to `.py`/`.json`/`.sh` under
   `core`/`checks`/`ai`. New explicit exemption convention (none existed
   before — ag's round-1 vague "tagged" clause was unshippable as written):
   `# INV19-ALLOW: HUMAN_CONSOLE` on the exact string-bearing statement for
   Python/shell, `\uXXXX` escapes preferred for fixtures; untagged
   Hangul in comments/docstrings/internal prose still fails.
4. **CHK-03**: split failure modes — git/index infrastructure failure fails
   CLOSED (replaces the existing fail-open test,
   `test_git_error_returns_no_findings`); missing doc-coverage mapping stays
   `WARN`-severity per `governance.md:137`'s own documented intent (NOT
   promoted to blocking yet — the current heuristic doesn't actually enforce
   its table, just accepts any docs-v2 edit as satisfying co-change; wiring
   that straight to blocking would punish/reward unrelated edits). Wired
   into the hook in advisory/WARN mode; blocking promotion deferred until
   the real script→doc mapping becomes machine-readable config.
5. **CHK-CONST**: see factual correction above; also checks ALL matches
   (not just first), doesn't walk into functions/classes for same-named
   locals, additionally catches literal `globals()["NAME"] = ...` (full
   metaprogramming evasion explicitly out of scope — "a drift guard, not a
   security sandbox").
6. **CHK-LEDGER empty-substring**: `expected_substring` required
   non-empty for `text_contains` checks — confirmed migration-safe (all 4
   real live entries already have valid values, zero breakage). Schema
   errors return structured `Finding` objects, not uncaught tracebacks.
7. **CHK-LEDGER blueprint item**: see factual correction above.

**Status**: design complete, unanimous, ready for TDD/implementation. Not
applied this session.

### C6 — FINAL DESIGN (unanimous, 2 rounds: cx draft → ag verification+reconciliation)

**Confirmed live bug** (both peers independently verified against real
source): `_decide_consensus()` (`hub.py:~6398-6415`) does
`any(_peer_effective_health(v)[0]=="RED" for v in voters)` LIVE on every
vote check — a voter who cast `agree` while GREEN gets that vote silently
invalidated (round forced to `escalated`/`human_gate`) if it later goes RED,
even though nothing about the vote itself was ever invalid. A second,
related live-race was found in passing: `_decide_consensus()` also reloads
`collab_rate.current` live from `protocol.json` during finalization, so a
mid-round config change can alter the decision rule (unanimity vs majority)
mid-ballot — folded into the same fix.

**Adopted — freeze quorum eligibility at ROUND START** (not vote-time, not
live): `action_consensus_propose()` performs one health-observation pass at
proposal creation and persists a `quorum_snapshot` (captured_at,
`collab_rate`, `decision_rule`, per-voter observations, `required_voters` =
eligible gate-open voters, `excluded_voters` retained with explicit reasons
so an unavailable peer is never silently erased or miscounted).
`_decide_consensus()` then uses ONLY the snapshotted `required_voters` +
`collab_rate` + committed votes — never re-reads live health again for that
round. An `agree` cast by an eligible voter stays valid for the round no
matter what happens to that peer's health afterward. An UNCAST required
voter going RED does NOT force immediate escalation — `N` doesn't shrink,
the round just waits (or times out via the sweep, see below).

**STALE-eligibility doc/code conflict resolved in favor of the CODE**: both
peers independently confirmed `_healthy_peer(peer, allow_stale=True)` sets
`blocked_statuses={"RED"}` — i.e. `STALE`+gate-open peers ARE already
treated as eligible voters, and this is intentional (STALE represents a
peer quietly thinking/idle, not an operational failure; excluding it would
silently shrink quorum for perfectly healthy-but-quiet peers). The ONE
protocol.md/INV-28 sentence claiming STALE should be excluded is the stale
artifact — the doc gets corrected to match the already-correct, already-
tested code, not the other way around.

**Vote immutability, adopted** (cx's self-flagged main challenge point,
ag scrutinized and agreed): once a vote is committed to the round file, it
is final. Identical resubmission = idempotent no-op. A DIFFERING
resubmission = rejected with `VOTE_ALREADY_CAST`. Reasoning: mutable
revotes inside an active ballot introduce real non-deterministic
finalization races (e.g. peer A's `agree` triggers finalization the same
instant peer B tries to mutate its own earlier `agree`→`disagree`). If a
voter discovers a genuine problem after voting, the path is a NEW proposal
round or a C1 guard exception — not an in-place revote. Explicitly deferred
(not designed here): a future formal vote-withdraw/revote protocol.

**Timeout-sweep gap found and folded in**: `action_consensus_sweep(ai_root,
timeout_minutes=30)` (`hub.py:~6573`) already exists and is fully
implemented — but (same recurring "designed, never scheduled" pattern as
`terminal-duty-sweep`/`freshness-sweep`) nothing currently calls it
automatically. Fix bundles wiring it into standard maintenance loops
(alongside `_lease_sweep`/`action_ask` entry checks) so an uncast-voter
stall doesn't require manual intervention to ever resolve.

**C1 interaction** (both peers agree, orthogonal but sharing the
vote-commit boundary): a broker vote carrying `source_ask_id` stays pending
while its source ask is running, only enters `votes` after a clean
`GuardVerificationReceipt`, gets quarantined if the source ask goes
`guard_integrity_indeterminate`; `_decide_consensus()` only ever sees
committed/verified votes. Doesn't need to ship in the same commit as C1,
but should share one authoritative `apply_vote()` path plus an integration
test spanning both.

**Legacy rounds**: a round file with no `quorum_snapshot` field fails
CLOSED to `human_gate` rather than reconstructing eligibility from current
health — closed historical rounds are left untouched.

**Status**: design complete, unanimous, ready for TDD/implementation. Not
applied this session.

### C7 — FINAL DESIGN (unanimous, 3 rounds: ag draft → cx empirical critique → ag reconciliation)

cx caught 4 real corrections in ag's round-1 draft, backed by actual empirical
probes (not just review) and git-history verification:

- **`ctx_end.py` cannot be fixed via C7 at all** — it calls `claude -p`
  directly, never routes through `hub.py`, so `SOFT_SKIP_EXIT=7` can't reach
  it. Its `input()` hang is entirely C9's problem — removed from C7 scope,
  along with `ctx_save.py`'s return-code fix (same `ctx_*.py` file family,
  reassigned to C9).
- **The stale-lease-on-escalation bug exists in BOTH Pipe and PTY transports**
  (ag's round 1 only covered PTY) — same recursion-before-close ordering
  defect at both sites. ag's proposed new `_update_lease_status()` function
  doesn't exist; the real, already-lock-protected primitive is
  `_lease_close()` (`hub.py:~9016`) — reused instead of inventing a new one.
- **`read1(4096)` was empirically validated with a real timing probe**, not
  assumed: `read(4096)` had NOT returned 250ms after a child flushed one
  byte; `read1(4096)` had already returned it. Confirmed hub.py's Popen
  pipes are binary `_io.BufferedReader` on this Windows runtime, so
  `read1()` is the correct call (with `os.read(fileno, 4096)` as an explicit
  raw-stream fallback, never a silent fallback to blocking `read(n)`).
- **ag's lease-timestamp fix would have SHIFTED every existing lease time by
  the host's UTC offset (9h in KST)** — the biggest correction. Existing
  naive lease timestamps were written as LOCAL wall time (`datetime.now()`),
  not UTC; ag's round-1 design (treat naive-as-already-UTC) would have
  silently reinterpreted their meaning. Also found: `_lease_open()`/
  `_lease_renew()` truncate `.isoformat()` with `[:19]`, stripping any UTC
  offset that WAS present — a second, independent bug in the same area.

**Adopted final design (all 4 bugs)**:
1. **Soft-skip (`SOFT_SKIP_EXIT=7`)**: 5 real Pipe `sys.exit(0)` sites
   identified (not 3 as the original audit listed) converted to exit 7,
   split into two categories — `not_started` (health precheck/
   `SandboxSpawnDeniedError`, eligible for policy-approved auto-failover)
   vs `execution_uncertain` (child went transient AFTER spawning, NEVER
   auto-retried without replay-safety evidence, since it may have had real
   side effects). `action_ask_all()` stores per-peer exit code, prints
   `[SOFT-SKIP]`, exits 0 if ≥1 peer answered / 7 if all soft-skipped / hard
   nonzero if none answered and a real hard failure occurred.
   `_real_arbiter_invoker()` already handles nonzero-as-failure correctly
   (ag's round-1 "new fallback" claim was describing pre-existing behavior)
   — just tags code 7 as `arbiter_soft_skipped` for clearer telemetry, no
   behavior change needed.
2. **Escalation lease closure**: call `_lease_close(ai_root, to, pid,
   status="escalated")` immediately before EITHER PTY or Pipe recursive
   escalation call, `lease_closed` flag prevents the surrounding `finally`
   from double-closing, abort escalation if the close itself fails, same
   `ask_id` carried through to the escalated attempt (consistent with C1).
3. **Pipe drain**: binary Popen pipes kept as-is; `read1(4096)` (verified)
   for `BufferedReader` + `os.read()` raw fallback; `last_chunk_at` updated
   under lock on any nonempty chunk from either reader; reader-thread
   exceptions surfaced to the supervisor instead of swallowed; zombie
   decision uses `last_chunk_at`, not buffer-length growth.
4. **Lease timestamps**: remove the `[:19]` truncation in `_lease_open()`/
   `_lease_renew()`; legacy naive timestamps parsed as LOCAL wall time and
   converted TO UTC (never assumed already-UTC); missing/corrupt/unparseable
   timestamps marked `invalid_timestamp`/quarantined with a logged warning
   rather than guessed or silently retried; PID validated before any kill
   regardless of timestamp state.

**Confirmed no prior design existed for Bug 1**: cx traced git history —
commit `74f2c11` introduced `SOFT_SKIP_EXIT=7` for routers to distinguish
"unavailable" from "success" but never designed/implemented caller
consumption. The audit doc's "fully designed in §6" reference was
unsupported; this round is the actual first design.

**Status**: design complete, unanimous, ready for TDD/implementation. Not
applied this session.

### C8 — FINAL DESIGN (unanimous, 2 rounds: cx draft w/ live CLI verification → ag reconciliation) — security-relevant

**Real, currently-live security gap** (both peers independently confirmed
via actual `codex --help` calls, not just static reading): `codex
exec`/`review`/`resume` — and a 4th command the original audit MISSED,
`fork` — all bypass workspace-write/profile security defaults entirely.
`peer_console.py:~187-189` returns early for these before the code that
would append `-s workspace-write`/model-profile defaults runs, because
`_CODEX_COMMANDS` lumps agent-launching commands in with pure
administrative ones (`login`/`logout`). Real impact: `codex exec`/`review`
currently execute UNSANDBOXED with no default profile flags. Also found: a
real CLI grammar constraint via live testing — `codex review -s
workspace-write --help` exits 2 (syntax error), but `codex -s
workspace-write -m ... review --help` exits 0 — security flags MUST be
inserted at ROOT scope (before the subcommand), so the naive fix of just
appending defaults after removing these commands from the bypass list would
have produced invalid, silently-broken argv. Also found: `delete` is a real
live Codex subcommand missing from `_CODEX_COMMANDS` entirely, so it
currently incorrectly gets sandbox/model defaults AND a banner applied to
what should be a plain admin operation.

**`apply_security_semantics()` naive wiring would have been an unsafe
BEHAVIOR CHANGE, not just plumbing** — concretely compared against the
hardcoded branches it should replace: for `cc`, an explicit
`--permission-mode default` currently correctly suppresses the hardcoded
skip-permissions default, but the declarative helper would add
`--dangerously-skip-permissions` regardless (silently overriding the user's
explicit safer choice); same class of bug for `ag`'s `--sandbox` override;
for `cx`, the declarative helper wrongly treats `--ask-for-approval` as
satisfying the sandbox requirement, when approval and sandbox are actually
independent axes in the real CLI. `forbidden_effective_args` is currently
only checked by static EMPTY-argv parity tests — real production console
argv is never actually validated against it at all.

**Adopted — invocation classification + root-scope insertion + unified
`prepare_console_launch()` API**:
```python
class InvocationKind(Enum):
    HELP_OR_VERSION = "help_or_version"
    LOCAL_AGENT = "local_agent"        # exec/e, review, resume, fork, nested exec review/resume, interactive root
    REMOTE_AGENT = "remote_agent"      # cloud, cloud exec -- local sandbox flags don't govern remote workers
    ADMIN_OR_SERVICE = "admin_or_service"  # login/logout, mcp, app-server, delete, doctor, completion, etc.

@dataclass(frozen=True)
class ConsoleLaunch:
    peer_id: str
    invocation_kind: InvocationKind
    final_argv: list[str]
    effective_model: str | None
    effective_profile: str  # e.g. "cx.effort" or "cx.custom" if the explicit model doesn't match a configured profile
    banner_message: str | None  # None for HELP_OR_VERSION/ADMIN_OR_SERVICE
```
- **Only `LOCAL_AGENT` gets security/profile defaults + a banner**;
  `REMOTE_AGENT` (cloud) still gets model defaults + forbidden-arg contract
  checks but NOT local sandbox flags (they don't apply to a remote worker),
  with its own distinct banner. An unrecognized subcommand is surfaced by a
  CLI-canary drift-detection test, never silently bucketed either way.
- **Root-scope insertion**: for `LOCAL_AGENT`, scan the FULL argv for
  existing flags (`-s`/`--sandbox`/`-m`/`--model`, in any position) before
  injecting; missing defaults are inserted BEFORE the subcommand token
  (`["-s","workspace-write","--model","...","review","--uncommitted"]`, not
  appended after); never reorders user-supplied options; invalid user
  syntax stays a visible CLI error, never silently "fixed."
- **`_append_missing()` replaced**: matches ONLY exact option tokens (never
  treats a bare positional value like `"workspace-write"` as evidence the
  flag was already present), adds `(flag,value)` as one atomic group,
  explicitly rejects a dangling value-taking flag rather than ambiguously
  patching it.
- **Privilege policy, adopted**: workspace-write/read-only satisfy policy;
  `-s danger-full-access` and `--dangerously-bypass-approvals-and-sandbox`
  are REJECTED by default in production, overridable only via an explicit
  administrator-set break-glass environment variable
  (`ALLOW_BREAK_GLASS_DANGER_ACCESS=1`) — not a silent user-argv pass-through.
- **Corrected security-semantics flow**: load peer's `security_contract` →
  classify invocation → reject `forbidden_effective_args` for LOCAL_AGENT →
  translate `sandbox_semantics` through the peer's actual CLI grammar →
  preserve an explicit EQUAL-OR-SAFER user override (never silently
  downgrade OR upgrade past user intent) → add profile defaults → validate
  final effective argv against the contract before launch. Once this common
  translator is correct, the duplicated hardcoded per-peer branches get
  deleted (a clearly isolated compatibility fallback may remain for
  disabled/unregistered `gc`, must not govern active peers).
- **Banner fix**: `effective_model` comes from the ACTUAL computed argv
  (`--model value`/`--model=value`/`-m value`), not a re-read of default
  config; if it doesn't match a configured profile, reports e.g.
  `cx.custom` instead of the stale default `cx.effort`. All entry points
  using the banner (`codex_entry.py`, `claude_entry.py`, `agy_entry.py`)
  migrate to `prepare_console_launch()`, not just the one caller the audit
  originally found.

**Landing strategy, approved**: two atomic pieces — C8-A security hotfix
(classifier + root-scope insertion + fixed `_append_missing` + forbidden-arg
enforcement + real nonempty-argv tests — resolves the P0 security bugs,
independently releasable) then C8-B consolidation (`ConsoleLaunch` API +
truthful banners + hardcoded-branch removal across all entry points). C8-A
safe to land alone if C8-B review surfaces cross-peer regressions.

**Test-gap fix, both peers agreed**: the existing parity test only exercises
`peer_default_args(peer_id, [])` — empty argv — which is exactly why the
subcommand-bypass and positional-flag-collision bugs stayed green. New test
matrix covers all `LOCAL_AGENT` command forms (including nested `exec
review`/`exec resume`), `delete` and other admin commands staying
unchanged/bannerless, dangling-flag/positional-collision cases, explicit
`--model` reaching the launch descriptor, forbidden-flag rejection, and
missing/corrupt security-contract fail-closed — plus real CLI-parser
canaries (`codex ... --help` for each LOCAL_AGENT form, asserting exit 0
with no "unexpected argument" error) and a live-root-help drift check that
fails when a new real subcommand isn't classified.

**Status**: design complete, unanimous, ready for TDD/implementation. Not
applied this session.

### C8 status line update: `[DONE, unanimous R2, security-relevant]`
### C9 status line update: `[DONE, unanimous R3]`

### C9 — FINAL DESIGN (unanimous, 3 rounds: ag draft → cx full-file critique → ag reconciliation) — user-facing, elevated priority

cx read both scripts end-to-end (confirmed live files via SHA-256 match)
and found ag's round-1 design incomplete on 2 core points plus surfaced
several genuinely NEW bugs beyond the original 2-item scope:

- **TTY-detection doesn't actually solve the hang.** `isatty()` only proves
  a prompt COULD render — it doesn't mean the user will ever press Enter;
  an attended-but-idle real terminal session can still hang indefinitely.
  `except (EOFError, KeyboardInterrupt)` doesn't help either (neither fires
  just because the user doesn't type anything). **Adopted: remove the
  blocking `input()` entirely, in ALL cases** — print a prominent error to
  stderr, run all independent cleanup, exit nonzero at the end. A
  "pause so a double-clicked console window doesn't vanish" behavior, if
  ever needed, becomes an explicit opt-in `--pause-on-error` flag evaluated
  AFTER cleanup completes (confirmed `ctx-end.bat` currently has no
  existing pause behavior to preserve — not a regression).
- **Unconditional `.bak` rejected** — nothing anywhere consumes
  `summary_session.md.bak`/`summary_save_error.log`; it would just be an
  unmanaged, never-cleaned-up duplicate artifact. **Adopted: same-directory
  atomic replacement** — require `returncode==0` AND nonempty stripped
  stdout, write to a uniquely-named temp file in the same directory with
  explicit `encoding="utf-8"`, flush+fsync, `os.replace()` the target. On
  any failure, remove the temp file and leave the original completely
  untouched. No `.bak` needed.
- **NEW bugs found while reading the real control flow** (not in the
  original audit's 2-item scope): cleanup is NOT currently guaranteed to
  run — a primary Claude failure exits before most cleanup steps; an
  `ai_check.py` failure archives Gemini then returns EARLY, skipping memory
  compaction/watchdog/self-care entirely; missing Claude binary/credentials
  exits before even raw logging; the optional `--global` Claude call
  currently ignores its return code entirely; `ctx_end.py`'s OPTIONAL
  Gemini-summary path shares the EXACT SAME return-code defect as
  `ctx_save.py`'s original Bug 2. **Adopted: full phase-based flow with no
  early-return cleanup-skipping** — Phase 1 environment checks (15s
  timeout, record don't exit), Phase 2 primary+global summaries (60s bounded
  timeouts), Phase 3 raw CLAUDE.md snapshot preserved regardless of LLM
  outcome, Phase 4 optional Gemini summary via the same atomic-replacement
  mechanism, Phase 5 every independent cleanup step run best-effort in its
  own try/except aggregating failures (not early-returning), Phase 6 exactly
  ONE exit at the end — nonzero if any REQUIRED phase (primary/global
  summary, critical cleanup) failed, zero-with-warnings if only the
  explicitly-optional Gemini enrichment was unavailable. `ctx_save.py`
  mirrors this — continues its consensus sweep even after summary failure,
  reports "checkpoint markers succeeded but blackboard regeneration failed"
  rather than stopping early.
- **NEW: timeout gap** — `ctx_save.py` already has a 60s timeout on its Hub
  summary call but catches the resulting exception GENERICALLY and still
  exits 0 anyway (defeats the timeout's purpose); `ctx_end.py`'s primary AND
  `--global` `claude -p` calls have NO timeout at all (can hang before ever
  reaching the input() bug); both scripts' `ai_check.py` calls also lack
  timeouts. Adopted: every subprocess call gets an explicit timeout (60s for
  LLM summaries, 15s for diagnostic scripts), `subprocess.TimeoutExpired`
  caught explicitly and handled identically to a nonzero exit — never
  swallowed.
- **Encoding fix rescoped** — every relevant `read_text()`/`write_text()`
  already specifies UTF-8 (adding it again would be a no-op). The REAL gap:
  `subprocess.run(..., capture_output=True, text=True)` without an explicit
  `encoding=` — `PYTHONUTF8=1` on the child doesn't control how the
  already-running PARENT decodes captured bytes; locale decoding (cp949 on
  Windows) can corrupt Korean text before it's re-saved as UTF-8. Confirmed
  NOT redundant with CHK-ENC (staged/governed repo files only) or
  `terminal_file_write_min_tier` (AI terminal edits only) — these are
  standalone runtime hooks generating `.ai`/archive artifacts outside both
  paths. Fix: explicit `encoding="utf-8", errors="strict"` for authoritative
  summary stdout (decode failure preserves the old summary + reports an
  error, never silently corrupts), `errors="replace"` acceptable only for
  non-authoritative diagnostic stderr.

**Status**: design complete, unanimous, ready for TDD/implementation. Not
applied this session. **This closes out all 9 Tier-1 clusters (C1-C9) for
this session.**

### C10 - SINGLE-PASS RESULT (cx, reduced rigor per Tier-2 budget, no round 2/3)

Correction to this doc's own C10 prompt: cx found diag.py (around line 778)
is ALSO hardcoded to "cx" for credit display - the earlier claim ("diag.py's
credit display IS already data-driven via _has_credit_concept") was
wrong/stale. All 3 sites (hub.py ~7334, snapshot.py ~832, diag.py ~778)
need the same fix.

1. Credit capability (S1.2): add an explicit root-peer capability field
   (e.g. quota_capabilities.reset_credits) with ONE shared helper consumed
   by hub/snapshot/diag together - not 3 separate string-compares. Don't
   infer capability from transient telemetry presence (missing telemetry
   and "doesn't support this" are different states).
2. Session/send admission (S1.5): reuse existing resolve_node_id()/
   is_routable() authority. action_init_session() validates+canonicalizes
   the agent BEFORE _lease_sweep()/any state mutation; action_send()
   validates sender+recipient+every CC before payload offload/mailbox
   writes. Profile/alias identities normalize to root peer; any non-peer
   service principal must be explicitly registered, never accepted as an
   arbitrary string.
3. Adapter-owned prompt staging (S2.1): new prepare_input(node, query,
   invocation, *, ask_id, ai_root, cwd, transport_limits) ->
   PreparedInvocation (immutable: argv, stdin payload, staged artifacts,
   cleanup metadata). Core calls it, cleans returned artifacts in finally;
   AgyAdapter alone decides whether to use the pointer-file form currently
   embedded directly in hub.py (~5853). Key risks flagged: staged-path
   containment, preserving the full UTF-8 payload/digest, keeping the
   artifact alive until the full child process tree exits.
4. peer_mgr._save() concurrency (S6.1): unique same-directory temp
   file + flush/fsync + os.replace() - but cx notes unique temp files
   ALONE don't prevent lost updates; an operation-level registry lock must
   cover the whole load-mutate-validate-save sequence, plus a deterministic
   recovery rule for abandoned Windows temp files.
5. Multi-file peer-manager transactions (S6.2): reuse C1's eventual
   _mutation_lock_resource()/expected_revision primitives (NOT its
   ask-specific scratch machinery - different context). One aggregate
   peer-registry lock, snapshot revisions for all affected files, stage+
   cross-validate the full new set, commit with a durable transaction
   journal + recovery/rollback record. cx's reasoning: multi-file replace
   can't be truly atomic at the filesystem level regardless, so the journal
   and recovery path is mandatory, not optional; per-file locks alone would
   still expose mixed state and add deadlock risk.
6. Extra-download extraction (S6.3): confirmed checksum verification
   DOES already precede _extract() (partial mitigation already exists),
   but the archive downloads directly to its final setup filename. Fix:
   download to a unique .part, close/fsync, validate expected length
   (where available) plus the mandatory declared digest, atomically promote
   to a verified artifact, only THEN extract into a staging dir; preserve
   cleanup on interruption; also flagged archive path-traversal validation
   as worth enforcing at this same boundary.
7. Quota timestamps (S6.4): reuse C7's PARSING foundation but explicitly
   NOT its lease-specific naive-means-local POLICY - cx's key distinction:
   legacy lease timestamps are KNOWN local wall time (that's why C7 could
   safely assume local), but a vendor's timezone-less quota-reset timestamp
   has no defensible implied zone at all. Quota parsing should use
   reject_naive and return None with diagnostic provenance UNLESS that
   specific provider has declared an explicit timezone contract - guessing
   either local or UTC here could shift reset math by hours with no way to
   know which is right.
8. context-ack (S7.1): DELETE it rather than fixing the lockless
   write - confirmed zero consumers, no defined blocking invariant.
   Remove/deprecate the CLI action, protocol/guard classifications,
   snapshots, docs, and tests TOGETHER (not just the write call); a
   deprecation-warning release cycle is optional if compatibility is
   needed, but must never write the dead file even during deprecation.
   Since this changes a public action_* API, DIR-003 requires updating
   contract tests in the same commit.
9. Quota defensive validation (S9.5): move reset_in_seconds conversion
   INSIDE the existing validation try/except; reject booleans/non-numeric/
   NaN/infinity values with None (finite negatives keep existing
   "already expired to 0" behavior). calculate_pacing() should validate
   all 3 inputs and return status="unknown", ratio=None plus a
   machine-readable invalid-input reason instead of classifying NaN as
   "safe" - renderers/tests currently assuming "unknown always means
   ratio=0.0" need to change in the same commit.
10. Test blind spots (S5.9): acknowledged, no standalone design -
    each owning cluster (several already converged this session) should
    replace "was called"/"didn't raise" assertions with real
    observable-effect tests when eventually implemented.
11. Traceability hygiene (S8C.8): confirmed both traceability_map.json:326
    references are genuinely absent; real doc lives under
    general/lifecycle.md, test reference should point at whichever real
    C2/C3 ContextGate test module gets created during implementation.

**Status**: single-pass design sketches complete (reduced rigor, no
round 2/3 per Tier-2 budget). Not applied this session.

---

## SESSION SUMMARY (2026-07-24 backlog design-consensus pass)

All 9 Tier-1 clusters (C1-C9) reached full 3-round-or-fewer mutual-critical
UNANIMOUS consensus; Tier-2 (C10) got an appropriately lighter
single-pass review. Combined with the earlier same-day Top-5 fix
implementation session (see project_architecture_audit_fix_implementation_2026_07_24
memory), essentially the ENTIRE 47+2-item backlog from
architecture-audit-2026-07-24.md now has either an applied fix or a
converged, ready-for-TDD design - the only items with NO forward motion
today are the small Tier-4 confirmed-non-bugs and the informational-only
test-blind-spot list (S5.9, folded into whichever cluster owns the
underlying bug).

**Process notes worth preserving**:
- Real disagreement surfaced in a genuine majority of rounds (C1, C2, C4,
  C7, C9 all needed a real round 3 because round 2's critique found
  substantive, not cosmetic, problems) - this was NOT rubber-stamping.
  Several of these corrections were things that would have shipped
  actively-broken code against real data if round 1 had been trusted alone
  (C2's ast.Call-vs-Subscript AST rule, C4's same AST mistake plus the
  wrong-artifact blueprint check, C7's UTC-offset-shifting timestamp bug,
  C9's ineffective TTY-detection fix).
- --to auto load-balanced routing was unavailable for this entire session
  (terminal_identity_absent) - a live, in-session demonstration of
  exactly the C5 bug being designed around. All dispatches used explicit
  --to cx / --to ag instead.
- Several rounds caught peers investigating from a stale scratch/mirror
  copy rather than live P:\ source (visible in their own search logs);
  explicit SHA-256 P:\ vs D:\PortableDev(v2.0)\ hash-comparison verification
  was added to prompts after the first occurrence and peers reliably
  self-corrected when asked.
- Several "designed but never wired" stubs were found ACROSS clusters, not
  just the one C5 started from: _fresh_active_coordinator() (C5),
  apply_security_semantics() (C8), context-ack (C10), the pre-fix
  arbiter override - same recurring pattern this whole session, now with 5+
  confirmed instances.

---

## Cross-cutting structural analysis (2026-07-24, cc's own synthesis)

User asked, after all 9 Tier-1 + Tier-2 designs converged: is there anything
that needs an actual STRUCTURAL change (not a local patch) across this
backlog? cc's direct answer (no peer round needed for this part - pure
synthesis of already-gathered context):

### S1. Implementation ordering is not flat - C1 is the foundation, not a peer of the others

C1's adopted mechanism (peer writes to scratch -> host does a short CAS
commit -> immutable receipt) is the only genuinely STRUCTURAL change in the
whole backlog - it changes the core peer-execution contract itself (every
governed peer write moves from "direct live-repo write, checked after the
fact" to "staged proposal, host-mediated commit"). Every other cluster's
design either directly depends on C1's primitives or interacts with its
commit path:
- Top-5 #1 (broker transaction safety, already designed pre-session) should
  be implemented USING C1's `_mutation_lock_resource()`/`expected_revision`
  primitives, not the other way around (C1's own design doc says this).
- C6 (consensus voter-health snapshot) shares the vote-commit boundary with
  C1 - a broker vote's `source_ask_id` must gate on C1's
  `GuardVerificationReceipt` before `_decide_consensus()` can see it.
- C3 (ContextGate failover planner) dispatches a NEW ask to a different
  profile on failover - that new ask needs its own C1 scratch/lease
  lifecycle, not a carried-over one from the original ask.
- C10 item 5 (peer_mgr.py multi-file transactions) was explicitly designed
  to reuse C1's `_mutation_lock_resource()`/`expected_revision` (not its
  ask-specific scratch machinery).

**Recommendation**: implement C1 FIRST, before starting TDD on Top-5 #1,
C3, C6, or C10-item-5's peer_mgr.py fix. Building those in parallel first
risks having to retrofit them once C1 lands. C2, C4, C5, C7, C8, C9 are
comparatively independent of C1 and each other and can proceed in any order
(or in parallel) without this ordering constraint.

### S2/S3. Sent to peers for a real infinite-round discovery pass (see below)

Two candidate structural improvements identified but requiring real design
work, not just synthesis - dispatched to ag/cx for genuine
mutual-critical/unanimous exploration (not yet converged, see the "Cluster
S" section once rounds complete):

- **S2 - capability-wiring verification**: this session found 5+ separate
  instances of the exact same bug class ("a function/hook was designed and
  has its own tests, but has zero real production callers") -
  `_fresh_active_coordinator()` (C5), `apply_security_semantics()` (C8),
  `context-ack` (C10), the pre-fix arbiter override, `action_consensus_sweep()`
  (C6, exists+fully implemented but nothing calls it automatically). Fixing
  each instance individually (which is what happened) doesn't prevent the
  NEXT one. Question for peers: is a lightweight structural check (e.g. a
  new `_sys/checks/` pre-commit check, or extending an existing one) that
  detects "a new/changed function matching some capability-marker convention
  has zero callers outside its own tests" actually buildable and worth
  building, and if so what should the marker/detection convention be?
- **S3 - console entry-point unification**: C5 (terminal-session lease,
  needs interactive console wrappers to send periodic heartbeats while
  alive) and C8 (peer_console security, needs a `prepare_console_launch()`
  classifier) BOTH require retrofitting the exact same 3 files
  (`codex_entry.py`, `claude_entry.py`, `agy_entry.py`). Question for
  peers: should these be co-designed as one shared "console wrapper
  contract" (one integration point per entry file, not two separate
  migrations of the same surface), and if so what does that shared contract
  look like? **RESOLVED, see S3 final design below — unified adoption,
  separate mechanisms.**

## Cluster S results (structural discovery pass)

### S3 - FINAL DESIGN (unanimous, 2 rounds: cx draft -> ag verification+reconciliation)

Unify the ENTRY-POINT ADOPTION (one integration call per file) without
merging the two underlying mechanisms. C8's prepare_console_launch() stays
a pure, one-shot, stateless security function. A new shared runner,
run_console_session(spec, user_argv) -> ConsoleResult, is the ONE function
all 3 entry points call - internally it invokes prepare_console_launch(),
then composes C5's stateful lease supervision (claim/heartbeat/release)
around the actual launched process.

Strict one-way dependency, verified by both peers: argv+config -> C8
security prep -> immutable ConsoleLaunch -> C5 lifecycle participation ->
spawn/wait. C8 never reads lease state; C5 never touches final_argv, model
selection, or sandbox strength. This specifically prevents the dangerous
failure mode where "lease unavailable" could silently degrade into
"launch using raw/unvalidated argv."

owner_pid = os.getpid() (the WRAPPER's PID, not the child's) is the
liveness anchor - ag independently verified via real code inspection that
all 3 entry points use synchronous subprocess.run() and wait for child
completion without exec/replacing themselves, confirming this is reliable
(if the wrapper dies/detaches it's genuinely no longer the human's attached
console even if a descendant survives).

Terminal-duty claiming uses an EXHAUSTIVE mapping with no default (fails
loudly on an unmapped future InvocationKind, preventing silent fallthrough):
LOCAL_AGENT claims+renews; REMOTE_AGENT (cloud/cloud exec) ALSO claims+
renews while the foreground wrapper stays attached (reconciled in round 2 -
reasoning: the user's wrapper process remains active and attached while
observing cloud output, so another peer shouldn't be able to hijack
terminal identity during that window even though the actual work runs
remotely); HELP_OR_VERSION and ADMIN_OR_SERVICE get no lease at all.

Lease-failure semantics, reconciled: initial claim failure on a LOCAL_AGENT/
REMOTE_AGENT invocation ABORTS by default (concurrent leader actions +
status-file corruption risk if two terminals both think they hold duty),
with an explicit break-glass ALLOW_UNLEASED_CONSOLE=1 env var for a
degraded launch (never affects C8 security validation - break-glass only
bypasses the lease requirement). ADMIN_OR_SERVICE/HELP_OR_VERSION commands
need no lease and run with zero friction. Transient heartbeat failure after
launch retries with bounded timeouts; if renewal can't complete before
expiry, reports terminal-priority-lost but does NOT kill the user's
already-running vendor process. CAS rejection (superseded by a newer
console) = expected, stop renewing, old console may keep running but isn't
canonical anymore. Wrapper crash = no special cleanup, natural lease expiry
is the only recovery path.

3-commit landing sequence (explicitly prevents ever shipping an unwired
prepare_console_launch() or a lease client with zero production callers -
directly serves S2's whole theme): (1) C8-A security hotfix alone, (2) C5's
hub-side lease schema + CAS claim/heartbeat/release + resolver + tests
alone, (3) ONE console-side adoption commit - shared runner + lease client +
migration of all 3 entry files + removal of old direct-spawn paths + a NEW
structural test prohibiting these 3 modules from calling subprocess.run/
Popen directly at all (forces any future 4th console entry point through
the shared contract too).

**Status**: design complete, unanimous, ready for TDD/implementation. Not
applied this session.

### S2 - FINAL DESIGN (unanimous, 3 rounds: ag draft -> cx real dry-run critique -> ag reconciliation)

cx ran an ACTUAL dry-run AST inventory against the live tree plus real
timing measurements, and found ag's round-1 design would not have survived
contact with the real codebase:

- Found 17 zero-reference candidates: 11 likely genuinely dead, 2 confirmed
  ANALYZER FALSE POSITIVES (functions only reachable via ImportFrom edges a
  naive ast.Name/ast.Call-only scanner would miss), 4 ambiguous API-boundary
  cases needing human compatibility judgment, not an automatic verdict.
- Found a REAL indirect-dispatch mechanism ag's design would have broken
  on: dispatcher.py does genuine config-driven getattr(module, method_name)
  dispatch from _sys/dispatch.json -- those pairs must be treated as
  call-graph roots, or the checker false-positives on real wired code.
  Conversely, hub.py's _extract_hub_signatures() does broad REFLECTIVE
  inspection across every action_* function that must NOT count as a real
  caller (would create false NEGATIVES, silencing the checker on
  everything).
- ag's action_* exemption was backwards: real hub dispatch is ordinary
  direct calls in an elif chain, so a correctly-wired handler already has a
  normal, visible AST edge needing no exemption; exempting anything merely
  LISTED in argparse choices would hide exactly the bug the checker exists
  to catch. Name-conversion between hyphenated actions and function names
  is also unreliable in practice (verified real mismatches). Fixed by
  splitting into a SEPARATE parity checker instead of folding exemption
  logic into the reference checker.
- The 10.6% (5/47) base-rate justification was invalid as stated: only 2 of
  the 5 original headline examples are actually zero-caller-function
  defects detectable by this class of checker at all (context-ack is
  really a "nobody reads the file this writes" defect; the pre-fix arbiter
  bug was "called but result didn't update state"; action_consensus_sweep
  already has a real caller today, its problem is nothing schedules it
  automatically) -- 3 of 5 are genuinely different bug shapes this checker
  was never going to catch. The dry-run's own 11 additional real findings
  independently justify building something narrower, just not for the
  reason originally given.
- <50ms was unsupported (measured ~500-800ms full-tree); INV19-ALLOW tag
  reuse would have collided with C4's already-adopted HUMAN_CONSOLE tag in
  the same namespace.

**Adopted final design** - two separate checkers, two modes:
1. `check_unreferenced_functions.py` -- Mode 1 (pre-commit gate,
   STAGED-ONLY, <100ms target): only inspects newly-added/materially-changed
   top-level functions via C4's staged-index helper; correctly resolves
   ImportFrom/attribute-access/registry-stored-function/exact-getattr/
   dispatch.json-declared roots; fails on zero non-test production edge +
   no `WIRING-EXEMPT` tag. Mode 2 (CI/on-demand, full-tree, ADVISORY only,
   never hard-fails legacy findings): reports all candidates for periodic
   human cleanup review.
2. `check_cli_dispatch_parity.py` -- separate, dedicated: every argparse
   `choices` entry has a real dispatch branch, every dispatch branch
   references a declared choice.
3. New exemption tag family (distinct from INV-19's namespace):
   `# WIRING-EXEMPT: EXPORTED_API|DYNAMIC_ENTRYPOINT|BACKCOMPAT_API
   reason="..."` (reason mandatory).
4. The 11 already-found legacy dead functions (including this session's
   own `_fresh_active_coordinator`/`apply_security_semantics` discoveries)
   get grandfathered into a `unreferenced_functions_baseline.json` so day-1
   enforcement doesn't immediately fail on pre-existing debt -- a follow-up
   cleanup task reviews and removes baseline entries over time, new
   additions get real enforcement from day one.
5. Explicit scope limit, both peers agreed: this checker does NOT detect
   write-only artifacts, ignored return values, or missing schedulers
   (context-ack's and action_consensus_sweep's actual bug shapes) -- those
   need separate producer/consumer contract checks if that pattern recurs
   often enough later to justify the extra complexity. Don't oversell what
   one checker covers.

**Status**: design complete, unanimous, ready for TDD/implementation. Not
applied this session. This completes the structural discovery pass
(S1 cc-synthesized, S2 and S3 both reached unanimous peer consensus).

## Cluster T results (post-hoc gap-check + simplification review)

### T2 - SIMPLIFICATION REVIEW FINAL (unanimous, 2 rounds: cx draft -> ag verification+reconciliation)

User asked whether any of the 12 converged designs (C1-C10, S2, S3 - S1
confirmed to be an ordering/dependency map, not a 13th runtime mechanism)
could be simplified without losing real value. Verdict: 3 substantive
trims, 5 local trims, 4 already near-minimal. Reconciled deltas:

- **C1**: 5 record types -> 3. Merge AskGuardLease+GuardVerificationReceipt
  into one AskGuardRecord (starts "running", makes ONE terminal immutable
  CAS transition to clean/indeterminate/failed - verified feasible under
  file locking: atomic JSON write under `_get_lock(ai_root, "ask_guards")`,
  once non-running, further mutations for that ask_id are rejected). Merge
  StagedMutationProposal+MutationIntent into one MutationRequest (peer
  writes the untrusted-proposal portion in scratch; host copies into
  host-owned storage + adds authorization state after clean verification -
  a peer-written status="authorized" must NEVER be trusted). MutationReceipt
  stays separate (needed by concurrent asks to explain legitimate live-tree
  transitions). Net: -2 schema files, same CAS/attribution guarantees.
- **C3**: keep the evaluator/planner separation of CONCERNS, but the
  "planner" becomes ONE pure function `plan_context_failover(source_decision,
  candidates, policy_snapshot) -> ContextFailoverPlan` instead of a stateful
  service/object. ContextFailoverPlan stays a lean ephemeral frozen result
  (selected profile+decision, rejected candidates with reason codes,
  fresh-session requirement) - not a persisted domain object unless audit
  logging actually serializes it. Rejected: returning just a bare chosen
  profile - loses honest NO_VALID_CONTEXT_FAILOVER_TARGET explanations,
  exclusion evidence, and the guarantee that telemetry+dispatch see the
  same evaluated snapshot (silent/misleading failover was the ORIGINAL bug
  class C3 exists to fix - too much to give up).
- **C5**: schema trims but owner_pid is RETAINED (verified load-bearing -
  used for process-liveness checks during lease renewal via
  psutil.pid_exists and during CAS takeover); assigned_at/last_heartbeat_at
  drop to audit-only/removed since nothing consumes them at runtime;
  is_active_terminal dropped from the resolver's return (redundant -
  status=="FRESH" already implies it). Final schema:
  {peer, profile, lease_id, owner_pid, expires_at}. The "just a scheduled
  sweep + shorter window, no lease at all" ultra-simple alternative was
  explicitly considered and rejected (confirmed, not just asserted): a
  sweep can't distinguish alive-but-quiet from dead; blindly refreshing the
  timestamp would perpetuate a crashed terminal forever; a timestamp keyed
  only by peer has a real ABA problem (an old wrapper could resume
  heartbeating after terminal duty moved away and later returned to the
  same peer) - heartbeat+lease_id+CAS is confirmed the minimum correct
  mechanism, not gold-plating.
- **C6**: required_voters alone is insufficient (C6 also fixes the live
  collab_rate/decision-rule race, and DIR-006 requires unavailable voters
  explicitly logged) - but the 5-field per-INCLUDED-voter observation
  detail drops to just `excluded_voters: {peer: reason}` (+ decision_rule +
  captured_at), no per-included-voter detail retained unless a concrete
  provenance need arises later.
- **S2**: the baseline-grandfather JSON file is DROPPED (unnecessary under
  the already-adopted staged-only rule - untouched legacy functions never
  enter the gate at all, only materially-changed ones get checked; a
  permanent baseline file would become permanent suppression debt instead
  of forcing real cleanup of the 11 already-found candidates - those get a
  one-time manual review: delete, wire, or explicitly tag). The 2 separate
  checker scripts merge into ONE `check_wiring.py` executable reporting 2
  logically-distinct, independently-tested rule sets
  (`[UNREFERENCED_FUNCTION]`, `[CLI_DISPATCH_PARITY]`) sharing one AST/
  import/dispatch inventory pass (~50% less pre-commit AST-parsing overhead
  than 2 separate full passes). Net: 4 artifacts (2 checkers + tag family +
  baseline file) down to 2 (1 checker + tag convention).
- **C2, C4, C7, C9 confirmed already near-minimal** - no cuts recommended.
  Specific justifications given: C2's `context_window_kind`/provenance
  fields are real admission distinctions, removing them recreates the
  original 200k-guessing bug; C4's separate IndexView/WorktreeView types
  are justified by staged-deletion/mode/symlink/unmerged-entry handling;
  C7's soft-skip categories and last_chunk_at are necessary, only real trim
  is sharing ONE timestamp parser between C7 and C10 (parameterized by
  explicit naive-policy: LOCAL for known-legacy leases, REJECT for
  vendor quota timestamps - matches C10's own earlier design note); C9's
  6-phase flow should stay straight-line control flow with a small failure
  accumulator, not become a workflow framework, but CAN share one atomic-
  summary-writer + bounded-subprocess helper between ctx_end.py/ctx_save.py.
- **C8, C10, S3 locally trimmable, not restructured**: C8's banner_message
  can derive from the frozen launch descriptor instead of being stored
  redundantly; C10's peer_mgr items 4+5 (fixed-tmp-path concurrency +
  multi-file transactions) combine into ONE registry-transaction primitive
  instead of 2 separate locking/save systems, and its provisioner's atomic
  archive-promotion step is CONFIRMED load-bearing (verified: provisioner
  downloads to `_sys/cache/`, atomic promotion via
  tmp->checksum-verify->os.replace() prevents corrupted cache entries -
  not removable); S3's architecture is already minimal as designed - the
  only note is to treat its "3 commits" as review-commit granularity, not
  3 independently-deployable states (deploy C8-A alone, then land
  C5+C8-B+runner+all-3-entry-migration together atomically).

**Status**: simplification review complete, unanimous. These deltas apply
ON TOP OF each cluster's existing FINAL DESIGN section above (not a
replacement - read both together at TDD time). Not applied this session.

### T1 result: NEW Cluster C11 discovered and FULLY DESIGNED (unanimous, 3 rounds)

Exhaustive audit-vs-backlog cross-reference (ag, verified) confirmed cc's
hypothesis: `check_cli_reality.py`'s own 4 bugs (audit S5.1-5.4) plus the
adapter-layer disconnection (S2.4) were the ONLY genuinely unassigned items
in the entire 47-item audit. Every other item maps to an existing cluster,
Tier-3 (applied), or Tier-4 (confirmed non-bug). Named Cluster C11.

**cx's round-2 critique found a CRITICAL SAFETY FLAW in ag's round-1
design via real empirical probing** (not just review) - this is the most
consequential correction found in the whole session's design work:

- ag's round-1 rule ("block dispatch on CONTRADICTED or ABSENT") would have
  IMMEDIATELY blocked every current `cx` dispatch the moment it shipped -
  cx actually read the live observation cache and found `cx` has ZERO
  entries in it at all (plus the existing entries are already past the 24h
  freshness window) - so "no observation yet" would have been
  indistinguishable from "confirmed broken" under the naive rule.
- Real timing probes: cache read = 0.094ms median; SHA-256-hashing ag's
  real 165MB executable for fingerprinting = 112.1ms median;
  `run(live=False)` (which does that fingerprinting) = 115.8ms median.
  Confirms pre-dispatch MUST use a pure cache-only reader, never anything
  that fingerprints/probes live (would add 100ms+ to every single ask).
- A "COMPLETE canary probe run" is NOT the same thing as "a complete model
  catalog" - canaries only prove POSITIVE confirmations; a missing PASS
  could mean timeout/budget/quota/auth/transport failure/reply-mismatch OR
  a real absence - even a fully-finished canary fan-out can't produce a
  trustworthy negative. Real exhaustive enumeration is the only evidence
  strong enough to justify a hard CONTRADICTED block.
- Several "bugs" were already partially fixed in real code (captured_at,
  provenance, SHA-256 fingerprint, 24h refresh interval already exist in
  `auto_refresh_observed()`) - the REAL C11.2 bug is narrower:
  `load_observed_models()` discards all that metadata on read, and there
  are TWO inconsistent producers (`auto_refresh_observed()` vs
  `check_cli_canary.emit_observed_capture()`) writing different shapes.

**Adopted final design**:
- Two-dimensional evidence classification: probe-attempt-status
  (COMPLETE|PARTIAL|FAILED|SKIPPED) x evidence-completeness
  (COMPLETE_CATALOG|POSITIVE_CONFIRMATIONS_ONLY). Only
  COMPLETE_CATALOG+missing = CONTRADICTED (hard-block-eligible);
  POSITIVE_CONFIRMATIONS_ONLY+missing = UNVERIFIED_INCOMPLETE (warn+allow);
  stale cache = STALE_LAST_KNOWN_PRESENT (warn+allow); missing/no cache =
  UNMEASURED (warn+allow, this is the current real `cx` state).
- **Pre-dispatch hard-blocks ONLY on a fresh CONTRADICTED status from a
  verified COMPLETE_CATALOG in the exact same identity namespace** -
  explicitly NEVER blocks on unmeasured/ABSENT/partial/failed/skipped/stale
  evidence or a missing cache entry. Permitting an attempt isn't claiming
  the model IS available - the attempt's real outcome becomes its own
  evidence either way.
- Pure `get_cached_reality_status(dispatch_target, *, ai_root, now) ->
  CachedRealityStatus` for the hot `action_ask()` path (<1ms, zero
  subprocess/hashing); full SHA-256 fingerprinting stays restricted to
  background canary sweeps and explicit `--live` CLI runs.
- Unified single observation-store schema for BOTH producers
  (`auto_refresh_observed()` and `check_cli_canary.emit_observed_capture()`
  currently write inconsistent shapes); partial refreshes MERGE positive
  observations instead of replacing a good prior set; atomic read/write
  under one lock; `ai_root` passed explicitly everywhere (currently
  inconsistent); binary mtime is only a cheap invalidation hint, SHA-256
  remains the real provenance signal; noted real gotcha that `cc`/`cx`
  resolve to tiny npm `.cmd` shims whose bytes can stay unchanged while the
  real package updates - fingerprint definition needs to be peer-
  appropriate, not just hash-the-launcher-shim.
- `real_binary()`/`probe_version()` get a structured observation-boundary
  wrapper (unknown/disabled peer, missing configured path, bare-command-
  absent-from-PATH, wrapper-target-rejected, binary-present) instead of
  scattered exception handling; `probe_version()` returns a structured
  result requiring returncode==0 AND a valid version token in COMBINED
  stdout+stderr (not stdout-only - legitimate CLIs can print version info
  to stderr).
- 24h refresh interval kept as-is (already the real default, not newly
  invented) but moved to governed config, treated as a refresh SLO not an
  abrupt validity cliff; background re-probe scheduling explicitly needs a
  real owner (wire into C6's maintenance-loop work or name another actual
  consumer - "trigger a re-probe" can't just be prose, same recurring
  designed-but-not-scheduled pattern as this whole session's other finds).
- C2/C3 relationship: C2/C3 answer "what context capacity," C11 answers "is
  this exact CLI operand/binary operationally present" - different
  questions sharing target canonicalization, not model identifiers. A
  composed dispatch target carries `profile_id` + `context_target` (C2) +
  `reality_model_key` (C11) side by side. C3's planner excludes fresh
  HARD-NEGATIVE C11 candidates alongside its existing exclusions.

**Status**: design complete, unanimous, ready for TDD/implementation. Not
applied this session.

---

## FINAL SESSION WRAP (2026-07-24, all rounds complete)

Backlog design-consensus session complete: 9 Tier-1 clusters (C1-C9) + 1
Tier-2 (C10) + 1 newly-discovered gap cluster (C11) = 11 fully-designed,
unanimous, ready-for-TDD clusters. Plus 3 structural/cross-cutting items
(S1 sequencing by cc, S2 wiring-verification check, S3 console
entry-point unification) + a full simplification pass (T2) trimming
complexity across 5 of the 12 original designs without losing correctness
guarantees. Combined with the same-day Top-5 fix-implementation pass
(4/6 applied), the ENTIRE architecture-audit-2026-07-24.md backlog now has
either an applied fix or a converged design - genuinely zero open design
decisions remain, only implementation (TDD stage) work.

Two more live self-demonstrations of the exact C1 bug occurred during this
extended session (writing to this doc while a peer ask was in flight
triggered GOVERNED_MUTATION_VIOLATION twice more, both false-positive
quarantines of cx, both recovered via `peer-recover`, no data loss either
time) - now 6+ confirmed live occurrences across the full day's work,
underscoring C1's priority as the first implementation target.

## C1 IMPLEMENTATION STATUS (2026-07-24, real code applied)

### Pass 2 progress update (2026-07-25) - blocker #5 + ask_id part of #6 CLOSED

User explicitly asked for C1 to be finished properly, step by step, rather
than moved past with known gaps. Tackled blocker #5 (success published
before verification) next, since it was the most structurally central of
the 6 pass-2 blockers.

- **8ea6556/e09789f/ccfaeb5/e427c49** (4 commits): `_action_ask_inner()`
  now returns a `_PendingAskSuccess` object instead of recording/printing
  success itself; `action_ask()`'s wrapper only calls `.publish()` in
  `finally`, after the guard confirms no violation.
- **Real bug found DURING this fix, not before it**: cx's cross-
  verification of the first attempt (e09789f) found a SECOND, non-obvious
  bypass -- the Pipe transport's permanent-resume-failure -> fresh-retry
  success branch recorded success inline, completely separate from the
  ordinary success branch, so it evaded the whole deferral mechanism.
  Fixed in ccfaeb5. This is the same "cross-verification catches what
  design-review missed" pattern that has now recurred on every single C1
  implementation pass this session.
- Added a structural AST regression test asserting `_action_ask_inner()`
  contains ZERO direct success-recording calls (any form) anywhere in the
  function -- a general guard against a THIRD bypass site, not just a
  test of the two specific bugs found. cx's re-verification (round 3 on
  this specific fix) found no third bypass, confirmed via independent AST
  scan, and flagged one more minor residual edge (PTY thread left
  "in progress" if the guard check itself raises rather than finding a
  violation) -- closed in e427c49.
- Also fixed as part of the same work: both PTY and Pipe escalation
  recursive calls now thread the ORIGINAL `ask_id` through (previously
  silently minted a new one, losing AskGuardRecord/lease continuity across
  an escalated retry) -- closes the `ask_id` part of blocker #6.
- **3 full rounds of real cross-verification on this one fix** (cx found
  a real bug in round 1, confirmed the fix + found one minor edge in round
  2, confirmed clean in round 3) -- all via real code tracing/AST
  inspection; cx's own pytest execution was blocked by an environment
  issue (WinError 5 temp-root, unrelated to the code) each time, so cc's
  independently-run 19/19 passes are the test-execution evidence of record.

### Pass 2 progress update (2026-07-25, continued) - blocker #1 CLOSED

Next tackled the highest-severity remaining item: the forgeable-receipt
vulnerability (cx's exploit against pass 1 -- an ancient/wrong-digest
receipt for a different ask suppressed detection of a real mutation).

- **31ec2c6**: `_commit_host_mutation()` now writes `previous_hashes`
  alongside `committed_hashes` in every receipt. `_verify_ask_guard_record()`
  only trusts a receipt if (a) `committed_at >= this ask's AskGuardRecord
  started_at` (rejects ancient receipts) AND (b) its
  `previous_hashes`/`committed_hashes` genuinely chain from the observed
  `pre_hash` to `post_hash` for that exact path.
- **Real bug found applying ag's draft, same pattern as before**: ag's
  original design kept a "legacy-compat" fallback trusting a receipt with
  NO `previous_hashes` field if its `committed_hashes` merely matched the
  current post-mutation hash -- trivially forgeable by whoever made the
  mutation (they already know that hash). cc removed this fallback
  entirely before applying (`_commit_host_mutation()` has zero legacy
  callers to support, so nothing legitimate depends on it).
- 4 new tests: cx's exact original exploit (now rejected), a wrong-digest-
  chain variant (rejected), the missing-`previous_hashes` gap cc found
  (rejected), and a positive genuine-receipt case (verifies clean, no
  false positives). 23/23 governed-guard tests pass; full suite 1406
  passed, same 4 pre-existing unrelated failures.
- **Cross-verification note**: cx zombied twice in a row on this dispatch
  (session-resume failures, recovered via `peer-recover` both times, per
  this session's established "never reuse a failed IPC file" rule) --
  switched to ag for this round. ag's CODE-LEVEL exploit analysis (4
  angles: no-upper-bound temporal check, chain-walk forgery, cross-path
  pollution, timestamp string-sortability) correctly matches the real
  applied source and found no new bug. However, ag's cited TEST EXECUTION
  results (test names, 17/17 count) did NOT match the real
  `test_governed_guard.py` file -- almost certainly ag's own stale scratch
  mirror from its ORIGINAL design-draft dispatch, the same
  stale-mirror pattern seen repeatedly earlier this session. Do not cite
  "ag ran the tests" as evidence; cc's own directly-run 23/23 + full-suite
  1406 pass is the test-execution evidence of record. The code-level
  exploit-angle analysis is still valid/useful independent of that mismatch.

**Still open** (blockers #2-4, and the cwd-isolation part of #6):
host-storage tamper-resistance, verify/commit lock
sharing, per-ask cwd isolation. Next up: blocker #1 (receipt forgery),
the most safety-critical of the remaining items.

### Pass 1 - APPLIED and committed (8ea6556)

- Automatic git-checkout/file-deletion revert deleted entirely, replaced
  with non-destructive quarantine (live bytes always preserved).
- action_ask()'s pre-check snapshot is genuinely fail-closed (was silently
  disabled on any exception before).
- No peer-health-penalty for an unattributed change (a before/after hash
  window proves temporal overlap, not authorship) -- logs
  UNATTRIBUTED_GOVERNED_CHANGE, not GOVERNED_MUTATION_VIOLATION.
- AskGuardRecord/MutationRequest/MutationReceipt scaffolding added, plus
  _mutation_lock_resource()/_commit_host_mutation() -- ZERO production
  callers by design, explicitly documented inline as not-yet-safe.
- check_lesson_enforcement.py's LL-20260703-005 live self-test updated to
  match the renamed log contract.
- 16/16 governed-guard tests pass; full 1403-test suite shows zero
  regressions (4 pre-existing unrelated failures confirmed via git-stash
  A/B comparison).
- Cross-verified by cx.deepthink against the REAL APPLIED code (not a
  design proposal) -- found and cc fixed 3 real bugs during application
  (return-type absolute-vs-relative regression, action_ask bypassing the
  _governed_post_check alias so existing monkeypatch-based tests silently
  stopped working, a leftover peer-health-penalty call contradicting the
  design). Design credit: ag.deepthink (pass-1 draft) + cx.deepthink
  (empirical cross-verification).

### Pass 2 - original 6 blockers found via real exploit probes against the applied code (cx)

cx's cross-verification went further than reviewing the diff -- it actually
exploited the applied code and found 6 real gaps, the most serious being an
actual forged-receipt attack that works today (dormant only because nothing
calls `_commit_host_mutation` yet). **#5 and the ask_id part of #6 are now
CLOSED** -- see the "Pass 2 progress update (2026-07-25)" section above.
#1-4 and the cwd-isolation part of #6 remain open:

1. **Receipt attribution is path-only, no epoch/window/digest-chain
   binding** -- cx created an ancient receipt for a DIFFERENT ask with an
   intentionally wrong digest; it still suppressed detection of a brand
   new unreceipted mutation on that path. Any future caller of
   `_commit_host_mutation` must not ship until this is fixed.
2. **Host-owned state (`.ai/ask_guards/`, `.ai/mutation_receipts/`, etc.)
   is not tamper-resistant** -- lives under peer-writable `.ai/`,
   `_write_json()` overwrites, 4-hex-digit IDs risk collision (cx
   empirically overwrote an existing guard record by reusing an ask ID).
3. **The scratch MutationRequest doesn't actually govern the commit** --
   `_commit_host_mutation()` never validates the scratch proposal's own
   ask_id/target/expected_revision/digest against what's actually
   committed (those come from separate function args) -- cx got a
   deliberately mismatched proposal to commit successfully. Also:
   `status="authorized"` is persisted BEFORE the CAS check, so a failed
   CAS leaves an orphaned "authorized" record behind.
4. **The original TOCTOU-class race is still present** -- verify and
   commit share no lock/epoch coordination, so a verifier can observe
   target bytes before the corresponding receipt exists (false
   quarantine of an authorized commit) or miss a commit landing right
   after its snapshot.
5. **Success is published before verification, not after** -- both PTY
   and Pipe transports record peer-health success, success history,
   routing metrics, AND print the final reply inside `_action_ask_inner()`
   -- all BEFORE the outer guard's post-check even runs in `finally`. An
   unattributed change therefore leaves contradictory success+failure
   records; "post-check failure prevents success publication" is not
   actually true yet. (Pre-existing architectural characteristic, not a
   NEW regression from pass 1 -- but blocks the design's full guarantee.)
6. **Per-ask isolation isn't wired** -- `.ai/scratch/<ask_id>` gets
   created, but peer subprocesses (PTY and Pipe) still run with cwd set to
   the LIVE repository, not the scratch dir -- meaning peers can still
   write directly to the live tree regardless. `_commit_host_mutation()`
   has zero production callers (same "unwired" pattern S2 exists to
   catch, ironically inside C1 itself). Two escalation paths also drop
   the original ask_id instead of carrying it through.

Additional smaller gaps noted: no `guard-reconcile` recovery action yet, no
admission consumer actually blocks on an `indeterminate` AskGuardRecord,
no scratch-dir cleanup, quarantine only captures current bytes (not
baseline+current), and the existing mutation broker still uses its old
`broker_<filename>` lock naming rather than the new
`_mutation_lock_resource()`.

**Status**: pass 1 is real, tested, cross-verified, and committed -- a
genuine safety improvement over the pre-fix code (no more destructive
revert, no more silently-disabled guard, no more unjustified peer
penalties). Pass 2 (the 6 blockers above) is real remaining work, not yet
started -- needed before `_commit_host_mutation`/the receipt system can
ever get a production caller. Both peers' verdict: do not treat receipts
as a real security boundary until pass 2 lands.

### C1 pass 2 COMPLETE (2026-07-25) - all 6 original blockers closed within practical scope

Final blockers closed:

- **7803821 (blocker #2, partial)**: both `_create_ask_guard_record()` and
  `_commit_host_mutation()` now fail closed on an ID collision instead of
  silently overwriting an existing record -- narrowly scoped to accidental
  collision/reuse (full tamper-resistance against a malicious peer with
  filesystem access remains explicitly out of scope, needs OS-level
  process isolation per C1's original design rounds).
- **a8f6e33 (blocker #3)**: `_commit_host_mutation()` now validates the
  scratch proposal's ask_id/target/expected_revision/staged_digest against
  the actual commit arguments (rejects any mismatch), and persists
  `status="authorized"` only after the CAS check + atomic write both
  succeed (no more orphaned "authorized" records on a failed CAS).
- **8497a06 (blocker #4)**: `_verify_ask_guard_record()` now re-reads both
  the current hash AND the receipts fresh, under the SAME per-path
  `_mutation_lock_resource()` lock the committer uses (one path at a time,
  no simultaneous multi-lock deadlock risk), instead of trusting one bulk
  snapshot taken before any locking. A real test simulates the race (a
  commit landing right after the bulk snapshot) and proves it's now
  correctly recognized as authorized rather than falsely quarantined.

**Final status**: all 6 blockers cx's cross-verification found against
pass 1 are now closed within their practical/in-scope boundaries. Two
narrow pieces remain explicitly deferred, both already flagged during
C1's original design rounds as needing a genuinely separate, larger
effort: (a) true tamper-resistance against a malicious peer with direct
`.ai/` filesystem write access (needs OS-level process isolation), and
(b) per-ask cwd isolation (peer subprocesses still run with cwd set to the
live repo, not `.ai/scratch/<ask_id>/`). Neither is currently exploitable
in practice since `_commit_host_mutation()` still has zero production
callers -- C1's mediated-mutation pipeline is now correctness- and
concurrency-hardened and ready for a real caller to be wired in, at which
point (a) and (b) become the natural next work.

10 real commits total for C1 (8ea6556 through 8497a06), every one tested
directly by cc and cross-verified by a peer with real exploit-style
probing (not just design review) before being trusted -- 5 of the 10
rounds found a genuine bug during cross-verification that pure design
review had missed, validating the one-fix-at-a-time-with-real-cross-
verification discipline as load-bearing, not ceremonial, for the entire
C1 effort.
