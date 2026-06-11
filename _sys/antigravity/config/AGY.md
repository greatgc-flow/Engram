# AGY.md — Antigravity (ag) Session Glue File
> Protocol v4.0 | Node ID: `ag` | Updated: 2026-06-11

## Role
agy is the Antigravity CLI peer. Capabilities: shell-scripts, quick-cli, file-ops,
system-orchestration, real-time-feedback-loop, image-generation.

## Session Start Checklist
On every session start, agy_entry.py automatically:
1. `hub.py init-session --agent ag` — join P2P room
2. `hub.py health-update --peer ag --status GREEN` — report health
3. `hub.py context-fill` — read GOAL/PENDING_ISSUES/KEY_DECISIONS/ACTIVE_THREADS from handoff.md
4. Print context-fill output (session context injection)

## Shared IPC Paths (read/write)
| Path | Purpose |
|------|---------|
| `.ai/state.json` | Active room, session members |
| `.ai/handoff.md` | Shared session state (goal, decisions, threads) |
| `.ai/mailbox.json` | Async messages from/to other peers |
| `.ai/consensus/{round_id}.json` | Consensus votes — **direct JSON write only** |
| `.ai/out/ag.last.md` | ag output artifact for other peers |

## Consensus Vote Policy (CRITICAL)
**Never use `hub.py ask` for consensus votes** — PTY deadlock risk.
- Preferred: write vote directly to `.ai/consensus/{round_id}.json`
- Fallback: `hub.py send --to cc` relay

```json
// .ai/consensus/{round_id}.json vote entry
{ "voter": "ag", "vote": "AGREE", "reason": "...", "voted_at": "..." }
```

## PTY Mode Rules
| Mode | When to use |
|------|-------------|
| async (send/check) | Default — non-blocking message delivery |
| sync/PTY (ask) | Only for self-contained queries needing immediate response |
| consensus votes | **Direct JSON write only** — never ask |

## Hub Commands Available
```
hub.py send --to {peer} --msg "..."       # async message
hub.py check --target ag                  # read inbox
hub.py health-update --peer ag --status GREEN
hub.py checkpoint --agent ag --msg "..."  # mid-session handoff note
hub.py context-fill                       # reload session context
```

## Protocol Config
- Master config: `_sys/ai/protocol.json`
- Peer registry: `_sys/ai/peers.json`
- Health file: `_sys/antigravity/health.json`
- Docs: `_sys/docs/protocol-antigravity.md`
