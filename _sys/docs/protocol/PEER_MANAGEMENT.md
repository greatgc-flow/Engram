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
Authoritative field names match `hub.py _read_peer_health()` and `protocol-health.md §2`.

```json
{
  "_version": "1.0",
  "peer_id": "gc",
  "context_health": {
    "status": "GREEN | YELLOW | RED",
    "jsonl_mb": 0.0,
    "checked_at": "20260614T120000",
    "source": "self"
  },
  "session_health": {
    "consecutive_failures": 0,
    "last_failure_reason": null,
    "last_success_at": "2026-06-14T12:00:00",
    "session_count_today": 0,
    "session_date": "20260614"
  },
  "availability": {
    "gate_open": true,
    "entrypoint_ok": true,
    "authenticated": true,
    "rate_limit_state": "ok",
    "last_invocation_exit_code": null,
    "last_invocation_duration_ms": null
  }
}
```

**Key Invariants:**
- `context_health.checked_at` — timestamp written by hub.py (not `last_updated`)
- `session_health.consecutive_failures` — incremented on failure, reset on success (not `failures`)
- `session_health.last_failure_reason` — last classified failure reason (timeout, rate_or_session_limit, etc.)
- `availability.gate_open` — false when peer is quarantined; blocks routing
- `cx` additionally writes `last_invocation_duration_ms` via `codex_entry.py`

> Cross-reference: `protocol-health.md §2` for status transition rules, `§11` for gc-specific legacy gate.

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

## 9. New Peer Onboarding Checklist

Use this checklist when activating a new peer or re-activating an inactive one (e.g., bringing ag back online after the `--dangerously-skip-permissions` gap is resolved).

### 9-1. Pre-Activation (Before any ask)

- [ ] **Read mandatory docs**: `PROTOCOL.md`, `_sys/docs/PROTOCOL_INVARIANTS.md`, `_sys/docs/protocol-permissions.md`
- [ ] **Verify permission profile**: `python _sys/core/hub.py profile-validate --peer <id>` — must pass parity check (no FORBIDDEN flags, no missing REQUIRED flags)
- [ ] **Initialize health file**: `python _sys/core/hub.py health-update --peer <id> --status GREEN --failures 0`
- [ ] **Register in peers.json**: Add capability entry and gate config (if peer has a legacy gate file like gc's `status.json`)
- [ ] **Add to `orchestration.json`**: CLI invocation command with correct minimum flags (DIR-002)
- [ ] **Add to `protocol.json["collab_rate"]["r10_voters"]`**: Only if peer will participate in R:10 votes

### 9-2. First Ask Validation

- [ ] Run `python _sys/core/hub.py health-precheck --peer <id>` — must return GREEN/YELLOW, gate_open=true
- [ ] Send a minimal smoke-test ask: `python _sys/core/hub.py ask --to <id> --query-file <test_file>`
- [ ] Confirm `_record_ask_success()` ran (health.json `consecutive_failures` reset to 0)
- [ ] Confirm session fingerprint written to health.json (if peer supports session resume)

### 9-3. Mandatory Invariants (INV-05, PRO-01~05)

- **NEVER** pass raw user text as executable arguments (PRO-01)
- **NEVER** grant root/admin elevation (PRO-02)
- **NEVER** use bypass/full-danger flags (`yolo`, `dangerously-bypass-*`) (PRO-03)
- **MUST** run minimum non-interactive permissions as specified in `protocol-permissions.md §2` (INV-12)

### 9-4. ag-Specific Gate (PRO-15)

ag remains inactive until `peer_console.py` ag block is updated with correct minimum flags.
Current known gap: `--dangerously-skip-permissions` is used but violates PRO-03.
Recovery path: Replace with `--permission-mode acceptEdits --allowedTools Edit Write Read Glob Grep Bash MultiEdit`, then re-run `profile-validate`.

---

> *Generated by cc (Claude Code) as part of Full System Overhaul v11 — 2026-06-13*
> *MECE: Each section covers exactly one aspect of peer management with no overlap.*
