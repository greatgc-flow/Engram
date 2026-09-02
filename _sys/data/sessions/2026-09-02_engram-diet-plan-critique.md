# Engram Diet & Release Plan — independent critique (cx.deepthink, 2026-09-02)

**Verdict: DO NOT RATIFY. Needs a full revised design round.**

Three of the most decisive citations independently spot-verified by the
terminal — all confirmed accurate: `engram.cmd` really does route
`diag`/`peerhub`/`launch`/`start`/`agy`/`claude`/`codex` directly to the
exact wrapper files Increment 1 deletes (`engram.cmd:41-47`, `:90-113`);
`virtualizer.py`'s `_apply_local_settings()` really does write Claude's
project `settings.local.json` trust state directly from `peers.json`'s
`local_settings` field (`:242-255`); and the master plan really does state
"install/uninstall/update/status-check" of AI CLIs stays in Engram's scope
(`PHASE2-ENGRAM-SEPARATION-MASTER-PLAN-2026-09-02.md:24`) — which the diet
plan's release scope directly contradicts.

## What's confirmed correct and survives

- The ownership direction (PeerHub owns collaboration/invocation/discovery/
  routing/sessions/health/governance).
- **Engram v3.0.0 is the right version identity** — retain the Engram name,
  major-bump for the breaking behavioral change; a fork/rename would only
  make sense if old and new products needed to coexist, which they don't.

## Two contradictions/errors found

1. **The plan never decided whether Engram retains AI-CLI install/update/
   status.** The user's own master goal explicitly permits this
   ("install/uninstall/update/status-check" stays); the diet plan's release
   scope instead says "users install AI CLIs separately" and Increment 4
   deletes `npm_package`/`native_binary` identity outright. **This is a real
   drift from the stated requirement, not an open question** — the next
   round must restore Engram's optional AI-CLI package-lifecycle scope
   (ordinary tool-catalog entries, not collaboration config) while keeping
   PeerHub's discovery fully independent of how a CLI got installed.
2. **`local_settings` is misclassified in the migration ledger.** It is not
   an adapter invocation setting — it's Engram-generated Claude project
   trust/permission state (verified above). PeerHub's real adapter
   (`peerhub/adapters/claude_adapter.py:195-210`) builds its own
   `InvocationPlan` independently and doesn't need it. **Disposition:
   delete/waive, do not migrate.** PeerHub must never mutate a user's Claude
   permission files during discovery/activation. An opt-in integration
   template (if a user wants Claude to be able to call `peerhub`
   interactively) is a separate, later, explicitly-security-reviewed
   feature — not part of this migration.

## Increment plan: real dependency bugs found, resequenced

Increments 1-3 are individually broken as originally sequenced:

- **Dangling routes**: Increment 1 deletes wrapper targets without editing
  `engram.cmd`'s routes/help/branding that call them — verified, real bug.
- **Local_settings keeps regenerating**: the full chain
  `engram register` → `register.bat` → `dispatch.json`'s `virtual.mount` →
  `virtualizer.mount()` → `_apply_local_settings()` → writes permissions
  for the now-deleted wrapper paths — stays live unless the
  registration-pipeline's `peers.json` dependency is cut in the *same*
  increment as wrapper deletion, not three increments later.
- **The stated `pytest _sys/tests` green check can't actually pass** —
  named ~10 specific test files (`test_peer_console_*`, `test_ctx_c9.py`,
  `test_workspace_template.py`, `test_launcher_paths.py`, `test_config*.py`,
  `test_permission_matrix.py`, `test_protocol_consensus.py`,
  `test_statusline.py`, `test_saturation_scan_*`,
  `test_check_contracts_gate.py`) that directly assert on surfaces the
  increments remove, with none scheduled for deletion/rewrite.
- **A "strict zero-AI-ownership" contract can't land in Increment 1**
  while Increments 2-4 deliberately still have AI trees in place — needs
  staged, increment-specific boundary contracts with an explicit
  shrinking allowlist, finalizing only after the last increment.
- **`check_contracts.py`'s disposition is contradictory** — ownership
  matrix says delete, Increment 1 says rewrite. Resolution: delete the
  Claude-hook integration, replace with an ordinary CI boundary checker
  under a neutral name.

### Revised increment structure proposed

- **Increment A** (public surface + registration safety, atomic): remove
  `engram.cmd` AI/PeerHub routes+branding, delete the full wrapper/console/
  diag/hook set, stop `local_settings` generation, cut the registration
  pipeline's `peers.json` dependency, update every directly-affected test,
  add an Increment-A-scoped boundary contract.
- **Increment B** (core/config cleanup): strip provider behavior from
  `virtualizer.py`/`launcher.py`/`doctor.py`/`scrubber.py`; clean
  `dispatch.json`/`env.json`/`runtimes.json`/`config/environment.json`;
  remove `.ai` config loading; resolve `relocator.py`; relocate
  `version_resolver.py`'s `.ai` cache; update core/config tests.
- **Increment C** (checks/templates/docs/dead tests): remove AI checks +
  launchers, AI workspace templates + tests, rewrite generic docs, decide
  archive-vs-delete for history/session docs.
- **Increment D** (provider metadata + vendor trees, **blocked on Gate 2/3**
  as before): delete `_sys/ai` + vendor trees, apply the final
  zero-AI-ownership contract, verify no remaining provider dependency.

Packaging (Gate 7) stays deferred until the source boundary is final — the
original plan scheduled a partial Winget-builder edit inside Increment 3,
which is premature; the builders contain far more AI surface
(`.ai`/`.codex`/`.peerhub`, AI-facing docs, multi-agent tags/descriptions,
a duplicate builder) than the single `.agy`/`.claude` line originally
scoped.

## v3.0 release requirements beyond the version number

A version bump alone doesn't define a release. Needed: one version-identity
SSOT (currently duplicated across `engram.cmd`, two package builders, and
the manifests); an explicit 2.x→3.0 upgrade contract (what happens to a
user's obsolete wrappers, `_sys/ai`, vendor trees, generated Claude
settings, and their own data — never recursively delete user-modified
files just because old Engram owned the parent directory); a measured
upgrade test (real 2.1.0 fixture → upgrade → prove obsolete surfaces don't
survive); and an explicit uninstall-semantics decision (`unregister` is not
the same as uninstall).

## Fourteen inventory omissions found

The formalized plan dropped several items the original gap-analysis
inventory already named: extensionless `_sys/cli/agy`/`claude`/`codex`,
`*_entry.py` files, `_bat-shim`, `diag`/`diag.bat`, hook `.bat` companions,
the AI checks from gap-analysis §3.9, AI-specific tests, `_sys/config/
environment.json`, `_sys/local.config.bat.template`, `relocator.py`,
`version_resolver.py`'s `.ai` cache, the duplicate Winget builder, an
actual uninstall front end (not yet decided), and `Engram.exe`/`wrapper.cs`
(correctly kept but never explicitly listed in the matrix).

## Release-scope inconsistencies

- **Generic launcher scope undecided**: the ownership matrix keeps generic
  shell/editor launching, but the release-scope command list omits
  `launch`/`start` entirely. Recommendation: keep a provider-neutral
  launch command — legitimately useful portable-environment functionality,
  not AI-specific.
- **Packaging scheduled too early** (Increment 3) — should be Gate 7, after
  the code boundary is final.
- **Repository provenance vs. shipped content vs. runtime state** need to
  be distinguished — the gap-analysis allowed keeping research/session
  history in Git while excluding it from the shipped runtime package; the
  diet plan sometimes said delete outright. Deleting design evidence from
  Git is not required to make the shipped package lean.

## Twelve corrections required for the next round

1. Redraw increments around real dependency edges, not directory
   categories.
2. Move `engram.cmd`, registration/local-settings cleanup, and affected
   tests into the same atomic slice as wrapper deletion.
3. Define staged boundary contracts + the final post-Increment-D contract.
4. Enumerate every wrapper/hook-companion/check/test/config/core file from
   the original inventory (the 14 omissions above).
5. Remove `local_settings` from the migration ledger.
6. Decide (per the master plan's own existing answer): Engram retains
   optional AI package lifecycle operations.
7. Produce an exact lessons/directives/statusline migration ledger (not
   just "can be injected").
8. Resolve generic launcher scope.
9. Add uninstall + 2.x→3.0 upgrade semantics.
10. Defer all packaging/manifest/version-output work to Gate 7.
11. Centralize version identity; retain `greatgc-flow.Engram` as v3.0.0.
12. Add measured clean-install/upgrade/uninstall/stale-file-absence
    validation to the test plan.

## Durable conclusions (survive into the next round unchanged)

- Engram stays Engram, releases as **v3.0.0**.
- PeerHub owns collaboration/invocation/discovery/routing/sessions/health/
  governance.
- Claude `local_settings` permission injection is **deleted, not
  migrated**.
- Increments A-C (the resequenced 1-3) can start before PeerHub Gate 2
  implementation lands — but only once resequenced into internally
  consistent, independently testable units as described above.
