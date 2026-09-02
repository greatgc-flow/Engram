# Sixth-round, final ratification-decision critique (cx.deepthink, 2026-09-02)

**Final verdict: NOT RATIFY.** Three of the four v5 corrections are
genuinely closed. The fourth (uninstall + executable acceptance gates) is
not, and the holistic pass found two new internal contradictions that
prevent v6 from being executable as written. Architecture, catalog
direction, DIR-002, and Gate 7 remain sound and unreopened.

Terminal verification: all 3 of the round's most decisive new citations
confirmed exact — `manage.bat:6-11` really does invoke `manage.py` via
`%BASE_DIR_PHYS%\_sys\env\python\python.exe`, the portable interpreter
living *inside* the directory uninstall must purge; `run-tests.bat` really
does set `GEMINI_DIR` and unconditionally write `_sys/gemini/status.json`
on every test run (lines ~17-18, ~43); `test_no_stray_health_files.py`
really does read `_sys/ai/peers.json` at module level (lines 15-20).

## Four-item closure review

| v5 requirement | Result |
|---|---|
| Deferred-state rule and destination | **PASS** |
| Exact Python/config dispositions | **PASS** |
| Explicit `_sys/hooks/**` disposition | **PASS** |
| Concrete uninstall + full-suite gates | **FAIL** |

**1.1 Deferred-state migration — closed.** v6's canonicalization rule
matches the real state (`peer:<peer_key>` keys and preserved fields both
confirmed real at `provisioner.py:826-830,882-892`) — a retained tool
whose key format changes is not dropped. One non-blocking implementation
note: an unresolvable historical alias should be retained/quarantined
with an error, not silently discarded, but this follows naturally from
the already-ratified rule and isn't itself a blocker.

**1.2 Exact retained-module changes — closed.** `virtualizer.py`/
`scrubber.py`/`manage.py`/`config.py` all now name actual branches;
`check_config.py`'s deletion is internally consistent (its only real
consumer, `test_config_validator.py`, is also deleted).

**1.3 Hook-tree disposition — closed.** Both the registration (Claude
settings) and the implementation tree (`_sys/hooks/**`, all 9 files) are
now separately, explicitly removed — closes the earlier
registration-vs-tree ambiguity.

**1.4 Uninstall + acceptance gates — NOT closed**, for four concrete
reasons:

1. **The executor purges its own directory while running from inside
   it.** `manage.py`'s launcher (`manage.bat:6-11`) invokes it via the
   base installation's own bundled `_sys/env/python/python.exe` — a
   process cannot reliably delete the directory tree containing its own
   running interpreter on Windows. v6 never addresses this.
2. **No journal location is specified.** If the journal lives under the
   base directory, `directory_purge` destroys the evidence needed to
   record completion or retry a recoverable failure — the promised
   idempotent retry isn't demonstrably implementable as designed.
3. **Whether an in-tree Python runtime can reliably self-uninstall on
   Windows is untested** — v6 supplies neither an external helper process
   nor a measured canary proving this works.
4. **Increment A claims uninstall ownership but its exact file list never
   touches `manage.py` or adds `test_uninstall_semantics.py`** —
   `manage.py` only appears under Increment B in the acceptance matrix, a
   real internal inconsistency.

**Required fix**: stage an external teardown helper + journal *outside*
the base directory (keyed by installation identity), which performs
SUBST/registry/junction/directory cleanup only after the in-tree launcher
process has exited. Fix the Increment A/B file-list mismatch.

## New finding: the final acceptance matrix is internally impossible

Increment D deletes `_sys/ai/**` (including `peers.json` and
`virtualizer._load_peers`) but its own gate then runs two unchanged tests
that require exactly those deleted surfaces:
`test_no_stray_health_files.py` reads `_sys/ai/peers.json` at module level
(confirmed); `test_system_lifecycle.py` repeatedly patches
`virtualizer._load_peers` (which Increment B already deleted) and still
asserts `.ai` governance-preservation semantics, directly contradicting
the final zero-AI boundary. Worse: the prescribed full-suite gate
(`run-tests.bat --full`) itself recreates retired provider state on every
invocation — sets `GEMINI_DIR` and writes `_sys/gemini/status.json`
(confirmed) — meaning the "final validation" step violates the very
boundary invariant it's supposed to prove. **Required correction**: delete
or replace `test_no_stray_health_files.py` with a genuine provider-absence
test; rewrite `test_system_lifecycle.py` to drop the `_load_peers`
patches and `.ai`-governance cases while keeping its generic lifecycle
coverage; remove Gemini state initialization from `run-tests.bat`; and
disposition the related Gemini checks found in
`_sys/tests/local-test.bat:30-74,162-168,261-262` and
`_sys/tests/host-test.ps1:175-180`.

## New finding: `check_contracts.py`'s disposition remains contradictory

`check_config.py`'s deletion is consistent, but `check_contracts.py` isn't
resolved the same way — v6 says it "becomes a neutral CI checker" while
also deleting its own test (`test_check_contracts_gate.py`), but the real
file's documented purpose is specifically a Claude `PreToolUse` hook
(`check_contracts.py:1-6`), its governed paths are AI orchestration/peers/
hub-contract tests (`:53-77`), and it parses Claude hook input directly
(`:320-364`) — once the hook registration and tree are gone, no concrete
neutral behavior is actually specified or tested. v6 must pick one: delete
`check_contracts.py` and its hook-specific tests outright (keeping a
separately-defined generic product-boundary test), or actually specify the
neutral checker's inputs/invariants/command/replacement tests.

## Non-blocking hardening (catalog)

The catalog does carry what current npm installation needs (Claude/Codex
`discovery_id` already real in `runtimes.json:220-248`, correctly mapped).
One schema tightening worth doing eventually, not ratification-blocking:
`source.discovery_provider`/`discovery_id` should be conditionally
required when `install.mechanism == "npm_peer"`, since currently only
`source.url` is unconditionally required and an unusable npm entry could
still validate.

## Exact blockers remaining for the next (seventh) round

1. Externalize uninstall execution + journal persistence outside the base
   directory; fix the Increment A/B file-list mismatch.
2. Make Increment D's tests compatible with what it deletes; strip Gemini
   state creation from the test harness.
3. Resolve `check_contracts.py` as either fully deleted or a concretely
   specified, tested neutral checker.

None of these reopen the architecture — the verdict is explicitly that
v6's document is not yet executable as written, not that the plan's
direction is wrong.
