# Engram Diet & Release Plan — REVISED (ag.deepthink, 2026-09-02)

Revision incorporating all 12 corrections from
`2026-09-02_engram-diet-plan-critique.md`. Supersedes
`2026-09-02_engram-diet-release-plan.md`.

**TERMINAL VERIFICATION NOTE (read before trusting §2.3):** section 2.3's
DIR-001 through DIR-006 entries are real — independently checked against
`P:\_sys\ai\user-directives.md` (85 lines, read in full) and every
directive's title/content matches exactly. **However, two fields in that
same section are not real**: `Digest [computed_hash]` is a literal
placeholder string, not an actual computed digest, for every entry; and
the destination `Schema: PeerHubGovernanceRule` **does not exist anywhere
in peerhub's real source** (`grep -rn "PeerHubGovernanceRule"
P:\workspace\peerhub --include="*.py"` returns zero hits) — ag invented
this type name rather than citing a real one. This matches a previously
documented ag fabrication pattern (plausible-looking entities/placeholders
presented as if real). **Section 2.3 needs a real pass**: find or design
an actual destination schema in peerhub's existing governance domain
(`peerhub/governance/lessons.py` is the real, existing lesson-lifecycle
code — check what it can actually represent) before this ledger is usable,
and drop the fake digest field or replace it with a real one (e.g. an
actual sha256 of the directive's text).

---

## 1. Ownership matrix

| Category / Path | Owner | Resolution |
|---|---|---|
| Root lifecycle scripts (`INSTALL.bat`, `UPDATE.bat`, `STATUS.bat`, `CLEANUP.bat`, `TIDY.bat`, `engram.cmd`, `register.bat`, `unregister.bat`) | **Engram** | Essential to the portable workspace; prune AI runtimes/PeerHub routing. Retains provider-neutral `launch`/`start` commands. |
| AI-CLI lifecycle | **Engram** | Retains optional AI-CLI install/uninstall/update/status-check as ordinary tool-catalog entries — matches the master plan's own stated scope, corrects the original plan's drift from it. |
| `Engram.exe` / `wrapper.cs` | **Engram** | Keep (core bootstrap). |
| `tools/winget` & `manifests` | **Engram** | Deferred to Gate 7. Canonical builder kept, AI-specific inclusions stripped, duplicate `build_winget_package.py` deleted. |
| `_sys/ai` (all config/orchestration/directives) | **PeerHub** | Every file deletes from Engram. |
| Vendor trees (`_sys/antigravity`, `_sys/claude`, `_sys/codex`) | **PeerHub** | Vendor config/trust/launchers delete entirely. |
| `_sys/cli` | **Engram** | Retained only for `manage.py`, `cleanup.py`, generic shell launchers; extensionless `agy`/`claude`/`codex`, `*_entry.py`, `_bat-shim`, `diag`/`diag.bat`, `console_runner.py`, `peerhub.bat` deleted. |
| `_sys/core` | **Engram** | Generic dispatch/env-load/virtualization stays; `relocator.py` deleted, `version_resolver.py`'s `.ai` cache stripped. |
| Core config files (`runtimes.json`, `env.json`, `dispatch.json`, `config/environment.json`) | **Engram** | Base config stays, scrubbed of AI paths/vars/PeerHub bindings. |
| `_sys/hooks` (all, incl. `.bat` companions) | **PeerHub** | AI session/context lifecycle mechanisms — deleted from Engram. |
| `_sys/checks` | **Engram** | Reduced to generic env/portability hygiene; AI-governance checks (gap-analysis §3.9) deleted. |
| Docs, data, templates | **Engram** | Generic templates retained; `_sys/local.config.bat.template` deleted; `_sys/docs/history` + `_sys/data` kept in Git for repository provenance but excluded from the shipped package. |
| `_sys/tests` | **Engram** | Generic testing retained; AI-specific tests deleted/rewritten per increment (see §3). |
| `check_contracts.py` | **Engram** | Claude-hook (`PreToolUse`) integration deleted, replaced by an ordinary CI boundary checker under a neutral name. |
| Uninstall frontend | **Engram** | Explicit `uninstall` command added — `unregister` alone is not uninstall. |

## 2. Migration ledger

### 2.1 Aggregate AI-CLI discovery / live installation observations
Already in PeerHub: named-target resolution + readiness probing. Engram's
own AI-CLI package-lifecycle scope (`npm_package`/`native_binary` identity)
stays in Engram's own tool-catalog data — NOT migrated to PeerHub's Gate-2
discovery, which stays strictly detection-only regardless of install
method.

### 2.2 Required declarative fields from `peers.json`
Migrate: `node_ids` (→ `peer_kind`), `env_vars` (→ `env_policy`). Do not
migrate: `npm_package`, `native_binary.{bin_name,win_exe,install_subdir}`
(these stay in Engram's own catalog per 2.1). `local_settings`: **delete/
waive**, not migrated — Claude project trust state
(`virtualizer.py:242-255`), PeerHub must never touch a user's Claude
permission files.

### 2.3 Lessons/directives/statusline migration ledger — SEE TERMINAL NOTE ABOVE
DIR-001 through DIR-006 (real, verified against `user-directives.md`)
proposed for migration into PeerHub's governance domain via injection at
`peerhub lesson activate`, fixing `lesson_inject.py:110-115`'s stale
Engram path reference. **The destination schema and digest values in this
section are not real — see the terminal verification note at the top of
this document before treating this ledger as usable.**

## 3. Phased deletion + release plan

**Increment A** (public surface + registration safety, atomic): remove
`engram.cmd` AI/PeerHub routes/help/branding; delete the full wrapper/
console/diag/hook set (extensionless `agy`/`claude`/`codex`, `*_entry.py`,
`_bat-shim`, `diag`/`diag.bat`, hook `.bat` companions); stop
`local_settings` generation (conservative cleanup of existing generated
files — remove only if provably Engram-generated, else flag); cut the
registration pipeline's `peers.json` dependency; replace
`check_contracts.py`. Named test dispositions:
`test_peer_console_c8a.py`/`c8b.py`/`l2_policy/test_peer_console_routing.py`/
`test_ctx_c9.py`/`test_workspace_template.py`/`test_permission_matrix.py`/
`test_protocol_consensus.py`/`test_saturation_scan_*`/
`test_check_contracts_gate.py` → delete;
`test_launcher_paths.py`/`test_config.py`/`test_config_scoping.py`/
`test_statusline.py` → rewrite (generic-only). Adds an Increment-A-scoped
boundary contract with a temporary, explicit, shrinking allowlist — not
yet the final zero-AI-ownership contract.

**Increment B** (core/config cleanup): strip provider behavior from
`virtualizer.py`/`launcher.py`/`doctor.py`/`scrubber.py`; clean
`dispatch.json`/`env.json`/`runtimes.json`/`config/environment.json`;
remove `.ai` config loading; delete `relocator.py`; strip
`version_resolver.py`'s `.ai` cache. Allowlist shrinks further.

**Increment C** (checks/templates/docs/dead tests): delete AI-governance
checks (gap-analysis §3.9), AI workspace templates,
`local.config.bat.template`, and corresponding tests; rewrite generic
docs; explicitly keep `_sys/docs/history`/`_sys/data` in Git while
excluding from the shipped package. Allowlist shrinks further.

**Increment D** (provider metadata + vendor trees, **still blocked on Gate
2/3**): delete `_sys/ai` + vendor trees; apply the **final**
zero-AI-ownership contract (no allowlist remains); verify no remaining
provider dependency.

## 4. Gate 7: packaging (deferred, unchanged from critique)
All Winget/manifest/version-output work happens after Increment D, not
during Increment 3 as the original plan mistakenly scheduled. Delete the
duplicate `build_winget_package.py`; strip AI-specific inclusions from the
canonical builder.

## 5. Release scope: Engram v3.0.0
Exclusively a portable-dev-environment lifecycle manager.
`engram.cmd` exposes exactly: `install`, `uninstall`, `update`,
`register`, `unregister`, `status`, `cleanup`, `tidy`, `launch`, `start`
(generic provider-neutral launchers retained, resolving the release-scope/
ownership-matrix inconsistency the critique found) — plus Engram's own
optional AI-CLI install/uninstall/update/status-check catalog entries (not
"users install separately").

**v3.0 requirements beyond the version number**: one version-identity SSOT
(a single `_sys/core/version.json`-style source, replacing the current
duplication across `engram.cmd`/two builders/manifests); an explicit
2.x→3.0 upgrade contract (never recursively delete user-modified files;
obsolete wrappers/vendor trees get conservative cleanup — remove only when
provably Engram-generated and unmodified, else flag for manual review); a
measured upgrade test (real 2.1.0 fixture → upgrade → prove obsolete
surfaces don't survive); an explicit `uninstall` command (Winget +
`unregister` alone is insufficient to safely clean up junctions/portable
state).

## Status

Revision, one voice (ag), incorporating the prior critique. **Not yet
ratified.** Terminal independently verified §2.3's directive content is
real but its schema/digest fields are not (see note at top) — this needs a
real fix, not just another read-through, before the next round. Otherwise
ready for a fresh independent critique pass (cx) focused specifically on:
whether the Increment A-D resequencing actually closes every dependency
gap the first critique found, and a real (not placeholder) version of the
§2.3 ledger.
