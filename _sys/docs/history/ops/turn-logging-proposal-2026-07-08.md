# Per-Turn Logging Proposal — 끝장토론 (2026-07-08)

Trigger: user proposed logging every turn's input/output/tokens/context, comparing
against a "target," and closing the gap over time. ag+cx independently discussed
(adversarial, not convergence-seeking), cc.fable arbitrated.

## Verdict: reject the framing, fix a real narrower gap instead

**Both peers independently concluded, and cc.fable confirmed**: as literally framed —
"compare to a target, close the gap over time" — this is the same failure shape as F1
(the already-rejected backlog-refresh feedback loop, see round-2 pre-TDD docs): an
optimization loop with no defined actuator (what would autonomously change to reduce
tokens? prompt truncation risks context starvation) and no consumer for the delta.
**Rejected in this form.**

**The sharper distinction (cc.fable)**: turn-level resource *measurement* is not F1,
because populated token fields have *already-shipped consumers* — DIR-004 source-tagged
claims, D6's reserve/starvation telemetry, pacing penalties, and headroom math all
become measured instead of estimated once real per-ask token data exists. Measurement
feeding existing decision mechanisms is not a new speculative loop.

## The real, well-evidenced gap

`_sys/data/logs/cost-log.jsonl` already has 11,446 rows via `HubLogger.log_cost()`
(hub.py already calls `adapter.extract_usage()` for token fields on every ask) — but
recent rows carry real `latency_sec`/`success` values with **all-null token fields**.
cc.fable traced the root cause precisely:
- The base `extract_usage()` in `hub_peer.py` (line ~441-443) returns `{}`.
- **Neither `ClaudeAdapter` nor `AgyAdapter` override it at all** — there's no existing
  implementation to "update," one must be added from scratch.
- `CodexAdapter`'s existing extractor (line ~660-674) is broken for current output: it
  does `json.loads(stdout)` on what is now a JSONL event stream, not a single JSON blob
  — explaining why even cx's rows (the one adapter with extraction code) are null.

## Scope — build (narrow, additive-only)

1. `ClaudeAdapter.extract_usage()` (new): after subprocess close, read the `usage`
   block from the session JSONL (`~/.claude/projects/<project>/<session-id>.jsonl`),
   matched to the actual `session_id` the subprocess used, taking the final assistant
   record. Any ambiguity/read failure → `{}` (null fields, never an estimate, DIR-004).
2. `AgyAdapter.extract_usage()` (new): same pattern against Antigravity's
   `transcript.jsonl`.
3. `CodexAdapter.extract_usage()` (fix): parse the JSONL event stream line-by-line
   (token_count/usage events) instead of `json.loads` on the whole stdout.
4. All three feed the existing `logger.log_cost()` calls (hub.py:4251, 4407) unchanged
   — no schema change, no new pipeline, no new DB.

**Implementation cautions (cc.fable)**: session-file correlation MUST key off the
subprocess's own `session_id`, never "most recent file" (misattribution under
concurrent asks is the one real hazard — correct fallback is null, not a guess). The
read happens post-close (no added latency to the ask path); wrap it so a missing/locked
session file can never fail the ask itself.

**Acceptable optional addition**: an on-demand read-only aggregate view (`diag --tokens`
style) once data exists. On-demand only — no scheduled daily job.

## Explicitly NOT building, under any framing

- Raw per-turn input/output *content* logging.
- Any target — static or rolling — positioned as an optimization objective.
- cx's proposed rolling p75-regression alert (per profile × task-size bucket, 7d-vs-7d,
  >25%-for-2-days) — cc.fable: this embeds ≥4 unmeasured tuning parameters designed
  *before a single row of real token data exists*. Estimation dressed as rigor.
- ag's proposed static 150k-token context-warning gate — milder (one number, passive)
  but still an unmeasured threshold, and redundant with the `context_affinity` +
  session-reuse hysteresis that already shipped today
  (`token-session-policy-design-2026-07-08.md`).
- Both alerting ideas are **deferred, not rejected forever**: revisit only once (a) ≥2
  weeks of populated token data exists to derive real thresholds from, and (b) someone
  can name the specific decision the alert would drive. If those two conditions can't be
  met even then, it genuinely was F1 after all.

## Status

Documentation-only per the user's request. The narrow `extract_usage()` fix (items 1-3
above) has full peer + arbiter consensus and cc.fable explicitly assessed it as safe to
implement immediately (additive-only, every failure path degrades to today's existing
null-field behavior, no public-API signature change) — but implementation has not
started; the user's ask this turn was framed as discuss-and-document, so the fix is
presented as a recommendation pending explicit go-ahead, not auto-applied.
