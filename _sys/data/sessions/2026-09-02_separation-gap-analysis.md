# Engram / PeerHub full-separation gap analysis

**Date:** 2026-09-02
**Status:** research only; no implementation performed
**Engram stable:** `36606f1180f859809afb3ede4b63520fe2188590`
**Engram main:** `b92057415ce97a300d352872d461fa3389dd554b`
**PeerHub main:** `5b7ce5a17b082d1bfd34e2e93b30644fd422327e`

Path abbreviations:

- `ENGRAM_MAIN` = `D:\Engram&Peerhub\engram-main-worktree`
- `STABLE` = `P:\`
- `PEERHUB` = `P:\workspace\peerhub`

## Scope and prior evidence

The mandatory 2026-08-19 checkpoint was read first. It records:

- Engram separation commits `6b50945` and `482ab76`, including removal of `hub.py` and the legacy coordination cluster (`ENGRAM_MAIN\_sys\data\sessions\2026-08-19_engram-peerhub-separation.md:9-18`).
- The lifecycle tooling retained after that removal (`:19-32`).
- The then-observed Engram result of 494 passes and four environment-specific failures (`:33-37`).
- PeerHub at `7a5f939`, five commits past the v0.1.7 tag and declaring package version 0.1.8 (`:39-43`).
- The already-known global `CLAUDE.md` protocol staleness (`:110-113`).

Measured repository comparison:

- PeerHub advanced exactly 441 commits from `7a5f939` to `5b7ce5a`.
- `git diff --stat 7a5f939..5b7ce5a` reports 198 files changed, 63,523 insertions, and 480 deletions.
- `[empirical_probe]` Current PeerHub collection found 1,432 selected tests out of 1,441 collected, with nine deselected.
- `[empirical_probe]` Current Engram `main` collection found 498 tests. These are collection counts, not claims that either suite passed.

## 1. Stable-vs-main drift since the fork

`git log --reverse main..stable/hub-py-restored --oneline` yields exactly eight commits.

### 1.1 `0fe4ff4` — statusline raw-input log restoration

**Classification:** legacy AI statusline coordination.

The commit changes only `_sys/ai/common/statusline/statusline-unified.sh`. It restores writes of Claude input to `_sys/claude/config/status_input.log` and Agy input to `_sys/data/temp/ag_statusline_stdin.log` (`0fe4ff48a308d8234ecee7cb0a84861bbd28b00c:_sys/ai/common/statusline/statusline-unified.sh:27-28`).

Engram `main` removed this statusline/coordination surface in `6b50945` (`ENGRAM_MAIN\_sys\data\sessions\2026-08-19_engram-peerhub-separation.md:9-18`). Current PeerHub uses PeerHub-owned `.peerhub/statusline` state (`PEERHUB\peerhub\cli.py:631-640`).

**Recommendation:** do not cherry-pick or reimplement in Engram. Any future raw-input capture belongs under PeerHub-owned storage, privacy, and retention rules.

### 1.2 `f8de373` — `hub.py` path-quoting workaround

**Classification:** `hub.py`-specific.

The only changed file is `_sys/core/hub.py`. The patch remaps an executable resolved below the physical `D:` root back to logical `P:` before spawning it, addressing spaces and `&` in the physical root (`f8de37338163f7b08207bb202b8a62ba4735ea54:_sys/core/hub.py:6732-6764`).

Engram `main` intentionally has no `hub.py` (`ENGRAM_MAIN\_sys\data\sessions\2026-08-19_engram-peerhub-separation.md:9-18`).

**Recommendation:** do not cherry-pick. Preserve only the general acceptance requirement that PeerHub process launching work with spaces and shell metacharacters, subject to an independent current PeerHub test audit.

### 1.3 `6bfaca0` — quota-bucket name in diagnostics

**Classification:** legacy Engram AI diagnostics.

The commit changes `_sys/ai/common/statusline/snapshot.py`, preserving the worst quota label and adding it to alert text (`6bfaca07215e9aa7f6090967ffdd7ab46b7a3b68:_sys/ai/common/statusline/snapshot.py:1946-1957`).

The Engram snapshot/statusline layer was removed from `main` (`ENGRAM_MAIN\_sys\data\sessions\2026-08-19_engram-peerhub-separation.md:9-18`).

**Recommendation:** do not cherry-pick. If PeerHub emits quota alerts, retain "identify the limiting bucket" only as a PeerHub requirement.

### 1.4 `d43f4cf` — Antigravity settings tracking

**Classification:** vendor-specific AI configuration.

The commit tracks `_sys/antigravity/config/settings.json`, including an Agy statusline command and trusted workspaces (`d43f4cf4d27950714c2eb9d1837b4e4c4eda24c1:_sys/antigravity/config/settings.json:5-11`).

**Recommendation:** do not cherry-pick. Machine trust lists belong to the user/vendor installation, not Engram.

### 1.5 `e1c8a7b` — deduplicated AI console-title handling

**Classification:** AI-wrapper UX.

The commit adds `_sys/cli/_console_helpers.py` and changes `agy_entry.py`, `claude_entry.py`, `codex_entry.py`, and `console_runner.py`. These are members of the vendor-console cluster removed by `6b50945` (`ENGRAM_MAIN\_sys\data\sessions\2026-08-19_engram-peerhub-separation.md:9-18`).

**Recommendation:** do not cherry-pick. If titled interactive consoles remain desirable, design that independently as a PeerHub CLI feature.

### 1.6 `169906f` — unified peer environment-variable resolution

**Classification:** AI peer-wrapper/configuration logic.

The commit makes vendor entrypoints resolve variables from `_sys/ai/peers.json`. That file owns provider installation, environment, junction, and local-settings declarations for Claude, Codex, and Agy (`STABLE\_sys\ai\peers.json:1-28`, `:29-74`, `:76-103`, `:105-146`).

**Recommendation:** do not cherry-pick. Still-needed executable/environment discovery belongs in PeerHub.

### 1.7 `7bc3133` — remove unreachable workspace-init branch

**Classification:** cleanup inside an AI workflow that itself should be removed.

Engram `main` still contains `_workspace_init_legacy`, which reads `_sys/ai/peers.json` and creates `.ai` collaboration/session glue (`ENGRAM_MAIN\_sys\cli\manage.py:89-96`, `:104-164`).

**Recommendation:** do not cherry-pick. Remove the complete legacy workspace-init path during the ratified separation.

### 1.8 `36606f1` — add physical `D:` path to Antigravity trust

**Classification:** host-specific vendor security state.

The commit adds the physical checkout to Antigravity's trusted-workspace list (`36606f1180f859809afb3ede4b63520fe2188590:_sys/antigravity/config/settings.json:7-11`).

**Recommendation:** do not cherry-pick or reimplement.

### 1.9 Drift conclusion

**None of the eight commits should be cherry-picked into Engram `main`.**

Six are direct hub/statusline/vendor/wrapper work, one fixes a workflow scheduled for deletion, and one embeds machine-specific trust state. Only two generic ideas merit independent PeerHub gap checks:

1. Metacharacter-safe process launching.
2. Precise quota-bucket identification.

They should become PeerHub requirements/tests if still missing, not migrated Engram code.

## 2. PeerHub capability audit: pinned versus current

### 2.1 Version identity

The checkpoint describes PeerHub at `7a5f939`, five commits after the v0.1.7 tag, while the package already declared 0.1.8 (`ENGRAM_MAIN\_sys\data\sessions\2026-08-19_engram-peerhub-separation.md:39-43`).

Both `7a5f939` and current `5b7ce5a` contain `version = "0.1.8"` (`PEERHUB\pyproject.toml:7`). `git describe 7a5f939` returns `v0.1.7-5-g7a5f939`.

Therefore the historical "v0.1.7/v0.1.8" wording mixed three different identities:

- Git tag.
- Exact source commit.
- Python package version.

A future integration contract must distinguish these explicitly.

### 2.2 Current PeerHub scope

Current PeerHub describes:

- Native adapters and direct CLI bootstrap (`PEERHUB\README.md:15-17`).
- Retry/resume, streaming, tool capture, and failover (`:20`).
- Broadcast, evidence, and health behavior (`:21-23`).
- A legacy catalog with 71 backed commands and 19 permanent waivers (`:42`).

The native CLI now owns many domains, including status, diagnostics, broadcast, health, peers, leases, gates, asks, statuslines, consensus, tasks, lessons, nodes, locks, artifacts, roles, routing, leadership, feedback, errors, alerts, rooms, duty, and sessions (`PEERHUB\peerhub\cli.py:2470-2664`, `:2664-3212`, `:3391-3675`).

The legacy compatibility catalog is also inside PeerHub (`PEERHUB\peerhub\application\legacy.py:146-180`). Engram therefore does not need an orchestration/action translation layer.

### 2.3 AI-CLI autodetection

#### What exists

PeerHub has target-specific resolution and readiness primitives:

- Built-in adapters are registered for `fake`, `ag`, `cc`, and `cx` (`PEERHUB\peerhub\adapters\registry.py:46-51`).
- Aliases include `agy`, `claude`, and `codex` (`:72-79`).
- Adapter packages may be explicitly registered at runtime (`:84-125`).
- `_resolve_executable_path()` searches for a supplied executable through the active environment/PATH (`:128-164`).
- `resolve_peer_target()` resolves an explicitly requested target/alias and its adapter command (`:166-214`).
- Direct bootstrap executes a live `--version` readiness probe after resolution (`PEERHUB\peerhub\application\bootstrap.py:106-205`).

#### What does not exist

PeerHub does not currently expose aggregate host discovery such as "list all supported AI CLIs installed on this machine."

`[empirical_probe]` Current `peerhub --help` exposes `status`, `diag`, `broadcast`, `health`, `peer`, `lease`, `broker`, `gate`, `ask`, `statusline`, `consensus`, `task`, `lesson`, `node`, `lock`, `artifact`, `role`, `routing`, `leadership`, `feedback`, `error`, `alert`, `room`, `duty`, and `session`. There is no host-CLI autodetection/inventory command.

`peerhub routing discover` is not executable discovery. `[empirical_probe]` Its public arguments are `--workspace`, `--needs`, `--effort`, and `--json`. Its implementation performs deterministic capability matching over registered routing and health facts (`PEERHUB\peerhub\cli.py:3097-3117`; `PEERHUB\peerhub\application\capability_matching.py:1-2`, `:123-143`).

PeerHub can determine whether a caller-named Claude/Agy/Codex target resolves and passes readiness. It cannot presently produce a complete installed-CLI inventory without the caller supplying candidates.

#### Existing design work

The repository contains draft designs for the missing capability:

- `PHASE1-AUTODETECT-SIDECAR-2026-08-19.md` is explicitly DRAFT (`PEERHUB\docs\design\PHASE1-AUTODETECT-SIDECAR-2026-08-19.md:1-18`).
- Its V2 is also DRAFT (`PEERHUB\docs\design\PHASE1-AUTODETECT-SIDECAR-V2-2026-08-19.md:1-5`).
- V2 proposes trusted-manifest scanning (`:25-32`), an optional Engram bridge (`:34-44`), and command shims (`:46-48`).

No matching production implementation was found.

**Verdict:** aggregate AI-CLI autodetection is a real PeerHub gap against the user's stated goal. It must be fully designed, ratified, implemented, and measured before Engram deletes any still-required discovery/install capability.

### 2.4 State and integration assumptions that changed

#### PeerHub owns its state

PeerHub stores its database at `.peerhub/peerhub.sqlite3` (`PEERHUB\peerhub\core\context.py:30-47`) and statusline state below `.peerhub/statusline` (`PEERHUB\peerhub\cli.py:631-640`).

Engram must not mirror this into `_sys/ai`, `.ai`, vendor logs, or another orchestration store.

#### Engram's version declarations conflict

Engram declares:

- PeerHub v0.1.7 in `_sys/runtimes.json` (`ENGRAM_MAIN\_sys\runtimes.json:250-264`).
- "PeerHub v0.1.0 Engine Integration" in `engram.cmd` (`ENGRAM_MAIN\engram.cmd:119-120`).
- PeerHub v0.1.7 in its README (`ENGRAM_MAIN\README.md:10`, `:38`, `:76`).

Current PeerHub declares package version 0.1.8 (`PEERHUB\pyproject.toml:5-19`), while its own README's installation example still pins v0.1.1 (`PEERHUB\README.md:53`).

This must be replaced by an independently versioned release/API contract, not another manually copied version string.

#### Entrypoint assumptions conflict

Current PeerHub registers only `peerhub = peerhub.cli:main` (`PEERHUB\pyproject.toml:16-19`). Its README nevertheless claims that both `peerhub` and `hub` entrypoints are registered (`PEERHUB\README.md:65`).

Engram's README invokes `_sys/cli/hub.bat` (`ENGRAM_MAIN\README.md:86-87`), but that file is absent from Engram `main`. Engram should contain no PeerHub passthrough wrapper once the packages are independent.

#### PeerHub's README also needs reconciliation

It says formal consensus is deferred (`PEERHUB\README.md:30`) and that legacy `hub.py` remains authoritative (`:38`), but later says consensus is implemented and 71/90 legacy commands are backed (`:42`).

Its own documentation rule correctly prohibits pinned test-pass numbers (`:123-134`). Engram should follow that rule.

### 2.5 Test and version badge verdict

Engram's badges are stale.

- `README.md` claims "1695+ green" and PeerHub v0.1.7 (`ENGRAM_MAIN\README.md:7-11`, `:102`).
- `[empirical_probe]` Current Engram source contains 498 collected tests.
- The 2026-08-19 checkpoint recorded 494 passes plus four environment-specific failures (`ENGRAM_MAIN\_sys\data\sessions\2026-08-19_engram-peerhub-separation.md:33-37`).
- `[empirical_probe]` Current PeerHub contains 1,432 selected tests out of 1,441 collected.
- Commit `3511313cc79b5868ec1cacc990a590d3e63fc866` records a separate measured run of 1,432 passed, nine deselected, and 13 subtests passed.
- Current PeerHub package metadata is 0.1.8 (`PEERHUB\pyproject.toml:7`).

**Recommendation:** remove static test-count and PeerHub-version badges from Engram. If compatibility needs to be expressed, publish a tested protocol/API range in machine-readable release metadata.

## 3. Full Engram `main` AI-CLI inventory

The inventory below covers the complete tracked tree at `b920574`. A directory-level entry applies to every tracked file below that path.

### 3.1 Root-level inventory

| Item | Classification | Required action |
|---|---|---|
| `.gitattributes`, `.gitignore`, `LICENSE` | Core repository infrastructure | Keep; remove only obsolete AI-specific ignore rules. |
| `Engram.exe` | Core installer launcher | Keep. Its source only locates and launches `INSTALL.bat` (`ENGRAM_MAIN\wrapper.cs:5-20`). |
| `wrapper.cs` | Core installer launcher source | Keep. |
| `INSTALL.bat` | Core, but currently drives a mixed runtime catalog | Keep the Python/environment bootstrap (`ENGRAM_MAIN\INSTALL.bat:4-18`, `:80-144`); remove AI runtimes from the catalog/backend. |
| `UPDATE.bat` | Core | Keep the environment update front end (`ENGRAM_MAIN\UPDATE.bat:1-16`); prune AI providers from updater/provisioner inputs. |
| `STATUS.bat` | Core | Keep (`ENGRAM_MAIN\STATUS.bat:1-10`); remove AI-peer/session reporting from `doctor.py`. |
| `register.bat`, `unregister.bat` | Core | Keep the P-drive/context-menu lifecycle. `engram.cmd` dispatches them at `:71-75`, and `manage.py` invokes mount/unmount at `:61-76`. |
| `CLEANUP.bat` | Mixed | Keep the generic cleanup front end (`ENGRAM_MAIN\CLEANUP.bat:1-2`); remove AI/session cleanup from `scrubber.py`. |
| `TIDY.bat` | Mixed | Keep the manual preview/confirmation flow (`ENGRAM_MAIN\TIDY.bat:1-15`); remove AI/vendor cache rules from `tidy_temp.py`. |
| `engram.cmd` | Mixed | Keep install/status/register/unregister/update/cleanup/tidy routing (`ENGRAM_MAIN\engram.cmd:32-40`, `:62-88`). Delete `diag`, `peerhub`, `launch`, `agy`, `claude`, and `codex` routing (`:42-47`, `:90-113`) and AI/PeerHub branding/help (`:119-145`). |
| `README.md` | Stale AI-product documentation | Rewrite; see section 4. |
| `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` | Stale AI-governance instructions | Rewrite as ordinary repository contributor/tool instructions or remove provider-specific duplicates. |
| `PROTOCOL.md` | Peer-collaboration pointer | Delete; PeerHub owns collaboration protocol. |
| `CONVENTION.md` | Partly core | Retain after removing Hub protection and AI-governance references (`ENGRAM_MAIN\CONVENTION.md:1-12`). |

There is no tracked `UNINSTALL.bat` at `b920574`. The future architecture should decide explicitly whether `unregister.bat` plus cleanup is the supported uninstall procedure or whether Engram needs an actual uninstall front end.

### 3.2 `tools/winget` and `manifests`

Two overlapping packaging implementations exist:

- `tools/winget/build_package.py`
- `tools/winget/build_winget_package.py`

Both are core packaging tools, but they duplicate archive and manifest generation.

`build_package.py` still advertises a multi-agent/PeerHub product and emits PeerHub release notes (`ENGRAM_MAIN\tools\winget\build_package.py:42-100`). It also packages AI-facing root documents (`:105-123`).

`build_winget_package.py` explicitly includes `.agy`, `.claude`, `_sys/ai`, and other AI surfaces (`ENGRAM_MAIN\tools\winget\build_winget_package.py:30-71`) and generates a multi-AI collaboration description (`:190-216`).

**Action:**

- Keep one canonical builder—prefer the more complete `build_package.py`.
- Delete `build_winget_package.py` after verifying and folding any unique generic Winget behavior.
- Rewrite the canonical builder's descriptions, tags, release notes, and include/exclude rules for the portable-development-environment product.
- Keep and regenerate all four Winget manifests: `greatgc-flow.Engram.yaml`, `.installer.yaml`, `.locale.en-US.yaml`, and `.locale.ko-KR.yaml`.

The English locale currently describes Engram as a multi-AI peer-coordination environment and names Claude/Gemini/Codex (`ENGRAM_MAIN\manifests\g\greatgc-flow\Engram\2.1.0\greatgc-flow.Engram.locale.en-US.yaml:10-26`). That description and its Korean counterpart must be regenerated. The version and installer manifests remain structurally within core packaging scope.

### 3.3 `_sys/ai`

Every tracked file under `ENGRAM_MAIN\_sys\ai` is outside Engram's final ownership boundary.

This includes:

- Coordination/configuration: `backlog.json`, `capability-declarations.json`, `collaboration_loop_bindings.json`, `collaboration_policy.schema.json`, `error-taxonomy.json`, `governance_params.json`, `infra.json`, `lifecycle_policy.json`, `logging-config.json`, `model-registry.json`, `orchestration.json`, `peers.json`, `policy-decisions.json`, `protocol.json`, `room_policy.example.json`, `routing-config.json`, `status_checks.json`, `telemetry-config.json`, `traceability_map.json`, and `user-directives.md`.
- Agents, skills, MCP, statusline, and tool registry below `_sys/ai/common`.
- Knowledge and lessons below `_sys/ai/knowledge`.
- Proposals, snapshots, and compatibility artifacts.

`_sys/ai/protocol.json` itself acknowledges that peer coordination belongs to PeerHub, but still defines `.ai` runtime/output/log locations (`ENGRAM_MAIN\_sys\ai\protocol.json:4-23`). `_sys/ai/orchestration.json` continues to define peer nodes and consensus configuration (`ENGRAM_MAIN\_sys\ai\orchestration.json:63-489`). `_sys/ai/peers.json` continues to own provider installation/environment configuration (`:1-146`).

**Move to PeerHub as semantics, not copied files:**

1. Still-required executable discovery/install facts from `peers.json`, redesigned as the ratified PeerHub autodetection manifest.
2. Ratified lessons/directives that are still current and not already represented in PeerHub, with provenance.
3. Still-supported adapter/tool-registry entries after verifying them against current PeerHub adapter/plugin contracts.

**Delete from Engram after migration:** the entire `_sys/ai` tree. Do not migrate credentials, transient state, host paths, stale orchestration policy, or compatibility snapshots.

### 3.4 Vendor-specific trees

These are all outside Engram's target scope:

- `_sys/antigravity/**`
- `_sys/claude/**`
- `_sys/codex/**`

They contain statusline launchers, provider settings, trust/configuration, agents, skills, and workspace templates. Examples include `_sys/antigravity/agy-status.bat`, `_sys/claude/claude-status.bat`, and `_sys/codex/codex-status.bat`.

Current PeerHub already owns provider adapters and statusline formatting (`PEERHUB\peerhub\adapters\registry.py:46-79`; `PEERHUB\peerhub\cli.py:631-640`).

**Action:** delete all three vendor trees from Engram. Move no host/user trust or credential state. If PeerHub needs any adapter documentation or fixtures, recreate only those reviewed assets in PeerHub.

### 3.5 `_sys/cli`

Complete tracked inventory:

- `_bat-shim`
- `agy`, `agy.bat`, `agy_entry.py`
- `claude`, `claude.bat`, `claude_entry.py`
- `codex`, `codex.bat`, `codex_entry.py`
- `console_runner.py`, `peer_console.py`
- `diag`, `diag.bat`
- `peerhub.bat`
- `cleanup.py`
- `launch`, `launch.bat`, `launcher.py`
- `manage`, `manage.bat`, `manage.py`

**Delete from Engram:** `_bat-shim`; all `agy*`, `claude*`, and `codex*` wrappers; `console_runner.py`; `peer_console.py`; `diag`; `diag.bat`; and `peerhub.bat`. The latter couples PeerHub to Engram's venv, P-drive fallback, and PATH (`ENGRAM_MAIN\_sys\cli\peerhub.bat:3-14`).

Do not move these wrappers wholesale. Vendor CLIs remain their own products; PeerHub should invoke them through its adapters.

**Keep after narrowing:** `cleanup.py`; `manage`, `manage.bat`, and `manage.py` only for register/unregister/cleanup; and `launch`, `launch.bat`, and `launcher.py` only if they launch generic shells/editors. Delete `workspace-init` and `_workspace_init_legacy` (`ENGRAM_MAIN\_sys\cli\manage.py:89-164`).

The existing product-boundary test still requires several AI launchers to remain (`ENGRAM_MAIN\_sys\tests\unit\l1_core\test_contracts.py:96-111`). That test encodes an obsolete boundary and must be updated during the future ratified implementation.

### 3.6 `_sys/core`

| File | Classification and action |
|---|---|
| `dispatch.bat`, `dispatcher.py` | Core command dispatch; keep. |
| `setup.py`, `updater.py`, `registrar.py`, `timestamps.py`, `env_loader.py` | Core environment lifecycle; keep. |
| `config.py` | Keep generic configuration; remove `.ai/config.json`, peer, and orchestration readers (`ENGRAM_MAIN\_sys\core\config.py:83-84`, `:128-169`). |
| `doctor.py` | Keep environment/runtime checks; delete AI CLI lookup and session-state checks (`ENGRAM_MAIN\_sys\core\doctor.py:133-142`, `:183-201`). |
| `launcher.py` | Keep generic environment, VS Code, and shell launching; remove peer/provider environment and relocation behavior (`ENGRAM_MAIN\_sys\core\launcher.py:51-101`, `:104-206`, `:241-251`). |
| `provisioner.py` | Keep generic checksum/download/install machinery; move required AI install/discovery semantics to PeerHub, then delete AI runtime/provider loops (`ENGRAM_MAIN\_sys\core\provisioner.py:1025-1042`, `:1133-1167`, `:1238-1266`). |
| `relocator.py` | AI `peers.json` relocation; delete after any generic managed-link behavior is assigned to `virtualizer.py`. |
| `scrubber.py` | Keep generic cleanup; delete `.ai`, governance, session, and peer cleanup (`ENGRAM_MAIN\_sys\core\scrubber.py:49-56`, `:109-169`). |
| `tidy_temp.py` | Keep generic caches; delete AI/vendor cache rules (`ENGRAM_MAIN\_sys\core\tidy_temp.py:45-72`, `:97-99`). |
| `version_resolver.py` | Keep, but relocate `.ai/tool_discovery_cache.json` to Engram-owned environment/cache state (`ENGRAM_MAIN\_sys\core\version_resolver.py:21-24`). |
| `virtualizer.py` | Keep SUBST/P-drive and generic managed links; delete peer-config and vendor junction logic (`ENGRAM_MAIN\_sys\core\virtualizer.py:13-20`, `:53-62`, `:177-336`). |

### 3.7 Core configuration files

- `_sys/runtimes.json`: keep for Engram-owned runtimes, but remove Agy (`:177-193`), Claude (`:220-234`), Codex (`:235-249`), and PeerHub (`:250-264`).
- `_sys/env.json`: keep generic environment configuration, but remove Claude/provider variables and Agy/vendor paths (`ENGRAM_MAIN\_sys\env.json:6-37`).
- `_sys/config/environment.json`: keep, but remove vendor-specific configuration directories (`ENGRAM_MAIN\_sys\config\environment.json:17-19`).
- `_sys/dispatch.json`: keep generic install/update/status/register actions; remove AI/peers bindings, including virtual-mount dependency on `_sys/ai/peers.json` (`ENGRAM_MAIN\_sys\dispatch.json:12-18`).
- `_sys/paths.json`, `_sys/context_menu.json`, `_sys/git-config/**`, and `_sys/start.bat`: core; keep after checking for stale AI references.
- `_sys/local.config.bat.template`: keep generic settings; remove AI/peer options (`ENGRAM_MAIN\_sys\local.config.bat.template:31-49`).

### 3.8 `_sys/hooks`

Complete inventory:

- `ai_check.py`, `ai-check.bat`
- `ctx_end.py`, `ctx-end.bat`
- `ctx_save.py`, `ctx-save.bat`
- `memory_compactor.py`
- `raw_log.py`, `raw-log.bat`

These are AI governance/session/context tools. `ctx_end.py` invokes Claude and edits global/provider state (`ENGRAM_MAIN\_sys\hooks\ctx_end.py:71-84`, `:219-341`). `ctx_save.py` explicitly manages peer/session summaries (`ENGRAM_MAIN\_sys\hooks\ctx_save.py:4-9`).

**Action:** delete them from Engram. If PeerHub needs session export, compaction, or raw-log retention, design it inside PeerHub rather than moving these scripts unchanged.

### 3.9 `_sys/checks`

**Keep or refactor as generic Engram checks:** `_common.py`, `check-deps.bat`, `check-portability.bat`, `check-versions.bat`, `check_config.py`, `check_encoding.py`, `check_root_hygiene.py`, `check_tool_updates.py`, and `check_unreferenced_functions.py`.

**Delete from Engram or recreate in PeerHub if still required:** `check-agents.bat`, `check-docs-mece.bat`, `check_docs_mece.py`, `check-health.bat`, `check-policy.bat`, `check-risk.bat`, `check_backlog.py`, `check_peer_characteristics.py`, `check_policy_constants.py`, `check_policy_ledger.py`, `saturation_scan.py`, `saturation-scan.bat`, `self-care.bat`, and `sync-docs.bat`.

`check_contracts.py` is a Claude PreToolUse/AI-governance hook (`ENGRAM_MAIN\_sys\checks\check_contracts.py:3-4`, `:62-63`). Replace it with ordinary CI product-boundary checks; do not retain the vendor-hook contract.

### 3.10 Documentation, data, and templates

#### `_sys/docs/history/**`

This tree is AI collaboration/governance history, not runtime functionality. Remove it from the distributed portable package. If historical provenance remains in Git, place it in a clearly archival, non-runtime location or PeerHub history archive.

#### `_sys/docs-v2/**`

Most entries describe consensus, routing, peer permissions, AI profiles, statuslines, and Hub behavior. The MOC points to consensus/routing/peer documents (`ENGRAM_MAIN\_sys\docs-v2\MOC.md:22-28`), while the architecture still describes Hub, `.ai`, and AI wrappers (`ENGRAM_MAIN\_sys\docs-v2\20-architecture.md:85-147`).

Replace it with a smaller Engram set covering portable installation, runtime/tool management, P-drive virtualization, update/status/cleanup, packaging, and contribution conventions.

#### `_sys/data/**`

The tracked content is proposals and session/history reports. Retain only as repository research/archive material if desired; exclude it from the portable runtime package. It must not become a second live governance store.

#### `_sys/templates/**`

AI-specific templates include global/project Claude files, Gemini files, `.ai` knowledge bindings, and workspace collaboration settings. Delete those templates. Keep only a generic workspace skeleton after removing `.ai`, Claude/Gemini, and collaboration-rate content.

### 3.11 `_sys/tests`

Keep tests for installation, generic dispatch, configuration loading, runtime update/status, P-drive virtualization, managed links, cleanup, portability/path scenarios, packaging, and root hygiene.

Delete or move coverage for peer routing/consoles, consensus/collaboration policy, quota/health/statusline governance, AI workspace templates, provider permissions/capabilities, backlog/policy-ledger/saturation behavior, and AI context hooks.

The current boundary test correctly prohibits reintroducing `hub.py` and related modules (`ENGRAM_MAIN\_sys\tests\unit\l1_core\test_contracts.py:21-93`) but incorrectly preserves vendor launchers (`:96-111`). Replace it with a stronger zero-AI-ownership contract.

### 3.12 `_sys/tools`

The tracked tool payload contains generic development utilities: `bat`, `delta`, `fd`, `fzf`, `gh`, `jq`, `oh-my-posh`, `ripgrep`, and `sqlite`. These remain portable-development-environment scope. Their install/update/status lifecycle stays in Engram.

### 3.13 Move-versus-delete summary

**Move or redesign into PeerHub before deletion:**

1. Aggregate AI-CLI discovery and live installation observations.
2. Required declarative executable/provider manifest fields from `_sys/ai/peers.json`.
3. Current ratified collaboration lessons/directives not already represented in PeerHub.
4. Any genuinely required adapter/statusline behavior not already present.

**Delete outright from Engram:** `_sys/ai/**`; `_sys/antigravity/**`; `_sys/claude/**`; `_sys/codex/**`; vendor CLI wrappers/consoles; PeerHub passthroughs; AI statusline/governance/health/quota/consensus/context hooks; and AI templates, docs, and policy checks.

**Keep and narrow:** environment install/update/status, P-drive registration/virtualization, generic runtime provisioning, generic shells/editor launch, cleanup, portability checks, packaging, and tool payloads.

## 4. Documentation and configuration staleness

### 4.1 `README.md`

The README requires a complete rewrite. Stale sections include:

- Product description as an autonomous peer-to-peer AI workspace (`ENGRAM_MAIN\README.md:2-4`).
- Orchestration, consensus, PeerHub, and test-count badges (`:7-11`).
- Multi-agent claims and governance behavior (`:16-27`).
- Peer network and role table (`:29-36`).
- PeerHub integration and `hub ask`/broadcast descriptions (`:38-49`).
- AI CLI prerequisites (`:57-60`).
- PeerHub bootstrap and `_sys/cli/hub.bat` examples (`:73-93`).
- `_sys/ai` as SSOT and the 1,695-test claim (`:99-105`).

The replacement should describe only the portable Windows development environment, lifecycle commands, P-drive virtualization, and tool inventory. PeerHub should be a separate optional project, if mentioned at all, with no embedded version or test-count badge.

### 4.2 `CLAUDE.md`

The file instructs Claude to load PeerHub/AI SSOT, peer-specific configuration, room handoffs, `_sys/claude/config`, and `_sys/ai/backlog.json` (`ENGRAM_MAIN\CLAUDE.md:3-26`).

Replace it with concise repository-development instructions, or remove it if `AGENTS.md` is sufficient. It must not establish collaboration state inside Engram.

### 4.3 `AGENTS.md`

It describes the repository as an AI-collaboration environment and points to `_sys/ai/protocol.json`, `_sys/ai/orchestration.json`, and the AI-oriented docs MOC (`ENGRAM_MAIN\AGENTS.md:4`, `:11-16`).

Rewrite it as the contributor pointer for the portable environment only.

### 4.4 `GEMINI.md`

The file is almost entirely AI-peer startup, peer-specific configuration, and `.ai` handoff instructions (`ENGRAM_MAIN\GEMINI.md:2-14`).

Delete or replace it with ordinary repository instructions. It must not own collaboration protocol.

### 4.5 `PROTOCOL.md`

This is only a collaboration-protocol index pointing into AI documentation (`ENGRAM_MAIN\PROTOCOL.md:1-5`). Delete it; Engram no longer has a collaboration protocol.

### 4.6 `CONVENTION.md`

The file has a salvageable portable-development purpose, but still points to Hub protection and AI-oriented conventions (`ENGRAM_MAIN\CONVENTION.md:1-12`). Retain it after rewriting around batch/PowerShell, JSON, testing, portability, packaging, and environment lifecycle.

### 4.7 `_sys/ai` configuration

`orchestration.json`, `protocol.json`, `peers.json`, routing policy, model registry, capability declarations, and governance state all duplicate PeerHub's intended ownership.

They must be removed from Engram after migration gates are satisfied. Engram must not retain a "thin" orchestration mirror, because that would preserve two authorities.

### 4.8 Global `P:\_sys\claude\config\CLAUDE.md`

The checkpoint's "dead protocol" finding remains correct for Engram `main` and the intended separated architecture, but it needs one temporal qualification:

- The protocol is not literally absent everywhere today because frozen `stable/hub-py-restored` still contains `P:\_sys\core\hub.py` and its old configuration.
- It is absent from Engram `main`, and it must not survive final separation.

Specific stale sections:

1. **Multi-Peer Collaboration Protocol:** lines 36-43 point to `P:\_sys\ai\protocol.json`, old docs-v2 protocol files, invariants, and archived legal code.
2. **Always-On Collaboration:** lines 45-52 require every request to use `collab_rate` and fallback routing.
3. **COLLAB_RATE and R-levels:** lines 56-77 define R:6–R:10 behavior and unanimity.
4. **Peer call method:** lines 79-101 require IPC query files and direct execution of `python "P:\_sys\core\hub.py" ask`.
5. **Output and cycle conventions:** lines 103-122 prescribe the old peer-response wrapper and collaboration cycle.
6. **Context files:** lines 124-127 point to Engram-owned session archival; this becomes stale if the Engram context hooks are removed.

The general communication, OS/environment, language, and coding preferences at lines 8-34 are not inherently tied to Hub and can be preserved selectively.

**Recommendation:** rewrite the global file at cutover to reference PeerHub's actual public CLI/protocol and current user directives. Do not edit it during pre-architecture research or while frozen stable remains the live checkout.

## Recommended pre-implementation gates

No implementation should begin until these are detailed and unanimously ratified:

1. **Ownership matrix:** Engram owns environment lifecycle; PeerHub owns every AI-provider, collaboration, routing, session, health, and governance capability.
2. **PeerHub autodetection design:** define trusted evidence sources, supported vendors, PATH/manifest precedence, stale-observation handling, output DTOs, and Windows path/security behavior.
3. **PeerHub implementation and measured release:** implement aggregate autodetection before deleting corresponding Engram provider metadata.
4. **Independent installation contract:** decide whether Engram merely links to PeerHub or optionally installs it. Full independence argues against Engram pinning or silently provisioning PeerHub.
5. **Migration ledger:** enumerate exact active lessons/provider facts moving to PeerHub and explicitly waive/delete everything else. Never migrate credentials or host trust state.
6. **Engram deletion plan:** remove AI directories, wrappers, hooks, checks, docs, templates, and tests in reviewable increments protected by a zero-AI-ownership contract.
7. **Packaging/doc reconciliation:** regenerate Winget metadata and rewrite root documentation after the code boundary is final.
8. **Clean-room validation:** validate only in the isolated Engram `main` worktree and PeerHub repository. Never switch or modify frozen `P:\stable/hub-py-restored`.

## Final conclusions

- None of the eight stable-only commits belongs on Engram `main`.
- PeerHub has named-target executable resolution and live readiness probing, but not aggregate installed-AI-CLI autodetection.
- Engram `main` still contains a substantial residual AI layer despite removal of `hub.py`: provider wrappers, `_sys/ai`, vendor configuration, hooks, checks, templates, mixed core functions, stale packaging, and obsolete documentation.
- Engram's PeerHub version, test-count, entrypoint, and capability claims are stale.
- The global Claude protocol is valid only as documentation of the still-frozen legacy checkout; it is dead for the target architecture and must be rewritten at cutover.
- Full separation requires migration of a small number of capabilities and facts—not preservation of old wrapper/configuration files.
