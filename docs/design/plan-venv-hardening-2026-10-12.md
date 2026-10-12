Plan document, 2026-10-12. Reference, not an instruction file.

# Engram PR-B2: venv hardening, release 3.9.3

## Status and evidence

This is an Engram-only decision record and implementation plan, not authorization
to merge or publish. The documentation branch is `fix/venv-hardening`, based on
`main`. This documentation change creates no code, changelog entry, or commit.
Structure follows [the PR-B plan](plan-update-advice-parity-2026-10-12.md).

Evidence is the owner's cc/cx/ag dialectic in the external scratchpad folder
`D:/PkgDev/_sys/data/temp/claude/D--PkgDev-workspace/4041a42e-f452-4f0d-9a0f-fc49b63dfd31/scratchpad/`:

- `venv_cx.out`: patch/minor split, editable dependency gap, snapshot pollution,
  conservative cleanup, and silent post-commit pin/manifest failures.
- `venv_ag.out`: missing editable build backends and suppressed dependency/build
  isolation; initially proposes rebuilding all venvs with an extras manifest.
- `venv_r2_cx.out`: retracts rebuild-always, votes P3, and limits blocking
  dependency verification to rebuilt/restored environments.
- `venv_r2_ag.out`: votes P3 after cc's offline/second-SSOT objection.

These are source reviews, not new live reproductions. The owner's resolved B2
scope below supersedes broader round-two proposals about bytecode and package undo.
The cx post-commit finding points to `env_ops.py` around line 340 (the current
`post_failed` return is around line 360); execute and resume need the same fix.

## Resolved decisions relevant to Engram

**UNANIMOUS: option P3.** Patch swaps stay in-place and offline-capable;
minor swaps rebuild the venv as today, with hardened restoration and verification.

| Option | Decision and reason |
| --- | --- |
| P1: status quo plus small fixes | Rejected as insufficient for editable build/runtime dependencies and warning-only rebuild verification. |
| P2: rebuild always | Rejected: makes routine patches depend on package resolution and available artifacts. |
| P3: hybrid | Adopted unanimously by cc/cx/ag: retain patch refresh and strengthen minor rebuilds transactionally. |
| Extras manifest | Rejected: a second SSOT alongside installed metadata; no `extras.json` lifecycle. |
| Package-upgrade undo journal | Separate PR-B3; not part of B2 or its acceptance criteria. |

`env/venv` remains a virtualenv tied to managed embedded Python. Patch refresh
uses `virtualenv --no-seed` and preserves installed packages, including editables.
Minor restoration retains the existing baseline/requested/editable classification
and baseline SSOT. No new manifest, dependency allowlist, or resolver is added.
Docs/help were already corrected in 3.9.2; B2 preserves those corrections.

## PR-B2 files and behavior

The following are proposed implementation files, not changes made by this plan.

| Files | Proposed change |
| --- | --- |
| `_sys/core/repair.py`, `_sys/core/python_manager.py` | Preflight the complete minor restore, including editable build backends and dependencies, before any destructive step; remove blanket `--no-deps` and `--no-build-isolation` from editable restoration. |
| `_sys/core/python_manager.py`, `_sys/core/venv_repair.py` | Gate rebuilt/restored venv completion on successful `pip check`; route failure through existing journaled rollback. |
| `_sys/core/venv_manager.py` | Ignore `~*` distribution metadata when snapshotting; retain existing conservative `pip_leftovers` ownership detection and doctor warning policy. |
| `_sys/core/python_manager.py`, `_sys/core/venv_repair.py` | Reuse conservative pre-swap quarantine under the existing journal, with identity-checked undo and resume. |
| `_sys/core/env_ops.py`, `_sys/core/repair.py` | Surface failed post-commit pin/manifest writes on execute and resume; preserve committed phase, propagate exit 1, and provide recovery advice. |
| `_sys/tests/unit/` files below | Add the fault matrix and preservation/recovery regressions. |
| `_sys/core/version.json`, `CHANGELOG.md` | Advance the version SSOT to 3.9.3 and add its release entry after validation. |

Minor preflight uses pip with execution-equivalent target, constraints, index/offline
policy, build isolation, and editable sources. Check declared and dynamically
required backends/build dependencies, runtime dependencies, and compatible artifacts
for the whole restore set, not just baseline packages. Do not rely on backends
installed in the old venv. Validate staged virtualenv availability as well.
Use disposable staging for target build/metadata checks where necessary; bound
subprocesses and retain actionable reasons. Offline mode never downloads.

Run this preflight before quarantine, backup moves, interpreter replacement, or
active-venv installation. Failure exits 11 with the managed Python, venv, pin,
manifest, and leftovers unchanged. Disposable staging/cache activity is distinct
from mutation of the managed environment. Unverifiable availability fails early.
Successful preflight is no guarantee against later races; actual restore failures
still roll back. Unavailable editable paths retain the existing reported skip policy.

After preflight passes, quarantine only candidates marked removable by existing
`venv_manager.pip_leftovers` checks, before the authoritative pre-swap snapshot.
Ownership requires metadata and a healthy canonical installation/RECORD; never
derive an owner by stripping `~`, guess from directory names, or treat namespace
directories as proof. Revalidate candidates under the lock. Ambiguous, unsafe, or
overlong paths stay with warnings. Failed moves undo earlier moves and stop the
swap. Quarantine is backed up, journaled, resumable, and reversible, not deletion.
Snapshot scanning excludes every `~*` distribution-metadata entry even if kept.

For rebuilt/restored venvs, run their own interpreter's `-m pip check` after all
restoration and before commit. Nonzero exit, timeout, or inability to run it is a
blocking verification failure. Restore the original Python and venv with the
existing rollback; preserve the failed build. Baseline import/version checks remain.
Doctor stays informational. Patch swaps gain no new blocking dependency gate:
pre-existing `pip check` warnings remain warnings, with no package reinstall or
package network dependency introduced by B2.

Post-commit decision: **warn loudly + non-zero exit + recovery hint**. A failed
`write-pin` or `write-manifest` returns failure with exit 1 and phase `COMMITTED`,
including `post_failed` and the operation ID; no generic success footer is printed.
The environment remains committed: do not automatically roll it back after commit.
Retain pending post-step journal state and backups so `engram repair --resume`
retries failed writes without repeating the swap or completed steps. The CLI mapper
must preserve this result rather than normalizing committed operations to success.

## Exact user-visible contract

Print one applicable failure summary, with bounded, sanitized reason text.
Angle-bracket fields are substitutions; fixed wording and exit behavior are contractual.

```text
[Warning] Python minor update preflight failed: <reason>. Managed Python and venv unchanged.
[Warning] Venv dependency verification failed: <reason>. Rolling back Python and venv.
[Warning] Pip leftover quarantined: <path>. Backup: <backup-path>.
[Warning] Pip leftover kept: <path>. <reason>.
[Warning] Python update committed, but state writes failed: <steps>. Exit 1; pin/manifest may be stale.
Recovery: fix write access or available disk space, then run engram repair --resume (operation <op-id>).
```

`<steps>` lists failed step names in execution order, e.g. `write-pin, write-manifest`.
Preflight fixtures use reasons `editable build backend unavailable`,
`no compatible dependency set`, and `required artifacts unavailable offline`.
For rollback completion, retain the existing dispatcher-owned summary and exit 12;
rollback failure retains exit 13 and the existing recovery guidance. Avoid duplicate
failure summaries. Existing patch dependency-warning wording stays unchanged.
JSON results expose the same failure, phase, exit code, and recovery information.

## Tests and acceptance criteria

Use deterministic subprocess/filesystem fault seams; these tests establish policy,
not live artifact availability. Assert exit, message, mutation boundaries, journal
state, and restored tree/package identity, rather than only command flags.

| Fault / behavior | Required evidence |
| --- | --- |
| Missing editable backend | Preflight discovers declared/dynamic build requirements; unavailable backend exits 11 before quarantine or swap; old trees and state remain identical. |
| Dependency conflict | Full restore-set resolution fails early, including editable runtime dependencies; no managed mutation. |
| Offline failure before swap | Missing backend/wheel/virtualenv artifact exits 11 without downloads or managed mutation; cached compatible artifacts can pass. |
| Restore failure / rollback | Inject failure after swap; original Python, venv, packages, and quarantined leftovers restored; failed rebuild retained; exit 12. |
| Unchanged patch behavior | Installed extras/editables preserved, no restore/resolver network calls, warning-only pre-existing dependency conflict does not block; offline patch succeeds with existing prerequisites. |
| Pip-check failure rollback | Rebuilt/restored venv conflict, timeout, and tool failure each block commit and invoke rollback; injected undo failure exits 13. |
| `~` metadata ignored | Healthy canonical plus stale `~*.dist-info`/`~*.egg-info` does not create duplicate snapshot requirements; unknown remnants also excluded. |
| Quarantine ownership | Metadata-proven duplicate moves; bare `~`, guessed names, unhealthy canonical, namespace-only and unsafe entries stay; move failure/crash/resume/undo preserve identity. |
| Pin-write failure | Fault each post-write independently and together on execute/resume: loud warning, exit 1, COMMITTED retained, no success footer or swap undo; successful resume writes only pending steps. |

Extend `test_repair.py`, `test_repair_wiring.py`, `test_python_swap_hardening.py`,
`test_venv_manager.py`, `test_venv_repair.py`, and `test_env_ops.py`.
Acceptance requires the complete matrix green, unchanged patch policy and 3.9.2
help/docs parity, no second SSOT or new dependency, and rollback/resume integrity.
Run the full unit suite and required consistency/contract checks; Windows CI runs
`python -X faulthandler -u -m pytest _sys/tests/unit -v --cp949-strict --tb=short --junitxml=contract-results.xml`.
Retain failure reports. Run managed Windows minor restore and offline patch smoke
where prerequisites exist; record unavailable prerequisites as skipped, never PASS.

## Order and release 3.9.3

1. Land this reference and its design/taxonomy index entries only.
2. Implement preflight and restoration, strict rebuild verification, conservative
   quarantine/snapshot filtering, then post-commit result/recovery propagation.
3. Run fault coverage, full required gates, independent review, and Windows smoke.
4. Advance `_sys/core/version.json` to 3.9.3. Plan a `CHANGELOG.md` 3.9.3 `Fixed`
   entry covering editable preflight/restoration, blocking rebuild `pip check`,
   conservative `~` handling, and visible post-commit state-write failures. State
   that patch package preservation and offline capability remain unchanged.
5. Use that selected changelog section for GitHub/WinGet notes; follow existing
   [release governance](../release_gate.md), packaging/hash and post-publish gates.

## Non-goals, risks, and rollback

No B3 package-upgrade undo journal, rebuild-always, extras manifest, bytecode scrub,
compiled-extension cleanup, or patch hygiene beyond conservative `~` quarantine.
No broad maintenance redesign or repeated 3.9.2 docs/help correction work.
This task does not implement B2, change versions/changelog, commit, or publish.

Risks: isolated builds require available backends/artifacts; resolver results can
change after preflight; editable sources can change; conservative cleanup leaves
ambiguous debris; post-commit state may temporarily disagree with the live runtime.
Mitigate with target-equivalent checks, bounded diagnostics, revalidation, blocking
rebuild verification, retained backups, and truthful resume guidance.

Before commit, use existing journaled rollback and out-of-tree runner, preserving
both original trees and failed builds; no parallel recovery mechanism. After commit,
repair pending state writes through resume. Before merge, revise or withdraw B2;
after merge, use a reviewed revert. Stop release promotion on failed gates. Keep
published 3.9.3 history/artifacts intact and use a new version for later corrections.
