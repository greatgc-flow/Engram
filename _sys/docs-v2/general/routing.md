# General — Leader Election & Role Assignment
> Source: protocol-routing.md v4.1

---

## 1. Leader (Active Coordinator)

Leader coordinates task framing, role assignment, and synthesis.
Leader is NOT a superior authority — all peers remain equal for consensus.

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

---

## 2. Peer Roles (session-scoped)

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

---

## 3. Failover Rules

- RED peer: stop routing immediately
- STALE peer: avoid new assignments/leadership; run precheck if needed
- If all suitable peers are RED/gate-closed/STALE: escalate to human interface peer
- Task failover: `hub.py task-failover --task-id <id> --peer <new_peer> --reason <reason>`

---

## 4. Forwarding Contract

- Single-hop forwarding only (`single_hop_forwarding_only: true`)
- Human interface peer stays fixed — not re-routed mid-session
- `hub.py ask-coordinator --from <peer> --query <query>`

---

## 5. Challenge Window

**Source:** `hub.py:action_leader_claim` — `protocol.json["leader_election"]["challenge_window_minutes"]` (default: `1`)

When a peer calls `hub.py leader-claim`, it does **not** become coordinator instantly.
Instead it enters a `PENDING` state with a **challenge window** that allows other peers to contest the claim.

### State Written on Claim

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

### Challenge Rules

| Condition | Action |
|-----------|--------|
| Current time < `challenge_until` | Another peer may challenge; claim is overwritten (logged) |
| Current time ≥ `challenge_until` AND current leader is GREEN/YELLOW | `[HUB:ERR]` — claim rejected, `sys.exit(1)` |
| Current time ≥ `challenge_until` AND current leader is RED/STALE | Claim succeeds unconditionally |
| No current leader | Claim succeeds immediately |

> Window duration is defined by `protocol.json["leader_election"]["challenge_window_minutes"]`.

### Handoff Entry

Each successful claim appends to `handoff.md[ACTIVE_THREADS]`:
```
[<ts>] (<agent>) [CLAIM-PENDING] claiming leadership. Challenge until: <ts> Reason: <reason>
```

---

## 6. Model-Level Routing (Within Peer)

> Requirement: B6 from docs-v2/user/requirements.md

Each peer may use multiple underlying models based on task characteristics.
Model definitions live under the root peer's nested `profiles` map in
`_sys/ai/orchestration.json`. Deterministic selection policy lives in
`routing-config.json["auto_profile_routing"]`; hub.py applies the decision before
invoking an adapter.

### Selection Matrix

| Mode | When to use | Examples |
|------|------------|---------|
| **Standard** | Routine tasks, low complexity | Health checks, file reads, summaries |
| **Effort** | Medium complexity or ambiguity | Implementation, refactor, tests, debugging |
| **DeepThink** | High complexity or risk | Protocol redesign, security review, exhaustive consensus |

### Decision Contract

```text
explicit peer.profile -> preserve
simple evidence       -> standard
implementation        -> effort
high risk              -> deepthink
ambiguous              -> effort
repeated failure       -> promote one tier
blocked selection      -> same-peer downward fallback
```

Root peer terminals start at `standard`. Root peer asks through hub.py are
classified automatically. Explicit profile nodes are immutable.

See `ops/automatic-profile-routing-2026-06-20.md` for the decision record,
signals, fallback rules, tests, and benchmark.

---

## 7. Coordinator Graceful Handoff

> Requirement: B1 from docs-v2/user/requirements.md (coordinator switch, not just failover)

**Graceful handoff** (voluntary) differs from **failover** (RED peer recovery).

### Handoff Trigger Conditions

| Condition | Action |
|-----------|--------|
| Context saturation (> 85%) | Current coordinator initiates voluntary yield |
| Task domain shift | Coordinator yields to peer with better capability match |
| End of session | Coordinator passes state to next session coordinator |
| User request | Explicit handoff on user instruction |

### Handoff Procedure

```
1. Coordinator writes final handoff.md state
2. hub.py leader-yield --agent <current> --reason <reason>
3. hub.py elect-leader --needs <new_domain> --effort <level>
4. New coordinator reads handoff.md → announces to room
5. User notification: "[<old>→<new>] Coordinator handed off: <reason>"
```

### Invariants

- Human-interface peer stays FIXED during handoff (user sees same peer)
- If new coordinator = different peer from human-interface peer: auto-forwarding enabled
- Handoff is logged in coordinator_history (AP-20 tracking)

---

## 6. AP-20: Coordinator Monopoly Guard

**Source:** `hub.py:action_leader_claim` — checked on every `leader-claim` call.

### Rule

If a peer has been coordinator for a consecutive number of terms exceeding `protocol.json["leader_election"]["yield_failure_threshold"]`, it is blocked from claiming leadership again until another peer leads at least once.

### Implementation

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

### Error

```
[HUB:ERR] AP-20 Violation: {agent} has been coordinator for 3 consecutive terms. Yield to others.
```
Exit code: `1`. No state mutation occurs when the violation fires.
