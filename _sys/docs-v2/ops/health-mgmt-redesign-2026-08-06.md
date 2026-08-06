# Health-Management Design Proposal (cx.deepthink, 2026-08-06)

I'll inspect the current implementation and configuration first, including the exact transition, precheck, failover, and profile metadata paths named in the request. I'll keep this proposal-only and distinguish verified behavior from recommended design.

The code confirms two overlapping mechanisms: legacy peer health uses JSONL file size and a shared status/gate, while the newer `ContextGate` already performs per-dispatch capacity admission using profile/model metadata and can prune or fresh-failover. I'm tracing their data sources and session lifecycle now, because the safest design should consolidate these mechanisms rather than add a third threshold system.

My proposal is to stop treating "peer health" as one shared traffic light. Context pressure, runtime availability, failure history, and telemetry freshness are different facts with different remedies. Context exhaustion should normally retire or rotate one profile/session -- not quarantine the entire peer.

No files were changed.

## What the current code actually does

One important refinement to the premise: the fixed-MB thresholds only run when `action_health_update(..., status="AUTO")`. The normal console lifecycle passes explicit `GREEN` or `RED`, with `jsonl_mb` defaulting to `0.0`, so it bypasses the threshold calculation and overwrites the recorded size. See `action_health_update` (hub.py:8011), console start (console_runner.py:185), console finish (console_runner.py:361). The repository search found no in-tree caller passing `AUTO`.

Separately, `check_health.py` measures only Claude's newest JSONL and writes `health.json` directly; it does not update `availability.gate_open`. See `check_health.py:101`. Thus the fixed-MB gating path exists, but the normal production wiring does not consistently exercise it. All three current peer health files reported `jsonl_mb: 0.0`. `[empirical_probe]`

There are several genuine state-machine conflations:

- `_record_ask_failure` writes failure-derived `YELLOW`/`RED` into `context_health.status`, even though the failure may have nothing to do with context. See `_record_ask_failure` (hub.py:2261).
- `_record_ask_success` changes context `YELLOW` back to `GREEN` and unconditionally opens the root gate, even though one successful invocation does not prove that a large conversation shrank. See `_record_ask_success` (hub.py:2143).
- `_ask_health_precheck` blocks when the root status is `RED`, regardless of whether a fresh session of the selected profile would work. See `_ask_health_precheck` (hub.py:2038).
- `action_peer_recover` resets context health to `GREEN` without measuring context or creating a fresh session. See `action_peer_recover` (hub.py:3510).
- An unsuccessful interactive console exit passes explicit `RED` after one failure, while `_record_ask_failure` otherwise uses configurable 3/5 failure thresholds. The same color therefore has two incompatible meanings.

The newer `ContextGate` is much better designed: it resolves a profile-specific token capacity and applies relative 80%/95% thresholds. See `ContextGate.check` (hub_context.py:377). Current orchestration declares substantially different profile capacities -- for example, `cx.*` currently says 272,000, not approximately 258,000 -- but these are configuration declarations, not newly re-probed values. `[declared, unverified]` See cx profile configuration (orchestration.json:415).

However, `ContextGate` currently estimates only the new serialized dispatch prompt. Its check occurs before the active reusable session is loaded, at hub.py:6544 versus session lookup at hub.py:6660. Active session records contain identity and timestamps but no occupancy fields; see `_set_active_session` (hub.py:4130). Therefore it protects against an oversized new prompt, but not against:

`existing remote conversation + new prompt + expected response`

exceeding the window.

The snapshot layer already contains useful pieces that should be reused: measured context collectors and exact session-ID-to-profile attribution. See snapshot exact attribution (snapshot.py:777) and profile context construction (snapshot.py:1410).

Historical replay is currently weaker than it appears. The live `ask_history.jsonl` had 215 records, but all 215 recorded `health_state_at_ask="unknown"`. `[empirical_probe]` The likely source-level cause is that `_append_ask_history` looks up logical peer IDs in the installation registry and consequently builds the wrong health path; see `_append_ask_history` (hub.py:4047) and `_load_peers` (hub.py:383). Current history therefore cannot calibrate context transitions reliably.

## 1. Rationalized health indicators

The primary state should be multidimensional and profile/session-scoped:

| Dimension | Concrete states | Scope | Dispatch consequence |
|---|---|---|---|
| Availability | `AVAILABLE`, `COOLDOWN`, `BLOCKED`, `QUARANTINED`, `UNKNOWN` | Peer or profile | May hard-block dispatch |
| Reliability | `HEALTHY`, `DEGRADED`, `UNHEALTHY` | Prefer profile; peer for genuine root failures | Routing penalty; eventual block by failure policy |
| Context | `NORMAL`, `PRESSURE`, `ROTATION_PENDING`, `EXHAUSTED`, `UNKNOWN` | Exact session + scope + profile | Controls reuse, not peer availability |
| Observation freshness | `CURRENT`, `STALE`, `ABSENT` | Each measured signal | Controls confidence and whether automation is allowed |
| Artifact/log size | `NORMAL`, `LARGE`, `CRITICAL` | JSONL/log file | Maintenance warning only |

`GREEN/YELLOW/RED` can remain as a compatibility/display projection, but must not be the authoritative state:

- `GREEN`: selected dispatch mode is normally allowed.
- `YELLOW`: dispatch remains possible, but reliability is degraded, context is under pressure, or evidence is stale.
- `RED`: the selected dispatch mode is unsafe or unavailable.

Crucially, context `EXHAUSTED` would normally produce:

- reuse: blocked;
- fresh same profile: allowed;
- other healthy profiles: unaffected.

Therefore context exhaustion must never set the root peer's availability gate false.

JSONL size should not be divided by the model window. JSONL bytes contain implementation-specific metadata and have no stable cross-peer token conversion. Keep MB thresholds only as an artifact-maintenance signal. Actual context health should use token occupancy divided by the resolved profile admission limit.

Failure counters should move wholly into reliability:

- Rate limits become profile-scoped availability cooldowns with `reset_at`.
- Authentication or missing root executable becomes availability-blocked at the scope actually proven.
- Non-transient failures increment reliability counters.
- A selected-profile success clears that profile's reliability streak and any availability condition it actually disproves.
- Success must not alter context occupancy or clear unrelated profile failures.

`gate_open` should become a backward-compatible derived field during migration. The real precheck should return a structured policy such as:

```text
allow=true
dispatch_mode=fresh
reuse_allowed=false
reason_codes=[context_rotation_required]
```

## 2. Optimal context usage management

The dispatch evaluator should project the next turn:

```text
projected_tokens =
    observed_active_session_tokens
  + estimated_new_prompt_tokens
  + measured_response_reserve
  + calibrated_estimator_margin
```

The capacity denominator should remain `ContextGate`'s `ResolvedContextTarget.admission_limit`, preserving its existing handling of per-profile limits and conservative proven lower bounds.

I would not invent a universal fixed response reserve. It should come from actual per-profile token-usage telemetry, such as a measured recent p95. If a profile lacks sufficient measured usage or exact session attribution, autonomous rotation remains shadow-only for that profile. That follows the measured-only rule instead of turning an estimate into a production invariant.

For bootstrap shadow decisions, retain the existing 80% pressure and 95% hard thresholds. Do not claim they are optimal; use shadow data to decide whether the intermediate rotation point should be percentage-based or based on measured remaining-turn headroom.

The operational policy should be:

```text
Availability blocked?
  -> block for the availability reason

Fresh/stateless dispatch?
  -> evaluate only the new prompt; prune/fail over as today

Reusable exact session with current occupancy evidence?
  -> evaluate projected total
       normal: reuse
       pressure: reuse + mark rotation pending
       safe boundary reached: fresh same profile
       hard limit, unsafe boundary: targeted continuity error

Occupancy absent or stale?
  -> warn/reuse or shadow only; never silently rotate
```

Fresh-session rotation should prefer the same profile. Cross-profile failover changes capability, cost, model behavior, and possibly permissions. It remains appropriate when the standalone prompt itself cannot fit, which is what the current capacity-aware failover planner handles.

### Protecting continuity

I would not silently fresh-rotate every `session_policy=auto` dispatch as soon as a percentage is crossed. A follow-up such as "continue," "apply the second option," or "fix the remaining failure" can depend heavily on opaque prior context.

Automatic rotation should require a mechanically verifiable safe boundary, not a natural-language guess. Initial safe boundaries:

- caller explicitly requests `fresh`;
- a new scope/task starts;
- the task registry marks the prior task complete;
- a structured continuity checkpoint is newer than the session's last ask;
- the caller supplies an explicit `rotation_safe` signal.

At pressure, the hub marks `rotation_pending`. At the next verified safe boundary, it starts a fresh session of the same profile and injects a bounded continuity capsule containing hub-trusted data: handoff sections, active-task state, last ask ID, relevant recent query/response artifacts, and their hashes.

`session_policy=reuse` must mean exactly that: never silently rotate. If it reaches the hard limit, return a specific pre-dispatch error requesting a checkpoint or explicit fresh start. Do not close the peer gate.

Rotation also needs a transactional lifecycle:

1. Acquire a scope/profile rotation claim and ensure there is no conflicting active lease.
2. Mark the old session `draining`, not retired.
3. Build and validate the continuity capsule.
4. Send the original user query exactly once to the fresh session.
5. Retire the old session only after the fresh session is successfully registered.
6. On pre-spawn failure, restore the old session to active.
7. On post-spawn uncertainty, preserve both records and never resend the user query automatically.

I would not add generic automatic `/compact` behavior in the first release. Compaction interfaces and semantics differ by peer CLI; assuming support would violate measured-only operation. A later adapter method such as `compact_session()` can be enabled per profile only after a `cli_live` or `empirical_probe` canary proves the command, session-ID behavior, failure mode, and continuity quality.

## 3. Concrete implementation sketch

In `hub_context.py`:

- Preserve `ContextGate.check()` as the prompt-only primitive.
- Add immutable `SessionContextObservation` and `ContextDispatchDecision` records.
- Add `evaluate_dispatch(...)` accepting active-session occupancy, observation provenance/freshness, response reserve, and session policy.
- Return decisions rather than encoding context pressure as a generic exception.

In `snapshot.py`:

- Promote the existing exact-attribution logic into a public read-only helper such as `get_session_context_observation(peer, profile, session_id)`.
- Return `used_tokens`, `window_tokens`, utilization, observation time, source tag, confidence, and exact-attribution status.
- Never assign a peer-level observation to a profile by model-name guessing.

In `hub.py`:

- Move active-session resolution before the combined context decision.
- Add `_plan_session_context_action(...)`.
- Keep `_ask_health_precheck` availability/reliability-only and pass the selected target/profile.
- For session pressure, try fresh same-profile rotation before cross-profile failover.
- Change `_record_ask_success` and `_record_ask_failure` so they cannot write context state.
- Change `action_peer_recover` so it clears quarantine/reliability/availability but does not assert context `GREEN`.
- Make `action_health_update` a compatibility event-ingestion path: `jsonl_mb` updates artifact health, not capacity health.
- Add a single health event reducer used by every writer, preventing mutually inconsistent direct writes.
- Append every transition to `.ai/health_transitions.jsonl`, including old/new state, reason, scope, session/profile, evidence source, configuration version, and dispatch effect.
- Extend `session_state.json` entries with context observation, rotation generation/state, and checkpoint identity.
- Update `peer-status` to show separate `AVAIL`, `RELIABILITY`, `CONTEXT`, `EVIDENCE`, and effective dispatch policy columns.

There is also a failover wiring issue to resolve before relying on that option: `action_ask` declares `allow_fresh_failover_on_session_reuse`, but its call into `_action_ask_inner` does not forward it, and the parser exposes no corresponding switch. See action_ask forwarding (hub.py:6048). Any public API adjustment must update `test_contracts.py` in the same commit per DIR-003.

Suggested configuration, initially shadow-only:

```json
{
  "context_management": {
    "schema_version": 1,
    "mode": "shadow",
    "pressure_pct": 0.80,
    "hard_pct": 0.95,
    "require_exact_session_attribution": true,
    "projection": {
      "response_reserve_source": "measured_profile_p95",
      "on_absent": "shadow_only"
    },
    "rotation": {
      "enabled": false,
      "strategy": "fresh_same_profile",
      "session_policy": "auto_only",
      "require_safe_boundary": true,
      "on_unsafe_boundary": "mark_pending",
      "on_unknown_context": "warn_reuse"
    }
  }
}
```

`protocol.json`'s current MB thresholds should be renamed/moved under `artifact_health`; the duplicate failure thresholds there should be removed or formally deprecated in favor of `lifecycle_policy.json`.

### Rollout

1. Ship the new event schema, multidimensional display, and shadow decision logging with no dispatch changes.
2. Repair health-history attribution and collect exact session-context observations. Current history is not adequate for calibration.
3. Replay copied transition/ask data through the pure reducer and dispatch planner; never test policy by mutating live health files.
4. Add tests for:
   - same relative utilization across different profile windows;
   - one exhausted session not blocking its peer or sibling profiles;
   - failure and success events never changing context;
   - stale/absent evidence never causing automatic rotation;
   - explicit `reuse` immunity;
   - safe-boundary rotation;
   - concurrent rotation claims;
   - pre-spawn rollback and post-spawn uncertainty;
   - original user query dispatched exactly once;
   - old `health.json` compatibility;
   - contract snapshots required by DIR-003.
5. Enable `fresh_same_profile` only for safe boundaries and profiles with exact, current context evidence.
6. Enable broader automatic checkpoint-and-fresh behavior only after shadow logs show that its decisions match real exhaustion/continuity outcomes.
7. Retain a one-key rollback to `mode: shadow` or `off`.

I ran the existing targeted context/failover tests: 33 passed; one additional test could not execute because this session's filesystem sandbox denied its attempt to create a real `_sys/data/temp/ask_*` directory, so I did not classify that as a product failure. `[empirical_probe]`

## 4. Weakness of this proposal

There is no universally lossless way for the hub to transfer an opaque vendor-managed conversation into a fresh session. Even a validated continuity capsule can omit tacit reasoning, old tool results, or details that later become relevant.

My design handles that honestly by requiring a safe boundary and blocking hard-limit rotation when continuity is not adequately checkpointed. The downside is that it will sometimes still request a checkpoint instead of self-healing completely. I consider that preferable to silently discarding mid-task context in live production infrastructure.

---

# Round 2: ag.deepthink's Independent Verification + Critique (2026-08-06)

### 1. Verification of Load-Bearing Claims
I have independently verified all of cx's claims against the live codebase and production data. They are perfectly accurate:
*   **Fixed-MB threshold dead code:** **True**. A codebase search confirms `status="AUTO"` is never passed to `action_health_update`. The active console hooks hardcode `GREEN` or `RED` and bypass the size calculations entirely.
*   **ContextGate gap:** **True**. `ContextGate.check()` in `hub_context.py:377` calculates only the estimated tokens of the *new* text/prompt against the resolved limit. It does not measure or include the existing remote conversation size.
*   **ask_history "unknown" status:** **True**. I checked `D:\PortableDev (v2.1)\peerhub\.ai\ask_history.jsonl`. Out of 216 total records currently present, exactly 216 records have `"health_state_at_ask": "unknown"`.
*   **Forwarding gap:** **True**. In `hub.py:6049`, `action_ask` receives `allow_fresh_failover_on_session_reuse` but calls `_action_ask_inner(...)` without forwarding it. `_action_ask_inner` defaults to `False`, rendering the argument useless in the public API.

### 2. Soundness of Multidimensional Model & Safe-Boundary Rotation
The shift from a single `GREEN/YELLOW/RED` traffic light to a multidimensional state (Availability vs. Reliability vs. Context) is structurally sound. It solves the genuine conflation bug where an oversized prompt would falsely mark a peer as unreachable.

However, **there is a real flaw in the transactional rotation lifecycle (7 steps) regarding crash-consistency.**
If the hub process crashes, is killed (SIGTERM, OOM), or loses power *after* Step 2 (marking the old session `draining`) but *before* Step 5 (successful fresh session registration), the system is left in a corrupted state on disk.
Because the hub process died, Step 6 ("On pre-spawn failure, restore...") never executes. Upon restart, the hub will see an orphaned `draining` session with no active replacement. Without a defined crash-recovery step (e.g., checking if a rotation claim is expired without a successor and automatically reverting the session to `active`), that profile/scope would be permanently bricked.

### 3. Safest First Concrete Step
cx's proposed Step 1 is indeed the safest entry point: **"ship new event schema, multidimensional display, shadow decision logging, no dispatch changes"**.
I agree this is implementable now with virtually zero risk to live dispatches, as it operates entirely in a shadow mode—observing and logging what the new rules *would* do without altering the current `action_ask` routing logic. The only minor risk is breaking legacy tooling that expects `health.json`, which cx mitigated by preserving a backward-compatible proxy object.

Additionally, patching the `allow_fresh_failover_on_session_reuse` forwarding bug is a one-line, zero-risk fix that should be bundled into Step 1 immediately.

### 4. Verdict
**Ratify with named changes.**

Proceed with the proposal, but apply these mandatory additions:
1.  **Crash-Recovery for Rotations:** Add a defined recovery mechanism for orphaned `draining` sessions. If the hub boots or processes a dispatch and encounters a `draining` session with an expired rotation claim and no valid successor, it must gracefully revert it to `active`.
2.  **DIR-003 Compliance:** If implementing Step 1 changes the method signature or parameter behavior of `action_health_update` (or fixes `action_ask`), `test_contracts.py` MUST be updated in the exact same commit.
3.  **Forwarding Patch:** Include the fix for the `allow_fresh_failover_on_session_reuse` forwarding gap in `action_ask` as part of the initial implementation.

**Status: RATIFIED, NOT YET IMPLEMENTED.** Implementation deliberately deferred to a future session (user's explicit choice, 2026-08-06) -- this is live production infrastructure and the end of an already-long session is not the time to start touching it. Next session should begin directly at Rollout Step 1.
