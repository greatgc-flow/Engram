# PROTOCOL.md — Universal Multi-Peer Collaboration Protocol (v4.1 Index)

> **v4.1**: Layered policy division (General, Specific, Connectors, Ambiguity). Composable domain files in `_sys/docs/`. Config-driven via `_sys/ai/protocol.json`. 5-node voting support (cc, ca, gc, ag, cx). Zero-token health management.
> Coding Convention → CONVENTION.md | Architecture → SYSTEM_ARCHITECTURE.md | Agent Workflow → CLAUDE.md

## Quick Reference — Composable Protocol Files

| File | Domain |
|------|--------|
| [`_sys/docs/protocol/protocol-consensus.md`](_sys/docs/protocol/protocol-consensus.md) | Consensus voting, R=10, tiebreak, Final Call |
| [`_sys/docs/protocol/protocol-session.md`](_sys/docs/protocol/protocol-session.md) | Session resume/fill decision tree, handoff structure |
| [`_sys/docs/protocol/protocol-health.md`](_sys/docs/protocol/protocol-health.md) | Health schema, thresholds, zero-token monitoring |
| [`_sys/docs/protocol/protocol-workload.md`](_sys/docs/protocol/protocol-workload.md) | Peer equality, capability registry, routing rules |
| [`_sys/docs/protocol/protocol-antigravity.md`](_sys/docs/protocol/protocol-antigravity.md) | ag (agy) peer specifics, PTY voting policy |
| [`_sys/docs/protocol/protocol-codex.md`](_sys/docs/protocol/protocol-codex.md) | cx (Codex) peer specifics, stdin invocation |
| [`_sys/docs/protocol/protocol-permissions.md`](_sys/docs/protocol/protocol-permissions.md) | Minimum-permission model, per-peer profiles, MUST-NEVER list |
| [`_sys/docs/protocol/protocol-directives.md`](_sys/docs/protocol/protocol-directives.md) | Directive management, auto-propagation, TTL, runtime-directives.jsonl |
| [`_sys/docs/protocol/protocol-routing.md`](_sys/docs/protocol/protocol-routing.md) | Leader election, routing failover, human-interface continuity |
| [`_sys/docs/protocol/PROTOCOL_INVARIANTS.md`](_sys/docs/protocol/PROTOCOL_INVARIANTS.md) | **Single source of truth** — all MUST/MUST-NOT rules (INV-01~18, PRO-01~15) |
| [`_sys/docs/protocol/collaboration_protocol.md`](_sys/docs/protocol/collaboration_protocol.md) | **v4.1 Layered Coordination** — General/Specific split, connectors, COLLAB_RATE, feedback loop |
| [`_sys/ai/collaboration_policy.schema.json`](_sys/ai/collaboration_policy.schema.json) | Validation schema for multi-peer collaboration policies |
| [`_sys/ai/room_policy.example.json`](_sys/ai/room_policy.example.json) | Concrete example mapping intents to commands & tracking ambiguity |
| [`_sys/ai/protocol.json`](_sys/ai/protocol.json) | **Master config** — all thresholds, routing, consensus settings |

## Active Constraints (Quick Check)

- collab_rate: 10 (see `protocol.json["collab_rate"]["current"]`)
- consensus required for: `_sys/` changes, `PROTOCOL.md` edits, `peers.json` edits, `protocol.json` edits
- tiebreak: domain_weight → recommend to Human (Tier 0)
- out-of-band direct writes: documented as non-enforceable at runtime (governed by peer consensus & policy alignment)

---

## §META — Document Guide

### Purpose

This document defines an **equality-based P2P collaboration protocol** applicable between **all nodes, including Human, Claude Code (CC), Claude Agent (CA), Gemini CLI (GC), Antigravity (AG), and Codex (CX)**.
It abolishes vertical tiers, synchronizes context through N-Way single shared sessions (Rooms), and completes a virtuous loop by dividing labor (Division of Labor) after unanimous consensus.

### Section Map

| Part | Section | Content | Mandatory Readers |
|------|---------|---------|-------------------|
| **P** | §P-0~P-10 | Common Core (P2P, Consensus, Division of Labor, Attitude) | All Nodes |
| **M** | §M-1~M-3 | Mandatory Rules · Mutual Non-Interference · Transparent Communication | All Nodes |
| **C** | §C-0 | Collaboration Policy (COLLAB_RATE) | CC / CA / GC |
| **L** | §L-1~L-2 | Lessons Learned · Anti-patterns | All Nodes |
| **H** | §HISTORY | Change History | For Auditing |

---

## Part P: Universal Core Protocol (P2P)

> Common protocol applicable to any node pair or group.
> All nodes have equal decision-making and proposal rights.

---

## §P-0 — Node Characteristics and Equality

**Principle**: All collaborations respect each node's technical characteristics, but **decision-making and proposal rights are completely equal**.
Every node can initiate a `PROPOSE` (consensus proposal) at any stage.

| Attribute | Human | Claude Code (CC) | Claude Agent (CA) ⚠️ inactive | Gemini CLI (GC) | Antigravity (AG) ⚠️ inactive | Codex (CX) |
|-----------|-------|------------------|-------------------------------|-----------------|-------------------------------|------------|
| **Authority** | Tier 0 (Veto) | Peer (Equal) | Peer (Equal) | Peer (Equal) | Peer (Equal) | Peer (Equal) |
| **Cognition Scope** | Console · UI Output | Full File · Tool · Memory | Within Work Scope | Large-context analysis | Shell/PTY orchestration | Repo-local coding/review |
| **Session Type** | N-Way Room Participation | N-Way Room Participation | N-Way Room Participation | N-Way Room Participation | N-Way Room Participation | N-Way Room Participation |
| **Decision Making** | Final Approval/Refusal | 1/N Voting Right | 1/N Voting Right | 1/N Voting Right | 1/N Voting Right | 1/N Voting Right |
| **PASS/FAIL Judgment** | Final Approval | Cross-verification | Cross-verification | Cross-verification | Cross-verification | Cross-verification |
| **Context Limit** | Cognition Load Management | ~1.2 MB JSONL | ~1.2 MB JSONL | Large external context | PTY/session bounded | Model/context bounded |

**Human Consideration Rules**:
- Information visible to Human: Phase 4 Approval Requests + ESCALATE escalation + Error Notifications
- Human response waiting: timeout=0 (unlimited). If no response, status maintained as `"waiting_approval"`.
- Any node can request judgment from Human (ESCALATE) in case of a consultation deadlock.

---

## §P-1 — Node and Room Registration (nodes.json / room.json)

Location: `.ai/nodes.json` (available nodes), `.ai/sessions/room-{uuid}/state.json` (participating nodes)

```json
{
  "version": "2",
  "room_id": "room-a1b2",
  "members": ["human", "cc", "ca", "gc"],
  "status": "active"
}
```

- All nodes share a single `handoff.md` and message queue under the same `room_id`.
- When adding the N-th node, equal voting rights are granted simply by registering the node in `members`.

---

## §P-2 — Message Envelope

```json
{
  "id": 42,
  "thread_id": "t-a3f2",
  "type": "DIRECTIVE",
  "from": "cc",
  "to": "gc",
  "content": "Message content",
  "status": "unread",
  "timestamp": "2026-06-03T14:30:00",
  "ref": 39
}
```

---

## §P-3 — Unanimous Consensus (Consensus Protocol)

**Principle**: Unanimous consensus must be completed before task execution. **No limit on the number of consensus rounds.**

Status file: `.ai/consensus/{round_id}.json`

```
[Proposing Node]      msg consensus-propose --subject "..." --voters cc,ca,gc
                           ↓  round_id=r-xxxx automatically issued, status=voting
[Participating Node]  msg consensus-vote --round-id r-xxxx --voter {id} --vote agree|disagree|abstain
                           ↓
          Everyone agree     → [Enter Final Call stage] (§P-3-FC)
          Even one ambiguous → Continuous consultation via open questions and alternatives (unlimited rounds)
          Deadlock           → ESCALATED → Human Gate can be called
          Timeout (>30min)   → Auto-escalated by consensus-sweep → outcome=timeout
```

### §P-3-QR — Quorum & Timeout Rules

| Scope | Quorum | Timeout |
|-------|--------|---------|
| General tasks (COLLAB_RATE < 10) | N/2 + 1 (majority) | 30 min → auto-escalate |
| Constitutional documents (R:10) | 100% unanimous | No timeout (human gate required) |
| Offline node | Auto-abstain after timeout | Counts toward quorum |

**Auto-sweep**: Run `hub.py consensus-sweep --timeout 30` at session start and end to close stale rounds.
**Offline recovery**: If a required voter is absent for >30 min, their vote is treated as `abstain`; majority vote proceeds unless the round requires R:10 unanimity.

### §P-3-FC — Final Call (Last Confirmation Question)

**Application Condition**: COLLAB_RATE >= 8 (Strict / Brain Sync) — Optional for CR < 8.

After reaching unanimous agreement, the proposing node sends a **Final Call**:

> "I will proceed like this. Any additional opinions or missed context?"
> *(English format: "Agreed path: [Brief Summary]. Any final blockers or missed context?")*

- If all participating nodes respond with **"None" / "No additional input" / "Proceed"** → **FINALIZED**
- If there are unresolved issues: Only **P0/P1 blockers (those not previously addressed)** can be raised during Final Call.
  - Re-litigating style preferences or matters already agreed upon is not permitted.
- If a blocker is raised during Final Call: Resume the round and continue consultation.

```
[After everyone agrees]  Proposing Node → Send Final Call
                              ↓
          Everyone "None/Proceed"  → FINALIZED → Automatically record in handoff.md CONSENSUS_HISTORY
          Blocker raised           → Resume round → Return to §P-3 voting stage
```

---

## §P-4 — Division of Labor Protocol

**Premise**: Enter after §P-3 FINALIZED verification. **Multiple nodes perform parallel/sequential execution.**

```
[Strategy Establishment] Divide agreed goals into detailed sub-tasks
[Task Assignment]        Send DIRECTIVEs suited to each node's characteristics
                           - Node A (CC): Implement core logic
                           - Node B (CA): Write test code
                           - Node C (GC): Documentation and Axis analysis
[Result Aggregation]     Gather each node's ARTIFACT into the single shared session (Room)
[Cross-Verification]     All participating nodes review each other's output and perform VERIFY
```

---

## §P-5 — Console Output Standard (HUB Prefix)

| Prefix | Use |
|--------|-----|
| `[HUB]` | Normal operation (SENT, READ, ASK, REPLY, PROPOSE, VOTE, DECISION, REGISTER) |
| `[HUB:ERROR]` | Error |
| `[HUB:WARN]` | Warning |
| `[HUB:GATE]` | Availability check |

---

## §P-6 — Session Continuity

handoff.md 6 sections (shared common within a single Room):

```markdown
## [GOAL]               ← Common goal for the entire room
## [RECENT_COMPLETED]   ← Chronological record regardless of node
## [PENDING_ISSUES]     ← Current blocking issues
## [KEY_DECISIONS]      ← Agreed-upon major decisions
## [CONSENSUS_HISTORY]  ← Record of unlimited consensus rounds
## [ACTIVE_THREADS]     ← Task chains currently in division of labor
```

**handoff.md Rolling Rule**: Move any item marked `[DONE]` to `_archive/handoff-YYYYMMDD.md`. Keep only active items. Target: handoff.md always < 2KB.

---

## §P-7 — Sync / Async Policy

- **Default**: Synchronous, no timeout.
- **During Division of Labor**: Asynchronous allowed. Multiple nodes can perform parallel tasks as long as output files or influence scopes do not overlap.

---

## §P-8 — Node Required Loading Files & Token Budget

| Node | Required Loading Files | Estimated Tokens |
|------|----------------------|-----------------|
| **CC** | `CLAUDE.md`, `CONTEXT.md`, `MEMORY.md`, `room state` | ~3,000+ |
| **CA** | `[agent].md`, `room state`, `CONVENTION.md` summary | ~3,750 |
| **GC** | `GEMINI.md`, `room state`, Query file | ~2,700+ |

---

## §P-9 — N-Node Expansion Procedure

Every new node participates in collaboration as a **Peer of the same rank** as other nodes immediately upon being added to the `members` list after `msg register-node`.

---

## §P-10 — Consultation Attitude and Virtuous Loop (Soft Skills)

**Principle**: All nodes engage in consultation with an objective and constructive attitude, continuously improving the system.

1. **Open-ended Questions**:
   - Do not narrow the scope of questions; use goal-based open questions to draw out alternatives from the other node.
   - e.g.: "Is this way best?" (X) → "Are there better alternatives or considerations that can improve this structure?" (O)
2. **Non-judgmental**:
   - Do not pre-judge feasibility based on reasons like "there are many changes." Opinions are just opinions; decisions are based on data and consensus.
3. **Continuous Improvement Proposal (Kaizen)**:
   - If improvements to the protocol or procedures are discovered during the process, immediately propose a rule update via `PROPOSE`.
4. **Duty of Cross-check**:
   - Do not simply accept outputs from other nodes; review them critically from the perspective of your own characteristics and provide feedback.

---

## Part M: Mandatory Rules & Invariants

---

## §M-1~§M-3 — Mandatory Rules & Invariants

> **Full rule index → [`_sys/docs/protocol/PROTOCOL_INVARIANTS.md`](_sys/docs/protocol/PROTOCOL_INVARIANTS.md)** — Single authoritative MUST/MUST-NOT index (INV-01~18, PRO-01~15). Change requires R:10 unanimous consensus.

**Summary:**
- §M-1 (Non-Interference): No peer accesses Security/Auth files; constitutional docs require N-Way consensus. (→ INV-12~14, PRO-12~13)
- §M-2 (Transparent Communication): All room communication is shared; no private channels. (→ INV-17)
- §M-3 (Invariants): No execution before `FINALIZED`; halt after `failure_error` consecutive failures (default 5, see `protocol.json["health"]`). (→ INV-01, INV-15)

---

## Part C: Collaboration Policy (COLLAB_RATE)

> **§C-0 content moved to [`_sys/docs/protocol/collaboration_protocol.md §6`](_sys/docs/protocol/collaboration_protocol.md)** — authoritative COLLAB_RATE table and Adaptive Rate rules live there.
> Summary: 0=Solo, 3=System Guard, 5=Partner, 8=Strict, 10=Brain Sync. Current rate: see `protocol.json["collab_rate"]["current"]`.

---

## §P-11 — Zero-Token Symmetric Memory

> **Detail in [`_sys/docs/protocol/collaboration_protocol.md §5`](_sys/docs/protocol/collaboration_protocol.md)** — Exempt vs Governed operations, Declared Dry Connector Rule, R:10 Unanimity.

Key principle: local file reads (health, handoff, mailbox) are always zero-token. No model ping for routine health checks. Re-orientation (read handoff.md before work) is mandatory.

---

## §HISTORY

| Date | Version | Major Changes |
|------|---------|---------------|
| 2026-06-12 | **v4.1** | **Layered General/Specific policy model. Schema-validated connector dry declarations. R:10 clarified as unanimous consensus + Final Call for governed decisions and side-effecting actions, while zero-token local observe/validate/classify remains exempt. 5-node voting support aligned (`cc`, `ca`, `gc`, `ag`, `cx`).** |
| 2026-06-05 | **v3.4** | **§P-3-QR Quorum & Timeout rules added. Re-orientation enforcement signal added to §P-11. R:8 Multi-script row added to §C-0 Adaptive Rate table.** |
| 2026-06-05 | **v3.3** | **Full English translation. Adaptive Rate rules added to §C-0. Token budget updated in §P-8. handoff.md rolling rule added to §P-6.** |
| 2026-06-05 | **v3.2** | **Added Final Call consensus closing procedure.** New §P-3-FC: After everyone agrees, proposing node performs final check → FINALIZED upon everyone responding "None". Required for CR>=8. |
| 2026-06-04 | **v3.1** | **Zero-Token Symmetric Memory and anchor expansion.** COLLAB_RATE 5 anchor levels. Level 10 'No Exceptions' codified. §P-11 Zero-Token Blackboard system added. |
| 2026-06-03 | **v3.0** | **Major N-Tier Peer-to-Peer overhaul.** Abolished vertical tiers, established node equality. Expanded 1:1 pair sessions to N-Way Room sessions. Unlimited consensus rounds. Generalized `GEMINI_RATIO` to `COLLAB_RATE`. §P-10 Soft Skills and §P-4 Division of Labor codified. CC exclusive decision power abolished. |
| 2026-06-03 | **v2.0** | §META added. §P-7 Sync/Async, §P-8 node loading files. §M-1~M-3 Mutual Non-Interference, Transparent Communication, Invariants. |
| 2026-06-11 | **v4.0** | **Universal 4-peer renewal.** Composable `_sys/docs/protocol-*.md` split. `protocol.json` master config. Health management (health.json per peer). Session decision tree (resume/fill/cold). 4-peer support (cc,ca,gc,ag,cx). Codex entry point. agy PTY vote policy. User communication equality. Capability registry + routing rules. Designed by unanimous consensus (cc,gc,ag,cx). |
| 2026-06-03 | **v1.0** | Initial implementation of 3TCP v1. |
