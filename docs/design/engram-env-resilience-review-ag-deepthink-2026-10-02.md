# Cross-review of engram-env-resilience-design (R1 draft) - ag.deepthink

- **Date**: 2026-10-02
- **Reviewer profile**: `ag.deepthink` via `peerhub ask` (READ_ONLY)
- **Target**: `docs/design/engram-env-resilience-design-2026-10-02.md` at draft R1
- **Disposition**: incorporated into R2 (see design doc section 17). Verbatim reviewer output follows.

---

**Verdict**
The design is fundamentally solid and well-structured, but requires critical adjustments for Windows idiosyncrasies, particularly regarding file locking, console script launchers, and logical drive behaviors.

**Factual Errors & Corrections**
- **File Locking/Rename (Sec 6 & 8.4):** While renaming a folder on the same volume is normally a fast operation, Windows strictly blocks renaming a directory if any file inside it (such as a loaded `.dll` or running `.exe`) has an open handle. The "cheap rename" swap (Step 4) will fail with `ERROR_ACCESS_DENIED`. You must strictly enforce the preflight holder check (X3) and ensure no background processes are holding locks before swapping.
- **Embedded Python (Sec 4.1 & 6):** Un-commenting `import site` in `._pth` is correct to enable `pip`. However, installing `virtualenv` is generally unnecessary on modern Python; the built-in `venv` module works perfectly for most use cases on Windows and avoids the extra bootstrap step.
- **Launchers & pyvenv.cfg (Sec 4.3):** The design correctly rejects in-place patching, but misses the core technical reason. While `pyvenv.cfg` is easily editable, `pip`-generated console script `.exe`s (like `pytest.exe` or `peerhub.exe`) physically embed the absolute path to `python.exe` in a shebang block appended to the launcher binary stub. Binary patching is unsafe, making venv rebuilding mandatory on Windows.
- **Volume Serial & SUBST (Sec 3 & 4.3):** A `SUBST` mapped drive shares the volume serial of its physical target. If a user accesses the same physical folder via `C:\PkgDev` and a SUBST drive `P:\`, they have the same serial but different logical paths. If treated strictly as a "move," Engram might thrash and continually rewrite state when the user toggles between the two paths.

**Missing Windows Scenarios**
- **MAX_PATH (260 characters):** While relocation checks budget (R-d), backing up deeply nested folders to `_sys/data/backups/` via copy (cross-volume) can easily exceed the 260-character limit and fail unless long paths are explicitly enabled in the registry or the `\\?\` prefix is used.
- **NTFS Junctions/Symlinks:** Relocating or backing up a root that contains directory junctions can lead to incorrect path resolution or infinite recursion during copies. 

**Answers to Decisions**
- **D1 (Rebuild vs. Patch):** **Rebuild**. Because pip-created `.exe` launchers hardcode absolute paths in their binary stubs, rebuilding is the only robust approach on Windows.
- **D2 (REQUESTED vs. Full Freeze):** **Restore only REQUESTED (T2)**. When upgrading Python minor versions, a full freeze often fails because specific versions of transitive dependencies with C extensions lack pre-compiled wheels. Letting pip re-resolve dependencies from REQUESTED is safer.
- **D5 (Auto-bump Bootstrap):** **Keep "latest" for fresh roots only**. Auto-bumping Python underneath an existing venv silently orphans native modules and breaks the environment. Never auto-bump an existing venv without an explicit `engram update`.
