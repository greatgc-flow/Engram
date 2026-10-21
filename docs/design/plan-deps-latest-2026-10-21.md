# Latest validated defaults and dependency PRs — v3.10.0

Residual disagreement: none. S1–S4 accepted with the exact boundaries below.
Status: SDD-ready; stop before TDD. This document alone authorizes no implementation.
Owners: cx implements; cc runs full pytest, hosted CI, merge and release.
Branch: `feat/deps-latest-3.10.0`; one implementation PR, followed by refresh/release PRs.

## Final decisions and non-goals

- R1 means latest validated compatible shipped defaults at release preparation, not live discovery at install.
- Python: latest stable; only wheel-preflight incompatibility permits latest-patch-of-current-minor fallback.
  Bootstrap/pytest failure after selection fails the run: no second fallback and no PR.
  Network/discovery failures are unverified, exit nonzero and publish nothing.
- Node: latest supported LTS. Git, VS Code and PowerShell: stable, excluding previews.
- All five shipped runtime artifacts have SHA-256; fresh digests for changed URLs/versions or missing hashes.
  Compare upstream checksums where available; mismatch fails. Local hashes pin bytes, not publisher identity.
- Bootstrap uses live configuration, seeded from defaults only when absent; invalid live JSON fails closed.
  Remove duplicate hardcoded Python defaults; retain existing absent-hash warning for legacy live declarations.
- Exact runtime pip pins apply only to fresh provisioning; repair/snapshot restoration retain existing behavior.
  Repair may install newer upstream packages outside PR review; do not claim all repair inputs are pinned.
  Existing healthy installs are not reconciled to pins; doctor gets no version-drift checks.
- Keep installed-user Python patch-only update default and explicit `--latest`/`--to` semantics.
- One refresh workflow, one test/publish job; weekly and `workflow_dispatch`; no auto-merge or auto-release.
- No bundle transport, reusable-CI changes, candidate artifacts, registry framework, new probe or canary job.
  No snapshot selectors, downgrade resolver, repair-path changes or transitive reproducibility claim.
- Native ACP=949 and prepared-host provider acceptance require actual host evidence; docs cannot supply it.

## Refresh workflow contract

1. Serialize scheduled/manual runs without cancelling an active publish. Checkout main on Windows.
   Use SHA-pinned existing Actions and Git/gh; job permissions: contents and pull-requests write only.
   Tested code is trusted main plus the generated declaration edit; never checkout PR input or execute it.
2. Copy tracked defaults to temporary working input; discover all five runtimes using setup-python tooling.
   Select Python by existing wheel preflight; record rejection/fallback reason. Select latest Node LTS.
   Produce all hashes and diagnostics, then atomically replace tracked defaults on complete success.
   Never read/update developer live `_sys/runtimes.json`; hosted bootstrap seeds its absent live copy.
3. Bootstrap from those defaults before pytest; require success and the managed embedded interpreter.
   Install `requirements-dev.txt`; duplicate CI consistency checks, full unit pytest command and required
   release-contract report check. Set `ENGRAM_REQUIRE_REAL_VENV=1` in both CI and this workflow.
   Use explicit nonzero-exit propagation in PowerShell; no later successful command may hide a failure.
4. Only if all checks pass and defaults changed, commit that file to `automation/refresh-runtimes`.
   Force-with-lease is permitted on this dedicated bot branch; serialize writers. Stage only defaults.
   Tests must not rewrite the candidate declaration; verify it is unchanged before committing.
   No-op creates no commit/PR; failed discovery/bootstrap/checks/tests create no PR.
5. `gh pr create/edit --body-file` maintains one PR with versions, hashes, fallback reasons and run URL.
   Record published commit SHA. That commit contains the tested main tree plus the tested JSON edit.
   A PR API failure fails visibly; retry can reuse the bot branch. No dependency on PR-event CI.
6. cc confirms PR head/evidence before merge; edits or conflicting main changes require revalidation.
   Main is unprotected: this is a maintainer obligation. Do not claim GitHub enforces these checks.

## Per-file change specification

| Files | Change |
|---|---|
| `_sys/core/bootstrap.bat` | Clear inherited declaration variables; validate JSON/required Python fields before network/install; fail closed; preserve journal, cache, hashes and metacharacter-path handling. |
| `_sys/checks/check_tool_updates.py` | Reuse discovery/preflight without live-config apply; expose Python release proposals and Node LTS-major selection only for release defaults. |
| `tools/refresh_runtime_defaults.py` (new) | Small defaults-only orchestration: selection, preflight/fallback, downloads/hashes, atomic write and PR-body report; no interpreter proof orchestration. |
| `_sys/defaults/runtimes.json` | Validated versions/URLs and five artifact hashes; preserve unrelated tool declarations. |
| `_sys/defaults/requirements-runtime.txt` (new) | Exact filelock, pywinpty, psutil, pydantic and virtualenv pins. Four venv packages; virtualenv belongs in embedded Python. |
| `_sys/core/baseline_packages.py` | Keep import-name mapping; tiny strict reader for these five exact declarations, rejecting malformed/missing/duplicate entries. |
| `_sys/core/provisioner.py` | Around 1462/1548/1564/1575: thread fresh-target context to virtualenv/default-spec selection. Record venv absence before creation; fresh targets use pins, existing targets keep bare-name behavior, including forced runs on an existing venv. Existing importable virtualenv remains untouched. |
| `requirements-dev.txt`, `.github/dependabot.yml` | Exact direct dev pins; grouped weekly pip updates for `/` and `/_sys/defaults`; retain Actions updates. |
| `.github/workflows/refresh-runtimes.yml` (new) | Single job implementing the contract above, schedule/concurrency/manual dispatch. |
| `.github/workflows/ci.yml` | Bootstrap before pytest, require real-venv execution; retain consistency checks and required-contract enforcement. No new reusable inputs. |
| `_sys/tests/unit/test_venv_repair.py` | Required flag converts missing interpreter or explicit skip request into failure; optional local skip behavior stays. Retain existing real refresh/regeneration coverage. |
| `_sys/core/isolation_check.py` | Guarded lazy optional provider imports; missing extension yields UNAVAILABLE with guidance. Do not suppress unrelated import errors. |
| Focused unit tests for changed modules | RED assertions below; one optional-extension removal regression. |
| CP949 guide, audit, blueprint/component registry, handoff and affected status docs | Reconcile native-proof policy; correct provider-port/import claims, #54, swap-test status, T92, I6, D1/D3/D12 with evidence; replace manual live-default copying recipe. |
| `CHANGELOG.md`, `_sys/core/version.json`, release manifest | cc finalizes v3.10.0 metadata through the handoff recipe, including #61. |

No edits to python_manager, venv_repair, repair, doctor, snapshot restoration or installed-artifact suite.
Existing recursive packaging must include the new runtime manifest; change packaging only if omitted.

## RED-first acceptance assertions

1. Bootstrap: absent declarations, malformed live JSON, missing Python fields, invalid values and inherited
   PY_* variables yield nonzero plus declaration error, with zero network/install calls. Valid defaults seed;
   valid live wins; malformed live never falls back. Existing journal/path/cache contracts remain green.
2. Refresh: supported latest minor is proposed; wheel incompatibility selects current-minor latest patch and
   records reason. Network failure says unverified, writes nothing, exits nonzero. Node chooses LTS over Current.
   Cover all five runtimes; changed artifact gets fresh digest; mismatch fails; repeat discovery is unchanged.
3. Pins: fresh venv receives four exact specs and embedded Python the virtualenv pin; existing/forced-existing
   venv receives no pinned replacement. Importable virtualenv causes no install; existing repair behavior stays.
   Invalid manifest fails clearly; portable archive includes it. Dependabot covers both manifest directories.
4. Venv: REQUIRE=1 plus missing managed interpreter or SKIP=1 fails, never skips; optional local missing
   interpreter still skips. Hosted result must show the named real test passed, not deselected or skipped.
   Existing regeneration assertions require zero failures and the generated launcher; no new production probe.
5. Isolation: one test hides both extensions, imports/runs the check, asserts success and two UNAVAILABLE
   records with reasons/guidance and no traceback. Normal provider behavior retains existing coverage.
6. Workflow: discovery/test/contract failures prevent publication; unchanged defaults create no PR. Hosted
   manual run proves bootstrap, named real test, one maintained PR and run URL; rerun updates that PR.
   Inspect published diff/head against tested defaults. No standalone workflow-testing framework.

## Work order, release and rollback

1. cx: RED → minimal bootstrap/manifest/provisioner changes; preserve existing-install behavior.
2. cx: optional-import regression/fix; required real-venv flag and CI bootstrap, with focused verification.
3. cx: defaults refresh/hashes, single workflow and Dependabot; docs/status corrections; one implementation PR.
4. cc: full pytest and hosted CI using `docs/maintainer_handoff.md`; review/merge implementation.
5. cc: enable authorized Actions PR creation setting, dependency alerts/security updates; verify via API.
   Dispatch first refresh after merge, inspect/merge generated PR, then validate final release tree.
6. cc: refresh before release; record fallback exceptions and actual no-skip proof. Follow handoff recipe:
   bump version, generate versioned manifest/archive, verify hashes, remove temporary outputs, release PR,
   green exact-head CI, squash merge, annotated v3.10.0 tag. Verify build/upgrade/clean-room/promotion evidence,
   published asset versions/digests and #61. Follow separate WinGet submission recipe and track #446461.
7. Keep #57 open for owner Defender submission; comment that guard work shipped with release/evidence.
   Close only verified completed issues; preserve deferred #60 requirements in peerhub#248 and host blockers.

Rollback: disable refresh workflow; revert bad dependency PR, rerun checks, corrective release if shipped.
Never move published tags. Preserve existing snapshot/backups. Old pins remain usable during outages.
Risks: duplicated CI commands can drift; update both together. Preflight can miss runtime incompatibility:
bootstrap/pytest then fails without PR or fallback. Repair dependencies remain moving upstream inputs.
Fail-closed bootstrap exposes corrupt live files; identify the file clearly. Pip direct pins leave transitives
mutable. Write-token scope is accepted for trusted-main execution; main/head review remains manual.
