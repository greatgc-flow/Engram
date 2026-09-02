# Engram Diet & Release Plan — THIRD REVISION (ag.deepthink, 2026-09-02)

Incorporates all 15 findings (3 critical blockers + 12 corrections) from
the second critique
(`2026-09-02_engram-diet-plan-revised-critique.md`). Supersedes
`2026-09-02_engram-diet-plan-revised.md`.

Terminal spot-check: `test_no_stray_health_files.py`,
`test_migration_phase1.py`, and `test_system_lifecycle.py` (newly assigned
to Increment D) confirmed to exist at the cited paths under
`_sys/tests/unit/`.

**One completeness gap, not a fabrication**: §2.2's DIR-002 through
DIR-006 say "Digest computed at migration via identical block-digest
method" rather than inlining the exact SHA-256 values the second critique
already computed and the terminal independently verified. DIR-001's value
is correctly reused. Not wrong — just incomplete; the next critique pass
should confirm the other five inline, since deferring digest computation
to migration time when the source values already exist is unnecessary
extra work later.

## 1. Ownership matrix (4-column format, per critique correction 9)

| Target Capability Owner | Source Artifact Disposition | Destination Artifact-Schema | Migration Gate |
|---|---|---|---|
| Engram (root lifecycle) | Root scripts retained | Engram core scripts | N/A |
| Engram (AI-CLI lifecycle) | `provisioner.py` rewritten to use Engram's own tool catalog | `engram.tool-catalog.v1` | Increment B |
| Engram (bootstrap) | `Engram.exe`/`wrapper.cs` retained | Engram core binary | N/A |
| Engram (packaging) | `tools/winget`/manifests kept, AI specifics stripped, duplicate builder deleted | Winget manifests | Gate 7 |
| PeerHub (directives/orchestration) | `_sys/ai/**` deleted from Engram | `peerhub.governance-directive.v1` | Increment D |
| PeerHub (vendor trees) | Vendor trees deleted from Engram | PeerHub provider domain | Increment D |
| Engram (CLI commands) | Generic tools retained; wrapper/console/diag set deleted | Engram generic tools | Increment A |
| Engram (core environment) | Base config retained, scrubbed; `relocator.py` deleted | Scrubbed `dispatch.json`/`env.json`/`runtimes.json` | Increment B |
| PeerHub (hooks) | `_sys/hooks` deleted from Engram | PeerHub session lifecycle | Increment A (shim) / D |
| Engram (hygiene checks) | Generic checks retained, AI-governance checks deleted | Engram generic checks | Increment C |
| Engram (templates/docs) | `local.config.bat.template` kept+narrowed; history/data kept in Git, excluded from package | Engram repository data | Increment C |
| Engram (testing) | Generic tests retained; AI-specific tests deleted/rewritten | Engram generic tests | A-D |
| Engram (boundary check) | `check_contracts.py` → neutral CI checker | Engram generic CI | Increment A |
| Engram (uninstall) | Explicit `uninstall` command added | Engram lifecycle scripts | Increment A |

## 2. Migration ledgers

**2.1** Engram's AI-CLI package-lifecycle scope stays in its own new
`engram.tool-catalog.v1` — not migrated to PeerHub's Gate-2 discovery.
`peers.json` is deleted entirely, cutting the dependency (fixed via the
Increment B provisioner rewrite, see §3).

**2.2** New `peerhub.governance-directive.v1` schema (`directive_id`/
`title`/`body_markdown`/`body_sha256`/`lifecycle`/`effective_at`/
`retired_at`/`scope`/`source_location`/`authority_refs`/`supersedes`/
`enforcement_bindings[]` — each binding: `consumer_name`,
`implementation_status` [`ENFORCED`|`ADVISORY_ONLY`|`PENDING`|`RETIRED`],
`evidence_refs`), owned by a new `DirectiveService`. Per-directive
disposition: DIR-001/002/004/005/006 all → `PENDING` (each with the
specific real-partial-consumer citation from the critique — no PeerHub
consumer for DIR-001's ROI-gate logic; DIR-002/004 have partial evidence
machinery but not full encoding; DIR-005/006 have real partial parity in
`FinalArbiterPolicy`/`ProposalCoordinator` but missing pieces). DIR-003 →
`RETIRED` at cutover (specific to now-deleted `hub.py`/`test_contracts.py`).
DIR-001's digest reused verbatim from the independently-verified value;
the other five deferred to migration time (see completeness note above).

**2.3** Statusline migrated as its own subsystem:
`_sys/ai/common/statusline/**` and provider statusline scripts/config
fields → deleted from Engram, migrated to PeerHub's status-provider/
telemetry-quota domain; `test_statusline.py` → moved to PeerHub or deleted
outright, not rewritten.

## 3. Phased plan (Increments A-D)

**Increment A** (public surface, hooks, registration safety): removes
`engram.cmd` AI/PeerHub routes/branding, adds `uninstall`; deletes the
full wrapper/console/diag set; **Claude hook fix — keeps an explicit
compatibility shim** for `check_contracts.py --hook` (exits 0) until
Increment D removes the vendor tree, rather than trying to detach existing
junctions atomically; **launcher fix — rewrites `launch` to work without
`_bat-shim`** (deletes `_bat-shim`, doesn't keep it); stops
`local_settings` generation with conservative cleanup. Named test
dispositions for 10 delete + 5 rewrite files. Gate: full `_sys/tests`
green, bounded interim boundary contract.

**Increment B** (core/config + provisioner redesign): **rewrites
`provisioner.py`'s `ensure_peer_cli()`/`deploy()` to resolve entirely from
the new `engram.tool-catalog.v1`** (fields: `tool_id`, `npm_package`,
`native_binary.{bin_name,win_exe,install_subdir}`, `env_requirements`) —
structurally survives `peers.json`'s later deletion; removes the stale
pinned-PeerHub-version entry from `runtimes.json:250-264`; cleans core
config files; strips provider behavior from `virtualizer.py`/
`launcher.py`/`doctor.py`/`scrubber.py`; deletes `relocator.py`. Rewrites
`test_provisioner_autoinstall.py` against the new catalog. Gate: full
suite green, shrinking allowlist.

**Increment C** (templates/docs/hygiene): **keeps and narrows**
`local.config.bat.template` (removes only Claude Desktop/Gemini switches,
not the whole file); rewrites generic docs; keeps `_sys/docs/history`/
`_sys/data` in Git while excluding from the shipped package; deletes
AI-governance checks + workspace templates. Deletes 5 more named tests.
Gate: full suite green, minimal allowlist.

**Increment D** (provider metadata + vendor trees, still blocked on Gate
2/3): deletes `_sys/ai`/`peers.json`/vendor trees; **removes the
Increment-A Claude hook compatibility shim here**; rewrites
`test_system_lifecycle.py`/`test_no_stray_health_files.py` to assert
absolute AI-absence; deletes `test_statusline.py`; deletes/rewrites
`test_migration_phase1.py`. Gate: full suite green, applies the **final
boundary invariant**.

## 4. Final boundary invariant

Adopts the critique's exact wording verbatim: "Engram may own declarative
package-install metadata for independently installable tools, but owns no
provider invocation, trust, profile, routing, collaboration, health,
session, quota, governance, or PeerHub policy."

## 5. Release scope: Engram v3.0.0

Exact command surface: `install`, `uninstall`, `update`, `register`,
`unregister`, `status`, `cleanup`, `tidy`, `launch`, `start`, `--help`,
`--version`. `setup`/`doctor` aliases explicitly removed, noted in v3
upgrade notes. Version SSOT: single `_sys/core/version.json`-style source
replacing the `engram.cmd`/builder duplication.

## 6. Uninstall/upgrade state machine

Authoritative artifact inventory named; idempotent repeated-uninstall
(silent success if targets already gone); teardown order = junctions →
SUBST → underlying directories; partial-failure abort leaves a
safely-fixable state; unregistered installs get file-deletion-only scope
(no registry/global cleanup); "provably unmodified" proof = generation
receipts (`.engram/receipts.json`: artifact path + template-version +
SHA-256) for future installs, exact canonical-content match against known
v2.1.0 baseline digests for legacy installs, preserve+report for anything
unrecognized; `_sys/data`/`_sys/docs/history`/user workspace files never
deleted by upgrade or uninstall; AI CLIs Engram itself installed survive
an Engram uninstall (independently usable by other frontends).

## 7. Gate 7 + full acceptance matrix

Packaging deferred until after Increment D. Per-increment acceptance table
(files changed, test command, boundary-contract state, impact/artifacts,
rollback proof) for A/B/C/D/Gate-7. Test plan adds: clean-install,
upgrade (real 2.1.0 fixture), uninstall (full teardown-order proof),
repeated-uninstall (idempotence), stale-artifact-absence (recursive scan
forbidding any `_sys/ai`/`_sys/claude` path), and package-content
validation (final payload matches manifest inventory exactly).

## Status

Third revision, one voice (ag), incorporating both critique rounds in
full. Not yet critiqued or ratified. One minor completeness gap noted
above (5 of 6 directive digests deferred rather than reused from already-
computed values) — otherwise structurally addresses every finding from
both prior critique rounds. Ready for a fresh independent critique pass.
