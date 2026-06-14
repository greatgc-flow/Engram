# PEER_MANAGEMENT.md — Per-Peer Folder, Log & Config Locations

> **Version**: 1.0 | **Date**: 2026-06-13
> **Scope**: General (workspace-independent). All paths relative to `P:\` (SUBST root).
> **MECE**: Each peer has its own isolated directory under `_sys/<peer_id>/`.
> Cross-peer shared state lives in `_sys/ai/` and `_sys/data/`.

---

## 1. Peer Directory Overview

| Peer ID | Full Name       | Root Dir              | Entry Script                    | Status |
|:-------:|:----------------|:----------------------|:--------------------------------|:------:|
| `cc`    | Claude Code     | `_sys/claude/`        | `_sys/cli/claude.bat`           | Active |
| `gc`    | Gemini CLI      | `_sys/gemini/`        | `_sys/cli/gemini.bat`           | Active |
| `cx`    | Codex (OpenAI)  | `_sys/codex/`         | `_sys/cli/codex.bat`            | Active |
| `ag`    | AntiGravity     | `_sys/antigravity/`   | `_sys/cli/agy.bat`              | Inactive (default) |

---

## 2. Per-Peer Folder Structure

### 2-1. CC — Claude Code (`_sys/claude/`)

```
_sys/claude/
├── config/                      # Claude Code configuration
│   ├── CLAUDE.md                # Global user preferences (loaded every session)
│   ├── settings.json            # Claude Code CLI settings
│   ├── plans/                   # Claude planning documents
│   ├── projects/                # Per-project memory/context
│   │   └── P--/
│   │       └── memory/          # Persistent memory files
│   ├── sessions/                # Session snapshots
│   ├── cache/                   # Prompt/response cache
│   ├── downloads/               # Downloaded artifacts
│   ├── history.jsonl            # Command history
│   ├── tasks/                   # Task tracking
│   ├── telemetry/               # Usage telemetry
│   ├── daemon/                  # Background daemon state
│   ├── daemon.log               # Daemon log file
│   └── daemon.status.json       # Daemon health status
├── health.json                  # Peer health (GREEN/YELLOW/RED)
├── agent/                       # Sub-agent definitions
├── project/                     # Project-level config
└── templates/                   # Template files
```

**Key Files:**
- `health.json` — Updated by `hub.py health-update --peer cc`
- `config/CLAUDE.md` — User global instructions (apply to all workspaces)
- `config/projects/P--/memory/MEMORY.md` — Persistent memory index

### 2-2. GC — Gemini CLI (`_sys/gemini/`)

```
_sys/gemini/
├── config/                      # Gemini CLI configuration
│   ├── GEMINI.md                # Gemini system instructions
│   ├── settings.json            # CLI settings
│   ├── state.json               # Current session state
│   ├── history/                 # Conversation history
│   ├── projects.json            # Known projects
│   ├── trustedFolders.json      # Trusted folder list
│   ├── google_accounts.json     # Account info (no credentials)
│   ├── policies/                # Policy files
│   └── tmp/                     # Temporary files
├── health.json                  # Peer health (GREEN/YELLOW/RED)
├── project/                     # Project-level config
├── status.json                  # Current status snapshot
└── templates/                   # Template files
```

**Key Files:**
- `health.json` — Updated by `hub.py health-update --peer gc`
- `config/GEMINI.md` — Gemini session instructions (loaded at invocation)
- `config/settings.json` — Model, temperature, and tool settings

**Gate Scripts:**
- `_sys/gemini/gemini-gate.bat` — Pre-invocation health + auth gate
- `_sys/gemini/gemini-status.bat` — Print current gc status

### 2-3. CX — Codex (`_sys/codex/`)

```
_sys/codex/
├── config/                      # Codex configuration (CODEX_HOME)
│   ├── CODEX.md                 # Codex system instructions
│   └── tmp/                     # Temp files
├── health.json                  # Peer health (GREEN/YELLOW/RED)
├── project/                     # Project-level config
├── goals_1.sqlite               # Goals database
├── logs_2.sqlite                # Log database
├── memories_1.sqlite            # Memory database
└── state_5.sqlite               # State database
```

**Key Files:**
- `health.json` — Updated by `hub.py health-update --peer cx` AND by `codex_entry.py`
- `config/CODEX.md` — Codex system instructions
- `health.json["availability"]["authenticated"]` — OAuth auth status
- `health.json["availability"]["entrypoint_ok"]` — Smoke test pass status

**Entry Point:** `_sys/cli/codex_entry.py`
- Calls `hub.py init-session`, `hub.py context-fill`, then launches `codex.cmd`
- Updates `availability.last_invocation_duration_ms` after each run
- `CODEX_HOME` env var set to `_sys/codex/config/`

**Direct Invocation:**
```bat
_sys\cli\codex.bat
_sys\cli\codex.bat --no-alt-screen
```

The wrapper appends `-s workspace-write` unless the user provides an explicit sandbox or approval policy.

### 2-4. AG — AntiGravity (`_sys/antigravity/`)

```
_sys/antigravity/
├── config/
│   ├── AGY.md                   # AntiGravity system instructions
│   ├── bin/                     # AGY binary/scripts
│   ├── brain/                   # Reasoning modules
│   ├── builtin/                 # Built-in commands
│   ├── cache/                   # Response cache
│   ├── conversations/           # Conversation history
│   ├── history.jsonl            # Command history
│   ├── knowledge/               # Knowledge base
│   ├── keybindings.json         # Key bindings
│   ├── settings.json            # AGY settings
│   ├── status.json              # Current status
│   ├── usage.json               # Usage tracking
│   └── log/                     # Log files
├── health.json                  # Peer health (GREEN/YELLOW/RED)
├── project/                     # Project-level config
└── templates/                   # Template files
```

**Note:** ag is `inactive_default` — excluded from R:10 voting unless explicitly activated.

---

## 3. Shared State (`_sys/ai/`)

All peers read/write shared governance state from `_sys/ai/`. This directory is **General** (workspace-independent).

| File | Purpose | Owner |
|:-----|:--------|:------|
| `protocol.json` | Consensus rules, collab_rate, peer roles | All peers |
| `governance_params.json` | 45 risk/budget/autonomy parameters (v11) | All peers |
| `orchestration.json` | CLI invocation commands per peer | hub.py |
| `peers.json` | Peer capability registry | hub.py |
| `status_checks.json` | Gate conditions per peer | hub.py |
| `protocol.json` | collab_rate, r10_voters, timeouts | All peers |
| `model_profiles.json` | Model cost/capability matrix | budget system |
| `traceability_map.json` | TAXONOMY gap → implementation mapping | governance |
| `lifecycle_policy.json` | Session lifecycle rules | hub.py |
| `infra.json` | Infrastructure and runtime config | hub.py |

---

## 4. IPC Maildir (`_sys/data/`)

Hub.py uses Maildir-style per-message files for durable IPC.

```
_sys/data/
├── logs/                        # System logs
├── state/                       # Persistent state files
├── temp/                        # Temporary files (Claude task outputs)
│   └── claude/P--/<session_id>/
│       └── tasks/               # Task output files
└── sessions/                    # Session archive
```

**IPC Query Files** (for peer-to-peer `hub.py ask`):
- Location: `_sys/gemini/<peer_id>-{YYYYMMDDHHMMSS}-{RAND4}.txt`
- Format: `TASK/CONTEXT/QUESTION` in English
- Timeout: 180s default, 600s supported

---

## 5. Health Schema (`health.json`)

All peers use the same health.json schema, updated by `hub.py health-update --peer <id>`.

```json
{
  "context_health": {
    "status": "GREEN | YELLOW | RED",
    "jsonl_mb": 0.0,
    "last_updated": "ISO-8601",
    "consecutive_failures": 0
  },
  "session_health": {
    "status": "GREEN | YELLOW | RED",
    "failures": 0,
    "last_success_at": "ISO-8601",
    "session_count_today": 0
  },
  "availability": {
    "authenticated": true,
    "entrypoint_ok": true,
    "last_invocation_duration_ms": null,
    "last_invocation_exit_code": null
  }
}
```

**Key Invariants:**
- `availability.authenticated = True` is auto-set when `health-update --status GREEN --failures 0` succeeds
- `availability.entrypoint_ok = False` when status is RED
- `cx` additionally writes `last_invocation_duration_ms` via `codex_entry.py`

---

## 6. Log Files

| Peer | Log Location | Format | Notes |
|:-----|:------------|:-------|:------|
| `cc` | `_sys/claude/config/daemon.log` | Plain text | Claude daemon log |
| `cc` | `_sys/claude/config/history.jsonl` | JSONL | Command history |
| `gc` | `_sys/gemini/config/history/` | Directory | Conversation history |
| `cx` | `_sys/codex/config/logs_2.sqlite` | SQLite | Session logs |
| `ag` | `_sys/antigravity/config/log/` | Directory | Session logs |
| `ag` | `_sys/antigravity/config/history.jsonl` | JSONL | Command history |
| All  | `_sys/data/logs/` | JSONL | Hub/system logs |

---

## 7. Configuration Update Protocol

When updating peer config files, follow this protocol:

1. **`_sys/ai/protocol.json`** — Requires R:10 unanimous consent (all active voters)
2. **`_sys/ai/governance_params.json`** — Requires peer review (≥ collab_rate threshold)
3. **`_sys/<peer>/health.json`** — Updated via `hub.py health-update`, never manually
4. **`_sys/<peer>/config/*.json`** — Peer-local, no consensus required
5. **`_sys/<peer>/config/*.md`** — Peer instructions, can be updated by owner peer

**Never commit** to git:
- `oauth_creds.json`, `google_accounts.json` (credentials)
- `*.sqlite` (databases with personal data)
- `_sys/claude/config/mcp-needs-auth-cache.json`

---

## 8. Peer Gate Scripts

Entry points for launching each peer with health+auth pre-checks:

| Peer | Gate Script | Status Check |
|:-----|:-----------|:-------------|
| `cc` | `_sys/claude/claude-gate.bat` | `claude-status.bat` |
| `gc` | `_sys/gemini/gemini-gate.bat` | `gemini-status.bat` |
| `cx` | `_sys/cli/codex.bat` → `codex_entry.py` | `_sys/codex/health.json` |
| `ag` | `_sys/cli/agy.bat` → `agy_entry.py` | `_sys/antigravity/health.json` |

Console autonomy defaults (minimum permission profiles) are documented in `_sys/docs/protocol-permissions.md`.

---

> *Generated by cc (Claude Code) as part of Full System Overhaul v11 — 2026-06-13*
> *MECE: Each section covers exactly one aspect of peer management with no overlap.*
