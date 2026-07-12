# Full-System Purpose-Centered Audit — 2026-07-12

> Requested by the user: a comprehensive, purpose-centered cross-audit of the whole system
> (not just this session's changes), evaluated recursively against six dimensions — MECE,
> virtuous-cycle feedback loops, 5-Whys root-cause resolution, alternative perspectives,
> resource efficiency ("zero-token orientation") vs effectiveness, and MUST/MUST-NOT boundary
> clarity — followed by documentation of the result.

## 1. Purpose & Method

Six dimensions, applied recursively at every level (pillar-vs-pillar, doc-vs-doc, check-vs-check,
test-vs-test):

1. **MECE** — anything redundant/overlapping to consolidate; any gap covered by nothing.
2. **Feedback loops** — does every problem-detector actually prevent recurrence, or just log it.
3. **5-Whys root cause** — is each existing fix/guard a true root-cause fix or a symptom patch.
4. **Alternative perspectives** — is there a fundamentally different approach nobody considered
   because everyone anchored on the current framing.
5. **Resource efficiency** — where is token/compute spent without proportional value, and where
   is more spend actually warranted.
6. **Boundary clarity** — are MUST-do/MUST-NOT-do invariants unambiguous with enough concrete
   examples.

**Method:** the audit was split across two independent passes to get genuinely
non-redundant coverage — ag audited the governance/docs/config layer (`docs-v2/`,
`protocol.json`, `orchestration.json`, `backlog.json`); cx audited the code/checks/tests layer
(`hub.py`, `_sys/checks/`, `_sys/tests/unit/`). The terminal (cc) independently spot-verified the
most consequential claims from both against live files before synthesis. cc.fable then
cross-arbitrated both passes, resolved tensions, and ruled on open questions. This document
records that full chain — see §11 for exactly who verified what.

## 2. Executive Verdict

The system is in good working health. No dimension surfaced a systemic failure. What the audit
actually found is two **meta-patterns**, each independently rediscovered from both the docs side
and the code side — which is itself evidence the two-layer/peer-equality audit design works as
intended:

- **Meta-Finding A — Detection→Prevention Gap:** this system is excellent at *detecting and
  recording* problems, and systematically weaker at *wiring detection into enforcement*. See §3.
- **Meta-Finding B — No Retirement Discipline:** superseded artifacts (docs, code paths, tests)
  tend to coexist with their replacements rather than being retired in the same change. See §4.

One concrete, previously-unnoticed bug was found and confirmed during this audit:
`check_contracts.py`'s internal-error path silently converts to `sys.exit(0)`, which is
indistinguishable from a genuine pass (§5).

## 3. Meta-Finding A: Detection→Prevention Gap

Five independent findings across both audit layers converge on one pattern:

| Finding | Layer | What is detected | Why it doesn't close the loop |
|---|---|---|---|
| `check_sandbox_behavior.py` | code (cx) | Real CLI sandbox-enforcement outcomes, with observed-JSON emission | No hub routing/eligibility consumer found — report-and-remember |
| AP-20 coordinator-monopoly guard | docs (ag) | A peer violating the coordinator-monopoly rule | Hard `sys.exit(1)` with no directive auto-promotion — the peer can blindly retry the same blocked action |
| `check_encoding.py` | both (ag + cx, independently) | UTF-8/mojibake corruption | Catches corruption **after** the write, not before — a true root-cause fix would prove write-safety first |
| `self_care.py` follow-up subprocess calls | code (cx) | N/A — this is the gap itself | Return codes from its own remediation attempts aren't checked or recorded into `state["errors"]` |
| ag's FS confinement | docs (ag) | Unsafe writes, but only after the fact via git-diff guard | Restates T8's already-accepted risk — not new, but the same shape of gap |

**Remediation status:** the `check_encoding.py` instance of this pattern is **already
remediated** by T20/T21's ratified capability-canary design (measured, peer-agnostic
write-safety scoring, replacing after-the-fact detection with before-the-fact proof — see
`_sys/ai/backlog.json` items T20/T21). The other four are tracked as new backlog items (§9).

## 4. Meta-Finding B: No Retirement Discipline

| Artifact pair | Status |
|---|---|
| `permissions.md` §8 vs `lifecycle.md` §18 (mutation boundary) | Near-verbatim duplicate — confirmed by direct read, both describe `SANDBOX_RENAME_DENIED`/broker-submit/atomic-replace |
| `protocol.md` §3.1 vs `learning.md` §1 (feedback loop) | Overlapping authority for the same operational loop |
| `lifecycle.md` §15 vs `learning.md` §4 (recovery/self-care) | Overlapping authority for RED/STALE peer-state handling |
| `_write_json_atomic`'s live broker fallback (`hub.py:735,750`) vs `_enqueue_hub_mutation_request` (`hub.py:788`) | Two parallel broker code paths — one active fallback, one inert future-API stub that journals intent but is gated off by `hub_mutation_broker_enabled` |
| `test_guard_dry_run.py` vs the newer operational-guard-matrix oracle + `check_operational_guard_matrix.py` | The old 5-case/20-shuffle soak test is now largely superseded by the exhaustive 54,912-case matrix check |
| `l1_core/l2_policy/l3_mocked` test taxonomy vs flat test files | Both organizational schemes coexist; drift, not a deliberate hybrid |
| `_sys/core/setup.py` | Documented-legacy dispatch wrapper, no check proving no stale caller still depends on it |

**Proposed convention (not yet adopted — recorded here per cc.fable's synthesis):**
*"supersede ⇒ retire in the same commit."* When a new mechanism replaces an old one, the change
that lands the new mechanism should also remove or explicitly stub the old one, rather than
leaving both live.

## 5. Ruling: `check_contracts.py` Gate Policy

**Confirmed bug (verified directly, `_sys/checks/check_contracts.py:129-139`):** `run_contracts()`
returns `rc=2` on internal error (pytest missing, timeout, test file not found). `main()`'s
handling of `rc==2` prints a `WARN (fail-open)` message and then calls `sys.exit(0)` — the exact
same exit code as a genuine pass. A caller checking only the process exit code (e.g. a pre-commit
hook) cannot distinguish "contracts verified and passed" from "the verifier itself is broken."

**Ruling (cc.fable, ratified):**

1. **Tiered fail-closed:** on internal error (`rc==2`), fail **closed** (block the write) if the
   changed file is in the DIR-003 governed-core set (`hub.py` and the contract-protected API
   surface) — these are exactly the files whose corruption motivated building this gate in the
   first place; if the checker is broken, that's precisely when a mutation to `hub.py` shouldn't
   proceed unreviewed. `--force-tier0` remains the human override. Fail-open is retained for
   files outside that governed set.
2. **Never exit 0 on internal error, anywhere:** preserve a distinct exit code (e.g. keep `2`, or
   a dedicated code) so the caller can always tell "passed" from "gate broke" apart. The current
   silent 2→0 conversion is the actual defect, independent of the fail-open/closed policy choice.
3. **Log + escalate:** every fail-open event writes an `operational_errors.jsonl` record; a
   consecutive-fail-open cap (default N=3, config-declared) escalates to fail-closed until a
   genuine pass is observed — mirroring the same evidence-triggered-escalation shape already used
   elsewhere in this system (e.g. the npm install retry-classification pattern from D11).

**Status: ratified design, not yet implemented.** Tracked as a Tier-1 backlog item (§9).

## 6. Ruling: Documentation Consolidations

| Duplicate pair | Canonical | Becomes a stub |
|---|---|---|
| Mutation boundary | `permissions.md` §8 (already the DIR-002-cited authority for who-may-mutate-what) | `lifecycle.md` §18 (jurisdiction is state *transitions*, not mutation *rights*) |
| Feedback loop | `learning.md` §1 (owns the 5-Whys/learning-loop mechanism) | `protocol.md` §3.1 (stubs to learning.md) |
| Recovery / self-care | Split by concern: `lifecycle.md` §15 keeps runbook **mechanics**; `learning.md` §4 keeps autonomy **bounds** | Each cross-references the other explicitly |

**Rule for landing these:** each consolidation must ship as a single commit (canonical-section
edit + stub-ification together), so no window exists where both copies are simultaneously live
and could drift apart. **Status: ratified, not yet implemented.** Tracked as a Tier-2 backlog item.

## 7. Boundary Clarifications

- **`COLLAB_RATE` R:3 vs R:5 ambiguity:** the table currently reads "R:3 applies to `_sys/`
  changes" and "R:5 applies to a single `_sys/` script edit" without disambiguating which governs
  editing exactly one system script. Needs a worked example distinguishing "multi-file `_sys/`
  change" (R:3) from "single-script edit" (R:5).
- **PRO-01 raw-vs-sanitized shell text:** prohibits "passing raw user shell text as
  executable/flag fragments" with no concrete example of what counts as raw versus
  sanitized/parsed. Needs a worked before/after example.

**Status: both are cheap, real documentation gaps.** Tracked as a Tier-2 backlog item.

## 8. Considered Alternatives & Revisit Triggers

| Alternative | Verdict | Reasoning | Revisit trigger |
|---|---|---|---|
| Replace `hub.py`'s `main` branch-chain dispatcher with a declarative action registry | **Pursue** | Only alternative with near-term ROI: incremental, testable, structurally prevents the "new action forgot its guard" bug class | — |
| Unify `check_cli_canary`/`check_cli_reality`/`check_sandbox_behavior`'s repeated probe concepts into a shared probe-result framework | **Pursue-lite** | Build T20/T21's canaries on a shared probe-result core now that they're ratified; retrofit the three existing checks opportunistically, no big-bang rewrite | — |
| Local SQLite store instead of flat-file IPC (`handoff.md`, `.ai/state.json`) | **Rejected** | Flat files' human-inspectability and git-diffability are load-bearing for this governance model — the terminal *reads* handoff.md directly; the audit trail *is* git history; the broker/atomic-replace patterns already work and are tested | A measured contention or corruption incident — not aesthetics |
| Direct vendor API/SDK integration instead of CLI-wrapper orchestration | **Rejected** | The CLI-wrapper premise is economic (subscription quota pooling vs per-token API billing), and the entire DIR-004 measurement apparatus (fingerprinting, canaries, observed-reality reconciliation) is built around CLI reality | Vendor CLI deprecation, or API pricing reaching parity with subscription economics |
| Reorganize tests by invariant ownership (transport/governance/encoding/routing/provisioning) instead of backlog-ID chronology | **Accepted, low urgency** | Backlog IDs age poorly as a test-organization scheme; batch with the test-taxonomy cleanup (§4) | — |

Recording the rejected alternatives with explicit revisit triggers is itself the answer to
dimension 4 (alternative perspectives) — the next auditor doesn't need to re-derive these from
scratch, only check whether a trigger has fired.

## 9. Ranked Action Register

**Tier 1 — load-bearing, act near-term:**
1. `check_contracts.py` tiered fail-closed + stop silently converting internal-error exit codes
   to 0 (§5).
2. AP-20 hard-exit with no directive auto-promotion — wire a blocked coordinator-monopoly
   violation into a runtime directive so the peer doesn't blindly retry (§3).
3. `self_care.py` unchecked subprocess return codes — record follow-up-command failures into
   `state["errors"]` (§3). Small fix, disproportionate value.
4. `check_sandbox_behavior.py` measured data has no consumer — wire it into eligibility/diag, or
   explicitly label it advisory-only so it isn't mistaken for enforcement (§3).

**Tier 2 — legitimate, schedule normally:**
5. Three documentation consolidations (§6).
6. `COLLAB_RATE` R:3/R:5 + PRO-01 worked examples (§7).
7. Retire or activate `_enqueue_hub_mutation_request`'s inert parallel broker path (§4).
8. Delete or merge `test_guard_dry_run.py`'s now-redundant soak test (§4).
9. `conftest.py`'s `os._exit(1)` OOM guard — write a diagnostic marker file before force-exit,
   so a hard-killed test run leaves a trace (verified: `_sys/tests/unit/conftest.py`).
10. `core/setup.py` stale-caller check, or a planned removal condition (§4).
11. Test-taxonomy inconsistency — batch with item 6's invariant-based reorg as one hygiene pass.

**Tier 3 — correctly identified, not worth acting on yet:**
- `hub.py`'s ~8,980-line scale — real, but should be attacked via the action-registry (§8's
  first "pursue"), not a big-bang decomposition.
- Runtime-directive broadcast to all peers regardless of relevance — add a failure-class scoping
  tag someday; not urgent.
- Static-metadata/regex-only routing (the "Zero-Token Boundary") potentially misrouting complex
  prompts to cheap profiles — legitimate hypothesis, but reversing a deliberate zero-token
  decision needs measurement first. `ask_history` now has enough real data to measure actual
  misroute cost before changing anything. **TEST NEEDED, not action.**

## 10. Closed / Rejected Findings

- **ag's FS-sandbox-confinement finding** restates T8's already-accepted-risk closure
  (2026-07-12) — not a new finding, same conclusion reached independently.
- **`check_encoding.py` is symptom-level** (found independently by both ag and cx) — already
  answered by the ratified T20/T21 capability-canary design.
- **SDK-vs-CLI and SQLite-vs-flat-file** "alternative perspective" findings — real observations,
  not actionable findings; recorded with explicit revisit triggers in §8 rather than acted on.

## 11. Appendix: Verification Ledger

This audit tries to hold itself to the same DIR-004 standard it audits the system against —
every consequential claim below is tagged with who verified it and how.

| Claim | Source | Verification |
|---|---|---|
| `permissions.md` §8 / `lifecycle.md` §18 near-duplicate | ag | **Verified** — terminal (cc) read both sections directly, confirmed near-verbatim overlap |
| `check_contracts.py` exit-2-as-fail-open | cx | **Verified** — terminal read the file directly, docstring + code match exactly |
| `check_contracts.py`'s 2→0 exit-code conversion | cc.fable (found during synthesis, not in either original pass) | **Verified** — terminal read `check_contracts.py:136-139` directly, confirmed |
| `_enqueue_hub_mutation_request` inert parallel broker path | cx | **Verified with correction** — function exists and journals intent gated by `hub_mutation_broker_enabled`; cx's exact phrasing ("raises NotImplementedError") was imprecise, but the substance (an inert/parallel code path) is real |
| `conftest.py`'s `os._exit(1)` OOM guard | cx | **Verified** — terminal read the file directly |
| `test_guard_dry_run.py` redundancy vs the new operational-guard-matrix tests | cx | **Verified** — terminal confirmed both files coexist |
| AP-20 hard-exit with no directive promotion | ag | **Declared, not independently re-verified this round** — plausible given the documented mechanism, not directly read line-by-line by the terminal |
| `check_sandbox_behavior.py` has no hub consumer | cx | **Declared, not independently re-verified this round** — cx's own search found no consumer; absence-of-evidence claim, would need a repo-wide grep to fully confirm |
| `self_care.py` unchecked return codes | cx | **Declared, not independently re-verified this round** |
| Static routing potentially misrouting complex prompts | ag | **Hypothesis, explicitly marked TEST NEEDED per cc.fable's ruling** — not measured |

---
*This document is a point-in-time audit record (2026-07-12). Per docs-v2's doc-status
taxonomy, this is a `historical` artifact under `_sys/docs/history/` — action items derived from
it live in `_sys/ai/backlog.json` (see §9's numbering for cross-reference), and any documentation
consolidations ratified here (§6) should be applied to the `living` docs-v2 pillars directly,
not by editing this record after the fact.*
