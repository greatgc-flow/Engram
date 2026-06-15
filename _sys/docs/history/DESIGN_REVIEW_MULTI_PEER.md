# Design Review: Multi-Peer Orchestration & Continuity
> Target: P:\ Portable Multi-Peer System (v4.1)
> Date: 2026-06-12

## 1. Executive Summary
This document provides a MECE (Mutually Exclusive, Collectively Exhaustive) design review for implementing dynamic leader selection, peer role assignment, model health management, and work continuity in the portable P2P system. It proposes concrete config, schema, and runtime changes that strictly adhere to the established equal-authority protocol while fulfilling the requirements from `TAXONOMY_v10.md` and `protocol.json`.

---

## 2. MECE Detailed Discussion

The design is decomposed into two major independent axes: **Execution Orchestration** (Who does what and when) and **System Resilience** (How the system survives and continues).

### 2.1. Execution Orchestration (Roles & Leadership)
**Concept**: Decouple Node IDs from Responsibilities.
*   **Leader Selection**: True P2P systems avoid static dictators. Leadership should be temporary and tied to a domain (e.g., `cx` leads coding, `gc` leads planning). The "Leader" is simply the peer holding the `Proposer` role for the current phase.
*   **Peer Role Assignment**: Roles (Architect, Reviewer, Coder) must be dynamically assigned at runtime. A peer can hold multiple roles, and roles can be re-assigned based on peer health and capability routing rules.

### 2.2. System Resilience (Health & Continuity)
**Concept**: Zero-token monitoring and persistent context state.
*   **Model Health Management**: Extend the existing `health.json` paradigm to include a "Governance Health Pre-Check" before any delegation. This prevents cascading failures by isolating degraded models before they corrupt the consensus.
*   **Work Continuity**: The `handoff.md` file is the source of truth, but manual edits are prone to formatting errors. Continuity requires programmatic, rolling updates to handoff sections to guarantee compliance with the `[GOAL]`, `[PENDING_ISSUES]`, etc., schema limits (e.g., Max 12KB).

---

## 3. Proposed Architecture Changes

### 3.1. Schema & Config Changes
**1. `.ai/state.json` (Runtime State)**
*   Add a `roles` dictionary mapping Role IDs to Node IDs.
*   Add a `current_leader` field representing the active domain leader.
*   *Schema Addition*:
    ```json
    "roles": {
      "architect": "cc",
      "coder": "cx",
      "reviewer": "ca"
    },
    "current_leader": "cc"
    ```

**2. `_sys/ai/orchestration.json` (Static Config)**
*   Define a `roles_registry` mapping valid roles to their expected capabilities.

### 3.2. Runtime Changes (`hub.py`)
Introduce three new minimal viable sub-commands to bridge the gap between human intent and automated governance:

1.  **`hub.py assign-role --role {role_id} --peer {peer_id}`**
    *   *Action*: Updates `.ai/state.json`'s `roles` mapping. Emits a `[HUB]` log for observability.
    *   *Validation*: Checks if peer exists in `members`.
2.  **`hub.py health-precheck`**
    *   *Action*: Iterates over all active members. Reads their `health.json`. Returns an aggregated status (e.g., `GREEN`, `YELLOW`, `RED`). Exits with code `1` if any critical role holder is `RED`.
3.  **`hub.py append-handoff --section {section_name} --text {content}`**
    *   *Action*: Safely appends an item to a specific section in `handoff.md`, enforcing the line/item limits defined in the protocol.

---

## 4. Risks and Mitigations

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| **Role Ambiguity** (Two peers acting as leader) | High (Consensus deadlock) | `state.json` acts as the single source of truth. Lock files (`.ai/.lock`) prevent race conditions during role assignment. |
| **Health Check Latency** | Low (Slow down operations) | Stick to the Zero-Token principle. `health-precheck` only reads local `health.json` files, ensuring sub-10ms latency. |
| **Handoff File Corruption** | High (Loss of context) | `append-handoff` will use atomic writes or temporary file swapping. |

---

## 5. Improvement Backlog (Future Work)
*   **[ROLE-01] Role Auto-reassignment**: If a peer holding a critical role drops to `RED` health, auto-trigger a consensus round to re-assign the role to the fallback peer (defined in `routing_rules`).
*   **[HEALTH-01] Cross-Peer Health Healing**: If `cx`'s context is bloated (`YELLOW`), allow `gc` to perform a summarizing operation to shrink it back to `GREEN`.
*   **[CONT-01] Handoff Garbage Collection**: Implement TTL on items inside `[RECENT_COMPLETED]` to automatically prune the file when it nears 12KB.
*   **[ORCH-01] Consensus Tie-Break Automation**: Automatically apply the Domain Weight from `capability_registry` when a vote is split.

---

## 6. Minimal Viable Implementation Plan (Next Steps)
1. Modify `_sys/ai/orchestration.json` to include `roles_registry`.
2. Update `_sys/core/hub.py` to initialize `roles` and `current_leader` in `state.json`.
3. Implement `assign-role`, `health-precheck`, and `append-handoff` commands in `hub.py`.
