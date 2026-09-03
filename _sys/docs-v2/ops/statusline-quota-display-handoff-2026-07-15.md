# Statusline Quota Display Handoff (2026-07-15)

> Status: design decided; peer review attempted; implementation not applied.

## Goal and Decisions

The user asked whether adding `F-7D` to the Claude Code statusline would make it
appear in `diag`, and whether every peer's full quota set could be shown with a
minimal change. The user selected:

- statusline is presentation only; `diag` remains the collector/normalizer;
- show every actually observed bucket as used percentage only;
- preserve `0%`, omit individually missing buckets, and show `quota:N/A` only
  when no buckets exist;
- never fabricate `F-7D`;
- leave reset, pacing, source, and freshness in `diag`;
- discuss with `ag` and `ag.opus` before applying.

## Measured Findings

- Current CC `_sys/claude/config/status_input.log` has only
  `rate_limits.five_hour` and `rate_limits.seven_day`.
- A live Claude Code 2.1.207 `/usage` probe now prints usage-contribution
  characteristics, not quota/reset rows. `diag --fresh` still omitted `F-7D`,
  ruling out cache staleness.
- Existing `snapshot.py` already maps any real `rate_limits` key containing
  `fable` plus `weekly`/`seven`/`7d` to `F-7D`. Therefore a real F field in the
  captured statusline JSON would reach `diag` without changing production
  collection code. Adding only rendered text would not; `diag` reads JSON.
- AG's live statusline JSON already contains `G-5H`, `G-7D`, `3P-5H`, and
  `3P-7D`. `diag` shows all four, but the common formatter displays only G.
- CX uses built-in statusline enums and `diag` obtains quota from the Codex
  app-server. Do not route CX quota through a statusline file.
- Statusline capture refreshes only when a peer TUI renders, so it must not
  become the universal quota SSOT.

Absence of F currently means **unobservable**, not zero and not proof that the
pool does not exist.

## Peer Review

`ag.effort` completed a read-only review in 189s and approved the central design:
one common presentation change, canonical labels/order, percentages only, 0%
preserved, missing omitted, no `snapshot.py`/`diag.py`/routing/CX changes. AG's
sample jq branched on `PEER_ID`; the final synthesis rejects that unnecessary
Generic/Specific coupling.

`ag.opus` ran 429s and inspected the telemetry docs, adapters, live JSON shapes,
`snapshot.py`, `_AG_QUOTA_LABELS`, and Claude usage parser, but its response ended
before the requested verdict. Two short follow-ups then failed with provider-side
`RESOURCE_EXHAUSTED (429)`, `model API currently overloaded`, and `model
unreachable`. Hub recovery used `hub peer-recover`; no manual GREEN override was
used. Evidence is in `_sys/antigravity/config/cli.log`, health.json, and
`.ai/ask_history.jsonl` near 2026-07-15 10:39-10:49 +0900.

Do not claim unanimous approval: AG approved; Opus inspected but did not deliver
a final verdict because its response was incomplete and the provider degraded.

## Final Implementation Design

In `statusline-unified.sh`, build one deterministic shape-driven list without
branching on peer identity:

1. `C-5H`: `rate_5h_pct` or `rate_limits.five_hour`
2. `C-7D`: `rate_7d_pct` or `rate_limits.seven_day`
3. `F-7D`: first real `rate_limits` key matching `fable` and
   `weekly|seven|7d`
4. `G-5H`, `G-7D`: `quota.gemini-5h`, `quota.gemini-weekly`
5. `3P-5H`, `3P-7D`: `quota.3p-5h`, `quota.3p-weekly`

Accept numeric percentages, `used_percentage`, `used_percent`, or
`remaining_fraction` converted with `(1 - remaining) * 100`. Output examples:

```text
C-5H:105% C-7D:14%
C-5H:10% C-7D:20% F-7D:12%   # only with real F input
G-5H:0% G-7D:42% 3P-5H:0% 3P-7D:2%
```

Intended files:

- production: `statusline-unified.sh` (legacy statusline helper, removed in Engram/peerhub separation) only;
- contract: `statusline-schema.json` (schema v2, repeated canonical buckets,
  fallback `quota:N/A`);
- SSOT: update obsolete F `/usage` statement in
  `diag-telemetry-architecture.md`;
- tests: `test_statusline.py` and `test_diag_cli.py`.

Tests must cover CC without F, CC with real `fable_weekly`, all four AG buckets,
0% preservation, partial omission, `quota:N/A`, and end-to-end statusline JSON
to `diag` F-7D normalization. CX tests remain unchanged.

## Current Workspace and Resume Steps

No intended patch was applied; target-file diffs are empty. Built-in
`apply_patch` failed on the P:/D: subst split-root sandbox. A host-side patch
piped to `apply_patch.bat` hung and was aborted; another attempt exceeded the
Windows batch argument limit. Three Bash processes from the aborted attempt were
visible at last check (PIDs 22224, 34412, 198876); verify ownership before any
termination.

Preserve unrelated existing changes:

```text
 M _sys/claude/config/settings.json
?? Windows PowerShell.lnk
?? _sys/data/sessions/
```

Next session:

1. Recheck git status and target diffs.
2. If Opus is healthy, request only its missing verdict; do not repeat inspection.
3. Apply the shape-driven formatter with no `PEER_ID` branch.
4. Update schema, SSOT, and focused tests.
5. Run focused pytest, encoding check, `git diff --check`, and real CC/AG fixtures.

Git Bash fixture execution required host-side permission in this session because
the restricted sandbox failed with `couldn't create signal pipe, Win32 error 5`.
