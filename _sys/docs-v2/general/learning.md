# General — Learning

> Note: This pillar consolidates the previously separate self-evolution, feedback-loop, directives, and knowledge systems into one single source of truth for the observe -> resolve -> propagate learning loop.

## 1. Learning Loop (5-Whys Virtuous Cycle)

Every task execution and failure feeds into a self-healing loop designed to achieve a Zero-Code MECE Architecture. Hardcoded workarounds are strictly forbidden; all resolutions must be configured in JSON or governed docs.

### The Loop

1. **Detect (Observer)**: `hub.py` execution wrappers, `check-health.bat`, or `self_care.py` detects an anomaly, timeout, or repeated error. This is logged to `ipc-log.jsonl` and `cost-log.jsonl`.
2. **Analyze (5-Whys)**: When a threshold of failures is met, `self_care.py` (or a designated peer acting as `observer`) asks "Why did this fail?" recursively until reaching the root configuration/documentation gap.
3. **Mitigate (Runtime Directive)**: `hub.py` automatically injects a temporary `runtime-directives.jsonl` rule to quarantine or instruct peers around the issue immediately (TTL-bound).
4. **Resolve (Permanent Consensus)**: Before the directive expires, a peer proposes a permanent fix via Consensus. The fix MUST be:
   - A change to `protocol.json` or `routing-config.json` (JSON Settings).
   - A change to `Docs_v2/` (Guidelines).
   - A logic fix in `hub.py` (Source Engine).
5. **Close (Active Lessons)**: The root cause is categorized in the active lessons registry, completing the loop and preventing recurrence.

### 5-Whys Root Cause Analysis (Standard Procedure)

When performing analysis, peers MUST use the 5-Whys method.

Example:
*   **Problem**: Peer `gc` failed with `sandbox_spawn_eperm`.
*   **Why 1**: `gemini.bat` could not write to `_sys/gemini/config/state.json`.
*   **Why 2**: The file lock was held by another process.
*   **Why 3**: The previous `hub.py ask` process crashed and orphaned the lock.
*   **Why 4**: Heartbeat/Lease timeout was too long, so the lock wasn't released.
*   **Why 5**: `protocol.json["communication_policy"]["lease_timeout_sec"]` is set too high for fast failover.
*   **Resolution**: Update JSON config instead of hardcoding timeouts in Python.

### Configuration

All statuses, paths, and categories for the feedback loop are managed in `protocol.json["feedback_loop"]`.

## 2. Directives System

### Two-Layer Model

| Layer | File | Authority | Created by | Modified by |
|-------|------|-----------|------------|-------------|
| **User Directives** | `_sys/ai/user-directives.md` | Human-confirmed | User (or cc at user request) | User only |
| **Runtime Directives** | `_sys/ai/runtime-directives.jsonl` | System-generated | hub.py auto-promote | Never by user |

Both layers are injected into every peer ask by `_build_ask_query_with_context()`.

### User Directives (`user-directives.md`)

Human-authored standing rules (DIR-NNN format). Examples: per-peer minimum permissions, language rules, architectural invariants.

**PRO-09**: NEVER write auto-generated warnings here — muddies human authority.

### Runtime Directives (`runtime-directives.jsonl`)

Auto-generated temporary rules. This is a state journal (entries are rewritten in-place — NOT append-only). Status can be: `active` | `resolved` | `expired`.

```json
{
  "id": "RD-20260614-001",
  "rule": "CAUTION: gc has repeatedly failed with reason=rate_limit. Verify peer health before routing.",
  "source_peer": "gc", "trigger_reason": "rate_limit",
  "effective": "20260614T125000", "expires": "20260614T185000",
  "ttl_hours": 6, "trigger_count": 2,
  "clear_condition": "first_success", "status": "active"
}
```

### Directive Lifecycle

- **Auto-Promote Trigger**: A runtime directive is auto-created when the same peer fails with the same `reason` consecutively exceeding the value in `protocol.json["runtime_directives"]["auto_promote_consecutive_failures"]`.
  - Logic in `_record_ask_failure()`: If failures exceed the threshold AND `prev_failure_reason == reason`, it triggers `_auto_promote_runtime_directive()`.
  - If an active directive already exists for the peer+reason, it bumps the `trigger_count` (no duplicate).
- **Auto-Clear Trigger**: A `first_success` directive is cleared when the same peer returns `exit_code=0`.
  - Logic: `_record_ask_success()` triggers `_clear_peer_runtime_directives(peer_id)`.
- **TTL & Expiry**:
  - Default TTL is configurable via `protocol.json["runtime_directives"]["default_ttl_hours"]` (adjustable via `--ttl-hours`).
  - Expired entries stay in the file for audit purposes but are never injected.
  - Injection caps are configured via `protocol.json["runtime_directives"]["max_active_directives"]` and max characters; overflow results in a truncation notice.
- **Cross-Peer Propagation**: Runtime directives propagate to ALL peers. For example, a `gc` failure gets injected into `cc`/`cx`/`ag` asks too. The purpose is to prevent other peers from routing to a known-degraded peer.

### Hub CLI Commands

```bash
hub.py directive-add --rule "..." --peer cc --ttl-hours 4 --clear-condition manual
hub.py directive-list
hub.py directive-clear --directive-id RD-20260614-001
```

## 3. Knowledge Propagation

Mistakes repeat when observations are not recorded, not propagated to other peers, or when there is no closed-loop (observe -> normalize -> approve -> inject -> verify).

### Three-Layer Architecture

```text
Layer 1: RAW EVENTS (audit store — never injected directly)
  _sys/ai/knowledge/mistake-events.jsonl
  _sys/ai/knowledge/user-feedback.jsonl
         ↓ triage/normalize
Layer 2: ACTIVE LESSON REGISTRY (approved rules)
  _sys/ai/knowledge/active-lessons.jsonl
         ↓ filter + compile (per-peer)
Layer 3: DELIVERY PACKS (prompt-facing)
  _sys/ai/knowledge/active-pack-index.json → hub.py [PEER LESSONS]
```

### Lesson Record Schema

```json
{
  "id": "L-2026-001",
  "scope": "global | workspace",
  "applies_to": ["cc", "gc"],
  "rule": "Always verify path exists before Move-Item.",
  "severity": "HIGH | MEDIUM | LOW",
  "source_event": "mistake-events.jsonl#event_id",
  "approved_by": "user",
  "status": "active | retired",
  "recurrence_count": 0,
  "expires": null
}
```

### Closed Feedback Loop

```text
observe → raw event written → candidate lesson →
approval (user) → active registry → compiled pack →
injected into peer ask → delivery log →
recurrence check → retire/update → (next cycle)
```

### Token Efficiency

- **Hash-ACK pack compression**: The peer ACKs the received pack hash, preventing re-injection if the hash is unchanged.
- **Global vs workspace scoping**: Global lessons are shared across all workspaces; workspace lessons are scoped to the current project.
- Never inject the entire lesson history — only active, approved, non-expired entries are injected.

## 4. Self-Care & Autonomy Bounds

### Core Principle: Autonomy vs. Consensus

Under COLLAB_RATE:10 (configured in `governance_params.json`), governed decisions require unanimous consensus. Autonomous maintenance layers actions:
- **Observation & Validation**: Always exempt from consensus.
- **Action Execution**: Autonomous mutation is strictly forbidden. All actions are proposals requiring human approval or full consensus.

### Three Subsystems

1. **SelfHealer**: Detects systemic errors.
   - **Triggers**: Configured in `protocol.json["autonomous_maintenance"]` (e.g., operational errors, `health.json` RED, `pytest` regressions).
   - **Behavior**: OBSERVE -> VALIDATE -> PROPOSE only. NO autonomous remediation or mutation is allowed. Failures hard-stop and surface to the human.
   - **DIR-003 Guard**: Any `hub.py` API change automatically requires full R:10 consensus.
2. **DocsSyncer (Automated Documentation)**: Keeps `_sys/docs-v2` synchronized without requiring a separate vote.
   - **Trigger**: Successful execution of the `consensus_finalize` connector.
   - **Mechanism**: DRY-RUN / propose only. It does not automatically apply changes. `gc` drafts the update (large-corpus) and `cc` validates against invariants.
3. **SaturationDetector (Proactive Refactoring)**: Monitors structural health and prevents architectural bloat.
   - **Triggers**: Commit intervals or manual scan, configured in `protocol.json["autonomous_maintenance"]`.
   - **Metrics**: File saturation, git churn, protocol saturation, coupling, and tech debt backlog thresholds are defined in `protocol.json["autonomous_maintenance"]`.
   - **Action**: Auto-generates a proposal for architecture refactoring. Never auto-executes.

### Self-Care Cycle (Event-Based)

> Requirement: C4 from docs-v2/user/requirements.md

Self-care is **event-driven** (not time-based) to save tokens when there is nothing to do.

**Trigger Events (Configured in `protocol.json["autonomous_maintenance"]`)**:
- `session_end`: User runs ctx-end or ctx-save (SelfHealer + DocsSyncer).
- `error_threshold`: Consecutive failures threshold reached for any peer (SelfHealer, immediate).
- `commit_interval`: Git commits threshold reached (SaturationDetector).
- `manual`: User runs `saturation_scan.py` directly (All subsystems).

**Self-Care Procedure (on trigger)**:
```text
1. [Observe]  Read health.json, runtime-directives.jsonl, active-lessons.jsonl
2. [Validate] Check junctions (virtualizer.py status), stale paths, invariant completeness
3. [Cleanup]  Remove expired directives (TTL expired), compact old logs
4. [Scan]     saturation_scan.py — check file saturation, git churn, coupling
5. [Propose]  If saturation or systemic errors are detected: auto-generate proposal via the hub CLI (exact CLI flag pending AT-0 roadmap). Never auto-execute.
6. [Sync]     DocsSyncer: apply any finalized capsules via sync_docs.py (DRY-RUN only)
7. [Record]   Write self-care summary to _archive/self-care-log.jsonl
```

**System Cannot Self-Apply**:
- Self-evolution proposals require human approval before execution.
- SaturationDetector/SelfHealer findings result in a proposal only (read-only trigger).
- DocsSyncer is dry-run/propose only.

## 5. Implementation Status

| Component / Subsystem | Status |
|-----------------------|--------|
| `protocol.json` autonomous_maintenance section | ✅ Present/enabled in config (triggers wired); scope of safe Tier-0 actions still bounded — autonomous mutation DROPPED (observe/propose only) |
| `saturation_scan.py` (Phase 2) | ✅ `_sys/checks/saturation_scan.py` |
| `sync_docs.py` / DocsSyncer (Phase 3) | ✅ DRY-RUN only via `_sys/checks/sync_docs.py` |
| `self_care.py` event pipeline + ctx_end wiring | ✅ `_sys/checks/self_care.py` |
| Lesson Injection (`active-lessons.jsonl`) | ✅ IMPLEMENTED (load/inject) |
| Knowledge Triage/Approval + Pack Compilation | ⏳ deferred-to-roadmap |
| SelfHealer autonomous mutation/actions | ❌ DROPPED (trust risk) |
