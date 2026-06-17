# Project Engram: MECE Requirement Analysis (Round 1)
> Source: `P:\MemoryDump.md` audit
> Analyst: Gemini Node (gc)
> Date: 2026-06-18

## 1. Requirement Classification (MECE)

### A. Architecture & Structure
*   **General-Specific Separation**: Composable architecture where general logic is separated from specific peer/task implementations via JSON configuration.
*   **MECE Directory Hierarchy**: Beautiful, extensible folder structure starting from Root. Vertical layers follow General (Parent) > Specific (Child) flow.
*   **Config-First (Zero-Hardcode)**: All variables, paths, limits, and environmental settings must live in JSON files. Logic should query JSON rather than hardcoding strings.
*   **Portability (Zero-Host Dependency)**: Entire environment must run from USB/Cloud without host OS modifications (beyond registration).
*   **No-Code Orientation**: Core logic resides in composable JSON configurations; source code serves as a generic execution engine (Harness).
*   **SSOT via Junctions**: Use directory junctions to map root folders (e.g., `.claude`) to internal system paths (`_sys/peers/...`), ensuring a single source of truth.
*   **Encapsulation**: Each folder level should only access its immediate sub-folders (downward transparency, upward opacity).
*   **Data Tiering**: Separate volatile/binary data (reinstallable) from user configurations and templates (persistent).

### B. AI Peer Collaboration System
*   **Multi-Peer Equality**: All nodes (cc, gc, cx, ag) and virtualized roles are equal. No single node monopolizes coordination.
*   **Coordination & Leader Election**: Any peer can become the active coordinator. Criteria include health, context availability, and user preference.
*   **Unanimous Consensus (Collab_RATE=10)**: High-risk decisions require 100% agreement between participating peers. No compromises on logic or system integrity.
*   **Health & Lease Monitoring**: Real-time monitoring of peer status (Green/Yellow/Red), context window saturation, and lease (heartbeat) validity.
*   **Minimum Permission Model**: Withdrawal of "Master" permissions; peers operate with task-specific minimum rights (Read/Write/Exec) to ensure safety.
*   **Error Propagation (Synchronized Learning)**: A mistake or feedback encountered by one peer must be immediately propagated to all peers to prevent recurrence.
*   **Model-Level Routing**: Dynamic selection of specific models (e.g., Effort, DeepThink) based on task complexity, cost (token-zero), and capability.
*   **Recursive Debate Protocol**: Exhaustive, multi-turn debate loops for requirement clarification and design validation.

### C. Memory & Learning System (Brain-Inspired)
*   **Hippocampal Memory Structure**: Implementation of short-term (session) and long-term (archive/knowledge) memory layers.
*   **Prefrontal Cortex (Orchestration)**: Logic for high-level decision making and planning (Plan-Do-See cycle).
*   **Amygdala (Risk/Safety)**: Immediate response to errors, security threats, or contradictory instructions.
*   **Self-Care / Self-Evolution**: Autonomous routine cleanup, reflection sessions, and policy updates without human intervention.
*   **User Feedback Lifecycle**: Transforming transient user feedback into permanent system directives or behavioral lessons.
*   **Runtime Directives (TTL)**: Behavioral corrections with Time-To-Live, allowing for temporary overrides or experimental logic.

### D. Workspace Management
*   **Common Workspace**: A shared pool for resources, scripts, and assets used across multiple project instances.
*   **Base Template**: "Zero-base" initialization template for new workspaces to ensure structural consistency.
*   **Specific Workspace Overrides**: Local `_state` or workspace-specific subdirectories for project-unique assets.
*   **Path Mapping Dictionary**: A centralized dictionary (key-path map) managing all internal and external path resolution.

### E. Quality & Process
*   **MECE + 5-Whys + Closed-Loop**: Core operating principles for problem-solving and documentation.
*   **TDD (Test-Driven Development)**: Mandatory test-first approach for all functional implementations.
*   **Audit Framework**: User-specified perspectives (lenses) applied to checkpoints during the execution phase.
*   **Zero-Token Optimization**: Minimizing context usage and token cost via English prompts, precise range-reads, and semantic compression.
*   **Error Visibility**: Explicit reporting of failures, stack traces, and environment inconsistencies to the user (no silent failures).
*   **Deterministic State Machine**: AI roles defined as precision data pipelines with lossless transcription goals.

### F. Lifecycle Scripts
*   **Bootstrap Tools**: `INSTALL`, `CLEANUP`, `REGISTER`, `UNREGISTER`.
*   **Context Control**: `ctx-save` (checkpointing) and `ctx-end` (session wrap-up).
*   **Execution Entrypoints**: `start.bat` as the gateway, `dispatcher.py` as the pipeline manager, and `hub.py` as the peer coordinator.
*   **Scripting Standards**: Batch files limited to 5 lines; complex logic strictly delegated to Python.

### G. Infrastructure
*   **Remote Accessibility**: Technical requirements for SSH tunneling and RDP GUI access in Windows environments.
*   **Sandbox Isolation**: Configurable sandbox levels (e.g., Codex sandbox flags) to protect the host while allowing necessary file operations.
*   **Portable Tooling**: Pre-bundled, portable versions of Node.js, Python, Git, and specific AI CLI tools.

### H. Documentation
*   **docs-v2 as SSOT**: Transition from legacy `docs/` to `docs-v2/` as the authoritative single source of truth.
*   **Traceability Map**: Bi-directional linking between documentation requirements, configuration files, and source code.
*   **Attractive README**: Showcase of AI collaboration capabilities with "Hello World" examples to attract GitHub community engagement.

### _exceptions (Items outside core MECE structure)
*   **Legal Document Citation Rules**: Specialized rules for citing supreme court precedents and statutes (separate skill, not part of Engram core).
*   **Prompt Conversion (XML to MD)**: Precision logic for converting system prompt XML structures into Markdown without information loss.
*   **External Reference Linking**: Handling of non-project URLs (e.g., YouTube motivational links) as part of a "Personal Wellbeing" layer rather than system engineering.

## 2. Gap Analysis

### GAPS (MemoryDump items missing from docs-v2)
- **Brain-inspired Anatomy**: The specific mapping of Amygdala/Prefrontal Cortex to system components is not fully codified in `docs-v2`.
- **Zero-Token Echo-back Protocol**: The requirement for precision "복명복창" (echo-back) and deterministic state machine roles is not fully detailed.
- **Model-Level Selection Matrix**: Detailed criteria for when to use "DeepThink" vs "Effort" vs "Standard" modes.
- **Self-Evolution Cleanup Routine**: Autonomous cleanup logic (moving files to `/Garbage`) is mentioned but not architected in detail.

### DUPLICATES (Overlap with existing docs-v2)
- **Multi-peer Collaboration**: `PROTOCOL.md` and `docs-v2` already cover 80% of the collaboration logic.
- **Folder Structure**: The MECE layout requirements are largely consistent with the current `_sys` structure.
- **Lifecycle Commands**: `INSTALL`/`REGISTER` logic is already well-documented.

### DEBATE POINTS (Ambiguities needing consensus)
- **Leader Election Frequency**: Should the leader be elected once per session or per task?
- **Sandbox Level "danger-full-access"**: Balancing safety with the requirement for "no approval prompts" during complex tasks.
- **/Garbage Folder Governance**: Should items in `/Garbage` be permanently deleted by a routine, or is it a manual user-controlled pit?
- **Coordinate forwarding cost**: If a coordinator forwards a user query to another peer, how do we minimize the "middle-man" token cost?

## 3. Contradictions & Clarifications
- **Contradiction**: "Withdraw all master permissions" vs "Automatic execution without human approval (Codex exec)". Need to define the boundary between "Restricted Scope" and "Autonomous Execution."
- **Clarification**: "Portable Root P:" is used in MemoryDump, but local environment uses "D:". Need to ensure all path mapping logic handles the `subst` abstraction seamlessly.