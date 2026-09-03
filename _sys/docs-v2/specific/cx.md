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
account/runtime catalog on 2026-07-27 (corrected from a stale 2026-07-13
reading — Codex 0.145.0's release notes state GPT-5.6 Sol/Terra/Luna context
windows were corrected to 272,000 tokens, confirmed live; the configured Luna/low, Terra/high, and Sol/xhigh pairs were all invoked successfully on 2026-07-27):

| Profile | Model | Reasoning | CLI context |
|---|---|---|---:|
| `cx.standard` | `gpt-5.6-luna` | low | 272k |
| `cx.effort` | `gpt-5.6-terra` | high | 272k |
| `cx.deepthink` | `gpt-5.6-sol` | xhigh | 272k |

The local catalog records measured support for `low`, `medium`, `high`, `xhigh`,
and `max` on all three `gpt-5.6` profiles. `gpt-5.6-terra` and `gpt-5.6-sol`
also support `ultra`; `gpt-5.6-luna` does not. `model-registry.json` tracks
the same value (`context_limit`), also corrected to 272k on 2026-07-27.

## Context and Collaboration

Local Codex memory is not shared directly; the hub injects durable room
references and records promoted outputs.

---

## Session Policy

cx session reuse is enabled (`session_mode: reuse`). While `codex exec resume` rejects the `-s workspace-write` CLI flag, it accepts the equivalent configuration override via `-c sandbox="workspace-write"`. Hub invocations now use this syntax to maintain context continuity.

---

## Entry Point

`codex_entry.py` (peerhub package; removed from Engram in the Engram/peerhub separation):
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
| `health.json` (removed from Engram in the Engram/peerhub separation) | Health manifest — was updated by BOTH hub.py AND codex_entry.py |
| `CODEX.md` (removed in Engram/peerhub separation) | System instructions |
| `health.json["availability"]["authenticated"]` | OAuth auth status |
| `health.json["availability"]["entrypoint_ok"]` | Smoke test pass status |

---

## Token Constraint

cx has limited token budget — avoid large corpus analysis tasks. Prefer cc/gc for document-heavy work.
