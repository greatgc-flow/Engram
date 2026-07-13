# Profile Policy — Ratified Decisions & TDD-Ready Specs

> Status: **DECIDED, TDD-READY** (2026-07-13). Exhaustive decision round on every
> deferred/undecided item from [`profile-policy.md`](profile-policy.md) §7-§8.
> Unanimous cx.deepthink + ag.deepthink; cc synthesis. This is the R:10 DECISION
> (verdicts + specs detailed to the point just before writing tests). **No config
> or code is changed by this document** — implementation is a separate TDD round.
> Companion: [`profile-policy.md`](profile-policy.md), [`intelligence-scores.md`](intelligence-scores.md).

## 0. Two P0 enforcement defects (VERIFIED REAL by cx + ag)

The most important finding of this round: the bulk-exclusion (profile-policy §4)
and terminal-minimization (§5) policies are **NOT actually enforced today**. Two
real code defects were verified against live code by both peers:

- **P0-1 — bulk exclusion bypassed.** `hub.py resolve_auto_target()` (~4126) has
  the load balancer pick a correct profile row (e.g. `ag.effort`, not the
  bulk-excluded `ag.opus`), then **discards it and returns only the peer**
  (`{"target": selected_peer}`). `_action_ask_inner` (~4659) then calls
  `_select_ask_profile(to, query)`, which re-runs textual analysis and can
  **re-select a bulk-excluded profile** (cc.fable / ag.opus). So
  `bulk_exclude_profiles` and `arbiter_models` are not enforced end-to-end.
- **P0-2 — terminal exclusion points at the wrong peer.** `resolve_auto_target()`
  (~4123) sets `terminal_peer = _fresh_active_coordinator(...)`. Live state:
  coordinator=`cx`, `human_interface_peer=null`, hub default=`cc`. So
  `terminal_hard_exclude` excludes the **coordinator (cx)**, not the actual
  human-interface terminal (cc) — cc can make bulk background calls and drain its
  own tokens unthrottled while cx is wrongly blocked.

These are filed as backlog (see §4) and are fixed as part of D7 below.

## 1. Decision table

| Item | Verdict | Kind |
|---|---|---|
| **D2** explicit `profile_class` (tier\|specialty) | **PROCEED** | config + validator + tests |
| **D4** declarative `quota_families` + remove stale `ag.sonnet` | **PROCEED** | config + code + tests |
| **D3** capability metadata (renamed) | **PROCEED, RENAMED** | config + snapshot/diag + tests |
| **D6** `ag.deepthink` accepted-inversion intent | **PROCEED** | config + validation |
| **D7** terminal-token leaks + the two P0 defects | **PROCEED (P0)** | code + telemetry + tests |
| **D8** provider-neutral arbiter *principle* | **PROCEED as policy** | docs now; membership later |
| **D1** add Sol to `arbiter_models` | **DEFER** | needs X reserve + measurement |
| **D5** complexity-capability clamp | **DEFER** | needs signal plumbing + local scores |
| **D9** ag session-context reader (T36) | **DEFER** | needs a measurement spike first |

Economic bottom line (both peers): **fix the truthful foundation (D2/D4) and the
terminal-leak/P0 defects (D7) FIRST**; adding Sol to the arbiter pool now would
remove valuable bulk capacity *without* protecting its shared X quota.

## 2. TDD-ready specs (PROCEED items)

### D2 — `profile_class`
- Add required per-profile field `"profile_class": "tier" | "specialty"`.
- Assignments: `tier` for every `standard`/`effort`/`deepthink` (incl. disabled
  `ca`); `specialty` for `cc.fable`, `ag.opus`, `ag.gptoss`.
- Validator (extend contracts / a new check): (1) every profile has exactly one
  valid class; (2) names in {standard,effort,deepthink} MUST be `tier`; (3) a
  `tier` profile may only have one of those three names; (4) any other name MUST
  be `specialty`; (5) enabled peers keep all three tier profiles; (6) `specialty`
  does NOT itself imply bulk/premium/arbiter authority.
- Replace only ad-hoc "specialty-by-name" string inference; routing authority
  stays `routing_state` / `arbiter_models` / `bulk_exclude_profiles`. The
  normalizer already copies arbitrary profile metadata — add a regression that
  the field survives normalization and reaches snapshot rows.
- Tests: full migration matrix; missing/invalid class fails; `standard:specialty`
  fails; `foo:tier` fails; disabled `ca` still validated; normalization preserves.

### D4 — `quota_families` (PLURAL) + T37
- Add `"quota_families": [...]` (PLURAL — `cc.fable` legitimately maps to BOTH
  `F` and `C`). Assignments: `cc.tiers=["C"]`, `cc.fable=["F","C"]`,
  `ag.tiers=["G"]`, `ag.opus`/`ag.gptoss=["3P"]`, `cx.tiers=["X"]`; disabled `ca`
  absent/empty until its real family is known.
- Refactor `snapshot._quota_family_for_profile`: load orchestration once, read the
  declared list, translate family IDs → bucket prefixes; transitional legacy
  fallback with the **stale `ag.sonnet -> 3P` entry REMOVED** (T37); unknown
  enabled profiles return no binding / `absent` (never a guessed family). The
  configured family is `[decl]`; bucket source tags stay app_server/statusline.
- **Cross-config invariant (assert in a check):** a *protected* profile (in
  `arbiter_models` or `bulk_exclude_profiles`, or `routing_state=manual_only`)
  that shares a family with a bulk-eligible profile MUST have
  `shared_quota_reserve.families[family]` listing it in `reserve_for`. Applies to
  `C` and `3P` today (and to `X` iff D1 later proceeds). Do NOT require a reserve
  merely because a profile is `specialty` (`ag.gptoss` is specialty but
  intentionally bulk).
- Caveat to record: a fresh probe showed Fable currently drawing only `C` buckets
  from statusline, so `F`-pool independence is itself `declared, unverified`;
  `["F","C"]` preserves today's filtering (min-effective-remaining) semantics.
- Tests: all assignments; Fable accepts C and F buckets and keeps the min
  constraint; `ag.sonnet` no longer maps to 3P; invalid family fails; missing
  family fails for enabled but allowed for disabled; reserve invariant accepts
  current C/3P and rejects an unreserved protected+shared family; legacy fallback
  identical except the removed `ag.sonnet`.

### D3 — capability metadata (RENAMED, DIR-004)
- Do **NOT** name it `measured_intelligence_score` — the table is external and
  unverified; "measured" would violate DIR-004. Use an evidence object:
  ```json
  "intelligence_evidence": {
    "estimate": {"kind": "point", "value": 59.0, "approximate": true},
    "scale": "external_composite",
    "source_kind": "declared",
    "verification": "unverified",
    "source_ref": "_sys/docs-v2/ops/intelligence-scores.md#1-source-data-dir-004-declared-unverified",
    "as_of": "2026-07-13"
  }
  ```
  Ranges use `{"kind":"range","min":46.0,"max":47.0,"approximate":true}`.
- Populate ONLY table-supported profiles (cc.deepthink~56, cc.fable~60,
  ag.effort~50, ag.deepthink~46-47, cx.standard~51, cx.effort~55, cx.deepthink~59);
  leave Haiku/Sonnet4.6/Opus4.6/Flash-low/GPT-OSS **`absent`** (no extrapolation).
- Consumption: snapshot propagates it; detailed diag MAY render `INTEL ~59 [decl]`,
  missing = `absent`; **load balancing and arbiter ordering MUST NOT consume
  declared/unverified scores** (a future D5 gate may consume only
  locally-verified `empirical_probe` evidence). Arbiter order stays explicit
  config, preserving operator control.
- Tests: point/range schemas mutually exclusive + validated; provenance mandatory
  when a score exists; unverified renders `[decl]`; missing renders `absent`;
  adding the metadata does NOT change routing weights or arbiter selection.

### D6 — `ag.deepthink` accepted-inversion intent
- Add a structured `profile_intent` object (not a capability claim):
  ```json
  "profile_intent": {
    "selection_basis": "resilience_over_external_composite",
    "workloads": ["long_context", "tool_use", "multi_turn_instruction_following"],
    "tier_score_exception": {
      "relative_to": "ag.effort",
      "kind": "external_composite_inversion",
      "status": "accepted_policy_exception"
    },
    "evidence_status": "declared_unverified",
    "source_ref": "_sys/docs-v2/ops/profile-policy.md#2-capability-tiering"
  }
  ```
- **Drop the "2M context" wording as fact** — orchestration.json declares
  `1,048,576` for all three AG tier profiles, so a distinct 2M advantage is
  unverified.
- Tests: intent survives normalization; `relative_to` resolves to a same-peer
  profile; workload/status values validated; model/routing_state/outcome
  unchanged; a monotonic-score check treats this documented inversion as an
  accepted exception, not an unexplained defect.

### D7 — terminal-token leaks + the two P0 fixes (P0 priority)
Treatment is **guard/warn + telemetry**, never a hard block (some manual
`--to cc.*` is legitimate operator choice).
1. **Fix P0-2 (terminal identity):** resolve the REAL terminal from the
   human-interface selection/state (reuse the T20 `_human_interface_peer_*`
   eligibility work), NOT `active_coordinator`. If `terminal_hard_exclude` is on
   but no trustworthy terminal identity resolves, AUTO fails loud
   (`terminal_identity_absent`). Test: coordinator=cx, terminal=cc → AUTO excludes
   cc, not cx.
2. **Fix P0-1 (AUTO profile preserved):** `resolve_auto_target()` must return the
   balancer's selected PROFILE id (e.g. `ag.gptoss`), and `_action_ask_inner` must
   **bypass `_select_ask_profile` when the effective target already carries a
   specific profile from the LB**. Session hysteresis must keep that exact
   representative (or explicitly pick a valid one). Tests: a bulk/arbiter-excluded
   profile cannot be reintroduced by `_select_ask_profile`; `ag.gptoss` chosen by
   the LB stays `ag.gptoss` through invocation.
3. **`--allow-terminal-spend` flag:** an explicit target resolving to the terminal
   peer emits `[HUB:WARN] terminal-token spend: ...` + a `terminal_spend_guard`
   routing-metric event `{mode:warn, reason:explicit_target, terminal_peer,
   requested_target, resolved_target, origin, acknowledged}`, but the ask still
   proceeds. The flag suppresses the warning and records `acknowledged=true`;
   works non-interactively.
4. **Same-peer downward fallback** (cc.effort→cc.standard) emits the same event
   with `reason=same_peer_fallback`; no cross-peer reroute (it may be intentional).
5. **Subagent/default-cc:** no in-repo subagent-spawn/default path found → scope
   the guard to `origin=worker` asks that explicitly resolve to the terminal
   (`reason=worker_explicit_target`); external subagent defaulting is `TEST NEEDED`
   (do not invent a hook without an observed call path).
- Adding `allow_terminal_spend` to `action_ask()` changes a public `action_*`
  signature → update `l1_core/test_contracts.py` under DIR-003.

### D8 — provider-neutral arbiter (policy PROCEED; Sol membership DEFER)
- Ratify the *principle*: the DIR-005 arbiter pool should be **provider-neutral**
  — Claude stays primary (first-usable, stylistic consistency) with a non-Claude
  premium as a fallback for epistemic diversity + resilience against a Claude
  outage/degraded-C-pool/systematic blind spot. The implementation is already
  provider-neutral (stores/invokes an opaque profile id, no Claude-specific
  logic). Membership criteria: locally-verified capability (not the composite),
  healthy path, numeric current headroom, independent failure family, protected
  quota economics, use within DIR-005 triggers + global budget.
- **Human taste call** (frame for the operator): Claude-only (more consistent
  final judgments) vs provider-diverse (stronger resilience). Both peers
  recommend provider-diverse.

## 3. Deferred items + their gating conditions

- **D1 (Sol → arbiter_models): DEFER.** Excluding Sol from bulk does NOT reserve
  the shared `X` pool (luna/terra keep draining X; no `X` entry in
  `shared_quota_reserve` today), so Sol would be starved. Gate to proceed: (a) add
  an `X` reserve `{"reserve_for":["cx.deepthink"], "reserve_fraction": <empirically
  derived — TEST NEEDED, must not be guessed>}`, (b) live X-headroom + arbiter
  budget evidence. Also note `target_decision_pct_cap=0.05` is declared but has no
  code consumer today (only the 5/5h budget is enforced) — surface that when D1 is
  revisited. Future arbiter list would be `["cc.fable","cc.deepthink","cx.deepthink"]`
  (Sol third = fallback, Claude keeps tie-break character).
- **D5 (complexity clamp): DEFER.** A hardness signal exists (`_score_query`), but
  the load balancer doesn't receive it, there are no locally-measured scores, AUTO
  discards the profile (P0-1), and Fable isn't bulk-eligible. Future shadow-only
  `complexity_capability_gate` (hard-remove candidates below a floor — NOT
  headroom=0, because weighting uses a 0.01 epsilon; ordered AFTER the reserve
  gate; `missing_score_policy:exclude`, `no_candidate_policy:fail_loud`), floor
  derived from empirical task outcomes, then a separate activation decision.
- **D9 (ag session context, T36): DEFER.** Needs a measurement spike first: a
  controlled 2-turn AG session, capture hub+agy ids, diff the conversation
  db/log, identify an exact numeric used/window field, validate vs statusline,
  produce a redacted fixture. Only then spec `_read_ag_session_context` (read-only,
  exact numeric only, `agy_conversation_db` source tag, `absent` on unknown
  schema/mapping). Diagnostic-only, not routing correctness.

## 4. Backlog filed this round

- **T39 (P0):** bulk exclusion bypassed — AUTO discards the LB profile and
  `_select_ask_profile` can reintroduce a bulk-excluded/arbiter profile (§0 P0-1).
  Fixed by D7 step 2.
- **T40 (P0):** `terminal_hard_exclude` keyed on `active_coordinator`, not the
  human-interface terminal — cc drains tokens unthrottled (§0 P0-2). Fixed by D7
  step 1.
- **T38** (terminal leaks) is now superseded/detailed by D7; **T37** (stale
  ag.sonnet) by D4; **T36** (ag ctx) by D9.

## 5. Implementation order (for the TDD round)

1. **D2 + D4** — explicit taxonomy + quota bindings with the cross-config validator.
2. **D3 + D6** — honest capability provenance + the accepted AG inversion intent.
3. **D7 (P0)** — terminal identity fix, AUTO profile preservation, warn+telemetry.
4. Gather X-family / intelligence / arbiter-frequency / AG-session evidence.
5. Re-decide **D1**, then **D5** shadow mode.
6. **D9** only after a stable machine-owned AG context source exists.
