# Changelog

All notable changes to Engram are documented here.
The format follows Keep a Changelog. Versions follow Semantic Versioning.
Historical entries are reconstructed from git commits and merged PR titles.

## [Unreleased]

## [3.11.9] - 2026-11-09

### Changed

- `engram snapshots restore NAME --apply` is refused with exit 14 while an operation journal is open (#112); finish or undo the interrupted operation first (`engram repair --resume` or `--rollback`). `list`, `show`, `pin`, `unpin` and the restore preview stay available. The previous behaviour could move back a still-pending backup that `repair --rollback` needs.

## [3.11.8] - 2026-11-09

### Changed

- Default VS Code 1.145.2 (validated by the refresh-runtimes workflow; Python 3.15.2, Node.js 26.13.0, Git 2.56.0.windows.4 and PowerShell 7.6.9 were already current).
- `engram repair` / `engram relocate` reject `--dry-run` together with `--resume` or `--rollback` (exit 2) instead of executing recovery despite `--dry-run`; recovery always executes directly.
- Option abbreviations (for example `--j` for `--json`) are rejected with exit 2 on `update`, `repair`, `relocate`, `tidy` and `isolation`.
- `engram open PATH` exits 1 when VS Code is missing (previously a warning with exit 0); a VS Code launch failure also exits 1 with an `[Error]` line instead of a traceback.
- `engram snapshots list` rejects surplus operands (exit 2) before scanning the registry.
- Runner and recovery hand-off notices, the "Engram is not set up" error, the other `dispatch.bat` `[Error]` lines and config-load warnings go to stderr, so `--json` output on stdout stays parseable.
- The `engram update` notice no longer claims the core update finishes when the terminal/VS Code closes; the helper waits for the updater process itself to exit.
- Help: "Engram is not set up" (exit 1) is stated once as a rule for every command instead of per verb; exit 1 causes added for `open`, `tidy`, `reset`; `engram help` Safety model rewritten; `isolation` listed under Health & repair in README and the CLI reference.
- Docs consolidated (one fact, one place): maintainer handoff split into current state plus `docs/history/handoff-2026-10.md`; README, CONVENTION, CONTRIBUTING and the guides de-duplicated and corrected.

### Removed

- Undocumented `tidy --base-dir` / `--sys-dir` options.

### Maintainers

- Sandbox test results write to `_sys/data/test-results/` (gitignored) instead of the legacy `_archive/` marker directory.

## [3.11.7] - 2026-11-01

### Changed

- Shipped runtime defaults now pin SHA-256 digests for the 8 GitHub-release tools that had none (ripgrep, bat, fd, delta, fzf, jq, gh, oh-my-posh), so downloads are verified before install (#100).

### Fixed

- The same 8 tools now declare an asset pattern, so update discovery can read the new release digest; without it `engram update --check` failed as soon as upstream was newer than a pinned version (found by the release clean-room gate; v3.11.6 was tagged but never published).

## [3.11.6] - YANKED

- Tagged but never published: the release clean-room gate held it. Its fixes ship in 3.11.7.

## [3.11.5] - 2026-11-01

### Fixed

- `engram.cmd` honors an absolute `ENGRAM_SYS_DIR` instead of prefixing the portable root a second time (#98).
- Update discovery checks the discoverer signature before calling it and never retries an internal `TypeError` with altered options (#93).
- Dispatcher paths follow the physical system directory even when `paths.sys` is configured; explicit external child paths remain unchanged (#95).

### Changed

- Shipped runtime defaults: pywinpty 3.1.1 and virtualenv 21.15.0 (Dependabot #87).

## [3.11.4] - 2026-10-31

### Fixed

- Every successful Engram core discovery cache hit now prints one quiet
  `Core discovery: cached (<UTC check time or unknown>)` notice with the
  `engram update --refresh` command, including when already up to date.
  This replaces the old hard-coded "up to 4 h old" hint; cache behavior is unchanged.

## [3.11.3] - 2026-10-30

### Changed

- Refreshed runtime defaults: Python 3.15.2, Node.js 26.13.0, Git
  2.56.0.windows.4, VS Code 1.144.0, and PowerShell 7.6.9.

### Fixed

- The weekly runtime-defaults refresh workflow no longer fails when the hosted
  runner has a different Python 3.15 patch preinstalled.

## [3.11.2] - 2026-10-25

### Fixed

- Corrected the layout migration command in the update advisory, README, and
  3.11.0 notes to `_sys\core\dispatch.bat migrate-layout`.

## [3.11.1] - 2026-10-25

### Added

- `engram update` advises when shipped default tools are not in the effective
  live declaration, with the explicit commands to adopt them. The advisory is
  suppressed with `--only` and leaves declarations and update proposals unchanged.

## [3.11.0] - 2026-10-25

### Added

- Managed ExifTool 13.59, yq 4.54.1, sd 1.1.0, hyperfine 2.0.0, dust 1.2.6,
  and ouch 0.8.3 with declared SHA-256 pins and PATH entries. Ouch supplies
  archive operations using its own CLI, replacing the proposed 7-Zip addition.
- Generic `required_paths` for companion payload directories, checked during
  staging, already-current detection, deployment verification, and doctor.
  ExifTool preserves its adjacent `exiftool_files` payload. Its pin is manual:
  no automatic version discovery; recompute SHA-256 by hand for each bump.
- Existing installations can adopt the new declarations with
  `_sys\core\dispatch.bat migrate-layout`, followed by `engram update` to install the tools.

### Changed

- Shipped defaults refreshed to the latest validated releases: Git 2.56.0.windows.3,
  VS Code 1.143.1, PowerShell 7.6.8, Node.js 24.22.1 LTS, Python 3.15.1.

### Fixed

- Canaries now require exit code zero as well as matching output. Pinned tool
  updates require a fresh discovered checksum and discard obsolete algorithms.
- Deliberately manual tool pins remain visible as unchecked advisories without
  causing `engram update --check` to report a provider failure.

## [3.10.0] - 2026-10-21

### Added

- `refresh-runtimes` workflow (weekly and manual): discovers the latest validated
  Python, Node.js LTS, Git, VS Code and PowerShell, computes SHA-256 for every
  artifact, bootstraps and tests the result, then maintains one pull request.
- Dependabot pip updates for dev and runtime pins (grouped, weekly) in addition
  to GitHub Actions. Runtime pins live in `_sys/defaults/requirements-runtime.txt`
  and apply to fresh provisioning only.
- CI bootstraps the managed Python after the unit suite and requires the real venv
  refresh/regeneration test to run (`ENGRAM_REQUIRE_REAL_VENV=1`).

### Changed

- Shipped defaults refreshed: Python 3.15.0, Node.js 24.22.0 LTS; SHA-256 now
  pinned for all five base runtimes.
- `bootstrap.bat` no longer carries a hardcoded Python fallback and fails closed
  on missing or invalid runtime declarations.
- `engram isolation check` reports a missing optional extension as UNAVAILABLE
  instead of failing.
- Documentation reconciled with current status (CP949 gate policy, audit record,
  maintainer handoff, blueprint).

### Fixed

- Remove the inert `GEMINI_DIR` override and automatic `.engram/agy`
  directory creation. Document Antigravity CLI state in the user profile
  (`~/.gemini/antigravity-cli`) and non-portable login tokens in the OS keyring.

## [3.9.7] - 2026-10-17

### Changed

- `engram update` now notes when the Engram core result came from the discovery
  cache (up to 4 h old) and points to `engram update --refresh`, so a release
  published minutes ago is not mistaken for missing.

### Fixed

- Unit tests can no longer reach the real network: an autouse guard in
  `conftest.py` rejects non-loopback connections (opt out with
  `@pytest.mark.network`). `test_root_write_locations` now pins discovery
  instead of calling live release APIs.

## [3.9.6] - 2026-10-17

### Fixed

- Antivirus false positives on download: `Engram.exe` launcher now embeds
  product/version metadata and an asInvoker manifest (it was a bare unsigned
  6 KB stub that spawns `cmd.exe`, a common heuristic trigger).
- `test_updater` no longer queries the live Node.js index (patched the
  top-level `version_resolver` module), removing a CI flake on new releases.

### Changed

- Bundled defaults refreshed to latest: VS Code 1.142.0, PowerShell 7.6.7,
  SQLite 3.54.1, Git 2.56.0, Claude Code 2.1.302, Codex 0.163.0.

## [3.9.5] - 2026-10-12

### Fixed

- Layout migration defaults-base idempotence (F-05): adopt baseline when
  defaults are adopted so subsequent runs are pure no-ops with no backup,
  rewrite, or summary; suppress rewriting and backing up live declarations
  when unchanged, while changed declarations, stale baselines, and
  downgrades still execute migration.
- Guidance for unrecognized pip leftovers: clarify in doctor and repair that
  Engram will not move unrecognized package directories automatically,
  printing the exact manual recovery steps (stop python/peerhub processes,
  move to <sys>/data/backups/venv/manual/<timestamp>/ instead of deleting,
  and run pip check).

## [3.9.4] - 2026-10-12

### Fixed

- Route clean operation failure exit code 1 through PipelineFailure in
  dispatcher, ensuring Node.js latest/offline failures exit with one message
  and no traceback; preserve ordinary failures for non-usage codes 2-9.
- Preserve `--check` intent when delegating environment updates to the repair
  engine; ensure managed Python preview exits with code 1 for unchecked
  requested components, and offline checks never apply.
- Clarify that `--force` overrides minor Python planning readiness checks;
  staged restore failures and dependency-integrity verification still block
  execution.
- Condition Python up-to-date reporting on newer minor availability to prevent
  displaying "up to date" alongside newer-minor warnings.

### Deferred

- Layout migration defaults-base idempotence (F-05) deferred.

## [3.9.3] - 2026-10-12

### Fixed

- Preflight complete minor restores, including editable build/runtime dependencies;
  restore editables with dependency resolution and build isolation.
- Block rebuilt venv commits on failed pip check and roll back Python and venv.
- Exclude pip ~ metadata from snapshots and conservatively quarantine proven
  duplicates before patch and minor swaps, with journaled resume and undo.
- Report committed pin/manifest write failures with exit 1 and exact resume
  recovery guidance; retain pending writes and backups.

### Changed

- Preserve patch packages and offline capability; ambiguous pip remnants stay
  with warnings.

## [3.9.2] - 2026-10-12

### Fixed

- Advertise Python minor updates only after archive and baseline dependency
  readiness is verified; reuse readiness for execution preflight.
- Report blocked and unverifiable targets without executable update advice.
- Print one dispatcher failure and preserve preflight refusal exit 11.
- Suppress empty layout maintenance output and state writes.
- Remove unsupported package update advice, fix change-count prompts, and fail
  update checks when requested components remain unchecked.

### Changed

- Share baseline package declarations and use managed pip for target resolution.
- Use the selected changelog section for GitHub and WinGet release notes.
- Retain CI contract reports on success and failure; document the strict
  single-pass CP949 gate.

## [3.9.1]

### Added

- Make bare `engram update` a single point of contact for core, tools and
  managed Python advice (#38).

### Changed

- Publish version 3.9.1 and its WinGet manifests (#39, #40).

## [3.9.0]

### Added

- Make managed Python updates discover newer patches and guard minor jumps (#34).
- Add `--latest` and the `-y` / `-o` update shortcuts (#35).
- Add isolation provider contracts, Windows Sandbox, WSL2 and actionable
  isolation checks (#30-#33).

### Changed

- Publish version 3.9.0 and its WinGet manifests (#36, #37).

## [3.8.2]

- Detect and conservatively quarantine pip `~` leftovers (#25-#27).

## [3.8.1]

- Require attestation only from the first attested release (#23, #24).

## [3.8.0]

- Add provenance and upgrade gates; prune legacy migration (#11, #17-#21).

## Before 3.8.0

Releases 1.0.0 to 3.7.0 predate this file; their notes are the GitHub release
notes and tags. Known gaps there: 3.2.7 has no checked-in release
manifest, and 3.6.0 was published without assets (superseded by 3.6.1).
