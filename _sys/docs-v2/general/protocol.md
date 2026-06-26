# General Protocol
> Applies to ALL peers. Specific deltas → `specific/{peer}.md`.
> Pillar consolidates {protocol, consensus, communication, tradeoffs}.
> Source: collaboration_protocol.md v4.1

---

## 1. Principles & Governance Roles

### 1.1 General-Specific Resolution Order
```
default → general → project → room → peer → task
```
Lower layers may only **narrow or add stricter** constraints — never weaken or bypass General invariants.
Peer equality = equal proposal/review/vote rights. Human veto always overrides.

**Rule:** English is the mandatory language for all internal reasoning, handoffs, and system logs (INV-19).

### 1.2 Governance Roles & Terminal Invariant (GAP-1)
**Terminal-transport invariant (GAP-1):** The human-interface terminal may frame, route, relay, and summarize worker outputs, but MUST NOT perform substantive task analysis once a worker is selected. "Coordinator"/"leader" is a task role assigned by protocol, not terminal authority. *(Cross-reference: Indexed in `10-invariants.md`)*.

### 1.3 Required Safety Dimensions
Policy schema MUST cover: versioning · authority · precedence · lifecycle · concurrency/locks · idempotency · observability · failure modes (fail closed) · security/privacy · extension fields (`x-*`).

---

## 2. System Trade-offs & Tunable Parameters

This section tracks tunable system parameters and the operational trade-offs involved in their adjustment. **A1 Compliance:** The policies and meanings of these parameters are defined here, but the values-of-record are located in their respective JSON configuration files (e.g., `protocol.json`, `_sys/ai/orchestration.json`, `governance_params.json`). Do not hardcode specific system state values here.

### 2.1 Tunable Parameters Policy
| Parameter | Description | Trade-off | Value-of-Record Location |
| :--- | :--- | :--- | :--- |
| **COLLAB_RATE** | Collaboration depth & consensus requirement | Token cost vs. Consensus quality | `protocol.json` -> `collab_rate.current` |
| **EFFORT** | Model effort level per peer | Speed vs. analytical depth | `_sys/ai/orchestration.json` -> `hub_nodes[].profiles` |
| **SLIM** | Protocol message/handoff verbosity | Token savings vs. Comprehension quality | `_sys/ai/orchestration.json` -> `session.slim_mode` |
| **SANDBOX** | Process/Tool isolation level | Execution speed vs. System safety | `governance_params.json` -> `security.sandbox_level` |
| **LEADER_REELECT_PER_TASK** | Force re-election for every discrete task | Optimal routing vs. Transactional overhead | `protocol.json` -> `leader_election.reelect_per_task` |

### 2.2 Runtime Adjustment
Parameters can be adjusted via the following methods:
- **CLI**: `python _sys/core/hub.py update-config --key {key} --value {value}`
- **Direct Edit**: Modifying the JSON config files (requires `COLLAB_RATE: 10` consensus for governed files).
- **Session Override**: Passing flags to `hub.py ask` (e.g., `--collab-rate 5`).

### 2.3 EFFORT (Model Intent) Policy
- **Low**: Quick syntax fixes, single file reads, status checks.
- **Medium**: Default for most implementation tasks.
- **High**: Complex refactoring, architectural review, deep debugging.

### 2.4 SLIM (Context Management) Policy
- **True**: Used during stable phases to minimize token burn.
- **False**: Required during "Exhaustive Review" or "Re-orientation" phases where full context is critical.

### 2.5 SANDBOX (Safety) Policy
- **Full**: Recommended for untrusted third-party code or experimental scripts.
- **Partial**: Default for `workspace/` operations.
- **Off**: Only for trusted `_sys/` core migrations (requires human oversight).

*(Cross-References: `protocol.json` is the primary runtime SSOT for `COLLAB_RATE` and election logic. `governance_params.json` is the secondary budget and safety parameters).*

---

## 3. Task Execution & Feedback Loop

### 3.1 Canonical Feedback Loop
```
observe → classify → decide → sync → act_or_ask → record → handoff → improve
```
- **observe**: read state.json, handoff.md, health, mailbox, runtime-directives.jsonl
- **classify**: map to declared rules (no semantic invention)
- **decide**: local action / connector / peer ask / human escalation
- **sync**: acquire lock, resolve contention
- **act_or_ask**: execute connector, ask peer, or escalate
- **record**: write provenance + classify ask outcome via `_record_ask_success/failure()`
- **handoff**: compact durable state; large content as file refs
- **improve**: resolved ambiguity → Specific rule or General proposal

**Operational Health Sub-Loop (automated, zero-token)**
```
ask_outcome → _record_ask_success/failure()
           → health.json updated
           → routing precheck reads health.json
           → RED/gate-closed peers excluded
           → peer-recover → routing restored
```

### 3.2 Plan-Do-See Cycle
> Requirement: E4 from docs-v2/user/requirements.md

Every substantive task follows this 3-phase loop. Repeats until task is complete.
```
┌─ PLAN ──────────────────────────────────────────────────────────┐
│  1. Scan available resources (health.json, handoff.md, docs)    │
│  2. Estimate token budget; chunk if task exceeds single session │
│  3. Get user approval on plan before execution                  │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─ DO ────────────────────────────────────────────────────────────┐
│  4. Execute one chunk                                           │
│  5. Report any delta (new info, blockers found mid-execution)   │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─ SEE ───────────────────────────────────────────────────────────┐
│  6. Checkpoint: cross-verify output against plan               │
│  7. If gaps found → loop back to PLAN                          │
│  8. If complete → record in handoff.md + report to user        │
└─────────────────────────────────────────────────────────────────┘
```
**Exception path**: on any failure → `[HALT: <reason>]` → propose workaround → human approval required before retry.

### 3.3 Zero-Token Boundary
**Exempt (no COLLAB_RATE gate):**
- `local_observe/read`: file/dir reads and environment state
- `local_validate/schema`: syntax, schema, declared dry checks
- `local_classify/risk routing`: static metadata routing (no edits)

**Governed (subject to COLLAB_RATE):**
- Write operations, workspace edits, command executions with side-effects
- A command is NOT exempt because it's "described as dry" — requires declared connector metadata

**Pre-Consensus Peer Asks:**
- Info gathering (non-binding): permitted without prior consensus
- Binding vote/approval: MUST follow consensus protocol
- NO implementation may execute based on non-binding gathering

### 3.4 Ambiguity Contract
Every ambiguity entry records: uncertainty · candidate interpretations · confidence · ask_threshold · escalation_vector · owner · status · resolution_reference.

If confidence < ask_threshold → MUST ask or escalate before acting.
If local records conflict and no rule resolves → fail closed (ask/escalate).

---

## 4. Collaboration & Consensus

### 4.1 COLLAB_RATE — Collaboration Depth
Zero-token local operations (observe/validate/classify) are **exempt** from COLLAB_RATE at all levels.
> **Always zero-token (explicit list):** reading `health.json`, `handoff.md`, `mailbox.json`, `runtime-directives.jsonl`, `user-directives.md` — regardless of COLLAB_RATE. See `general/lifecycle.md §7`.

*(Values for these modes are referenced in `protocol.json["collab_rate"]["current"]`)*

| Rate | Mode | Autonomy | Rule / Peer Consensus Requirement | Applies to (Risk Category) |
|:----:|:-----|:--------:|:-----|:-----------|
| 0 | Solo / Observe | 100% | Fully autonomous. No consensus required (Exempt). | Low: Read-only, grep, explore, doc reads |
| 3 | System Guard / Workspace | 75% | Informal notification or single peer review. `_sys/` changes and constitutional docs require consensus. | Med: `workspace/` code changes |
| 5 | Partner / Sys-Single | 50% | Majority ACK (2+ peers). Consensus at design start + milestone. | High: Single `_sys/` script edit |
| 8 | Strict / Sys-Multi | 25% | Supermajority ACK (All active peers). All logic changes need consensus. Only typos autonomous. | Multi-script: Spans multiple `_sys/` scripts |
| 10 | Brain Sync / Constitutional | 0% | Unanimous ACK + Final Call (FC). ANY file modification requires prior consensus. No exceptions. | Critical: `PROTOCOL.md`, `CLAUDE.md`, `GEMINI.md`, `hub.py`, `protocol.json`, core config |

### 4.2 Round Lifecycle
```
PROPOSE → VOTE → FINALIZE
```
1. `hub.py consensus-propose --subject "..." --voters cc,ag,cx --from {peer}`
2. `hub.py consensus-vote --round-id r-XXXX --voter {peer} --vote agree|disagree|abstain`
3. Auto-finalize when all votes collected:
   - `unanimous`: All agree → Proceed
   - `abstain`: Mix of agree + abstain → Proceed
   - `human_gate`: Any disagree → Escalate to Human (Tier 0)
   - `timeout`: Stalled > 30min → Escalate to Human

### 4.3 Vote Meanings
| Vote | Meaning |
|------|---------|
| `agree` | Explicit approval |
| `disagree` | Explicit rejection (reason required) |
| `abstain` | Offline auto-abstain after `offline_auto_abstain_minutes` |

### 4.4 R:10 Rules & Quorum Authority
- All **gate-OPEN** registered voters (per the round-start snapshot — see Gate-Based Quorum below, D-08g/INV-28) MUST explicitly `agree` before FINALIZE. RED/STALE/quarantined peers are excluded from the snapshot denominator N — NOT counted as silent approval.
- Offline auto-abstain does NOT satisfy agreement; a gate-OPEN required voter that goes offline mid-round with no prior `agree` blocks finalization → escalate to Human (Tier 0).
- Any explicit `disagree` from a gate-OPEN voter blocks; requires resolution or Human override.
- PTY peers (ag): write vote directly to `.ai/consensus/{round_id}.json` OR relay via `hub.py send --to cc` (NEVER `hub.py ask` — PTY deadlock risk).

**Gate-Based Quorum (D-08g)**
- **Gate-OPEN peers only**: Only peers whose health gate is OPEN at round-start count toward quorum. A gate-CLOSED peer's timeout is gate-closure (availability loss), NEVER silent approval.
- **At COLLAB_RATE = 10**: Every gate-OPEN registered voter in `protocol.json["consensus"]["r10_voters"]` MUST explicitly vote `agree` before FINALIZE. A mid-round gate closure without a prior `agree` blocks finalization and escalates to Human (Tier 0). A previously cast `agree` remains valid.
- **At COLLAB_RATE < 10**: Mix of `agree` + `abstain` permitted if min quorum met. Any explicit `disagree` blocks; requires unanimous active consent or Human override.
- **Gate state is round-scoped**: Snapshot captured at round-start. Gate closure after snapshot does NOT change N (the quorum denominator). A previously cast vote stands through round close.
- **Voter set change**: If the effective eligible voter set must change mid-round, the round MUST restart with a fresh snapshot.
- **Stale examples updated**: `hub.py consensus-propose --voters cc,ag,cx` (gc SUSPENDED 2026-06-19).

**Quorum Authority Principle (INV-28, D-08g unanimous)**
- **Minimum quorum**: `max(2, f(N, risk))` where N = count of gate-OPEN eligible voters at round-start snapshot. f is risk-adjusted (undefined above N=3; default to N).
- **Non-proposer requirement**: At least one voter from a distinct failure domain from the proposer MUST actively `agree`. Proposer MUST NOT self-finalize.
- **Retroactive veto**: NONE for procedurally valid rounds. A peer gate-OPEN at round-start that did not vote `disagree` before FINALIZE cannot retroactively block. Exception: finalization that violates a higher-order invariant (INV-01~19) may be voided by Human.
- **Mid-round gate closure rule**: Gate closure after snapshot does not change N. At R:10, any required voter with no cast `agree` → blocks finalization. No silent-approval by inaction.

### 4.5 Final Call (INV-02, mandatory at R:8+)
Proposer sends: *"Any additional feedback or missed context?"*
All peers reply `ACK/Proceed` or raise concerns.
Round finalizes only after all ACKs received. (INV-02)

### 4.6 Tiebreak (2v2 or N/2 split)
1. Check `protocol.json["workload"]["capability_registry"]` for disputed task domain
2. Highest-domain-expertise peer recommends to Human
3. Human (Tier 0) makes final decision — no peer can override

### 4.7 Stale Round Sweep
```
hub.py consensus-sweep   # clean rounds stalled > timeout_minutes (30m)
```
Run at session end or ctx-save.

---

## 5. Communication & IPC

### 5.1 Communication Matrix (MECE)
All communication is categorized by Synchronicity, Formality, and Reach.

| Tool | Sync/Async | Formality | Scope | Primary Use Case |
| :--- | :---: | :---: | :---: | :--- |
| `ask` | Sync | Semi-formal | 1:1 | Direct inquiry, synchronous fact-gathering. |
| `send` | Async | Casual | 1:1 | Mailbox transport, transient notifications, peer-to-peer pointers. |
| `thread` | Async | Casual/Formal | 1:N (Room) | Durable discussion, debate, and shared reasoning records. |
| `proposal`| Async | Formal | 1:N (Voters) | Binding governance decisions (R:10). |
| `checkpoint`| Async | Operational | N:N (Shared) | Real-time status updates and session mirroring. |
| `alert` | **Sync** | **Formal** | 1:N | Tier-0 Emergency alerts (blocking, requires immediate ACK). |

### 5.2 Interaction Tiers
**2.1. Casual Sync**
- **Tool:** `thread-append`
- **Convention:** Use `sync-{topic}` naming for low-latency, non-blocking inquiries.
- **Rule:** Peers should respond as part of their next turn if a specific inquiry is directed at them.

**2.2. End-game Debate**
- **Tool:** `thread-new` + `proposal-add`
- **Convention:** Use `debate-{topic}` naming for formal, blocking architectural or protocol disputes.
- **Rule:** Requires R:7+ COLLAB_RATE and mandatory unanimous ACK/NACK before closure.

**2.3 Tier-0 Emergency Alerts**
- **Implemented:** `alert-raise`
- **Current behavior:** records `state.alert_active`, sets the human-readable `state.blocked` marker, and sends CRITICAL mailbox notifications.
- **PLANNED:** enforced `_guard_action` blocking, per-peer ACK, timeout escalation, and alert-clear lifecycle. The current blocked marker is not an execution guard without PRO-19 (see Terminal Guard Rule).

### 5.3 Usage Contract: Send vs. Thread
To avoid overlap (ME violation), peers MUST follow this contract:
- **Use `send`** for directed, transient delivery where only the recipient needs to act (e.g., "Wake up", "Your turn").
- **Use `thread`** for any content that contributes to shared reasoning, review history, or handoff continuity.
- **Pointers:** `send` may contain a pointer to a `thread://` or `proposal://` resource, but MUST NOT duplicate the substantive content.

### 5.4 Decision Flow
1. **Inquiry:** `ask` or `sync-thread` for exploration.
2. **Proposal:** `proposal-add` for formal change.
3. **Debate:** `thread-new --topic debate-{topic}` plus `thread-append`.
4. **Resolution:** `proposal-vote` or `consensus-vote`, depending on the selected governance record.
5. **Finalization:** `consensus-vote` auto-finalizes when all votes are cast, appends `CONSENSUS_HISTORY`, and emits a Decision Capsule.
6. **PLANNED automation:** no dedicated `consensus_finalize` hub action currently exists. DocsSyncer exists as `_sys/checks/sync_docs.py`, but self-care invokes it in dry-run mode and finalization does not automatically apply documentation.

### 5.5 Zero-Token IPC Protocol
> Requirement: B8 from docs-v2/user/requirements.md

**Echo-Back (Precision Acknowledgement)**
After receiving any instruction, peer MUST echo back its understanding before executing:
```
"Understood: [task summary in 1 line]. Proceeding."
```
No silent execution. Lossless transcription: no information added, removed, or transformed during relay.

**Coordinator Signal Pattern**
Coordinator does NOT relay full conversation to target peer. Instead:
```
1. Coordinator writes shared state to IPC file (query file or handoff.md section)
2. Coordinator sends 1-line signal: hub.py ask --to <peer> --query "SEE: <file_path>"
3. Target peer reads file directly
4. Target peer echo-backs and proceeds
```
This eliminates middle-man token cost — coordinator's token budget is NOT consumed by relay.

**Query File Lifecycle**
```
Write → hub.py ask (file read + auto-deleted) → peer processes → response logged
```
IPC query files are consumed (deleted) on first read by hub.py. Never re-use the same file path.
Naming: `{peer_id}-{YYYYMMDDHHMMSS}-{RAND4}.txt`

---

## 6. State Stores & Data Handoff

### 6.1 Durable State Stores (MECE)
| Store | File | Content | TTL |
|-------|------|---------|-----|
| Session blackboard | `.ai/sessions/<room>/handoff.md` | Tasks, decisions, blockers | Until archived |
| Operational directives | `_sys/ai/runtime-directives.jsonl` | Behavioral corrections from failures | TTL-bound (default 6h) |

handoff.md = volatile state (WHAT we're doing).
runtime-directives.jsonl = durable corrections (HOW to behave differently).

### 6.2 Data Handoff Contract
**Markdown Handoff (`handoff.md`)**
- **Purpose:** Human-readable Single Source of Truth for the session state.
- **Sections:** GOAL, RECENT_COMPLETED, PENDING_ISSUES, KEY_DECISIONS, CONSENSUS_HISTORY, ACTIVE_THREADS.

**Structured Handoff (`handoff.json`)**
Implemented. `_write_handoff()` writes `handoff.md` and `handoff.json`; reads prefer the typed JSON sidecar and fall back to Markdown.

---

## 7. Terminal Command Contract (GAP-3)

To ensure terminal parity and proper read patterns, the terminal MUST interact with peer and system state through canonical commands rather than raw file access where commands exist.

**Terminal Command Mappings:**
- **peer status**: `hub.py peer-status`
- **room/session**: `status`
- **routability**: `health-precheck --peer <id>`
- **models**: `model-status`
- **parity**: `profile-validate`
- **leases/locks/tasks/roles**: `lease-status` / `lock-status` / `task-status` / `role-status`

**Terminal Guard Rule (PRO-19):** The terminal reads raw `_sys/` state ONLY for explicit audit or when the canonical command is missing/broken, and MUST explicitly state so when bypassing the command contract.
