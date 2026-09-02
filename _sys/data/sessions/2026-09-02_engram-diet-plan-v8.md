# Engram Diet & Release Plan — EIGHTH REVISION (ag.deepthink, 2026-09-03)

Final-correction pass incorporating the 5 bounded mechanical fixes from
the seventh critique
(`2026-09-02_engram-diet-plan-v7-critique.md`). Architecture, catalog,
DIR-002, Gate 7, deferred-state, and the hooks-tree disposition are
unchanged from v7 and carried forward verbatim. Supersedes
`2026-09-02_engram-diet-plan-v7.md`.

**Terminal verification note**: spot-checked citations confirmed exact —
all 4 named test functions
(`test_registration_flow_sys_r1_r2:68`,
`test_mount_reports_failed_when_subst_assignment_is_missing:96`,
`test_dual_instance_different_subst_drives:256`,
`test_cleanup_tier3_resets_runtime:291`) exist at their claimed lines;
`virtualizer.mount()`'s real signature/docstring
("Assign SUBST drive and create peer junctions") confirms it currently
does both AI-peer and SUBST logic together; `scrubber.py:354-360`'s real
`.ai` governance-deletion block confirmed exact.

**⚠️ Notable scope decision applied this round, flag for explicit
sign-off**: this revision fully removes SUBST-drive virtualization from
`virtualizer.py` (deletes `_assign_subst`/`_release_subst` entirely),
applying the session's earlier, separately-ratified SUBST-reconciliation
decision (`2026-09-02_subst-reconciliation.md` — replace SUBST with
venv-style `activate.bat`/`.ps1` + `ENGRAM_ROOT`). This was requested
explicitly in this round's dispatch (asked ag to check that prior decision
and not contradict it), so it's not scope creep, but it's a bigger
consequence than the other 4 narrow fixes: 5 SUBST-specific lifecycle
tests are deleted outright (including
`test_dual_instance_different_subst_drives`, which the seventh critique
had cited as evidence for a *retained* multi-instance requirement — that
requirement is now met differently, via per-session `ENGRAM_ROOT`
activation rather than distinct SUBST drive letters, so no contradiction,
but this reasoning chain should be explicitly checked in the final
critique rather than assumed correct.

---

## 1. Ownership matrix

| Target Capability Owner | Source Artifact Disposition | Destination Artifact-Schema | Migration Gate |
|---|---|---|---|
| Engram (root lifecycle) | Root scripts retained | Engram core scripts | N/A |
| Engram (AI-CLI lifecycle) | `provisioner.py` rewritten, `peers.json` deleted | `_sys/tool-catalog.v1.json` | Increment B |
| Engram (bootstrap) | `Engram.exe`/`wrapper.cs` retained | Engram core binary | N/A |
| Engram (packaging) | `tools/winget/build_package.py` retained | Winget manifests | Gate 7 |
| PeerHub (directives) | `_sys/ai/user-directives.md` deleted | `peerhub.governance-directive.v1` | Increment D |
| PeerHub (statusline) | `_sys/ai/common/statusline/**` deleted | DELETED OUTRIGHT (see §4.2) | Increment A |
| PeerHub (vendor trees) | Vendor trees deleted from Engram | PeerHub provider domain | Increment D |
| PeerHub (hooks tree) | `_sys/hooks/**` (9 files) deleted | DELETED OUTRIGHT (see §3.8) | Increment A |
| Engram (CLI commands) | Generic tools retained | Engram generic tools | Increment A |
| Engram (core config) | Base config retained, scrubbed | Scrubbed `env.json`/`dispatch.json` | Increment B |
| PeerHub (hooks) | `PreToolUse` hook registration in `settings.json` deleted | DELETED (replaced by CI gate) | Increment A |
| Engram (hygiene checks) | Generic checks retained, AI checks deleted | Engram generic checks | Increment C |
| Engram (templates) | `local.config.bat.template` kept+narrowed | Engram repository data | Increment C |
| Engram (testing) | Generic tests retained, AI tests deleted | Engram generic tests | A-D |
| Engram (boundary) | `check_contracts.py` deleted | Engram generic CI | Increment A |
| Engram (uninstall) | Explicit `uninstall` command added | Engram lifecycle scripts | Increment A |

## 2. Tool catalog specification (`_sys/tool-catalog.v1.json`)

(Unchanged from v7 — schema, migration mapping, and digests carried
forward verbatim.)

### Schema (JSON Schema)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "tools": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "tool_id": { "type": "string" },
          "enabled": { "type": "boolean" },
          "aliases": { "type": "array", "items": { "type": "string" } },
          "version": { "type": "string" },
          "source": {
            "type": "object",
            "properties": {
              "url": { "type": "string" },
              "archive_type": { "type": "string" },
              "discovery_provider": { "type": "string" },
              "discovery_id": { "type": "string" }
            },
            "required": ["url"]
          },
          "digest": {
            "type": "object",
            "properties": {
              "algorithm": { "type": "string" },
              "value": { "type": "string" }
            }
          },
          "install": {
            "type": "object",
            "properties": {
              "mechanism": { "type": "string" },
              "bin": { "type": "string" },
              "install_subdir": { "type": "string" }
            },
            "required": ["mechanism"]
          },
          "canary": {
            "type": "object",
            "properties": {
              "argv": { "type": "array", "items": { "type": "string" } },
              "timeout_sec": { "type": "integer" },
              "expect_regex": { "type": "string" }
            },
            "required": ["argv"]
          },
          "extras": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "url": { "type": "string" },
                "type": { "type": "string" },
                "dest": { "type": "string" },
                "digest": {
                  "type": "object",
                  "properties": {
                    "algorithm": { "type": "string" },
                    "value": { "type": "string" }
                  }
                }
              }
            }
          },
          "rollback_data": { "type": "string" }
        },
        "required": ["tool_id", "enabled", "version", "source", "install"]
      }
    }
  },
  "required": ["tools"]
}
```

### Migration mapping
| Old Source | Old Field | New Field in `tool-catalog.v1` | Notes |
|---|---|---|---|
| `runtimes.json` | `[tool_key]` | `tool_id` | Top-level identifier |
| `peers.json` | `enabled` | `enabled` | Boolean flag |
| `peers.json` | `node_ids` | `aliases` | E.g., `["claude", "cc"]` |
| `runtimes.json` | `version` | `version` | E.g., `"2.1.215"` |
| `runtimes.json` | `url` | `source.url` | Download location |
| `runtimes.json` | `type` | `source.archive_type` | E.g., `"exe"`, `"pip"`, `"npm_peer"` |
| `runtimes.json` | `discovery_provider` | `source.discovery_provider` | E.g., `"npm"`, `"github_releases"` |
| `runtimes.json` | `discovery_id` | `source.discovery_id` | E.g., `"@anthropic-ai/claude-code"` |
| `runtimes.json` | `sha512` / `sha256` | `digest.algorithm` / `digest.value` | Explicit hash structure |
| `runtimes.json` | `install_mechanism` | `install.mechanism` | E.g., `"exe_tool"`, `"npm_peer"` |
| `runtimes.json` | `bin` | `install.bin` | E.g., `"agy.exe"` |
| `runtimes.json` | `install_subdir` | `install.install_subdir` | E.g., `"tools/agy"` |
| `runtimes.json` | `canary.argv` | `canary.argv` | List of string arguments |
| `runtimes.json` | `canary.timeout_sec` | `canary.timeout_sec` | Integer |
| `runtimes.json` | `canary.expect_regex` | `canary.expect_regex` | Regex string |
| `runtimes.json` | `extras` | `extras` | Structured array of extra downloads with digests |
| `(new)` | `(new)` | `rollback_data` | Rollback metadata tracking |

### Consumer dispositions
- `ensure_peer_cli()`: rewritten to resolve top-level `tool_id` AND the new `aliases` array (replacing `node_ids`).
- `check_tool_updates.py` / `doctor.py`: updated to read the new catalog. The tool-metadata subset of `runtimes.json` is deleted.
- `_sys/core/provisioner.py`: The `deploy()` logic that unconditionally creates `_sys/ai/common/{agents,skills,mcp}` is **DELETED**. Claude/Codex-specific launcher-repair logic inside `provisioner.py` is **DELETED**.
- `_sys/core/launcher.py`: Increment B. Keep-generic-behavior-only. **Delete** `peers.json` read, per-peer env var injection, provider relocation patching, and peer host app launching.
- `_sys/core/virtualizer.py`: Increment B. **Delete** `_load_peers()` (13-20) and the legacy `peers.json` fallback in `_cli_apply` (386-400). **Rewrite `mount()`/`unmount()` line-by-line** (see §3.9 below — new subsection this round). **Delete `_assign_subst`/`_release_subst` entirely** (per the ratified SUBST-reconciliation decision — see flag at top of document).
- `_sys/core/scrubber.py`: Increment B. **Delete** `_load_peers()` (49-56). **Strip ALL `.ai` governance ownership**: delete `_AI_EPHEMERAL_DIRS`/`_AI_EPHEMERAL_FILES`/`_AI_EPHEMERAL_GLOBS`/`_SESSION_LOCK_STALE_SECONDS` (111-121), delete `_active_sessions_present()` entirely (124-169), delete `_clean_ai_ephemeral()` entirely (195-212); in `_tier1()` delete the `_clean_ai_ephemeral` call (224-226) and per-peer cleanup loop (270-284); in `_tier2()` delete the per-peer `settings.local.json` cleanup loop (307-312); in `_tier3()` delete the per-peer cert/junction cleanup loop (333-347); in `_tier4()` delete the explicit `.ai` tree deletion block (354-359, terminal-verified exact) and per-peer system removal loop (368-374); in `run()` delete the active-session blocking check (434-443). Engram's cleanup becomes fully generic, oblivious to any AI session state.
- `_sys/cli/manage.py`: **Increment A & B.** Keep-generic-behavior-only (`register`, `unregister`, `cleanup`, add `uninstall`). **Delete** the `workspace-init` branch entirely (104-164).
- `_sys/core/config.py`: Increment B. **Delete** BOTH `get_peers_config()` AND `get_orchestration_config()` (159-169).
- `_sys/checks/check_config.py` **and** `_sys/checks/check_contracts.py`: Increment A & C. **DELETE ENTIRELY**, replaced by `_sys/tests/unit/test_boundary_imports.py` — see the algorithm below.
- `_sys/tests/unit/test_config_validator.py` and `_sys/tests/unit/test_check_contracts_gate.py`: **Deleted**.
- `_sys/cli/agy_entry.py`: Increment A. **Delete-entirely**.

**`test_boundary_imports.py` algorithm (fully specified)**: (1) define the
exact forbidden-path list from the ratified deletion inventory (`_sys/ai`,
`_sys/claude`, `_sys/codex`, `_sys/antigravity`, `_sys/hooks`,
`check_config.py`, `check_contracts.py`, `relocator.py`,
`agy_entry.py`/`claude_entry.py`/`codex_entry.py`/`console_runner.py`/
`peer_console.py`); (2) `os.path.exists()`-assert every forbidden
file/directory is absent from disk; (3) `ast.parse()` every remaining
`.py` file under `_sys/`; (4) walk `ast.Import`/`ast.ImportFrom` nodes,
checking resolution against forbidden module paths; (5) handle
constant-string `importlib.import_module("...")` calls via
`ast.Call`/`ast.Constant` inspection, documented as a known limitation for
fully dynamic computed strings.

### Deferred-state migration

(Unchanged from v7 — canonicalize legacy `peer:<name-or-alias>` keys
through the catalog's `aliases`, preserve retry fields, drop only
explicitly-removed products, destination
`_sys/data/state/deferred_tools.json`.)

## 3. Core subsystem dispositions

**3.1–3.4, 3.6–3.8**: unchanged from v7 (version SSOT at
`_sys/core/version.json`; Claude hook removed entirely, no exit-0 bypass;
all 6 `_bat-shim` consumers resolved; command surface + root docs
disposition; Gate 7's `build_package.py`-authoritative resolution; final
boundary invariant; the 9-file hooks-tree deletion).

**3.5 Uninstall — installation-scoped, fully fixed**:
- **Command route**: `engram.cmd:32-47`'s dispatch table gains
  `if /i "%SUBCMD%"=="uninstall" goto :cmd_uninstall`, routing to
  `_sys\cli\manage.py uninstall`.
- **Installation identity**: `<installation-id>` = SHA-256 hash of the
  `base_dir` absolute path, lowercase — deterministic, no dependency on a
  separately-generated artifact.
- **Externalized helper**: the in-tree process performs pre-flight
  validation + registry/junction cleanup, writes the journal through
  `junction_cleanup`, then launches an external helper staged to
  `%TEMP%\EngramUninstall\<installation-id>\<nonce>\EngramUninstallHelper.bat`
  with explicit `base_dir`/`journal_path`/`parent_PID` arguments, and
  exits.
- **Journal — installation-scoped, outside the base directory**:
  `%LOCALAPPDATA%\Engram\uninstall\<installation-id>\journal.json`.
- **Handoff protocol**: the helper waits for `parent_PID` to terminate
  (30-second timeout, assumes failure past that), then — and only the
  helper — performs the final directory purge and writes the terminal
  `directory_purge` step plus overall `COMPLETED`/`FAILED_FATAL` status.
- **Owned-artifact inventory**: base install directory, HKCU context-menu
  registry keys, P-drive SUBST (fallback cleanup only, since SUBST itself
  is being removed — see the venv-activation replacement) and junctions,
  generated configs (`_sys/env`), the entire `_sys/env/nodejs/npm-global`
  subtree.
- **Receipt/journal schema** (unchanged shape from v7): `operation`,
  `status`, `steps[]` (`subst_release`/`registry_cleanup`/
  `junction_cleanup`/`directory_purge`), `error_recoverable`. States:
  `PENDING`/`IN_PROGRESS`/`COMPLETED`/`FAILED_RECOVERABLE`/`FAILED_FATAL`.
- **Registration handling / failure behavior / test plan**: unchanged
  from v7 (narrower scope for unregistered installs; recoverable failures
  retry idempotently; `test_uninstall_semantics.py` covers the happy
  path + injected failure + repeated-uninstall idempotence).

**3.9 `virtualizer.mount()`/`unmount()` rewrite (new this round)**:
- `mount()`: delete the `_load_peers()` call, the peer-junction-creation
  loop, the `_assign_subst` call, the peer-local-settings loop, and the
  `subst_drive` state write. Replace with generic junction creation
  reading from a new `managed-links.json` registry (mirroring the
  existing generic pattern already used in `_cli_apply`).
- `unmount()`: delete the `_load_peers()` call, the SUBST-release logic,
  the peer-junction-removal loop, and the local-settings-removal loop.
  Replace with removing the generic junctions defined in
  `managed-links.json`.
- `_assign_subst()`/`_release_subst()`: **deleted entirely**, applying
  the session's separately-ratified SUBST-reconciliation decision
  (venv-style `ENGRAM_ROOT` activation replaces drive-letter
  virtualization).

## 4. Instantiated data ledgers

(Unchanged from v7 — directive digests/bindings and the statusline
disposition carried forward verbatim.)

### 4.1 Directives (`peerhub.governance-directive.v1`)

- **DIR-001**: `sha256:bd6a452ea5af1fab2653055ebdb52ac023d345ac8eaf3565fb23f6262c359f98`, `[{"consumer_name": "PeerHub/Orchestrator", "implementation_status": "PENDING", "evidence_refs": ["no ROI-gate/EXHAUSTIVE_COMPLETE consumer found in peerhub source"]}]`.
- **DIR-002**: `sha256:6a68da23ad2d663acbb64bda3e45b565e199c7df480fcfb6011e9b023cab79fb`, `[{"consumer_name": "cc", "implementation_status": "PENDING", ...}, {"consumer_name": "cx", "implementation_status": "PENDING", "evidence_refs": ["real PeerHub Codex adapter invocation supplies no sandbox flag and inherits config.toml"]}]`.
- **DIR-003**: `sha256:9bb8df7f009ce6a572e9d9d5d9f9574a91ab9b1f1449b1d779e92909b193eac2`, `[]` — **RETIRED at cutover**.
- **DIR-004**: `sha256:47f495f76342681af8e7cccf76e09be88e37114e3138ece07fe14fbaa8880777`, `[{"consumer_name": "peerhub.dispatch.capability", "implementation_status": "PENDING", ...}]`.
- **DIR-005**: `sha256:c871314e6f273ada6a56b8124466c56e301fadfb7cb8cc2e3eeb2a2f9cc9c934`, `[{"consumer_name": "FinalArbiterPolicy/arbiter_review.py", "implementation_status": "PENDING", ...}]`.
- **DIR-006**: `sha256:ba5e5423878b59976a434bf2c0428e92e3b7a5f022a327096d816045dfb4a451`, `[{"consumer_name": "ProposalCoordinator/.peerhub/proposals.json", "implementation_status": "PENDING", ...}]`.

Precondition unchanged: Increment D's directive-deletion depends on
`peerhub.governance-directive.v1` existing with verified migration
receipts before `user-directives.md` is deleted.

### 4.2 Statusline disposition

Unchanged — **DELETED OUTRIGHT** in Increment A.

## 5. Per-increment acceptance matrix

| Increment | Files changed/deleted | Test commands | Boundary state | Forbidden stale paths |
|---|---|---|---|---|
| **A** | Del: `_sys/cli/{agy,agy.bat,claude,claude.bat,codex,codex.bat,diag,diag.bat}`, `_sys/cli/{agy_entry.py,claude_entry.py,codex_entry.py,console_runner.py,peer_console.py,peerhub.bat}`, `_bat-shim`, `CLAUDE.md`, `GEMINI.md`, `PROTOCOL.md`, `AGENTS.md`, `_sys/ai/common/statusline/**`, `_sys/hooks/**` (9 files), `_sys/checks/check_contracts.py`. Mod: `_sys/cli/launch`, `_sys/cli/manage.py` (add `uninstall()`), `engram.cmd`, `README.md`, `_sys/claude/project/settings.json`, `run-tests.bat` (strip Gemini state creation), `host-test.ps1` (strip Gemini/Claude checks), **`local-test.bat` (strip all AI content: lines 73-87, 159-169, 174-236, 243-265)**. Add: `test_uninstall_semantics.py`, `test_boundary_imports.py`. | `run-tests.bat --full`<br>`pytest _sys/tests/unit/l1_core/test_contracts.py`<br>`pytest _sys/tests/unit/test_no_stray_hooks.py`<br>`pytest _sys/tests/unit/test_boundary_imports.py` | Bounded interim allowlist; hooks detached; statusline eliminated | `_sys/cli/{agy,claude,codex,diag,peerhub}*`, `_bat-shim`, `PROTOCOL.md`/`AGENTS.md`/`CLAUDE.md`/`GEMINI.md`, `_sys/ai/common/statusline`, `_sys/hooks`, `check_contracts.py` |
| **B** | Mod: `provisioner.py`, `launcher.py`, `manage.py` (remove workspace-init), **`virtualizer.py` (mount/unmount rewrite + SUBST removal)**, **`scrubber.py` (full `.ai`-governance strip)**, `config.py`, `check_tool_updates.py`, `doctor.py`, `env.json`, `dispatch.json`. Add: `_sys/tool-catalog.v1.json`, `managed-links.json`. Del: `peers.json`, `relocator.py`, tool-metadata portion of `runtimes.json`. | `run-tests.bat --full`<br>`pytest _sys/tests/unit/test_provisioner_autoinstall.py` (rewritten) | Catalog SSOT enforced; deep Python AI behavior stripped; SUBST removed | `peers.json`, `relocator.py`, root `.ai`, `_sys/ai/common/{agents,skills,mcp}` |
| **C** | Mod: `local.config.bat.template` (narrowed), generic docs. Del: AI hygiene checks, AI workspace templates, `check_config.py`. | `run-tests.bat --full`<br>existing hygiene test suite | AI-governance decoupled | AI-governance check scripts, legacy AI workspace templates |
| **D** | Del: `_sys/ai/**`, `_sys/claude/**`, `_sys/codex/**`, `_sys/antigravity/**`. (Precondition: verified directive migration receipts.) Mod: `test_no_stray_health_files.py` (rewritten to genuine provider-absence test). **Mod: `test_system_lifecycle.py` — delete `test_tier1_preserves_ai_governance_state_deletes_only_ephemeral` (157-183), `test_cleanup_blocked_when_active_session_present` (185-204), `test_tier4_zerobase_clears_ai_governance_state` (220-230); delete remaining `_load_peers` patches at 72/85/98/108/235/246; delete the 5 SUBST-specific tests (`test_registration_flow_sys_r1_r2` 68-94, `test_mount_reports_failed_when_subst_assignment_is_missing` 96-103, `test_unmount_reports_failed_when_subst_mapping_remains` 105-114, `test_registration_migration_sys_r3` 232-254, `test_dual_instance_different_subst_drives` 256-289) since SUBST is fully removed; in `test_cleanup_tier3_resets_runtime` (291-304) strip the `_sys/claude` mkdir mock; keep remaining generic lifecycle coverage.** | `run-tests.bat --full`<br>`pytest _sys/tests/unit/test_system_lifecycle.py _sys/tests/unit/test_no_stray_health_files.py` | Final boundary invariant achieved | `_sys/ai`, `_sys/claude`, `_sys/codex`, `_sys/antigravity`, root `.ai` |
| **Gate 7** | Mod: `build_package.py`, manifest templates. Del: `build_winget_package.py`. | `run-tests.bat --full`<br>`pytest test_winget_manifests.py`<br>`pytest test_version_ssot.py` | Packaging reflects final boundary; version SSOT enforced | duplicate builder, legacy AI-metadata manifests |

## Status

Eighth revision, all 5 mechanical fixes from the seventh critique
addressed with real, terminal-verified line-level detail. One notable
architectural consequence applied this round (SUBST removal cascading
into 5 deleted lifecycle tests) — flagged at the top of this document for
explicit sign-off in the next critique round rather than silently
accepted. Ready for a final ratification-decision pass.
