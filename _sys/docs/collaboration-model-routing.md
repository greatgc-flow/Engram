# MECE Review: Model-Level Routing & Profile Optimization

**Context:** Analysis for the P:\ portable multi-peer environment (P2P Collab v3).
**Objective:** Evaluate whether sub-model/model-profile routing improves token efficiency and effectiveness, and provide actionable design recommendations.

---

## 1. Model Metadata (from Q/A)
To route tasks effectively, the system must understand the capabilities of each underlying model.
- **Current State:** Nodes (cc, gc, ag) are treated as monolithic peers.
- **Optimization:** Agents should expose metadata indicating their sub-model tier (e.g., Sonnet vs. Haiku, Pro vs. Flash).
- **Metadata Fields Required:** `max_context`, `cost_tier` (low/mid/high), `supported_tools` (e.g., `web_search`, `bash`), `reasoning_depth`.

## 2. CLI Discoverability (Models/Specs/Effort/Web Tools)
The portable environment requires a standard way to query available capabilities without knowing the underlying provider API.
- **Optimization:** The CLI layer (`hub.py` and `msg.bat`) should support discovery commands.
- **Mechanism:** A node can ask the hub for peers matching specific criteria: `hub.py discover --needs web_search --effort low`.
- **Benefit:** Allows peers to dynamically discover the cheapest/fastest node capable of fulfilling a sub-task.

## 3. Top-to-Bottom Model Role Allocation
Not all tasks require high reasoning capabilities.
- **High-Tier (Pro/Opus):** Complex consensus, architectural planning, resolving `NACK` stalemates, editing `PROTOCOL.md` (R:10 tasks).
- **Mid-Tier (Sonnet/Flash):** Standard code execution, running tests, implementing isolated features (R:3 tasks).
- **Low-Tier (Haiku/Flash-8B):** Log parsing, `handoff.md` compaction, syntax validation (`check-*` scripts).
- **Benefit:** Massive token cost reduction by keeping routine tasks out of expensive context windows.

## 4. Coordinator Model Switching & Reassignment (Health/Token/Context)
In the P2P equal-authority model, any node can act as the "Active Proposer".
- **Dynamic Reassignment:** If the active proposer reaches >80% of its context window, experiences API rate limits, or fails health checks (via `health.json`), it must explicitly yield the role.
- **Mechanism:** The struggling peer writes `[YIELD: CONTEXT_LIMIT]` in `handoff.md`, prompting a fresh peer (or a peer with a larger context window) to pick up the active thread.

## 5. Compact Protocol for Weaker Models
Lower-tier models struggle with complex, deeply nested JSON or multi-layered protocols.
- **Optimization:** Utilize the existing **IPC Compact Syntax** (`ACK:r-1`, `NACK:r-1:REASON=...`).
- **Implementation:** When querying a `low` effort peer, the prompt must explicitly constrain output to strict IPC syntax or single-line responses, omitting the full `PROTOCOL.md` context to prevent hallucination and reduce token usage.

## 6. Alternatives to Sub-Model Routing
- **Static Peer Profiles:** Hardcode `cc-fast` (Haiku) and `cc-smart` (Opus) as distinct peers in `.ai/state.json`. (Pros: easier to implement; Cons: clutters the peer namespace).
- **External API Gateway:** Use an LLM proxy (like LiteLLM or OpenRouter) that automatically routes based on the prompt complexity. (Pros: zero CLI changes; Cons: breaks the portable/offline-capable philosophy of P:\).
- **Homogeneous Swarm:** Keep all peers on mid-tier models and rely on prompt-engineering. (Suboptimal for both cost and deep reasoning).

## 7. Metrics for Collaboration Understanding/Compliance
To validate the effectiveness of model routing, we must track:
1. **Rounds-per-Task:** If routing to a cheaper model increases the number of `NACK` rounds from 2 to 5, the efficiency gain is lost.
2. **Token Utilization Ratio:** Cost of task completion vs. baseline single-model cost.
3. **Policy Violation Count:** Measure how often weaker models violate the `COLLAB_RATE` (e.g., executing side-effects without finalized consensus at R:10).
4. **Time-to-Resume (Axis-1):** Does a low-tier model compact `handoff.md` effectively enough for a high-tier model to resume quickly?

---

## Actionable Design Recommendations for P:\

1. **Implement Node Capabilities in `health.json`:**
   Extend the existing health schema to include model profiles:
   ```json
   "profile": { "tier": "low", "context_window": 128000, "tools": ["read_only"] }
   ```
2. **Introduce `--effort` and `--needs` Flags to `msg.bat` and `hub.py`:**
   Allow nodes to route queries optimally: `%SYS_DIR%\cli\msg.bat ask --needs summary --effort low --query-file ...`
3. **Explicit Handoff Compaction Role:**
   Assign the `ctx-save` and log rotation hooks explicitly to low-tier profiles (e.g., Gemini Flash) to preserve high-tier tokens for actual development work.
4. **Context-Aware Yielding Protocol:**
   Update `PROTOCOL.md` to define a mandatory yield condition: if a node's token usage exceeds a defined threshold, it must append a `[YIELD]` token to `handoff.md` and transition to an `observe` state.
5. **Strict Exempt Connectors for Weaker Models:**
   Ensure lower-tier models are constrained via `action_policy: "exempt"` connectors (read-only, dry checks) to prevent them from inadvertently triggering R:10 violations due to instruction-following degradation.