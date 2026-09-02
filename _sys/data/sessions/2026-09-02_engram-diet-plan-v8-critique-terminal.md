# Eighth-round, final ratification critique — terminal-performed (2026-09-02/03)

**Status note**: `cx` (all three profiles — `deepthink`, `effort`,
`standard`) failed identically this round with `session resume failed
(permanent)` and a soft-skip until 2026-09-07T11:59, confirmed via
`peer-recover` (ran, didn't fix it), a zombie-process check (none found),
and a direct `codex --version` probe (the underlying CLI itself is
healthy — this is specifically hub.py's own session-resume layer holding
a stale reference for `cx`). See
`reference_cx_session_resume_permanent_failure_2026_09_02` in the
assistant's memory. Per the established precedent from this same
session's Gap 6 round, the terminal performs this critique directly
rather than leaving the round without a second independent check.

## Verdict: **RATIFY**, with one concrete addition required during
## Increment B/D implementation (not another design round)

The architecture, catalog, DIR-002, Gate 7, deferred-state,
Python-module dispositions, hooks-tree disposition, and all 5 of round 7's
mechanical fixes have now survived 7-8 rounds of independent critique with
zero architectural reopening. This round's one genuinely new question —
the SUBST-removal consequence — checks out.

## Task 1: SUBST-removal consequence — sound, with one real gap

Read `test_dual_instance_different_subst_drives`
(`test_system_lifecycle.py:256-289`) directly: it verifies "SYS-R4" — two
Engram installations registered on the same machine must not collide,
specifically by receiving *different SUBST drive letters* (a shared,
limited, 26-value global OS resource requiring explicit collision-
avoidance logic, which is exactly what `_assign_subst()` implements and
this test exercises).

Under the venv-style `ENGRAM_ROOT` replacement (per
`2026-09-02_subst-reconciliation.md`): `ENGRAM_ROOT` is derived from
`%~dp0` — the activating script's own physical directory — which is
**inherently unique per installation with zero shared-resource
contention** (unlike drive letters, there is no small fixed pool to
collide over; every install lives at its own distinct path by
construction). So the underlying property `test_dual_instance_
different_subst_drives` protected — two installs on one machine don't
interfere with each other — is not just preserved but structurally
guaranteed *more simply* than before, with no assignment/collision logic
needed at all. Deleting the SUBST-specific test is correct.

**But**: v8's Increment D test-disposition list only *deletes* the 5
SUBST-specific tests; it does not add a replacement test asserting the
underlying dual-instance-non-interference property under the new
`ENGRAM_ROOT` model. This is a real, if narrow, coverage gap — deleting
evidence for a property without adding new evidence that the replacement
mechanism actually satisfies it. **Not implementation-blocking on its
own** (a competent implementer naturally adds this alongside the
`mount()`/`unmount()` rewrite in Increment B, and the property itself is
sound by construction as reasoned above) — but it should be tracked as a
concrete required addition, not silently dropped: a new test asserting
two `activate.bat` invocations from two different install directories in
the same process/session produce two independently-correct `ENGRAM_ROOT`
values with no shared state.

## Task 2: spot-verification of the 5 round-7 fixes

**`managed-links.json` consistency — confirmed positive.** v8's
`mount()`/`unmount()` rewrite proposes reading from
`_sys/data/state/pathmap/managed-links.json`. Verified directly:
this file/concept **already exists as the established, preferred
resolution path** in `_cli_apply()` (`virtualizer.py:349-357`, docstring:
"Resolution order: 1. managed-links.json (new registry — post-restructure)
2. ai/peers.json (legacy fallback — pre-restructure)"), confirming v8's
proposal aligns with an *already-intended* architectural direction in
this exact file, not an invented new concept. Also confirmed:
`mount()`/`unmount()` (lines 258-297, 300-342) currently reference
`managed-links.json` **nowhere** — they're still 100% on the legacy
`peers.json`-only path, while `_cli_apply()` already modernized. v8's fix
brings `mount()`/`unmount()` in line with the codebase's own existing
modern pattern, which is the right direction.

The remaining 4 fixes (installation-scoped uninstall, `scrubber.py`'s
`.ai`-governance strip, the completed test dispositions, and
`test_boundary_imports.py`'s algorithm) were already independently
verified with real citations at persist time for v8 (see the terminal
verification note at the top of `2026-09-02_engram-diet-plan-v8.md`) and
held up under that scrutiny — not re-litigated here.

## Task 3: final holistic pass

No new issues found beyond the dual-instance replacement-test gap above.
8 rounds of independently-verified, citation-grounded critique have not
found a single architectural problem since round 1 — every finding since
has been progressively narrower (conceptual → file paths → exact line
numbers → self-consistency between specific functions). That convergence
pattern, combined with this round's two checks (SUBST reasoning sound,
`managed-links.json` consistent with existing code) both passing, supports
treating this as ready.

## Final verdict

**RATIFY.** Required addition during implementation (Increment B/D, not
a new design round): add a replacement test for the dual-instance
non-interference property under the `ENGRAM_ROOT` model, to close the
one real coverage gap this pass found. Everything else — architecture,
catalog, ownership matrix, migration ledger, uninstall design, hooks
disposition, directive ledger, Gate 7, and all prior rounds' fixes —
stands as specified in
`2026-09-02_engram-diet-plan-v8.md`.

This closes Gates 1 (ownership matrix), 5 (migration ledger), and 6
(phased deletion + release plan) of the Engram/PeerHub separation master
plan, pending the user's own review and go-ahead before any actual
implementation begins.
