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

**Always use stdin, never shell-quoted args** (avoids Windows escaping bugs):

```python
# In codex_entry.py / hub.py ask
subprocess.run(
    ["codex", "exec", "-", "--cd", str(workspace), 
     "--sandbox", "workspace-write",
     "--ask-for-approval", "never",
     "--json"],
    input=query_text,
    text=True
)
```

Key flags:
- `codex exec -` reads from stdin
- `--cd P:\` sets workspace root
- `--sandbox workspace-write` limits filesystem access
- `--ask-for-approval never` for non-interactive batch use
- `--json` for machine-parseable output
- `-o .ai/out/cx.last.md` for output file

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
- v4.1 (2026-06-12): Verified stdin interface with 5-node consensus protocol.
- v4.0 (2026-06-11): New file; stdin invocation pattern, sandbox flags, health metrics, user comm scenarios
