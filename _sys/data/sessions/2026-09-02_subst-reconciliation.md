# SUBST proposal reconciliation against 2026-07-22 architecture (ag.deepthink, 2026-09-02)

Checks the earlier SUBST-simplification proposal
(`2026-09-02_subst-virtualization-simplification.md`) against
`_sys/docs-v2/ops/phase2-arch-general-specific-2026-07-22.md`, which its
own citation trail led to. Three citations independently spot-verified by
the terminal — all accurate: zero `RuntimeContext`/`EngramApplication`
hits anywhere in the worktree's `.py` files (confirms the design was never
implemented); the doc's line-216 "LEGACY MIGRATION FLAG" quote demoting
`virtualizer.py`'s SUBST/junction mechanism to an "Optional Legacy
Migration Backend" gated behind explicit user confirmation; and its own
2026-07-27 re-scope note (line 2) stating Engram's scope back then was
"permanently fixed to the internal multi-peer collaboration engine" — i.e.
this document predates and was written for a broader scope than exists
today, since today's user directive removed the collaboration engine from
Engram entirely.

## What the 2026-07-22 design actually specifies

- **4 logical stores** replacing "PORTABLE_ROOT coupling" (lines 80-95):
  immutable core (`~/.engram-core/` or `%APPDATA%/Engram/`), shared global
  config (`~/.engram-shared/config/`), shared mutable data
  (`~/.engram-shared/data/`), workspace-state (a per-repo `.ai/`
  directory).
- **`RuntimeContext`** with explicit precedence (lines 97-104): CLI args >
  bootstrap manifest/env vars > cwd-walking discovery.
- **SUBST demotion, not removal**: kept as an "Optional Legacy Migration
  Backend," explicitly gated behind user confirmation due to "high blast
  radius" (line 216) — the design does NOT specify a `venv`/`activate`-
  script replacement; it only says "shift to native LongPaths where
  possible," with no session-local `PATH`-mutation mechanism at all.

## Where the two proposals agree and differ

**Agree**: both independently identify SUBST as a MAX_PATH-era crutch now
largely obsolete given `LongPathsEnabled`.

**Differ**: the 2026-07-22 design solves this via heavy architectural
decoupling (4 logical stores) while *cautiously retaining* SUBST as an
opt-out legacy fallback; the 2026-09-02 proposal replaces SUBST outright
with a session-local `activate.bat`/`.ps1` + `ENGRAM_ROOT` env var, no
legacy fallback.

## Which is more correct for today's scope

**The 2026-09-02 proposal, not the 2026-07-22 architecture.** The older
design's own re-scope note (quoted above) shows it was built for a broader
"Engram = portable dev env + internal collaboration engine" shape that no
longer exists — today's user directive removed collaboration from Engram
entirely. Under today's narrower scope, the 4-logical-stores decoupling is
over-engineering, and retaining SUBST as any kind of fallback preserves
exactly the brittle OS-mutation code the diet effort is trying to delete.

## Implementation status

**Purely dormant** — zero `RuntimeContext`/`EngramApplication` references
anywhere in the real `.py` source (verified independently by the
terminal). Exists only as markdown design text; never built.

## Final recommendation (supersedes the earlier proposal only by removing
its "not yet reconciled" caveat — the mechanism itself is unchanged)

Proceed with the 2026-09-02 proposal as originally specified:

1. Delete `_assign_subst`/`_release_subst` from `virtualizer.py`
   completely — no legacy fallback, no optional gate.
2. Ship `activate.bat`/`activate.ps1` in the workspace root: resolve own
   physical path (`%~dp0`), set `%ENGRAM_ROOT%`, prepend
   `%ENGRAM_ROOT%\bin` to `PATH` for the active session only.
3. `register.bat`/`registrar.py` write the active absolute physical path
   directly into the `%LOCALAPPDATA%` relay scripts at registration time —
   no dependency on a stable virtual drive letter.
4. `doctor.py` gains a check warning if `LongPathsEnabled` is disabled.

## Status

Reconciliation complete, one voice (ag) resolving its own prior proposal
against newly-discovered prior art. Citations independently verified.
Still needs a genuine second-voice critique (cx) before ratification,
matching the standing dialectical process — this round removed the
"unreconciled prior art" blocker but did not itself constitute the
required independent critique.
