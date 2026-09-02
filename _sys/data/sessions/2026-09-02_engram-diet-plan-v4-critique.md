# Fourth-revision critique (cx.deepthink, 2026-09-02)

**Verdict: Another focused revision required before ratification — but
explicitly a final, narrow correction pass, not another architectural
cycle.** "The A-D architecture is sound and should not be reopened. The
corrected directive digests are genuine, the Claude exit-0 bypass is gone,
and all six direct `_bat-shim` references now have dispositions."

Terminal verification: both newly-flagged path errors confirmed real —
the contract test genuinely lives at `_sys/tests/unit/l1_core/
test_contracts.py` (not directly under `unit/`), and
`test_system_lifecycle.py` genuinely lives at `_sys/tests/unit/` (not
`scenario/`) — v4's proposed acceptance-matrix commands for both were
wrong.

## Independent digest re-verification: all 6 confirmed identical

cx recomputed all 6 directive digests independently from scratch using the
same stated method and got byte-for-byte identical results to the
terminal's corrections in v4 — confirms the terminal's fabrication-fix was
correct, not just plausible. Also resolved an ambiguity in the method
itself: for DIR-006, "next heading" must include the following `##
Revoked Directives` level-2 heading, not just the next `###` — v4's value
is correct under this reading.

## Two remaining material blockers (not cosmetic)

**1. `engram.tool-catalog.v1` is still too small to actually install
anything.** v4 added real fields (aliases, version, mechanism, canary,
etc.) fixing several v3 gaps, and the `deploy()` AI-directory-creation
deletion is confirmed real and fixed. But native installation needs
structured `url`/archive-type/named-digest-algorithm+value/structured
`extras`/structured canary (`argv`+`timeout_sec`+`expect_regex`) —
`runtimes.json`'s real Agy/Claude/Codex entries all have this
(`discovery_provider`, `discovery_id`, `install_mechanism`, structured
canaries); v4's opaque single `"canary": "boolean"` and string
`"source_hash"` can't represent any of it. **A genuinely exhaustive
source search found 8 more `peers.json` consumers beyond what v4 named**:
`launcher.py` (injects per-peer env vars, patches provider files,
launches peer host apps), `virtualizer.py` (real fallback), `scrubber.py`
(per-peer cleanup), `config.py`, `check_config.py`, `check_contracts.py`,
`manage.py` (creates `.ai`, builds provider shadows/junctions), and
`agy_entry.py` — none dispositioned. Deferred-state migration
(`.ai/tool_deferred_retries.json` → `_sys/state/deferred_tools.json`)
also needs an explicit key-migration/reconciliation plan, not just a new
path.

**2. The acceptance matrix has real path errors and internal
contradictions.** Beyond the two test-path errors above: the ownership
matrix assigns statusline + `_sys/hooks` deletion to Increment A, but
Increment A's actual file list touches neither; provider wrappers appear
scheduled in both A and D redundantly; the wrapper deletion list misses
`agy_entry.py`/`claude_entry.py`/`codex_entry.py`/`console_runner.py`/
`peer_console.py`/`peerhub.bat` (the current `test_contracts.py:96-112`
actually *asserts these must exist* — Increment A must explicitly rewrite
that assertion, not just delete the files); Gate 7 leaves two competing
Winget builders unresolved and a genuinely-probed `winget validate
--help` returned exit `-1978335231` with no output, so Gate 7 needs a
deterministic internal validator plus separately-reported external-Winget
results, not an assumed-successful CLI call.

## `_bat-shim`/hook: narrowly fixed, boundary work still incomplete

The direct shim-consumer enumeration and the Claude-hook removal are both
confirmed real fixes — no remaining direct `_bat-shim` dependency, no
second `PreToolUse` registration found anywhere else. But rewriting the
`manage`/`launch` *shell shims* isn't enough: `manage.py`'s retained
`workspace-init` branch still reads `peers.json`/creates `.ai`/builds
provider junctions (`manage.py:104-164`), and `core/launcher.py` (reached
via `launch.bat` → `start.bat` → `dispatch.bat` → `launcher.main`) still
injects provider env vars and launches peer apps. The *Python* logic
behind these commands needs the same AI-stripping the shell wrapper got.

## Directive/statusline: one correction needed

DIR-002's Codex binding should be `PENDING`, not `ADVISORY_ONLY` — the
`ADVISORY_ONLY` value was based on the OLD `codex.cmd exec -c
sandbox="workspace-write"` probe; PeerHub's real Codex adapter invocation
(`codex.cmd exec [resume] --json ...`) explicitly supplies no sandbox flag
and inherits `config.toml` instead — that's evidence about the retired
launcher, not evidence PeerHub itself encodes DIR-002. The other five
directive dispositions (DIR-001/004/005/006, all `PENDING`) are confirmed
accurate against real PeerHub source. Also: Increment D must explicitly
depend on the `peerhub.governance-directive.v1` service actually existing
and producing verified migration receipts before `user-directives.md` is
deleted — otherwise the source gets deleted while every migrated binding
is still merely planned.

## Uninstall design partially regressed

v4 correctly resolves the AI-CLI-survival contradiction (wholesale
Node/npm-subtree removal), but otherwise dropped the third revision's
uninstall state-machine detail entirely (no command implementation,
receipt schema, recovery/retry semantics, or acceptance tests) — since v4
explicitly supersedes v3, that detail needs to be reincorporated, not left
implicitly inherited.

## Required for the next (explicitly final-correction) round

Complete the tool-catalog schema (exact path, real JSON Schema, full
source/discovery/digest/canary/rollback structure, migration mapping from
both `runtimes.json` and `peers.json`); disposition all 8 newly-found
`peers.json` consumers plus deferred-state migration; strip AI behavior
from `manage.py`/`launcher.py`'s actual Python logic, not just their
shell shims; fix the acceptance matrix's real path errors and name every
changed/deleted test; reconcile Increment A's statusline/hooks ownership
claims with its actual file list; restore the uninstall design/tests;
correct DIR-002 to `PENDING`; resolve the Gate-7 builder/validator
ambiguity.

## Overall verdict

**Not ready for ratification yet**, but decisively closer — architecture
confirmed stable across 4 rounds now, several real blockers genuinely
closed this round, remaining gaps are catalog/consumer-graph completeness
and acceptance-ledger accuracy, not open design questions.
