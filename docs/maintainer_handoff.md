Reference notes for maintainers. Not an instruction file: open it only when needed.

For AI peer collaboration rules, see [PeerHub docs/HANDOFF.md](https://github.com/greatgc-flow/peerhub/blob/main/docs/HANDOFF.md).

## 1. Release recipe (as done for v3.9.0/v3.9.1)

- Bump `_sys/core/version.json` first.
- Generate `_sys/core/release-manifests/<ver>.json` by calling `tools.winget.build_package.create_portable_archive()` directly, verify hashes against the checkout, and delete the temporary ZIP and unversioned manifest.
- Open PR `chore(release): vX.Y.Z` with full unit suite and CI green.
- Squash-merge into `main`.
- Create annotated tag `git tag -a vX.Y.Z` on `main` and push it (credential fallback: `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push origin vX.Y.Z`).
- The tag workflow (`build-candidate`, `upgrade-gate`, `winget-smoke`, `clean-room-hosted`, `promotion`; `clean-room-sandbox` is skipped without a self-hosted runner) publishes the GitHub Release.
- Open a separate `chore(release): winget manifests for vX.Y.Z` PR copying the release's `greatgc-flow.Engram*.yaml` assets into `manifests/g/greatgc-flow/Engram/<ver>/` after checking `InstallerSha256` equals the release ZIP digest.

## 2. Pitfalls

- `engram` on PATH runs the INSTALLED copy (`D:\PkgDev\_sys`), not a dev checkout (call module code directly to test dev changes).
- Never create `_archive` in the Engram root (legacy-layout marker breaks updater tests).
- Peers cannot run pytest (temp-dir ACL): run `python -m pytest -q _sys/tests -p no:cacheprovider` yourself (~9 min; fast parallel: `python -m pytest -q _sys/tests -p no:cacheprovider -n auto`, ~2 min on 12 cores; rerun serially before treating a parallel-only failure as a bug).
- One-off flakes that pass on rerun: `test_upgrade_gate_offline`, `test_wave_c1`.
- Help files must be ASCII and <=80 columns and are embedded verbatim in `docs/cli_reference.md`.
- Claude Code creates a project folder per working directory (tests using a temp cwd litter `.engram/claude/projects`).

## 3. Decisions and deferrals

- Python update flow (`engram update -o python [--latest] -y`):
  - Default = latest patch of the installed minor.
  - Minor jumps need `--latest` or `--to` and run a pre-flight for the embed zip and `win_amd64` wheels of `pywinpty`, `pydantic-core`, `psutil`.
  - No pinned SHA-256 so a warning is printed.
  - `bootstrap.bat` no longer auto-bumps.
- Isolation `run` and an AI Skill are DEFERRED until a tracked request, a concrete caller/command, a reason existing workflows fail, and a supported host for live acceptance exist.
- Isolation is not in release gates.
- A shared cross-AI memory folder/junction/standing-instruction scheme was tried and rejected by the owner (no junctions or subst) - do not retry.

## 4. State as of 2026-10-17 (v3.9.6)

- Released v3.9.6 (Latest). Engram.exe now embeds version info and an asInvoker manifest to reduce AV false positives (still unsigned; a code-signing cert or a Microsoft Defender false-positive submission is the durable fix).
- Remote and local branches pruned to `main` (full backup bundle was made before deletion). Keep it that way: delete release/feature branches after merge.
- Open backlog:
  - Dependabot PR #54 is merged (`fb0ca76`); upload-artifact is SHA-pinned at 7.0.2. No follow-up remains.
  - Code signing for Engram.exe / Defender false-positive submission.
  - winget manifests for 3.9.6 deliberately not generated (owner excluded winget this round).
  - `agy` "mkdir ...\.gemini\antigravity-cli: file already exists" is external to Engram: a stale file/dangling link at that path; delete it and agy recreates it.
- Pitfall: `check_tool_updates` imports top-level `version_resolver`, a different module object from `core.version_resolver`; tests must patch both or they hit the live network.
- Before release, dispatch `refresh-runtimes.yml` from main (`gh workflow run refresh-runtimes.yml --ref main`). It discovers tracked defaults, bootstraps, runs the full unit suite and required contracts, then creates/updates one PR only on success. Review its versions, hashes, fallback reasons, run URL and exact head before merging; main has no required checks. Never copy developer live declarations into shipped defaults.
- One-time owner setup: enable Actions PR creation (`can_approve_pull_request_reviews=true`, default workflow permissions remain read); enable dependency graph/alerts/security updates and verify via API. The refresh job requests only contents/pull-requests write. No PR-event CI trigger is assumed.
- Python release defaults select latest stable; wheel incompatibility alone permits current-minor patch fallback. Bootstrap/test failure publishes nothing; discovery/network failure is unverified. Node selects supported LTS. Fresh pip provisioning uses direct manifest pins; repair and snapshot restore retain their existing package policy.

## 5. v3.9.7 (2026-10-17)

- Released v3.9.7 (Latest). `engram update` prints a cache note and a `--refresh` pointer when the core result comes from the 4 h discovery cache (a release made minutes earlier looked missing on a user PC). `--refresh`/`-r` already existed.
- Unit tests are now blocked from real network access by an autouse guard in `_sys/tests/unit/conftest.py` (opt out: `@pytest.mark.network`). The guard immediately exposed `test_root_write_locations` calling live release APIs; it now pins discovery.
- Pitfall: a pinned discovery fake must return the current version (nothing newer). Returning `0.0.0` made `update --yes` rewrite the live gitignored `_sys/runtimes.json` and tool catalog with `0.0.0`; restore them from `_sys/defaults/`.
- Backlog: Defender false-positive submission for Engram.exe (owner action); winget manifests for 3.9.6/3.9.7 not generated by choice.

## 6. v3.10.0 (2026-10-21)

- Released v3.10.0 (Latest) via PR #62: ZIP digest equals the manifest `InstallerSha256`, `gh attestation verify` passes, post-release closure succeeded. Design record: `docs/design/plan-deps-latest-2026-10-21.md` (cc+cx unanimous; a heavier bundle/reusable-CI design was cut for simplicity).
- Defaults now: Python 3.15.0, Node.js 24.22.0 LTS, SHA-256 on all five runtimes. `bootstrap.bat` has no hardcoded Python fallback and fails closed. `refresh-runtimes.yml` (weekly + `gh workflow run refresh-runtimes.yml --ref main`) maintains one PR only after bootstrap + full tests pass; review its run URL/head before merging (main has no required checks). Dependabot pip covers `/` and `/_sys/defaults`. Repo alerts, security updates and Actions PR creation are enabled.
- CI lesson: bootstrapping the managed Python inside the checkout before the unit suite pollutes root-layout tests and hangs the upgrade gate. Bootstrap after the suite and run `test_real_venv_refresh_and_regen` separately with `ENGRAM_REQUIRE_REAL_VENV=1`. `ci.yml` must keep exactly one `-m pytest` (doc-consistency test), so the second run uses the `pytest` entry point.
- Test pitfall: tests must not read live `_sys/defaults/runtimes.json` for version-dependent assertions (refresh fixtures pin Python 3.14.5); subprocess tests of `.bat` output need `errors="replace"` on CP949 hosts.
- Issues: none open. #57 closed (lesson + network guard shipped); the owner-only Defender false-positive submission / code signing was split to #63 and closed as not planned (reopen if users report AV blocks). #60 closed; deferred multi-account requirements live in peerhub#248 (PeerHub v0.22.0 already provides `peerhub account bind` for cc/cx; ag unsupported and banned).
- Still outstanding: winget-pkgs PR #446461 (3.7.0) is stale; WinGet manifests for 3.9.6-3.10.0 are not generated by owner choice, so closure may report DRIFT after 21 days (needs an explicit policy); native ACP=949 (D10) and prepared-host Sandbox/WSL acceptance need real hosts; T92 housekeeping is resolved (clean tree).
- Rollback: disable refresh automation, revert the bad dependency PR, rerun checks and publish a corrective release if already shipped. Never move published tags.
