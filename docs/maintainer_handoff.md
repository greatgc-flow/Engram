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
  - Dependabot PR #54 (upload-artifact 7.0.2): update-branch, wait for CI, merge.
  - Code signing for Engram.exe / Defender false-positive submission.
  - winget manifests for 3.9.6 deliberately not generated (owner excluded winget this round).
  - `agy` "mkdir ...\.gemini\antigravity-cli: file already exists" is external to Engram: a stale file/dangling link at that path; delete it and agy recreates it.
- Pitfall: `check_tool_updates` imports top-level `version_resolver`, a different module object from `core.version_resolver`; tests must patch both or they hit the live network.
- Run `check_tool_updates --refresh --propose-diff` then `--apply`, and copy the live `_sys/runtimes.json` / `tool-catalog.v1.json` into `_sys/defaults/` before every release (live copies are gitignored).
