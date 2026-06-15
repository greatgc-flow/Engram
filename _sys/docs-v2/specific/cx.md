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

---

## Session Reuse (delta from general/session.md)

- New: `codex exec -s workspace-write --json --ignore-rules`
- Resume: `codex exec resume <thread_id> -s workspace-write --json --ignore-rules`
- State: `_sys/codex/session_state.json`
- `hub.py ask --session-policy fresh` for independent cross-review calls (§14 queries)

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
