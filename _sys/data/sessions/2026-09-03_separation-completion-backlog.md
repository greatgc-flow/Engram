# Engram/peerhub separation — completion status & remaining backlog (2026-09-03, updated 2026-09-05)

Written at the point the full ratified v8 diet plan (Increments A-D, Gate
2 design, Gate 7, README rewrites) is complete and both projects have
shipped real releases (Engram v3.0.0, peerhub v0.1.8). This is the single
pointer doc for "what's left" on both sides of the separation.

**Bottom line as of 2026-09-05 (end of session): the separation is fully
done, verified, AND closed out end to end.** The multi-night `&`/`%`/`!`/`^`
cmd.exe path-bug sweep (items 6-10) is now completely closed -- the
`context_menu.json`/`registrar.py` gap item 10.5 flagged is fixed (sidecar
files, fail-closed, atomic writes; a critical `root==phys_root` production
flaw the terminal's own first fix missed was caught by a second
`cx.deepthink` cross-review before shipping), and all of it now has real,
empirically-verified regression test coverage (four separate historical
buggy commits checked out and confirmed to genuinely fail against the new
tests, not just pass against current code). **Gate 2 Lane 2 (trusted
third-party adapter-manifest discovery) also got its required security
review** -- dispatched early (cx has been reliably available all session;
the original 2026-09-07 date assumed otherwise) rather than left waiting.
Verdict: reject running it under Phase 1's model (admission-time hashing
provides no real trust, several concrete attack paths found and
independently re-verified by the terminal against real source); a safe
inert-discovery-only subset was identified but the user chose NOT to
build even that for now, so it stays fully documented and parked, not
implemented. Full detail:
`_sys/data/sessions/2026-09-03_gate2-lane2-deferred-security-note.md`
(Engram side) and peerhub's
`docs/design/PHASE1-MANIFEST-SCHEMA-V2-FINAL-SECURITY-REVIEW-2026-09-05.md`.
Everything else remaining is either (a) waiting on something outside this
session's control entirely (winget human review), or (b) deliberately out
of scope (peerhub's own general roadmap, confirmed empty of other
ready-to-pick-up items as of this session's own direct check of
`docs/design/PEERHUB-BACKLOG-2026-08-27.md`). **Nothing else is "still
being worked on."**

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
8. ~~**Apply the same fix to `provisioner.py::_run_canary()`
   (2026-09-04, later the same night)**~~ — **done** (commit `01c1c4f`).
   Closes item 7's own noted follow-up: `_resolve_canary_direct_binary()`
   now resolves `claude.cmd`/`codex.cmd` to the real underlying binary
   the same way peerhub's `pipe.py` does, before falling back to the
   original `shell=True` behavior for any other `.cmd`/`.bat` target.
   4 new tests (direct-binary success for both, a fallback-when-missing
   case, a focused resolver unit test). CONVENTION.md §2.6 updated to
   drop the now-stale "not fixable" framing. One transient, unrelated
   test failure (`test_provisioner_extra_checksum.py`, a checksum
   mismatch) appeared once on the full suite and did not reproduce in
   isolation or across 3 full-suite re-runs — confirmed environmental
   flake, not a regression, before committing.
   This dispatch (and the two before it that same night) needed 3
   retries total across real system memory pressure (OOM-kills) — each
   time, checked `git status`/`git branch` before retrying rather than
   assuming a killed dispatch wrote nothing; the final "killed" report
   for this one turned out to have actually completed all the writes
   before the kill landed, confirmed only by checking the working tree
   directly rather than trusting the kill notification's timing.
9. ~~**Check the other batch-scripting special characters (`%`, `!`)
   for the same class of bug (2026-09-05)**~~ — **done** (commit
   `857d381`). Asked before G-pool's quota window reset whether a
   portable root path containing a literal `%` or `!` breaks anything
   the same way `&` did — it does, and `!` turned out worse than `&`:
   - **`%`**: tonight's existing relative-path fix already fully
     protects `INSTALL.bat`/`launcher.py` (no additional fix needed
     there) — but exposed a SEPARATE bug: every root-level wrapper
     `.bat` still calling a sub-script via an absolute `%~dp0`-prefixed
     path (`STATUS.bat`, `UPDATE.bat`, `CLEANUP.bat`, `TIDY.bat`,
     `register.bat`, `unregister.bat`, `_sys/start.bat`,
     `_sys/cli/launch.bat`, `_sys/cli/manage.bat`, `engram.cmd`) broke
     on a literal `%`, because cmd.exe's `CALL` re-expands `%` variables
     a second time. `scrubber.py`'s generated purge script had the same
     issue (fixed by escaping `%` as `%%`).
   - **`!`**: a genuinely new, more severe bug — broke `INSTALL.bat`
     itself (not just wrappers): `setlocal enabledelayedexpansion`
     before `cd /d "%~dp0"` meant delayed expansion silently stripped
     `!` out of `%~dp0`'s value, so `cd /d` failed **without erroring
     out** — execution continued in the wrong directory. Fixed by
     reordering (`cd` before `setlocal`) in `INSTALL.bat`/`engram.cmd`,
     or switching to `setlocal DisableDelayedExpansion` entirely where
     delayed expansion wasn't actually needed (`dispatch.bat`,
     `STATUS.bat`, `UPDATE.bat`, `TIDY.bat`). `manage.py`'s generated
     uninstall helper now captures `%~1`-`%~4` before enabling delayed
     expansion (which its `WAIT_LOOP` genuinely does need, just
     reordered). Also removed a genuine pre-existing UTF-8 BOM from
     `engram.cmd` (a real CONVENTION.md §2.1 violation predating tonight,
     found as a byproduct of the rewrite).
   - Verified in real, fresh `%`/`!`-named folders (both by `ag.effort`
     and independently re-verified by the terminal, including a
     deliberate `%name%`-vs-active-env-var collision test). One real
     scare during terminal verification: an actual `INSTALL.bat` run in
     this repo's own dev worktree failed at the venv step — root-caused
     to leftover pollution from `ag`'s OWN extensive in-place testing
     (a stale `_sys/env` missing pip after repeated install/update
     runs), unrelated to the diff; cleaned up, then a genuinely fresh
     clone in a new real `!`-named folder confirmed full success
     (all 18 components, exit 0). Also caught and fixed before this
     landed: the initial commit accidentally included a regenerated
     `_sys/tools/oh-my-posh/.install_manifest.json` timestamp/hash from
     that same stray test run — reverted before pushing (amended +
     force-pushed after catching it in the post-push `git show --stat`).
     Full suite: 266 passed, 2 skipped (unchanged).
10. ~~**cx cross-review of item 9 found 3 real regressions (2026-09-05)**~~
   — **done** (commit `023e5b4`). Dispatched `cx.deepthink` for a
   genuinely independent second opinion on `857d381` (after both the
   terminal's own review AND `ag.opus`'s separate 8-commit audit had
   already come back clean) — it found 3 real bugs the other two passes
   missed: `scrubber.py`'s percent-escaping edit had accidentally
   deleted the line that actually renames the live python runtime
   before "purging" it (cleanup silently did nothing); `engram.cmd`'s
   fallback dispatch block used `%ERRORLEVEL%` inside a parenthesized
   block with delayed expansion disabled, silently discarding every
   real exit code from that path (reproduced live: exit 9 reported as
   0); `manage.py`'s uninstall helper passed an `&`-laden `base_dir` as
   a positional CLI argument, which `subprocess.list2cmdline()` doesn't
   quote for `&` (only whitespace) — a pre-existing bug tonight's
   earlier fixes never touched. All 3 independently re-verified by the
   terminal (real reproductions, not just trusting the reports) both
   before AND after the fix (delegated to `ag.opus`). See
   `reference_cx_crossreview_caught_regressions_2026_09_05` in the
   memory system for the durable lesson: dispatch a genuinely different
   peer for cross-review even after one prior pass already came back
   clean — this is now standing practice, not a one-off.
11. **`cx`'s broader post-completion audit (MECE / feedback-loop-closure
   / higher-concept / self-review / human-convenience), 2026-09-05** —
   went beyond re-reviewing individual commits and found several more
   real, still-open items across the whole sweep:
   - ~~**HIGH — `manage.py`'s uninstall helper still vulnerable**~~ —
     **done** (commit `e794415`). Commit `023e5b4` moved the DATA to
     env vars but still passed the helper SCRIPT'S OWN absolute path
     directly to `subprocess.Popen`, which breaks the same way when
     `_sys/core/launcher.py` redirects `TEMP` under an `&`-laden
     portable root (confirmed real via `engram launch`). Fixed with
     the same relative-path-plus-`cwd` pattern (delegated to
     `ag.effort`, needed 3 retries across a genuine 3P-pool 7-day-cap
     quarantine and other dispatch interruptions) — then the terminal's
     own re-verification found ag's specific fix ALSO subtly incomplete
     (a bare relative name fails; only the `.\`-prefixed form used
     everywhere else tonight actually works) and corrected it directly
     after pinning down the exact difference with a real repro.
   - **MEDIUM, not yet fixed — a literal `!` in a CLI argument now gets
     silently corrupted.** Commit `023e5b4` re-enabled delayed
     expansion for the whole of `engram.cmd` (to fix the `%ERRORLEVEL%`
     bug in one specific block) and then forwards `%1`-`%9` to the
     dispatcher — but with delayed expansion active file-wide, a literal
     `!` in any user-supplied argument (e.g. a filename) gets stripped/
     misinterpreted before the dispatcher ever sees it. This is a new
     trade-off introduced by fixing the `%ERRORLEVEL%` bug, not a
     regression of an existing fix — needs a real design decision
     (per-block delayed expansion via a sub-routine, or accept this as
     a documented limitation) rather than a reflexive revert.
   - **RESOLVED 2026-09-05 — `^` (caret), `%` (percent) in
     `_sys/context_menu.json` / `_sys/core/registrar.py`'s "Open in
     Sandbox" relay.** Root cause, found via direct empirical testing
     (many isolated real `.bat` repros, not simulated): a path value
     containing a literal `^` that is embedded as ESCAPED LITERAL
     SOURCE TEXT in a `set "X=...^^..."` statement (even correctly
     doubled) still fails when later used as a `cd`/`pushd`/`call`
     target — even though `echo` displays the stored value as if
     correct. A value obtained via the special `%~dp0` parameter
     expansion, or via `set /p VAR=<file` (reading raw bytes from a
     data file, never parsed as cmd.exe syntax), does NOT carry this
     taint. `call` specifically also fails on a set/p-loaded caret
     value if the caret sits directly in the call's own path argument
     — only `cd /d` into the caret-laden dir first, then `call` with a
     bare RELATIVE name, works.
     Fix: both `root` and `phys_root` are now written to sidecar data
     files (`{key_name}.root.txt` / `{key_name}.physroot.txt`, zero
     escaping needed) and loaded via `set /p`; the relay does
     `cd /d "%SANDBOX_ROOT%" || goto :fail` then a relative `call`;
     `setlocal DisableDelayedExpansion` is now explicit (was implicit);
     `_write_sidecar` uses `errors="strict"` so an unrepresentable path
     fails registration loudly instead of writing a silently-corrupted
     `"?"` path; both the relay `.bat` and sidecar writes are now
     atomic (write-to-temp + `os.replace`); all 3 cleanup code paths
     (`_unregister_entry`, `_clean_orphans`, the saved-state unregister
     pipeline) now also remove the sidecar files, and the pre-existing
     `str(relay).rstrip(".bat")` bug (character-strip, not suffix-strip
     — silently truncated any key_name ending in `a`/`b`/`t`) is fixed
     to use `Path.stem`. **Cross-review by `cx.deepthink` caught a
     critical flaw in the FIRST version of this fix**: it assumed
     `root` was always a bare, metacharacter-free drive letter (true
     only when a SUBST/virtual drive is mounted) — but
     `virtualizer.py`'s current production `mount()` only creates
     junctions and never sets `state["subst_drive"]`, so in real
     production today `root == phys_root` exactly, meaning the
     "fast path" branch was still embedding the arbitrary physical
     path directly and unprotected. Fixed by sidecar-loading BOTH
     values unconditionally. See
     `reference_cx_crossreview_caught_regressions_2026_09_05.md` for
     why this pattern (dispatch a second, genuinely independent peer
     for cross-review even after your own manual verification looks
     solid) keeps paying off.
     Verified: full test suite (267 passed, 2 skipped, including a new
     `test_registrar_caret_percent_relay_end_to_end` that actually
     executes the generated relay via `subprocess` against a real
     caret+percent-named directory) plus manual end-to-end runs of both
     the success path and the fail-closed path.
   - **STILL OPEN, confirmed real, narrower in scope — `%~1` (the
     right-click target path) is not reliably preserved through nested
     `call ... "%~1"` forwarding if the TARGET's own path contains a
     literal `^` or `%`.** Confirmed independently by both the terminal
     (direct `cmd.exe` repro: two nested `call` layers doubled a caret
     to `^^`) and `cx` (`C:\caret^name` → `C:\caret^^name`,
     `C:\pct%ZZARG%name` → ambient-variable-expanded). This is `CALL`'s
     documented "expands its argument line twice" behavior, and it
     affects any nested `call ... %*`/`call ... "%~1"` chain in this
     codebase (`start.bat`, `engram.cmd`, the lifecycle wrappers all do
     this), not just the sandbox relay — so it's a broader,
     pre-existing argument-forwarding gap, separate from the
     `SANDBOX_ROOT` fix above, and out of scope for tonight's fix. `cx`'s
     suggested proper fix is a generated PowerShell (or small .exe)
     relay reading a UTF-8 sidecar and invoking the Python dispatcher
     directly with an argument array, removing the repeated
     `cmd.exe`/`CALL` parse boundaries entirely — judged worth doing
     but a materially bigger undertaking than the caret fix; not
     started.
   - **STILL OPEN — sidecar/relay mbcs encoding is codepage-dependent,
     not universally portable.** `cx` confirmed a Korean+special-char
     sidecar round-trips correctly under this host's default CP949, but
     the identical content fails if `cmd.exe` is run under `chcp 65001`
     (UTF-8 mode). `errors="strict"` (this fix) at least makes a
     genuinely unrepresentable value fail registration loudly instead
     of silently writing a `"?"`-corrupted path — but does not make the
     mechanism codepage-portable. Matches the PowerShell/`.exe`-relay
     recommendation above; not started.
   - **CLOSED — test-coverage gap.** All of tonight's `&`/`%`/`!`/`^`
     path-bug fixes now have durable, empirically-verified automated
     regression tests (written by `ag`, independently re-verified by
     the terminal — for 3 of 5, actually checking out the real
     historical buggy commit and confirming the new test genuinely
     fails against it, not just passes against current code):
     `test_registrar_caret_percent_relay_end_to_end` (registrar.py
     `^`/`%` relay fix), `test_engram_cmd_cli_entrypoint.py`'s Test B
     (engram.cmd's goto/ERRORLEVEL/`!` fix — verified against both
     857d381 and 023e5b4), `test_scrubber_tier5.py` (the
     `py_dir.rename` regression cx caught in 857d381 — verified against
     857d381 directly), and 2 new tests in `test_uninstall_semantics.py`
     for manage.py's `.\`-prefix uninstall-helper fix (a real subprocess
     run in a genuine `&`-laden directory, plus a sanity check that the
     bare-name form genuinely still fails).
   - Also flagged, not yet actioned: peerhub's `pipe.py`/`bootstrap.py`/
     `quota_polling.py` each independently hardcode the Claude/Codex
     package-layout resolution logic (3 copies, already drifted in
     their exact fallback chains) — `cx`'s recommendation is a single
     shared `resolve_direct_invocation()` boundary in peerhub, judged
     worth doing now (unlike a broader cross-repo shared library, which
     `cx` judged NOT worth building). See `reference_cx_...` memory
     entries (to be added) for the full audit text.
   - The dedicated `ag` dispatch tasked with checking `^`/`@` tonight
     never returned a completed report (repeated dispatch interruptions
     — see the session record). Superseded: the terminal's own direct
     empirical investigation (see the RESOLVED `^`/`%` item above) fully
     covered and fixed the `^` case; the production `cd /d "%~dp0"`
     pattern used by every OTHER batch entrypoint tonight was confirmed
     safe against `^` in its own script's directory (that mechanism
     never needed a fix — only `registrar.py`'s `SANDBOX_ROOT`, which
     must represent an ARBITRARY external path rather than the running
     script's own location, did). `@` was not separately investigated.

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

1. **CLOSED (2026-09-05) — Gate 2 Lane 2** (trusted third-party
   adapter-manifest discovery, scanning `%LOCALAPPDATA%\PeerHub\adapters.d`)
   — the required `cx.deepthink` adversarial security review is done
   (dispatched early, on your explicit direction, rather than waiting for
   the original 2026-09-07 date — cx has in fact been reliably available
   all session). **Verdict: reject running Lane 2 under Phase 1's
   validation model.** Admission-time hashing provides no real trust
   (an attacker can place malicious bytes before admission, or point the
   manifest at an already-trusted interpreter with the payload in
   argv/stdin — no race needed at all), plus several more findings
   independently re-verified by the terminal directly against real source/
   tooling. Full report: peerhub's `docs/design/
   PHASE1-MANIFEST-SCHEMA-V2-FINAL-SECURITY-REVIEW-2026-09-05.md`. A safe
   inert-discovery-only subset (scan+display, never execute/probe/
   register) was identified as a real, concretely-scoped option, but **you
   chose not to build even that for now** — it stays fully documented and
   parked, not implemented. Only Lane 1 (built-in cc/cx/ag PATH-based
   discovery, no untrusted input) remains implemented (peerhub commit
   `c565386`). Nothing further to do here unless you decide to revisit.
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
| Tests (unit, 2026-09-05) | 266 passed, 2 skipped | 661 passed, 1 deselected, 13 subtests |
