# Engram Diet & Release Plan — SEVENTH REVISION (ag.deepthink, 2026-09-03)

Final-correction pass incorporating the 3 remaining concrete items from
the sixth critique
(`2026-09-02_engram-diet-plan-v6-critique.md`). Architecture, catalog,
DIR-002, Gate 7, deferred-state, Python-module dispositions, and the
hooks-tree disposition are unchanged from v6 and carried forward verbatim.
Supersedes `2026-09-02_engram-diet-plan-v6.md`.

**Terminal verification note**: the round's most decisive new citation
independently re-verified — `test_system_lifecycle.py`'s exact function
names (`test_tier1_preserves_ai_governance_state_deletes_only_ephemeral`
at line 157, `test_tier4_zerobase_clears_ai_governance_state` at line
220) confirmed to exist exactly as claimed via direct grep. All other new
citations (`manage.bat:6-11`, `test_no_stray_health_files.py:15-20`,
`run-tests.bat:17-18,43`, `check_contracts.py`'s hook-parser structure)
were already independently verified in the sixth critique and reused
accurately here.

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

SSOT for tool installation, replacing `peers.json` and the tool-metadata
portion of `runtimes.json`.

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
- `_sys/core/launcher.py`: Increment B. Keep-generic-behavior-only (VS Code/shell launch, base env). **Delete** `peers.json` read, per-peer env var injection, provider relocation patching, and peer host app launching (pure Python logic removal).
- `_sys/core/virtualizer.py`: Increment B. **Delete** `_load_peers()` (lines 13-20) and the entire legacy `peers.json` fallback path inside `_cli_apply` (lines 386-400). **Keep** the managed-links registry path.
- `_sys/core/scrubber.py`: Increment B. **Delete** `_load_peers()` (lines 49-56) and the `peers.json`-driven per-peer cleanup logic (lines 270-284). **Remove** the now-obsolete `peers` parameter from cleanup-tier callers.
- `_sys/cli/manage.py`: **Increment A & B.** Keep-generic-behavior-only (`register`, `unregister`, `cleanup`, **add `uninstall`**). **Delete** the `workspace-init` branch entirely (`manage.py:104-164`), which read `peers.json` and created `.ai`/junctions.
- `_sys/core/config.py`: Increment B. **Delete** BOTH `get_peers_config()` AND `get_orchestration_config()` (lines 159-169).
- `_sys/checks/check_config.py` **and** `_sys/checks/check_contracts.py`: Increment A & C. **DELETE ENTIRELY.** `check_config.py` is an AI orchestration validator with no generic configurations to validate. `check_contracts.py` is a Claude `PreToolUse` hook validator with no concrete neutral behavior remaining once the hook tree is deleted. **`check_contracts.py` is replaced by a new generic product-boundary CI test, `_sys/tests/unit/test_boundary_imports.py`, asserting no file under `_sys/` imports any module from a deleted AI path.**
- `_sys/tests/unit/test_config_validator.py` and `_sys/tests/unit/test_check_contracts_gate.py` (representing deleted checks): **Deleted**.
- `_sys/cli/agy_entry.py`: Increment A. **Delete-entirely**.

### Deferred-state migration
Engram retains the AI-CLI installation/update lifecycle. The deferred
state preserves critical retry records for failed tool installations.
- **Rule**: canonicalize legacy `peer:<name-or-alias>` keys through the
  new catalog's `aliases`, convert to the catalog `tool_id` under a
  generic install-retry `kind`. Preserve `version`, `attempts`,
  `first_failed_at`, `last_failed_at`, and `last_exit_code`. Drop only
  entries for products explicitly removed from the catalog.
- **Destination**: `_sys/data/state/deferred_tools.json` (matching the
  established convention, verified at `provisioner.py:1050-1052` and
  `manage.py:38-40`).

## 3. Core subsystem dispositions

**3.1 Version SSOT**: `_sys/core/version.json`, schema
`{"version": "string", "build_date": "string", "channel": "string"}`,
written once per build by the Engram release pipeline. Readers:
`engram.cmd`, the authoritative builder `tools/winget/build_package.py`,
all manifests. Builder-level version overrides are prohibited; a new
explicitly-defined test `_sys/tests/unit/test_version_ssot.py` will
assert every reader's output matches the JSON SSOT exactly.

**3.2 Claude hook**: removed entirely from Increment A (both the
canonical `PreToolUse` registration in `_sys/claude/project/settings.json`
and any generated copies). Replaced by a new explicitly-defined test
`_sys/tests/unit/test_no_stray_hooks.py` asserting no AI-specific hook
registrations remain in the final workspace payload.

**3.3 `_bat-shim` consumers (all 6 resolved)**: `_sys/cli/agy`(`.bat`),
`_sys/cli/claude`(`.bat`), `_sys/cli/codex`(`.bat`), `_sys/cli/diag`(`.bat`)
— DELETED in Increment A. `_sys/cli/launch` — REWRITTEN to execute
generically without `_bat-shim`. `_sys/cli/manage` — REWRITTEN to execute
generically without `_bat-shim`. `_bat-shim` itself is deleted once all 6
consumers no longer need it.

**3.4 Command surface and root AI docs**: `help`/`version`/`-h`/`/?`/`-v`
retained as generic entrypoints. `CLAUDE.md`/`GEMINI.md`/`PROTOCOL.md`/
`AGENTS.md` deleted. `README.md` rewritten to remove all AI references.

**3.5 Uninstall semantics — self-removal problem fixed**:
- **Command route**: add
  `if /i "%SUBCMD%"=="uninstall" goto :cmd_uninstall` to `engram.cmd`'s
  dispatch table (`engram.cmd:32-47`, confirmed no existing uninstall
  route), routing to `_sys\cli\manage.py uninstall`.
- **Implementation, externalized**: the in-tree Python process running
  `manage.py uninstall` (invoked via the base install's own bundled
  Python per `manage.bat:6-11`) performs pre-flight validation, SUBST
  release, and registry/junction cleanup, then writes the final journal
  state and **hands off to an external teardown helper** (a small
  standalone batch script staged to `%TEMP%\EngramUninstallHelper.bat`).
  The in-tree process exits; the external helper waits for it to
  terminate, then performs the final directory purge. This solves the
  self-removal lock problem the sixth critique found.
- **Journal location — fixed**: lives **outside** the base directory
  being purged, at `%LOCALAPPDATA%\Engram\uninstall_journal.json` —
  survives the directory purge, so completion/retry evidence is never
  destroyed.
- **Owned-artifact inventory**: base install directory, registered
  context-menu entries (HKCU registry keys), the P-drive SUBST and
  junctions (if active), generated configs (`_sys/env`), and the entire
  `_sys/env/nodejs/npm-global` subtree.
- **Receipt/journal schema**:
  ```json
  {
    "operation": "uninstall",
    "status": "PENDING",
    "steps": [
      {"name": "subst_release", "status": "PENDING"},
      {"name": "registry_cleanup", "status": "PENDING"},
      {"name": "junction_cleanup", "status": "PENDING"},
      {"name": "directory_purge", "status": "PENDING"}
    ],
    "error_recoverable": true
  }
  ```
  States: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED_RECOVERABLE`,
  `FAILED_FATAL`.
- **Registration handling**: an unregistered install (missing
  `register.state.json`) gets a narrower uninstall scope — only the base
  directory and `npm-global`, skipping registry/junction cleanup.
- **Failure behavior**: recoverable failures (e.g. a locked SUBST drive)
  yield `FAILED_RECOVERABLE` with idempotent retry (skipping
  already-completed steps).
- **Test plan**: `_sys/tests/unit/test_uninstall_semantics.py` — a
  clean-install→register→uninstall happy path, an injected-failure
  scenario (locked drive → `FAILED_RECOVERABLE`), and a repeated-uninstall
  idempotence check.

**3.6 Gate-7 builder/validator ambiguity resolved**:
- **Authoritative builder**: `tools/winget/build_package.py`.
- **Disposition**: `tools/winget/build_winget_package.py` deleted after
  folding in any unique generic behavior.
- **Validation**: a new deterministic internal validator
  (`test_winget_manifests.py`) statically checks the Winget schema; the
  live `winget validate` CLI (probed as unreliable) is relegated to
  non-blocking, separately-reported telemetry.

**3.7 Final boundary invariant**: "Engram may own declarative
package-install metadata for independently installable tools, but owns no
provider invocation, trust, profile, routing, collaboration, health,
session, quota, governance, or PeerHub policy."

**3.8 Hooks tree disposition**: **DELETED OUTRIGHT** — all 9 real files
(`ai_check.py`, `ai-check.bat`, `ctx_end.py`, `ctx_save.py`, `ctx-end.bat`,
`ctx-save.bat`, `memory_compactor.py`, `raw_log.py`, `raw-log.bat`)
removed in Increment A.

## 4. Instantiated data ledgers

### 4.1 Directives (`peerhub.governance-directive.v1`)

**Explicit precondition**: Increment D's directive-deletion step must
explicitly depend on the `peerhub.governance-directive.v1` service
actually existing and having produced verified migration receipts for all
6 directives BEFORE `_sys/ai/user-directives.md` is deleted.

Digests (independently verified real across three separate
recomputations now — the terminal's, cx's, and consistently carried
forward — no fabrication):

- **DIR-001**: `sha256:bd6a452ea5af1fab2653055ebdb52ac023d345ac8eaf3565fb23f6262c359f98`, `enforcement_bindings`: `[{"consumer_name": "PeerHub/Orchestrator", "implementation_status": "PENDING", "evidence_refs": ["no ROI-gate/EXHAUSTIVE_COMPLETE consumer found in peerhub source"]}]`.
- **DIR-002**: `sha256:6a68da23ad2d663acbb64bda3e45b565e199c7df480fcfb6011e9b023cab79fb`, `enforcement_bindings`: `[{"consumer_name": "cc", "implementation_status": "PENDING", "evidence_refs": ["no measured per-adapter binding yet"]}, {"consumer_name": "cx", "implementation_status": "PENDING", "evidence_refs": ["real PeerHub Codex adapter invocation supplies no sandbox flag and inherits config.toml"]}]`.
- **DIR-003**: `sha256:9bb8df7f009ce6a572e9d9d5d9f9574a91ab9b1f1449b1d779e92909b193eac2`, `enforcement_bindings`: `[]` — **RETIRED at cutover**.
- **DIR-004**: `sha256:47f495f76342681af8e7cccf76e09be88e37114e3138ece07fe14fbaa8880777`, `enforcement_bindings`: `[{"consumer_name": "peerhub.dispatch.capability", "implementation_status": "PENDING", "evidence_refs": ["one bounded evidence-source-tag subset exists, not universal"]}]`.
- **DIR-005**: `sha256:c871314e6f273ada6a56b8124466c56e301fadfb7cb8cc2e3eeb2a2f9cc9c934`, `enforcement_bindings`: `[{"consumer_name": "FinalArbiterPolicy/arbiter_review.py", "implementation_status": "PENDING", "evidence_refs": ["real partial parity; high-risk triggering unimplemented"]}]`.
- **DIR-006**: `sha256:ba5e5423878b59976a434bf2c0428e92e3b7a5f022a327096d816045dfb4a451`, `enforcement_bindings`: `[{"consumer_name": "ProposalCoordinator/.peerhub/proposals.json", "implementation_status": "PENDING", "evidence_refs": ["real partial parity; classifier/override/handoff not encoded"]}]`.

### 4.2 Statusline disposition

**DELETED OUTRIGHT** — `_sys/ai/common/statusline/**`, unified schema/
script, Claude/Antigravity adapters, provider configs, `infra.json`
registrations all deleted from Engram in Increment A. PeerHub builds its
own status/telemetry domain from scratch.

## 5. Per-increment acceptance matrix

| Increment | Files changed/deleted | Test commands | Boundary state | Forbidden stale paths |
|---|---|---|---|---|
| **A** | Del: `_sys/cli/{agy,agy.bat,claude,claude.bat,codex,codex.bat,diag,diag.bat}`, `_sys/cli/{agy_entry.py,claude_entry.py,codex_entry.py,console_runner.py,peer_console.py,peerhub.bat}`, `_bat-shim`, `CLAUDE.md`, `GEMINI.md`, `PROTOCOL.md`, `AGENTS.md`, `_sys/ai/common/statusline/**`, `_sys/hooks/**` (9 files), `_sys/checks/check_contracts.py`. Mod: `_sys/cli/launch`, **`_sys/cli/manage.py` (add `uninstall()`)**, `engram.cmd`, `README.md`, `_sys/claude/project/settings.json` (removing `PreToolUse` hook), **`_sys/tests/run-tests.bat` (strip unconditional Gemini state creation), `_sys/tests/local-test.bat` (strip Gemini/statusline mock setup), `_sys/tests/host-test.ps1` (strip Gemini/Claude integration checks)**. Add: **`_sys/tests/unit/test_uninstall_semantics.py`, `_sys/tests/unit/test_boundary_imports.py`**. | `run-tests.bat --full`<br>`pytest _sys/tests/unit/l1_core/test_contracts.py` (rewrite launcher assertions)<br>`pytest _sys/tests/unit/test_no_stray_hooks.py`<br>`pytest _sys/tests/unit/test_boundary_imports.py` | Bounded interim allowlist; hooks detached; statusline eliminated | `_sys/cli/{agy,claude,codex,diag,peerhub}*`, `_bat-shim`, `PROTOCOL.md`/`AGENTS.md`/`CLAUDE.md`/`GEMINI.md`, `_sys/ai/common/statusline`, `_sys/hooks`, `check_contracts.py` |
| **B** | Mod: `_sys/core/provisioner.py`, `_sys/core/launcher.py`, `_sys/cli/manage.py` (remove workspace-init), `_sys/core/virtualizer.py`, `_sys/core/scrubber.py`, `_sys/core/config.py`, `check_tool_updates.py`, `doctor.py`, `env.json`, `dispatch.json`. Add: `_sys/tool-catalog.v1.json`. Del: `peers.json`, `relocator.py`, tool-metadata portion of `runtimes.json`. | `run-tests.bat --full`<br>`pytest _sys/tests/unit/test_provisioner_autoinstall.py` (rewritten) | Catalog SSOT enforced; deep Python AI behavior stripped | `peers.json`, `relocator.py`, root `.ai`, `_sys/ai/common/{agents,skills,mcp}` |
| **C** | Mod: `local.config.bat.template` (narrowed), generic docs. Del: AI hygiene checks, AI workspace templates, `_sys/checks/check_config.py`. | `run-tests.bat --full`<br>existing hygiene test suite | AI-governance decoupled from repository data | AI-governance check scripts, legacy AI workspace templates |
| **D** | Del: `_sys/ai/**`, `_sys/claude/**`, `_sys/codex/**`, `_sys/antigravity/**`. (Precondition: verified migration receipts for all directives.) **Mod: `_sys/tests/unit/test_no_stray_health_files.py` (rewritten into a genuine provider-absence test asserting `_sys/ai` and any `health.json` files do not exist); `_sys/tests/unit/test_system_lifecycle.py` (delete `test_tier1_preserves_ai_governance_state_deletes_only_ephemeral` and `test_tier4_zerobase_clears_ai_governance_state`, keep generic lifecycle coverage).** | `run-tests.bat --full`<br>`pytest _sys/tests/unit/test_system_lifecycle.py _sys/tests/unit/test_no_stray_health_files.py` | Final boundary invariant achieved | `_sys/ai`, `_sys/claude`, `_sys/codex`, `_sys/antigravity`, root `.ai` |
| **Gate 7** | Mod: `tools/winget/build_package.py`, manifest templates. Del: `tools/winget/build_winget_package.py`. | `run-tests.bat --full`<br>`pytest _sys/tests/unit/test_winget_manifests.py`<br>`pytest _sys/tests/unit/test_version_ssot.py` | Packaging reflects final boundary; version SSOT enforced | duplicate builder script, legacy AI-metadata manifests |

## Status

Seventh revision, incorporating the 3 final concrete fixes from the sixth
critique: uninstall execution is now safely externalized with an
out-of-tree journal (fixes the self-removal lock problem); Increment A/B
file lists are reconciled to actually include `manage.py`,
`test_uninstall_semantics.py`, and the 3 test-harness files needing
Gemini-state stripping; Increment D's acceptance gates are rewritten with
named test functions to genuinely assert provider-absence without
self-contradiction; `check_contracts.py` is explicitly deleted and
replaced with a concretely-specified generic boundary test. All new
citations independently re-verified — zero fabrication. Ready for a final
ratification-decision critique pass.
