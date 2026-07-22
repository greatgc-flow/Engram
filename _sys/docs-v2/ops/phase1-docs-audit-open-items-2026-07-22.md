# Phase 1 Docs MECE Audit — Open Items & Improvement Ideas (2026-07-22)

Collected per the user's request to keep remaining discussion items and
improvement ideas out of the SSOT's normative docs and in one place. Status:
Phase 1 (the docs MECE audit itself) is closed as of this doc; these are
follow-ups, not blockers.

## Open items

1. **`check_docs_mece.py` only validates structure, not semantic truth.**
   It catches broken links, missing MANIFEST entries, and formatting drift,
   but nothing in the current check suite would have caught this session's
   two real content errors (a stale INV/PRO/DIR range repeated in three
   files; a "does not exist" claim about a file that does exist and is
   read by live code) without a peer or human directly re-verifying the
   claim against reality. A stronger check would spot-check a sample of
   concrete factual claims (numeric ranges, "file X exists/doesn't exist,"
   "field Y defaults to Z") against the actual repo state on each run.
   Not designed or scoped yet — flagged as a real gap, not a plan.

2. **`_sys/ai/common/skills/*` (~30 files) and `_sys/templates/*` are still
   in place, correctly, but their long-term fate is undecided.** Both were
   flagged as move/delete candidates by ag.gptoss's first (unreliable) audit
   pass, and both turned out to be actively referenced (`tool-registry.json`,
   `agents/proposer.json` for skills; `user/requirements.md` for templates)
   — so "keep them" is the currently-correct, verified answer. Whether they
   should eventually be restructured into `docs-v2/` proper (with the active
   references updated to match, the way `peer-rules.md` was migrated) is a
   separate design question nobody has picked up yet.

3. **The Knowledge Propagation "Three-Layer Architecture" (`learning.md`)
   is a completed design that was never built**, except Layer 2
   (`active-lessons.jsonl`, which is live and working). Layers 1 and 3
   remain an unstarted backlog item with no owner or target date — the doc
   now accurately says so (fixed 2026-07-22), but the underlying feature
   gap itself is unaddressed.

4. **`user/manual.md`'s Token Load-Balancing section points a live-system
   description at a historical design doc**
   (`_sys/docs/history/ops/token-load-balancing-design.md`) for lack of a
   current living spec of the *active* rules. The system works and is
   documented well enough to operate it, but there's no single "this is
   what's actually running today" doc separate from the original design
   record (which predates several since-shipped changes). Worth extracting
   a small living `ops/` doc from it eventually, not urgent.

## MECE-excluded / edge cases / noise

- Two similarly-named `AGY.md` files exist under `_sys/antigravity/`
  (`config/AGY.md` and `ipc-config/AGY.md`) with different purposes and
  different content — not a duplication bug, but the naming collision
  itself caused a real mistake this session (a peer edited the wrong one
  while migrating a shared-rules reference). Worth a distinguishing
  rename or a clarifying header comment in each, at some point — cosmetic,
  not urgent.
- `_sys/docs/history/` (~120+ archived files) was correctly left untouched
  throughout this audit as intentionally-inert provenance. Not re-scanned
  file-by-file for internal consistency (out of scope — it's historical by
  design, not meant to stay current).

## Process note for future audits

Every peer-driven docs edit in this round hit the governed-mutation guard
at least once, and roughly half the time the guard reverted the change
entirely rather than just quarantining it (the difference wasn't obviously
predictable in advance). The terminal peer ended up re-applying several
fixes directly after independently re-deriving the same content the peer
had already produced and reported as complete. Worth a future look at
whether concurrent peer-ask timing around docs-v2 specifically triggers
this more than other governed paths, or whether it's incidental to how
much of this particular session's peer traffic touched that directory.
