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
4. A hosted promotion job starts after the build, independently of Sandbox
   runner scheduling. It polls this run's exact attempt Sandbox job every 15 seconds
   for at most 45 minutes. Missing runners, queued jobs, unsuccessful outcomes,
   timeout, cancellation, skipped jobs, API errors, or missing artifacts mean
   HOLD. Sandbox execution itself is limited to 40 minutes; promotion has a
   55-minute job limit. Workflow concurrency serializes Sandbox host access.
5. Promotion downloads only this run/attempt's artifacts, rechecks the asset
   inventory and SHA256 values, checks candidate ref/commit and evidence run/attempt
   against the workflow identity, and runs `release_evidence.py verify` against
   the candidate and evidence. Only subsequent `v*` tag runs call
   `gh release create --draft --verify-tag` with those downloaded assets, then
   publishes the completed draft. Upload failures leave an unpublished draft. Existing
   releases are not overwritten; publication failure is HOLD. All manifest
   files and the ZIP are published without rebuilding.

A green build or a missing Sandbox report does not authorize release. Treat a
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
not bypass this workflow. No change to `release_evidence.py` was needed.
