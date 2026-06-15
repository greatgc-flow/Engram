# Porta-Flow: Universal Multi-Peer Collaboration Manual (v4.1)

> **Porta-Flow** is a 100% portable, multi-AI collaboration environment for Windows. It allows humans and multiple AI models (Claude, Gemini, Codex, AntiGravity, etc.) to operate as equal nodes within a unified, self-contained workspace. This manual is the definitive guide for setting up, using, and extending the system. It is designed to be a single source of truth for both human directors and AI peer nodes.

---

## 1. Overview & Philosophy (시스템 개요 및 철학)

Porta-Flow handles AI-to-AI and Human-to-AI interaction through a **Decentralized P2P Hub model**. No single AI "rules" the session; instead, they operate as equal nodes in a shared "Room." This architecture is designed to foster a collaborative environment where specialized models can contribute their unique strengths to a project.

### 1-1. Philosophy: Peer-to-Peer (P2P) Equality
The core philosophy of Porta-Flow is that AI models are more effective when they can critique, verify, and assist each other as peers, rather than acting as isolated silos. By establishing a shared state and a unanimous consensus protocol, Porta-Flow creates a "team" environment where the human acts as the high-level director (Tier 0) while the AI peers handle the technical execution.

**The Four Pillars of Porta-Flow:**
1.  **Equality**: All nodes have a 1/N vote in the consensus process. No node can override another without reaching the human gate. This prevents any single model's biases from dominating the architecture and ensures that every technical decision is cross-verified by at least one other peer.
2.  **Portability**: The entire environment—including Python, Node.js, Git, and all LLM configuration—lives in a single folder. You can move this folder to a USB drive or cloud storage and continue your work on any Windows machine. This "Sandbox" approach ensures that your development environment is consistent across all hosts and requires zero permanent installation on the host OS, making it ideal for mobile developers or secure environments.
3.  **Auditability**: Every P2P message, system change, and tool invocation is logged in a transparent, line-delimited `log.jsonl` file. This ensures a complete trail of "who did what and why." This is essential for debugging complex multi-agent interactions and for security auditing. The log can be ingested by analysis tools to generate performance reports or to identify bottlenecks in the collaboration loop.
4.  **Consensus**: High-risk changes to the system layer (`_sys/`) or constitutional documents (`PROTOCOL.md`, `CONVENTION.md`) require unanimous agreement from all registered peers. This "Constitutional Safety" ensures that the core rules of the system cannot be changed by a single rogue or confused node, protecting the long-term stability and integrity of the workspace.

### 1-2. ASCII Architecture Diagram

```text
                                [ HUMAN (Tier 0 - Final Arbiter) ]
                                              |
                                              | (Gate/Approval/Consensus)
                                              v
        +-----------------------------------------------------------------------+
        |                       HUB.PY (Universal Message Broker)               |
        |          (Manages mailbox.json, consensus.json, session lifecycle)     |
        +---+-----------------+-----------------+-----------------+-------------+
            |                 |                 |                 |
     +------v-----+    +------v-----+    +------v-----+    +------v-----+
     |     CC     |    |     GC     |    |     CX     |    |     AG     |
     | Claude Code|    | Gemini CLI |    | Codex Exec |    | AntiGravity|
     | (Architect) |    | (Research) |    | (Coding)   |    | (Shell/PTY)|
     +------+-----+    +-----+------+    +-----+------+    +-----+------+
            |                 |                 |                 |
            +-----------------+-----------------+-----------------+
                                      |
                   +------------------v------------------+
                   |           .ai/ SHARED STATE         |
                   |   (handoff.md, state.json, log.jsonl)|
                   |   (The Single Source of Truth)      |
                   +-------------------------------------+
```

### 1-3. Core Components Deep Dive

#### hub.py: The System Heart
The central Python-based hub provides a unified API for all nodes. It uses the **Facade Pattern** to hide the complexity of file-based IPC.
- **Message Routing**: Ensures that `send` and `ask` commands are correctly delivered to the intended recipient's mailbox. It handles the parsing of sender and receiver IDs and manages the JSON-based message envelope, including timestamps and unique message IDs.
- **Session Control**: Manages the transitions between Room states. It creates the unique Room UUID, sets the initial mission statement, and handles the archival process when a session ends, ensuring that all temporary state is safely stored in the `_archive/` folder.
- **Consensus Orchestration**: Tracks the progress of voting rounds. It stores votes in individual JSON files within the `.ai/consensus/` directory, calculates whether a quorum has been reached, and enforces the "Unanimous for R:10" rule for critical system modifications.
- **Health Monitoring**: Periodically checks the health of each peer node. It monitors the size of the `mailbox.json` file and the age of the last status update to detect if a node has become "Stale" or if there is a communication bottleneck.
- **File Locking**: Uses a sophisticated file-locking mechanism to prevent race conditions. When multiple nodes attempt to access the shared mailbox or state files simultaneously, `hub.py` ensures that only one write operation happens at a time, preserving data integrity and preventing corruption.

#### .ai/: The Project Brain
This folder contains all ephemeral and persistent session state. It is the "source of truth" for the current intelligence state of the project.
- `mailbox.json`: A shared JSON queue. It acts as the "post office" for all P2P messages. Each message has a unique ID, thread ID, timestamp, and read/unread status.
- `state.json`: The master record for the current Room. It includes the Room ID, the mission statement, the current phase (e.g., Research, Strategy, Execution), and the list of active members.
- `log.jsonl`: A permanent, append-only execution log. It records every interaction in a machine-readable format. Each line is a standalone JSON object, making it easy to parse with tools like `jq` or to ingest into a database for long-term analysis.
- `consensus/`: A directory containing JSON files for every consensus round. This provides a transparent history of all major architectural decisions, documenting who voted for what and when, along with any dissent comments or justifications.
- `sessions/room-{uuid}/handoff.md`: The shared memory blackboard. This is where peers write their progress, pending issues, and key decisions. It is designed to be human-readable while still being structured enough for AI nodes to parse reliably, ensuring continuity across different physical sessions.

---

## 2. Prerequisites and Installation (요구 사양 및 설치 가이드)

Porta-Flow is designed to be truly "Zero-Install" on the host machine, requiring only a few basic Windows features to be enabled. It leaves no trace in the registry or system environment variables outside of the virtual drive mapping.

### 2-1. Prerequisites
- **Operating System**: Windows 10 or 11. Windows 11 is preferred for its improved Terminal support and support for the latest PowerShell features.
- **Shell**: PowerShell 7+ is highly recommended for its advanced scripting capabilities and better UTF-8 support, though standard PowerShell 5.1 and CMD are also supported for most basic operations.
- **Disk Space**: At least 2.5GB of free space. This includes the space for the portable Python distribution, Node.js, Git, FFmpeg, and the various LLM CLI tools used by the peers.
- **Permissions**: You must have permission to run batch files and PowerShell scripts. Administrative privileges are only required for the initial `register.bat` to add the context menu and the virtual drive mapping.

### 2-2. Step-by-Step Installation

#### Phase 1: Folder Preparation
1.  **Extract**: Extract the Porta-Flow archive to your desired location (e.g., `C:\PortaFlow` or `E:\PortaFlow` on a USB drive).
2.  **Path Hygiene**: Ensure the path contains no spaces or special characters. Some legacy tools used by the portable environment may not handle spaces correctly, so a clean path like `C:\PortaFlow` is safest.

#### Phase 2: Runtime Initialization (`INSTALL.bat`)
1.  **Run `INSTALL.bat`**: This script downloads all necessary portable software and tools.
2.  **What it does**:
    - It reads `runtimes.json` to identify the correct versions and URLs of all required software.
    - It downloads a portable Python "embeddable" distribution and installs `pip` for package management.
    - It creates a dedicated virtual environment (`_sys/env/venv`) to isolate all Porta-Flow Python dependencies from your host machine.
    - It downloads portable versions of Node.js, Git, and FFmpeg.
    - It installs essential CLI utilities: `ripgrep` (fast searching), `fd` (fast finding), `jq` (JSON processing), `bat` (syntax highlighting), and `delta` (pretty diffs).

#### Phase 3: System Registration (`register.bat`)
1.  **Run `register.bat`**: This integrates the folder with your host OS for a seamless experience.
2.  **What it does**:
    - **SUBST mapping**: It maps the current folder to a virtual drive letter (default `P:`). This ensures that absolute paths in config files remain consistent regardless of the physical drive letter or location of the folder.
    - **Context Menu**: It adds an "Open with Porta-Flow" option to the Windows Explorer right-click menu, allowing you to quickly launch a workspace with all environment variables pre-configured.
    - **Git Config**: It sets up a project-local sandbox Git identity to prevent leaking your personal host-level Git credentials and to ensure consistent commit authorship within the sandbox.

---

## 3. Daily Workflow: The Collaborative Lifecycle (사용자 워크플로우)

A typical day in Porta-Flow follows a structured pattern to ensure that context is consistently maintained and that no work is lost between session shifts.

### 3-1. Starting the Session
1.  **Launch**: Use the context menu or run `_sys\cli\launch.bat` to open the terminal environment.
2.  **Initialize**:
    ```bat
    msg init-session --mission "Implement new API endpoint"
    ```
    This command sets the stage. It clears out any stale mailbox entries, registers the active peers for the new mission, and creates a fresh Room ID. This is the "Morning Stand-up" of the Porta-Flow system.

### 3-2. The Collaboration Loop
Porta-Flow encourages a **Research -> Strategy -> Execution -> Verification** loop to maintain high software quality and architectural consistency.

1.  **Research (GC)**:
    - Ask Gemini to analyze the codebase and find similar implementations or patterns. Gemini's 2M context window is perfect for scanning the entire project history.
    - `msg ask --to gc --query "Where are the other API endpoints defined in this project? Provide a list of files and their routing logic."`
2.  **Strategy (CC)**:
    - Ask Claude to design the new endpoint based on the research findings. Claude's strong reasoning capabilities are ideal for creating robust architectural designs.
    - `msg ask --to cc --query "Design the /v1/users endpoint structure and validation rules based on the patterns found by Gemini."`
3.  **Consensus (All)**:
    - If the design involves changes to the system layer or core protocols, initiate a consensus vote. This ensures that all peers agree with the proposed direction.
    - `msg consensus-propose --subject "New API routing logic and security policy"`
4.  **Execution (CX)**:
    - Ask Codex to write the actual Python or Node.js code according to the agreed strategy. Codex is optimized for fast and accurate code generation.
    - `msg ask --to cx --query "Implement the /v1/users endpoint logic in src/api.py as designed by Claude."`
5.  **Verification (CC/CA)**:
    - Ask Claude or the Claude Agent to run the project's tests and verify the new implementation. Verification is key to preventing regressions.
    - `msg ask --to ca --query "Run the unit and integration tests for the users endpoint and report any failures."`

### 3-3. Snapshotting and Syncing (`ctx-save.bat`)
At any point during the session, especially after a successful milestone or a complex design discussion, you should run `ctx-save.bat`.
- **Symmetric Memory**: This script writes a summary of the current state into both `CLAUDE.md` and `GEMINI.md`. This ensures that all peers are "in sync" with the latest progress, even if the primary model is switched.
- **Snapshotting**: It creates a record of all modified files and their current state, acting as a reliable checkpoint for your local development session. It's like a "Save Game" for your project.

### 3-4. Ending the Session (`ctx-end.bat`)
Always end your session properly to prepare the workspace for the next user or node. This is the "Evening Wrap-up."
- **Handoff**: It writes a final summary to `handoff.md`, clearly marking tasks as [DONE] or [PENDING]. This file is the first thing a new node reads when it joins the Room.
- **Clean Mailbox**: It archives your current message history to `_archive/` and empties the active `mailbox.json`, preventing the next session from being overwhelmed by stale context and ensuring a fresh start.
- **Session Closure**: It marks the Room as `closed` and ensures all background processes are safely terminated, freeing up system resources.

---

## 4. Comprehensive Command Reference (명령어 상세 레퍼런스)

### 4-1. Root Directory Scripts

#### `INSTALL.bat`
- **Purpose**: Initial environment and runtime setup.
- **Action**: Downloads and extracts all portable software defined in `runtimes.json`. It creates the Python virtual environment and installs all necessary system-level dependencies.
- **When to run**: First time setup, or after a manual update to `runtimes.json` to upgrade internal tools.

#### `register.bat`
- **Purpose**: Integrates the portable environment with the Windows host.
- **Action**: Maps the portable directory to drive `P:` using the `subst` command. It also registers the context menu and sets up the local Git environment within the sandbox.
- **When to run**: When moving the Porta-Flow folder to a new computer or when you need to re-map the drive letter.

#### `unregister.bat`
- **Purpose**: Removes all Porta-Flow traces from the Windows host.
- **Action**: Deletes the virtual drive mapping and removes the context menu registry keys from the Windows system.
- **When to run**: Before deleting the Porta-Flow folder or moving it permanently to another storage device.

#### `CLEANUP.bat`
- **Purpose**: Performs workspace maintenance and space optimization.
- **Action**: Deletes temporary files, large logs, build caches, and stale lock files. It helps keep the portable folder small and fast.
- **Options**: Supports light to deep cleaning tiers (1 to 4).

### 4-2. CLI Entry Points (`_sys\cli\`)

#### `msg.bat`
- **Purpose**: The primary interface for all Peer-to-Peer (P2P) communication and Room management.
- **Usage**: Wraps the core `hub.py` logic and provides a convenient way to send and receive messages, check status, and manage consensus.

#### `claude.bat` / `gemini.bat` / `codex.bat` / `agy.bat`
- **Purpose**: Direct entry points to the specific AI model CLI environments.
- **Usage**: Automatically sets up all necessary environment variables, paths, and sandbox configurations before calling the model CLI.

### 4-3. Specific IPC Commands (`msg.bat`)

#### `msg status`
- **Purpose**: Displays the current metadata, mission statement, and health of the active Room.
- **Example Output**:
  ```text
  [HUB] Room ID: room-fe18
  [HUB] Mission: Documentation Expansion
  [HUB] Phase: Execution
  [HUB] Members: cc, gc, cx, human
  [HUB] Status: active
  ```

#### `msg ask` (Synchronous)
- **Purpose**: Sends a query to a specific peer and blocks the terminal until a response is received from that peer.
- **Usage**: `msg ask --to <PEER_ID> --query "<YOUR_QUESTION>"`
- **Notes**: Useful for immediate feedback or when a task depends on the output of a specific peer.

#### `msg send` (Asynchronous)
- **Purpose**: Sends a message to a peer's mailbox without waiting for a reply.
- **Usage**: `msg send --from <SENDER_ID> --to <RECEIVER_ID> --msg "<MESSAGE_CONTENT>"`
- **Notes**: Ideal for providing updates or background information that doesn't require an immediate response.

#### `msg check`
- **Purpose**: Lists all unread messages in the mailbox for a specific target peer.
- **Usage**: `msg check --target <PEER_ID>`

---

## 5. Detailed Directory Structure Reference (디렉토리 구조 상세 안내)

Understanding the internal organization of Porta-Flow is essential for developers and advanced users who want to customize or extend the system.

- **`_sys/`**: The system layer. **Mandatory Peer Review for any changes here.**
  - **`_sys/ai/`**: Governance and protocol configurations. This is where the "laws" of the environment are defined.
    - `protocol.json`: Defines the consensus rules, health thresholds, and peer roles.
    - `governance_params.json`: Contains the 45+ parameters that control risk, budget, and autonomy.
    - `orchestration.json`: Defines the invocation commands and arguments for each AI peer node.
  - **`_sys/cli/`**: The batch file entry points for all user commands.
  - **`_sys/core/`**: The Python-based logic core, including the `hub.py` message broker and session manager.
  - **`_sys/env/`**: The portable runtimes, including Python, Node.js, and the isolated sandbox virtual environment.
  - **`_sys/hooks/`**: Scripts that are automatically triggered at key lifecycle events like saving context or ending a session.
  - **`_sys/checks/`**: The "Axis" scripts that verify system integrity, health, and portability.
  - **`_sys/docs/`**: All manuals, protocol documents, and architectural guides.
  - **`_sys/data/`**: Persistent data storage for system logs, generated files, and state.
  - **`_sys/tools/`**: A collection of sandboxed binaries like `rg.exe`, `jq.exe`, and `fd.exe`.
- **`.ai/`**: The project-local active session workspace.
  - `mailbox.json`: The active IPC message queue for all peers.
  - `state.json`: Metadata and status for the currently active Room.
  - `consensus/`: Records of all active and historical voting rounds.
- **`workspace/`**: The default folder for your project files. This area is safe for AI models to modify autonomously.
- **`_archive/`**: Contains compressed backups of old session data, logs, and achieved project goals. It acts as the "Project Attic."

---

## 6. The 10-Axis Framework: Measuring Integrity (건전성 평가 체계)

Porta-Flow evaluates its own health and integrity through 10 distinct dimensions, or "Axes." Each axis has a dedicated verification script.

| Axis | Command | Focus | Pillar |
|:---:|:---|:---|:---|
| **A** | `check-portability.bat` | Hardcoded Path Scan | Axis-4 (Environmental) |
| **B** | `check-versions.bat` | Runtime Version Check | Axis-4 (Environmental) |
| **C** | `ctx-end.bat` | Session Handoff Logic | Axis-1 (Runtime Flow) |
| **D** | (Inline) | Syntax Validation | Axis-3 (Integrity) |
| **D+**| `ctx-save.bat` | Mid-session Snapshot | Axis-1 (Runtime Flow) |
| **E** | `check-agents.bat` | Agent Metadata Audit | Axis-3 (Integrity) |
| **F** | `check-deps.bat` | Hook Dependency Map | Axis-3 (Integrity) |
| **G** | `git-draft.bat` | Commit Message Quality | Productivity |
| **H** | `check-health.bat` | Context & Mailbox Load | Axis-1 (Runtime Flow) |
| **I** | `check-risk.bat` | Shell Command Safety | Axis-3 (Integrity) |
| **J** | `check-policy.bat` | Policy Regression Gate | Axis-3 (Integrity) |

---

## 7. Configuration Reference: Governance Parameters (상세 설정 안내)

The file `P:/_sys/ai/governance_params.json` governs the entire system's risk, budget, and autonomy levels. Below are all 45+ parameters explained in detail.

### 7-1. Core Collaboration & Consensus
- **`collaboration_depth`** (10): Controls the intensity of peer interaction. A higher number forces more detailed consultation and multi-peer reasoning before any significant action.
- **`consensus_timeout`** (30): The number of minutes a voting round remains active. If it doesn't reach a decision within this time, it is marked as `stale` and requires human intervention.
- **`final_call_threshold`** (8): When the `COLLAB_RATE` is 8 or higher (Strict mode), a "Final Call" (a last-chance blocker check) is mandatory before execution.
- **`task_delegation_threshold`** (5): If a task's complexity score is above this level, the lead peer is required to delegate sub-tasks to specialists.
- **`max_nodes_per_consensus`** (10): The maximum number of AI nodes allowed to participate in a single consensus voting round.
- **`min_collaboration_depth`** (1): The minimum level of consultation required even for the most trivial tasks, preventing complete isolation.

### 7-2. Vendor & Budget Management
- **`vendor_interop_mode`** ("strict"): Defines the strictness of agreement required when multiple vendors (e.g., Anthropic vs Google) are involved in a task.
- **`daily_compute_budget`** (50000): The maximum allowed token consumption (in normalized units) for a 24-hour period for the entire workspace.
- **`budget_unit_standard`** ("ref_tokens"): The standardized unit used to calculate and compare costs across different AI model providers.
- **`max_external_invocations`** (50): Limits the number of times a session can call binary files located outside the `_sys/tools/` sandbox.
- **`token_cost_matrix`**: A weighting table that defines the relative cost for each AI model family based on their pricing and performance.

### 7-3. Context & Memory Governance
- **`context_warn_threshold`** (600KB): The size of the active mailbox that triggers a YELLOW "Warning" health status, suggesting compaction.
- **`context_critical_threshold`** (1200KB): The mailbox size that triggers a RED "Critical" status, halting execution until compaction is performed.
- **`memory_compaction_interval`** (7 days): The frequency at which the system automatically archives old entries from the `handoff.md` file.
- **`resolved_item_ttl`** (3 days): How long a completed task [DONE] remains visible in the active `handoff.md` before archival to the background history.
- **`active_item_ttl`** (14 days): How long a pending task [PENDING] can remain without update before being flagged as a "Stale" or "Zombie" task.

### 7-4. Safety & Decisioning Logic
- **`policy_bypass_floor`** (8): The minimum `COLLAB_RATE` required to skip minor style or linting gates for quick prototyping sessions.
- **`human_escalation_sla`** (120 min): The time a human is expected to respond to an `ESCALATE` request before the system assumes a communication timeout.
- **`confidence_floor`** (70%): The minimum confidence score (0-100) a model must report before it is permitted to autonomously modify a file.
- **`intent_timeout`** (60 sec): The time allowed for a peer to resolve an ambiguous user command before it must ask for clarification.
- **`clarification_max_turns`** (3): The maximum number of follow-up questions an AI can ask a user before it must commit to an action or fail.

### 7-5. Telemetry & Environment
- **`metrics_persist_interval`** (300 sec): How often system performance and usage metrics are flushed to the local data storage for auditing.
- **`doc_freshness_interval`** (30 days): The period after which documentation is flagged for re-review to ensure it hasn't drifted from the current codebase.
- **`idle_teardown_timeout`** (15 min): How long a Room can remain inactive before it is automatically hibernated to save compute resources.
- **`post_mortem_sla_hours`** (48 hours): The deadline for generating a full failure analysis report after a critical system error occurs.
- **`lazy_init_enabled`** (1): Whether to wait until the first call to initialize a specific peer node's configuration and runtime.
- **`hot_reload_enabled`** (0): Whether the hub should reload system configuration files in real-time without requiring a session restart.
- **`workspace_template_path`**: The source directory used when creating new workspaces via the management tools.
- **`common_space_path`**: The directory for shared system assets like icons, common scripts, and libraries.

---

## 8. Troubleshooting & FAQ (트러블슈팅 및 자주 묻는 질문)

### 8-1. Common Scenarios

**Q: My `P:` drive is gone. What do I do?**
A: The `subst` mapping is not persistent across reboots. Simply run `register.bat` from the Porta-Flow folder to restore the drive and all system integrations.

**Q: I keep getting "File Locked" errors in hub.py.**
A: This is usually caused by two peers trying to write to the state simultaneously. Wait a few seconds and try your command again. If it continues, run `CLEANUP.bat` to clear any orphaned lock files.

**Q: Why did Gemini give me a "REFUSAL" code?**
A: This is a safety feature for Axis checks. It usually triggers if you try to send a file larger than 400KB to the Gemini CLI. Use line-targeted reads (head/tail) to send only the necessary context.

**Q: How do I install a new Python package?**
A: You must use the sandbox's pip. Run:
   `P:\_sys\env\venv\Scripts\pip install <package_name>`
   This keeps the library isolated from your host system and ensures it travels with your portable folder.

### 8-2. Advanced Troubleshooting

- **Mailbox Corruption**: If `mailbox.json` becomes malformed, you can safely delete it. The system will recreate a clean one. You will lose recent message history, but the Room remains active.
- **Consensus Deadlock**: If peers keep voting against each other, the human director must step in. You can manually finalize a round by editing its JSON file in `.ai/consensus/` and setting the status to `"finalized"`.

---

## 9. Developer Guide: Extending the System (고급 개발자 가이드)

Porta-Flow is designed to be highly extensible for developers who want to add new capabilities or AI nodes.

### 9-1. Adding a New Peer Node
1.  **Define in `orchestration.json`**: Add an entry for your new node (e.g., `gpt-4o`) including its CLI command and invocation arguments.
2.  **Assign Role in `protocol.json`**: Register the node in the `capability_registry` and assign it a specific role like `["image-analysis"]`.
3.  **Final Registration**: Run `msg register-node --agent gpt-4o` to enable it in the Hub and make it available for P2P messages.

### 9-2. Writing a Custom Hook
Hooks allow you to run custom logic at key points in the session lifecycle, such as before a context save.
1.  Create a Python script in `_sys/hooks/` (e.g., `verify_licenses.py`).
2.  Follow the locking pattern used in `ctx_save.py` to ensure thread safety across multiple peers.
3.  Register your hook in the `_sys/dispatch.json` file.

### 9-3. Creating a New Axis Check
1.  Create a verification script in `_sys/checks/` inheriting from the `PolicyResult` class defined in `_common.py`.
2.  Add a batch file wrapper to call your script and report the result to the console.
3.  Update the Axis table in `SYSTEM_ARCHITECTURE.md` to make your new check discoverable and well-documented.

---

## 10. Glossary of Terms (용어 사전)

- **Room**: A shared collaborative session identified by a unique UUID and mission statement.
- **Node/Peer**: An AI model or human participant that has equal voting rights within a Room.
- **Consensus**: The process of reaching unanimous agreement between all registered nodes on high-risk tasks.
- **Handoff**: The structured transfer of context and pending tasks at the end of a session.
- **Subst**: The Windows command used to map a local folder to a virtual drive letter (e.g., `P:`).
- **Zero-Token**: A script or check that runs entirely locally, saving on AI vendor costs and latency.
- **Axis**: A specific dimension of system integrity, health, or portability evaluation.
- **Mailbox**: The asynchronous IPC channel where all nodes send and receive messages.
- **Phase**: The current stage of a mission (Research, Strategy, Execution, Verification).
- **Handoff.md**: The shared memory file that acts as the primary synchronization point for all nodes.

---

## 11. Detailed Annotated File Directory (파일 상세 설명)

For developers and administrators who need to understand the purpose of every critical file.

### 11-1. Root Directory
- **`INSTALL.bat`**: The bootstrapping script. It handles the initial download of portable runtimes and triggers the setup logic.
- **`register.bat`**: The integration script. It maps the virtual drive and registers context menus on the host OS.
- **`unregister.bat`**: The cleanup script. It safely detaches the virtual drive and removes all registry entries.
- **`CLEANUP.bat`**: The maintenance script. It removes temporary files, caches, and build artifacts to save space.
- **`PROTOCOL.md`**: The system's constitution. It defines the rules for P2P collaboration and consensus.
- **`CONVENTION.md`**: The coding standards document. It defines the mandatory policies for system-level scripts.

### 11-2. The `_sys/` System Layer
- **`hub.py`**: The central message broker and session manager. The most critical logic file in the system.
- **`protocol.json`**: The machine-readable implementation of all collaboration and voting rules.
- **`governance_params.json`**: The database of all numeric and boolean risk management parameters.
- **`orchestration.json`**: Defines how the system invokes the various AI peer CLIs.
- **`paths.json`**: Maps symbolic path aliases to their absolute locations on the `P:` drive.
- **`runtimes.json`**: The manifest of all required portable software versions and download URLs.

### 11-3. Lifecycle & Checks
- **`ctx_save.py`**: Handles mid-session snapshots and symmetric memory synchronization between models.
- **`ctx_end.py`**: Handles the final handoff logic and archives the session state.
- **`check_health.py`**: Monitors system health, context window usage, and mailbox load.
- **`check_policy.py`**: Verifies that the implementation still aligns with the documented protocols.
- **`check_portability.py`**: Ensures that the codebase remains fully portable and free of host-level leaks.

---

> **Porta-Flow v4.1 Technical Manual**
> Generated by **gc (Gemini CLI)** on 2026-06-13.
> Porta-Flow — The portable, peer-to-peer future of collaborative AI development.
