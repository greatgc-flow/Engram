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
