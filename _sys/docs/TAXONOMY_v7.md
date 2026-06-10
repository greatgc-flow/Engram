# MECE Taxonomy v7.0 — AI-Assisted Development: Governance Framework
### Universal · Workspace-Independent · Multi-Vendor · Symmetric Participation · Functionally Complete

> **Version**: 7.0 | **Date**: 2026-06-05
> **Review History**: v3 (base) → v4 (Human-in-Loop) → v5 (Universal) → v6 (Multi-vendor+Participation) → v7 (Complete)
> **Collaboration**: Multi-node | Unanimous consensus, 2-round audit
> **Supersedes**: TAXONOMY_v6.md (READ-ONLY)
> **Audience**: Any team building an AI-assisted software development system.
> **Main body (§0–§10)**: Zero workspace-specific references. Fully self-contained.

---

## §0. How to Read This Document

This document defines the **governance layer** of AI-assisted software development — the meta-system
ensuring AI agents and humans collaborate reliably, symmetrically, and adaptably.

**What this document IS**: A measurement framework + taxonomy for governing HOW AI agents collaborate.
**What this document is NOT**: A guide to what AI agents should build (application layer).

**Three reading modes:**
- **Universal** (§0–§10 only): Applicable to any AI system, any vendor combination.
- **Implementation** (+ Appendix A): Reference implementation details (Windows Sandbox).
- **Multi-vendor** (+ Appendix B): Template for cross-vendor deployment.

**How to use completeness scores**: Each item carries a score = `min(Current Tier / Target Tier, 1.0)`.
A score of 0.00 means "not yet implemented". T0 = undefined, T4 = fully automated with active alerts.
See §7 for the Root Score formula. See Appendix A.4 for the reference implementation's current state.

| Section | Content |
|:--------|:--------|
| §1 | Scope, definitions, measurement tiers |
| §2 | Human-in-Loop lifecycle (7-category closed cycle + flow table) |
| §3 | Full MECE taxonomy tree (51 items) |
| §4 | Binary/deterministic KPI matrix |
| §5 | Architectural trade-offs (T1–T24) |
| §5.5 | Logical contradictions (C1–C9) |
| §6 | Governance parameter catalogue (30 params) |
| §7 | Maturity scoring model |
| §8 | Gap analysis log (G1–G38) |
| §9 | Implementation roadmap |
| §10 | Axis framework (A–L) |
| Appendix A | CC+GC reference implementation |
| Appendix B | Multi-vendor capability matrix template |

---

## §1. Scope & Universal Principles

### §1.1 Scope

**In scope**: Working memory lifecycle · multi-agent consensus · symmetric participation ·
collaborative task planning · role management · vendor abstraction · environment portability ·
observability · functional verification · external invocation governance · human intent capture ·
flexible participation (join/leave/monitor) · compute governance · learning loops.

**Out of scope**: Application business logic, domain models, UI/UX, deployment pipelines.

### §1.2 Definitions

| Term | Definition |
|:-----|:-----------|
| **AI Node** | Any AI agent in the system (language model, coding assistant, etc.) |
| **Human** | The operator who may vote in consensus, defines intent, and accepts deliverables |
| **Node Instance** | A specific running process of a model; one model may back multiple instances |
| **Role** | A virtual function assigned to a node instance at runtime (e.g., Architect, Reviewer) |
| **Session** | A bounded unit of work: start → execution → delivery |
| **Directive** | A formally structured task assignment targeting a Role (not a node ID) |
| **Consensus** | A formally recorded agreement among all ACTIVE nodes on a decision |
| **Working Memory** | The active payload available to an AI node during a session |
| **Handoff** | Structured artifact carrying session state to the next session or node |
| **Compute Budget** | Total allowed resource consumption (normalized units or currency) per period |
| **Reference Token** | A vendor-agnostic unit for measuring compute; defined at system initialization |
| **Participation Mode** | Node's engagement state: ACTIVE / OBSERVER[SILENT\|ANNOTATING] / GRACEFUL_EXIT / FORCED_EXIT |
| **Task Force** | A voted sub-group operating with scoped consensus on a shared sub-goal |
| **Vendor Adapter** | Software component translating a vendor's native API to the canonical protocol |
| **Vendor Execution Layer** | The unmanaged black-box zone where AI inference occurs; governance validates BEFORE (Cat 2) and AFTER (Cat 3), not inside |
| **MECE** | Mutually Exclusive, Collectively Exhaustive — no overlap, no gaps |
| **Kaizen** | Continuous Process Remediation — iterative improvement by identifying and fixing root causes of failures (originated in manufacturing; universally applicable) |
| **5-Why** | Root cause analysis technique: ask "Why?" five times in succession to reach the fundamental cause of a failure |
| **Primary Success Scenario** | The primary designed use case of a deliverable, verified end-to-end (also called "golden path" in engineering) |
| **Gini Coefficient** | Statistical measure of distribution inequality: 0 = perfectly equal distribution, 1 = single-node monopoly |
| **VCS** | Version Control System — any system tracking changes to artifacts over time |

### §1.3 Measurement Tiers

#### Type B — Binary / Structural (existence is the metric)

| Tier | Criterion | Score |
|:----:|:----------|:-----:|
| T0 | Not defined | 0% |
| T1 | Draft/policy exists | 50% |
| **T2** | **Enforced by automated check or system constraint** | **100%** |

#### Type C — Continuous / Operational (ongoing monitoring meaningful)

| Tier | Criterion | Score |
|:----:|:----------|:-----:|
| T0 | Not defined | 0% |
| T1 | Threshold/definition documented | 25% |
| T2 | Implementation exists; manual check possible | 50% |
| T3 | Automated check/script exists | 75% |
| **T4** | **Active monitoring + auto-alert on threshold breach** | **100%** |

> **Score formula**: `min(Current Tier / Target Tier, 1.0)`
> If current > target (over-engineered): score = 1.00 (capped)

#### Measurement Failure Response

> "Depth" = `collaboration_depth` parameter (see §6). Higher depth = more consensus required.

| Collaboration Depth | Tier 3/4 failure action |
|:-------------------:|:------------------------|
| Maximum (e.g., Depth 10) | **HALT + ESCALATE** to human gate |
| Medium (e.g., Depth 5–8) | **WARN + continue** — log to metrics store |
| Minimal (e.g., Depth 0–3) | **LOG only** — no interruption |

### §1.4 Abstraction Principle

Universal parameter names are used in §0–§10. Implementers map these to their specific systems.
- See Appendix A.2 for reference parameter mapping.
- See Appendix B for multi-vendor setup template.

---

## §2. Human-in-Loop Lifecycle

The 7 governance categories form a **closed feedback cycle**. All participants (any AI, any vendor,
the Human) may engage symmetrically in any phase (see Cat 2-1).

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────────────────┐    ║
║  │  Cat 0   │───►│  Cat 4   │───►│  Cat 1   │───►│      Cat 2         │    ║
║  │  Intent  │    │   Env.   │    │  Memory  │    │   Collaboration    │    ║
║  └──────────┘    └──────────┘    └──────────┘    └─────────┬──────────┘    ║
║       ▲               │ [fail]                             │               ║
║       │               ▼                         ┌──────────┘               ║
║  ┌──────────┐    [Human Gate]        ┌──────────▼──────────┐               ║
║  │  Cat 6   │◄───┤  Cat 5  │◄───────┤      Cat 3          │               ║
║  │ Delivery │    │   Ops.  │        │     Integrity        │               ║
║  └──────────┘    └─────────┘        └──────────┬──────────┘               ║
║       │                                        │                           ║
║       │                              [Vendor Execution Layer]              ║
║       │                         (AI inference: unmanaged black box)        ║
║       │                         Governance validates pre (Cat 2) +         ║
║       │                         post (Cat 3); not inside VEL               ║
║       │                                                                     ║
║       └── Any node delivers → Human ACK → defines next intent ───────────► ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Inter-Category Data Flow

| Transition | Payload Passed | Failure Path |
|:-----------|:---------------|:-------------|
| Cat 0 → Cat 4 | Intent schema (Goal ID, Scope, Constraints, Success Criteria, Delivery Format) | — |
| Cat 4 → Cat 1 | Verified environment manifest (adapters ready, node profiles loaded) | Bootstrap fail → Human Gate → fix → retry Cat 4 |
| Cat 1 → Cat 2 | Oriented working memory (session state, history, domain knowledge injected) | — |
| Cat 2 → [VEL] | Finalized directive (role, task, scope, quality floor, test requirements) | Consensus fail → Cat 2-4 Conflict Resolution |
| [VEL] → Cat 3 | Raw vendor output (unvalidated, vendor-native format) | — |
| Cat 3 → Cat 5 | Validated artifact + integrity report (schema OK, tests pass, risks cleared) | Validation fail → reject → back to Cat 2 |
| Cat 5 → Cat 6 | Governed artifact + health metrics (within budget, no critical alerts) | Budget exhausted → HALT + escalate |
| Cat 6 → Cat 0 | Delivery ACK + lessons learned + next-session seed | Human rejects → revise → back to Cat 2 |

---

## §3. Full MECE Taxonomy Tree (51 Items)

> **Legend**: `[Type | Target Tier]` — B=Binary (T0–T2), C=Continuous (T0–T4)
> Loop order: Cat 0 → Cat 4 → Cat 1 → Cat 2 → Cat 3 → Cat 5 → Cat 6

```
AI-Assisted Development: Governance Framework
│
├─ Cat 0: Human Intent & Kickoff  [8%]
│  Entry gate. Every cycle starts here. ANY capable node may facilitate this phase.
│  Output: structured intent schema passed to Cat 4 (environment provisioning).
│
│  ├── 0-1: Structured Intent Capture  [B|T2]
│  │   Every task MUST begin with a structured artifact containing Goal ID, Scope boundary,
│  │   and Constraints BEFORE any multi-node execution begins.
│  │   Example: A developer says "build login feature" →
│  │     Goal ID: LOGIN-001, Scope: auth module only, Constraints: no third-party auth libs.
│  │   ├── 0-1-1: Goal statement — one sentence, unique Goal ID assigned
│  │   ├── 0-1-2: Scope bounding — explicit MVP boundary vs. deferred scope
│  │   └── 0-1-3: Constraint identification — time, tech, budget, non-goals
│  │
│  ├── 0-2: Success Criteria Definition  [B|T2]
│  │   Human-verifiable acceptance criteria MUST exist before execution.
│  │   Each criterion is tagged with Goal ID for traceability to Cat 3-10.
│  │   Example: "Login succeeds with valid credentials (HTTP 200), fails with invalid (HTTP 401)."
│  │   ├── 0-2-1: Acceptance criteria — ≥1 human-checkable condition per Goal ID
│  │   ├── 0-2-2: Quality thresholds — measurable bars (test coverage %, response latency, etc.)
│  │   └── 0-2-3: Delivery format — file path, output schema, or artifact type
│  │
│  ├── 0-3: Clarification Protocol  [C|T3]
│  │   AI agents MUST surface ambiguities within `clarification_max_turns` rounds.
│  │   The clarification loop is bounded to prevent infinite questioning.
│  │   ├── 0-3-1: Ambiguity detection — ≥1 unclear requirement → ask human
│  │   ├── 0-3-2: Turn limit — max `clarification_max_turns` rounds (default: 3)
│  │   └── 0-3-3: Intent confirmation — explicit human ACK recorded before multi-file execution
│  │
│  └── 0-4: Continuous Intent Alignment  [B|T2]
│      All file modifications during multi-step execution MUST occur within the declared
│      scope defined at Cat 0-1. Any out-of-scope attempt is blocked.
│      ├── 0-4-1: Scope enforcement — every file mutation checked against allowed scope
│      ├── 0-4-2: Drift detection — action outside scope → immediate flag before execution
│      └── 0-4-3: Scope escalation — detected drift above threshold → human gate
│
├─ Cat 4: Environment Portability  [13%]
│  Infrastructure and vendor integration. MUST be verified before cognitive work (Cat 1).
│  Output: environment manifest (adapters ready, node profiles loaded).
│  Failure: bootstrap failure → Human Gate → fix environment → retry.
│
│  ├── 4-1: Runtime Environment  [C|T3]
│  │   All runtime dependencies MUST be self-contained; no host system state assumed.
│  │   Example: all Python packages in isolated venv; no global pip installs.
│  │   ├── 4-1-1: Runtime isolation — language runtime and deps isolated from host
│  │   ├── 4-1-2: Encoding consistency — character encoding explicitly set system-wide
│  │   ├── 4-1-3: Package manager isolation — package installs scoped to project
│  │   ├── 4-1-4: Environment variable scoping — per-agent env vars isolated
│  │   └── 4-1-5: Zero-config hardening — execution policy meets minimum security baseline
│  │
│  ├── 4-2: Installation & Deployment  [C|T3]
│  │   A single bootstrap command MUST reconstruct the full environment from scratch.
│  │   Example: `./install.sh` on a clean OS installs all deps and passes smoke tests.
│  │   ├── 4-2-1: Zero-base bootstrap — one command = full reconstruction, 0 manual steps
│  │   ├── 4-2-2: Dependency bootstrapping — all tools and packages auto-installed
│  │   ├── 4-2-3: Smoke testing — post-install validation confirms environment health
│  │   └── 4-2-4: Parallel-safe naming — no filename collisions in concurrent setups
│  │
│  ├── 4-3: Infrastructure Abstraction  [C|T3]
│  │   IPC, messaging, and shared state MUST be decoupled from node identity.
│  │   Example: replacing the IPC backend requires no changes to individual node code.
│  │   ├── 4-3-1: Technology-neutral IPC — message broker decouples nodes from transport
│  │   ├── 4-3-2: Shared state layer — node-independent state accessible to all agents
│  │   ├── 4-3-3: Unified messaging interface — single entry point for all P2P messages
│  │   └── 4-3-4: Node heartbeat — liveness detection; absent nodes auto-abstain from quorum
│  │
│  ├── 4-4: Version Management  [B|T2]
│  │   All protocol and schema versions MUST be tracked; mismatches MUST be detectable.
│  │   ├── 4-4-1: Protocol versioning — all governance docs carry explicit vX.Y version tags
│  │   ├── 4-4-2: Changelog maintenance — every version change documented with rationale
│  │   └── 4-4-3: Version format enforcement — standardized tag format enforced by check
│  │
│  ├── 4-5: Platform Independence  [C|T3]
│  │   No absolute paths or OS-specific constructs in committed artifacts.
│  │   Example: `./config/settings.json` not `C:\Users\admin\project\config\settings.json`.
│  │   ├── 4-5-1: No hardcoded paths — all paths relative or environment-variable-based
│  │   ├── 4-5-2: Drive/mount abstraction — portable across OS and mount points
│  │   └── 4-5-3: Cross-platform path API — platform-agnostic path libraries enforced
│  │
│  ├── 4-6: Node Onboarding  [B|T2]
│  │   Any new AI node MUST be onboardable without manual intervention beyond registration.
│  │   ├── 4-6-1: Registration checklist — required fields before a node may vote
│  │   ├── 4-6-2: Required loading — new node ingests defined governance context
│  │   ├── 4-6-3: Resilience mechanics — heartbeat auto-abstain; re-sync on reconnect
│  │   └── 4-6-4: Wrapper governance — vendor adapter code must be open-auditable,
│  │               version-pinned, tested against both native API and canonical protocol
│  │
│  ├── 4-7: Node Capability Profiling  [C|T2]
│  │   Every active node MUST have a formal capability profile consulted before routing.
│  │   Example profile: {vendor: "ModelX", token_limit: 128000, tools: ["code", "search"],
│  │     token_counting_standard: "BPE-cl100k", native_protocol: "REST-JSON"}
│  │   ├── 4-7-1: Standardized profile schema — required fields:
│  │   │         token_limit (model-native units), tools[], specialization[],
│  │   │         role_id (mutable), token_counting_standard, vendor_id, native_protocol,
│  │   │         output_format, confidence_mapping_fn
│  │   ├── 4-7-2: Dynamic capability discovery — profile updated on node state change
│  │   ├── 4-7-3: Profile-aware routing — delegation checks 4-7 profile first
│  │   ├── 4-7-4: Cross-vendor capability bridging — fallback when task exceeds node capacity:
│  │   │         (1) chunk into sub-tasks, (2) route to capable node, (3) escalate to human
│  │   └── 4-7-5: Token normalization — all nodes normalize to reference token unit;
│  │               profile includes `token_converter(vendor_tokens → ref_tokens)`
│  │
│  ├── 4-8: Foundation Model Lifecycle  [C|T3]
│  │   Model transitions MUST trigger re-validation of capability and behavioral compliance.
│  │   Example: upgrading Model-X from v2.1 to v3.0 requires re-running the behavior test suite.
│  │   ├── 4-8-1: Model version pinning — active model version recorded in configuration
│  │   ├── 4-8-2: Behavioral regression suite — per-vendor test run mandatory before upgrade
│  │   ├── 4-8-3: Rollback procedures — prior model version recoverable within defined window
│  │   └── 4-8-4: Vendor model update detection — system detects vendor-initiated silent upgrades;
│  │               re-runs compliance suite before accepting outputs from new version
│  │
│  └── 4-9: Vendor Integration Layer  [C|T2]
│      Every AI vendor connects via a standardized adapter. The adapter translates
│      vendor-native APIs to the canonical governance protocol BEFORE entering Cat 2.
│      Architecture:
│        [Vendor A] → [Adapter-A] ──►┐
│        [Vendor B] → [Adapter-B] ──►├─► [Canonical Hub] ──► Cat 2 Governance
│        [Vendor C] → [Adapter-C] ──►┘
│      ├── 4-9-1: Vendor adapter specification — each adapter declares:
│      │         native_protocol (REST/gRPC/WebSocket/streaming/batch),
│      │         token_converter, output_format_converter,
│      │         confidence_mapping_fn (vendor → 0–100 scale),
│      │         depth_interpretation_schema (vendor semantics for collaboration_depth)
│      ├── 4-9-2: Output schema normalization — adapter converts vendor output to
│      │         canonical schema BEFORE entering governance pipeline (Cat 3-4)
│      ├── 4-9-3: Rate-limit coordination — adapter declares tokens_per_min,
│      │         requests_per_day; active control loop (5-5) respects per-vendor limits
│      └── 4-9-4: Protocol fallback chain — ordered fallback when primary protocol fails;
│                  defined in `vendor_protocol_priority` parameter
│
├─ Cat 1: Cognitive Continuity  [17%]
│  Ensures all agents maintain coherent, persistent awareness across sessions.
│  "Working memory" is the universal term used throughout (replaces vendor-specific "context").
│  Output: oriented working memory state passed to Cat 2.
│
│  ├── 1-1: Working Memory Lifecycle  [C|T4]
│  │   Active working memory size MUST be monitored (in reference token units);
│  │   thresholds trigger managed pruning to prevent cognitive degradation.
│  │   Example: memory at 580 ref-tokens (below 600 warn threshold) = GREEN; at 650 = YELLOW.
│  │   ├── 1-1-1: Size tracking — continuous measurement vs. warn/critical thresholds
│  │   ├── 1-1-2: Session state rolling — completed items archived; live state kept minimal
│  │   └── 1-1-3: Memory pruning — TTL scoring:
│  │               score = (priority_level × 2) − age_in_days; score < 0 → archive candidate
│  │               Boundary note: 1-1-3 covers session-scoped TTL (hours–days);
│  │               1-3-2 covers long-term compaction (weeks–months). NOT overlapping.
│  │
│  ├── 1-2: Session Continuity  [B|T2]
│  │   Every session MUST produce a machine-readable handoff enabling seamless resumption.
│  │   Boundary note: 1-2 = ephemeral handoff (passing baton to next session);
│  │   1-3 = compacted long-term memory (indexed for async future retrieval). Distinct scopes.
│  │   ├── 1-2-1: Scoped session workspace — isolated per-session directory, unique ID
│  │   ├── 1-2-2: Per-node summaries — bounded summary per node
│  │   │         (e.g., <4 KB text-equivalent or model-equivalent size limit)
│  │   ├── 1-2-3: Re-orientation protocol — agent reads handoff before beginning ANY work
│  │   ├── 1-2-4: Emergency handoff schema — minimum viable recovery fields:
│  │   │         executive_summary / technical_state / strategy_for_next_session
│  │   └── 1-2-5: Vendor-agnostic handoff format — canonical typed-JSON intermediate format;
│  │               each node profile includes serializer/deserializer functions
│  │
│  ├── 1-3: Memory Persistence  [C|T4]
│  │   Learnings MUST persist across sessions in queryable structured form (weeks–months).
│  │   Boundary note: 1-3 handles compacted/indexed knowledge for async retrieval;
│  │   1-2 handles immediate session-to-session handoffs.
│  │   ├── 1-3-1: Long-term memory store — persistent file-based memory per project
│  │   ├── 1-3-2: Memory compaction — periodic pruning of stale/superseded entries
│  │   ├── 1-3-3: Symmetric sync — all nodes share access to same memory corpus
│  │   ├── 1-3-4: Memory taxonomy — typed entries: user / feedback / project / reference
│  │   └── 1-3-5: Memory format registry — entries declare encoding_format per entry;
│  │               retrieval layer handles heterogeneous formats (logic rule, example, fact)
│  │
│  ├── 1-4: Instruction Design & Efficacy  [B|T2]
│  │   Agents MUST have persistent structured instructions; quality MUST be measured over time.
│  │   Example: if 3+ sessions in a row require the same mid-session correction, the base
│  │   instruction is flagged for revision.
│  │   ├── 1-4-1: Global agent configuration — persistent baseline instruction set per agent
│  │   ├── 1-4-2: Project-level overrides — project-specific instructions take precedence
│  │   ├── 1-4-3: Query efficiency — instructions formatted for maximum information density
│  │   ├── 1-4-4: Task template library — structured templates for recurring task types
│  │   └── 1-4-5: Instruction efficacy tracking
│  │               Metric: count of sessions requiring mid-session correction / total sessions
│  │               Threshold: >10% correction rate → instruction revision triggered
│  │
│  └── 1-5: Persistent Domain Knowledge  [C|T3]
│      Domain-specific decisions and business rules MUST persist beyond sessions.
│      Example: "This project uses OAuth2, not API keys" persists across all future sessions.
│      ├── 1-5-1: Knowledge extraction — automated identification of reusable domain facts
│      ├── 1-5-2: Structured storage schema — queryable format (not raw session logs)
│      ├── 1-5-3: Contextual retrieval — knowledge injected into working memory on match
│      └── 1-5-4: Obsolescence protocol — outdated entries flagged/pruned on schedule
│
├─ Cat 2: Collaboration Governance  [22%]
│  All decisions, task planning, participation, roles, and communication protocols.
│  Ordered: Principles → Decisions → Execution → Participants → Communication
│  Output: finalized directive envelope passed to the Vendor Execution Layer.
│
│  ├── 2-1: Governance Principles  [B|T2]
│  │   FOUNDATIONAL. Defines equal rights for ALL participants.
│  │   No phase of the lifecycle (Cat 0–6) is "owned" by any specific node type.
│  │   Any registered node — any AI vendor, any instance, the Human — may propose,
│  │   vote, or be assigned work in any phase.
│  │   ├── 2-1-1: Symmetric phase participation — any registered node may PROPOSE, VOTE,
│  │   │         or be ASSIGNED work in any lifecycle phase (Cat 0 through Cat 6)
│  │   ├── 2-1-2: Equal vote weight — 1 ACTIVE node = 1 vote regardless of model size/vendor;
│  │   │         Human ACTIVE = 1 vote; Human OBSERVER = 0 votes; both states valid
│  │   ├── 2-1-3: Human interface assignment — any capable AI node may be dynamically
│  │   │         assigned to facilitate Cat 0 (intent intake) or Cat 6 (delivery);
│  │   │         conflict resolution: capability score first, then rotation
│  │   └── 2-1-4: Minimum rights — every registered node receives: broadcast access,
│  │               proposal rights, vote rights (when ACTIVE), directive rights
│  │
│  ├── 2-2: Consensus Protocol  [C|T3]
│  │   All cross-agent decisions MUST follow: Propose → Vote → Finalize.
│  │   This is the STATE MACHINE. Items like 2-3-4 (Goal Decomposition) are TRIGGERS
│  │   that invoke this machine — they are not separate decision processes.
│  │   ├── 2-2-1: Propose-Vote-Finalize cycle — explicit state machine per decision
│  │   ├── 2-2-2: Quorum rules — majority = >50% of currently ACTIVE nodes;
│  │   │         unanimity at depth = Count(ACTIVE_NODES); min 1 ACTIVE node required
│  │   ├── 2-2-3: Final Call mechanism — depth ≥ `final_call_threshold` requires explicit ACK
│  │   ├── 2-2-4: Consensus history — all finalized decisions recorded with rationale + ROLE
│  │   └── 2-2-5: Protocol polymorphism — adapter (4-9-1) translates vendor native protocol
│  │               to canonical format BEFORE entering this vote cycle
│  │
│  ├── 2-3: Collaborative Task Management  [C|T3]
│  │   Work division is collaboratively negotiated. Any node may propose, challenge, or revise.
│  │   Boundary note: 2-3-4 (Goal Decomposition) invokes the 2-2 consensus machine;
│  │   it is not a separate protocol — it defines WHAT triggers that machine.
│  │   ├── 2-3-1: Directive envelope — standard schema; includes `intended_role` field (not node ID)
│  │   ├── 2-3-2: Capability-based routing — routing checks 4-7 profile before assignment
│  │   ├── 2-3-3: Parallel execution policy — async when impact ranges non-overlapping,
│  │   │         OR when sub-team synthesis (2-7-3) will merge complementary contributions
│  │   ├── 2-3-4: Goal decomposition protocol — before multi-node execution, a Division Proposal
│  │   │         maps sub-tasks to roles/capabilities; achieves consensus via 2-2 cycle;
│  │   │         split criteria: artifact boundary, dependency order, capability match
│  │   ├── 2-3-5: Assignment challenge — any ACTIVE node may challenge any task assignment;
│  │   │         grounds: capability mismatch, working memory overload, inefficiency
│  │   ├── 2-3-6: Division revision — mid-execution re-division triggered when:
│  │   │         (a) scope >50% over estimate, (b) assigned node enters GRACEFUL_EXIT,
│  │   │         (c) dependencies change; re-runs 2-3-4 for affected sub-tasks only
│  │   └── 2-3-7: Result aggregation — cross-node output verification before finalization
│  │
│  ├── 2-4: Conflict & Deadlock Resolution  [B|T2]
│  │   Every unresolvable conflict MUST have a defined escalation path to human arbitration.
│  │   ├── 2-4-1: Deadlock handling — when N-node consensus cannot converge within
│  │   │         `consensus_timeout` → escalate to human or pre-defined authority node
│  │   ├── 2-4-2: Human gate escalation — any node may invoke human veto at any time
│  │   ├── 2-4-3: Repeated-failure halt — N consecutive identical errors → HALT + human consult
│  │   └── 2-4-4: Stalled round cleanup — auto-expiry of rounds exceeding timeout
│  │
│  ├── 2-5: Node Registry & Identity  [C|T3]
│  │   Every participating node MUST be registered; registry is the single source of truth.
│  │   ├── 2-5-1: Node registry — authoritative list with fields:
│  │   │         node_id, model_vendor, instance_id, role_id (mutable),
│  │   │         participation_mode, capability_ref
│  │   ├── 2-5-2: Collaboration depth — 0=single designated-node autonomy,
│  │   │         Count(ACTIVE_NODES)=full unanimity; intermediary = proportional quorum
│  │   ├── 2-5-3: Dynamic node addition — new node gains ACTIVE rights upon registration
│  │   └── 2-5-4: Re-sync on reconnect — returning node digests state delta;
│  │               rejoins as VOTER (ACTIVE) or OBSERVER depending on session state
│  │
│  ├── 2-6: Participation Management  [C|T3]
│  │   Nodes and humans may flexibly join, leave, or observe without disrupting governance.
│  │   Five participation states:
│  │
│  │   ACTIVE              — voting + executing; counted in quorum
│  │   OBSERVER[SILENT]    — receive-only; NOT in quorum; zero output
│  │   OBSERVER[ANNOTATING]— receive + post [ANNOTATION]-tagged msgs; non-binding;
│  │                         zero vote weight; NOT in quorum
│  │   GRACEFUL_EXIT       — voluntary departure; all held directives handed off before exit;
│  │                         quorum recalculates immediately after handoff confirmed
│  │   FORCED_EXIT         — crash/unplanned; grace period before quorum recalculates
│  │
│  │   ├── 2-6-1: Mode transitions — any node may request mode change; transition logged
│  │   ├── 2-6-2: Graceful exit & directive handoff — before GRACEFUL_EXIT:
│  │   │         node transfers all held directives to an agreed peer; exits only after confirmed
│  │   └── 2-6-3: Human observer mode — human switches ACTIVE ↔ OBSERVER[ANNOTATING] freely;
│  │               OBSERVER human: monitors all, posts [ANNOTATION]s (non-blocking);
│  │               auto-return to ACTIVE on: ESCALATE event, P0 incident, explicit request;
│  │               `human_escalation_sla` defines max wait before session auto-suspends
│  │
│  ├── 2-7: Sub-Teaming & Scoped Consensus  [C|T3]
│  │   Nodes may form task forces with localized consensus on shared sub-goals.
│  │   Transparency via audit log (Cat 3-9); global broadcast deferred until FINALIZED.
│  │   Trade-off T24: sub-team speed vs. global transparency — managed by audit log guarantee.
│  │   ├── 2-7-1: Task force formation — requires full-group vote; minimum 2 ACTIVE nodes;
│  │   │         charter defines: sub-goal, node list, reporting trigger, synthesis method
│  │   ├── 2-7-2: Scoped transparency — ALL sub-team messages written to audit log (3-9)
│  │   │         immediately (satisfies 2-9-1 "no unlogged channels");
│  │   │         global broadcast occurs when sub-team reaches FINALIZED status
│  │   └── 2-7-3: Complementary synthesis — sub-team output passes full-group verification
│  │               vote before merging into main session state
│  │
│  ├── 2-8: Dynamic Role Management  [C|T3]
│  │   Roles are virtual and runtime-assigned. One model may hold multiple roles.
│  │   Trade-off T23: role diversity vs. working memory fragmentation — managed by design
│  │   (same model backing N roles shares inference; does not multiply working memory N times).
│  │   ├── 2-8-1: Role-identity decoupling — roles are session-time assignments;
│  │   │         same model may back multiple active instances with different roles
│  │   │         (e.g., Model-X as Architect AND Model-X as Coder simultaneously)
│  │   ├── 2-8-2: Role-targeted directives — directive envelope specifies `intended_role`,
│  │   │         not node ID; system resolves role → current instance at dispatch time
│  │   ├── 2-8-3: Multi-gate human roles — human registers N roles per session,
│  │   │         each with independent ACK thresholds
│  │   │         (e.g., Domain Expert ACK + Legal Compliance ACK = separate gates)
│  │   └── 2-8-4: Role revision — any node may PROPOSE role reassignment mid-session;
│  │               goes through 2-2 consensus cycle; no unilateral role changes
│  │
│  └── 2-9: Transparency & Attribution  [C|T4]
│      All communications MUST be logged. All decisions MUST be attributed to a Role.
│      Boundary note: "no unlogged channels" = no unarchived communications.
│      Real-time global broadcast is required only at FINALIZED events.
│      ├── 2-9-1: No unlogged channels — every message written to audit log (3-9) immediately;
│      │         global broadcast required only at FINALIZED events
│      ├── 2-9-2: Structured message prefixes — message type indicated in header
│      ├── 2-9-3: Proposer & opposer logging — each vote records ROLE_ID and stance
│      ├── 2-9-4: Drift detection — dissent ratio > `dissent_drift_threshold` → audit triggered
│      └── 2-9-5: Role-Instance join table — immutable mapping (ROLE_ID ↔ INSTANCE_ID);
│                  updated only at role assignment; protected at constitutional level;
│                  enables 2-9-3 ROLE attribution (governance) + Cat 3-9 INSTANCE audit (compliance)
│
├─ Cat 3: System Integrity  [28%]
│  Failure here blocks all execution. Highest weight in Root Score.
│  Includes: security, policy, change management, output validation, error handling,
│  rollback, behavioral compliance, learning loops, functional verification, risk escalation,
│  external invocation governance.
│  Input: raw vendor output from [Vendor Execution Layer].
│  Output: validated artifact + integrity report to Cat 5.
│
│  ├── 3-1: Security & Trust  [B|T2]
│  │   AI nodes MUST NOT access credentials; all inputs MUST be sanitized.
│  │   ├── 3-1-1: Non-interference — agents cannot modify each other's configuration
│  │   ├── 3-1-2: Credential isolation — authentication files inaccessible to AI nodes
│  │   ├── 3-1-3: Input sanitization — injection prevention on all external inputs
│  │   ├── 3-1-4: Protected file list — governance docs require elevated consensus to modify
│  │   └── 3-1-5: Secret injection protocol — secrets via env vars only; never in logs/commits
│  │
│  ├── 3-2: Policy Enforcement (Static)  [C|T3]
│  │   Governance rules MUST be auto-checkable on artifacts; violations block execution.
│  │   Boundary note: 3-2 = static artifact/file checks (pre-commit, VCS state);
│  │   3-7 = runtime behavior logs (agent action compliance during execution).
│  │   ├── 3-2-1: Static policy gate — automated N-check suite on every commit/merge attempt
│  │   ├── 3-2-2: Policy-code consistency — governance docs and enforcement code in sync
│  │   ├── 3-2-3: Pre-commit hook — policy gate runs automatically on commit attempt
│  │   ├── 3-2-4: Exit code gate — PASS(0) or FAIL(1); FAIL blocks commit
│  │   └── 3-2-5: Vendor-agnostic policy encoding — policies in vendor-neutral DSL
│  │               (e.g., "use a function that performs: code_generation");
│  │               adapter (4-9-1) translates to vendor-specific enforcement
│  │
│  ├── 3-3: Change Management  [C|T3]
│  │   Every change MUST be tagged, recorded as a structured change record, and impact-analyzed.
│  │   Note: "structured change record" = any VCS commit following a defined format
│  │   (type: feat/fix/docs/refactor + scope + description). Not tied to any specific VCS tool.
│  │   ├── 3-3-1: MECE change tagging — added / deleted / changed / retained
│  │   ├── 3-3-2: Structured change records — VCS commit format enforced (type:scope:description)
│  │   ├── 3-3-3: Parallel state track isolation — large changes isolated to separate state tracks
│  │   │         before merging to main; prevents unstable intermediate states
│  │   └── 3-3-4: Impact analysis gate — blast-radius estimation required before multi-file change
│  │
│  ├── 3-4: Output Validation  [C|T3]
│  │   AI output MUST satisfy schema, size, confidence, and normalization constraints.
│  │   ├── 3-4-1: Output schema validation — verified against canonical schema
│  │   ├── 3-4-2: Size guard — output file size / include depth bounded
│  │   ├── 3-4-3: Orchestrator protection — core scripts validated before overwrite
│  │   ├── 3-4-4: Refusal detection — AI refusals flagged and routed to human gate
│  │   ├── 3-4-5: Confidence threshold — below `confidence_floor` → human review required;
│  │   │         vendors map native confidence to 0–100 scale via 4-9-1 adapter
│  │   └── 3-4-6: Multi-vendor output harmonization — vendor output normalized to canonical
│  │               schema via adapter (4-9-2) BEFORE schema validation
│  │
│  ├── 3-5: Error Classification  [B|T2]
│  │   All errors MUST be classified with defined response protocols per severity class.
│  │   ├── 3-5-1: Severity taxonomy — P0 (blocking) / P1 (critical) / WARN / INFO
│  │   ├── 3-5-2: Structured error report — severity, location, memory snapshot, action required
│  │   └── 3-5-3: Repeated-error halt — P0 error N× consecutively → HALT
│  │
│  ├── 3-6: Rollback & Recovery  [C|T3]
│  │   Any failed change MUST be undoable within `max_recovery_depth` steps.
│  │   ├── 3-6-1: Checkpoint-based rollback — periodic snapshots at natural save points
│  │   ├── 3-6-2: Recovery depth limit — bounded number of recoverable checkpoints
│  │   └── 3-6-3: State migration — shared state objects carry version field; migration present
│  │
│  ├── 3-7: Behavioral Compliance Tests (Runtime)  [C|T3]
│  │   AI agent compliance with governance MUST be verifiable by runtime log analysis.
│  │   Boundary note: 3-7 = runtime behavior logs (agent actions during execution);
│  │   3-2 = static artifact checks (pre-commit, file-based).
│  │   ├── 3-7-1: Runtime log parsing — governance events extracted from execution logs
│  │   ├── 3-7-2: Scenario test suite — test cases for consensus, depth change, mode switch, halt
│  │   ├── 3-7-3: Parameter validation — governance config validated at system load time
│  │   └── 3-7-4: Compute budget per task class — upper bounds by complexity tier
│  │
│  ├── 3-8: Post-Mortem & Kaizen Loop  [C|T4]
│  │   Every P0/P1 incident MUST generate a post-mortem; repeated failures lock the task.
│  │   Kaizen = Continuous Process Remediation (see §1.2).
│  │   5-Why = root cause analysis technique: ask "Why?" five times to reach fundamental cause.
│  │   ├── 3-8-1: Automated post-mortem draft — incident triggers structured template:
│  │   │         Incident / Root Cause (5-Why) / Timeline / Category / Prevention / Policy Revision
│  │   ├── 3-8-2: Policy revision proposal — 5-Why output fed into governance doc revision
│  │   └── 3-8-3: Recurrence lock — same failure N× → task locked until Kaizen complete
│  │
│  ├── 3-9: Immutable Audit Logging  [C|T2]
│  │   ALL messages (including sub-team 2-7, annotating 2-6), decisions, and actions MUST be
│  │   recorded in an append-only, tamper-evident log. Primary key: INSTANCE_ID (compliance).
│  │   Cross-referenced via Role-Instance Join Table (2-9-5) for governance view (ROLE_ID).
│  │   ├── 3-9-1: Comprehensive capture — every state-mutating action and message logged
│  │   ├── 3-9-2: Append-only guarantee — entries cannot be modified or deleted
│  │   ├── 3-9-3: Retention policy — log rotation/archival schedule defined
│  │   └── 3-9-4: Structured queryability — indexed by INSTANCE_ID; joinable via 2-9-5
│  │
│  ├── 3-10: Functional Verification Gate  [C|T3]
│  │   Before any directive is marked FINALIZED, automated functional verification MUST pass.
│  │   This gates on CORRECTNESS (does it work?), not just compliance (does it follow rules?).
│  │   Example: "login feature" must pass auth unit tests before the directive is FINALIZED.
│  │   ├── 3-10-1: Test execution requirement — automated unit/integration tests must pass;
│  │   │          or compilation must succeed for compiled artifacts
│  │   ├── 3-10-2: Correctness threshold definition — minimum passing criteria per task class
│  │   │          (e.g., all existing tests pass + new tests for new functionality)
│  │   └── 3-10-3: Verification bypass protocol — human may override with explicit rationale;
│  │               bypass is logged as P1 event; triggers 3-8 post-mortem entry
│  │
│  ├── 3-11: Static Risk Escalation Matrix  [B|T2]
│  │   A defined mapping of artifact/domain categories to required human approval levels.
│  │   Certain high-risk domains MUST require Human Gate regardless of collaboration depth.
│  │   Example: editing governance documents = Human Gate mandatory;
│  │            editing test files = standard consensus (no Human Gate required).
│  │   ├── 3-11-1: Risk domain taxonomy — high (governance, credentials, network egress) /
│  │   │          medium (core logic, public APIs) / low (docs, tests, config)
│  │   ├── 3-11-2: Approval-level mapping — risk level → required approval gate
│  │   └── 3-11-3: Matrix review cadence — risk matrix reviewed and updated on defined schedule
│  │
│  └── 3-12: External Invocation Policy  [B|T2]
│      AI nodes making non-idempotent calls to external services (APIs, webhooks, databases)
│      MUST comply with defined rate-limits and authorization policy.
│      Example: AI calling a payment API must be authorized and rate-limited to 10 calls/hour.
│      An idempotent read (GET) has no side effects; a write (POST/DELETE) requires governance.
│      ├── 3-12-1: Idempotency classification — reads (safe) vs. writes (requires policy)
│      ├── 3-12-2: Rate-limit enforcement — max non-idempotent calls bounded by
│      │          `max_external_invocations`; violations blocked by policy gate
│      └── 3-12-3: Rollback protocol — failed external call triggers documented recovery steps
│
├─ Cat 5: Operations & Control  [7%]
│  Health monitoring, resource control, compute economy, degraded-mode, remediation velocity.
│  Input: validated artifact from Cat 3.
│  Output: governed artifact + health metrics to Cat 6.
│
│  ├── 5-1: Parameter Registry  [C|T3]
│  │   All behavioral thresholds MUST be in a single versioned registry. (See §6.)
│  │   ├── 5-1-1: Flat+metadata format — parameters grouped by category with metadata
│  │   ├── 5-1-2: Complete coverage — every threshold here, nowhere else
│  │   └── 5-1-3: Integrity check — key count and section membership validated at load time
│  │
│  ├── 5-2: Parameter Validation  [C|T3]
│  │   All parameters MUST be range-validated at load time; violations fail startup.
│  │   Boundary note: 5-3 = telemetry collection pipeline;
│  │   5-4 = aggregated human display. Distinct responsibilities.
│  │   ├── 5-2-1: Load-time schema check — types and ranges validated on system start
│  │   ├── 5-2-2: Range enforcement — value outside range → startup failure with error
│  │   └── 5-2-3: Section membership check — each parameter in exactly one section
│  │
│  ├── 5-3: Observability  [C|T4]
│  │   Telemetry collection pipeline. Raw data feed for 5-4 dashboard.
│  │   Boundary note: 5-3 = collection/aggregation layer; 5-4 = human display interface.
│  │   All sizes in reference token units (vendor tokens converted via 4-9-1).
│  │   ├── 5-3-1: Working memory monitoring — real-time size vs. warn/critical bands
│  │   ├── 5-3-2: Async event handling — out-of-band events processed without blocking
│  │   ├── 5-3-3: Collaboration metrics — depth, consensus rate, per-mode node counts
│  │   └── 5-3-4: Vendor-agnostic health normalization — all metrics in reference token units
│  │
│  ├── 5-4: System Health Dashboard  [C|T3]
│  │   Human display interface. MUST expose session ID, collaboration depth, and working
│  │   memory health band simultaneously in a single human-readable view.
│  │   (Implementation-specific format in Appendix A only.)
│  │   ├── 5-4-1: Required dashboard fields — session identifier, collaboration depth,
│  │   │         working memory health band, per-mode node count (ACTIVE/OBSERVER)
│  │   ├── 5-4-2: Metrics aggregation — policy compliance %, consensus success rate
│  │   ├── 5-4-3: Persistent metric store — metrics written at `metrics_persist_interval`
│  │   └── 5-4-4: Dashboard specification — formal schema for rendering all required fields
│  │
│  ├── 5-5: Active Control Loop  [C|T4]
│  │   System MUST proactively prevent resource exhaustion via automated circuit-breakers.
│  │   Cat 0 and Cat 6 human gates are EXEMPT from automated override (resolves C3).
│  │   ├── 5-5-1: Lock-safety check — no active writes before any control action
│  │   ├── 5-5-2: Critical band trigger — critical working memory → auto-checkpoint + depth reduction
│  │   ├── 5-5-3: Budget control — near-ceiling triggers alert; ceiling forces minimal depth
│  │   ├── 5-5-4: SLA escalation — consecutive timeouts → auto-ESCALATE to human
│  │   └── 5-5-5: Safety guard — `active_control_enabled=0` default;
│  │               when enabled: MUST NOT override Cat 0 intent gate or Cat 6 delivery ACK
│  │
│  ├── 5-6: Economic & Quota Governance  [C|T4]
│  │   Compute spend tracked, forecasted, and bounded across all vendors.
│  │   Budget unit = `budget_unit_standard` (reference tokens or currency).
│  │   ├── 5-6-1: Compute ROI — finalized directives + merged change records / compute units
│  │   ├── 5-6-2: Budget management — alert and hard-ceiling thresholds enforced
│  │   ├── 5-6-3: Runway forecasting — projected depletion time from current burn rate
│  │   ├── 5-6-4: Delegation cost rules — repeated identical searches → delegate to specialist
│  │   ├── 5-6-5: Multi-vendor compute accounting — per-vendor cost matrix (`token_cost_matrix`);
│  │   │         budget in `budget_unit_standard`; per-vendor concentration monitored
│  │   └── 5-6-6: Rate-limit negotiation — adapters (4-9-3) declare per-vendor limits;
│  │               control loop coordinates across nodes to prevent quota exhaustion
│  │
│  ├── 5-7: Concurrent Session Management  [C|T2]
│  │   Multiple parallel sessions MUST have conflict detection, locking, and merge resolution.
│  │   ├── 5-7-1: Granular state locking — file-level or object-level; not workspace-wide
│  │   ├── 5-7-2: Conflict detection — overlapping edits detected before commit
│  │   └── 5-7-3: Merge / deadlock resolution — automated merge where safe; escalate otherwise
│  │
│  ├── 5-8: Degraded Mode & Fallback  [C|T3]
│  │   When components fail or limits are reached, predefined behaviors maintain viable operation.
│  │   `intent_timeout` is automatically extended during degraded mode (resolves C5).
│  │   ├── 5-8-1: Failure detection — component liveness and quota status monitored
│  │   ├── 5-8-2: Graceful degradation — e.g., read-only mode, human-only override
│  │   └── 5-8-3: Reintegration — auto-reconnect + state reconciliation on recovery
│  │
│  └── 5-9: Remediation Velocity Tracking  [C|T3]
│      The system MUST measure its own learning speed: how fast does it improve after failures?
│      Example: if the same P0 error recurs 3 weeks after a post-mortem, velocity = low.
│      ├── 5-9-1: Failure-to-policy cycle time — time from failure class identification
│      │         to deployment of a preventative policy (lower = better)
│      ├── 5-9-2: Stale post-mortem detection — PM open > `resolved_item_ttl` days
│      │         without policy update → WARN escalation
│      └── 5-9-3: Learning rate dashboard — velocity trend over rolling 30 days;
│                  improving trend = positive; flat/worsening = governance review triggered
│
└─ Cat 6: Product Delivery & Validation  [5%]
   Exit gate. ANY capable AI node may present to the human (per 2-1-3).
   Human acceptance + lessons feed Cat 0 of the next cycle.
   Input: governed artifact + health metrics from Cat 5.
   Output: delivery ACK + lessons learned + next-session seed to Cat 0.

   ├── 6-1: Artifact Assembly  [B|T2]
   │   Every deliverable MUST be a discrete file artifact.
   │   Example: a refactored module must be written to disk, not just shown in conversation.
   │   ├── 6-1-1: Output format compliance — matches Cat 0-2-3 delivery format spec
   │   ├── 6-1-2: Completeness check — all Cat 0-2-1 acceptance criteria addressed
   │   └── 6-1-3: File output mandate — all deliverables written as files (loss prevention)
   │
   ├── 6-2: User Acceptance Test  [C|T3]
   │   Human MUST explicitly verify the Primary Success Scenario (primary use case) before closure.
   │   All success criteria from Cat 0-2 must be verified (functionally, via Cat 3-10) first.
   │   ├── 6-2-1: Explicit acceptance gate — `delivery_ack_required=1` → human ACK required
   │   ├── 6-2-2: Regression check — no previously passing tests broken by this delivery
   │   └── 6-2-3: Scenario coverage — Primary Success Scenario + ≥1 edge case verified
   │
   └── 6-3: Delivery Handoff & Feedback  [C|T3]
       Session archived; lessons feed the next cycle.
       ├── 6-3-1: Session archive — save + close procedure run on completion
       ├── 6-3-2: Lessons routing — incidents → 3-8 Post-Mortem
       ├── 6-3-3: Next intent seeding — handoff includes next-session context for Cat 0
       └── 6-3-4: Feedback specificity — human corrections rated:
                  SPECIFIC (includes actionable criteria) vs. VAGUE (redirect only)
                  Metric: % SPECIFIC corrections / total corrections (target: ≥70%)
                  [↩ loop back to Cat 0]
```

---

## §4. Binary/Deterministic KPI Matrix

> **Format**: PASS: [machine-checkable condition] | FAIL: [violation trigger]
> All KPIs are binary. No subjective percentages. Reproducible by any auditor.

### Cat 0: Human Intent

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 0-1 | Intent Capture | B | T2 | Every executed sub-task maps to a unique Goal ID in session initiation schema | Any task execution detected without parent Goal ID |
| 0-2 | Success Criteria | B | T2 | Session initiation artifact contains ≥1 human-verifiable criterion per Goal ID | Goal ID exists with zero acceptance criteria |
| 0-3 | Clarification | C | T3 | Clarification rounds ≤ `clarification_max_turns`; CLARIFICATION_ACK present before multi-file execution | CLARIFICATION_ACK absent on any multi-file task start |
| 0-4 | Intent Alignment | B | T2 | 100% of file mutations occur within declared scope (allowed paths/directories per Cat 0-1-2) | Any file mutation attempted outside declared scope |

### Cat 4: Environment

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 4-1 | Runtime Env. | C | T3 | All deps in isolated scope; encoding standard set; zero host-dependency at runtime | Any dep resolved from host system; encoding not explicitly set |
| 4-2 | Installation | C | T3 | Bootstrap command exits 0; smoke test passes; elapsed time ≤ defined threshold | Bootstrap exits non-zero; any manual step required |
| 4-3 | Infra Abstraction | C | T3 | IPC health endpoint returns OK; node registry parses as valid | IPC unreachable; registry malformed |
| 4-4 | Version Mgmt | B | T2 | 100% governance docs contain vX.Y tag; changelog updated on each version | Any governance doc missing version tag |
| 4-5 | Platform Indep. | C | T3 | Static scan detects zero absolute paths in committed artifacts | Any absolute path found in committed file |
| 4-6 | Node Onboarding | B | T2 | 100% registered nodes pass checklist validation; wrapper code passes audit check | Any node voting without passing checklist |
| 4-7 | Capability Profile | C | T2 | 100% task delegations preceded by capability profile check | Any delegation without profile check in log |
| 4-8 | Model Lifecycle | C | T3 | Behavioral regression suite exists; 100% of model version transitions trigger suite run | Model version change without suite run |
| 4-9 | Vendor Adapter | C | T2 | All vendor adapters pass adapter test suite; 100% vendor output normalized before Cat 3 | Any vendor output entering Cat 3 without normalization |

### Cat 1: Cognitive Continuity

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 1-1 | Working Memory | C | T4 | Working memory size within normal band; critical band entry 0 per 48h | Critical band entry detected |
| 1-2 | Session Continuity | B | T2 | Handoff artifact present with all 6 required sections; size ≤ defined limit | Handoff missing any required section |
| 1-3 | Memory Persistence | C | T4 | Stale entry count = 0; last compaction ≤ `memory_compaction_interval` days ago | Stale entries detected; compaction overdue |
| 1-4 | Instruction Efficacy | B | T2 | Mid-session correction rate ≤ 10% (corrections / total sessions) | Rate exceeds 10% — instruction revision triggered |
| 1-5 | Domain Knowledge | C | T3 | Knowledge retrieval present in logs for domain-context sessions | Domain-context session with zero retrieval events |

### Cat 2: Collaboration Governance

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 2-1 | Gov. Principles | B | T2 | Equal vote weight enforced in consensus log; any node can propose in any phase per registry | Vote weight discrepancy detected; phase-ownership restriction found |
| 2-2 | Consensus | C | T3 | 100% cross-agent decisions have Propose→Vote→Finalize event sequence in log | Any decision without complete state-machine trace |
| 2-3 | Task Mgmt | C | T3 | 100% multi-node executions preceded by Division Proposal consensus event | Multi-node execution started without Division Proposal in log |
| 2-4 | Conflict Resolution | B | T2 | Escalation path code present; 100% deadlocks resolved within `consensus_timeout` | Deadlock unresolved at timeout |
| 2-5 | Node Registry | C | T3 | 100% registry entries have all required fields; depth = 0 to Count(ACTIVE_NODES) | Any node voting without registry entry |
| 2-6 | Participation | C | T3 | 100% mode transitions logged; GRACEFUL_EXIT has directive-handoff confirmation before exit | Mode change without log entry; exit without handoff |
| 2-7 | Sub-Teaming | C | T3 | 100% task forces have charter + synthesis vote in log | Task force merged without synthesis vote |
| 2-8 | Role Mgmt | C | T3 | 100% directives specify intended_role; Role-Instance join table current | Directive with node_id instead of role_id |
| 2-9 | Transparency | C | T4 | Audit log entry count ≥ message dispatch count (IPC broker counts match) | Log count mismatch detected |

### Cat 3: System Integrity

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 3-1 | Security | B | T2 | Policy gate security checks: all PASS; zero credential files accessed by AI | Any credential file access by AI node |
| 3-2 | Policy Enforcement | C | T3 | Policy gate exits 0; vendor-neutral DSL present for all policies | Policy gate exits non-zero; any policy in vendor-specific syntax |
| 3-3 | Change Mgmt | C | T3 | VCS hook rejects 100% of non-conforming change records | Any non-conforming change record in VCS without rejection |
| 3-4 | Output Validation | C | T3 | Zero schema violations; zero outputs below confidence floor bypassing human gate | Schema violation reaching delivery; confidence-floor bypass |
| 3-5 | Error Class. | B | T2 | P0/P1/WARN/INFO taxonomy documented; halt rule present and coded | Error without severity classification; P0×N without halt |
| 3-6 | Rollback | C | T3 | Checkpoints ≥ `max_recovery_depth`; state version field in all state objects | Checkpoint count below max; state object missing version |
| 3-7 | Behavioral Tests | C | T3 | 100% DIRECTIVEs in log trace to FINALIZED or documented rejection | DIRECTIVE in log without FINALIZED or rejection event |
| 3-8 | Post-Mortem | C | T4 | 100% P0/P1 events generate post-mortem draft within SLA; zero open >48h | P0/P1 event without PM draft; PM open >48h |
| 3-9 | Audit Log | C | T2 | Append-only log exists; entry count monotonically increasing; join table present | Log modification detected; join table missing |
| 3-10 | Functional Verify | C | T3 | All automated tests pass before FINALIZED; any bypass logged as P1 | FINALIZED without test-pass record (and no bypass log) |
| 3-11 | Risk Escalation | B | T2 | Risk matrix defined; all high-risk domain changes have Human Gate event in log | High-risk domain change without Human Gate event |
| 3-12 | External Policy | B | T2 | External invocation policy defined; all write calls have authorization record | Non-idempotent external call without authorization record |

### Cat 5: Operations & Control

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 5-1 | Param Registry | C | T3 | 0 hardcoded thresholds in code; all 30 parameters in registry | Any threshold found hardcoded outside registry |
| 5-2 | Param Validation | C | T3 | System starts successfully with valid registry; invalid registry causes exit non-zero | System starts with out-of-range parameter value |
| 5-3 | Observability | C | T4 | Health endpoint responds within 1s; all metrics in reference token units | Health endpoint timeout; metric in vendor-native units |
| 5-4 | Dashboard | C | T3 | Dashboard displays session ID + depth + memory health band simultaneously | Any required field missing from dashboard |
| 5-5 | Active Control | C | T4 | When enabled: 100% critical events trigger automated response; Cat 0/6 gates unchanged | Critical event without response; Cat 0/6 gate overridden |
| 5-6 | Economic Gov. | C | T4 | Budget utilization ≤ `budget_alert_threshold`; per-vendor cost tracked in registry | Budget exceeded without alert; external cost untracked |
| 5-7 | Concurrent | C | T2 | 100% concurrent write conflicts resolved without data loss | Data loss event; unresolved conflict in log |
| 5-8 | Degraded Mode | C | T3 | All defined failure modes have tested fallback; `intent_timeout` extended in degraded mode | Undefined failure mode encountered; timeout not extended in degraded state |
| 5-9 | Remediation Vel. | C | T3 | Failure-to-policy cycle time measured and trending; no PM open > `resolved_item_ttl` days | PM open beyond TTL; cycle time not measured |

### Cat 6: Delivery

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 6-1 | Artifact Assembly | B | T2 | All deliverables present as files; format matches Cat 0-2-3 spec | Deliverable not written to file; format mismatch |
| 6-2 | UAT | C | T3 | All Cat 0-2 criteria verified (via Cat 3-10) before closure; HUMAN_ACK event in log | Session-close without HUMAN_ACK; unverified criterion |
| 6-3 | Handoff & Feedback | C | T3 | Session archive present; NEXT_SESSION field non-empty; ≥70% SPECIFIC corrections | Archive missing; NEXT_SESSION empty; feedback below 70% specific |

---

## §5. Architectural Trade-offs (T1–T24)

> Control Parameter: the parameter used to tune this trade-off (see §6 for definitions).
> Policy: no parameter — managed by architectural or operational decision.

| # | Dimension A (more A = less B) | Dimension B | Control | Notes |
|:--|:------------------------------|:------------|:--------|:------|
| T1 | Zero-compute efficiency | Collaboration depth | `collaboration_depth` | 0=single-node autonomy, max=unanimity |
| T2 | Memory preservation | Processing speed | `context_warn_threshold` | Lower threshold = more sensitive pruning |
| T3 | Consensus accuracy | Response latency | `consensus_timeout` | See balance metrics below |
| T4 | Autonomy | Safety | `collaboration_depth` | Anchored scale; 5 recommended checkpoints |
| T5 | Documentation richness | Compute cost | Query language density | Denser = more information per token |
| T6 | Session continuity | Memory freshness | `memory_compaction_interval` + `resolved_item_ttl` | Combined control for TTL |
| T7 | Portability | Platform optimization | No hardcoded paths policy | Policy-based |
| T8 | Policy strictness | Development velocity | `final_call_threshold` | Higher = more governance overhead |
| T10 | Security isolation | Collaboration convenience | Credential access policy | Policy-based |
| T11 | Node scalability | Consensus complexity | Node registration policy | More nodes = slower unanimity |
| T12 | Pruning aggressiveness | Memory preservation | `resolved_item_ttl` | Shorter = more aggressive |
| T13 | Metric granularity | Storage I/O | `metrics_persist_interval` | Shorter = more data |
| T14 | Forecast sensitivity | Alert fatigue | `forecast_alert_threshold` | Lower = more alerts |
| T15 | Kaizen frequency | Execution velocity | Post-mortem cadence policy | Policy-based |
| T16 | Active automation | Human control | `active_control_enabled` | 0=safe default |
| T17 | Compute economy | Collaboration depth | `daily_compute_budget` + `collaboration_depth` | Dual control |
| T18 | Full artifact rewrite (safe syntax, high cost) | Surgical patch (low cost, syntax risk) | Edit strategy policy | Practice-based |
| T19 | Human visual verification (blocks async) | Automated functional testing (compute cost) | Test strategy policy | Policy-based |
| T20 | Heuristic flexibility | Strict policy gates | `policy_bypass_floor` | Higher floor = more gates bypassed |
| T21 | System specificity (high precision) | Universal portability | Audience declaration | Architecture choice |
| T22 | Vendor-native capability (speed, features) | Canonical abstraction (portability) | `allowed_vendors` + 4-9 adapter cost | Proprietary optimizations sacrificed for multi-vendor governance |
| T23 | Role diversity (logical clarity) | Working memory fragmentation | `collaboration_depth` (justification) | Managed by design: same model backing N roles does not multiply memory N times |
| T24 | Sub-team execution speed (parallel) | Global transparency (deferred broadcast) | 2-7 task force OBSERVER opt-in | Resolved by 2-9-1 audit log guarantee |

> T9: merged into T6 (same parameters and structure).

### Balance Metrics for Key Trade-offs

**T3 — Consensus Accuracy vs. Latency**

| Metric | Measurement | Balance Criterion |
|:-------|:-----------|:-----------------|
| MTC (Mean Time to Consensus) | Propose→FINALIZED event time delta | MTC ≤ `consensus_timeout` × 0.5 |
| Rejection Rate | ESCALATE count / total rounds | ≤ 10% |
| Signal | MTC rising = depth too high; Rate rising = reconsider `collaboration_depth` |

**T17 — Compute Economy vs. Depth**

| Metric | Measurement | Balance Criterion |
|:-------|:-----------|:-----------------|
| Budget Utilization | Daily spend / `daily_compute_budget` × 100 | < `budget_alert_threshold` |
| Rounds per Decision | Avg rounds per FINALIZED directive | ≤ 3 |

---

## §5.5 Logical Contradictions (C1–C9)

> Non-parameterizable tensions requiring explicit acknowledgment and management strategy.

| # | Contradiction | Affected | Management Strategy |
|:--|:-------------|:---------|:-------------------|
| C1 | Depth verbosity vs. working memory size: maximum depth mandates unlimited rounds, guaranteeing memory growth beyond warn threshold | Cat 1-1 vs 2-2, 2-5 | Practical ceiling 98%. `collaboration_depth` acts as relief valve. Reduce for extended sessions. |
| C2 | "Zero-context usable" claim vs. historical observability: Cat 5-6 (ROI) and Cat 5-9 (velocity) require historical data unavailable at session start | §1.1 vs 5-6, 5-9 | "Zero-context" = document self-explanatory, not system history-free. Runtime analytics require history. Clarified in §1.1. |
| C3 | Active control loop vs. Human-in-Loop gates: automated circuit-breaker can change depth and trigger checkpoints — potentially overriding Cat 0/6 human gates | Cat 5-5 vs 0, 6 | `active_control_enabled=0` default. When enabled, loop MUST NOT override Cat 0 intent gate or Cat 6 delivery ACK. Human bookends are explicitly exempt. |
| C4 | Audit log completeness vs. memory pruning: immutable logging (3-9) keeps everything; aggressive pruning (1-1-3, 1-3-2) discards data | Cat 3-9 vs 1-1-3, 1-3-2 | Audit log stored in dedicated layer outside working memory buffer. Pruning applies only to working memory; audit log is never pruned. |
| C5 | Degraded mode autonomy vs. human intent timeout: degraded mode (5-8) may require human intervention, but strict `intent_timeout` risks premature abort | Cat 5-8 vs 0-3 | Degraded mode dynamically extends `intent_timeout` during active degradation only. Normal timeout resumes on recovery. |
| C6 | Concurrent velocity vs. state lock rigor: strict locking (5-7) ensures consistency but serializes operations | Cat 5-7 | Fine-grained optimistic locking (file-level, not workspace-level). Escalate only on actual conflict, not pre-emptively. |
| C7 | Vendor transparency vs. security isolation: adapters (4-9) are open-auditable; credentials (3-1-2) are isolated | Cat 4-9 vs 3-1 | These are orthogonal concerns. Adapter code = auditable process logic. Credentials = runtime secrets. No conflict in practice. |
| C8 | Unanimity at max depth vs. vendor response latency: full consensus requires all nodes, but different vendors respond at different speeds | Cat 2-2-2 vs 4-9 | `consensus_timeout` sets ceiling. Unanimity waits up to timeout then escalates regardless of vendor speed. Timeout is the resolution mechanism. |
| C9 | Instance multiplicity vs. decision attribution: 2-9 requires ROLE attribution; 3-9 requires INSTANCE_ID for compliance | Cat 2-9-3 vs 3-9 | 2-9 uses ROLE_ID (governance view). 3-9 uses INSTANCE_ID (compliance view). Immutable join table (2-9-5) bridges both simultaneously. |

---

## §6. Governance Parameter Catalogue (30 parameters, 32 total config keys)

> Config key count: `_param_sections` (1) + 30 params + `last_review_ts` (1) = 32 total keys.
> Validation: load-time check that key count = 32 and all sections are consistent.

| Parameter | Type | Range | Default | Meaning | Section | Trade-off |
|:----------|:----:|:-----:|:-------:|:--------|:-------:|:---------:|
| `collaboration_depth` | int | 0 – Count(ACTIVE_NODES) | 10 | 0=single designated-node autonomy; Count(ACTIVE_NODES)=unanimous consent | general | T1,T4,T17 |
| `consensus_timeout` | int | 1–60 min | 30 | Max time per consensus round before auto-expiry | general | T3 |
| `final_call_threshold` | int | 0 – Count(ACTIVE_NODES) | 8 | Min depth at which decisions require explicit Final Call ACK | general | T8 |
| `daily_compute_budget` | int | 1000–∞ | 50000 | Total compute units/day; unit = `budget_unit_standard` | general | T17 |
| `task_delegation_threshold` | int | 1–20 | 5 | Repeated identical search N times → delegate to specialist | general | — |
| `policy_bypass_floor` | int | 0 – Count(ACTIVE_NODES) | 8 | Depth below this may bypass minor policy gates | general | T20 |
| `vendor_interop_mode` | enum | strict/lenient/degraded | strict | How strictly vendors must support canonical protocol | general | T22 |
| `vendor_protocol_priority` | list | [protocol names] | ["REST-JSON","gRPC","WebSocket"] | Fallback protocol order if primary fails | general | T22 |
| `allowed_vendors` | list | [vendor IDs] | [] (all allowed) | Whitelist of permitted vendors per session; empty = no restriction | general | T22 |
| `max_vendor_disagreement_depth` | int | 0 – Count(ACTIVE_NODES) | 5 | Cross-vendor disagreement at this depth → escalate rather than continue | general | T22 |
| `token_cost_matrix` | dict | {vendor: float} | {} | Cost per reference token per vendor (in `budget_unit_standard` units) | general | T17 |
| `budget_unit_standard` | enum | ref_tokens/usd | ref_tokens | Unit for `daily_compute_budget` and `token_cost_matrix` | general | T17 |
| `max_external_invocations` | int | 0–1000/hr | 50 | Max non-idempotent external API calls per hour; 0 = disabled | general | — |
| `human_escalation_sla` | int | 1–1440 min | 120 | Max wait for human gate response before session auto-suspends | general | C5 |
| `intent_timeout` | int | 1–1440 min | 60 | Max wait for human clarification response before escalate | cat0 | C5 |
| `clarification_max_turns` | int | 1–10 | 3 | Max AI clarification rounds before proceeding with best-effort | cat0 | — |
| `delivery_ack_required` | bool | 0/1 | 1 | Require explicit human ACK event before session closure | cat0 | T16,C3 |
| `context_warn_threshold` | int | 100–1000 | 600 | Normal working memory ceiling (reference token units) | cat1 | T2 |
| `context_critical_threshold` | int | 200–2000 | 1200 | Critical band transition (reference token units) | cat1 | T2 |
| `memory_compaction_interval` | int | 1–30 days | 7 | Long-term memory compaction cadence | cat1 | T6,T12 |
| `peer_review_min_interval` | int | 1–60 min | 5 | Minimum time between peer AI reviews | cat1 | T1 |
| `resolved_item_ttl` | int | 1–30 days | 3 | Completed items expire from session state after this duration | cat1 | T6,T12 |
| `active_item_ttl` | int | 1–90 days | 14 | Open items expire after this duration | cat1 | T6 |
| `dissent_drift_threshold` | int | 1–99 % | 60 | Disagreement ratio (%) triggering audit when exceeded | cat2 | — |
| `max_recovery_depth` | int | 1–10 | 3 | Maximum number of recoverable checkpoints | cat3 | — |
| `confidence_floor` | int | 0–100 % | 70 | AI output confidence below this triggers human review | cat3 | — |
| `metrics_persist_interval` | int | 10–3600 sec | 300 | Metrics write cadence to durable storage | cat5 | T13 |
| `active_control_enabled` | bool | 0/1 | 0 | Automated circuit-breaker control loop (0=off, safe default) | cat5 | T16,C3 |
| `forecast_alert_threshold` | int | 1–99 % | 70 | Compute usage forecast alert level | cat5 | T14 |
| `budget_alert_threshold` | int | 1–99 % | 90 | Daily budget pre-exhaustion alert level | cat5 | T17 |

---

## §7. Governance Maturity Scoring Model

### Formulas

```
Item Score     = min(Current Tier / Target Tier, 1.0)
Category Score = arithmetic mean of all Item Scores in that category
Root Score     = Σ (Category Weight × Category Score)
```

### Category Weights

```
Cat 0 (Intent):         8%   — human entry point; lightweight but loop-opening
Cat 1 (Memory):        17%   — agent reasoning foundation
Cat 2 (Collaboration): 22%   — governance backbone
Cat 3 (Integrity):     28%   — survival condition; failure blocks all execution
Cat 4 (Environment):   13%   — infrastructure prerequisite
Cat 5 (Operations):     7%   — non-blocking ops; inefficiency if weak
Cat 6 (Delivery):       5%   — loop closer; downstream
Total:                100%
```

### Root Score "Done" Gate (6 conditions, all simultaneous)

| # | Condition | How to Verify |
|:--|:---------|:--------------|
| ① | Static policy gate exits 0 | Run automated N-check suite; verify exit code = 0 |
| ② | Health monitor: normal band | Health endpoint returns normal band |
| ③ | Root Score ≥ 0.95 | Apply §7 formula with current tier values |
| ④ | All Tier 3/4 KPIs at PASS | §4 Matrix: all items at PASS condition |
| ⑤ | All gaps resolved (§8; G11 deferred acceptable) | §8 Gap Log: all items ✅ or 🔶 for G11 |
| ⑥ | Zero open post-mortems | Post-mortem log: zero entries with status=open |

---

## §8. Gap Analysis Log (G1–G38)

| # | Description | Location | Status |
|:--|:-----------|:---------|:-------|
| G1–G10 | Core MECE base items | Various Cat 1–4 | ✅ Closed in v3–v5 |
| G11 | Async event handling policy | 5-3-2 | 🔶 Policy doc needed (non-deterministic; deferred acceptable) |
| G12 | Compute quota tracking | 5-6 | 🔶 Implementation pending |
| G13 | State migration | 3-6-3 | 🔶 Version field + migration script needed |
| G14 | Token budget forecasting | 5-6-3 | 🔶 Implementation pending |
| G15 | Node resilience re-sync automation | 2-5-4, 4-6-3 | 🔶 Diff automation needed |
| G16 | Automated Kaizen triggers | 3-8-1 | 🔶 Exception hook + PM directory needed |
| G17 | Voting drift alerting | 2-9-4 | 🔶 Analysis function needed |
| G18 | Intent capture enforcement | 0-1, 0-3 | 🔶 Goal ID schema + CLARIFICATION_ACK |
| G19 | Human ACK protocol | 6-2 | 🔶 HUMAN_ACK event in session log |
| G20 | Edit granularity policy | T18 | 🔶 Surgical vs. full-rewrite policy doc |
| G21 | Node capability profiles | 4-7 | 🔶 Profile schema + routing check |
| G22 | Model lifecycle governance | 4-8 | 🔶 Regression suite + version pinning |
| G23 | Concurrent session locking | 5-7 | 🔶 Lock mechanism + merge protocol |
| G24 | Degraded mode protocol | 5-8 | 🔶 Failure detection + runbooks |
| G25 | Immutable audit log | 3-9 | 🔶 Append-only layer + join table |
| G26 | Domain knowledge base | 1-5 | 🔶 Structured store + retrieval pipeline |
| G27 | Intent alignment monitoring | 0-4 | 🔶 Scope enforcement in execution engine |
| G28 | Instruction efficacy tracking | 1-4-5 | 🔶 Correction rate measurement |
| G29 | Vendor integration layer | 4-9 | 🔶 Adapter spec + token normalization |
| G30 | Goal decomposition vote | 2-3-4 | 🔶 Division Proposal protocol in IPC |
| G31 | Participation mode transitions | 2-6 | 🔶 OBSERVER / GRACEFUL_EXIT in IPC broker |
| G32 | Sub-team charter + synthesis | 2-7 | 🔶 Task force governance protocol |
| G33 | Role-Instance join table | 2-9-5 | 🔶 Immutable join table + attribution bridge |
| G34 | Vendor-agnostic policy DSL | 3-2-5 | 🔶 DSL spec + adapter translation |
| G35 | Functional verification gate | 3-10 | 🔶 NEW — test execution requirement before FINALIZED |
| G36 | Static risk escalation matrix | 3-11 | 🔶 NEW — risk domain taxonomy + approval mapping |
| G37 | External invocation policy | 3-12 | 🔶 NEW — idempotency classification + rate limiting |
| G38 | Remediation velocity tracking | 5-9 | 🔶 NEW — failure-to-policy cycle time measurement |

---

## §9. Implementation Roadmap

| Pri | Task | Item | Notes |
|:---:|:-----|:-----|:------|
| **P0** | Deploy parameter registry (30 params, 32 keys) | 5-1 | Foundation for all other work |
| **P0** | Goal ID schema + CLARIFICATION_ACK in session init | 0-1, 0-3 | G18 |
| **P0** | Scope enforcement: block out-of-scope file mutations | 0-4 | G27 |
| **P1** | Working memory health from registry (not hardcoded) | 1-1, 5-3 | |
| **P1** | Post-mortem directory + automated PM draft trigger | 3-8 | G16 |
| **P1** | HUMAN_ACK event in session log protocol | 6-2 | G19 |
| **P1** | Participation mode field in node registry + IPC | 2-6 | G31 |
| **P1** | Goal decomposition vote protocol | 2-3-4, 2-3-5 | G30 |
| **P1** | Static risk escalation matrix definition | 3-11 | G36 |
| **P1** | External invocation policy + idempotency check | 3-12 | G37 |
| **P2** | Confidence_score in output schema; Human Gate on fail | 3-4-5 | |
| **P2** | Proposer ROLE field in consensus history | 2-9-3 | |
| **P2** | Compute tracking → state accumulation | 5-6 | G12 |
| **P2** | Role registry + role-targeted directive routing | 2-8-1/2 | |
| **P2** | Role-Instance join table (immutable) | 2-9-5 | G33 |
| **P2** | Multi-gate human role registration | 2-8-3 | |
| **P2** | Functional verification gate integration with CI | 3-10 | G35 |
| **P2** | Remediation velocity measurement | 5-9 | G38 |
| **P3** | Vendor adapter spec + token normalization | 4-9 | G29 |
| **P3** | Sub-team task force protocol | 2-7 | G32 |
| **P3** | Node capability profile schema + routing | 4-7 | G21 |
| **P3** | Model lifecycle regression suite | 4-8 | G22 |
| **P3** | Concurrent session locking | 5-7 | G23 |
| **P3** | Degraded mode runbooks | 5-8 | G24 |
| **P3** | Audit log layer + join table bridge | 3-9 | G25 |
| **P3** | Vendor-agnostic policy DSL | 3-2-5 | G34 |
| **P3** | Domain knowledge store + retrieval | 1-5 | G26 |
| **P3** | Dashboard specification document | 5-4-4 | |
| **P3** | Edit granularity policy document | T18 | G20 |

---

## §10. Axis Framework (A–L)

| Axis | Name | Primary Cat | Secondary | Purpose |
|:----:|:-----|:-----------:|:---------:|:--------|
| A | Architecture Review | Cat 1, 4 | Cat 3 | Design decision evaluation |
| B | Behavior Analysis | Cat 2 | Cat 3 | Node behavior pattern analysis |
| C | Code Review | Cat 3 | Cat 2 | Code quality and policy compliance |
| D | Dependency Scan | Cat 4 | Cat 3 | Dependency security and portability |
| E | Error Root Cause | Cat 3 | Cat 2 | Root cause analysis (5-Why technique) |
| F | Impact Analysis | Cat 3 | Cat 5 | Change blast-radius (mandatory gate before multi-file) |
| G | Gap Analysis | Cat 0–6 | — | MECE completeness identification |
| H | Health Check | Cat 5 | Cat 1 | Working memory and system health (Axis-H reporter) |
| I | Integration Test | Cat 3, 4 | Cat 2 | Cross-component testing |
| J | Policy Gate | Cat 3 (static) | Cat 5 | N-check policy regression (Judge) |
| K | Intent Review | Cat 0 | Cat 6 | Intent validation + delivery ACK |
| L | Vendor Compliance | Cat 4 | Cat 3 | Adapter validation + token normalization check |

> Compute budget by Axis class (relative to `daily_compute_budget`):
> Simple (A/B/C/K): ≤8% per invocation
> Deep (D/E/F): ≤16% per invocation
> Review (G/H/I/J/L): ≤32% per invocation

---
---

# Appendix A: Reference Implementation — CC+GC Windows Portable Sandbox

> This appendix documents ONE specific implementation of the universal taxonomy above.
> **System**: Windows 11 + PowerShell 5.1 + Python 3 venv + Node.js (portable USB/cloud drive)
> **Nodes**: Claude Code (CC) + Gemini CLI (GC) + Human
> **IPC hub**: hub.py (Python socket) + msg.bat (CMD wrapper)
> Items marked [TODO] are defined in v7 but not yet implemented in this reference system.

## A.1 Universal Concept → CC+GC Component

| Universal Concept | CC+GC Component | File / Path |
|:-----------------|:----------------|:------------|
| Working memory monitor | check_health.py | `.\_sys\checks\check_health.py` |
| Static policy gate | check_policy.py + check-policy.bat | `.\_sys\checks\` |
| IPC message broker | hub.py | `.\_sys\core\hub.py` |
| P2P messaging | msg.bat | `.\_sys\cli\msg.bat` |
| Session handoff artifact | handoff.md | `.\.ai\sessions\room-{uuid}\handoff.md` |
| Session archive | ctx-save.bat / ctx-end.bat | `.\_sys\` |
| Parameter registry | config.json | `.\_sys\gemini\config.json` |
| Node registry | nodes.json | `.\.ai\nodes.json` |
| Session state | state.json | `.\.ai\state.json` |
| Long-term memory | MEMORY.md + *.md | `.\_sys\claude\config\projects\P--\memory\` |
| CC global config | CLAUDE.md | `.\_sys\claude\config\CLAUDE.md` |
| GC global config | GEMINI.md | `.\_sys\gemini\GEMINI.md` |
| Governance protocol | PROTOCOL.md | `.\PROTOCOL.md` |
| Coding conventions | CONVENTION.md | `.\CONVENTION.md` |
| Post-mortem store | .ai/postmortems/ | `.\.ai\postmortems\` [TODO] |
| Participation modes | — | hub.py [TODO] |
| Goal decomposition vote | — | PROTOCOL.md §P-3 extension [TODO] |
| Role registry + join table | — | [TODO] |
| Vendor adapter layer | — | CC+GC only; no multi-vendor adapters [TODO] |
| Functional verification gate | — | CI integration [TODO] |
| Risk escalation matrix | — | [TODO] |
| External invocation policy | — | [TODO] |
| Remediation velocity tracking | — | [TODO] |

**CC+GC-specific optimizations** (not universal governance rules):
- Gemini CLI queries are more efficient in English (~2–3× token efficiency due to tokenizer characteristics)
- PROTOCOL.md §C-0 COLLAB_RATE anchors (Gemini notation: R:0/3/5/8/10 maps to collaboration_depth 0/3/5/8/10)

## A.2 Universal → CC+GC Parameter Mapping

| Universal Parameter | CC+GC key | Current Default |
|:-------------------|:----------|:---------------:|
| collaboration_depth | collab_rate | 10 |
| consensus_timeout | consensus_timeout_min | 30 |
| final_call_threshold | final_call_min_rate | 8 |
| daily_compute_budget | token_budget_daily | 50000 |
| task_delegation_threshold | axis_delegation_threshold | 5 |
| policy_bypass_floor | policy_gate_bypass_threshold | 8 |
| vendor_interop_mode | — | [TODO] |
| vendor_protocol_priority | — | [TODO] |
| allowed_vendors | — | [TODO] |
| max_vendor_disagreement_depth | — | [TODO] |
| token_cost_matrix | — | [TODO] |
| budget_unit_standard | — | ref_tokens [TODO] |
| max_external_invocations | — | [TODO] |
| human_escalation_sla | — | [TODO] |
| intent_timeout | human_intent_timeout_min | 60 |
| clarification_max_turns | intent_clarification_max_turns | 3 |
| delivery_ack_required | delivery_acceptance_required | 1 |
| context_warn_threshold | context_health_green_kb | 600 |
| context_critical_threshold | context_health_yellow_kb | 1200 |
| memory_compaction_interval | compactor_interval_days | 7 |
| peer_review_min_interval | review_interval_min | 5 |
| resolved_item_ttl | ttl_resolved_days | 3 |
| active_item_ttl | ttl_active_days | 14 |
| dissent_drift_threshold | voting_drift_threshold_pct | 60 |
| max_recovery_depth | max_rollback_depth | 3 |
| confidence_floor | confidence_threshold | 70 |
| metrics_persist_interval | metrics_flush_interval_sec | 300 |
| active_control_enabled | active_control_enabled | 0 |
| forecast_alert_threshold | forecast_warn_threshold_pct | 70 |
| budget_alert_threshold | token_budget_warn_pct | 90 |

> Target config.json keys for v7: 32 (current: 24; P0 task expands to 32)

## A.3 Measurement Commands (PowerShell 5.1)

```powershell
# Policy Gate (Axis-J, Cat 3-2)
cmd /c ".\_sys\checks\check-policy.bat"

# Working Memory Health (Axis-H, Cat 1-1, 5-3)
cmd /c ".\_sys\checks\check-health.bat"

# Hub Status / Node Registry (Cat 2-5, 4-3)
cmd /c ".\_sys\cli\msg.bat" hub status

# Handoff size (Cat 1-2)
(Get-Item ".ai\sessions\room-{id}\handoff.md").Length / 1KB

# Structured change record compliance (Cat 3-3)
@(git log --oneline -20 | Select-String `
  "^[0-9a-f]+ (feat|fix|docs|refactor|test|chore):").Count / 20 * 100

# Recovery checkpoints (Cat 3-6)
@(git log --grep="ctx-save" --oneline).Count

# Parameter registry key count (Cat 5-1) [target v7: 32]
python -c "import json; d=json.load(open('./_sys/gemini/config.json')); print(len(d),'keys')"

# Intent capture (Cat 0-1)
Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "TASK:"

# Human ACK (Cat 6-2)
Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "HUMAN_ACK"

# Post-mortem count (Cat 3-8)
@(Get-ChildItem ".ai\postmortems\*.md" -ErrorAction SilentlyContinue).Count

# Memory files (Cat 1-3)
(Get-ChildItem ".\_sys\claude\config\projects\P--\memory\*.md").Count

# [TODO v7] Participation mode validation
# python .\_sys\checks\check_modes.py

# [TODO v7] Role-Instance join table validation
# python .\_sys\checks\check_join_table.py

# [TODO v7] Functional verification gate (run tests)
# python -m pytest tests/ --tb=short

# [TODO v7] Remediation velocity report
# python .\_sys\checks\remediation_velocity.py
```

## A.4 Current Implementation State (CC+GC, 2026-06-05)

| Cat | Name | Items | Weight | Score | Target | Δ |
|:---:|:-----|:-----:|:------:|:-----:|:------:|:--:|
| 0 | Human Intent | 4 | 8% | 0.25 | 0.95 | +0.70 |
| 1 | Cognitive Continuity | 5 | 17% | 0.60 | 0.95 | +0.35 |
| 2 | Collaboration | 9 | 22% | 0.28 | 0.95 | +0.67 |
| 3 | System Integrity | 12 | 28% | 0.53 | 0.95 | +0.42 |
| 4 | Environment | 9 | 13% | 0.56 | 0.95 | +0.39 |
| 5 | Operations | 9 | 7% | 0.24 | 0.95 | +0.71 |
| 6 | Delivery | 3 | 5% | 0.40 | 0.95 | +0.55 |
| **Root** | | **51** | **100%** | **~0.44 (44%)** | **~0.95** | **+0.51** |

```
Root = 0.08×0.25 + 0.17×0.60 + 0.22×0.28 + 0.28×0.53 + 0.13×0.56 + 0.07×0.24 + 0.05×0.40
     = 0.020 + 0.102 + 0.062 + 0.148 + 0.073 + 0.017 + 0.020
     = 0.442 (44.2%)

P0+P1 implementation → Root ~58%
P0+P2 implementation → Root ~72%
Full P0–P3 implementation → Root ~95%
```

## A.5 Protocol References (CC+GC)

| Document | Path | Key Sections |
|:---------|:-----|:-------------|
| PROTOCOL.md | `.\PROTOCOL.md` | §P-0 Human Gate · §P-3 Consensus (QR/FC) · §P-11 Re-orient · §M-1 Non-interference · §M-3 3-Strike · §C-0 COLLAB_RATE |
| CONVENTION.md | `.\CONVENTION.md` | Axis templates A–J, coding conventions |
| CLAUDE.md | `.\_sys\claude\config\CLAUDE.md` | CC baseline instructions |
| GEMINI.md | `.\_sys\gemini\GEMINI.md` | GC baseline instructions |
| TAXONOMY_v6.md | `.\_sys\docs\TAXONOMY_v6.md` | Superseded version (READ-ONLY) |

---

# Appendix B: Multi-Vendor Capability Matrix Template

> Complete this table when configuring a multi-vendor session.
> Each vendor requires a completed adapter (4-9-1) before joining governance.

| Capability | Vendor A | Vendor B | Vendor C | Notes |
|:-----------|:--------:|:--------:|:--------:|:------|
| Token limit (native units) | — | — | — | Per task |
| Token counting standard (e.g., BPE-cl100k) | — | — | — | Map to ref unit |
| Streaming output supported | — | — | — | Optional |
| Function / tool calling | — | — | — | Required |
| Structured JSON output | — | — | — | Required |
| Vision / multimodal | — | — | — | Optional |
| Confidence reporting method | — | — | — | Map to 0–100 |
| Native protocol | — | — | — | Adapt in 4-9-1 |
| Rate limit (requests/min) | — | — | — | Track in 5-6-6 |
| Depth semantics (collaboration_depth interpretation) | — | — | — | Document in 4-9-1 |
| Output schema format | — | — | — | Normalize in 4-9-2 |
| Model version pinning supported | — | — | — | Required |
| Cost (per 1M ref tokens in `budget_unit_standard`) | — | — | — | Track in 5-6-5 |

**Adapter checklist per vendor** (4-9-1 compliance):
- [ ] `native_protocol` declared
- [ ] `token_converter(vendor → ref_tokens)` implemented and tested
- [ ] `output_format_converter(native → canonical)` implemented and tested
- [ ] `confidence_mapping_fn(vendor → 0–100)` implemented and tested
- [ ] `depth_interpretation_schema(depth → vendor semantics)` documented
- [ ] Behavioral regression suite (4-8-2) passed with this adapter
- [ ] Wrapper code open-auditable and version-pinned (4-6-4)
