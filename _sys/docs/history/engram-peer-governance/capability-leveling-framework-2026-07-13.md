# Capability Leveling Framework

> Status: **living** (design pillar) | Date: 2026-07-13 | Language: English (INV-19)
> Consensus: cx.deepthink (primary design) + ag (cross-check, PTY/quota focus) + cc.fable synthesis
> Governs: how each `(peer, profile, model, effort)` gets a capability *level*, and how routing consumes it by purpose.
> Supersedes-in-spirit: the single composite table in `ops/intelligence-scores.md` (that becomes the *declared bootstrap layer* under §4 here).

---

## 0. Decision summary

The current model-ranking is a **single external composite scalar** (Fable5~60 … Gemini3.1Pro~46), imported from the internet, `declared/unverified` (see `ops/intelligence-scores.md`). DIR-004 forbids routing on it, so the deferred routing items **D1 (Sol→arbiter)** and **D5 (complexity clamp)** are permanently blocked: they need *measured* scores that do not exist.

This framework replaces that scalar with a **capability level** that is:

1. a **vector**, not one number — MECE axes that stay independent (a big-context weak model must be distinguishable from a small-context strong model);
2. **evidence-qualified per axis** — `measured` supersedes `operational` supersedes `declared` supersedes `absent`, never reconciling different scales;
3. **consumed by purpose** — `bulk_fitness` / `arbiter_fitness` / `complexity_fitness`, each computed from only the axes it needs; economics never enters the capability score;
4. **built before it is used** — this round is **Phase 0 (documentation only)**. It does **not** activate D1/D5. It defines the honest measurement layer that will *later* let a human decide them.

Non-negotiable boundary: **routing consumes only valid measured/operational evidence. Declared/composite scores never enter a routing decision** (they bootstrap and display only).

---

## 1. Why not a single score

| Problem with a scalar | Consequence |
|---|---|
| Conflates orthogonal abilities | A 1M-context weak model outranks a 200k strong model on a *dense reasoning* task. |
| Conflates capability with cost | Load balancer sends hard tasks to cheap low-capability nodes, or protects the wrong profile. |
| One provenance for all abilities | Cannot mark "context measured, reasoning only declared" — DIR-004 needs per-axis provenance. |
| Cross-provider scale mixing | External composite 59 and a local suite 92 are *different rulers*; a scalar forces a false comparison. |

The level is therefore a small vector plus two envelopes, each axis independently sourced and provenance-tagged.

---

## 2. Capability axes (MECE)

A level is composed of four mutually-exclusive, collectively-exhaustive axis groups.

### 2.1 Performance vector (intrinsic ability)
Four sub-axes, each `0-100` **only within a fixed suite version** (see §6 on comparability):

| Sub-axis | Measures | Judged on |
|---|---|---|
| `reasoning_correctness` | closed-form logic/math/planning | exact expected answer |
| `code_fidelity` | patch a fixture so hidden tests pass | test pass + exact diff |
| `agentic_reliability` | write correct files, honor schema, refuse forbidden paths, fail truthfully | on-disk artifacts (T21-style) |
| `long_context_quality` | recall + combine facts across a long prompt | closed-form answer; measured **per length** `{8k,32k,128k}` |

Never judged on a transcript or by an LLM judge (§5.4).

### 2.2 Context envelope (capacity)
`window_tokens` + `bound_kind ∈ {machine_reported, lower_bound}`. A synthetic-prompt success that did not error is only a **lower bound**; asking a model its own window is **not evidence** (→ `absent`).

### 2.3 Resource envelope (economics — NOT part of the capability score)
`quota_families[] · remaining · reset · pacing · cost`. Kept **out** of the capability vector and **in** the purpose-fitness computation (§7). `cost` has no machine source → it is a **derived** figure (machine-observed token deltas × static rate table); when token deltas are unobservable it is `absent`, never `0`.

### 2.4 Identity / treatment (the subject key, §3)
Not a score — the tuple that a score is *valid for*. `effort` is a measurement **treatment**, not a capability bonus: the same model at a higher reasoning budget is a *different subject*, re-measured, not up-weighted.

> ag & cx both AGREE: mixing economics into capability would misroute complex work to cheap nodes; the four groups stay independent.

---

## 3. Subject identity & fingerprint

A score is valid only for a **subject tuple**:

```
subject = (peer, profile, deployed_model_id, reasoning_effort, adapter/runtime)
```

T21's `check_peer_capability_canary._same_runtime` today compares only `model_id + binary_sha`. It **must widen** to also fingerprint `invoke_args`, `reasoning_effort`, `adapter`, and the profile-config hash. A record whose fingerprint no longer matches the live subject is **stale** (falls back to the next evidence tier), not silently reused. (Backlog **T41**.)

---

## 4. Evidence model & precedence (DIR-004)

Two governed/append stores + one machine-owned overlay:

Planned paths (Phase 1 artifacts — do not exist yet in Phase 0):
```
_sys/ai/capability-declarations.json        (new, governed)
_sys/ai/knowledge/peer-capability-scores.jsonl  (exists — T21 ledger)
.ai/capability-reality.json                 (new, machine-generated)
```

| Store | File | Owner | Contents | Routing? |
|---|---|---|---|---|
| Declarations | `capability-declarations.json` | governed (human/R:10) | vendor model-card + the external composite; `source_tag=declared`, `verification=unverified` | **never** |
| Empirical ledger | `peer-capability-scores.jsonl` | append-only | `empirical_probe` local-canary results (T21 lineage) | yes (when valid) |
| Reality overlay | `capability-reality.json` | machine-owned (generated) | resolved effective vector per subject/axis + `MATCH/DRIFT/CONTRADICTED/ABSENT` | yes (read) |

### 4.1 Per-axis precedence
```
valid local empirical_probe  >  machine operational (app_server / statusline / cli_live)  >  declared  >  absent
```
Resolved **independently per axis** — `context` can be `machine_reported` while `reasoning` is only `declared`.

### 4.2 Do-not-reconcile-scales
External composite `59` and local suite `92` are **different rulers**. A gap between them is **not** a DRIFT and must never be "corrected". DRIFT/CONTRADICTED are computed **only within the same scale/suite** (e.g. a new measured run vs a prior measured run of the same `capability_id`).

### 4.3 Supersede-not-overwrite lifecycle
Measured records **supersede** declared without deleting it. When a measured record **expires** (`is_capability_record_valid`, 7-day TTL + fingerprint), the declared value **re-surfaces** as the fallback and the UI re-tags it `[decl]`. Declared is the permanent floor; measured is the temporary, decaying overlay.

### 4.4 Evidence band (display, calibrated later)
```
ABSENT → DECLARED → EXPLORATORY → CERTIFIED → STALE
```
This is an **evidence** band, not an ability band. Ability-band thresholds require task-outcome calibration and are **not guessed now** (DIR-004).

---

## 5. What to measure, how, at what cost

| Axis | Measurable now? | How | Cost |
|---|---|---|---|
| Context (peer) | **yes** | `snapshot.model_context_window`, `ag_statusline_stdin.log`, `codex debug models` | free (already read) |
| Context (session) | **no** for ag | agy SQLite conversation-DB schema unverified (D9) | needs a measurement spike |
| Resource/quota | **yes** | `_codex_rate_limits`, statusline, quota-family map | free |
| Cost | **derived** | token delta × static rate; `absent` if delta unobservable | free / absent |
| Performance | **new canary** (§5.1) | budgeted deterministic probe | tokens (Phase 2+) |

### 5.1 The performance canary
- `capability-core.v1` — one invocation exercising reasoning + code + agentic, scored **only** on deterministic artifacts (T21 lineage: file writes, schema, forbidden-path refusal, truthful failure). Three repeatability runs like T21.
- `long_context.{8k,32k,128k}.v1` — separate suites; **never run above the subject's measured capacity**.

### 5.2 Budget (hard bounds)
- Exactly **3 invocations / profile** for core certification; long-context is a separate, separately-approved 3.
- A **common budget ledger** — T21 does **not** currently use `check_cli_canary`'s ledger; unify them. Atomic reserve before invocation; **no auto-measure below the quota reserve floor**.
- Token metering is **TEST NEEDED**: record `actual_tokens` only when machine-observed, else `absent`.

### 5.3 AG (agy) measurement feasibility — ag's focal finding
agy on Windows is **PTY-only** (native `WriteConsole` console API). The current canary invoker uses plain `subprocess.run` → agy would hang/crash/emit nothing. Therefore:
- A **PTY-native canary harness** is required, reusing hub's `_ask_with_pty` daemon-reader queue. Once it exists, agy output **is** deterministically artifact-judgeable (AgyAdapter already sanitizes ANSI/CR/BS in `parse_output`).
- Peer-level context for ag **is** machine-measurable (statusline). Session-level context is **absent** (D9).
- **Verdict:** ag cannot join the *measured performance* level in Phase 1 or Phase 2. It stays **declared-only** until a dedicated **Phase 1.5 PTY harness spike** certifies the `pywinpty` path. (Backlog **T42**.)

### 5.4 What we do NOT do
No external LLM judge (reproducibility + provider bias). No scheduled fan-out of all profiles. Premium/arbiter measurement is **allowlist + explicit operator approval** only. During Phase 2 all results are **shadow-only**.

---

## 6. The level & cross-peer comparability

The level is the **evidence-qualified vector**, e.g.:

```json
{
  "subject": "cx.deepthink",
  "performance": {
    "reasoning": {"score": 92, "source_tag": "empirical_probe"},
    "code":      {"score": 88, "source_tag": "empirical_probe"},
    "agentic":   {"score": 95, "source_tag": "empirical_probe"},
    "long_context": {"32k": 90, "source_tag": "empirical_probe"}
  },
  "capacity":  {"window_tokens": 353400, "bound_kind": "machine_reported", "source_tag": "app_server"},
  "economics": {"quota_families": ["X"], "remaining": 0.92, "source_tag": "app_server"},
  "certification": "core_certified"
}
```

- Cross-peer comparison is valid **only** at the same `capability_id + suite version + fixture generation + judge version`.
- `standard/effort/deepthink` remain **per-peer intent labels**, not a cross-peer level.
- The D3 `intelligence_evidence` field is **not deleted now**: it is retained as `legacy_external_composite`, displayed `~59 [decl]`, and never placed in the same column as a local score. After enough measurement, `intelligence-scores.md` shrinks to a historical/bootstrap appendix.

---

## 7. Purpose-based routing consumption

Extends the `profile-policy.md §4` gate chain (state → terminal-exclusion → arbiter/bulk-role exclusion → shared-quota reserve → selection) with three capability gates:

```
1 state
2 terminal exclusion
3 arbiter/bulk role exclusion
4 shared-quota reserve
5 measured-capability requirement      ← new
6 context-fit requirement              ← new
7 live economics / headroom / pacing
8 weighted selection
```

### 7.1 Bulk
- Existing eligible set is preserved.
- A **measured** `bulk_fitness` acts **only** as a bounded weight multiplier.
- **Declaration-only profiles get neither bonus nor penalty (neutral 1.0)** — this prevents a migration regression that would drop every not-yet-measured profile.
- Headroom · pacing · cost remain the primary decision factors.

### 7.2 Arbiter (D1)
- A measured `arbiter_fitness` (reasoning + agentic-truthfulness) lets a profile **pass the capability gate** — it does **not** auto-grant `arbiter_models` membership.
- New-arbiter admission still requires: locally-certified arbiter axes **+** healthy invocation path **+** numeric headroom **+** provider/failure-family independence **+** its quota-family reserve **+** DIR-005 budget **+** a **separate R:10 decision**.
- Currently-configured Claude arbiters are **grandfathered** — the new declaration-only layer must not evict them.
- ∴ if Sol (`cx.deepthink`) tops local measurement, D1's *capability* gate is satisfied, but membership still waits on an **X-family reserve** design + provider-diversity architecture call.

### 7.3 Reserve
Reserve protects **role & scarcity, not capability**. Capability is an *input* to "who should hold a premium role"; membership is decided by protected-role/config; the reserve **fraction** comes from measured consumption/starvation telemetry, never from a high score. (3P nuance: `ag.opus` premium + `ag.gptoss` bulk share the `3P` pool → a `shared_quota_reserve` is mandatory, already configured.)

### 7.4 Complexity gate (D5) — with ag's refinement
A task carries a **requirement vector**:
```json
{"complexity":"high","requirements":{"reasoning":"high","code":"medium","long_context":"32k","agentic":"high"}}
```
D5 behaviour:
- On a hard task, a candidate that **could be measured** but lacks a valid measured score on a required axis is **hard-removed** (declaration-only == `missing_score`); below a calibrated floor is also hard-removed (no `headroom=0.01` epsilon survival).
- **ag's refinement (adopted):** a profile that is **feasibility-blocked** from measurement (e.g. ag before the PTY harness) is treated as **neutral/allowed**, NOT hard-removed — otherwise D5 would strand every ag profile the day it ships. The `missing_score_policy` is therefore: `hard_remove` for *measurable-but-unmeasured*, `allow` for *measurement-infeasible*.
- No eligible candidate → **fail loud**. Explicit operator target → warn-then-allow. First deployment is **shadow events only**.
- Declared/composite scores **never** enter this gate.

---

## 8. Progressive refinement & migration

### 8.1 File / config structure
```
_sys/docs-v2/ops/capability-leveling.md      this doc — the framework
_sys/ai/capability-declarations.json         (new) governed declared bootstrap (composite + model cards)
_sys/ai/knowledge/peer-capability-scores.jsonl   empirical ledger (exists)
.ai/capability-reality.json                  (new) generated resolved overlay
_sys/ai/orchestration.json                   keeps identity/effort/intent/class/quota-family only
_sys/ai/routing-config.json                  keeps purpose rules + calibrated thresholds only
```

### 8.2 Migrating the current table
1. Copy the composite records into the declarations registry, fixed to `external_composite`, `declared/unverified`.
2. Keep orchestration `intelligence_evidence` during the compatibility window.
3. A local empirical record **supersedes** (not overwrites) the declaration.
4. An expired measured record → `stale`; the declaration fallback re-surfaces.
5. Routing always reads **only** the valid measured/operational overlay.

A new check must verify: evidence provenance + subject identity; source-tag × verification combos; runtime/suite fingerprint; revocation on latest scored failure; expiry; declared-vs-measured scale compatibility; MATCH/DRIFT/CONTRADICTED/ABSENT; and the **contract that routing never consumes declared evidence**.

---

## 9. Phasing

| Phase | Output | Change kind | Spends tokens? |
|---|---|---|---|
| **0** | this framework, evidence boundary, purpose policy documented | docs only | no |
| **1** | normalize ctx/quota/cost sources + build resolver & overlay | config + check + snapshot + tests | **no** (reuses app_server/statusline/cli_live) |
| **1.5** | **PTY-native canary harness spike** (ag/agy via `pywinpty`, reuse `_ask_with_pty`) | code + tests (feasibility) | minimal, gated |
| **2** | budgeted `capability-core` + `long_context` canaries, append-only records | code + fixtures + tests + explicit probes | **yes**, budgeted |
| **3a** | evaluate purpose fitness + D5 in **shadow** | routing code/config + tests | routing only |
| **3b** | re-decide D1, activate calibrated D5 | **R:10** config decision + tests | as configured |

Phase 3 activates only when task-outcome + false-route telemetry is sufficient.

### MECE closure
```
profile identity/effort
  → axis-specific evidence (measured | operational | declared | absent)
  → valid effective capability vector
  → context/resource envelope
  → purpose-specific eligibility & fitness (bulk | arbiter | complexity)
  → existing state/terminal/role/reserve gates
  → auditable routing decision
```

---

## 10. Human taste calls (for R:10)

| # | Call | cx | ag | Recommended |
|---|---|---|---|---|
| 1 | Provider-diverse arbiter (Sol into `arbiter_models`) | yes-in-principle, Sol after measurement + X reserve | agree, deferred until X reserve (else bulk Codex starves Sol) | **Yes in principle; Sol admission deferred to D1 with an X-family reserve** |
| 2 | Auto-refresh premium/arbiter measurements | explicit/allowlist only | agree — explicit/allowlist only | **Explicit/allowlist only** |
| 3 | External LLM judge for scoring | no (reproducibility + provider bias) | strong NO — deterministic asserts only | **No** |

---

## 11. Backlog spawned

| ID | Item | Phase |
|---|---|---|
| T41 | Widen T21 subject fingerprint (effort/adapter/invoke_args/profile-config hash) + stale-on-mismatch | 1 |
| T42 | PTY-native canary harness spike for ag/agy (reuse `_ask_with_pty`); certify or keep ag declared-only | 1.5 |
| T43 | `capability-declarations.json` + resolver + `.ai/capability-reality.json` overlay + new check (no token spend) | 1 |
| T44 | Unify T21 + `check_cli_canary` budget ledger; `capability-core.v1` + `long_context.*` canaries | 2 |
| T45 | Shadow purpose-fitness + D5 requirement-vector gate (with `missing_score_policy` feasibility split) | 3a |
| D1/D5 | Re-decide with measured evidence (R:10) | 3b |

> This round changed **no config and no code** — it is the honest measurement layer's blueprint, not its activation.
