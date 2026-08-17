# Multi-AI Collaboration & Quota Architecture Accord (2026-08-15)

> **Status:** UNANIMOUSLY RATIFIED (CC + CX + AG 3-Way Dialectical Consensus)  
> **Source Paper:** Deep Analysis of Multi-AI Collaboration and Heterogeneous LLMs Integration Projects  
> **Target Subsystems:** `peerhub/`, `_sys/ai/orchestration.json`, `protocol.json`, `_sys/docs-v2/`

---

## 1. Executive Summary & Root Cause Resolution

Following an empirical investigation and live 3-way IPC debate across all active peers (**CX DeepThink / GPT-5.6 Sol**, **AG DeepThink / Gemini 3.1 Pro**, and **CC Effort / Claude Sonnet 5**), this accord establishes the unified architectural standard for multi-AI collaboration, heterogeneous governance, and quota protection within the PeerHub ecosystem.

### Incident Root Causes Addressed
1. **CC Quota Depletion:** Pinned `deepthink` (Opus-5/High) on routine IPC asks -> downgraded to `effort` (Sonnet-5).
2. **Context Bloat:** Eager injection of bulk tool outputs -> partitioned into 3-tier context and `EvidenceArtifact` references.
3. **Forced Over-compromising:** Excessive debate turns under `INV-31` -> Free-MAD protocol with 1-round cross-examination and scoped DIR-005 arbitration.
4. **Planning Signature Drift:** FDD planning failures (SWE-Dev 55.8%) -> machine-enforced `InterfaceManifest` integrated into DIR-003.

---

## 2. 3-Peer Dialectical Synthesis

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [CX: Thesis]      Formal Epistemic vs Authorization Split + 5 Topologies │
│ [AG: Antithesis]  Pragmatic State Graph + Windows Reality + Prompt Cache │
│ [CC: Synthesis]   Deterministic Rules (No Loophole) + DIR Alignment      │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
                                   ▼
          ★ UNANIMOUS ACCORD: 15 Core Principles & Standards ★
```

---

## 3. The 15 Core Ratified Clauses

### Section I: Epistemic Selection & Governance Topology
1. **Epistemic vs. Authorization Decoupling:** Epistemic evaluation ("What is technically true/optimal?") is formally separated from state mutation authorization ("Who is allowed to write code or modify files?").
2. **Deterministic Governance Routing (`TaskDescriptor`):** Workload topology is deterministically selected based on an auditable, pre-ratified rule set:
   - `SINGLE_FAST`: Deterministic coding, bugfixes, unit tests, and tasks covered by ratified plans (bypasses multi-agent ceremony; saves 8–12x tokens).
   - `INDEPENDENT_ARBITRATED`: Design disputes, diagnosis, and heterogeneous model reasoning.
   - `FEDERAL`: Multi-stage development with specialist handoffs.
   - `P2P_SHARDED`: Broad data processing and research.
   - `UNANIMOUS_AUTHORITY`: High-blast-radius policy, protocol, and security invariant modifications.
3. **Revisioned State Graph over Rigid Hash Locks:** Iterative coding uses a LangGraph-inspired state graph with cyclic transitions; cryptographic hashes provide provenance and concurrency control (reusing existing `R:10` hash conventions `r-ff91`/`r-eb81`), preserving pair-programming agility.
4. **Interface Drift Defense (`InterfaceManifest`):** Hard scope, effect, and public symbol changes cannot occur silently during execution. Merged into `DIR-003` (`test_contracts.py` update obligations).

### Section II: Multi-Agent Debate & Epistemic Alignment (Free-MAD)
5. **Bounded Free-MAD Protocol:** Multi-agent review executes via:
   - `Map (1-Round Independent Opinion)` -> `Cross-Exam (1-Round Bounded Query)` -> `Reduce (DIR-005 Arbiter)`
   - No endless debate loops or forced compromise.
6. **Anti-Dilution Invariant:** No participant is coerced into compromising a sound technical or factual conclusion to reach artificial consensus.
7. **Scoped Arbitration:** Free-MAD arbitration is strictly bound to the existing `DIR-005` framework (budget-capped at 5 calls/5h, narrow trigger conditions).

### Section III: Execution Environment & Context Economics
8. **Windows-Native Practical Confinement:** The portable baseline relies on host-brokered Read-Only operations, CLI permission profiles, and post-condition `SEC-01` Git-diff guards. Heavy container dependencies are optional, not mandatory.
9. **Empirically Verified Permissions:** CLI permission claims are accepted only after passing live canary probes (`DIR-004`).
10. **Three-Tier Context Partitioning:**
    - **`AuthorityCapsule`:** Immutable standing rules (`user-directives.md`), canonically serialized as a prompt-cacheable prefix.
    - **`TaskCapsule`:** Ephemeral task-specific plan, blockers, and acceptance criteria.
    - **`EvidenceArtifact`:** Bulk tool and MCP results kept out-of-prompt; models receive typed handles and request bounded slices.
11. **Prompt Mode (`-p`) Output Threshold:** In stateless `-p` mode, tool outputs exceeding token threshold N are written to disk and relayed via file reference + summary to prevent repetitive context bloat.
12. **Telemetry & Verification (`PromptReceipt`):** Prompt cache hit rates, actual token consumption, and context duplication are measured via machine receipts, never assumed.
13. **MCP as Transport, Not Token Silo:** MCP passes artifact references; raw bulk JSON is never eagerly inlined into the model prompt.
14. **Machine Evidence Supremacy:** Machine-verifiable artifacts (failing tests, broken invariants, syntax errors) strictly outrank qualitative model rhetoric.
15. **Immutable Authority Kernel:** The existing PeerHub authority kernel (`r-aec7`) remains the inviolable enforcement boundary.

---

## 4. Prioritized Execution Backlog

| Tier | Priority | Action Item | Target Subsystem | Status |
|:---:|:---:|:---|:---|:---:|
| **P0** | Immediate | Change CC IPC default profile to `effort` (`claude-sonnet-5`) | `_sys/ai/orchestration.json` | **Applied** |
| **P0** | Immediate | Enable `SINGLE_FAST` fast-path for ratified single-file/unit tasks | `_sys/ai/protocol.json` | **Active** |
| **P0** | Immediate | Add `PromptReceipt` telemetry & cache monitoring | `_sys/ai/common/` | Planned |
| **P1** | Short-term | Implement 1-Round Bounded Free-MAD protocol in Hub | `_sys/core/hub.py` | Backlog |
| **P1** | Short-term | Merge `InterfaceManifest` verification into `DIR-003` gates | `_sys/checks/` | Backlog |
| **P2** | Mid-term | Implement 3-Tier Context Partitioning (`EvidenceArtifact`) | `peerhub/` | Backlog |
| **P2** | Mid-term | Deploy Windows-native Brokered Read-Only Reducers | `peerhub/adapters/` | Backlog |

---

## 5. Peer Sign-Off & Ratification Records

* **CX DeepThink (`gpt-5.6-sol`, xhigh):** `RATIFIED` (Round 3 Synthesis Accord)
* **AG DeepThink (`gemini-3.1-pro-high`):** `RATIFIED` (Round 2 Dialectical Alignment)
* **CC Effort (`claude-sonnet-5`, high):** `RATIFIED` (Review with 5 DIR-alignment conditions incorporated)
