Plan document, 2026-10-12. Reference, not an instruction file.

# Engram PR-B: advice equals guard, release 3.9.2

## Status and evidence

This is an Engram-only implementation and audit plan, not authorization to merge
or publish. The documentation branch is `docs/plan-update-advice-parity`, based
on `main`. The uncommitted draft on `fix/update-minor-preflight-advice` is
superseded by PR-B; preserve it untouched, and do not use it as the implementation
baseline. This documentation change creates no code, changelog, or commit.

Source evidence is the owner's external scratchpad folder
`D:/PkgDev/_sys/data/temp/claude/D--PkgDev-workspace/4041a42e-f452-4f0d-9a0f-fc49b63dfd31/scratchpad/`:

- `plan_v2.md`, including its amendments, is the resolved scope and decision record.
- `q_engram.out` records the read-only Engram review and in-memory metadata probe.
- `r2_cx.out` and `r2_ag.out` record competing proposals, superseded where v2 resolves them.
- `q_peerhub.out` and `q_sb.out` provide review context; their implementation work is outside this repo.

The owner's reported 3.9.1 terminal behavior was an advertised Python minor
update followed by refusal of that same command. The review found that the draft
still advertised a target when readiness verification failed (F3), while the
execution guard refused it. This is credible reported evidence, not a new live
reproduction. The metadata probe accepted a wheel explicitly excluding Python
3.15 (F1); filename compatibility alone does not establish installability.
Discovery success also masks readiness errors (F2). Planning repeats checks and
tests assert that duplication (F8/F9). Dispatcher output repeats failures (F4),
and migration emits an all-zero summary and writes state before refusal (F5).
Other evidence: unconditional package advice, `Apply 1 changes?`, inconsistent
unchecked-component exit policy, stale WinGet notes, obsolete CP949 second-run
documentation, and JUnit reports not uploaded by CI (F6/F7/F9-F12).

## Resolved decisions relevant to Engram

| Decision | Engram disposition |
| --- | --- |
| D6 | One embed-zip HEAD check plus managed pip dry-run resolves the complete baseline for the target patch version. Use `--ignore-installed` and execution-equivalent constraints. Network/tool failure is `unverifiable`; proven incompatibility is `blocked`. No custom wheel/metadata parser fallback. |
| D7 | Only `ok` readiness permits executable minor-update advice. Blocked and unverifiable targets remain informational warnings. |
| D8 | Suppress empty migration summaries and empty state writes; dispatcher owns the single failure message; preserve exit 11 and `_sys/dispatch.json` order. |
| D9 | Root `CHANGELOG.md` is the single source for the selected version's GitHub Release body and WinGet `ReleaseNotes`. |
| D10 | Engram's bugfix release is 3.9.2. Other repos' versions and releases are excluded. |

D1-D5 concern other repos and do not change Engram. Adopt v2 amendments over
round-2 disagreements: pip resolution replaces the proposed partial PyPI parser;
do not reorder dispatch. PR-B adds no third-party dependency. Existing pip is the
resolver, and external-module adoption requires a later owner decision.

## PR-B files and behavior

The following are proposed implementation files, not changes made by this plan.

| Files | Proposed change |
| --- | --- |
| `_sys/core/baseline_packages.py` (new) | Define the sole `BASELINE_PACKAGES` constant with pip distribution specs and import-module names; retain effective baseline constraints. |
| `_sys/core/{provisioner,python_manager,venv_manager,venv_repair,repair}.py` | Replace five independently maintained baseline lists with derived views of that constant. |
| `_sys/core/repair.py` | Share readiness between `python_update_status`, `_python_minor_preflight`, and `update_env_main`; distinguish discovery from readiness; reuse one result within a plan. |
| `_sys/core/updater.py` | Show verified advice only, remove routine `-o packages` advice without discovery evidence, fix pluralization, and align `--check` failure policy. |
| `_sys/core/dispatcher.py`, `_sys/core/layout_migration.py` | Print a failure once; suppress zero-operation migration output/state writes without changing dispatch order. |
| `_sys/core/help/update.txt`, `docs/cli_reference.md` | Update advice, readiness, and exit descriptions together; preserve generated help/reference parity. |
| `CHANGELOG.md` (new in PR-B, not created now), `tools/winget/build_package.py` | Extract the selected version section for release notes; remove stale independently authored notes. |
| `_sys/core/version.json` | Advance the version SSOT from 3.9.1 to 3.9.2 after validation. |
| `docs/cp949_verification.md`, `.github/workflows/ci.yml` | Describe the consolidated strict CP949 run; upload existing JUnit evidence on success and failure. |
| `_sys/tests/unit/` files listed below | Add behavioral regression coverage and replace assertions that preserve the reviewed defects. |

`BASELINE_PACKAGES` owns `filelock`, `psutil`, `pydantic`, and `pywinpty`;
`pywinpty` maps to import module `winpty`. Do not install `winpty` as a separate
distribution. Derive install specs, import checks, and baseline classification
from this constant. Let pip resolve transitive dependencies such as
`pydantic-core`; do not maintain a second dependency allowlist. Preserve existing
baseline constraints and the distinction between baseline and user packages.

For target `X.Y.Z`, the readiness engine checks the target embed URL with HEAD
and invokes the managed interpreter's pip once per plan:

```text
<managed-python> -m pip install --dry-run --ignore-installed --only-binary=:all: --platform win_amd64 --python-version X.Y.Z --implementation cp --abi cpXY <baseline specs and execution-equivalent constraints>
```

`cpXY` means the concatenated target major/minor, e.g. `cp315`. Use the complete
target patch, not merely `X.Y`. Bound subprocess duration and normalize reasons
for display. A successful archive check and dependency resolution yield `ok`;
proven archive absence or dependency incompatibility yields `blocked`;
offline, timeout, network, or pip/tool failure yields `unverifiable`. Nonzero pip
exit alone does not prove dependency incompatibility. No installation or Python
swap occurs during readiness checks. Reuse the result only within the same plan;
a later invocation verifies its own target and constraints again.

## Exact user-visible contract

For the illustrative target 3.15.0, print one applicable readiness line:

```text
[Warning] Python 3.15 blocked: <pkg reason>.
[Warning] Python 3.15 readiness unverifiable: <why>.
Python 3.15 dependency readiness verified. Next: engram update -o python --latest -y
```

Use actual target minor and normalized reasons. Example fixed fixtures:

```text
[Warning] Python 3.15 blocked: no compatible dependency set.
[Warning] Python 3.15 readiness unverifiable: network unavailable.
```

Only the verified case contributes `engram update -o python --latest -y` to
`Next steps:` or another executable-advice section. Unknown targets stay visible
without a command. Preserve applicable patch advice and explicit minor consent.
Execution refusal prints one dispatcher-owned error containing the shared
readiness reason and exits 11 before Python/venv mutation. Its existing error
prefix remains canonical; the plan does not introduce a second error format.
An empty migration emits no `--- Layout Migration Summary ---` block and does
not create or rewrite `layout.json`; nonempty maintenance remains supported.
Routine reports do not append `engram update -o packages -y` without evidence.

Prompts are exactly `Apply 1 change? [y/N] ` and `Apply N changes? [y/N] ` for
N greater than one. Their count covers this invocation's core/tool changes,
not separately advertised Python actions. `--check` exits 1 for failed or
unchecked requested components; 0 means the requested checks completed, not
that an unverifiable component is current. Preserve usage exit 2, declined
exit 3, and managed-environment exits 10-14, including preflight exit 11.

## Tests and acceptance criteria

- `test_repair.py`, `test_repair_wiring.py`, `test_update_report.py`: exercise
  ok/blocked/unverifiable advice-to-execution parity, target patch/constraints,
  `requires_python` exclusion, incompatible dependencies, archive absence,
  offline/network/tool failure, and exactly one pip resolver call per plan.
- `test_python_manager.py`, `test_venv_manager.py`, `test_venv_repair.py`,
  `test_provisioner_venv_failure.py`, and proposed `test_baseline_packages.py`:
  verify all five consumers use the SSOT, distribution/module mapping, and
  baseline-versus-user-package behavior without independent package lists.
- `test_dispatcher_bool_result.py`, `test_dispatch_wiring.py`,
  `test_layout_migration.py`, `test_updater.py`: one error, exit 11 with no swap,
  unchanged dispatch order, no empty summary/state write, nonempty migration,
  unchecked-component exits, no unsupported package advice, and singular/plural.
- `test_winget_manifests.py`, `test_release_evidence.py`,
  `test_version_ssot.py`, `test_doc_consistency.py`: selected-version changelog
  extraction, missing-section failure, release-body/manifest parity, 3.9.2
  consistency, retained JUnit evidence, and help/reference parity.

Use deterministic resolver seams for negative cases; these tests establish
policy, not live package availability. Maintainer runs the full unit suite and
required consistency checks after each implementation wave. Windows CI runs
`python -X faulthandler -u -m pytest _sys/tests/unit -v --cp949-strict --tb=short --junitxml=contract-results.xml`
and the existing required-contract gate; retain reports even on failure.
Acceptance requires all regressions green, preserved rollback safeguards,
no new dependency, and a live managed-pip target check plus package-install
smoke where prerequisites exist. Record unavailable prerequisites explicitly;
never count skipped evidence as PASS.

## Order and Engram Phase 2 audits

1. Documentation: land this reference and its one taxonomy index entry.
2. Before PR merge: audit release history for removed tests/docs/options
   (P2-6), and perform the targeted baseline SSOT/test-regression review.
   Maintainer owns the inventory; reviewer closes each item as intentional,
   restored regression coverage, or a blocking finding, with commit evidence.
3. PR-B: implement from `main`, run checks, obtain independent cross-review and
   clean-room verification, then merge through existing release governance.
4. Phase 2: complete the following Engram audits before release cleanup.

| Audit | Owner, evidence, measurable closure and gate |
| --- | --- |
| P2-1 feedback loop | Maintainer: inventory history/lessons/errors, issue templates and changelog; every finding has an issue/disposition and regression or documented limitation; zero unowned findings. |
| P2-2 SSOT/duplication/hardcoding/no-code | Implementer + reviewer: scan baseline consumers, literals and duplicated rules; one baseline owner, zero unexplained duplicates, explicit disposition for every no-code candidate. |
| P2-3 learnability/folder MECE/rename | Documentation reviewer: record quickstart token counts and owner-approved numeric budget; all entrypoints meet it, links resolve, ownership overlaps close; renamed-root CLI/test smoke passes. |
| P2-4 test-suite MECE/live coverage | Test maintainer: marker/catalog map and gap list; every suite classified, gaps dispositioned, available live suites run; credential failures recorded `SKIPPED_PREREQ`, never PASS. |
| P2-5 platform-limit warnings | Windows verifier: special-character-path and Node.js warning fixtures; all inventoried limits surface truthful warnings; no attempts to overcome unsupported platform limits. |
| P2-6 history closure | Maintainer + reviewer: release-by-release removed/changed tests/docs/options inventory; each item justified or restored, zero unexplained losses; targeted check gates PR merge. |

Each audit records owner, evidence, pass/fail and closure in a retained report;
unresolved failures block completion. Prefer minimal scripts/CI checks over a
new audit framework. Later owner decisions cover five-whys generalizations tied
to regression checks and dated research relevant to Engram: CLI self-update UX,
changelog SSOT, Windows pytest parallelization/privilege handling, and replacing
custom package logic. External-module adoption is a separate PR. Release 3.9.2
requires closed findings, green tests, clean tree/version/changelog checks,
portable-package smoke, WinGet manifest hash verification, and post-publish
GitHub/WinGet verification under [release governance](../release_gate.md).

## Non-goals, risks, and rollback

No PeerHub or SecondBrain changes; no quota, backup, store, or waiver redesign.
No new dependencies, legacy compatibility layer, dispatch reordering, custom
wheel parser, broad maintenance redesign, or changes to patch-first defaults,
explicit minor consent, journal/backup rollback, conservative pip `~` cleanup,
opt-in xdist, or #44's CP949 consolidation. This task does not run audits,
implement PR-B, publish 3.9.2, edit the superseded draft, or create CHANGELOG.md.

Risks: network latency and unavailable pip reduce actionable advice; a dry-run
does not prove runtime imports; availability can change between invocations;
constraint or distribution/module drift could break baseline handling;
empty-summary suppression must preserve genuine failures and nonempty cleanup.
Mitigate with bounded checks, explicit unverifiable states, shared constraints,
behavioral tests, and live Windows/package smoke. `--force` remains an explicit
override, never routine advice; do not describe it as verified readiness.

Before merge, revise or withdraw PR-B while leaving the original draft intact.
After merge, revert the PR-B changes through a reviewed revert; retain changelog
and audit history as historical evidence and use a new version for any published
correction. For a failed managed Python swap, use the existing journaled rollback
and exits 12/13; do not add a parallel recovery mechanism. Stop release promotion
on failed gates; do not overwrite published artifacts or retag 3.9.2.
