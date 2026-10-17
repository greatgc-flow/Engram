# Changelog

All notable changes to Engram are documented here.
The format follows Keep a Changelog. Versions follow Semantic Versioning.
Historical entries are reconstructed from git commits and merged PR titles.

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
