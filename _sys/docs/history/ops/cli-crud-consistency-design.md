# CLI-CRUD Consistency Design (E2E & Operations)

**Author:** ag (design) — first written out-of-band during the design ask; the
LL-20260703-005 guard CAUGHT the write (GOVERNED_MUTATION_VIOLATION, _sys/docs now
in the manifest), and the terminal reviewed + committed it here (correction: the
r-8b3b model-operand validator is NOT a future gap — it SHIPPED this session as
hub_peer.validate_model_operand, W2). cx review pending.
**Date:** 2026-07-04  
**Context:** P:\_sys\ai\orchestration.json, P:\_sys\checks\check_cli_reality.py, P:\_sys\checks\validate_peer_config.py, P:\_sys\core\snapshot.py  
**Directive Enforcement:** DIR-004 (Measured-Only Claims).

## 1. Goal & Architecture

To construct a **Mutually Exclusive, Collectively Exhaustive (MECE)** consistency-check framework covering the full lifecycle (CRUD) of our peer CLIs (`cc`, `cx`, `ag`), their models, and their usage quotas.

The core problem is **Drift**: when a real binary updates, when an upstream provider deprecates a model, or when a quota boundary shifts, the orchestration configuration (our declared intent) can silently decouple from the CLI's actual runtime behavior. Since `--help` output is merely a hypothesis, our verification must rely purely on empirical measurements (DIR-004) to ensure the system state flows unbroken from **Config → Adapter → Real CLI → Telemetry → User View**.

---

## 2. Q1: CLI Lifecycle CRUD (Binary Level)

The lifecycle of the underlying binaries (`claude.cmd`, `codex.cmd`, `agy.exe`).

### (a) ADD a New Peer CLI
**Standard Scenario Steps:**
1. **Binary Placement:** Place the new binary in the workspace (e.g., `_sys/env/nodejs/npm-global/` or `_sys/tools/`).
2. **Orchestration Registration:** Add a new `hub_node` of type `peer` to `_sys/ai/orchestration.json`. Define `invoke` path, base `invoke_args`, and minimum `profiles` (standard, effort, deepthink).
3. **Adapter Implementation:** Create the Python adapter (e.g., `NewPeerAdapter`) mapped in orchestration.
4. **Identity Registration:** Add to `_sys/ai/peers.json` (assign `node_ids`).
5. **Docs:** Create `_sys/docs-v2/specific/<peer>.md`.
6. **Check Integration:** Update `REAL_BINARIES` dict in `_sys/checks/check_cli_reality.py`.

**Verification & Check:**
- `validate_peer_config.py` enforces the orchestration vs. peers.json vs. docs cross-check.
- `check_cli_reality.py` verifies the binary exists at the `invoke` path and probes it.

**Invariant:** A peer declared `enabled: true` MUST possess an executable binary on disk and be resolvable in the registry.
**Failure Mode if Skipped:** Missing binary leads to runtime `FileNotFoundError` during invocation; missing registry leads to `validate_peer_config.py` CI failure.

### (b) UPDATE/Upgrade a CLI Version (e.g., codex 0.142 → 0.143)
**Standard Scenario Steps:**
1. **Binary Replacement:** `npm install -g @x/codex` or equivalent.
2. **Detection:** Run `check_cli_reality.py`.

**Verification & Check:**
- `check_cli_reality.py` calculates `sha256` in `fingerprint()`. If fingerprint changes, it's an update.
- `probe_version()` reads the new semantic version. If the new version != `declared_version` (if tracked), it emits a **DRIFT (P1)** severity overlay.
- Re-validate the `cli-reality-observed.json` verified models capture, as the new binary may have altered its supported model list.

**Invariant:** A modified CLI binary fingerprint invalidates prior behavioral assumptions until re-verified.
**Failure Mode if Skipped:** Silent breakage if the new CLI renames a flag or deprecates a default model.

### (c) DELETE/Retire a CLI
**Standard Scenario Steps:**
1. **Orchestration:** Set `"enabled": false` in `orchestration.json` for the peer.
2. **Docs:** Prefix `_sys/docs-v2/specific/<peer>.md` with `SUSPENDED`.
3. **Registry:** Leave in `peers.json` but update to `enabled: false`.

**Verification & Check:**
- `validate_peer_config.py` verifies no routing rules (`collaboration_loop_bindings.json`) point to profiles of a disabled peer, preventing black-hole routing.
- `validate_peer_config.py` verifies documentation accurately reflects the SUSPENDED state.

**Invariant:** Disabled peers MUST NOT exist in any active routing topology or protocol voter lists.

---

## 3. Q2: Model Lifecycle CRUD

Models mapped within a peer's `profiles` block.

### (a) ADD a Model to a Peer
**Standard Scenario Steps:**
1. **Config Update:** Add a new profile in `orchestration.json` (e.g., `"model_id": "claude-fable-5"`).
2. **Provenance Capture:** Update the empirical capture file `_sys/.ai/cli-reality-observed.json` (e.g. running a script that gets the true model list from the CLI, since `--help` is untrusted and some CLIs need a PTY).

**Verification & Check:**
- `check_cli_reality.py` executes `classify_model(declared, actual_list)`. If the new model is in the observed list, it returns **MATCH**.

**Invariant:** Any declared model MUST exist in the empirically captured actual models list.

### (b) CHANGE a Model (Rename/Swap)
**Standard Scenario Steps:**
1. **Config Edit:** Change `model_id` / `runtime_model` in `orchestration.json` profile.
2. **Update Provenance:** Refresh `cli-reality-observed.json`.

**Verification & Check:**
- If the orchestration specifies `gpt-5.6` but the CLI's actual list only has `gpt-5.5`, `check_cli_reality.py` yields **CONTRADICTED (P0)**.
- The `r-8b3b` model-operand validator (SHIPPED — `hub_peer.validate_model_operand`, `_sys/core/hub_peer.py:226`, W2 this session) ensures the passed operand strictly matches the declared model; the hub refuses to build a drifting command.

**Invariant:** The runtime alias mapped by the config MUST exactly match the upstream CLI's expected operand.

### (c) DELETE a Model
**Standard Scenario Steps:**
1. **Deprecation:** The upstream provider removes `ag.3p`.
2. **Provenance Sync:** We refresh `cli-reality-observed.json` (the model drops off the list).
3. **Drift Detection:** `check_cli_reality.py` runs, compares `orchestration.json` to the new list, flags `ag.3p` as **CONTRADICTED (P0)**.
4. **Remediation:** Remove the profile from `orchestration.json` or switch its `routing_state` to `blocked`.

**Failure Mode if Skipped:** Invoking the deleted model fails asynchronously at runtime, burning routing time. The P0 check block prevents this from reaching runtime.

---

## 4. Q3: Usage, Token, and Limit CRUD

Quota tracking handled via `_sys/core/snapshot.py`.

### (a) A New Quota Window Appears (e.g., `F-7D` for Fable)
**Standard Scenario Steps:**
1. **CLI Output Changes:** `claude /usage` starts outputting "Current week (Fable): X% used...".
2. **Parser Update:** Update `_CLAUDE_USAGE_SECTIONS` in `_sys/core/snapshot.py` to map the new label.
3. **Fallback Dynamic Parsing:** `snapshot.py` logic handles unexpected keys dynamically (e.g., the `prefix = "F-" if "fable" in key else "C-"` block for codex).

**Invariant:** Any active quota bucket reported by the upstream CLI MUST be surfaced and normalized. Unmeasured = `absent` (DIR-004).

### (b) Limit Changes (Reset Cadence, Cap)
**Standard Scenario Steps:**
1. **Measurement:** `snapshot.py` queries `claude /usage` or the Codex `app-server` (`account/rateLimits/read`).
2. **Normalization:** The exact reset string (e.g., "Jul 7, 10pm (Asia/Seoul)") is parsed by `_parse_reset()` into an ISO8601 local timestamp.

**Verification & Check:**
- The LB checks `pacing["status"]`. If a limit resets sooner, the pacing calculation automatically adjusts without config changes.

### (c) A Window is Removed
**Standard Scenario Steps:**
1. The CLI stops emitting the bucket.
2. `snapshot.py` ceases to parse it.
3. Diag renders it as `absent`.

**Failure Mode if Skipped:** If hardcoded, the LB might divide-by-zero or assume a permanently exhausted bucket. Relying purely on live parsed state prevents silent breakage.

---

## 5. Q4: Real-Behavior Verification (The Canary)

`--help` is a hypothesis. `check_cli_reality.py` currently checks versions and correlates against out-of-band lists, but lacks an **ACTUAL-operation probe**.

### The Canary Design
A new script `_sys/checks/check_cli_canary.py`.
- **Purpose:** Execute a minimal, real request to verify E2E execution at a BOUNDED, BUDGETED token cost (cx correction: it is NOT free — see §9 cost policy).
- **Payload:** `{"prompt": "Respond with the single word 'OK'.", "max_tokens": 1}`.
- **Execution:**
  - `cc`: `claude.cmd -p "Respond with OK" --model <model>`
  - `cx`: `codex.cmd exec "Respond with OK" -c model="<model>"`
  - `ag`: `agy.exe -p "Respond with OK" --model "<model>"`
- **Verdicts:**
  1. Launches? (Exit code 0, no unhandled Python/Node errors).
  2. Accepts Operands? (No "unknown argument --model" errors).
  3. Returns Reply? (Output == "OK").
  4. Reports Usage? (Canary checks if the live state log / sqlite db updated).
- **Budgeting:** Cached. Only run upon fingerprint change detected by `check_cli_reality.py` or when explicitly invoked.

---

## 6. Q5: CLI ↔ USER E2E Consistency Invariant

**Scenario:** Trace the `cc.deepthink` model field.
1. **Config (Declared):** `orchestration.json` -> `profiles["deepthink"]["model_id"] = "claude-opus-4-8"`.
2. **Adapter (Mapped):** `ClaudeAdapter` compiles args -> `["--model", "claude-opus-4-8"]`.
3. **Execution (Real):** Subprocess calls `claude.cmd ... --model claude-opus-4-8`.
4. **Telemetry (Observed):** `snapshot.py` parses `status_input.log`, sees `{"model": {"id": "claude-opus-4-8"}}`.
5. **Render (User View):** `diag.py` displays `[cc] claude-opus-4-8`.

**Divergence Vectors:**
- The Adapter ignores the config and hardcodes a model.
- The CLI silently fallbacks to `claude-haiku` despite the flag.
- The Telemetry fails to parse the new log format.

**E2E Invariant:**
`Config.model_id == Telemetry.observed_model`
If the user requests `deepthink`, the telemetry MUST reflect `opus`. If `snapshot.py` detects a different model executing, a severe desync has occurred.

**Enforcement:**
Introduce a cross-check comparing the active session's requested profile against the `snapshot.py` observed state during `hub.py` teardown.

---

## 7. Q6: MECE Gap Map

| Dimension | Scenario | Existing Coverage | Gap / Missing Artifact | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **CLI** | ADD Binary | `check_cli_reality.py` (fingerprint), `validate_peer_config.py` | None | ok |
| **CLI** | UPDATE Version | `check_cli_reality.py` (version parsing) | **No execution validation on new binaries.** | HIGH |
| **CLI** | DELETE Binary | `validate_peer_config.py` (catches disabled routes) | None | ok |
| **Model** | ADD Model | `check_cli_reality.py` (matches against observed json) | **`cli-reality-observed.json` generation is manual.** | MED |
| **Model** | CHANGE Model | `check_cli_reality.py` (CONTRADICTED P0 block) | None | ok |
| **Model** | DELETE Model | `check_cli_reality.py` (CONTRADICTED P0 block) | None | ok |
| **Quota** | ADD Window | `snapshot.py` (parses some dynamically) | Strict Regex (`_CLAUDE_USAGE_SECTIONS`) ignores unknown buckets. | MED |
| **Quota** | CHANGE Limit | `snapshot.py` (reads live reset times) | None | ok |
| **Quota** | DEL Window | `snapshot.py` (renders `absent`) | None | ok |
| **E2E** | Live Verification | None | **Canary execution probe.** | HIGH |
| **E2E** | Live Desync | None | **Config vs Telemetry post-run assertion.** | HIGH |

---

## 8. Q7: Scope & Phasing

### Recommended First Increment (TDD-able)
The most valuable and least complex first step is **closing the Live Verification gap (The Canary).**
Before building complex runbooks, we need a script that actually proves the binary works.

**Increment 1: `_sys/checks/check_cli_canary.py`**
- Input: Takes a peer and profile (e.g., `cc deepthink`).
- Action: Reads the `invoke_args` from `orchestration.json`, fires the real binary with `Respond with OK`, captures the output.
- Assertions:
  - Return code == 0.
  - Output contains "OK".
- Integration: Add an optional `--canary` flag to `check_cli_reality.py` that runs this for all enabled profiles if the binary fingerprint has drifted.

### Phasing
- **Phase 1 (SHIPPED 2026-07-04, commit `01495b4`):** `check_cli_canary.py` — empirical E2E invocation verification. R:10 `r-958c` unanimous.
- **Phase 2 (DEFERRED 2026-07-04, R:10 `r-e845` unanimous):** post-run `Config.model_id == Telemetry.observed_model` assertion in `hub.py`. **Deferred — not soundly buildable now (see §10).** Re-scoped onto Phase 3.
- **Phase 3:** Automate the generation of `cli-reality-observed.json` via a trusted sandbox PTY scraper script. This unblocks the *sound* form of Phase 2 (declared-vs-known-good model, no live-timing dependency).

---
**Open Questions for Review (cx):**
1. For Codex, our wrapper invokes the `app-server` daemon. When running a canary probe, should we spin up a transient daemon or just do a one-shot CLI `exec`?
2. `r-8b3b` model-operand validator: is this a planned feature that should be rolled into the adapter layer?
3. Do you agree that `check_cli_canary.py` is the highest ROI first increment to fulfill DIR-004 empirical verification?

---

## 9. cx review resolution (2026-07-04) — binding refinements

- **Canary invocation (Q1):** one-shot `codex.cmd exec` for the INVOCATION canary
  (not the app-server daemon; the daemon belongs to the separate QUOTA-telemetry
  canary). Keep the two canaries distinct.
- **r-8b3b (Q2):** references corrected to EXISTING (`hub_peer.validate_model_operand`).
  The canary must assert the operand validator PASSES first, then prove the real
  CLI accepts the same operand.
- **Cost/budget policy (Q5 — the "without burning quota" claim was FALSE):** the
  canary spends real tokens, so it is bounded by:
  - `--canary` OPT-IN (never auto-runs on every check);
  - cache key = `binary_fingerprint + invoke_args + model_id + prompt_version`
    (skip if unchanged);
  - fingerprint-triggered (run only when check_cli_reality detects a binary drift);
  - 1-token output cap + timeout;
  - a per-5h / per-day invocation budget (reuse the arbiter budget pattern);
  - **skip premium profiles** (cc.fable/cc.deepthink) unless explicitly requested;
  - record the last result for audit.
- **Default scope (Q6):** probe the CHEAPEST enabled profile per peer by default;
  all profiles only under `--all-profiles`.
- **MECE gaps to add (Q4):** adapter arg-synthesis coverage; telemetry
  parser/render coverage (a new log/quota format that snapshot fails to parse);
  stale `cli-reality-observed.json` deletion/cleanup; noninteractive/permission
  flag coverage; PTY-vs-non-PTY behavior; strict separation of the quota-telemetry
  canary from the model-invocation canary.

**Verdict:** ag GO (design) + cx GO (after the above edits). Phase 1 =
`_sys/checks/check_cli_canary.py` (invocation canary, opt-in/cached/budgeted,
cheapest-profile default). This doc is the design contract.

---

## 10. Phase 2 deferral — measured telemetry-semantics blocker (2026-07-04)

Phase 2 proposed a post-ask assertion `Config.model_id == Telemetry.observed_model`
in `hub.py`. A first ag implementation claimed all three peers expose a per-peer
observed model. **Terminal verification against the real files refuted the premise
(DIR-004 — measured, not assumed):**

| Peer | Declared (`orchestration.json`) | Observed telemetry | Soundness |
| :--- | :--- | :--- | :--- |
| `cc` | `model_id` per profile (e.g. deepthink=`claude-opus-4-8`) | `status_input.log` model=`{id:claude-opus-4-8, display_name:'Opus 4.8'}` — but this is the **interactive terminal statusline**, NOT a `claude.cmd -p` peer subprocess (which emits no statusline). | **Unsound** — comparing a cc-peer profile (e.g. standard=haiku) vs the terminal's live model = false DESYNC every ask. |
| `ag` | `model_id` = **null for all profiles** (runtime-resolved) | `ag_stdin.log` model=`{id:'Gemini 3.1 Pro (High)'}` exists | **No comparison** — nothing declared to assert against; helper early-returns. |
| `cx` | `model_id` per profile (e.g. deepthink=`gpt-5.5`) | `state_5.sqlite` `threads.model` (table confirmed) | **Fragile** — `ORDER BY updated_at DESC LIMIT 1` is timing-dependent (not guaranteed THIS ask); stored format vs declared id unverified. |

Additional blocker: `cli-reality-observed.json` (the known-good model snapshot) does
not exist yet (its generation is Phase 3, currently manual).

**Decision (R:10 `r-e845` unanimous — ag, cx, cc):** DEFER the live per-ask
assertion. Shipping it would violate DIR-004 (false-alarms). The sound form —
declared `model_id` vs a known-good model set with no live-timing dependency —
is gated on **Phase 3** (`cli-reality-observed.json`). A weaker interim option
(declared-vs-declared config-integrity, e.g. enabled profile must declare a
non-null well-formed `model_id`, skipping runtime-null ag) may be picked up
independently but is not part of this E2E-desync line.

**Lesson (LL):** per-peer subprocess model is not observable from current
telemetry. `status_input.log` observes the terminal; `ag` declares null; `cx`
telemetry is post-hoc/timing-fragile. Any "observed model" claim must name the
exact source and prove it reflects the invoked subprocess before asserting.

---

## 11. B7 spec — security invocation contract drift (DEFINE-ONLY, 2026-07-04)

B7 (R:10 `r-395f` unanimous — ag, cx, cc): **DEFINE-ONLY**, no implementation now.
`check_cli_reality` today reconciles only model / version / fingerprint. It does
NOT reconcile the **security invocation contract** — the permission/sandbox flags
that must (or must not) reach the real CLI.

**Scope (concrete):** cc/ag `--dangerously-skip-permissions`, cx `workspace-write`
sandbox policy, forbidden unsafe flags, and absence of stale allowlist /
`--ignore-rules` claims. Declared today in `orchestration.json` `invoke_args`
(machine-readable) plus free-text DIR-002/permission notes (NOT a reliable
contract). Observable as the effective hub/console command args produced by the
adapters.

**Measurability:** PARTIAL. Arg *presence/parity* is measurable statically today
(and already partly covered by `hub._check_flag_parity()`); actual *enforcement
behavior* is blocked — it needs empirical probes, not static reconciliation, and
must not be faked (DIR-004).

**Backlog spec (for a later increment):** add a machine-readable per-peer
`security_contract` block with:
- `required_effective_args` — flags that MUST appear in the adapter-built command,
- `forbidden_effective_args` — flags that MUST NOT appear (e.g. an over-broad
  permission or a stale `--ignore-rules`),
- `sandbox_semantics` — the expected sandbox/permission mode (e.g. cx
  `workspace-write`).
Reconcile these against the adapter-built hub args + `peer_console` args (a new
check, or a `security` dimension folded into `check_cli_reality`). Do **NOT** parse
free-text DIR-002 notes into the checker — only the machine-readable contract is
authoritative. Enforcement-behavior probing is a separate, later step.

### 11a. B7 static arg-parity — IMPLEMENTED (2026-07-05, R:10 `r-f6b5`)

The `security_contract` block is now declared per peer in `orchestration.json`
(cc/ag `skip-permissions`, cx `workspace-write`; the disabled `ca` alias has
none). `hub._check_flag_parity()` reads it — skipping non-peer / disabled /
contract-less nodes (DIR-004: no invented policy, disabled alias must not
false-fail) — and reconciles `required_effective_args` present + `forbidden_
effective_args` absent across BOTH the hub adapter command and `peer_console`
defaults, plus the `workspace-write` semantic (substring, `-s` or `-c sandbox=`).
The old hardcoded REQUIRED/FORBIDDEN maps were removed. Wired into
`check_contracts`; live parity is clean. Tests: `test_security_contract_parity.py`.

### 11b. Enforcement-BEHAVIOR probe — DEFERRED (2026-07-05, R:10 `r-f253` unanimous)

Verifying the CLI actually **honors** the sandbox/permission at runtime (not just
that the flag is present) is **deferred** — measured feasibility (DIR-004):
- No existing signal observes a PEER CLI's enforcement. The hub's own
  `_is_sandbox_rename_denied` / `_is_sandbox_spawn_denied` detectors concern the
  HUB's sandbox, not a peer's.
- **Attack-probing** (prompt the peer to attempt an out-of-sandbox op and parse
  blocked/allowed) is real-token, non-deterministic (the model may refuse or
  describe instead of attempt), and safety-sensitive.
- **Self-reported effective mode** is only PARTIAL: `ag_stdin.log` carries a
  `sandbox` field, but a machine-readable effective-sandbox field for cc/cx
  (e.g. in `codex exec --json`) is unproven.

**Decision:** keep the shipped static arg-parity (§11a) as the automated gate.
**Unblock condition:** add behavioral verification only once a *proven*
machine-readable effective-sandbox self-report field exists across the target
CLIs (then parse-and-assert == declared `sandbox_semantics` — sound, cheap,
deterministic, no attack). Until then, behavioral enforcement stays a manual/
ad-hoc step.
