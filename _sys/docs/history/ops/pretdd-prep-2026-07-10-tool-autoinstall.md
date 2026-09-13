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

## Implementation-level spec (rounds 6-9, same-day follow-up)

Policy above was settled and ratified first (rounds 1-5). This section takes it
down to concrete schemas/signatures for zero-ambiguity TDD handoff. Round
history: ag round-6 elaboration (file layout/schemas/CLI/test-matrix) → cx
round-7 review found 5 gaps (install-mechanism dispatch, checksum provenance,
propose-diff artifact shape, session-boundary reliability, four smaller items) →
ag round-8 conceded all 5 → cx final-call confirmed → cc.fable round-9
ratification found the session-boundary fix ITSELF referenced non-existent
infrastructure (same class of mistake the policy round already guarded against
for `periodic_minutes`) plus 2 more required amendments (npm_peer checksum
semantics, `base_sha256` enforcement) → ag round-10 conceded all → cx final-call
confirmed. Fully unanimous.

### File / module layout

- **New `_sys/core/version_resolver.py`**: `resolve_latest(tool_name, provider,
  current_version) -> dict`, delegating to `_resolve_github()` / `_resolve_npm()`
  / `_resolve_sqlite()` internal helpers.
- **New `_sys/checks/check_tool_updates.py`** (matches `check_versions.py`'s
  location convention): `--json` and `--propose-diff` flags.
- **`_sys/core/provisioner.py` additions**: `ensure_tool(name, orch=None) ->
  dict`, `ensure_peer_cli(peer, orch=None) -> dict`, both returning
  `{"status": "<enum>", "detail": "..."}`.
- **Install dispatch is explicit by mechanism** (cx's correction of ag's
  original single-shared-helper idea — confirmed `provisioner.py` already
  splits `_install_tools()` (zip/exe) from `_install_ai_peers()` (npm) today):
  dispatch by `install_mechanism: zip_tool | exe_tool | npm_peer`. `zip_tool`/
  `exe_tool` share one `_install_atomic(name, cfg, manifest_path)` helper
  (download/verify/extract/canary/swap). `npm_peer` is a genuinely different,
  separate strategy (see npm semantics below) since `npm install -g` mutates a
  shared `node_modules` in place — no atomic directory swap is possible there.

### `runtimes.json` schema additions

No schema-version bump needed (confirmed: `runtimes.json`'s only top-level keys
today are `_comment`, `runtimes`, `tools` — no version field to bump). New
per-entry fields:
- `discovery_provider`: `"github_releases"` | `"npm"` | `"sqlite_org_page"` |
  `"manual"`.
- `discovery_id`: explicit identity for the discovery provider to query — e.g.
  `"BurntSushi/ripgrep"` (owner/repo) for GitHub, the npm package name for npm.
  Required because deriving identity from the download URL is fragile (URL
  format can change between versions).
- `install_mechanism`: `"zip_tool"` | `"exe_tool"` | `"npm_peer"`.
- `canary`: `{"argv": [...], "timeout_sec": N, "expect_regex": "..."}` (no
  universal `--version` assumption).
- Checksum: bare `<algo>` key per algorithm (`sha256`, `sha3_256`), matching the
  pre-existing `sha512` convention already on `agy`'s entry.

Example (ripgrep — github_releases, sha256):
```json
"ripgrep": {
  "version": "15.1.0",
  "url": "https://github.com/BurntSushi/ripgrep/releases/download/15.1.0/ripgrep-15.1.0-x86_64-pc-windows-msvc.zip",
  "type": "zip",
  "install_mechanism": "zip_tool",
  "discovery_provider": "github_releases",
  "discovery_id": "BurntSushi/ripgrep",
  "sha256": "a81907cb...",
  "canary": {"argv": ["--version"], "timeout_sec": 5, "expect_regex": "^ripgrep 15\\."}
}
```

Example (sqlite — sqlite_org_page, sha3_256):
```json
"sqlite": {
  "version": "3.53.1",
  "url": "https://www.sqlite.org/2026/sqlite-tools-win-x64-3530100.zip",
  "type": "zip",
  "install_mechanism": "zip_tool",
  "discovery_provider": "sqlite_org_page",
  "discovery_id": "sqlite-tools-win-x64",
  "sha3_256": "4b97a2c...",
  "canary": {"argv": ["-version"], "timeout_sec": 5, "expect_regex": "^3\\.\\d+"}
}
```

`ensure-peer-cli <name>` argument mapping (cx's gap, ag conceded must be
explicit, not implicit): accepts the human-facing tool names `claude`/`codex`/
`agy`, internally mapped to this project's node_ids `cc`/`cx`/`ag`
respectively — state this mapping explicitly in the implementation, not left
for a TDD implementer to guess which form is accepted.

Extras (e.g. oh-my-posh themes, handled by `_install_extra()` today) must be
staged as part of the SAME atomic-swap candidate directory as the main binary —
not copied in as a separate step after the swap completes (which would create a
window where the swap "succeeded" but extras are missing, or extras land but
the main swap then rolls back, leaving orphans).

### `.install_manifest.json` schema

Lives at `_sys/tools/<name>/.install_manifest.json`. Full example (ripgrep):
```json
{
  "tool": "ripgrep",
  "declared_version": "15.1.0",
  "url": "https://github.com/BurntSushi/ripgrep/releases/download/15.1.0/ripgrep-15.1.0-x86_64-pc-windows-msvc.zip",
  "checksum_algo": "sha256",
  "checksum_value": "a81907cb...",
  "checksum_source": "declared",
  "checksum_verified": true,
  "installed_bytes_hash": "c4d5e6f7...",
  "canary_command": ["ripgrep.exe", "--version"],
  "canary_output": "ripgrep 15.1.0\n",
  "installed_at": "2026-07-10T12:00:00Z",
  "source_config_hash": "f1e2d3c4..."
}
```

`checksum_source`/`checksum_verified` (cx's addition, required — without this a
future reader can't distinguish "verified against a known-good hash" from "just
recorded whatever bytes we got", which matters for the TOFU-shrinking optional
amendment): `checksum_source` is `"declared"` (from `runtimes.json`),
`"release_asset"` (from a GitHub release's own published checksum),
`"registry_integrity"` (npm's own packument integrity field — npm_peer only),
or `"computed_tls_trust"` (no verifiable source existed; the hash is
drift-evidence only). `checksum_verified` is `true` only for the first three.

`source_config_hash` is scoped to just this tool's own `runtimes.json` entry
(not the whole file — an unrelated edit elsewhere in runtimes.json must not
spuriously invalidate every other tool's manifest), computed over a
**canonically serialized** form (sorted keys, stable separators) so
semantically-identical entries with different key ordering hash identically
(fable's note, ag included).

### npm_peer install semantics (fable's required amendment)

The `install_mechanism: npm_peer` path (claude/codex) has distinct rules from
zip/exe tools:
1. **Always install pinned** to the exact version declared in `runtimes.json`
   (`npm install -g pkg@x.y.z`) — never bare `@latest`, or the manifest's
   `declared_version` field would be fiction.
2. **Checksum = npm registry's own `integrity` field** (npm's sha512) from the
   package's packument, recorded with `checksum_source: "registry_integrity"`
   and `checksum_verified: true` (npm itself already enforces this during
   install).
3. **No atomic swap is possible** — `npm install -g` mutates the shared
   `node_modules` in place. A failed bootstrap must, at minimum, leave the tool
   re-detectable as "missing/broken" afterward (never falsely reporting
   "installed"). Acceptable given peer CLIs are bootstrap-only scope, but must
   be written down explicitly.
4. **Node.js bootstrap dependency ordering** (fable's separate required
   amendment): `ensure-peer-cli claude` on a clean machine must check/ensure
   the portable Node.js runtime exists first, or fail with an explicit
   "install nodejs-lts first" message — not discover the gap mid-install.

### `check_tool_updates.py --propose-diff` artifact (cx's gap, made concrete)

Read-only — **never** touches the real `_sys/runtimes.json`. Writes to
`_archive/tool-updates/<UTC-timestamp>/`:
- `proposal.json` — structured discovery summary.
- `runtimes.proposed.json` — full proposed replacement file (for direct diffing
  against the real one).
- `runtimes.diff` — unified diff text.

Stdout JSON (also used for `--json`):
```json
{
  "artifact_dir": "_archive/tool-updates/2026-07-10T12-00-00Z/",
  "base_sha256": "<hash of current runtimes.json at proposal time>",
  "updates_discovered": [
    {"tool": "ripgrep", "current_version": "15.1.0", "latest_version": "15.2.0",
     "url": "https://...", "checksum_algo": "sha256", "checksum_value": "..."}
  ],
  "up_to_date": ["bat", "delta"],
  "rate_limited": ["gh"],
  "errors": []
}
```

**`base_sha256` must be ENFORCED at apply time, not just recorded** (fable's
required amendment — "recording without checking is provenance theater"): the
apply path (governed merge of a version-bump diff) must reject the proposal if
the current `runtimes.json`'s hash no longer matches the proposal's recorded
`base_sha256` — i.e. someone edited `runtimes.json` in the meantime and this is
now a stale proposal.

`rate_limited` entries come from `discovery_provider`s that hit GitHub's
60/hour unauthenticated cap — classified as `discovery_unavailable`
internally, never silently folded into `up_to_date` (DIR-004: absence of
evidence is not evidence of "no update").

`_archive/tool-updates/<timestamp>/` needs a retention policy (fable's note,
ag included) — assign it a scrubber tier or a retention-count limit; it
accumulates forever otherwise.

### CLI interfaces, exact

- `check_tool_updates.py [--json] [--propose-diff]`.
- `python _sys/core/provisioner.py ensure-tool <name>` /
  `ensure-peer-cli <claude|codex|agy>`. Exit codes: `0` (already current, or
  installed/updated successfully), `1` (network failure), `2` (checksum
  mismatch), `3` (deferred — in-use at attempt time, see retry mechanism
  below).
- `--repair-missing`: opt-in flag added to `_sys/checks/check_cli_reality.py`
  (confirmed today's `main()` already uses simple `if "--flag" in argv:`
  string-checks, not argparse — `--repair-missing` follows the same existing
  style). When set, a reported-missing peer/tool maps to
  `ensure_tool()`/`ensure_peer_cli()`. `real_binary()` itself is never touched
  by this — it stays the pure resolver `main()` already calls.

### Deferred-install retry mechanism (CORRECTED — this is the important fix)

An earlier draft of this section proposed retrying a deferred (file-locked)
swap "at the next session's `on_session_start`" — **this was wrong and has been
removed**: `cc.fable` and independently `cc` verified `_sys/hooks/` contains
only `ai_check.py, collab_log.py, ctx_end.py, ctx_save.py, memory_compactor.py,
raw_log.py` — there is no session-start handler anywhere in this codebase. This
was the exact "build on infrastructure that doesn't exist" mistake the
Scheduling section above already avoided for `self_care.py`'s
`periodic_minutes` (confirmed `0`, unwired).

**Corrected mechanism**: `ensure-tool --retry-deferred` is the PRIMARY retry
path (an explicit command a human or future hook can invoke), plus **lazy
opportunistic draining** — any subsequent `ensure-tool`/`ensure-peer-cli`
invocation, for any tool, first drains the deferred-retry list before doing its
own work. If session-boundary wiring is wanted later, it is new, separately
scoped work (name the exact hook, verify it actually fires) — not assumed
infrastructure.

### TDD test matrix (checklist)

`version_resolver.py`:
- [ ] github_releases: 200 OK returns version/URL.
- [ ] github_releases: 403 rate-limit returns `discovery_unavailable`, not
      "no update".
- [ ] github_releases: matching ETag (304) returns cached value, no re-download.
- [ ] sqlite_org_page: correctly parses the HTML-comment CSV for version/URL/
      sha3 hash.
- [ ] npm: 200 OK returns latest version (discovery only, no apply path).
- [ ] all providers: network timeout/error handled without crashing, classified
      distinctly from rate-limit.

`provisioner.py` (`ensure_tool`/`ensure_peer_cli`/`_install_atomic`):
- [ ] manifest-vs-runtimes.json version mismatch correctly triggers the update
      path (the confirmed root gap this whole feature fixes).
- [ ] checksum match proceeds; mismatch deletes temp dir, aborts, leaves active
      install untouched.
- [ ] TLS-trust fallback completes when no hash is declared/discoverable;
      records `checksum_source: "computed_tls_trust"`,
      `checksum_verified: false`.
- [ ] atomic swap success: canary passes, `_old` rotated (max 1-2
      generations), temp becomes active.
- [ ] canary failure: temp deleted, active untouched, returns error (not a
      partial state).
- [ ] Windows file-locked rename failure: leaves active untouched, returns
      `in_use_retry_at_session_boundary`/status 3, recorded for
      `--retry-deferred`.
- [ ] `--retry-deferred` successfully re-attempts a previously-deferred update
      once the lock is gone.
- [ ] lazy draining: an unrelated `ensure-tool` call drains a pending deferred
      entry for a DIFFERENT tool before doing its own work.
- [ ] governance gate: aborts to manual/governed path if URL != tracked entry,
      OR checksum declared-but-mismatched, OR redirect is cross-host, OR a 404
      would otherwise silently fall back to "latest".
- [ ] `npm_peer`: always installs `pkg@declared_version`, never bare `@latest`.
- [ ] `npm_peer`: checksum recorded as `registry_integrity` from the packument,
      `checksum_verified: true`.
- [ ] `npm_peer`: failed bootstrap leaves the tool detectable as missing/broken,
      not falsely "installed".
- [ ] `npm_peer`: `ensure-peer-cli claude` fails with an explicit
      "install nodejs-lts first" message if Node.js isn't present yet, rather
      than failing deep inside npm.
- [ ] `source_config_hash` uses canonical (sorted-key) serialization — two
      differently-key-ordered but semantically identical entries hash the
      same.

`check_tool_updates.py`:
- [ ] `--propose-diff` never writes to the real `runtimes.json`.
- [ ] artifact directory contains all 3 files (`proposal.json`,
      `runtimes.proposed.json`, `runtimes.diff`) with correct `base_sha256`.
- [ ] apply path rejects a proposal whose `base_sha256` no longer matches the
      current `runtimes.json` (stale-proposal rejection).

`check_cli_reality.py`:
- [ ] `real_binary()` NEVER triggers any install path under any circumstance —
      regression guard for the architectural read-only rule.
- [ ] `--repair-missing` correctly routes a reported-missing peer/tool to
      `ensure_tool`/`ensure_peer_cli`.

## Status

Unanimous across 10 rounds (5 policy + 5 implementation-elaboration,
ag+cx+cc.fable), TDD-ready. Nothing implemented yet — this doc is the complete
spec for the next TDD pass.
