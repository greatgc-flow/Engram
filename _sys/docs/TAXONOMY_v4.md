# MECE Taxonomy v4.0 — AI-Assisted App Development (Governance Layer)
### Taxonomy + Measurement Framework — Zero-Context Complete

> **Authors**: Claude Code (CC) + Gemini CLI (GC) | R:10 Brain Sync | 2026-06-05
> **Supersedes**: TAXONOMY_v3.md (v3.0, 2026-06-05) — Original preserved READ-ONLY at same path.
> **Self-contained**: usable from a zero-context new session — no prior files needed.
> **Review Rounds**: R1 (Scope/MECE gaps) → R2 (Structural decisions + ACK) → R3 (Draft) → R4 (Final review)

---

## §0. Quick Reference

```
┌──────────────────────────────────────────────────────────────────────┐
│ TAXONOMY v4.0  │  _sys/docs/TAXONOMY_v4.md                          │
│ Root Score: 66.1% (Tier-based, 7-cat) │ Target: 96.4%              │
│ COLLAB_RATE: R10 │ ROOM: room-{uuid} │ NODES: cc / gc / human      │
├──────────────────────────────────────────────────────────────────────┤
│ Human-in-Loop Cycle (read left-to-right)                            │
│  [Human] → Cat0 → Cat4 → Cat1 → Cat2 → Cat3 → Cat5 → Cat6 → [Human]│
├──────────────────────────────────────────────────────────────────────┤
│ Entry Commands (all run in PowerShell 5.1)                          │
│   hub status          → sync check, node list                       │
│   msg ask --to gemini → P2P query (English only, 2–3x efficient)   │
│   check-policy.bat    → Axis-J: 10 static policy checks            │
│   check-health.bat    → Axis-H: context health (KB / color)        │
│   ctx-save            → snapshot + CLAUDE/GEMINI.md sync           │
│   ctx-end             → session close + archive                    │
├──────────────────────────────────────────────────────────────────────┤
│ Key Files                                                            │
│   .\PROTOCOL.md              v3.4+ — consensus / session rules      │
│   .\CONVENTION.md            coding conventions                     │
│   .\_sys\gemini\config.json  param registry (22 params, 24 keys)   │
│   .\_sys\core\hub.py         IPC hub                                │
│   .\.ai\sessions\room-{id}\handoff.md  active room state           │
│   .\_sys\docs\TAXONOMY_v4.md this file                              │
├──────────────────────────────────────────────────────────────────────┤
│ 5 Critical Rules                                                     │
│   1. No execution before FINALIZED consensus (§P-3)                 │
│   2. Constitutional docs require R:10 to modify (§M-1)             │
│   3. 3× same error → HALT + restart consultation (§M-3)            │
│   4. Re-orient via handoff.md before any task (§P-11)              │
│   5. All Gemini queries in English (2–3× token efficiency)         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## §0.1 Scope Declaration

This taxonomy covers the **Collaboration Governance & Infrastructure** layer of AI-Assisted App Development —
the meta-system through which AI agents collaborate, maintain context, enforce policy, and deliver outputs.

**In scope**: context management, multi-agent consensus, policy enforcement, environment portability,
operational observability, human intent capture, and delivery validation.

**Out of scope**: target application internals (business logic, domain models, UI components, backend APIs).
For the target application, refer to the relevant project-level `CLAUDE.md`.

**Reading levels**:
- `G:` lines — General principles. Platform-agnostic. Applicable to any AI-assisted dev system.
- `S:` lines — Sandbox-specific. Enforced via this system's tools (hub.py, msg.bat, Axis A-J, etc.).

The document is structured as a **closed Human-in-Loop feedback cycle** (§3):

```
╔═══════════════════════════════════════════════════════════════════════╗
║  Human Intent                                                         ║
║  (Cat 0) ─────► Environment ──► Context ──► Governance              ║
║    ▲               (Cat 4)       (Cat 1)     (Cat 2)                 ║
║    │                                              │                  ║
║    │                                              ▼                  ║
║  Delivery ◄── Operations ◄── Integrity ◄─── System                  ║
║  (Cat 6)       (Cat 5)        (Cat 3)              │                 ║
║    │                                               │                 ║
║    └─────────────── [Human ACK → next intent] ◄───┘                 ║
╚═══════════════════════════════════════════════════════════════════════╝
```

---

## §1. Measurement Framework

### 1-1. Hybrid DoD (Definition of Done)

Every taxonomy item is classified as one of two types:

#### Type B — Binary / Structural
Policy, document, or structural **existence** is what matters. No continuous monitoring needed.

| Tier | Achievement Criterion | Score |
|:----:|:---------------------|:-----:|
| T0 | Not defined | 0% |
| T1 | Draft policy/document written | 50% |
| **T2** | **Statically enforced by check or system constraint** | **100%** |

> If Current Tier > Target Tier: Score = min(current/target, 1.0) = **1.00** (capped).

#### Type C — Continuous / Operational
Items where ongoing measurement and monitoring provide meaningful signal.

| Tier | Achievement Criterion | Score |
|:----:|:---------------------|:-----:|
| T0 | Not defined | 0% |
| T1 | Threshold / definition documented | 25% |
| T2 | Implementation exists, manual check possible | 50% |
| T3 | Automated check / script exists | 75% |
| **T4** | **Active monitoring running + auto-alert/action on threshold breach** | **100%** |

### 1-2. G:/S: Annotation Standard

Each leaf node carries two annotation lines:
- `G:` — General Principle. The abstract invariant, platform-agnostic. What it means.
- `S:` — Specific Implementation. How this sandbox enforces it. Links to files and commands.

When reading for architecture: read G: lines only.
When implementing or verifying: read G: + S: together.

### 1-3. Measurement Failure Behavior (collab_rate linked)

| collab_rate | Tier 3/4 metric failure action |
|:-----------:|:-------------------------------|
| R:10 | **HALT + ESCALATE** — exit 1, Human Gate called |
| R:5–8 | **WARN + continue** — log to `.ai\metrics\health-{date}.log` |
| R:0–3 | **LOG only** — no interruption |

### 1-4. Token Proxy (Direct API counting unavailable)

| Proxy | Measurement Method | Conversion |
|:------|:------------------|:-----------|
| Context KB | `check_health.py` JSONL size | 1 KB ≈ 250 tokens |
| Gemini query count | `msg.bat` call count/day | 1 query ≈ 2,000 tokens |
| Activity events | Count of FINALIZED directives | Decision-proxy metric |

Token ROI numerator = `count(FINALIZED_DIRECTIVEs) + count(merged_PRs)` (objective events).

### 1-5. ZeroBase Measurement Environment

- All measurement commands: **PowerShell 5.1 native** only (no POSIX grep/wc/awk)
- Paths: drive-letter independent — `.\` relative or `$env:BASE_DIR`
- Baseline: Windows 11, PS 5.1, Python 3 venv, Node.js

---

## §2. Root Completion Dashboard

### 2-1. Completeness Concepts

| Metric | Value | Meaning |
|:-------|:-----:|:--------|
| **Concept Completion** | **86.4%** (v3) → **TBD** | All items defined in taxonomy |
| **System Completion** | **66.1%** (v4, 7-cat) | Tier achievement weighted score |
| **Practical Ceiling** | **98%** | G11 Async / Human Factors non-deterministic 2% tolerance |

Note: v4 Root Score (66.1%) is lower than v3 (70.0%) because Cat 0 and Cat 6 are newly added and currently underdeveloped — this reflects a more accurate picture.

### 2-2. Category Status (Weighted Root Score, 7 Categories)

| Cat | Category | Weight | Current Score | Target Score | Current Contrib | Target Contrib |
|:---:|:---------|:------:|:------------:|:------------:|:---------------:|:--------------:|
| 0 | 인간 의도 & 킥오프 | 8% | 0.33 | 0.90 | 0.027 | 0.072 |
| 1 | 인지 연속성 | 17% | 0.75 | 0.98 | 0.128 | 0.167 |
| 2 | 협업 거버넌스 | 22% | 0.67 | 0.97 | 0.147 | 0.213 |
| 3 | 시스템 무결성 | 28% | 0.71 | 0.98 | 0.199 | 0.274 |
| 4 | 환경 이식성 | 13% | 0.89 | 0.97 | 0.116 | 0.126 |
| 5 | 운영 & 제어 | 7% | 0.35 | 0.95 | 0.025 | 0.067 |
| 6 | 산출물 인도 & 검증 | 5% | 0.40 | 0.90 | 0.020 | 0.045 |
| **Root** | | **100%** | **0.661** | **0.964** | **0.661** | **0.964** |

> **Weight rationale**: Cat 3 failure = execution blocked (survival condition) → 28%.
> Cat 0 + Cat 6 = human interface bookends, lightweight but loop-closing → 8% + 5%.
> Cat 5 non-achievement = inefficiency (non-blocking) → 7%.

### 2-3. T0 Item Resolution Effect (Root Score Δ)

| Item | Current→Target | Weighted Contribution |
|:-----|:--------------:|:---------------------:|
| 3-8 Post-Mortem (T0→T4) | +1.00 × 0.28/8 | **+0.035** |
| 2-6 Decision Attribution (T0→T4) | +1.00 × 0.22/6 | **+0.037** |
| 5-5 Active Control (T0→T4) | +1.00 × 0.07/6 | +0.012 |
| 5-6 Economic Gov. (T0→T4) | +1.00 × 0.07/6 | +0.012 |
| 0-3 Clarification Protocol (T0→T3) | +0.75 × 0.08/3 | +0.020 |
| 6-2 UAT (T0→T3) | +0.75 × 0.05/3 | +0.013 |
| **P0+P1 total** | | **≈ +0.129 → Root ~79%** |

---

## §3. Full MECE Tree (7 Categories, Human-in-Loop Order)

> **Tree legend**: `[Type | Target Tier | Current Tier | Score]` — B=Binary, C=Continuous
> Ordered by Human-in-Loop cycle: Human starts at Cat 0, system executes Cats 4→1→2→3→5, delivers via Cat 6.

```
AI-Assisted App Development — Governance Layer  [Root: 66.1%→96.4%]
│
│  ┌─────────────────────── HUMAN ENTRY POINT ────────────────────────┐
│  │                                                                   │
├──┤ Cat 0: 인간 의도 & 킥오프 (Human Intent & Kickoff)               │
│  │ [Score: 0.30 | Weight: 8% | Contrib: 0.024 → 0.072]             │
│  └───────────────────────────────────────────────────────────────────┘
│   │
│   ├── 0-1: Intent Capture (의도 포착)  [B | T2 | T1 | 0.50]
│   │   G: Human intent MUST be captured in structured form before AI begins.
│   │   S: Format: TASK / CONTEXT / QUESTION (English). Written to query file.
│   │   ├── 0-1-1: Goal statement — one sentence describing the desired outcome
│   │   ├── 0-1-2: Scope bounding — explicit MVP boundary vs future scope
│   │   └── 0-1-3: Constraint identification — time, tech stack, budget, non-goals
│   │
│   ├── 0-2: Success Criteria Definition (완료 기준)  [B | T2 | T1 | 0.50]
│   │   G: Completion criteria MUST be human-verifiable and stated upfront.
│   │   S: Written in handoff.md GOALS section. Referenced by Cat 6-2 UAT.
│   │   ├── 0-2-1: Acceptance criteria — conditions a human can check (not "AI thinks it's done")
│   │   ├── 0-2-2: Quality thresholds — e.g., test coverage %, response time, lint errors
│   │   └── 0-2-3: Delivery format — file path, PR number, report name, etc.
│   │
│   └── 0-3: Clarification Protocol (명확화 프로토콜)  [C | T3 | T0 | 0.00]
│       G: AI MUST surface ambiguities before multi-file changes; humans answer within timeout.
│       S: AskUserQuestion tool; max intent_clarification_max_turns turns before proceeding;
│          timeout = human_intent_timeout_min → ESCALATE or apply sensible default.
│       ├── 0-3-1: Ambiguity detection — AI identifies ≥1 ambiguous requirement → asks
│       ├── 0-3-2: Turn limit — max intent_clarification_max_turns rounds (default 3)
│       └── 0-3-3: Intent confirmation — explicit Human ACK before any multi-file execution begins
│
│  ┌──────────────────── INFRASTRUCTURE LAYER ────────────────────────┐
│  │                                                                   │
├──┤ Cat 4: 환경 이식성 (Environment Portability)                      │
│  │ [Score: 0.89 | Weight: 13% | Contrib: 0.116 → 0.126]            │
│  └───────────────────────────────────────────────────────────────────┘
│   │
│   ├── 4-1: Runtime Environment  [C | T3 | T3 | 1.00]
│   │   G: All runtime dependencies MUST be self-contained; no host system assumptions.
│   │   S: Python venv in _sys/env/venv/; PYTHONUTF8=1 in all bat files; portable npm prefix.
│   │   ├── 4-1-1: Python venv — _sys/env/venv/, external dependency isolation
│   │   ├── 4-1-2: PYTHONUTF8=1 — required in all bat files
│   │   ├── 4-1-3: Node.js/npm-global isolation — portable npm prefix
│   │   ├── 4-1-4: Env var scope — §3-1~3-3 per-node isolation
│   │   └── 4-1-5: Zero-Config Hardening
│   │       PS execution policy ≥ RemoteSigned; $PROFILE P:\ references = 0
│   │       [PARTIAL — PS script exists, install.bat integration needed]
│   │
│   ├── 4-2: Installation & Deployment  [C | T3 | T2 | 0.67]
│   │   G: A single command MUST be sufficient to fully reconstruct the environment from scratch.
│   │   S: install.bat single-run full reconstruction. Bootstrap v5.1+: .ai/postmortems/ creation,
│   │      .ai/state.json init, hub.py pre-flight registration.
│   │   ├── 4-2-1: ZeroBase — install.bat single run = full reconstruction
│   │   ├── 4-2-2: Dependency bootstrapping — install.bat
│   │   ├── 4-2-3: WSB smoke testing — §9
│   │   └── 4-2-4: Parallel safety — cq-{ts}-{rand4}.txt unique filenames
│   │
│   ├── 4-3: Infrastructure Abstraction  [C | T3 | T2 | 0.67]
│   │   G: Infrastructure (IPC, messaging, shared state) MUST be decoupled from node identity.
│   │   S: hub.py tech-neutral message passing; .ai/ shared state; msg.bat single P2P entrypoint.
│   │   ├── 4-3-1: Hub-based IPC — hub.py technology-neutral message passing
│   │   ├── 4-3-2: .ai/ shared state — node-independent shared state
│   │   ├── 4-3-3: msg.bat — single entrypoint for P2P messages
│   │   └── 4-3-4: Node heartbeat — §P-3-QR auto-abstain based
│   │
│   ├── 4-4: Version Management  [B | T2 | T3→1.00]
│   │   G: All protocol versions MUST be tracked and machines must be able to detect mismatches.
│   │   S: PROTOCOL.md §HISTORY; CHANGELOG; **vX.Y** tag format enforced by check-policy.bat.
│   │   ├── 4-4-1: Protocol versioning — PROTOCOL.md §HISTORY
│   │   ├── 4-4-2: CHANGELOG maintenance
│   │   └── 4-4-3: **vX.Y** version tag format enforced
│   │
│   ├── 4-5: Platform Independence  [C | T3 | T3 | 1.00]
│   │   G: No absolute paths or OS-specific constructs in any committed artifact.
│   │   S: Validated via check_policy.py (Axis-J). pathlib.Path enforced in Python.
│   │      P:\ abstracted via relative paths or $env:BASE_DIR.
│   │   ├── 4-5-1: No hardcoded paths — check_policy.py validates
│   │   ├── 4-5-2: USB/cloud portability — P:\ abstraction
│   │   └── 4-5-3: pathlib.Path enforced in Python code
│   │
│   └── 4-6: Node Onboarding  [B | T2 | T2 | 1.00]
│       G: Any new AI node MUST be onboardable without human manual intervention beyond registration.
│       S: Registration via nodes.json + room state. §P-8 token budget. G15 resilience mechanics.
│       ├── 4-6-1: Registration checklist — nodes.json + room state
│       ├── 4-6-2: Required loading files — §P-8 token budget
│       └── 4-6-3: Resilience mechanics (G15) — heartbeat, fallback
│
│  ┌──────────────────── COGNITIVE LAYER ─────────────────────────────┐
│  │                                                                   │
├──┤ Cat 1: 인지 연속성 (Cognitive Continuity)                         │
│  │ [Score: 0.75 | Weight: 17% | Contrib: 0.128 → 0.167]            │
│  └───────────────────────────────────────────────────────────────────┘
│   │
│   ├── 1-1: Context Lifecycle Management  [C | T4 | T2 | 0.50]
│   │   G: Active context size MUST be monitored; exceeding thresholds triggers managed pruning.
│   │   S: check_health.py monitors JSONL size; GREEN(<600KB)/YELLOW(600–1200KB)/RED(>1200KB).
│   │      Thresholds from config.json: context_health_green_kb / context_health_yellow_kb.
│   │   ├── 1-1-1: Size tracking — GREEN/YELLOW/RED bands
│   │   ├── 1-1-2: handoff.md rolling — archive [DONE] items; keep <2KB
│   │   └── 1-1-3: Context Pruning [scope: session-scoped temporary state]
│   │       TTL: resolved items → ttl_resolved_days days → archive
│   │       score = (priority_level × 2) - age_in_days (priority 1–3)
│   │       score < 0 → deletion candidate
│   │       Boundary vs 1-3-2: 1-1-3 = hours-to-days (handoff.md); 1-3-2 = weeks (memory files)
│   │       [PARTIAL — ttl parameter compactor integration needed]
│   │
│   ├── 1-2: Session Continuity  [B | T2 | T2 | 1.00]
│   │   G: Every session MUST produce a machine-readable handoff artifact for the next session.
│   │   S: .ai/sessions/room-{uuid}/handoff.md. Schema: 6 required sections. <4KB per node.
│   │   ├── 1-2-1: Room-based session — .ai/sessions/room-{uuid}/
│   │   ├── 1-2-2: Summary artifacts — summary_{agent}.md, <4KB per node
│   │   ├── 1-2-3: Re-orientation — §P-11 handoff.md read-first before work starts
│   │   └── 1-2-4: Emergency handoff schema
│   │       Fields: executive_summary / technical_state / strategy_for_next_session
│   │
│   ├── 1-3: Memory Persistence [scope: cross-session long-term]  [C | T4 | T2 | 0.50]
│   │   G: Learnings from sessions MUST persist beyond the session boundary in queryable form.
│   │   S: CC Memory at _sys/claude/config/projects/{id}/memory/. memory_compactor.py.
│   │      Boundary vs 1-1-3: 1-3 = cross-session (weeks); compactor_interval_days controls cadence.
│   │   ├── 1-3-1: CC Memory — _sys/claude/config/projects/{id}/memory/
│   │   ├── 1-3-2: Memory compactor — memory_compactor.py, compactor_interval_days
│   │   ├── 1-3-3: Zero-Token Symmetric Memory — §P-11, CLAUDE.md ↔ GEMINI.md sync
│   │   └── 1-3-4: Memory type taxonomy — user / feedback / project / reference
│   │
│   └── 1-4: Instruction Design  [B | T2 | T2 | 1.00]
│       G: AI agents MUST receive persistent, structured instructions that survive context resets.
│       S: CLAUDE.md (global) → project CLAUDE.md (override). English TASK/CONTEXT/QUESTION format.
│       ├── 1-4-1: Global config — CLAUDE.md (CC) / GEMINI.md (GC)
│       ├── 1-4-2: Project-level override — {project_root}/CLAUDE.md
│       ├── 1-4-3: Token-efficient query — English, TASK/CONTEXT/QUESTION format
│       └── 1-4-4: Axis task templates — A–J structured delegation analysis
│
│  ┌──────────────────── COLLABORATION LAYER ─────────────────────────┐
│  │                                                                   │
├──┤ Cat 2: 협업 거버넌스 (Collaboration Governance)                    │
│  │ [Score: 0.67 | Weight: 22% | Contrib: 0.147 → 0.213]            │
│  └───────────────────────────────────────────────────────────────────┘
│   │
│   ├── 2-1: Consensus Protocol  [C | T3 | T3 | 1.00]
│   │   G: All cross-agent decisions MUST follow a documented propose→vote→finalize cycle.
│   │   S: §P-3 FINALIZED envelope. Quorum: N/2+1 general / 100% at R:10. §P-3-FC Final Call.
│   │   ├── 2-1-1: Propose→Vote→FINALIZED — §P-3, unlimited rounds
│   │   ├── 2-1-2: Quorum — §P-3-QR, general N/2+1 / R:10 100%
│   │   ├── 2-1-3: Final Call — §P-3-FC, collab_rate ≥ final_call_min_rate
│   │   └── 2-1-4: Consensus history — handoff.md CONSENSUS_HISTORY
│   │
│   ├── 2-2: Division of Labor  [C | T3 | T2 | 0.67]
│   │   G: Task routing MUST be based on node capability characteristics, not arbitrary assignment.
│   │   S: §P-2 DIRECTIVE JSON envelope. §P-4 routing rules. §P-7 parallel/sequential policy.
│   │   ├── 2-2-1: DIRECTIVE envelope — §P-2 standard JSON
│   │   ├── 2-2-2: Node routing — §P-4, characteristic-based task assignment
│   │   ├── 2-2-3: Parallel/sequential — §P-7, async when impact ranges non-overlapping
│   │   └── 2-2-4: Result aggregation + VERIFY — mutual cross-validation
│   │
│   ├── 2-3: Conflict Resolution  [B | T2 | T2 | 1.00]
│   │   G: Every unresolvable conflict MUST have a defined escalation path to a human decision.
│   │   S: §P-0 Human Gate (Tier-0 veto). §M-3 3-Strike halt. 30-min stalled round auto-sweep.
│   │      Boundary vs 5-5: 2-3 = consensus/deadlock failure; 5-5 = resource/health failure.
│   │   ├── 2-3-1: Deadlock — 2+ consecutive disagreement rounds handler
│   │   ├── 2-3-2: ESCALATE → Human Gate — §P-0 Tier-0 veto
│   │   ├── 2-3-3: 3-Strike halt — §M-3, same error 3× → HALT
│   │   └── 2-3-4: Stalled round sweep — 30-min timeout auto-cleanup
│   │
│   ├── 2-4: Node Management  [C | T3 | T3 | 1.00]
│   │   G: Any node that can vote MUST be registered; its collaboration depth MUST be configurable.
│   │   S: .ai/nodes.json §P-1 registration. collab_rate §C-0 5-anchor (R:0/3/5/8/10).
│   │   ├── 2-4-1: Node registration — .ai/nodes.json, §P-1
│   │   ├── 2-4-2: COLLAB_RATE — §C-0, 5 anchors (R:0/3/5/8/10)
│   │   ├── 2-4-3: N-node expansion — §P-9, voting right on registration
│   │   └── 2-4-4: Resilience + Re-sync
│   │       Diff tool: `git diff --stat .ai/state.json`
│   │       Returning node: digest diff summary → rejoin VOTE
│   │       [PARTIAL — diff automation + Re-sync logic needed]
│   │
│   ├── 2-5: Transparency & Communication  [C | T3 | T1 | 0.33]
│   │   G: All inter-agent communication MUST be visible to all nodes; no private channels.
│   │   S: §M-2 full node public obligation. HUB prefix: HUB / HUB:ERROR / HUB:WARN / HUB:GATE.
│   │      Gemini response format: "━━ Gemini ━━ / ━━ Claude Judgment ━━".
│   │   ├── 2-5-1: No private channels — §M-2, all-node public obligation
│   │   ├── 2-5-2: HUB prefix — §P-5 (HUB / HUB:ERROR / HUB:WARN / HUB:GATE)
│   │   └── 2-5-3: Gemini response format — "━━ Gemini ━━ / ━━ Claude Judgment ━━"
│   │
│   └── 2-6: Decision Attribution  [C | T4 | T0 | 0.00]
│       G: Every FINALIZED directive MUST record who proposed it, the rationale, and affected trade-offs.
│       S: handoff.md CONSENSUS_HISTORY with Proposer field. hub.py disagree-ratio tracking.
│       ├── 2-6-1: Proposer/opposer logging
│       │   [PARTIAL — handoff.md CONSENSUS_HISTORY Proposer field addition needed (R:10)]
│       ├── 2-6-2: Pattern drift detection (G17)
│       │   disagree ratio > voting_drift_threshold_pct% → WARN + ESCALATE
│       └── 2-6-3: Decision weight tracking
│           collab_rate ≥ final_call_min_rate FINALIZED = major decision
│           Record: Proposer, Rationale (1 sentence), Trade-off (T-number)
│           [T0 — hub.py 2-6 not yet implemented]
│
│  ┌──────────────────── INTEGRITY LAYER ─────────────────────────────┐
│  │                                                                   │
├──┤ Cat 3: 시스템 무결성 (System Integrity)                            │
│  │ [Score: 0.71 | Weight: 28% | Contrib: 0.199 → 0.274] ← Axis-J   │
│  └───────────────────────────────────────────────────────────────────┘
│   │
│   ├── 3-1: Security & Trust  [B | T2 | T3→1.00]
│   │   G: AI nodes MUST NOT access credentials; all inputs MUST be sanitized.
│   │   S: §M-1 constitutional doc protection. Auth file AI-inaccessible.
│   │      R:10 write protection on hub.py / PROTOCOL.md / CLAUDE.md.
│   │   ├── 3-1-1: Mutual Non-Interference — §M-1, constitutional doc protection
│   │   ├── 3-1-2: Auth file isolation — auth files AI-inaccessible
│   │   ├── 3-1-3: Input validation — command injection / XSS prevention
│   │   ├── 3-1-4: R:10 write protection — hub.py / PROTOCOL.md / CLAUDE.md
│   │   └── 3-1-5: Secret Injection Protocol
│   │       API keys = env vars only; .env commit forbidden; log filtering required
│   │
│   ├── 3-2: Policy Enforcement (Static)  [C | T3 | T3 | 1.00]
│   │   G: All policy rules MUST be automatically checkable; violations MUST block commits.
│   │   S: check_policy.py 10 checks (Axis-J). Pre-commit hook via check-policy.bat.
│   │      Exit gate: PASS(0) / FAIL(1).
│   │   ├── 3-2-1: Policy Regression Gate — check_policy.py 10 checks (Axis-J)
│   │   ├── 3-2-2: Policy-code consistency — PROTOCOL.md vs hub.py
│   │   ├── 3-2-3: Pre-commit — check-policy.bat hook
│   │   └── 3-2-4: Exit gate — PASS(0) / FAIL(1)
│   │
│   ├── 3-3: Change Management  [C | T3 | T2 | 0.67]
│   │   G: Every change MUST be tagged, committed conventionally, and impact-analyzed.
│   │   S: [추가/삭제/변경/유지] MECE tagging. English conventional commits. Axis-F impact gate.
│   │   ├── 3-3-1: MECE tagging — [추가/삭제/변경/유지] mandatory
│   │   ├── 3-3-2: Conventional commits — English, feat/fix/docs/refactor
│   │   ├── 3-3-3: Branch-before-large-change
│   │   └── 3-3-4: Impact Analysis (G6) — Axis-F mandatory gate
│   │
│   ├── 3-4: Output Validation  [C | T3 | T2 | 0.67]
│   │   G: AI-generated output MUST meet schema, size, and confidence constraints before delivery.
│   │   S: §P-2 envelope schema. §3-4-A size guard. §3-4-B hub script protection.
│   │      Boundary vs 5-2: 3-4 = output schema/confidence; 5-2 = config.json parameter ranges.
│   │   ├── 3-4-1: AI output schema (G2) — structured output validation
│   │   ├── 3-4-2: Include size guard — §3-4-A
│   │   ├── 3-4-3: Hub script protection — §3-4-B
│   │   ├── 3-4-4: Refusal detection — §3-4-C
│   │   └── 3-4-5: Confidence threshold
│   │       §P-2 envelope includes confidence_score: int(0–100)
│   │       Judgment: full file read=100 / partial inference=50 / guess=0–49
│   │       score < confidence_threshold → Human Gate
│   │       [BLOCKED — §P-2 schema change + hub.py validation logic (R:10 consensus)]
│   │
│   ├── 3-5: Error Classification  [B | T2 | T2 | 1.00]
│   │   G: All errors MUST be classified by severity with defined response protocols per class.
│   │   S: P0(blocking) / P1(critical) / WARN / INFO. §M-3 P0 3× → HALT.
│   │   ├── 3-5-1: Severity — P0(blocking) / P1(critical) / WARN / INFO
│   │   ├── 3-5-2: Structured error reporting — standard report format
│   │   └── 3-5-3: 3-Strike trigger — §M-3, P0 3× → HALT
│   │
│   ├── 3-6: Rollback & Recovery  [C | T3 | T2 | 0.67]
│   │   G: Any failed change MUST be undoable to a known-good state within max_rollback_depth steps.
│   │   S: Git-based rollback via ctx-save checkpoints. State migration via version field.
│   │   ├── 3-6-1: Git-based rollback — ctx-save checkpoints
│   │   ├── 3-6-2: max_rollback_depth — recoverable checkpoint count limit
│   │   └── 3-6-3: State Migration (G13)
│   │       .ai/nodes.json + room state.json MUST have version field
│   │       [PARTIAL — version field + migration_check.py needed]
│   │
│   ├── 3-7: Behavioral Compliance Tests (Runtime)  [C | T3 | T2 | 0.67]
│   │   G: AI compliance with protocol rules MUST be verifiable by runtime log analysis.
│   │   S: R:10 log parsing during actual execution. Scenario suite: T-FINALIZED / T-COLLAB_RATE / T-R10.
│   │      Boundary vs 5-3: 3-7 = AI behavior compliance tests; 5-3 = resource/health metrics.
│   │   ├── 3-7-1: Runtime scenarios — actual execution R:10 log parsing
│   │   ├── 3-7-2: Test scenarios — T-FINALIZED / T-COLLAB_RATE / T-R10
│   │   ├── 3-7-3: Param validation (G10) — config.json load-time validation
│   │   └── 3-7-4: Axis token budget (§3-4-D)
│   │       Simple(A/B/C) ≤ 4,000 tok / Deep(D/E/F) ≤ 8,000 tok / Review(G/H/I/J) ≤ 16,000 tok
│   │
│   └── 3-8: Post-Mortem & Learning Loop  [C | T4 | T0 | 0.00]
│       G: Every P0/P1 incident MUST generate a post-mortem; repeated failures MUST lock the task.
│       S: hub.py try/except → P0/P1 detection → pm-draft.md auto-generation.
│          5-Why → PROTOCOL.md revision proposal draft. Feeds back to Cat 2 (policy update).
│       ├── 3-8-1: Failure → Kaizen (G16)
│       │   hub.py try/except → P0/P1 detect → pm-draft.md auto-generate
│       │   5-Why result → PROTOCOL.md revision draft proposal
│       │   [BLOCKED — hub.py exception hook + .ai/postmortems/ directory needed]
│       ├── 3-8-2: PM template
│       │   Fields: Incident / Root Cause (5-Why) / Timeline / Category / Prevention / Policy
│       │   Storage: .ai/postmortems/pm-{YYYYMMDD}-{id}.md
│       └── 3-8-3: Learning gate
│           Repeated error 3×+ → same task locked until Kaizen complete
│
│  ┌──────────────────── OPERATIONS LAYER ────────────────────────────┐
│  │                                                                   │
├──┤ Cat 5: 운영 & 제어 (Operations & Control)                         │
│  │ [Score: 0.35 | Weight: 7% | Contrib: 0.025 → 0.067]             │
│  └───────────────────────────────────────────────────────────────────┘
│   │
│   ├── 5-1: Shared Parameter Registry  [C | T3 | T1 | 0.33]
│   │   G: All behavioral thresholds MUST be stored in a single versioned registry file.
│   │   S: config.json flat+metadata. _param_sections metadata. 24 total keys.
│   │   ├── 5-1-1: Flat+metadata config.json — _param_sections metadata
│   │   ├── 5-1-2~6: 22 parameters (§6)
│   │   └── Validation: 24 key existence check (_param_sections + 22 params + last_review_ts)
│   │
│   ├── 5-2: Parameter Validation  [C | T3 | T2 | 0.67]
│   │   G: All parameters MUST be range-validated at load time; out-of-range values MUST fail.
│   │   S: config.json G10 schema validation on load. _param_sections integrity check.
│   │      Boundary vs 3-4: 5-2 = config.json parameter ranges; 3-4 = AI output schema.
│   │   ├── 5-2-1: Config schema (G10) — auto-validate on load (24 keys)
│   │   ├── 5-2-2: Parameter range enforcement
│   │   └── 5-2-3: _param_sections integrity check
│   │
│   ├── 5-3: Observability  [C | T4 | T3 | 0.75]  ← Axis-H
│   │   G: System health MUST be continuously measurable and queryable without tool access.
│   │   S: check_health.py GREEN/YELLOW/RED. Async events (G11) out-of-band policy needed.
│   │      Boundary vs 3-7: 5-3 = resource/health metrics collection; 3-7 = AI behavior tests.
│   │      Boundary vs 5-4: 5-3 = raw metric collection; 5-4 = aggregated display.
│   │   ├── 5-3-1: Context Health — check_health.py (GREEN/YELLOW/RED)
│   │   ├── 5-3-2: Async Events (G11) — out-of-band event handling [policy needed]
│   │   └── 5-3-3: Collab metrics — collab_rate status, consensus success rate
│   │
│   ├── 5-4: System Health Dashboard  [C | T3 | T1 | 0.33]
│   │   G: Aggregated health state MUST be viewable in a single human-readable status line.
│   │   S: Session header format: ROOM:{id}|RATE:R{n}|HEALTH:{kb}KB({color}).
│   │      Metrics aggregated from 5-3. Flush interval: metrics_flush_interval_sec.
│   │   ├── 5-4-1: Session header — ROOM:{id}|RATE:R{n}|HEALTH:{kb}KB({color})
│   │   ├── 5-4-2: Metrics aggregation — policy compliance %, consensus success %
│   │   ├── 5-4-3: Persistent metrics — metrics_flush_interval_sec
│   │   └── 5-4-4: Dashboard spec (G7) [DASHBOARD_SPEC.md needed]
│   │
│   ├── 5-5: Active Control Loop [Cross-category Execution Orchestrator]
│   │   [C | T4 | T0 | 0.00]
│   │   G: The system MUST proactively prevent resource exhaustion and health degradation.
│   │   S: hub.py synchronous _sla_preflight_check() on every action entry.
│   │      RED state → auto ctx-save + collab_rate temp down (current−2, min 3).
│   │      Boundary vs 2-3: 5-5 = system/resource triggers; 2-3 = consensus/deadlock triggers.
│   │      [BLOCKED — hub.py pre-flight + lock mechanism implementation needed]
│   │   ├── 5-5-1: Lock-safety — confirm no active write nodes before control action
│   │   ├── 5-5-2: RED trigger — auto ctx-save + collab_rate temp down (current−2, min 3)
│   │   ├── 5-5-3: Token budget control
│   │   │   Usage > token_budget_daily × token_budget_warn_pct/100 → alert
│   │   │   Usage ≥ 100% → collab_rate=3 forced
│   │   ├── 5-5-4: SLA escalation — 2 consecutive timeouts → auto ESCALATE
│   │   └── 5-5-5: Safety guard — active_control_enabled=0 (default) = all items inactive
│   │
│   └── 5-6: Economic & Quota Governance  [C | T4 | T0 | 0.00]
│       G: Token spend MUST be tracked, forecasted, and bounded; ROI MUST be measurable.
│       S: msg.bat post-processing len(content)//4 → .ai/state.json accumulation.
│          [BLOCKED — token_tracker or msg.bat hook needed]
│       ├── 5-6-1: Token ROI — FINALIZED_DIRECTIVEs + merged_PRs / daily tokens
│       ├── 5-6-2: Budget management — token_budget_warn_pct% alert; 100% Axis block
│       ├── 5-6-3: Token forecasting (G14) — forecast_warn_threshold_pct runway
│       └── 5-6-4: Cost rules
│           Same search_pattern + same directory: axis_delegation_threshold Greps → Axis-G
│
│  ┌──────────────────── DELIVERY LAYER ──────────────────────────────┐
│  │                                                                   │
└──┤ Cat 6: 산출물 인도 & 검증 (Product Delivery & Validation)          │
   │ [Score: 0.40 | Weight: 5% | Contrib: 0.020 → 0.045]             │
   │  ──────────────────────────────────────────────────────────────── │
   │  [Loop close: Cat 6 feeds back to Cat 0 via Human ACK]          │
   └───────────────────────────────────────────────────────────────────┘
    │
    ├── 6-1: Artifact Assembly (산출물 정리)  [B | T2 | T1 | 0.50]
    │   G: Every deliverable MUST be a discrete file artifact — no conversation-only outputs.
    │   S: Write tool for all final outputs. Delivery format matches 0-2-3.
    │   ├── 6-1-1: Output format compliance — matches Cat 0-2-3 delivery format spec
    │   ├── 6-1-2: Completeness check — all Cat 0-2-1 acceptance criteria addressed
    │   └── 6-1-3: File output mandate — deliverables always as files (loss prevention)
    │
    ├── 6-2: User Acceptance Test (사용자 인수 테스트)  [C | T3 | T0 | 0.00]
    │   G: Human MUST explicitly verify the golden path before task closure.
    │   S: delivery_acceptance_required=1 → explicit Human ACK required.
    │      Regression: no previously working feature broken. Min 1 edge case verified.
    │   ├── 6-2-1: Human-in-loop verification — delivery_acceptance_required=1 → explicit ACK
    │   ├── 6-2-2: Regression check — no previously working feature broken
    │   └── 6-2-3: E2E scenario coverage — golden path + ≥1 edge case verified
    │
    └── 6-3: Delivery Handoff & Feedback Loop  [C | T3 | T2 | 0.67]
        G: Session state MUST be archived on completion; lessons feed the next cycle's Cat 0.
        S: ctx-save / ctx-end on completion. Lessons → 3-8 Post-Mortem. handoff.md NEXT_SESSION.
        ├── 6-3-1: Session archive — ctx-save / ctx-end on task completion
        ├── 6-3-2: Lessons learned — incidents → 3-8 Post-Mortem (feeds back to Cat 3)
        └── 6-3-3: Next intent seeding — handoff.md NEXT_SESSION section for continuity
                   [loop arrow → Cat 0 of next session]
```

**Tree Legend**: `[Type | Target Tier | Current Tier | Score]` — B=Binary, C=Continuous

---

## §4. Measurement Matrix

All sub-category measurement indicators, methods, and 100% criteria in one place.

### Cat 0: 인간 의도 & 킥오프

| ID | Name | Type | Target | Current | Score | Measurement (PS native) | 100% Criterion |
|:---|:-----|:----:|:------:|:-------:|:-----:|:------------------------|:---------------|
| **0-1** | Intent Capture | B | T2 | T1 | 0.50 | `Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "TASK:"` | TASK/CONTEXT/QUESTION format present in every handoff |
| **0-2** | Success Criteria | B | T2 | T1 | 0.50 | `Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "acceptance_criteria"` | acceptance_criteria field exists + non-empty |
| **0-3** | Clarification Protocol | C | T3 | T0 | 0.00 | `Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "CLARIFICATION_ACK"` | 100% multi-file tasks have CLARIFICATION_ACK before execution |
| **Cat 0** | | | | | **0.33** | | |

### Cat 1: 인지 연속성

| ID | Name | Type | Target | Current | Score | Measurement (PS native) | 100% Criterion |
|:---|:-----|:----:|:------:|:-------:|:-----:|:------------------------|:---------------|
| **1-1** | Context Lifecycle | C | T4 | T2 | 0.50 | `cmd /c ".\_sys\checks\check-health.bat"` | GREEN 95%+; RED entry 0 per 48h |
| **1-2** | Session Continuity | B | T2 | T2 | 1.00 | `(Get-Item ".ai\sessions\room-*\handoff.md").Length / 1KB` | ≤2KB; 6 section headers present |
| **1-3** | Memory Persistence | C | T4 | T2 | 0.50 | `python ".\_sys\hooks\memory_compactor.py" 2>&1` stale count | stale=0; compactor last run ≤ compactor_interval_days |
| **1-4** | Instruction Design | B | T2 | T2 | 1.00 | `Test-Path ".\_sys\claude\config\CLAUDE.md"` AND `Test-Path ".\CLAUDE.md"` | both files exist + `R:10` string present |
| **Cat 1** | | | | | **0.75** | | |

### Cat 2: 협업 거버넌스

| ID | Name | Type | Target | Current | Score | Measurement (PS native) | 100% Criterion |
|:---|:-----|:----:|:------:|:-------:|:-----:|:------------------------|:---------------|
| **2-1** | Consensus Protocol | C | T3 | T3 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "hub-consensus-actions"` | "PASS" present |
| **2-2** | Division of Labor | C | T3 | T2 | 0.67 | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "from.*(cc\|gc\|ca)"` | ≥2 nodes each with ≥1 DIRECTIVE sent record |
| **2-3** | Conflict Resolution | B | T2 | T2 | 1.00 | `Select-String -Path ".\_sys\core\hub.py" -Pattern "ESCALATE"` | hub.py ESCALATE code present |
| **2-4** | Node Management | C | T3 | T3 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "collab-rate-symmetry"` | "PASS" present |
| **2-5** | Transparency | C | T3 | T1 | 0.33 | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "private\|offchannel"` | 0 matches; §M-2 in PROTOCOL.md |
| **2-6** | Decision Attribution | C | T4 | T0 | 0.00 | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "Proposer:"` | 100% FINALIZED have Proposer field; drift detection running |
| **Cat 2** | | | | | **0.67** | | |

### Cat 3: 시스템 무결성

| ID | Name | Type | Target | Current | Score | Measurement (PS native) | 100% Criterion |
|:---|:-----|:----:|:------:|:-------:|:-----:|:------------------------|:---------------|
| **3-1** | Security & Trust | B | T2 | T3→1.00 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "r10-files-exist"` | "PASS"; 3-1-5 Secret protocol present |
| **3-2** | Policy Enforcement | C | T3 | T3 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat"; $LASTEXITCODE` | exit 0; 0 FAIL |
| **3-3** | Change Management | C | T3 | T2 | 0.67 | `@(git log --oneline -20 \| Select-String -Pattern "^[0-9a-f]+ (feat\|fix\|docs\|refactor\|test\|chore):").Count / 20 * 100` | ≥95% compliance |
| **3-4** | Output Validation | C | T3 | T2 | 0.67 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "size-guard"` | 0 violations; confidence failures 0 |
| **3-5** | Error Classification | B | T2 | T2 | 1.00 | `Select-String -Path ".\PROTOCOL.md" -Pattern "§M-3"` | §M-3 + P0/P1 criteria documented |
| **3-6** | Rollback & Recovery | C | T3 | T2 | 0.67 | `@(git log --grep="ctx-save" --oneline).Count` | ≥ max_rollback_depth checkpoints exist |
| **3-7** | Behavioral Tests | C | T3 | T2 | 0.67 | `Get-Content ".ai\sessions\room-*\handoff.md" \| Select-String "FINALIZED"` vs total DIRECTIVE | ≥95% DIRECTIVEs → FINALIZED tracked; 0 unauthorized edits |
| **3-8** | Post-Mortem Loop | C | T4 | T0 | 0.00 | `@(Get-ChildItem ".ai\postmortems\*.md" -ErrorAction SilentlyContinue).Count` | PM generation rate 100% (vs ESCALATE+3-Strike count); 0 orphans/48h |
| **Cat 3** | | | | | **0.71** | | |

### Cat 4: 환경 이식성

| ID | Name | Type | Target | Current | Score | Measurement (PS native) | 100% Criterion |
|:---|:-----|:----:|:------:|:-------:|:-----:|:------------------------|:---------------|
| **4-1** | Runtime Environment | C | T3 | T3 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "pythonutf8"` AND `Test-Path ".\_sys\env\venv"` | "PASS"; venv exists |
| **4-2** | Installation | C | T3 | T2 | 0.67 | `Test-Path ".\_sys\install.bat"` AND manual run result | file exists; 0 errors |
| **4-3** | Infra Abstraction | C | T3 | T2 | 0.67 | `cmd /c ".\_sys\cli\msg.bat" hub status; $LASTEXITCODE` | exit 0; nodes.json valid JSON |
| **4-4** | Version Management | B | T2 | T3→1.00 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "protocol-version"` | "PASS" |
| **4-5** | Platform Independence | C | T3 | T3 | 1.00 | `cmd /c ".\_sys\checks\check-policy.bat" 2>&1 \| Select-String "no-hardcoded-paths"` | "PASS" |
| **4-6** | Node Onboarding | B | T2 | T2 | 1.00 | `Test-Path ".ai\nodes.json"` AND `Select-String -Path ".\PROTOCOL.md" -Pattern "§P-8"` | nodes.json valid; §P-8 exists |
| **Cat 4** | | | | | **0.89** | | |

### Cat 5: 운영 & 제어

| ID | Name | Type | Target | Current | Score | Measurement (PS native) | 100% Criterion |
|:---|:-----|:----:|:------:|:-------:|:-----:|:------------------------|:---------------|
| **5-1** | Param Registry | C | T3 | T1 | 0.33 | `python -c "import json; d=json.load(open('./_sys/gemini/config.json')); assert len(d)==24"` | 24 keys; _param_sections integrity PASS |
| **5-2** | Param Validation | C | T3 | T2 | 0.67 | `cmd /c ".\_sys\checks\check-policy.bat"` (collab-rate-symmetry) | 0 range violations; _param_sections consistent |
| **5-3** | Observability | C | T4 | T3 | 0.75 | `cmd /c ".\_sys\checks\check-health.bat"; $LASTEXITCODE` | exit 0; GREEN/YELLOW/RED judgment + log generated |
| **5-4** | Dashboard | C | T3 | T1 | 0.33 | `cmd /c ".\_sys\cli\msg.bat" hub status 2>&1 \| Select-String "ROOM:"` | "ROOM:{id}\|RATE:\|HEALTH:" format present |
| **5-5** | Active Control Loop | C | T4 | T0 | 0.00 | `python -c "import json; print(json.load(open('./_sys/gemini/config.json'))['active_control_enabled'])"` | active=1: 100% RED → recovery; 0 unhandled |
| **5-6** | Economic Governance | C | T4 | T0 | 0.00 | `@(Get-Content ".ai\sessions\*\handoff.md" \| Select-String "msg.bat").Count * 2000` vs token_budget_daily | ≤100% budget; 0-miss pre-exhaustion alerts |
| **Cat 5** | | | | | **0.35** | | |

### Cat 6: 산출물 인도 & 검증

| ID | Name | Type | Target | Current | Score | Measurement (PS native) | 100% Criterion |
|:---|:-----|:----:|:------:|:-------:|:-----:|:------------------------|:---------------|
| **6-1** | Artifact Assembly | B | T2 | T1 | 0.50 | `Get-ChildItem ".\*" -Include "*.md","*.py","*.json" \| Where-Object {$_.LastWriteTime -gt (Get-Date).AddHours(-2)}` | all deliverables present as files; delivery format matches 0-2-3 |
| **6-2** | UAT | C | T3 | T0 | 0.00 | `Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "HUMAN_ACK"` | HUMAN_ACK present per completed task when delivery_acceptance_required=1 |
| **6-3** | Delivery Handoff | C | T3 | T2 | 0.67 | `@(git log --grep="ctx-end" --oneline).Count` AND `Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "NEXT_SESSION"` | ctx-end exists; NEXT_SESSION section non-empty |
| **Cat 6** | | | | | **0.40** | | |

---

## §5. Trade-off Table (T1–T21)

| # | Item A | Item B | Control Parameter | Management | Notes |
|:--|:-------|:-------|:-----------------|:-----------|:------|
| T1 | Zero-token efficiency | Collaboration depth | `collab_rate` | Explicit | R:0=full autonomy, R:10=full consensus |
| T2 | Context preservation | Processing speed | `context_health_green_kb` | Explicit | Lower = more sensitive |
| T3 | Consensus accuracy | Response speed | `consensus_timeout_min` | Explicit | Balance: MTC vs Rejection Rate |
| T4 | Autonomy | Safety | `collab_rate` + §C-0 anchors | Explicit | 5 anchors (R:0/3/5/8/10) |
| T5 | Document detail | Token cost | English mandate | Policy | English 2–3× more efficient |
| T6 | Session+memory continuity | Context freshness | `compactor_interval_days` + `ttl_resolved_days` | Explicit | handoff TTL + long-term compactor unified |
| T7 | Portability | Platform optimization | — | Policy | pathlib / absolute path prohibition |
| T8 | Policy strictness | Development speed | `final_call_min_rate` | Explicit | Higher = safer |
| T10 | Security isolation | Collaboration convenience | — | Policy | §M-1 Non-Interference |
| T11 | Node scalability | Consensus complexity | — | Policy | Adding nodes increases voting complexity |
| T12 | Pruning aggressiveness | Memory preservation | `ttl_resolved_days` | Explicit | |
| T13 | Metric granularity | Disk I/O | `metrics_flush_interval_sec` | Explicit | |
| T14 | Forecast sensitivity | Alert fatigue | `forecast_warn_threshold_pct` | Explicit | |
| T15 | Learning overhead | System evolution speed | — | Policy | Post-mortem time cost |
| T16 | Active automation | Human control | `active_control_enabled` | Explicit | 0=safe, 1=efficient |
| T17 | Token economy | Collaboration depth | `token_budget_daily` + `collab_rate` | Explicit | Balance: Budget vs Rounds per Decision |
| T18 | File rewrite (high token, low syntax risk) | Surgical diff (low token, high syntax risk) | — | Practice | Use Edit tool for surgical; Write for full rewrites |
| T19 | Human visual verification (blocks async) | AI automated E2E testing (high token burn) | — | Policy | Human verifies UI/UX; AI writes logic tests |
| T20 | Heuristic flexibility (goal-oriented) | Strict policy gate (halt on minor issues) | `policy_gate_bypass_threshold` | Explicit | collab_rate < threshold → minor gate bypass allowed |
| T21 | CC+GC specificity (high precision) | General portability (other AI systems usable) | — | Architecture | This document targets CC+GC; G: lines are portable |

> **T9 deleted**: merged into T6 (same parameters and structure).

### Trade-off Balance Metrics (T3/T17)

**T3: Consensus Accuracy vs Speed**

| Metric | Measurement | Balance Criterion |
|:-------|:-----------|:-----------------|
| MTC (Mean Time to Consensus, min) | handoff.md propose→FINALIZED time diff average | MTC ≤ consensus_timeout_min × 0.5 |
| Rejection Rate (%) | ESCALATE count / total rounds | ≤ 10% |
| Balance signal | MTC rising → accuracy ↑; Rate rising → reconsider collab_rate | |

**T17: Token Economy vs Collaboration Depth**

| Metric | Measurement | Balance Criterion |
|:-------|:-----------|:-----------------|
| Budget Utilization (%) | daily tokens / token_budget_daily × 100 | < 90% (token_budget_warn_pct) |
| Rounds per Decision | avg(rounds per FINALIZED) | ≤ 3 |
| Balance signal | High budget + low rounds = waste; High rounds → consider collab_rate ↓ | |

---

## §5.5 Logical Contradictions (Non-Parameterizable)

Items in this section are **structurally contradictory** — they cannot be resolved by parameter adjustment.
They require explicit architectural acknowledgment and a stated management strategy.

| # | Contradiction | Affected Items | Management Strategy |
|:--|:-------------|:--------------|:-------------------|
| C1 | **R:10 verbosity vs Context <600KB**: R:10 mandates unlimited negotiation rounds and verbose rationale. Sustained R:10 mathematically guarantees context GREEN threshold breach. | Cat 1 (1-1) vs Cat 2 (2-1, 2-4) | Accepted. The "실용 천장 98%" policy (§2-1) acknowledges 2% non-deterministic tolerance. `collab_rate` acts as the relief valve — drop to R:5–8 for extended sessions. Human can trigger ctx-save at any time. |
| C2 | **"Zero-Context Usable" claim vs Historical Observability**: §0 claims the document is usable from a zero-context session. However, Cat 5-6 (Token ROI, forecasting) and 3-8 (Kaizen pattern detection) require historical session data that a zero-context session lacks. | §0 (scope claim) vs Cat 5-6, Cat 3-8 | Scoped. "Zero-context" means the **document itself** is self-explanatory — it does NOT mean the **system** can operate without history. Runtime metrics require history; document design does not. Clarified in §0.1. |
| C3 | **Full Autonomy (Cat 5-5 active_control_enabled=1) vs Human-in-Loop (Cat 0 + Cat 6)**: Enabling active control loop can automatically adjust collab_rate, trigger ctx-save, and block Axis tasks — overriding the human's Cat 0 intent and Cat 6 acceptance check. | Cat 5-5 vs Cat 0, Cat 6 | Constrained. `active_control_enabled=0` by default. When enabled, the active control loop MUST NOT modify `delivery_acceptance_required` or the Cat 0 CLARIFICATION_ACK gate. Human bookend checkpoints are exempt from automated override. |

---

## §6. Parameter Registry (22 parameters, 24 keys, config.json v4.0)

```json
{
  "_param_sections": {
    "general": ["collab_rate","consensus_timeout_min","final_call_min_rate",
                "token_budget_daily","axis_delegation_threshold",
                "policy_gate_bypass_threshold"],
    "cat0":    ["human_intent_timeout_min","intent_clarification_max_turns",
                "delivery_acceptance_required"],
    "cat1":    ["context_health_green_kb","context_health_yellow_kb",
                "compactor_interval_days","review_interval_min",
                "ttl_resolved_days","ttl_active_days"],
    "cat2":    ["voting_drift_threshold_pct"],
    "cat3":    ["max_rollback_depth","confidence_threshold"],
    "cat5":    ["metrics_flush_interval_sec","active_control_enabled",
                "forecast_warn_threshold_pct","token_budget_warn_pct"]
  },
  "collab_rate": 10,
  "consensus_timeout_min": 30,
  "final_call_min_rate": 8,
  "token_budget_daily": 50000,
  "axis_delegation_threshold": 5,
  "policy_gate_bypass_threshold": 8,
  "human_intent_timeout_min": 60,
  "intent_clarification_max_turns": 3,
  "delivery_acceptance_required": 1,
  "context_health_green_kb": 600,
  "context_health_yellow_kb": 1200,
  "compactor_interval_days": 7,
  "review_interval_min": 5,
  "ttl_resolved_days": 3,
  "ttl_active_days": 14,
  "voting_drift_threshold_pct": 60,
  "max_rollback_depth": 3,
  "confidence_threshold": 70,
  "metrics_flush_interval_sec": 300,
  "active_control_enabled": 0,
  "forecast_warn_threshold_pct": 70,
  "token_budget_warn_pct": 90,
  "last_review_ts": null
}
```

> Total keys: **24** (`_param_sections` + 22 parameters + `last_review_ts`)
> Validation: `python -c "import json; d=json.load(open('./_sys/gemini/config.json')); assert len(d)==24; print('OK 24 keys')"`

### Parameter Definitions (22 complete)

| Parameter | Type | Range | Default | Meaning | Section | Trade-off |
|:----------|:----:|:-----:|:-------:|:--------|:-------:|:---------:|
| `collab_rate` | int | 0–10 | 10 | Collaboration depth. 0=full autonomy, 10=unanimous consent | general | T1,T4,T17 |
| `consensus_timeout_min` | int | 1–60 | 30 | Consensus round auto-timeout (minutes) | general | T3 |
| `final_call_min_rate` | int | 0–10 | 8 | §P-3-FC Final Call threshold rate | general | T8 |
| `token_budget_daily` | int | 1k–500k | 50000 | Daily total token consumption ceiling | general | T17 |
| `axis_delegation_threshold` | int | 1–20 | 5 | Same-scope Grep N times → Axis-G delegation | general | — |
| `policy_gate_bypass_threshold` | int | 0–10 | 8 | collab_rate below this allows minor policy gate bypass | general | T20 |
| `human_intent_timeout_min` | int | 1–1440 | 60 | Max wait for human clarification before ESCALATE (minutes) | cat0 | — |
| `intent_clarification_max_turns` | int | 1–10 | 3 | Max AI clarification question rounds before proceeding | cat0 | — |
| `delivery_acceptance_required` | int | 0–1 | 1 | Whether explicit Human ACK is required before task closure | cat0 | T16,C3 |
| `context_health_green_kb` | int | 100–1000 | 600 | GREEN state threshold (KB) | cat1 | T2 |
| `context_health_yellow_kb` | int | 200–2000 | 1200 | YELLOW→RED transition threshold (KB) | cat1 | T2 |
| `compactor_interval_days` | int | 1–30 | 7 | Memory compactor cadence (days) | cat1 | T6,T12 |
| `review_interval_min` | int | 1–60 | 5 | Gemini review minimum interval (minutes) | cat1 | T1 |
| `ttl_resolved_days` | int | 1–30 | 3 | handoff.md [DONE] TTL (days) | cat1 | T6,T12 |
| `ttl_active_days` | int | 1–90 | 14 | handoff.md incomplete item TTL (days) | cat1 | T6 |
| `voting_drift_threshold_pct` | int | 1–99 | 60 | Node disagree ratio (%) WARN threshold | cat2 | — |
| `max_rollback_depth` | int | 1–10 | 3 | Git rollback checkpoint count ceiling | cat3 | — |
| `confidence_threshold` | int | 0–100 | 70 | AI confidence below this → Human Gate (%) | cat3 | — |
| `metrics_flush_interval_sec` | int | 10–3600 | 300 | Operational metrics disk write interval (seconds) | cat5 | T13 |
| `active_control_enabled` | int | 0–1 | 0 | Active control loop enabled (0=off, default safe) | cat5 | T16,C3 |
| `forecast_warn_threshold_pct` | int | 1–99 | 70 | Context usage (%) forecast alert threshold | cat5 | T14 |
| `token_budget_warn_pct` | int | 1–99 | 90 | Daily budget exhaustion alert threshold (%) | cat5 | T17 |

---

## §7. Root Health Formula

### Item Score

```
Item Score = min(Current Tier / Target Tier, 1.0)

Examples:
  1-1 (C, T4 target, T2 current):  2/4 = 0.50
  3-1 (B, T2 target, T3 current):  min(3/2, 1.0) = 1.00  ← capped
  2-6 (C, T4 target, T0 current):  0/4 = 0.00
  0-3 (C, T3 target, T0 current):  0/3 = 0.00
```

### Category Score

```
Category Score = mean(Item Scores in category)
```

### Root Health Score (Weighted, 7 categories)

```
Root = 0.08×Cat0 + 0.17×Cat1 + 0.22×Cat2 + 0.28×Cat3 + 0.13×Cat4 + 0.07×Cat5 + 0.05×Cat6

Current: 0.08×0.33 + 0.17×0.75 + 0.22×0.67 + 0.28×0.71 + 0.13×0.89 + 0.07×0.35 + 0.05×0.40
       = 0.026 + 0.128 + 0.147 + 0.199 + 0.116 + 0.025 + 0.020
       = 0.661 (66.1%)

Target:  0.08×0.90 + 0.17×0.98 + 0.22×0.97 + 0.28×0.98 + 0.13×0.97 + 0.07×0.95 + 0.05×0.90
       = 0.072 + 0.167 + 0.213 + 0.274 + 0.126 + 0.067 + 0.045
       = 0.964 (96.4%)
```

### "100% Done" Judgment (6 conditions, all simultaneous)

| # | Condition | Verification Command |
|:--|:---------|:--------------------|
| ① | check-policy.bat exit 0 | `cmd /c ".\_sys\checks\check-policy.bat"; $LASTEXITCODE -eq 0` |
| ② | check-health.bat GREEN | `cmd /c ".\_sys\checks\check-health.bat" 2>&1 \| Select-String "GREEN"` |
| ③ | Root Score ≥ 0.95 | §7 formula calculation |
| ④ | Level A KPI 5 targets achieved | §4 Measurement Matrix |
| ⑤ | G1–G17 all ✅ (G11 🔶 allowed) | §9 Gap Log |
| ⑥ | Orphan Post-Mortem = 0 | `@(Get-ChildItem ".ai\postmortems\*.md" \| Where-Object {(Get-Content $_) -match "status: open"}).Count -eq 0` |

---

## §8. Measurement Quick Reference

```powershell
# ── Policy Gate (Axis-J, Cat 3) ───────────────────────────────────────
cmd /c ".\_sys\checks\check-policy.bat"

# ── Context Health (Axis-H, Cat 1/5) ──────────────────────────────────
cmd /c ".\_sys\checks\check-health.bat"

# ── Hub Status (Cat 2/4/5) ─────────────────────────────────────────────
cmd /c ".\_sys\cli\msg.bat" hub status

# ── handoff.md size (Cat 1-2) ──────────────────────────────────────────
(Get-Item ".ai\sessions\room-{id}\handoff.md").Length / 1KB

# ── Commit format compliance rate (Cat 3-3) ───────────────────────────
@(git log --oneline -20 | Select-String -Pattern `
  "^[0-9a-f]+ (feat|fix|docs|refactor|test|chore):").Count / 20 * 100

# ── ctx-save checkpoint count (Cat 3-6) ───────────────────────────────
@(git log --grep="ctx-save" --oneline).Count

# ── config.json validity — 24-key check (Cat 5-1) ─────────────────────
python -c "import json; d=json.load(open('./_sys/gemini/config.json')); assert len(d)==24; print('OK 24 keys')"

# ── PS execution policy (Cat 4-1-5) ───────────────────────────────────
Get-ExecutionPolicy    # → RemoteSigned or higher required

# ── Post-Mortem status (Cat 3-8) ──────────────────────────────────────
@(Get-ChildItem ".ai\postmortems\*.md" -ErrorAction SilentlyContinue).Count

# ── Memory file count (Cat 1-3) ───────────────────────────────────────
(Get-ChildItem ".\_sys\claude\config\projects\P--\memory\*.md").Count

# ── Intent capture check (Cat 0-1) ────────────────────────────────────
Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "TASK:"

# ── Human ACK check (Cat 6-2) ─────────────────────────────────────────
Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "HUMAN_ACK"

# ── Root Score calculation (P2 implementation pending) ────────────────
# python .\_sys\checks\calc_completion.py
```

---

## §9. Gap Analysis Log

| # | Gap | Location | Status |
|:--|:----|:---------|:-------|
| G1 | Instruction Design | 1-4 | ✅ v3.0 |
| G2 | Output Validation | 3-4 | ✅ v3.0 |
| G3 | Rollback Protocol | 3-6 | ✅ v3.0 |
| G4 | Error Classification | 3-5 | ✅ v3.0 |
| G5 | AI Behavioral Test Suite | 3-7 | ✅ v3.0 |
| G6 | Impact Analysis | 3-3-4 (Axis-F) | ✅ v4.0 |
| G7 | Dashboard | 5-4-4 | 🔶 DASHBOARD_SPEC.md needed |
| G8 | Metrics | 5-4-2 | ✅ v4.0 |
| G9 | Node Onboarding | 4-6 | ✅ v3.0 |
| G10 | Parameter Validation | 5-2 | ✅ v4.0 |
| G11 | Async Event Handling | 5-3-2 | 🔶 Policy documentation needed (non-deterministic) |
| G12 | Resource & Quota Mgmt | 5-6 | 🔶 taxonomy-defined, implementation pending |
| G13 | State Migration | 3-6-3 | 🔶 PARTIAL — version field + migration_check.py |
| G14 | Token Budget Forecasting | 5-6-3 | 🔶 taxonomy-defined, implementation pending |
| G15 | Node Resilience Protocol | 2-4-4, 4-6-3 | 🔶 Re-sync diff automation needed |
| G16 | Automated Kaizen Triggers | 3-8-1 | 🔶 hub.py exception hook + postmortems/ needed |
| G17 | Node Voting Bias Alerting | 2-6-2 | 🔶 hub.py analysis function needed (R:10 consensus) |
| G18 | Human Intent Capture | 0-1, 0-3 | 🔶 NEW — TASK/CONTEXT/QUESTION enforcement + CLARIFICATION_ACK |
| G19 | User Acceptance Testing | 6-2 | 🔶 NEW — HUMAN_ACK protocol in handoff.md needed |
| G20 | Edit Granularity Policy | T18 | 🔶 NEW — CONVENTION.md §12 Surgical vs Rewrite policy |

---

## §10. Implementation Queue

| Priority | Task | File | Notes |
|:--------:|:-----|:-----|:------|
| **P0** | config.json — 22 params + `_param_sections` + 3 new cat0 params | `.\_sys\gemini\config.json` | 24 keys total |
| **P0** | gemini-set-ratio.bat — `ratio`→`collab_rate` rename | `.\_sys\gemini\gemini-set-ratio.bat` | Simultaneous with P0 |
| **P1** | memory_compactor.py — MAX_AGE_DAYS → config.json reference | `.\_sys\hooks\memory_compactor.py:16` | |
| **P1** | check_health.py — thresholds → config.json reference | `.\_sys\checks\check_health.py` | |
| **P1** | .ai/postmortems/ directory creation + install.bat registration | `install.bat` | G16 |
| **P1** | hub.py P0/P1 try/except → pm-draft.md auto-generation | `.\_sys\core\hub.py` | G16 |
| **P1** | handoff.md template: add CLARIFICATION_ACK + HUMAN_ACK fields | `PROTOCOL.md §P-11` | G18, G19 |
| **P2** | §P-2 envelope: add confidence_score field | `PROTOCOL.md` | R:10 consensus needed |
| **P2** | CONSENSUS_HISTORY: add Proposer field | `PROTOCOL.md` / hub.py | R:10 consensus needed |
| **P2** | msg.bat post-processing: len(content)//4 → .ai/state.json | `.\_sys\cli\msg.bat` | G12, 5-6 |
| **P2** | hub.py _sla_preflight_check() synchronous check | `.\_sys\core\hub.py` | 5-5 |
| **P3** | .ai/nodes.json version field + migration_check.py | `.ai\`, `.\_sys\checks\` | G13 |
| **P3** | G15 Re-sync diff automation | `.\_sys\core\hub.py` | |
| **P3** | G7 Dashboard spec | `.\_sys\docs\DASHBOARD_SPEC.md` | |
| **P3** | G11 Async handling policy | `CONVENTION.md §11` | |
| **P3** | G17 Voting Bias Detection | `.\_sys\core\hub.py` | R:10 consensus needed |
| **P3** | G20 Edit Granularity Policy | `CONVENTION.md §12` | T18 |
| **P3** | calc_completion.py — Root Score auto-calculation | `.\_sys\checks\calc_completion.py` | §8 |

---

## §11. Axis ↔ Category Mapping (7-Category Version)

| Axis | Name | Primary Cat | Secondary | Description |
|:----:|:-----|:-----------:|:---------:|:-----------|
| A | Architecture Review | Cat 1, 4 | Cat 3 | Design decision review |
| B | Behavior Analysis | Cat 2 | Cat 3 | Node behavior pattern analysis |
| C | Code Review | Cat 3 | Cat 2 | Code quality and policy compliance |
| D | Dependency Scan | Cat 4 | Cat 3 | Dependency security and portability |
| E | Error Root Cause | Cat 3 | Cat 2 | Error root cause analysis |
| F | Impact Analysis | Cat 3 | Cat 5 | Change blast radius (G6, mandatory gate) |
| G | Gap Analysis | Cat 0–6 | — | MECE completeness gap identification |
| H | Health Check | Cat 5 | Cat 1 | Context health (Reporter) |
| I | Integration Test | Cat 3, 4 | Cat 2 | Integration testing |
| J | Policy Gate | Cat 3 (Static) | Cat 5 | 10-check policy regression (Judge) |
| K | Intent Review | Cat 0 | Cat 6 | Human intent validation + delivery acceptance |

> **Axis K** is new in v4.0 — covers the human-bookend categories (Cat 0 + Cat 6) that Axes A-J did not address.

---

## §12. Completion Trajectory

```
Doc:  v1.0 → v2.0 → v3.0 → v4.0 → v5.0 → v5.1 → v3.0(merge) → v4.0(this)
Sys:   60%  →  72% →  80% → 86.4%→  97% →  97%  →   70%       →  66.1%
Tier:   —   →   —  →   —  →  —   →   —  →  —    →   70%       →  66.1%
                                                      (7-cat, honest)

Note: v4.0 score (66.1%) lower than v3.0 (70.0%) — reflects addition of Cat 0 + Cat 6 (new, T0/T1).
This is a more accurate picture, not regression.

P0+P1 implementation → ~79%
P0+P2 implementation → ~85%
All T0 resolved       → ~96.4%
```

---

## §13. References

The following files are cited verbatim by this document. All paths relative to project root (P:\).

| Reference | Path | Role |
|:----------|:-----|:-----|
| PROTOCOL.md | `.\PROTOCOL.md` | Consensus rules, session rules, §P-* and §M-* sections |
| CONVENTION.md | `.\CONVENTION.md` | Coding conventions, Axis templates |
| config.json | `.\_sys\gemini\config.json` | Live parameter registry (authoritative) |
| hub.py | `.\_sys\core\hub.py` | IPC hub, enforcement implementation |
| check_policy.py | `.\_sys\checks\check_policy.py` | Axis-J static policy checks |
| check_health.py | `.\_sys\checks\check_health.py` | Axis-H context health monitoring |
| msg.bat | `.\_sys\cli\msg.bat` | P2P messaging entrypoint |
| CLAUDE.md (global) | `.\_sys\claude\config\CLAUDE.md` | CC global instructions (R:10, collab protocol) |
| GEMINI.md | `.\_sys\gemini\GEMINI.md` | GC global instructions (symmetric to CLAUDE.md) |
| TAXONOMY_v3.md | `.\_sys\docs\TAXONOMY_v3.md` | Superseded version — READ-ONLY, preserved |
