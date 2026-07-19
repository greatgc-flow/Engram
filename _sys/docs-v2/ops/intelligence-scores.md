# Intelligence Scores & Profile Policy

> Status: **DOCUMENTED ONLY** (2026-07-13). No orchestration/routing config was
> changed on the basis of this table. Recommendations below are for review; a
> governed R:10 round is required before any of the config changes land.
> Discussion: cx.deepthink + ag.deepthink, synthesized by cc; human directed
> "document first, apply later."
>
> **Update 2026-07-19:** §4.1 (ag.deepthink inversion) is RESOLVED — Option A
> empirically confirmed unavailable, Option B already live in orchestration.json.
> §4.2 (arbiter_models expansion) remains OPEN and unapplied (explicitly an R:10
> decision per its own text) — `routing-config.json`'s `arbiter_models` is still
> `["cc.fable", "cc.deepthink"]`, cx.deepthink not included.
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

### 4.1 ag.deepthink inversion — RESOLVED 2026-07-19 (Option B, empirically forced)
- **Option A confirmed UNAVAILABLE** [measured, 2026-07-19]: `agy models` does
  not list a "Gemini 3.5 Pro" entry (catalog is exactly: Gemini 3.5 Flash
  Low/Medium/High, Gemini 3.1 Pro Low/High, Claude Sonnet 4.6 Thinking, Claude
  Opus 4.6 Thinking, GPT-OSS 120B Medium) — a live canary confirms this is not
  just an unlisted-but-invokable model either: `agy --model "Gemini 3.5 Pro" -p
  "..."` fails hard with `Error: invalid --model "Gemini 3.5 Pro": model Gemini
  3.5 Pro is not recognized as a known model or custom model in settings`.
  Option A is not a live choice through this CLI; do not re-propose it without a
  new agy version/catalog change.
- **Option B is therefore the only viable path, and is already applied**:
  `orchestration.json`'s `ag.deepthink` profile carries a `profile_intent` block
  (`selection_basis: "resilience_over_external_composite"`,
  `tier_score_exception.status: "accepted_policy_exception"`) keeping Gemini 3.1
  Pro at `ag.deepthink` for long-context/multi-turn/tool-call resilience rather
  than raw composite score. No further action needed on this sub-item.

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

## 4.5 Measured cx context capacity (DIR-004: `measured` supersedes external `declared`)

Live measurement 2026-07-13 (operator OK'd token spend) resolving an external
`declared` claim (a ChatGPT screenshot: "GPT-5.6 API context window = 1,050,000
tokens / 128k output") against our actual tooling:

| Source | cx (gpt-5.6) context | Kind |
|---|---|---|
| ChatGPT / API spec | 1,050,000 tok | `declared, external, unverified` |
| `codex debug models` (our CLI) | **272,000** (`context_window`=`max_context_window`) | `machine-reported` |
| single `codex exec` input hard cap | **1,048,576 chars ≈ 258k tok** (`input_too_large`, model-agnostic — 5.4 rejects identically) | `measured` |
| sol live needle-in-haystack | ingested **248,371 input_tokens**, retrieved a needle at 92% depth | `measured` |

**Conclusion (governs routing, DIR-004 measured>declared):** the 1.05M figure is a
raw API-tier number **not reachable through our Codex CLI** — a single `exec` input
hits the ~1 MiB char wall (~258k tok) first, and the CLI reports a 272k window.
(The 272k window can still fill across multi-turn history/tool outputs, but no single
injected document exceeds ~258k tok.) Effort (low..ultra) does **not** change context;
capacity is flat ~272k across sol/terra/luna. Consequence: **there is no usable
"bigger-context" cx specialty via our CLI** — the earlier gpt-5.4 (declared 1M)
candidate is withdrawn (same 1 MiB input wall + lower reasoning tier). The only
unused higher lever is sol `max`/`ultra` effort (context-flat; quality delta vs
`xhigh` is unmeasured → a T44 `capability-core` question). Higher efforts are
live-invocable (confirmed). This is a worked example of
[`capability-leveling.md`](capability-leveling.md): a real external declaration,
overridden by our measured operational reality.

## 4.6 Measured file-write fidelity — first cross-peer empirical (DIR-004)

First real capability-canary run (operator-approved, 2026-07-13/14) of
`direct_file_write.safe_utf8.v1` (the T21 agentic canary: UTF-8 byte roundtrip,
targeted + 50 KB partial edit, CRLF/LF/BOM preservation, forbidden-path truthful
failure, scope discipline) across the three deepthink profiles. Records live in
the empirical ledger `_sys/ai/knowledge/peer-capability-scores.jsonl` (7-day TTL).

| Profile | Model / runtime | Score | Verdict | Failed subcheck |
|---|---|---:|---|---|
| `cx.deepthink` | GPT-5.6 Sol (codex) | **100** | **CERTIFIED** (3 consecutive passes) | — |
| `ag.deepthink` | Gemini 3.1 Pro (agy, PTY) | 80 | fail (not certified) | `line_endings_and_bom` — agy normalizes CRLF |
| `cc.deepthink` | Claude Opus 4.8 (claude CLI) | 65 | fail (not certified) | `unicode_byte_roundtrip` — `roundtrip_utf8.txt` bytes not preserved |

**This is the AGENTIC file-write FIDELITY axis, NOT reasoning.** It measures how
faithfully each peer's CLI/file tooling round-trips bytes — a real
`agentic_reliability` characteristic, but orthogonal to the §1 external reasoning
composite (Fable ~60 / Sol ~59 / Opus ~56 / Gemini 3.1 ~46). Per DIR-004
**do-not-reconcile-different-scales**: a low fidelity score is NOT a low
intelligence claim, and the two rulers must never be merged. The measured
ordering here (cx > ag > cc) even inverts the declared composite — precisely why
[`capability-leveling.md`](capability-leveling.md) insists on per-axis measurement
over a single scalar.

Actionable (measured, not guessed): for **byte-exact** file operations, codex
(cx) is the reliable choice today; the claude CLI (UTF-8 roundtrip) and agy (CRLF)
each have a specific, reproducible fidelity gap worth a tooling fix. Only
`cx.deepthink` is CERTIFIED; ag/cc records are honest fails, not absent.

## 4.7 Measured capability-core (reasoning + code + agentic) — first run

First `capability-core.v1` run (operator-approved, 2026-07-14; budget flags
cap 10 / window 5h / floor 0.1, single pass each — NOT the 3-pass certified
aggregate). Three deterministic axes in one invocation: reasoning (four closed-
form arithmetic answers → `reasoning_answers.json`), code (patch `normalize_name`
→ `value.strip().lower()`, exact-diff oracle), agentic (the T21 file-fidelity
fixture).

| Profile | Model | reasoning | code | agentic | Note |
|---|---|---:|---:|---:|---|
| `cx.deepthink` | GPT-5.6 Sol | 100 | 100 | 100 | all axes clean |
| `cc.deepthink` | Claude Opus 4.8 | 100 | 100 | 68 | agentic = the §4.6 UTF-8 roundtrip gap |

**Honest limitations (DIR-004):**
- The **reasoning** canary is four trivial arithmetic questions — both peers max
  it, so it does **not discriminate** reasoning capability. It proves the harness
  works, not that Sol == Opus at reasoning. A harder, still-deterministic reasoning
  suite is required before this axis can inform **D1** (arbiter reasoning-fitness).
- The **code** axis uses the exact-patch oracle (T46) — it rewards the canonical
  patch, not any functionally-correct one.
- Single pass only; `min-of-3` certification not run.
- `ag.deepthink` is **absent** here: `default_core_invoker` uses the std subprocess
  driver, but agy is PTY-only — capability-core needs the PTY invoker wired (a gap;
  T42's PTY driver exists but isn't yet plumbed into capability-core). Backlogged.

Net: on reasoning + code both are tied (and the reasoning bar is too low to trust);
the only measured differentiator remains agentic file-write fidelity (§4.6).

## 4.8 Re-measurement with a harder reasoning suite — the discrimination finding

After T47 replaced the trivial arithmetic with four multi-step closed-form
problems (`((7^4 mod 100)*13+45) mod 1000` = 58; a two-leg average-speed = 36;
count 1..100 divisible by 3 or 5 but not 15 = 41; `0x2F` = 47) and wired the PTY
driver so agy can run, capability-core was re-run across all three deepthink
profiles (single pass, 2026-07-14):

| Profile | Model | reasoning | code | agentic |
|---|---|---:|---:|---:|
| `cx.deepthink` | GPT-5.6 Sol | 100 | 100 | 100 |
| `cc.deepthink` | Claude Opus 4.8 | 100 | 100 | 68 |
| `ag.deepthink` | Gemini 3.1 Pro (agy, PTY) | 100 | 100 | 100\* |

\* ag agentic was **80** in the §4.6 T21 spike (CRLF fail) but **100** here —
the agy line-ending result is **not stable** (non-deterministic CRLF handling);
untrustworthy until a 3-pass `min-of-3` confirms it.

**Headline finding (honest, DIR-004):**
1. The reasoning + code canaries **do not discriminate** these frontier models —
   all three, *including the declared-weakest* (Gemini 3.1 Pro, external composite
   ~46), score a perfect reasoning 100 / code 100. The four "harder" problems are
   still trivial for frontier models.
2. So the declared composite ordering (Fable ~60 / Sol ~59 / Opus ~56 / Gemini
   ~46) is **NOT reproduced by measurement** — our canaries are too easy to expose
   any reasoning gap.
3. The only axis that shows any difference is agentic file-write fidelity, and it
   is **mildly flaky** for agy. **CORRECTED (2026-07-14, after artifact review —
   the earlier "10/80/80/100 genuinely non-deterministic" claim was WRONG):** the
   retained *complete* ag.deepthink observations are **95 / 80 / 80** — the 80s
   fail `line_endings_and_bom` (CRLF), the **95 passes it cleanly**, so agy is
   mildly flaky on CRLF preservation in an **80–95 band**, NOT a 10→100 collapse.
   The alarming **"10" was a PTY DEADLINE timeout artifact** (a 300 s-deadline run
   with empty stdout + partial artifacts, mis-scored as a capability 10 because
   `PtyCompletedProcess` dropped the `timed_out` flag), and it was *caused* by the
   T49 prompt-via-file change roughly **doubling agy's wall time** (100–149 s →
   252–300 s) while not fixing CRLF. No `--characterize` aggregate was ever written
   (the run was killed), so the four-number sequence conflated separate runs + a
   timeout. Honest verdict (cx + ag consensus): **agy is mildly-flaky-80–95 on
   CRLF, not broken; the harness corrupted the measurement.** A trustworthy agy
   agentic score needs 3 complete same-runtime runs after the harness fixes
   (timeout no longer scored as capability; a byte-exact prompt-delivery + seeded
   config home — see backlog T51). cc.deepthink (Opus) remains a stable ~68 on the
   same axis (its own UTF-8-roundtrip gap).

   **FINAL clean re-measurement (2026-07-14, fixed harness — inline delivery, 600 s
   ceiling, timeout-as-transport-unstable):** `--characterize 3` on ag.deepthink =
   **runs [80, 80, 80], evidence_state `stable_failed`, range 0**, each 66–94 s (vs
   the 252–300 s prompt-file runs — inline speed restored, no timeouts). So agy is
   **NOT flaky** — it is **stable at 80 with a single reproducible limitation: it
   does not preserve exact CRLF line endings** (`line_endings_and_bom`), while
   passing UTF-8 roundtrip, targeted + 50 KB partial edit, truthful failure, and
   scope every time. The earlier lone `95` was an outlier; the honest result is a
   **stable CRLF-preservation gap, not non-determinism** — and a clean validation of
   the T49 harness fixes.
4. **Consequence for D1:** measurement **cannot yet rank peers on reasoning**, so
   the Sol-as-arbiter decision remains undecidable from local data. Replacing the
   declared composite for reasoning-based routing needs a genuinely hard,
   discriminating benchmark (competition-level math / multi-hop logic / long
   deductions) — a substantial undertaking well beyond these canaries. Until then,
   the declared composite stays the (non-routing) bootstrap and D1 stays an
   architecture/taste call, not a measured one.

The measurement **infrastructure** is complete and honest; what it reveals is that
easy probes can't separate frontier reasoning — itself a valuable, DIR-004-correct
result (measured absence of a gap, not a guessed ranking).

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
