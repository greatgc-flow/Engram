# General — Routing

> Pillar consolidates {routing, resource-governance}.
> English is the mandatory language for all internal reasoning, handoffs, and system logs (INV-19).
> Status: ACTIVE v4 | Updated: 2026-06-26
> Sources: `orchestration.json`, `model-registry.json`, `routing-config.json`, `peers.json`

## 1. Separation of Concerns & Node Architecture

### 1.1 Separation of Concerns

| Concern | Canonical source |
|---|---|
| CLI installation, relocation, workspace glue | `peers.json` (peer→sys_subdir resolution via `resolve_peer_sys_dir`) |
| Logical peer lifecycle, profiles, invocation, permission class | `orchestration.json` |
| Vendor model facts | `model-registry.json` |
| Global collaboration and governance policy | `protocol.json` |
| Runtime health and failures | ignored `health.json` plus `.ai/` provenance |

No generated node list is tracked.

### 1.2 Node Architecture

Each tracked root peer owns exactly three MECE profiles:

- `standard`: lowest sufficient cost/latency;
- `effort`: default balanced profile;
- `deepthink`: highest verified reasoning setting.

Runtime normalization generates `{peer}.{profile}` children. Root IDs stay stable and use the low-cost `standard` profile in direct terminals. Root asks through the hub are classified automatically. Effective enablement is recursive and fail-closed.

## 2. Peer-Level & Model-Level Routing

### 2.1 Routing Order & Fallback

Routing order:

1. reject unknown, disabled, blocked, cyclic, or orphaned nodes;
2. preserve an explicitly selected profile;
3. classify root asks using deterministic zero-token signals;
4. select the lowest sufficient eligible profile;
5. prefer continuity when quality is equal;
6. use SAME-PEER DOWNWARD fallback for blocked profiles (cross-peer fallback is coordinator policy, not router);
7. default ambiguous requests to `effort`.

The hub owns transport and policy. A peer adapter owns CLI syntax and session behavior.

### 2.2 Model-Level Routing (Within Peer)

> Requirement: B6 from docs-v2/user/requirements.md

Each peer may use multiple underlying models based on task characteristics. Model definitions live under the root peer's nested `profiles` map in `_sys/ai/orchestration.json`. Deterministic selection policy lives in `routing-config.json["auto_profile_routing"]`; hub.py applies the decision before invoking an adapter.

#### Selection Matrix

| Mode | When to use | Examples |
|------|------------|---------|
| **Standard** | Routine tasks, low complexity | Health checks, file reads, summaries |
| **Effort** | Medium complexity or ambiguity | Implementation, refactor, tests, debugging |
| **DeepThink** | High complexity or risk | Protocol redesign, security review, exhaustive consensus |

#### Decision Contract

```text
explicit peer.profile -> preserve
simple evidence       -> standard
implementation        -> effort
high risk             -> deepthink
ambiguous             -> effort
repeated failure      -> promote one tier
blocked selection     -> same-peer downward fallback
```

Root peer terminals start at `standard`. Root peer asks through hub.py are classified automatically. Explicit profile nodes are immutable.

See `_sys/docs/history/ops/automatic-profile-routing-2026-06-20.md` (archived decision record) for signals, fallback rules, tests, and benchmark.

## 3. Leader Election & Role Assignment

### 3.1 Leader (Active Coordinator)

Leader coordinates task framing, role assignment, and synthesis.
Leader is NOT a superior authority — all peers remain equal for consensus.

**Terminal-Transport Invariant (GAP-1):** The human-interface terminal may frame, route, relay, and summarize worker outputs, but MUST NOT perform substantive task analysis once a worker is selected. "Coordinator"/"leader" is a task role assigned by protocol, not terminal authority (Cross-reference: `protocol.md §1.2`).

**Election Score:**
```
score =
  capability_match    0..10
+ health_score        GREEN=3, YELLOW=1, STALE=-5, RED=blocked
+ continuity_bonus    0..2  (current task owner preferred if healthy)
+ console_fit_bonus   0..1  (avoid forwarding if human-interface peer fits)
- cost_penalty        low=0, mid=1, high=2
- cold_start_penalty  0..1
```

**Tiebreak order:** task checkpoint owner → healthier → lower cost (low risk) → higher capability (high risk) → ask human interface peer.

**Commands:**
```
hub.py elect-leader --needs <capability> --effort <low|mid|high>
hub.py leader-claim --agent <peer> --needs <domain> --reason <reason>
hub.py leader-yield --agent <peer> --reason <reason>
```

**Runtime state:** `.ai/state.json.active_coordinator` / `.ai/state.json.leadership`

**Governance:** Low-risk routing = optimistic claim (logged). `_sys/` / protocol / destructive ops = election visible before execution + R:10 rules apply.

### 3.2 Peer Roles (session-scoped)

| Role | Responsibility |
|------|---------------|
| coordinator | Frames task, delegates |
| implementer | Edits files, focused checks |
| verifier | Reviews output, validates risk |
| researcher | Broad context, web/large-corpus |
| documenter | Durable handoff + design artifacts |
| observer | Receives context, does not mutate |

**Commands:**
```
hub.py assign-role --role <role> --peer <peer>
hub.py release-role --role <role> [--peer <peer>]
hub.py role-status
```

**Runtime state:** `.ai/state.json.role_assignments`

## 4. Leader Claim & Coordinator Graceful Handoff

### 4.1 Challenge Window

**Source:** `hub.py:action_leader_claim` — Window duration defined by `protocol.json["leader_election"]["challenge_window_minutes"]`.

When a peer calls `hub.py leader-claim`, it does **not** become coordinator instantly.
Instead it enters a `PENDING` state with a **challenge window** that allows other peers to contest the claim.

#### State Written on Claim

```json
"leadership": {
  "peer":            "<agent>",
  "status":          "PENDING",
  "domain":          "<domain>",
  "reason":          "<reason>",
  "claimed_at":      "<ISO8601>",
  "challenge_until": "<ISO8601 = claimed_at + challenge_window_minutes>"
}
```

Fields set in `state.json`: `leader`, `active_coordinator`, `leadership`.

#### Challenge Rules

| Condition | Action |
|-----------|--------|
| Current time < `challenge_until` | Another peer may challenge; claim is overwritten (logged) |
| Current time ≥ `challenge_until` AND current leader is GREEN/YELLOW | `[HUB:ERR]` — claim rejected, `sys.exit(1)` |
| Current time ≥ `challenge_until` AND current leader is RED/STALE | Claim succeeds unconditionally |
| No current leader | Claim succeeds immediately |

#### Handoff Entry

Each successful claim appends to `handoff.md[ACTIVE_THREADS]`:
```
[<ts>] (<agent>) [CLAIM-PENDING] claiming leadership. Challenge until: <ts> Reason: <reason>
```

### 4.2 Coordinator Graceful Handoff

> Requirement: B1 from docs-v2/user/requirements.md (coordinator switch, not just failover)

**Graceful handoff** (voluntary) differs from **failover** (RED peer recovery).

#### Handoff Trigger Conditions

| Condition | Action |
|-----------|--------|
| Context saturation (> 85%) | Current coordinator initiates voluntary yield |
| Task domain shift | Coordinator yields to peer with better capability match |
| End of session | Coordinator passes state to next session coordinator |
| User request | Explicit handoff on user instruction |

#### Handoff Procedure

```
1. Coordinator writes final handoff.md state
2. hub.py leader-yield --agent <current> --reason <reason>
3. hub.py elect-leader --needs <new_domain> --effort <level>
4. New coordinator reads handoff.md → announces to room
5. User notification: "[<old>→<new>] Coordinator handed off: <reason>"
```

#### Invariants

- Human-interface peer stays FIXED during handoff (user sees same peer)
- If new coordinator = different peer from human-interface peer: auto-forwarding enabled
- Handoff is logged in coordinator_history (AP-20 tracking)

### 4.3 AP-20: Coordinator Monopoly Guard

**Source:** `hub.py:action_leader_claim` — checked on every `leader-claim` call.

#### Rule

If a peer has been coordinator for a consecutive number of terms exceeding `protocol.json["leader_election"]["yield_failure_threshold"]`, it is blocked from claiming leadership again until another peer leads at least once.

#### Implementation

```python
# Threshold configured via protocol.json["leader_election"]["yield_failure_threshold"]
history = state.get("coordinator_history", [])   # history kept for recent terms
threshold = get_config("leader_election.yield_failure_threshold")
recent = [h.get("peer") for h in history[-threshold:]]
if len(recent) == threshold and all(p == agent for p in recent):
    print(f"[HUB:ERR] AP-20 Violation: {agent} has been coordinator for {threshold} consecutive terms.")
    sys.exit(1)
```

- `coordinator_history` stores recent entries: `{"peer": str, "at": ISO8601, "room": str}`.
- History is appended on every successful claim (after AP-20 passes).
- The check is **pre-claim** — it runs before the challenge window is opened.

#### Error

```text
[HUB:ERR] AP-20 Violation: {agent} has been coordinator for {threshold} consecutive terms. Yield to others.
```
Exit code: `1`. No state mutation occurs when the violation fires.

## 5. Forwarding & Failover Rules

### 5.1 Forwarding Contract

- Single-hop forwarding only (`single_hop_forwarding_only: true`)
- Human interface peer stays fixed — not re-routed mid-session
- `hub.py ask-coordinator --from <peer> --query <query>`

### 5.2 Failover Rules

- RED peer: stop routing immediately
- STALE peer: avoid new assignments/leadership; run precheck if needed
- If all suitable peers are RED/gate-closed/STALE: escalate to human interface peer
- Task failover: `hub.py task-failover --task-id <id> --peer <new_peer> --reason <reason>`

## 6. Cost, Quality & Context

### 6.1 Cost and Quality

Cost tiers are routing hints, not vendor facts. Exact prices and capacities come from `model-registry.json`. Runtime measurements are appended to routing/cost logs. Unknown price or model identity must be recorded as `unknown`, never inferred.

Quality acceptance requires:

- task-specific tests pass;
- independent review for governed changes;
- no unresolved HIGH finding;
- provenance includes selected peer/profile and failure class.

### 6.2 Context

Peers share explicit state references, not hidden model memory. Compact forwarding contains the task, constraints, and references. Full history is not relayed through the human-interface model. Durable shared context requires promotion or ACK.

## 7. Governance, Permissions & Continuous Update

### 7.1 Governance and Permissions

Active peers have equal vote weight, leadership eligibility, role eligibility, and human communication rights. Execution permission mappings are adapter-specific and must declare a capability class. Governance equality does not require identical dangerous flags.

### 7.2 Continuous Update

1. Verify vendor facts from official documentation.
2. Verify local CLI model/option support without a paid model call where possible.
3. Update the registry and affected nested profile once.
4. Run strict config validation, profile validation, tests, and benchmarks.
5. Record source, as-of date, confidence, and any unavailable runtime variant.

For logical peers that reuse an existing installation provider:

```text
peer_mgr.py add <peer> --invoke <cli> [--provider <provider>] --model <model>
peer_mgr.py suspend <peer>
peer_mgr.py resume <peer>
peer_mgr.py remove <peer>
peer_mgr.py validate --strict
```

The lifecycle command synchronizes topology, installation `node_ids`, status probe inheritance, active/inactive voters, role registries, and the Specific document. A brand-new CLI/provider installation must first be registered in `peers.json`.

### 7.3 Acceptance Metrics

| Metric | Target Policy |
|---|---|
| Normalization median | Value defined in `routing-config.json` |
| Full-tree routability median | Value defined in `routing-config.json` |
| Generated files tracked | 0 |
| Routine status model calls | 0 |
| Active voter/role parity | exact set equality |
| Disabled descendant routing | 0 |

See `_sys/docs/history/ops/peer-debate-2026-06-19.md` (archived) for the full decision record.


