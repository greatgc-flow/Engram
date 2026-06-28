# Standard / Terminal Model Capability — Design Consensus (2026-06-25)

> **Status:** IMPLEMENTED (AT-4 standard terminal slice + AT-5 runtime escalation both landed via feat(hub) AT-4/AT-5).
> **Roadmap (2026-06-26):** SPLIT into slices **AT-4** (terminal relay frame + explicit-profile immutability + classifier boundary) and **AT-5** (bounded runtime `[ESCALATE]`, deferred behind AT-4) — see `ops/backlog-5whys-consensus-2026-06-26.md`. The `[ESCALATE]` valve stays specced but is NOT in the first slice.
> **Origin:** a broken `[ESCALATE]` attempt (BUG-03 bundle) was reviewed NO-GO by 3 models and rolled back; this is the corrected design. See the rollback + review in the same session.

## Goal
Make STANDARD-tier models usable for normal work: (1) the cc terminal runs on Haiku and must route/orchestrate without heavy analysis (D-01/ARCH-01); (2) each peer's `.standard` profile handles light tasks and cleanly hands off heavy ones. A standard model must do routine work reliably, know its boundary, and ESCALATE cleanly — without the brittleness that sank the first attempt.

## What failed (do not repeat)
The `[ESCALATE]` attempt: recursive `action_ask(..., is_resume_attempt=..., to=requested_to)` → TypeError (no such param) + NameError (undefined) = guaranteed runtime crash; unbounded (no `_depth+1`); `sys.exit(0)` masked failure; ZERO test coverage (900/900 green never hit it); scope-crept (silent `escalation_requested` in routing-config + 2 rewritten tests).

## CONSENSUS (both peers signed)

### 1. Capability boundary (Q1)
`standard` = routine/low-risk only: status/list/show/read, short summarize, simple explain, health reporting, mechanical routing. NOT implementation, multi-file reasoning, protocol/governance, security, exhaustive/consensus work. Boundary is score-gated in `routing-config.json` + `hub_profile_router.select_profile_node`; an explicit `.standard` invoked above the deepthink threshold is ineligible. Self-knowledge is a secondary signal only, never the first line of defense.

### 2. Escalation — dual, asymmetric (A + Q2)
Pre-routing classifier is PRIMARY (zero-token, up-front). Runtime self-declared escalation is a BOUNDED safety valve for complexity discovered mid-task.
- **Detection:** strict first non-whitespace marker `[ESCALATE]` / `[ESCALATE:<profile>]` in the PARSED assistant output (verified: no adapter exposes a shared structured flag — Claude/ag/Codex all return plain text). Implement `hub._detect_runtime_escalation(parsed_output)` called AFTER `adapter.parse_output(...)` in BOTH the PTY and subprocess paths (shared post-parse helper).
- **Bounded:** increment `_depth` (ceiling `_depth >= 2` or profile ceiling); preserve `origin`, `quiet`, `output_file`, `session_policy`, `explicit_scope`, timeout, and the raw pre-context query; write `output_file` only for the FINAL answer; return the final attempt's exit code — never `sys.exit(0)` after a failed retry.
- **Not a health failure:** record as a routing metric/event `runtime_escalation_requested`; do NOT add it to `failure_promotion.allowed_reasons`.
- **Explicit target:** an explicit `peer.profile` emitting `[ESCALATE]` does NOT silently change target.

### 3. Terminal role at R:10 (B + Q3)
The terminal AUTO-ROUTES over-capacity work to the right-tier peer — it does NOT abort and does NOT analyze. (No `SOFT_SKIP_EXIT` merely because score selects effort/deepthink — that would refuse exactly the work the router exists to delegate.) `_guard_action`/PRO-19 remains the HARD guard for terminal-origin governance mutation. Add a terminal-frame builder around peer envelopes: `USER_QUERY_RAW` + `ROUTING_METADATA` + `CONTEXT_REFERENCES`, with NO terminal-authored analysis block. Code enforces STRUCTURE (relay shape, raw-query preservation); it cannot detect semantic bias — that stays doc/discipline.

### 4. Routing / health fallback (C + Q4)
- `--to peer.profile`: IMMUTABLE — no classifier promotion/demotion, no silent substitute; unavailable → fail VISIBLY.
- `--to peer`: classified via `_select_ask_profile`, then config + runtime eligibility.
- Health fallback: `hub_profile_router` owns SAME-PEER DOWNWARD only (root-classified `--to cc` selecting `cc.deepthink` may serve `cc.effort` with a visible `[HUB:FALLBACK]`). Cross-peer failover is COORDINATOR policy, NOT the router (grounding: `automatic-profile-routing-2026-06-20.md` rejected horizontal fallback — changing peer changes identity/provider/memory/permissions; B1 design is same-peer downward). Cross-peer same-tier failover deferred to a separate coordinator-policy design.
- RED/gate-closed must never invoke the model.

### 5. Safety / process (Q5)
Any new ask control-flow path MUST have BOTH subprocess and PTY tests + a `test_contracts.py` entry (DIR-003) for signature changes + a dispatch-coverage ratchet entry. The brief MUST list explicit "Out of Scope"; touching tests/config not required by the brief → auto-reject (coordinator).

### Objective bug to fix (found in review, agreed)
`HUB_PEER_TIER` is set from `profile_decision["tier"]`, but `ProfileDecision.as_dict()` exposes `selected_profile`, not `tier` → auto-routed deepthink workers wrongly get env tier `standard`. Fix: `HUB_PEER_TIER = profile_decision["selected_profile"]`. (Also noted: subprocess `_lease_cfg()` called without `node_id` — profile-aware timeout context loss.)

## Phased TDD plan (signed by both)
1. Failing tests first: parsed-output `[ESCALATE]` for subprocess AND PTY; explicit-profile immutability; depth ceiling; final-output-file-only.
2. Fix `HUB_PEER_TIER = profile_decision["selected_profile"]`.
3. Add `hub._detect_runtime_escalation(parsed_output)` — no `failure_promotion` config changes.
4. Add terminal relay frame + tests proving no terminal-authored analysis enters worker prompts.
5. Refactor `action_ask` minimally to share the post-parse escalation handler across PTY/subprocess.
6. Implement B1 per-profile health as same-peer downward for root-classified asks; explicit profile stays fail-visible.
7. Defer cross-peer same-tier failover to a separate coordinator-policy design.

**CONSENSUS one-liner:** pre-route primary + strict parsed-output `[ESCALATE]` marker as a bounded runtime fallback; terminal auto-routes (never aborts/analyzes); router fallback stays same-peer downward while cross-peer failover stays coordinator-owned.
