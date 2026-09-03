# Purpose-Centered Final Closure Review — 2026-07-17

> Status: living | Follow-up to `ops/mega-mece-audit-2026-07-16.md` (that audit's Track1-3 findings were ALL implemented and merged before this review started).

## Process

Full 5-way unanimous-debate protocol, run twice:

- **Round A** (independent, parallel): cx.effort, cx.deepthink, ag.effort, ag.deepthink each reviewed the whole project against 8 closure lenses (recursive MECE, recursive feedback-loop closure, recursive 5-Whys root-cause resolution, alternative-perspective check, resource-efficiency vs effectiveness, MUST/MUST-NOT boundary clarity, MECE-ambiguous catch-all, overwhelming-advantage filter), anchored on README.md's stated purpose.
- **ag.deepthink's Round A response was discarded as unreliable**: it admitted mid-response that the prompt was truncated in its context, then answered against a self-invented 8-lens framework instead of the one given, and asserted as fact that `.ai/sessions/` directories are "now recursively wiped via `shutil.rmtree`" — directly false; that exact change had been reverted earlier in the same session as unsafe. Not used in any convergence decision below.
- ag.effort and cx.effort reported "mostly clean, doc-hygiene-level gaps only." cx.deepthink reported "NOT CLOSED" with much deeper, architectural-level findings.
- **Round B**: cx.effort and ag.effort independently re-verified every one of cx.deepthink's claims from scratch (fresh file:line citations, not trusting the Round-A citations). All 7 substantive claims came back CONFIRMED (one, the unconsumed-`governance_params.json`-key count, came back *worse* than originally stated: 50-55 of 61 keys, not ~46).
- A separate, directly-observed finding (not from any peer paper): `default:cx.effort`/`default:cx.deepthink` sessions had been continuously reused since 2026-07-16T17:04 across every unrelated debate that night; the single most recent `cx.deepthink` call's `cost-log.jsonl` entry showed **33,232,646 input tokens** for one ask. Confirmed by direct inspection of `session_state.json` (codex session state, removed in separation) and `_sys/data/logs/cost-log.jsonl`, not a peer claim.


## Findings and resolutions

| # | Finding | Verdict | Resolution |
|---|---|---|---|
| 1 | Two independent, disagreeing consensus engines exist (JSON rounds vs Markdown `_sys/ai/proposals`) — different voter-health rules, no cross-link. | Confirmed (3/3 peers) | **Deferred.** Genuine unification/refactor, not a same-session fix. Needs its own design pass. |
| 2 | **INV-03 violation**: RED peers were silently dropped from the voter snapshot at `action_consensus_propose()` time (never counted, no human_gate); `--voters` let a caller silently replace the canonical voter set with an arbitrary subset at R:10. | Confirmed (3/3 peers), then directly verified against INV-03's exact text ("offline peer auto-abstain does NOT satisfy unanimity. Human override required.") | **Fixed** (`b56da31`). Full voter list now snapshotted as-is; existing, already-tested `_decide_consensus` RED-voter handling (`mid_round_closed` → `escalated`/`human_gate`) now actually runs for RED-at-proposal-time peers, not just RED-mid-round ones. `--voters` at COLLAB_RATE≥10 must match the canonical set exactly or the propose is rejected. |
| 3 | ~50-55 of 61 non-metadata `governance_params.json` keys have zero Python consumers ("declared but unenforced," the audit's own recurring pattern). | Confirmed (3/3 peers) | **Deferred.** Safe in principle (peers independently grepped and found zero refs) but pruning 50+ keys deserves its own careful pass, not a rushed same-session sweep. |
| 4 | `directive-add`/`directive-clear` classified `read_only`, but they mutate `_sys/ai/runtime-directives.jsonl` — PRO-19's terminal-mutation guard never fired for them. | Confirmed (3/3 peers) | **Fixed** (`2777bad`). Moved into `operational_guard.mutating_hub_actions` (the list `_is_mutating_action()` actually checks); removed from `read_only_hub_actions`. Also de-duplicated `context-ack`'s redundant `read_only_hub_actions` entry (already correctly in `recovery_hub_actions`). |
| 5 | `--allow-governed-mutation` bypasses the LL-20260703-005 hash guard entirely, with zero gating on who can pass it and zero internal callers (only reachable via the raw CLI flag), despite its docstring claiming "authorized broker/consensus execution." | Confirmed (3/3 peers) | **Fixed** (`191fe42`), minimal audit-trail version (not the full scoped-capability system the peers recommended as the eventual root fix). Now requires a non-empty `--governed-mutation-reason`; missing reason fails closed (guard still runs); a granted bypass is logged as a high-severity AUDIT event. |
| 6 | `autonomous_maintenance` reads as an autonomous cron scheduler but has no timer/dispatcher — only fires at `ctx-start.bat`/`ctx-end.bat` hook points. | Confirmed (3/3 peers) | **Fixed** (`987e728`), doc-only. Clarified in `protocol.json`'s `_doc` field; the hook-based design itself is fine, the naming was misleading. |
| 7 | Pacing ≤1.0 hard gate's ratified design (mega-mece-audit-2026-07-16 Q2) specified `confirmation_count: 2` (two independent fresh breach observations before hard-blocking) and a human-only `--force-pacing` break-glass override. Neither shipped — single-reading gate, no override flag exists. | Confirmed (3/3 peers) | **Deferred.** The original audit itself flagged this as needing its own TDD pass (touches 6 call sites in live routing dispatch); not safe to rush at the end of an already very long session. |
| 8 | Session-reuse scope defaults to `default:{profile}` regardless of topic, so unrelated debates share one ever-growing session (33M input tokens observed on one call). | Confirmed directly (not a peer claim) | **Operationally mitigated, not code-fixed.** Switched to `--session-policy fresh` for all debate dispatches from Round B onward. The real fix (auto-derive a scope from topic/task context in `_compute_scope_key` when none is given) is a real feature, deferred alongside #1/#3/#7. |

## Deferred backlog (not implemented tonight — explicitly flagged, not silently dropped)

1. Unify the two consensus engines (JSON rounds absorb Markdown proposals; proposals become a view, not a second write path).
2. Governance_params.json dead-key pruning (~50-55 keys) — safe in principle, needs a dedicated careful pass.
3. Pacing `confirmation_count: 2` state machine + `--force-pacing` human break-glass override — touches 6 live routing call sites, needs its own TDD pass per the original audit's own recommendation.
4. Auto-derived session scope (stop `default:{profile}` from silently spanning unrelated topics) — real feature, not a quick patch.

## Process finding

ag.deepthink is unreliable for large (8-lens, ~5KB prompt), read-only analytical asks: it silently truncated the instructions and then fabricated a plausible-sounding but factually wrong report rather than flagging the truncation and refusing to guess (DIR-004). ag.effort, on the same class of task, performed reliably both times (Round A and Round B, including a genuine foreground/backgrounding failure recovery). Treat ag.deepthink's output on long analytical prompts as unverified until independently cross-checked, same as any other single-source claim.
