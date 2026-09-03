# Hard Benchmark & D1 — Decisions (T48)

> Status: **living** (decision) | Date: 2026-07-14 | Language: English (INV-19)
> Consensus: cx.deepthink (design) + ag (Windows-sandbox / PTY cross-check) + cc.fable synthesis.
> Companion: [`capability-leveling.md`](capability-leveling.md), [`intelligence-scores.md`](intelligence-scores.md) §4.6–4.8.
> **No code changed by this document.** It records the design and two ratifiable calls.

---

## 0. Headline decision — DECOUPLE D1 from a measured reasoning edge

The capability-leveling measurement layer is complete and honest, and it produced a
clear empirical verdict (`intelligence-scores.md §4.8`): **cx.deepthink (Sol),
cc.deepthink (Opus 4.8) and ag.deepthink (Gemini 3.1 Pro) all tie at reasoning 100
/ code 100** on every deterministic canary we can currently author — including the
declared-*weakest* peer. A tie is a **measured `ceiling`, not co-first**, and it is
**not** a ranking.

Therefore, per ag's ROI argument (which cc/fable adopts over cx's build-first
stance): **D1 (Sol → arbiter) MUST NOT be gated on building a research-grade
discriminating reasoning benchmark.** Authoring deterministic, closed-form problems
that actually separate frontier models is an open-ended research undertaking that
may never discriminate. Instead:

- **D1 is ratified as an ARCHITECTURE / PROVIDER-DIVERSITY call, not a measured
  one** — admit Sol (`cx.deepthink`) to `arbiter_models` for epistemic diversity
  and Claude-outage resilience, conditioned on the existing non-capability gates
  (an **X-family reserve** so bulk Codex can't starve the Sol arbiter, provider-
  diversity, DIR-005 budget), as a normal **R:10** decision. The measured reasoning
  edge is recorded as **`ceiling` / undecidable** and contributes nothing to the
  decision.
- The measurement layer stays valuable for **regression tracking** and the
  **agentic-fidelity** axis — not for ranking frontier reasoning.

D5 (complexity clamp) is likewise only ever fed by a suite whose `suite_quality`
is `discriminating`; a `ceiling`/`tie` suite must never rank.

---

## 1. Why local measurement can't rank frontier reasoning here

1. **Tractable-and-deterministic ⇒ easy for frontier models.** Every problem class
   we can score exactly (no LLM judge) — arithmetic, multi-step word problems,
   counting, hex/base, modular chains — is solved by all three peers. Hard-enough-
   to-separate + exact-scorable is the core tension (cx §A).
2. **Real code execution is infeasible on this host (ag verdict, decisive).**
   Windows Sandbox and container runtimes need Windows Pro/Enterprise **+ admin**
   to enable — **100% unavailable** on a portable, no-admin USB/cloud-drive env.
   Job Objects cap processes/RAM without admin but **cannot** confine a generic
   `python.exe`'s filesystem/network; and `general/permissions.md §7` already shows
   even a peer's own `--sandbox` fails to confine writes. **So `code-hidden.v1`
   cannot safely execute untrusted candidate code here.**
3. **Some things are not locally measurable at all** and must stay `declared` /
   `absent` / outcome-telemetry (never faked as an exact score): open-ended design
   quality, creativity/style, current factual knowledge, natural-language proof
   quality, external-tool workflows, general code safety without a certified jail,
   and separating pure-model reasoning from the CLI/tool surface.

---

## 2. If/when a hard suite is built — the ratified architecture (cx, adopted)

Not required for D1; this is the **regression/future** design, Phase-1 buildable
with **no token spend**.

- **Split the monolith** into axis suites: `reasoning-hard.v1`, `code-hidden.v1`,
  `agentic-reliability`, `long_context.Nk`. `capability-core.v1`'s 100s stay as
  **smoke evidence** with `suite_quality.status = ceiling` (excluded from ranking).
- **Parametric generation, contamination-proof:** `(generator_version, family,
  difficulty_rung, batch_seed) → instance → INDEPENDENT oracle → exact answer`.
  Same seed ⇒ byte-identical instance; the answer is **never** written to the
  candidate workspace; generator validates uniqueness; oracle re-verified by a
  bounded exhaustive/independent reference; workspace wiped between profiles.
  **DIR-004 (ag):** commit `sha256(batch_seed)` to `_sys/ai/knowledge/` **before**
  reserving budget or invoking — reveal after the batch (not on success), to stop
  cherry-picking.
- **Fixed ladder, not adaptive:** 4 families × 4 rungs × 16 items/form, 3 parallel
  forms = 48 exact 1/0 observations/profile; family/rung subscores kept.
- **Calibration ≠ certification:** `*.calibration.v0` (wide ladder, 3 peers,
  never routes) fixes difficulty; `*.v1` re-runs on **fresh held-out seeds** — no
  post-hoc overfit.
- **Discrimination CONTRACT** per axis record — `insufficient | ceiling | floor |
  tie | unstable | discriminating`. `discriminating` needs: all subjects same
  runtime fingerprint × 3 forms, ≥4 informative items, same pairwise order in
  ≥2/3 forms, paired-bootstrap 95% CI excluding 0, no hard failures. **Partial
  orders allowed** (`Sol > Gemini`, `Sol ~ Opus`); a full total order is never
  forced. **Only a `discriminating` suite feeds routing.**

---

## 3. Code axis (T46) — verdict: no safe jail ⇒ restricted-DSL or absent

`code-hidden.v1` would replace the exact-patch oracle with sandboxed hidden-test
execution (3 parametric buggy fixtures × 4 test groups nominal/edge/adversarial/
regression, all-or-nothing, functionally-correct-different patches score equal).
**But** (ag, decisive) there is no admin-free certified jail on this host.

- **Do NOT run general untrusted Python.** T46 stays `declared`/`absent` unless a
  jail passes a **sandbox self-test** that actively ATTEMPTS and is BLOCKED on:
  write outside workspace (`%TEMP%\leak.txt`), read outside (`C:\Windows\win.ini`),
  spawn a child (`cmd.exe`/`ping`), open a network/DNS connection, and exhaust
  resources (infinite loop / >500 MB) — with a forced SIGKILL on timeout. Any
  success or un-killed timeout ⇒ **leaky ⇒ `sandbox_unavailable` ⇒ code axis
  `absent`**.
- **Fallback:** a restricted AST/DSL interpreter (no import/attr/arbitrary calls)
  is a **distinct `restricted_code_reasoning` axis** — NOT general code-repair
  capability. Label it honestly; never present it as the code axis.

---

## 4. Agentic axis fix — the flaky 80↔100 is likely a PTY harness artifact

ag's root-cause (adopted): agy's `line_endings_and_bom` result flipping 80↔100 is
**probably winpty mangling line endings** (Windows PTYs inject CRLF for display),
corrupting the byte-exact fixture prompt in transit — **not** a real agy capability
gap. This means the **§4.6 ag score of 80 may be invalid harness noise.**

- **Fix:** never send the byte-exact fixture prompt through PTY stdin. Write the
  prompt to a **read-only file in the workspace** and instruct the agent to read
  it; use the PTY strictly for process control, not payload transit. Re-measure ag
  after the fix before trusting any agy fidelity number.
- **Evidence model (cx+ag):** store the full distribution `{runs, median, min,
  max, range, pass_rate, hard_failure_fingerprints, evidence_state}` with states
  `stable_certified | stable_failed | flaky | transport_unstable | insufficient`.
  **`flaky` ≠ a low score**; only `stable_certified` feeds D1. Transport failures
  retry (≤5 attempts for 3 complete runs); a genuine scored failure never retries.

### 4.1 agy has NO byte-exact large-prompt delivery — a hard-benchmark PREREQUISITE (T51)

Empirically verified (ag, 2026-07-15) — `agy` cannot receive a large byte-exact
prompt for the hard benchmark:
- **STDIN: unsupported.** `echo x | agy --dangerously-skip-permissions -p -` → the
  model sees an empty prompt (answers "How can I help you today?"). `AgyAdapter.
  build_cmd` documents inline-only (`use_stdin=False`).
- **No native prompt-file flag** (`--prompt-file` / `-f` / `@file`) in `agy --help`.
- **PTY stdin is mangled** on Windows ConPTY (CR/LF translation, echo, no clean
  EOF) — not a byte-exact channel.
- **Inline `-p <text>`** hits the ~8191-char Windows command-line limit + arg
  escaping — fine for the *small* current canary (agy runs 80/80/80 inline), but
  unusable for a hard-benchmark-sized prompt.

So a large byte-exact agy measurement is **BLOCKED on an ABSENT agy capability, not
a harness bug**. cx + ag both ruled STOP: T51 ends at the diagnostic-record slice
(landed — `prompt_delivery_mode`/`prompt_bytes`/`config_home` on the PTY invocation
record + the shared `_is_transport_unstable` classifier). Prerequisites before any
hard benchmark that needs agy: (a) a native `agy --prompt-file`/stdin capability, or
(b) a proven byte-exact PTY-write conformance probe (no-token, local). A **seeded
read-only `AGY_CONFIG_HOME`** (a `settings.json` with `toolPermission`/
`trustedWorkspaces`; auth via env/G1 credits, no seeded secrets) is a feasible
future fix to stop fresh-home re-onboarding CRLF-nondeterminism — not needed now.
Cross-provider diagnostics should share ONE dependency-light record + classifier
(cx: use a `config_home_kind` of `default|ipc_stateless|canary_disposable`, not a
raw path), applied without coupling normal asks to canary code.

---

## 5. Phasing & what is NOT worth building now

| Phase | Scope | Tokens | Build now? |
|---|---|---|---|
| P1 | parametric generators + independent oracles + uniqueness + ladder/forms + seed commit + suite-quality classifier + mock-invoker scoring | none | optional (regression infra) |
| P2 | code sandbox self-test + jail (T46) | none | **NO** — no admin-free jail exists; restricted-DSL only, or absent |
| P3 | budgeted live `calibration.v0` → held-out `.v1`, discrimination status | budgeted | only if P1 lands and a discriminating signal is plausible |

Given the §4.8 ceiling result, **P3 may never yield a discriminating reasoning
signal** — which is exactly why D1 is decoupled (§0). Recommended immediate work is
**none of P1–P3**; instead take the two ratifiable calls (§0 D1 decouple, §4 PTY
fix) and treat the hard suite as deferred regression infrastructure.

---

## 6. Backlog & human calls

- **T48 (this doc):** design + decisions recorded. The `reasoning-hard.v1` build is
  **deferred** (regression-only, not a D1 gate).
- **D1 (R:10):** ratify Sol → `arbiter_models` on architecture/provider-diversity
  grounds + an X-family reserve — a human decision, not measured.
- **T46:** code-hidden stays `absent` (no jail) or a labelled `restricted_code_
  reasoning` DSL axis. No general Python execution on this host.
- **T49 (spawned):** apply ag's PTY prompt-via-file fix + full-distribution
  evidence_state to the agentic canary, then re-measure ag (the 80 may be noise).
- **Bug (spawned, T50):** the terminal-spend guard raises `can't compare offset-
  naive and offset-aware datetimes` on every ask (seen twice this round) — a real
  tz-aware datetime defect in the D7 guard; harmless (warns, proceeds) but should
  be fixed.

Human taste calls: (1) admit Sol as a provider-diverse arbiter now vs wait — cc/ag
lean **admit now** (R:10 + X reserve); (2) invest in `reasoning-hard.v1` at all —
cc/ag lean **defer** (may never discriminate); (3) build a restricted-DSL code axis
vs leave code `absent` — lean **leave absent** until a real need appears.
