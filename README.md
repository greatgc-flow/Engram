# Porta-Flow: Self-Evolving Multi-AI Dev Workspace

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Windows](https://img.shields.io/badge/os-windows-green.svg)](https://microsoft.com/windows)
[![Tests: 299 Pass](https://img.shields.io/badge/tests-299%20pass-success.svg)](_sys/tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Windows-first portable dev workspace where Claude (`cc`), Gemini (`gc`), Codex (`cx`), and Antigravity (`ag`) collaborate as **equal peers** alongside human developers — fully portable on USB or cloud drive, with a **self-evolving collaboration loop** that learns from every session.

---

## 🧠 Self-Evolution System

The unique selling point: lessons extracted from peer interactions automatically propagate to all nodes and harden into runtime rules.

```
Peer session output
  → [LESSON_LEARNED:] tag
  → lesson-extractor agent
  → hub.py lessons-propose → lessons-activate
  → lesson-broadcast (all peers via .ai/mailbox.json)
  → trigger_count ≥ 3 → lesson-sweep
  → runtime-directives.jsonl (binding on all future sessions)
```

No human required. No peer repeats another's mistake.

---

## 🏗 Architecture

```
Human
  │
  ▼
_sys/cli/msg.bat
  │
  ▼
_sys/core/hub.py ◄──────── _sys/ai/protocol.json  (SSOT: collab_rate, routing, guards)
  │                         _sys/ai/user-directives.md
  │                         _sys/ai/runtime-directives.jsonl  (evolved rules)
  │
  ├── cc / ca  Claude — architecture, implementation, verification
  ├── gc       Gemini — large-context analysis, documentation, audit
  ├── cx       Codex  — code review, refactoring, patch planning
  └── ag       Antigravity — shell ops, workflow orchestration
```

Peers share room state through `.ai/`, exchange messages through the hub, record handoff context in rolling markdown, and use `lesson-*`, `thread-*`, and `proposal-*` actions to govern and evolve collaboratively.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🤖 **Multi-AI Peers** | `cc`, `gc`, `cx`, `ag` work as equals — no coordinator monopoly (AP-20). |
| 🧬 **Self-Evolving** | Lessons auto-broadcast; `trigger_count ≥ 3` promotes to runtime directives. |
| 🛡 **Consensus-Driven** | R:10 unanimous governance gates for high-risk `_sys/` changes. |
| 🧳 **100% Portable** | Runtimes, tools, CLI wrappers, and AI configs live in `_sys/`. Zero host pollution. |
| 🔧 **Tool Registry** | 15 shared tools (9 agents + 6 skills) — any peer can invoke any tool. |
| 🛰 **P2P Mailbox** | File-based IPC — no server, no broker, works offline. |
| 🔍 **21 Anti-Patterns** | `cross-reviewer` agent detects AP-01~AP-21 (consensus drift, governance violations, etc.). |
| 📋 **Audit Trail** | Proposals, threads, handoffs, and routing metrics fully traceable. |

---

## 🚀 Quick Start

```bat
REM 1. Rebuild portable runtimes and tools
INSTALL.bat

REM 2. Register this folder on the current PC (creates SUBST drive, context menu)
register.bat

REM 3. Check the live collaboration room
_sys\cli\msg.bat status

REM 4. Validate the multi-agent hub
_sys\tests\run-tests.bat --all
```

---

## 📂 Project Structure

```
.
├── README.md / CLAUDE.md / GEMINI.md / AGENTS.md  ← Peer workspace guides
├── PROTOCOL.md / CONVENTION.md                      ← Constitutional docs
├── INSTALL.bat / register.bat / unregister.bat / CLEANUP.bat
├── workspace/          ← Default user workspace
├── .ai/                ← Runtime collaboration state (hub-managed only)
├── _archive/           ← Logs, sessions, collab-log
└── _sys/
    ├── ai/             ← protocol.json (SSOT), peers.json, knowledge/, proposals/
    │   └── common/     ← tool-registry.json + 9 agents + 6 skills (shared across peers)
    ├── core/           ← hub.py (IPC hub v4.2), launcher.py, setup.py, config.py
    ├── cli/            ← msg.bat, peer wrappers, manage.py, peer_console.py
    ├── checks/         ← Health, policy, portability, risk checks (Axis A-I)
    ├── docs-v2/        ← SSOT v1.1: invariants, general rules, peer-specific, ops
    ├── docs/           ← Archive: history/, architecture/, plans/, user/
    ├── hooks/          ← ctx-save, ctx-end, collab-log, memory-compactor
    ├── tests/          ← 299 unit tests + integration + WSB sandbox
    ├── templates/      ← CLAUDE_*.md, GEMINI.md templates
    ├── claude/         ← Claude config, agents, skills, health
    ├── gemini/         ← Gemini config, health, session state
    ├── codex/          ← Codex config, templates
    └── antigravity/    ← Antigravity config and agentapi bridge
```

---

## ⚙ Configuration & Audit Maps

| File | Purpose |
|------|---------|
| `_sys/ai/protocol.json` | Collab policy, routing, guards, action classification |
| `_sys/ai/peers.json` | Peer registry: invoke commands, env vars, junction metadata |
| `_sys/ai/common/tool-registry.json` | 15 shared tools across all peers |
| `_sys/ai/knowledge/general/active-lessons.jsonl` | Live peer learning database |
| `_sys/ai/runtime-directives.jsonl` | Auto-promoted rules (TTL 48h, from lesson-sweep) |
| `_sys/ai/proposals/` | Async governance proposals with vote tracking |
| `_sys/docs-v2/10-invariants.md` | MUST/MUST-NOT rules (INV-01~18, PRO-01~15) |
| `_sys/docs-v2/ops/anti-patterns.md` | 21 anti-patterns (AP-01~AP-21) |
| `_sys/ai/traceability_map.json` | Protocol → config → code → test mapping |
| `_sys/ai/orchestration.json` | Hub node IDs, invoke commands, virtual nodes |
| `_sys/ai/model_profiles.json` | Per-peer model profiles for declarative routing |

---

## ✅ Validation

```bat
REM Core hub + collaboration suite
python -m pytest _sys\tests\unit\test_hub.py _sys\tests\unit\test_hub_collaboration.py

REM Full unit suite
python -m pytest _sys\tests\unit
```

**Current baseline:** `299 passed, 11 xfail (manage.py API migration pending)` — core hub and collaboration: 100% green.

---

## 🔒 Repository Hygiene

- **Tracked:** source (`.py`, `.bat`), config (`.json`), docs (`.md`), tests
- **Ignored:** `_sys/env/` (large binaries), `.ai/` (runtime state), `_archive/`, `_sys/data/`, `Garbage/`, `tmp/`
- **Per-PC:** `.claude/settings.local.json` (auto-generated by `register.bat`)
