# Protocol: Codex Peer — cx (v4.1)
> Part of composable PROTOCOL.md | Peer-specific rules for cx node

## Node Identity

| Field | Value |
|-------|-------|
| Node ID | `cx` |
| Peer | codex |
| CLI | `codex` (npm, @openai/codex) |
| Version | codex-cli 0.139.0 |
| Config | `_sys/codex/config/` |
| Health | `_sys/codex/health.json` |
| Glue File | `CODEX.md` (in workspace) |
| Memory | session |

## Invocation Pattern

Interactive console entry:

```bat
_sys\cli\codex.bat
```

`codex_entry.py` appends `-s workspace-write` by default for console sessions, unless the user supplies an explicit sandbox or approval policy.

**Always use stdin, never shell-quoted args** (avoids Windows escaping bugs):

```python
# In hub.py _build_session_cmd / action_ask
subprocess.Popen(
    ["codex", "exec", "-", "--json", "--ignore-rules",
     "-s", "workspace-write"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
# Session resume: ["codex", "exec", "resume", <thread_id>, "-", ...]
# Ephemeral (no session): add "--ephemeral" — only used for fresh/none policy
```

Key flags:
- `codex exec -` reads from stdin (session-aware path)
- `--json` for JSONL output (thread.started event → thread_id extraction)
- `--ignore-rules` skips project-level execpolicy rules
- `-s workspace-write` minimum non-interactive permissions — workspace-write sandbox for repo-scoped edits
- `--ephemeral` prevents session persistence (used only when session_policy=fresh/none)
- Session reuse via `hub.py --session-policy reuse` (default); scope_key = room_id

## Health Metrics (cx-specific)

Written to `_sys/codex/health.json`:
```json
{
  "cli_version": "codex-cli 0.139.0",
  "entrypoint_ok": true,
  "last_invocation_exit_code": 0,
  "last_invocation_duration_ms": 12345,
  "rate_limit_state": "ok",
  "workspace_access": "workspace-write"
}
```

## User Communication Scenarios

cx leads user communication when:
1. **Code review findings** — concrete bugs, regressions, risky assumptions
2. **Implementation plan** tied to specific repo files
3. **Refactoring strategy** — scope, approach, verification steps
4. **Test strategy** for a changed area
5. **"What changed and why"** summaries for completed patches

## Smoke Test (run after entry point setup)

```
hub.py ask --to cx --query "Echo: system ready. Reply with your node ID and version."
```
Verify: response received + `health.json entrypoint_ok = true`

## §HISTORY
- v4.4 (2026-06-14): Corrected cx flag throughout — `--ask-for-approval` is console-only; `-s workspace-write` is the correct `codex exec` flag.
- v4.3 (2026-06-13): Direct console wrapper defaults to minimum non-interactive permissions, with explicit sandbox/approval user overrides preserved.
- v4.2 (2026-06-13): Added minimum non-interactive permissions flag for cx; session reuse via hub.py session_state.json; updated invocation pattern.
- v4.1 (2026-06-12): Verified stdin interface with 5-node consensus protocol.
- v4.0 (2026-06-11): New file; stdin invocation pattern, sandbox flags, health metrics, user comm scenarios
