# Engram Diet & Release Plan — FIFTH REVISION (ag.deepthink, 2026-09-02)

**⚠️ TERMINAL RE-PERSIST NOTE (2026-09-02, after the fifth critique):** the
version of this document first committed contained a terminal-introduced
error, not an ag fabrication — the terminal summarized ag's actual raw
response into prose instead of reproducing its real JSON Schema, migration
table, and acceptance-matrix rows. cx's fifth critique correctly flagged
those sections as "claims artifacts exist that are absent from the
persisted file." **This version restores ag's actual raw content
verbatim** for those sections. cx's other findings — the deferred-state
migration rule incorrectly discarding Engram-owned AI-CLI retry state, the
established state-path convention being `_sys/data/state` not
`_sys/state` (verified: `provisioner.py:1050-1052`, `manage.py:38-40`),
several "keep-generic-only" dispositions still lacking exact branch-level
detail, `_sys/hooks/**` never actually dispositioned, and the uninstall
section still lacking real command-route/journal/receipt detail — are
**real content gaps in ag's own response**, not a persistence error, and
remain open; they are annotated inline below rather than silently fixed,
since fixing them is legitimate peer work for the next round, not a
transcription problem.

Final-correction pass incorporating all 9 items from the fourth critique
(`2026-09-02_engram-diet-plan-v4-critique.md`). Supersedes
`2026-09-02_engram-diet-plan-v4.md`.

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
| Engram (CLI commands) | Generic tools retained | Engram generic tools | Increment A |
| Engram (core config) | Base config retained, scrubbed | Scrubbed `env.json`/`dispatch.json` | Increment B |
| PeerHub (hooks) | `PreToolUse` hook registration in `settings.json` deleted | DELETED (replaced by CI gate) | Increment A |
| Engram (hygiene checks) | Generic checks retained, AI checks deleted | Engram generic checks | Increment C |
| Engram (templates) | `local.config.bat.template` kept+narrowed | Engram repository data | Increment C |
| Engram (testing) | Generic tests retained, AI tests deleted | Engram generic tests | A-D |
| Engram (boundary) | `check_contracts.py` → neutral CI checker | Engram generic CI | Increment A |
| Engram (uninstall) | Explicit `uninstall` command added | Engram lifecycle scripts | Increment A |

**[OPEN — cx fifth critique]** `_sys/hooks/**` (`ai_check.py`,
`ctx_end.py`, `ctx_save.py`, `memory_compactor.py`, `raw_log.py`, and
their `.bat` entrypoints) is not represented as its own row — only the
Claude `PreToolUse` *registration* is dispositioned. This tree needs its
own explicit delete list and matching test deletions/rewrites in the next
round.

## 2. Tool catalog specification (`_sys/tool-catalog.v1.json`)

SSOT for tool installation, replacing `peers.json` and the tool-metadata
portion of `runtimes.json`.

### Schema (JSON Schema, ag's actual draft)
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

**[OPEN — cx fifth critique]** this schema is real progress over v4's
opaque fields, but is still not fully ratifiable: no discriminated
variants for npm/executable/archive/SFX/pip installation mechanisms (the
real installer distinguishes archive layouts, strip counts, and preserved
paths per-mechanism at `provisioner.py:469-530`), no alias-uniqueness
rule, no install-manifest/CAS canonicalization for `rollback_data` (still
just an untyped string — real npm rollback derives the prior version from
the install manifest, `provisioner.py:920-934`), and native-binary
identity fields (`bin_name`/`win_exe` distinct from generic `install.bin`,
real at `peers.json:110-114`) aren't fully represented.

### Migration mapping (ag's actual table)
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

Terminal-verified against the real `runtimes.json` `agy` entry
(lines 177-193): every field this table claims exists in the real source
does exist, with the real values matching (`url`, `type`, `bin`,
`sha512`, `install_subdir`, `discovery_provider`, `install_mechanism`,
`canary.{argv,timeout_sec,expect_regex}`).

### Consumer dispositions
- `ensure_peer_cli()`: rewritten to resolve top-level `tool_id` AND the new `aliases` array (replacing `node_ids`).
- `check_tool_updates.py` / `doctor.py`: updated to read the new catalog. The tool-metadata subset of `runtimes.json` is deleted.
- `_sys/core/provisioner.py`: The `deploy()` logic that unconditionally creates `_sys/ai/common/{agents,skills,mcp}` is **DELETED**. Claude/Codex-specific launcher-repair logic inside `provisioner.py` is **DELETED**.
- `_sys/core/launcher.py`: Increment B. Keep-generic-behavior-only (VS Code/shell launch, base env). **Delete** `peers.json` read, per-peer env var injection, provider relocation patching, and peer host app launching (pure Python logic removal). *(Terminal-verified concrete: matches real logic at `launcher.py:52-79,104-122,158-163,206-255`.)*
- `_sys/core/virtualizer.py`: Increment B. Keep-generic-behavior-only. **Delete** `peers.json` dependency and provider-specific mount logic. **[OPEN — cx fifth critique]** still too vague: must name deleting `_load_peers()` and the entire legacy fallback at `virtualizer.py:13-20,349-400` specifically, while retaining the managed-links registry path.
- `_sys/core/scrubber.py`: Increment B. Keep-generic-behavior-only. **Delete** `peers.json`-driven per-peer cleanup logic. **[OPEN]** must name deleting `_load_peers()` and per-peer cleanup at `scrubber.py:48-55,269-281` and removing the now-obsolete `peers` parameter from cleanup-tier callers.
- `_sys/cli/manage.py`: Increment B. Keep-generic-behavior-only (`register`, `unregister`, `cleanup`). **Delete** the `workspace-init` branch entirely (`manage.py:104-164`), which read `peers.json` and created `.ai`/junctions. *(Terminal-verified: `manage.py:104` exactly matches `_workspace_init_legacy`'s real signature.)*
- `_sys/core/config.py`: Increment B. Keep-generic-behavior-only. **Delete** `peers.json` parsing and AI-specific configuration structures. **[OPEN]** must name removing both `get_peers_config()` AND `get_orchestration_config()` (`config.py:159-169`) — v5 only named the former.
- `_sys/tests/unit/test_config_validator.py` and `_sys/tests/unit/test_check_contracts_gate.py` (representing `check_config.py`/`check_contracts.py`): Increment A & C. **[OPEN]** `check_config.py` is overwhelmingly an AI-orchestration validator (loads protocol/orchestration/peers/routing/lifecycle configs at `check_config.py:39-61`, validates peer shapes at `:341-349`) — the next round must state whether the file is deleted outright or replaced with a named, genuinely generic validator, not just "keep-generic-only."
- `_sys/cli/agy_entry.py`: Increment A. **Delete-entirely**.

### Deferred-state migration — **[OPEN, cx fifth critique found this wrong]**
Original text: `.ai/tool_deferred_retries.json` migrates to
`_sys/state/deferred_tools.json` on first load, filtering out any AI-CLI
key (now PeerHub-owned) and carrying forward only generic-tool keys.

**This is incorrect and must be fixed next round.** Engram still owns
AI-CLI *installation/update* lifecycle (v5 itself retains and rewrites
`ensure_peer_cli()` for exactly this) — only *invocation/collaboration/
autodetection* moves to PeerHub. Dropping deferred Claude/Codex/Agy
install-retry records would lose real, meaningful Engram-owned state:
verified real deferred entries carry `kind`, `name`, `version`,
`attempts`, `first_failed_at`/`last_failed_at`, `last_exit_code`
(`provisioner.py:879-895`). Correct migration: canonicalize legacy
`peer:<name-or-alias>` keys through the new catalog's aliases, convert to
the catalog `tool_id` under a generic install-retry kind, preserve
version/attempts/timestamps/exit-code, and drop only entries for products
explicitly removed from the catalog — not every AI CLI. **Destination
path is also wrong**: `_sys/state/deferred_tools.json` doesn't match the
established convention — verified real state lives at `_sys/data/state`
(`provisioner.py:1050-1052`, `manage.py:38-40`), so the natural
destination is `_sys/data/state/deferred_tools.json` unless a deliberate
new state-root migration is separately designed.

## 3. Core subsystem dispositions

**3.1 Version SSOT**: `_sys/core/version.json`, schema
`{"version": "string", "build_date": "string", "channel": "string"}`,
written once per build by the Engram release pipeline. Readers:
`engram.cmd`, the authoritative builder `tools/winget/build_package.py`,
all manifests. Builder-level version overrides are prohibited; a new
explicitly-defined test `_sys/tests/unit/test_version_ssot.py` will
assert every reader's output matches the JSON SSOT exactly.

**3.2 Claude hook**: Removed entirely from Increment A (both the
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

**3.5 Uninstall semantics — [OPEN, cx fifth critique: still not concrete
enough]**: Reinstated from the third revision at the *principle* level:
AI CLIs Engram installed do not survive an Engram uninstall; the
`_sys/env/nodejs/npm-global` subtree is deleted wholesale. **But the next
round must actually instantiate**: the `engram uninstall` command route
(current `engram.cmd`'s dispatch table at `engram.cmd:32-47` has no
uninstall route today), the implementation file/function, an exact
owned-artifact inventory, a real receipt/journal schema with named
states, registered-vs-unregistered handling, recoverable/nonrecoverable
failure behavior, idempotent-retry semantics, and a concrete
clean-install→register→uninstall test with failure injection — a proposed
test filename (`test_uninstall_semantics.py`) is not itself the design.

**3.6 Gate-7 builder/validator ambiguity resolved**:
- **Authoritative builder**: `tools/winget/build_package.py` is selected as the ONE authoritative builder.
- **Disposition**: `tools/winget/build_winget_package.py` is DELETED after folding in any unique behavior.
- **Validation**: Gate 7 implements a deterministic internal validator via a new test `_sys/tests/unit/test_winget_manifests.py` that statically verifies the Winget schema. The `winget validate` command is explicitly relegated to non-blocking telemetry (a separately-reported external result), preventing its unreliable exit codes from blocking Gate 7. *(Terminal note: this direction fits real code — `build_package.py:401-440,483-555` already has internal validation plus a separately-invoked Winget CLI path.)*

**3.7 Final boundary invariant**: "Engram may own declarative
package-install metadata for independently installable tools, but owns no
provider invocation, trust, profile, routing, collaboration, health,
session, quota, governance, or PeerHub policy."

## 4. Instantiated data ledgers

### 4.1 Directives (`peerhub.governance-directive.v1`)

**Explicit precondition**: Increment D's directive-deletion step must
explicitly depend on the `peerhub.governance-directive.v1` service
actually existing and having produced verified migration receipts for all
6 directives BEFORE `_sys/ai/user-directives.md` is deleted.

Digests (verified identical to the established real values across two
independent recomputations — the terminal's and cx's — no fabrication):

- **DIR-001** (ROI-Based Auto-Termination): `sha256:bd6a452ea5af1fab2653055ebdb52ac023d345ac8eaf3565fb23f6262c359f98`.
  `enforcement_bindings`: `[{"consumer_name": "PeerHub/Orchestrator", "implementation_status": "PENDING", "evidence_refs": ["no ROI-gate/EXHAUSTIVE_COMPLETE consumer found in peerhub source"]}]`.
- **DIR-002** (Minimum Non-Interactive Permissions): `sha256:6a68da23ad2d663acbb64bda3e45b565e199c7df480fcfb6011e9b023cab79fb`.
  `enforcement_bindings`: `[{"consumer_name": "cc", "implementation_status": "PENDING", "evidence_refs": ["no measured per-adapter binding yet"]}, {"consumer_name": "cx", "implementation_status": "PENDING", "evidence_refs": ["real PeerHub Codex adapter invocation (codex.cmd exec [resume] --json ...) supplies no sandbox flag and inherits config.toml, invalidating the old ADVISORY_ONLY evidence based on the retired launcher"]}]`.
- **DIR-003** (`test_contracts.py` update rule): `sha256:9bb8df7f009ce6a572e9d9d5d9f9574a91ab9b1f1449b1d779e92909b193eac2`.
  `enforcement_bindings`: `[]` — **RETIRED at cutover**, specific to `hub.py`'s now-deleted API.
- **DIR-004** (Measured-Only Claims): `sha256:47f495f76342681af8e7cccf76e09be88e37114e3138ece07fe14fbaa8880777`.
  `enforcement_bindings`: `[{"consumer_name": "peerhub.dispatch.capability", "implementation_status": "PENDING", "evidence_refs": ["one bounded evidence-source-tag subset exists, not a universal validator for every claim type"]}]`.
- **DIR-005** (Smartest-Model Final Arbiter): `sha256:c871314e6f273ada6a56b8124466c56e301fadfb7cb8cc2e3eeb2a2f9cc9c934`.
  `enforcement_bindings`: `[{"consumer_name": "FinalArbiterPolicy/arbiter_review.py", "implementation_status": "PENDING", "evidence_refs": ["real partial parity exists; high-risk triggering + scoped-override semantics unimplemented"]}]`.
- **DIR-006** (Unanimous Consensus): `sha256:ba5e5423878b59976a434bf2c0428e92e3b7a5f022a327096d816045dfb4a451`.
  `enforcement_bindings`: `[{"consumer_name": "ProposalCoordinator/.peerhub/proposals.json", "implementation_status": "PENDING", "evidence_refs": ["real partial parity exists; direction/tool-call classifier, override phrase, unreachable-peer rule, arbiter handoff not encoded as one standing policy"]}]`.

### 4.2 Statusline disposition

**DELETED OUTRIGHT** — `_sys/ai/common/statusline/**`, the unified
schema/script, Claude/Antigravity adapters, the three provider configs,
and `infra.json` registrations are all permanently deleted from Engram in
Increment A. PeerHub implements its own independent status/telemetry
domain from scratch.

## 5. Per-increment acceptance matrix (ag's actual table)

| Increment | Files changed/deleted | Test commands | Boundary state | Forbidden stale paths |
|---|---|---|---|---|
| **A** | Del: `_sys/cli/{agy,agy.bat,claude,claude.bat,codex,codex.bat,diag,diag.bat}`, `_sys/cli/{agy_entry.py,claude_entry.py,codex_entry.py,console_runner.py,peer_console.py,peerhub.bat}`, `_bat-shim`, `CLAUDE.md`, `GEMINI.md`, `PROTOCOL.md`, `AGENTS.md`, `_sys/ai/common/statusline/**`. Mod: `_sys/cli/launch`, `_sys/cli/manage`, `engram.cmd`, `README.md`, `_sys/claude/project/settings.json` (removing `PreToolUse` hook). | `pytest _sys/tests/unit/l1_core/test_contracts.py` (explicitly rewrite `test_interactive_console_launchers_still_exist` and `test_console_runner_is_a_pure_process_wrapper` assertions). `pytest _sys/tests/unit/test_no_stray_hooks.py` (NEW) | Bounded interim allowlist; hooks detached; statusline eliminated | `_sys/cli/{agy,claude,codex,diag,peerhub}*`, `_bat-shim`, `PROTOCOL.md`/`AGENTS.md`/`CLAUDE.md`/`GEMINI.md`, `_sys/ai/common/statusline` |
| **B** | Mod: `_sys/core/provisioner.py`, `_sys/core/launcher.py`, `_sys/cli/manage.py` (Python logic AI stripping), `_sys/core/virtualizer.py`, `_sys/core/scrubber.py`, `_sys/core/config.py`, `check_tool_updates.py`, `doctor.py`, `env.json`, `dispatch.json`. Add: `_sys/tool-catalog.v1.json`. Del: `peers.json`, `relocator.py`, tool-metadata portion of `runtimes.json`. | `pytest _sys/tests/unit/test_provisioner_autoinstall.py` (rewritten) | Catalog SSOT enforced; `deploy()`'s AI-directory creation eliminated; deep Python AI behavior stripped | `peers.json`, `relocator.py`, root `.ai`, `_sys/ai/common/{agents,skills,mcp}` |
| **C** | Mod: `local.config.bat.template` (narrowed), generic docs, `check_config.py`. Del: AI hygiene checks, AI workspace templates. | existing hygiene test suite | AI-governance decoupled from repository data | AI-governance check scripts, legacy AI workspace templates |
| **D** | Del: `_sys/ai/**`, `_sys/claude/**`, `_sys/codex/**`, `_sys/antigravity/**`. (Precondition: verified migration receipts for all directives). | `pytest _sys/tests/unit/test_system_lifecycle.py _sys/tests/unit/test_no_stray_health_files.py` | Final boundary invariant achieved | `_sys/ai`, `_sys/claude`, `_sys/codex`, `_sys/antigravity`, root `.ai` |
| **Gate 7** | Mod: `tools/winget/build_package.py`, manifest templates. Del: `tools/winget/build_winget_package.py`. | `pytest _sys/tests/unit/test_winget_manifests.py` (NEW), `pytest _sys/tests/unit/test_version_ssot.py` (NEW) | Packaging reflects final boundary; version SSOT enforced | duplicate builder script, legacy AI-metadata manifests |

**[OPEN — cx fifth critique]**: no `--full`/`--all` final-suite gate
command is specified per increment (the real runner exposes `--unit`,
`--scenario`, `--all`, `--full` at `run-tests.bat:4-14,22-33,58-108`); no
clean-install/upgrade/uninstall/package-payload test commands are named
here (they're described narratively in §3.5 but not given as executable
commands in this table); `_sys/hooks/**` doesn't appear in Increment A's
file list despite the ownership matrix assigning its deletion there.

## Status

Fifth revision, one voice (ag) for the substance. **This persisted version
corrects a terminal transcription error from the first commit of this
round** (the actual schema/table/matrix content above is ag's real,
verified-accurate work, not a summary). Genuinely closed this round: DIR-002
correction + directive-service precondition (item 8), Gate 7 builder/
validator resolution (item 9), `manage.py`/`launcher.py`'s concrete AI-logic
removal (part of item 3). **Still open per cx's fifth critique** (annotated
inline above): the deferred-state migration rule (wrong disposition + wrong
path), `virtualizer.py`/`scrubber.py`/`config.py`/`check_config.py`'s
dispositions (too vague), `_sys/hooks/**` (never dispositioned), the
uninstall design (principle-level only, no concrete implementation), and the
per-increment full-suite/lifecycle test commands (not yet named). Needs one
more focused round — the critique is explicit that no new architectural
debate is needed, these are four concrete, scoped document repairs.
