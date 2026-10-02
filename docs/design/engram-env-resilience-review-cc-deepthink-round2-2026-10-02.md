# Cross-review of engram-env-resilience-design (R3 delta, round 2) - cc.deepthink

- **Date**: 2026-10-02
- **Reviewer profile**: `cc.deepthink` via `peerhub ask` (READ_ONLY)
- **Target**: `docs/design/engram-env-resilience-design-2026-10-02.md` at draft R3
- **Disposition**: incorporated into R4 (design doc section 17). Verbatim reviewer output follows.

---

**Verdict: APPROVE-WITH-CHANGES.** The R3 delta has three blockers.

**B1. S-1 and S-9 didn't test the case that actually triggers P1-P3.** In both spikes, `home` pointed at a folder that no longer existed. In P1-P3, `home` points at a folder that exists but holds a different Python. On Windows, `getpath` sets `sys._base_executable = <home>\python.exe` without checking it exists. `multiprocessing` spawn (bpo-35797) then starts its child processes from that path. Expected effects:
- After a delete or a move, child processes fail to start.
- With patch skew, a 3.14.9 child runs on 3.14.8 site-packages.
- With minor skew, the child loads cp314 extensions.

So `home` is not cosmetic, contrary to S-1 and 5.1 step 6. Add a spike S-12 that runs `ProcessPoolExecutor` in each of these states, and make a `home` mismatch a repair trigger. Also run R-1 now with a 3.14.7 zip, because P2 depends on it.

**B2. The in-place refresh overwrites many files without atomicity.** Windows lets you rename an exe that is in use, but not overwrite it. If an IDE, MCP server or hook holds `venv\Scripts\python.exe`, the refresh stops halfway: new zip/pyd files next to the old DLL. That contradicts:
- 6.2 step 7 ("old venv still intact")
- 6.3/D6 ("Group A atomic")
- T-F1 (bit-for-bit rollback)

Fix it one of two ways: clone the venv, refresh the clone, then swap by rename. Or back up the interpreter files plus `pyvenv.cfg` first and journal that step. The refresh also re-installs pip, which may downgrade a pip the user upgraded. It leaves behind DLLs/pyds the new build no longer ships, too. The version probe reads only the DLL, so record hashes of the venv's interpreter files in the manifest. That catches zip/pyd drift and AV quarantine. Self-containment comes from virtualenv's handling of the embeddable build, not from CPython. So pin `virtualenv` in `runtimes.json` and check self-containment after every create.

**B3. Regenerating console scripts as in S-10 is fragile.**
- `--force-reinstall <pkg>` without `==<installed>` upgrades the package.
- Packages from scrubbed private indexes, or yanked or local wheels, fail to reinstall.
- Editable reinstall needs build isolation, which means network access.
- Limiting it to REQUESTED misses scripts that dependencies ship (`pygmentize`, `normalizer`).
- P1 runs it before the env lock exists (the lock only arrives in P3a).

**R2 text now inconsistent with R3:**
- 6.1 (`-m venv|virtualenv`) and 6.2 step 2 (`[U: stdlib venv]`) contradict S-7.
- 7.1 still says `[I - verify S-2]`; S-2 makes it [V].
- 4.1 P2 gates on `pip check`, but 5.1 calls it warning-only.
- The section 16 heading still says "resolved in R2".
- 4.3 row 7 misses absolute old-root paths in MCP `command` entries and hooks.
- Problem 1's ABI sentence only holds through the B1 mechanism.

**D9:** Regenerate offline first. Use `distlib.scripts.ScriptMaker`: it should already be in `env\python` as a virtualenv dependency (worth confirming). Feed it every installed package's `entry_points.txt` (console and GUI scripts), target `venv\Scripts`, with the venv's python as the executable. This is the same generator pip uses, not patching the launcher trailer. If that fails, reinstall pinned to `==version --no-deps`, adding `--no-build-isolation` for editables. Only if that also fails, report and tell the user to run `python -m <tool>`.

**D10:** Agree that `repair` should be the single engine for changes. `relocate` and `update --only python|venv` should build their plans through it. The name `snapshots` is fine, but `snapshots restore` for python/venv must take the journal and lock.
