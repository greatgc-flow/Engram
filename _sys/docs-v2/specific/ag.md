# Specific — ag (AntiGravity)
> Delta from general/*. Status: ACTIVE (gc replacement, 2026-06-19).

---

## Status: ACTIVE

ag is an active consensus voter (cc/ag/cx). Replaces gc after IneligibleTierError (tier_suspended 2026-06-19).

Peer equality means equal governance rights and role eligibility. CLI permission
flags remain adapter-specific under DIR-002.

**Permission profile:**
```
agy --dangerously-skip-permissions -p {query} --print-timeout 60m
```

**Critical Windows note:** agy writes to Windows Console API, not stdout pipes.
`requires_pty=true` is mandatory in orchestration.json. subprocess.PIPE capture hangs indefinitely.

## Invocation Contract

- **Inline prompt, not stdin:** ag uses inline `-p {query}`. agy empirically ignores
  `-p -` (it does not read the prompt from stdin), so the hub passes the query inline
  via `_substitute_args` in `AgyAdapter.build_cmd`.
- **`--print-timeout 60m`:** this is the agy *child-process* output ceiling, not the
  hub deadline. The hub-side `timeout: 300` (seconds) remains the authoritative deadline;
  `60m` only prevents agy from self-terminating its print loop before the hub decides.
- **`session_mode: none`:** ag is not hub-managed for session reuse. The hub never sends
  `-c` / `--continue` / `--conversation`, so each ask is an independent `agy -p` invocation.

### Durable conversations (storage ≠ session reuse)

`session_mode: none` is a statement about *hub-managed reuse*, **not** a claim of stateless
storage. agy itself persists conversation state on disk:

- `AGY_CONFIG_HOME/config/conversations/*.db` and the `implicit/` directory are **durable**.
- A bare `agy -p` invocation **may load ambient/implicit context** from that store.
- Therefore `session_mode: none` must NOT be read as "ag has no memory between calls" — it
  only means the hub does not orchestrate `-c`/`--continue`/`--conversation` resume flags.
  Storage-level durability is an agy-internal behavior outside hub control.

## Runtime Profiles

The available model labels were verified locally through `agy models` using a
Windows PTY on 2026-06-20:

| Profile | Runtime model |
|---|---|
| `ag.standard` | `Gemini 3.5 Flash (Low)` |
| `ag.effort` | `Gemini 3.5 Flash (High)` |
| `ag.deepthink` | `Gemini 3.1 Pro (High)` |

The terminal and root default use `ag.standard`. Each profile passes its model
label through `agy --model`. The CLI's persistent `settings.json` model is not
modified by profile invocation.

`agy models` writes through the Windows Console API. Capturing it with ordinary
stdout returns an empty string; model discovery and validation require a PTY.

## Context and Collaboration

ag receives the common versioned room references. PTY output becomes shared state
only after the hub records or promotes it.

---

## Directory Layout

```
_sys/antigravity/
├── config/
│   ├── AGY.md              ← session instructions
│   ├── brain/              ← reasoning modules (now archived to _archive/reviews/agy/)
│   ├── builtin/            ← built-in commands
│   ├── settings.json       ← agy settings
│   └── log/                ← session logs
├── health.json             ← peer health (runtime-generated)
└── project/
```

---

## Gate & Entry (when active)

- Entry: `_sys/cli/agy.bat` → `agy_entry.py`
- Health: `_sys/antigravity/health.json`
- Config: `CODEX_HOME`-style env var pointing to `_sys/antigravity/config/`
