# Quota Balance & Statusline Display — Decisions

> Status: **DECIDED** (2026-07-15). Exhaustive discussion cx + ag (unanimous,
> evidence-grounded) + cc.fable synthesis. Companion:
> [`statusline-quota-display-handoff-2026-07-15.md`](statusline-quota-display-handoff-2026-07-15.md).
> **No routing algorithm change** — the diagnosis is behavioral + hygiene.

---

## 0. Diagnosis (evidence, not assumption)

The operator asked how to use ag.opus's quota — and ALL quotas — "naturally +
balanced," after observing a session where **cx (X family) was driven to 6.10×
pacing and went RED repeatedly, while ag 3P sat at 0–2% and cc C-5H hit 100%.**
The measured root cause overturns the premise:

- **The load balancer was never called.** `routing_metrics.jsonl` 2026-07-13..15:
  **`direct_ask` 69, `load_balance_route` 0.** The terminal delegated with
  explicit `--to cx` / `--to ag` (35 direct cx calls), which **bypasses the LB's
  cross-family balancing entirely**. `auto_profile_route` only picks a profile
  *within* one peer; only `--to auto` runs `load_balance_route`.
- **Pacing is already ON.** There is no `pacing_penalty_enabled` key in
  `routing-config.json`; `snapshot.py` defaults it to **True**
  (`H_eff = H_base / max(1, pacing_max)`; a unit test verifies pacing 2.0 halves
  headroom). The earlier "pacing = FALSE" premise was wrong. (And with 0 auto
  calls, pacing could not have affected the explicit cx calls anyway.)
- **ag.opus's failures are provider-side, not idle quota.** It hit
  `RESOURCE_EXHAUSTED (429)` / overloaded / unreachable while the **3P family was
  at 0–2% used** — a provider concurrency/QPM overload of Opus-4.6-via-Antigravity
  (Vertex throttles expensive premium models to low concurrency), independent of
  our 3P token budget. **A 429 consumes ZERO tokens** → no 3P impact. Routing bulk
  to ag.opus would hit a 429 wall, not "use spare quota."
- **3P is available and IS used — via `ag.gptoss`.** ag.opus (premium, manual) and
  ag.gptoss (bulk-eligible) share the 3P family; the reserve clamps ag.gptoss
  below its floor to protect ag.opus. Under `--to auto`, bulk naturally flows to
  ag.gptoss while 3P has headroom.

**So the fix is behavioral + hygiene, not an LB rewrite. The biggest lever is
simply calling the LB.**

---

## 1. What "balanced" means (cx, adopted)

NOT equalizing raw `used%` across families — window lengths, resets, roles, and
reserves differ, and an unobservable bucket (F-7D) must never enter the balance.
Balanced = *after* eligibility / terminal-exclusion / premium-exclusion / reserve /
capability constraints, give more probability to the bulk path with the larger
**measured risk-adjusted effective headroom**, lowering the risk of the
soonest-to-exhaust family. Role scoping:

| Family | Role |
|---|---|
| `G`, `3P`, `X` | the bulk-balance set (`--to auto` spreads across these) |
| `C` | terminal + arbiter protected (cc terminal, cc.deepthink arbiter) |
| `F` (+ `C`) | fable arbiter — idle `F` is normal when no arbiter work exists |
| `3P` `ag.opus` | premium manual reserve |

The LB already carries the needed signals: min(quota, context) headroom · pacing ·
cost penalty · absolute-context bias · terminal/premium exclusion · shared-family
reserve · seeded weighted-random. It does not need a new family-spread term yet.

---

## 2. Ratified plan (minimal, sequenced, safe)

1. **Statusline all-buckets display** (the handoff design) — apply the
   shape-driven formatter in `statusline-unified.sh` (legacy statusline helper, removed in separation):

   one canonical bucket list, NO `PEER_ID` branch, first valid numeric per label,
   %-only, `0%` preserved, missing omitted, `quota:N/A` only if no buckets,
   **never fabricate `F-7D`**. AG's JSON uses `remaining_fraction` (float) →
   `(1-remaining)*100`; keys `3p-5h`/`3p-weekly`/`gemini-5h`/`gemini-weekly` →
   `3P-5H`/`3P-7D`/`G-5H`/`G-7D`. Presentation-only: no snapshot/diag/routing/CX
   change. (A UX/audit prerequisite so the operator stops over-using an explicit
   target — NOT an LB-mechanical prerequisite; the LB reads snapshot JSON, not
   rendered text.)
2. **Pacing truthfulness** — set `pacing_penalty_enabled: true` EXPLICITLY in
   `routing-config.json` and fix any stale "P2 pending / opt-in" docs. **No
   behavior change** — it only makes the current default explicit.
3. **Bulk delegation policy** — **fungible bulk work goes `--to auto`** (repeated
   implementation/tests, general investigation, provider-agnostic review, routine
   work); explicit `--to <peer>` only with a reason (user-specified target,
   provider/model canary, `manual_only` like ag.opus, arbiter/high-risk,
   capability-required, session-continuity). Do NOT reinterpret an omitted `--to`
   as global auto — the capability gate is still shadow-only, so all-auto could
   send a hard design task to a cheap representative.
4. **Routing telemetry enrichment** — record on `load_balance_route`:
   `pacing_applied`, `probabilities`, `representative_profiles`, the selected
   `quota_families`, and reserve-clamp status, so the AUTO distribution is
   auditable and the next call is measured.
5. **Observe, then decide** — run real fungible work through `--to auto` across a
   reset window and compare family utilization / pacing / failures BEFORE
   considering a family-spread term (deferred — a premature term risks
   double-counting profiles that share a family or conflicting with the reserve).
6. **ag.opus — unchanged.** Manual premium, bulk-excluded, 3P-reserved. Its issue
   is provider availability (429), not idle quota; routing to it just to spend
   quota is rejected. Arbiter admission is a separate DIR-005/R:10 matter (and it
   is Claude-Opus-family, so it adds little non-Claude intellectual diversity).

**Do NOT change:** terminal hard-exclusion, the shared-family reserve, seeded
weighting, explicit-target preservation, the F-7D-absence-means-unobservable
semantics, CX app-server quota collection, or the D4 auto-retry deferral.

---

## 3. Backlog

- **T55** — statusline all-buckets shape-driven formatter + schema v2 + fixtures
  (the handoff's unapplied implementation).
- **T56** — `pacing_penalty_enabled: true` explicit + stale-doc fix (hygiene).
- **T57** — `load_balance_route` telemetry enrichment.
- **Policy (this doc)** — fungible bulk → `--to auto`; observe AUTO distribution
  before any family-spread term. ag.opus stays manual premium.
