# diag MECE Redesign — Design (pre-TDD)

> Status: DESIGN, pre-TDD. R:10: user spec + cx validation (GO with must-fixes)
> + terminal synthesis. Date: 2026-07-04.
> NOTE: the original redesign prompt referenced consensus docs at
> `_sys/docs-v2/scratch/diag-redesign-*.md` which NO LONGER EXIST (deleted), and
> was drafted against an OUTDATED premise ("diag rolled back to original"). The
> current diag.py already has the FP-4 layout + restored ANSI color (this session,
> ca04bf5 / 59456d3). This design re-derives the spec against the CURRENT diag.

## 0. Goal
A cleaner MECE separation of diag sections + emoji-safe column alignment. Today
quota is DUPLICATED (profile matrix has 5H/weekly/reset columns AND the peer
cards render quota bars). Move all raw quota to ONE place (SUMMARY continuation
rows), make PROFILES pure routing topology, and fix emoji width so columns don't
break.

## 1. Section → field ownership (MECE, cx-validated)

| Section | OWNS | MUST NOT own |
|---|---|---|
| HUB | room / state / leader / mission (hub.py status) | quota |
| PROFILES & ROUTING | profile id, model, effort, cost tier, **declared** ctx capacity, routing state, compact source tags | quota bars, reset, pacing |
| PEER DETAIL (render_card) | peer gate/quarantine/account/**current** context | raw quota bucket table |
| SESSIONS & HEADROOM | per-session live ctx + derived `quota_remaining` (headroom) | raw quota buckets |
| ALERTS | stale / source / quota / context alerts | topology |
| SUMMARY | volatile per-peer quota buckets (label, glyph, pct, pace, reset, source, WARN/critical) — nearest the prompt | declared topology |

Rationale (cx): quota belongs in SUMMARY, not the profile matrix; moving it out
also fixes the FP-4 profile matrix being too wide (it carried two ~26-col quota
columns + reset). No info loss — SUMMARY stays nearest the prompt, HEADROOM keeps
derived `quota_remaining`.

## 2. Emoji-safe display width (_dw / _pad)

Emoji (🟢🟡🔴🚫) render as 2 terminal columns but Python `len()` = 1, so
f-string width specs (`{s:<24}`) break alignment. Add:
- `_dw(s)`: display width. Count East-Asian W/F = 2; known emoji blocks
  (0x1F300–0x1FAFF, 0x2600–0x27BF) = 2; combining marks / variation selectors /
  ZWJ = 0; ignore ANSI escape sequences defensively; else 1.
- `_pad(s, width, align)`: pad to a target DISPLAY width using `_dw`.
- **Rule:** pad RAW text with `_pad` FIRST, THEN apply ANSI color (coloring first
  inflates length and breaks the pad). Avoid ZWJ family emoji in tables (width is
  only approximate for those).

## 3. snapshot.py patches (cx must-fixes folded)

1. **Sort quota buckets by label** in the snapshot data (before render/profile
   derivation) — deterministic ordering everywhere.
2. **DO NOT inject a C-5H 0% bucket.** (cx REJECTED the original spec's
   unconditional injection.) Evidence: the parser maps "Current session" → C-5H,
   but only emits rows the CLI text actually contains; a live `/usage` probe
   returned NO C-5H rows → missing C-5H is **absent**, not a measured 0% (DIR-004:
   injecting it would fabricate data). cc.fable sharing cc's C-5H is UNVERIFIED.
3. **Preserve measured `0.0` buckets exactly.** `format_quota_bucket` already
   distinguishes a measured zero from absent; **`absent` MUST stay the literal
   string** (a prior emoji change replacing "absent" with ➖ was reverted for
   breaking the unanimous literal-absent spec + DIR-004).

## 4. Renderers

- **render_profiles → PROFILES & ROUTING** (~84 cols): columns
  `PROFILE | MODEL | EFF | TIER | CTX(declared window only) | STATE | SRC`.
  Remove quota bars/emoji/reset. `[decl]` prefix when source=orchestration.
  STATE: eligible→green, manual_only→yellow. CTX = declared `window_tokens`
  (`_short`), NOT live occupancy.
- **render_summary → per-peer header + `  ↳ ` quota continuation rows**: header
  `PEER GATE MODEL CONTEXT(used/win %) COST SRC`; each `  ↳ label glyph pct pace
  resets <reset>`, sorted by label (snapshot sorts), `WARN` at used_frac ≥ 0.90,
  glyph 🚫 at used_frac ≥ 1.0 (a MEASURED saturation marker — SAFE, distinct from
  the reverted absent→➖). Use `_pad` for the glyph cell; never an f-string width
  spec on an emoji.
- **render_card (DETAIL):** minimal change; drop its raw quota-bar block (quota
  now lives only in SUMMARY).

## 5. Section order (nearest-prompt = volatile last)
HUB → PROFILES & ROUTING → PEER DETAIL → SESSIONS & HEADROOM → ALERTS → SUMMARY.

## 6. Constraints
- Width budget 100–110 cols; each section fits after quota removal (cx verified:
  profile 22 / model 28 / eff 5 / tier 5 / ctx 12 / state 10 / src 12).
- MECE: each data field appears in exactly one section.
- `absent` stays literal everywhere; 0% stays a measured bar.

## 7. Tests (pre-TDD list)
`_dw`/`_pad` (emoji, CJK, ANSI-colored cell, combining mark, literal "absent");
render_profiles has no quota columns; render_summary emits sorted `↳` rows with
correct glyph/WARN/🚫; snapshot bucket sort; absent stays literal; a measured 0%
bucket still renders a bar. Verify live with `diag.bat` (NO_COLOR + colored).

## 8. Verdict
cx: **GO** as the implementation spec, with the must-fixes above (no C-5H
injection, absent literal, _dw/_pad pad-before-color, quota→SUMMARY only, sort in
snapshot). Implementation order = the user's 6 steps, minus the C-5H injection.

---
*Next: TDD from step 1 (snapshot sort) → _dw/_pad → render_profiles → render_summary → section order → live diag.bat check.*
