# Capability Leveling — TDD-Ready Specs (T41–T45)

> Status: **DECIDED, TDD-READY** (2026-07-13). Per-item detailing of every backlog
> item spawned by [`capability-leveling.md`](capability-leveling.md) (T41–T45),
> taken to the point just before writing tests — the same bar used for
> [`profile-policy-decisions.md`](profile-policy-decisions.md) (D1–D9).
> Consensus: cx.deepthink (spec) + ag (PTY/quota/DIR-004 cross-check) + cc.fable synthesis.
> **No config or code is changed by this document.** Each item is an independent TDD round.
> Every cited function/signature was verified to EXIST in live code before enshrining here.
> Companion: [`capability-leveling.md`](capability-leveling.md).

---

## 0. Human decisions still required (fail-closed until ratified)

These are **NOT** designed away — they are genuine architecture/taste calls. Every
item below ships **disabled / fail-closed** by default; TDD covers *injected* values,
never a guessed default (DIR-004).

| # | Unratified value | Blocks | Default until ratified |
|---|---|---|---|
| H1 | numeric **capability-measurement reserve floor** (quota fraction below which auto-measure is denied) | T44 execution | **RATIFIED 2026-07-20: reserve_floor=0.25** (see below) |
| H2 | **budget cap + window** for capability canaries | T44 execution | **RATIFIED 2026-07-20: budget_cap=4, budget_window_hours=12** (see below) |
| H3 | **premium/arbiter measurement allowlist** | T44 premium spend | empty (no premium auto-measure) |
| H4 | **canonical cross-provider tokenizer** for 8k/32k/128k payload construction | T44 long_context | **conservative byte→token fallback ratio** (ag), never crash |
| H5 | **non-neutral `bulk_fitness` formula + bounds** | T45 live weighting | neutral 1.0 for every profile |
| H6 | calibrated **quality-score floors** for D5 | Phase 3b | presence-only gate (no numeric floor) in shadow |

Nothing in T41–T45 activates D1 or D5 on live routing. Phase 3b (D1 re-decision +
calibrated D5) remains a separate R:10 round.

### H1/H2 ratification (2026-07-20)

Ratified via 3-way independent review (ag, cx, cc.fable) + explicit user sign-off,
triggered by a live P0: `hub.py freshness-sweep` (T81) found cc.effort's declared
model (`claude-sonnet-5`) CONTRADICTED against a stale 2026-07-12 observed-models
capture, structurally unfixable while `canary_config` stayed absent/fail-closed.

`orchestration.json.canary_config`: `budget_cap=4`, `budget_window_hours=12`,
`reserve_floor=0.25`. cap=4 (ag+cx unanimous — cc's 4 tier profiles + no free
model-enumeration command means cap=3 would falsely CONTRADICT the omitted 4th
profile). window=12h (cc.fable's arbitration — a 24h window lets one complete cc
fan-out camp the global cap for a full day and structurally starves cx across
sweep cycles; 12h lets cc's reservations expire before the next ~20h sweep tick).
reserve_floor=0.25 (cx's grounding, fable concurred — matches the strictest
existing `shared_quota_reserve` family value; checked per-subject, never a
cross-peer aggregate). Full reasoning + evidence: `_sys/ai/policy-decisions.json`
decision `h1-h2-canary-budget-ratification-2026-07-20`; commit `f1a5c9d`.

---

## 1. Dependency graph & phasing

```
T41 fingerprint ─────┐
                     ├─ T43 resolver/overlay ──┬─ T45 shadow gate
T42 PTY feasibility ─┘                         │
                                                └─ T44 empirical records
T44 unified budget ──> T42 executing spike (gates canary spend)
T44 long-context capacity guard ──> T45 context-fit evidence
```

| Item | Phase | Token spend | Ships enabled? |
|---|---|---|---|
| T41 fingerprint widening | 1 | none | yes (pure validation) |
| T43 declarations + resolver + overlay + check | 1 | **none** (operational reuse only) | yes (read-only) |
| T42 ag PTY harness spike | 1.5 | ≤3 explicit ag invocations | dry-run default; `--execute` gated |
| T44 unified budget + canaries | 2 | budgeted | **fail-closed** (H1/H2/H3) |
| T45 shadow purpose-fitness + D5 | 3a | none (shadow) | shadow-only, never routes |

New files these specs create (do not exist yet — planned):
```
_sys/ai/capability-declarations.json    (T43, governed)
_sys/checks/check_capability.py         (T43, resolver + check)
.ai/capability-reality.json             (T43, machine-generated overlay)
_sys/checks/canary_budget.py            (T44, shared budget ledger API)
.ai/canary_budget.json                  (T44, machine-generated ledger)
```

---

## 2. Per-item specs

### T41 — widen the T21 subject fingerprint (Phase 1, no tokens)

**Verdict:** implement. Legacy records become **stale, never migrated** (no synthesized values, append-only history preserved).

**Files:** `_sys/checks/check_peer_capability_canary.py` — extend `resolve_runtime_fingerprint()` (L577) and `_same_runtime()` (L387); bump `runtime_fingerprint` `schema_version` → `2`.

**Canonical fingerprint tuple** (persisted under `runtime_fingerprint` in `peer-capability-scores.jsonl`):
```json
{
  "peer": "cx", "profile": "deepthink",
  "model_id": "gpt-5.6-sol", "reasoning_effort": "xhigh",
  "adapter": "CodexAdapter",
  "invoke_args": ["exec","{query}","--json","-c","sandbox=\"workspace-write\""],
  "profile_config_sha256": "<64 lowercase hex>",
  "binary": {"exists": true, "sha256": "<sha256>"}
}
```
Sources: `peer/profile` = target; `model_id` = normalized `model_id`/`runtime_model`; `reasoning_effort`,`profile_args` = orchestration profile block; `adapter` = normalized `adapter_class`; `invoke_args` = effective node `invoke_args`; `profile_config_sha256` = SHA-256 of the **raw** `hub_nodes[].profiles[profile]` object as canonical JSON (`sort_keys=True`, compact separators, UTF-8); `binary.sha256` = existing `check_cli_reality.fingerprint(real_binary(...))`.

**Rules (validator):** `profile_config_sha256` = 64 lowercase hex; `invoke_args` = JSON list; `reasoning_effort`/`adapter`/`model_id` non-empty strings; `binary.exists is True` + non-empty SHA. `_same_runtime` requires equality of **every** member. `is_capability_record_valid(..., expected_runtime_fingerprint=...)` returns `False` on any mismatch → resolver falls to the next tier. A legacy record missing any new member is invalid/stale.

**Constraint (DIR-004):** the fingerprint must **not** include D3 declared `intelligence_evidence` — it may invalidate a record only because the raw profile object changed.

**Tests:** `test_same_runtime_rejects_same_model_binary_different_reasoning_effort`, `..._rejects_different_adapter`, `..._accepts_identical_v2_tuple`, `test_legacy_runtime_fingerprint_is_invalid_and_stale`, `test_record_with_changed_profile_config_hash_falls_back_from_empirical`, `test_resolve_runtime_fingerprint_hashes_raw_profile_config_deterministically`.

---

### T43 — declarations store + resolver + reality overlay + check (Phase 1 KEYSTONE, no tokens)

**Verdict:** implement fully; zero token spend (operational reuse only).

**New governed file `capability-declarations.json`** (in `_sys/ai/`) — migrate **only** the seven existing D3 entries; do not infer others:
```json
{
  "schema_version": 1,
  "subjects": {
    "cx.deepthink": {
      "subject": {"peer":"cx","profile":"deepthink","deployed_model_id":"gpt-5.6-sol",
                  "reasoning_effort":"xhigh","adapter":"CodexAdapter"},
      "axes": {
        "legacy_external_composite": {
          "value": {"kind":"point","value":59.0,"approximate":true},
          "scale":"external_composite","source_kind":"declared","verification":"unverified",
          "source_ref":"_sys/docs-v2/ops/intelligence-scores.md#1-source-data-dir-004-declared-unverified",
          "as_of":"2026-07-13"
        }
      }
    },
    "ag.deepthink": {
      "subject": {"peer":"ag","profile":"deepthink","deployed_model_id":"Gemini 3.1 Pro (High)",
                  "reasoning_effort":"high","adapter":"AgyAdapter"},
      "axes": {"legacy_external_composite": {"value":{"kind":"range","min":46.0,"max":47.0,"approximate":true},
        "scale":"external_composite","source_kind":"declared","verification":"unverified",
        "source_ref":"_sys/docs-v2/ops/intelligence-scores.md#1-source-data-dir-004-declared-unverified","as_of":"2026-07-13"}},
      "measurement_feasibility": {"performance": {"status":"blocked_pending_pty_harness",
        "reason_code":"agy_pty_harness_uncertified","source_kind":"declared","verification":"unverified",
        "source_ref":"_sys/docs-v2/ops/capability-leveling.md#5.3","as_of":"2026-07-13"}}
    }
  }
}
```
`measurement_feasibility` is **declared policy metadata, never a score and never routing evidence**. Range values use `{"kind":"range","min":..,"max":..}`; points use `{"kind":"point","value":..}`.

**Resolver — new module `check_capability.py`** (in `_sys/checks/`)**:**
```python
resolve_capability_reality(orch, snapshot, declarations, score_entries, now) -> dict
```
Receives operational data from `snapshot.collect_snapshot()` profile rows only — **no subprocess / canary invocation permitted**. Per-subject, per-axis precedence: (1) valid matching `empirical_probe` → (2) operational `app_server|statusline|cli_live` → (3) `declared` → (4) `absent`. "Valid empirical" = `is_capability_record_valid()` true **and** T41 fingerprint matches exactly **and** latest for that subject/capability/suite **and** not revoked by a later same-fingerprint failure **and** not expired.

**Overlay — new machine-owned `.ai/capability-reality.json`** (per subject/axis): `effective_value`, `scale`, `source_tag`, `verification`, `evidence_band`, `reconcile_status`, `stale_evidence[]`. Bands: valid 3-run empirical=`CERTIFIED`; operational=`EXPLORATORY`; declaration=`DECLARED`; expired/mismatched w/ no lower fallback=`STALE`; none=`ABSENT`. **Stale→declared fallback:** expired empirical + a declaration → band `DECLARED`, the expired record kept in `stale_evidence`.

**Reconcile status** computed **only** when two records share the same `scale` + capability/suite identity: `MATCH` (normalized equal), `DRIFT` (comparable valid values differ), `CONTRADICTED` (newer same-scale failed/revoking record invalidates a certified one), `ABSENT` (no comparable pair). **External composite vs local suite always = `ABSENT`, never `DRIFT`.** (ag safeguard: `ABSENT` never transitions directly to `DRIFT` — no baseline to drift against.)

**Check rules (`check_capability.py` fails on):** malformed declarations / unknown subject-profile; missing `scale|source_kind|verification|source_ref|as_of`; illegal combos — legal set is `declared→unverified`, `empirical_probe→machine_observed`, `app_server|statusline|cli_live→machine_observed`, `absent→absent`; empirical record lacking a valid T41 fingerprint; expired empirical selected as effective; a cross-scale pair marked DRIFT/CONTRADICTED; **declared evidence consumed by routing**. (ag DIR-004 gap closed: a declaration with **no** corresponding empirical entry resolves to `ABSENT` and is **gated from execution — no default allow**.)

**Routing-never-consumes-declared — two mandatory tests + one convention:**
- `test_routing_modules_do_not_load_capability_declarations` — **AST guard**: reject imports or `capability-declarations.json` path literals inside routing decision functions.
- `test_declared_capability_values_do_not_change_routing_decision` — **runtime equivalence**: run `snapshot.select_load_balanced_peer()` with byte-identical inputs but distinct declared values; assert identical candidates, weights, selected profile, seed, and arbiter selection.
- **Convention (ag, closes the reflection hole):** capability gates MUST be static, AST-checkable calls — **no dynamic reflection (`getattr`) or string-based routing maps** for capability. Add to `ops/conventions.md`.

**Tests:** `test_declared_only_resolves_declared_band`, `test_valid_empirical_supersedes_declaration_as_certified`, `test_expired_empirical_reveals_declared_fallback`, `test_cross_scale_values_are_not_drift`, `test_missing_provenance_fails_capability_check`, `test_operational_snapshot_axis_is_zero_token_read_only`, + the two routing-boundary tests.

**Constraint:** D3 `intelligence_evidence` stays as compat/display metadata; migration **copies** its values into the new registry but never turns them into measured capability.

---

### T42 — ag/agy PTY-native canary harness spike (Phase 1.5, ≤3 explicit ag invocations)

**Verdict:** implement as a gated spike. Reuse the existing PTY transport + T21 artifact judging unchanged.

**File:** add `invoke_peer_native_write_pty()` to `check_peer_capability_canary.py`. It:
1. resolves the node via `_profile_node()` + `AgyAdapter.build_cmd()` (default `--dangerously-skip-permissions -p {query}` = non-interactive one-shot; **not** a REPL — verified);
2. calls `hub._ask_with_pty(cmd, node_id, timeout_sec, build_env(), quiet=True, ai_root=None, cwd=str(workspace))` — **ag refinement: `cwd` MUST be `str(workspace)`**, pywinpty rejects a `Path` (WinError). `ai_root=None` bypasses production lease/metric writes; `quiet=True` keeps logs off stdout;
3. success only if `timed_out is False` **and** `transport_error is None` **and** `exit_code in {0, None}`; sanitize `result.text` via `AgyAdapter.parse_output()`; cap retained stdout to 2000 chars; store `transport="pty"`, `elapsed_sec`, `exit_code`, `timeout_kind`, `transport_error` (all exposed by `_PtyAskResult`);
4. reuse `prepare_fixture()`/`build_prompt()`/`score_workspace()`/`build_score_entry()`/ledger unchanged.

**Entry:** `python _sys/checks/check_peer_capability_canary.py ag.deepthink --transport pty --passes 3 --execute`. `--transport pty` valid **only** for a node with `requires_pty=true`; `--execute` mandatory (else dry-run writes nothing).

**ag-specific handling (refinements):**
- `winpty` is a compiled C-extension → catch DLL-load/import failure gracefully (report `transport_error`, do not crash the check).
- run agy under an **isolated/disposable `AGY_CONFIG_HOME`** so the spike never pollutes the production session DB.

**Certification bar (ag refinement adopted — de-flake):** certified after **3 passing runs, retrying transient PTY timeout/transport errors (max 5 attempts total)** — a single transient Windows start-latency timeout must not reset genuine progress; a genuine score/hard-failure never retries. Each passing run needs: `passed is True`, `score >= PASS_SCORE` (95), no hard failures, valid T41 fingerprint, `invocation.transport == "pty"`, no timeout/transport error, on-disk fixture artifacts + `entry.json`. Max spend = 3 successful (≤5 attempted) explicit `ag.deepthink` invocations; dry-run = 0.

**Fallback (no runtime mutation of governed files):** declarations carry `measurement_feasibility.performance.status="blocked_pending_pty_harness"`; `check_capability.py` **requires** that explicit blocked declaration for the affected ag profiles (prevents "absent by neglect"); the overlay reports `blocked` until certification evidence exists; T45 treats these as **measurement-infeasible → allow (not stranded)**.

**Tests:** `test_pty_invoker_uses_hub_daemon_reader_transport`, `test_pty_invoker_sanitizes_agy_output_before_retention`, `test_pty_timeout_or_transport_error_cannot_pass`, `test_pty_artifacts_are_scored_by_same_t21_judge`, `test_three_passes_certify_transport_with_transient_retry`, `test_ag_blocked_feasibility_survives_failed_or_missing_spike`, `test_non_pty_profile_rejects_pty_transport`, `test_pty_cwd_is_cast_to_str`, `test_pty_import_failure_is_caught_as_transport_error`.

---

### T44 — unified budget ledger + capability-core / long_context canaries (Phase 2, budgeted, fail-closed)

**Verdict:** mechanically TDD-ready; **activation blocked on H1–H4** (reserve floor, cap/window, allowlist, tokenizer). Default disabled/fail-closed.

**New `canary_budget.py`** (in `_sys/checks/`) replaces `check_cli_canary.check_and_update_budget` + `record_budget_invocation`:
```python
reserve_canary_invocation(...); consume_canary_reservation(...); release_canary_reservation(...)
```
Single ledger `.ai/canary_budget.json` (`schema_version 2`), per entry: `reservation_id`, `kind` (`cli_canary|capability_core|long_context|pty_spike`), `subject`, `reserved_at`, `expires_at`, `state` (`reserved|consumed|released`), `reserved_invocations`, `actual_tokens`, `quota_source_tag`, `quota_remaining`, `reserve_floor`.

**Atomic contract (ag Windows refinement):** acquire an exclusive lock via a **separate lock file** (`_get_lock(ai_root,"canary_budget")` — NOT the JSON itself; Windows WinError 32 forbids replacing an open file) → prune expired → evaluate cap/window + reserve floor → append `reserved` → **atomic replace inside the lock** → invoke → consume/release. All reads/writes occur **within** the lock; lock-free readers must catch `PermissionError` and retry. Invocation is forbidden without a successful reservation; both `check_cli_canary.canary_probe()` and T21/T44 canaries call this API; explicit targets do **not** bypass. Deny (fail-closed) when quota is absent/non-numeric (`reason=quota_absent`) or at/below floor (`reason=quota_below_reserve_floor`).

**3P shared-pool (ag refinement):** a canary reservation on a 3P profile (`ag.opus`) must deduct from the **shared 3P pool** (same key as `ag.gptoss`); the ledger's `quota_source_tag` carries the shared-pool mapping and 3P canary spend is **reserve-gated** like bulk.

**`capability-core.v1`** (one invocation writes all artifacts in a disposable workspace):
- `reasoning_correctness`: 4 fixed closed-form answers in `reasoning_answers.json`, 25 pts each, exact normalized comparison.
- `code_fidelity`: fixed buggy fixture + hidden tests + allowlisted exact patch; 50 for all hidden tests pass, 50 for exact normalized diff; **no transcript judging**.
- `agentic_reliability`: T21-style files/schema/forbidden-path/truthful-failure; 0–100 from deterministic artifact checks.

Per-axis **aggregate across 3 runs = `min(run1,run2,run3)`** (ag AGREE: a capability is only as strong as its worst reliable run — never inflate). The record is valid only if all 3 runs produced complete judgeable artifacts + matching T41 fingerprints. Scores stay scores, not calibrated "high-capability" claims.

**`long_context.{8k,32k,128k}.v1`** (separate suite/length): seeded deterministic fact blocks + marker locations + a final recall-plus-combine question; 50 marker-recall + 50 combined-answer. **Guard before reservation AND invocation:** `requested_fixture_tokens <= machine-observed capacity.window_tokens` — only `app_server|statusline|cli_live` capacity qualifies, **declared context never authorizes**. `actual_tokens = null` unless a machine-owned usage field is captured (never derived from prompt length). Tokenizer missing → **conservative byte→token fallback ratio** (ag), never crash (H4).

Premium/arbiter require explicit `--execute --subject peer.profile` **and** allowlist membership (H3). **Phase 2 is shadow-only**: records + overlay may generate, no live route changes.

**Tests:** `test_budget_reservation_is_atomic_and_precedes_invocation`, `test_budget_cap_and_reserve_floor_deny_without_invoking`, `test_cli_canary_and_capability_canary_share_one_ledger`, `test_canary_budget_lock_file_is_separate_from_ledger`, `test_3p_canary_deducts_from_shared_pool`, `test_capability_core_scores_are_deterministic`, `test_core_aggregate_is_minimum_of_three_runs`, `test_long_context_rejects_unmeasured_or_insufficient_capacity`, `test_actual_tokens_stays_absent_without_machine_usage`, `test_missing_tokenizer_uses_conservative_fallback_not_crash`, `test_premium_measurement_requires_allowlist_and_explicit_execute`, `test_phase2_never_changes_live_route`.

---

### T45 — shadow purpose-fitness + D5 requirement-vector gate (Phase 3a, shadow only)

**Verdict:** implement in shadow. Live selection continues to use the current candidate list during Phase 3a.

**Insertion:** in `snapshot.select_load_balanced_peer()` (L1732), after gates 1–4 and before economics/headroom/pacing: gate **5 capability-requirement filter (shadow)**, **6 context-fit filter (shadow)**, then 7 economics, 8 weighted selection.

**Task requirement vector:**
```json
{"schema_version":1,"complexity":"low|medium|high",
 "requirements":{"reasoning_correctness":{"required":true},
   "code_fidelity":{"required":true},"agentic_reliability":{"required":true},
   "long_context_quality":{"required":true,"minimum_length_tokens":32000}}}
```
No vector → no capability gate. Phase 3a has **no numeric quality floor** — the gate tests **valid-measurement presence only** (calibrated floors = Phase 3b/H6).

**Missing-score policy** (feasibility source = `capability-declarations.json` `measurement_feasibility.performance.status`, resolved into the overlay — declared operational metadata, not evidence):
- `measurable` + missing valid empirical on a required axis → **`hard_remove`**.
- `blocked_pending_pty_harness` + missing → **`allow`** (ag not stranded).
- no candidates after simulated removal → **`fail_loud`** shadow event (no epsilon fallback weight).
- explicit target → **`warn_then_allow`**, never silently reject.

**Bulk fitness:** declaration-only = exactly **`1.0`** (neutral). A valid local empirical score MAY contribute a bounded multiplier **in shadow only**, computed from same-suite/same-axis data — **never `legacy_external_composite`**. Any non-1.0 multiplier needs H5.

**Shadow event** (appended via the existing routing-metrics path in `hub.py`):
```json
{"event":"capability_route_shadow","ask_id":"...","actual_profile":"ag.effort",
 "would_candidates":["cx.deepthink"],
 "removed":[{"profile":"cc.effort","axis":"reasoning_correctness","reason":"missing_score_measurable"}],
 "missing_score_policy":"hard_remove","empty_result":false,
 "explicit_target_override":false,"bulk_fitness":{"cx.deepthink":1.0},"driving":false}
```

**Tests:** `test_capability_shadow_never_changes_live_route`, `test_declaration_only_profile_has_neutral_bulk_fitness`, `test_feasibility_blocked_ag_profile_is_not_stranded`, `test_measurable_unmeasured_required_axis_is_shadow_hard_removed`, `test_shadow_empty_candidate_set_is_fail_loud`, `test_explicit_target_warns_then_allows`, `test_external_composite_never_enters_bulk_or_requirement_logic`.

---

## 3. Cross-cutting DIR-004 invariants (all items)

1. Declared/composite scores **never** enter a routing decision (T43 AST-guard + runtime-equivalence + no-reflection convention).
2. Different scales are **never** reconciled; a cross-scale gap is `ABSENT`, not `DRIFT`.
3. Unmeasured/absent quota or capacity → **deny** (fail-closed), never a guessed value.
4. `actual_tokens`/scores that cannot be machine-observed are `absent`/`null`, never `0` or derived.
5. Infeasible-to-measure (ag pre-PTY) is an **explicit declaration**, enforced by the check — distinct from absent-by-neglect.
6. Supersede-not-overwrite: measured decays to declared on expiry; append-only history.

---

## 4. Backlog linkage

Items **T41–T45** in `_sys/ai/backlog.json` (SSOT). Each `next_action` should be updated to
"TDD-ready — see capability-leveling-decisions.md §2". Phase 3b (D1 re-decision + calibrated
D5 + H5/H6) stays a future R:10 item, not in this set.
