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
- **`session_mode: reuse`:** ag is now hub-managed for session reuse to align horizontally with other peers. The hub tracks and injects `--conversation <ID>` to maintain state continuity for background asks.

### Durable conversations (storage → session reuse)

`session_mode: reuse` ensures that hub-managed IPC asks leverage agy's internal storage explicitly via `--conversation <ID>`:

- `AGY_CONFIG_HOME/conversations/*.db` and the `implicit/` directory are **durable**.
- A bare `agy -p` invocation **auto-continues ambient/implicit context** from that store
  even with no `-c`/`--conversation` flag (empirically verified 2026-06-23: a fresh
  config home answered a fresh query cleanly; the shared home ignored the query and
  replayed prior session state).
- Therefore, `session_mode: reuse` brings ag into horizontal alignment with other peers, meaning the hub orchestrates `--conversation` resume flags while relying on agy's robust internal `conversations/` `.db` durability.

### IPC stateless home (A6 contamination fix)

Because agy auto-continues durable state, **hub IPC asks would otherwise inherit prior
interactive session content** (the A6 contamination root cause: an ag ping replied about
unrelated prior work that was never in the prompt). The hub fixes this **without touching
the user's interactive `config/` home**:

- `peers.json → antigravity.ipc_stateless_home` declares a dedicated **IPC config home**
  (`_sys/antigravity/ipc-config/`).
- Before every hub IPC invocation, `hub._prepare_ipc_stateless_home()`:
  1. **Seeds** auth/model files from `config/` by explicit allowlist
     (`settings.json`, `installation_id`, `AGY.md`, `keybindings.json`, `status.json`,
     `usage.json`) — so model selection and auth still resolve and ag actually runs.
  2. **Recreates the durable-state dirs (`conversations/`, `implicit/`) EMPTY** on every
     call, so each ask is stateless.
- The hub then **repoints `AGY_CONFIG_HOME` and `GEMINI_DIR`** (the `env_keys`) at the IPC
  home for the ag invocation only.
- **Non-destructive:** the interactive `config/` home — including its 100+ durable
  `conversations/*.db` — is never read-modified or deleted.
- **General-specific clean:** this is a config-declared capability resolved in the generic
  env-injection path (`target_peer_cfg.get("ipc_stateless_home")`); there is **no peer-id
  branch** in core dispatch. Peers without the key (cc/cx) are entirely unaffected — their
  environment is byte-identical.
- The IPC home is fully runtime-generated and `.gitignore`d (`_sys/antigravity/ipc-config/`).

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
├── config/                 ← INTERACTIVE home (durable; never mutated by hub IPC)
│   ├── AGY.md              ← session instructions
│   ├── brain/              ← reasoning modules (now archived to _archive/reviews/agy/)
│   ├── builtin/            ← built-in commands
│   ├── conversations/      ← durable session .db store (auto-continued by agy)
│   ├── implicit/           ← durable implicit context
│   ├── settings.json       ← agy settings
│   └── log/                ← session logs
├── ipc-config/             ← STATELESS IPC home (A6; gitignored, runtime-generated)
│   ├── settings.json       ← seeded from config/ (auth/model resolve)
│   ├── installation_id     ← seeded from config/
│   ├── AGY.md              ← seeded from config/
│   ├── conversations/      ← recreated EMPTY before every IPC ask
│   └── implicit/           ← recreated EMPTY before every IPC ask
├── health.json             ← peer health (runtime-generated)
└── project/
```

---

## Gate & Entry (when active)

- Entry: `_sys/cli/agy.bat` → `agy_entry.py`
- Health: `_sys/antigravity/health.json`
- Config: `CODEX_HOME`-style env var pointing to `_sys/antigravity/config/`
