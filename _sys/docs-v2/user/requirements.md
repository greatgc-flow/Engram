# Engram Project Requirements — MECE Classification (Final)
> Source: P:\MemoryDump.md  
> Authors: cc (Claude) + gc (Gemini) — Debate Round 1, unanimous consensus  
> Date: 2026-06-18  
> Status: FINAL — all items resolved

---

## A. Architecture & Structure

### A1. General-Specific Separation (Composable, No-Code)
- All configuration (env vars, paths, constants, option ranges) in JSON settings files; zero hardcoding
- Logic implemented as general/common layer; peer-specific or scenario-specific overrides in lower layer
- General-Specific connection points expressed as JSON (interface contracts)
- No-code orientation: common logic in shared modules, individual cases driven by config
- All alias/mapping info in JSON (no implicit naming conventions in code)
- Core logic in composable JSON; source code is a generic execution harness
- Each folder level only accesses its immediate sub-folders (encapsulation: downward transparency, upward opacity)

### A2. Folder/File Structure
- Root → upper folders = General; lower folders = Specific (MECE hierarchy)
- Upper folders stay simple; anything that must live higher uses junctions pointing to SSOT
- Files/folders that can be grouped (≥2 related items) move into a category subfolder
- Each folder layer is independently extensible horizontally (new peers, new workspaces)
- Volatile/binary files (reinstallable via script) separated from user-managed config/template files
- User-managed config consolidated under one root (minimize scattered config)
- External path references managed via path dictionary file (key→path map) + junction
- Path dictionary integrity verified by a dedicated check script
- Data tiering: volatile/binary vs. persistent config/templates vs. read-only archive

### A3. Portability
- Entire environment (Python, Node.js, Git, all AI CLIs, tools) in single portable folder
- No permanent host installation; zero registry dependency (REGISTER.bat / UNREGISTER.bat handle host integration)
- Drive letter abstracted via BASE_DIR / SYS_DIR env vars; no hardcoded drive letters anywhere
- SUBST or junction used for drive-letter-agnostic access (P: → actual drive path)

### A4. Lifecycle Scripts
- INSTALL.bat: bootstrap runtimes, AI CLIs, tools from clean checkout
- CLEANUP.bat: remove all bootstrapped content (env, Node, all AI CLIs, root .peer dirs)
- REGISTER.bat: host integration (SUBST, context menu, PATH)
- UNREGISTER.bat: remove host integration
- START.bat / dispatcher.py / hub.py: runtime entry points
- ctx-save / ctx-end: session checkpoint and close
- .bat files ≤5 lines; all logic in Python
- All AI CLI installs go into _sys/; root .claude/.gemini/.chatgpt dirs → junctions → _sys/peer/config/

### A5. Lazy Initialization
- Every module/feature initializes only when first needed
- Peer health check runs before any substantive work begins
- AI CLI features (MCP, agents, skills) loaded on demand

---

## B. AI Peer Collaboration System

### B1. Peer Equality & Coordinator
- All peers (cc, gc, cx, ag + future peers) are absolutely equal in authority
- Any peer can be human-interface coordinator; coordinator role transferable by consensus
- Coordinator switch is transparent to user (auto-forwarding to new coordinator)
- Peer-specific strengths can receive weighted vote on their domain (by consensus, not default)
- Peer definitions (id, capabilities, model, health schema) in peers.json; new peers added via config only

### B2. Unanimous Consensus
- All decisions require unanimous agreement across active peers
- No unilateral action on any system-layer change; no arbitrary compromise
- Debate is unlimited (no turn limit, no time limit, no message size limit)
- Debate uses open questions (no leading questions); biased framing prohibited
- Proposal is only final after unanimous ACK from all active peers

### B3. Health Monitoring
- Before every task: check all active peer health (context %, token limit, session state)
- If any peer not GREEN: pause, notify user, resolve before proceeding
- Heartbeat/lease mechanism: periodic lightweight check; lease expiry kills unresponsive peer session
- Health schema peer-agnostic (general schema; per-peer overrides in specific layer)
- Health state (GREEN/YELLOW/RED) and failure reason in structured JSON

### B4. Minimum Permission Model
- All master/admin permissions revoked from all peers by default
- Each peer granted only minimum permissions needed for its role (scope-limited, not approval-limited)
- "Minimum permissions" = minimum SCOPE of allowed actions; NOT minimum approval count
- Codex can execute autonomously WITHIN its minimum permission scope
- Actions exceeding defined scope → stop immediately + ask user
- Permission set cross-checked and verified by another peer; any change requires consensus

### B5. Error & Knowledge Propagation
- Any error a peer encounters → logged → root cause analysis (5-Whys) → fix → propagated to all peers
- Same mistake must never recur in any peer after propagation
- Propagation method: directive file update (TTL-bound) + source/doc update if structural fix needed
- User feedback (any size) captured → proposal → consensus → directive or source update
- Feedback processing procedure itself is documented and versioned

### B6. Model-Level Routing
- Each peer can use multiple underlying models (e.g., Haiku for lightweight tasks, Opus for deep analysis)
- Model selection criteria: task complexity, token cost, context window, health state
- Implementation: per-peer config in peers.json (hub.py stays thin — generic dispatcher only)
- Selection matrix: Standard / Effort / DeepThink modes with documented trigger criteria per peer profile

### B7. Recursive Debate Protocol
- Trigger: ambiguity, ≥2 options, design decision, protocol change
- Rules: unlimited turns/time/message size; open questions only; no unilateral conclusion
- Termination: unanimous ACK from all active peers
- Output: documented decision + rationale → committed to docs-v2 or directive

### B8. Zero-Token IPC Protocol
- All inter-peer IPC queries in English (Korean costs 2-3x tokens)
- Coordinator does NOT relay full conversation; writes shared state to IPC file; target peer reads directly
- Coordinator sends only a 1-line signal/ACK — no middle-man token cost
- Precision echo-back (복명복창) after receiving instructions: lossless transcription, no information loss
- Lazy loading of context (fill only what's needed for the task)

---

## C. Memory & Learning System (Brain-Inspired)

### C1. Four-Layer Brain Anatomy Model
- **Amygdala** → `check_risk.py` / safety module: immediate risk/safety response, error detection, security threat handler, contradiction resolver
- **Prefrontal Cortex** → `hub.py` / coordinator: orchestration, high-level planning, Plan-Do-See cycle
- **Hippocampus** → `_archive/` + `handoff.md`: short-term (session context) + long-term (archive/knowledge base) memory
- **Neocortex** → `docs-v2/`: semantic knowledge store — structured, versioned, normative SSOT

### C2. Runtime Directives
- Behavioral corrections expressed as TTL-bound JSONL entries
- Auto-propagated to all peers on session start
- Expires after TTL; structural fixes move to source/doc

### C3. Lesson Propagation Cycle
- Trigger: peer error, user feedback, or cross-review finding
- Process: observe → classify → root-cause (5-Whys) → propose fix → consensus → apply → verify → record
- Record: lesson-taxonomy.json + active-lessons.jsonl
- Verification: saturation_scan.py periodically checks for stale path literals and invariant completeness

### C4. Self-Care & Self-Evolution
- Cycle: event-based (triggers: session-end, consecutive_failures > 5, every N commits)
- Routine: cleanup stale state, compact logs, validate junctions, docs-v2 ↔ source ↔ config consistency scan
- Improvement proposals auto-generated from lessons and user feedback patterns
- System can propose its own structural improvements for human approval (never self-apply)

---

## D. Workspace Management

### D1. Common Workspace
- Resources needed across ALL workspaces stored in _sys/ai/common/ (agents, skills, MCP catalog, tool-registry)
- Shared via junction from each workspace

### D2. Workspace Base Template
- First-time workspace creation uses base template in _sys/templates/workspace/
- Template includes skeleton structure, initial config stubs, README

### D3. Per-Workspace Resources
- Workspace-specific resources in workspace/<name>/specific/ subdirectory
- Local _state for workspace-unique assets (excluded from template)

### D4. Junction & Path Management
- managed-links.json: SSOT for all junctions (path → target mapping)
- virtualizer.py: apply/verify/status for managed junctions
- External path references use path dictionary (not hardcoded); structural refactor = dictionary update only

---

## E. Quality & Process

### E1. Operating Principles (Applied Recursively)
- **MECE**: every classification is mutually exclusive and collectively exhaustive; consolidate overlaps
- **5-Whys**: every error or design gap traced to root cause; fix at root, not symptom
- **Closed Feedback Loop**: every process output feeds back into process improvement
- Applied recursively until no further improvement found

### E2. TDD
- Tests written before implementation (unit → integration → scenario)
- Scenario tests cover: Unicode paths, special chars, reboot, multi-workspace, peer health degradation
- Tests run in clean environment (WSB or equivalent sandbox)
- Test results feed back into lesson system

### E3. Audit Framework
- Location: `docs-v2/ops/audit-checklist.md` — single standalone runnable SSOT
- User-specified audit perspectives as checklist sections
- Phrased as: "From <X> perspective, check…" (portability, token-zero, MECE, etc.)
- Covers: MECE completeness, feedback loop closure, 5-Whys resolution, trade-off clarity, examples sufficiency

### E4. Plan-Do-See Cycle
- **PLAN**: scan resources, estimate token usage, chunk large tasks, get user approval on plan
- **DO**: execute chunk; report delta/changes discovered mid-execution
- **SEE**: checkpoint after each chunk; cross-verify output; loop back to PLAN if gaps found
- **EXCEPTION**: on failure → [HALT + reason] → propose workaround → human approval

### E5. Error Visibility
- Any error/failure → user notified immediately with full stack trace
- Peer detects its own limit (context %, token remaining) and proactively reports before hitting wall
- Output exceeding console capacity → file output (never truncated in console)
- Context saturation → auto-generate handoff doc → request new session

---

## F. Sandbox & Isolation

### F1. Sandbox Options
- Primary: WSB (Windows Sandbox) for clean test runs; lighter alternatives desirable
- Codex sandbox modes: danger-full-access + ask-for-approval (recommended), full bypass (last resort)
- AI CLI processes isolated in portable env; root .peer dirs are junctions, not permanent

### F2. Portable CLI Setup
- All AI CLIs (claude, gemini, codex, antigravity) installed in _sys/env/ (portable)
- Cleanup removes all CLI installs and junction dirs
- MCP and other extensions added post-install; extensible design

---

## G. Documentation Standards

### G1. docs-v2 as SSOT
- All normative content lives in docs-v2; docs/history/ is read-only archive
- Every normative claim cites a capsule (Decision Capsule) round ID
- sync_docs.py applies approved capsules to docs-v2 automatically

### G2. Traceability
- Every component (doc, source, config) has bidirectional links to related components
- Traceable from any peer in any session (zero-context → single doc sufficient)
- Document independence: each doc self-contained for new-session readability

### G3. README
- Attractive, hip, GitHub-star-worthy
- Emphasizes: autonomous AI collaboration, self-evolution, zero-trust peer equality
- Includes Hello World example (3-AI collaboration demo, runnable immediately)
- Clear structure: what it is → why it's different → quick start → architecture → contribute

---

## H. Trade-Off Parameters

| Parameter | Description | Range | Trade-off |
|-----------|-------------|-------|-----------|
| COLLAB_RATE | Collaboration depth | 0–10 | Token cost ↑ vs. consensus quality ↑ |
| EFFORT | Model effort level | low/medium/high | Speed ↑ vs. depth ↓ |
| SLIM | Protocol message size | true/false | Token ↓ vs. comprehension quality ↓ |
| SANDBOX | Isolation level | off/partial/full | Speed ↑ vs. safety ↓ |
| LEADER_REELECT_PER_TASK | Leader election frequency | bool | Optimal routing ↑ vs. overhead ↑ |

---

## _exceptions (Personal items — outside Engram scope)

| Item | Source | Disposition |
|------|--------|-------------|
| SSH/RDP Setup Guide | MemoryDump §remote access | Personal home network runbook — OUTSIDE docs-v2, gitignored |
| Legal document citation rules (원문 유지 법칙) | MemoryDump §원문 유지 법칙 | Personal legal tool — NOT in Engram skills registry |
| RAG transcription XML system prompt | MemoryDump §md파일로 변경 | Personal Gemini Gem — NOT in Engram repo |
| Kim Yong-hun fraud case notes | MemoryDump §김용훈 관련 | Personal legal matter — not in any doc |
| SSH credentials / WAN admin info | MemoryDump lines 1-15 | Personal infrastructure — gitignored, NEVER committed |
| SK AX resort booking info | MemoryDump §휴양소 | Personal — not in any doc |
| YouTube / motivational video links | Various sections | Personal — not in any doc |

---

## GAPS — Not yet in docs-v2 (to be addressed in Step 2)

| # | Gap | Category | Target doc |
|---|-----|----------|------------|
| 1 | Model-level routing matrix (Standard/Effort/DeepThink criteria) | B6 | docs-v2/general/routing.md |
| 2 | Self-care cycle event triggers + procedure | C4 | docs-v2/general/self-evolution.md |
| 3 | Audit checklist (standalone) | E3 | docs-v2/ops/audit-checklist.md |
| 4 | Trade-off parameter registry (EFFORT, SLIM, SANDBOX, LEADER_REELECT_PER_TASK) | H | docs-v2/general/tradeoffs.md |
| 5 | Plan-Do-See as standalone executable procedure | E4 | docs-v2/general/protocol.md |
| 6 | Coordinator handoff (graceful switch, not just failover) | B1 | docs-v2/general/routing.md |
| 7 | Brain anatomy mapping (4-layer: Amygdala/PFC/Hippocampus/Neocortex) | C1 | docs-v2/general/architecture.md |
| 8 | Zero-Token IPC Protocol (echo-back + coordinator signal pattern) | B8 | docs-v2/general/protocol.md |
| 9 | LEADER_REELECT_PER_TASK flag in protocol.json schema | H | _sys/ai/protocol.json |
| 10 | /Garbage governance policy (manual, user-controlled, no auto-delete) | — | docs-v2/ops/governance.md |
