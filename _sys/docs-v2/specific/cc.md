# Specific — cc (Claude Code)
> Delta-only from general/*. Status: ACTIVE.

---

## Directory Layout & Key Files
```
_sys/claude/
├── config/
│   ├── CLAUDE.md           ← global user preferences (loaded every session)
│   ├── settings.json       ← CLI settings
│   ├── plans/              ← planning documents
│   ├── projects/P--/memory/MEMORY.md  ← persistent memory index
│   ├── sessions/           ← session snapshots
│   └── history.jsonl       ← command history
├── health.json             ← peer health
└── agent/                  ← sub-agent definitions
```
- **Project Config:** `P:\CLAUDE.md` (consumed by Claude Code CLI at startup).

## Permission Flags
```
claude -p {query} --dangerously-skip-permissions
```

## Runtime Profiles
| Profile | Model | Effort | CLI context observed |
|---|---|---|---:|
| `cc.standard` | `claude-haiku-4-5-20251001` | low | 200k |
| `cc.effort` | `claude-sonnet-4-6` | high | 200k |
| `cc.deepthink` | `claude-opus-4-8` | max | 1M |

*(Note: Claude Fable 5 is recognized via `fable`/`claude-fable-5` but not routed if unavailable to the account. Claude Code lacks a zero-token catalog command).*

## Session & State
- **Session reuse:** hub IPC asks reuse per `session_mode: reuse` (orchestration.json), scoped by `room_id`. The interactive human-facing cc terminal is a separate fresh session per launch.
- **Local Memory:** Claude-local memory is not automatically shared with other peers.

## Gate & Entry
- **Gate script:** `_sys/claude/claude-gate.bat`
- **Status check:** `claude-status.bat`

## Update Protocol & Health
- `config/CLAUDE.md` — update via `ctx-end --global` or manual edit.
- `config/projects/*/memory/` — auto-managed by cc memory system.
- `health.json` — ONLY via `hub.py health-update --peer cc`.
- **Auto-Remediation (INV-15/16):** cc cannot be auto-restarted silently by SelfHealer Tier-0/1. On RED state: SelfHealer logs the event and escalates to Human Gate.

## Context and Collaboration
*(Delta from general/protocol.md + general/learning.md.)*
- **Primary human-interface terminal:** cc most often holds the thin-terminal role (GAP-1/PRO-19) — routes/relays, does not self-analyze once a worker is selected.
- **Local memory is private:** cc's `projects/*/memory/` is NOT auto-propagated to peers; durable cross-peer knowledge must go through the lesson/directive loop (general/learning.md), not cc-local memory.
