# Engram

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 688](https://img.shields.io/badge/tests-688%20passing-brightgreen.svg)](_sys/tests/unit)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows%2011-0078d4.svg)](https://microsoft.com/windows)
[![Protocol: v4.2](https://img.shields.io/badge/protocol-v4.2-purple.svg)](_sys/ai/protocol.json)
[![Peers: 4](https://img.shields.io/badge/AI%20peers-4%20equal-ff69b4.svg)](_sys/ai/peers.json)

> **A portable Windows dev environment where Claude, Gemini, Codex, and Antigravity collaborate as equal AI peers — every task, every decision, automatically cross-verified and self-healing.**

---

## Why Engram?

Most AI coding tools work in isolation. Engram is different: it runs **4 AI peers in parallel**, each checking the others' work. Every code change, every architectural decision, every bug fix goes through peer review — automatically, without you having to ask.

And it all runs from a single folder. USB drive, cloud share, or network path. Zero host pollution. Right-click any folder → instant AI-powered dev environment.

---

## ✨ Key Features

### 🤝 Always-On Multi-Peer Collaboration
Every task is automatically routed through active peer collaboration per `collab_rate`. Claude, Gemini, Codex, and Antigravity each contribute their strengths. No single AI is in charge — unanimous consent is required for high-risk changes.

```
You → [hub.py] → Claude + Gemini + Codex + Antigravity
                      ↕ cross-verify ↕
                  [consensus] → action
```

### 🔌 Portable by Design
Zero installation on the host. Mount from USB, cloud drive, or network share. All tools (Python 3.14, Node.js, Git, AI CLIs) are self-contained under a single root folder.

```bat
:: Mount anywhere, leave zero trace
REGISTER.bat   :: Maps P:\ via subst — removes on UNREGISTER.bat
```

### 🧠 ContextGate v1.0
CJK-aware token estimation protects your context budget automatically:
- **80% utilization** → warning logged
- **95% utilization** → automatic failover to a lower-cost peer
- **>95%** → request rejected before token overflow

### 🛡️ Protocol v4.2 — Governance at Every Level
11 collaboration levels from fully autonomous to unanimous consent:

| Rate | Mode | When It Applies | Consent Required |
|:----:|:-----|:----------------|:----------------|
| 0 | **Inactive** | Exploration, read-only | — |
| 1 | **Manual** | Explicit axis calls only | — |
| 2 | **Architecture** | Before arch/structure decisions | — |
| 3 | **Planning** | Multi-file task planning | — |
| 4 | **Checkpoint** | Start + completion review | — |
| 5 | **Code Partner** | Before every Edit/Write | — |
| 6 | **Error Partner** | All edits + on any error | — |
| 7 | **Direction** | All edits + trade-off analysis | Major direction shifts |
| 8 | **Milestone** | Every sub-task review | Step completion |
| 9 | **Pairing** | Every 5 explores, verify direction | Direction changes |
| 10 | **Sync** | Full Phase: Plan/Exec/Review/Report | **Mandatory every step** |

### 🏥 Self-Healing Error Taxonomy (T0–T4)
5-tier error classification with automatic remediation:

| Tier | Severity | Action |
|:----:|:---------|:-------|
| T0 | Info | Log only |
| T1 | Silent | Record, continue |
| T2 | Display | Show to user |
| T3 | Warning | Alert + suggest fix |
| T4 | **Fatal** | Display + `sys.exit(4)` |

### 📋 MECE Doc Validation (CHK-01~07)
7 automated checks keep code, config, and documentation in perfect sync:

| Check | What it validates |
|:-----:|:-----------------|
| CHK-01 | All paths in docs actually exist |
| CHK-02 | No Korean (CJK) in internal docs (INV-19) |
| CHK-03 | Python file changes covered in docs |
| CHK-04 | All `[[anchor]]` links resolve |
| CHK-05 | `collab_rate` values match `protocol.json` |
| CHK-06 | No proposals older than 14 days pending |
| CHK-07 | All docs listed in `00-MANIFEST.md` |

### 🧪 688 Tests, All Passing
Comprehensive TDD coverage including parallel IPC stress tests, adapter protocol conformance, context gate edge cases, and error taxonomy integration.

---

## 🏗️ Architecture

```
P:\  (portable root, mapped via subst)
│
├── _sys/
│   ├── core/
│   │   ├── hub.py           ← IPC orchestrator (all peer routing)
│   │   ├── hub_peer.py      ← PeerAdapter: Claude/Gemini/Codex/Virtual
│   │   ├── hub_context.py   ← ContextGate v1.0
│   │   ├── hub_health.py    ← HealthReader + PeerHealthState
│   │   ├── hub_logging.py   ← 7-type JSONL logger
│   │   └── hub_error.py     ← T0-T4 error taxonomy display
│   │
│   ├── ai/
│   │   ├── protocol.json    ← collab_rate, consensus, routing (SSOT)
│   │   ├── orchestration.json ← 7 hub nodes + adapter_class
│   │   ├── model_profiles.json ← context/output limits per model
│   │   └── error-taxonomy.json ← T0-T4 error definitions
│   │
│   ├── checks/
│   │   ├── check_docs_mece.py ← CHK-01~07 validation
│   │   └── self_care.py       ← autonomous maintenance
│   │
│   └── tests/unit/          ← 688 tests, all pass
│
├── workspace/               ← your projects go here
├── CLAUDE.md                ← Claude's global instructions
├── GEMINI.md                ← Gemini's global instructions
└── README.md                ← you are here
```

---

## ⚡ Quick Start

### Prerequisites
- Windows 10/11
- Git
- Node.js (for AI CLIs)

### 1. Clone
```bat
git clone https://github.com/greatgc-flow/Porta-Flow.git engram
cd engram
```

### 2. Install AI Peers
```bat
npm install -g @anthropic-ai/claude-cli
npm install -g @google/gemini-cli
```

### 3. Mount the Environment
```bat
REGISTER.bat
```
This maps `P:\` via Windows `subst`. All tools become available at `P:\_sys\`.

### 4. Run Your First Collaboration
```bat
python P:\_sys\core\hub.py peer-status
```
```
┌──────────────────────────────────────────────────────────────┐
│  PEER STATUS (live-refreshed)                                │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│ Peer     │ Gate     │ Health   │ Version  │ Details        │
├──────────┼──────────┼──────────┼──────────┼────────────────┤
│ claude   │ OPEN     │ GREEN    │ 2.1.x    │ 0.0MB          │
│ gemini   │ OPEN     │ GREEN    │ 0.47.x   │ 0.0MB          │
│ codex    │ open     │ GREEN    │ codex-cl │ 0.0MB          │
│ antigrav │ open     │ GREEN    │ 1.0.x    │ 0.0MB          │
└──────────┴──────────┴──────────┴──────────┴────────────────┘
```

---

## 📖 Usage Examples

### Ask a single peer
```bat
python P:\_sys\core\hub.py ask --to gc --query "Review this architecture diagram"
```

### Broadcast to all peers
```bat
python P:\_sys\core\hub.py ask-all --query "Should we use JSONL or SQLite for the log store?"
```
Each peer responds independently, Claude synthesizes.

### Run MECE doc validation
```bat
python P:\_sys\checks\check_docs_mece.py --checks CHK-01,CHK-02,CHK-03
```
```
[CHK-01] ✓ All 47 doc paths exist
[CHK-02] ✓ No INV-19 violations found
[CHK-03] ✓ All Python changes covered in docs
```

### Change collaboration intensity
```bat
:: Check current level
python P:\_sys\core\hub.py status

:: Bump to full sync mode (unanimous consent on everything)
P:\_sys\cli\set-collab-rate.bat 10
```

### Run the full test suite
```bat
cd P:\_sys\tests\unit
python -m pytest -q
```
```
688 passed in 32s ✓
```

---

## 🔧 Configuration

All configuration lives in `_sys/ai/` as JSON files (single source of truth):

| File | Purpose |
|:-----|:--------|
| `protocol.json` | `collab_rate`, consensus voters, routing |
| `orchestration.json` | Hub nodes, adapter classes |
| `model_profiles.json` | Context/output limits per model |
| `error-taxonomy.json` | T0-T4 error definitions |
| `logging-config.json` | 7-type JSONL log settings |
| `governance_params.json` | Thresholds (ContextGate, CHK checks) |

---

## 🤝 Contributing

1. Fork and create a branch
2. Write tests first (TDD)
3. All 688 tests must pass: `python -m pytest _sys/tests/unit/ -q`
4. MECE checks must pass: `python _sys/checks/check_docs_mece.py`
5. Open a PR — peer review required (at least one AI peer cross-check encouraged)

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

Built for portability. Engineered for autonomy. Designed for collaboration.

---

*Engram — because good ideas need a place to live.*
