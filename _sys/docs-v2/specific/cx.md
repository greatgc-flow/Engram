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

Environment variable: `CODEX_HOME` → `_sys/codex/config/`. Hub IPC pins this via
`peers.json` `codex.env_vars.CODEX_HOME = "config"` (resolved to `_sys/codex/config`).
Without the pin, `codex.cmd` falls back to the host home `~/.codex` — non-portable and
a cold-cache re-sync that can silently stall an ask until the zombie timeout. Interactive
launch pins the same home via `codex_entry.py`.

---

## Permission Flags (delta from general/permissions.md)

```
codex exec -s workspace-write --json
```

FORBIDDEN: `--dangerously-bypass-approvals-and-sandbox`, `-s full-auto`.

## Runtime Profiles

`cx.standard`, `cx.effort`, and `cx.deepthink` are generated from
`orchestration.json`. The root default is `cx.deepthink`; hub root asks may
automatically select a profile based on task shape.

`codex debug models` and minimal profile invocations verified the current
account/runtime catalog on 2026-07-13:

| Profile | Model | Reasoning | CLI context |
|---|---|---|---:|
| `cx.standard` | `gpt-5.6-luna` | low | 372k |
| `cx.effort` | `gpt-5.6-terra` | high | 372k |
| `cx.deepthink` | `gpt-5.6-sol` | xhigh | 372k |

The local catalog records measured support for `low`, `medium`, `high`, `xhigh`,
and `max` on all three `gpt-5.6` profiles. `gpt-5.6-terra` and `gpt-5.6-sol`
also support `ultra`; `gpt-5.6-luna` does not. Runtime catalog context is
intentionally recorded separately from the larger API maximum in
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
