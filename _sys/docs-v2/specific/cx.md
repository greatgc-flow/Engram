# Specific — cx (Codex / OpenAI CLI)
> Delta from general/*. Load after general/. Status: ACTIVE.

---

## Directory Layout

```
_sys/codex/
├── config/
│   ├── CODEX.md            ← system instructions
│   └── tmp/
├── health.json             ← peer health
├── goals_1.sqlite          ← goals database
├── logs_2.sqlite           ← log database
├── memories_1.sqlite       ← memory database
└── state_5.sqlite          ← state database
```

Environment variable: `CODEX_HOME` → `_sys/codex/config/`

---

## Permission Flags (delta from general/permissions.md)

```
codex exec -s workspace-write --json --ignore-rules
```

FORBIDDEN: `--dangerously-bypass-approvals-and-sandbox`, `-s full-auto`.

## Runtime Profiles

`cx.standard`, `cx.effort`, and `cx.deepthink` are generated from
`orchestration.json`. The terminal and root default use `cx.standard`; hub root
asks may automatically select a higher profile.

`codex debug models` and minimal profile invocations verified the current
account/runtime catalog on 2026-06-20:

| Profile | Model | Reasoning | CLI context |
|---|---|---|---:|
| `cx.standard` | `gpt-5.4-mini` | low | 272k |
| `cx.effort` | `gpt-5.5` | high | 272k |
| `cx.deepthink` | `gpt-5.5` | xhigh | 272k |

The local catalog also exposes `gpt-5.4`. All three visible models support
`low`, `medium`, `high`, and `xhigh`; their default is `medium`. Runtime catalog
context is intentionally recorded separately from the larger API maximum in
`model-registry.json`.

## Context and Collaboration

Local Codex memory is not shared directly; the hub injects durable room
references and records promoted outputs.

---

## Session Policy

cx session reuse is enabled (`session_mode: reuse`). While `codex exec resume` rejects the `-s workspace-write` CLI flag, it accepts the equivalent configuration override via `-c sandbox="workspace-write"`. Hub invocations now use this syntax to maintain context continuity.

---

## Entry Point

`_sys/cli/codex_entry.py`:
1. Calls `hub.py init-session`, `hub.py context-fill`
2. Launches `codex.cmd`
3. Updates `availability.last_invocation_duration_ms` after each run

Direct invocation:
```
_sys\cli\codex.bat
_sys\cli\codex.bat --no-alt-screen
```

---

## Key Files

| File | Role |
|------|------|
| `_sys/codex/health.json` | Health manifest — updated by BOTH hub.py AND codex_entry.py |
| `_sys/codex/config/CODEX.md` | System instructions |
| `health.json["availability"]["authenticated"]` | OAuth auth status |
| `health.json["availability"]["entrypoint_ok"]` | Smoke test pass status |

---

## Token Constraint

cx has limited token budget — avoid large corpus analysis tasks. Prefer cc/gc for document-heavy work.
