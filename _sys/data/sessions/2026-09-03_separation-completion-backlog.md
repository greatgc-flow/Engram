# Engram/peerhub separation — completion status & remaining backlog (2026-09-03, updated 2026-09-04)

Written at the point the full ratified v8 diet plan (Increments A-D, Gate
2 design, Gate 7, README rewrites) is complete and both projects have
shipped real releases (Engram v3.0.0, peerhub v0.1.8). This is the single
pointer doc for "what's left" on both sides of the separation.

**Bottom line as of 2026-09-04: the separation itself is done and verified.**
Everything genuinely remaining is either (a) waiting on something outside
this session's control (winget human review, `cx`'s return), or (b) a real,
permanent, documented limitation (the `&`-path issue), or (c) deliberately
out of scope (peerhub's own general roadmap). Nothing is "still being
worked on."

## Status: separation is real, verified in both directions

- **peerhub → Engram**: an automated, already-passing test
  (`tests/unit/telemetry/test_presenter.py::TestNoHardcodedPaths::
  test_no_hardcoded_drive_letters_in_package_source`) grep-scans the
  entire installable `peerhub/` package for hardcoded `P:`/`D:\Engram`-
  style paths and asserts none exist. The only real path dependency
  anywhere in the peerhub repo is `scripts/migrate_engram_directives_
  2026_09_03.py`, a one-time, already-executed migration script excluded
  from the installable package by construction (not under `peerhub/`) —
  its dev-machine-hardcoded source path is expected and harmless.
- **Engram → peerhub**: manually grepped `_sys/core`, `_sys/cli`,
  `_sys/checks` for "peerhub" — every hit is either a comment explicitly
  confirming the boundary or a generic directory-name allowlist entry
  (`.peerhub` in `check_root_hygiene.py`). Engram treats peerhub purely as
  an optional, arbitrary tool entry in `_sys/runtimes.json`, no different
  from ripgrep or jq.
- Real, end-to-end verified installs: `git+https://github.com/greatgc-
  flow/peerhub.git@v0.1.8` builds a real sdist, installs cleanly, and
  `peerhub adapter discover` genuinely finds installed AI CLIs. Engram's
  `tools/winget/build_package.py` builds a real, `winget validate`-clean
  portable archive (independently re-downloaded from the GitHub Release
  and re-hashed to confirm byte-for-byte integrity against the manifest's
  `InstallerSha256`).

## Engram-side open items

1. ~~**`_sys/docs-v2/**`'s final disposition**~~ — **done**, executed
   2026-09-04 (proposal `31bcebf`, execution `17359b5`). `_sys/docs-v2/`
   no longer exists: 36 files moved into `_sys/docs/history/
   engram-peer-governance/` (51 total, historical reference only), 8
   files + 3 CLI baselines ported to peerhub verbatim (peerhub commit
   `fa7a5fb`, see peerhub section below), dead references cleaned up in
   both repos (`_sys/checks/check_docs_mece.py` + its test removed,
   `saturation_scan.py`/`test_doc_consistency.py` updated). Both old entry
   points are gone with the tree, so there's nothing left to carry a
   notice on.
2. **Winget submission**: [microsoft/winget-pkgs#428737](https://github.com/microsoft/winget-pkgs/pull/428737)
   is open, validated locally (`winget validate` clean). Status as of
   2026-09-04: the `license/cla` check-run shows `completed`/`success`
   ("All CLA requirements met") confirming the CLA is genuinely signed,
   but the `Needs-CLA` **label** is still stuck on the issue (a known,
   separate bot-sync desync — the check-run is the authoritative signal,
   not the label). No PR activity since 2026-09-03T17:14 UTC. Purely
   **waiting on a human Microsoft maintainer to review**, outside anyone's
   control — nothing left to do on our side. A real local
   `winget install --manifest ...` end-to-end test remains blocked in
   this environment (`winget settings --enable LocalManifestFiles`
   requires admin rights not available here) — only `winget validate` was
   completed, disclosed honestly in the PR body. Worth doing once from a
   machine with admin access, though `validate` passing plus the
   archive's SHA256 being independently re-verified live is already
   strong evidence it's correct.
3. **Low-priority, confirmed-harmless, not fixed**:
   `_sys/checks/saturation_scan.py`'s `EXCLUDE_DIRS`/`EXCLUDE_FILES` still
   carry dead vendor-cache-exclusion entries (`.tmp`, `.system`, `skills`,
   `plugins`, `marketplaces`, `cache`, `scratch`, `brain`, `.claude.json`)
   for vendor trees that no longer exist. Left alone deliberately: keeping
   an overly-broad-but-inert exclusion is safer than removing it (a
   removed entry could cause future false-positive noise if a
   similarly-named legitimate directory ever appears; a kept-but-unused
   one causes nothing). Revisit only if the comment's accuracy starts
   actually mattering to someone.
   `_sys/core/tidy_temp.py`'s `plan_brain_logs()`/`BRAIN_DIR` still points
   at the deleted `_sys/antigravity/config/brain` -- but is
   `.exists()`-guarded and always returns `[]` now, so it's inert, same
   category as the `saturation_scan.py` item above.
4. ~~`local.config.bat`'s entire per-PC-override mechanism was dead~~ —
   **fixed 2026-09-04**. Found 2026-09-03 that this went deeper than "not
   loaded": no entry point sourced the file at all, `BASE_DIR_WORKSPACE`
   had zero consumers anywhere, and `NPM_CONFIG_PREFIX`'s only real
   consumer (`launcher.py`'s `build_env()`) unconditionally overwrote it
   regardless of any pre-set value. Resolved with a real design choice
   (documented as needing one, not attempted as a shallow fix, in the
   version of this note that preceded this one): `launcher.py` now reads
   `local.config.bat`'s `set "KEY=VALUE"` lines as plain-text data via a
   new `_load_local_config_overrides()` (an explicit 2-key allowlist,
   never executes the file, so it can't collide with an unrelated
   ambient environment variable) instead of adding batch-sourcing or a
   new JSON format. `NPM_CONFIG_PREFIX` now wins over the computed
   default in `build_env()`; `BASE_DIR_WORKSPACE` is now consumed by a
   new `_resolve_default_target()` (also newly gives `engram launch`
   with no arguments a real `base_dir/workspace` default, ahead of
   falling back to the portable root, matching what the template's own
   comment always claimed but no code implemented). 10 new tests in
   `_sys/tests/unit/test_local_config_overrides.py`. See CONVENTION.md
   §6.2 for the current, accurate description.
5. ~~**Final exhaustive sweep (2026-09-04)**~~ — **done**, commit
   `854e89b`. Found and fixed 3 real gaps the increments above missed
   (none broke anything, all were dead/stale references to deleted
   infra, found via a fresh full-repo grep rather than the narrower
   per-increment checks): `_sys/config/environment.json` had 4 path
   entries (`claude_config`/`gemini_config`/`codex_config`/
   `workspace_template`) pointing at deleted dirs -- confirmed a real,
   live consumer (`dispatcher.py` loads this file on every dispatch)
   but zero code ever read those 4 specific keys, so removed them.
   `_sys/managed-links.json` (a real, live-consumed junction SSOT --
   `virtualizer.py` creates directory junctions from it on
   register/apply/mount) had all 4 entries targeting the deleted
   `_sys/claude`/`_sys/antigravity` subdirs -- emptied to `entries: {}`,
   kept as reusable generic infrastructure. `.gitignore` had ~150 lines
   of dead AI-peer-specific ignore rules -- removed, kept the genuinely
   generic `.ai/` and the real `peerhub/`/`.peerhub/` entries.
   `_sys/data/backlog.json`'s historical AI-orchestration entries (2400
   lines, `IMPLEMENTED`/`DONE` work-log items) were checked and judged
   out of scope -- completed history, not live config, same treatment
   as `_sys/docs/history/`.
6. ~~**Real fresh-install verification (2026-09-04)**~~ — **done**.
   Ran the actual documented install paths in genuinely fresh folders
   (`INSTALL.bat` on a clean clone, `pip install "git+...@v0.1.8"` into
   a fresh venv) rather than trusting the test suite alone. Found and
   fixed 3 more real bugs no prior pass caught, all committed + pushed +
   re-verified against a real install:
   - `_sys/runtimes.json` pinned peerhub at the stale `v0.1.7` — bumped
     to `v0.1.8` (`fd5e980`).
   - `doctor.py`'s component-presence check never looked in
     `_sys/env/venv/Scripts/` (where `install_mechanism: pip_tool`
     installs land) — so a correctly-installed peerhub was always
     reported "not found" in `STATUS.bat`. Fixed + regression test
     (`d0d0852`); re-verified: `STATUS.bat` now reports "all 18 declared
     components present".
   - **A real portable-root-path bug**: a folder path containing `&`
     (this session's own `D:\Engram&Peerhub\...` worktree location)
     breaks `INSTALL.bat`'s Python-version `for /f` lines and, deeper,
     `provisioner.py`'s npm-based peer-CLI installs (`npm.cmd` is an
     npm-generated launcher with the identical hazard). Fixed both
     layers we own (`f2fd8e1`): `INSTALL.bat` now `cd /d "%~dp0"` once
     and uses relative paths throughout instead of re-embedding the
     absolute path in any command string; `provisioner.py` now calls
     `node.exe` + `npm-cli.js` directly instead of going through
     `npm.cmd`. At the time, `provisioner.py`'s own post-install canary
     check for `claude.cmd`/`codex.cmd` was documented as **not fixable
     by us** (`9cc1565`, CONVENTION.md §2.6) — root-caused to `&` being
     explicitly on cmd.exe's own `/C` special-character list, excluded
     from the quote-preservation rule that protects parens/spaces/
     Korean text (CONVENTION.md §3.1's double-quote trick doesn't
     apply). **Superseded 2026-09-04 (later the same night, see item 7
     below): the real fix wasn't a better quoting trick, it was
     bypassing cmd.exe entirely** (direct claude.exe / node.exe+codex.js
     invocation, same pattern peerhub's fix uses) — this general
     pattern DOES fix the class of problem CONVENTION.md §2.6 called
     unfixable; `provisioner.py`'s own canary specifically wasn't
     revisited with it (out of scope for item 7's peerhub-focused pass)
     but is now a known, concrete, low-risk follow-up rather than a
     genuine dead end. CONVENTION.md §2.6 itself hasn't been corrected
     yet to reflect this — do that before calling it stale in any future
     pass. Practical guidance (still broadly true for anything that
     really does have to go through cmd.exe rather than bypass it):
     avoid `&` in your portable root folder path.
7. ~~**Repo-wide "&" vulnerability sweep + fix, both repos
   (2026-09-04)**~~ — **done**. Item 6's fix covered 2 instances; asked
   `ag.effort` to search exhaustively for more (real 723s search, both
   repos, ripgrep + Python AST parsing of every subprocess call site) —
   found 10 more real instances, 7 in Engram + 3 in peerhub. All 10
   fixed, empirically verified against this repo's own real `&`-laden
   checkout, tests green, committed + pushed to both repos:
   - Engram (commit `389c04a`, 7 fixes): `virtualizer.py` (mklink/rmdir
     via `shell=True` → native `_winapi.CreateJunction`/`os.rmdir`, no
     cmd.exe involved at all), `check_tool_updates.py` (relative
     `.\INSTALL.bat` instead of absolute), `manage.py` (generated
     uninstall helper's `echo` line now quotes its expansions),
     `launcher.py` (`.bat`/`.cmd` dispatch now relative+cwd; `cmd /k`
     and PATH-building investigated and left alone — not actually
     vulnerable, see the commit for why), `scrubber.py` (relative+cwd),
     `lifecycle_tester.py` (added a `_run_bat()` helper, applied to all
     6 `.bat` invocations in this Korean/special-char-path test suite).
     `test-runner.ps1` needed real back-and-forth: `ag.opus`'s first
     attempt (escaping `&` as `^&` inside an already-quoted
     `-ArgumentList` string) was live-tested by the terminal and proven
     NOT to work — neither that form, a plain quoted string, nor an
     array-form `-ArgumentList` reliably survives an `&`-laden argument
     VALUE through cmd.exe. Terminal fixed it directly: pass the value
     via an environment variable instead of a command-line argument
     (never parsed as command-line text at all), verified working
     end-to-end. Also discovered while investigating: the
     `sandbox-test.bat` this code references doesn't currently exist in
     the repo (pre-existing, unrelated dead code) — the env-var contract
     change is documented in the file for whoever eventually recreates
     it.
   - peerhub (commit `cf2102a`, 3 fixes): the real fix is centralized in
     `peerhub/dispatch/pipe.py`'s new `_resolve_real_direct_binary()`,
     applied to every dispatched `argv` in `run_process()` — resolves
     bare/absolute `claude.cmd`/`codex.cmd` to the real underlying
     binary (`claude.exe`; `node.exe` + `codex.js`, matching each real
     installed `.cmd` wrapper's actual content, independently verified
     by the terminal against real files) regardless of caller.
     `quota_polling.py` and `bootstrap.py`'s own direct invocations
     fixed the same way. `claude_adapter.py`/`codex_adapter.py` gained
     an optional (currently-unused, backward-compatible) constructor
     param for future direct wiring. Full unit suite (661 passed) +
     targeted integration subset (142 passed) independently re-run by
     the terminal, matching ag's own reported 661/714 results.
   - Both dispatches were interrupted at least once by real system
     memory pressure on this machine (OOM-kills, not zombie AI-peer
     processes — confirmed no orphaned `agy.exe` after each kill) and
     once by a genuine 1057s hub.py timeout; per established practice,
     checked `git status`/`git branch` after every interruption before
     retrying or trusting partial progress, rather than assuming a
     killed dispatch wrote nothing.
   - **Not done, worth a future narrow pass**: the same "bypass cmd.exe,
     invoke the real binary directly" pattern that fixed peerhub's
     canary-equivalent problem was never applied back to Engram's own
     `provisioner.py::_run_canary()` (still documented in item 6 above
     as a CONVENTION.md §2.6 "not fixable" limitation) — it's now a
     known, concrete, low-risk follow-up, not a genuine dead end.
     CONVENTION.md §2.6 hasn't been corrected to reflect this yet.

## peerhub-side open items

peerhub maintains its own much larger, independently-scoped backlog —
**don't duplicate it here**, see
[`docs/design/PEERHUB-BACKLOG-2026-08-27.md`](https://github.com/greatgc-flow/peerhub/blob/main/docs/design/PEERHUB-BACKLOG-2026-08-27.md)
in the peerhub repo (1241 lines as of 2026-09-04 — a large, mostly-complete
research/implementation log for the separate "replace hub.py's action
catalog natively" project, unrelated to the Engram/peerhub separation
itself) for the full, current, organized list. As of 2026-09-02 that
catalog reached 71/90 legacy actions genuinely translating and executing
end-to-end; the remaining 19 are permanently waived (see item 2 below),
not open work. Items directly relevant to the Engram/peerhub separation
specifically (not peerhub's general roadmap):

1. **Gate 2 Lane 2** (trusted third-party adapter-manifest discovery,
   scanning `%LOCALAPPDATA%\PeerHub\adapters.d`) — deliberately NOT
   implemented, unchanged since 2026-09-03. This is a real security trust
   boundary over untrusted input that ultimately gates code execution (an
   admitted manifest's named executable eventually gets spawned); the
   admission engine it would need (ACL evaluation, executable hashing,
   collision detection, atomic registry publication — see `docs/design/
   PHASE1-MANIFEST-SCHEMA-V2-2026-08-20.md`) doesn't exist anywhere in
   the codebase despite the design already being fully specified. Only
   Lane 1 (built-in cc/cx/ag PATH-based discovery, no untrusted input) was
   implemented (peerhub commit `c565386`). Resume once `cx` recovers
   (2026-09-07) for genuine adversarial security review, or on your
   explicit direction to proceed without one — see the Engram worktree's
   `2026-09-03_gate2-lane2-deferred-security-note.md` for full reasoning.
   **2026-09-04: a preliminary (not a substitute) second-opinion review is
   now done** — `ag.opus`, 10 grounded findings, see peerhub's
   `docs/design/PHASE1-MANIFEST-SCHEMA-V2-PRELIM-SECURITY-REVIEW-2026-09-04.md`.
   cx's real 2026-09-07 review is still required; this just gives it a
   concrete starting checklist.
2. **19 permanently-waived `LEGACY_CATALOG` actions** — each individually
   cited as an intentional, settled non-goal (host-environment-only
   tooling, an architecturally-incompatible generic write queue, upstream
   account/billing management peerhub deliberately does not fake, etc.),
   not open work, but worth knowing about if you ever go looking for a
   specific old `hub.py` action and don't find it.
3. Ported docs (2026-09-03, peerhub commit `fa7a5fb`): 8 markdown files +
   3 CLI baselines from Engram's old `_sys/docs-v2/` now live under
   `docs/adapters/` and `tests/fixtures/cli-baselines/`, each carrying a
   "Ported from Engram" notice. Several internal references inside them
   (`_sys/ai/orchestration.json`, `_sys/ai/model-registry.json`, `P:\`)
   still describe the old pre-separation workflow and were deliberately
   left as flagged historical context rather than silently rewritten —
   revisit only if/when peerhub defines its own equivalent
   update-checkpoint workflow.

## Release state (for reference)

| | Engram | peerhub |
|---|---|---|
| Latest tag | `v3.0.0` | `v0.1.8` |
| GitHub Release | [v3.0.0](https://github.com/greatgc-flow/Engram/releases/tag/v3.0.0) | [v0.1.8](https://github.com/greatgc-flow/peerhub/releases/tag/v0.1.8) |
| Install (working today) | git clone or release-zip download (see README) | `pip install "git+https://github.com/greatgc-flow/peerhub.git@v0.1.8"` |
| Install (pending) | `winget install greatgc-flow.Engram` — [PR #428737](https://github.com/microsoft/winget-pkgs/pull/428737) open | — |
| Tests (unit, 2026-09-04) | 262 passed, 2 skipped | 661 passed, 1 deselected, 13 subtests |
