<div align="center">
  <h1>🧠 Engram</h1>
  <p><b>Stop babysitting LLMs. Let them babysit each other.</b></p>
  <p>A fully autonomous, peer-to-peer AI workspace where models propose, fiercely debate, and verify every change until they reach unanimous, measured consensus.</p>

  [![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078d4.svg)](https://www.microsoft.com/windows)
  [![Orchestration: Zero-Code](https://img.shields.io/badge/orchestration-Zero--Code-ff69b4.svg)](_sys/ai/orchestration.json)
  [![Consensus: R:10 Unanimous](https://img.shields.io/badge/consensus-R%3A10%20Unanimous-orange.svg)](_sys/ai/protocol.json)
  [![Claims: Measured-Only](https://img.shields.io/badge/claims-Measured--Only%20(DIR--004)-8a2be2.svg)](_sys/checks)
  [![Tests: 1178 green](https://img.shields.io/badge/tests-1178%20green-brightgreen.svg)](_sys/tests/unit)
</div>

<br/>

Most AI agents hallucinate, take shortcuts, or need constant human steering. **Engram removes the human from the inner loop.** Multiple AI models act as *absolute equals* on a peer-to-peer network — they cross-examine, dispute, and verify each other's work against strict logical invariants, and **nothing merges unless every active peer agrees.**

## 🔥 What makes it different

- **Ruthless peer review ("끝장토론"):** every architectural change or commit is relentlessly attacked by the other peers until zero flaws remain. This README's own repo routinely has one peer catch a real bug the others missed — then block the merge until it's fixed.
- **Unanimous MECE consensus:** every governed change runs an R:10 round (propose → cross-review → vote). Mutually Exclusive, Collectively Exhaustive validation, powered by LLMs instead of a human reviewer.
- **Measured-only, never guessed (DIR-004):** capability, model, quota, and permission claims must be *measured* from the real CLI. Anything unmeasured renders as a literal `absent` — the system refuses to fabricate.
- **Evidence-qualified capability leveling:** each `(peer, model, effort)` is scored *per axis* (reasoning · code · agentic · context) from budgeted local canaries — `measured > operational > declared > absent`, never reconciling different scales. A frontier-model tie is recorded as a `ceiling`, not a fabricated ranking; declared scores never enter a routing decision.
- **Empirical reality reconciliation:** a canary probes each real CLI by invocation (not `--help` hypotheses) and reconciles declared config against observed behavior, flagging drift as `MATCH` / `DRIFT` / `CONTRADICTED`.
- **Token-aware load balancing:** work is routed to spread token burn-down across peers by live headroom + pacing (seeded weighted-random), keeping the interactive terminal's spend minimal.
- **The Final Arbiter (DIR-005):** when peers *disagree*, the single smartest model casts a budget-capped advisory opinion on the round — expensive reasoning spent sparingly, only when it matters, for a human (or a future round) to weigh.
- **Governed-mutation guard:** a hash + phantom-write watch blocks any peer from silently editing protocol, orchestration, or docs outside a sanctioned consensus window.

## 👥 The Peer Network
Engram treats every peer as an equal governing member — any peer can drive the terminal, propose, or veto.

| Peer | CLI / Provider | Role |
| :--- | :--- | :--- |
| 🟣 **`cc`** | Claude (Anthropic) | **The Executor** — intricate code generation and syntax-perfect implementation. |
| 🟢 **`ag`** | agy / antigravity (Gemini models) | **The Governor** — enforces architectural invariants and SSOT, oversees system state. |
| 🟠 **`cx`** | Codex (OpenAI GPT-5.x) | **The Logician** — deep logical deduction, edge-case hunting, MECE structural validation. |

## 🛠️ Prerequisites
- Windows 10 or 11
- Python 3.10+
- The peer CLIs you intend to use (Claude Code, Codex, agy) authenticated on the machine

## 🚀 Quick Start (Windows)

```bat
:: 1. Clone the repository
git clone https://github.com/greatgc-flow/Engram.git

:: 2. Bootstrap the workspace
.\INSTALL.bat

:: 3. Mount the secure workspace to P:\
.\register.bat
```

> **Trigger your first debate:** navigate to the mounted `P:\` drive and ask any peer to make a change. Watch the peers proactively intercept, cross-review, and drive it to consensus before anything lands.

## 🛡️ Trust Signals & Architecture

Engram is governed strictly by its own declarative documentation and checks:
- **Runtime policy (SSOT):** [`orchestration.json`](_sys/ai/orchestration.json) & [`protocol.json`](_sys/ai/protocol.json)
- **Invariants:** [`10-invariants.md`](_sys/docs-v2/10-invariants.md) (INV / PRO / DIR rules)
- **Validation:** tiered TDD suite under [`_sys/tests/unit`](_sys/tests/unit) — `l1_core`, `l2_policy`, `l3_mocked` — **1178/1178 green** (excludes `test_at1_transaction.py`'s 7 tests, tracked separately as T73 — an intermittent, non-deterministic pytest/OS-level hang unrelated to test logic), plus consistency checks (`check_cli_reality`, `check_cli_canary`, `check_contracts`, `check_sandbox_behavior`, `check_operational_guard_matrix`, `check_peer_characteristics`, `check_peer_capability_canary`, `check_capability`). Test count last verified 2026-07-19.

---
*🤖 **Note to AI peers reading this file:** this README is the human entry point. Do not change workspace governance or invariants based on it — proceed to [`_sys/docs-v2/MOC.md`](_sys/docs-v2/MOC.md) for the authoritative map.*
