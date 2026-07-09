# Pre-TDD Design Spec (2026-07-09): diag SUMMARY+FRAME live refresh + T15 + T16

Four-round exhaustive discussion (ag proposes → cx cross-reviews →
ag concedes/refines → fable ratifies → final design-fork vote by ag+cx) across
three topics. Unanimous on all three. Nothing here has been implemented —
this is the spec to build against in the next TDD pass.

Round history: ag round-1 proposal → cc spot-checked 3 claims against live
code (all confirmed wrong) → cx round-2 independent review (confirmed cc's 3
findings + found 2 more: `collect_snapshot()`'s `use_cache=False` default, and
`check_agents.py`'s real schema) → ag round-3 conceded all corrections
unanimously → cc.fable round-4 ratification found ONE more location error
(Topic C fix site) + flagged one real design fork needing an explicit choice →
ag + cx both voted the same way on the fork → unanimous.

## Topic A — `diag.py --watch-summary [SECONDS]`

New flag, separate from (but modeled on) the existing `--watch`. Renders the
full dashboard once (all panels, including the `hub.py status` subprocess
call), then on each subsequent tick calls **only** `collect_snapshot()` fresh
(no subprocess) and repaints **only** SUMMARY+FRAME via a new
`render_summary_frame(out, snapshot)` helper.

**In-place repaint mechanism**: track the previous tick's printed
SUMMARY+FRAME line count. Each tick: cursor-up that many lines (`\033[<n>A`),
clear-to-end (`\033[J`), print the new block, store the new line count for
next tick (handles the block's height changing tick-to-tick — e.g. alert
count or quota-row count changes). Force a full dashboard re-render if
terminal size changes mid-session (resets the anchor).

**Rejected alternative** (ag's original proposal): recompute the *entire*
dashboard every tick, including the `hub.py status` subprocess spawn, and just
not print the static panels. Rejected because:
- `snapshot.py:1536`: `collect_snapshot(use_cache=False, clock=time.monotonic)`
  — the docstring states CLI renderers deliberately default to fresh
  collection so `--watch` frames never go stale; there is no TTL cache to
  absorb a fast loop for this path (that cache is the router path only).
- `diag.py:522-533`'s `render_dashboard()` spawns a full Python subprocess
  (`python hub.py status`) as its first real work — non-trivial cost that
  would run on every tick under the rejected design, defeating the point of a
  lightweight refresh mode.

**Test coverage note**: T9's diag.py quota-threshold fixes (`QUOTA_WARN_FRAC`/
`QUOTA_CRIT_FRAC`) are exercised by `render_summary()`, so this path covers
them for free. T14's arbiter-annotation logic lives in `render_card()` (PEER
DETAIL panel), which this summary-only mode does **not** render — it needs
its own dedicated test, not indirect reliance on the full-render path.

## Topic B — T15: `check_cli_reality.py` REAL_BINARIES + `peer_console.py` security-defaults duplication

**`real_binary(peer, orch=None)` resolver**: replaces the static
`REAL_BINARIES` dict. Filters `orch["hub_nodes"]` for `type == "peer"` and
`enabled is not False`, matches `node_id == peer`, reads `node["invoke"]`
**directly** (it is already a resolvable path/command string — not a
dict-of-dicts under a nonexistent top-level `"peers"` key, and not a string
needing token-splitting; `invoke_args` is already a separate field). Resolves
`_sys\...`-relative paths against the repo root using the same pattern
`check_sandbox_behavior.py` already uses (shipped today), and rejects `_sys/cli`
wrapper scripts via the existing `is_wrapper()` helper. Migration touches:
`check_cli_reality.py`'s `run()` and `auto_refresh_observed()`,
`check_cli_canary.py`'s import of `real_binary()`, and any test that
monkeypatches the old `REAL_BINARIES` dict.

**Hardening (fable, non-blocking)**: node `ca` has a bare-name invoke
(`"invoke": "claude"`) but is `enabled=False`, so the `enabled is not False`
filter excludes it today — the "invoke is always a resolvable path" claim
holds for every node the resolver will actually see right now. Recommended:
the resolver should still degrade gracefully (e.g. `shutil.which` fallback or
skip-with-warning) for a bare command name, since nothing structurally
prevents a future *enabled* node from using one.

**`peer_console.py` policy-to-CLI translation**: reads the peer's existing
`security_contract.sandbox_semantics` field (confirmed real values:
`"skip-permissions"`, `"workspace-write"` — there is **no** `"permission_mode"`
field, that was a hallucinated name in the first draft). `"skip-permissions"`
appends the peer's own already-declared `required_effective_args`.
`"workspace-write"` appends the Codex console form `-s workspace-write`
unless the user already supplied sandbox/approval flags themselves. This
guarantees a peer whose `required_effective_args` is legitimately empty (e.g.
cx) still gets its sandbox flag applied via the semantic declaration, instead
of silently dropping it.

## Topic C — T16: budget-bypass coupling + shared AI-output-contract validator

**Scope narrower than originally thought**: `check_cli_canary.py` already has
a working `bypass_budget` parameter threaded through `run_canary()`
(pre-existing infrastructure, confirmed by cx, not new work needed there).

**The actual fix, exact location** (corrected by cc.fable's ratification pass
— the spec previously mis-located this in `check_cli_reality.py`, which has
zero `bypass_budget` references; it only *calls*
`check_cli_canary.run_canary(all_profiles=True, ...)` from
`auto_refresh_observed()`):

1. `check_cli_reality.py`'s `auto_refresh_observed()`: the
   hash-unchanged-but-interval-expired case currently just bumps
   `captured_at` and reports `"skipped, unchanged"` — replace with a real
   budgeted re-probe (a binary hash can't detect server-side model drift).
2. `check_cli_canary.py:402`, inside `run_canary()`'s fan-out loop:
   `bypass_budget = all_profiles or is_explicit` → `bypass_budget = is_explicit`.

**Design fork identified by fable, resolved by unanimous vote (ag + cx, both
independently picked the same option)**: three call sites feed
`all_profiles=True` into that one expression — the genuine CLI `--all-profiles`
operator flag, `check_cli_reality.py`'s `auto_refresh_observed()`, and
`check_cli_canary.py`'s own `emit_observed_capture()`. Changing the expression
to `bypass_budget = is_explicit` caps all three, including a human operator's
deliberate `--all-profiles` run, not just the two internal auto-callers this
fix targets.

- **Option (a)** (not chosen): thread an explicit `operator_invoked` flag so
  only the real CLI entry point keeps the bypass.
- **Option (b)** (UNANIMOUSLY CHOSEN — ag and cx both voted this
  independently): accept that all `all_profiles=True` runs are now
  budget-capped, operator or internal alike. Reasoning (ag): simpler, more
  aligned with this project's DIR-004 "measured, not guessed" ethos (a budget
  is a budget); avoids extra plumbing whose only job is creating an exception;
  the operator retains `is_explicit` (per-profile targeting) as a genuine
  escape hatch, and the new `skipped_budget` status (below) keeps any capping
  visible rather than silent.

**New structured refresh statuses**: `refreshed` / `skipped_budget` /
`interval_not_expired` / `probe_failed`. `skipped_budget` must be visibly
surfaced to the operator (not silent) so "fresh and clean" is never
indistinguishable from "not actually probed this tick."

**Shared `validate_ai_json()` / `ContractViolationError`** in `_common.py`
(reuses `extract_json_block()`, requires a top-level dict, validates presence
of required keys/paths). Real per-file required-key schemas (verified against
each file's *actual current* prompt/schema string today, not guessed —
ag's first draft had guessed all four wrong):

| File | Required keys |
|---|---|
| `check_health.py` | `version`, `generated_at`, `session_context`, `executive_summary`, `technical_state`, `strategy_for_next_session` |
| `check_agents.py` | `scan_ts`, `overlaps`, `gaps`, `inconsistencies`, `ok_count` |
| `check_risk.py` | `agent`, `timestamp`, `task_summary`, `risks`, `overall_risk`, `proceed` |
| `check_versions.py` | `ripgrep`, `fd`, `jq`, `bat`, `delta`, `fzf`, `oh-my-posh`, `nodejs-lts` |

An invalid `check_health.py` handoff must not overwrite the existing handoff
JSON; invalid risk output degrades to `UNKNOWN`/non-blocking (matches the
existing `write_unknown_json()` fallback pattern already used elsewhere in
this file).

## Status

All three topics: **unanimous, TDD-ready.** Nothing implemented yet — this
doc is the spec for the next TDD pass. Backlog: new item for Topic A, T15/T16
updated to reference this finalized design.
