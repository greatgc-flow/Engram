# Leader, Role, Health, and Continuity Design

## Purpose

This design separates the console-facing peer from the active coordinator. The user can keep typing in the same console while the room elects a better coordinator for the current task.

## MECE Control Areas

### 1. Leader Selection

The leader is the active coordinator, not a superior authority. It coordinates task framing, role assignment, and final synthesis while all peers remain equal for consensus.

Selection inputs:
- Task need: architecture, coding, review, research, shell, documentation.
- Health: GREEN preferred, RED blocked, STALE avoided.
- Model profile: context window, cost tier, capabilities, tool access.
- Continuity: current task owner is preferred if healthy and already has context.
- Console fit: if the human interface peer already matches the task and is healthy, avoid forwarding.

Election score:

```text
score =
  capability_match          0..10
+ health_score              GREEN=3, YELLOW=1, STALE=-5, RED=blocked
+ continuity_bonus          0..2
+ console_fit_bonus         0..1
- cost_penalty              low=0, mid=1, high=2
- cold_start_penalty        0..1
```

Tie break order:
1. Peer already owning the task checkpoint.
2. Healthier peer.
3. Lower cost peer if task risk is low.
4. Higher capability peer if task risk is high.
5. Ask the human interface peer to confirm.

Runtime state:
- `.ai/state.json.active_coordinator`
- `.ai/state.json.leadership`

Commands:
- `hub.py elect-leader --needs <capability> --effort <low|mid|high>`
- `hub.py leader-claim --agent <peer> --needs <domain> --reason <reason>`
- `hub.py leader-yield --agent <peer> --reason <reason>`
- `hub.py ask-coordinator --from <peer> --query <query>`

Consensus rule:
- Leader election is a coordination decision, not a grant of extra authority.
- For low-risk routing, optimistic claim is allowed and logged.
- For governed work on `_sys/`, protocol files, or destructive operations, election and role assignment must be visible before execution and remain subject to the existing R:10 consensus rules.

### 2. Peer Role Assignment

Roles are session-scoped and separate from peer identity.

Core roles:
- coordinator: frames the task and delegates.
- implementer: edits files and runs focused checks.
- verifier: reviews output and validates risk.
- researcher: handles broad context and web/large-corpus work.
- documenter: writes durable handoff and design artifacts.
- observer: receives context but does not mutate.

Runtime state:
- `.ai/state.json.role_assignments`

Commands:
- `hub.py assign-role --role <role> --peer <peer>`
- `hub.py release-role --role <role> [--peer <peer>]`
- `hub.py role-status`

### 3. Model Health Management

Health gates must affect routing, not only reporting.

Effective health:
- RED: do not route work.
- STALE: avoid for leadership and new assignments.
- GREEN/YELLOW: eligible, with YELLOW lower priority.

Profile fields live in each peer health manifest:
- tier
- context_window
- cost_tier
- supported_tools
- capabilities

Command:
- `hub.py health-precheck`
- `hub.py health-precheck --needs <capability>`
- `hub.py health-precheck --peer <peer-or-comma-list>`
- `hub.py health-sweep`
- `hub.py profile-validate`
- `hub.py model-status`

### 4. Work Continuity

Continuity requires checkpoints independent of any one model's chat context.

Runtime state:
- `.ai/task_registry.json`
- `.ai/sessions/{room_id}/handoff.md`

Commands:
- `hub.py task-checkpoint --id <task_id> --peer <peer> --msg <summary>`
- `hub.py task-status [--id <task_id>]`
- `hub.py task-failover --task-id <task_id> --peer <new_owner> --reason <reason>`

Checkpoint rules:
- Record file paths, decisions, pending risks, and next action.
- Do not store full transcripts unless needed.
- Prefer durable file references over pasted context.
- When yielding because of context, health, rate-limit, or failure pressure, the current coordinator must record a checkpoint before leadership becomes vacant.

Task registry schema:

```json
{
  "task-id": {
    "task_id": "task-id",
    "owner": "cx",
    "status": "ACTIVE",
    "created_at": "2026-06-12T00:00:00",
    "updated_at": "2026-06-12T00:00:00",
    "checkpoints": [
      {"peer": "cx", "note": "summary", "at": "2026-06-12T00:00:00"}
    ]
  }
}
```

## Console Forwarding Token Cost

Coordinator switching should not require changing the user's console. The console peer stays as the human interface and forwards to `active_coordinator`.

To keep token use low, forwarding must use a thin envelope:

```text
ROOM: room-id
TASK_ID: optional-id
USER_QUERY: current user request
STATE_REFS:
- .ai/state.json
- .ai/sessions/{room_id}/handoff.md
- .ai/task_registry.json
REQUEST: coordinate / assign / answer
```

The console peer must not paste the full conversation history into every forwarded ask. The coordinator should read local state and referenced files directly. This keeps console-peer token usage close to a short routing message plus the user's latest query.

Forwarding policy:
- Single hop only: `human_interface_peer -> active_coordinator`.
- No relay chains such as `cx -> cc -> gc`.
- Target envelope should normally stay under 800 characters plus the current user query.
- The coordinator performs its own peer asks; sub-queries do not route back through the user console.

Cost expectation:
- Good path: one thin envelope plus current user message.
- Bad path: full chat transcript copied into every ask. This is forbidden.

## Human Interface Peer Health

The human interface peer is the console where the user is currently typing. It is separate from the active coordinator and can degrade independently.

States:
- HEALTHY: normal interaction.
- DEGRADED: context high, latency high, quota warning, or YELLOW health.
- RATE_LIMITED: model refuses or delays due to quota/session limits.
- AUTH_BLOCKED: login, connector, browser, API key, or local permission is missing.
- HARD_FAIL: process unavailable or cannot respond.

Response policy:
- DEGRADED: keep the same console, but force thin forwarding and concise local summaries.
- RATE_LIMITED: ask the user to switch console, or queue the request in `.ai` for another interface peer to pick up.
- AUTH_BLOCKED: do not forward credentials. Ask through the current console for explicit setup or reroute to an already authenticated peer.
- HARD_FAIL: manual console migration is required; another peer may write a visible handoff note, but cannot magically move the user's terminal session.

Console migration rule:
- `human_interface_peer_stays_fixed=true` means "do not switch unnecessarily", not "never switch".
- If the console peer cannot talk to the user, the system must recommend a new console peer and record `human_interface_peer` migration in state once the user resumes there.

## User Console Selection

The user can use any peer console because routing should compensate. Efficiency improves when the console peer matches the likely task.

Recommended defaults:

| User task | Best console | Reason |
|---|---|---|
| General coordination and implementation in this repo | `cx` | Good user interface plus repo-local coding workflow |
| Architecture, policy, and careful review | `cc` | Strong long-form reasoning and persistent project memory |
| Large corpus, long documents, broad research | `gc` | Long context and research-oriented profile |
| Shell workflow and fast operational checks | `ag` | CLI-oriented execution flow |
| Independent verification | `ca` | Keep as verifier/second opinion when available |

Rule of thumb:
- If unsure, use `cx` or the most stable available console.
- If the task obviously belongs to a model family, start there to avoid one forwarding hop.
- Do not choose a console just for credentials; credentials stay local to each peer and must be requested explicitly when needed.

## Auth And Approval Handling

Coordinator changes must not move credential custody.

Rules:
- The human interface peer owns user-facing approval and authentication prompts.
- Credentials, tokens, browser sessions, connector grants, and local account state are never forwarded between peers.
- The peer that executes an action must use its own available auth surface.
- If the active coordinator needs an action that requires user approval, it sends a structured approval request back to the human interface peer.
- The human interface peer asks the user, records the decision, and then tells the executing peer what was approved.
- If a peer lacks required auth, the coordinator can reassign the task to an authenticated peer or ask the human interface peer to request setup from the user.

Approval request shape:

```text
APPROVAL_REQUEST:
REQUESTING_PEER: gc
EXECUTING_PEER: cx
ACTION: run tests / access connector / install dependency
AUTH_NEEDED: local CLI login / API key / browser connector / filesystem write
SCOPE: exact command, file path, or connector operation
RISK: read-only | workspace-write | external-io | credential
FALLBACK: alternative peer or degraded read-only path
```

This keeps the console peer as the user trust boundary while allowing another peer to coordinate the work.

Runtime command:

```text
hub.py approval-request --from <peer> --subject <action> --auth-needed <kind> --scope <scope> --severity <risk>
```

## Locks And Visibility

Governed file ownership and section locks are tracked through the hub. This is an MVI runtime contract: peers must check and claim before editing governed files.

Commands:

```text
hub.py file-lock --name <path-or-section> --peer <owner> --scope <file|section|governed-file>
hub.py file-unlock --name <path-or-section> --peer <owner>
hub.py lock-status
hub.py transient-scan
```

`hub.py status` includes active task and lock counts.

Failover auth rule:
- A new coordinator does not inherit approvals or credentials from the previous coordinator.
- File-write approval, connector grants, and external I/O approval must be revalidated for the executing peer.

## Volatile Tool Artifacts

`_sys/antigravity/config/bin/agentapi.bat` is treated as a volatile artifact generated by `agy.exe`. It may contain the current mounted drive path and may be rewritten during `ag` calls.

This file is not part of the active coordinator MVI trust boundary. Peer-to-peer communication with `ag` must use the stable wrapper path:

```text
_sys/cli/agy.bat
hub.py ask --to ag
```

Do not use `agentapi.bat` as a blocker for active coordinator consensus as long as the stable wrapper path remains portable and operational.
