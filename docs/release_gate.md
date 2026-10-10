# Release gate (P0-001)

## Post-release closure (EN-GAP-P1-006)

`post-release-closure.yml` runs after a successful tag-push `sandbox-gate`
completion, independently of promotion, and every Friday at 19:00 UTC.
Manual dispatch provides an immediate recheck. It downloads the exact
`candidate-<run_id>-<run_attempt>` artifact, checks its commit against the
publishing run, and retains its frozen JSON in `closure-ledger`. Every run
restores the latest ledger and checks all retained candidates; weekly uploads
renew its 90-day retention. Keep this workflow enabled on the default branch.
After a retention gap or lost initial download, recover the original promotion
candidate artifact and rerun the publishing workflow's closure run; never
reconstruct hashes from the public assets. An empty ledger or API failure fails
loudly; neither proves closure. This workflow cannot block publication.

`tools/release_gate/post_release_closure.py --candidate release/candidate.json
--repo OWNER/REPO --out post_release_closure.json` uses only stdlib and `gh`.
There are no import-time network calls; `check_closure` accepts injectable
release and WinGet fetchers for offline tests. The offline tests exercise injected fetchers without network access.

The release query is `gh api repos/OWNER/REPO/releases/tags/TAG`, followed by
paginated `releases/ID/assets` inventory queries. It requires a published,
non-draft release under the exact tag. The [GitHub release asset API](https://docs.github.com/en/rest/releases/assets)
supplies `digest: sha256:...`; absent digests are errors, with no fallback that
could silently approve unknown bytes. Frozen relative paths map to uploaded
basenames because promotion flattens the inventory. Basename collisions,
missing/extra assets, incomplete uploads, and digest mismatches mean DRIFT.
This detects the post-publication replacement described in blueprint
`07_AUDIT/RELEASE_PROVENANCE_FINDING.md` and follows the incident handling in
`08_LIFECYCLE/RELEASE_PROMOTION_ROLLBACK.md`.

The simplest upstream availability proof is
`gh api repos/microsoft/winget-pkgs/contents/manifests/g/greatgc-flow/Engram/VERSION/greatgc-flow.Engram.yaml`.
An existing file on upstream's default branch proves the version manifest has
merged; no PR search is needed. Only an explicit HTTP 404 means `pending`.
Auth/rate-limit/network errors or malformed responses never mean CLOSED.
This checks upstream manifest availability, not client index propagation.

Each candidate gets `post_release_closure.json` containing status, original
`candidate_sha256s`, `published_digests`, `checked_at`, publication time,
WinGet availability, deadline, summary, and recheck instructions. CLOSED means
exact inventory/digest equality and upstream availability. OPEN_PENDING is
non-failing only while digests match and publication is less than 21 days old.
Weekly/manual rechecks resolve pending; at 21 days it becomes DRIFT until
resolved. DRIFT exits nonzero with an issue-ready summary naming missing,
extra, or replaced assets (or the API error). Workflow summaries and the
uploaded ledger preserve evidence even on failure. No issue is posted
automatically, and no release assets are modified.

The `Windows Sandbox release and weekly gate` workflow owns tag publication.
There was no separate release/publish workflow. CI is reusable via
`workflow_call`; its checks must pass before the candidate is built. Manual and
weekly runs exercise the same gate but do not publish a release.

### Local pre-release verification

Maintainers can run the isolated, real-network clean-room gate locally before tagging:
```cmd
_sys\tests\run-sandbox-test.bat
```
This launches a fresh Windows Sandbox instance, downloads declared runtimes, installs source-only test dependencies, runs the unit/lifecycle/path suite, runs `engram doctor --json`, and forces a live update-discovery refresh. It requires an interactive Windows session (cannot run in Session 0).

### Dry run before a release

- Use `workflow_dispatch` for `sandbox-gate` on a throwaway branch, never the
  release tag. Bump `version.json` above the previous stable version:
  `upgrade-gate` requires candidate > previous; the same version produces HOLD
  with a clear message. Promotion on a non-tag ref verifies evidence but does
  not publish. Delete the throwaway branch after the dry run.
- A queued scheduled run on `main` waiting for a non-existent self-hosted runner
  holds the `engram-sandbox` concurrency group and blocks other runs. Cancel it
  with `gh run cancel <id>`. This only affects workflows from before the sandbox
  job became opt-in via `ENGRAM_SANDBOX_RUNNER`.
- Rerun failed jobs with `gh run rerun <id> --failed`. One runner flake was seen:
  the pytest process ended without a message at about 89%, then passed on rerun.
  Rerun once; investigate if it repeats. If promotion needs a fresh candidate
  artifact for the new attempt, rerun all jobs as required below.
- The first hosted run catches root-hygiene and WinGet source-agreement
  (`0x8A150046`) problems that local tests cannot catch.

### Automated release workflow

1. A hosted Windows runner builds Engram.exe and the portable ZIP and WinGet
   manifests once. On tag pushes, `build-candidate` checks that the tag commit is
   a verified ancestor of `origin/main` using `tools/release_gate/check_tag_on_main.py`
   with full checkout (`fetch-depth: 0`). `release_evidence.py freeze` records
   the tag/ref, commit, and every asset SHA256 in `candidate.json`, outside the
   assets directory. The immutable `candidate-<run_id>-<run_attempt>` artifact
   contains that JSON and the assets. No downstream job rebuilds assets.
2. Two clean-room validation jobs are scheduled in parallel:
   - `clean-room-sandbox`: Dedicated interactive self-hosted runner (`engram-sandbox`)
     extracts the candidate ZIP, adds source test harnesses, and launches real
     Windows Sandbox container isolation (`provider: windows-sandbox`, `runner_environment: self-hosted`).
   - `clean-room-hosted`: GitHub-hosted ephemeral VM (`windows-latest`) extracts the candidate
     ZIP into an isolated directory with NO repo checkout or development tree, and runs
     candidate-contained checks (`bootstrap.bat`, `doctor --json`, and `update --check --refresh`)
     via `tools/release_gate/hosted_clean_room.py` (`provider: hosted-ephemeral-vm`, `runner_environment: github-hosted`).
3. Both clean-room jobs emit `sandbox_evidence.json` with required metadata:
   `status`, `candidate_sha256s`, `cancelled`, `skipped`, `run_id`, `run_attempt`,
   `provider`, `runner_environment`, `workflow_run_id`, and `image`. Missing,
   cancelled, or failing jobs emit HOLD. Each uploads its own distinct artifact:
   `sandbox-evidence-windows-sandbox-<run_id>-<run_attempt>` or
   `sandbox-evidence-hosted-ephemeral-vm-<run_id>-<run_attempt>`.
4. A hosted `upgrade-gate` job (`needs: build-candidate`, `windows-latest`)
   downloads the candidate artifact and the latest published stable release
   ZIP via `gh` (`tag != candidate`). It extracts the previous release to an
   isolated root, seeds user data under `.engram/` (structured JSON, Unicode,
   and raw binary content), and runs `tools/release_gate/upgrade_harness.py`
   against the candidate ZIP using the external SHA256 from `candidate.json`.
   From v3.8.0 on, the gate uses the previous release's updater; candidate-updater
   evidence is rejected. The harness fallback remains only for candidate-path tests.
   Before running the updater, the harness enforces that candidate version is strictly newer than the previous installation, and fails fast if the updater exits without starting a core update.
   The harness verifies offline staging, manifest integrity, detached helper
   execution, verified failed-update rollback, journal completion, updated installed version, and byte-for-byte
   preservation of user data. It emits `upgrade_evidence.json` bound to the
   candidate SHA256s and previous tag, and uploads the
   `upgrade-evidence-<run_id>-<run_attempt>` artifact.
5. A hosted promotion job (`needs: [build-candidate, upgrade-gate, winget-smoke]`) starts
   after build, upgrade, and WinGet checks succeed, independently of self-hosted runner
   scheduling. It executes `.github/scripts/wait_for_sandbox.js` to poll candidate clean-room
   jobs every 15 seconds up to 45 minutes, accepting evidence from EITHER job (whichever completed PASS).
   If neither job completes successfully within the deadline, it throws HOLD.
6. Promotion downloads candidate, upgrade, WinGet, and all candidate clean-room artifacts
   (`pattern: sandbox-evidence-*`), selects the PASS clean-room evidence, and runs
   `_sys/checks/release_evidence.py verify` with `--policy tools/release_gate/release_policy.json`,
   `--evidence`, `--upgrade-evidence`, `--winget-evidence`, and required
   `--run-id ${{ github.run_id }} --run-attempt ${{ github.run_attempt }}`.
   Promotion selects artifacts only from the current run and attempt.
   The policy file at `tools/release_gate/release_policy.json` serves as the trust root: evidence provider must
   exist in policy, runner environment must match provider, and evidence cannot widen policy.
   After evidence verification, promotion attests `release/assets/*.zip` with
   `actions/attest-build-provenance` v4.2.2. This proves the build ran in this repo's
   workflow at this commit; it provides no code signing. Only promotion has
   `id-token: write` and `attestations: write`. Non-tag `workflow_dispatch` dry runs
   exercise attestation too. Attestation failure reports HOLD and prevents publication.
   Closure downloads each published ZIP and runs `gh attestation verify <zip> --repo <repo>`;
   Policy `attestation_required_from: "3.8.1"` requires verification from v3.8.1 onward; missing or invalid attestation produces DRIFT.
   Older releases record `attestation: not-applicable (predates attestation)` and still verify published hashes. It uses only stdlib and `gh`.
   If any check fails, promotion fails closed and reports HOLD. Only subsequent `v*` tag runs call
   `gh release create --draft --verify-tag` with verified assets, then publishes the draft.

A green build or a missing clean-room/upgrade report does not authorize release. Treat a
cancelled workflow, a still-queued workflow, and any missing/failed promotion
check as HOLD. GitHub job execution timeouts do not bound runner queue time;
this is why the hosted promotion job does not have a direct workflow dependency on
the clean-room candidate jobs. A runner that appears after the evidence deadline
cannot revive the failed promotion job. Rerun all jobs for a new attempt and a fresh candidate; rerunning
only failed jobs cannot reuse a previous attempt's candidate artifact. Never
publish manually to bypass HOLD. The real ACP=949 locale claim is deferred. Current locale coverage is emulated
only; it does not prove execution on a machine whose GetACP returns 949.

The offline verifier checks consistency, not authenticity. Evidence trust
comes from workflow permissions, same-run artifact selection, protected tags,
ancestry checks against `origin/main`, the `tools/release_gate/release_policy.json` trust root,
and runner evidence metadata. Configure repository access so release writers do
not bypass this workflow.

## Provider-agnostic clean-room gate (EN-GAP-P1-005)

### Policy trust root (`tools/release_gate/release_policy.json`)

The policy file `tools/release_gate/release_policy.json` defines allowable clean-room providers:
```json
{
  "sandbox_providers": [
    "windows-sandbox",
    "hosted-ephemeral-vm"
  ]
}
```
`_sys/checks/release_evidence.py verify` reads this via `--policy` (defaulting to
`tools/release_gate/release_policy.json`). Rules enforced:
- `evidence.provider` must appear in `policy.sandbox_providers`.
- Provider / environment pairs are strictly mapped:
  - `windows-sandbox` requires `runner_environment: self-hosted`.
  - `hosted-ephemeral-vm` requires `runner_environment: github-hosted`.
- Required string fields: `provider`, `runner_environment`, `workflow_run_id`, `image`.
- Evidence cannot widen policy; policy is immutable repository configuration.

### What hosted clean-room proves vs does NOT prove

The hosted clean-room gate (`clean-room-hosted`) executes on GitHub-hosted `windows-latest`
ephemeral VMs using `tools/release_gate/hosted_clean_room.py`.

**What hosted clean-room PROVES:**
- **Candidate packaging integrity**: The frozen candidate ZIP extracts cleanly without dev tree dependencies.
- **Isolated bootstrapping**: In a fresh root with NO Git repository (`.git` absent) and NO dev tree (`requirements-dev.txt` absent), `_sys/core/bootstrap.bat --skip-vscode --skip-claude` installs embedded Python and executes initial setup.
- **Runtime health**: `engram.cmd doctor --json` succeeds and validates environment invariants.
- **Network discovery**: `engram.cmd update --check --refresh` succeeds in discovering runtime components.
- **Asset hash binding**: Evidence strictly binds to frozen candidate digests, workflow run ID, attempt, and runner image version.

**What hosted clean-room does NOT prove:**
- **No Windows Sandbox hypervisor isolation**: Hosted runs directly inside the ephemeral VM; it does not test execution under disposable Windows Sandbox hypervisor / container isolation.
- **Network is ON**: Hosted VM retains default network connectivity during bootstrap and checks; it does not test air-gapped isolation.
- **Shared runner image environment**: The GitHub-hosted image contains pre-installed software and developer runtimes, unlike bare Windows client installations.
- **Not offline completeness**: Candidate checks exercise network discovery; they do not prove offline self-containment without external mirrors.

### Self-hosted runner opt-in (`ENGRAM_SANDBOX_RUNNER`)

The self-hosted `clean-room-sandbox` job is gated by `if: ${{ vars.ENGRAM_SANDBOX_RUNNER == 'true' }}` to prevent runs from queuing up to 24 hours and blocking the `engram-sandbox` concurrency group when no runner is registered. Once an interactive `engram-sandbox` runner is registered, enable the job by adding repository variable `ENGRAM_SANDBOX_RUNNER` set to `true` under **Settings > Secrets and variables > Actions > Variables**. When unset or set to any other value, the job is skipped immediately and clean-room validation resolves via `clean-room-hosted`.

## Exact-candidate WinGet smoke (EN-GAP-P1-004)

The hosted `winget-smoke` job requires `build-candidate` and runs on
`windows-latest`. It downloads the frozen artifact, verifies provenance and
all asset hashes, and invokes `tools/release_gate/winget_smoke.py`.
WinGet availability on hosted images is not assumed: absence, setting-enable
failure, command timeout, failed or skipped checks, or missing evidence means
HOLD. No hosted WinGet execution has been demonstrated by offline tests.

Generated manifests use an unpublished GitHub release download URL and the
candidate ZIP's SHA256. The harness checks that digest, serves the unchanged
ZIP on loopback HTTP, and rewrites only InstallerUrl in a temporary manifest
copy. Frozen manifests remain untouched and are hashed again after the smoke.
It enables LocalManifestFiles, then runs `winget install --manifest <temp-dir>`
with user scope and an isolated installation location. Every ZIP file must
exist there with the candidate bytes. The installed `engram` alias must target
that executable, and `--version` must print the candidate version in the
existing `Engram <version> (Portable Dev Runtime)` format.

Before uninstall, the harness seeds `<install-root>/.engram` with binary user
data and snapshots its inventory and bytes. It records a `winget list --scope user`
dump, then uses `winget uninstall --manifest <temp-dir> --scope user
--accept-source-agreements --disable-interactivity`. Local manifest matching avoids
relying on a catalog ID or display name; no source filter or force is needed, and
`--purge` is never used. Hosted run 37993728437 reached uninstall but returned
0x8A150046: [source agreements were not accepted](https://github.com/microsoft/winget-cli/blob/master/doc/windows/package-manager/winget/returnCodes.md).
The [uninstall documentation](https://learn.microsoft.com/en-us/windows/package-manager/winget/uninstall)
supports local manifests and source-agreement acceptance; the specific source
was not captured in that run (Microsoft Store is a possible cause). Each command
records its arguments, exit code, stdout and stderr (bounded to 2 KiB per stream)
in evidence; failure and timeout HOLD reasons include both streams. This retains
the list dump before uninstall for the next hosted run. WinGet uninstall must exit zero,
remove program files and the command alias, and leave `.engram` unchanged.
If WinGet's portable uninstaller deletes that directory, the gate correctly
reports HOLD; this change does not alter the installer or runtime to bypass
that requirement. Installed data preservation needs hosted confirmation.

`winget_evidence.json` records PASS only after every assertion, exact candidate
hashes, false cancellation/skipping flags, and workflow run/attempt. The
workflow emits fallback HOLD evidence if the harness cannot run and uploads
it with `if: always()`. Promotion downloads that exact run/attempt's evidence
and requires it alongside Sandbox and upgrade evidence. A failed dependency
also prevents publication; missing uploads never approve a release.

The single verifier is `_sys/checks/release_evidence.py`. It requires WinGet
and upgrade evidence by default, with PASS, exact candidate hashes, and both
cancellation/skipping flags present and exactly false. Explicit
`--no-winget-evidence` is a legacy/test-only opt-out, analogous to
`--no-upgrade-evidence`; each is mutually exclusive with its evidence option.
The hosted workflow never uses either opt-out. Upgrade and WinGet evidence are mandatory with no opt-out.

Offline contracts: `python -m pytest _sys/tests/unit/test_winget_smoke.py`.
Tests stub CLI execution and cover success, unavailable WinGet, failed settings,
install/uninstall, incorrect installed bytes/version, remaining files, lost
user data, evidence hash/identity mismatch, missing flags/files, and timeouts.

## Bounded-HOLD clean-room wait contract (EN-GAP-P1-005)

The promotion job executes `.github/scripts/wait_for_sandbox.js` to poll candidate clean-room jobs (`clean-room-sandbox` and `clean-room-hosted`) every 15 seconds up to the policy-defined 45-minute deadline, accepting evidence from either clean-room provider:
- Successful completion (`status: completed`, `conclusion: success`) on either candidate job logs PASS and resolves immediately.
- If all listed candidate jobs have completed unsuccessfully (`failure`, `cancelled`, `skipped`), throw `HOLD: Sandbox concluded <conclusion>`; while any candidate job remains pending or running, polling continues.
- Evidence deadline exceeded: if no candidate job completes successfully before the deadline, polling terminates at 45 minutes and throws `HOLD: Sandbox runner unavailable or evidence deadline exceeded (45 minutes)`.
- Resilient late dispatch: candidate jobs appearing or running before the deadline poll until completion.
- Fail-closed API handling: GitHub API errors throw `HOLD: GitHub API error: <msg>`; malformed or empty job lists throw `HOLD: malformed or empty job list`. The script never silently passes.

Offline contract verification: `_sys/tests/unit/test_wait_for_sandbox.py` tests `.github/scripts/wait_for_sandbox.js` under Node.js via `tools/release_gate/wait_for_sandbox_driver.js`, stubbing GitHub Actions pagination and overriding `Date.now`/`setTimeout` with fake timers so tests run instantly without real waiting.


### Core helper rollback journal

The helper records candidate-created paths in `created_files` before replacement.
On failure it writes `ROLLBACK_IN_PROGRESS`, removes those files, restores backups,
and verifies original SHA-256 hashes and absence of candidate-created files.
Only verified undo receives `FAILED_ROLLED_BACK`; undo or verification failure
receives `FAILED_ROLLBACK_FAILED`. Both failures exit 1. The upgrade gate requires both successful `COMPLETED` replacement and injected
failed replacement with verified `FAILED_ROLLED_BACK` undo. Keep staging, backups, and the journal for investigation when
rollback fails; do not treat that state as a restored installation.
The offline helper fault tests compare the full installed file inventory, excluding
handoff artifacts under the system directory's `data/temp`, and cover renamed systems.

## Wave B1 coherence contracts

`validate_evidence` in `_sys/checks/release_evidence.py` is the shared predicate
for Sandbox (either provider), upgrade, and WinGet. Each requires `status: PASS`,
`cancelled` and `skipped` present and exactly JSON false, identical candidate
hashes, and string `run_id` / `run_attempt` equal to the current promotion.
The CLI requires both current identity arguments; the workflow supplies GitHub
context values. Python callers may supply those arguments or current GitHub
environment values; missing current identity fails closed. Sandbox additionally
requires `workflow_run_id` to equal that current run, allowed provider/environment
metadata, and image. Upgrade additionally requires a different previous tag.

Hosted extraction belongs to `hosted_clean_room.py`: the supplied archive must
identify exactly one frozen asset and its bytes must match that asset SHA256.
The root must not exist, including an empty root or link. The driver extracts
the same bytes it hashed and rejects paths escaping that fresh root. A populated
installation cannot substitute for the supplied candidate archive.

`tools/release_gate/installed_artifact_suite.json` defines the mandatory suite
once: bootstrap with `--skip-vscode --skip-claude`, `doctor --json`, and
`update --check --refresh`. Hosted runs these through the shared Python runner;
Sandbox's entry is generated from the same data by `sandbox_installed_suite.py`
into the extracted candidate's source-only harness. Both require every command
to exit zero. Sandbox additionally provides hypervisor isolation, installs source
test dependencies, and runs the full unit/lifecycle/path suite. Hosted adds no
source suite; archive integrity and fresh-root checks precede its installed suite.

`tools/release_gate/release_policy.json` owns `evidence_wait_minutes: 45`,
`evidence_poll_seconds: 15`, `winget_pending_days: 21`, and
`closure_retention_days: 90`. The wait script, closure tool, and ledger upload
read these values. Workflow job timeouts and the wait step's outer 46-minute
safety timeout remain fixed; making YAML timeout expressions consume checkout
files would require additional job-output plumbing. They must be reviewed if
the evidence deadline grows. No requested policy value remains hardcoded in its
operational consumer.

The policy's small `required_test_ids` list names release evidence, installed
hosted validation, upgrade, bounded wait, missing flags, and closure continuation
contracts. CI and Sandbox produce JUnit XML and run `check_required_tests.py`.
Any required ID absent, skipped, failed, or errored fails the gate; all parameter
cases for a listed ID must pass. Other platform-specific skips remain allowed.
IDs use JUnit `module[.Class]::test` names, without a repository package prefix.

Closure checks each retained candidate with an independent subprocess deadline.
A timeout writes candidate-bound DRIFT evidence and a summary, then checks the
remaining candidates. Any DRIFT makes the ledger check fail after traversal.


## Wave F public upgrade coverage

The hosted upgrade job runs the previous installation's public updater with
`--only core --yes`, using its own helper and the frozen local candidate seam.
If its resolver/provisioner lack the external-digest seam, the gate explicitly
records `updater_source: candidate`: candidate updater and helper code run against
the previous tree. This proves candidate migration/rollback compatibility, but
cannot prove that the older release's updater can discover or install the candidate.
No staging implementation is copied into the harness.

A separate clone exercises deterministic failure after replacement through a
PowerShell filesystem boundary wrapper. Undo must expose `ROLLBACK_IN_PROGRESS`,
end in `FAILED_ROLLED_BACK`, and preserve the full file inventory captured at
handoff, excluding only `_sys/data/temp` helper artifacts. Public updater
bookkeeping before handoff remains in that inventory. Success must install the
candidate version and preserve seeded user data. Promotion requires both
`scenarios: {upgrade: PASS, rollback: PASS}` and the recorded updater source.
