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
claude -p {query} --dangerously-skip-permissions
```

This is the current DIR-002 adapter mapping. It does not define governance
equality; all active peers have equal vote and role rights independently of CLI
flag syntax.

## Runtime Profiles

`cc.standard`, `cc.effort`, and `cc.deepthink` are generated from the nested
profiles in `orchestration.json`. The terminal and root default use
`cc.standard`; hub root asks may automatically select a higher profile.

The current account was verified by minimal JSON invocations on 2026-06-20:

| Profile | Model | Effort | CLI context observed |
|---|---|---|---:|
| `cc.standard` | `claude-haiku-4-5-20251001` | low | 200k |
| `cc.effort` | `claude-sonnet-4-6` | high | 200k |
| `cc.deepthink` | `claude-opus-4-8` | max | 1M |

Claude Fable 5 is the newest generally available Anthropic model and the CLI
recognizes the `fable`/`claude-fable-5` selector. It is not available to the
current account, so it is recorded in `model-registry.json` but is not routed.
Claude Code does not expose a zero-token model catalog command; availability
must be rechecked with a minimal invocation when profiles or account access
change.

## Context and Collaboration

cc receives the same versioned room references and durable handoff contract as
every peer. Claude-local memory is not automatically shared with other peers.

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

- INV-15 triggers SelfHealer when `consecutive_failures ≥ protocol.json["health"]["failure_error"]`.
- cc is the **primary human interface node** and cannot be auto-restarted by SelfHealer Tier-0/1 without explicit human approval.
- On cc RED state: SelfHealer logs the event, escalates to Human Gate (INV-16). Do NOT auto-recover cc silently.
- See `general/self-evolution.md §2.1` for full SelfHealer tier description.
