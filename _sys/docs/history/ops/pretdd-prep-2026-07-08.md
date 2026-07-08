# Pre-TDD Prep — D5 / P2 / Backlog-SSOT (2026-07-08)

> Follow-up to `backlog-5whys-consensus-2026-07-08.md`. Design/spec only — no code changes made. Peers: ag.deepthink (169s), cx.deepthink (127s). cc verified both against live source (`hub.py`, `hub_profile_router.py`, `snapshot.py`, `hub_health.py`) before synthesizing — one peer claim was corrected as a result.

## Item 1 — D5 Per-Profile Health: READY FOR TDD (gap-completion, not greenfield)

**Verified against source (cc):** the write/read plumbing is already substantially in place — this is a real, narrow gap, not a new feature.
- `hub.py:1819` `_record_ask_success(..., profile_key=...)` and `hub.py:1898` `_record_ask_failure(..., profile_key=...)` already write to `health.json` under `availability.profiles.<name>` (confirms cx; **ag's proposal to add this logic in a new `hub_health.py` is wrong** — `hub_health.py` is an explicitly read-only summary/CLI reader (its own docstring: *"Does NOT duplicate hub.py's write logic — reads only"*) and has no profile awareness at all today; the write path stays in `hub.py`).
- `hub_profile_router.py:180` `_eligible_profile(root, requested, profile_order, health)` **already reads** `health["availability"]["profiles"][candidate]["gate_open"]` and `rate_limit_state`, walking the fallback chain — this ask-time gate already works.
- **The actual gap, confirmed by reading `snapshot.py:1027`**: `_build_profile_rows()` sets `"state": prof.get("routing_state") or "unknown"` — i.e. the snapshot/routing-candidate view is **config-only**, and never looks at `health.json`'s `availability.profiles[profile].gate_open`. So `select_load_balanced_peer()` can route bulk traffic to a profile that `_eligible_profile()` would have refused at ask-time. That inconsistency is the real D5 deliverable.

**Spec:**
- Schema (already in use, no change needed): `availability.profiles.<name> = {gate_open, consecutive_failures, rate_limit_state, last_failure_at, ...}`.
- Change: `_build_profile_rows(orch, peer_records, observed_at)` in `snapshot.py` gains a `health` lookup per peer (mirror what `hub_profile_router.py` already does) and folds `gate_open`/expired-cooldown logic into the `state` field instead of using `routing_state` alone.
- `_healthy_peer()` (`hub.py:2258`) stays a peer-aggregate signal: true if root healthy AND at least one profile open — no change needed, already correct per both peers.
- Edge cases (both peers agreed): missing profile health → treat as eligible (config-only); profile removed from config → excluded by config check before health is even read; expired `cooldown_until`/`reset_at` → treat as open, don't require a write to clear it.

**TDD targets:** closed `ag.gptoss` absent from load-balanced candidates while `ag.opus` stays eligible; all-profiles-closed ⇒ `_healthy_peer("ag") == False`; missing profile health doesn't block; stale/removed profile health ignored; expired cooldown unblocks without a write.

## Item 2 — P2 gc/gemini residue: PLAN READY, execution needs a retention decision first

Both peers converged on the same order — **code fallbacks → config → binaries/docs last** — because removing config/binaries while `hub.py` still falls back to `"gc"` risks KeyErrors/broken routing. Reported line numbers (hub.py ~1570/3067/4358/4422) are approximate and drift-prone; re-grep at execution time, don't trust either peer's line numbers as-is.

- **Phase 1 (code):** strip `gc`/`gemini` fallback literals in `hub.py` (voter fallback lists, ContextGate `failover_model`, `check_gate.default_agent` default, any fixed peer-loop tuples) — replace with config-derived enabled-peer lists, not a hardcoded new default.
- **Phase 2 (config):** remove `gemini` peer entry + `gc` alias from `peers.json`; scrub `orchestration.json`/`routing-config.json` mentions.
- **Phase 3 (binaries/tests, last, gated):** `_sys/cli/gemini*`, then `_sys/gemini/**` — **cx flagged `_sys/gemini/**` may hold non-regenerable config/history/auth-like files; do not delete until a retention decision is made** (this is the one open question blocking full execution — needs your call, not a peer decision).
- Verification command for execution time: case-sensitive `rg "gc|gemini|Gemini|GEMINI"` across `_sys/core _sys/ai _sys/cli _sys/tests _sys/docs-v2` — exclude ag's Gemini-*family model* references (those are legitimate, not residue) and `_sys/docs-v2/specific/gc.md` (keep as tombstone).
- Rollback: split into 2 commits (runtime decouple, then deletion) so a routing break can `git restore` just the second commit.

**Status: ready for TDD on Phase 1/2; Phase 3 physical deletion blocked on your retention decision for `_sys/gemini/**`.**

## Item 3 — Backlog SSOT migration: format disagreement, resolved

- **cx**: `_sys/ai/backlog.json` as SSOT (schema, status enum, `evidence_commit` must resolve to a real git hash, a `check_backlog.py` validator) + optional generated Markdown view.
- **ag**: `_sys/docs-v2/ops/BACKLOG.md` as SSOT (human-readable, git-diff friendly), with a "DONE requires a real commit hash" check bolted onto `check_cli_reality.py`.
- **Resolution (cc judgment): go with cx's JSON-as-SSOT.** The entire reason this exercise started was that a prose/memory-based backlog silently went stale (3 items this round alone: A, D1, G1) with no mechanism catching it. JSON + a dedicated validator makes "evidence_commit must exist in git" and "done requires evidence" *enforceable*, not just a documentation convention — which is exactly the failure mode just observed. Markdown alone (ag's option) repeats the same class of problem it's meant to fix. Take cx's suggestion to still render a derived `.md` for human skimming.
- Schema: `{schema_version, updated_at, items: [{id, title, status, priority, category, owner, blocker, evidence_commit[], supersedes[], source_refs[], next_action, risk, last_verified_at}]}`. Status enum: `proposed|active|blocked|deferred|done|dropped|superseded`.
- Migration: seed from `backlog-5whys-consensus-2026-07-08.md` + `backlog_reorg_2026_07_04.md`, mark today's DROP/DONE items with their evidence commits, keep old docs/memory as historical (not SSOT) with a pointer.
- New check: `_sys/checks/check_backlog.py` — valid schema, unique ids, `supersedes` targets exist, `done/dropped/superseded` requires an `evidence_commit` that resolves via `git cat-file -e`.

**Status: ready for TDD.**

## Claude Judgment

- **Adopt**: cx's D5 gap-completion framing (verified correct against source — the gap is exactly `_build_profile_rows` not reading profile health); cx's JSON-SSOT recommendation for item 3; both peers' P2 removal ordering.
- **Refine**: D5 spec corrected to *not* create a `hub_health.py` write path (ag's proposal) — writes already live in `hub.py`; `hub_health.py` should at most gain a read-only profile accessor later if needed for CLI display, out of scope for this gap-fix.
- **Counter**: ag's BACKLOG.md-as-SSOT rejected — same staleness failure mode this whole exercise exists to fix.
- **Next**: three items are TDD-ready except P2 Phase 3 (needs your retention call on `_sys/gemini/**`). Say the word and I'll start TDD on D5 (smallest, most isolated) first, or on backlog.json migration (unblocks future sessions immediately).
