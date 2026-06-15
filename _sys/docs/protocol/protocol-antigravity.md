# Protocol: Antigravity (agy) Peer — ag (v4.1)
> Part of composable PROTOCOL.md | Peer-specific rules for ag node

## Node Identity

| Field | Value |
|-------|-------|
| Node ID | `ag` |
| Peer | antigravity |
| Binary | `agy.exe` (native, not npm) |
| Config | `_sys/antigravity/config/` |
| Health | `_sys/antigravity/health.json` |
| Glue File | `AGY.md` (in workspace) |
| Memory | session |
| Model | Gemini Flash (Low) |

## Invocation Modes

### Interactive console
```
_sys\cli\agy.bat
```
`agy_entry.py` appends `--allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits` by default unless the user supplies `--sandbox` or the permission flag explicitly.

### Async (default — use for messaging)
```
hub.py send --from ag --to cc --msg "..."
hub.py check --target ag
```

### Sync/PTY (hub.py ask — use only when synchronous response required)
```
hub.py ask --to ag --query "..."
```
PTY handled transparently via pywinpty. Use only for self-contained queries (no multi-turn).

## Consensus Voting Protocol

**NEVER use `hub.py ask` for consensus votes** — PTY + blocking = deadlock risk.

Preferred: Direct JSON write to `.ai/consensus/{round_id}.json`:
```json
{"voter": "ag", "vote": "agree", "reason": "...", "voted_at": "ISO8601"}
```

Fallback: `hub.py send --from ag --to cc --msg "vote:agree round:r-XXXX reason:..."`

## Environment

Env vars injected at invocation (from peers.json):
- `AGY_CONFIG_HOME` = `_sys/antigravity/config`
- `GEMINI_DIR` = `_sys/antigravity/config`

Host junction: `USERPROFILE\.gemini\antigravity-cli` → `_sys/antigravity/config`

## User Communication Scenarios

ag leads user communication when:
1. **Interactive command** needing real-time feedback (shell execution, port conflicts)
2. **Image generation / visual verification** (ag has `generate_image` capability)
3. **Timer / schedule notifications** (ag manages background tasks and timers)

## Health Metrics (ag-specific)

Written to `_sys/antigravity/health.json`:
```json
{
  "model_latency_ms": 850,
  "session_token_count": 12400,
  "quota_limit_remaining": 87,
  "active_background_tasks_count": 0
}
```

## §HISTORY
- v4.2 (2026-06-13): Direct console wrapper defaults to minimum non-interactive permissions, with explicit sandbox user override preserved.
- v4.1 (2026-06-12): Verified integration of native agy.exe with N-Way Rooms.
- v4.0 (2026-06-11): New file; PTY consensus policy, direct JSON vote, user comm scenarios
