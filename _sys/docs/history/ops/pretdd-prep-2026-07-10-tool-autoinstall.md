# Pre-TDD Design Spec (2026-07-10): auto-install + auto-update for tools & peer CLIs

Five-round exhaustive discussion (ag proposes → cx cross-reviews/corrects → ag
concedes → cc.fable ratifies + adds 4 required amendments + 1 optional → ag acks
all 5). Unanimous. Nothing here has been implemented — this is the spec to build
against in the next TDD pass.

Round history: ag round-1 proposal (9-part design covering scope/discovery/trigger/
apply/rollback/verify/schedule/governance/cleanup) → cc spot-checked 4 claims against
live code (found 3 confirmed issues + 1 real code find: a dead, never-checked
`sha512` field already in `runtimes.json`) → cx round-2 independent review (confirmed
cc's findings, corrected agy's and sqlite's real distribution mechanisms, and raised
the one significant architectural objection: `real_binary()` must stay read-only) →
ag round-3 conceded all corrections unanimously → cc.fable round-4 ratification found
4 more gaps neither peer named (Windows file-locking, GitHub rate limits, SHA3
support, npm bootstrap ordering) + 1 optional (TOFU auto-pinning) → ag round-5 acked
all 5.

## Current infrastructure (confirmed by direct code read, not assumption)

- `_sys/runtimes.json`: manually-maintained pinned version+URL registry.
  `runtimes.{python,nodejs,git,vscode,pwsh,ffmpeg}` (`{version, url}`) plus
  `runtimes.tools.{ripgrep,bat,fd,delta,fzf,jq,gh,sqlite,agy,...}` (`{version, url,
  type, bin, extras}`). At least one entry (`agy`) already declares an unused
  `sha512` field.
- `_sys/core/provisioner.py`'s `deploy(ctx)` (reached via INSTALL.bat →
  dispatch.bat install → setup.py) does the actual one-time install:
  `_install_tools()` downloads/extracts each `runtimes.json` tool entry into
  `_sys/tools/<name>/`; `_install_ai_peers()` does `npm install -g <pkg>` for
  claude/codex into `_sys/env/nodejs/npm-global/`. **Confirmed root gap**: the
  "already installed" check is `sentinel.exists()` only — no version comparison
  against `runtimes.json`'s declared version, and zero checksum/hash verification
  anywhere in the file (grepped, zero matches for sha256/sha512/hashlib).
- `_sys/checks/check_versions.py` (already has T16's real JSON-contract validator)
  currently asks an LLM to guess the latest version of 8 tools and writes the
  reply for a human to manually read and update `runtimes.json` — purely advisory,
  not measured (contradicts this project's own DIR-004), and doesn't act on the
  result at all.
- `_sys/core/scrubber.py` exists; Tier 3 already removes `_sys/tools/*` (except
  `apps`) on a full reset. Tier 2 (soft cleanup) does not yet handle
  update-rollback artifacts.
- `check_cli_reality.py`'s `real_binary(peer, orch=None)` (shipped 2026-07-09 as
  T15) already has a `shutil.which()` fallback for a bare command name — the
  nearest existing "tool not found" signal in the codebase, but this module's own
  docstring states it "NEVER mutates" (drift-report overlay only) and is used
  throughout by other explicitly read-only reconciliation functions.
- `_sys/ai/protocol.json`'s `autonomous_maintenance.schedule.periodic_minutes` is
  currently `0` — there is no real periodic timer today, only session_start/
  session_end hooks.

## Scope

- **Auxiliary tools** (ripgrep, fd, jq, bat, delta, fzf, gh, sqlite, oh-my-posh):
  full auto-install (when missing) + auto-update-discovery.
- **Peer CLIs** (claude, codex, agy): auto-install ONLY when completely missing
  (bootstrap). Auto-UPDATING an already-installed peer CLI mid-session is
  explicitly OUT of automation scope — risk of schema/flag drift during active
  multi-peer collaboration (this project hit real instances of exactly this kind
  of drift in its own check scripts this week). Requires explicit human approval
  at a session boundary, never automated.

## Version discovery (measured, not AI-guessed)

Per-tool mechanism, no generic "check for updates" hand-wave:

| Tool(s) | Mechanism |
|---|---|
| ripgrep, fd, jq, bat, delta, fzf, gh, oh-my-posh | GitHub Releases API (`/repos/{owner}/{repo}/releases/latest`) |
| claude, codex | npm registry API (`registry.npmjs.org/{pkg}/latest`) — **discovery only**, no automatic update apply (bootstrap-only per scope) |
| sqlite | Parse **sqlite.org's own `download.html`** page directly (has a purpose-built HTML-comment CSV: `PRODUCT,VERSION,RELATIVE-URL,SIZE-IN-BYTES,SHA3-HASH`) — NOT a third-party mirror (an earlier draft proposed Scoop's bucket JSON; corrected once the real sqlite.org-direct download source and sqlite.org's own machine-readable block were confirmed) |
| agy | `discovery_provider: manual` — agy is a Google Cloud Storage bucket URL (`storage.googleapis.com/antigravity-public/...`), NOT GitHub Releases; no known public "latest" endpoint exists. Only pinned-URL/checksum *validation* is automated, never latest-discovery |

**GitHub API rate limits** (fable amendment, required): unauthenticated is
60 req/hour/IP. Use conditional requests (ETag/If-None-Match); prefer
authenticated `gh api` when `gh` is available and logged in; classify a
rate-limited response as `discovery_unavailable` — never silently as "no update
available" (that would itself be an unmeasured/guessed claim, DIR-004).

## On-demand install trigger

**`real_binary()` stays strictly read-only** (cx's architectural objection, ag
conceded as "airtight"): it's the pure path resolver used throughout
`check_cli_reality.py`'s explicitly-documented "never mutates" reconciliation
module. Auto-install must live in a separate, explicit path: a new `provisioner
ensure-tool <name>` / `ensure-peer-cli <peer>` command, or an opt-in
`--repair-missing` flag on whatever check invokes it. Default checks *report*
"missing", they never silently mutate.

Mechanical-recovery conditions for a missing-but-pinned tool (all must hold, or
it escalates to governed/manual — see Governance below):
- the URL used is exactly `runtimes.json`'s tracked entry (no substitution)
- checksum is verified when one is declared
- any redirect stays same-host
- no silent fallback to "latest" on a 404/gone response

## Update application

Fixes the confirmed provisioner.py gap via a new per-tool
`_sys/tools/<name>/.install_manifest.json` recording: `tool`, `declared_version`,
`url`, checksum algorithm/value, installed-bytes hash, canary command/output,
`installed_at`, source-config hash. Provisioner compares manifest vs
`runtimes.json`'s declared version — `sentinel.exists()` alone is no longer
sufficient.

New-version discovery produces a *proposed* `runtimes.json` diff.
`runtimes.json` is treated as governed (same tier as `protocol.json`) — a
version-bump diff requires peer consensus before merging. Once merged, the
provisioner detects manifest != declared version and applies the update through
the same atomic-swap path as any install.

**Scheduling** (revised down from ag's original 24h-cadence-via-self_care.py
proposal after cx found `periodic_minutes: 0` means no real timer exists yet):
start with a manual `check_tool_updates.py --json / --propose-diff` command. A
session-hook-based, TTL-gated, non-blocking proposal is a possible *later*
increment — do not build the design around infrastructure that isn't actually
wired up.

## Atomicity / rollback

1. Download new version to a versioned temp dir on the same volume
   (`_sys/tools/<name>_v<new>_tmp`).
2. Verify checksum (see Verification below).
3. Extract.
4. Run the tool's declared canary command (no universal `--version` assumption —
   some tools may not support it safely; canary config is per-tool: argv, timeout,
   expected-output regex) with a timeout.
5. On success: rename active dir → `_old`, rename temp → active.
6. On any failure at any step: delete temp, abort, leave the existing install
   completely untouched.
7. Keep at most 1-2 `_old` generations for manual rollback.

**Windows file-locking is the common case, not an edge case** (fable amendment,
required): the rename-to-`_old` step will routinely hit an EACCES/sharing
violation — `oh-my-posh` is loaded by every open PowerShell prompt, `gh`/`rg`/`fzf`
run intermittently. Add a distinct outcome `in_use_retry_at_session_boundary`:
detect this specific rename failure, leave everything untouched, surface as
**deferred**, not failed. Without this, the most frequently-updated tool on the
list would be effectively un-updatable and every attempt would look like a
generic error.

**npm bootstrap dependency ordering** (fable amendment, required): claude/codex
install via npm, which needs the portable Node.js runtime to exist first.
`ensure-peer-cli claude` on a clean machine must check/ensure the Node.js
dependency first, or fail with an explicit "install nodejs-lts first" message —
not discover the gap mid-install.

## Verification

`runtimes.json`'s own declared checksum fields (e.g. agy's existing `sha512`,
confirmed never actually checked by `provisioner.py` today) are **authoritative
and checked first** — this is wiring up an already-declared-but-dead field, not
inventing new work. GitHub-release-asset-checksum discovery is only a fallback
for entries that don't have a declared hash yet. If neither exists: TLS-trust,
with the downloaded hash recorded in the manifest as drift-evidence only (not
treated as first-install trust).

**SHA3 support must be explicit** (fable amendment, required): sqlite.org's CSV
block publishes SHA3 hashes. The manifest's generic "checksum algorithm/value"
field must have an implementation that actually handles `sha3_256` (Python's
`hashlib` supports it natively) alongside sha256/sha512 — include a sqlite-shaped
case in the TDD test matrix, don't assume sha256/512 coverage is sufficient.

**Optional, non-blocking** (fable amendment, ag acked as worth including): when
an unpinned entry (no declared checksum, none discoverable) is installed under
the TLS-trust path, auto-propose a `runtimes.json` checksum-pin diff from the
recorded hash — governed/consensus-gated like any other version bump. This
shrinks the unpinned/TOFU (trust-on-first-use) surface monotonically over time
instead of leaving it static.

## Governance

"Missing pinned tool install = exempt from consensus" is **conditional**, not
unconditional (cx's tightening, ag agreed): only exempt when all four
mechanical-recovery conditions above hold. If the URL has gone stale, redirects
cross-host, a checksum mismatches, or the source is unavailable/serving
something else — it escalates to governed/manual recovery, never silent
auto-repair, regardless of how long ago the pin was originally approved.

"Auto-updating" (bumping a pinned version to a newer one) is **always
governed** — routes through this project's standard peer-consensus process
before the `runtimes.json` diff merges, same as any other config change.

## Cleanup interconnection

`_sys/core/scrubber.py`'s Tier 3 already removes `_sys/tools/*` (except `apps`)
on a full reset — covers rollback artifacts implicitly. Tier 2 (soft cleanup)
should be **expanded** (confirmed new work, not already present) to purge
`_sys/tools/*_old` rollback directories specifically — never active tool
directories.

## Status

Unanimous, TDD-ready. Nothing implemented yet — this doc is the spec for the
next TDD pass.
