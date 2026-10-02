# Cross-review of engram-env-resilience-design (R4 sanity pass, round 3) - ag.pro

- **Date**: 2026-10-02
- **Reviewer profile**: `ag.pro` via `peerhub ask` (READ_ONLY)
- **Target**: `docs/design/engram-env-resilience-design-2026-10-02.md` at draft R4
- **Disposition**: incorporated into R4.1 (design doc section 17). Verbatim reviewer output follows.

---

**Verdict:** Approved with minor findings.

**7.4 & 8.3 Risks (Data Loss / Retention):**
1. **7.4 (Refresh Deletion):** Step 4 deletes stale files by diffing against the backed-up set (removing files present in the backup but absent in the new build). If a user or third-party tool manually placed custom DLLs or binaries directly into `venv\Scripts`, they will be silently deleted during a refresh. 
2. **8.3 (Orphaned Pending Backups):** Rule 9 resolves `pending` backups via the op ledger. However, if a crash occurs *after* creating a `pending` backup but *before* the journal flushes the `PLANNED` record referencing it, the journal won't contain the operation. Tidy needs a rule to safely reap `pending` backups whose `op_id` appears in neither the manifest nor any active journal, otherwise they remain undeletable forever.

**Phasing (P0-P5) Ordering Problems:**
1. **P1 vs. P2 (Snapshots):** P1 introduces environment "snapshotting" (freeze + metadata scan). However, the backup registry required to safely store and manage these snapshots is not built until P2. P2 should precede P1.
2. **P1 vs. P3a (Mutation without Rollback):** P1 allows "offline console-script regeneration," which modifies multiple launcher executables non-atomically. Because P3a's journal and rollback machinery isn't implemented yet, a crash during this multi-file regeneration in P1 would leave launchers corrupted with no automated recovery. P1 should remain strictly read-only; script regeneration should be moved to P3a where the journal can protect it.

*(No disagreements with resolved decisions D1-D10.)*
