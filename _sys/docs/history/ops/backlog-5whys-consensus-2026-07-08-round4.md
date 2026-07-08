# SSOT Gate-Expiry Bug — Round 4 (2026-07-08)

Trigger: user noticed `hub.py ask --to cc.fable` was refused 3 times ("rate-limited
until unknown time" / "profile 'fable' is currently unavailable"), but `diag`'s live
quota display never showed fable as rate-limited — a real internal-state-vs-display
divergence, not a misunderstanding. ag and cx independently audited in parallel (both
converged, no material dissent) with cx also proposing complete fix code.

## Root cause (confirmed via `.ai/ask_history.jsonl` + `_sys/claude/health.json`)

- `10:40:11` cc.fable ask succeeded.
- `11:03:06` cc.fable ask failed for real: `rate_or_session_limit`
  ("You've hit your session limit · resets 11:20am").
- `~11:44` a retry failed with `profile 'fable' is currently unavailable`, traced to
  `hub_profile_router.py`'s explicit-profile branch: a raw `gate_open is False` check
  with **no expiry logic at all** — it never looked at `rate_limit_state.reset_at`.
- Meanwhile today's D5 work had already added `_profile_health_gate_open()` in
  `snapshot.py`, which DOES treat an expired cooldown as open — but that function only
  fed the diag DISPLAY layer (`_build_profile_rows`), never the actual routing
  enforcement in `hub_profile_router.py`. So diag could self-heal past an expired
  cooldown while the router kept rejecting the same profile.
- ag additionally found the SAME class of bug in `_eligible_profile()`'s root-level gate
  check (line ~187) and in `snapshot.py`'s raw `info["gate"]` (line ~638) — the
  profile-level per-candidate logic already had (buggy, duplicated, `ValueError`-only)
  inline expiry handling, but root-level checks had none anywhere.

## Fix shipped

- `snapshot.py`: renamed `_profile_health_gate_open` → public `profile_health_gate_open`
  (kept as a back-compat alias) so it can be imported elsewhere — one shared SSOT gate
  check instead of two diverging implementations.
- `hub_profile_router.py`: both `_eligible_profile()` (root + per-candidate) and
  `select_profile_node()`'s explicit-profile branch (root + profile) now call the same
  `profile_health_gate_open()` from snapshot.py, replacing all raw/duplicated checks.
- 2 new regression tests in `test_auto_profile_routing.py`: an expired cooldown must
  route through; an unexpired one must still block. 649/649 tests green.

## Other questions resolved

- **Quota-% vs gate_open — intentionally disconnected.** SUMMARY's quota `used_frac`
  (from `claude /usage` / Codex rate-limits) is informational only; it never writes
  `availability.profiles[x].gate_open`. Both ag and cx agree this is correct fail-safe
  design — quota percentages are estimated/delayed, so only a confirmed live API
  rejection should actually close a routing gate. (This is why AG's peer showed
  `GATE OPEN` even with a `3P-7D` bucket at 100% used, 1.44x pace — expected behavior,
  not a bug.)
- **"F-7H" doesn't exist.** `_CLAUDE_USAGE_SECTIONS` only defines `C-5H` (session,
  shared across all cc profiles including fable), `C-7D` (week, all models), and `F-7D`
  (week, fable-only) — there has never been a fable-specific 5-hour bucket; that usage
  is folded into the shared `C-5H`. Added a one-line annotation to `diag.py`'s
  `render_card` DETAIL view (only shown for `cc` when a `fable` profile-health record
  exists) instead of renaming the `C-5H` label itself, which would have broken
  SUMMARY's fixed 6-char column width.

## Deferred (new backlog item T2, not fixed today — scope creep risk)

cx separately found `snapshot._quota_family_for_profile()` maps `cc.fable` to only the
`F-` prefix, so fable's own headroom/routing-math calculations never account for its
actual `C-5H` consumption. This is a routing-math correctness question (does fable's
computed headroom currently look optimistic?), not just a display gap, and needs its
own focused design pass rather than being bundled into this fix.
