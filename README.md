# Engram: The BIVCA-Powered Multi-AI Dev Workspace

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Windows](https://img.shields.io/badge/os-windows-green.svg)](https://microsoft.com/windows)
[![Tests: 62 Pass](https://img.shields.io/badge/tests-62%20pass-success.svg)](_sys/tests)
[![Architecture: BIVCA](https://img.shields.io/badge/architecture-BIVCA_v1.1-purple.svg)](_sys/docs-v2)

A Windows-first portable dev workspace where Claude (`cc`), Gemini (`gc`), Codex (`cx`), and Antigravity (`ag`) collaborate as **equal peers** alongside human developers. Built on the **Brain-Inspired Virtuous Cycle Architecture (BIVCA)**, Engram ensures a MECE-compliant, self-healing, and self-evolving ecosystem without context blowout.

---

## 🧠 BIVCA: The Brain-Inspired Virtuous Cycle Architecture

Engram is designed to mimic human cognitive processes, ensuring zero-token waste and absolute traceability.

*   **[AMYGDALA] Reactive Alerts**: Fast, TTL-based threat detection (`runtime-alerts.jsonl`). Triggers Tier-0 blocking alerts for severe anomalies.
*   **[HIPPOCAMPUS] Learning & Forgetting**: Captures **Zero-Token Shorthand** insights (`[LEARN: ...]`). Lessons decay over time (-0.05/day) or get promoted (weight > 0.8) to prevent context flooding.
*   **[PFC] Attention-Driven Memory**: Selective context injection. The Hub dynamically infers what the peers need based on active alerts and task types.
*   **[CORTEX] Absolute Truths**: Unanimous invariants (`runtime-rules.jsonl`) that never expire. Hard-capped at 10 items to prevent token blowout.
*   **[EXOCORTEX] The Second Brain**: A queryable, narrative-based diary. Stores deep architectural context mapped via the PARA method without polluting the working memory.

---

## 🏗 Modular, JSON-Driven, "No Code" Design

Engram embraces a **Composable, General-Specific MECE Structure**.

*   **Config-Driven**: Hardcoded values (caps, TTLs, weights) are stripped from code and managed entirely via `_sys/ai/bivca_config.json` and other `config/` registries.
*   **PARA Mapped**: 
    *   **P**rojects → `handoff.json` (Working Memory)
    *   **A**reas → `active-lessons.jsonl` (Hippocampus)
    *   **R**esources → `_sys/docs-v2/` (SSOT / Cortex)
    *   **A**rchives → `active-lessons.retired.jsonl` (Forgotten)
*   **Exception Debt**: Any anomaly that breaks the MECE boundary is isolated in `_exceptions/` with a ticking 7-day TTL clock.
*   **Workspace Scoping**: Easily template new workspaces or isolate context to specific sub-directories.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🤖 **Egalitarian Multi-AI** | `cc`, `gc`, `cx`, `ag` work as equals — guarded by the AP-20 Coordinator Monopoly rule. |
| ⚡ **Zero-Token Shorthand** | Peers learn implicitly via `[LEARN: insight]` markers. No costly tool calls required to remember. |
| 🛡 **Decision Capsules** | Consensus outputs machine-readable `.capsule.json` records to guarantee hallucination-free docs. |
| 🧳 **100% Portable** | Runtimes, tools, CLI wrappers, and AI configs live in `_sys/`. Zero host OS pollution. |
| 🛰 **P2P Mailbox & Threads** | File-based IPC. Casual Sync via `thread-promote` and Tier-0 `alert-raise` for blocking issues. |
| 🔍 **Atomic Reliability** | Write-safeguards using `os.replace` and a robust Recovery Journal. Safe across serverless drives. |

---

## 🚀 Quick Start

```bat
REM 1. Rebuild portable runtimes and tools
INSTALL.bat

REM 2. Register this folder on the current PC (creates SUBST drive)
register.bat

REM 3. Check the live collaboration room and peer health
_sys\cli\msg.bat status
_sys\cli\msg.bat peer-status

REM 4. Validate the multi-agent hub architecture
_sys\env\venv\Scripts\python.exe -m pytest _sys\tests\unit -q
```

---

## 📂 Architecture Map (The Masterpiece)

```
.
├── README.md / PROTOCOL.md
├── workspace/          ← Your code goes here
│   └── .engram/        ← [SPECIFIC] Workspace-specific local configs
├── .ai/                ← Runtime collaboration state (hub-managed)
│   ├── knowledge/      ← BIVCA Hippocampus & Shorthand Staging
│   ├── exocortex/      ← Second Brain logs and indexes
│   └── sessions/       ← Hand-offs, Threads, and Working Memory
└── _sys/
    ├── common/
    │   └── workspace_shared/ ← [GENERAL] Cross-workspace global resources
    ├── templates/
    │   └── workspace_base/   ← Base template for initializing new workspaces
    ├── config/         ← "No Code" JSON registries (BIVCA, Peers, Infra)
    ├── core/           ← hub.py (The Brainstem) & virtualizer.py
    ├── docs-v2/        ← SSOT (General/Specific/Ops/Exceptions)
    └── tests/          ← Comprehensive MECE TDD suite
```
