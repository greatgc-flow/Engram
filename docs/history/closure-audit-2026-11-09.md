# Closure audit 2026-11-09 (v3.11.8)

Frozen record. Owner goal: a mutually recursive MECE audit that checks vertical closure (code <-> help <-> CLI reference <-> guides <-> tests <-> release artifacts) and horizontal closure (verb <-> verb, doc <-> doc), repeated until every axis scores 100. PR #111.

## Method

- Peers (PeerHub): ag `ag.effort` critiqued the audit design and checked the help set, cx `cx.effort` audited and fixed code and help, fable `cc.fable` audited and fixed docs, and cc orchestrated, ran the tests and merged.
- A deterministic script checked 24 closure rules: version SSOT, CHANGELOG/tag/manifest coverage, release-manifest hashes against the tagged files, the WinGet digest against the release asset, verb lists across the help, index, `engram.cmd` and CLI reference, verb groups, help ASCII/width, links, the docs index, component registry coverage, dispatch operations, workflow script references, check-script callers, runtime PATH wiring, and git hygiene. It was kept out of the repo because the unit contracts already cover the recurring checks.
- Each round, a peer cross-reviewed the other peer's diff against the code and scored three axes (vertical, horizontal, MECE).

## Scores

| Round | Script | cx V/H/M | fable V/H/M | ag H/M |
|---|---|---|---|---|
| Baseline | 56 (10/18) | - | - | - |
| 2 (after fixes) | 100 (24/24) | 88/85/90 | - | - |
| 4 | 100 | 96/98/100 | 96/95/98 | 82/84 |
| 6 | 100 | 98/98/99 | 98/97/99 | 100/100 |
| 7 (final) | 100 | 100/100/100 | 100/100/100 | 100/100 |

## Main findings fixed

- `repair`/`relocate` with `--resume`/`--rollback` executed recovery even with `--dry-run`. This combination is now rejected with exit 2, and a regression test covers it.
- Abbreviated options were accepted inconsistently (`repair --j` printed no JSON), so abbreviations are now rejected.
- `--json` stdout was polluted by loader, runner and `dispatch.bat` diagnostics. These now go to stderr.
- `engram open PATH` returned exit 0 without VS Code. `snapshots list` accepted surplus operands. `tidy` had undocumented path overrides, which were removed.
- The sandbox test wrote `<root>\_archive`, which is a legacy-layout marker. It now writes `_sys\data\test-results`.
- The help Safety model, exit codes and the "not set up" rule were each stated once and made true for every verb.
- Contradictions, stale states and duplicates across the README, guides, handoff, release gate and CONVENTION were resolved. The handoff history moved to `handoff-2026-10.md`.
- Coverage gaps were closed in the component registry, the docs index, the CHANGELOG (3.11.6 yanked, pre-3.8.0 pointer) and the isolation placement in the CLI reference.

## Deferred

- #112: `snapshots restore` runs while an operation journal is open. This is documented, and the policy decision is deferred (cc, cx and fable approved).
- `pyright` reports 265 diagnostics on main and on the branch alike, so none come from this change. Pyright is not a CI gate.
- `test_windows_sandbox_provider::test_serialization_across_processes` flakes under heavy parallel load (it is in the handoff flake list).
