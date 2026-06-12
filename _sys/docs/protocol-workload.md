# Protocol: Workload Distribution (v4.1)
> Source: `_sys/ai/protocol.json["workload"]` | Part of composable PROTOCOL.md

## 1. Peer Equality & User Communication

All AI peers have **absolutely equal** authority in decision-making and proposal rights.
**Any peer may communicate directly with the Human** — there is no fixed coordinator or spokesperson.
Domain expertise guides *who leads* a topic, not who is allowed to speak.

## 2. Capability Registry

From `protocol.json["workload"]["capability_registry"]`:

| Peer | Strengths |
|------|-----------|
| **cc** | architecture, implementation, _sys-scripts, orchestration, persistent-memory |
| **ca** | testing, verification, cross-check, targeted-implementation |
| **gc** | documentation, large-corpus-analysis, global-dependency-mapping, zero-shot-tool-integration |
| **ag** | shell-scripts, quick-cli, file-ops, system-orchestration, real-time-feedback-loop, image-generation |
| **cx** | code-generation, refactoring, code-review, bug-fixing, test-authoring, patch-planning, repo-local-reasoning |

**Domain Weight**: When a tiebreak or conflict resolution is needed, the peer with most relevant capabilities for that task domain carries higher weight in the recommendation to Human.

## 3. Routing Rules

From `protocol.json["workload"]["routing_rules"]`:

| Task Type | Preferred | Fallback |
|-----------|-----------|---------|
| doc | gc → cc | cc |
| script | cc → ag | cc |
| verify | ca | cc |
| code | cx → cc | cc |
| code-review | cx → ca | cc |
| large-corpus | gc | cc |
| shell-ops | ag → cc | cc |

Routing requires: `context_health.status != "RED"` AND `availability.gate_open == true`

## 4. Context Fill Depth

gc has `fill_depth_multiplier: 3` — when gc starts a session, it reads 3x more handoff sections than other peers, leveraging its larger context window for building the most comprehensive shared blackboard.

## 5. Token Efficiency & Cross-Verification

- Assign large-corpus tasks to gc (saves cc context tokens)
- Assign code verification to ca/cx (parallel cross-check)
- Assign shell/file ops to ag (saves cc for architectural thinking)
- gc produces doc drafts; cc reviews for correctness
- cx produces code patches; ca writes tests; cc reviews architecture

## §HISTORY
- v4.1 (2026-06-12): Confirmed equal-authority P2P routing defaults.
- v4.0 (2026-06-11): Extracted from PROTOCOL.md §P-4; added user communication equality, fill_depth_multiplier, cross-verification strategy
