# common-peer-rules.md — Shared Peer Invariants (v1.0)
> **Date**: 2026-06-14 | **Scope**: All AI peers (cc, gc, cx, ag)
> These rules apply to every peer equally. Peer-specific files reference this document
> and override only where their technical constraints differ.

---

## 1. Peer Equality

All AI peers have **absolutely equal** authority, proposal rights, and voting rights.
Human is Tier 0 (veto authority). No peer may claim superior standing over another.

Any peer may communicate directly with the Human. Lead user communication for tasks
that fall within your stated capability strengths.

---

## 2. Shared IPC Paths

All peers read and write shared governance state through these paths:

| Path | Purpose |
|------|---------|
| `.ai/state.json` | Active room ID, current session members |
| `.ai/sessions/{room_id}/handoff.md` | Shared session context (goal, decisions, threads) |
| `.ai/mailbox.json` | Async peer-to-peer messages |
| `.ai/consensus/{round_id}.json` | Consensus round votes |
| `_sys/ai/protocol.json` | Master config — collab_rate, routing, health thresholds |
| `_sys/ai/peers.json` | Peer capability registry |
| `_sys/ai/user-directives.md` | Human-authored standing rules |
| `_sys/ai/runtime-directives.jsonl` | Auto-promoted operational corrections (TTL-bound) |

**Never write shared IPC files directly** — use `hub.py` commands to ensure FileLock concurrency.

---

## 3. Common Hub Commands

```bash
# Session
hub.py init-session --agent <peer_id>          # join P2P room
hub.py context-fill                             # load GOAL/PENDING/DECISIONS from handoff.md

# Health
hub.py health-update --peer <id> --status GREEN  # self-report health at session start/end
hub.py health-check                              # view all peer health

# Messaging
hub.py send --from <id> --to <id> --msg "..."   # async message delivery
hub.py check --target <id>                       # read inbox

# Consensus
hub.py consensus-vote --round-id r-XXXX --voter <id> --vote agree|disagree|abstain

# Coordination
hub.py checkpoint --agent <id> --msg "..."      # mid-session handoff note
hub.py task-checkpoint --id <task_id> --peer <id> --msg "..."
```

---

## 4. Session Start Invariants (INV-05, INV-06)

Every peer entry point MUST execute this sequence:
1. `hub.py init-session --agent <peer_id>` — register in active room
2. `hub.py health-update --peer <peer_id> --status GREEN` — report health
3. `hub.py context-fill` — read session context from handoff.md
4. Check inbox — `hub.py check --target <peer_id>`

Re-orientation (reading handoff.md before any work) is mandatory. If no prior session
is found, state explicitly: `[SKIPPED: no prior session found]`.

---

## 5. Collaboration Safety Rules

- Do not overwrite unrelated peer changes
- Prefer existing project conventions over new abstractions
- Report blockers clearly via `hub.py send --from <id> --to cc --msg "blocked: ..."`
- Respect `COLLAB_RATE` threshold — see `protocol.json["collab_rate"]["current"]`
- Do not run destructive git commands unless explicitly instructed by Human

---

## 6. Health Self-Reporting

Run at **session start** and **session end**:
```bash
hub.py health-update --peer <peer_id> --status GREEN --failures 0
```

The health gate (GREEN/YELLOW/RED) governs whether this peer receives routed asks.
A RED peer will not receive work until `peer-recover` is run. See `protocol-health.md §6`.

---

> *Authority: `_sys/docs-v2/10-invariants.md` (INV-01~18, PRO-01~15)*
> *Protocol docs: `_sys/docs-v2/` (SSOT — see 00-MANIFEST.md for load order)*
> *Legal Code archive: `_sys/docs/history/` (read-only reference)*
