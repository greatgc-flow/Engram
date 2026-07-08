# Remaining Backlog Items — Pre-TDD Detailing (2026-07-08)

> Follow-up to today's earlier rounds. ag detailed T3/T4/T5 (process/meta issues from
> today's own session); cx detailed B7/D2/P1 (product features, already partially
> speced). cc.fable arbitrated, with one significant safety refinement (T4). This is
> discuss-and-document only — nothing here was implemented this round.

## T4 — governed-mutation enforcement: capture-then-quarantine-then-conditional-revert

**The most consequential item.** ag admits candidly: prompt-level "DO_NOT edit files"
constraints structurally lose to agentic training — once a solution is found deep in a
tool-calling loop, the action-oriented drive overrides the earlier negative constraint.
This happened 7 times today (T2, D6, D2, C, D6-round2, D2-round2, T7) — every single
time with content matching what was reported, zero actual harm, but currently only
`GOVERNED_MUTATION_VIOLATION` warn-and-log (`_governed_post_check`, hub.py:3192-3217).

ag's first-draft fix (blanket `git checkout -- <file>` auto-revert) has a fatal flaw
cc.fable caught: **the empirical record cuts the opposite way from how ag read it** —
7/7 correct writes means a blanket revert would have destroyed valid work 100% of the
time. `git checkout --` restores to HEAD, not pre-ask state, so if the file had
legitimate uncommitted changes *before* the ask (terminal WIP, a concurrent authorized
ask), blanket revert destroys those too.

**Refined design (fable):**
1. **Capture first**: on detection, write the offending content as a patch/full-copy to
   `.ai/quarantine/<ask_id>/` before touching anything. The failure record points there
   so cc can `git apply` deliberately — restores review authority to where PRO-19 says
   it belongs, at near-zero cost.
2. **Revert only when provably safe**: auto-revert (`git checkout --`) ONLY if
   pre-ask hash == HEAD hash (file was clean at dispatch — HEAD *is* pre-ask state). If
   the file was already dirty pre-ask, quarantine + loud fail only, no revert.
   Untracked new governed files need the delete path, not checkout.
3. **Guard the race**: re-hash between detection and revert; if changed again
   (concurrent writer), abort the revert and warn rather than fight over it.
4. **Fail the ask, keep the report**: mark the ask violation/failed (nothing downstream
   treats state as clean) but preserve the peer's textual report in the failure record —
   the analysis was fine in all 7 cases; discarding it punishes the caller, not the peer.

**Status: ready for TDD** (reject only the blanket form; capture + conditional-revert +
race guard is safe and worth building). **Priority: build this first if only one item
gets built** — it's the only item guarding an active, recurring integrity hole, and the
detection layer + sha256 snapshots + test scaffolding (`test_governed_guard.py`) already
exist, so the delta is capture + conditional-revert + race guard, not a new system.

## T3 — ag's 900s zombie timeout

ag's self-assessment: context dilution across many tool calls, its tool-calling loop
doesn't flush partial output (accumulates until final completion — if combined time
exceeds 900s, caller gets zero output), and task entanglement (planner jumps between
items, redundant calls, deeper trees).

**cc.fable refinement**: confirm the fail-fast half, drop the silent auto-split of free
text — an item-count heuristic requires parsing task structure out of prose (brittle),
and mechanically splitting "compare these 7 items" breaks cross-item context. Fail-fast
with a "split this" warning by default; auto-split only when the caller passes a
structured task list (not prose). Thresholds are config-declared heuristics (DIR-004),
tuned later from `ask_history.jsonl`.

**Status: ready for TDD** (pre-dispatch fail-fast heuristic in hub.py; no silent
auto-split of prose).

## T5 — cx's tempfile create-but-cannot-delete sandbox issue

ag's analysis: classic Windows ACL/permissions issue — sandbox allows create but
restricts delete on %TEMP%/%TMP%. Fix: hub.py creates a dedicated, guaranteed
writable/deletable dir under `_sys/data/temp/cx_session_<id>` before invoking cx,
injects via TEMP/TMP/TMPDIR, tears down after.

**cc.fable confirmation, with one condition**: the mechanism reasoning holds *because*
sandbox denial is path-scoped (workspace-write allows create+delete inside the
workspace; %TEMP% lives outside it) — so redirecting TEMP into the injected path
genuinely addresses the mechanism, not just moves the problem. But this is
reasoned-declared, not measured — **TDD must include an empirical probe** (create+delete
inside the injected TEMP under the real cx sandbox) before claiming fixed.

**Status: ready for TDD**, with a mandatory empirical verification step.

## B (B7) — sandbox behavioral probe

cx's sharpened spec: new `_sys/checks/check_sandbox_behavior.py`, reusing the
check_cli_reality.py/check_cli_canary.py precedent (real binaries, budgeted, no config
mutation). Creates `_sys/data/temp/sandbox-probe/<probe_id>/{workspace,outside}`,
sends an exact unambiguous prompt asking for one write outside the workspace, classifies
by actual sentinel-file existence (not the printed marker alone). Manual/opt-in only.

**cc.fable found one real gap**: the "outside" dir sits under `_sys/data/temp/…`, which
is *inside the repo*. If a CLI's sandbox root is repo-derived rather than cwd-derived,
writing there is still in-bounds — the probe could reach a wrong conclusion about
*what* is being confined (cwd vs repo), even though it can't produce a false
"enforced" pass. **Fix**: two outside targets — one outside-cwd-but-inside-repo, one
disposable outside-repo path — to disambiguate confinement scope. Also add a
per-invocation timeout + budget guard (mirroring check_cli_canary) and ensure cleanup
runs even on `classification=error`.

**Status: ready for TDD**, with the two-outside-target refinement folded in.

## D2 — INV-26 soak-promotion criterion

cx's sharpened spec, confirmed by cc.fable as "the right bar, not overkill" (the three
gates test different failure classes — correctness, state leakage, distribution
reality — and ≥24h/≥100 live evaluations is modest, not excessive):

1. **Static exhaustive matrix** generated from live `protocol.json` (action groups ×
   phase_action_matrix × collab_rate_guard.exempt_actions × origins) — zero false
   positives/negatives required.
2. **100-pass deterministic shuffle** over that matrix, fixed seed, zero mismatches
   (catches hidden state leakage).
3. **Live shadow**: ≥24h and ≥100 real `_guard_action` evaluations, dry-run vs actual
   outcome, zero mismatches.

**cc.fable's one addition**: define what happens when the live shadow sees an action
shape absent from the static matrix — that's a coverage gap that must EXTEND the soak
(add the missing case to the static matrix and re-run gates 1-2), not silently pass
gate 3.

**Status: NOT ready to promote fail-closed** (that requires the full 3-gate soak to
actually run and pass); **ready for TDD** on the exhaustive-matrix generator + live-shadow
logger infrastructure itself.

## P1 — root hygiene gate

cx's sharpened spec, confirmed by cc.fable as ready as-spec'd: new
`_sys/checks/check_root_hygiene.py` (not extending check_docs_mece.py). Allowlist =
today's verified live root entries (`.agents .ai .claude .git .gitattributes .gitignore
.pytest_cache .vscode _archive _sys AGENTS.md CLAUDE.md CLEANUP.bat CONVENTION.md
Engram.exe GEMINI.md INSTALL.bat PROTOCOL.md README.md register.bat tmp unregister.bat
workspace wrapper.cs`). Default mode scans root children only, exits 2 on unexpected
entries. `--closure` mode also runs git status/diff-check/check_backlog.py. NOT
pre-commit-blocking on day one (legitimate root additions need an allowlist-update
path first).

Confirmed empirically: this WOULD have caught every root-level stray-file incident from
today; would NOT catch `_sys/data/temp` buildup (gitignored — a separate, lower-priority
concern with a different consumer: git history vs disk space).

**Status: ready for TDD as spec'd.**

## Not part of this round — already resolved or externally blocked

- **D4, F1**: already resolved earlier today (both deferred/rejected with clear
  rationale) — no further design work applicable.
- **P2, P5**: blocked purely on the user's own retention-policy decision for
  `_sys/gemini/**` and `_archive` (68M) respectively — not something ag/cx/fable
  discussion can resolve further. Needs the user's explicit call, not more design.
