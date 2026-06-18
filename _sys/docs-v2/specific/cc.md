# Specific — cc (Claude Code)
> Delta from general/*. Load after general/. Status: ACTIVE.

---

## Directory Layout

```
_sys/claude/
├── config/
│   ├── CLAUDE.md           ← global user preferences (loaded every session)
│   ├── settings.json       ← Claude Code CLI settings
│   ├── plans/              ← planning documents
│   ├── projects/P--/memory/MEMORY.md  ← persistent memory index
│   ├── sessions/           ← session snapshots
│   └── history.jsonl       ← command history
├── health.json             ← peer health (GREEN/YELLOW/RED)
├── agent/                  ← sub-agent definitions
└── project/                ← project-level config
```

---

## Permission Flags (delta from general/permissions.md)

```
claude --allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits
```

No additional flags. FORBIDDEN: `--dangerously-skip-permissions`.

---

## Gate & Entry

- Gate script: `_sys/claude/claude-gate.bat`
- Status check: `claude-status.bat`
- Context: `P:\CLAUDE.md` (project root) + `_sys/claude/config/CLAUDE.md` (global)
- No session reuse — fresh session per invocation (cc is the human interface peer)

---

## Key Files

| File | Role |
|------|------|
| `_sys/claude/health.json` | Health manifest |
| `_sys/claude/config/CLAUDE.md` | Global preferences (all projects) |
| `_sys/claude/config/projects/P--/memory/MEMORY.md` | Persistent memory index |
| `P:\CLAUDE.md` | Project-level config (consumed by Claude Code CLI at startup) |

---

## Update Protocol

- `config/CLAUDE.md` — update via `ctx-end --global` or manual edit
- `config/projects/*/memory/` — auto-managed by cc memory system
- `health.json` — ONLY via `hub.py health-update --peer cc`

---

## Health & Auto-Remediation

- INV-15 triggers SelfHealer when `consecutive_failures ≥ failure_threshold` (default 5, from `protocol.json["health"]`).
- cc is the **primary human interface node** and cannot be auto-restarted by SelfHealer Tier-0/1 without explicit human approval.
- On cc RED state: SelfHealer logs the event, escalates to Human Gate (INV-16). Do NOT auto-recover cc silently.
- See `general/self-evolution.md §2.1` for full SelfHealer tier description.
