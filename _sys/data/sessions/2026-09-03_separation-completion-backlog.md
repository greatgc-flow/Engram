# Engram/peerhub separation — completion status & remaining backlog (2026-09-03)

Written at the point the full ratified v8 diet plan (Increments A-D, Gate
2 design, Gate 7, README rewrites) is complete and both projects have
shipped real releases (Engram v3.0.0, peerhub v0.1.8). This is the single
pointer doc for "what's left" on both sides of the separation.

## Status: separation is real, verified in both directions

- **peerhub → Engram**: an automated, already-passing test
  (`tests/unit/telemetry/test_presenter.py::TestNoHardcodedPaths::
  test_no_hardcoded_drive_letters_in_package_source`) grep-scans the
  entire installable `peerhub/` package for hardcoded `P:`/`D:\Engram`-
  style paths and asserts none exist. The only real path dependency
  anywhere in the peerhub repo is `scripts/migrate_engram_directives_
  2026_09_03.py`, a one-time, already-executed migration script excluded
  from the installable package by construction (not under `peerhub/`) —
  its dev-machine-hardcoded source path is expected and harmless.
- **Engram → peerhub**: manually grepped `_sys/core`, `_sys/cli`,
  `_sys/checks` for "peerhub" — every hit is either a comment explicitly
  confirming the boundary or a generic directory-name allowlist entry
  (`.peerhub` in `check_root_hygiene.py`). Engram treats peerhub purely as
  an optional, arbitrary tool entry in `_sys/runtimes.json`, no different
  from ripgrep or jq.
- Real, end-to-end verified installs: `git+https://github.com/greatgc-
  flow/peerhub.git@v0.1.8` builds a real sdist, installs cleanly, and
  `peerhub adapter discover` genuinely finds installed AI CLIs. Engram's
  `tools/winget/build_package.py` builds a real, `winget validate`-clean
  portable archive (independently re-downloaded from the GitHub Release
  and re-hashed to confirm byte-for-byte integrity against the manifest's
  `InstallerSha256`).

## Engram-side open items

1. **`_sys/docs-v2/**`'s final disposition** — keep as historical
   reference, narrow to what's still Engram-generic, or delete/migrate to
   peerhub. A real, tracked, deliberately-unresolved gap (see
   `2026-09-03_pre-commit-hook-blindspot-and-docsv2-gap.md`) — the whole
   tree predates the separation and describes the old hub.py-integrated
   architecture. Both entry points (`MOC.md`, `00-MANIFEST.md`) now carry
   a factual notice so nobody is misled in the meantime, but the actual
   decision needs a real review round, not a unilateral terminal call.
2. **Winget submission**: [microsoft/winget-pkgs#428737](https://github.com/microsoft/winget-pkgs/pull/428737)
   is open, validated locally (`winget validate` clean), but blocked on:
   - **The `greatgc-flow` account signing Microsoft's CLA** — a personal/
     organizational legal step, cannot be done on your behalf. The CLA
     bot commented on the PR with the signing link
     (https://opensource.microsoft.com/cla/).
   - A real local `winget install --manifest ...` end-to-end test was
     attempted but blocked in this environment (`winget settings --enable
     LocalManifestFiles` requires admin rights not available here) — only
     `winget validate` was completed, disclosed honestly in the PR body.
     Worth doing once from a machine with admin access, though the
     manifest passing `validate` plus the archive's SHA256 being verified
     live is already strong evidence it's correct.
   - Ordinary Microsoft review/merge timing after that, outside anyone's
     control.
3. **Low-priority, confirmed-harmless, not fixed**:
   `_sys/checks/saturation_scan.py`'s `EXCLUDE_DIRS`/`EXCLUDE_FILES` still
   carry dead vendor-cache-exclusion entries (`.tmp`, `.system`, `skills`,
   `plugins`, `marketplaces`, `cache`, `scratch`, `brain`, `.claude.json`)
   for vendor trees that no longer exist. Left alone deliberately: keeping
   an overly-broad-but-inert exclusion is safer than removing it (a
   removed entry could cause future false-positive noise if a
   similarly-named legitimate directory ever appears; a kept-but-unused
   one causes nothing). Revisit only if the comment's accuracy starts
   actually mattering to someone.
4. **`local.config.bat` has no real loading mechanism** (found 2026-09-03
   while reviewing a delegated CONVENTION.md rewrite that confidently
   described a `call "%SYS_DIR%\local.config.bat"` pattern that doesn't
   exist anywhere in the live tree). The template
   (`_sys/local.config.bat.template`) and its 2 real settings
   (`BASE_DIR_WORKSPACE`, `NPM_CONFIG_PREFIX`) are genuine, but no entry
   point (`engram.cmd`, `INSTALL.bat`, any `_sys/core/*.py`) actually
   sources a copied `local.config.bat` -- the template's own internal
   comment referenced a `start.bat` that predates the diet plan and no
   longer exists. This is a real, unimplemented feature gap, not just a
   docs gap -- worth wiring up for real if per-PC overrides are still
   wanted, or removing the template + docs entirely if not.

## peerhub-side open items

peerhub maintains its own much larger, independently-scoped backlog —
**don't duplicate it here**, see
[`docs/design/PEERHUB-BACKLOG-2026-08-27.md`](https://github.com/greatgc-flow/peerhub/blob/main/docs/design/PEERHUB-BACKLOG-2026-08-27.md)
in the peerhub repo for the full, current, organized list. Items directly
relevant to the Engram/peerhub separation specifically (not peerhub's
general roadmap):

1. **Gate 2 Lane 2** (trusted third-party adapter-manifest discovery,
   scanning `%LOCALAPPDATA%\PeerHub\adapters.d`) — deliberately NOT
   implemented. This is a real security trust boundary over untrusted
   input that ultimately gates code execution (an admitted manifest's
   named executable eventually gets spawned); the admission engine it
   would need (ACL evaluation, executable hashing, collision detection,
   atomic registry publication — see `docs/design/
   PHASE1-MANIFEST-SCHEMA-V2-2026-08-20.md`) doesn't exist anywhere in
   the codebase despite the design already being fully specified. Only
   Lane 1 (built-in cc/cx/ag PATH-based discovery, no untrusted input) was
   implemented (peerhub commit `c565386`). Resume once `cx` recovers
   (2026-09-07) for genuine adversarial security review, or on your
   explicit direction to proceed without one — see the Engram worktree's
   `2026-09-03_gate2-lane2-deferred-security-note.md` for full reasoning.
2. **19 permanently-waived `LEGACY_CATALOG` actions** — each individually
   cited as an intentional, settled non-goal (host-environment-only
   tooling, an architecturally-incompatible generic write queue, upstream
   account/billing management peerhub deliberately does not fake, etc.),
   not open work, but worth knowing about if you ever go looking for a
   specific old `hub.py` action and don't find it.

## Release state (for reference)

| | Engram | peerhub |
|---|---|---|
| Latest tag | `v3.0.0` | `v0.1.8` |
| GitHub Release | [v3.0.0](https://github.com/greatgc-flow/Engram/releases/tag/v3.0.0) | [v0.1.8](https://github.com/greatgc-flow/peerhub/releases/tag/v0.1.8) |
| Install (working today) | git clone or release-zip download (see README) | `pip install "git+https://github.com/greatgc-flow/peerhub.git@v0.1.8"` |
| Install (pending) | `winget install greatgc-flow.Engram` — [PR #428737](https://github.com/microsoft/winget-pkgs/pull/428737) open | — |
| Tests | 301 passed, 2 skipped | 1442 passed, 2 skipped |
