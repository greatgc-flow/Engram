# INSTALL/UPDATE trigger MECE design — 2026-07-10

Unanimous (ag + cx + cc.fable, 5 rounds) design for extending D10's auto-install
infrastructure (commit `03af006`) so that **every** component — including peer
CLIs (claude/codex/agy), not just auxiliary tools — actually gets *updated* in
place, not merely bootstrapped when missing. Triggered by the user's request:
"peer CLIs and every other component need to actually update; consider
INSTALL.bat as the trigger (renaming/refactoring it is fine)."

## Starting state (before this design)

- D10 shipped `version_resolver.py` (github_releases/npm/sqlite_org_page
  discovery) + `check_tool_updates.py --propose-diff` (read-only, writes
  `_archive/tool-updates/<UTC>/` artifacts, never mutates `runtimes.json`) +
  `provisioner.py`'s `ensure_tool()`/`ensure_peer_cli()` (atomic zip/exe swap
  with checksum+canary+rollback; npm-based peer install via `npm install -g`
  with no atomic swap, since npm mutates `node_modules` in place).
- Peer-CLI policy was **bootstrap-only**: `ensure_peer_cli` only ran when a
  peer binary was genuinely absent (`check_cli_reality.py --repair-missing`).
  Nothing drove an update to an *already-installed* component even after
  `runtimes.json`'s declared version was bumped — that required a human to
  manually apply a `--propose-diff` artifact AND separately invoke
  `ensure_tool`/`ensure_peer_cli` by hand.
- `INSTALL.bat` (root) already has its own, older, unrelated self-update
  pattern — but only for Python: on every run it live-queries
  `https://endoflife.date/api/python.json`, and if a newer non-EOL version
  exists, it directly overwrites `runtimes.json`'s `runtimes.python.*` fields
  via inline PowerShell and re-bootstraps — no review step, no diff artifact.
  This predates D10 and exists purely because Python must exist before any
  Python script (including `check_tool_updates.py`) can run.
- `INSTALL.bat` → `_sys/core/dispatch.bat install` → `dispatcher.py`'s
  `install` pipeline (`dispatch.json`: `provision.deploy` → `state.write`) →
  `provisioner.deploy(ctx)`, which still calls the **old**
  `_install_tools()`/`_install_ai_peers()` — naive `sentinel.exists()` /
  `peer_cmd.exists()` checks, no version comparison at all. Re-running
  `INSTALL.bat` today does not update an already-installed tool or peer CLI
  even if `runtimes.json`'s declared version has since changed.

## MECE axes and final unanimous position

### (A) Trigger
**Split trigger.** `INSTALL.bat` = *apply*: every run, unconditionally syncs
local disk to whatever `runtimes.json` currently declares, via `ensure_tool`/
`ensure_peer_cli` looped over every `tools`/`peers` entry. A new `UPDATE.bat`
= *discover*: explicit, opt-in, runs
`_sys\env\python\python.exe _sys\checks\check_tool_updates.py --propose-diff`,
guarded with "run INSTALL first" if the portable Python is absent. Discovery
is network-bound and rate-limit-sensitive (GitHub's 60/hr unauthenticated
cap already a D10 concern) and must never run unconditionally on every boot.

### (B) Scope per component class
- **Aux tools** (`runtimes.json.tools`, ripgrep/bat/fd/delta/fzf/jq/gh/sqlite/
  oh-my-posh) and **peer CLIs** (`peers.json.peers`, claude/codex/agy) both
  get `INSTALL.bat`'s apply-current-declared-version treatment.
- **Base runtimes** (`runtimes.json.runtimes`: python/nodejs/git/vscode/pwsh/
  ffmpeg) are **explicitly out of scope** for this round — each has bespoke
  install logic (7z self-extractor, zip-then-move, direct zip-extract) that
  doesn't cleanly fit today's `zip_tool`/`exe_tool`/`npm_peer`
  `install_mechanism` enum. Queued as a separate future ticket.

### (C) Governance
The review gate stays on the **discover/bump** step (a human accepts an
`UPDATE.bat`-generated diff into `runtimes.json`), never on the **apply**
step (`INSTALL.bat` only ever installs whatever `runtimes.json`, once bumped
via the reviewed path, already declares). This is what preserves
`collab_rate=10`'s `requires_unanimous` for `config_edits` (the bump) while
still letting `INSTALL.bat` freely re-sync disk state to an already-approved
config on every run.

### (D) Mechanism reuse
No — `INSTALL.bat`'s inline PowerShell/`endoflife.date` Python self-update
logic stays a permanent, isolated special case. `version_resolver.py` needs
Python to already exist to run; it cannot be used to discover the Python
version needed to bootstrap Python itself. (Amendment: this special case
must append an audit/drift log line on each live rewrite — see below.)

### (E) Naming / refactor
`INSTALL.bat` keeps its name; its contract shifts from "ensure components
exist" to "ensure components exist **and exactly match** `runtimes.json`".
A new `UPDATE.bat` is added for the discovery/propose-diff flow.

### (F) Failure modes
- Offline: `INSTALL.bat` falls back to the local `runtimes.json` / skips
  Python discovery silently; must never brick an otherwise-working env.
- File locks (Windows) on zip/exe tools: already handled generically by
  `_install_atomic`'s `in_use_retry_at_session_boundary` + deferred-retry.
- npm peer install failures: see the ratified spec below (this was the one
  point of genuine three-way dissent in this discussion).
- Rate limits: avoided entirely by keeping discovery out of `INSTALL.bat`'s
  every-run path.

### (G) Security / trust
Registry/GitHub checksums prove transport integrity only, not upstream
trustworthiness — insufficient grounds to auto-apply a newly *discovered*
version without human review. The `runtimes.json` bump is and remains the
review checkpoint; this is unaffected by how aggressively `INSTALL.bat`
re-applies an already-approved config.

## Implementation plan (ratified)

No new modules. `ensure_tool()` / `ensure_peer_cli()` stay in
`_sys/core/provisioner.py` (an earlier draft proposed splitting into
`tool_manager.py`/`peer_manager.py` — confirmed by direct tree read that
these files do not exist; rejected as fabricated).

1. **`provisioner.deploy()`**: replace `_install_tools()`'s and
   `_install_ai_peers()`'s naive sentinel/peer_cmd existence checks with a
   loop over `runtimes.json.tools` calling `ensure_tool(name, sys_dir=...,
   force=...)` (skipping `install_mechanism == "npm_peer"` entries, handled
   by the peer loop) and a loop over enabled `peers.json.peers` calling
   `ensure_peer_cli(peer_key, sys_dir=..., force=...)`.
2. **`force: bool = False`** added to both `ensure_tool`/`ensure_peer_cli`;
   `True` unconditionally bypasses the already-current fast path. `deploy()`
   passes its existing `--force` flag through (previously had no effect on
   the D10 ensure-path).
3. **Already-current fast path tightened** to three conditions, all must
   hold to skip a reinstall: (a) `manifest.declared_version == cfg.version`,
   (b) `manifest.source_config_hash == _canon_hash(cfg)` (hashing the full
   cfg dict, canonical sorted serialization — catches a URL/checksum/canary
   change with no version bump), (c) the installed binary still physically
   exists on disk (catches manual deletion).
4. **npm peer canary gap fixed**: `ensure_peer_cli`'s npm_peer branch runs
   the declared canary (resolved against the newly-installed npm-global
   `peer_cmd` path) immediately after `npm install -g` succeeds and before
   the manifest is written. Canary failure is a hard error; the manifest is
   not written.
5. **npm peer update-canary-failure rollback** (fable amendment, closes the
   "no atomic swap for npm_peer" gap for the common case): if the canary
   fails during an *update* (an old manifest exists), retry
   `npm install -g pkg@<old manifest.declared_version>` and re-run the
   canary; only hard-fail (`npm_canary_failed`) if that also fails.
6. **npm install failure classification** (the one dissent point, ratified
   by cc.fable under DIR-005 arbiter authority):
   - No stderr string-matching for `EPERM`/`EBUSY`/etc across npm
     versions/platforms — both peers agreed this is too brittle.
   - Any nonzero exit from `npm install -g` gets status
     `npm_install_retry_deferred` — **not** `in_use_retry_at_session_boundary`
     (that name asserts an unmeasured cause; DIR-004 requires status names
     claim only what was actually measured — an nonzero exit, not a lock).
   - A retry-attempt counter is keyed on `(peer_key, declared_version)` and
     stored in the existing `tool_deferred_retries.json` entry:
     `attempts`, `first_failed_at`, `last_failed_at`, `last_exit_code`,
     `declared_version`. Bumping `declared_version` in `runtimes.json` resets
     the counter (a new pin is a new situation, and gives the operator a
     natural fix path — correct the version, counter re-arms).
   - `N = 3` consecutive failed drains (a named, configurable constant, not
     a buried literal — matching this project's existing CHK-CONST pattern)
     before escalating to a hard `npm_install_failed` status. This halts
     auto-retry for that entry until a successful install, a
     `declared_version` change, or explicit `--force`.
7. **Active-peer guard** (fable amendment): before the npm_peer **update**
   path specifically (never needed for bootstrap — nothing can be "in use"
   if the binary is absent), check `.ai/leases.json` (confirmed real: `hub.py`
   already tracks active peer leases with PID/heartbeat/timeout) for an
   active lease on that peer. If active, defer with an honestly-labeled
   `in_use` status — this is the one case in this design where "in use" is
   actually measured (a live lease), not guessed.
8. **INSTALL.bat Python self-update audit trail** (fable amendment): the
   existing live `endoflife.date` rewrite of `runtimes.json` must append a
   one-line drift/audit log record (old version → new version, timestamp,
   `source=install_bat_python_bootstrap`) so this governed file's history
   stays reconstructible even though the rewrite itself stays unreviewed
   (justified purely by the hard Python bootstrap-ordering constraint).
9. **`UPDATE.bat` (new, root)**: guards on portable Python's presence
   ("run INSTALL.bat first" if absent), then runs
   `_sys\env\python\python.exe _sys\checks\check_tool_updates.py --propose-diff`
   and prints instructions to review the generated artifact under
   `_archive/tool-updates/<UTC>/`.

## Explicitly out of scope this round

- Base runtimes (python/nodejs/git/vscode/pwsh/ffmpeg) parity — separate
  future ticket.
- Any auto-apply of a newly *discovered* version without a human accepting
  an `UPDATE.bat`-generated diff first.

## Process note

One genuine three-way dissent point (item 6) was resolved via cc.fable's
DIR-005 arbiter authority after ag conceded its original "any nonzero exit =
harmless idempotent retry" position was true only per-attempt, not at the
system level (an indefinitely-broken peer CLI silently reporting "retry
pending" forever is not harmless). ag's tool_manager.py/peer_manager.py
module-split proposal was caught as fabricated (verified against the real
tree: no such files exist) before being folded into the plan — consistent
with this project's standing practice of independently verifying every
peer-proposed API/file claim before acting on it.

---

## Round 2 (2026-07-10, same day): base runtimes join the model

The user asked to reopen the "base runtimes explicitly out of scope" call
from round 1 and discuss — "완벽할 때까지" (until perfect) — bringing
python/nodejs/git/vscode/pwsh/ffmpeg into the SAME install/update/cleanup
loop. 5 more rounds (ag + cx + cc.fable), unanimous, with one genuinely
serious structural bug caught in the final ratification pass.

### Starting facts (verified against the real repo)

- **Python**: has real install code (embeddable zip, `._pth` edit to enable
  `site`, `get-pip.py`). Separately has its OWN older self-update mechanism
  in `INSTALL.bat` (live `endoflife.date` query, direct PowerShell rewrite of
  `runtimes.json`, no review) — predates D10/D11, exists because Python must
  exist before any Python script (including `ensure_tool` itself) can run.
- **Node.js**: has real install code — zip extract to temp, then the single
  top-level wrapper folder's *contents* get moved into `env_dir/nodejs/`,
  overwriting existing items.
- **Git**: has real install code — downloads a self-extracting 7z `.exe` and
  runs it directly as `-o<dest> -y`; no separate `_extract()` call, no
  staging, no atomic swap today.
- **VSCode**: has real install code — flat zip, direct `_extract()` into
  `env_dir/vscode`, `data/` subfolder created after for portable-mode state.
- **Pwsh, FFmpeg**: confirmed **zero install code** anywhere in `deploy()` —
  folders get created, `runtimes.json`/V/URLS entries exist, but nothing ever
  downloads or extracts them. Greenfield. FFmpeg's `version: "latest"` is
  additionally a bare DIR-004 violation (a rolling GitHub tag, not a pin).

### Ratified design

**1. Schema — one new `install_mechanism`, two new `zip_tool`-only fields.**
Keep the existing enum (`zip_tool | exe_tool | npm_peer`, shipped in D10),
add exactly one new value: `sfx_exe` (Git's self-extracting installer). For
`zip_tool` entries only, add `archive_layout: "flatten_exes" | "preserve_tree"`
and, when `preserve_tree`, `strip_components: 0 | 1`. This replaces an
earlier single-enum-value proposal (`zip_unwrap`) that conflated "download
mechanism" with "archive post-processing" — cx correctly rejected it: Node
needs "strip 1 wrapper level, keep everything else," VSCode/Pwsh need
"preserve everything, strip nothing" (today's `flatten_exes`, which only
rglob-copies `*.exe`, would silently discard every DLL/resource/locale
folder these apps actually need — confirmed live: a real PowerShell
`v7.6.2-win-x64.zip` was downloaded and inspected directly, showing ~330
files including dozens of DLLs at the zip root plus `Modules/`, `Schemas/`,
and per-locale subdirectories, none of which `flatten_exes` would preserve).

Final corrected mechanism table (independently verified against the actual
shipped `runtimes.json`, correcting a regression in an earlier draft that
had re-labeled several already-`exe_tool`/`npm_peer` entries as `zip_tool`):

| entry | install_mechanism | archive_layout | strip_components |
|---|---|---|---|
| ripgrep, bat, fd, delta, fzf, gh, sqlite | zip_tool | flatten_exes | — |
| jq, oh-my-posh, agy | exe_tool | — | — |
| claude, codex | npm_peer | — | — |
| nodejs (new) | zip_tool | preserve_tree | 1 |
| ffmpeg (new) | zip_tool | preserve_tree | 1 |
| vscode (new) | zip_tool | preserve_tree | 0 |
| pwsh (new) | zip_tool | preserve_tree | 0 |
| git (new) | sfx_exe | — | — |

**2. Bootstrap ordering.** Only Python is a genuine hard constraint. Node,
Git, VSCode, Pwsh, FFmpeg installers are pure Python-stdlib + network I/O —
zero ordering dependency on each other. `ensure_runtime("nodejs")` and
`ensure_peer_cli`'s npm-based claude/codex install are a normal DAG (runtime
batch before peer batch), not circular — `ensure_runtime` doesn't need Node
to already work in order to run, it only needs Node's target files to not
yet exist.

**3. FFmpeg version-pinning fix.** Switch discovery from BtbN/FFmpeg-Builds'
rolling `latest` tag to `GyanD/codexffmpeg` (independently verified real,
public, actively maintained, tags actual semver releases, e.g. "ffmpeg
8.1.2 builds" dated 2026-06-27, documents SHA-256 files) — a genuinely
measured source per DIR-004.

**4. Git `sfx_exe` — empirical confirmation required, not assumed.** It is
NOT proven that `PortableGit...7z.exe -o<dest> -y` behaves correctly when
pointed at a fresh staging directory (today's code runs it directly against
the final directory, no staging at all). TDD must include a fake-SFX unit
test (a mock executable asserting the exact `-o`/`-y` args used) plus one
optional live canary test before the real Git atomic-swap path is trusted.

**5. Venv package pinning.** Venv creation stays outside the ensure model
(it's the execution boundary, not an immutable vendor binary) but its
current `pip install filelock pywinpty --quiet` with zero version pins is
its own separate DIR-004 violation. Fix: pin exact versions in config, add a
measured verify-exact-version step during venv setup — no atomic swap, just
pin + verify.

**6. Dual dispatch, one shared core.** `ensure_tool(name, force=False)`
(reads `runtimes.json.tools`, swap-target `_sys/tools/<name>`) and a new
`ensure_runtime(name, force=False)` (reads `runtimes.json.runtimes`,
swap-target `_sys/env/<name>`, manifest at
`_sys/env/<name>/.install_manifest.json`) share one internal atomic-install
core parameterized by target root and archive_layout/strip_components — no
duplicated swap/checksum/canary logic.

**7. Flag behavior.** `--skip-vscode` drops "vscode" from the runtimes loop
entirely (no `ensure_runtime` call). `--skip-ai` drops claude/codex/agy from
their loop. `--force` passes through to `ensure_tool`/`ensure_runtime`,
unconditionally bypassing the already-current fast path.

**8. THE CRITICAL FINDING (cc.fable, caught in final ratification — missed
by both ag and cx, and by the terminal's own independent check): mutable
state living inside an atomic-swap target.** `npm_global =
env_dir / "nodejs" / "npm-global"` (`provisioner.py:483,655`) — the npm
prefix holding the *installed claude/codex peer CLIs* — lives **inside**
`_sys/env/nodejs`, which this design designates as a swap target. As
designed, the first Node.js version bump would rename the live `nodejs` dir
to `nodejs_old` and swap in a freshly-extracted vendor zip containing no
`npm-global` at all — silently destroying both installed peer CLIs. Worse:
the Tier 2 `_old`-purge this round adds for `env_dir` (mirroring D10's
`tools_dir` purge) would then delete the only surviving copy. The full
`INSTALL.bat` loop would eventually self-heal (the runtime batch runs before
the peer batch, and the already-current fast path's on-disk-exists check
would notice the missing binary and reinstall on the *next* run) — but a
standalone `ensure_runtime("nodejs")` call, or a bare `--retry-deferred`
drain, leaves the collaboration system silently broken in between.
"Self-healing by accident is not a design."

**Fix (a new class of field, not a one-off patch):** every swap-target entry
gets an optional `preserve_paths: []` field — mutable-state subdirectories
that must be migrated from the old directory into the new one *before* the
swap finalizes, and before the old directory becomes purge-eligible.
Confirmed: `nodejs: ["npm-global"]`. Flagged `TEST NEEDED` for TDD audit
(not yet confirmed either way): VSCode's portable-mode `data/` dir
(settings/extensions), Git's `etc/` (portable system gitconfig).

**9. Mandatory TDD guards (not optional — this round's blast radius crosses
from "a CLI tool might be missing" to "the dev environment hosting this very
system could brick itself"):**
   - (a) A regression test exercising a simulated update over a *populated*
     fake env tree (mutable-state dirs present): `preserve_paths` content
     must survive, rollback must restore the pre-state byte-identical, and a
     failure at *any* stage (download / checksum / extract / canary /
     rename) must leave the original completely untouched.
   - (b) A runtime keeps at least one `_old` generation until the *new*
     version's canary has actually passed — Tier 2 purge-eligibility begins
     only after that point, never before.
   - (c) Git's `sfx_exe` staging behavior is empirically confirmed (item 4's
     fake-SFX test + live canary) before the real Git update path is
     enabled.
   - (d) The npm_peer active-lease guard (`.ai/leases.json`, ratified in the
     round-1 discussion above) extends to Node.js swaps specifically too,
     since Node.js now *hosts* the peer CLIs — check active peer leases
     before swapping `nodejs`, not only before direct `npm_peer` updates.

### Explicitly out of scope / unaffected

- Nothing else remains base-runtime-side after this round: only (a) Python's
  own `INSTALL.bat` self-update (hard bootstrap-ordering exception) and (b)
  the Python venv itself (not an immutable vendor binary, but now gets
  measured package pinning per item 5) stay outside the unified model.

### Process note (round 2)

An intermediate draft's final "complete" table regressed jq/oh-my-posh/agy
back to `zip_tool` and claude/codex back to a zip-based mechanism, having
lost track of the already-shipped D10 assignments (`exe_tool`/`npm_peer`)
while focused on the new archive-layout axis — caught by independently
re-reading the actual shipped `runtimes.json` rather than trusting the
peer-summarized table. The PowerShell zip's real internal layout was
likewise verified by an actual download and inspection rather than trusting
either peer's unverified "it's probably flat" assertion. The
`preserve_paths` gap (item 8) was the most consequential finding of this
entire two-round discussion and was caught only in the final cc.fable
ratification pass — a reminder that "everyone agrees" and "it's actually
safe" are different claims, and this project's practice of independently
re-verifying even a peer's own "완벽/complete" self-assessment is what
surfaced it.

---

## Amendment (2026-07-10, same day): FFmpeg dropped entirely

The user asked why FFmpeg was in scope at all. A grep across this project's
own code found **zero actual consumers**: no script in `_sys/core`,
`_sys/checks`, or `_sys/hooks` invokes `ffmpeg`/`ffprobe`. Its only concrete
tie to the system was a reserved `PATH` slot (`_sys/env.json`'s
`path_entries`) — pure infrastructure for a workflow nobody has written yet.
The closest things to a real reason were circumstantial: a few AI-peer skill
docs under `_sys/antigravity/config/skills/` and
`_sys/codex/config/.tmp/plugins/` (audio-transcriber, video-content-extractor,
youtube-notetaker, etc.) describe tasks that would want ffmpeg, and a few
already-installed venv packages (imageio, pydub, onnxruntime's whisper
scripts) can optionally use it as a backend if actually exercised - but
nothing in this project currently exercises them.

Given zero present usage, the user chose to **remove FFmpeg entirely**
rather than keep speculative scope in an already-large design. Reverted:

- `runtimes.json`'s `runtimes.ffmpeg` entry — deleted.
- `env.json`'s `{"base": "env", "sub": "ffmpeg/bin"}` `path_entries` slot —
  deleted.
- `provisioner.py`'s `URLS["FFmpeg"]` lookup and the `env_dir / "ffmpeg"`
  folder-structure entry — deleted.
- This round's mechanism table (item 1) and every other FFmpeg-specific item
  above (the version-pinning fix, the `GyanD/codexffmpeg` discovery switch)
  are now moot and superseded by this amendment — left in place above as an
  accurate record of what was discussed, not as remaining scope.

**Corrected final scope for base-runtime `ensure_runtime` coverage:**
python (bootstrap-exempt), nodejs, git, vscode, pwsh. FFmpeg is out, full
stop — not deferred, not TEST NEEDED, removed. If a real need for it shows
up later (an actual skill or script that calls it), it re-enters through the
same discovery-provider/version-pin process as everything else, from a
clean slate rather than reviving these speculative entries.
