# Portable Sandbox Dev Environment (Porta-Flow)

A fully isolated portable development environment based on a single Windows folder.  
Carry it on a USB drive or cloud drive — spin up **the exact same environment** on any PC and collaborate with AI agents immediately.

---

## Project Structure (Minimalist Core)

Only **design files and scripts** are git-tracked. Heavy binaries and data are managed automatically by `install.bat`.

```
[PortableDev Root]
├── install.bat               ← First-time install and environment rebuild (ZeroBase)
├── register.bat              ← Register PC (SUBST assignment + right-click menu)
├── unregister.bat            ← Permanent PC removal (context menu + SUBST deletion)
├── cleanup.bat               ← Tiered space optimization (Level 1~4)
│
├── CLAUDE.md                 ← Claude Code collaboration guide
├── GEMINI.md                 ← Gemini CLI collaboration guide
├── README.md                 ← This document
├── CONVENTION.md             ← Coding and agent conventions
├── PROTOCOL.md               ← P2P collaboration protocol (consensus, division of labor, session continuity)
├── WORKLOG.md                ← Change history and current mission
│
├── workspace/                ← Default project workspace
├── .claude/                  ← Claude Code harness (agents/, skills/)
├── .ai/                      ← IPC state (hub.py only — never write directly)
├── _state/                   ← Agent session workspace (auto-managed)
├── _archive/                 ← Logs, sessions, workspace backups
└── _sys/                     ← System layer (logic and config)
    ├── core/                 ← System core logic (hub.py, setup.py, manage.py)
    ├── cli/                  ← User entry tools (msg.bat, manage.bat, cleanup.bat)
    ├── checks/               ← Axis A~I static analysis scans
    ├── hooks/                ← Agent lifecycle hooks
    ├── tests/                ← Unit / integration / sandbox test suite
    ├── templates/            ← Copy-ready file templates
    ├── data/                 ← Session and log data (local)
    ├── env/                  ← Python, Node.js, VS Code, Git portable binaries
    ├── tools/                ← Auxiliary CLI tools (ripgrep, jq, etc.)
    ├── claude/               ← Claude Code CLI config and agent definitions
    ├── gemini/               ← Gemini CLI config (Directory Junction integration)
    └── git-config/           ← Portable git environment config
```

---

## Quick Start

1. **First-time install**: Double-click `install.bat`  
   - Automatically downloads Portable Python, Node.js, Git, VS Code, etc. and builds the environment.
2. **Register PC**: Double-click `register.bat`  
   - Adds **'Open in Sandbox'** to Windows Explorer right-click menu and assigns a fixed drive (SUBST).
3. **Launch environment**: Right-click folder → select **Open in Sandbox**  
   - VS Code launches in an isolated environment with all tools auto-registered in PATH.

---

## Agent Collaboration and Security (P2P Peer)

This environment is designed for **Claude Code, Gemini CLI, Claude Agent**, and all other nodes to collaborate as **equal Peers**. No vertical tier structure — unanimous consensus in an N-Way Room session, then division of labor.

- **N-Way Room Session**: All nodes share the same context via a common `handoff.md` under `.ai/`.
- **Unanimous Consensus**: Critical decisions go through full consensus via `msg.bat consensus`. (`PROTOCOL.md §P-3`)
- **Full Isolation**: All caches and settings are stored inside the folder — no host PC contamination.

---

## Management Principles (Portability)

1. **ZeroBase Architecture**: With only the essential scripts present, running `install.bat` restores 100% of the environment anywhere.
2. **Minimal Git Tracking**: Binaries (`env/`, `tools/`), logs (`_archive/`), and state (`.ai/`) are excluded from git to keep the repo lightweight.
3. **Relative Path Basis**: All paths are calculated dynamically at runtime — drive letter changes cause no disruption.

---

## Testing and Verification

System stability is ensured through 3 levels of testing:

- **Unit Tests**: Validates hub.py IPC and consensus logic.
- **Integration Tests**: Validates interactions between real tools (msg.bat, git, etc.).
- **WSB Tests**: Validates destructive lifecycle (ZeroBase install) inside Windows Sandbox.

Run: `_sys\tests\run-tests.bat --all`
