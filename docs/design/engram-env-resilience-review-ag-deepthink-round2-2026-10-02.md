# Cross-review of engram-env-resilience-design (R3 delta, round 2) - ag.deepthink

- **Date**: 2026-10-02
- **Reviewer profile**: `ag.deepthink` via `peerhub ask` (READ_ONLY)
- **Target**: `docs/design/engram-env-resilience-design-2026-10-02.md` at draft R3
- **Disposition**: incorporated into R4 (design doc section 17). Verbatim reviewer output follows.

---

**Verdict:** APPROVE-WITH-CHANGES

**Flaws in In-Place Repair & Spike Interpretation:**
1. **Antivirus (AV) Interference:** Regenerating `.exe` console-script launchers in-place frequently triggers Windows AV heuristics, resulting in locked files or silent quarantines during the swap. The bounded retry might not outlast an AV scan.
2. **`python314.zip` Overwrites:** A patch-level `virtualenv` refresh (Scenario P2) replaces the venv's `python314.zip` and `python314.dll`. If a user or tool monkey-patched the venv's stdlib, those changes will be silently wiped out.
3. **Offline Editable Re-installs:** Running `pip install -e --force-reinstall` can invoke PEP 517 build backends (e.g., `hatchling`, `setuptools`). If these build dependencies are absent from the offline wheelhouse, the editable repair will fail. 
4. **`virtualenv` Dependency:** The self-contained premise relies heavily on current `virtualenv` behavior. Future upgrades to `virtualenv` could change what is copied versus linked, potentially re-introducing base-environment coupling. 

**Inconsistencies in R2 Text vs. R3:**
- **Section 4.1 P2:** States to "regenerate other console scripts only if needed" during a patch upgrade. S-11 establishes that `virtualenv` refresh only fixes `pip.exe`. If the root hasn't moved, the absolute paths in other scripts remain valid, so this condition needs to be explicitly defined (i.e., only regenerate if a relocation also occurred).
- **Section 6.2 Step 8:** Says "Verify: python/venv doctor checks + import probes, run from the new interpreter." To correctly verify the venv, its probes must run using the *venv's* interpreter (`venv\Scripts\python.exe`), not the base `env\python`.

**Answers to D9 & D10:**
- **D9 (Offline console-script policy):** Acceptable fallback. However, you should document that tools lacking a `__main__.py` entry point cannot be invoked via `python -m <tool>`, leaving them completely inaccessible until an online repair is performed.
- **D10 (`snapshots` naming & `repair` entry point):** Approved. `engram snapshots` effectively avoids namespace collision with user-data `engram backup`. Using `engram repair` as the unified entry point provides excellent, intuitive UX for disaster recovery.
