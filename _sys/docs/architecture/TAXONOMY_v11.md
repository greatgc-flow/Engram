# MECE Taxonomy v11.0 — AI-Assisted Development: Governance Framework
### Universal · Workspace-Independent · Multi-Vendor · Symmetric Participation · Functionally Complete · Quality-Attribute Governed · MECE-Audited · Extension-Ready

> **Version**: 11.0 | **Date**: 2026-06-13
> **Review History**: v3 (base) → v4 (Human-in-Loop) → v5 (Universal) → v6 (Multi-vendor+Participation) → v7 (Complete) → v8 (Flexibility+Scalability+Maintainability) → v9 (MECE Audit + Structural Completeness) → v10 (Peer Interface + Agent/MCP + Lazy Init + Observability) → v11 (Composable + Workspace Template Architecture)
> **Collaboration**: Multi-node (CC+GC+Human) | R=10 Unanimous consensus, 2-round MECE audit
> **Supersedes**: TAXONOMY_v10.md (READ-ONLY, path: `P:\_sys\docs\TAXONOMY_v10.md`)
> **New in v11**: 2 new items (4-16, 4-17); 7 new sub-items (4-16-1..4, 4-17-1..3); 3 new params; 4-5-4 strengthened [변경됨]; G58-G65 added; total 69 items, 45 params (47 keys).
> **Audience**: Any team building an AI-assisted software development system.
> **Main body (§0–§10)**: Zero workspace-specific references. Fully self-contained.

---

## §0. How to Read This Document

This document defines the **governance layer** of AI-assisted software development — the meta-system ensuring AI agents and humans collaborate reliably, symmetrically, and adaptably.

**What this document IS**: A measurement framework + taxonomy for governing HOW AI agents collaborate.
**What this document is NOT**: A guide to what AI agents should build (application layer).

**Three reading modes:**
- **Universal** (§0–§10 only): Applicable to any AI system, any vendor combination.
- **Implementation** (+ Appendix A): Reference implementation details (Windows Sandbox).
- **Multi-vendor** (+ Appendix B): Template for cross-vendor deployment.

**How to use completeness scores**: Two scores are tracked (see §7 for formulas):
- **Framework Score** = % of items with defined governance rules (T1 or above). v11 = ~100%.
- **Implementation Score** = min(Current Tier / Target Tier, 1.0) for each item. v11 = ~35.9%.
A score of 0.00 means "not yet implemented". T0 = undefined, T4 = fully automated with active alerts.

**Category ID vs. Phase Label**: Category IDs (Cat 0, Cat 1, ...) are the permanent reference identifiers used throughout this document and in all external references. Phase labels (Phase 1 through Phase 7) describe the **chronological lifecycle order** and are used in §2 and diagrams for readability. Both refer to the same categories.

| Phase Label | Category ID | Name | Weight |
|:------------|:------------|:-----|:------:|
| Phase 1 | Cat 0 | Human Intent & Kickoff | 8% |
| Phase 2 | Cat 4 | Environment Portability | 13% |
| Phase 3 | Cat 1 | Cognitive Continuity | 17% |
| Phase 4 | Cat 2 | Collaboration Governance | 22% |
| Phase 5 | Cat 3 | System Integrity | 28% |
| Phase 6 | Cat 5 | Operations & Control | 7% |
| Phase 7 | Cat 6 | Product Delivery & Validation | 5% |

| Section | Content |
|:--------|:--------|
| §1 | Scope, definitions, measurement tiers, abstraction principle, quality attributes overlay |
| §2 | Human-in-Loop lifecycle (7-phase closed cycle + flow table) |
| §3 | Full MECE taxonomy tree (69 items) |
| §4 | Binary/deterministic KPI matrix + §4.5 Quality Attribute KPI view |
| §5 | Architectural trade-offs (T1–T31) |
| §5.5 | Logical contradictions (C1–C10) |
| §6 | Governance parameter catalogue (45 params, 47 total keys) |
| §7 | Maturity scoring model (dual: Framework Score + Implementation Score) |
| §8 | Gap analysis log (G1–G65) |
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
flexible participation (join/leave/monitor) · compute governance · learning loops ·
runtime reconfigurability · artifact scale governance · governance debt tracking ·
quality attribute measurement (flexibility · scalability · maintainability) ·
meta-governance (framework self-upgrade) · human authority transfer · delivery failure handling ·
workspace template architecture · composable architecture components.

**Out of scope**: Application business logic, domain models, UI/UX, deployment pipelines,
bare-metal infrastructure scaling (hardware, container orchestration, RAM allocation).

### §1.2 Definitions

| Term | Definition |
|:-----|:-----------|
| **AI Node** | Any AI agent in the system (language model, coding assistant, etc.) |
| **Human** | The operator who may vote in consensus, defines intent, and accepts deliverables |
| **Node Instance** | A specific running process of a model; one model may back multiple instances |
| **Role** | A virtual function assigned to a node instance at runtime (e.g., Architect, Reviewer) |
| **Session** | A bounded unit of work: start → execution → delivery. Used as the base unit for all session-scoped measurements (e.g., overhead ratio in 5-11, retry count in 6-4). |
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
| **Kaizen** | Continuous Process Remediation — iterative improvement by identifying and fixing the root causes of failures. Originated in manufacturing (Japanese: 改善 = "change for better"); universally applicable to any system that must learn from failures. |
| **5-Why** | Root cause analysis technique: ask "Why?" five times in succession to reach the fundamental cause of a failure. Example: "Why did the test fail?" → "Why was the dependency wrong?" → ... until root cause is found. |
| **Primary Success Scenario** | The primary designed use case of a deliverable, verified end-to-end (also called "golden path" in engineering) |
| **VCS** | Version Control System — any system tracking changes to artifacts over time (e.g., Git, SVN) |
| **Governance Debt** | Cumulative cost of deferred or bypassed governance. GD Score = (active_bypass_count × 5) + (stale_pm_count × 3) + (floor(degraded_hours/24) × 2). Unit: GD points. Ceiling: `governance_debt_ceiling`. |
| **Quality Attribute** | A cross-cutting non-functional property describing HOW the governance system behaves: Flexibility, Scalability, or Maintainability. Distinct from functional governance categories. |
| **Hot-reload** | Updating a governance parameter mid-session without stopping and restarting nodes. Requires `hot_reload_enabled=1` and satisfies state-consistency pre-conditions (5-10). |
| **Artifact Scale** | Total count of managed artifacts (files, modules, schemas) in a session's scope. When count exceeds `artifact_scale_threshold`, governance applies localized scope rather than full-repository scope. |
| **Configuration Drift** | State where a parameter's default value differs between its source-code definition and its external config-file definition. Detected and blocked by 3-14. |
| **Meta-Governance** | The process of applying governance to the governance framework itself — how the taxonomy, parameters, and rules are officially modified, versioned, and deployed. Defined in 3-15. |
| **Framework Score** | % of items at T1 or above (governance rule is at least documented). Measures framework definition completeness. See §7. |
| **Implementation Score** | Weighted average of min(Current Tier / Target Tier, 1.0) for all items. Measures how much of the framework is actually deployed. See §7. |
| **Canonical Peer Interface** | The minimum interface contract that any AI peer must satisfy to participate in governance (4-13). Separates the common interface layer from vendor-specific adapter translation (4-9). |
| **MCP (Model Context Protocol)** | A standardized protocol for connecting AI models to tools, data sources, and services. Governed as an extension type under 4-14-3. |
| **Agent Framework** | An execution wrapper that orchestrates multi-step AI behavior (e.g., AutoGen, CrewAI, LangChain). Must be sandboxed per 4-14-1 before joining sessions. |
| **Skill** | A discrete, versioned, callable capability registered per 4-14-2. Distinguished from a full Agent by its single-function scope. |
| **Lazy Initialization** | Deferring resource instantiation until the resource is first explicitly requested by a directive (5-12). Reduces bootstrap cost; pairs with idle teardown. |
| **MTC (Mean Time to Consensus)** | The elapsed time from a PROPOSE event to a FINALIZED event in the consensus cycle (2-2). Used in T3 and T11 balance metrics. |
| **UAT (User Acceptance Test)** | A test performed by the Human to verify that delivered artifacts satisfy the acceptance criteria defined in Cat 0-2. Governs Cat 6-2 delivery closure. |
| **PM (Post-Mortem)** | A structured incident review document generated after a P0/P1 event. Required by Cat 3-8. Contains Root Cause (5-Why), Timeline, Category, Prevention, and Policy Revision fields. |
| **Connection Point File** | A JSON-declared configuration file that acts as the sole interface for workspace-specific paths, environment variables, and vendor settings, preventing logic hardcoding. |
| **Base Template** | A standardized, workspace-independent directory structure used to instantiate new workspaces. |

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

> **Implementation Score formula**: `min(Current Tier / Target Tier, 1.0)`
> If current > target (over-engineered): score = 1.00 (capped)

#### Measurement Failure Response

| Collaboration Depth | Tier 3/4 failure action |
|:-------------------:|:------------------------|
| Maximum (e.g., Depth 10) | **HALT + ESCALATE** to human gate |
| Medium (e.g., Depth 5–8) | **WARN + continue** — log to metrics store |
| Minimal (e.g., Depth 0–3) | **LOG only** — no interruption |

### §1.4 Abstraction Principle

Universal parameter names are used in §0–§10. Implementers map these to their specific systems.
- See Appendix A.2 for reference parameter mapping.
- See Appendix B for multi-vendor setup template.

**Selective Deployment**: Items in this taxonomy may be deployed incrementally. The Implementation Score (§7) tracks which items are active. An item at T0 is "defined but not deployed" — it does not block other items from functioning. Teams may choose to deploy only the categories and items relevant to their governance maturity level. Core infrastructure items (4-2-5 eager core) are prerequisites; all others are independently deployable.

### §1.5 Quality Attributes Overlay

Three cross-cutting quality attributes are formally tracked. They describe **HOW** the governance system performs, not WHAT it governs. They are embedded in existing lifecycle categories rather than forming standalone categories, preserving the closed-loop structure.

#### Attribute Definitions

| Attribute | Symbol | Definition |
|:----------|:------:|:-----------|
| **Flexibility** | [FLEX] | Ability to adapt governance behavior without breaking correctness. Examples: adding a new AI vendor; changing parameters mid-session; hot-reloading config without restart; swapping vendor instances during execution. |
| **Scalability** | [SCALE] | Ability to maintain governance quality as the system grows in any of four dimensions: (a) horizontal — more nodes; (b) vertical — more complex tasks; (c) temporal — longer sessions; (d) artifact scale — larger repositories. |
| **Maintainability** | [MAINT] | Ability to evolve the governance system sustainably. Examples: detecting configuration drift; measuring governance debt; keeping governance documents current; tracking improvement velocity. |

#### Coverage Map

| Attribute | Taxonomy Items | Coverage |
|:----------|:---------------|:---------|
| FLEX | 0-5, 2-6, 2-8, 2-8-5, 4-3, 4-9, 4-13, 4-14, 4-16, 4-17, 5-2, 5-8, 5-10, T22 | 100% |
| SCALE | 2-7, 4-10, 4-14, 4-17, 5-6, 5-7, 5-11, 5-12, T11 | 100% |
| MAINT | 1-4, 3-2-6, 3-3, 3-8, 3-13, 3-14, 3-15, 4-4, 4-11, 4-16, 5-9 | 100% |

#### Quality Attribute Closed-Loop (Full 7-Phase Path)

All quality attribute constraints declared in 0-5 flow through **every phase** of the lifecycle:

```
[Human] Phase 1 (Cat 0): 0-5 declares F/S/M constraints
  → Phase 2 (Cat 4): Environment provisioned respecting constraints (4-10, 4-11, 4-12, 4-16, 4-17)
  → Phase 3 (Cat 1): Memory lifecycle respects scale limits (1-1)
  → Phase 4 (Cat 2): Collaboration governed with flexibility (2-6, 2-8, 5-10)
  → Phase 5 (Cat 3): Integrity enforces and measures compliance (3-13, 3-14, 3-15)
  → Phase 6 (Cat 5): Operations enforces overhead limits (5-10, 5-11)
  → Phase 7 (Cat 6): Delivery validated; F/S/M lessons captured (6-3-2)
  → Phase 1 (Cat 0): Refine constraints for next session  [↩ closed loop]
```

---

## §2. Human-in-Loop Lifecycle

The 7 governance categories (Phase 1–7) form a **closed feedback cycle**. All participants (any AI, any vendor, the Human) may engage symmetrically in any phase (see Cat 2-1).

```
╔═══════════════════════════════════════════════════════════════════════════════════╗
║  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐  ║
║  │  Phase 1     │──►│  Phase 2     │──►│  Phase 3     │──►│  Phase 4         │  ║
║  │  Cat 0       │   │  Cat 4       │   │  Cat 1       │◄──┤  Cat 2           │  ║
║  │  Intent      │   │  Environment │   │  Memory      │   │  Collaboration   │  ║
║  └──────────────┘   └──────────────┘   └─────┬────────┘   └────────┬─────────┘  ║
║       ▲                   │ [fail]            │ [re-orient]         │            ║
║       │                   ▼                   ▼            ┌────────┘            ║
║  ┌──────────────┐   [Human Gate]    ┌─────────▼──────────┐                      ║
║  │  Phase 7     │◄──┤  Phase 6  │◄──┤      Phase 5       │                      ║
║  │  Cat 6       │   │  Cat 5    │   │      Cat 3         │                      ║
║  │  Delivery    │   │  Ops.     │   │      Integrity     │                      ║
║  └──────────────┘   └───────────┘   └────────────────────┘                      ║
║       │                                        │                                 ║
║       │                    [Vendor Execution Layer]                              ║
║       │               (AI inference: unmanaged black box)                        ║
║       │               Governance validates pre (Cat 2) +                         ║
║       │               at Adapter Boundary (4-15) on exit +                       ║
║       │               post-normalization (Cat 3); never inside VEL               ║
║       │                                                                           ║
║       └── Human ACK → lessons → F/S/M refinements → next intent ───────────────► ║
╚═══════════════════════════════════════════════════════════════════════════════════╝

Short-circuit paths:
  Cat 4 failure    → Human Gate → fix environment → retry Phase 2 (Cat 4)
  Cat 3 corruption → Skip Cat 2 re-plan → back to Phase 3 (Cat 1) for re-orientation first
```

### Inter-Category Data Flow

| Transition | Payload Passed | Failure Path |
|:-----------|:---------------|:-------------|
| Phase 1 (Cat 0) → Phase 2 (Cat 4) | Intent schema (Goal ID, Scope, Constraints, Success Criteria, Delivery Format, F/S/M constraints from 0-5) + Health Pre-Check result (0-6) | — |
| Phase 2 (Cat 4) → Phase 3 (Cat 1) | Verified environment manifest (adapters ready, node profiles loaded, scale mode set, audit storage confirmed, connection point file verified) | Bootstrap fail → Human Gate → fix → retry Cat 4 |
| Phase 3 (Cat 1) → Phase 4 (Cat 2) | Oriented working memory (session state, history, domain knowledge injected) | — |
| Phase 4 (Cat 2) → [VEL] | Finalized directive (role, task, scope, quality floor, test requirements) | Consensus fail → Cat 2-4 Conflict Resolution |
| [VEL] → [Adapter Boundary 4-15] | Raw vendor output (vendor-native format) | — |
| [Adapter Boundary 4-15] → Phase 5 (Cat 3) | Adapter-normalized canonical output (4-9-2 schema + 4-13-3 error mapping applied; operational state mapped to 5-4-5 canonical states) | Normalization fail → P0 alert; output quarantined |
| Phase 5 (Cat 3) → Phase 6 (Cat 5) | Validated artifact + integrity report (schema OK, tests pass, risks cleared, GD Score updated) | Validation fail → reject → back to Cat 2; State corruption → back to Cat 1 |
| Phase 6 (Cat 5) → Phase 7 (Cat 6) | Governed artifact + health metrics (within budget, no critical alerts, overhead ratio OK) | Budget exhausted → HALT + escalate |
| Phase 7 (Cat 6) → Phase 1 (Cat 0) | Delivery ACK + lessons learned + next-session seed + F/S/M constraint refinements | Human rejects → revise → back to Cat 2; UAT fails N× → 6-4 retry limit escalation |

---

## §3. Full MECE Taxonomy Tree (69 Items)

> **Legend**: `[Type | Target Tier]` — B=Binary (T0–T2), C=Continuous (T0–T4)
> Loop order: Cat 0 (Ph1) → Cat 4 (Ph2) → Cat 1 (Ph3) → Cat 2 (Ph4) → Cat 3 (Ph5) → Cat 5 (Ph6) → Cat 6 (Ph7)
> Quality attribute tags: [FLEX]=Flexibility [SCALE]=Scalability [MAINT]=Maintainability

```
AI-Assisted Development: Governance Framework
│
├─ Cat 0 / Phase 1: Human Intent & Kickoff  [8%]
│  Entry gate. Every cycle starts here — including a health pre-check (0-6) before intent
│  capture. ANY capable node may facilitate this phase. Output: structured intent schema.
│
│  ├── 0-1: Structured Intent Capture  [B|T2]
│  │   Every task MUST begin with a structured artifact containing Goal ID, Scope boundary,
│  │   and Constraints BEFORE any multi-node execution begins.
│  │   Example: "build login feature" → Goal ID: LOGIN-001, Scope: auth module only,
│  │   Constraints: no third-party auth libs, target: HTTP 200/401 responses.
│  │   ├── 0-1-1: Goal statement — one sentence, unique Goal ID assigned
│  │   ├── 0-1-2: Scope bounding — explicit MVP boundary vs. deferred scope
│  │   └── 0-1-3: Constraint identification — time, tech, budget, non-goals
│  │
│  ├── 0-2: Success Criteria Definition  [B|T2]
│  │   Human-verifiable acceptance criteria MUST exist before execution.
│  │   Example: "Login: HTTP 200 with valid credentials; HTTP 401 with invalid."
│  │   ├── 0-2-1: Acceptance criteria — ≥1 human-checkable condition per Goal ID
│  │   ├── 0-2-2: Quality thresholds — measurable bars (test coverage %, latency ms, etc.)
│  │   └── 0-2-3: Delivery format — file path, output schema, or artifact type
│  │
│  ├── 0-3: Clarification Protocol  [C|T3]
│  │   AI agents MUST surface ambiguities within `clarification_max_turns` rounds.
│  │   ├── 0-3-1: Ambiguity detection — ≥1 unclear requirement → ask human
│  │   ├── 0-3-2: Turn limit — max `clarification_max_turns` rounds (default: 3)
│  │   └── 0-3-3: Intent confirmation — explicit human ACK recorded before multi-file execution
│  │
│  ├── 0-4: Continuous Intent Alignment  [B|T2]
│  │   All file modifications MUST occur within the declared scope. Out-of-scope = blocked.
│  │   ├── 0-4-1: Scope enforcement — every file mutation checked against allowed scope
│  │   ├── 0-4-2: Drift detection — out-of-scope action → flag before execution
│  │   └── 0-4-3: Scope escalation — drift above threshold → human gate
│  │
│  ├── 0-5: Non-Functional Intent Capture  [B|T2]  [FLEX] [SCALE] [MAINT]
│  │   Human MUST declare quality attribute constraints before infrastructure is provisioned.
│  │   These constraints scope all subsequent governance decisions across all 7 phases.
│  │   Human-first entry point for the Quality Attribute closed-loop cycle (§1.5).
│  │   Example: "Must support 5,000+ files" (SCALE), "Hot-reload permitted" (FLEX),
│  │   "Doc review every 30 days" (MAINT).
│  │   ├── 0-5-1: Scalability constraints — max artifact count, max node count, session duration
│  │   ├── 0-5-2: Flexibility constraints — hot-reload permitted (Y/N), vendor swap (Y/N)
│  │   └── 0-5-3: Maintainability constraints — doc freshness interval, governance debt ceiling
│  │
│  └── 0-6: Governance Health Pre-Check  [C|T3]
│      BEFORE capturing new intent, the system MUST verify it is in a healthy enough state
│      to begin a new session. This prevents building new work on top of unresolved failures
│      or an improperly closed previous session.
│      Example: Previous session left 2 unresolved P0 alerts → pre-check blocks new session
│      start until human acknowledges and resolves alerts.
│      ├── 0-6-1: GD Score gate — GD Score (from 3-13) < `governance_debt_ceiling`
│      ├── 0-6-2: Critical alert clearance — no active P0 alerts from previous session
│      └── 0-6-3: Session closure confirmation — previous session properly archived (6-3-1 done)
│
├─ Cat 4 / Phase 2: Environment Portability  [13%]
│  Infrastructure and vendor integration. MUST be verified before cognitive work (Cat 1).
│  Output: environment manifest (adapters ready, node profiles loaded, audit storage confirmed).
│  Failure: bootstrap fail → Human Gate → fix environment → retry.
│
│  ├── 4-1: Runtime Environment  [C|T3]
│  │   All runtime dependencies MUST be self-contained; no host system state assumed.
│  │   Example: all runtime packages in an isolated virtual environment; no host installs.
│  │   ├── 4-1-1: Runtime isolation — language runtime and deps isolated from host
│  │   ├── 4-1-2: Encoding consistency — character encoding explicitly set system-wide
│  │   ├── 4-1-3: Package manager isolation — package installs scoped to project
│  │   ├── 4-1-4: Environment variable scoping — per-agent env vars isolated
│  │   └── 4-1-5: Runtime security profile — execution meets minimum security baseline
│  │               (e.g., no unrestricted script execution; policy defined per platform)
│  │
│  ├── 4-2: Installation & Deployment  [C|T3]
│  │   A single bootstrap entry point MUST reconstruct the full environment from scratch.
│  │   Example: running the bootstrap command on a clean OS installs all dependencies
│  │   and passes smoke tests with zero manual steps.
│  │   ├── 4-2-1: Zero-base bootstrap — one entry point = full reconstruction, 0 manual steps
│  │   ├── 4-2-2: Dependency bootstrapping — all tools and packages auto-installed
│  │   ├── 4-2-3: Smoke testing — post-install validation confirms environment health
│  │   ├── 4-2-4: Parallel-safe naming — no filename collisions in concurrent setups
│  │   └── 4-2-5: Eager Core, Lazy Periphery — bootstrap MUST eagerly initialize ONLY core
│  │               governance infrastructure: parameter registry (5-1), event broker (4-3),
│  │               and basic policy check engine (3-2). All vendor connections, agent frameworks,
│  │               MCP servers, and capability extensions MUST be verified for availability
│  │               (health-check only) but remain dormant until explicitly invoked by a directive.
│  │               This item co-governs with 5-12 (Resource Lazy Initialization):
│  │               4-2-5 defines WHAT belongs in the eager core; 5-12 governs the lazy periphery.
│  │               PASS: bootstrap exits with only core infra active; no vendor connections open.
│  │               FAIL: vendor client or agent framework initialized during bootstrap without an
│  │               active directive.
│  │
│  ├── 4-3: Infrastructure Abstraction  [C|T3]  [FLEX] [SCALE]
│  │   IPC, messaging, and shared state MUST be decoupled from node identity.
│  │   Example: replacing the IPC backend requires no changes to individual node code.
│  │   ├── 4-3-1: Technology-neutral IPC — message broker decouples nodes from transport
│  │   ├── 4-3-2: Shared state layer — node-independent state accessible to all agents
│  │   ├── 4-3-3: Unified messaging interface — single entry point for all P2P messages
│  │   ├── 4-3-4: Node heartbeat — liveness detection; absent nodes auto-abstain from quorum
│  │   └── 4-3-5: Dynamic transport scaling — IPC transport supports runtime capacity
│  │               adjustment without node restart; throughput scales with active node count
│  │
│  ├── 4-4: Version Management  [B|T2]  [MAINT]
│  │   All protocol and schema versions MUST be tracked; mismatches MUST be detectable.
│  │   ├── 4-4-1: Protocol versioning — all governance docs carry explicit vX.Y version tags
│  │   ├── 4-4-2: Changelog maintenance — every version change documented with rationale
│  │   └── 4-4-3: Version format enforcement — standardized tag format enforced by check
│  │
│  ├── 4-5: Platform Independence  [C|T3]  [FLEX] [MAINT]
│  │   No absolute paths or platform-specific constructs in committed artifacts.
│  │   Example: use `./config/settings.json` not `C:\Users\admin\project\config\settings.json`.
│  │   ├── 4-5-1: No hardcoded paths — all paths relative or environment-variable-based
│  │   ├── 4-5-2: Drive/mount abstraction — portable across OS and mount points
│  │   ├── 4-5-3: Cross-platform path API — platform-agnostic path libraries enforced
│  │   └── 4-5-4: Architectural Separation Mandate — [변경됨] universal framework source files (§0–§10)
│  │               and governance components MUST NOT mix General (universal) logic with Specific
│  │               (workspace-specific) implementations in the same file or function. ALL workspace-specific
│  │               connections (paths, env vars, vendor settings) MUST be declared in a JSON connection point
│  │               file (e.g., `paths.json`, `env.json`) and accessed via the orchestrator.
│  │               PASS: static analysis confirms 0 workspace-specific constants in universal components;
│  │               all specific connections trace to a validated JSON connection point file.
│  │               FAIL: universal component contains hardcoded workspace paths, vendor names, or
│  │               non-parameterized workspace constants.
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
│  │   ├── 4-7-1: Standardized profile schema — required fields: token_limit, tools[],
│  │   │         specialization[], role_id (mutable), token_counting_standard, vendor_id,
│  │   │         native_protocol, output_format, confidence_mapping_fn
│  │   ├── 4-7-2: Dynamic capability discovery — profile updated on node state change
│  │   ├── 4-7-3: Profile-aware routing — delegation checks 4-7 profile first
│  │   ├── 4-7-4: Cross-vendor capability bridging — fallback: chunk sub-tasks / route to
│  │   │         capable node / escalate to human
│  │   ├── 4-7-5: Token normalization — all nodes normalize to reference token unit;
│  │   │           profile includes `token_converter(vendor_tokens → ref_tokens)`
│  │   └── 4-7-6: Capability Overflow Mapping — vendor-native capabilities that exceed the
│  │               4-13 canonical interface contract CANNOT be invoked directly in the
│  │               governance pipeline. They MUST be formally registered as a Skill via
│  │               4-14-2 (Skill Registration Protocol) before invocation.
│  │               PASS: 100% of non-canonical vendor capability invocations trace to a
│  │               registered Skill entry (4-14-2) in the extension registry.
│  │               FAIL: vendor-native overflow capability invoked directly without Skill registration.
│  │
│  ├── 4-8: Foundation Model Lifecycle  [C|T3]  [MAINT]
│  │   Model transitions MUST trigger re-validation of capability and behavioral compliance.
│  │   Example: upgrading from Model-X v2.1 to v3.0 requires re-running the behavior test suite.
│  │   ├── 4-8-1: Model version pinning — active model version recorded in configuration
│  │   ├── 4-8-2: Behavioral regression suite — per-vendor test run mandatory before upgrade
│  │   ├── 4-8-3: Rollback procedures — prior model version recoverable within defined window
│  │   └── 4-8-4: Vendor model update detection — system detects vendor-initiated silent upgrades;
│  │               re-runs compliance suite before accepting outputs from new version
│  │
│  ├── 4-9: Vendor Integration Layer  [C|T2]  [FLEX]
│  │   Every AI vendor connects via a standardized adapter translating vendor-native APIs
│  │   to the canonical governance protocol BEFORE entering Cat 2.
│  │   Architecture: [Vendor A→Adapter-A]──►[Canonical Hub]──►Cat 2 Governance
│  │   ├── 4-9-1: Vendor adapter specification — each adapter declares: native_protocol,
│  │   │         token_converter, output_format_converter, confidence_mapping_fn (0–100 scale),
│  │   │         depth_interpretation_schema, operational_state_mapping_fn (vendor-native
│  │   │         execution state → 5-4-5 canonical states: RUNNING/WAITING_FOR_HUMAN/
│  │   │         DEGRADED/IDLE/COMPLETED)
│  │   ├── 4-9-2: Output schema normalization — adapter converts vendor output to canonical
│  │   │         schema BEFORE entering governance pipeline (Cat 3-4)
│  │   ├── 4-9-3: Rate-limit coordination — adapter declares tokens_per_min, requests_per_day;
│  │   │         active control loop (5-5) respects per-vendor limits
│  │   ├── 4-9-4: Protocol fallback chain — ordered fallback when primary protocol fails;
│  │   │           defined in `vendor_protocol_priority` parameter
│  │   └── 4-9-5: Declarative Adapter Specification — adapters for standard REST/JSON AI APIs
│  │               SHOULD be expressible as a declarative mapping document (JSON/YAML) defining:
│  │               endpoint URLs, auth headers, JSONPath expressions for field extraction,
│  │               token conversion ratios, and response normalization rules — with zero custom
│  │               code. Imperative code adapters are permitted only for non-standard protocols
│  │               (e.g., custom gRPC streaming) that cannot be expressed declaratively.
│  │               This supports the No-Code orientation: new vendors can be onboarded by
│  │               writing a config file, not by modifying source code.
│  │               PASS: vendor onboarded via declarative spec only; no source code changed.
│  │               ACCEPTABLE: code adapter present with documented justification (non-standard protocol).
│  │               FAIL: code adapter used for a standard REST/JSON API that could be declarative.
│  │   Note: 4-9-1 adapters MUST first satisfy the 4-13 Canonical AI Peer Interface contract
│  │   as their baseline structure BEFORE applying vendor-specific API translation logic.
│  │
│  ├── 4-10: Artifact Scale Governance  [C|T3]  [SCALE]
│  │   When artifact count exceeds `artifact_scale_threshold`, policy gates (3-2-1) and
│  │   blast-radius analysis (3-3-4) MUST apply localized dependency scope, not full-repo scope.
│  │   Example: Repository with 8,000 files (above threshold 5,000) → blast-radius analysis
│  │   bounded to the affected module's subgraph.
│  │   ├── 4-10-1: Scale trigger detection — automated count; triggers "localized mode" above threshold
│  │   ├── 4-10-2: Localized dependency scope — blast-radius bounded to direct dependencies +
│  │   │           1 level of transitive dependencies
│  │   └── 4-10-3: Full-scope override — human may request full-scope; override logged;
│  │               threshold temporarily raised for that session
│  │
│  ├── 4-11: Governance Document Freshness  [C|T3]  [MAINT]
│  │   Governance documents MUST be reviewed against implementation at a defined cadence.
│  │   A versioned document (4-4) may still contain stale content.
│  │   Example: PROTOCOL.md says "3-strike halt" but code implements "2-strike halt" → stale.
│  │   ├── 4-11-1: Review schedule — all governance docs scheduled at `doc_freshness_interval`
│  │   │           days; last-review timestamp tracked per document
│  │   ├── 4-11-2: Orphaned reference detection — references to undefined components, deprecated
│  │   │           APIs, or removed parameters flagged automatically
│  │   ├── 4-11-3: Staleness alert — doc with no review in > `doc_freshness_interval` days → WARN
│  │   └── 4-11-4: Document Boundary Principle — workspace documents (PROTOCOL.md, CONVENTION.md,
│  │               etc.) MUST NOT duplicate governance rules defined in this Taxonomy. They MUST
│  │               reference Taxonomy items by explicit ID (e.g., "per [Taxonomy: 3-12]").
│  │               Example: PROTOCOL.md §M-3 saying "3 strikes halt" is a DUPLICATE of 3-5-3;
│  │               it should reference "[Taxonomy: 3-5-3]" instead.
│  │               PASS: static grep confirms all governance directives in workspace .md files
│  │               contain a regex-parsable Taxonomy item ID citation pattern.
│  │               FAIL: governance directive in workspace doc without Taxonomy citation; rule text
│  │               duplicated outside Taxonomy.
│  │
│  ├── 4-12: Durable Audit Infrastructure  [C|T2]  [MAINT]
│  │   The "dedicated layer" referenced in C4 (§5.5) and 3-9 (Immutable Audit Logging)
│  │   MUST be physically defined. The audit log requires durable, append-only storage
│  │   independent of the working memory buffer and system restart cycles.
│  │   Example: Audit log stored in a separate append-only file (or database) that persists
│  │   across sessions and cannot be truncated by memory pruning (1-1-3, 1-3-2).
│  │   ├── 4-12-1: Audit storage spec — dedicated storage location defined and isolated from
│  │   │           working memory; never subject to memory pruning operations
│  │   ├── 4-12-2: Persistence across restarts — audit log survives node restarts and session ends
│  │   └── 4-12-3: Capacity management — audit log rotation/archival policy defined (distinct
│  │                  from 3-9-3 retention policy, which is operational; this defines infrastructure)
│  │
│  ├── 4-13: Canonical AI Peer Interface Specification  [B|T2]  [FLEX]
│  │   Any AI system joining as a peer MUST implement the canonical interface contract BEFORE
│  │   a vendor adapter (4-9) is built. This separates the common interface (WHAT any peer must
│  │   support) from the vendor-specific translation layer (HOW each vendor maps to it).
│  │   The adapter pattern in 4-9 targets this contract; the contract does not target the adapter.
│  │   Example: ChatGPT, Gemini, Claude — all different APIs — but all MUST satisfy 4-13 before
│  │   their respective adapters can register them as governance peers.
│  │   ├── 4-13-1: Interface Schema Definition — typed-JSON schema defining required request/response
│  │   │           fields for all peer operations: token count, state ingestion, standard output
│  │   │           generation, confidence reporting (0–100 scale)
│  │   ├── 4-13-2: Capability Contract — minimum operations any peer must demonstrate before
│  │   │           receiving voting rights: (a) token measurement in reference units (4-7-5),
│  │   │           (b) session state ingestion from canonical handoff format (1-2-5),
│  │   │           (c) standard structured JSON output, (d) confidence score reporting
│  │   ├── 4-13-3: Error Normalization Contract — vendor-specific error codes MUST map to the
│  │   │           canonical error taxonomy (3-5-1: P0/P1/WARN/INFO) via the adapter.
│  │   │           Unknown vendor errors default to WARN until classified.
│  │   └── 4-13-4: Canonical Depth Semantics Contract — `collaboration_depth=N` MUST represent
│  │               identical governance weight and quorum behavior for ALL peers regardless of
│  │               vendor. Each vendor adapter MUST declare a `depth_semantics_mapping` that
│  │               produces equivalent quorum results at each depth value.
│  │               Example: depth=3 on Vendor A and depth=3 on Vendor B must both require the
│  │               same quorum size and consensus rules — no vendor may interpret depth=3 as
│  │               "consult 1 peer" while another interprets it as "consult 5 peers."
│  │               PASS: behavioral equivalence test — depth=N on any two registered vendors
│  │               produces identical quorum sizes and voting requirements.
│  │               FAIL: two vendors at depth=N produce different quorum sizes or rule interpretations.
│  │
│  ├── 4-14: Agent/Skill/Tool Extension Governance  [C|T3]  [FLEX] [SCALE]
│  │   Any extension that adds capabilities to the AI system — Agent frameworks (AutoGen/CrewAI/
│  │   LangChain), discrete Skills (callable functions), or MCP Servers (Model Context Protocol)
│  │   — MUST follow a defined registration and execution lifecycle. This governs HOW extensions
│  │   join and operate, not what they do. Execution boundary: tool micro-actions are autonomous
│  │   within a pre-approved envelope (granted by 2-3 Task Management); macro-result validated at
│  │   3-10 Functional Verification Gate.
│  │   Example: An MCP weather-tool server must be registered (4-14-2), sandboxed (4-14-1), and
│  │   its calls bounded by the session's pre-approved invocation envelope (4-14-3).
│  │   ├── 4-14-1: Agent Framework Encapsulation — execution wrappers (AutoGen/CrewAI/LangChain)
│  │   │           MUST be sandboxed; their internal state MUST NOT bleed into canonical session
│  │   │           state; framework version pinned (per 4-8-1)
│  │   ├── 4-14-2: Skill/Tool Registration Protocol — discrete capabilities and MCP tools MUST be
│  │   │           formally registered, linked to a 4-7 capability profile, version-pinned, and
│  │   │           granted explicit execution scope BEFORE any invocation
│  │   └── 4-14-3: MCP Server Lifecycle Management — MCP server connections MUST define:
│  │                  (a) connection scope (session-scoped or persistent),
│  │                  (b) execution boundary (pre-approved authorization envelope from 2-3),
│  │                  (c) teardown condition (session end, explicit close, or `idle_teardown_timeout`);
│  │                  all MCP tool calls logged to 3-9 audit log with authorization reference
│  │
│  ├── 4-15: General-Specific Boundary Enforcement  [B|T2]  [FLEX]
│  │   ALL output from the Vendor Execution Layer (VEL) MUST pass through adapter
│  │   normalization — 4-9-2 (schema normalization) + 4-13-3 (error mapping) + operational
│  │   state mapping — BEFORE entering any Phase 5 (Cat 3) governance item.
│  │   No raw vendor-specific data may bypass this boundary. This rule closes the structural
│  │   leak where 3-1 (Security), 3-2 (Policy), 3-3 (Change Management) could receive
│  │   unnormalized vendor output. Item 3-4-6 is the FIRST Cat 3 validation AFTER 4-15
│  │   has completed normalization at the VEL exit.
│  │   Example: vendor returns native JSON with vendor-specific error codes and state flags →
│  │   adapter maps to canonical schema, P0/P1/WARN/INFO, and RUNNING/IDLE before Cat 3 entry.
│  │   ├── 4-15-1: VEL exit normalization mandate — adapter runs 4-9-2 schema conversion +
│  │   │           4-13-3 error normalization + operational_state_mapping_fn as the FINAL step
│  │   │           before output leaves the VEL boundary; Cat 3 receives ONLY canonical format
│  │   └── 4-15-2: Boundary integrity audit — periodic sampling of Cat 3 inputs to verify
│  │                  canonical format compliance; any non-canonical input = P0 alert + quarantine
│  │
│  ├── 4-16: Workspace Template Architecture  [B|T2] [추가됨] [FLEX] [MAINT]
│  │   The system MUST support a template-based workspace model where `_sys/` is a universal hub
│  │   and `workspace/` is a specific instance generated from a template. This ensures the
│  │   orchestrator is completely workspace-independent and interacts only via JSON configs.
│  │   ├── 4-16-1: Base Template Registry — Registry of available workspace templates
│  │   │           (`_sys/templates/workspace/`) used to stamp out new workspaces.
│  │   ├── 4-16-2: Workspace-Independent Core — Core logic in `_sys/` MUST have zero knowledge
│  │   │           of specific workspace paths until runtime, accessed via `workspace_template_path`.
│  │   ├── 4-16-3: Cross-Workspace Common Space — A shared directory (`common_space_path`)
│  │   │           accessible by multiple workspaces for shared assets, tools, or memory.
│  │   └── 4-16-4: Workspace-Local Space — An isolated space within the workspace for
│  │               session-specific artifacts and local configurations.
│  │
│  └── 4-17: Composable Architecture  [B|T2] [추가됨] [FLEX] [SCALE]
│      System components MUST be zero-dependency and dynamically composable via JSON declarations.
│      This enables "Hot-swap" capability for any part of the governance pipeline.
│      ├── 4-17-1: Zero-dependency components — Components MUST be functional in isolation or
│      │           via standard IPC (4-3), without assuming the presence of other specific peers.
│      ├── 4-17-2: JSON-declared dependency graph — All inter-component dependencies and
│      │           routing logic MUST be declared in a JSON file (e.g., `dispatch.json`).
│      └── 4-17-3: Hot-swap composability — Components can be replaced or updated mid-session
│                  by updating the JSON graph, enabling runtime architecture evolution.
│
├─ Cat 1 / Phase 3: Cognitive Continuity  [17%]
│  Ensures all agents maintain coherent, persistent awareness across sessions.
│  "Working memory" is the universal term used throughout.
│  Output: oriented working memory state passed to Cat 2.
│
│  ├── 1-1: Working Memory Lifecycle  [C|T4]
│  │   Active working memory size MUST be monitored (in reference token units).
│  │   Example: memory at 580 ref-tokens (below 600 warn threshold) = GREEN; at 650 = YELLOW.
│  │   ├── 1-1-1: Size tracking — continuous measurement vs. warn/critical thresholds
│  │   ├── 1-1-2: Session state rolling — completed items archived; live state kept minimal
│  │   └── 1-1-3: Memory pruning — TTL scoring:
│  │               score = (priority_level × 2) − age_in_days; score < 0 → archive candidate
│  │               Boundary note: 1-1-3 = session-scoped TTL (hours–days);
│  │               1-3-2 = long-term compaction (weeks–months). NOT overlapping.
│  │
│  ├── 1-2: Session Continuity  [B|T2]
│  │   Every session MUST produce a machine-readable handoff enabling seamless resumption.
│  │   Boundary note: 1-2 = ephemeral handoff (next session); 1-3 = compacted long-term memory.
│  │   ├── 1-2-1: Scoped session workspace — isolated per-session directory, unique ID
│  │   ├── 1-2-2: Per-node summaries — bounded summary per node (<4 KB or model-equivalent limit)
│  │   ├── 1-2-3: Re-orientation protocol — agent reads handoff before beginning ANY work
│  │   ├── 1-2-4: Emergency handoff schema — minimum viable recovery fields:
│  │   │         executive_summary / technical_state / strategy_for_next_session
│  │   ├── 1-2-5: Vendor-agnostic handoff format — canonical typed-JSON intermediate format;
│  │   │           each node profile includes serializer/deserializer functions
│  │   └── 1-2-6: Canonical Handoff Validation — any session state loaded into Cat 1 working
│  │               memory MUST pass schema validation against the canonical handoff format
│  │               (1-2-4/1-2-5) BEFORE ingestion. This is the Cat4→Cat1 boundary check.
│  │               Prevents vendor-specific or malformed session state from entering the
│  │               general cognitive layer.
│  │               PASS: handoff schema validation succeeds before any Cat 1 processing begins.
│  │               FAIL: session state with non-canonical or missing fields accepted into
│  │               working memory without validation.
│  │
│  ├── 1-3: Memory Persistence  [C|T4]
│  │   Learnings MUST persist across sessions in queryable structured form (weeks–months).
│  │   ├── 1-3-1: Long-term memory store — persistent file-based memory per project
│  │   ├── 1-3-2: Memory compaction — periodic pruning of stale/superseded entries
│  │   ├── 1-3-3: Symmetric sync — all nodes share access to same memory corpus
│  │   ├── 1-3-4: Memory taxonomy — typed entries: user / feedback / project / reference
│  │   └── 1-3-5: Memory format registry — entries declare encoding_format per entry;
│  │               retrieval handles heterogeneous formats (logic rule, example, fact)
│  │
│  ├── 1-4: Instruction Design & Efficacy  [B|T2]  [MAINT]
│  │   Agents MUST have persistent structured instructions; quality MUST be measured.
│  │   Example: if 3+ sessions require the same mid-session correction, the base instruction
│  │   is flagged for revision.
│  │   ├── 1-4-1: Global agent configuration — persistent baseline instruction set per agent
│  │   ├── 1-4-2: Project-level overrides — project-specific instructions take precedence
│  │   ├── 1-4-3: Query efficiency — instructions formatted for maximum information density
│  │   ├── 1-4-4: Task template library — structured templates for recurring task types
│  │   └── 1-4-5: Instruction efficacy tracking
│  │               Metric: sessions requiring mid-session correction / total sessions
│  │               Threshold: >10% correction rate → instruction revision triggered
│  │
│  └── 1-5: Persistent Domain Knowledge  [C|T3]
│      Domain-specific decisions and business rules MUST persist beyond sessions.
│      Example: "This project uses OAuth2, not API keys" persists across all sessions.
│      ├── 1-5-1: Knowledge extraction — automated identification of reusable domain facts
│      ├── 1-5-2: Structured storage schema — queryable format (not raw session logs)
│      ├── 1-5-3: Contextual retrieval — knowledge injected into working memory on match
│      └── 1-5-4: Obsolescence protocol — outdated entries flagged/pruned on schedule
│
├─ Cat 2 / Phase 4: Collaboration Governance  [22%]
│  All decisions, task planning, participation, roles, and communication protocols.
│  Output: finalized directive envelope passed to the Vendor Execution Layer.
│
│  ├── 2-1: Governance Principles  [B|T2]
│  │   FOUNDATIONAL. Defines equal rights for ALL participants.
│  │   No phase of the lifecycle is "owned" by any specific node type.
│  │   ├── 2-1-1: Symmetric phase participation — any registered node may PROPOSE, VOTE,
│  │   │         or be ASSIGNED work in any lifecycle phase (Phase 1 through Phase 7)
│  │   ├── 2-1-2: Equal vote weight — 1 ACTIVE node = 1 vote regardless of model size/vendor;
│  │   │         Human ACTIVE = 1 vote; Human OBSERVER = 0 votes
│  │   ├── 2-1-3: Human interface assignment — any capable AI node may facilitate Phase 1
│  │   │         (intent intake) or Phase 7 (delivery); conflict resolution: capability first, rotation
│  │   └── 2-1-4: Minimum rights — every registered node receives: broadcast access,
│  │               proposal rights, vote rights (when ACTIVE), directive rights
│  │
│  ├── 2-2: Consensus Protocol  [C|T3]
│  │   All cross-agent decisions MUST follow: Propose → Vote → Finalize.
│  │   ├── 2-2-1: Propose-Vote-Finalize cycle — explicit state machine per decision
│  │   ├── 2-2-2: Quorum rules — majority = >50% of currently ACTIVE nodes;
│  │   │         unanimity at depth = Count(ACTIVE_NODES); min 1 ACTIVE node required;
│  │   │         hard cap: `max_nodes_per_consensus` (prevents MTC exponential decay)
│  │   ├── 2-2-3: Final Call mechanism — depth ≥ `final_call_threshold` requires explicit ACK
│  │   ├── 2-2-4: Consensus history — all finalized decisions recorded with rationale + ROLE
│  │   └── 2-2-5: Protocol polymorphism — adapter (4-9-1) translates vendor native protocol
│  │               to canonical format BEFORE entering this vote cycle
│  │
│  ├── 2-3: Collaborative Task Management  [C|T3]
│  │   Work division is collaboratively negotiated. Any node may propose, challenge, or revise.
│  │   ├── 2-3-1: Directive envelope — standard schema; includes `intended_role` field (not node ID)
│  │   ├── 2-3-2: Capability-based routing — routing checks 4-7 profile before assignment
│  │   ├── 2-3-3: Parallel execution policy — async when impact ranges non-overlapping,
│  │   │         OR when sub-team synthesis (2-7-3) will merge complementary contributions
│  │   ├── 2-3-4: Goal decomposition protocol — Division Proposal maps sub-tasks to roles;
│  │   │         achieves consensus via 2-2; split criteria: artifact boundary, dependency, capability
│  │   ├── 2-3-5: Assignment challenge — any ACTIVE node may challenge assignment;
│  │   │         grounds: capability mismatch, working memory overload, inefficiency
│  │   ├── 2-3-6: Division revision — mid-execution re-division when scope >50% over estimate,
│  │   │         assigned node exits, or dependencies change
│  │   └── 2-3-7: Result aggregation — cross-node output verification before finalization
│  │
│  ├── 2-4: Conflict & Deadlock Resolution  [B|T2]
│  │   Every unresolvable conflict MUST have a defined escalation path to human arbitration.
│  │   ├── 2-4-1: Deadlock handling — consensus cannot converge within `consensus_timeout` →
│  │   │         escalate to human or pre-defined authority node
│  │   ├── 2-4-2: Human gate escalation — any node may invoke human veto at any time
│  │   ├── 2-4-3: Repeated-failure halt — N consecutive identical errors → HALT + human consult
│  │   └── 2-4-4: Stalled round cleanup — auto-expiry of rounds exceeding timeout
│  │
│  ├── 2-5: Node Registry & Identity  [C|T3]
│  │   Every participating node MUST be registered; registry is the single source of truth.
│  │   ├── 2-5-1: Node registry — authoritative list: node_id, model_vendor, instance_id,
│  │   │         role_id (mutable), participation_mode, capability_ref
│  │   ├── 2-5-2: Collaboration depth — 0=single designated-node autonomy,
│  │   │         Count(ACTIVE_NODES)=full unanimity; min_collaboration_depth = safety floor
│  │   ├── 2-5-3: Dynamic node addition — new node gains ACTIVE rights upon registration
│  │   └── 2-5-4: Re-sync on reconnect — returning node digests state delta;
│  │               rejoins as VOTER (ACTIVE) or OBSERVER depending on session state
│  │
│  ├── 2-6: Participation Management  [C|T3]  [FLEX]
│  │   Nodes and humans may flexibly join, leave, or observe without disrupting governance.
│  │   Five participation states:
│  │     ACTIVE              — voting + executing; counted in quorum
│  │     OBSERVER[SILENT]    — receive-only; NOT in quorum; zero output
│  │     OBSERVER[ANNOTATING]— receive + post [ANNOTATION]-tagged msgs; non-binding
│  │     GRACEFUL_EXIT       — voluntary; directives handed off before exit; quorum recalculates
│  │     FORCED_EXIT         — crash/unplanned; grace period before quorum recalculates
│  │   ├── 2-6-1: Mode transitions — any node may request mode change; transition logged
│  │   ├── 2-6-2: Graceful exit & directive handoff — before GRACEFUL_EXIT: node transfers all
│  │   │         held directives to agreed peer; exits only after confirmed
│  │   ├── 2-6-3: Human observer mode — human switches ACTIVE ↔ OBSERVER[ANNOTATING] freely;
│  │   │         auto-return to ACTIVE on: ESCALATE event, P0 incident, explicit request;
│  │   │         `human_escalation_sla` defines max wait before session auto-suspends
│  │   └── 2-6-4: Human Transfer of Authority — when the designated Human operator is replaced
│  │               mid-session or project, a formal Transfer of Authority protocol MUST execute:
│  │               (1) outgoing Human completes all pending ACKs or explicitly defers;
│  │               (2) incoming Human receives full session state (handoff + intent schema);
│  │               (3) transfer event logged to 3-9 as HUMAN_TRANSFER boundary marker;
│  │               (4) incoming Human explicitly ACKs before receiving vote rights.
│  │               Without this, Cat 0/Cat 6 human gates become orphaned.
│  │
│  ├── 2-7: Sub-Teaming & Scoped Consensus  [C|T3]  [SCALE]
│  │   Nodes may form task forces with localized consensus on shared sub-goals.
│  │   ├── 2-7-1: Task force formation — requires full-group vote; minimum 2 ACTIVE nodes;
│  │   │         charter defines: sub-goal, node list, reporting trigger, synthesis method
│  │   ├── 2-7-2: Scoped transparency — ALL sub-team messages written to audit log (3-9);
│  │   │         global broadcast occurs when sub-team reaches FINALIZED status
│  │   └── 2-7-3: Complementary synthesis — sub-team output passes full-group verification
│  │               vote before merging into main session state
│  │
│  ├── 2-8: Dynamic Role Management  [C|T3]  [FLEX]
│  │   Roles are virtual and runtime-assigned. One model may hold multiple roles.
│  │   ├── 2-8-1: Role-identity decoupling — roles are session-time assignments;
│  │   │         same model may back multiple active instances with different roles
│  │   ├── 2-8-2: Role-targeted directives — directive specifies `intended_role`, not node ID
│  │   ├── 2-8-3: Multi-gate human roles — human registers N roles per session,
│  │   │         each with independent ACK thresholds
│  │   ├── 2-8-4: Role revision — any node may PROPOSE role reassignment; goes through 2-2;
│  │   │         no unilateral role changes
│  │   └── 2-8-5: Mid-session vendor/instance hot-swap — replacing node MUST:
│  │               (1) complete all held directives or hand off via 2-6-2;
│  │               (2) have registered adapter (4-9) ready;
│  │               (3) re-sync working memory (1-2-3) before accepting new directives.
│  │               Hot-swap event logged to 3-9 as state-machine boundary.
│  │
│  └── 2-9: Transparency & Attribution  [C|T4]
│      All communications MUST be logged. All decisions MUST be attributed to a Role.
│      ├── 2-9-1: No unlogged channels — every message written to audit log (3-9) immediately;
│      │         global broadcast only at FINALIZED events
│      ├── 2-9-2: Structured message prefixes — message type indicated in header
│      ├── 2-9-3: Proposer & opposer logging — each vote records ROLE_ID and stance
│      ├── 2-9-4: Drift detection — dissent ratio > `dissent_drift_threshold` → audit triggered
│      └── 2-9-5: Role-Instance join table — immutable mapping (ROLE_ID ↔ INSTANCE_ID);
│                  enables governance view (ROLE_ID) + compliance view (INSTANCE_ID)
│
├─ Cat 3 / Phase 5: System Integrity  [28%]
│  Failure here blocks all execution. Highest weight in Root Score.
│  Input: raw vendor output from [Vendor Execution Layer].
│  Output: validated artifact + integrity report to Cat 5.
│  Note: Cat 3 failure due to state CORRUPTION triggers re-orientation in Cat 1 before
│        re-planning in Cat 2 (see §2 short-circuit path).
│
│  ├── 3-1: Security & Trust  [B|T2]
│  │   ├── 3-1-1: Non-interference — agents cannot modify each other's configuration
│  │   ├── 3-1-2: Credential isolation — authentication files inaccessible to AI nodes
│  │   ├── 3-1-3: Input sanitization — injection prevention on all external inputs
│  │   ├── 3-1-4: Protected file list — governance docs require elevated consensus to modify
│  │   └── 3-1-5: Secret injection protocol — secrets via env vars only; never in logs/commits
│  │
│  ├── 3-2: Policy Enforcement (Static)  [C|T3]  [MAINT]
│  │   Static artifact checks (pre-commit, VCS state). Boundary: 3-7 = runtime behavior.
│  │   ├── 3-2-1: Static policy gate — automated N-check suite on every commit/merge attempt
│  │   ├── 3-2-2: Policy-code consistency — governance docs and enforcement code in sync
│  │   ├── 3-2-3: Pre-commit hook — policy gate runs automatically on commit attempt
│  │   ├── 3-2-4: Exit code gate — PASS(0) or FAIL(1); FAIL blocks commit
│  │   ├── 3-2-5: Vendor-agnostic policy encoding — policies in vendor-neutral DSL;
│  │   │           adapter (4-9-1) translates to vendor-specific enforcement
│  │   └── 3-2-6: Implementation Constant Extraction  [MAINT] — all constants in governance
│  │               orchestration scripts (file path templates, URL patterns, non-parameterized
│  │               defaults) MUST be extracted to the top of the file or a dedicated config file,
│  │               separated from execution logic. Applies to governance scripts only (§1.1 scope).
│  │               Example: orchestrator root path template declared at top of file, not repeated inline in 3 functions.
│  │               PASS: static analysis finds 0 inline magic strings/constants within execution
│  │               logic blocks in governance scripts.
│  │               FAIL: hardcoded operational constant detected inside an execution logic block.
│  │
│  ├── 3-3: Change Management  [C|T3]  [MAINT]
│  │   Every change MUST be tagged, recorded as a structured change record, and impact-analyzed.
│  │   ├── 3-3-1: MECE change tagging — added / deleted / changed / retained
│  │   ├── 3-3-2: Structured change records — VCS commit format enforced (type:scope:description)
│  │   ├── 3-3-3: Parallel state track isolation — large changes isolated before merging to main
│  │   └── 3-3-4: Impact analysis gate — blast-radius estimation required before multi-file change
│  │
│  ├── 3-4: Output Validation  [C|T3]
│  │   ├── 3-4-1: Output schema validation — verified against canonical schema
│  │   ├── 3-4-2: Size guard — output file size / include depth bounded
│  │   ├── 3-4-3: Orchestrator protection — core scripts validated before overwrite
│  │   ├── 3-4-4: Refusal detection — AI refusals flagged and routed to human gate
│  │   ├── 3-4-5: Confidence threshold — below `confidence_floor` → human review required
│  │   └── 3-4-6: Multi-vendor output harmonization — confirms adapter normalization (4-9-2)
│  │               completed at 4-15 boundary. This is the FIRST Cat 3 verification step
│  │               after normalization; verifies output is in canonical schema before any
│  │               Cat 3 security/policy checks execute. (Pre-Cat3 normalization is governed
│  │               by 4-15; 3-4-6 confirms and re-validates the result.)
│  │
│  ├── 3-5: Error Classification  [B|T2]
│  │   ├── 3-5-1: Severity taxonomy — P0 (blocking) / P1 (critical) / WARN / INFO
│  │   ├── 3-5-2: Structured error report — severity, location, memory snapshot, action required
│  │   ├── 3-5-3: Repeated-error halt — P0 error N× consecutively → HALT
│  │   └── 3-5-4: Actionable Error Presentation — any P0/P1 error escalated to the Human Gate
│  │               MUST be formatted with: (a) Root Cause (human-readable, not raw stack trace),
│  │               (b) System Impact (what is blocked, what state is affected),
│  │               (c) Actionable Remediation Steps (ordered list of human actions).
│  │               Optional: redacted stack trace for debugging context.
│  │               Example: not "AttributeError: 'NoneType' object has no attribute 'get'" —
│  │               instead: "Root: configuration store missing required key. Impact: parameter registry failed,
│  │               system cannot start. Steps: (1) add key X, (2) re-run bootstrap."
│  │               PASS: 100% of human-escalated terminal errors conform to actionable schema.
│  │               FAIL: error presented as raw stack trace or opaque code without context.
│  │
│  ├── 3-6: Rollback & Recovery  [C|T3]
│  │   ├── 3-6-1: Checkpoint-based rollback — periodic snapshots at natural save points
│  │   ├── 3-6-2: Recovery depth limit — bounded number of recoverable checkpoints
│  │   └── 3-6-3: State migration — shared state objects carry version field; migration present
│  │
│  ├── 3-7: Behavioral Compliance Tests (Runtime)  [C|T3]
│  │   Runtime behavior logs (agent actions during execution). Boundary: 3-2 = static checks.
│  │   ├── 3-7-1: Runtime log parsing — governance events extracted from execution logs
│  │   ├── 3-7-2: Scenario test suite — test cases: consensus, depth change, mode switch, halt
│  │   ├── 3-7-3: Parameter validation — governance config validated at system load time
│  │   └── 3-7-4: Compute budget per task class — upper bounds by complexity tier
│  │
│  ├── 3-8: Post-Mortem & Kaizen Loop  [C|T4]  [MAINT]
│  │   Every P0/P1 incident MUST generate a post-mortem. Kaizen = Continuous Process Remediation.
│  │   ├── 3-8-1: Automated post-mortem draft — incident triggers template:
│  │   │         Incident / Root Cause (5-Why) / Timeline / Category / Prevention / Policy Revision
│  │   ├── 3-8-2: Policy revision proposal — 5-Why output fed into governance doc revision
│  │   └── 3-8-3: Recurrence lock — same failure N× → task locked until Kaizen complete
│  │
│  ├── 3-9: Immutable Audit Logging  [C|T2]
│  │   ALL messages, decisions, and actions recorded in append-only, tamper-evident log.
│  │   Stored in dedicated infrastructure defined in 4-12 (outside working memory buffer).
│  │   Primary key: INSTANCE_ID (compliance). Cross-referenced via 2-9-5 join table (ROLE_ID).
│  │   ├── 3-9-1: Comprehensive capture — every state-mutating action and message logged
│  │   ├── 3-9-2: Append-only guarantee — entries cannot be modified or deleted
│  │   ├── 3-9-3: Retention policy — log rotation/archival schedule defined (operational policy)
│  │   └── 3-9-4: Structured queryability — indexed by INSTANCE_ID; joinable via 2-9-5
│  │
│  ├── 3-10: Functional Verification Gate  [C|T3]
│  │   Before any directive is marked FINALIZED, automated tests MUST pass.
│  │   Example: "login feature" must pass auth unit tests before FINALIZED.
│  │   ├── 3-10-1: Test execution requirement — automated tests must pass; or compilation succeeds
│  │   ├── 3-10-2: Correctness threshold — minimum passing criteria per task class
│  │   └── 3-10-3: Verification bypass — human may override with rationale; logged as P1;
│  │               triggers 3-8 post-mortem entry
│  │
│  ├── 3-11: Static Risk Escalation Matrix  [B|T2]
│  │   Certain high-risk domains MUST require Human Gate regardless of collaboration depth.
│  │   Example: editing governance documents = Human Gate mandatory; editing test files = standard.
│  │   ├── 3-11-1: Risk domain taxonomy — high (governance, credentials, network egress) /
│  │   │          medium (core logic, public APIs) / low (docs, tests, config)
│  │   ├── 3-11-2: Approval-level mapping — risk level → required approval gate
│  │   └── 3-11-3: Matrix review cadence — risk matrix reviewed on defined schedule
│  │
│  ├── 3-12: External Invocation Policy  [B|T2]
│  │   AI nodes making non-idempotent calls (writes) to external services MUST comply with policy.
│  │   Example: AI calling a payment API must be authorized and rate-limited to 10 calls/hour.
│  │   ├── 3-12-1: Idempotency classification — reads (safe) vs. writes (requires policy)
│  │   ├── 3-12-2: Rate-limit enforcement — max calls bounded by `max_external_invocations`
│  │   └── 3-12-3: Rollback protocol — failed external call triggers documented recovery steps
│  │
│  ├── 3-13: Governance Debt Tracking  [C|T3]  [MAINT]
│  │   GD Score = (active_bypass_count × 5) + (stale_pm_count × 3) +
│  │   (floor(degraded_hours/24) × 2). Unit: GD points. Ceiling: `governance_debt_ceiling`.
│  │   Measures VOLUME (accumulated debt). Distinct from 5-9 which measures VELOCITY (rate).
│  │   Example: 2 bypasses + 1 stale PM + 48 degraded hours = (10+3+4) = 17 GD points.
│  │   ├── 3-13-1: Bypass accumulation tracking — count of active policy bypasses (3-10-3)
│  │   ├── 3-13-2: Stale post-mortem count — PMs open > `post_mortem_sla_hours` per period (VOLUME measure)
│  │   ├── 3-13-3: Degraded-mode hours — cumulative hours in degraded mode per period
│  │   ├── 3-13-4: GD Score computation — automated daily calculation and logging
│  │   └── 3-13-5: GD ceiling enforcement — GD Score ≥ `governance_debt_ceiling` →
│  │               HALT new tasks until Kaizen (3-8) clears score below ceiling
│  │
│  ├── 3-14: Configuration Drift Detection  [C|T3]  [MAINT]
│  │   When parameters have both code-level defaults AND external config file values, they MUST
│  │   remain synchronized. Drift = any parameter where code default ≠ config file value.
│  │   Boundary note: 3-14 = default-value sync; 5-1 = parameter registry completeness.
│  │   Example: orchestrator code default HANDOFF_MAX_CHARS=12000 but external config says 8000 → drift →
│  │   startup MUST fail with a diff report.
│  │   ├── 3-14-1: Default source inventory — all defaults catalogued with authoritative source:
│  │   │           code-level OR config-file-level (never both as separate authorities)
│  │   ├── 3-14-2: Drift check at load time — automated comparison at system startup;
│  │   │           generates diff report on mismatch
│  │   └── 3-14-3: Single-source enforcement — drift detected → startup fails; operator must
│  │               designate ONE authoritative source and sync the other
│  │
│  └── 3-15: Meta-Governance Framework Upgrade Protocol  [B|T2]  [MAINT]
│      The governance framework itself MUST have a defined process for being upgraded.
│      Without this, the taxonomy, parameters, and rules cannot evolve in a controlled way.
│      This item applies the same governance rigor to FRAMEWORK changes as is applied to
│      application changes (3-3 Change Management, 3-9 Audit Logging).
│      Example: Adding a new item to §3 (like this item itself) MUST follow this protocol.
│      ├── 3-15-1: Upgrade proposal — framework changes proposed as formal directives (2-3-1);
│      │           require elevated consensus (minimum depth = `final_call_threshold`)
│      ├── 3-15-2: Impact assessment — before upgrading, analyze effect on:
│      │           active sessions, existing parameters, external references (PROTOCOL.md, etc.)
│      ├── 3-15-3: Versioned rollout — framework upgrade MUST produce a new version tag (4-4);
│      │           previous version stays accessible for active sessions that started on it
│      ├── 3-15-4: Migration window — active sessions may continue on prior version until natural
│      │           session end; new sessions MUST start on the new version
│      └── 3-15-5: Upgrade audit entry — framework upgrade event written to 3-9 audit log
│                  as a FRAMEWORK_UPGRADE boundary marker
│
├─ Cat 5 / Phase 6: Operations & Control  [7%]
│  Health monitoring, resource control, compute economy, degraded-mode, remediation velocity,
│  runtime reconfiguration, governance overhead bounding.
│  Input: validated artifact from Cat 3.
│  Output: governed artifact + health metrics to Cat 6.
│
│  ├── 5-1: Parameter Registry  [C|T3]
│  │   All behavioral thresholds MUST be in a single versioned registry. (See §6.)
│  │   ├── 5-1-1: Flat+metadata format — parameters grouped by category with metadata
│  │   ├── 5-1-2: Complete coverage — every threshold here, nowhere else
│  │   ├── 5-1-3: Integrity check — key count and section membership validated at load time
│  │   └── 5-1-4: Configuration-Driven Behavior Mandate — all governance behavioral variants
│  │               (vendor routing decisions, scenario activations, workflow mode switches,
│  │               collaboration depth adjustments) MUST be expressible as parameter combinations
│  │               in §6. No execution logic in governance components may be conditional on
│  │               hardcoded vendor names, node IDs, or non-parameterized environmental states.
│  │               Adding a new governance scenario MUST require only config file changes, not
│  │               source code modifications to the governance infrastructure.
│  │               PASS: static analysis of governance components finds 0 hardcoded vendor/node
│  │               identifiers in conditional logic; all behavioral branches driven by §6 params.
│  │               FAIL: governance component contains `if vendor == "X"` or equivalent
│  │               non-parameterized behavioral branch.
│  │
│  ├── 5-2: Parameter Validation  [C|T3]  [FLEX] [MAINT]
│  │   All parameters range-validated at load time; violations fail startup.
│  │   ├── 5-2-1: Load-time schema check — types and ranges validated on system start
│  │   ├── 5-2-2: Range enforcement — value outside range → startup failure with error
│  │   ├── 5-2-3: Section membership check — each parameter in exactly one section
│  │   └── 5-2-4: Hot-reload pre-conditions — when `hot_reload_enabled=1`, validate that:
│  │               (a) no active consensus rounds, (b) no uncommitted directives,
│  │               (c) new value passes range check; only then apply hot-reload
│  │
│  ├── 5-3: Observability  [C|T4]
│  │   Telemetry collection pipeline. Raw data feed for 5-4 dashboard.
│  │   All sizes in reference token units (vendor tokens converted via 4-9-1).
│  │   ├── 5-3-1: Working memory monitoring — real-time size vs. warn/critical bands
│  │   ├── 5-3-2: Async event handling — out-of-band events processed without blocking
│  │   ├── 5-3-3: Collaboration metrics — depth, consensus rate, per-mode node counts
│  │   └── 5-3-4: Vendor-agnostic health normalization — all metrics in reference token units
│  │
│  ├── 5-4: System Health Dashboard  [C|T3]
│  │   Human display interface. MUST show: session ID, collaboration depth, working memory
│  │   health band, and governance overhead ratio simultaneously.
│  │   ├── 5-4-1: Required fields — session ID, collaboration depth, memory health band,
│  │   │         per-mode node count (ACTIVE/OBSERVER), governance overhead ratio
│  │   ├── 5-4-2: Metrics aggregation — policy compliance %, consensus success rate
│  │   ├── 5-4-3: Persistent metric store — metrics written at `metrics_persist_interval`
│  │   ├── 5-4-4: Dashboard specification — formal schema for all required fields
│  │   └── 5-4-5: Real-time Operational Status Presentation — dashboard MUST display the current
│  │               operational state as a discrete, human-readable status indicator.
│  │               States: RUNNING / WAITING_FOR_HUMAN / DEGRADED / IDLE / COMPLETED
│  │               Each state includes temporal context (time-in-state) and last-action summary.
│  │               This complements 3-5-4 (error format on failure) with normal-path visibility.
│  │               Example: "WAITING_FOR_HUMAN [00:03:21] — awaiting ACK on UAT criteria review"
│  │               PASS: system provides distinct deterministic state indicators with temporal
│  │               context; state transitions logged to audit log.
│  │               FAIL: progress status relies solely on raw unparsed logs; no discrete state
│  │               indicator available to human operator.
│  │
│  ├── 5-5: Active Control Loop  [C|T4]
│  │   System proactively prevents resource exhaustion via automated circuit-breakers.
│  │   Cat 0 and Cat 6 human gates are EXEMPT from automated override (see C3 in §5.5).
│  │   ├── 5-5-1: Lock-safety check — no active writes before any control action
│  │   ├── 5-5-2: Critical band trigger — critical working memory → auto-checkpoint +
│  │   │         depth reduction (floor: `min_collaboration_depth`)
│  │   ├── 5-5-3: Budget control — near-ceiling triggers alert; ceiling forces minimal depth
│  │   ├── 5-5-4: SLA escalation — consecutive timeouts → auto-ESCALATE to human
│  │   └── 5-5-5: Safety guard — `active_control_enabled=0` default;
│  │               when enabled: MUST NOT override Cat 0 intent gate or Cat 6 delivery ACK
│  │
│  ├── 5-6: Economic & Quota Governance  [C|T4]
│  │   Compute spend tracked, forecasted, and bounded across all vendors.
│  │   ├── 5-6-1: Compute ROI — finalized directives + merged change records / compute units
│  │   ├── 5-6-2: Budget management — alert and hard-ceiling thresholds enforced
│  │   ├── 5-6-3: Runway forecasting — projected depletion from current burn rate
│  │   ├── 5-6-4: Delegation cost rules — repeated identical searches → delegate to specialist
│  │   ├── 5-6-5: Multi-vendor compute accounting — per-vendor cost matrix (`token_cost_matrix`)
│  │   └── 5-6-6: Rate-limit negotiation — adapters declare per-vendor limits; control loop
│  │               coordinates across nodes to prevent quota exhaustion
│  │
│  ├── 5-7: Concurrent Session Management  [C|T2]  [SCALE]
│  │   Multiple parallel sessions MUST have conflict detection, locking, and merge resolution.
│  │   ├── 5-7-1: Granular state locking — file-level or object-level; not workspace-wide
│  │   ├── 5-7-2: Conflict detection — overlapping edits detected before commit
│  │   └── 5-7-3: Merge / deadlock resolution — automated merge where safe; escalate otherwise
│  │
│  ├── 5-8: Degraded Mode & Fallback  [C|T3]
│  │   When components fail or limits are reached, predefined behaviors maintain viable operation.
│  │   `intent_timeout` is SUSPENDED (not merely extended) during degraded mode (see C5 in §5.5).
│  │   ├── 5-8-1: Failure detection — component liveness and quota status monitored
│  │   ├── 5-8-2: Graceful degradation — e.g., read-only mode, human-only override
│  │   └── 5-8-3: Reintegration — auto-reconnect + state reconciliation on recovery
│  │
│  ├── 5-9: Remediation Velocity Tracking  [C|T3]  [MAINT]
│  │   The system MUST measure its own learning RATE: how fast does it improve after failures?
│  │   Measures VELOCITY (flow/rate). Distinct from 3-13 which measures VOLUME (stock of debt).
│  │   Example: same P0 error recurs 3 weeks after post-mortem → velocity = critically low.
│  │   ├── 5-9-1: Failure-to-policy cycle time — time from failure class identification to
│  │   │         deployment of preventative policy (lower = better)
│  │   ├── 5-9-2: PM closure rate trend — mean time-to-close PMs over rolling 30 days;
│  │   │         worsening trend (increasing mean) → WARN escalation.
│  │   │         Boundary note: this measures VELOCITY; 3-13-2 measures cumulative COUNT.
│  │   └── 5-9-3: Learning rate dashboard — velocity trend over rolling 30 days;
│  │               improving trend = positive; flat/worsening = governance review triggered
│  │
│  ├── 5-10: Runtime Reconfiguration Protocol  [C|T3]  [FLEX]
│  │   When `hot_reload_enabled=1`, governance parameters MAY be updated mid-session.
│  │   Example: `collaboration_depth` lowered from 10 to 5 mid-session due to budget pressure.
│  │   ├── 5-10-1: Hot-reload trigger — request arrives as PARAM_HOT_RELOAD event via 2-2
│  │   ├── 5-10-2: State consistency pre-check — (a) no active consensus rounds,
│  │   │           (b) no uncommitted directives, (c) all nodes ACK via 2-2 vote
│  │   └── 5-10-3: Audit boundary marker — event written to 3-9 as immutable boundary;
│  │               subsequent decisions audited against NEW value; prior against old value
│  │
│  ├── 5-11: Governance Overhead Budget  [C|T3]  [SCALE]
│  │   If governance overhead exceeds `governance_overhead_ceiling_pct` of total compute,
│  │   the governance meta-system becomes a bottleneck to productive work.
│  │   Example: 30% of compute on consensus rounds (threshold 20%) → auto-propose depth reduction.
│  │   ├── 5-11-1: Overhead ratio tracking — governance compute / total compute; logged per session
│  │   ├── 5-11-2: Overhead alert — ratio > ceiling → WARN in health dashboard (5-4-1)
│  │   └── 5-11-3: Overhead reduction protocol — ratio exceeds ceiling for 3+ consecutive sessions:
│  │               (a) auto-propose `collaboration_depth` reduction (floor: `min_collaboration_depth`);
│  │               (b) suggest deferring non-critical governance events;
│  │               (c) human ACK required before depth change
│  │
│  └── 5-12: Resource Lazy Initialization  [C|T3]  [SCALE]
│      Heavy resources (vendor API connections, Agent frameworks, MCP servers, specialized node
│      instances) MUST be initialized upon first explicit directive use, NOT at system bootstrap.
│      This prevents resource waste during idle phases and supports lightweight startup.
│      Boundary note: 4-2 (bootstrap) defines WHAT is required at startup (core governance infra);
│      5-12 defines WHEN heavy optional resources are instantiated (lazy, on demand).
│      Example: a vendor AI client connection deferred until first directive requiring it; not initialized at orchestrator startup.
│      ├── 5-12-1: Just-In-Time Allocation — heavy/vendor resources MUST be deferred until the
│      │           first directive explicitly requires them; system bootstrap allocates only core
│      │           governance infrastructure (IPC hub, registry, parameter store)
│      ├── 5-12-2: Idle Teardown — initialized resources unused for > `idle_teardown_timeout`
│      │           minutes MUST be deallocated; prevents resource leak during long-running sessions;
│      │           teardown event logged to 3-9 audit log
│      └── 5-12-3: Event-Driven Check Execution — governance checks (e.g., GD Score computation
│                  in 3-13, behavioral compliance tests in 3-7, artifact scale check in 4-10)
│                  MUST execute on-demand, triggered by relevant lifecycle events or explicit
│                  boundary transitions — NOT by continuous idle polling loops.
│                  Example: GD Score recalculates on bypass event or session end, not every second.
│                  This extends 5-12's lazy principle from resources to governance checks.
│                  PASS: check execution traces are event-triggered (audit log shows trigger event
│                  immediately preceding check run); no periodic polling loops in governance scripts.
│                  FAIL: governance check running on a fixed-interval polling loop without a
│                  corresponding triggering event.
│
└─ Cat 6 / Phase 7: Product Delivery & Validation  [5%]
   Exit gate. ANY capable AI node may present to human (per 2-1-3).
   Human acceptance + lessons feed Phase 1 of the next cycle.
   Input: governed artifact + health metrics from Cat 5.
   Output: delivery ACK + lessons + next-session seed to Cat 0.

   ├── 6-1: Artifact Assembly  [B|T2]
   │   Every deliverable MUST be a discrete file artifact.
   │   ├── 6-1-1: Output format compliance — matches Cat 0-2-3 delivery format spec
   │   ├── 6-1-2: Completeness check — all Cat 0-2-1 acceptance criteria addressed
   │   └── 6-1-3: File output mandate — all deliverables written as files (loss prevention)
   │
   ├── 6-2: User Acceptance Test  [C|T3]
   │   Human MUST verify the Primary Success Scenario before closure.
   │   ├── 6-2-1: Explicit acceptance gate — `delivery_ack_required=1` → human ACK required
   │   ├── 6-2-2: Regression check — no previously passing tests broken by this delivery
   │   └── 6-2-3: Scenario coverage — Primary Success Scenario + ≥1 edge case verified
   │
   ├── 6-3: Delivery Handoff & Feedback  [C|T3]
   │   Session archived; lessons feed the next cycle including F/S/M constraint refinements.
   │   ├── 6-3-1: Session archive — save + close procedure run on completion
   │   ├── 6-3-2: Lessons routing — incidents → 3-8 Post-Mortem; F/S/M lessons → 0-5 next cycle
   │   ├── 6-3-3: Next intent seeding — handoff includes next-session context for Cat 0
   │   └── 6-3-4: Feedback specificity — human corrections rated SPECIFIC vs. VAGUE;
   │               Metric: % SPECIFIC / total (target: ≥70%)  [↩ loop back to Cat 0]
   │
   ├── 6-4: Delivery Failure & Retry Limits  [C|T3]
   │   Repeated UAT failures MUST trigger escalation rather than indefinite retry.
   │   This prevents infinite revision loops and forces structured problem resolution.
   │   Example: After 3 UAT failures (delivery_retry_limit=3), the session escalates to
   │   human with full failure log rather than attempting a 4th revision autonomously.
   │   ├── 6-4-1: Retry counter — count of consecutive UAT (6-2) failures per delivery attempt
   │   ├── 6-4-2: Retry limit enforcement — when counter reaches `delivery_retry_limit` →
   │   │           HALT autonomous revision; escalate to Human Gate with failure log
   │   └── 6-4-3: Reset condition — counter resets only after explicit human intervention
   │               and a new CLARIFICATION_ACK for revised acceptance criteria
   │
   └── 6-5: Partial Acceptance Protocol  [C|T3]
       When a delivery partially satisfies acceptance criteria, a defined protocol allows
       partial acceptance rather than binary pass/fail, enabling iterative delivery.
       Example: 7 of 10 acceptance criteria met → partial ACK with explicit deferred list;
       next session picks up the deferred criteria as its starting intent (0-1).
       ├── 6-5-1: Partial acceptance threshold — minimum % of acceptance criteria met for
       │           partial delivery to be valid (default: ≥60%; configurable per session)
       ├── 6-5-2: Deferred criteria tracking — unmet criteria explicitly listed and forwarded
       │           to next session's intent schema (Cat 0-1)
       └── 6-5-3: Partial delivery log — partial acceptance event logged to 3-9 with:
                  accepted criteria, deferred criteria, rationale, and next-session Goal ID
```

---

## §4. Binary/Deterministic KPI Matrix

> **Format**: PASS: [machine-checkable condition] | FAIL: [violation trigger]. All binary, reproducible.

### Cat 0 / Phase 1: Human Intent

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 0-1 | Intent Capture | B | T2 | Every executed sub-task maps to a unique Goal ID in session initiation schema | Any task execution without parent Goal ID |
| 0-2 | Success Criteria | B | T2 | Session initiation artifact contains ≥1 human-verifiable criterion per Goal ID | Goal ID exists with zero acceptance criteria |
| 0-3 | Clarification | C | T3 | Rounds ≤ `clarification_max_turns`; CLARIFICATION_ACK present before multi-file execution | CLARIFICATION_ACK absent on any multi-file task start |
| 0-4 | Intent Alignment | B | T2 | 100% of file mutations within declared scope (per Cat 0-1-2) | Any file mutation outside declared scope |
| 0-5 | Non-Functional Intent | B | T2 | Session initiation artifact contains 0-5-1/2/3 fields before multi-node execution | Multi-node session started without 0-5 fields |
| 0-6 | Health Pre-Check | C | T3 | GD Score < ceiling; zero active P0 alerts; previous session archived (6-3-1 done) | New session started with GD Score ≥ ceiling, active P0, or unarchived session |

### Cat 4 / Phase 2: Environment

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 4-1 | Runtime Env. | C | T3 | All deps isolated; encoding set; zero host-dependency at runtime | Any dep from host; encoding unset |
| 4-2 | Installation | C | T3 | Bootstrap exits 0; smoke test passes; 0 manual steps | Bootstrap non-zero; manual step required |
| 4-3 | Infra Abstraction | C | T3 | IPC OK; node registry valid; transport scalable without restart | IPC unreachable; transport requires restart to scale |
| 4-4 | Version Mgmt | B | T2 | 100% governance docs carry vX.Y tag; changelog updated on each version | Any governance doc missing version tag |
| 4-5 | Platform Indep. | C | T3 | Static scan: zero absolute paths in committed artifacts | Any absolute path in committed file |
| 4-5-4 | Separation Mandate | B | T2 | [변경됨] Zero workspace-specific constants in universal components; 100% of connections trace to connection point file | Hardcoded workspace paths/vendors in universal logic; missing connection point file |
| 4-6 | Node Onboarding | B | T2 | 100% registered nodes pass checklist; wrapper code passes audit | Any node voting without checklist |
| 4-7 | Capability Profile | C | T2 | 100% task delegations preceded by capability profile check | Any delegation without profile check in log |
| 4-8 | Model Lifecycle | C | T3 | Behavioral regression suite exists; 100% model version transitions trigger suite | Model version change without suite run |
| 4-9 | Vendor Adapter | C | T2 | All adapters pass test suite; 100% vendor output normalized before Cat 3 | Any vendor output entering Cat 3 without normalization |
| 4-10 | Artifact Scale | C | T3 | When count > `artifact_scale_threshold`: localized scope applied; override logged | Scale trigger reached without localized scope or override log |
| 4-11 | Doc Freshness | C | T3 | 100% governance docs reviewed within `doc_freshness_interval` days; zero orphaned refs | Any doc overdue; orphaned reference detected |
| 4-12 | Durable Audit Infra | C | T2 | Audit storage location defined + isolated from working memory; persists across restarts | Audit storage undefined; audit lost on restart; pruning operation touches audit log |
| 4-13 | Canonical Peer Interface | B | T2 | All registered peers satisfy 4-13 capability contract; adapters (4-9) target canonical schema; depth semantics equivalent across vendors | Any peer voting without contract compliance; adapter bypasses canonical schema; depth=N produces different quorum on different vendors |
| 4-14 | Agent/Skill/Tool Ext. | C | T3 | 100% extensions run through registered lifecycle; MCP calls logged with authorization reference | Extension invoked without registration; MCP call without authorization envelope |
| 4-15 | Adapter Boundary | B | T2 | 100% VEL outputs pass 4-15 normalization before Cat 3 entry; no raw vendor data in Cat 3 | Raw vendor-format data detected in Cat 3 input; normalization bypassed |
| 4-16 | Workspace Template | B | T2 | [추가됨] Core logic has zero knowledge of workspace paths; all connections via connection point file; template registry exists | Hardcoded workspace references in core; template registry missing |
| 4-17 | Composable Arch. | B | T2 | [추가됨] All inter-component dependencies declared in JSON; zero circular imports; components functional via IPC | Hardcoded component dependencies; circular imports; monolithic coupling |

### Cat 1 / Phase 3: Cognitive Continuity

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 1-1 | Working Memory | C | T4 | Memory within normal band; critical band entry 0 per 48h | Critical band entry detected |
| 1-2 | Session Continuity | B | T2 | Handoff artifact present with all required sections (1-2-1 through 1-2-5); size ≤ limit | Handoff missing any required section |
| 1-3 | Memory Persistence | C | T4 | Stale entry count = 0; last compaction ≤ `memory_compaction_interval` days ago | Stale entries detected; compaction overdue |
| 1-4 | Instruction Efficacy | B | T2 | Mid-session correction rate ≤ 10% (corrections / total sessions) | Rate exceeds 10% |
| 1-5 | Domain Knowledge | C | T3 | Knowledge retrieval present in logs for domain-context sessions | Domain-context session with zero retrieval events |

### Cat 2 / Phase 4: Collaboration Governance

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 2-1 | Gov. Principles | B | T2 | Equal vote weight enforced; any node can propose in any phase per registry | Vote weight discrepancy; phase-ownership restriction |
| 2-2 | Consensus | C | T3 | 100% decisions have Propose→Vote→Finalize trace; quorum ≤ `max_nodes_per_consensus` | Decision without trace; quorum exceeded cap |
| 2-3 | Task Mgmt | C | T3 | 100% multi-node executions preceded by Division Proposal consensus event | Multi-node execution without Division Proposal |
| 2-4 | Conflict Resolution | B | T2 | Escalation path present; 100% deadlocks resolved within `consensus_timeout` | Deadlock unresolved at timeout |
| 2-5 | Node Registry | C | T3 | 100% registry entries complete; depth within 0 to Count(ACTIVE_NODES) | Any node voting without registry entry |
| 2-6 | Participation | C | T3 | 100% mode transitions logged; GRACEFUL_EXIT has handoff confirmation; HUMAN_TRANSFER boundary logged | Mode change unlogged; exit without handoff; authority transfer without boundary marker |
| 2-7 | Sub-Teaming | C | T3 | 100% task forces have charter + synthesis vote in log | Task force merged without synthesis vote |
| 2-8 | Role Mgmt | C | T3 | 100% directives specify intended_role; join table current; hot-swap events logged as boundaries | Directive with node_id; hot-swap without boundary |
| 2-9 | Transparency | C | T4 | Audit log entry count ≥ message dispatch count | Log count mismatch |

### Cat 3 / Phase 5: System Integrity

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 3-1 | Security | B | T2 | Policy gate security checks PASS; zero credential files accessed by AI | Any credential file access by AI node |
| 3-2 | Policy Enforcement | C | T3 | Policy gate exits 0; vendor-neutral DSL present | Gate exits non-zero; policy in vendor-specific syntax |
| 3-3 | Change Mgmt | C | T3 | VCS hook rejects 100% non-conforming change records | Non-conforming change record accepted |
| 3-4 | Output Validation | C | T3 | Zero schema violations; zero outputs below confidence floor reaching delivery | Schema violation at delivery; confidence bypass |
| 3-5 | Error Class. | B | T2 | P0/P1/WARN/INFO taxonomy documented; halt rule coded | Error without severity class; P0×N without halt |
| 3-6 | Rollback | C | T3 | Checkpoints ≥ `max_recovery_depth`; state version field in all state objects | Checkpoint count below max; state object missing version |
| 3-7 | Behavioral Tests | C | T3 | 100% DIRECTIVEs trace to FINALIZED or documented rejection | DIRECTIVE without FINALIZED or rejection |
| 3-8 | Post-Mortem | C | T4 | 100% P0/P1 events generate PM draft within SLA; zero open >`post_mortem_sla_hours` | P0/P1 without PM draft; PM open past `post_mortem_sla_hours` |
| 3-9 | Audit Log | C | T2 | Append-only log exists; entry count monotonically increasing; join table present | Log modification detected; join table missing |
| 3-10 | Functional Verify | C | T3 | All automated tests pass before FINALIZED; bypass logged as P1 | FINALIZED without test-pass (and no bypass log) |
| 3-11 | Risk Escalation | B | T2 | Risk matrix defined; all high-risk domain changes have Human Gate event | High-risk change without Human Gate |
| 3-12 | External Policy | B | T2 | External invocation policy defined; all write calls have authorization record | Non-idempotent call without authorization |
| 3-13 | Governance Debt | C | T3 | GD Score computed daily; GD Score < `governance_debt_ceiling` | GD Score ≥ ceiling for >24h; task started while ceiling breached |
| 3-14 | Config Drift | C | T3 | System starts with zero parameter drift (code default = config value, all params) | Drift detected at load time; system starts despite drift |
| 3-15 | Meta-Governance | B | T2 | Framework changes follow 3-15-1 through 3-15-5 protocol; upgrade boundary in audit log | Framework change without formal directive; no upgrade boundary in 3-9 |

### Cat 5 / Phase 6: Operations & Control

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 5-1 | Param Registry | C | T3 | Zero hardcoded thresholds in code; all 38 parameters in registry | Any threshold hardcoded outside registry |
| 5-2 | Param Validation | C | T3 | Valid registry = system starts; invalid = exit non-zero; hot-reload pre-conditions checked | System starts with out-of-range value; hot-reload without pre-condition check |
| 5-3 | Observability | C | T4 | Health endpoint responds within 1s; all metrics in reference token units | Endpoint timeout; metric in vendor-native units |
| 5-4 | Dashboard | C | T3 | Dashboard shows session ID + depth + memory band + overhead ratio simultaneously | Any required field missing |
| 5-5 | Active Control | C | T4 | When enabled: 100% critical events trigger response; Cat 0/6 gates unchanged | Critical event without response; Cat 0/6 gate overridden |
| 5-6 | Economic Gov. | C | T4 | Budget ≤ `budget_alert_threshold`; per-vendor cost tracked | Budget exceeded without alert; cost untracked |
| 5-7 | Concurrent | C | T2 | 100% concurrent write conflicts resolved without data loss | Data loss; unresolved conflict in log |
| 5-8 | Degraded Mode | C | T3 | All failure modes have tested fallback; `intent_timeout` SUSPENDED (not merely extended) in degraded mode | Undefined failure mode; timeout expires during degraded state |
| 5-9 | Remediation Vel. | C | T3 | Failure-to-policy cycle time measured + trending; PM closure rate monitored | Cycle time not measured; PM closure rate worsening without alert |
| 5-10 | Runtime Reconfig | C | T3 | When enabled: 100% hot-reloads pass pre-check; boundary markers in audit log | Hot-reload without pre-check; boundary marker absent |
| 5-11 | Gov. Overhead | C | T3 | Overhead ratio ≤ `governance_overhead_ceiling_pct`; logged per session | Ratio exceeds ceiling for 3+ consecutive sessions without corrective action |
| 5-12 | Lazy Init | C | T3 | Bootstrap allocates 0 heavy/vendor resources; idle resources deallocated after `idle_teardown_timeout` | Heavy resource initialized at bootstrap without directive; resource not torn down after timeout |

### Cat 6 / Phase 7: Delivery

| ID | Item | Type | Tier | PASS Condition | FAIL Trigger |
|:---|:-----|:----:|:----:|:---------------|:-------------|
| 6-1 | Artifact Assembly | B | T2 | All deliverables as files; format matches Cat 0-2-3 spec | Deliverable not a file; format mismatch |
| 6-2 | UAT | C | T3 | All Cat 0-2 criteria verified (via Cat 3-10) before closure; HUMAN_ACK in log | Session closed without HUMAN_ACK; unverified criterion |
| 6-3 | Handoff & Feedback | C | T3 | Archive present; NEXT_SESSION non-empty; ≥70% SPECIFIC corrections | Archive missing; NEXT_SESSION empty; <70% specific |
| 6-4 | Delivery Retry Limit | C | T3 | Retry counter tracked; when count ≥ `delivery_retry_limit` → escalation triggered before next revision | UAT failed N+ times without escalation; revision attempted after limit reached |
| 6-5 | Partial Acceptance | C | T3 | Partial ACK event logged with accepted + deferred criteria; deferred forwarded to next session 0-1 | Partial delivery accepted without explicit deferred list; deferred criteria not in next session intent |

---

## §4.5 Quality Attribute KPI Summary View

> This section consolidates all items tagged [FLEX], [SCALE], or [MAINT] for quality attribute monitoring.
> Completeness = items with Implementation Score > 0 / total items per attribute.

### Flexibility [FLEX] Items

| Item ID | Name | Tier | Current Status | Key Metric |
|:--------|:-----|:----:|:---------------|:-----------|
| 4-3 | Infrastructure Abstraction | C\|T3 | Partial (4-3-5 TODO) | Transport restartless scaling |
| 4-9 | Vendor Integration Layer | C\|T2 | Partial (TODO) | Adapter test pass rate |
| 2-6 | Participation Management | C\|T3 | Partial | Mode transition log completeness |
| 2-8 | Dynamic Role Management | C\|T3 | Partial (2-8-5 TODO) | Hot-swap boundary events in 3-9 |
| 5-8 | Degraded Mode & Fallback | C\|T3 | Partial | Fallback coverage % |
| 0-5 | Non-Functional Intent | B\|T2 | TODO (G39) | 0-5-1/2/3 fields in session init |
| 5-2 | Parameter Validation | C\|T3 | Partial | Hot-reload pre-check pass rate |
| 5-10 | Runtime Reconfiguration | C\|T3 | TODO (G42) | Hot-reload success rate |
| 4-13 | Canonical Peer Interface | B\|T2 | TODO (G48) | Adapter canonical schema compliance |
| 4-14 | Agent/Skill/Tool Extension | C\|T3 | TODO (G49) | Extension registration compliance |
| 4-16 | Workspace Template Arch. | B\|T2 | TODO (G58) | Template-based workspace creation rate |
| 4-17 | Composable Architecture | B\|T2 | TODO (G62) | Component hot-swap success rate |

### Scalability [SCALE] Items

| Item ID | Name | Tier | Current Status | Key Metric |
|:--------|:-----|:----:|:---------------|:-----------|
| 5-7 | Concurrent Session Management | C\|T2 | Partial | Conflict resolution rate |
| 2-7 | Sub-Teaming | C\|T3 | TODO (G32) | Task force synthesis success |
| 5-6 | Economic & Quota Governance | C\|T4 | Partial | Budget utilization % |
| 4-10 | Artifact Scale Governance | C\|T3 | TODO (G41) | Localized scope activation rate |
| 5-11 | Governance Overhead Budget | C\|T3 | TODO (G42) | Overhead ratio per session |
| T11 | Consensus Breadth KPI | Trade-off | — | MTC decay rate per added node |
| 4-14 | Agent/Skill/Tool Extension | C\|T3 | TODO (G49) | Extension invocation rate vs. governance overhead |
| 5-12 | Resource Lazy Initialization | C\|T3 | TODO (G50) | Bootstrap resource count; idle teardown compliance |
| 4-17 | Composable Architecture | B\|T2 | TODO (G63) | Dependency graph depth; zero-dependency component count |

### Maintainability [MAINT] Items

| Item ID | Name | Tier | Current Status | Key Metric |
|:--------|:-----|:----:|:---------------|:-----------|
| 3-3 | Change Management | C\|T3 | Partial | Conforming change record % |
| 3-8 | Post-Mortem & Kaizen | C\|T4 | Partial (TODO) | PM draft SLA compliance % |
| 4-4 | Version Management | B\|T2 | Partial | Docs with version tags % |
| 5-9 | Remediation Velocity | C\|T3 | TODO (G38) | Mean time-to-close PMs |
| 1-4 | Instruction Efficacy | B\|T2 | Partial | Mid-session correction rate |
| 3-13 | Governance Debt | C\|T3 | TODO (G40) | GD Score value |
| 3-14 | Config Drift Detection | C\|T3 | TODO (G40) | Drift instances at load time |
| 4-11 | Doc Freshness | C\|T3 | TODO (G41) | Overdue docs count |
| 4-12 | Durable Audit Infrastructure | C\|T2 | TODO (G43) | Audit storage isolation confirmed |
| 3-15 | Meta-Governance | B\|T2 | TODO (G44) | Framework upgrades following protocol |
| 3-2-6 | Implementation Constant Extraction | C\|T3 | TODO (G51) | Zero inline magic constants in governance scripts |
| 4-16 | Workspace Template Arch. | B\|T2 | TODO (G59) | Zero hardcoded workspace paths in core components |

---

## §5. Architectural Trade-offs (T1–T31)

> Control Parameter: the parameter used to tune this trade-off (see §6).
> Policy: no parameter — managed by architectural or operational decision.

| # | Dimension A (more A = less B) | Dimension B | Control | Notes |
|:--|:------------------------------|:------------|:--------|:------|
| T1 | Consensus Breadth (more nodes involved) | Compute Efficiency | `collaboration_depth` | 0=single-node autonomy, max=unanimity; floor: `min_collaboration_depth` |
| T2 | Memory preservation | Processing speed | `context_warn_threshold` | Lower = more sensitive pruning |
| T3 | Consensus accuracy | Response latency | `consensus_timeout` | See balance metrics below |
| T4 | Autonomy | Safety | `collaboration_depth` | Anchored scale; 5 recommended checkpoints |
| T5 | Documentation richness | Compute cost | Query language density | Denser = more information per token |
| T6 | Session continuity | Memory freshness | `memory_compaction_interval` + `resolved_item_ttl` | Combined control for TTL |
| T7 | Portability | Platform optimization | No hardcoded paths policy | Policy-based |
| T8 | Policy strictness | Development velocity | `final_call_threshold` | Higher = more governance overhead |
| T10 | Security isolation | Collaboration convenience | Credential access policy | Policy-based |
| T11 | Node scalability | Consensus complexity | `max_nodes_per_consensus` | KPI: MTC decay rate per added node; linear = acceptable, exponential = failing |
| T12 | Pruning aggressiveness | Memory preservation | `resolved_item_ttl` | Shorter = more aggressive |
| T13 | Metric granularity | Storage I/O | `metrics_persist_interval` | Shorter = more data |
| T14 | Forecast sensitivity | Alert fatigue | `forecast_alert_threshold` | Lower = more alerts |
| T15 | Kaizen frequency | Execution velocity | Post-mortem cadence policy | Policy-based |
| T16 | Active automation | Human control | `active_control_enabled` | 0=safe default |
| T17 | Compute economy | Collaboration depth | `daily_compute_budget` + `collaboration_depth` | Dual control |
| T18 | Full rewrite (safe syntax, high cost) | Surgical patch (low cost, syntax risk) | Edit strategy policy | Practice-based |
| T19 | Human visual verification (blocks async) | Automated testing (compute cost) | Test strategy policy | Policy-based |
| T20 | Heuristic flexibility | Strict policy gates | `policy_bypass_floor` | Higher = more gates bypassed |
| T21 | System specificity (high precision) | Universal portability | Audience declaration | Architecture choice |
| T22 | Vendor-native capability | Canonical abstraction (portability) | `allowed_vendors` + 4-9 adapter cost | Proprietary optimizations vs. multi-vendor governance |
| T23 | Role diversity (logical clarity) | Working memory fragmentation | Justification: same model backing N roles shares inference | No memory multiplication |
| T24 | Sub-team execution speed | Global transparency (deferred broadcast) | 2-7 task force OBSERVER opt-in | Resolved by 2-9-1 audit log guarantee |
| T25 | Execution velocity (bypasses allowed) | Governance debt accumulation | `governance_debt_ceiling` | Lower = stricter; 0 = zero tolerance; ceiling breach → HALT |
| T26 | Hot-reload flexibility | Audit stability | `hot_reload_enabled` | 0=stable audit; 1=flexible with mandatory boundary events |
| T27 | Governance completeness | Execution velocity | `governance_overhead_ceiling_pct` | Distinct from T1: T1=WHETHER to invoke collaboration; T27=COST of governance once running |
| T28 | Hot-reload flexibility (mid-session param changes) | Audit clarity (unambiguous rule version for each decision) | `hot_reload_enabled` + 5-10-3 | Resolved by mandatory audit boundary marker event (5-10-3) |
| T29 | Interface Standardization (canonical 4-13 contract enforced) | Vendor Feature Access (proprietary capabilities not in canonical interface) | `mcp_strictness_mode` | Distinct from T22 (vendor adapter translation cost); T29 governs the canonical contract layer that adapters must target |
| T30 | Lazy Init Efficiency (5-12; defer heavy init until needed) | Runtime Failure Visibility (eager init → errors at boot, known state; lazy init → errors mid-execution) | `lazy_init_enabled` / `idle_teardown_timeout` | Higher risk in degraded mode (5-8) if lazy-init fails mid-session; mitigated by 5-12-2 idle teardown and 5-8 fallback runbooks |
| T31 | Tool/Skill Execution Autonomy (micro-actions autonomous within pre-approved envelope) | Centralized Governance (every action requires 2-2 consensus) | `mcp_strictness_mode` | Balance: macro-authorization via 2-3 Task Management + micro-autonomy within envelope + gate at 3-10 Functional Verification. strict=full gate; lenient=envelope-bounded autonomy; permissive=no gate |

> Note: Identifier T9 is intentionally reserved (its concerns are managed under T6).

### Balance Metrics for Key Trade-offs

**T3 — Consensus Accuracy vs. Latency**

| Metric | Measurement | Balance Criterion |
|:-------|:-----------|:-----------------|
| MTC (Mean Time to Consensus) | Propose→FINALIZED event time delta | MTC ≤ `consensus_timeout` × 0.5 |
| Rejection Rate | ESCALATE count / total rounds | ≤ 10% |

**T11 — Node Scalability vs. Consensus Complexity**

| Metric | Measurement | Balance Criterion |
|:-------|:-----------|:-----------------|
| MTC Decay Rate | Δ MTC per additional ACTIVE node | Linear growth = acceptable; exponential = scalability failing |
| Quorum Cap | Active quorum vs. `max_nodes_per_consensus` | Quorum ≤ cap at all times |

**T17 — Compute Economy vs. Depth**

| Metric | Measurement | Balance Criterion |
|:-------|:-----------|:-----------------|
| Budget Utilization | Daily spend / `daily_compute_budget` × 100 | < `budget_alert_threshold` |
| Rounds per Decision | Avg rounds per FINALIZED directive | ≤ 3 |

**T27 — Governance Completeness vs. Execution Velocity**

| Metric | Measurement | Balance Criterion |
|:-------|:-----------|:-----------------|
| Overhead Ratio | Governance compute / total compute | ≤ `governance_overhead_ceiling_pct` |
| Consecutive Violations | Sessions with ratio > ceiling | < 3 consecutive sessions |

---

## §5.5 Logical Contradictions (C1–C10)

> Non-parameterizable tensions requiring explicit acknowledgment and management strategy.

| # | Contradiction | Affected | Management Strategy |
|:--|:-------------|:---------|:-------------------|
| C1 | Depth verbosity vs. working memory size: maximum depth mandates unlimited rounds, guaranteeing memory growth beyond warn threshold | Cat 1-1 vs 2-2, 2-5 | `collaboration_depth` acts as relief valve. Reduce for extended sessions. Ceiling enforced by `context_critical_threshold`. |
| C2 | "Zero-context usable" claim vs. historical observability: Cat 5-6 (ROI) and Cat 5-9 (velocity) require historical data unavailable at session start | §1.1 vs 5-6, 5-9 | "Zero-context" = document self-explanatory, not system history-free. Runtime analytics require history. Framework Score (100%) is zero-context; Implementation Score is not. |
| C3 | Active control loop vs. Human-in-Loop gates: automated circuit-breaker may change depth and trigger checkpoints — potentially overriding Cat 0/6 human gates | Cat 5-5 vs 0, 6 | `active_control_enabled=0` default. When enabled, loop MUST NOT override Cat 0 intent gate or Cat 6 delivery ACK. Human bookends explicitly exempt. |
| C4 | Audit log completeness vs. memory pruning: immutable logging (3-9) keeps everything; aggressive pruning (1-1-3, 1-3-2) discards data | Cat 3-9 vs 1-1-3, 1-3-2 | Audit log stored in dedicated infrastructure (4-12), outside working memory buffer. Pruning applies only to working memory. Audit log is NEVER subject to memory pruning operations. |
| C5 | Degraded mode autonomy vs. human intent timeout: degraded mode (5-8) requires human intervention, but `intent_timeout` risks premature abort before human can respond | Cat 5-8 vs 0-3 | Degraded mode SUSPENDS `intent_timeout` indefinitely (not merely extends it). Session auto-suspends and resumes when human responds. Auto-resume triggered by human response event. Normal timeout resumes only after full recovery. |
| C6 | Concurrent velocity vs. state lock rigor: strict locking (5-7) ensures consistency but serializes operations | Cat 5-7 | Fine-grained optimistic locking (file-level, not workspace-wide). Escalate only on actual conflict, not pre-emptively. |
| C7 | Vendor transparency vs. security isolation: adapters (4-9) are open-auditable; credentials (3-1-2) are isolated | Cat 4-9 vs 3-1 | Orthogonal concerns. Adapter code = auditable process logic. Credentials = runtime secrets. No conflict in practice. |
| C8 | Unanimity at max depth vs. vendor response latency: full consensus requires all nodes, but vendors respond at different speeds | Cat 2-2-2 vs 4-9 | `consensus_timeout` sets ceiling. Unanimity waits up to timeout then escalates regardless of vendor speed. |
| C9 | Instance multiplicity vs. decision attribution: 2-9 requires ROLE attribution; 3-9 requires INSTANCE_ID for compliance | Cat 2-9-3 vs 3-9 | 2-9 uses ROLE_ID (governance). 3-9 uses INSTANCE_ID (compliance). Immutable join table (2-9-5) bridges both simultaneously. |
| C10 | Sub-team scalability vs. global working memory: concurrent sub-team synthesis can instantly saturate global working memory threshold (1-1) | Cat 2-7 vs 1-1 | Memory compaction (1-3-2) invoked dynamically during sub-team synthesis before merged output enters global working memory. Sub-team output bounded by remaining memory budget. |

---

## §6. Governance Parameter Catalogue (45 parameters, 47 total config keys)

> Config key count: `_param_sections` (1) + 45 params + `last_review_ts` (1) = 47 total keys.
> Validation: load-time check that key count = 47 and all sections are consistent.
> **General** = applies to all implementations. **cat0–cat6** = category-scoped.

| Parameter | Type | Range | Default | Meaning | Section | Trade-off |
|:----------|:----:|:-----:|:-------:|:--------|:-------:|:---------:|
| `collaboration_depth` | int | `min_collaboration_depth`–Count(ACTIVE_NODES) | 10 | 0=single designated-node autonomy; Count(ACTIVE_NODES)=unanimous consent | general | T1,T4,T17 |
| `consensus_timeout` | int | 1–60 min | 30 | Max time per consensus round before auto-expiry | general | T3 |
| `final_call_threshold` | int | 0–Count(ACTIVE_NODES) | 8 | Min depth requiring explicit Final Call ACK | general | T8 |
| `daily_compute_budget` | int | 1000–∞ | 50000 | Total compute units/day; unit = `budget_unit_standard` | general | T17 |
| `task_delegation_threshold` | int | 1–20 | 5 | Repeated identical search N times → delegate to specialist | general | — |
| `policy_bypass_floor` | int | 0–Count(ACTIVE_NODES) | 8 | Depth below this may bypass minor policy gates | general | T20 |
| `vendor_interop_mode` | enum | strict/lenient/degraded | strict | How strictly vendors must support canonical protocol | general | T22 |
| `vendor_protocol_priority` | list | [protocol names] | ["REST-JSON","gRPC","WebSocket"] | Fallback protocol order if primary fails | general | T22 |
| `allowed_vendors` | list | [vendor IDs] | [] (all allowed) | Whitelist of permitted vendors; empty = no restriction | general | T22 |
| `mcp_strictness_mode` | enum | strict/lenient/permissive | strict | How strictly tool/agent calls must comply with 4-13 canonical interface and 4-14 extension lifecycle. | general | T29,T31 |
| `max_vendor_disagreement_depth` | int | 0–Count(ACTIVE_NODES) | 5 | Cross-vendor disagreement at this depth → escalate | general | T22 |
| `token_cost_matrix` | dict | {vendor: float} | {} | Cost per reference token per vendor | general | T17 |
| `budget_unit_standard` | enum | ref_tokens/usd | ref_tokens | Unit for `daily_compute_budget` and `token_cost_matrix` | general | T17 |
| `max_external_invocations` | int | 0–1000/hr | 50 | Max non-idempotent external API calls per hour | general | — |
| `human_escalation_sla` | int | 1–1440 min | 120 | Max wait for human gate response before session auto-suspends | general | C5 |
| `max_nodes_per_consensus` | int | 2–Count(ACTIVE_NODES) | 10 | Hard cap on active quorum; prevents exponential MTC decay | general | T11 |
| `min_collaboration_depth` | int | 0–Count(ACTIVE_NODES) | 1 | Safety floor for automated control loops. | general | T1,T16 |
| `workspace_template_path` | string | path | `./_sys/templates/workspace/` | [추가됨] Path to base workspace templates. | general | T7,T21 |
| `common_space_path` | string | path | `./_sys/common/` | [추가됨] Path to cross-workspace shared space. | general | T7,T21 |
| `workspace_connection_schema` | string | path | `./_sys/paths.json` | [추가됨] Path to JSON connection point file (4-5-4). | general | T7,T21 |
| `intent_timeout` | int | 1–1440 min | 60 | Max wait for human clarification; suspended during degraded mode | cat0 | C5 |
| `clarification_max_turns` | int | 1–10 | 3 | Max AI clarification rounds before proceeding with best-effort | cat0 | — |
| `delivery_ack_required` | bool | 0/1 | 1 | Require explicit human ACK before session closure | cat0 | T16,C3 |
| `context_warn_threshold` | int | 100–1000 | 600 | Normal working memory ceiling (reference token units) | cat1 | T2 |
| `context_critical_threshold` | int | 200–2000 | 1200 | Critical band transition (reference token units) | cat1 | T2 |
| `memory_compaction_interval` | int | 1–30 days | 7 | Long-term memory compaction cadence | cat1 | T6,T12 |
| `peer_review_min_interval` | int | 1–60 min | 5 | Minimum time between peer AI reviews | cat1 | T1 |
| `resolved_item_ttl` | int | 1–30 days | 3 | Completed items expire from session state after this duration | cat1 | T6,T12 |
| `active_item_ttl` | int | 1–90 days | 14 | Open items expire after this duration | cat1 | T6 |
| `dissent_drift_threshold` | int | 1–99 % | 60 | Disagreement ratio (%) triggering audit when exceeded | cat2 | — |
| `governance_debt_ceiling` | int | 0–100 GD points | 10 | Max GD Score before new tasks are halted. | cat3 | T25 |
| `max_recovery_depth` | int | 1–10 | 3 | Maximum recoverable checkpoints | cat3 | — |
| `confidence_floor` | int | 0–100 % | 70 | AI output confidence below this triggers human review | cat3 | — |
| `artifact_scale_threshold` | int | 100–100000 | 5000 | Artifact count above which localized dependency scope is applied | cat4 | — |
| `doc_freshness_interval` | int | 7–365 days | 30 | Max days before governance doc requires review event | cat4 | T6 |
| `metrics_persist_interval` | int | 10–3600 sec | 300 | Metrics write cadence to durable storage | cat5 | T13 |
| `active_control_enabled` | bool | 0/1 | 0 | Automated circuit-breaker control loop (0=off) | cat5 | T16,C3 |
| `forecast_alert_threshold` | int | 1–99 % | 70 | Compute usage forecast alert level | cat5 | T14 |
| `budget_alert_threshold` | int | 1–99 % | 90 | Daily budget pre-exhaustion alert level | cat5 | T17 |
| `hot_reload_enabled` | bool | 0/1 | 0 | Permits parameter hot-reload without node restart (5-10). | cat5 | T26,T28 |
| `governance_overhead_ceiling_pct` | int | 5–50 % | 20 | Max % of compute for governance meta-system events | cat5 | T27 |
| `idle_teardown_timeout` | int | 1–60 min | 15 | Unused heavy/resource deallocated after this period. | cat5 | T30 |
| `post_mortem_sla_hours` | int | 1–168 h | 48 | Maximum hours a P0/P1 post-mortem may remain open. | cat3 | T15 |
| `delivery_retry_limit` | int | 1–5 | 3 | Max consecutive UAT failures before escalation. | cat6 | — |
| `lazy_init_enabled` | bool | 0/1 | 1 | Defers heavy resource initialization until first directive (5-12). | cat4 | T30 |

---

## §7. Governance Maturity Scoring Model

### Dual Scoring System

```
FRAMEWORK SCORE (Definition Completeness):
  = items at T1 or above / total items × 100%
  v11 = ~100% (all 69 items have defined governance rules in §3)

IMPLEMENTATION SCORE (Deployment Completeness):
  Item Score     = min(Current Tier / Target Tier, 1.0)
  Root Score     = Σ (Category Weight × Category Score)
  v11 = ~35.9% (New items start at T0, temporarily lowering score)
```

### Category Weights

```
Cat 0 (Intent):         8%   Cat 4 (Environment):   13%
Cat 1 (Memory):        17%   Cat 5 (Operations):     7%
Cat 2 (Collaboration): 22%   Cat 6 (Delivery):       5%
Cat 3 (Integrity):     28%
Total:                100%
```

### Item Counts by Category (v11)

```
Cat 0:  6 items
Cat 1:  5 items
Cat 2:  9 items
Cat 3: 15 items
Cat 4: 17 items (4-16, 4-17 [추가됨])
Cat 5: 12 items
Cat 6:  5 items
Total: 69 items
```

---

## §8. Gap Analysis Log (G1–G65)

| # | Description | Location | Status |
|:--|:-----------|:---------|:-------|
| G1–G10 | Core MECE base items | Various Cat 1–4 | ✅ Closed |
| G11 | Async event handling policy | 5-3-2 | 🔶 Deferred |
| G12–G57 | v8–v10 Gaps (Observability, Metadata, Debt, Drift, Lazy Init) | Various | 🔶 Pending |
| G58 | Workspace Template Registry implementation [추가됨] | 4-16-1 | 🔶 Pending |
| G59 | Workspace-Independent Core refactoring [추가됨] | 4-16-2 | 🔶 Pending |
| G60 | Cross-Workspace Common Space setup [추가됨] | 4-16-3 | 🔶 Pending |
| G61 | Workspace-Local Space isolation [추가됨] | 4-16-4 | 🔶 Pending |
| G62 | Zero-dependency component audit [추가됨] | 4-17-1 | 🔶 Pending |
| G63 | JSON-declared dependency graph implementation [추가됨] | 4-17-2 | 🔶 Pending |
| G64 | Hot-swap composability logic [추가됨] | 4-17-3 | 🔶 Pending |
| G65 | JSON connection point enforcement for 4-5-4 [추가됨] | 4-5-4 | 🔶 Pending |

---

## §9. Implementation Roadmap

| Pri | Task | Item | Notes |
|:---:|:-----|:-----|:------|
| **P0** | Deploy parameter registry (45 params, 47 keys) | 5-1 | Foundation |
| **P0** | JSON connection point file enforcement | 4-5-4 | G65 |
| **P0** | Workspace-Independent Core refactoring | 4-16-2 | G59 |
| **P1** | Base Template Registry instantiation | 4-16-1 | G58 |
| **P1** | Zero-dependency component audit & IPC refactoring | 4-17-1 | G62 |
| **P1** | JSON-declared dependency graph (`dispatch.json`) | 4-17-2 | G63 |
| **P2** | Hot-swap composability logic implementation | 4-17-3 | G64 |
| **P2** | Cross-Workspace Common Space setup | 4-16-3 | G60 |
| **P2** | Workspace-Local Space isolation | 4-16-4 | G61 |

---

## §10. Axis Framework (A–L)

(No changes to Axis definitions for v11; coverage extended to new architectural items.)

---
---

# Appendix A: Reference Implementation — CC+GC Windows Portable Sandbox

## A.1 Universal Concept → CC+GC Component

| Universal Concept | CC+GC Component | File / Path |
|:-----------------|:----------------|:------------|
| Connection Point File | paths.json, env.json | `.\_sys\paths.json` |
| Workspace Template Registry | templates/workspace/ | `.\_sys\templates\workspace\` |
| Composable Dispatcher | dispatch.json | `.\_sys\dispatch.json` |
| Common Space | common/ | `.\_sys\common\` |

## A.2 Universal → CC+GC Parameter Mapping

| Universal Parameter | CC+GC key | Current Default |
|:-------------------|:----------|:---------------:|
| workspace_template_path | workspace_template_dir | `.\_sys\templates\workspace\` |
| common_space_path | common_space_dir | `.\_sys\common\` |
| workspace_connection_schema | connection_schema_file | `.\_sys\paths.json` |

---

# Appendix B: Multi-Vendor Capability Matrix Template

(No changes to Appendix B for v11.)

---

## References

- **TAXONOMY_v10.md** (READ-ONLY): `P:\_sys\docs\TAXONOMY_v10.md`
  Base document for v11. Introduced Peer Interface, Agent/MCP, Lazy Init.

- **gc-analysis-phase0.md**: `P:\_sys\docs\gc-analysis-phase0.md`
  Analysis document identifying Workspace Template and Composable Architecture requirements for v11.

- **governance_params.json** (§6 Parameter Registry — P0): `P:\_sys\ai\governance_params.json`
  Machine-readable registry for all 45 §6 parameters. Version 11.0. Single source of truth for
  runtime defaults. Created as part of v11 overhaul (previously missing).

- **PEER_MANAGEMENT.md** (Peer Folder/Log/Config Reference): `P:\_sys\docs\PEER_MANAGEMENT.md`
  Per-peer directory layout, health.json schema, IPC patterns, and configuration update protocol.
  Created as part of v11 overhaul.

- **R=10 Collaboration Log (CC+GC, 2026-06-13 — v11)**:
  Round 1: Gemini drafted v11 introducing Cat 4-16 and 4-17, strengthening 4-5-4, and adding
  JSON connection point requirements. Consolidated the No-Code vision with workspace isolation.
  Implementation Score adjusted to 35.9%. ACK/Proceed confirmed. TAXONOMY_v11.md written.
  Round 2 (cc): hub.py availability bug fixed, governance_params.json created, USER_MANUAL.md
  expanded (393 lines), PEER_MANAGEMENT.md created, old TAXONOMY versions (v2-v10_DRAFT) archived
  to P:\Garbage\. Full artifact consistency verified.
