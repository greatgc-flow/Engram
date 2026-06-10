# MECE Taxonomy v5.0 — AI-Assisted Development: Governance Framework
### Universal Taxonomy + Measurement Framework — Workspace-Independent

> **Version**: 5.0 | **Date**: 2026-06-05 | **Review Rounds**: 4 rounds (CC+GC, full-consensus protocol)
> **Supersedes**: TAXONOMY_v4.md (kept READ-ONLY)
> **Audience**: Any team building or operating an AI-assisted software development system.
> **Workspace independence**: This document's main body contains NO references to specific tools,
> file paths, or proprietary implementations. All implementation-specific details are in **Appendix A**.

---

## §0. How to Read This Document

This taxonomy defines the **governance layer** of AI-assisted software development — the meta-system
that ensures AI agents collaborate reliably, maintain context, enforce policy, and deliver to humans.

**Two reading modes:**
- **Universal mode** (§1–§10): Read the main body only. Applicable to any AI orchestration system.
- **Implementation mode** (§1–§10 + Appendix A): Add the Appendix for concrete commands, file paths,
  and current state of a specific reference implementation (Windows Portable Sandbox / CC+GC).

**Document structure at a glance:**

| Section | Content |
|:--------|:--------|
| §1 | Scope, Measurement Framework, Maturity Tiers |
| §2 | Human-in-Loop Lifecycle (7-category cycle) |
| §3 | Full MECE Taxonomy Tree (all 43 items, conceptual) |
| §4 | Universal KPI & Measurement Matrix |
| §5 | Architectural Trade-offs (T1–T21) |
| §5.5 | Logical Contradictions (C1–C6) |
| §6 | Governance Parameter Catalogue (22 universal parameters) |
| §7 | Governance Maturity Scoring Model |
| §8 | Gap Analysis Log |
| §9 | Implementation Roadmap |
| §10 | Axis Framework |
| Appendix A | Reference Implementation (CC+GC Windows Sandbox) |

---

## §1. Scope & Universal Principles

### §1.1 Scope Declaration

**In scope — Governance layer:**
Context lifecycle management, multi-agent consensus protocols, policy enforcement, environment
portability, operational observability, human intent capture, delivery validation, security,
rollback/recovery, learning loops, and economic governance of compute resources.

**Out of scope — Application layer:**
The target application's business logic, domain models, UI/UX design, or deployment pipelines.
This taxonomy governs HOW AI agents collaborate to build applications, not WHAT they build.

**Definitions used throughout this document:**

| Term | Definition |
|:-----|:-----------|
| **AI Node** | Any AI agent participating in the system (e.g., a language model, a coding assistant) |
| **Human** | The human operator who defines intent, approves major decisions, and accepts deliverables |
| **Session** | A bounded unit of collaborative work with a defined start, execution, and delivery phase |
| **Directive** | A formally structured task assignment from one node to another |
| **Consensus** | A formally recorded agreement among all active nodes on a decision |
| **Handoff** | A structured artifact that carries session state to the next session or node |
| **Context** | The active working memory available to an AI node during a session |
| **Compute Budget** | The total allowed resource consumption (tokens, API calls) per time period |

### §1.2 Measurement Framework

#### Maturity Type B — Binary / Structural
Policy, process, or structural **existence** is the key metric. No continuous monitoring needed.

| Tier | Achievement Criterion | Score |
|:----:|:---------------------|:-----:|
| T0 | Not defined | 0% |
| T1 | Draft policy or document exists | 50% |
| **T2** | **Enforced by automated check or system constraint** | **100%** |

#### Maturity Type C — Continuous / Operational
Items requiring ongoing measurement and active monitoring.

| Tier | Achievement Criterion | Score |
|:----:|:---------------------|:-----:|
| T0 | Not defined | 0% |
| T1 | Threshold or definition documented | 25% |
| T2 | Manual check possible; implementation exists | 50% |
| T3 | Automated check or script exists | 75% |
| **T4** | **Active monitoring + auto-alert on threshold breach** | **100%** |

> **Scoring rule**: Item Score = `min(Current Tier / Target Tier, 1.0)`. If current exceeds target, score = 1.00.

#### Measurement Failure Response (scales with collaboration depth)

> **Note**: "Depth" in this table refers to the `collaboration_depth` parameter defined in §6.

| Collaboration Depth | Tier 3/4 failure action |
|:-------------------:|:------------------------|
| Maximum (e.g., Depth 10) | **HALT + ESCALATE** to human gate |
| Medium (e.g., Depth 5–8) | **WARN + continue** — log to metrics file |
| Minimal (e.g., Depth 0–3) | **LOG only** — no interruption |

### §1.3 Abstraction Principle

This taxonomy uses **universal parameter names** and **abstract measurement criteria**.
Implementers must map these to concrete variables in their specific architecture.
The reference mapping for one implementation (CC+GC sandbox) is provided in Appendix A.2.

---

## §2. Human-in-Loop Lifecycle

The 7 governance categories form a **closed feedback cycle**. Human operators are the first and
last step of each work cycle. The categories are ordered by lifecycle phase:

```
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────────────┐   ║
║  │  Cat 0  │────►│  Cat 4  │────►│  Cat 1  │────►│     Cat 2       │   ║
║  │ Intent  │     │  Env.   │     │ Context │     │  Collaboration  │   ║
║  └─────────┘     └─────────┘     └─────────┘     └────────┬────────┘   ║
║       ▲                                                     │           ║
║       │                                                     ▼           ║
║  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────────────┐   ║
║  │  Cat 6  │◄────│  Cat 5  │◄────│  Cat 3  │◄────│     Cat 3       │   ║
║  │Delivery │     │  Ops.   │     │Integrity│     │  (continued)    │   ║
║  └─────────┘     └─────────┘     └─────────┘     └─────────────────┘   ║
║       │                                                                  ║
║       └─── Human reviews deliverable → defines next intent ─────────►  ║
║                                                         [back to Cat 0] ║
╚══════════════════════════════════════════════════════════════════════════╝
```

**Cycle Rationale:**
- **Cat 0** — Human defines what to build (entry point of every cycle)
- **Cat 4** — Ensure the runtime environment is ready before any cognitive work
- **Cat 1** — Orient AI agents within session context
- **Cat 2** — Execute tasks with multi-agent consensus
- **Cat 3** — Validate outputs, enforce policy, handle errors, learn from failures
- **Cat 5** — Monitor resources, control execution, manage compute economy
- **Cat 6** — Deliver to human, get explicit acceptance, feed lessons into next cycle

---

## §3. Full MECE Taxonomy Tree (43 Items)

> **Legend**: `[Type | Target Tier]` — B=Binary (T0–T2), C=Continuous (T0–T4)
> Items are ordered by Human-in-Loop lifecycle phase (Cat 0 → Cat 4 → Cat 1 → Cat 2 → Cat 3 → Cat 5 → Cat 6).

```
AI-Assisted Development: Governance Framework
│
├─ Cat 0: Human Intent & Kickoff  [Weight: 8%]
│  The human-facing entry gate. Every work cycle begins here.
│  4 items.
│  │
│  ├── 0-1: Structured Intent Capture  [B | T2]
│  │   Every task MUST be initiated with a formally structured statement of Goal,
│  │   Scope boundary, and Constraints before any AI execution begins.
│  │   ├── 0-1-1: Goal statement — one sentence describing desired outcome
│  │   ├── 0-1-2: Scope bounding — explicit MVP boundary vs. deferred scope
│  │   └── 0-1-3: Constraint identification — time, technology, budget, non-goals
│  │
│  ├── 0-2: Success Criteria Definition  [B | T2]
│  │   Completion criteria MUST be human-verifiable and defined before execution starts.
│  │   ├── 0-2-1: Acceptance criteria — conditions a human can check (not "AI believes done")
│  │   ├── 0-2-2: Quality thresholds — measurable quality bars (coverage %, latency, etc.)
│  │   └── 0-2-3: Delivery format — file path, output schema, or artifact type
│  │
│  ├── 0-3: Clarification Protocol  [C | T3]
│  │   AI agents MUST surface ambiguities before multi-step changes; humans respond
│  │   within a defined timeout. Max clarification rounds is bounded.
│  │   ├── 0-3-1: Ambiguity detection — AI identifies ≥1 unclear requirement → asks
│  │   ├── 0-3-2: Turn limit — at most `clarification_max_turns` rounds
│  │   └── 0-3-3: Intent confirmation — explicit human acknowledgment before multi-file execution
│  │
│  └── 0-4: Continuous Intent Alignment Monitoring  [B | T2]
│      During multi-step execution, the system MUST periodically verify ongoing
│      actions remain aligned with the original human intent baseline.
│      ├── 0-4-1: Periodic re-verification — re-check alignment at defined milestones
│      ├── 0-4-2: Drift detection — heuristics to flag when actions diverge from Cat 0 goals
│      └── 0-4-3: Escalation — ambiguity above threshold → human gate before proceeding
│
├─ Cat 4: Environment Portability  [Weight: 13%]
│  Infrastructure and runtime prerequisites for any AI agent to operate.
│  Must be established before cognitive work (Cat 1) begins.
│  8 items.
│  │
│  ├── 4-1: Runtime Environment  [C | T3]
│  │   All runtime dependencies MUST be self-contained; no host system state assumed.
│  │   ├── 4-1-1: Language runtime isolation — dependencies isolated from host (e.g., virtual environments)
│  │   ├── 4-1-2: Encoding consistency — character encoding explicitly set system-wide
│  │   ├── 4-1-3: Package manager isolation — package installs scoped to project, not global
│  │   ├── 4-1-4: Environment variable scoping — per-agent env vars isolated
│  │   └── 4-1-5: Zero-config hardening — execution policy meets minimum security baseline
│  │
│  ├── 4-2: Installation & Deployment  [C | T3]
│  │   A single bootstrap command MUST fully reconstruct the environment from scratch.
│  │   ├── 4-2-1: Zero-base bootstrap — one command = full environment reconstruction
│  │   ├── 4-2-2: Dependency bootstrapping — all tools and packages auto-installed
│  │   ├── 4-2-3: Smoke testing — post-install validation confirms environment health
│  │   └── 4-2-4: Parallel-safe file naming — prevents naming collisions in concurrent setups
│  │
│  ├── 4-3: Infrastructure Abstraction  [C | T3]
│  │   IPC, messaging, and shared state MUST be decoupled from node identity.
│  │   ├── 4-3-1: Technology-neutral IPC — message broker decouples nodes from transport
│  │   ├── 4-3-2: Shared state layer — node-independent state accessible to all agents
│  │   ├── 4-3-3: Unified messaging interface — single entry point for all P2P messages
│  │   └── 4-3-4: Node heartbeat — liveness detection; absent nodes auto-abstain
│  │
│  ├── 4-4: Version Management  [B | T2]
│  │   All protocol and schema versions MUST be tracked; version mismatches MUST be detectable.
│  │   ├── 4-4-1: Protocol versioning — all governance docs carry explicit version tags
│  │   ├── 4-4-2: Changelog maintenance — every version change documented
│  │   └── 4-4-3: Version format enforcement — standardized tag format (e.g., vX.Y)
│  │
│  ├── 4-5: Platform Independence  [C | T3]
│  │   No absolute paths or OS-specific constructs in any committed artifact.
│  │   ├── 4-5-1: No hardcoded paths — all paths relative or environment-variable-based
│  │   ├── 4-5-2: Drive/mount abstraction — portable across OS and mount points
│  │   └── 4-5-3: Cross-platform path API — use platform-agnostic path libraries
│  │
│  ├── 4-6: Node Onboarding  [B | T2]
│  │   Any new AI node MUST be onboardable without manual human intervention beyond registration.
│  │   ├── 4-6-1: Registration checklist — defined fields required before a node may vote
│  │   ├── 4-6-2: Required loading — new node must ingest defined governance context
│  │   └── 4-6-3: Resilience mechanics — heartbeat-based auto-abstain; re-sync on reconnect
│  │
│  ├── 4-7: Node Capability Profiling  [C | T2]
│  │   Every active AI node MUST have a formal capability profile (context limit, tool access,
│  │   specialization) consulted before task routing.
│  │   ├── 4-7-1: Standardized profile schema — required fields: context_limit, tools[], specialization[]
│  │   ├── 4-7-2: Dynamic capability discovery — profile updated on node state change
│  │   └── 4-7-3: Profile-aware routing — task delegation MUST check target node's profile first
│  │
│  └── 4-8: Foundation Model Lifecycle Governance  [C | T3]
│      Transitions of the underlying AI model MUST trigger re-validation of capability
│      assumptions and behavioral compliance tests.
│      ├── 4-8-1: Model version pinning — active model version recorded in configuration
│      ├── 4-8-2: Behavioral regression suite — mandatory test run before model upgrade
│      └── 4-8-3: Rollback procedures — prior model version recoverable within defined window
│
├─ Cat 1: Cognitive Continuity  [Weight: 17%]
│  Ensures AI agents maintain coherent, persistent awareness across sessions.
│  5 items.
│  │
│  ├── 1-1: Context Lifecycle Management  [C | T4]
│  │   Active context size MUST be monitored; thresholds trigger managed pruning to prevent
│  │   cognitive degradation.
│  │   ├── 1-1-1: Size tracking — continuous measurement against warn/critical thresholds
│  │   ├── 1-1-2: Session state rolling — completed items archived; live state kept minimal
│  │   └── 1-1-3: Context pruning — resolved items expire via TTL scoring mechanism
│  │       Score = (priority_level × 2) − age_in_days; negative score → archive candidate
│  │
│  ├── 1-2: Session Continuity  [B | T2]
│  │   Every session MUST produce a machine-readable handoff artifact enabling seamless
│  │   resumption by any node or successor session.
│  │   ├── 1-2-1: Scoped session workspace — isolated per-session directory with unique ID
│  │   ├── 1-2-2: Per-node summaries — each node writes a bounded (<4 KB) state summary
│  │   ├── 1-2-3: Re-orientation protocol — agent reads handoff before beginning any work
│  │   └── 1-2-4: Emergency handoff schema — minimal viable fields for crash recovery
│  │       Required: executive_summary / technical_state / strategy_for_next_session
│  │
│  ├── 1-3: Memory Persistence  [C | T4]
│  │   Learnings and decisions MUST persist across session boundaries in a queryable,
│  │   structured form. Scope: cross-session (weeks to months).
│  │   ├── 1-3-1: Long-term memory store — persistent file-based memory per project
│  │   ├── 1-3-2: Memory compaction — periodic pruning of stale or superseded entries
│  │   ├── 1-3-3: Symmetric sync — all nodes share access to the same memory corpus
│  │   └── 1-3-4: Memory taxonomy — typed entries (user profile / feedback / project / reference)
│  │
│  ├── 1-4: Instruction Design & Efficacy  [B | T2]
│  │   AI agents MUST receive persistent, structured instructions that survive context resets,
│  │   and the quality of those instructions MUST be periodically measured and improved.
│  │   ├── 1-4-1: Global agent configuration — persistent baseline instruction set per agent
│  │   ├── 1-4-2: Project-level overrides — project-specific instructions take precedence
│  │   ├── 1-4-3: Query efficiency — instructions formatted for maximum information density
│  │   ├── 1-4-4: Task template library — structured templates for recurring task types
│  │   └── 1-4-5: Instruction efficacy tracking — periodic audit of misinterpretation frequency
│  │       Metric: % of sessions requiring mid-session correction due to instruction ambiguity
│  │
│  └── 1-5: Persistent Domain Knowledge Management  [C | T3]
│      A structured knowledge base MUST persist domain-specific decisions, architectural
│      patterns, and business rules beyond individual session boundaries.
│      ├── 1-5-1: Knowledge extraction — automated identification of reusable domain facts
│      ├── 1-5-2: Structured storage schema — queryable format (not raw session logs)
│      ├── 1-5-3: Contextual retrieval — knowledge injected into agent context on relevance match
│      └── 1-5-4: Obsolescence protocol — outdated entries flagged/pruned on schedule
│
├─ Cat 2: Collaboration Governance  [Weight: 22%]
│  The protocols by which multiple AI nodes and humans make decisions together.
│  6 items.
│  │
│  ├── 2-1: Consensus Protocol  [C | T3]
│  │   All cross-agent decisions MUST follow a documented Propose → Vote → Finalize cycle.
│  │   ├── 2-1-1: Propose-Vote-Finalize cycle — explicit state machine for each decision
│  │   ├── 2-1-2: Quorum rules — majority threshold for general decisions; unanimity at max depth
│  │   ├── 2-1-3: Final Call mechanism — decisions above defined depth require explicit final ACK
│  │   └── 2-1-4: Consensus history — all finalized decisions recorded with rationale
│  │
│  ├── 2-2: Division of Labor  [C | T3]
│  │   Task routing MUST be based on node capability profiles (see 4-7); not arbitrary assignment.
│  │   ├── 2-2-1: Directive envelope — standard JSON schema for all inter-node task assignments
│  │   ├── 2-2-2: Capability-based routing — routing checks 4-7 profile before assignment
│  │   ├── 2-2-3: Parallel vs. sequential policy — async allowed when impact ranges non-overlapping
│  │   └── 2-2-4: Result aggregation — cross-node output verification before finalization
│  │
│  ├── 2-3: Conflict Resolution  [B | T2]
│  │   Every unresolvable conflict MUST have a defined escalation path to human arbitration.
│  │   ├── 2-3-1: Deadlock handling — 2+ consecutive disagreement rounds → defined resolution
│  │   ├── 2-3-2: Human gate escalation — any node may invoke human veto at any time
│  │   ├── 2-3-3: Repeated-failure halt — N consecutive identical errors → HALT, human consult
│  │   └── 2-3-4: Stalled round cleanup — auto-expiry of rounds exceeding timeout threshold
│  │
│  ├── 2-4: Node Management  [C | T3]
│  │   Any node with voting rights MUST be registered; collaboration depth MUST be configurable.
│  │   ├── 2-4-1: Node registry — authoritative list of registered nodes and their roles
│  │   ├── 2-4-2: Collaboration depth — configurable scale (0=full autonomy, N=full consensus)
│  │   ├── 2-4-3: Dynamic node addition — new node gains voting rights upon registration
│  │   └── 2-4-4: Re-sync on reconnect — returning node digests state delta, rejoins voting
│  │
│  ├── 2-5: Transparency & Communication  [C | T3]
│  │   All inter-agent communication MUST be visible to all nodes; no private channels.
│  │   ├── 2-5-1: No private channels — all messages broadcast to the full node set
│  │   ├── 2-5-2: Structured message prefixes — message type indicated in header
│  │   └── 2-5-3: Response format standard — each node's output follows consistent structure
│  │
│  └── 2-6: Decision Attribution  [C | T4]
│      Every finalized directive MUST record who proposed it, the rationale, and affected trade-offs.
│      ├── 2-6-1: Proposer & opposer logging — each vote records node ID and stance
│      ├── 2-6-2: Drift detection — dissent ratio exceeding threshold triggers audit
│      └── 2-6-3: Decision weight tracking — high-depth decisions recorded with T-number reference
│
├─ Cat 3: System Integrity  [Weight: 28%]
│  The highest-weighted category: failure here blocks all execution.
│  9 items.
│  │
│  ├── 3-1: Security & Trust  [B | T2]
│  │   AI nodes MUST NOT access credentials; all inputs MUST be sanitized.
│  │   ├── 3-1-1: Non-interference principle — agents cannot modify each other's configuration
│  │   ├── 3-1-2: Credential isolation — authentication files inaccessible to AI nodes
│  │   ├── 3-1-3: Input sanitization — all external inputs validated (injection prevention)
│  │   ├── 3-1-4: Protected file list — critical governance docs require elevated consensus to modify
│  │   └── 3-1-5: Secret injection protocol — API keys via env vars only; never in logs or commits
│  │
│  ├── 3-2: Policy Enforcement  [C | T3]
│  │   All governance rules MUST be automatically checkable; violations MUST block execution.
│  │   ├── 3-2-1: Static policy gate — automated N-check suite run before each commit/merge
│  │   ├── 3-2-2: Policy-code consistency — governance docs and enforcement code kept in sync
│  │   ├── 3-2-3: Pre-commit hook — policy gate runs automatically on every commit attempt
│  │   └── 3-2-4: Exit code gate — PASS(0) or FAIL(1) — FAIL blocks execution
│  │
│  ├── 3-3: Change Management  [C | T3]
│  │   Every change MUST be tagged, committed conventionally, and impact-analyzed.
│  │   ├── 3-3-1: MECE change tagging — every change labeled: added / deleted / changed / retained
│  │   ├── 3-3-2: Conventional commits — structured commit message format enforced
│  │   ├── 3-3-3: Branch discipline — large changes isolated to branches before merge
│  │   └── 3-3-4: Impact analysis gate — blast-radius estimation required before multi-file change
│  │
│  ├── 3-4: Output Validation  [C | T3]
│  │   AI-generated output MUST satisfy schema, size, and confidence constraints before delivery.
│  │   ├── 3-4-1: Output schema validation — structured output verified against defined schema
│  │   ├── 3-4-2: Size guard — output file size / include depth bounded
│  │   ├── 3-4-3: Orchestrator script protection — core scripts validated before overwrite
│  │   ├── 3-4-4: Refusal detection — AI refusals flagged and routed to human gate
│  │   └── 3-4-5: Confidence threshold — output below confidence floor → human review required
│  │       Confidence scale: file fully read = 100; partial inference = 50; speculation = 0–49
│  │
│  ├── 3-5: Error Classification  [B | T2]
│  │   All errors MUST be classified by severity with defined response protocols per class.
│  │   ├── 3-5-1: Severity taxonomy — P0 (execution-blocking) / P1 (critical) / WARN / INFO
│  │   ├── 3-5-2: Structured error reporting — standard fields: severity, location, context, action
│  │   └── 3-5-3: Repeated-error halt — P0 occurring N times consecutively → HALT
│  │
│  ├── 3-6: Rollback & Recovery  [C | T3]
│  │   Any failed change MUST be undoable to a known-good state within `max_recovery_depth` steps.
│  │   ├── 3-6-1: Checkpoint-based rollback — periodic snapshots at natural save points
│  │   ├── 3-6-2: Recovery depth limit — bounded number of recoverable checkpoints
│  │   └── 3-6-3: State migration — shared state objects carry version field; migration script present
│  │
│  ├── 3-7: Behavioral Compliance Tests  [C | T3]
│  │   AI agent compliance with governance rules MUST be verifiable by runtime log analysis.
│  │   ├── 3-7-1: Runtime log parsing — governance events extracted from execution logs
│  │   ├── 3-7-2: Scenario test suite — explicit test cases for consensus, depth change, halt
│  │   ├── 3-7-3: Parameter validation — governance config validated at load time
│  │   └── 3-7-4: Compute budget per task class — defined upper bounds by task complexity tier
│  │
│  ├── 3-8: Post-Mortem & Learning Loop  [C | T4]
│  │   Every P0/P1 incident MUST generate a post-mortem; repeated failures lock the task
│  │   until root cause is resolved and governance policy updated.
│  │   ├── 3-8-1: Automated PM draft generation — incident triggers structured template creation
│  │   │   Template: Incident / Root Cause (5-Why) / Timeline / Category / Prevention / Policy
│  │   ├── 3-8-2: Policy revision proposal — 5-Why output fed into governance doc revision
│  │   └── 3-8-3: Recurrence lock — same failure N times → task locked until Kaizen complete
│  │
│  └── 3-9: Immutable Audit Logging  [C | T2]
│      All agent state changes, consensus decisions, and outputs MUST be recorded in
│      an append-only, tamper-evident audit log for compliance and retrospective analysis.
│      ├── 3-9-1: Comprehensive action capture — every state-mutating action logged
│      ├── 3-9-2: Append-only guarantee — log entries cannot be modified or deleted
│      ├── 3-9-3: Retention policy — log rotation/archival schedule defined
│      └── 3-9-4: Structured queryability — logs indexed for audit queries
│
├─ Cat 5: Operations & Control  [Weight: 7%]
│  Ongoing monitoring, resource control, and system health management.
│  8 items.
│  │
│  ├── 5-1: Governance Parameter Registry  [C | T3]
│  │   All behavioral thresholds MUST be stored in a single versioned, structured registry.
│  │   (See §6 for the full parameter catalogue.)
│  │   ├── 5-1-1: Flat+metadata format — parameters grouped by category with metadata
│  │   ├── 5-1-2: Complete coverage — every configurable threshold stored here, nowhere else
│  │   └── 5-1-3: Integrity check — key count and section membership validated at load time
│  │
│  ├── 5-2: Parameter Validation  [C | T3]
│  │   All parameters MUST be range-validated at load time; out-of-range values MUST fail.
│  │   ├── 5-2-1: Load-time schema check — parameter types and ranges validated on startup
│  │   ├── 5-2-2: Range enforcement — value outside defined range → startup failure
│  │   └── 5-2-3: Section membership check — each parameter assigned to exactly one section
│  │
│  ├── 5-3: Observability  [C | T4]
│  │   System health MUST be continuously measurable and queryable without interrupting execution.
│  │   ├── 5-3-1: Context health monitoring — real-time context size vs. threshold bands
│  │   ├── 5-3-2: Asynchronous event handling — out-of-band events processed without blocking
│  │   └── 5-3-3: Collaboration metrics — current depth level, consensus success rate tracked
│  │
│  ├── 5-4: System Health Dashboard  [C | T3]
│  │   Aggregated health state MUST be viewable in a single human-readable status line.
│  │   ├── 5-4-1: Session header format — ROOM:{id}|DEPTH:D{n}|HEALTH:{size}({band})
│  │   ├── 5-4-2: Metrics aggregation — policy compliance %, consensus success %
│  │   ├── 5-4-3: Persistent metric store — metrics written to durable storage at defined interval
│  │   └── 5-4-4: Dashboard specification — formal schema for rendering all metrics
│  │
│  ├── 5-5: Active Control Loop  [C | T4]
│  │   The system MUST proactively prevent resource exhaustion and health degradation
│  │   via automated circuit-breaker actions.
│  │   ├── 5-5-1: Lock-safety check — no active writes before control action
│  │   ├── 5-5-2: Critical health trigger — critical band entry → auto-checkpoint + depth reduction
│  │   ├── 5-5-3: Budget control — near-ceiling spend triggers alert; ceiling-hit forces minimal depth
│  │   ├── 5-5-4: SLA escalation — consecutive timeouts → auto-escalate to human
│  │   └── 5-5-5: Safety guard — active control disabled by default (`active_control_enabled = 0`)
│  │
│  ├── 5-6: Economic & Quota Governance  [C | T4]
│  │   Compute spend MUST be tracked, forecasted, and bounded; ROI MUST be measurable.
│  │   ├── 5-6-1: Compute ROI — finalized directives + merged PRs / normalized compute units
│  │   ├── 5-6-2: Budget management — pre-defined alert and hard-ceiling thresholds
│  │   ├── 5-6-3: Runway forecasting — projected depletion time based on burn rate
│  │   └── 5-6-4: Delegation cost rules — repeated identical searches trigger delegation to reduce waste
│  │
│  ├── 5-7: Concurrent Session Management  [C | T2]
│  │   When multiple parallel sessions access shared state, the system MUST provide
│  │   conflict detection, locking, and merge resolution.
│  │   ├── 5-7-1: Granular state locking — file-level or object-level locks, not workspace-wide
│  │   ├── 5-7-2: Conflict detection — overlapping edits detected before commit
│  │   └── 5-7-3: Merge / deadlock resolution — automated merge where safe; escalate otherwise
│  │
│  └── 5-8: Degraded Mode & Fallback Protocols  [C | T3]
│      When critical components fail or resource limits are reached, the system MUST execute
│      predefined degraded-mode behaviors that maintain minimum viable operation.
│      ├── 5-8-1: Failure detection monitors — component liveness and quota status watched
│      ├── 5-8-2: Graceful degradation strategies — e.g., read-only mode, human-only override
│      └── 5-8-3: Reintegration procedures — auto-reconnect and state reconciliation on recovery
│
└─ Cat 6: Product Delivery & Validation  [Weight: 5%]
   The human-facing exit gate. Every work cycle ends with explicit human acceptance.
   Feeds lessons back into Cat 0 of the next cycle.
   3 items.
   │
   ├── 6-1: Artifact Assembly  [B | T2]
   │   Every deliverable MUST be a discrete file artifact — no conversation-only outputs.
   │   ├── 6-1-1: Output format compliance — artifact matches Cat 0-2-3 delivery format
   │   ├── 6-1-2: Completeness check — all Cat 0-2-1 acceptance criteria addressed
   │   └── 6-1-3: File output mandate — all deliverables written as files (loss prevention)
   │
   ├── 6-2: User Acceptance Test  [C | T3]
   │   Human MUST explicitly verify the primary use case before task closure.
   │   ├── 6-2-1: Explicit acceptance gate — `delivery_ack_required = 1` → human ACK required
   │   ├── 6-2-2: Regression check — no previously working feature broken
   │   └── 6-2-3: Scenario coverage — golden path + ≥1 edge case verified
   │
   └── 6-3: Delivery Handoff & Feedback Loop  [C | T3]
       Session state MUST be archived on completion; lessons feed the next cycle.
       ├── 6-3-1: Session archive — save + close procedure run on task completion
       ├── 6-3-2: Lessons learned routing — incidents → 3-8 Post-Mortem
       ├── 6-3-3: Next intent seeding — handoff artifact includes next-session context
       └── 6-3-4: Feedback specificity measurement — human corrections rated for specificity
           Metric: % of corrections including actionable criteria vs. vague redirects
           [loop back → Cat 0 of next session]
```

---

## §4. Universal Measurement & KPI Matrix

Measurement criteria are expressed as **universal KPIs** — tool-agnostic ratios and audit questions.
Implementation-specific commands are in Appendix A.3.

### Cat 0: Human Intent & Kickoff

| ID | Item | Type | Target | KPI Metric | Measurement Method | 100% Criterion |
|:---|:-----|:----:|:------:|:-----------|:-------------------|:---------------|
| 0-1 | Structured Intent Capture | B | T2 | % of tasks initiated with Goal/Scope/Constraint schema | Review session initiation logs | ≥95% of multi-file tasks have all 3 fields present |
| 0-2 | Success Criteria | B | T2 | % of tasks with human-verifiable acceptance criteria | Review handoff start state | ≥95% of tasks have ≥1 checkable criterion |
| 0-3 | Clarification Protocol | C | T3 | Mean turns to clarification (MTTC) | Count clarification rounds per task | MTTC ≤ `clarification_max_turns`; 0 tasks proceeding with known ambiguity |
| 0-4 | Intent Alignment Monitoring | B | T2 | % of multi-step tasks with mid-execution re-verification | Audit execution logs | 100% of tasks > N steps re-verify intent at defined checkpoints |

### Cat 1: Cognitive Continuity

| ID | Item | Type | Target | KPI Metric | Measurement Method | 100% Criterion |
|:---|:-----|:----:|:------:|:-----------|:-------------------|:---------------|
| 1-1 | Context Lifecycle | C | T4 | Context utilization ratio (%) vs. warn threshold | Continuous size monitoring | Normal band ≥95% of session time; critical band entry 0 per 48h |
| 1-2 | Session Continuity | B | T2 | Handoff artifact completeness | Check required section headers | ≤2 KB; all 6 required sections present |
| 1-3 | Memory Persistence | C | T4 | Stale memory entry count | Periodic compaction audit | Stale = 0; compaction run within `memory_compaction_interval` |
| 1-4 | Instruction Design & Efficacy | B | T2 | % of sessions requiring mid-session correction due to instruction ambiguity | Session correction log | ≤5% correction rate; global + project config both present |
| 1-5 | Domain Knowledge Mgmt | C | T3 | % of domain-context sessions actively retrieving cross-session knowledge | Knowledge retrieval log | ≥80% retrieval rate where domain context is needed |

### Cat 2: Collaboration Governance

| ID | Item | Type | Target | KPI Metric | Measurement Method | 100% Criterion |
|:---|:-----|:----:|:------:|:-----------|:-------------------|:---------------|
| 2-1 | Consensus Protocol | C | T3 | % of directives finalized via documented propose-vote-finalize | Consensus log audit | ≥99% of cross-agent decisions follow protocol |
| 2-2 | Division of Labor | C | T3 | Node utilization balance (Gini coefficient of task distribution) | Task log distribution | Gini ≤ 0.3; ≥2 nodes active per session |
| 2-3 | Conflict Resolution | B | T2 | % of deadlocks resolved within `consensus_timeout` | Deadlock event log | 100% resolved; escalation path code present |
| 2-4 | Node Management | C | T3 | % of collaboration depth changes documented with rationale | Config change log | 100% depth changes logged; all nodes symmetric |
| 2-5 | Transparency | C | T3 | Count of private-channel messages detected | Communication audit | 0 private messages; all messages broadcast |
| 2-6 | Decision Attribution | C | T4 | % of finalized decisions with proposer + rationale + trade-off reference | Consensus history audit | 100% attribution; drift detection active |

### Cat 3: System Integrity

| ID | Item | Type | Target | KPI Metric | Measurement Method | 100% Criterion |
|:---|:-----|:----:|:------:|:-----------|:-------------------|:---------------|
| 3-1 | Security & Trust | B | T2 | Policy gate check result for security rules | Static policy suite | All security checks PASS; 0 credential exposures |
| 3-2 | Policy Enforcement | C | T3 | Policy gate exit code | Pre-commit gate | Exit 0; 0 FAILs; consistent with governance docs |
| 3-3 | Change Management | C | T3 | % of commits following conventional format | Commit log audit (last 20) | ≥95% conventional format; Axis impact gate present |
| 3-4 | Output Validation | C | T3 | % of AI outputs passing schema + confidence check | Output log | 0 schema violations; 0 sub-threshold confidence deliveries |
| 3-5 | Error Classification | B | T2 | % of errors with correct severity classification | Error log spot-check | P0/P1/WARN/INFO taxonomy documented; halt rule present |
| 3-6 | Rollback & Recovery | C | T3 | Count of available recovery checkpoints | Checkpoint inventory | ≥ `max_recovery_depth` checkpoints; state version field present |
| 3-7 | Behavioral Tests | C | T3 | % of governance directives → finalized (traceability) | Directive trace log | ≥95% traceability; 0 unauthorized modifications |
| 3-8 | Post-Mortem Loop | C | T4 | % of P0/P1 incidents generating post-mortem within SLA | Incident vs PM log | PM generation rate = 100%; 0 open orphans > 48h |
| 3-9 | Immutable Audit Log | C | T2 | % of state-mutating actions captured in append-only log | Log completeness audit | 100% capture rate; 0 deletions from log |

### Cat 4: Environment Portability

| ID | Item | Type | Target | KPI Metric | Measurement Method | 100% Criterion |
|:---|:-----|:----:|:------:|:-----------|:-------------------|:---------------|
| 4-1 | Runtime Environment | C | T3 | % of dependencies isolated from host | Environment audit | All deps in isolated scope; encoding explicitly set |
| 4-2 | Installation | C | T3 | Mean Time to Bootstrap (MTTB) from zero | Timed bootstrap test | MTTB ≤ 5 min; 0 manual steps |
| 4-3 | Infra Abstraction | C | T3 | IPC layer health check exit code | Hub status check | Exit 0; node registry valid |
| 4-4 | Version Management | B | T2 | % of governance docs with version tags | Document audit | 100% versioned; changelog current |
| 4-5 | Platform Independence | C | T3 | Count of hardcoded absolute paths in codebase | Static scan | 0 hardcoded paths |
| 4-6 | Node Onboarding | B | T2 | % of nodes registered per documented checklist | Node registry audit | 100% fields present per node; §onboarding protocol present |
| 4-7 | Node Capability Profiling | C | T2 | % of task delegations that checked target capability profile | Task routing log | ≥95% of delegations capability-verified |
| 4-8 | Model Lifecycle Governance | C | T3 | Boolean: regression suite present + required before model upgrade | Suite existence check | Suite exists; 0 model upgrades without suite pass |

### Cat 5: Operations & Control

| ID | Item | Type | Target | KPI Metric | Measurement Method | 100% Criterion |
|:---|:-----|:----:|:------:|:-----------|:-------------------|:---------------|
| 5-1 | Parameter Registry | C | T3 | % of configurable thresholds in registry vs. hardcoded | Registry audit | 0 hardcoded thresholds; all sections valid |
| 5-2 | Parameter Validation | C | T3 | Count of out-of-range parameter values at startup | Load-time check | 0 range violations; load fails on invalid |
| 5-3 | Observability | C | T4 | Health check availability (% of execution time) | Health endpoint uptime | 100% uptime; health bands defined and reported |
| 5-4 | Dashboard | C | T3 | Session header completeness | Header format check | All required fields present; metrics refreshed within interval |
| 5-5 | Active Control Loop | C | T4 | % of critical health events triggering automated response | Event vs response log | When enabled: 100% response rate; 0 unhandled critical events |
| 5-6 | Economic Governance | C | T4 | Compute ROI (decisions/PRs per budget unit) | Budget vs outcome log | ≤100% budget; 0 undetected pre-exhaustion events |
| 5-7 | Concurrent Sessions | C | T2 | % of concurrent write conflicts safely resolved | Conflict log | 100% resolved; 0 data loss events |
| 5-8 | Degraded Mode | C | T3 | % of defined failure modes with tested fallback | Failure mode inventory | 100% failure modes have fallback; 0 unhandled critical failures |

### Cat 6: Product Delivery & Validation

| ID | Item | Type | Target | KPI Metric | Measurement Method | 100% Criterion |
|:---|:-----|:----:|:------:|:-----------|:-------------------|:---------------|
| 6-1 | Artifact Assembly | B | T2 | % of deliverables present as files matching agreed format | Output audit | 100% file output; format matches Cat 0-2-3 |
| 6-2 | User Acceptance Test | C | T3 | First-pass acceptance rate (% accepted without rework) | Delivery ACK log | ≥90% first-pass; HUMAN_ACK recorded per task |
| 6-3 | Delivery Handoff & Feedback | C | T3 | % of sessions with structured next-session seeding | Handoff completeness | 100% archived; NEXT_SESSION section non-empty; ≥70% feedback specific |

---

## §5. Architectural Trade-offs (T1–T21)

Trade-offs represent parameter-manageable tensions. See §6 for parameter definitions.

| # | Dimension A | Dimension B | Control Parameter | Management |
|:--|:-----------|:-----------|:-----------------|:-----------|
| T1 | Zero-compute efficiency | Collaboration depth | `collaboration_depth` | Explicit scale |
| T2 | Context preservation | Processing speed | `context_warn_threshold` | Explicit threshold |
| T3 | Consensus accuracy | Response latency | `consensus_timeout` | Explicit duration |
| T4 | Autonomy | Safety | `collaboration_depth` | Anchored scale |
| T5 | Documentation richness | Compute cost | Language choice (dense) | Policy |
| T6 | Session continuity | Context freshness | `memory_compaction_interval` + `resolved_item_ttl` | Explicit durations |
| T7 | Portability | Platform optimization | Path abstraction mandate | Policy |
| T8 | Policy strictness | Development velocity | `final_call_threshold` | Explicit level |
| T10 | Security isolation | Collaboration convenience | Credential access policy | Policy |
| T11 | Node count (scalability) | Consensus complexity | Node registration policy | Policy |
| T12 | Pruning aggressiveness | Memory preservation | `resolved_item_ttl` | Explicit duration |
| T13 | Metric granularity | Storage I/O | `metrics_persist_interval` | Explicit interval |
| T14 | Forecast sensitivity | Alert fatigue | `forecast_alert_threshold` | Explicit % |
| T15 | Learning overhead | System evolution speed | Post-mortem cadence | Policy |
| T16 | Active automation | Human control | `active_control_enabled` | Boolean gate |
| T17 | Compute economy | Collaboration depth | `daily_compute_budget` + `collaboration_depth` | Dual control |
| T18 | Full rewrite (safe syntax, high cost) | Surgical patch (low cost, syntax risk) | Edit strategy preference | Practice |
| T19 | Human visual verification (blocks async) | AI automated testing (high compute) | Test strategy policy | Policy |
| T20 | Heuristic flexibility | Strict policy gates | `policy_bypass_floor` | Explicit floor |
| T21 | System specificity (high precision) | Universal portability | Audience declaration | Architecture |

> T9 absorbed into T6.

### Balance Metrics for Key Trade-offs

**T3 — Consensus Accuracy vs. Latency**

| Metric | How to Measure | Balance Signal |
|:-------|:--------------|:---------------|
| MTC (Mean Time to Consensus) | Time from Propose to Finalize | MTC ≤ `consensus_timeout` × 0.5 |
| Rejection Rate | ESCALATE count / total rounds | ≤ 10% |
| Signal | MTC rising = accuracy up; Rate rising = reconsider `collaboration_depth` |

**T17 — Compute Economy vs. Depth**

| Metric | How to Measure | Balance Signal |
|:-------|:--------------|:---------------|
| Budget Utilization | Daily spend / `daily_compute_budget` × 100 | < `budget_alert_threshold` |
| Rounds per Decision | Avg rounds per Finalized directive | ≤ 3 |
| Signal | High budget + low rounds = waste; High rounds → consider lowering depth |

---

## §5.5 Logical Contradictions (Non-Parameterizable)

Items here are **structurally contradictory** — no parameter can resolve them. Each requires an
acknowledged management strategy.

| # | Contradiction | Affected Items | Management Strategy |
|:--|:-------------|:--------------|:-------------------|
| C1 | **Collaboration verbosity vs. Context size**: Maximum depth mandates unlimited negotiation, guaranteeing context growth that violates the warn threshold. | Cat 1-1 vs Cat 2-1, 2-4 | Accepted. "Practical ceiling 98%" tolerates theoretical violations. `collaboration_depth` acts as relief valve — reduce for long sessions. |
| C2 | **"Zero-context usable" claim vs. Historical observability**: The document claims zero-context usability, but compute ROI (5-6) and Kaizen pattern detection (3-8) require historical data unavailable at session start. | §1.1 vs Cat 5-6, Cat 3-8 | Scoped. "Zero-context" applies to the **document** being self-explanatory, not the **system** operating without history. Runtime analytics require history. Clarified in §1.1. |
| C3 | **Active control loop vs. Human-in-Loop bookends**: The active control loop (5-5) can autonomously reduce `collaboration_depth` and trigger checkpoints — potentially overriding the human's intent gate (Cat 0) and delivery ACK (Cat 6). | Cat 5-5 vs Cat 0, Cat 6 | Constrained. `active_control_enabled = 0` by default. When enabled, the loop MUST NOT override the Cat 0 intent gate or Cat 6 delivery ACK. Human bookends are exempt from automated override. |
| C4 | **Audit log completeness vs. Context pruning**: Immutable logging (3-9) captures everything; aggressive pruning (1-1-3, 1-3-2) discards old data. Both cannot be maximized simultaneously. | Cat 3-9 vs Cat 1-1-3, 1-3-2 | Architectural. Audit logs MUST be stored in a separate, dedicated storage layer outside the session context buffer. Pruning rules apply only to the context layer, not the audit log layer. |
| C5 | **Degraded mode autonomy vs. Human intent timeout**: Degraded mode (5-8) may require heightened human intervention, but strict `intent_timeout` enforcement risks aborting safe operations prematurely. | Cat 5-8 vs Cat 0-3 (`intent_timeout`) | Overriding rule: degraded mode MUST dynamically extend `intent_timeout` to a defined safe-pause interval, bypassing the normal timeout only while degraded mode is active. |
| C6 | **Concurrent session velocity vs. State lock rigor**: Strict locking (5-7) ensures consistency but serializes operations, negating the speed advantage of concurrent sessions. | Cat 5-7 vs concurrent execution intent | Architectural. Implement optimistic concurrency with fine-grained locks (file-level, not workspace-level). Escalate only on actual conflicts, not pre-emptively. |

---

## §6. Governance Parameter Catalogue

22 universal parameters. See Appendix A.2 for workspace-specific name mappings and default values.

| Parameter | Type | Range | Meaning | Category | Trade-off |
|:----------|:----:|:-----:|:--------|:--------:|:---------:|
| `collaboration_depth` | int | 0–N | 0 = full autonomy; N = unanimous consent required | general | T1,T4,T17 |
| `consensus_timeout` | duration | 1–60 min | Max time per consensus round before auto-expiry | general | T3 |
| `final_call_threshold` | int | 0–N | Min depth at which a decision requires explicit "Final Call" | general | T8 |
| `daily_compute_budget` | int | 1k–∞ | Total compute units (tokens, API calls) per day | general | T17 |
| `task_delegation_threshold` | int | 1–20 | Repeated identical search N times → delegate to specialist | general | — |
| `policy_bypass_floor` | int | 0–N | Collaboration depth below this may bypass minor policy gates | general | T20 |
| `intent_timeout` | duration | 1 min–24h | Max wait for human intent clarification before escalate | cat0 | C5 |
| `clarification_max_turns` | int | 1–10 | Max AI clarification question rounds before proceeding | cat0 | — |
| `delivery_ack_required` | bool | 0/1 | Require explicit human ACK before task closure | cat0 | T16, C3 |
| `context_warn_threshold` | size | 100–1000 KB | Upper bound of normal context operation | cat1 | T2 |
| `context_critical_threshold` | size | 200–2000 KB | Threshold for degraded → critical transition | cat1 | T2 |
| `memory_compaction_interval` | duration | 1–30 days | Periodic long-term memory compaction cadence | cat1 | T6, T12 |
| `peer_review_min_interval` | duration | 1–60 min | Minimum time between peer AI reviews | cat1 | T1 |
| `resolved_item_ttl` | duration | 1–30 days | Completed items expire from session state after this | cat1 | T6, T12 |
| `active_item_ttl` | duration | 1–90 days | Open items expire from session state after this | cat1 | T6 |
| `dissent_drift_threshold` | % | 1–99 | Disagreement ratio triggering WARN + audit | cat2 | — |
| `max_recovery_depth` | int | 1–10 | Maximum number of recoverable checkpoints | cat3 | — |
| `confidence_floor` | % | 0–100 | AI confidence below this routes output to human review | cat3 | — |
| `metrics_persist_interval` | duration | 10s–1h | Metrics write cadence to durable storage | cat5 | T13 |
| `active_control_enabled` | bool | 0/1 | Enables automated circuit-breaker control loop (0=off) | cat5 | T16, C3 |
| `forecast_alert_threshold` | % | 1–99 | Compute usage forecast alert level | cat5 | T14 |
| `budget_alert_threshold` | % | 1–99 | Daily budget pre-exhaustion alert level | cat5 | T17 |

---

## §7. Governance Maturity Scoring Model

### Item Score

```
Item Score = min(Current Tier / Target Tier, 1.0)

Examples:
  Item targeting T4, currently at T2:  2 / 4 = 0.50
  Item targeting T2, currently at T3:  min(3/2, 1.0) = 1.00  ← capped
  Item targeting T4, currently at T0:  0 / 4 = 0.00
```

### Category Score

```
Category Score = arithmetic mean of all Item Scores in the category
```

### Root Health Score (Weighted)

```
Root = Σ (Category Weight × Category Score)

Weights:  Cat0=0.08, Cat1=0.17, Cat2=0.22, Cat3=0.28, Cat4=0.13, Cat5=0.07, Cat6=0.05

Weight rationale:
  Cat 3 (0.28): Highest — failure blocks all execution (survival condition)
  Cat 2 (0.22): Second — without governance, agents cannot collaborate
  Cat 1 (0.17): Third — without context, agents cannot reason
  Cat 4 (0.13): Fourth — without environment, nothing runs
  Cat 0 (0.08): Fifth — human entry point, but lightweight
  Cat 5 (0.07): Sixth — non-achievement = inefficiency (non-blocking)
  Cat 6 (0.05): Seventh — delivery layer, loop-closing but downstream
```

### "Done" Gate (6 simultaneous conditions)

| # | Condition | How to verify |
|:--|:---------|:--------------|
| ① | Static policy gate passes | Policy suite exits 0; 0 failures |
| ② | Health monitoring reports Normal band | Health check returns Normal status |
| ③ | Root Score ≥ 0.95 | Apply §7 formula |
| ④ | All Tier 3/4 KPIs at target | §4 Matrix — all 100% criteria met |
| ⑤ | All gaps resolved (G1–G20, G11 deferred acceptable) | §8 Gap Log |
| ⑥ | Zero open post-mortems | PM log shows 0 "status: open" items |

> See Appendix A.4 for the current state of the reference implementation against this gate.

---

## §8. Gap Analysis Log

| # | Gap Description | Location | Status |
|:--|:----------------|:---------|:-------|
| G1 | Instruction Design | 1-4 | ✅ Closed |
| G2 | Output Validation | 3-4 | ✅ Closed |
| G3 | Rollback Protocol | 3-6 | ✅ Closed |
| G4 | Error Classification | 3-5 | ✅ Closed |
| G5 | AI Behavioral Test Suite | 3-7 | ✅ Closed |
| G6 | Impact Analysis | 3-3-4 | ✅ Closed |
| G7 | Dashboard specification | 5-4-4 | 🔶 Spec document needed |
| G8 | Metrics aggregation | 5-4-2 | ✅ Closed |
| G9 | Node Onboarding | 4-6 | ✅ Closed |
| G10 | Parameter Validation | 5-2 | ✅ Closed |
| G11 | Async event handling | 5-3-2 | 🔶 Policy document needed (non-deterministic; deferred acceptable) |
| G12 | Compute quota management | 5-6 | 🔶 Defined; implementation pending |
| G13 | State migration | 3-6-3 | 🔶 Version field + migration script needed |
| G14 | Compute budget forecasting | 5-6-3 | 🔶 Defined; implementation pending |
| G15 | Node resilience re-sync | 2-4-4, 4-6-3 | 🔶 Re-sync diff automation needed |
| G16 | Automated Kaizen triggers | 3-8-1 | 🔶 Exception hook + PM directory needed |
| G17 | Voting drift alerting | 2-6-2 | 🔶 Analysis function needed |
| G18 | Intent capture enforcement | 0-1, 0-3 | 🔶 NEW — structured intent + CLARIFICATION_ACK protocol |
| G19 | User acceptance testing | 6-2 | 🔶 NEW — HUMAN_ACK protocol in handoff needed |
| G20 | Edit granularity policy | T18 | 🔶 NEW — Surgical vs. Full-rewrite policy document |
| G21 | Node capability profiles | 4-7 | 🔶 NEW — Profile schema + routing check |
| G22 | Model lifecycle governance | 4-8 | 🔶 NEW — Regression suite + version pinning |
| G23 | Concurrent session locking | 5-7 | 🔶 NEW — Lock mechanism + merge protocol |
| G24 | Degraded mode protocol | 5-8 | 🔶 NEW — Failure detection + fallback runbooks |
| G25 | Immutable audit log | 3-9 | 🔶 NEW — Append-only log layer |
| G26 | Domain knowledge base | 1-5 | 🔶 NEW — Structured knowledge store + retrieval |
| G27 | Intent alignment monitoring | 0-4 | 🔶 NEW — Mid-execution re-verification protocol |
| G28 | Instruction efficacy tracking | 1-4-5 | 🔶 NEW — Misinterpretation rate measurement |

---

## §9. Implementation Roadmap

| Priority | Task | Governance Item | Notes |
|:--------:|:-----|:----------------|:------|
| **P0** | Deploy governance parameter registry with all 22 params | 5-1 | Foundation for all other P0–P3 |
| **P0** | Implement intent capture schema in session initiation | 0-1, 0-2 | G18 |
| **P1** | Build health monitoring thresholds from registry (not hardcoded) | 1-1, 5-3 | |
| **P1** | Create post-mortem directory + automated PM draft trigger | 3-8 | G16 |
| **P1** | Add CLARIFICATION_ACK + HUMAN_ACK fields to handoff schema | 0-3, 6-2 | G18, G19 |
| **P2** | Add confidence_score to output schema; route low-confidence to human | 3-4-5 | |
| **P2** | Add proposer field to consensus history | 2-6-1 | |
| **P2** | Implement compute tracking (token counting → state accumulation) | 5-6 | G12 |
| **P2** | Implement active control pre-flight check in orchestration hub | 5-5 | |
| **P3** | Add version field to all state objects + write migration script | 3-6-3 | G13 |
| **P3** | Node capability profile schema + routing integration | 4-7 | G21 |
| **P3** | Foundation model version pinning + regression test suite | 4-8 | G22 |
| **P3** | Concurrent session state locking mechanism | 5-7 | G23 |
| **P3** | Degraded mode runbooks + failure detection monitors | 5-8 | G24 |
| **P3** | Append-only audit log layer (separate from context) | 3-9 | G25 |
| **P3** | Domain knowledge schema + contextual retrieval | 1-5 | G26 |
| **P3** | Dashboard specification document | 5-4-4 | G7 |
| **P3** | Edit granularity policy document | T18 | G20 |
| **P3** | Async event handling policy document | 5-3-2 | G11 |

---

## §10. Axis Framework

The Axis framework defines structured delegation tasks that map to governance categories.
Each Axis is a named analysis type assignable to any capable AI node.

| Axis | Name | Primary Category | Secondary | Purpose |
|:----:|:-----|:----------------:|:---------:|:--------|
| A | Architecture Review | Cat 1, 4 | Cat 3 | Evaluate design decisions |
| B | Behavior Analysis | Cat 2 | Cat 3 | Analyze node behavior patterns |
| C | Code Review | Cat 3 | Cat 2 | Code quality and policy compliance |
| D | Dependency Scan | Cat 4 | Cat 3 | Dependency security and portability |
| E | Error Root Cause | Cat 3 | Cat 2 | Root cause analysis for failures |
| F | Impact Analysis | Cat 3 | Cat 5 | Change blast-radius estimation (mandatory gate) |
| G | Gap Analysis | Cat 0–6 | — | MECE completeness gap identification |
| H | Health Check | Cat 5 | Cat 1 | Context and system health reporting |
| I | Integration Test | Cat 3, 4 | Cat 2 | Cross-component integration testing |
| J | Policy Gate | Cat 3 (Static) | Cat 5 | N-check policy regression (Judge) |
| K | Intent Review | Cat 0 | Cat 6 | Human intent validation + delivery acceptance |

**Axis compute budget classes** (applies to any implementation):
- Simple (A/B/C): ≤ 8% of `daily_compute_budget` per invocation
- Deep (D/E/F): ≤ 16% of `daily_compute_budget` per invocation
- Review (G/H/I/J/K): ≤ 32% of `daily_compute_budget` per invocation

---

---

# Appendix A: Reference Implementation — Windows Portable Sandbox (CC+GC)

> **Scope**: This appendix documents ONE specific implementation of the universal taxonomy above.
> It is provided as a concrete reference, not as a required approach.
> **System**: Windows 11 + PowerShell 5.1 + Python 3 venv + Node.js (portable)
> **AI Nodes**: Claude Code (CC) + Gemini CLI (GC) + Human
> **IPC**: hub.py (Python) + msg.bat (CMD wrapper)

---

## A.1 System Architecture Map

| Universal Concept | CC+GC Implementation | File / Component |
|:-----------------|:---------------------|:-----------------|
| IPC message broker | hub.py | `.\_sys\core\hub.py` |
| P2P messaging interface | msg.bat | `.\_sys\cli\msg.bat` |
| Static policy gate | check-policy.bat → check_policy.py | `.\_sys\checks\` |
| Health monitor | check-health.bat → check_health.py | `.\_sys\checks\` |
| Session handoff artifact | handoff.md | `.\.ai\sessions\room-{uuid}\handoff.md` |
| Session archive commands | ctx-save.bat / ctx-end.bat | `.\_sys\` |
| Governance parameter registry | config.json | `.\_sys\gemini\config.json` |
| Agent global configuration | CLAUDE.md (CC) / GEMINI.md (GC) | `.\_sys\claude\config\` / `.\_sys\gemini\` |
| Project configuration override | project CLAUDE.md | `.\CLAUDE.md` |
| Consensus governance docs | PROTOCOL.md | `.\PROTOCOL.md` |
| Coding conventions | CONVENTION.md | `.\CONVENTION.md` |
| Post-mortem store | .ai/postmortems/ | `.\.ai\postmortems\` |
| Long-term memory store | MEMORY.md + *.md | `.\_sys\claude\config\projects\P--\memory\` |
| Version control / rollback | git + ctx-save tags | git repository |
| Node registry | nodes.json | `.\.ai\nodes.json` |
| Session state | state.json | `.\.ai\state.json` |

**5 Critical Rules (CC+GC protocol):**
1. No execution before FINALIZED consensus (PROTOCOL.md §P-3)
2. Constitutional docs require R:10 to modify (PROTOCOL.md §M-1)
3. Three consecutive same errors → HALT + human consult (PROTOCOL.md §M-3)
4. Re-orient via handoff.md before any task (PROTOCOL.md §P-11)
5. All Gemini queries in English (2–3× token efficiency)

---

## A.2 Universal → Implementation Parameter Mapping

| Universal Parameter | CC+GC config.json key | Default | Range |
|:-------------------|:----------------------|:-------:|:-----:|
| `collaboration_depth` | `collab_rate` | 10 | 0–10 |
| `consensus_timeout` | `consensus_timeout_min` | 30 | 1–60 (min) |
| `final_call_threshold` | `final_call_min_rate` | 8 | 0–10 |
| `daily_compute_budget` | `token_budget_daily` | 50000 | 1k–500k (tokens) |
| `task_delegation_threshold` | `axis_delegation_threshold` | 5 | 1–20 |
| `policy_bypass_floor` | `policy_gate_bypass_threshold` | 8 | 0–10 |
| `intent_timeout` | `human_intent_timeout_min` | 60 | 1–1440 (min) |
| `clarification_max_turns` | `intent_clarification_max_turns` | 3 | 1–10 |
| `delivery_ack_required` | `delivery_acceptance_required` | 1 | 0–1 |
| `context_warn_threshold` | `context_health_green_kb` | 600 | 100–1000 (KB) |
| `context_critical_threshold` | `context_health_yellow_kb` | 1200 | 200–2000 (KB) |
| `memory_compaction_interval` | `compactor_interval_days` | 7 | 1–30 (days) |
| `peer_review_min_interval` | `review_interval_min` | 5 | 1–60 (min) |
| `resolved_item_ttl` | `ttl_resolved_days` | 3 | 1–30 (days) |
| `active_item_ttl` | `ttl_active_days` | 14 | 1–90 (days) |
| `dissent_drift_threshold` | `voting_drift_threshold_pct` | 60 | 1–99 (%) |
| `max_recovery_depth` | `max_rollback_depth` | 3 | 1–10 |
| `confidence_floor` | `confidence_threshold` | 70 | 0–100 (%) |
| `metrics_persist_interval` | `metrics_flush_interval_sec` | 300 | 10–3600 (s) |
| `active_control_enabled` | `active_control_enabled` | 0 | 0–1 |
| `forecast_alert_threshold` | `forecast_warn_threshold_pct` | 70 | 1–99 (%) |
| `budget_alert_threshold` | `token_budget_warn_pct` | 90 | 1–99 (%) |

**config.json full schema** (24 keys: `_param_sections` + 22 params + `last_review_ts`):
```json
{
  "_param_sections": {
    "general": ["collab_rate","consensus_timeout_min","final_call_min_rate",
                "token_budget_daily","axis_delegation_threshold","policy_gate_bypass_threshold"],
    "cat0":    ["human_intent_timeout_min","intent_clarification_max_turns",
                "delivery_acceptance_required"],
    "cat1":    ["context_health_green_kb","context_health_yellow_kb","compactor_interval_days",
                "review_interval_min","ttl_resolved_days","ttl_active_days"],
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
Validation: `python -c "import json; d=json.load(open('./_sys/gemini/config.json')); assert len(d)==24; print('OK')"`

---

## A.3 Measurement Commands (PowerShell 5.1 Native)

```powershell
# ── Policy Gate (Axis-J, Cat 3-2) ─────────────────────────────────────
cmd /c ".\_sys\checks\check-policy.bat"

# ── Context Health (Axis-H, Cat 1-1, 5-3) ─────────────────────────────
cmd /c ".\_sys\checks\check-health.bat"

# ── Hub Status / Node Registry (Cat 2-4, 4-3) ─────────────────────────
cmd /c ".\_sys\cli\msg.bat" hub status

# ── Handoff size check (Cat 1-2) ───────────────────────────────────────
(Get-Item ".ai\sessions\room-{id}\handoff.md").Length / 1KB
# Target: ≤ 2 KB

# ── Commit format compliance rate (Cat 3-3) ───────────────────────────
@(git log --oneline -20 | Select-String -Pattern `
  "^[0-9a-f]+ (feat|fix|docs|refactor|test|chore):").Count / 20 * 100
# Target: ≥ 95%

# ── Recovery checkpoint count (Cat 3-6) ───────────────────────────────
@(git log --grep="ctx-save" --oneline).Count
# Target: ≥ max_rollback_depth

# ── Parameter registry validation (Cat 5-1) ───────────────────────────
python -c "import json; d=json.load(open('./_sys/gemini/config.json')); assert len(d)==24; print('OK 24 keys')"

# ── PowerShell execution policy (Cat 4-1-5) ───────────────────────────
Get-ExecutionPolicy
# Target: RemoteSigned or higher

# ── Post-mortem count (Cat 3-8) ───────────────────────────────────────
@(Get-ChildItem ".ai\postmortems\*.md" -ErrorAction SilentlyContinue).Count

# ── Memory file count (Cat 1-3) ───────────────────────────────────────
(Get-ChildItem ".\_sys\claude\config\projects\P--\memory\*.md").Count

# ── Intent capture check (Cat 0-1) ────────────────────────────────────
Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "TASK:"

# ── Human ACK check (Cat 6-2) ─────────────────────────────────────────
Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "HUMAN_ACK"

# ── FINALIZED directive traceability (Cat 3-7) ────────────────────────
Get-Content ".ai\sessions\room-*\handoff.md" | Select-String "FINALIZED"

# ── Proposer attribution (Cat 2-6) ────────────────────────────────────
Get-Content ".ai\sessions\room-*\handoff.md" | Select-String "Proposer:"

# ── Collaboration depth symmetry (Cat 2-4) ────────────────────────────
cmd /c ".\_sys\checks\check-policy.bat" 2>&1 | Select-String "collab-rate-symmetry"
```

---

## A.4 Current Implementation Completion State

> **Date of assessment**: 2026-06-05 | **System**: CC+GC Windows Portable Sandbox

| Cat | Category | Items | Weight | Current Score | Target | Δ |
|:---:|:---------|:-----:|:------:|:------------:|:------:|:--:|
| 0 | Human Intent & Kickoff | 4 | 8% | 0.25 | 0.90 | +0.65 |
| 1 | Cognitive Continuity | 5 | 17% | 0.60 | 0.95 | +0.35 |
| 2 | Collaboration Governance | 6 | 22% | 0.67 | 0.97 | +0.30 |
| 3 | System Integrity | 9 | 28% | 0.63 | 0.95 | +0.32 |
| 4 | Environment Portability | 8 | 13% | 0.67 | 0.95 | +0.28 |
| 5 | Operations & Control | 8 | 7% | 0.26 | 0.90 | +0.64 |
| 6 | Product Delivery | 3 | 5% | 0.40 | 0.90 | +0.50 |
| **Root** | | **43** | **100%** | **0.571 (57.1%)** | **0.945 (94.5%)** | **+0.374** |

**Root formula** (CC+GC current):
```
0.08×0.25 + 0.17×0.60 + 0.22×0.67 + 0.28×0.63 + 0.13×0.67 + 0.07×0.26 + 0.05×0.40
= 0.020 + 0.102 + 0.147 + 0.177 + 0.087 + 0.018 + 0.020
= 0.571 (57.1%)
```

**T0 items** (highest priority, score = 0.00):
- 0-4 Intent Alignment Monitoring
- 1-5 Domain Knowledge Management
- 2-6 Decision Attribution
- 3-8 Post-Mortem Loop
- 3-9 Immutable Audit Log
- 4-7 Node Capability Profiling
- 4-8 Model Lifecycle Governance
- 5-5 Active Control Loop
- 5-6 Economic Governance
- 5-7 Concurrent Session Management
- 5-8 Degraded Mode Protocols
- 6-2 User Acceptance Test

**P0+P1 implementation effect**: +0.12 → Root ~69%
**P0+P2 implementation effect**: +0.20 → Root ~77%
**All T0 resolved**: +0.37 → Root ~94.5%

---

## A.5 Governance Protocol References

The following documents define the CC+GC collaboration rules referenced throughout this system.
All paths are relative to the project root (P:\).

| Document | Path | Content Summary |
|:---------|:-----|:----------------|
| PROTOCOL.md | `.\PROTOCOL.md` | Consensus rules, session protocol, §P-* and §M-* sections |
| CONVENTION.md | `.\CONVENTION.md` | Coding conventions, Axis task templates |
| CLAUDE.md (global) | `.\_sys\claude\config\CLAUDE.md` | CC global instructions (collaboration depth, query format) |
| GEMINI.md | `.\_sys\gemini\GEMINI.md` | GC global instructions (symmetric to CLAUDE.md) |
| TAXONOMY_v4.md | `.\_sys\docs\TAXONOMY_v4.md` | Previous version (READ-ONLY, preserved) |
| TAXONOMY_v5.md | `.\_sys\docs\TAXONOMY_v5.md` | This document |

**PROTOCOL.md key sections** (verbatim section names):
- §P-0: Human Gate (Tier-0 veto)
- §P-2: DIRECTIVE envelope schema
- §P-3: Propose → Vote → FINALIZED cycle + §P-3-QR Quorum + §P-3-FC Final Call
- §P-4: Node routing rules
- §P-7: Parallel vs. sequential execution policy
- §P-8: Node loading token budget
- §P-9: N-node expansion protocol
- §P-11: Re-orientation via handoff.md
- §M-1: Constitutional document non-interference
- §M-2: No private channels
- §M-3: 3-Strike halt rule
- §C-0: COLLAB_RATE anchors (R:0=autonomous / R:3=light / R:5=medium / R:8=high / R:10=unanimous)
