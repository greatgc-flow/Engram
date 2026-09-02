# Third-revision critique (cx.deepthink, fresh session, 2026-09-02)

**Verdict: NOT READY FOR RATIFICATION.** Direction (A-D structure) is
sound and should not be reopened, but 2 of the 3 "fixed" critical blockers
are not actually fixed, `_bat-shim`'s fix is incomplete, and several
sections (notably the "full acceptance matrix") describe artifacts that
aren't actually present in the document.

Terminal verification: `check_contracts.py`'s own docstring confirmed
exit-code semantics exactly as cited (0/1 = allow/fail-open-allow, 2 =
block); all 6 claimed `_bat-shim` consumers (`agy`/`claude`/`codex`/
`diag`/`manage`/`launch`) independently confirmed to each source
`_bat-shim` via `. "$(dirname -- "${BASH_SOURCE[0]}")/_bat-shim"`.

## 1. Critical-blocker re-verification

| Blocker | Result |
|---|---|
| `provisioner.py`/`peers.json` | **NOT FIXED** |
| Claude hook compatibility shim | **NOT SAFE / NOT FIXED** |
| `_bat-shim` deletion | **INCOMPLETE** |

**1.1 provisioner.py**: the proposed `engram.tool-catalog.v1` (just
`tool_id`/`npm_package`/`native_binary`/`env_requirements`) cannot support
real behavior. `ensure_peer_cli()` resolves both top-level keys AND
`node_ids` aliases (no alias field in the new schema); install needs
version/mechanism/canary/source-hash/rollback data that today lives in
`runtimes.json` (a second, un-migrated authority — if it stays there, the
"resolves entirely from the new catalog" claim is false; if it moves,
`check_tool_updates.py` and `doctor.py` both still only read
`runtimes.json` and break); `deploy()` also consumes `enabled`/
`sys_subdir`/native-binary classification for directory creation,
`--skip-ai` decisions, and postcondition checks — none represented in the
new schema; **`deploy()` unconditionally recreates `_sys/ai/common/
{agents,skills,mcp}`**, which would violate Increment D's own
absolute-AI-absence gate even with `peers.json` gone; deferred-tool queue
state lives under root `.ai` and isn't in the stale-artifact boundary.
External callers (`setup.py`, `dispatcher.py`) are fine if the function
signature/result shape is preserved — the gap is the internal consumer
graph, not the external interface.

**1.2 The exit-0 Claude shim is an enforcement bypass, not a
compatibility shim**: `check_contracts.py`'s own documented semantics are
exit 0/1 = allow, exit 2 = block, and a real contract violation exits 2
with an explicit NACK. A shim that unconditionally exits 0 silently turns
every governed contract violation into permission to proceed — the exact
opposite of "compatibility." Also contradicts the ownership matrix's own
claim that the checker becomes a neutral CI boundary checker in the same
increment. Real choices: (1) preserve functional `--hook` enforcement
until Increment D (rename/narrow the checker if needed, but keep it
blocking), or (2) remove the `PreToolUse` registration entirely from
Claude's settings (canonical + all generated copies) in Increment A with
an explicit replacement gate. A no-op shim should never be called
"compatibility."

**1.3 `_bat-shim` has 6 consumers, not 1**: `agy`/`claude`/`codex`/
`diag`/`manage`/`launch` all source it. `manage` specifically is a
backward-compatible wrapper for generic register/unregister/cleanup/
workspace-init behavior — genuinely retained functionality, not slated for
deletion — so it needs its own explicit disposition, not an inference from
"launch is rewritten."

## 2. Ownership matrix: format improved, disposition ambiguity remains

Many "destination artifact-schema" cells are component labels ("Engram
core scripts," "PeerHub provider domain"), not real schemas/paths.
Spot-checks: **AI-CLI lifecycle row FAILS** (maps only `provisioner.py`,
misses `peers.json`/`runtimes.json`/deferred state/updater-status
consumers/CLI alias contracts/provider postconditions — schema is too
small per §1.1). **Hooks row FAILS** (says source is `_sys/hooks`, but the
live `PreToolUse` registration is actually in
`_sys/claude/project/settings.json`; `ctx_end.py` is a separate
session-end subsystem that also invokes the checker as a watchdog —
"PeerHub session lifecycle" isn't a real artifact schema or migration
target). **`local.config.bat.template` row PASSES** (keep-and-narrow is
correct — SUBST/workspace/tool-path sections are generic, only Claude/
Gemini switches are AI-specific, confirmed against the real file).

## 3. The "full acceptance matrix" doesn't exist

Section 7 is one paragraph claiming a per-increment table exists — it has
no rows, files, commands, boundary revisions, expected artifacts, or
rollback predicates. "Named test dispositions for 10 delete + 5 rewrite
files" in Increment A names none of them. "Full `_sys/tests` green" isn't
a concrete command — the real test runner distinguishes unit/lifecycle/
integration/scenario/`--all`/`--full` (with `--full` adding stress
execution) and each increment needs its exact command. The added test
scenarios (clean-install, upgrade, uninstall, etc.) lack fixture
locations/hashes, expected exit codes/poststate, failure-injection points,
a baseline-digest ledger, or a named manifest for payload-equality
checking. The stale-artifact scan only forbids `_sys/ai`/`_sys/claude`,
omitting the equally-real `_sys/codex`/`_sys/antigravity` trees plus root
`.ai`, provider wrappers, and root AI-policy docs.

## 4. Four more high/medium findings

- **HIGH — uninstall semantics contradict AI-CLI survival**: the plan
  promises both underlying-directory teardown and survival of
  Engram-installed AI CLIs, but those CLIs currently live inside Engram's
  own bundled `_sys/env/nodejs/npm-global` — removing the Engram root or
  Node runtime removes or strands them. Needs an explicit choice: retain
  the Node/npm subtree, transfer adopted CLIs elsewhere, or drop the
  survival guarantee.
- **HIGH — directive/statusline "ledgers" are still prose, not
  instantiated data**: §2.2 defines a schema but has zero actual
  `enforcement_bindings[]` entries; the statusline disposition
  ("moved to PeerHub or deleted outright") isn't a decision — the real
  subsystem spans the unified schema/script, Claude/Antigravity adapters,
  three provider configs, and `infra.json` registrations, and needs one
  concrete choice with exact PeerHub targets.
- **HIGH — version SSOT still just a style suggestion**: repeats the exact
  underspecification the second critique already rejected — real
  duplication confirmed across `engram.cmd`, both Winget builders. Needs
  the exact schema, writer/owner, every reader, manifest propagation, and
  whether a builder override is permitted.
- **MEDIUM — command-surface list still incomplete** (bare `help`/
  `version`, `-h`/`/?`/`-v` unaccounted for) and **MEDIUM — root AI
  surfaces missing from the final boundary inventory** (`CLAUDE.md`/
  `GEMINI.md`/`PROTOCOL.md`/`AGENTS.md`/README all still need explicit
  keep/rewrite/delete destinations, not just "rewrite generic docs").

## Digest-note treatment

The 5 deferred directive digests are explicitly NOT a reason to withhold
ratification on their own — mechanical completeness, not an architectural
blocker. Inline them before the migration manifest is finalized either way.

## Overall verdict

**Needs one more focused round. Do not reopen the A-D architecture — that
direction is sound.** Required for the next revision: fully specify the
tool catalog against every real consumer; preserve or atomically detach
the real Claude hook (no exit-0 bypass); enumerate all 6 `_bat-shim`
consumers' dispositions, especially `manage`; include an actual
per-increment acceptance table + executable test matrix; resolve AI-CLI
uninstall survival; turn the directive/statusline ledgers into real
instantiated data; define the version SSOT and the complete stale-artifact
boundary precisely.
