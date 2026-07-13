# Profile Policy — Taxonomy, Quota Economics, Load Balancing, Terminal Minimization

> Status: **DOCUMENTED** (2026-07-13). This is the MECE framework for the peer
> profile system. It describes current reality and names the intended model;
> the **config/code changes in §7 are DEFERRED to an R:10 governance round**
> (like T26) and are NOT applied by this document.
> Exhaustive design discussion: cx.deepthink + ag.deepthink; synthesized by cc.
> Companion: [`intelligence-scores.md`](intelligence-scores.md) (score table);
> [`../general/routing.md`](../general/routing.md) (routing weights / arbiter).

## 0. The MECE picture

Five mutually-exclusive, collectively-exhaustive dimensions describe every
profile. Read top to bottom; each answers a different question:

| Dimension | Question | Field / mechanism |
|---|---|---|
| **Taxonomy** (§1) | tier or specialty? | `profile_class` (proposed) |
| **Capability** (§2) | how smart, comparably? | tier intent + `measured_intelligence_score` (proposed) |
| **Quota economics** (§3) | whose budget does it spend? | `quota_family` (C/F/G/3P/X) |
| **Load balancing** (§4) | may auto-routing pick it? | routing_state + arbiter/bulk/reserve gates |
| **Terminal minimization** (§5) | does it protect cc's tokens? | `terminal_hard_exclude` |

## 1. Profile taxonomy (naming criterion)

Two classes. This resolves the "why are some profiles `standard/effort/deepthink`
and others `fable/opus/gptoss`?" question.

- **TIER profiles** — named exactly `standard` / `effort` / `deepthink`. The
  systematic per-peer capability ladder: a monotonically increasing rung of
  reasoning/effort, one native provider model per rung, present on every enabled
  peer, and the **default candidate set for bulk auto-routing**.
- **SPECIALTY profiles** — any name outside that triad (`fable`, `opus`,
  `gptoss`, ...). Off-ladder profiles that exist for a specific **role or
  economic reason** (premium arbiter / manual premium / cheap bulk overflow) and
  are named by model/role because they do not fit the tier semantics.

Current assignments (cx+ag agree they are consistent):

| Profile | Class | Why |
|---|---|---|
| `cc/ag/cx . standard/effort/deepthink` | TIER | per-peer ladder, native models |
| `cc.fable` (Fable 5) | SPECIALTY | premium DIR-005 arbiter |
| `ag.opus` (Opus 4.6, manual_only) | SPECIALTY | manual premium / escalation |
| `ag.gptoss` (GPT-OSS) | SPECIALTY | cheap bulk overflow, off the Gemini ladder |

Note `cx.deepthink = gpt-5.6-sol` is correctly a **TIER** profile even though Sol
is a specific top model — it is Codex's highest native rung, not an off-ladder
specialty. `ag.opus` and `cc.fable` are the **same class** (both premium
specialty), which is why both are kept out of bulk routing (§4).

## 2. Capability tiering

- **Intent, not just score.** A TIER ladder should be monotonic in *verified task
  fitness* (`standard < effort < deepthink`), which is broader than a single-shot
  composite benchmark. Where a composite score inverts the intent, the intent
  wins **if** there is a structural reason.
- **The ag.deepthink "inversion" is intentional.** By the supplied composite
  (see intelligence-scores.md), `ag.deepthink` = Gemini 3.1 Pro (~46) scores
  *below* `ag.effort` = Gemini 3.5 Flash (~50). Both peers' resolution: **keep
  3.1 Pro at deepthink** (ag: Option B) because it brings a ~2M-token context,
  higher tool-call fidelity, and better multi-turn instruction-following —
  structural advantages a single-shot score does not capture. This is a
  documented, deliberate exception, not a bug.
- **Cross-peer capability is separate from the local label.** "deepthink" is a
  per-peer intent label; across peers the actual capability differs sharply
  (cx.sol ~59 > cc.opus ~56 > ag.3.1pro ~46). Routing that wants "the smartest
  available model" must key on a measured capability value, not the tier word —
  hence the proposed `measured_intelligence_score` field (§7), stored
  `declared, unverified` per DIR-004 until locally benchmarked.

## 3. Quota-family economics

Each profile spends from exactly one **quota family**. Same-peer profiles can sit
on *different* families — that decoupling is the whole point.

| Family | Pool | Profiles |
|---|---|---|
| `C-` | Claude first-party subscription | `cc.standard/effort/deepthink` |
| `F-` | Claude **Fable** distinct premium pool | `cc.fable` |
| `G-` | Gemini first-party native | `ag.standard/effort/deepthink` |
| `3P-` | Antigravity **third-party** premium+bulk weekly pool | `ag.opus`, `ag.gptoss` |
| `X-` | Codex native | `cx.standard/effort/deepthink` |

- **Why ag's specialty profiles sit on 3P, not G:** Antigravity hosts both
  first-party Gemini (the `G` pool) and third-party models — Claude Opus 4.6 and
  GPT-OSS — which draw from a separate, constrained `3P` weekly pool. Decoupling
  them means heavy bulk load on `ag.effort` (G pool) **physically cannot drain**
  the 3P budget, and vice-versa. This is why "3P-opus usage is a separate pool."
- **Shared-quota invariant (mandatory reserve):** when a premium SPECIALTY
  profile shares a family with a bulk-eligible profile — the canonical case is
  `ag.opus` (arbiter/escalation) sharing `3P` with `ag.gptoss` (bulk) — a
  `shared_quota_reserve` is **required**. Without it, gptoss bulk generation
  would consume the weekly 3P budget and starve the opus arbiter. The reserve
  clamps the bulk profile's headroom to 0 for `--to auto` once the family's
  remaining share drops below the reserve floor; `reserve_for` profiles are never
  clamped.
- **Known mapping defect (backlog):** `snapshot._quota_family_for_profile`
  contains a **stale `ag.sonnet -> 3P-`** entry, but `ag` has no `sonnet` profile
  in orchestration.json. Harmless today (no such profile) but should be removed.

## 4. Load-balancing policy (MECE decision table)

`--to auto` eligibility is the ordered conjunction of these gates. They are
mutually exclusive as *reasons to exclude* and collectively exhaustive:

1. **State gate** — `routing_state != "eligible"` → **excluded** (catches
   `blocked` and `manual_only`, e.g. `ag.opus`).
2. **Terminal gate** — `terminal_hard_exclude == true` AND peer is the active
   terminal (cc) → **excluded** (§5).
3. **Arbiter/bulk gate** — profile in `arbiter_models` (`cc.fable`, `cc.deepthink`)
   OR in `bulk_exclude_profiles` (`ag.opus`) → **excluded from bulk** (premium
   kept for dissent/high-risk/manual only).
4. **Reserve gate** — profile shares a family protected by `shared_quota_reserve`,
   that family's remaining share is below the reserve floor, and the profile is
   not in `reserve_for` → **excluded** (protects the premium sharer).
5. **Selection** — of the survivors, pick by headroom + pacing + cost bias
   (seeded weighted-random).

- **The cx.deepthink (Sol) question:** Sol (~59) is co-top with Fable, but it is
  a TIER profile, so it passes all gates and is currently **bulk-eligible** —
  meaning the smartest Codex model can be spent on routine work. If the operator
  wants Sol reserved for hard reasoning, **add `cx.deepthink` to `arbiter_models`**
  (§7); this both protects its tokens and adds a non-Claude voice to the arbiter
  pool. cx cautioned: settle the bulk-vs-arbiter tradeoff (losing Sol from bulk
  shrinks cheap high-capability capacity) before changing membership.

## 5. Terminal token minimization

- **Invariant:** the terminal (`cc`) orchestrates and must minimize its own token
  spend — it delegates implementation, bulk file reading, and heavy reasoning to
  peers, and preserves its context window + rate limits to keep the unbroken
  human conversation loop alive. `terminal_hard_exclude=true` enforces this for
  `--to auto`: cc is never an auto-routing bulk target.
- **Enforcement leaks (backlog):** `terminal_hard_exclude` only guards the
  `--to auto` *selection*. It does NOT protect the terminal from (a) explicit
  `--to cc.*` asks, or (b) subagent spawns that default to cc, or (c) the
  `same_peer_downward_only` fallback (an explicit `cc.effort` that fails falls to
  `cc.standard`, still burning terminal context). Closing these is a routing
  change, not covered here.

## 6. Findings surfaced (for backlog, not fixed here)

- Stale `ag.sonnet -> 3P-` mapping in `_quota_family_for_profile` (§3).
- Terminal-minimization leaks: manual `--to cc.*`, subagent cc default,
  downward same-peer fallback (§5).

## 7. Deferred to an R:10 governance round (NOT applied here)

The operator chose "document first." Applying any of the below is a separate
governed round (re-measure live where relevant, edit atomically, add tests):

1. **orchestration.json** — add explicit per-profile fields: `profile_class`
   (`tier`|`specialty`), `measured_intelligence_score` (float, `declared,
   unverified` + `score_source`), and `quota_family` (`C`|`F`|`G`|`3P`|`X`). This
   replaces string-matching heuristics with declared data.
2. **snapshot.py** — read `quota_family` from orchestration.json instead of the
   hardcoded `_quota_family_for_profile`; drop the stale `ag.sonnet` entry.
3. **routing-config.json** — consider adding `cx.deepthink` (Sol) to
   `arbiter_models` (§4) so the arbiter pool reflects measured capability, and a
   `complexity_threshold` clamp that steers hard tasks to high-score profiles
   (§2 / intelligence-scores.md).
4. **ag.deepthink** — no model change recommended (keep 3.1 Pro, §2); instead
   document the tier's intent (context/tool resilience) in orchestration.json.

## 8. Taste / architecture calls for the human

- Whether to reserve Sol (add to arbiter_models) or keep it in cheap bulk (§4).
- Whether to expand the DIR-005 arbiter pool beyond the Claude family at all
  (adding a non-Claude arbiter changes the tie-break character).
- How strictly to close the terminal-minimization leaks in §5 (some manual
  `--to cc.*` use is legitimate operator choice).
