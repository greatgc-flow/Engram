<div align="center">
  <h1>🧠 Engram</h1>
  <p><b>Stop babysitting LLMs. Let them babysit each other.</b></p>
  <p>A fully autonomous, peer-to-peer AI workspace where models propose, fiercely debate, and verify every change until they reach unanimous, measured consensus.</p>

  [![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078d4.svg)](https://www.microsoft.com/windows)
  [![Orchestration: Zero-Code](https://img.shields.io/badge/orchestration-Zero--Code-ff69b4.svg)](_sys/ai/orchestration.json)
  [![Consensus: R:10 Unanimous](https://img.shields.io/badge/consensus-R%3A10%20Unanimous-orange.svg)](_sys/ai/protocol.json)
  [![Claims: Measured-Only](https://img.shields.io/badge/claims-Measured--Only%20(DIR--004)-8a2be2.svg)](_sys/checks)
  [![Coordination: PeerHub v0.1.0](https://img.shields.io/badge/coordination-PeerHub%20v0.1.0-blue.svg)](https://github.com/greatgc-flow/peerhub)
  [![Tests: 1695+ green](https://img.shields.io/badge/tests-1695%2B%20green-brightgreen.svg)](_sys/tests/unit)
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

## 🕹️ PeerHub Coordination Engine (`v0.1.0`)

Engram integrates the standalone [`peerhub`](https://github.com/greatgc-flow/peerhub) coordination engine, delivering transactional inter-peer communication and real-time observability:

- **`diag`**: Real-time terminal diagnostic telemetry displaying multi-peer quota consumption, exhaustion pacing, headroom matrices, and active failover routing targets.
- **`hub ask <peer> <prompt>`**: Transactional single-peer execution pipeline with isolated execution leases and strict capability-tier enforcement.
- **`hub broadcast --peers <peers> <prompt>`**: Multi-peer bounded consensus coordinator for fan-out deliberation and cross-examination.
- **`hub status`**: SQLite workspace ledger status and health circuit inspection.

## Current verified CLI profiles (2026-08-18)

The active peer profiles were verified by minimal live invocations using each CLI's configured model and reasoning effort. The configuration authority remains [`orchestration.json`](_sys/ai/orchestration.json); detailed runbooks are in [`docs-v2`](_sys/docs-v2/MOC.md).

| Peer | Verified profile mapping |
|---|---|
| `ag` | Gemini 3.7 Flash (`low` / `high`), Gemini 3.1 Pro (`high`), Claude Opus 4.6 Thinking (embedded effort), GPT-OSS 120B (`medium`) |
| `cc` | Claude Haiku 4.5 (`low`), Sonnet 5 (`high`), Opus 5 (`high`), Fable 5 (`high`) |
| `cx` | GPT-5.6 Luna (`low`), Terra (`high`), Sol (`xhigh`) |

## 🛠️ Prerequisites
- Windows 10 or 11
- Python 3.10+
- The peer CLIs you intend to use (Claude Code, Codex, agy) authenticated on the machine

## 🚀 Quick Start (Windows)

```bat
:: 1. Clone the repository
git clone https://github.com/greatgc-flow/Engram.git

:: 2. Bootstrap the workspace (Python, Node, PeerHub, runtimes)
.\INSTALL.bat

:: 3. Mount the secure workspace to P:\
.\register.bat

:: 4. Check real-time peer telemetry and quota
.\_sys\cli\diag.bat

:: 5. (Optional) Clean up temporary workspace files
.\TIDY.bat
```

> **Trigger your first debate:** navigate to the mounted `P:\` drive and ask any peer to make a change. Watch the peers proactively intercept, cross-review, and drive it to consensus before anything lands.

> **Workspace Maintenance:** `.\TIDY.bat` provides on-demand cleanup of temporary workspace files (shows a dry-run preview and prompts for confirmation; strictly manual/on-demand by design, with no scheduled background automation).

## 🛡️ Trust Signals & Architecture

Engram is governed strictly by its own declarative documentation and checks:
- **Runtime policy (SSOT):** [`orchestration.json`](_sys/ai/orchestration.json) & [`protocol.json`](_sys/ai/protocol.json)
- **Invariants:** [`10-invariants.md`](_sys/docs-v2/10-invariants.md) (INV / PRO / DIR rules)
- **Validation:** tiered TDD suite under [`_sys/tests/unit`](_sys/tests/unit) — `l1_core`, `l2_policy`, `l3_mocked` — **1695/1695 green**, plus consistency/pre-commit checks (`check_cli_reality`, `check_cli_canary`, `check_contracts`, `check_sandbox_behavior`, `check_operational_guard_matrix`, `check_peer_characteristics`, `check_peer_capability_canary`, `check_capability`, `check_policy_ledger`, `check_docs_mece`, `check_policy_constants`, `check_unreferenced_functions`, `check_cli_dispatch_parity`).

---
*🤖 **Note to AI peers reading this file:** this README is the human entry point. Do not change workspace governance or invariants based on it — proceed to [`_sys/docs-v2/MOC.md`](_sys/docs-v2/MOC.md) for the authoritative map.*
