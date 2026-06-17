# Engram Project Requirements — MECE Classification (Claude Draft R1)
_Source: P:\MemoryDump.md | Date: 2026-06-18 | Status: DRAFT — pending gc debate_

---

## A. Architecture & Structure

### A1. General-Specific Separation (Composable, No-Code)
- All configuration (env vars, paths, constants, option ranges) in JSON settings files; zero hardcoding
- Logic implemented as general/common layer; peer-specific or scenario-specific overrides in lower layer
- General-Specific connection points also expressed as JSON (interface contracts)
- No-code orientation: common logic in shared modules, individual cases driven by config
- All alias/mapping info in JSON (no implicit naming conventions in code)

### A2. Folder/File Structure
- Root → upper folders = General; lower folders = Specific
- Upper folders stay simple; anything that must live higher uses junctions pointing to SSOT
- Files/folders that can be grouped (≥2 related items) move into a category subfolder
- Each folder layer is independently extensible horizontally (new peers, new workspaces)
- Each folder only accesses its own subtree (encapsulation)
- Volatile/binary files (reinstallable via script) separated from user-managed config/template files
- User-managed config consolidated under one root (minimize scattered config)
- External path references managed via path dictionary file (key→path map) + junction; enables structural refactor without code change
- Path dictionary integrity verified by a dedicated check script

### A3. Portability
- Entire environment (Python, Node.js, Git, all AI CLIs, tools) in single portable folder
- No permanent host installation; zero registry dependency (register/unregister scripts handle host integration)
- Drive letter abstracted via BASE_DIR / SYS_DIR env vars; no hardcoded drive letters anywhere
- SUBST or junction used for drive-letter-agnostic access

### A4. Lifecycle Scripts
- INSTALL.bat: bootstrap runtimes, AI CLIs, tools from clean checkout
- CLEANUP.bat: remove all bootstrapped content (env, Node, all AI CLIs, root .peer dirs)
- REGISTER.bat: host integration (SUBST, context menu, PATH)
- UNREGISTER.bat: remove host integration
- START.bat / dispatch.bat / hub.py: runtime entry points
- ctx-save / ctx-end: session checkpoint and close
- bat files ≤5 lines; all logic in Python
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
- Peer can propose, but proposal is only final after unanimous ACK from all active peers

### B3. Health Monitoring
- Before every task: check all active peer health (context %, token limit, session state)
- If any peer not GREEN: pause, notify user, resolve before proceeding
- Heartbeat/lease mechanism: periodic lightweight check; lease expiry kills unresponsive peer session
- Health schema peer-agnostic (general schema; per-peer overrides in specific layer)
- Health state (GREEN/YELLOW/RED) and failure reason in structured JSON

### B4. Minimum Permission Model
- All master/admin permissions revoked from all peers by default
- Each peer granted only minimum permissions needed for its role
- Permission set cross-checked and verified by another peer
- Any permission change requires consensus and is documented

### B5. Error & Knowledge Propagation
- Any error a peer encounters → logged → root cause analysis (5-Whys) → fix → propagated to all peers
- Same mistake must never recur in any peer after propagation
- Propagation method: directive file update (TTL-bound) + source/doc update if structural fix needed
- User feedback (any size) captured → proposal → consensus → directive or source update
- Feedback processing procedure itself is documented and versioned

### B6. Model-Level Routing
- Each peer can use multiple underlying models (e.g., Haiku for lightweight tasks, Opus for deep analysis)
- Model selection criteria: task complexity, token cost, context window, health state
- Available models per CLI (types, specs, strengths/weaknesses) documented in peer profile
- Coordinator peer model also selectable by consensus to maximize synergy

---

## C. Memory & Learning System (Brain-Inspired)

### C1. Memory Architecture
- Short-term memory: session context (in-flight, volatile)
- Long-term memory: lessons, directives, knowledge base (persistent, versioned)
- Episodic memory analogy: session archive (handoff docs, ctx-end output)
- Semantic memory analogy: docs-v2 (structured knowledge, SSOT)

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
- Periodic cleanup routine (remove stale state, compact logs, validate junctions)
- Self-reflection check: docs-v2 ↔ source ↔ config consistency scan
- Improvement proposals auto-generated from lessons and user feedback patterns
- System can propose its own structural improvements for human approval

---

## D. Workspace Management

### D1. Common Workspace
- Resources needed across ALL workspaces stored in _sys/ai/common/ (agents, skills, MCP catalog, tool-registry)
- Shared via junction from each workspace

### D2. Workspace Base Template
- First-time workspace creation uses base template in _sys/templates/workspace/
- Template includes skeleton structure, initial config stubs, README

### D3. Per-Workspace Resources
- Workspace-specific resources in workspace/<name>/ subdirectory
- Workspace-specific agents/skills/config in workspace/<name>/specific/

### D4. Junction & Path Management
- managed-links.json: SSOT for all junctions (path → target mapping)
- virtualizer.py: apply/verify/status for managed junctions
- External path references use path dictionary (not hardcoded); structural refactor = dictionary update only

---

## E. Quality & Process

### E1. Operating Principles (Applied Recursively)
- MECE: every classification is mutually exclusive and collectively exhaustive; consolidate overlaps
- 5-Whys: every error or design gap traced to root cause; fix at root, not symptom
- Closed feedback loop: every process output feeds back into process improvement
- These three principles applied recursively until no further improvement found

### E2. TDD
- Tests written before implementation (unit → integration → scenario)
- Scenario tests cover: Unicode paths, special chars, reboot, multi-workspace, peer health degradation
- Tests run in clean environment (WSB or equivalent sandbox)
- Test results feed back into lesson system

### E3. Audit Framework
- User-specified audit perspectives embedded in docs as checklist sections
- Audit prompts phrased as: "From <X> perspective, check…" (e.g., portability perspective, token-zero perspective)
- Audit checklist covers: MECE completeness, feedback loop closure, 5-Whys resolution, trade-off clarity, examples sufficiency

### E4. Zero-Token Optimization
- All inter-peer IPC queries in English (Korean costs 2-3x tokens)
- Lazy loading of context (fill only what's needed for the task)
- Health checks use minimum-payload queries
- Slim protocols where possible, but not at the cost of correctness (trade-off parameterized)
- COLLAB_RATE parameter controls collaboration depth vs. token cost

### E5. Error Visibility
- Any error/failure → user notified immediately with full stack trace
- Peer detects its own limit (context %, token remaining) and proactively reports before hitting wall
- Output that exceeds console capacity → file output (never truncated in console)
- Context saturation → auto-generate handoff doc → request new session

### E6. Debate Protocol
- Trigger: ambiguity, ≥2 options, design decision, protocol change
- Goal: complete requirement elucidation; unambiguous design
- Rules: unlimited turns/time/message size; open questions only; no unilateral conclusion
- Termination: unanimous ACK from all active peers
- Output: documented decision + rationale → committed to docs-v2 or directive

### E7. Plan-Do-See Cycle
- PLAN: scan resources, estimate token usage, chunk large tasks, get user approval on plan
- DO: execute chunk; report delta/changes discovered mid-execution
- SEE: checkpoint after each chunk; cross-verify output; loop back to PLAN if gaps found
- EXCEPTION: on failure → [HALT + reason] → propose workaround → human approval

---

## F. Infrastructure

### F1. Remote Access (SSH + RDP)
- OpenSSH server setup on target PC (PowerShell automation script)
- Port forwarding via router (external port → internal SSH port)
- SSH tunnel for RDP (not exposing RDP directly externally)
- DDNS for dynamic IP (ggcc9.tplinkdns.com pattern)
- Tunnel management: start, background kill, port verification

### F2. Sandbox & Isolation
- Primary: WSB (Windows Sandbox) for clean test runs
- Alternative lighter sandboxes desirable (WSB heavy/inconvenient)
- Codex sandbox modes: danger-full-access + ask-for-approval (recommended), full bypass (last resort)
- AI CLI processes isolated in portable env; root .peer dirs are junctions, not permanent

### F3. Portable CLI Setup
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

---

## _exceptions (Not MECE-classifiable as Engram requirements)

| Item | Source | Disposition |
|------|--------|-------------|
| Legal document citation rules (원문 유지 법칙) | MemoryDump §원문 유지 법칙 | Separate legal tool/skill — not Engram requirement |
| RAG transcription XML system prompt | MemoryDump §md파일로 변경 | Separate Gemini Gem / tool — not Engram requirement |
| Kim Yong-hun fraud case notes | MemoryDump §김용훈 관련 | Personal legal matter — not in any doc |
| SSH credentials / WAN admin info | MemoryDump lines 1-15 | Personal infrastructure — gitignored, never committed |
| SK AX resort booking info | MemoryDump §휴양소 | Personal — not in any doc |
| YouTube / motivational video links | Various sections | Personal — not in any doc |

---

## GAPS — In MemoryDump but not yet in docs-v2

1. **Model-level routing** (B6): docs-v2 has routing.md but it covers peer-level routing, not model-level within a peer
2. **Self-care cycle** (C4): self-evolution.md exists but cleanup routine / reflection cycle not formalized
3. **Audit framework** (E3): no dedicated audit checklist doc in docs-v2
4. **Remote access** (F1): SSH/RDP setup guide not in docs-v2 (infrastructure ops doc missing)
5. **Trade-off parameter registry** (H): COLLAB_RATE documented but EFFORT, SLIM, SANDBOX not formalized
6. **Plan-Do-See** (E7): partially in general/protocol.md but not as a standalone executable procedure
7. **Coordinator handoff without console change** (B1): routing.md covers failover but not graceful coordinator switch

## DEBATE POINTS for cc+gc consensus

1. Should SSH/RDP setup (F1) be in docs-v2/ops/ or in a separate infrastructure runbook outside docs-v2?
2. Should the "legal citation rules" and "RAG transcription prompt" be extracted as standalone skill files in _sys/ai/common/skills/?
3. Model-level routing (B6): implement at hub.py level or per-peer config level?
4. Self-care cycle frequency: time-based (cron) vs. event-based (on session end, on error threshold)?
5. Audit checklist: separate file (docs-v2/ops/audit-checklist.md) or embedded in each general/*.md?
