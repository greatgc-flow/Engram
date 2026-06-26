# System Trade-off Parameter Registry

This registry tracks all tunable system parameters, their config locations, and the operational trade-offs involved in their adjustment.

## Tunable Parameters

| Parameter | Description | Range | Trade-off | Config Location |
| :--- | :--- | :--- | :--- | :--- |
| **COLLAB_RATE** | Collaboration depth & consensus requirement | 0-10 | Token cost vs. Consensus quality | `protocol.json` -> `collab_rate.current` |
| **EFFORT** | Model effort level per peer | standard/effort/deepthink | Speed vs. analytical depth | `_sys/ai/orchestration.json` -> `hub_nodes[].profiles` |
| **SLIM** | Protocol message/handoff verbosity | true/false | Token savings vs. Comprehension quality | `orchestration.json` -> `session.slim_mode` |
| **SANDBOX** | Process/Tool isolation level | off/partial/full | Execution speed vs. System safety | `governance_params.json` -> `security.sandbox_level` |
| **LEADER_REELECT_PER_TASK** | Force re-election for every discrete task | bool (default: false) | Optimal routing vs. Transactional overhead | `protocol.json` -> `leader_election.reelect_per_task` |

## Runtime Adjustment
Parameters can be adjusted via the following methods:
- **CLI**: `python _sys/core/hub.py update-config --key {key} --value {value}`
- **Direct Edit**: Modifying the JSON config files (requires `COLLAB_RATE: 10` consensus for governed files).
- **Session Override**: Passing flags to `hub.py ask` (e.g., `--collab-rate 5`).

## Parameter Deep-Dive

### COLLAB_RATE Modes
Derived from `protocol.json` risk table and semantics.

| Rate | Mode | Risk Category | Peer Consensus Rule |
| :--- | :--- | :--- | :--- |
| **0** | **Observe** | Read-only / Explore | No consensus required (Exempt) |
| **3** | **Workspace** | `workspace/` changes | Informal notification or single peer review |
| **5** | **Sys-Single** | Single `_sys/` script edit | Majority ACK (2+ peers) |
| **8** | **Sys-Multi** | Cross-script `_sys/` changes | Supermajority ACK (All active peers) |
| **10** | **Constitutional** | Core protocol/config edits | Unanimous ACK + Final Call (FC) |

**Use Cases:**
- **Rate 0**: Initial research, bug hunting, reading logs.
- **Rate 5**: Routine maintenance of helper scripts.
- **Rate 10**: Changing `protocol.json`, `GEMINI.md`, or core `hub.py` logic.

### EFFORT (Model Intent)
- **Low**: Quick syntax fixes, single file reads, status checks.
- **Medium**: Default for most implementation tasks.
- **High**: Complex refactoring, architectural review, deep debugging.

### SLIM (Context Management)
- **True**: Used during stable phases to minimize token burn.
- **False**: Required during "Exhaustive Review" or "Re-orientation" phases where full context is critical.

### SANDBOX (Safety)
- **Full**: Recommended for untrusted third-party code or experimental scripts.
- **Partial**: Default for `workspace/` operations.
- **Off**: Only for trusted `_sys/` core migrations (requires human oversight).

## Cross-References
- `protocol.json`: Primary runtime SSOT for `COLLAB_RATE` and election logic.
- `governance_params.json`: Secondary budget and safety parameters.
