# Engram Diet & Release Plan — Gates 1, 5, 6 (ag.deepthink, 2026-09-02)

Formalizes the ownership matrix, migration ledger, and phased deletion +
release plan per the user's explicit mandate: Engram keeps only completely
essential portable-dev-environment functions; everything AI-provider/
collaboration/routing/session/health/governance moves out or is deleted.

Terminal verification: the `_sys/ai/peers.json` field claims in §2.2 below
were checked directly against the real file (`P:\_sys\ai\peers.json`, 148
lines, read in full) — every named field (`node_ids`, `npm_package`,
`native_binary.{bin_name,win_exe,install_subdir}`, `env_vars`,
`local_settings`) and every named excluded field (`host_junction`,
`project_junction`, `host_app`, `workspace.{shadow_subdir,junction_name}`,
`cleanup`, `relocate`) matches the real file's structure exactly. One
incompleteness (not an error): the `env_vars` citation names
`CLAUDE_CONFIG_DIR`/`CODEX_HOME`/`GEMINI_DIR` but the real file also has
`AGY_CONFIG_HOME` for antigravity — same category, just not individually
listed. One open detail this plan doesn't address: `claude`'s
`local_settings.permissions.allow` list hardcodes paths to the exact
wrapper scripts being deleted in Increment 1 (`_sys\cli\msg.bat`,
`claude.bat`, `codex.bat`, `agy.bat`) — whatever migrates this field to
PeerHub will need to rewrite those paths, not copy them verbatim.

## 1. Ownership matrix

| Category / Path | Owner | Resolution |
|---|---|---|
| Root lifecycle scripts (`INSTALL.bat`, `UPDATE.bat`, `STATUS.bat`, `CLEANUP.bat`, `TIDY.bat`, `engram.cmd`, `register.bat`, `unregister.bat`) | **Engram** | Essential to the portable workspace; prune AI runtimes/PeerHub routing from them. |
| `tools/winget` & `manifests` | **Engram** | Generic packaging stays (canonical builder: `build_package.py`); strip AI-specific inclusions and multi-agent descriptions. |
| `_sys/ai` (all config/orchestration/directives) | **PeerHub** | Every file deletes from Engram. |
| Vendor trees (`_sys/antigravity`, `_sys/claude`, `_sys/codex`) | **PeerHub** | Vendor config/trust/launchers delete entirely. |
| `_sys/cli` | **Engram** | Retained only for `manage.py`, `cleanup.py`, standard shell launchers; all `agy*`/`claude*`/`codex*`, `console_runner.py`, `peerhub.bat` deleted. |
| `_sys/core` | **Engram** | Generic dispatch/env-load/virtualization stays; AI-specific extensions (vendor caches, peer lookups, `.ai` relocators) pruned. |
| Core config files (`_sys/runtimes.json`, `_sys/env.json`, `_sys/dispatch.json`) | **Engram** | Base config stays, scrubbed of AI paths/vars/PeerHub bindings. |
| `_sys/hooks` (`ai_check`, `ctx_end`, `ctx_save`, `memory_compactor`, `raw_log`) | **PeerHub** | AI session/context lifecycle mechanisms — deleted from Engram. |
| `_sys/checks` | **Engram** | Reduced to generic env/portability hygiene; AI-governance checks (`check_contracts.py`, `saturation_scan`, etc.) deleted. |
| Docs, data, templates | **Engram** | Only generic portable-workspace docs/skeletons retained; AI/governance history, `.ai` templates, consensus docs deleted. |
| `_sys/tests` | **Engram** | Generic testing retained; the stale boundary test protecting vendor CLI launchers (`test_contracts.py:96-111`) rewritten to a zero-AI-ownership contract. |
| `_sys/tools` (`bat`/`jq`/`rg`/`fzf`/etc.) | **Engram** | Portable dev utilities stay. |

## 2. Migration ledger

### 2.1 Aggregate AI-CLI discovery / live installation observations

- **Already in PeerHub:** named-target resolution + readiness probing.
- **Missing:** aggregate host discovery ("scan and list all installed AI
  CLIs").
- **BLOCKED** on Gate 2's discovery-sweep design + implementation.

### 2.2 Required declarative fields from `_sys/ai/peers.json`

- **Already in PeerHub:** Phase 1 Manifest Schema V2 already defines the
  target fields (`adapter_id`, `peer_kind`, `execution.executable`,
  `env_policy`).
- **Exact fields to migrate** (terminal-verified against the real file):
  `node_ids` (→ `peer_kind`), `npm_package` / `native_binary.{bin_name,
  win_exe,install_subdir}` (canonical package/binary identity for
  autodetection/installation), `env_vars` (→ `env_policy`), and
  `local_settings` (specifically the `permissions` injection that safely
  constrains the CLI) — **note:** the hardcoded wrapper-script paths inside
  `local_settings` must be rewritten, not copied verbatim, since those
  wrapper scripts are deleted in Increment 1.
- **Explicitly excluded (no migration, verified against the real file):**
  `host_junction`, `project_junction`, `workspace.{shadow_subdir,
  junction_name}`, `host_app` (hardcoded `LOCALAPPDATA` launch path),
  `cleanup`, `relocate` — all machine-specific paths / host trust /
  transient state.

### 2.3 Ratified lessons/directives still current

- **Already in PeerHub:** native lesson lifecycle
  (`peerhub lesson propose|approve|activate|retire`, `peerhub/governance/
  lessons.py`, persisted in `.peerhub/peerhub.sqlite3`).
- **NOT BLOCKED** — active directives from `_sys/ai/user-directives.md` can
  be injected directly into PeerHub's database.

### 2.4 Required adapter/statusline behavior

- **Already in PeerHub:** native adapter registry
  (`peerhub/adapters/registry.py`) and `peerhub statusline` command,
  state under `.peerhub/statusline`.
- **NOT BLOCKED.**

## 3. Phased deletion + release plan

Three of four increments have **no PeerHub dependency** and can start
immediately; only Increment 4 is blocked.

**Increment 1 — strip vendor interactive launchers & governance hooks**
(not blocked): delete `agy.bat`/`claude.bat`/`codex.bat`/
`console_runner.py`/`peer_console.py`/`peerhub.bat`; delete `ai_check.py`/
`ctx_end.py`/`ctx_save.py`/`memory_compactor.py`/`raw_log.py`; rewrite the
stale `test_contracts.py`/`check_contracts.py` boundary to a strict
zero-AI-ownership contract. Verify: `pytest _sys/tests` green after the
rewrite; standard shells still launch normally.

**Increment 2 — prune legacy coordination data & dead code** (not
blocked): delete `_workspace_init_legacy` from `manage.py`; delete AI
workspace templates; delete `_sys/docs/history` AI-governance history,
`_sys/data` AI proposals, stale AI sections of `_sys/docs-v2`; delete root
`PROTOCOL.md`/`CLAUDE.md`/`GEMINI.md`/`AGENTS.md`; rewrite `README.md`/
`CONVENTION.md` to drop all PeerHub/multi-agent claims. Verify: doc-hygiene
checks pass.

**Increment 3 — cleanse core configuration & lifecycles** (not blocked):
strip AI-specific logic from `_sys/core/config.py`/`doctor.py`/
`launcher.py`/`scrubber.py`/`tidy_temp.py`/`virtualizer.py`; strip AI
provider bindings from `_sys/env.json`/`_sys/runtimes.json`/
`_sys/dispatch.json`; strip `.agy`/`.claude` inclusions from the Winget
builders. Verify: `CLEANUP.bat`/`TIDY.bat`/`STATUS.bat` succeed without
erroring on missing AI variables; P-drive mounts cleanly.

**Increment 4 — delete provider metadata and the `_sys/ai` tree**
(**BLOCKED on Gate 2's discovery-sweep design + implementation**): delete
all of `_sys/ai` (including `peers.json`, `orchestration.json`,
`protocol.json`) and the three vendor trees; remove AI runtime install
loops from `provisioner.py`. Verify: Engram provisions a clean workspace
from scratch without attempting to fetch/route AI executables. **Cannot
start until PeerHub can reliably detect and map cc/ag/cx itself.**

### Release scope: Engram vNext

Exclusively a portable-dev-environment lifecycle manager, entirely
oblivious to multi-agent collaboration/routing/consensus.

- `Engram.exe`/`INSTALL.bat` bootstrap the Python environment + portable
  tool payload (`fd`/`rg`/`gh`/`jq`/etc.) — no AI wrappers.
- `engram.cmd` exposes exactly: `install`, `update`, `register` (mount
  P-drive + context menus), `unregister`, `status`, `cleanup`, `tidy`.
- AI interaction: users separately install PeerHub and AI CLIs; Engram just
  provides the clean environment they run in.

### Version identity recommendation

**v3.0.0** (current Winget manifests are at 2.1.0). Reasoning: stripping
the AI orchestration layer, removing interactive wrappers, and breaking the
`hub ask` compatibility layer is a large, backwards-incompatible behavioral
change — a major bump correctly signals the pivot from "autonomous
peer-to-peer workspace" to "portable dev environment" and sets correct
upgrade expectations.

## Status

Design proposal, one voice — not yet critiqued or ratified. Strong citation
accuracy on independent spot-check (the `peers.json` field-by-field claims,
the highest-risk citations in this document, all verified exactly against
the real file). Recommend one critique pass focused on: (a) whether
Increment 1-3's ordering has any hidden dependency the plan missed, (b) the
version-bump recommendation, (c) the unaddressed `local_settings` path-
rewrite detail noted above, before treating this as ratified.
