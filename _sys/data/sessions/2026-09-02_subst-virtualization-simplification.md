# Engram SUBST/virtualization simplification research (ag.deepthink, 2026-09-02)

New design thread added directly by the user: drop SUBST and ad-hoc
folder/file-linking machinery, rebuild Engram's "virtual environment"
concept as simply as possible (external packages explicitly permitted).
Scoped to `virtualizer.py`'s drive-letter mechanism only — the AI-peer
junction logic (`_ensure_junction`/`_set_peer_junctions`/etc.) is already
correctly slated for deletion by the diet plan and out of scope here.

Terminal-verified citations (both accurate):
`_sys/docs-v2/00-MANIFEST.md:81`'s "260-char MAX_PATH justification
empirically verified: a real repo file measures 267 chars without the
`P:\` shortcut" quote, and `registrar.py:241-245`'s real use of
`virt_state.get("subst_drive")` for context-menu relay batch files.

## 1. Why SUBST exists

Two genuine historical problems: Windows `MAX_PATH` (verified: a real repo
file measures 267 chars without the `P:\` shortcut, per the architecture
doc cited above) and USB-drive-letter instability across machines (context
menus and per-peer config hardcode the stable letter).

**Conclusion: the mobility problem still exists, but SUBST is not the only
solution to it, and the MAX_PATH crutch is largely obsolete on modern
Windows** (long-path support via the `LongPathsEnabled` registry key /
Python's native long-path handling).

## 2. Alternatives surveyed

(a) Python `venv`/`virtualenv`-style shell activation (`activate.bat`/
`.ps1` resolving its own location via `%~dp0`, setting an env var, mutating
`PATH` for the current session only — no OS-level drive mutation, no admin
privileges). (b) Plain NTFS directory junctions to a fixed user-profile
path — still custom filesystem-mutation code, and complicates running
concurrent workspaces. (c) Environment-variable-only (`%ENGRAM_ROOT%`),
batch wrappers resolve their own path via `%~dp0`. (d) Established
packages: `virtualenv` itself (Engram is already Python-cored, could
literally be distributed as a standard venv), `python-dotenv` for
workspace-relative config loading.

## 3. Recommendation: drop SUBST, adopt venv-style activation

Replace the drive mount with an `activate.bat`/`.ps1` in the workspace
root: resolves its own physical path via `%~dp0`, sets `ENGRAM_ROOT`,
prepends CLI bin directories to `PATH` for the current shell session only.

- **Simpler**: deletes `_assign_subst`/`_release_subst`
  (`virtualizer.py:37-111`) outright — no more brittle OS-level `subst.exe`
  shelling.
- **Still fully portable**: `%~dp0` resolves dynamically every activation;
  moving the USB drive to a new machine needs zero path rewriting, just
  re-running activation.
- **Context menus still work**: they're already machine-local `HKCU`
  state; at `register.bat` time, `registrar.py` can hardcode the physical
  absolute path directly into the `%LOCALAPPDATA%` relay script — no
  stable virtual drive is needed to bridge context menus across machines.

**What needs addressing**: paths return to full physical length without
SUBST — `doctor.py` should check the `LongPathsEnabled` registry key and
warn if disabled; anything using virtualizer's `{DRIVE}` interpolation
needs to move to `{BASE_DIR}`/`ENGRAM_ROOT` instead (moot for AI-peer
config specifically, since that whole mechanism is already being deleted
by the diet plan).

## 4. Compatibility with frozen `stable`

**Zero conflict.** `stable/hub-py-restored` keeps its global OS-level SUBST
mount; the proposed `main` approach only mutates the active terminal
session's `PATH`/env vars. Both can run simultaneously with no interaction.
No change to the frozen checkout required or implied.

## Notable incidental discovery: another dormant ratified-adjacent design

`00-MANIFEST.md:81` references `ops/phase2-arch-general-specific-2026-07-22.md`
— a 5-round `ag.deepthink+cx.effort+cc` design (dated 2026-07-22, well
before today) that already **demotes SUBST/junction to an explicit
"Legacy Migration Backend"** as part of a larger "4 logical stores"
architecture (immutable core / shared config / shared mutable data /
workspace state) replacing what it calls "PORTABLE_ROOT coupling," with a
`RuntimeContext` using explicit CLI > bootstrap-manifest > discovery
precedence. Marked "architecture only — not yet implemented, Phase 3 is
exact schema/interface detail." This matches the exact pattern found
earlier today for Gate 2 (`PHASE1-MANIFEST-SCHEMA-V2` already solving the
adapter-contract problem before anyone went looking) — **this doc should
be read in full and reconciled against today's SUBST-removal proposal
before ratification**, since it may already contain a more complete,
previously-debated answer to the same question this dispatch just
independently arrived at from scratch.

## Status

Design proposal, one voice, not yet critiqued or ratified. Two citations
verified accurate. **Explicit follow-up required before ratification**:
read `ops/phase2-arch-general-specific-2026-07-22.md` in full and
reconcile its "4 logical stores" / SUBST-demotion architecture against
this proposal's simpler venv-activation approach — they may agree, or the
2026-07-22 design may be more complete and supersede this round's proposal
in relevant part, the same way `PHASE1-MANIFEST-SCHEMA-V2` did for Gate 2.
