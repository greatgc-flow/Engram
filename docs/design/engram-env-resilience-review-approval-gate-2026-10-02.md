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
