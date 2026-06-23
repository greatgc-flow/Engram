# General — Communication & Decision-Making
> Status: ACTIVE WITH EXPLICIT PLANNED GAPS
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

### 2.3 Tier-0 Emergency Alerts

- **Implemented:** `alert-raise`
- **Current behavior:** records `state.alert_active`, sets the human-readable
  `state.blocked` marker, and sends CRITICAL mailbox notifications.
- **PLANNED:** enforced `_guard_action` blocking, per-peer ACK, timeout escalation,
  and alert-clear lifecycle. The current blocked marker is not an execution guard.

---

## 3. Data Handoff Contract

### 3.1. Markdown Handoff (`handoff.md`)
- **Purpose:** Human-readable Single Source of Truth for the session state.
- **Sections:** GOAL, RECENT_COMPLETED, PENDING_ISSUES, KEY_DECISIONS, CONSENSUS_HISTORY, ACTIVE_THREADS.

### 3.2 Structured Handoff (`handoff.json`)

Implemented. `_write_handoff()` writes `handoff.md` and `handoff.json`; reads prefer
the typed JSON sidecar and fall back to Markdown.

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
3. **Debate:** `thread-new --topic debate-{topic}` plus `thread-append`.
4. **Resolution:** `proposal-vote` or `consensus-vote`, depending on the selected
   governance record.
5. **Finalization:** `consensus-vote` auto-finalizes when all votes are cast,
   appends `CONSENSUS_HISTORY`, and emits a Decision Capsule.
6. **PLANNED automation:** no dedicated `consensus_finalize` hub action currently
   exists. DocsSyncer exists as `_sys/checks/sync_docs.py`, but self-care invokes
   it in dry-run mode and finalization does not automatically apply documentation.
