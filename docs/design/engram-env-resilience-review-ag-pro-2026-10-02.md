# Cross-review of engram-env-resilience-design (R1 draft) - ag.pro

- **Date**: 2026-10-02
- **Reviewer profile**: `ag.pro` via `peerhub ask` (READ_ONLY)
- **Target**: `docs/design/engram-env-resilience-design-2026-10-02.md` at draft R1
- **Disposition**: incorporated into R2 (see design doc section 17). Verbatim reviewer output follows.

---

**Verdict:** 
The design provides a solid foundation for environment resilience, but requires refinement concerning cross-volume operation atomicity, backup security boundaries, and unattended UX safety.

**Tidy Deletion & Secret Leak Risks:**
- **Data Loss:** The 2GB soft cap forces the deletion of "oldest committed" backups even if they are well within their TTL. If `min_keep` is too low, users might lose critical rollback states during a flurry of updates. Furthermore, the `--adopt-legacy` flag could accidentally delete user-created fallback folders if the adoption logic only relies on loose name matching without structural verification.
- **Secret Leaks:** While `ai-state` backups correctly receive strict ACLs and repository URLs are scrubbed of userinfo/tokens, other backup kinds (like `venv` or `state`) might inadvertently capture secrets, `.env` files, or API keys placed there by users. The backup registry must enforce restrictive ACLs globally across all backup types, not just `ai-state`.

**Cross-Volume & Disk-Space Gaps:**
- **Atomicity:** The cross-volume fallback (copy + verify + delete) is fundamentally not atomic. A crash or power loss during the deletion phase leaves duplicated, unmanaged state. 
- **Time-of-Check to Time-of-Use:** Disk preflight only validates space prior to the operation. During a slow cross-volume copy, concurrent system activity could consume the remaining space, causing a late-stage failure.
- **Symlinks:** Cross-volume backup copies may flatten symlinks or hardlinks inside the virtual environment, inflating the disk footprint beyond the preflight estimate.

**UX, Exit-Code, & Prompt Gaps:**
- **CI/CD Hanging:** Relying solely on TTY detection to decide between interactive prompts and throwing an error can cause indefinite hangs in CI/CD environments that emulate TTYs. Commands should have a strict timeout on prompts or explicitly require an `--interactive` flag if destructive actions are pending without `--yes`.
- **Exit Codes:** The unverified `[U]` exit code convention is a significant gap. Destructive/repair operations need discrete, documented exit codes to distinguish between "user aborted," "disk full," "network offline," and "corrupt state" for automation reliability.
- **Bilingual Confusion:** Mixing a Korean CLI UX with English JSON/logs could cause friction when the console prompts users to inspect specific English keys or file paths.

**Answers to D3, D4, and D7:**
- **D3 (Tidy Ownership):** Choose marker-based (`BACKUP.json`). It guarantees explicit ownership and prevents the catastrophic deletion of unrelated user directories that happen to match regex patterns.
- **D4 (AI State Remap):** Keep it **opt-in**. Automatically rewriting third-party AI state configurations is highly risky; unknown schema variations could lead to corruption or silently invalidated credentials.
- **D7 (Retention Defaults & 2GB Cap):** The 2GB cap is a sensible default but should dynamically scale on constrained environments (e.g., "2GB or 10% of free space, whichever is smaller"). The `min_keep` absolute floor must strictly override the soft cap to guarantee rollback availability.
