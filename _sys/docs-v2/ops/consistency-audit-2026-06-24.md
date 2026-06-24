# Consistency Audit — Health, Timeout/Lease, Communication & Turns (vertical/horizontal)

> **Date:** 2026-06-24 · **Type:** Audit (findings only — NO changes made)
> **Authors:** ag.deepthink (analysis) + cc.deepthink (code cross-verification) + terminal (enrichment + spot-checks)
> **Provenance:** Health & Timeout sections are cc-code-verified. Communication & Turns section is ag-analyzed + terminal spot-checked (pending cc cross-verification).
> **Governance note:** This audit cannot be R:10-finalized right now — see Drift H-1 (consensus quorum deadlock). Treat as high-confidence two-party (cc+ag) cross-check pending a third voter / human approval before remediation.

Axes used throughout: **vertical** = consistency across the 4 layers (docs / source / guidelines / config) for the same concept. **horizontal** = consistency across peers / profiles / transports.

---

## 0. Executive summary — the intended directions vs reality

| Subsystem | Intended SSOT direction | Reality |
|---|---|---|
| Timeout/liveness | Unbounded thinking + heartbeat/zombie liveness; lease = crash-safety only | Implemented for **non-PTY (cc/cx)** only; **PTY (ag) hard-capped at 300s total** |
| Communication | Unbounded semantic discussion via `file_ref`; thin bounded envelope | Payload intent unbounded, but **silent char-truncation** at transport + **per-peer context windows ignored** |
| Turns/rounds | Iterate until agreed (R:10); legitimate runaway breakers only | Mostly aligned, but **`timeout_minutes=30` + `offline_auto_abstain=30` contradict "until agreed"** |
| Consensus quorum | INV-28 dynamic gate-OPEN quorum `max(2,f(N))` | **NOT implemented** — static unanimity over `[cc,ag,cx]`; with cx rate-limited → **deadlock** |
| No-code discipline | discussion→design→impl phase gating | **Dormant** — defined+tested, never set by any operational workflow |
| Self-improvement loop | recurring lessons graduate to invariants | **Wired but functionally open** — graduation→proposal works, but proposal→invariant ratification deadlocks under H-1 |
| 5-Whys root cause | per-incident root-cause investigation | **Canned templates** per error type, auto-logged; not a live investigation, not wired to prevention |

**Top drift = H-1 (quorum deadlock).** It is the **keystone for consensus ratification** (static unanimity over `[cc,ag,cx]`, cx gated, INV-28 dynamic quorum uncoded → no round finalizes). **Corrected by cross-check (§7):** H-1 is *necessary but not sufficient* for self-improvement-loop closure — closure has a **SECOND break**: there is no automated `ratified-proposal → 10-invariants.md` writer, so even with H-1 fixed, graduated lessons become ratified *proposals* but still require a manual edit to become *invariants*. Remediation must address BOTH. H-1 remains the bootstrap blocker (needs human approval to seed).

> ⚠️ **Provenance update:** §1-2 and §3b/§3c keystone claims are cc-code-verified. §3 (comms/turns) was **materially over-stated by the first pass** and is corrected in §7 — several "drifts" are *inert config never read by code*, not active harms. Read §7 before acting on §3.

---

## 1. Health system (cc-code-verified)

| # | Severity | Drift | Evidence |
|---|----------|-------|----------|
| H-1 | **UNIMPLEMENTED (high)** | INV-28 dynamic gate-OPEN quorum not coded; consensus = static unanimity over `[cc,ag,cx]`. cx gated → consensus unreachable → human deadlock. | hub.py:3152-3168, 4916-4923, 4991-4997 vs 10-invariants.md:63 |
| H-2 | **REAL CONSTRAINT (PTY-scoped)** | ag.deepthink hard-killed at 300s total (PTY deadline = pty_lease_sec, output-independent). cc/cx uncapped (600s silence). | hub.py:2294-2297, 1932, 1945 |
| H-3 | **DESIGN GAP** | No per-profile health. Downward fallback works at config layer (`_eligible_profile`) but a root health gate-close drops all profiles first. | hub_profile_router.py:174-192; hub.py:1310-1319, 2288-2289 |
| H-4 | **DOC-STALENESS** | C1 transient soft-gate is a state class absent from the RED-centric health/invariant model. Not unsafe; auto-reopen is safe. (ag mis-rated this "UNSAFE/INV-11 violation"; corrected.) | hub.py:1186, 1419-1442, 1295-1308 |
| H-5 | **DOC/OPS (minor)** | `jsonl_mb` stale for non-cc / when check_health not run; + MB threshold scale mismatch (0.6/1.2 vs 80/150 MB). MB is an outdated proxy (use tokens). | check_health.py:26-44; protocol.json health.thresholds vs autonomous_maintenance |

**Aligned (OK):** peer-health zero-token reads (INV-08); session fingerprint check exists in `action_ask` (hub.py:2361-2374, INV-14/23) — NOT in `_session_reuse_enabled` (capability-only); RED machinery (modulo H-4 reframe).

---

## 2. Timeout / Lease / Liveness — vertical/horizontal

**Intended direction (SSOT):** unbounded thinking + liveness via heartbeat/zombie; lease = crash-safety only.
Evidence: protocol.json `communication_policy.{unbounded_semantic_discussion, bounded_transport_required, heartbeat_required_for_long_running}`; docs-v2/general/health.md:113 "Heartbeat / Lease (crash-safety only)". **non-PTY (cc/cx) implements it correctly** (node.timeout=0 → unbounded + 600s-silence zombie).

### horizontal (cross-peer / transport)
| | Inconsistency | Evidence |
|---|---|---|
| H2a | `ag.timeout=300` vs `cc/cx.timeout=0` — ag is the only peer with a hard total cap | orchestration.json |
| H2b | PTY → hard 300s TOTAL deadline; non-PTY → unbounded + 600s-silence zombie. Two liveness models by transport; PTY violates the unbounded SSOT. | hub.py:1932 / 2299 |
| H2c | `ag.timeout=300` vs `agy --print-timeout 60m (3600)` — ag's own config is internally contradictory (child told 60 min, hub kills at 5 min). | orchestration.json (ag node) |

### vertical (cross-layer)
| | Inconsistency | Evidence |
|---|---|---|
| V1 | "lease" overloaded / triple-valued: `lease_timeout_sec=1800` (orphan cleanup, `_lease_cfg`) vs `pty_lease_sec=300` (PTY deadline) vs feedback-loop.md "should be 300". | protocol.json runtime vs communication_policy |
| V2 | **DOC↔SOURCE contradiction:** health.md "lease = crash-safety only (≠ timeout)" vs code using `pty_lease_sec(300)` AS the PTY total deadline. | health.md:113 vs hub.py:1890,1932 |
| V3 | `zombie_timeout_sec=600` is GLOBAL (not profile-aware): a `*.deepthink` thinking silently >600s is force-killed. Insufficient for heavy reasoning (prior agreement mentioned 7200). | protocol.json vs hub.py:1956 |
| V4 | Guideline default `CLAUDE.md` 180s vs unbounded intent vs the long `--timeout 400000+` actually passed. | CLAUDE.md vs protocol.json runtime |
| A1 | non-PTY silent-zombie triggers at 600s but logs/raises with `lease_timeout_sec(1800)` — wrong value in error/log. | hub.py:2773-2776 |
| A3 | `consensus.timeout_minutes=30 (1800s)` vs `ask_default_timeout_sec=180` — a default ask kills a peer long before a consensus window expires. | protocol.json |

---

## 3. Communication & Turns — vertical/horizontal (ag-analyzed + terminal spot-checked)

### Perspective A — Inter-peer COMMUNICATION
**Intended:** unbounded semantic discussion via `large_content_strategy=file_ref` + thin bounded envelope.
- **vertical drift:** `HANDOFF_MAX_*` arrays silently **truncate** handoff (hub.py:682-687, 746-753) — destroys history rather than offloading to file_ref. `max_inline_response_chars=4000` truncates inline payloads.
- **horizontal drift:** `prompt_templates.max_context_chars` (compact=800 / standard=4000 / deep_review=12000) are **global hardcoded**, ignoring per-peer `context_window` (verified: cc=200K–1M, cx=272K). High-context profiles are massively under-fed (≤12K of a 1M window).
- **Legitimate vs drift:** `max_forward_chars=800` = legitimate thin-envelope pointer. `HANDOFF_MAX_*` truncation + `max_inline_response_chars` = DRIFT (silent context destruction instead of file_ref).

### Perspective B — TURNS / rounds
**Intended:** iterate until agreed (CLAUDE.md R:10); only runaway breakers should bound it.
- **vertical drift:** CLAUDE.md "until agreed" (qualitative, unbounded) vs `consensus.timeout_minutes=30` + `offline_auto_abstain_minutes=30` (hard quantitative time-bounds that silently drop a slow voter → compromise unanimity). `session_count_today` is incremented but **uncapped** (correctly unbounded).
- **horizontal:** failover `_depth` (+1, hub.py:2337) and C3 `_escalation_depth=1` apply **symmetrically** to all peers — no horizontal inconsistency. **Legitimate** bounds.
- **Legitimate vs drift:** `failure_error=5` HALT (INV-15) + recursion depth = legitimate runaway breakers. `timeout_minutes=30` / `offline_auto_abstain=30` = drift against "iterate until agreed".

---

## 3b. No-code, closed-loop & 5-Whys — governance / self-improvement loops

Theme: do the improvement loops actually **close** (detect → analyze → fix → learn → **prevent**), or do they detect/propose but stall before prevention?

### No-code phase discipline → **DORMANT**
- **Intent:** discussion → design → implementation gating (the discussion→docs→TDD workflow); `no_code` phases block `mutating_hub_actions`.
- **Reality:** `no_code_phases` (`discussion_no_code`, `design_review_no_code`, `review_no_code`, `planning_no_code`) are defined (protocol.json:613-616), matrix-coded, and **only set in test fixtures** — no operational workflow ever sets a no_code phase. Production phases actually set are `new-topic` / `clear-room` / `active` (hub.py:1809, 1841, `update-status`), none of which are no_code.
- **Verdict (vertical):** docs/plan (workflow) declare a gated discipline; code (matrix) implements it; runtime never enters it → **vestigial**. Either wire a workflow that sets a no_code phase during design/review, or document the discipline as manual-only.

### Closed virtuous loop (lesson graduation) → **WIRED but FUNCTIONALLY OPEN (blocked by H-1)**
- **Intent:** recurring lessons graduate to invariants (feedback-loop.md): detect → `active-lessons.jsonl` → graduate → invariant → prevent.
- **Reality:** the loop is wired end-to-end in code: `self_care.py.lesson_graduation` is **scheduled** at session_start (autonomous_maintenance.schedule steps: health_check, docs_mece_fast, self_care_full, **lesson_graduation**), scans `active-lessons.jsonl` for `source_refs >= threshold(3)`, and calls `hub.py proposal-add` → R:10 vote → `10-invariants.md`.
- **The break:** the FINAL closure (proposal → **ratified** invariant) depends on an R:10 vote, which **deadlocks under H-1** (static unanimity over `[cc,ag,cx]`, cx rate-limited). So lessons graduate to **proposals** but can never become **invariants** → no prevention.
- **Verdict:** **structurally closed, functionally open** — the strongest evidence that **H-1 is the keystone**: it gates not only consensus but the entire self-improvement loop's closure.

### 5-Whys / root cause → **CANNED, not investigated; not wired to prevention**
- **Intent:** per-incident 5-Whys root-cause analysis (feedback-loop.md example; INV-16 P0/P1 → root cause · impact · remediation).
- **Reality:** 5-Whys are **canned templates** keyed per error-taxonomy type (`error-taxonomy.json` `5whys_templates`), auto-logged to stderr + `error-log.jsonl` via `hub_error._5whys_auto_log`. Remediation is a **static suggestion string** per error class (e.g. PEER_RATE_LIMIT → "wait then retry or use fallback"). It is NOT a live per-incident investigation, and the 5-Whys log does **not** auto-feed `lesson_graduation` (separate path) → no automated route from 5-Whys → lesson → prevention.
- **Verdict (vertical):** docs declare a root-cause *process*; code provides a canned *lookup*; reality resolves root cause **manually**, if at all → "5-Whys applied" is largely **template-display, not investigation**. The user's suspicion (root cause unresolved) is confirmed for the automated path.

**Meta-conclusion:** the self-improvement machinery is wired (loop exists, graduation scheduled) but **open at closure**, primarily because (1) **H-1 quorum deadlock** blocks lesson→invariant ratification, (2) 5-Whys is canned and not wired into graduation, (3) the no-code discipline is never engaged. Detect/propose works; **prevent/ratify is blocked — keystone = H-1.**

## 3c. Additional governance dimensions — mostly ALIGNED (implemented)

Checked to confirm the system is not broadly theater. These are **implemented**, not vestigial:
- **INV-18 directive injection:** `_append_directives_and_lessons` (hub.py:1498) injects user-directives + runtime directives + lessons into asks; runtime directives auto-promote after 2 same-reason failures (1457-1459) and clear on first success (1356-1357). Aligned.
- **Artifact workflow:** `enabled=true`; `action_artifact_claim` + statuses/draft_dir/single_owner_merge (hub.py:5267-5293). Implemented.
- **INV-20 Recovery Journal:** `_journal_op` → `.ai/operations.jsonl` (hub.py:519-528). Implemented.
- **INV-21 Challenge Window:** `action_leader_claim` honors `challenge_window_minutes` (hub.py:3595). Implemented.
- **INV-22 Term Limits:** 3-consecutive-term coordinator block (hub.py:3605, "AP-20 Violation"). Implemented.

**Candidate enforcement gap (INV-05/06):** `action_init_session` reads handoff (re-orientation available, hub.py:806) but context-fill / "every peer entry MUST run init→health→context-fill→mailbox" appears to rely on **peer self-discipline**, not hub fail-closed enforcement — consistent with the INV-26 tension (governance should be enforced, not trusted). Pending verification in cross-check.

**Net:** the hub governance machinery (directives, artifacts, leader election, journaling, challenge/term) is real and implemented. The audit's drifts are **localized** — keystone H-1, dormant no-code, canned 5-Whys, and the timeout/comms inconsistencies — not a system-wide theater.

---

## 4. MECE verdict (consolidated)

The 4 layers are **NOT Mutually-Exclusive** and **NOT Collectively-Exhaustive** on these subsystems:
- **Not ME (overloaded concepts):** "lease" = orphan-cleanup ↔ PTY execution deadline. "timeout" = wall-clock total ↔ silent-zombie liveness. "unbounded" = payload (file_ref) ↔ but forwarded context/turns are bounded.
- **Not CE (non-uniform coverage):** transport (PTY vs non-PTY) and profile (standard vs deepthink) are not covered uniformly — no profile-aware liveness, global context caps ignore per-peer windows, PTY total-capped while non-PTY is not.
- **Structural pattern:** Policy/Intent layers (docs, profiles) declare unbounded capacity (file_ref, iterate-until-agreed); Transport/Execution layers (hub, protocol limits) enforce rigid, capability-unaware caps that **silently truncate** instead of delegating to the unbounded mechanisms.

---

## 5. Unification target (the single coherent model)

1. **Total timeout:** all peers/transports unbounded (`node.timeout=0`); retire `ask_default_timeout_sec` and `pty_lease_sec` as execution deadlines. PTY treated identically to non-PTY.
2. **Liveness:** enforced ONLY via `zombie_timeout_sec` (silent-output), made **profile-aware** (e.g. standard≈300s, deepthink≈7200s). Fix the A1 mis-labelled exception value.
3. **Crash-safety:** `lease_timeout_sec` used EXCLUSIVELY for lock/orphan cleanup, strictly detached from execution deadlines.
4. **Communication:** replace string-char truncation (`max_inline_response_chars`, `HANDOFF_MAX_*`) with token-aware `file_ref` offloading; make `max_context_chars` per-peer `context_window`-aware (not a global 800/4000/12000).
5. **Turns:** keep runaway breakers (`failure_error=5`, depth limits); reconcile `timeout_minutes`/`offline_auto_abstain` with "iterate until agreed" (e.g. heartbeat-extended rounds, not a flat 30-min kill).
6. **Quorum (H-1, prerequisite):** implement INV-28 dynamic gate-OPEN quorum (read live `gate_open` voters at round-start) instead of static unanimity — this also un-deadlocks the ability to ratify the rest.

---

## 6. Prioritized remediation

1. **H-1 quorum** (UNIMPLEMENTED, unblocks everything; needs human seed due to bootstrap deadlock).
2. **H-2/H2a-c timeout unification** for PTY (ag) — profile-aware unbounded + zombie liveness.
3. **Comms context-window awareness** + stop silent truncation (use file_ref).
4. **H-3 per-profile health** (or remove the doc promise of same-peer downward health-fallback).
5. **Doc/label sync:** transient-gate state (H-4), lease vs timeout (V2), A1 exception label, MB→token (H-5), turns vs timeout_minutes (B).

---

---

## 7. Cross-check corrections (cc final exhaustive verification)

cc re-derived every §3/§3b/§3c claim from live code. The two load-bearing findings (**H-1 keystone**, **loop functionally open**) survive; several §3 comms/turns claims were **over-stated** and are retracted/corrected here.

### Retracted overclaims (do NOT act on these as "active harms")
1. **`max_inline_response_chars=4000` (protocol.json:455) — INERT.** Zero code references; nothing reads it → nothing truncates inline payloads. Retract the §3 "inline truncation" drift.
2. **`prompt_templates.max_context_chars` 800/4000/12000 (protocol.json:76-112) — INERT schema.** Never read by code; no path caps a profile's context. Retract the §3 "high-context profiles massively under-fed" horizontal drift (the most over-stated claim).
3. **`offline_auto_abstain_minutes=30` — INERT** (never read; auto-abstains nobody). **`timeout_minutes=30`** is enforced only by the **manual, opt-in `consensus-sweep`** which **escalates to human** (status=escalated) over `consensus/` rounds (not `proposals/`) — a legitimate human-escalation breaker, NOT a silent unanimity-compromising kill. Retract the §3 TURNS "silent 30-min kill" framing.
4. **`max_forward_chars=800` is even safer than stated** — only the metadata envelope is bounded; `USER_QUERY` is forwarded in FULL (hub.py:3029-3031). No payload context-loss.

### Minor citation/label corrections
- lesson_graduation runs at **session_END**, not session_start (protocol.json on_session_end).
- `init_session reads handoff @806` mis-cited (806 = end_session). init_session does NOT read handoff.
- **`_escalation_depth=1` does not exist** as code (only an `escalation` routing block, no depth). Failover uniformity still holds via `_depth` (guard `_depth>2` at hub.py:2206).
- no_code: plain **`"discussion"`** is also a no_code phase (list omitted it); `update-status` accepts an arbitrary phase, so no_code IS **manually** settable (not "only in test fixtures") — but still never **auto-**engaged, so "dormant" stands.
- **INV-05/06 resolved → peer self-discipline, NOT fail-closed:** `action_init_session` only registers member + creates session dir; it does not run health-update/context-fill/mailbox/handoff. The MUST-sequence is voluntary, hub does not gate on it.

### Newly-found drifts the first pass MISSED (real)
- **D-1 (co-keystone): no `ratified-proposal → 10-invariants.md` writer.** proposal-vote on CONSENSUS_OK only prints + appends to CONSENSUS_HISTORY (hub.py:4995-4997); nothing writes the invariant. So loop closure needs this AND H-1. Fixing H-1 alone yields ratified proposals that never become invariants.
- **D-2: broken self_care schedule wiring.** `on_session_start.health_check` passes arg `"observe"` and `on_session_end.lesson_graduation` passes `--lesson-grad-only`, but `self_care.py` argparse accepts only `--trigger` → **both steps error out**, hidden by `abort_on_fail:false`. Graduation actually runs only as a sub-step of `self_care_full` (args=[]). Real, silent drift.
- **D-3: `large_content_strategy=file_ref` is itself UNIMPLEMENTED** (zero code refs). The "offload to file_ref instead of truncating" remediation target does not exist yet — so the only real comms drift (HANDOFF_MAX_* permanent trim, CONFIRMED) cannot be fixed by "delegating to file_ref" until file_ref is built.
- **D-4: inert-config class.** #1-3 above reveal a config-vs-code MECE violation of its own: protocol.json declares **phantom knobs** (limits no code reads). These mislead audits and operators into "fixing" non-firing controls.

### Corrected keystone statement
> **H-1 is the keystone for consensus *ratification*** (unanimous static `r10_voters`; cx gated; INV-28 uncoded → no finalization). It blocks consensus and the FIRST of TWO self-improvement-loop breaks. **Loop closure also requires D-1 (an automated proposal→invariant writer).** H-1 is necessary-but-not-sufficient for closure.

### Verdict
Directionally **act-on-able**. Priorities unchanged at the top: **H-1 + D-1** (loop closure), then PTY timeout unification (H-2), then per-profile health (H-3). **Do NOT** spend effort "fixing" the inert comms caps (#1-3); the real comms work is **building `file_ref`** + deciding handoff-trim policy. Two-party `{cc,ag}` cross-check; per H-1 it cannot itself be R:10-finalized.

---

*Source replies: REPLY-ag-healthaudit, REPLY-cc-healthaudit, REPLY-ag-matrix, REPLY-ag-commsturn, REPLY-cc-finalcheck (in `_sys/ai/ipc/`). No code/config/doc-normative changes were made by this audit.*
