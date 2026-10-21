# Open Items Preserved from Migrated Backlog

On 2026-09-20, `_sys/data/backlog.json` (129 items) was migrated from the Engram product repo to the PeerHub repository (`docs/history/from-engram-repo/backlog.json`).

Of the 129 items, 127 were closed (`done`, `dropped`, or `superseded`). Exactly 2 items had a non-closed status (`deferred`). They are recorded here to ensure no operational or housekeeping items are lost.

---

### 1. D4: Diag Inc-4 Failover Engine
- **Title**: `diag inc-4 failover engine`
- **Category**: `diag`
- **Status**: `deferred` (Settled — NOT ACTIONABLE)
- **Resolution**: Re-affirmed "not worth building" 3 separate times across peer reviews. Failover on mutating operations is unsafe without end-to-end idempotency guarantees from AI CLI tools (DIR-004 violation: double-execution hazard). Pre-dispatch failure is already safely handled by `--to auto` and fail-closed routing. Settled decision, permanently deferred / closed in practice.

---

### 2. T92: Engram Working-Tree Untracked Clutter
- **Title**: `Engram working tree has long-standing untracked clutter (*_old tool dirs, sandbox files, stale session archive)`
- **Category**: `housekeeping`
- **Status**: `deferred` (per-item owner housekeeping; reaffirmed 2026-10-21)
- **Priority**: Low (Cosmetic/hygiene only, no runtime impact)
- **Description**: Flagged during cross-repo sanity passes: the working tree contains untracked directories/files (e.g. `_sys/tools/*_old` directories, legacy sandbox files, stale lock/state files, and intentional test/worktree artifacts).
- **Next Action**: Owner triages each installed/worktree item (`delete`, `.gitignore`, or `keep`). A clean tracked feature branch is not evidence that installed debris is gone. No blanket removal or runtime cleanup mechanism is planned.
- **Reference**: Full provenance and historical context are preserved in PeerHub's migrated backlog: [`docs/history/from-engram-repo/backlog.json`](https://github.com/greatgc-flow/peerhub/blob/main/docs/history/from-engram-repo/backlog.json).
