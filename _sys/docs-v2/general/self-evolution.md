# General — Autonomous Environment Maintenance (Self-Evolution)
> Status: ACTIVE (self_care.py implemented 2026-06-18; event pipeline wired to ctx_end)
> Purpose: Defines the mechanisms for peers to autonomously heal, document, and refactor the environment.

## 1. Core Principle: Autonomy vs. Consensus
Under COLLAB_RATE:10, governed decisions require unanimous consensus. Autonomous maintenance does not bypass this; instead, it layers actions by severity:
- **Observation & Validation:** Always exempt.
- **Action Execution:** Tiered by severity (Tier-0 auto-execute, Tier-1 fast-consensus, Tier-2 full R:10 consensus).

## 2. Three Subsystems

### 2.1. SelfHealer (Auto-Remediation)
Detects and fixes systemic errors.
- **Triggers:** `operational_errors.jsonl`, `health.json` (RED > 5m), `pytest` regressions.
- **Tier-0 (Low Risk):** Reversible changes, local to `_sys/data/` or `_archive/`. Excludes `_sys/core/`. Executes immediately with an audit log.
- **Tier-1 (Medium Risk):** Local file writes. Requires fast-consensus (15 min, 2/3 voters).
- **Tier-2 (High Risk):** Protocol/config edits. Requires full R:10 consensus.
- **DIR-003 Guard:** Any `hub.py` API change automatically escalates to Tier-2.

### 2.2. DocsSyncer (Automated Documentation)
Keeps `_sys/docs-v2` synchronized with actual protocol changes without requiring a separate vote.
- **Trigger:** Successful execution of the `consensus_finalize` connector.
- **Mechanism (Inherited Consensus):** Since the parent action already achieved consensus, the documentation update inherits this approval.
- **Roles:** `gc` drafts the update (large-corpus); `cc` validates against invariants.

### 2.3. SaturationDetector (Proactive Refactoring)
Monitors structural health and prevents architectural bloat.
- **Triggers:** Every 10 commits or manual `saturation-scan`.
- **Metrics:**
  - File saturation (lines > 800)
  - Git churn (> 5 commits in 7 days)
  - Protocol saturation (`protocol.json` > 850 lines or > 30 invariants)
  - Coupling (shared modules imported by > 3 peers)
  - Tech debt backlog (> 3 unresolved `_exceptions`)
- **Action:** Auto-generates a `proposal-add` for architecture refactoring. *Never auto-executes.*

## 3. Protocol.json Integration
**Status: Phase 1 — Pending R:10 consensus** (see §5 implementation table).
A new `"autonomous_maintenance"` section will be added to `protocol.json` to define thresholds, voters, and triggers for these subsystems. Until Phase 1 is complete, all thresholds are hardcoded in the scripts listed in §5.

## 4. Self-Care Cycle (Event-Based)

> Requirement: C4 from docs-v2/user/requirements.md

Self-care is **event-driven** (not time-based). Time-based cycles waste tokens when there is nothing to do.

### Trigger Events

| Event | Trigger Condition | Subsystem |
|-------|-----------------|-----------|
| `session_end` | User runs ctx-end or ctx-save | SelfHealer + DocsSyncer |
| `error_threshold` | `consecutive_failures > 5` for any peer | SelfHealer (immediate) |
| `commit_interval` | Every 10 git commits | SaturationDetector |
| `manual` | User runs saturation_scan.py directly | All subsystems |

### Self-Care Procedure (on trigger)

```
1. [Observe]  Read health.json, runtime-directives.jsonl, active-lessons.jsonl
2. [Validate] Check junctions (virtualizer.py status), stale paths, invariant completeness
3. [Cleanup]  Remove expired directives (TTL expired), compact old logs
4. [Scan]     saturation_scan.py — check file saturation, git churn, coupling
5. [Propose]  If saturation detected: auto-generate proposal-add (never auto-execute)
6. [Sync]     DocsSyncer: apply any finalized capsules via sync_docs.py
7. [Record]   Write self-care summary to _archive/self-care-log.jsonl
```

### System Cannot Self-Apply

- Self-evolution proposals require human approval before execution
- SaturationDetector findings → `proposal-add` only (read-only trigger)
- Tier-2 (protocol/config) changes → full R:10 consensus required

## 5. Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | `protocol.json` autonomous_maintenance section | ⏳ Pending R:10 consensus |
| Phase 2 | `saturation_scan.py` — Read-only, Tier-0 | ✅ `_sys/checks/saturation_scan.py` |
| Phase 3 | `sync_docs.py` — capsule → docs-v2 syncer | ✅ `_sys/checks/sync_docs.py` |
| Phase 4 | SelfHealer actions in `hub.py` | ⏳ Requires R:10 |
| Phase 5 | `self_care.py` event pipeline + ctx_end wiring | ✅ `_sys/checks/self_care.py` (2026-06-18) |
| Phase 6 | Lesson-frequency graduation: active-lessons → docs-v2 proposal | ⏳ EDGE-05 (closes feedback loop gap) |

### Implemented Entry Points (Phase 5)

```
ctx_end.py  →  self_care.py --trigger session_end
                    ↓ (non-blocking Popen)
              Step 1: observe   (health.json + directives)
              Step 2: validate  (virtualizer.py --status)
              Step 3: cleanup   (sweep expired TTL directives)
              Step 4: scan      (saturation_scan.py --quiet)
              Step 5: propose   (hub.py proposal-add if findings)
              Step 6: sync      (sync_docs.py --dry-run)
              Step 7: record    (_archive/self-care-log.jsonl)
```