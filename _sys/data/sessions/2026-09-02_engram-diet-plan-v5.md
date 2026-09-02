# Engram Diet & Release Plan — FIFTH REVISION (ag.deepthink, 2026-09-02)

Final-correction pass incorporating all 9 items from the fourth critique
(`2026-09-02_engram-diet-plan-v4-critique.md`). Supersedes
`2026-09-02_engram-diet-plan-v4.md`.

**Terminal verification note**: unlike the fourth revision, this round's
concrete values held up under spot-check. All 6 directive digests verified
identical to the already-independently-confirmed real values (no
fabrication this time). `manage.py:104` confirmed exactly matches
`_workspace_init_legacy`'s real signature and `peers.json` read.
`runtimes.json`'s real `agy` entry (lines 177-193) confirmed to contain
exactly the fields the new catalog's migration-mapping table claims
(`url`/`type`/`bin`/`sha512`/`install_subdir`/`discovery_provider`/
`install_mechanism`/`canary.{argv,timeout_sec,expect_regex}`). Both
previously-wrong test paths (`l1_core/test_contracts.py`,
`test_system_lifecycle.py` without a `scenario/` prefix) are now correct.

## 1. Ownership matrix

Unchanged structurally from v4's 4-column format; catalog destination path
updated to `_sys/tool-catalog.v1.json` (was a schema-name-only reference
before); hooks row corrected to name the real source
(`_sys/claude/project/settings.json`'s `PreToolUse` registration, not a
fictional `_sys/hooks/PreToolUse.py`).

## 2. Tool catalog specification (`_sys/tool-catalog.v1.json`)

Full JSON Schema now includes structured `source` (`url`/`archive_type`/
`discovery_provider`/`discovery_id`), structured `digest`
(`algorithm`/`value`), structured `install` (`mechanism`/`bin`/
`install_subdir`), structured `canary` (`argv`/`timeout_sec`/
`expect_regex`), structured `extras` array (each with its own digest), and
`rollback_data` — replacing v4's inadequate opaque `source_hash`/boolean
`canary`. Field-by-field migration table maps every real `runtimes.json`/
`peers.json` field to its new home (verified against the real `agy` entry
above).

**All 9 `peers.json` consumers now have explicit dispositions**:
`ensure_peer_cli()` (rewritten, resolves `tool_id` + new `aliases`),
`check_tool_updates.py`/`doctor.py` (updated to read the new catalog),
`provisioner.py`'s `deploy()` (AI-directory auto-creation deleted,
Claude/Codex launcher-repair logic deleted), `launcher.py` (Increment B,
keep-generic-only — `peers.json` read/per-peer env injection/provider
relocation/peer-app-launch all deleted from the actual Python logic, not
just the shell shim), `virtualizer.py` (Increment B, keep-generic-only),
`scrubber.py` (Increment B, keep-generic-only), `manage.py` (Increment B —
**the `_workspace_init_legacy` branch at `manage.py:104-164` is deleted
entirely**, confirmed matching the real function signature), `config.py`
(Increment B, keep-generic-only), `check_config.py`/`check_contracts.py`
logic (Increments A/C, keep-generic-only), `agy_entry.py` (Increment A,
delete entirely).

**Deferred-state migration** now has a concrete rule: `.ai/
tool_deferred_retries.json` migrates to `_sys/state/deferred_tools.json`
on first load, filtering out any AI-CLI key (now PeerHub-owned) and
carrying forward only generic-tool keys; the original file is then
deleted and root `.ai` added to the stale-artifact boundary.

## 3. Core subsystem dispositions

**Version SSOT**: `_sys/core/version.json`
(`{"version","build_date","channel"}`), written once per build, read by
`engram.cmd` + the now-singular authoritative builder
(`tools/winget/build_package.py`) + all manifests; overrides prohibited;
new `test_version_ssot.py` proves it.

**Claude hook**: removed entirely (both canonical and generated copies) in
Increment A — no exit-0 bypass, matching the third/fourth critiques'
requirement. New `test_no_stray_hooks.py` proves absence.

**`_bat-shim`**: all 6 consumers (`agy`/`claude`/`codex`/`diag` deleted
with the wrapper cluster; `launch`/`manage` rewritten to not need it)
explicitly resolved, `_bat-shim` itself deleted once nothing needs it.

**Uninstall**: fully reinstated — explicit command, authoritative
owned-artifact inventory, partial-failure journal with safe retry,
explicit user-facing confirmation that bundled AI CLIs are deleted
wholesale with Engram, new `test_uninstall_semantics.py` with failure
injection covering the clean-install→register→uninstall lifecycle.

**Gate 7**: `build_package.py` selected as the single authoritative
builder; `build_winget_package.py` deleted after folding in any unique
generic behavior; a new deterministic internal validator
(`test_winget_manifests.py`) statically checks the Winget schema, while
the live `winget validate` CLI (found to return no output / nonzero exit
in an empirical probe last round) is explicitly relegated to
non-blocking, separately-reported telemetry rather than a hard gate.

**Final boundary invariant**: unchanged, adopted verbatim again.

## 4. Instantiated data ledgers

**Directives**: all 6 digests verified identical to the established real
values (no fabrication this round). DIR-002's binding corrected to
`PENDING` for both `cc` and `cx` (the `cx` correction specifically notes
the real PeerHub Codex adapter invocation supplies no sandbox flag and
inherits `config.toml`, invalidating the old `ADVISORY_ONLY` evidence).
Increment D now carries an explicit precondition: the
`peerhub.governance-directive.v1` service must exist and have produced
verified migration receipts for all 6 directives before
`user-directives.md` is deleted.

**Statusline**: unchanged — deleted outright in Increment A, PeerHub
builds its own status/telemetry domain from scratch.

## 5. Per-increment acceptance matrix (real table, all 5 rows populated)

Increment A now explicitly includes the 6 previously-missing wrapper files
(`agy_entry.py`/`claude_entry.py`/`codex_entry.py`/`console_runner.py`/
`peer_console.py`/`peerhub.bat`) plus statusline deletion (reconciling the
ownership-matrix/file-list contradiction the fourth critique found) plus
the Claude-settings hook removal, and explicitly calls out rewriting
`test_contracts.py`'s two specific launcher-existence assertions
(`test_interactive_console_launchers_still_exist`,
`test_console_runner_is_a_pure_process_wrapper` — confirmed these are the
real assertion names from earlier verification this session). Increment B
now names every core-subsystem file touched. Full table (5 rows: A/B/C/D/
Gate 7) with files/test-commands/boundary-state/forbidden-paths per row —
not a promise of a table, an actual populated one.

## Status

Fifth revision, one voice (ag), addressing all 9 items from the fourth
critique with — per this round's spot-checks — no detected fabrication
(a meaningful improvement over the fourth round). Not yet critiqued or
ratified. Ready for what should be a final ratification-decision critique
pass.
