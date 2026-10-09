# Release gate (P0-001)

The `Windows Sandbox release and weekly gate` workflow owns tag publication.
There was no separate release/publish workflow. CI is reusable via
`workflow_call`; its checks must pass before the candidate is built. Manual and
weekly runs exercise the same gate but do not publish a release.

1. A hosted Windows runner builds Engram.exe and the portable ZIP and WinGet
   manifests once. `release_evidence.py freeze` records the tag/ref, commit,
   and every asset SHA256 in `candidate.json`, outside the assets directory.
   The immutable `candidate-<run_id>-<run_attempt>` artifact contains that JSON
   and the assets. No downstream job rebuilds assets.
2. The dedicated interactive `engram-sandbox` runner downloads that exact
   artifact and checks its complete asset inventory and hashes. It extracts
   the frozen ZIP into a fresh run-specific directory and adds source-only
   tests, tools, and test requirements from the same checkout. Runtime
   files come from the ZIP. The existing Sandbox harness runs bootstrap,
   tests, doctor, and network update checks with a 30-minute completion wait.
3. The Sandbox job emits `sandbox_evidence.json`: status is PASS only when
   the harness and preceding steps succeeded, otherwise HOLD. It includes
   the identical `candidate_sha256s`, cancellation/skipping flags, and run ID
   and attempt. The `sandbox-evidence-<run_id>-<run_attempt>` artifact is
   required; missing files are errors. Hard cancellation can prevent upload;
   absent evidence is never approval. Detailed reports remain in the runner's
   run-specific `_archive/test-results` directory.
4. A hosted `upgrade-gate` job (`needs: build-candidate`, `windows-latest`)
   downloads the candidate artifact and the latest published stable release
   ZIP via `gh` (`tag != candidate`). It extracts the previous release to an
   isolated root, seeds user data under `.engram/` (structured JSON, Unicode,
   and raw binary content), and runs `tools/release_gate/upgrade_harness.py`
   against the candidate ZIP using the external SHA256 from `candidate.json`.
   The harness verifies offline staging, manifest integrity, detached helper
   execution, journal completion, updated installed version, and byte-for-byte
   preservation of user data. It emits `upgrade_evidence.json` bound to the
   candidate SHA256s and previous tag, and uploads the
   `upgrade-evidence-<run_id>-<run_attempt>` artifact.
5. A hosted promotion job (`needs: [build-candidate, upgrade-gate, winget-smoke]`) starts
   after build, upgrade, and WinGet checks succeed, independently of Sandbox runner
   scheduling. It polls this run's exact attempt Sandbox job every 15 seconds
   for at most 45 minutes. Missing runners, queued jobs, unsuccessful outcomes,
   timeout, cancellation, skipped jobs, API errors, or missing artifacts mean
   HOLD. Sandbox execution itself is limited to 40 minutes; promotion has a
   55-minute job limit. Workflow concurrency serializes Sandbox host access.
6. Promotion downloads only this run/attempt's artifacts (`candidate`,
   `sandbox-evidence`, `upgrade-evidence`, and `winget-evidence`), rechecks asset inventory
   and SHA256 values, checks candidate ref/commit and evidence run/attempt
   against workflow identity, and runs `_sys/checks/release_evidence.py verify` with
   `--evidence`, `--upgrade-evidence`, and required `--winget-evidence`. If any evidence document is missing,
   non-PASS, or mismatched against candidate hashes or tags, verification
   fails closed and reports HOLD. Only subsequent `v*` tag runs call
   `gh release create --draft --verify-tag` with those downloaded assets, then
   publishes the completed draft. Upload failures leave an unpublished draft. Existing
   releases are not overwritten; publication failure is HOLD. All manifest
   files and the ZIP are published without rebuilding.

A green build or a missing Sandbox/upgrade report does not authorize release. Treat a
cancelled workflow, a still-queued workflow, and any missing/failed promotion
check as HOLD. GitHub job execution timeouts do not bound runner queue time;
this is why the hosted polling job does not have `needs: clean-room-sandbox`.
A runner that appears after the evidence deadline cannot revive the failed
promotion job. Rerun all jobs for a new attempt and a fresh candidate; rerunning
only failed jobs cannot reuse a previous attempt's candidate artifact. Never
publish manually to bypass HOLD. The real ACP=949 proof described in
`docs/cp949_verification.md` remains a separate required pre-release check.

The offline verifier checks consistency, not authenticity. Evidence trust
comes from workflow permissions, same-run artifact selection, protected tags,
and the dedicated runner. Configure repository access so release writers do
not bypass this workflow. `release_evidence.py verify` was extended to check
upgrade evidence compatibility, previous tag validity, and hash binding.

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
data and snapshots its inventory and bytes. WinGet uninstall must exit zero,
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
The hosted workflow never uses either opt-out.

Offline contracts: `python -m pytest _sys/tests/unit/test_winget_smoke.py`.
Tests stub CLI execution and cover success, unavailable WinGet, failed settings,
install/uninstall, incorrect installed bytes/version, remaining files, lost
user data, evidence hash/identity mismatch, missing flags/files, and timeouts.
