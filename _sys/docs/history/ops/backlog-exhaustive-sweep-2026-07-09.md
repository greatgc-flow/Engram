# Exhaustive Sweep and Consolidated Backlog Report (2026-07-09)

Delegated to `ag.deepthink` for a fresh sweep of anything not yet captured in
`backlog.json`, after cc's shallow TODO/FIXME/skip-marker grep found nothing beyond
vendored third-party skill templates and legitimate conditional test skips. Every claim
below was independently re-verified by cc against the live file/config before being
accepted (file:line checked, not taken on ag's word).

## Section A — Active / Ready-for-TDD work items

- **T5** (proposed, low, ops) — cx sandbox tempfile create-but-cannot-delete, causing
  repeated large stray-file dumps. Fix: `hub.py` creates a dedicated writable/deletable
  dir under `_sys/data/temp/cx_session_<id>` before invoking cx, injects it via
  TEMP/TMP/TMPDIR, tears it down after. TDD must include an empirical create+delete
  probe under the real cx sandbox before claiming fixed (reasoned-declared, not yet
  measured).
- **T3** (proposed, low, ops) — ag zombie-timeout at 900s on large multi-item asks (ag's
  tool-calling loop doesn't flush partial output, so a large combined ask yields zero
  output). Fix: hub.py pre-dispatch fail-fast heuristic (task-count/token-size
  threshold, DIR-004-declared) warns "split this" by default. cc.fable rejected silent
  auto-split of free-text prose — only auto-split when the caller passes an explicit
  structured task list.
- **D2** (active, low, security, owner=cx) — INV-26 fail-closed promotion. Dry-run
  helper + 20-pass matrix shipped (`feadb3b`). Blocked on the actual 3-gate soak: (1)
  static exhaustive matrix, zero false pos/neg; (2) 100-pass deterministic shuffle, zero
  mismatches; (3) live shadow ≥24h / ≥100 real `_guard_action` evaluations, zero
  mismatches. An action shape seen in live shadow but absent from the static matrix is a
  coverage gap requiring the soak to *extend*, not silently pass.

## Section B — Deferred items (with explicit revisit conditions)

- **D4** (deferred, low, diag) — diag inc-4 failover engine. Existing per-profile health
  gating + pre-dispatch headroom failover already cover "don't route to a dead
  profile"; a full auto-retry engine can't distinguish "never executed" from "executed
  but response lost," so re-dispatching non-idempotent mutating asks risks double
  execution. **Revisit condition:** measured failure-rate evidence (DIR-004) showing
  this actually matters in practice.
- **F1** (deferred, medium, ops) — backlog-refresh automated feedback loop. Design
  remains valid but moot at current scale (backlog is ~8 open items against the
  design's own ~50-item bar). **Revisit condition:** backlog regrows past roughly that
  size and manual re-triage rounds become costly again.

## Section C — Newly found / now tracked

- **D8** (new, proposed, low, routing) — `ag.gptoss` bulk-candidate enablement is fully
  speced and its precondition (D6's `shared_quota_reserve`) already shipped; the only
  remaining step is flipping `routing_state` from `manual_only` to `eligible` once the
  3P-7D shared quota window resets. Verified at `_sys/ai/orchestration.json:296`
  (`_routing_note`): "Blocked now: 3P-7D at 100% until 2026-07-10." Tracked purely so
  the calendar-gated flip isn't forgotten — no code work needed before that date.
- **T8** (new, proposed, low, security, needs-discussion) — cc runs
  `--dangerously-skip-permissions` and ag has no filesystem confinement
  (`--sandbox` doesn't enforce it). Both are pre-existing *declared* risk postures
  (verified at `_sys/ai/orchestration.json:34` and `:39`, DIR-002), not new bugs — and
  now cross-confirmed empirically by [[B7's sandbox probe]]
  (`ops/sandbox-behavior-probe-b7-2026-07-08.md`): cc unenforced 3/3 real runs, ag
  unenforced 2/2 external real runs. A CLI-permission-tool allowlist was already
  trialed for cc (2026-07-03) and reverted (didn't hard-enforce under `-p`). No
  concrete OS-level/hook enforcement design exists yet, so this is `needs-discussion`,
  not ready-for-TDD — tracked so the gap has a home, not because a fix is imminent.
- **Stale routing-config doc strings (fixed directly, no backlog item needed)** — three
  docstrings in `_sys/ai/routing-config.json` had drifted from their adjacent live
  values and were corrected in place: `token_load_balancing._phase` said "enabled=False
  until shadow-validated" while `enabled: true` (shipped/activated 2026-07-04);
  `final_arbiter._doc` said live wiring was "pending" while it shipped and activated
  2026-07-05 (`b52e496`); `final_arbiter._auto_wire_doc` described only the disabled
  default while `auto_wire_on_finalize: true` has been active since the same commit.
  Purely cosmetic — no behavior was affected, only the explanatory text was outdated.

## Section D — Confirmed non-issues (negative-result sweep)

- **No hidden code debt.** `grep -rn "TODO\|FIXME\|XXX:"` across all of `_sys/**/*.py`
  (excluding vendored env/skill trees) returns zero hits inside our own code — every
  match is inside third-party vendored skill templates
  (`_sys/antigravity/config/skills/**`, `_sys/codex/config/skills/**`), not project
  code.
- **No hidden test debt.** Every `skip`/`xfail` marker found in `_sys/tests/**` is a
  legitimate conditional guard (missing fixture file, mocked-dependency branch), not a
  masked failure.
- **D3** (ag V5 Phase 3 refactor) — confirmed correctly `dropped`; quota-contention root
  cause was mitigated by `context_affinity` steering (shipped) and D6's
  `shared_quota_reserve` gating (shipped/activated), matching the dropped item's own
  rationale.
- **P3** (`_legacy` test triage) — confirmed correctly `done`; remaining
  gc/Gemini-coupled tests were properly handed to P2's cleanup pass (physically
  deleted), nothing actionable left under P3 itself.
- Spot-checked G-VOTER, P1, P4, P5, G1, G2, T1, T2, T4, T6, T7, A, B, C, D1, D5, D6, D7
  against their evidence commits and current config/code state — all still accurately
  reflect reality; no drift found.

## Backlog state after this sweep

8 open items: T5, T3, D2 (ready-for-TDD/active) · D4, F1 (deferred) · D8, T8 (newly
tracked, low-priority/calendar-or-discussion-gated). Everything else is done, dropped,
or superseded with resolving evidence commits.
