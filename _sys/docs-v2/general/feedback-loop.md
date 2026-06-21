# General — Continuous Feedback Loop (5 Whys)
> Source: feedback.jsonl | Status: ACTIVE

---

## 1. The Virtuous Cycle
Every task execution and failure feeds into a self-healing loop designed to achieve a Zero-Code MECE Architecture. Hardcoded workarounds are strictly forbidden; all resolutions must be configured in JSON or governed docs.

### The Loop
1. **Detect (Observer)**: `hub.py` execution wrappers, `check-health.bat`, or `self_care.py` detects an anomaly, timeout, or repeated error. This is logged to `ipc-log.jsonl` and `cost-log.jsonl`.
2. **Analyze (5-Whys)**: When a threshold of failures is met, `self_care.py` (or a designated peer acting as `observer`) asks "Why did this fail?" recursively until reaching the root configuration/documentation gap.
3. **Mitigate (Runtime Directive)**: `hub.py` automatically injects a temporary `runtime-directives.jsonl` rule to quarantine or instruct peers around the issue immediately (TTL-bound).
4. **Resolve (Permanent Consensus)**: Before the directive expires, a peer proposes a permanent fix via Consensus. The fix MUST be:
   - A change to `protocol.json` or `routing-config.json` (JSON Settings).
   - A change to `Docs_v2/` (Guidelines).
   - A logic fix in `hub.py` (Source Engine).
5. **Close (Active Lessons)**: The root cause is categorized in `feedback.jsonl`, completing the loop and preventing recurrence.

---

## 2. 5-Whys Root Cause Analysis (Standard Procedure)

When performing analysis, peers MUST use the 5-Whys method.
Example:
*   **Problem**: Peer `gc` failed with `sandbox_spawn_eperm`.
*   **Why 1**: `gemini.bat` could not write to `_sys/gemini/config/state.json`.
*   **Why 2**: The file lock was held by another process.
*   **Why 3**: The previous `hub.py ask` process crashed and orphaned the lock.
*   **Why 4**: Heartbeat/Lease timeout was too long, so the lock wasn't released.
*   **Why 5**: `protocol.json["communication_policy"]["lease_timeout_sec"]` is set to 1800, which is too high for fast failover.
*   **Resolution**: Update JSON config to `300` (or appropriate value) instead of hardcoding timeouts in Python.

---

## 3. Configuration

All statuses, paths, and categories for the feedback loop are managed in:
**`protocol.json["feedback_loop"]`**
