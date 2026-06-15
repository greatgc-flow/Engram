# Protocol: Session Management (v4.1)
> Source: `_sys/ai/protocol.json["session"]` | Part of composable PROTOCOL.md

## 1. Session Decision Tree

At entry point startup, check `.ai/state.json`:

```
Check state.json
  ├─ room_id exists + this peer in members + updated_at < resume_window_hours (4h)?
  │     → RESUME: hub.py init-session (rejoin)
  │       Re-orientation: read full handoff.md
  │
  ├─ room_id exists + 4h <= updated_at < staleness_hours (24h)?
  │     → NEW + CONTEXT FILL:
  │       1. hub.py init-session (new join, same room_id)
  │       2. hub.py context-fill → inject into first prompt
  │
  ├─ room_id exists + updated_at >= staleness_hours (24h)?
  │     → STALE + FULL FILL:
  │       1. hub.py end-session for stale members
  │       2. hub.py init-session (new session)
  │       3. hub.py context-fill (all fill sections)
  │
  └─ no room_id
        → COLD START: hub.py init-session (empty handoff)
```

## 2. Context-Fill Command

```
hub.py context-fill [--sections GOAL,PENDING_ISSUES,KEY_DECISIONS,ACTIVE_THREADS]
```

- Zero-token: local handoff.md read only, no API calls
- Sections controlled by `protocol.json["session"]["context_fill_sections"]`
- `fill_depth_multiplier` per peer: gc=3 (reads more sections), others=1

## 3. Handoff Structure (`handoff.md`)

6 rolling sections (max 12KB, limits from `hub_config.json`):

| Section | Content | Max Items |
|---------|---------|-----------|
| `[GOAL]` | Current mission | 1 |
| `[RECENT_COMPLETED]` | Done tasks | 5 |
| `[PENDING_ISSUES]` | Blockers | 3 |
| `[KEY_DECISIONS]` | Architecture choices | 3 |
| `[CONSENSUS_HISTORY]` | Round outcomes | 10 |
| `[ACTIVE_THREADS]` | In-flight threads | 5 |

## 4. Startup Contract (all peers)

Every peer entry point MUST:
1. `hub.py init-session --agent {peer_id}`
2. `hub.py health-update --peer {peer_id} --status GREEN`
3. `hub.py context-fill` (inject output into first prompt)
4. `hub.py check --target {peer_id}` (read mailbox)

## 5. Session Expiry Rules

| Rule | Value | Config Key |
|------|-------|------------|
| Resume window | 4h | `session.resume_window_hours` |
| Staleness threshold | 24h | `session.handoff_staleness_hours` |
| Consensus round timeout | 30m | `consensus.timeout_minutes` |

## 6. Peer CLI Session Reuse (cx / gc)

`hub.py ask` reuses CLI process sessions across calls (scope_key = room_id by default).

| Peer | New session | Resume session |
|------|------------|---------------|
| cx | `codex exec - -s workspace-write --json --ignore-rules` | `codex exec resume <thread_id> - -s workspace-write --json --ignore-rules` |
| gc | `gemini --session-id <uuid> -p - -o text --approval-mode auto_edit --skip-trust` | `gemini --resume <uuid> -p - -o text --approval-mode auto_edit --skip-trust` |

State file: `_sys/{peer_subdir}/session_state.json` (gitignored)
- `active[scope_key]` → current session entry
- `history[]` → retired sessions (last 50)

On resume failure: retire old session → retry fresh once → store new session_id.
Topic boundary (`new-topic`, `clear-room`): all peer sessions retired.
Policy override: `hub.py ask --session-policy fresh` for independent cross-review calls.

## §HISTORY
- v4.2 (2026-06-13): Added §6 peer CLI session reuse (cx/gc) — session_state.json, scope_key, retry policy.
- v4.1 (2026-06-12): Verified session state and N-Way active room resolution.
- v4.0 (2026-06-11): Extracted from PROTOCOL.md §P-6,§P-11; added decision tree, startup contract, fill_depth_multiplier
