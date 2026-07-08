# Backlog Re-triage Round 2 (2026-07-08)

Trigger: diag.py POLICY/SUMMARY section-order fix + settings.json revert + Engram
packaging-artifact cleanup surfaced new findings. ag.deepthink + cx.deepthink ran
independent 5-Whys/MECE passes over the full `_sys/ai/backlog.json` (19 items incl. T1).

## Convergent findings (both peers agreed)

**Stale/done, archive candidates**: A, D1, G1 (done — evidence-committed, no longer
live work) and D3, P4 (already dropped/superseded). Recommend moving these out of the
active view into an archive section on the next backlog schema pass — not applied here
(structural change, needs a separate sign-off).

**Generalize**:
- T1 (test path mismatch) → don't fix narrowly. `P:` is a `subst` of
  `D:\PortableDev (v2.0)`; code mixes `Path(__file__).resolve()` (subst-resolved) with
  raw drive-letter paths (unresolved) across hub/CLI/tests. Needs one canonical
  root-identity helper, not a per-test patch.
- D5/D3/D6 → unified peer/profile resource governance (health + quota + cost + context
  + in-flight) instead of separate mechanisms per concern.
- P2 → generalize to a reusable "retired-peer decommission protocol" (not gc/gemini-specific).
- G-VOTER/D7 → consensus-artifact lifecycle hygiene, same bucket.

**Efficiency (cross-cutting, not per-item)**:
1. One canonical root/path-resolution helper (fixes T1, prevents recurrence).
2. One unified snapshot/probe feeding routing + quota + health + diag, replacing
   several separate chatty probes.
3. One scheduled drift/fingerprint scanner (budget-capped) covering C/P1/P4/T1
   source-doc staleness instead of ad-hoc manual checks.

**Feedback loop (both proposed the same shape)**: an automated `backlog-refresh` job
that reads test/check failures + lessons + health/ask logs, scores them (recurrence,
blast radius, staleness, evidence freshness), and either auto-registers a `proposed`
backlog item or emits a triage report — human/peer consensus still required before it
patches `backlog.json` itself. Goal: make exhaustive manual re-triage rounds like this
one increasingly unnecessary.

## Applied this round
- T1 reframed to the generalized scope (see backlog.json).
- New item F1 added: the backlog-refresh feedback-loop mechanism above (`proposed`,
  not yet implemented).
- Everything else above is a recommendation, not yet applied — needs explicit go-ahead
  before merging/archiving existing IDs.
