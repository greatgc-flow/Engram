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

- Released v3.9.7 (Latest). `engram update` added a cache note and a `--refresh` pointer (a release made minutes earlier looked missing on a user PC). The current notice shows the UTC check time or `unknown` on every successful core cache hit, including no-update results. `--refresh`/`-r` already existed; cache behavior is unchanged.
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

## 7. v3.11.0 and v3.11.1 (2026-10-25)

- Released v3.11.0 (PR #66 feature, #67 release, #68 WinGet manifests) and v3.11.1 (PR #70 advisory + release, #71 WinGet manifests). For both, the ZIP SHA-256 equals the manifest `InstallerSha256` and the release asset digest, and `gh attestation verify` passes. WinGet manifests were generated for these two versions per the recipe in section 1 (the 3.9.6-3.10.0 gap from section 6 remains); the post-release closure check was not run for them.
- New managed tools in `_sys/defaults/runtimes.json`: ExifTool 13.59 (needed by markitdown for image/audio metadata), yq 4.54.1 (raw exe, `exe_tool`), sd 1.1.0, hyperfine 2.0.0, dust 1.2.6, ouch 0.8.3 (`zip_tool`). Each has a declared SHA-256, an explicit `asset_pattern` (GitHub tools), a canary and a PATH entry in `_sys/env.json`. Not added: zoxide (needs shell init and an isolated `_ZO_DATA_DIR`) and 7-Zip (NSIS installer; `7zr.exe` is `.7z`-only), ouch covers archive work but is not `7z.exe`-compatible.
- Installer hardening: generic `required_paths` (companion directories such as ExifTool's `exiftool_files`) is checked in staging, `_already_current`, post-condition and doctor; canaries now require exit code 0 plus the regex; a pinned entry updated from discovery replaces the old SHA-256 and is rejected without a fresh digest; deliberate manual pins no longer make `update --check` report a provider failure. ExifTool is a manual pin: no version discovery, recompute SHA-256 by hand on each bump (the zip comes from oliverbetz.de, `ExifTool.exe` + `exiftool_files/`).
- Existing installs do not get new default tools from a core update (`update` runs `migrate_layout(merge_defaults=False)` on purpose). Adopt them with `_sys\core\dispatch.bat migrate-layout [--dry-run]`, then `engram update -y`. v3.11.1 adds an advisory printed by `engram update` for shipped default tools missing from the live declaration. KNOWN BUG (issue #72): the README, the 3.11.0 CHANGELOG entry and the advisory text say `engram migrate-layout`, which is not a public verb ("Unknown command"). Fix = change the three texts and add a test that the printed command is runnable; release as v3.11.2.
- Core update on a live install finishes only after the terminal/VS Code that started it closes (`core_update_helper.ps1`); Git and VS Code components are deferred ("in_use_retry_at_session_boundary") while those processes run.
- Lessons: (1) execute every user-facing command string once on a real install before release (cause of #72); (2) peers cannot reach the network or push, and a peer sandbox may have a read-only `.git`: use a fresh clone as the peer workspace, set `git config user.name/user.email` in it before committing, and push/PR from the orchestrator; (3) the auto-mode classifier blocks merges, force-pushes and some `rm -rf $(...)` until the owner says so explicitly; (4) a dependabot PR that failed CI on an old base (Bootstrap managed Python, tests green) passed after `@dependabot rebase`.
- Open: issue #72 (above); dependabot PR #69 (virtualenv 21.14.12 -> 21.14.13 in `_sys/defaults`, CI green, shipped-default pin, not yet reviewed); the owner's live install still needs the terminal restart that completes core 3.11.1.

## 8. v3.11.2 (2026-10-25)

- Released v3.11.2 (PR #74 fix + release, #75 WinGet manifests): README, CHANGELOG 3.11.0 entry and the `engram update` advisory now say `_sys\core\dispatch.bat migrate-layout` (single constant `updater._MIGRATE_LAYOUT_COMMAND`; tests assert the verb is dispatchable and the `engram` CLI does not route it). Closes #72. Dependabot PR #69 (virtualenv 21.14.13) merged first and ships in 3.11.2. ZIP SHA-256 == `InstallerSha256`, attestation verified, post-release closure green.
- Lessons: `peerhub ask` no longer has `--resume` (stream reuse is automatic); cx cannot write `.git/index.lock`, so the orchestrator commits; full suite in a cx sandbox needs a temp dir outside the worktree.
- Open: the owner's live install still needs core 3.11.1 -> 3.11.2 (`engram update`, finishes after the terminal/VS Code closes).

## 9. v3.11.3 (2026-10-30)

- Released v3.11.3 (PR #80 release, #81 WinGet manifests): refreshed runtime defaults (#77: Python 3.15.2, Node 26.13.0, Git 2.56.0.windows.4, VS Code 1.144.0, pwsh 7.6.9) plus the weekly-refresh fix (#78). ZIP SHA-256 == `InstallerSha256`, `gh attestation verify` passed.
- Root cause of the failed 2026-10-26 refresh: the hosted windows image preinstalls Python 3.15.1; its `Lib` leaked into the managed 3.15.2 venv `sys.path` (`_socket` ABI mismatch, pip dead). Workflows (`refresh-runtimes`, `ci`, and the `sandbox-gate` hosted jobs) now delete `C:\hostedtoolcache\windows\Python\3.15*` before bootstrap. Robust fix pending in #79 (`-E`/`-I` on venv pip calls). If a future pin bump fails the same way on another minor, extend the glob.
- Lessons: a refresh dispatch on a branch really opens the automation PR (#77); bot PRs get no CI checks. Python string escapes corrupted `\3` in workflow paths twice (use `chr(92)`/raw bytes). Flaky 10 s/60 s timeouts (`test_release_gate_b1::test_wait_reads_policy_numbers`, `test_python_swap_hardening::test_crash_anywhere...`) passed on rerun; see the flake issue.
- Open: owner live install needs `engram update` (core 3.11.3); #79.

## 10. v3.11.4 (2026-10-31)

- Released v3.11.4 (PR #88 release, #89 WinGet manifests): every core discovery cache hit prints `Core discovery: cached (<time>)` (#84). ZIP SHA-256 == `InstallerSha256`, `gh attestation verify` passed. Full suite 2227 passed; `test_windows_sandbox_provider::test_serialization_across_processes` failed once under `-n auto` and passed serially.
- Lesson: Dependabot PRs #86 (setup-python 7.1.0) and #87 (pytest, hypothesis, pywinpty 3.1.1, virtualenv 21.15.0) arrived while the release was in flight and were NOT included; check `gh pr list` right before tagging. A merge outside the release PRs needs a separate owner go-ahead.
- Open: #79 (deferred); #86/#87 await owner merge; live install needs `engram update --refresh` (core 3.11.4).

## 11. v3.11.5 (2026-11-01)

- Released v3.11.5 (PR #99 release, #101 WinGet manifests): `engram.cmd` honors an absolute `ENGRAM_SYS_DIR` (#98), update discovery never retries an internal `TypeError` with altered options (#93), dependent paths follow the physical system folder (#96), pywinpty 3.1.1 / virtualenv 21.15.0 (#87). ZIP SHA-256 == `InstallerSha256`, `gh attestation verify` passed. Full suite 2238 passed; `test_windows_sandbox_provider::test_serialization_across_processes` fails only under `-n auto`.
- Another AI session filed draft PRs and umbrella issues (#91, #92, #94, #97): only the minimal fixes were merged; the opt-in `--require-pinned-sha256` flag (#94) and a bespoke installed-layout evidence log (#97) were closed as not planned. Start triggers: unattended upgrades installing an unpinned Python; a user-reported failure on a renamed install.
- Open: none (#79 is closed as not planned, start trigger in its comment). Live install needs `engram update --refresh` (core 3.11.5).
