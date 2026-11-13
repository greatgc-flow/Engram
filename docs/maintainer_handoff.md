Reference notes for maintainers. Not an instruction file: open it only when needed.

For AI peer collaboration rules, see [PeerHub docs/HANDOFF.md](https://github.com/greatgc-flow/peerhub/blob/main/docs/HANDOFF.md).

## 1. Release recipe

- Dispatch `refresh-runtimes.yml` from main first (`gh workflow run refresh-runtimes.yml --ref main`). It discovers tracked defaults, bootstraps, runs the full unit suite and required contracts, then creates/updates one PR only on success. Review its versions, hashes, fallback reasons, run URL and exact head before merging; main has no required checks. Never copy developer live declarations into shipped defaults. An upstream 5xx (for example HTTP 504) during refresh is not a release hold: rerun it once or twice, then release on the last merged defaults and say so in the release PR (v3.11.9).
- Check `gh pr list` right before tagging: Dependabot PRs that arrive while a release is in flight are not included, and a merge outside the release PR needs a separate owner go-ahead.
- Bump `_sys/core/version.json` and write the `CHANGELOG.md` section (it is the release-notes source, see [`release_gate.md`](release_gate.md#release-notes-source)).
- Generate `_sys/core/release-manifests/<ver>.json` by calling `tools.winget.build_package.create_portable_archive()` directly, verify hashes against the checkout, and delete the temporary ZIP and unversioned manifest.
- Open PR `chore(release): vX.Y.Z` with full unit suite and CI green.
- Squash-merge into `main`.
- Create annotated tag `git tag -a vX.Y.Z` on `main` and push it (credential fallback: `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push origin vX.Y.Z`).
- Release promotion requires successful clean-room evidence as defined by [`.github/workflows/sandbox-gate.yml`](../.github/workflows/sandbox-gate.yml) (step "Verify before promotion or publish"); do not release without it. A held run must be rerun whole: `gh run rerun --failed` cannot reuse the candidate artifact. A hosted hold on `update --check` reporting "Engram core (rate limited)" is a shared-runner GitHub API limit, not a defect: rerun whole (#115, v3.11.8). A tagged version whose rerun still holds stays burned (CHANGELOG marks it YANKED); never move published tags.
- Open a separate `chore(release): winget manifests for vX.Y.Z` PR copying the release's `greatgc-flow.Engram*.yaml` assets into `manifests/g/greatgc-flow/Engram/<ver>/` after checking `InstallerSha256` equals the release ZIP digest.
- Rollback of a bad dependency refresh: disable the refresh automation, revert the dependency PR, rerun checks and publish a corrective release if already shipped.
- Afterwards the owner's live install needs `engram update --refresh`. A core update finishes only after the updater process that started it exits (`core_update_helper.ps1` waits for that PID, `updater.py`); closing the terminal or VS Code is not what completes it. Git/VS Code components use separate in-use locks and are deferred while those processes run.

## 2. Pitfalls

- `engram` on PATH runs the INSTALLED copy (`D:\PkgDev\_sys`), not a dev checkout (call module code directly to test dev changes).
- Never create `_archive` in the Engram root (legacy-layout marker breaks updater tests).
- Test commands and the parallel run are in [`CONTRIBUTING.md`](../CONTRIBUTING.md#2-running-tests). Peer sandboxes hit two separate problems: no write access to the default temp dir (point `TMP`/`TEMP` at a writable folder), and tidy's guard against a temp dir inside the worktree (keep it outside). If neither can be arranged, the maintainer runs the suite.
- One-off flakes that pass on rerun: `test_upgrade_gate_offline`, `test_wave_c1`, `test_release_gate_b1::test_wait_reads_policy_numbers`, `test_python_swap_hardening::test_crash_anywhere...`; `test_windows_sandbox_provider::test_serialization_across_processes` fails under heavy parallel load (`-n auto`, seen 2026-10-31 and 2026-11-09) and passes on rerun.
- Help files must be ASCII and <=80 columns and are embedded verbatim in `docs/cli_reference.md`.
- Claude Code creates a project folder per working directory (tests using a temp cwd litter `.engram/claude/projects`).
- `check_tool_updates` imports top-level `version_resolver`, a different module object from `core.version_resolver`; tests must patch both or they hit the live network. An autouse guard in `_sys/tests/unit/conftest.py` blocks real network access (opt out: `@pytest.mark.network`).
- A pinned discovery fake must return the current version (nothing newer). Returning `0.0.0` makes `update --yes` rewrite the live gitignored `_sys/runtimes.json` and tool catalog; restore them from `_sys/defaults/`.
- Tests must not read live `_sys/defaults/runtimes.json` for version-dependent assertions; subprocess tests of `.bat` output need `errors="replace"` on CP949 hosts.
- CI: bootstrap the managed Python after the unit suite, never before (it pollutes root-layout tests and hangs the upgrade gate); run `test_real_venv_refresh_and_regen` separately with `ENGRAM_REQUIRE_REAL_VENV=1`; `ci.yml` keeps exactly one `-m pytest`.
- Hosted Windows images preinstall Python; the workflows delete `C:\hostedtoolcache\windows\Python\3.15*` before bootstrap (extend the glob on the next minor). Python string escapes corrupt `\3` in workflow paths (use `chr(92)` or raw bytes).
- Pinning a tool's digest requires an `asset_pattern` so discovery can read newer upstream digests (a unit test enforces it). `hosted_clean_room.default_runner` reports stderr and falls back to stdout only when stderr is empty, so a discovery error list printed on stdout is hidden; get the real payload by dispatching `sandbox-gate.yml` on a branch that prints `check_tool_updates.py --json` (`PYTHONPATH=<root>/_sys`).
- Execute every user-facing command string once on a real install before release (#72).
- Existing installs do not get new default tools from a core update; adopt them with `_sys\core\dispatch.bat migrate-layout`, then `engram update -y` (`engram update` prints this advisory).
- Peers: no network or push, possibly a read-only `.git`. Use a fresh clone as the peer workspace, set `git config user.name/user.email` in it, and commit/push/PR from the orchestrator. The auto-mode classifier blocks merges and force-pushes until the owner says so. Bot PRs get no CI checks; a Dependabot PR that failed CI on an old base passes after `@dependabot rebase`.

## 3. Decisions and deferrals

- Python update flow (`engram update -o python [--latest] -y`): default = latest patch of the installed minor; minor jumps need `--latest` or `--to` and pass the readiness check described in [`cli_reference.md`](cli_reference.md#engram-update); when no SHA-256 is declared for the target version a warning is printed and the computed hash is recorded; `bootstrap.bat` no longer auto-bumps.
- Shipped Python defaults select latest stable; wheel incompatibility alone permits current-minor patch fallback. Node selects supported LTS. Fresh pip provisioning uses direct manifest pins; repair and snapshot restore keep their package policy.
- Isolation `run` and an AI Skill are DEFERRED until a tracked request, a concrete caller/command, a reason existing workflows fail, and a supported host for live acceptance exist. Isolation is not in release gates.
- A shared cross-AI memory folder/junction/standing-instruction scheme was tried and rejected by the owner (no junctions or subst) - do not retry.
- WinGet manifests for 3.9.6-3.10.0 were deliberately not generated (owner choice). Manifests resumed with 3.11.0.
- WinGet channel PAUSED by owner decision 2026-11-10 (#119): `release_policy.json` `"winget_channel": "paused"`; post-release closure treats WinGet as not submitted (CLOSED, "paused (owner policy)") once digests and attestation pass. Only G8 closure is paused: `winget-smoke` and manifest generation keep running. Re-activate with `"winget_channel": "active"` (see [`release_gate.md`](release_gate.md)).
- Code signing / Defender false-positive submission for Engram.exe: #63 closed as not planned; reopen if users report AV blocks.
- Not added as managed tools: zoxide (needs shell init) and 7-Zip (NSIS installer); ouch covers archives but is not `7z.exe`-compatible.
- Closed as not planned with recorded start triggers: `--require-pinned-sha256` (#94), installed-layout evidence log (#97), `-E`/`-I` on venv pip calls (#79).

## 4. Current state (3.11.13, as of 2026-11-13)

- Pending: v3.11.13 (2026-11-13; hidden-launch errors logged to start_*.log). Previous release: v3.11.12 (2026-11-13; PR #128, tag `v3.11.12`, sandbox-gate run 43357228410 promoted on attempt 2 after a rate-limited hosted hold (#115 pattern); WinGet manifests in-repo, upstream channel paused; hidden double-click launch, VS Code output to vscode.log, first run keeps the console; unsigned Engram.exe). Previous release: v3.11.11 (2026-11-12 UTC / 11-13 KST; PR #126, tag `v3.11.11`, sandbox-gate run 43257804438 promoted; WinGet manifests in-repo, upstream channel paused; #125 guided recovery for dependency-blocked Python minor updates; triage scored 100 unanimously by cx/ag). Previous release: v3.11.10 (2026-11-11; PR #123, tag `v3.11.10`, sandbox-gate run 42992408143 promoted; ZIP sha256 `614C46AA...D82B`; WinGet manifests in-repo, upstream channel paused; #121 Python minor-update blockers named in the warning, #122 runtime refresh Git 2.56.1 / VS Code 1.145.3 / PowerShell 7.7.0; scope voted unanimously cc/cx/ag). Previous release: v3.11.9 (2026-11-09; PR #117, tag `v3.11.9`, sandbox-gate run 42575276836 promoted; ZIP sha256 `18EFBF1C...DD9D`; runtime defaults from the last successful refresh 2026-11-08 16:30Z because three refresh dispatches hit upstream HTTP 504; #112: `snapshots restore --apply` refused with exit 14 while a journal is open, cx/ag/cc unanimous option a). v3.11.8: closure audit ([`history/closure-audit-2026-11-09.md`](history/closure-audit-2026-11-09.md)). See [`CHANGELOG.md`](../CHANGELOG.md). v3.11.6 was tagged but never published (YANKED).
- Open issues: none. Owner follow-ups: live install `engram update --refresh`; T92 per-item host clutter triage ([`history/migrated-backlog-open-items.md`](history/migrated-backlog-open-items.md)); native ACP=949 and prepared-host Sandbox/WSL acceptance need real hosts ([audit D10](history/audit-2026-10.md#4-open-decisions-for-the-maintainer)).
- Keep the remote at `main` only: delete release/feature/automation branches after merge.
- One-time owner setup is done: Actions PR creation, dependency graph/alerts/security updates, Dependabot pip for `/` and `/_sys/defaults`.
- Per-release notes v3.9.6-v3.11.7 are archived in [`history/handoff-2026-10.md`](history/handoff-2026-10.md).
