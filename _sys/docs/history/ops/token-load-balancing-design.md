# Token Load Balancing — Design (pre-TDD)

> Status: DESIGN COMPLETE, pre-TDD. R:10 discussion: ag (primary design) + cx
> (critical review) + cc (synthesis). Design-only — no code/tests yet.
> Date: 2026-07-04. Foundation: `_sys/core/snapshot.py` SSOT (W4, r-f291).

## 0. Problem & Goal

Peer asks currently route by capability + reactive ContextGate failover. There
is no **proactive** distribution of work by token budget, so one peer can
exhaust a quota window while others sit idle. Goal: route each *routable* ask to
the peer that best **equalizes total token burn-down**, so budgets deplete
proportionally rather than one-at-a-time — using the highest-headroom peer most,
the next-most second, sparing the most-depleted peer, and keeping the
**terminal's own token use minimal** (the terminal delegates, it does not
self-answer when a peer can).

Non-goal (this doc): task-quality routing (capability fit stays a hard
prefilter, unchanged), and the reactive ContextGate failover (stays as-is).

## 1. Requirements (MECE)

### Functional
- **R-F1 Balance objective.** Distribute routable asks so the *remaining-budget
  fraction* across peers converges (equalize burn-down), not merely pick the
  momentary max.
- **R-F2 Terminal minimization (hard).** The terminal (cc when it is the active
  coordinator) is **HARD-EXCLUDED** from routing whenever any non-terminal
  candidate passes capability and has effective headroom above a floor. Terminal
  participates only when (a) all non-terminal candidates are below floor /
  unavailable, or (b) it is explicitly targeted, or (c) it is uniquely capable.
  (cx: a discount alone still burns terminal tokens; the user requirement is
  "terminal tokens ALWAYS minimal" ⇒ exclusion, not discount.)
- **R-F3 Capability fit is a hard prefilter.** Fairness never routes to a
  peer/profile that cannot satisfy task capability, role, sandbox, or an
  explicit-target/governance constraint.
- **R-F4 Window awareness.** Respect BOTH the 5h and weekly windows; a peer must
  not be pushed into premature exhaustion of its most-binding window.
- **R-F5 Pacing safety.** A peer burning faster than its time-to-reset allows
  (pacing ratio > 1) is de-weighted proportionally to the overrun.
- **R-F6 Explicit bypass.** Explicit `--to <peer>`, R:10 governance votes (voters
  fixed regardless of load), and emergency failover **bypass** balancing.

### Non-functional
- **R-N1 Determinism & auditability.** Every routing decision is reproducible and
  logged (snapshot hash, candidate weights, RNG seed + draw, floors applied,
  terminal-exclusion reason, in-flight deduction). Seed = `snapshot_hash+ask_id`.
- **R-N2 No thrash / no stampede.** Parallel asks over 60s-cached telemetry must
  not all pile onto the current max.
- **R-N3 SSOT.** Consume the same `collect_snapshot()` the renderer + failover
  use. No private telemetry path.
- **R-N4 Fail-safe.** Absent/stale telemetry, all-saturated, and single-peer
  cases degrade predictably, never crash the ask.

### Objective function
Let each peer *i* have remaining-budget fraction across accounted windows. Define
per-peer **effective headroom** `H_eff(i)` (below). The balancer approximates
**proportional fairness**: over N asks, share(i) ∝ `H_eff(i)`. This
maximizes Σ log(work_i weighted by headroom) — i.e. it favors the peer with most
slack while never fully starving others, and it equalizes remaining-fraction in
expectation. Exact convergence requires **in-flight deduction** (§3.5), because
cached telemetry lags real burn.

## 2. Signals (inputs, all from the snapshot SSOT)

Per candidate profile row (`_derive_headroom_rows` / `_build_profile_rows`,
`snapshot.py`):
- `context.utilization_pct` → `ctx_remaining = 1 − util`.
- `quota.buckets[]` each `{label(5H|7D), used_frac, pacing{ratio,indicator}}` →
  per-window `remaining = 1 − used_frac`, and `pacing.ratio`.
- `state` (eligible / manual_only / quarantined), `capability_class`, `cost_tier`.
- Provenance: `source_tag`, `observed_at` (for stale policy), snapshot hash.

**Per-peer vs per-profile accounting (MECE gap resolved).** Quota windows belong
to the *peer/account*, not the profile; multiple profiles of one peer share the
same buckets. The balancer accounts **quota per-peer** (dedupe buckets by
peer+window) and **context per-profile/session**. A peer's headroom is computed
once from its shared quota; profile selection within a chosen peer is a separate,
capability-driven step.

## 3. Algorithm

### 3.1 Capability prefilter (hard)
Filter candidates to those that satisfy the task's capability/role/sandbox and
are `state == eligible` with non-absent telemetry. Everything below operates on
this set. If the set is empty → fall back to existing capability/health routing.

### 3.2 Per-window remaining → base headroom
For peer *i*: `H_base(i) = min(ctx_remaining_i, min_over_windows(quota_remaining_i))`.
`min()` is a **hard safety cap** (a tight window must bottleneck). BUT keep the
per-window vector too (see 3.6) so a fresh 5H window is not hidden by a tight
weekly when the task fits within 5h.

### 3.3 Pacing penalty
`P_max(i) = max(pacing.ratio over i's windows)` (worst overrun). 
`H_eff(i) = H_base(i) / max(1.0, P_max(i))`. Pacing < 1 (safe) → unpenalized;
pacing 1.64 → headroom cut ~39%.

### 3.4 Terminal exclusion (hard) & warm-up
- Identify the terminal from `state.json.active_coordinator` (MECE gap: terminal
  identity source). 
- **Exclusion rule (R-F2):** let `FLOOR` be a configured effective-headroom
  floor (e.g. 0.10). If ∃ a non-terminal candidate with `H_eff ≥ FLOOR`, set the
  terminal's routing probability to **0**. Otherwise the terminal may participate.
- **Warm-up bonus (capped):** an eligible non-terminal peer unused this window,
  with valid telemetry + capability, gets a small capped bonus `+b` to `H_eff`
  (encourages spreading; a cold peer has fresh context). NO bonus for absent-quota
  peers.

### 3.5 In-flight deduction (P1.5 — cx: too important to defer to P3)
Before scoring, subtract an estimate of each peer's **in-flight** ask cost from
its remaining fraction: `H_eff(i) −= inflight_tokens(i)/budget_i`. Track in-flight
asks in memory (ask start → estimated tokens; clear on completion). This is what
makes the balancer actually **converge** under 60s-cached telemetry + parallel
asks, instead of stampeding the momentary max.

### 3.6 Task token-size estimation (cx gap)
Estimate the ask's token size (query + expected output class: short reply vs
large-corpus). A huge ask consumes more budget, so it should (a) prefer peers
with absolute headroom to *absorb* it, and (b) count more in in-flight deduction.
Minimal first cut: 3 size buckets (S/M/L) from query length + task_type; scale
the in-flight deduction and optionally gate L-asks to peers above a higher floor.

### 3.7 Cost tie-break
`Score(i) = max(ε, H_eff(i) − COST_MAP[cost_tier_i])` with an explicit numeric
`COST_MAP` (e.g. {low:0.0, mid:0.02, high:0.04}); `cost_tier` is data, never
assume it is numeric. `ε` (floor) guarantees a nonzero draw among *eligible*
peers **but must NOT** resurrect an excluded terminal, an absent-telemetry peer,
or a hard-floored candidate (those are already probability 0 before ε).

### 3.8 Selection — deterministic-audited weighted-random (P1)
`P(i) = Score(i) / Σ Score`. Draw with an RNG **seeded from
`snapshot_hash + ask_id`** so the decision is reproducible and auditable; log the
seed, the draw, and all weights. Rationale (cx ACK): stateless weighted-random
avoids a disk-backed deficit counter (write contention) and self-distributes
parallel asks; its variance is acceptable **only because** it is paired with
in-flight deduction (3.5) and logged draws. (A stateful deficit round-robin is a
possible P3 upgrade if measured fairness variance is too high.)

## 4. Integration

- **Hook:** new `snapshot.select_load_balanced_peer(candidates, task_meta)` (pure,
  in the SSOT module) + a thin `hub.py` caller used when the ask target is
  implicit (`auto`), AFTER the capability prefilter, BEFORE profile selection.
- **Source:** `snapshot.collect_snapshot(use_cache=True)` (router path; 60s TTL).
- **Independent of reactive failover:** proactive balancer picks the initial
  target; if it later trips ContextGate mid-generation, the existing
  `_snapshot_failover_choice` reroutes (unchanged).
- **Logging (R-N1):** append to `.ai/routing_metrics.jsonl`:
  `{ts, event:"load_balance_route", snapshot_hash, task_size, candidates:{peer:weight}, seed, draw, selected_peer, selected_profile, terminal_excluded:<reason|null>, inflight_applied}`.
- **Terminal invocation:** the terminal, when it would otherwise self-answer a
  delegable task, calls the balancer; if a non-terminal peer is selected it
  delegates (one-command-per-ask playbook). Self-answer only when balancer
  returns the terminal (all peers below floor / uniquely capable).

## 5. Config / Policy (`_sys/ai/routing-config.json`)

```json
"token_load_balancing": {
  "enabled": true,
  "effective_headroom_floor": 0.10,
  "terminal_hard_exclude": true,
  "warmup_bonus": 0.05,
  "cost_map": {"low": 0.0, "mid": 0.02, "high": 0.04},
  "pacing_penalty_enabled": true,
  "inflight_deduction_enabled": true,
  "task_size_buckets": {"S": 4000, "M": 32000, "L": 200000},
  "select": "seeded_weighted_random"
}
```

**Governance interaction (R-F6):** balancing is fully bypassed for explicit
targets and R:10 consensus votes — voter set is fixed by the round, never altered
by load. Quota fairness must never override consensus integrity. `collab_rate`
unaffected.

## 6. Edge cases

| Case | Behavior |
|---|---|
| All peers saturated (H_eff < floor) | No non-terminal ≥ floor → terminal may participate; among non-terminals, ε-floored near-uniform draw sheds load evenly (no single-peer overload). |
| Single-peer capability | Prefilter yields one → 100% to it (no weighting). |
| Governance vote needs a depleted voter | Explicit-target bypass; the voter is used regardless of load. |
| Terminal is only candidate | Terminal participates (uniquely capable / all others unavailable). |
| Absent/stale telemetry | Peer with absent quota/context is **non-routable** (probability 0), matching failover's absent policy; STALE (observed_at older than TTL·k) is de-weighted or excluded per policy. |
| Peer hard rate-limited (429 / tier_floor) | state≠eligible or remaining→0 ⇒ filtered; tier_floor_fallback still governs governed votes. |
| Capability vs fairness conflict | Capability wins (hard prefilter); fairness only orders within the capable set. |

## 7. MECE gaps (resolved in this doc)
- Terminal identity source → `state.json.active_coordinator`.
- Absent/stale telemetry policy → non-routable (absent) / de-weight-or-exclude (stale, by TTL).
- Per-peer vs per-profile accounting → quota per-peer (dedupe buckets), context per-profile.
- Audit fields → enumerated in §4 logging.
- Explicit bypasses → explicit target, R:10 votes, emergency failover (§5).
- Task token-size estimation → §3.6.
- Numeric cost map → §5.

## 8. Phasing (bounds the TDD)
- **P1** capability prefilter → H_base → terminal HARD exclusion → cost tie-break
  → seeded-audited weighted-random → routing_metrics logging.
- **P1.5** in-flight deduction + task-size estimate (needed for convergence).
- **P2** pacing penalty + warm-up bonus + per-window (not just min) awareness.
- **P3** telemetry age-decay; optional stateful deficit tracker if variance high;
  predictive cost modeling.

## 9. Worked example (real scenario 2026-07-04)

Remaining fractions: CC ctx .48 / 5H .12 / 7D .41 (pace 1.33); AG ctx .90 / 5H
.96 / 7D .31 (pace .75); CX ctx .30 / 5H .58 / 7D .20 (pace 1.64).

- H_base: CC .12 (5H-bound), AG .31 (7D-bound), CX .20 (7D-bound).
- H_eff = H_base/max(1,P_max): CC .12/1.33=.090, AG .31/1.0=.310, CX .20/1.64=.122.
- Terminal HARD exclude: AG & CX both ≥ FLOOR(.10) ⇒ **CC probability = 0**.
- Among non-terminals: AG .310, CX .122 → **AG 71.7%, CX 28.3%** (CC 0%).
- Next ~6 auto asks (expectation): AG, AG, CX, AG, AG, CX.

Result: CC (terminal, tightest 5H, high burn) does ZERO delegable work; AG (huge
5H headroom, safe pacing) absorbs the bulk; CX takes a minority, held back by its
RED weekly pacing — exactly the user's intent, with terminal at strict minimum.
(Under ag's soft 0.25 discount CC would still draw ~5%; the hard-exclusion rule
enforces the "ALWAYS minimal" requirement.)

## 10. Open decisions for user / TDD entry
1. FLOOR value (0.10 proposed) and warm-up bonus magnitude — tune with real logs.
2. Task-size estimator fidelity for P1.5 (heuristic length-based first).
3. Whether L-asks get a higher floor gate (protect small windows like CX ctx 258k).
4. Enablement default (opt-in `enabled:true` in routing-config, or shadow-log-only
   first to validate distribution before it drives routing).
5. (ag nit) In-flight deduction must handle concurrent + aborted/timed-out asks
   robustly — deduction is cleared on completion, failure, AND timeout (no leak
   that permanently under-weights a peer). Bound the in-flight table lifetime.
6. (ag nit) `routing-config.json` needs schema validation enforcing numeric
   `cost_map` values / floor ranges (fail-closed to defaults on invalid config).

---
Design ACK: ag GO + cx GO (2026-07-04, pre-TDD). This doc is the design contract.
*Next step (on user go): TDD from Phase 1.*

---

# Smartest-Model Final Arbiter — design addendum

> Added 2026-07-04 (R:10). ag designed this section; terminal integrated it
> here (ag first wrote it out-of-band to a phantom root path — reverted;
> the LL-005 governed manifest does not yet cover _sys/docs/history, a
> coverage gap now on the backlog). Grounded in the live P1 shadow finding:
> the balancer would have picked expensive cc because active_coordinator was
> stale and cost_tier under-represents cc.fable — so premium identification
> must be structural (arbiter_models + real cost metadata), not terminal-based.
> **AUTHORITY MODEL NEEDS USER RATIFICATION** (peer-equality override — see §4).

## Smartest-Model Final Arbiter (+ premium-tier bulk de-weighting)

**Objective**: Ensure bulk background work is routed exclusively to cheap, high-headroom peers, while reserving the most capable, expensive model (e.g., `cc.fable`) strictly for authoritative, final-pass judgments on high-stakes or contested decisions.

### 1. Requirements (Q1)
*   **Reliable Premium Identification**: Stop relying on stale `active_coordinator` status for exclusion. Identify premium models structurally via explicit configuration (`arbiter_models` list) and real metadata (e.g., exact cost per 1k tokens), superseding coarse `cost_tier` metrics.
*   **Bulk De-weighting**: The bulk load balancer must actively exclude or heavily penalize the designated premium tier to prevent it from absorbing routine "cheap" asks.
*   **Arbiter Final Opinion**: The smartest model must synthesize and render a final judgment on qualifying decisions, serving as the definitive voice.
*   **Minimize Spend**: The arbiter must only be invoked when truly necessary, utilizing summarized contexts.
*   **Authority Semantics**: Define precisely how the arbiter's opinion interacts with peer-consensus.

### 2. Identifying the Premium/Smartest Model (Q2)
*   **Explicit Designation**: Maintain an explicit `arbiter_models` list in the routing configuration (e.g., `["cc.fable", "ag.deepthink"]`). 
*   **Real Cost Signal**: Add strict cost metadata to `_sys/ai/orchestration.json` (e.g., `$15.00/1M in`, `$75.00/1M out`). The balancer uses this concrete cost metric to exclude premium models from bulk rather than relying on a weak `0.04` tie-breaker.
*   **Deterministic Pick & Fallback**: The arbiter is deterministically chosen by ranking the `arbiter_models` list by `capability_class`. If the primary arbiter (e.g., `cc.fable`) is RED/rate-limited, routing falls back down the chain. 

### 3. Triggers for Arbiter Invocation (Q3)
To strictly control costs, the arbiter is **NOT** invoked on every ask. Triggers are bounded and rare:
*   **Consensus Dissent / Tie**: When cheap peers exploring a solution cannot reach a unanimous agreement.
*   **High-Risk / Irreversible Action**: Decisions involving irreversible mutations (e.g., structural DB drops) or major security boundaries.
*   **Final Synthesis**: On `R:10` governed decisions, before generating the final report or committing to the user.
*   *Skip Condition*: If cheap peers reach a unanimous, uncontested consensus on a standard task, the arbiter pass is entirely skipped.

### 4. Authority Semantics (Q4)
*   **Role**: The arbiter functions as the `recorded-advisory` final-synthesis-author. 
*   **Binding vs. Peer Consensus**: If the arbiter dissents from a cheap-peer consensus, the arbiter's opinion is recorded as the authoritative `FINAL_OPINION`. 
*   **WARNING - Protocol Ratification Needed**: The core protocol defines all peers as equal. Elevating one model to an "Arbiter" with override or final-synthesis authority violates strict peer-equality. **This authority imbalance MUST require explicit USER RATIFICATION before enactment.**

### 5. Token Minimization & Constraints (Q5)
*   **Condensed Input**: The arbiter never receives the raw conversational history. It receives a strictly condensed summary of the cheap peers' findings, the dissent/problem statement, and the proposed actions.
*   **Single-Shot**: Arbiter invocations are `no-iteration`. It fires once, yields its verdict, and terminates.
*   **Invocation Budget**: Implement a strict per-window budget (e.g., max 5 arbiter invocations per 5H window).
*   **Target KPI**: The arbiter should be invoked in `<= 5%` of total daily routing decisions.

### 6. Integration & Flow Position (Q6)
*   **Flow Position**: Fires *after* the bulk cheap-peer exploration/review phase, but *before* the LL-005 governed-mutation commit or final user report.
*   **Reconciliation with LL-005**: The arbiter does not mutate directly. It returns structured advisory text. The current active terminal applies the mutation based on the arbiter's verdict.
*   **Bypassing the Balancer**: Arbiter invocations explicitly target the designated model (e.g., `targets=["cc.fable"]`), completely bypassing the standard bulk load balancer.
*   **Record**: The decision is permanently logged in the consensus record via a dedicated `FINAL_OPINION` field and tracked in `routing_metrics.jsonl`.

### 7. Edge Cases (Q7)
*   **Arbiter Unavailable / Fallback**: If all defined arbiters are exhausted/RED, the system gracefully degrades to standard unanimous cheap-peer consensus.
*   **Arbiter Disagrees with Unanimous Cheap Peers**: The arbiter's verdict wins and is recorded as the canonical path forward, but the cheap peers' original consensus is archived in the telemetry for review.
*   **Arbiter == Terminal**: If the premium model is currently acting as the terminal, it executes the final arbiter pass internally (self-reflection) but still adheres to the summarized-input and single-shot constraints.
*   **Budget Exhausted**: The trigger automatically evaluates to `false`, and the system falls back to standard peer consensus.
*   **Trivial Decision**: Bypassed entirely based on the Trigger rules (Q3).
*   **Stale Terminal Identity**: Ignored. Premium exclusion relies on the static cost metadata and `arbiter_models` list, rendering stale `state.json` status irrelevant.

### 8. Config & Phasing (Q8)
**Configuration Structure (`routing-config.json`)**:
```json
"final_arbiter": {
  "enabled": true,
  "arbiter_models": ["cc.fable", "ag.deepthink"],
  "triggers": ["dissent", "high_risk", "r10_final"],
  "invocation_budget_5h": 5,
  "target_decision_pct_cap": 0.05
}
```
**Phase 1 (Minimal Increment)**:
Introduce the explicit `arbiter_models` config and the concrete cost metadata to orchestration profiles. Update the bulk load balancer to unconditionally filter/exclude any model in `arbiter_models` from implicit `auto` bulk routing. (This solves the immediate bleeding cost issue).

---

### Worked Example

**Scenario**: A design change is proposed for the `hub.py` state machine.
1.  **Cheap Peers Explore**: `ag` and `cx` (cheap peers) are selected by the bulk balancer to evaluate the change.
2.  **Dissent Detected**: `ag` approves the state mutation, but `cx` flags a potential race condition. They fail to reach unanimous consensus.
3.  **Arbiter Triggered**: The routing engine detects a `dissent` trigger.
4.  **Condensed Input Generation**: The terminal synthesizes a 300-token summary of the `ag` vs. `cx` positions and sends a single-shot query to `cc.fable` (the designated arbiter).
5.  **Arbiter Verdict**: `cc.fable` reviews the condensed state and sides with `cx`, providing a structural fix to the race condition.
6.  **Recorded & Applied**: The verdict is written to the `FINAL_OPINION` log. The terminal (e.g., `ag`) applies the structural fix dictated by `cc.fable` per LL-005 mutation rules, without re-engaging `cc.fable` in the iteration loop.

---


### cx review resolution (2026-07-04)
- **Condensation engine (Q-A):** TERMINAL-LOCAL — a deterministic ~300-token
  template over {votes, blockers, evidence}. Cheaper, faster, no second routing
  decision (no extra model call).
- **Authority (Q-B, binding default):** the arbiter is **ADVISORY-RECORDED-ONLY**
  by default (its FINAL_OPINION is logged + surfaced, peers stay equal). The
  "arbiter verdict OVERRIDES peer consensus" semantics are **GATED behind explicit
  USER RATIFICATION** — not enabled until the user ratifies the peer-equality
  exception. (cx: GO for advisory-recorded contract; NO-GO for auto-override pre-ratification.)
- **Pre-TDD gaps to pin (Q-C):** (1) a STRUCTURED dissent-detection mechanism
  (what counts as unresolved dissent among cheap peers); (2) an explicit HIGH-RISK
  classifier (which actions qualify); (3) HARD enforcement of the 5H invocation
  budget + the <=5% target; (4) REAL per-model cost metadata (cc.fable is still
  cost_tier:"mid" in orchestration.json — must be corrected so bulk actually
  de-weights it).
- **Verdict:** GO as pre-TDD design contract with authority = advisory-recorded
  until user ratifies override. ag GO + cx GO.

### Backlog surfaced this round
- LL-005 governed-manifest COVERAGE GAP: peers wrote out-of-band to phantom paths
  (root `ops/`, `_sys/docs-v2/scratch/`) this session — the manifest does not cover
  `_sys/docs/history` nor detect writes to NEW files outside the tree. Extend the
  guard to (a) include docs/history, (b) flag creation of governed-adjacent files
  at unexpected paths.
- Terminal identity: `active_coordinator` in state.json is STALE (=cx). Premium/
  terminal identification must not depend on it (use arbiter_models + real cost).
