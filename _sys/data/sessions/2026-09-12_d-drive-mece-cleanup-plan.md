# D: Drive MECE Audit & Cleanup Plan

- **Date**: 2026-09-12
- **Author**: Antigravity (Pair Programming Agent)
- **Status**: DRAFT / PLAN ONLY (No deletions or moves executed) -- **EXECUTED 2026-09-16** (independently re-derived and carried out by Claude Sonnet 5, see below)

**Update (2026-09-16): fully executed, discovered independently.** A fresh D:\ survey four days later (not informed by this document -- found only afterward) reached matching conclusions and completed the recommended actions: `ClaudeDev`, `t2`, `tttt` deleted (their workspaces were already empty by 09-16); `workspace`/`workspace_ori` had their real uncommitted work (a MarkItDown-Flow UI change and an experimental image-router change) archived to new GitHub branches before deletion, since by 09-16 those were the only remaining unpreserved content; both root zip backups were deleted outright rather than moved to cold storage, per explicit user instruction after confirming the user had already relocated `D:\To RAID\` as a manual backup. The `install-test-2026-09-04` folder and the 7 root audit files this plan describes were already gone by 09-16 (the audit files' destination, `_sys/data/sessions/holding/2026-09-09_audit_scratch/`, was cleaned up the same day as this update, its findings already preserved in the committed `p-drive-mece-migration-audit-2026-09-09.md`). Net additional finding this plan didn't have: `workspace_ori` also contained a plaintext Azure Document Intelligence API key, deleted (never committed/pushed anywhere).
- **Scope**: Exhaustive MECE audit and action plan for non-system/unprotected directories and root files on `D:\`
- **Exclusions (Protected Boundaries - Do Not Touch)**:
  - `D:\To RAID\`
  - `D:\$RECYCLE.BIN`
  - `D:\.Cache`
  - `D:\.tmp.driveupload`
  - `D:\System Volume Information`
  - `D:\pagefile.sys`
  - `D:\Engram&Peerhub\engram-main-worktree` (Active worktree)
  - `D:\Engram&Peerhub\PortableDev (v2.1)` (Active `P:\` SUBST drive target)

---

## 1. Executive Summary

This MECE audit examines the non-protected file structures on `D:\` to identify obsolete installations, stray Git clones, redundant test fixtures, legacy archives, and working scratch files.

Across all evaluated targets:
- **Potential Space Reclaimed Immediately**: **~9.97 GB** (Ephemeral test installs + stale dev environments)
- **Potential Cold-Storage Offload**: **~7.16 GB** (Point-in-time full archive zip files)
- **Total Recoverable / Archivable Footprint**: **~17.13 GB**
- **Operational Clarity Win**: Elimination of a high-risk stale duplicate Git clone (`D:\ClaudeDev\workspace\peerhub`), preventing future accidental peer edits in dead repositories.

---

## 2. In-Depth Item Findings & Audit

### 2.1 `D:\ClaudeDev` (Legacy Engram 3.2.2 Environment)

- **Total Size**: 2,746 MB (~2.75 GB)
  - `_sys`: 2,717.03 MB
  - `workspace`: 28.90 MB
- **Engram Version**: `3.2.2` (via `D:\ClaudeDev\_sys\core\version.json`)
  - Compared against `D:\t2` and `D:\tttt` (`version: 3.2.6`) and `PortableDev (v2.1)` (`P:\`), `D:\ClaudeDev` is a legacy, superseded installation.
- **Stray Clone Audit (`D:\ClaudeDev\workspace\peerhub`)**:
  - **Remote**: `origin` -> `https://github.com/greatgc-flow/peerhub.git`
  - **Branch**: `main`
  - **HEAD Commit**: `9b8e30c chore(release): bump version 0.1.12 -> 0.1.13`
  - **Working Tree Cleanliness**: Fully clean (0 uncommitted changes, 0 untracked files, 0 stashes).
  - **Commit Divergence vs Active Peerhub (`P:\workspace\peerhub`)**:
    - Active Peerhub HEAD: `4e7fc13`
    - Merge Base: `9b8e30c` (HEAD of `D:\ClaudeDev\workspace\peerhub` is an exact ancestor of active `P:\workspace\peerhub`)
    - Divergence Count: Active peerhub is **85 commits ahead** of `D:\ClaudeDev\workspace\peerhub`.
    - Unpushed Commits in ClaudeDev: **0**.
  - **Risk Assessment**: **HIGH OPERATIONAL RISK IF RETAINED**. Earlier tonight, a peer accidentally operated inside `D:\Engram&Peerhub\PortableDev (v2.1)\workspace\Engram` (an old clone) instead of the active repository. A stale clone of `peerhub` sitting in `D:\ClaudeDev\workspace\peerhub` presents the exact same collision risk if any tool or agent navigates by name.
- **Recommendation**:
  1. Immediately delete `D:\ClaudeDev\workspace\peerhub`.
  2. Move entire `D:\ClaudeDev\` to a holding directory or delete upon user confirmation.
- **Confidence**: **HIGH (99% on peerhub clone, 95% on ClaudeDev root)**.

---

### 2.2 `D:\Engram&Peerhub` In-Scope Subdirectories & Root Zips

*(Excluding active `PortableDev (v2.1)` and `engram-main-worktree`)*

#### A. `D:\Engram&Peerhub\install-test-2026-09-04`
- **Total Size**: 224.91 MB
- **Contents**: `Engram`, `peerhub-venv`, and `install-log.txt`.
- **Finding**: Log shows a failed installer run from September 4, 2026 (`'D:\Engram' is not recognized as an internal or external command` caused by unquoted path handling during Python bootstrap).
- **Cross-Reference Check**: Grep search across `P:\` returned 0 references.
- **Recommendation**: **DELETE**. It is a dead, failed installation test run.
- **Confidence**: **HIGH (99%)**.

#### B. `D:\Engram&Peerhub\workspace` vs `D:\Engram&Peerhub\workspace_ori`
- **`workspace` Size**: 239.67 MB (last modified 2026-07-19).
  - Contains `CasePack_extracted`, `MarkItDown-Flow`, `obsidian-releases`, `Vault`, and `ENGRAM_HANDOFF_CasePack_aux_v1.md`.
- **`workspace_ori` Size**: 112.18 MB (last modified 2026-06-07).
  - Contains earlier baseline snapshot from late May/early June 2026 (`markitdown`, `obsidian-markitdown`, `2. 요청.txt`).
- **Comparison & Finding**:
  - `workspace_ori` is strictly superseded by `workspace` (June 7 baseline vs July 19 state).
  - Neither is referenced by the active `P:\` drive environment (`P:\workspace` has its own distinct project folders: `Engram`, `peerhub`, `plans`, `sandbox`).
- **Recommendation**:
  - `workspace_ori`: Move to holding / archive, or delete (Confidence: 90%).
  - `workspace`: Move to cold storage / archive (`P:\_sys\data\archive\2026-07-19_legacy_workspace\`) before removal (Confidence: 90%).

#### C. `D:\Engram&Peerhub\Docs`
- **Total Size**: 0.05 MB (50 KB, dated 2026-06 to 2026-08).
- **Contents**: Specification notes (`1. 21대 국회 환경노동위.txt`, `2. 요청.txt`, `개요 2.txt`, etc.).
- **Recommendation**: Retain in place or move to `P:\_sys\docs\history\legacy-notes\`.
- **Confidence**: **HIGH (95%)**.

#### D. Root Zip Archives (`D:\Engram&Peerhub*.zip`)
- **`D:\Engram&Peerhub_20260809.zip`**: 2.71 GB (2,712,346,944 bytes, dated 2026-08-09).
  - Contains point-in-time full zip of `Docs/` and `PortableDev (v2.1)/`.
- **`D:\Engram&Peerhub.zip`**: 4.45 GB (4,454,274,604 bytes, dated 2026-09-02).
  - Contains point-in-time full zip of `Engram&Peerhub/` (`Docs/` and `PortableDev (v2.1)/`).
- **Combined Size**: **7.16 GB**.
- **Finding**: These are standalone full backup snapshots taken prior to major migrations in August and September 2026. They are inert and not referenced by runtime systems.
- **Recommendation**: **DO NOT DELETE**. Flag for user to move to cold storage (e.g. NAS, external RAID, or cloud backup) to reclaim ~7.16 GB of primary NVMe/SSD space safely.
- **Confidence**: **HIGH (95%)**.

---

### 2.3 `D:\t2` and `D:\tttt` (Ephemeral Test Installations)

- **`D:\t2`**:
  - **Total Size**: 3,410.80 MB (~3.41 GB)
  - **Engram Version**: `3.2.6`
  - **Workspace**: `D:\t2\workspace` is **completely empty** (0 bytes).
  - **Purpose**: Installer / deployment test created 2026-09-10.
  - **Recommendation**: **DELETE**. Empty workspace, zero unique user data.
  - **Confidence**: **HIGH (95%)**.

- **`D:\tttt`**:
  - **Total Size**: 3,590.81 MB (~3.59 GB)
  - **Engram Version**: `3.2.6`
  - **Activity**: Launched today (2026-09-12 00:05 and 00:12) via `start.bat`.
  - **Workspace**: Only contains `workspace\smoke-test\.peerhub\` (660 KB dummy smoke-test directory).
  - **Purpose**: Ephemeral testing environment used earlier today for testing launch scripts.
  - **Recommendation**: **DELETE** (after quick user spot-check of `smoke-test` if desired).
  - **Confidence**: **HIGH (95%)**.

- **Combined Reclaim**: **~7.00 GB**.

---

### 2.4 Seven Root Audit Files on `D:\`

- **Files**:
  1. `audit_issues.csv` (34,668 bytes)
  2. `audit_report.md` (61,420 bytes)
  3. `audit_results.csv` (74,457 bytes)
  4. `dest_files.txt` (137,562 bytes)
  5. `dest_tracked.txt` (49,188 bytes)
  6. `p_files.txt` (2,481,280 bytes)
  7. `p_tracked.txt` (53,742 bytes)
- **Total Size**: ~2.8 MB
- **Origin & Git Verification**:
  - Created between 09:02 and 09:06 on 2026-09-09 during the P-drive MECE migration audit.
  - The finalized, authoritative audit report synthesized from these scratch files was committed to Git at `P:\workspace\peerhub\docs\reviews\p-drive-mece-migration-audit-2026-09-09.md` in commit `6fe021c6c1c784296b2026c5549ad0a3c5d8d04f` ("docs: P:\ -> Engram+peerhub MECE migration audit (in progress)").
- **Finding**: These 7 files are intermediate output logs that completed their purpose on 2026-09-09.
- **Recommendation**: Move to archive directory (`P:\_sys\data\sessions\holding\2026-09-09_audit_scratch\`) or delete from `D:\` root to keep the drive root uncluttered.
- **Confidence**: **HIGH (99%)**.

---

## 3. Action Matrix & MECE Summary

| Path | Current Size | Role / Finding | Recommended Action | Confidence | Potential Space Reclaimed |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `D:\ClaudeDev\workspace\peerhub` | 28.9 MB | Stale clone (HEAD 9b8e30c, 85 commits behind, clean) | **DELETE** (Prevent confusion) | 99% | 28.9 MB |
| `D:\ClaudeDev` (remainder) | ~2.72 GB | Obsolete Engram 3.2.2 install | **DELETE** or **MOVE TO HOLDING** | 95% | ~2.72 GB |
| `D:\Engram&Peerhub\install-test-2026-09-04` | 224.9 MB | Failed installer test run (unquoted ampersand) | **DELETE** | 99% | 224.9 MB |
| `D:\Engram&Peerhub\workspace_ori` | 112.2 MB | June 7 baseline snapshot (superseded) | **MOVE TO ARCHIVE** / **DELETE** | 90% | 112.2 MB |
| `D:\Engram&Peerhub\workspace` | 239.7 MB | July 19 legacy project workspace | **MOVE TO ARCHIVE** | 90% | 239.7 MB |
| `D:\Engram&Peerhub\Docs` | 0.05 MB | Legacy specification notes | **KEEP** / Archive to docs | 95% | 0 MB |
| `D:\t2\` | 3,410.8 MB | Test install 3.2.6 (empty workspace) | **DELETE** | 95% | ~3.41 GB |
| `D:\tttt\` | 3,590.8 MB | Test install 3.2.6 (smoke test only) | **DELETE** | 95% | ~3.59 GB |
| 7 Root Audit Files (`D:\audit_*`, `D:\*.txt`) | 2.8 MB | Intermediate audit logs (committed to git) | **DELETE** / Move to holding | 99% | 2.8 MB |
| `D:\Engram&Peerhub_20260809.zip` | 2,712.3 MB | Snapshot archive (2026-08-09) | **MOVE TO COLD STORAGE** | 95% | 2.71 GB |
| `D:\Engram&Peerhub.zip` | 4,454.3 MB | Snapshot archive (2026-09-02) | **MOVE TO COLD STORAGE** | 95% | 4.45 GB |

---

## 4. Top 3 Recommended Actions

1. **Eliminate Stray Git Clone & Retire `D:\ClaudeDev` (Immediate Clarity & Safety)**
   - *Action*: Delete `D:\ClaudeDev\workspace\peerhub` (confirmed 100% clean, 85 commits behind active repo), then decommission `D:\ClaudeDev`.
   - *Impact*: Eliminates a high operational confusion hazard for multi-agent peer routing and reclaims **~2.75 GB**.
2. **Purge Ephemeral Test Installs (`D:\t2`, `D:\tttt`, `D:\Engram&Peerhub\install-test-2026-09-04`)**
   - *Action*: Remove both test installs and the failed installer run.
   - *Impact*: Immediately reclaims **~7.22 GB** of disk space with zero risk to production data (`t2` is empty, `tttt` is just a smoke test, `install-test` is failed).
3. **Offload Large Root Backup Zips to Cold Storage**
   - *Action*: Move `D:\Engram&Peerhub.zip` (4.45 GB) and `D:\Engram&Peerhub_20260809.zip` (2.71 GB) to external RAID, NAS, or secondary backup storage.
   - *Impact*: Reclaims **~7.16 GB** of primary SSD space safely while preserving historical backup integrity.
