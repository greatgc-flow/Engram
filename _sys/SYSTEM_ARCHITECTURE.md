# SYSTEM ARCHITECTURE — Portable Dev Environment (P2P Collab v3)

> Describes the design decisions and equal-authority P2P collaboration structure of the `_sys/` system layer.

---

## 1. Layer Structure

```
[User / All AI Nodes]
        ↓
[Entry]  _sys/cli/claude.bat  gemini.bat  msg.bat  manage.bat  cleanup.bat  install.bat
        ↓ (PORTABLE_ROOT + venv PATH injection)
[Logic]  _sys/core/hub.py  setup.py  manage.py  cleanup.py
        ↓
[State]  .ai/  ← project-local AI state (mailbox.json, state.json, sessions/)
        ↓
[Lifecycle] _sys/hooks/ (session-end, log-write, raw-log, ai-check, collab-log, archive-data, ctx-save, ctx-end)
[Analysis]  _sys/checks/ (check-risk, check-agents, check-deps, check-health, check-versions)
[Tools]     _sys/cli/ (git-draft, batch-review) + _sys/hooks/ (archive-data)
```

## 2. hub.py — P2P Message Broker (Facade Pattern)

**Raw Data Philosophy**: All output is lossless pretty-print Markdown.
**Equal Authority**: All nodes call the actions below with equal permissions.

### Write Actions (filelock applied)

| Action | Description | Lock |
|--------|-------------|------|
| `init-session --agent A [--room R]` | Create or join a Room (issues room-{uuid}) | state.lock |
| `end-session --agent A` | Update handoff.md, clean mailbox | state.lock + mailbox.lock |
| `send --from A --to B --msg TEXT` | Send message within N-Way Room | mailbox.lock |
| `mark-read --target A` | Mark messages as read | mailbox.lock |
| `append-log --axis X --status S` | Write to .ai/log.jsonl | log.lock |
| `update-status --mission T` | Update mission/status (reflects consensus) | state.lock |

### Read Actions (Lock-Free)

| Action | Description |
|--------|-------------|
| `check --target A` | Pretty-print received messages |
| `status` | Full Room state + raw handoff pretty-print |

### Sync Action

| Action | Description |
|--------|-------------|
| `ask --to NODE --query TEXT` | Synchronous query to a specific node (subprocess) |

---

## 3. .ai/ Folder Structure (N-Way Room)

```
.ai/
├── mailbox.json          Message queue (shared by all Room participants)
├── state.json            Room ID + participating nodes (members) list
├── log.jsonl             Execution log
├── .lock/                File locks for concurrent access control
└── sessions/
    └── room-{uuid}/      Single shared N-Way session context
        └── handoff.md    Room shared memory (FIFO)
```

## 4. Room ID and P2P Communication

- **Room ID**: `room-{uuid}` (e.g., `room-a1b2`).
- **P2P Principle**: No single node monopolizes orchestration; all messages flow equally from `from` node to `to` node (or `broadcast`).
- **Context Sharing**: All nodes in the same Room read and write the same `handoff.md` to sync context.

## 5. handoff.md Structure (Single Room Shared)

```markdown
## [GOAL]               ← Room-wide final objective
## [RECENT_COMPLETED]   ← All participating nodes' achievements (FIFO)
## [PENDING_ISSUES]     ← Issues currently requiring resolution
## [KEY_DECISIONS]      ← Unanimously agreed decisions
## [CONSENSUS_HISTORY]  ← Unlimited consensus round history
## [ACTIVE_THREADS]     ← In-progress task chains (division of labor)
```

## 6. Batch File Structure Principles

- **≤5-line rule**: No logic in bat files. All logic delegated to `_sys/core/*.py` or dedicated `.py` modules.
- **PORTABLE_ROOT**: Dynamic calculation via `%~dp0` — no hardcoded drive letters.
- **Exception**: `start.bat` — must remain bat to set parent process env vars (SUBST restore + PATH/VENV injection).

## 7. Collaborative Axis (Generalized Analysis Tools)

Token budget details: `CONVENTION.md §3-4-D`

| Axis | Trigger Script | Purpose | GC |
|------|---------------|---------|-----|
| A | `check-portability.bat` / portability-auditor | Full corpus portability audit | ✓ |
| B | `check-versions.bat` | Runtime & tool version check | ✓ |
| C | `ctx-end.bat` | Session end summary | ✓ |
| D | inline syntax check | bat/py syntax validation | ✓ |
| D+ | `ctx-save.bat` | Mid-session snapshot (opt-in) | ✓ |
| E | `check-agents.bat` | agents/*.md audit | ✓ |
| F | `check-deps.bat` | Script dependency map | ✓ |
| G | `git-draft.bat` | Commit message draft | ✓ |
| H | `check-health.bat` | Context health check | ✓ |
| I | `check-risk.bat` | Pre-flight risk scan (Phase 1.5) | ✓ |

---

## 8. Quick Path Reference

| Component | Path |
|-----------|------|
| Core Python | `_sys/core/hub.py` |
| CLI Entry | `_sys/cli/claude.bat`, `gemini.bat`, `msg.bat` |
| AI State | `.ai/state.json` (write via hub.py only) |
| Room Session | `.ai/sessions/room-*/handoff.md` |
| Tests | `_sys/tests/run-tests.bat` |
