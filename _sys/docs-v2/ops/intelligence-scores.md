# Intelligence Scores & Profile Policy

> Status: **DOCUMENTED ONLY** (2026-07-13). No orchestration/routing config was
> changed on the basis of this table. Recommendations below are for review; a
> governed R:10 round is required before any of the config changes land.
> Discussion: cx.deepthink + ag.deepthink, synthesized by cc; human directed
> "document first, apply later."
>
> **SUPERSEDED-IN-SPIRIT (2026-07-13):** the single composite scalar below is now
> the **declared bootstrap layer** of the capability-leveling framework
> (`ops/capability-leveling.md`). It is `declared/unverified` and **never enters a
> routing decision**; measured per-axis evidence supersedes it (supersede-not-
> overwrite). This table shrinks to a historical/bootstrap appendix once local
> measurement exists (Phase 2+). See `ops/capability-leveling.md §4, §6`.

## 1. Source data (DIR-004: `declared, unverified`)

A **composite** intelligence-score table was supplied by the human operator on
2026-07-13. It is an external composite (reasoning/knowledge-weighted), **not**
our own measurement, so per DIR-004 it must be treated as `declared, unverified`
until backed by a local empirical benchmark. Do not render these as measured
truth in telemetry.

| Model / setting | Composite score | Note |
|---|---:|---|
| Claude Fable 5 (max) | ~60 | current top |
| GPT-5.6 Sol (max) | ~59 | effectively tied with Fable 5 |
| Claude Opus 4.8 (max) | ~56 | slightly below Sol |
| GPT-5.6 Terra (max) | ~55 | ~= Opus 4.8 |
| Claude Sonnet 5 (max) | ~53 | a bit below Terra |
| GPT-5.6 Luna (max) | ~51 | strong upper-mid |
| Gemini 3.5 Flash (high) | ~50 | ~= Luna |
| Gemini 3.1 Pro (Preview) | ~46-47 | below Flash on this composite |

## 2. Current profile mapping (orchestration.json, as of T26)

| Peer | standard | effort | deepthink | other |
|---|---|---|---|---|
| `cc` | Haiku 4.5 | Sonnet 4.6 | Opus 4.8 (~56) | `fable` = Fable 5 (~60), arbiter |
| `ag` | Gemini 3.5 Flash / low | Gemini 3.5 Flash / high (~50) | Gemini 3.1 Pro / high (~46-47) | `opus` = Opus 4.6 (manual), `gptoss` = GPT-OSS |
| `cx` | gpt-5.6-luna (~51) | gpt-5.6-terra (~55) | gpt-5.6-sol (~59) | — |

## 3. Findings

- **ag tier inversion (real):** `ag.deepthink` (Gemini 3.1 Pro, ~46-47) scores
  BELOW `ag.effort` (Gemini 3.5 Flash high, ~50) on this composite. ag's
  "deepthink" is therefore weaker than its "effort" on raw score.
- **Cross-peer deepthink ranking:** `cx.deepthink` (sol ~59) > `cc.deepthink`
  (Opus 4.8 ~56) > `ag.deepthink` (3.1 Pro ~46). The strongest non-arbiter
  reasoner is currently cx.deepthink, above cc's Opus.
- **Top tier:** Fable 5 (~60) and Sol (~59) are effectively co-top; Opus 4.8 and
  Terra form the next band.

## 4. Recommendations (NOT yet applied)

### 4.1 ag.deepthink inversion — two options
- **Option A (preferred if available):** switch `ag.deepthink` to **Gemini 3.5
  Pro** (composite ~57-58 per ag), which clears the inversion and outscores Opus
  4.8. **Blocked on a measurement:** confirm Gemini 3.5 Pro is actually available
  to the agy CLI (DIR-004 — do not declare it usable until a real invocation
  succeeds), analogous to how the T26 cx migration was gated on `codex debug
  models` + a live canary.
- **Option B (fallback):** keep Gemini 3.1 Pro at `ag.deepthink`, but document in
  orchestration.json that this tier is chosen for **long-context (2M window),
  multi-turn instruction following, and tool-call fidelity resilience**, not raw
  composite superiority over Flash. Rationale (ag): Pro-tier models are typically
  more robust than Flash under complex multi-turn/JSON/tool workflows even when a
  single-shot composite score is lower.

### 4.2 Arbiter policy
- The DIR-005 `arbiter_models` list currently holds the premium Claude profiles
  (cc.fable, cc.deepthink). Given Sol (~59) is co-top with Fable (~60),
  **consider adding `cx.deepthink` (gpt-5.6-sol) to `arbiter_models`** so the
  smartest-model tie-breaker pool reflects measured capability, not just the
  Claude family. Keep `ag.deepthink` OUT of the arbiter pool and out of the R05
  "Deep Reasoner" primary/fallback slots.
- Caveat: expanding `arbiter_models` widens the Tier-0-ratified DIR-005 arbiter
  candidate set and spends premium tokens; it is itself an R:10 decision.

### 4.3 Cross-peer capability, structurally
To let routing use measured capability instead of only per-peer
`standard/effort/deepthink` labels:
- Add an optional `measured_intelligence_score` (float) + `score_source` (string,
  e.g. `external_composite_table:2026-07-13`) field to each profile block in
  `orchestration.json`. Absent = unknown (DIR-004 `absent`, never implied 0).
- In `routing-config.json` `token_load_balancing`, an optional
  `complexity_threshold` gate: for tasks classified high-complexity, clamp the
  bulk headroom of candidates whose `measured_intelligence_score` is below a
  configured floor, forcing failover to high-capability nodes (sol / fable).
  This mirrors the existing headroom-clamp mechanism.
- This file is the canonical registry for the score table; the config fields
  reference it via `score_source`.

## 5. Risks / caveats (DIR-004)

- **Workload divergence:** a composite (math/knowledge/reasoning) may not track
  actual coding / file-manipulation / tool-use performance for our workloads.
- **Context trade-off:** a high-score model with a smaller usable window can lose
  to a lower-score model with a large window on big-context tasks (relevant to
  Gemini 3.1 Pro's 2M window vs Flash).
- **Storage/labeling:** wherever these scores surface (config or telemetry), flag
  them `declared, unverified`. Supersede this table when a local empirical
  benchmark suite exists (do not silently overwrite — keep provenance, like the
  peer-characteristics supersede pattern).

## 6. Next step

If the operator approves any of §4, open an R:10 round (like T26): re-measure the
relevant model availability live, apply orchestration/routing edits atomically,
add tests, and record the decision. Until then this document is advisory only.

See also: `general/routing.md` (routing weights, arbiter, token load balancing).
