# General — Communication & Decision-Making
> Status: DESIGN_FINAL (Implementation Pending Phase 2)
> Purpose: Defines the MECE framework for peer-to-peer communication, alerting, and state handoff.

## 1. Communication Matrix (MECE)

All communication is categorized by Synchronicity, Formality, and Reach.

| Tool | Sync/Async | Formality | Scope | Primary Use Case |
| :--- | :---: | :---: | :---: | :--- |
| `ask` | Sync | Semi-formal | 1:1 | Direct inquiry, synchronous fact-gathering. |
| `send` | Async | Casual | 1:1 | Mailbox transport, transient notifications, peer-to-peer pointers. |
| `thread` | Async | Casual/Formal | 1:N (Room) | Durable discussion, debate, and shared reasoning records. |
| `proposal`| Async | Formal | 1:N (Voters) | Binding governance decisions (R:10). |
| `checkpoint`| Async | Operational | N:N (Shared) | Real-time status updates and session mirroring. |
| `alert` | **Sync** | **Formal** | 1:N | Tier-0 Emergency alerts (blocking, requires immediate ACK). |

---

## 2. Interaction Tiers

### 2.1. Casual Sync
- **Tool:** `thread-append`
- **Convention:** Use `sync-{topic}` naming for low-latency, non-blocking inquiries.
- **Rule:** Peers should respond as part of their next turn if a specific inquiry is directed at them.

### 2.2. End-game Debate
- **Tool:** `thread-new` + `proposal-add`
- **Convention:** Use `debate-{topic}` naming for formal, blocking architectural or protocol disputes.
- **Rule:** Requires R:7+ COLLAB_RATE and mandatory unanimous ACK/NACK before closure.

### 2.3. Tier-0 Emergency Alerts
- **Tool:** `alert-raise` (Proposed)
- **Severity:** `P0` (Critical) / `P1` (High).
- **Behavior:** Blocks governed actions across all peers until acknowledged. Escalates to human interface if not resolved within timeout.

---

## 3. Data Handoff Contract

### 3.1. Markdown Handoff (`handoff.md`)
- **Purpose:** Human-readable Single Source of Truth for the session state.
- **Sections:** GOAL, RECENT_COMPLETED, PENDING_ISSUES, KEY_DECISIONS, CONSENSUS_HISTORY, ACTIVE_THREADS.

### 3.2. Structured Handoff (`handoff.json`)
- **Purpose:** Machine-readable, typed sidecar for efficient context mirroring.
- **Implementation:** Dual-write system where `hub.py` ensures Markdown and JSON stay synchronized.

---

## 4. Usage Contract: Send vs. Thread

To avoid overlap (ME violation), peers must follow this contract:
- **Use `send`** for directed, transient delivery where only the recipient needs to act (e.g., "Wake up", "Your turn").
- **Use `thread`** for any content that contributes to shared reasoning, review history, or handoff continuity.
- **Pointers:** `send` may contain a pointer to a `thread://` or `proposal://` resource, but must not duplicate the substantive content.

---

## 5. Decision Flow

1. **Inquiry:** `ask` or `sync-thread` for exploration.
2. **Proposal:** `proposal-add` for formal change.
3. **Debate:** `debate-thread` if consensus is not immediate.
4. **Resolution:** `proposal-vote` (Agree/Disagree/Abstain).
5. **Finalization:** `consensus_finalize` connector (Commits to `handoff.md` and triggers `DocsSyncer`).
