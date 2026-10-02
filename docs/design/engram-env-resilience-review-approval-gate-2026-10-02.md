# Push-approval gate for branch feat/env-resilience-p0 (P0-P2)

- **Date**: 2026-10-02
- **Requested by**: user ("get the higher model's approval before pushing")
- **Reviewers**: `cc.deepthink` (Opus; `cc.pro` was unavailable: usage limit reached), `ag.pro`
- **Round 1 result**: cc.deepthink **BLOCK_PUSH** (one blocker), ag.pro APPROVE_PUSH.
- **Disposition**: blocker and follow-ups reproduced by `_sys/tests/unit/test_approval_fixes.py` and fixed; bootstrap.bat re-verified by real execution (HTTP 404, garbage cache with matching hash). Round 2 below.

## Round 1 - cc.deepthink (verbatim)

(1) **VERDICT: BLOCK_PUSH**

(2) **BLOCKERS**
- **`_sys/core/bootstrap.bat:149,169,172-179` – a bad download gets cached as "verified".** `curl -L` has no `-f`, so it exits 0 on an HTTP 404/503 or a captive-portal page. Python has no `sha256` in `defaults/runtimes.json`, so nothing checks the file, and its own hash goes into `.sha256` before extraction is tried. Expand-Archive then fails and exits without removing either file. Every later run prints "[OK] Using the verified cached Python zip" and fails again, even after the network recovers. The old code re-downloaded each time, so it recovered on its own. Fix: use `curl -fL`, and write `.sha256` only after Expand-Archive succeeds (or delete the zip and `.sha256` when it fails).

(3) **RISKS TO EXISTING USERS**
- **`last_base_dir.txt` no longer written on launch:** acceptable. But once a manifest exists, moving the install or a USB drive-letter change prints the hint (`launcher.py:183`) on every launch. Nothing clears it: `commit_install` skips an existing manifest (`env_manifest.py:360`) and `repair` doesn't exist yet.
- **New install/update operations:** acceptable. Failures only warn, the manifest is written only on fresh installs, and the snapshot takes the lock and skips if it's busy.
- **tidy now includes backups:** acceptable. It only deletes marker-valid, non-pending, non-pinned dirs under `data/backups/env`, and today that's only venv-freeze snapshots. One catch: `--adopt-legacy --apply` can evict newly adopted dirs by size cap in the same run, and the dry-run doesn't show that. `*_old` dirs are disposable anyway (`provisioner.py:769-770`).
- **`engram snapshots`:** acceptable. Dry-run by default, never overwrites, refuses the python/venv kinds.
- **bootstrap fresh-root gate:** acceptable, but `bootstrap.bat:94-96` still says "remove env\python and rerun to upgrade". With a venv present, that now just reinstalls the same pinned version.
- **doctor probes:** up to 5 subprocesses, about 105 s worst case. A venv `error` sets `ok=False` (`venv_manager.py:47`), which flips the overall result and exit code to failed. That contradicts the comment at `doctor.py:280`. Acceptable only if intended.

(4) **DATA-LOSS / SECURITY CHECK**
Nothing deletes or overwrites data it doesn't own. Moves delete the source only after a rename or a verified copy, restore refuses an existing target, and `find_stale_entries` is dry-run only. No credential leak in practice. Minor gaps:
- tidy checks the lock but doesn't hold it, so adoption could race an update that's mid-swap.
- restore uses the absolute `source_path`, so after a move it recreates folders at the old root.
- `sanitize_url` (`venv_manager.py:305`) misses `access_token=`, `api_key=` and `private_token=`, because `\b` doesn't match after an underscore.

(5) **NON-BLOCKING FOLLOW-UPS**
1. The bump path (`bootstrap.bat:101-104`) keeps the old pin's `PY_SHA256`. Once a Python sha256 is ever declared, every fresh-root bump will fail the checksum. The cached zip is also never checked against `PY_SHA256`.
2. Give users a way to clear the drift hint. Use `volume_serial` to recognise a drive-letter change.
3. Guard `plan_backups`: one malformed `BACKUP.json` timestamp raises in `_parse` and crashes even `tidy --only tmp`.
4. Hold `env_lock` while tidy deletes or adopts backups; the provisioner should take it too.
5. Fix the `sanitize_url` regex, and add the backup ACLs the design calls for.

Notes:
- `diff.txt` is untracked; don't commit it.
- This worktree's branch is `feat/env-resilience-p1-venv-manager`, not `-p0`. Confirm which one you're pushing.
- I didn't run the tests; the pass/fail numbers are the author's.
- Despite the read-only instruction, I accidentally ran one no-op `echo`. Nothing was changed.

## Round 1 - ag.pro (verbatim)

(1) VERDICT: APPROVE_PUSH

(2) BLOCKERS: None.

(3) RISKS TO EXISTING USERS:
- **Launcher no longer writes `last_base_dir.txt`:** Acceptable. It preserves evidence of the true install root, allowing reliable root-drift detection when users move the folder.
- **Install/update pipelines gained operations:** Acceptable. `env.commit_install` and `venv.snapshot` are idempotent, non-destructive, and use a `warn` failure policy, meaning they cannot crash existing workflows.
- **Tidy default targets include backups:** Acceptable. Reclaims space safely by strictly respecting the retention plan (2GiB size cap, TTLs, min-keep floors) without touching pinned backups.
- **New `engram snapshots` verb:** Acceptable. Provides safe read-only visibility and controlled restores (safely blocking system-critical engine-only kinds).
- **`bootstrap.bat` changes:** Acceptable. Cached zip reuse is safeguarded by SHA256 integrity checks. Fresh-root detection prevents silent version skew when an unmanaged `venv` is already present.
- **Doctor subprocess probes:** Acceptable. Probes are wrapped in strict timeouts and `try-except` blocks; failures yield informational findings rather than breaking `doctor`.

(4) DATA-LOSS / SECURITY CHECK:
- **Passed.** Ownership is strictly marker-based. Tidy will never delete unmarked directories under `data/backups/env`, even if they match a naming pattern, guaranteeing it only touches what it owns.
- Restores strictly refuse to overwrite existing directories (`if target.exists(): raise FileExistsError()`), preventing clobbering of live user data.
- The `env_lock` and manifest writers use atomic `os.replace` via unique temp files, eliminating data corruption during partial writes or power loss.
- Security: `venv_manager.sanitize_url` correctly redacts credentials and tokens from `direct_url.json` (editable packages) before recording metadata.

(5) NON-BLOCKING FOLLOW-UPS:
1. **Tidy read-only files:** `tidy_temp.py`'s `_rm()` uses standard `shutil.rmtree()`, which will fail on read-only files (e.g., git objects inside a backed-up repo), leaving a partially-deleted directory. Consider importing and using `backups._rmtree(path)` which has an `onerror` handler to unlock and delete them.
2. **Memory usage in bootstrap:** `[System.IO.File]::ReadAllBytes` loads the entire zip into memory to compute the SHA256. While perfectly fine for the ~30MB Python zip, a streaming hash computation would scale better if much larger artifacts are cached in the future.

## Round 2 (after fix commit bf99afd) - cc.deepthink: APPROVE_PUSH (verbatim)

(1) VERDICT: APPROVE_PUSH

(2) BLOCKERS: none. The round-1 blocker is fixed:
- bootstrap.bat:153 uses `curl -fL` and deletes the zip and the `.sha256` on failure.
- :168 checks the declared hash.
- :193 writes the `.sha256` only after `Expand-Archive` succeeded.
- :182-190 cleans up after a failed extract.
- :145 lets PY_SHA256 gate the cache.

(3) Regressions (low, not blocking):
- **bootstrap.bat:185-186:** Any extract failure deletes the cached zip and its `.sha256`, even when the cause is a full disk, an antivirus lock or a PowerShell module-path problem. That throws away a good verified cache, so an offline re-bootstrap can't recover. It's a deliberate trade-off, but worth knowing.
- **tidy_temp.py:530-567:** tidy holds `env_lock` for the whole run, including the npm, vscode and pycache deletes, not just the backup changes. A concurrent `engram update` gets `EnvLockBusy` for that whole time.

(4) Notes:
1. **test_approval_fixes.py:188-195:** A single adopted dir is already kept by the 72h newest-commit rule (backups.py:479), so this test passes even without `protect`. Adopt 2 or more `*_old` dirs to actually prove the fix.
2. **bootstrap.bat:221:** Saving a version bump doesn't update or remove `runtimes.python.sha256`. If a hash was ever declared, the next fresh install fails with a checksum mismatch. It fails safe, but the error would be confusing.
3. **backups.py:490/501:** `int(meta["size_bytes"])` can still raise on a hand-edited marker, so "plan_retention never raises" isn't fully true. Validate it in `_read_meta`. Two smaller gaps: `sanitize_url` ignores `#fragment`, and the get-pip download (bootstrap.bat:202) still has no `-f` and no errorlevel check (this one predates the fix).

## Round 2 - ag.pro: APPROVE_PUSH (verbatim)

(1) VERDICT: APPROVE_PUSH.
(2) BLOCKERS: none.
(3) Regressions: None found. The fixes correctly address the issues from Round 1 without introducing regressions.
(4) Notes:
- `venv_manager.py`'s `sanitize_url` aggressively drops the *entire* query string if any sensitive parameter is found (e.g., `?version=1&api_key=...` becomes just the base URL). This is safe for logging but removes benign parameters alongside secrets.
- In `tidy_temp.py`, `plan_backups_retention` is executed twice when `backups` are targeted (once to generate `backups_plan` for orphans, and again within `build_plan`). This is harmless but slightly inefficient.
- In `bootstrap.bat`, if `!PY_DIR!` existed prior to a failed extraction attempt (`_PY_DIR_NEW=0`), it won't be deleted on failure. This is appropriately cautious, avoiding deletion of pre-existing data.

## Outcome

Both reviewers approved the push of branch `feat/env-resilience-p0`. Non-blocking notes carried as follow-ups: adopt two or more legacy dirs in the protect test; validate `size_bytes` in `_read_meta`; `sanitize_url` fragment handling; get-pip download without `-f`; tidy holds the lock for the whole run; a bump should drop the persisted pin hash; failed extract also discards a good cache (deliberate).
