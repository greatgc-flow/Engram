# Antigravity Peer Configuration

> Protocol 4.2 | Node ID: `ag` | Updated: 2026-06-24

`ag` is the active Antigravity CLI peer. Runtime topology, lifecycle, profiles,
models, permissions, and roles are defined in `_sys/ai/orchestration.json`.

## Session Contract

- Shared rules: `_sys/docs-v2/general/protocol.md` and `_sys/docs-v2/general/lifecycle.md`
- Runtime policy: `_sys/ai/protocol.json`
- Health state: `_sys/antigravity/health.json`
- IPC entry point: `_sys/cli/msg.bat`

## Execution & Stateless IPC

- **Launch:** Hub `ask --to ag` invokes the native `_sys\tools\agy\agy.exe` DIRECTLY via `AgyAdapter`. This bypasses `agy.bat` to avoid context-fill contamination. (`agy_entry.py` / `agy.bat` are used for INTERACTIVE launch only).
- **Arguments:** `ag` is PTY-only, inline `-p {query}` (agy ignores stdin); `--print-timeout 60m`.
- **Session reuse WORKS (VERIFIED end-to-end 2026-07-02):** agy owns its conversation
  id (the `conversations/<id>.db` filename; not stdout). Hub CREATE omits
  `--conversation`; `extract_session_id` captures the newest `conversations/<id>.db`
  stem; RESUME injects `--conversation <that-id>`. A 2-ask probe recalled the codeword.
  (Requires a console — provided by the hub's winpty; only a headless no-console harness
  hangs. cc/cx also reuse.)
- **Durable home (verified 2026-07-01):** ag uses the durable `AGY_CONFIG_HOME=config` home. There is **no** clean/stateless `ipc-config` home — `ipc_stateless_home` is not configured (earlier design, inactive).

## Profile Defaults

| Profile | Runtime model | Effort |
|---------|---------------|--------|
| `standard` | `gemini-3.6-flash` | `low` |
| `effort` | `gemini-3.6-flash` | `high` |
| `deepthink` | `gemini-3.1-pro` | `high` |
| `opus` | `claude-opus-4-6-thinking` | embedded (no `--effort`) |
| `gptoss` | `gpt-oss-120b` | `medium` |

The standard profile is the terminal default. Hub requests may be promoted or
demoted automatically.

## IPC Rules

- Use asynchronous `send` and `check` for normal peer communication.
- Use synchronous `ask` only for self-contained requests requiring a response.
- Do not recursively invoke `ag` from an active `ag` PTY session.
- Use hub consensus actions rather than editing consensus state directly.

```bat
_sys\cli\msg.bat check --target ag
_sys\cli\msg.bat send --from ag --to cx --msg "Review requested"
_sys\cli\msg.bat health-update --peer ag --status GREEN
_sys\cli\msg.bat checkpoint --agent ag --msg "Checkpoint recorded"
```
