# Peer Console Defaults

This note records the local CLI option audit for launching peer consoles from both Claude and a terminal.

## Default Policy

Peer console wrappers default to minimum non-interactive execution:

| Peer | Wrapper | Default args appended by `_sys/cli/peer_console.py` |
|------|---------|------------------------------------------------------|
| cc | `_sys/cli/claude.bat` | `--allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits` |
| gc | `_sys/cli/gemini.bat` | `--approval-mode auto_edit --skip-trust` |
| cx | `_sys/cli/codex.bat` | `-s workspace-write` |
| ag | `_sys/cli/agy.bat` | `--allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits` |

User-supplied safety flags win. The wrapper does not override explicit permission, approval, or sandbox settings.

## Override Rules

| Peer | Override flags that suppress the minimum-permission default |
|------|--------------------------------------------------------|
| cc | `--permission-mode`, `--allowedTools`, `--safe-mode` |
| gc | `--approval-mode`, `-y`, `--yolo`, `--sandbox`, `-s` |
| cx | `--sandbox`, `-s`, `--ask-for-approval`, `-a` |
| ag | `--sandbox`, `--allowedTools` |

For Gemini, `--skip-trust` is still appended when the user chooses an explicit approval mode because workspace trust is a separate prompt class.

## P2P Invocation Defaults

`hub.py ask` uses `_sys/ai/orchestration.json` and session-aware command construction:

| Peer | P2P default |
|------|-------------|
| cc/ca | `--allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits` |
| gc | `--approval-mode auto_edit --skip-trust` |
| cx | `-s workspace-write` |
| ag | `--allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits` |

`gc-plan` intentionally keeps `--approval-mode plan --skip-trust` because it is a read-only planning virtual node.

## Convenience Options Audited

### Claude Code

Useful but not default:
- `--ide`: auto-connect to a detected IDE.
- `--continue` / `--resume`: continue prior conversations; not default because fresh peer entry should not silently attach to unrelated work.
- `--effort <level>` and `--model <model>`: task-specific.
- `--worktree`: useful for isolated branches, but mutates git state.
- `--remote-control`: useful for remote orchestration, but changes console control semantics.
- `--no-session-persistence`: useful for throwaway print mode, but conflicts with peer continuity.

### Gemini CLI

Useful but not default:
- `--resume latest`: convenient, but can cross-contaminate room context.
- `--prompt-interactive`: good for starting from a prompt and keeping the TUI open.
- `--worktree`: useful but mutates git state.
- `--output-format json|stream-json`: best for automation, not interactive console.
- `--include-directories`: task-specific workspace expansion.
- `--raw-output --accept-raw-output-risk`: preserves raw output, but unsafe for untrusted text.
- `--screen-reader`: accessibility-specific.

### Codex CLI

Useful but not default:
- `--no-alt-screen`: preserves terminal scrollback; useful for logging/debugging interactive sessions.
- `--search`: enables live web search; not default because it changes external I/O behavior.
- `--profile <name>` and `--model <model>`: task-specific.
- `--cd <dir>` / `--add-dir <dir>`: useful for explicit workspace scope, but wrapper should respect current terminal cwd.
- `resume`, `fork`, `archive`, `doctor`: operational commands, not session defaults.
- `--dangerously-bypass-hook-trust`: not default because it bypasses hook trust in addition to model approval/sandbox.

### Antigravity (`agy`)

Useful but not default:
- `--continue` / `--conversation <id>`: useful for manual resume, not safe as a silent default.
- `--prompt-interactive`: useful for seeded interactive sessions.
- `--model`: task-specific.
- `--print-timeout`: print-mode only.
- `--log-file`: useful for diagnostics.
- `--add-dir`: task-specific scope expansion.

## Claude Permission Surface

Claude can launch peer consoles through:

- Relative project permission: `Bash(_sys/cli/*.bat)`.
- Generated local absolute permissions from `_sys/ai/peers.json`.
- Current global absolute permissions in `_sys/claude/config/settings.json`.

The absolute permissions intentionally enumerate `claude.bat`, `gemini.bat`, `codex.bat`, and `agy.bat` instead of using a wildcard, so Claude's permission matcher does not have to interpret wildcard semantics for privileged console launches.
