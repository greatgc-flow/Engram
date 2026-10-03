# Cross-review of engram-env-resilience-design (R1 draft) - cc.deepthink

- **Date**: 2026-10-02
- **Reviewer profile**: `cc.deepthink` via `peerhub ask` (READ_ONLY)
- **Target**: `docs/design/engram-env-resilience-design-2026-10-02.md` at draft R1
- **Disposition**: incorporated into R2 (see design doc section 17). Verbatim reviewer output follows.

---

**1) Verdict: APPROVE-WITH-CHANGES.** The direction is right: a manifest, dry-run by default, move instead of delete, and marker-based tidy. But the execution model in §6 and §9 can't be implemented as written. Please issue R2 before TDD.

**2) Blocking issues**

- **B1. The process can't swap its own interpreter.** `dispatch.bat:6,24` runs every command on `env\python\python.exe`, and `provisioner.py:921-922` already says it "cannot swap the interpreter it's currently running under". So step 4's rename fails. The X9 rollback fails for the same reason when run from the new interpreter.
  - *Fix:* run steps 4–8 from a runner interpreter that lives outside both targets, e.g. a copy of the staged Python in `data/state/env-op/<op>/runner/`. Re-exec under it and let the parent exit, the same way `core_update_helper.ps1:23-29` waits on the parent PID. Create the venv through a child `env\python\python.exe -m virtualenv` process that exits.
- **B2. Recovery can't be reached in the crash window.** Between the two renames there is no `env\python\python.exe`. At that point:
  - `engram.cmd:173-179` blocks `doctor`, `update` and `repair`.
  - `engram.cmd:144-146` sends plain `engram` to first-run bootstrap, which extracts a fresh Python into `env\python` (`bootstrap.bat:107-139`) without looking at the journal.
  - Resume and rollback then hit rename collisions.
  - *Fix:* have `bootstrap.bat` and `dispatch.bat` first check whether `env-op.journal.json` exists. If it does, run `--resume` with the first interpreter found: `python` → `python.new` → runner → backup.
- **B3. There is no single commit point, so the manifest can desync.** "Commit" is spread over the manifest, N `BACKUP.json` files, the journal, `last_base_dir` and the state files. If a crash lands after the manifest write but before the journal says COMMITTED, `--rollback` puts the old Python back while the manifest says new.
  - *Fix:* make the journal's COMMITTED record the only commit point. Before it, only roll back; after it, only roll forward. Everything else becomes an idempotent step after commit, reconciled through `manifest.last_op.id`. Tidy should resolve `pending` backups through the op ledger; otherwise backups left `pending` by a crash are never deleted.
- **B4. The journal and lock aren't crash-safe.**
  - `os.replace` does not fsync. Use write → fsync → replace, or an append-only JSONL file with a CRC per record.
  - Generate the timestamped backup paths at PLANNED and journal them before renaming anything, or a resume can't find the old Python.
  - Take the lock with an exclusive (`O_EXCL`) create, and break stale locks atomically. In B1 the PID owning the lock exits by design, so a non-terminal journal must block all new operations no matter what the lock says.
  - Every component that changes the environment must honour the lock. That includes the `deploy` venv block (`provisioner.py:1499-1519`), `_drain_deferred_lazy`, `updater`, `registrar`, the launcher, and `layout_migration`, which `engram.cmd:82-95` runs automatically on any command.
- **B5. The rename order is wrong.** Quarantine the venv and move the old Python out *before* moving `python.new` in. As written, if VS Code, pyright or `peerhub.exe` holds the venv, the failure comes after Python has already been swapped. Also, step 7's "remove new venv" should be a quarantine move, to keep the move-never-delete rule.

**3) Missing scenarios / wrong assumptions**

- **The previous-root signal is erased before use.** `launcher.py:165-182` overwrites `last_base_dir.txt` on every launch, so the first `engram open` after a move wipes it out. Adopting `root=current` then hides the move permanently. Instead, take the old root from `pyvenv.cfg home`, then `*.state.json base_dir`, then the sidecar files, and have the launcher write the file only on commit.
- **Copy vs move by volume serial is wrong both ways.** A copy on the same volume is not a move, and a move to another drive is not a copy. Use an `install_id` in the manifest: if the old root still exists with the same id, it's a copy, and the copy gets a new id.
- **Registry assumptions don't hold.**
  - `registrar.py:323` writes the same value for root and physical root, so logical vs physical isn't actually recorded today.
  - `_clean_orphans` sweeps every install, not just this one (`registrar.py:244-251`). Relocation should limit itself to keys whose sidecar equals the old root, and export them first. The plan has no export step.
- **`features.context_menu` goes stale after `menu disable`.** Repair would then re-enable a menu the user removed. Work out intent from `register.state.json` plus HKCU when building the plan.
- **P9's offline cache doesn't exist.** Bootstrap has no hash check and always caches to the fixed name `python-bootstrap.zip` (`bootstrap.bat:111,114`), with no version.
- **X3's holder check silently passes.** `_is_component_in_use` returns "not in use" when `psutil` is missing (`provisioner.py:1060-1063`). `psutil` is installed only in the venv, not in the portable Python the dispatcher runs on [I]. The check is also time-of-check/time-of-use; the swap rename is the real test.
- **Smaller contradictions.** §7.3 runs T1 with `--upgrade` every time, which contradicts principle 5. Doctor "adopts" by writing the manifest, but §9 says doctor never takes the lock. The `engram backups` verb is one letter away from `engram backup` (user data).

**4) Decisions**

- **D1:** Agree: rebuild, never patch.
- **D2:** Restore REQUESTED packages, using the freeze as a constraints file (`-c`) and falling back per package. Pin T1 rather than upgrading it.
- **D3:** Agree, plus require paths to stay under `backups/env` and never traverse reparse points.
- **D4:** Opt-in. Also refuse while `claude.exe` is running.
- **D5:** Agree, but stricter: auto-bump only when none of `env\`, the manifest or `data\state` exist.
- **D6:** One journal file split into groups. {python + venv} is one atomic group; registry/state only roll forward. A registry failure must never undo a verified Python swap.
- **D7:** Fine. Start ttl at commit, not creation. Set venv to 7 days and ai-state to 30. The cap must never evict the only rollback copy of the latest operation within 72 hours.
- **D8:** At launch, run only cheap file checks. A non-terminal journal means refuse to launch; a root mismatch gets the one-line hint. No Python probes at launch.

**5) Top 3 phasing risks**

1. **P1 ships a destructive venv rebuild before P2 (backup registry) and P3 (lock/journal),** which contradicts the doc's own order rationale. Limit P1 to probe and snapshot, and move the rebuild after the lock/journal work.
2. **P0's adoption bakes in the wrong root** because the launcher overwrites the signal, and later phases trust it. P0 needs the launcher fix and evidence-based adoption, and adoption should happen only inside `repair`.
3. **P3 bundles too much:** the runner handoff, journal, lock, entry-point gates and bootstrap recovery. Split it into P3a (lock, journal and gates, proven first on the lower-stakes venv rebuild) and P3b (the Python swap). Gate both on fault injection that kills the process between each rename.

A few line citations in the doc are slightly off: `virtualenv` is installed at `provisioner.py:1501` and the baseline list is at `:1517`. I couldn't read the live `D:\PkgDev\_sys\env` because permission was denied, so the `psutil` point stays inferred. I didn't modify any files.
