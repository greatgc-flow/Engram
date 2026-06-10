# MECE Taxonomy v6.0 — AI-Assisted Development: Governance Framework
### Universal · Workspace-Independent · Multi-Vendor · Symmetric Participation

> **Version**: 6.0 | **Date**: 2026-06-05
> **Review History**:
>   v3 (MECE base) → v4 (Human-in-Loop 7-cat) → v5 (Workspace-independent)
>   → v6 (Multi-vendor + Symmetric participation + Role diversity + Flexible participation)
> **Collaboration**: CC + GC (R:10, joint review across all rounds)
>   v6 restructure: CC (Gemini rate-limited during final pass; Gemini validation pending next session)
> **Supersedes**: TAXONOMY_v5.md (READ-ONLY)
> **Audience**: Any team building an AI-assisted software development system.
>
> **Main body (§0–§10)**: NO workspace-specific references.
> **Appendix A**: CC+GC implementation details.
> **Appendix B**: Multi-vendor capability matrix template.

---

## §0. How to Read This Document

This document defines the **governance layer** of AI-assisted development: the meta-system
ensuring AI agents and humans collaborate reliably, symmetrically, and adaptably — regardless
of which AI vendors are used or how many participants are involved.

**Reading modes:**
- **Universal** (§0–§10): Applies to any AI orchestration system, any vendor.
- **Implementation** (+ Appendix A): Concrete CC+GC reference.
- **Multi-vendor setup** (+ Appendix B): Template for cross-vendor deployments.

**Document map:**

| Section | Content |
|:--------|:--------|
| §1 | Scope, definitions, measurement tiers |
| §2 | Human-in-Loop lifecycle (7-category closed cycle) |
| §3 | Full MECE taxonomy tree (47 items) |
| §4 | Universal KPI & measurement matrix |
| §5 | Architectural trade-offs (T1–T21) |
| §5.5 | Logical contradictions (C1–C9) |
| §6 | Governance parameter catalogue (28 params) |
| §7 | Maturity scoring model |
| §8 | Gap analysis log (G1–G34) |
| §9 | Implementation roadmap |
| §10 | Axis framework (A–L) |
| Appendix A | CC+GC Windows Sandbox reference |
| Appendix B | Multi-vendor capability matrix template |

---

## §1. Scope & Universal Principles

### §1.1 Scope

**In scope**: Working memory lifecycle · multi-agent consensus · symmetric participation ·
division of labor · role management · policy enforcement · vendor abstraction · environment
portability · observability · human intent capture · flexible participation (join/leave/monitor) ·
compute governance · learning loops.

**Out of scope**: Target application business logic, domain models, UI/UX, deployment pipelines.

### §1.2 Definitions

| Term | Definition |
|:-----|:-----------|
| **AI Node** | Any AI agent in the system (language model, coding assistant, etc.) |
| **Human** | The operator who may vote, defines intent, and accepts deliverables |
| **Node Instance** | A specific running process of a model; one model → multiple instances possible |
| **Role** | A virtual function assigned to a node instance at runtime (e.g., Architect, Reviewer) |
| **Session** | A bounded unit of work: start → execution → delivery |
| **Directive** | A formally structured task assignment targeting a Role (not a node ID) |
| **Consensus** | A formally recorded agreement among all ACTIVE nodes on a decision |
| **Working Memory** | Active payload available to an AI node during a session |
| **Handoff** | Structured artifact carrying session state to next session or node |
| **Compute Budget** | Total allowed resource consumption (normalized units or currency) per period |
| **Participation Mode** | Node's engagement level: ACTIVE / OBSERVER[SILENT\|ANNOTATING] / GRACEFUL_EXIT / FORCED_EXIT |
| **Task Force** | A voted sub-group operating with scoped consensus on a shared sub-goal |
| **Vendor Adapter** | Software component translating a vendor's native API to the canonical protocol |
| **Reference Token** | A vendor-agnostic unit for measuring compute; defined at system initialization |

### §1.3 Measurement Tiers

#### Type B — Binary / Structural (existence is the metric)

| Tier | Criterion | Score |
|:----:|:----------|:-----:|
| T0 | Not defined | 0% |
| T1 | Draft exists | 50% |
| **T2** | **Enforced by automated check or system constraint** | **100%** |

#### Type C — Continuous / Operational (ongoing monitoring meaningful)

| Tier | Criterion | Score |
|:----:|:----------|:-----:|
| T0 | Not defined | 0% |
| T1 | Threshold/definition documented | 25% |
| T2 | Implementation exists; manual check possible | 50% |
| T3 | Automated check/script exists | 75% |
| **T4** | **Active monitoring + auto-alert on breach** | **100%** |

> **Score formula**: `min(Current Tier / Target Tier, 1.0)`

#### Measurement Failure Response

> "Depth" = the `collaboration_depth` parameter defined in §6.

| Collaboration Depth | Tier 3/4 failure action |
|:-------------------:|:------------------------|
| Maximum (e.g., Depth 10) | **HALT + ESCALATE** to human gate |
| Medium (e.g., Depth 5–8) | **WARN + continue** — log to metrics file |
| Minimal (e.g., Depth 0–3) | **LOG only** — no interruption |

### §1.4 Abstraction Principle

Universal parameter names are used throughout the main body.
Implementers map these to their specific systems (see Appendix A.2 for CC+GC mapping;
Appendix B for multi-vendor template).

---

## §2. Human-in-Loop Lifecycle

The 7 governance categories form a **closed feedback cycle**. Any participant (AI or Human)
may engage in any phase per the Governance Principles (Cat 2-1).

```
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────────────────┐   ║
║  │  Cat 0   │──►│  Cat 4   │──►│  Cat 1   │──►│      Cat 2         │   ║
║  │  Intent  │   │   Env.   │   │  Memory  │   │   Collaboration    │   ║
║  └──────────┘   └──────────┘   └──────────┘   └─────────┬──────────┘   ║
║       ▲                                                   │              ║
║       │                                                   ▼              ║
║  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────────────────┐   ║
║  │  Cat 6   │◄──│  Cat 5   │◄──│  Cat 3   │◄──│    (continued)     │   ║
║  │ Delivery │   │   Ops.   │   │Integrity │   │                    │   ║
║  └──────────┘   └──────────┘   └──────────┘   └────────────────────┘   ║
║       │                                                                  ║
║       └── Any node delivers → Human ACK → defines next intent ────────► ║
╚══════════════════════════════════════════════════════════════════════════╝

Key properties:
• Symmetric: Any registered node may propose, vote, or be assigned in any phase (Cat 2-1)
• Flexible: Nodes may join/leave/observe at any time (Cat 2-6)
• Multi-vendor: Vendor adapters (Cat 4-9) translate to canonical protocol before Cat 2
• Role-diverse: Roles are virtual; same model may hold multiple roles (Cat 2-8)
```

---

## §3. Full MECE Taxonomy Tree (47 Items)

> **Legend**: `[Type | Target Tier]` — B=Binary (T0–T2), C=Continuous (T0–T4)
> Ordering: Cat 0 → Cat 4 → Cat 1 → Cat 2 → Cat 3 → Cat 5 → Cat 6 (Human-in-Loop cycle)

```
AI-Assisted Development: Governance Framework
│
├─ Cat 0: Human Intent & Kickoff  [8%]
│  Entry gate. Every cycle starts here. ANY capable node may facilitate this phase.
│
│  ├── 0-1: Structured Intent Capture  [B|T2]
│  │   Every task MUST begin with a structured statement: Goal / Scope boundary / Constraints.
│  │   ├── 0-1-1: Goal statement — one sentence, desired outcome
│  │   ├── 0-1-2: Scope bounding — MVP boundary vs. deferred scope explicit
│  │   └── 0-1-3: Constraint identification — time, tech, budget, non-goals
│  │
│  ├── 0-2: Success Criteria Definition  [B|T2]
│  │   Human-verifiable acceptance criteria MUST be defined before execution.
│  │   ├── 0-2-1: Acceptance criteria — checkable conditions (not "AI believes done")
│  │   ├── 0-2-2: Quality thresholds — measurable bars (coverage %, latency, etc.)
│  │   └── 0-2-3: Delivery format — file path, output schema, artifact type
│  │
│  ├── 0-3: Clarification Protocol  [C|T3]
│  │   AI agents MUST surface ambiguities; humans respond within `clarification_max_turns`.
│  │   ├── 0-3-1: Ambiguity detection — ≥1 unclear requirement → ask
│  │   ├── 0-3-2: Turn limit — max `clarification_max_turns` rounds
│  │   └── 0-3-3: Intent confirmation — explicit human ACK before multi-file execution
│  │
│  └── 0-4: Continuous Intent Alignment  [B|T2]
│      During multi-step execution, ongoing actions MUST be periodically re-verified
│      against the original intent baseline.
│      ├── 0-4-1: Periodic re-verification — at defined execution milestones
│      ├── 0-4-2: Drift detection — flags when actions diverge from Cat 0 goals
│      └── 0-4-3: Escalation — ambiguity above threshold → human gate before proceeding
│
├─ Cat 4: Environment Portability  [13%]
│  Infrastructure and vendor integration. Must be ready before cognitive work (Cat 1).
│
│  ├── 4-1: Runtime Environment  [C|T3]
│  │   All runtime dependencies MUST be self-contained; no host system state assumed.
│  │   ├── 4-1-1: Language runtime isolation — dependencies isolated from host
│  │   ├── 4-1-2: Encoding consistency — character encoding explicitly set system-wide
│  │   ├── 4-1-3: Package manager isolation — scoped to project, not global
│  │   ├── 4-1-4: Environment variable scoping — per-agent isolation
│  │   └── 4-1-5: Zero-config hardening — execution policy meets minimum security baseline
│  │
│  ├── 4-2: Installation & Deployment  [C|T3]
│  │   A single bootstrap command MUST fully reconstruct the environment from scratch.
│  │   ├── 4-2-1: Zero-base bootstrap — one command = full reconstruction
│  │   ├── 4-2-2: Dependency bootstrapping — all tools and packages auto-installed
│  │   ├── 4-2-3: Smoke testing — post-install validation confirms environment health
│  │   └── 4-2-4: Parallel-safe naming — no collisions in concurrent setups
│  │
│  ├── 4-3: Infrastructure Abstraction  [C|T3]
│  │   IPC, messaging, and shared state MUST be decoupled from node identity.
│  │   ├── 4-3-1: Technology-neutral IPC — message broker decouples nodes from transport
│  │   ├── 4-3-2: Shared state layer — node-independent state accessible to all agents
│  │   ├── 4-3-3: Unified messaging interface — single entry point for all P2P messages
│  │   └── 4-3-4: Node heartbeat — liveness detection; absent nodes auto-abstain
│  │
│  ├── 4-4: Version Management  [B|T2]
│  │   All protocol and schema versions MUST be tracked; mismatches MUST be detectable.
│  │   ├── 4-4-1: Protocol versioning — all governance docs carry explicit version tags
│  │   ├── 4-4-2: Changelog maintenance — every version change documented
│  │   └── 4-4-3: Version format enforcement — standardized tag (e.g., vX.Y)
│  │
│  ├── 4-5: Platform Independence  [C|T3]
│  │   No absolute paths or OS-specific constructs in any committed artifact.
│  │   ├── 4-5-1: No hardcoded paths — all relative or environment-variable-based
│  │   ├── 4-5-2: Drive/mount abstraction — portable across OS and mount points
│  │   └── 4-5-3: Cross-platform path API — platform-agnostic path libraries enforced
│  │
│  ├── 4-6: Node Onboarding  [B|T2]
│  │   Any new AI node MUST be onboardable without manual intervention beyond registration.
│  │   ├── 4-6-1: Registration checklist — required fields before a node may vote
│  │   ├── 4-6-2: Required loading — new node ingests defined governance context
│  │   ├── 4-6-3: Resilience mechanics — heartbeat auto-abstain; re-sync on reconnect
│  │   └── 4-6-4: Wrapper governance — vendor adapter code must be open-auditable,
│  │               version-pinned, and tested against both native API and canonical protocol
│  │
│  ├── 4-7: Node Capability Profiling  [C|T2]
│  │   Every active node MUST have a formal capability profile consulted before task routing.
│  │   ├── 4-7-1: Standardized profile schema — required fields:
│  │   │         token_limit (model-native units), tools[], specialization[],
│  │   │         role_id (mutable, session-assigned), token_counting_standard,
│  │   │         vendor_id, native_protocol, output_format, confidence_mapping_fn
│  │   ├── 4-7-2: Dynamic capability discovery — profile updated on node state change
│  │   ├── 4-7-3: Profile-aware routing — delegation checks 4-7 profile first
│  │   ├── 4-7-4: Cross-vendor capability bridging — fallback when task exceeds node capability:
│  │   │         (1) chunk into sub-tasks, (2) route to capable node, (3) escalate to human
│  │   └── 4-7-5: Token normalization — all nodes normalize to reference token unit;
│  │               profile includes token_converter(vendor_tokens → ref_tokens)
│  │
│  ├── 4-8: Foundation Model Lifecycle  [C|T3]
│  │   Model transitions MUST trigger re-validation of capability and behavioral compliance.
│  │   ├── 4-8-1: Model version pinning — active model version recorded in configuration
│  │   ├── 4-8-2: Behavioral regression suite — per-vendor test run mandatory before upgrade
│  │   ├── 4-8-3: Rollback procedures — prior model recoverable within defined window
│  │   └── 4-8-4: Vendor model update detection — system detects vendor-initiated silent upgrades;
│  │               re-runs compliance suite before accepting outputs from new version
│  │
│  └── 4-9: Vendor Integration Layer  [C|T2]
│      Every AI vendor connects via a standardized adapter translating native APIs to the
│      canonical governance protocol. Enables any vendor combination.
│      Architecture:
│        [Claude] → [Adapter-A] ──►┐
│        [ChatGPT]→ [Adapter-B] ──►├─► [Canonical Protocol Hub] ──► Cat 2 Governance
│        [Gemini] → [Adapter-C] ──►┘
│      ├── 4-9-1: Vendor adapter specification — each adapter declares:
│      │         native_protocol (REST/gRPC/WebSocket/streaming/batch),
│      │         token_converter, output_format_converter,
│      │         confidence_mapping_fn (vendor → 0–100 scale),
│      │         depth_interpretation_schema (vendor semantics for collaboration_depth)
│      ├── 4-9-2: Output schema normalization — adapter converts vendor output to
│      │         canonical schema BEFORE entering governance pipeline
│      ├── 4-9-3: Rate-limit coordination — adapter declares tokens_per_min,
│      │         requests_per_day; active control loop (5-5) respects per-vendor limits
│      └── 4-9-4: Protocol fallback chain — ordered fallback when primary protocol fails;
│                  defined in `vendor_protocol_priority` parameter
│
├─ Cat 1: Cognitive Continuity  [17%]
│  Ensures all agents maintain coherent, persistent awareness across sessions.
│  Note: "Working memory" replaces vendor-specific term "context" throughout.
│
│  ├── 1-1: Working Memory Lifecycle  [C|T4]
│  │   Active working memory size MUST be monitored in reference token units;
│  │   thresholds trigger managed pruning to prevent cognitive degradation.
│  │   ├── 1-1-1: Size tracking — continuous measurement vs. warn/critical thresholds
│  │   ├── 1-1-2: Session state rolling — completed items archived; live state minimal
│  │   └── 1-1-3: Memory pruning — TTL scoring: (priority × 2) − age_in_days < 0 → archive
│  │
│  ├── 1-2: Session Continuity  [B|T2]
│  │   Every session MUST produce a machine-readable handoff enabling seamless resumption.
│  │   ├── 1-2-1: Scoped session workspace — isolated per-session directory, unique ID
│  │   ├── 1-2-2: Per-node summaries — bounded summary per node
│  │   │         (e.g., <4 KB text-equivalent or model-specific equivalent)
│  │   ├── 1-2-3: Re-orientation protocol — agent reads handoff before beginning work
│  │   ├── 1-2-4: Emergency handoff schema — minimum viable recovery fields:
│  │   │         executive_summary / technical_state / strategy_for_next_session
│  │   └── 1-2-5: Vendor-agnostic handoff format — per-node summaries converted to
│  │               canonical typed-JSON format; profile includes serializer/deserializer
│  │
│  ├── 1-3: Memory Persistence  [C|T4]
│  │   Learnings MUST persist across sessions in queryable structured form (weeks–months).
│  │   ├── 1-3-1: Long-term memory store — persistent file-based memory per project
│  │   ├── 1-3-2: Memory compaction — periodic pruning of stale/superseded entries
│  │   ├── 1-3-3: Symmetric sync — all nodes share the same memory corpus
│  │   ├── 1-3-4: Memory taxonomy — typed: user / feedback / project / reference
│  │   └── 1-3-5: Memory format registry — entries declare encoding_format;
│  │               retrieval layer handles heterogeneous formats (logic rule, example, fact)
│  │
│  ├── 1-4: Instruction Design & Efficacy  [B|T2]
│  │   Agents MUST have persistent structured instructions; quality MUST be measured.
│  │   ├── 1-4-1: Global agent configuration — persistent baseline instruction set per agent
│  │   ├── 1-4-2: Project-level overrides — project instructions take precedence
│  │   ├── 1-4-3: Query efficiency — instructions formatted for maximum information density
│  │   ├── 1-4-4: Task template library — structured templates for recurring task types
│  │   └── 1-4-5: Instruction efficacy tracking
│  │               Metric: % of sessions requiring mid-session correction due to ambiguity
│  │
│  └── 1-5: Persistent Domain Knowledge  [C|T3]
│      Domain-specific decisions, patterns, and business rules MUST persist beyond sessions.
│      ├── 1-5-1: Knowledge extraction — automated identification of reusable domain facts
│      ├── 1-5-2: Structured storage schema — queryable format (not raw session logs)
│      ├── 1-5-3: Contextual retrieval — knowledge injected into working memory on relevance
│      └── 1-5-4: Obsolescence protocol — outdated entries flagged/pruned on schedule
│
├─ Cat 2: Collaboration Governance  [22%]
│  All decisions, task division, participation, roles, and communication protocols.
│  Organized: Principles → Decisions → Execution → Participants → Communication
│  9 items.
│
│  ├── 2-1: Governance Principles  [B|T2]
│  │   FOUNDATIONAL. Defines the rights and access that ALL participants hold equally.
│  │   No phase of the lifecycle (Cat 0–6) is "owned" by any specific node type.
│  │   ├── 2-1-1: Symmetric phase participation — any registered node may PROPOSE, VOTE,
│  │   │         or be ASSIGNED work in any lifecycle phase (Cat 0 through Cat 6)
│  │   ├── 2-1-2: Equal vote weight — 1 ACTIVE node = 1 vote; no capability-based inflation;
│  │   │         Human ACTIVE = 1 vote; Human OBSERVER = 0 votes; both states are valid
│  │   ├── 2-1-3: Human interface assignment — any capable AI node may be dynamically
│  │   │         assigned to facilitate Cat 0 (intent) or Cat 6 (delivery) with the human;
│  │   │         conflict resolution: capability score first, then rotation;
│  │   │         Human may address any node directly at any time regardless of assignment
│  │   └── 2-1-4: Minimum rights — every registered node receives: broadcast access,
│  │               proposal rights, vote rights (when ACTIVE), directive rights
│  │
│  ├── 2-2: Consensus Protocol  [C|T3]
│  │   All cross-agent decisions MUST follow Propose → Vote → Finalize.
│  │   ├── 2-2-1: Propose-Vote-Finalize cycle — explicit state machine per decision
│  │   ├── 2-2-2: Quorum rules — majority = >50% of ACTIVE nodes;
│  │   │         unanimity at max depth (all ACTIVE nodes affirm);
│  │   │         minimum 1 ACTIVE node required for any decision
│  │   ├── 2-2-3: Final Call mechanism — depth ≥ `final_call_threshold` requires explicit ACK
│  │   ├── 2-2-4: Consensus history — all finalized decisions recorded with rationale and ROLE
│  │   └── 2-2-5: Protocol polymorphism — vendor adapter (4-9-1) translates native protocol
│  │               to canonical format BEFORE entering vote cycle; heterogeneous vendors supported
│  │
│  ├── 2-3: Collaborative Task Management  [C|T3]
│  │   Work division is collaboratively negotiated. Any node may propose, challenge, or revise.
│  │   ├── 2-3-1: Directive envelope — standard schema; `intended_role` field (not node ID)
│  │   ├── 2-3-2: Capability-based routing — routing checks 4-7 profile before assignment
│  │   ├── 2-3-3: Parallel execution policy — async when impact ranges non-overlapping,
│  │   │         OR when sub-team synthesis (2-7-3) will merge complementary contributions
│  │   ├── 2-3-4: Goal decomposition protocol — before multi-node execution, a Division Proposal
│  │   │         maps sub-tasks to roles/capabilities; MUST achieve consensus via 2-2 cycle;
│  │   │         split criteria: artifact boundary, dependency order, capability match
│  │   ├── 2-3-5: Assignment challenge — any ACTIVE node may challenge any task assignment;
│  │   │         grounds: capability mismatch, memory overload, inefficiency
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
│  │   └── 2-4-4: Stalled round cleanup — auto-expiry of rounds exceeding timeout threshold
│  │
│  ├── 2-5: Node Registry & Identity  [C|T3]
│  │   Every participating node MUST be registered; registry enables collaboration management.
│  │   ├── 2-5-1: Node registry — authoritative list with fields:
│  │   │         node_id, model_vendor, instance_id, role_id (mutable),
│  │   │         participation_mode, capability_ref
│  │   ├── 2-5-2: Collaboration depth — 0=single designated-node autonomy,
│  │   │         N=full ACTIVE-node consensus; intermediary = proportional quorum
│  │   ├── 2-5-3: Dynamic node addition — new node gains ACTIVE rights upon registration
│  │   └── 2-5-4: Re-sync on reconnect — returning node digests state delta;
│  │               rejoins as VOTER (ACTIVE) or OBSERVER depending on session state
│  │
│  ├── 2-6: Participation Management  [C|T3]
│  │   Nodes and humans may flexibly join, leave, or observe without disrupting governance.
│  │   Five participation states are defined:
│  │
│  │   ACTIVE          — voting + executing; counted in quorum
│  │   OBSERVER[SILENT]     — receive-only; NOT in quorum; zero output
│  │   OBSERVER[ANNOTATING] — receive + post [ANNOTATION]-tagged messages;
│  │                          non-binding; zero vote weight; NOT in quorum
│  │   GRACEFUL_EXIT   — voluntary departure; all held directives handed off first;
│  │                     quorum recalculates immediately after handoff confirmed
│  │   FORCED_EXIT     — crash/unplanned; grace period before quorum recalculates
│  │
│  │   ├── 2-6-1: Mode transitions — any node may request mode change; state change logged
│  │   ├── 2-6-2: Graceful exit & directive handoff — before GRACEFUL_EXIT, node transfers
│  │   │         all held directives to agreed peer; exit only after handoff confirmed
│  │   └── 2-6-3: Human observer mode — human may switch ACTIVE ↔ OBSERVER[ANNOTATING]
│  │               at any time; OBSERVER human: monitors all, posts [ANNOTATION]s (non-blocking);
│  │               auto-return to ACTIVE on: ESCALATE event, P0 incident, explicit request
│  │
│  ├── 2-7: Sub-Teaming & Scoped Consensus  [C|T3]
│  │   Nodes may form task forces operating with localized consensus on shared sub-goals.
│  │   Transparency is maintained via audit log (Cat 3-9), not real-time global broadcast.
│  │   ├── 2-7-1: Task force formation — requires full-group vote; minimum 2 ACTIVE nodes;
│  │   │         charter defines: sub-goal, node list, reporting trigger, synthesis method
│  │   ├── 2-7-2: Scoped transparency — ALL sub-team communications written to audit log
│  │   │         immediately (satisfies 2-9-1 "no unlogged channels");
│  │   │         global broadcast occurs when sub-team reaches FINALIZED status;
│  │   │         OBSERVER nodes may opt in to real-time sub-team feed
│  │   └── 2-7-3: Complementary synthesis — sub-team output passes full-group verification
│  │               vote before merging into main session state;
│  │               conflicting sub-team outputs → Cat 2-4 Conflict Resolution
│  │
│  ├── 2-8: Dynamic Role Management  [C|T3]
│  │   Roles are virtual and runtime-assigned. One model may hold multiple roles.
│  │   The same human may hold multiple roles with independent approval gates.
│  │   Role attribution (governance) uses ROLE_ID. Audit (compliance) uses INSTANCE_ID.
│  │   A protected Role-Instance Join Table bridges both views.
│  │   ├── 2-8-1: Role-identity decoupling — roles are session-time assignments;
│  │   │         same foundation model may back multiple active instances with different roles
│  │   │         (e.g., Model-X as Architect AND Model-X as Coder simultaneously)
│  │   ├── 2-8-2: Role-targeted directives — directive envelope specifies `intended_role`,
│  │   │         not node ID; system resolves role → current instance at dispatch time
│  │   ├── 2-8-3: Multi-gate human roles — human registers N roles per session,
│  │   │         each with independent ACK thresholds
│  │   │         (e.g., Domain Expert ACK + Legal Compliance ACK = separate gates)
│  │   └── 2-8-4: Role revision — any node may PROPOSE role reassignment mid-session;
│  │               goes through 2-2 consensus cycle; no unilateral role changes allowed
│  │
│  └── 2-9: Transparency & Attribution  [C|T4]
│      All communications MUST be logged. All decisions MUST be attributed to a Role.
│      "No unlogged channels" — transparency is ensured via audit log, not real-time broadcast.
│      ├── 2-9-1: No unlogged channels — every message written to audit log (3-9) immediately;
│      │         global broadcast required only at FINALIZED events
│      ├── 2-9-2: Structured message prefixes — message type indicated in header
│      ├── 2-9-3: Proposer & opposer logging — each vote records ROLE_ID and stance
│      ├── 2-9-4: Drift detection — dissent ratio > `dissent_drift_threshold` → audit triggered
│      └── 2-9-5: Role-Instance join table — immutable mapping (ROLE_ID ↔ INSTANCE_ID);
│                  updated only at role assignment events; protected at constitutional level;
│                  enables 2-9-3 ROLE attribution (governance) + Cat 3-9 INSTANCE audit (compliance)
│
├─ Cat 3: System Integrity  [28%]
│  Failure here blocks all execution. Highest weight in Root Score.
│
│  ├── 3-1: Security & Trust  [B|T2]
│  │   AI nodes MUST NOT access credentials; all inputs MUST be sanitized.
│  │   ├── 3-1-1: Non-interference — agents cannot modify each other's configuration
│  │   ├── 3-1-2: Credential isolation — auth files inaccessible to AI nodes
│  │   ├── 3-1-3: Input sanitization — injection prevention on all external inputs
│  │   ├── 3-1-4: Protected file list — constitutional docs require elevated consensus to modify
│  │   └── 3-1-5: Secret injection protocol — API keys via env vars only; never in logs/commits
│  │
│  ├── 3-2: Policy Enforcement  [C|T3]
│  │   All governance rules MUST be automatically checkable; violations block execution.
│  │   ├── 3-2-1: Static policy gate — automated N-check suite before each commit/merge
│  │   ├── 3-2-2: Policy-code consistency — governance docs and enforcement code in sync
│  │   ├── 3-2-3: Pre-commit hook — policy gate runs automatically on commit attempt
│  │   ├── 3-2-4: Exit code gate — PASS(0) or FAIL(1); FAIL blocks execution
│  │   └── 3-2-5: Vendor-agnostic policy encoding — policies expressed in vendor-neutral DSL
│  │               (e.g., "use a function that performs: code_generation");
│  │               adapter (4-9-1) translates to vendor-specific enforcement
│  │
│  ├── 3-3: Change Management  [C|T3]
│  │   Every change MUST be tagged, committed conventionally, and impact-analyzed.
│  │   ├── 3-3-1: MECE change tagging — added / deleted / changed / retained
│  │   ├── 3-3-2: Conventional commits — structured format enforced
│  │   ├── 3-3-3: Branch discipline — large changes on branches before merge
│  │   └── 3-3-4: Impact analysis gate — blast-radius estimation required before multi-file change
│  │
│  ├── 3-4: Output Validation  [C|T3]
│  │   AI output MUST satisfy schema, size, confidence, and vendor-normalization constraints.
│  │   ├── 3-4-1: Output schema validation — verified against canonical schema
│  │   ├── 3-4-2: Size guard — output file size / include depth bounded
│  │   ├── 3-4-3: Orchestrator protection — core scripts validated before overwrite
│  │   ├── 3-4-4: Refusal detection — AI refusals flagged and routed to human gate
│  │   ├── 3-4-5: Confidence threshold — below `confidence_floor` → human review required;
│  │   │         Vendors MUST map native confidence to 0–100 scale via 4-9-1 adapter
│  │   └── 3-4-6: Multi-vendor output harmonization — vendor-native output normalized to
│  │               canonical schema via adapter (4-9-2) BEFORE entering validation pipeline
│  │
│  ├── 3-5: Error Classification  [B|T2]
│  │   All errors MUST be classified with defined response protocols per severity class.
│  │   ├── 3-5-1: Severity taxonomy — P0 (blocking) / P1 (critical) / WARN / INFO
│  │   ├── 3-5-2: Structured error reporting — severity, location, memory snapshot, action
│  │   └── 3-5-3: Repeated-error halt — P0 N× consecutively → HALT
│  │
│  ├── 3-6: Rollback & Recovery  [C|T3]
│  │   Any failed change MUST be undoable within `max_recovery_depth` steps.
│  │   ├── 3-6-1: Checkpoint-based rollback — periodic snapshots at natural save points
│  │   ├── 3-6-2: Recovery depth limit — bounded recoverable checkpoints
│  │   └── 3-6-3: State migration — shared state objects carry version field; migration present
│  │
│  ├── 3-7: Behavioral Compliance Tests  [C|T3]
│  │   AI agent compliance with governance MUST be verifiable by runtime log analysis.
│  │   ├── 3-7-1: Runtime log parsing — governance events extracted from execution logs
│  │   ├── 3-7-2: Scenario test suite — test cases for consensus, depth change, mode switch, halt
│  │   ├── 3-7-3: Parameter validation — governance config validated at load time
│  │   └── 3-7-4: Compute budget per task class — defined upper bounds by complexity tier
│  │
│  ├── 3-8: Post-Mortem & Learning Loop  [C|T4]
│  │   Every P0/P1 incident MUST generate a post-mortem; repeated failures lock the task.
│  │   ├── 3-8-1: Automated PM draft — incident triggers structured template:
│  │   │         Incident / Root Cause (5-Why) / Timeline / Category / Prevention / Policy
│  │   ├── 3-8-2: Policy revision proposal — 5-Why output fed into governance doc revision
│  │   └── 3-8-3: Recurrence lock — same failure N× → task locked until Kaizen complete
│  │
│  └── 3-9: Immutable Audit Logging  [C|T2]
│      ALL messages (including sub-team 2-7 and annotating 2-6), decisions, and actions
│      MUST be recorded in an append-only, tamper-evident log.
│      Primary audit key: INSTANCE_ID (compliance).
│      Cross-referenced via Role-Instance Join Table (2-9-5) for governance view.
│      ├── 3-9-1: Comprehensive capture — every state-mutating action and message logged
│      ├── 3-9-2: Append-only guarantee — entries cannot be modified or deleted
│      ├── 3-9-3: Retention policy — log rotation/archival schedule defined
│      └── 3-9-4: Structured queryability — indexed by INSTANCE_ID; joinable via 2-9-5
│
├─ Cat 5: Operations & Control  [7%]
│  Health monitoring, resource control, compute economy, degraded-mode protocols.
│
│  ├── 5-1: Parameter Registry  [C|T3]
│  │   All behavioral thresholds MUST be in a single versioned registry. (See §6.)
│  │   ├── 5-1-1: Flat+metadata format — parameters grouped by category with metadata
│  │   ├── 5-1-2: Complete coverage — every threshold here, nowhere else
│  │   └── 5-1-3: Integrity check — key count and section membership validated at load time
│  │
│  ├── 5-2: Parameter Validation  [C|T3]
│  │   All parameters MUST be range-validated at load time; out-of-range values MUST fail.
│  │   ├── 5-2-1: Load-time schema check — types and ranges validated on startup
│  │   ├── 5-2-2: Range enforcement — value outside range → startup failure
│  │   └── 5-2-3: Section membership check — each parameter in exactly one section
│  │
│  ├── 5-3: Observability  [C|T4]
│  │   System health MUST be continuously measurable; bands defined in reference token units.
│  │   ├── 5-3-1: Working memory monitoring — real-time size vs. warn/critical bands
│  │   │         (in reference token units; per-vendor tokens converted via 4-9-1)
│  │   ├── 5-3-2: Async event handling — out-of-band events processed without blocking
│  │   ├── 5-3-3: Collaboration metrics — depth, consensus success rate, per-mode node counts
│  │   └── 5-3-4: Vendor-agnostic health normalization — health bands apply to reference units;
│  │               each vendor's actual token count converted via adapter (4-9-1)
│  │
│  ├── 5-4: System Health Dashboard  [C|T3]
│  │   Aggregated health MUST be viewable in a single human-readable status line.
│  │   ├── 5-4-1: Session header — ROOM:{id}|DEPTH:D{n}|HEALTH:{size_ref}({band})
│  │   │         showing per-mode node counts: ACTIVE:{n}, OBSERVER:{n}
│  │   ├── 5-4-2: Metrics aggregation — policy compliance %, consensus success %
│  │   ├── 5-4-3: Persistent metric store — metrics written at `metrics_persist_interval`
│  │   └── 5-4-4: Dashboard specification — formal schema for rendering all metrics
│  │
│  ├── 5-5: Active Control Loop  [C|T4]
│  │   System MUST proactively prevent resource exhaustion via automated circuit-breakers.
│  │   Cat 0 and Cat 6 human gates are EXEMPT from automated override (resolves C3).
│  │   ├── 5-5-1: Lock-safety check — no active writes before control action
│  │   ├── 5-5-2: Critical band trigger — critical working memory → auto-checkpoint + depth drop
│  │   ├── 5-5-3: Budget control — near-ceiling triggers alert; ceiling forces minimal depth
│  │   ├── 5-5-4: SLA escalation — consecutive timeouts → auto-ESCALATE to human
│  │   └── 5-5-5: Safety guard — `active_control_enabled=0` default;
│  │               when enabled: MUST NOT override Cat 0 intent gate or Cat 6 delivery ACK
│  │
│  ├── 5-6: Economic & Quota Governance  [C|T4]
│  │   Compute spend tracked, forecasted, and bounded across all vendors.
│  │   Budget expressed in `budget_unit_standard` (reference tokens or currency).
│  │   ├── 5-6-1: Compute ROI — finalized directives + merged PRs / normalized compute units
│  │   ├── 5-6-2: Budget management — alert and hard-ceiling thresholds
│  │   ├── 5-6-3: Runway forecasting — projected depletion from current burn rate
│  │   ├── 5-6-4: Delegation cost rules — repeated identical searches → delegate to specialist
│  │   ├── 5-6-5: Multi-vendor compute accounting — per-vendor cost matrix (`token_cost_matrix`);
│  │   │         budget tracked in `budget_unit_standard`; per-vendor concentration monitored
│  │   └── 5-6-6: Rate-limit negotiation — adapters (4-9-3) declare per-vendor limits;
│  │               control loop coordinates to prevent quota exhaustion
│  │
│  ├── 5-7: Concurrent Session Management  [C|T2]
│  │   Multiple parallel sessions MUST have conflict detection, locking, and merge resolution.
│  │   ├── 5-7-1: Granular state locking — file-level or object-level; not workspace-wide
│  │   ├── 5-7-2: Conflict detection — overlapping edits detected before commit
│  │   └── 5-7-3: Merge / deadlock resolution — automated merge where safe; escalate otherwise
│  │
│  └── 5-8: Degraded Mode & Fallback  [C|T3]
│      When components fail or limits are reached, predefined behaviors maintain viable operation.
│      `intent_timeout` is automatically extended during degraded mode (resolves C5).
│      ├── 5-8-1: Failure detection — component liveness and quota status monitored
│      ├── 5-8-2: Graceful degradation — e.g., read-only mode, human-only override
│      └── 5-8-3: Reintegration — auto-reconnect + state reconciliation on recovery
│
└─ Cat 6: Product Delivery & Validation  [5%]
   Exit gate. ANY capable AI node may present to the human (per 2-1-3).
   Human acceptance closes the loop; lessons feed Cat 0 of the next cycle.
│
   ├── 6-1: Artifact Assembly  [B|T2]
   │   Every deliverable MUST be a discrete file artifact; no conversation-only outputs.
   │   ├── 6-1-1: Output format compliance — matches Cat 0-2-3 delivery format
   │   ├── 6-1-2: Completeness check — all Cat 0-2-1 acceptance criteria addressed
   │   └── 6-1-3: File output mandate — all deliverables as files (loss prevention)
   │
   ├── 6-2: User Acceptance Test  [C|T3]
   │   Human MUST explicitly verify the primary use case before task closure.
   │   ├── 6-2-1: Explicit acceptance gate — `delivery_ack_required=1` → human ACK required
   │   ├── 6-2-2: Regression check — no previously working feature broken
   │   └── 6-2-3: Scenario coverage — golden path + ≥1 edge case verified
   │
   └── 6-3: Delivery Handoff & Feedback  [C|T3]
       Session state archived; lessons feed the next cycle via Cat 0.
       ├── 6-3-1: Session archive — save + close procedure on task completion
       ├── 6-3-2: Lessons routing — incidents → 3-8 Post-Mortem
       ├── 6-3-3: Next intent seeding — handoff includes next-session context
       └── 6-3-4: Feedback specificity — human corrections rated for specificity
                  Metric: % with actionable criteria vs. vague redirects
                  [↩ loop back to Cat 0]
```

---

## §4. Universal KPI & Measurement Matrix

### Cat 0: Human Intent

| ID | Type | Target | KPI | 100% Criterion |
|:---|:----:|:------:|:----|:---------------|
| 0-1 | B | T2 | % tasks initiated with full Goal/Scope/Constraint | ≥95% multi-file tasks structured |
| 0-2 | B | T2 | % tasks with human-verifiable criterion | ≥95% with ≥1 checkable criterion |
| 0-3 | C | T3 | MTTC ≤ clarification_max_turns | 0 tasks proceed with known ambiguity |
| 0-4 | B | T2 | % multi-step tasks with mid-execution re-verify | 100% tasks >N steps re-verified |

### Cat 4: Environment

| ID | Type | Target | KPI | 100% Criterion |
|:---|:----:|:------:|:----|:---------------|
| 4-1 | C | T3 | % deps isolated | All in isolated scope |
| 4-2 | C | T3 | MTTB (Mean Time to Bootstrap) | ≤5 min; 0 manual steps |
| 4-3 | C | T3 | IPC health exit code | Exit 0; registry valid |
| 4-4 | B | T2 | % governance docs versioned | 100%; changelog current |
| 4-5 | C | T3 | Hardcoded paths = 0 | 0 absolute paths |
| 4-6 | B | T2 | % nodes registered per checklist | 100%; wrapper auditable |
| 4-7 | C | T2 | % delegations checking capability profile | ≥95% |
| 4-8 | C | T3 | Regression suite present; required before upgrade | Suite exists; 0 bypassed upgrades |
| 4-9 | C | T2 | % vendors with compliant adapter | 100%; all protocols tested |

### Cat 1: Cognitive Continuity

| ID | Type | Target | KPI | 100% Criterion |
|:---|:----:|:------:|:----|:---------------|
| 1-1 | C | T4 | Memory utilization vs. warn threshold | Normal band ≥95%; critical = 0/48h |
| 1-2 | B | T2 | Handoff completeness | All 6 sections; bounded size |
| 1-3 | C | T4 | Stale entry count | Stale = 0; compaction within interval |
| 1-4 | B | T2 | % sessions needing mid-session correction | ≤5% correction rate |
| 1-5 | C | T3 | % domain-context sessions with retrieval | ≥80% where domain context needed |

### Cat 2: Collaboration Governance

| ID | Type | Target | KPI | 100% Criterion |
|:---|:----:|:------:|:----|:---------------|
| 2-1 | B | T2 | Governance principles documented; equal vote weight enforced | Phase access universal; 1-node=1-vote confirmed |
| 2-2 | C | T3 | % cross-agent decisions via documented cycle | ≥99% follow protocol |
| 2-3 | C | T3 | % tasks with Division Proposal vote before multi-node execution | 100% multi-node tasks |
| 2-4 | B | T2 | % deadlocks resolved within timeout | 100% resolved; escalation path present |
| 2-5 | C | T3 | Node registry completeness; mode tracking active | 100% fields per node; mode transitions logged |
| 2-6 | C | T3 | Participation mode transitions logged; quorum recalculates correctly | 100% mode changes recorded |
| 2-7 | C | T3 | % task forces with charter + synthesis vote | 100% properly formed and synthesized |
| 2-8 | C | T3 | % directives using intended_role (not node ID) | ≥95% role-targeted; join table valid |
| 2-9 | C | T4 | Unlogged messages = 0; ROLE attribution 100% | 0 unlogged; 100% attribution with join table |

### Cat 3: System Integrity

| ID | Type | Target | KPI | 100% Criterion |
|:---|:----:|:------:|:----|:---------------|
| 3-1 | B | T2 | Policy gate security checks | 0 credential exposures; all PASS |
| 3-2 | C | T3 | Policy gate exit code | Exit 0; vendor-neutral DSL present |
| 3-3 | C | T3 | % conventional commits | ≥95%; impact gate present |
| 3-4 | C | T3 | 0 schema violations; confidence compliance | 0 sub-threshold deliveries; harmonization present |
| 3-5 | B | T2 | Error taxonomy documented | P0/P1/WARN/INFO defined; halt rule present |
| 3-6 | C | T3 | Checkpoints ≥ max_recovery_depth | State version field present |
| 3-7 | C | T3 | ≥95% DIRECTIVE → FINALIZED traceability | 0 unauthorized modifications |
| 3-8 | C | T4 | PM generation rate = 100% | 0 open orphans >48h |
| 3-9 | C | T2 | % actions captured; join table valid | 100% capture; 0 deletions |

### Cat 5: Operations & Control

| ID | Type | Target | KPI | 100% Criterion |
|:---|:----:|:------:|:----|:---------------|
| 5-1 | C | T3 | 0 hardcoded thresholds | All in registry |
| 5-2 | C | T3 | 0 out-of-range params at startup | Load fails on invalid |
| 5-3 | C | T4 | Health check uptime 100% | Bands defined; vendor-normalized |
| 5-4 | C | T3 | Header completeness; per-mode counts | All fields present |
| 5-5 | C | T4 | 100% critical event response (when enabled) | 0 unhandled; human gates exempt |
| 5-6 | C | T4 | ≤100% budget; per-vendor accounting | 0 undetected pre-exhaustion events |
| 5-7 | C | T2 | % concurrent conflicts resolved | 100%; 0 data loss |
| 5-8 | C | T3 | % failure modes with tested fallback | 100%; timeout extended in degraded state |

### Cat 6: Delivery

| ID | Type | Target | KPI | 100% Criterion |
|:---|:----:|:------:|:----|:---------------|
| 6-1 | B | T2 | 100% deliverables as files | Format matches Cat 0-2-3 |
| 6-2 | C | T3 | ≥90% first-pass acceptance | HUMAN_ACK per task |
| 6-3 | C | T3 | 100% sessions archived | NEXT_SESSION non-empty; ≥70% specific feedback |

---

## §5. Architectural Trade-offs (T1–T21)

| # | Dimension A | Dimension B | Control Parameter | Notes |
|:--|:-----------|:-----------|:-----------------|:------|
| T1 | Zero-compute efficiency | Collaboration depth | `collaboration_depth` | 0=single-node, N=unanimous |
| T2 | Memory preservation | Processing speed | `context_warn_threshold` | Lower = more sensitive |
| T3 | Consensus accuracy | Response latency | `consensus_timeout` | Balance via MTC/rejection rate |
| T4 | Autonomy | Safety | `collaboration_depth` | Anchored scale |
| T5 | Documentation richness | Compute cost | Query language density | Dense language = efficient |
| T6 | Session continuity | Memory freshness | `memory_compaction_interval` + `resolved_item_ttl` | |
| T7 | Portability | Platform optimization | Path abstraction mandate | Policy |
| T8 | Policy strictness | Development velocity | `final_call_threshold` | Higher = safer |
| T10 | Security isolation | Collaboration convenience | Credential access policy | Policy |
| T11 | Node count (scalability) | Consensus complexity | Node registration policy | |
| T12 | Pruning aggressiveness | Memory preservation | `resolved_item_ttl` | |
| T13 | Metric granularity | Storage I/O | `metrics_persist_interval` | |
| T14 | Forecast sensitivity | Alert fatigue | `forecast_alert_threshold` | |
| T15 | Learning overhead | System evolution speed | Post-mortem cadence | Policy |
| T16 | Active automation | Human control | `active_control_enabled` | 0=safe default |
| T17 | Compute economy | Collaboration depth | `daily_compute_budget` + `collaboration_depth` | Dual control |
| T18 | Full rewrite (safe, expensive) | Surgical patch (cheap, risky) | Edit strategy policy | Practice |
| T19 | Human visual verification (blocks) | AI automated testing (compute) | Test strategy | Policy |
| T20 | Heuristic flexibility | Strict policy gates | `policy_bypass_floor` | |
| T21 | System specificity | Universal portability | Audience declaration | Architecture |

---

## §5.5 Logical Contradictions (C1–C9)

| # | Contradiction | Affected Items | Management |
|:--|:-------------|:--------------|:-----------|
| C1 | Depth verbosity vs. working memory size | Cat 1-1 vs 2-2, 2-5 | Practical ceiling 98%. `collaboration_depth` is relief valve. |
| C2 | "Zero-context usable" claim vs. historical observability | §1.1 vs 5-6, 3-8 | "Zero-context" = document self-explanatory; system still needs history for analytics. |
| C3 | Active control loop vs. Human-in-Loop gates | Cat 5-5 vs 0, 6 | `active_control_enabled=0` default; Cat 0/6 gates explicitly exempt from override. |
| C4 | Audit log completeness vs. memory pruning | Cat 3-9 vs 1-1-3, 1-3-2 | Audit log in dedicated storage layer separate from working memory; pruning applies only to memory layer. |
| C5 | Degraded mode autonomy vs. human intent timeout | Cat 5-8 vs 0-3 | Degraded mode dynamically extends `intent_timeout` during active degradation only. |
| C6 | Concurrent session velocity vs. state lock rigor | Cat 5-7 | Fine-grained optimistic locking (file-level, not workspace); escalate on actual conflict only. |
| C7 | Vendor transparency vs. security isolation | Cat 4-9 vs 3-1 | Adapters are open-auditable (4-6-4) but credential access remains isolated (3-1-2). Orthogonal concerns. |
| C8 | Unanimity at max depth vs. vendor response latency | Cat 2-2-2 vs 4-9 | `consensus_timeout` sets ceiling; unanimity waits up to timeout then escalates regardless of vendor speed. |
| C9 | Instance multiplicity vs. decision attribution | Cat 2-9-3 vs 3-9 | 2-9 uses ROLE_ID (governance); 3-9 uses INSTANCE_ID (compliance). Immutable join table (2-9-5) bridges both views simultaneously. |

---

## §6. Governance Parameter Catalogue (28 parameters, 30 total config keys)

| Parameter | Type | Range | Meaning | Category |
|:----------|:----:|:-----:|:--------|:--------:|
| `collaboration_depth` | int | 0–N | 0=single-node autonomy; N=unanimous consent | general |
| `consensus_timeout` | dur | 1–60 min | Max time per round before auto-expiry | general |
| `final_call_threshold` | int | 0–N | Min depth requiring explicit final ACK | general |
| `daily_compute_budget` | int | 1k–∞ | Compute units/day; unit = `budget_unit_standard` | general |
| `task_delegation_threshold` | int | 1–20 | Repeated identical searches N times → delegate | general |
| `policy_bypass_floor` | int | 0–N | Depth below this may bypass minor policy gates | general |
| `vendor_interop_mode` | enum | strict/lenient/degraded | How strictly vendors must support canonical protocol | general |
| `vendor_protocol_priority` | list | protocols | Fallback order if primary vendor protocol fails | general |
| `allowed_vendors` | list | vendor IDs | Whitelist of permitted vendors per session | general |
| `max_vendor_disagreement_depth` | int | 0–N | Cross-vendor disagreement at this depth → escalate | general |
| `token_cost_matrix` | dict | float/vendor | Cost per reference token per vendor | general |
| `budget_unit_standard` | enum | ref_tokens/usd | Unit for `daily_compute_budget` | general |
| `intent_timeout` | dur | 1min–24h | Max wait for human clarification before escalate | cat0 |
| `clarification_max_turns` | int | 1–10 | Max AI clarification rounds | cat0 |
| `delivery_ack_required` | bool | 0/1 | Require human ACK before task closure | cat0 |
| `context_warn_threshold` | size | 100–1000 | Normal working memory ceiling (ref token units) | cat1 |
| `context_critical_threshold` | size | 200–2000 | Critical band transition (ref token units) | cat1 |
| `memory_compaction_interval` | dur | 1–30 days | Long-term memory compaction cadence | cat1 |
| `peer_review_min_interval` | dur | 1–60 min | Minimum time between peer AI reviews | cat1 |
| `resolved_item_ttl` | dur | 1–30 days | Done items expire from session state after this | cat1 |
| `active_item_ttl` | dur | 1–90 days | Open items expire after this | cat1 |
| `dissent_drift_threshold` | % | 1–99 | Disagreement ratio triggering audit | cat2 |
| `max_recovery_depth` | int | 1–10 | Maximum recoverable checkpoints | cat3 |
| `confidence_floor` | % | 0–100 | AI confidence below this → human review | cat3 |
| `metrics_persist_interval` | dur | 10s–1h | Metrics write cadence | cat5 |
| `active_control_enabled` | bool | 0/1 | Automated circuit-breaker (0=off default) | cat5 |
| `forecast_alert_threshold` | % | 1–99 | Compute forecast alert level | cat5 |
| `budget_alert_threshold` | % | 1–99 | Daily budget pre-exhaustion alert | cat5 |

> Total config keys: **30** (`_param_sections` + 28 params + `last_review_ts`)

---

## §7. Governance Maturity Scoring Model

```
Item Score     = min(Current Tier / Target Tier, 1.0)
Category Score = arithmetic mean of Item Scores in category
Root Score     = Σ (Category Weight × Category Score)

Weights:
  Cat 0 =  8%  (human entry; lightweight but loop-opening)
  Cat 1 = 17%  (agent reasoning foundation)
  Cat 2 = 22%  (collaboration backbone)
  Cat 3 = 28%  (survival condition; failure blocks all)
  Cat 4 = 13%  (infrastructure prerequisite)
  Cat 5 =  7%  (non-blocking ops; inefficiency if weak)
  Cat 6 =  5%  (loop closer; downstream)
  Total = 100%

Weight rationale:
  Cat 3 highest: integrity failure = no execution. Infrastructure for safety.
  Cat 2 second: without governance, collaboration collapses.
  Cat 1 third: without working memory, agents cannot reason.
```

**"Done" gate** (6 conditions simultaneous):
1. Static policy gate exits 0
2. Health monitoring reports normal band
3. Root Score ≥ 0.95
4. All Tier 3/4 KPIs at target (§4)
5. All gaps resolved (§8; G11 deferred OK)
6. Zero open post-mortems

---

## §8. Gap Analysis Log

| # | Gap | Location | Status |
|:--|:----|:---------|:-------|
| G1–G10 | Core MECE base | Various Cat 1–4 | ✅ Closed in v3–v5 |
| G11 | Async event handling | 5-3-2 | 🔶 Policy doc needed (deferred OK) |
| G12–G14 | Compute quota / forecasting / state migration | 5-6, 3-6-3 | 🔶 Implementation pending |
| G15 | Node resilience re-sync automation | 2-5-4, 4-6-3 | 🔶 Diff automation needed |
| G16 | Automated Kaizen triggers | 3-8-1 | 🔶 Exception hook + PM directory |
| G17 | Voting drift alerting | 2-9-4 | 🔶 Analysis function needed |
| G18 | Intent capture enforcement | 0-1, 0-3 | 🔶 CLARIFICATION_ACK in handoff |
| G19 | User acceptance testing | 6-2 | 🔶 HUMAN_ACK in handoff needed |
| G20 | Edit granularity policy | T18 | 🔶 Surgical vs. rewrite policy doc |
| G21 | Node capability profiles | 4-7 | 🔶 Profile schema + routing check |
| G22 | Model lifecycle governance | 4-8 | 🔶 Regression suite + version pinning |
| G23 | Concurrent session locking | 5-7 | 🔶 Lock mechanism + merge protocol |
| G24 | Degraded mode protocol | 5-8 | 🔶 Failure detection + runbooks |
| G25 | Immutable audit log | 3-9 | 🔶 Append-only layer + join table |
| G26 | Domain knowledge base | 1-5 | 🔶 Structured store + retrieval |
| G27 | Intent alignment monitoring | 0-4 | 🔶 Mid-execution re-verify protocol |
| G28 | Instruction efficacy tracking | 1-4-5 | 🔶 Misinterpretation rate measurement |
| G29 | Vendor integration layer | 4-9 | 🔶 Adapter spec + token normalization |
| G30 | Goal decomposition vote | 2-3-4 | 🔶 Division Proposal protocol |
| G31 | Participation mode transitions | 2-6 | 🔶 OBSERVER/GRACEFUL_EXIT protocol |
| G32 | Sub-team charter + synthesis | 2-7 | 🔶 Task force governance |
| G33 | Role-Instance join table | 2-9-5 | 🔶 Attribution + audit bridge |
| G34 | Vendor-agnostic policy DSL | 3-2-5 | 🔶 Vendor-neutral policy encoding |

---

## §9. Implementation Roadmap

| Pri | Task | Item | Notes |
|:---:|:-----|:-----|:------|
| **P0** | Deploy parameter registry (28 params, 30 keys) | 5-1 | Foundation for everything |
| **P0** | Intent capture schema in session handoff | 0-1, 0-2 | G18 |
| **P1** | Health monitoring thresholds from registry | 1-1, 5-3 | |
| **P1** | Post-mortem directory + automated PM draft | 3-8 | G16 |
| **P1** | CLARIFICATION_ACK + HUMAN_ACK in handoff template | 0-3, 6-2 | G18, G19 |
| **P1** | Participation mode field in node registry | 2-6, 2-5-1 | G31 |
| **P1** | Goal decomposition vote protocol | 2-3-4/5 | G30 |
| **P2** | Confidence_score in output schema | 3-4-5 | |
| **P2** | Proposer ROLE field in consensus history | 2-9-3 | |
| **P2** | Compute tracking (tokens → state accumulation) | 5-6 | G12 |
| **P2** | Role registry + role-targeted directive routing | 2-8-1/2 | |
| **P2** | Role-Instance join table (immutable) | 2-9-5 | G33 |
| **P2** | Multi-gate human role registration | 2-8-3 | |
| **P3** | Vendor adapter specification + token normalization | 4-9 | G29 |
| **P3** | Sub-team task force protocol | 2-7 | G32 |
| **P3** | Node capability profile schema + routing | 4-7 | G21 |
| **P3** | Model lifecycle regression suite | 4-8 | G22 |
| **P3** | Concurrent session locking | 5-7 | G23 |
| **P3** | Degraded mode runbooks | 5-8 | G24 |
| **P3** | Audit log layer + join table bridge | 3-9 | G25 |
| **P3** | Vendor-agnostic policy DSL | 3-2-5 | G34 |

---

## §10. Axis Framework (A–L)

| Axis | Name | Primary Cat | Secondary | Purpose |
|:----:|:-----|:-----------:|:---------:|:--------|
| A | Architecture Review | Cat 1, 4 | Cat 3 | Design decision review |
| B | Behavior Analysis | Cat 2 | Cat 3 | Node behavior pattern analysis |
| C | Code Review | Cat 3 | Cat 2 | Code quality and policy compliance |
| D | Dependency Scan | Cat 4 | Cat 3 | Dependency security and portability |
| E | Error Root Cause | Cat 3 | Cat 2 | Root cause analysis |
| F | Impact Analysis | Cat 3 | Cat 5 | Change blast-radius (mandatory gate) |
| G | Gap Analysis | Cat 0–6 | — | MECE completeness identification |
| H | Health Check | Cat 5 | Cat 1 | Working memory and system health |
| I | Integration Test | Cat 3, 4 | Cat 2 | Cross-component testing |
| J | Policy Gate | Cat 3 (static) | Cat 5 | N-check policy regression |
| K | Intent Review | Cat 0 | Cat 6 | Intent validation + delivery ACK |
| L | Vendor Compliance | Cat 4 | Cat 3 | Adapter validation + normalization |

> Compute budget by class (relative to `daily_compute_budget`):
> Simple (A/B/C/K): ≤8% · Deep (D/E/F): ≤16% · Review (G/H/I/J/L): ≤32%

---
---

# Appendix A: Reference Implementation — CC+GC Windows Portable Sandbox

> One specific implementation of this taxonomy.
> **System**: Windows 11 + PowerShell 5.1 + Python 3 venv + Node.js (portable)
> **Nodes**: Claude Code (CC) + Gemini CLI (GC) + Human
> **IPC**: hub.py + msg.bat
> Items marked [TODO] are defined in v6 but not yet implemented.

## A.1 Universal → CC+GC Component Map

| Universal Concept | CC+GC Component | Path |
|:-----------------|:----------------|:-----|
| Working memory monitor | check_health.py | `.\_sys\checks\` |
| Static policy gate | check_policy.py + check-policy.bat | `.\_sys\checks\` |
| IPC message broker | hub.py | `.\_sys\core\hub.py` |
| P2P messaging interface | msg.bat | `.\_sys\cli\msg.bat` |
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
| Vendor adapter layer | — | CC+GC only; multi-vendor adapters [TODO] |

**CC+GC-specific optimization** (not universal rule):
Gemini CLI queries are more efficient in English (2–3× token efficiency).
This is a Gemini CLI optimization, not a universal governance principle.

**PROTOCOL.md key section reference:**
- §P-0 Human Gate · §P-3 Consensus (+ QR Quorum + FC Final Call) · §P-11 Re-orient
- §M-1 Non-interference · §M-3 3-Strike halt
- §C-0 COLLAB_RATE anchors (Gemini notation: R:0/3/5/8/10 = collaboration_depth 0/3/5/8/10)

## A.2 Parameter Name Mapping (Universal → CC+GC)

| Universal | CC+GC key | Default | Range |
|:----------|:----------|:-------:|:-----:|
| collaboration_depth | collab_rate | 10 | 0–10 |
| consensus_timeout | consensus_timeout_min | 30 | 1–60 min |
| final_call_threshold | final_call_min_rate | 8 | 0–10 |
| daily_compute_budget | token_budget_daily | 50000 | tokens |
| task_delegation_threshold | axis_delegation_threshold | 5 | 1–20 |
| policy_bypass_floor | policy_gate_bypass_threshold | 8 | 0–10 |
| vendor_interop_mode | — | — | [TODO] |
| vendor_protocol_priority | — | — | [TODO] |
| allowed_vendors | — | — | [TODO] |
| max_vendor_disagreement_depth | — | — | [TODO] |
| token_cost_matrix | — | — | [TODO] |
| budget_unit_standard | — | ref_tokens | [TODO] |
| intent_timeout | human_intent_timeout_min | 60 | 1–1440 min |
| clarification_max_turns | intent_clarification_max_turns | 3 | 1–10 |
| delivery_ack_required | delivery_acceptance_required | 1 | 0/1 |
| context_warn_threshold | context_health_green_kb | 600 | 100–1000 KB |
| context_critical_threshold | context_health_yellow_kb | 1200 | 200–2000 KB |
| memory_compaction_interval | compactor_interval_days | 7 | 1–30 days |
| peer_review_min_interval | review_interval_min | 5 | 1–60 min |
| resolved_item_ttl | ttl_resolved_days | 3 | 1–30 days |
| active_item_ttl | ttl_active_days | 14 | 1–90 days |
| dissent_drift_threshold | voting_drift_threshold_pct | 60 | 1–99 % |
| max_recovery_depth | max_rollback_depth | 3 | 1–10 |
| confidence_floor | confidence_threshold | 70 | 0–100 % |
| metrics_persist_interval | metrics_flush_interval_sec | 300 | 10–3600 s |
| active_control_enabled | active_control_enabled | 0 | 0/1 |
| forecast_alert_threshold | forecast_warn_threshold_pct | 70 | 1–99 % |
| budget_alert_threshold | token_budget_warn_pct | 90 | 1–99 % |

> Target config.json keys: 30 (current: 24; P0 task expands to 30)

## A.3 Key Measurement Commands (PowerShell 5.1)

```powershell
# Policy Gate (3-2)
cmd /c ".\_sys\checks\check-policy.bat"

# Working Memory Health (1-1, 5-3)
cmd /c ".\_sys\checks\check-health.bat"

# Hub Status / Node Registry (2-5, 4-3)
cmd /c ".\_sys\cli\msg.bat" hub status

# Handoff size (1-2)
(Get-Item ".ai\sessions\room-{id}\handoff.md").Length / 1KB

# Conventional commit compliance (3-3)
@(git log --oneline -20 | Select-String `
  "^[0-9a-f]+ (feat|fix|docs|refactor|test|chore):").Count / 20 * 100

# Recovery checkpoints (3-6)
@(git log --grep="ctx-save" --oneline).Count

# Parameter key count (5-1)
python -c "import json; d=json.load(open('./_sys/gemini/config.json')); print(len(d),'keys')"
# Target v6: 30 keys

# Intent capture (0-1)
Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "TASK:"

# Human ACK (6-2)
Select-String -Path ".ai\sessions\room-*\handoff.md" -Pattern "HUMAN_ACK"

# [TODO v6] Participation mode check
# python .\_sys\checks\check_modes.py

# [TODO v6] Role-Instance join table validation
# python .\_sys\checks\check_join_table.py
```

## A.4 Current Implementation State (CC+GC, 2026-06-05)

| Cat | Items | Weight | Score | Target | Δ |
|:---:|:-----:|:------:|:-----:|:------:|:--:|
| 0 | 4 | 8% | 0.25 | 0.90 | +0.65 |
| 1 | 5 | 17% | 0.60 | 0.95 | +0.35 |
| 2 | 9 | 22% | 0.28 | 0.95 | +0.67 |
| 3 | 9 | 28% | 0.60 | 0.95 | +0.35 |
| 4 | 9 | 13% | 0.56 | 0.92 | +0.36 |
| 5 | 8 | 7% | 0.26 | 0.90 | +0.64 |
| 6 | 3 | 5% | 0.40 | 0.90 | +0.50 |
| **Root** | **47** | **100%** | **~0.46** | **~0.93** | **+0.47** |

> Cat 2 = 0.28: 9 items, 6 new items (2-3 through 2-9 expanded) are mostly T0.
> This is accurate — v6 defines ambitious governance requirements not yet implemented.

---

# Appendix B: Multi-Vendor Capability Matrix Template

> Fill this when configuring a multi-vendor session.
> Each vendor requires a completed adapter (4-9-1) before joining governance.

| Capability | Vendor A | Vendor B | Vendor C | Required? |
|:-----------|:--------:|:--------:|:--------:|:---------:|
| Token limit (native units) | — | — | — | Per task |
| Token counting standard | — | — | — | Mapped to ref unit |
| Streaming output | — | — | — | No |
| Function / tool calling | — | — | — | Yes |
| Structured JSON output | — | — | — | Yes |
| Vision / multimodal | — | — | — | No |
| Confidence reporting method | — | — | — | Mapped to 0–100 |
| Native protocol | — | — | — | Adapted |
| Rate limit (req/min) | — | — | — | Tracked |
| Depth semantics (how vendor interprets collaboration_depth) | — | — | — | Documented |
| Output schema format | — | — | — | Normalized |
| Model version pinning supported | — | — | — | Yes |
| Cost (per 1M ref tokens) | — | — | — | Tracked |

**Adapter checklist per vendor** (4-9-1 required):
- [ ] `native_protocol` declared
- [ ] `token_converter(vendor_tokens → ref_tokens)` tested
- [ ] `output_format_converter(native → canonical)` tested
- [ ] `confidence_mapping_fn(vendor → 0–100)` tested
- [ ] `depth_interpretation_schema(depth level → vendor semantics)` documented
- [ ] Behavioral regression suite (4-8-2) passed
- [ ] Wrapper code open-auditable and version-pinned (4-6-4)
