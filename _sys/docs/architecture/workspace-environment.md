# Workspace Environment Inventory

This document records the essential workspace configuration and portable components. It intentionally excludes runtime state, logs, telemetry, temporary files, archives, and generated caches.

## Root Entry Points

| Path | Purpose |
|---|---|
| `INSTALL.bat` | Rebuild portable runtimes and tools from a minimal checkout. |
| `register.bat` | Register host integration such as SUBST and Explorer context menu. |
| `unregister.bat` | Remove host integration. |
| `CLEANUP.bat` | Run cleanup tiers for generated data and local caches. |
| `README.md` | Public project overview and GitHub-facing value proposition. |
| `AGENTS.md` | Contributor guide for coding, testing, and PR work. |
| `PROTOCOL.md` | Index for the multi-peer collaboration protocol. |
| `CLAUDE.md`, `GEMINI.md` | Peer-facing workspace guides. |

## System Configuration

| Path | Role |
|---|---|
| `_sys/ai/protocol.json` | Master collaboration policy: R:10, runtime, guards, feedback, artifacts, model profiles. |
| `_sys/ai/peers.json` | Managed peer registry: Claude, Gemini, Codex, Antigravity host/project config. |
| `_sys/ai/orchestration.json` | Hub node IDs: `cc`, `ca`, `gc`, `ag`, `cx`, invoke args, aliases, default voters. |
| `_sys/ai/lifecycle_policy.json` | Health lifecycle, ask failure classification, room reset, messaging policy. |
| `_sys/ai/traceability_map.json` | Machine-readable mapping from docs to config, runtime functions, and tests. |
| `_sys/core/hub_config.json` | Hub limits for mailbox, handoff rolling windows, and payload threshold. |
| `_sys/context_menu.json`, `_sys/env.json`, `_sys/runtimes.json` | Host integration and portable runtime metadata. |

## Runtime and CLI Control Plane

| Path | Role |
|---|---|
| `_sys/core/hub.py` | Central P2P hub: sessions, mailbox, ask, consensus, health, feedback, artifacts. |
| `_sys/cli/msg.bat` | Single command entrypoint into `hub.py`. |
| `_sys/cli/*_entry.py`, `_sys/cli/*.bat` | Peer launch wrappers and command shims. |
| `_sys/checks/check-*.bat` | Health, dependency, policy, portability, risk, and version checks. |
| `_sys/hooks/*` | Context, logging, archive, and lifecycle hooks. |
| `_sys/tests/` | Unit, integration, host, and Windows Sandbox validation. |

## Portable Tools and Runtimes

The workspace is designed to carry its own runtime and command tools under `_sys/`.

| Area | Examples |
|---|---|
| `_sys/env/` | Portable Python, Node.js, virtual environment, and related runtime assets. |
| `_sys/tools/` | `rg`, `jq`, `gh`, `fd`, `fzf`, `bat`, `delta`, `sqlite`, `oh-my-posh`, `agy`. |
| `_sys/templates/` | Workspace and global file templates. |

Heavy binaries are environment assets and should generally remain untracked unless the repository policy explicitly says otherwise.

## AI Peer Configuration

| Peer node | Managed peer | Config roots | Notes |
|---|---|---|---|
| `cc` | `claude` | `_sys/claude/config`, `_sys/claude/project`, `.claude` junction | Primary Claude peer with persistent memory role. |
| `ca` | `claude` | Same managed peer, separate node identity | Claude alternate/verification node from `orchestration.json`. |
| `gc` | `gemini` | `_sys/gemini/config`, `_sys/gemini/project`, `.gemini` junction | Gemini peer for large-context analysis and docs. |
| `ag` | `antigravity` | `_sys/antigravity/config`, `.agy` junction | Antigravity/agy shell and workflow orchestration peer. |
| `cx` | `codex` | `_sys/codex/config`, `.codex` junction | Codex peer for repo-local coding, review, and tests. |

`peers.json` defines managed peer configuration. `orchestration.json` defines hub node identities and invocation commands. This distinction is intentional: multiple nodes can map to one managed peer family.

## Skills, Agents, and Shared AI Assets

| Path | Purpose |
|---|---|
| `_sys/claude/project/agents/` | Claude project agents such as verifier, coordinator, proposer, risk scanner. |
| `_sys/claude/project/skills/` | Peer skills for portability, risk scan, scenario review, Gemini coordination, and improvement proposals. |
| `_sys/ai/common/agents/` | Cross-peer agent definitions. |
| `_sys/ai/common/skills/` | Shared skill docs for health check, context fill, and consensus voting. |
| `_sys/ai/common/mcp/catalog.json` | Common MCP/catalog metadata. |

## Collaboration State Boundaries

| Path | Policy |
|---|---|
| `.ai/` | Runtime collaboration state. Peers should use `hub.py` / `msg.bat`, not direct writes. |
| `.ai/payloads/` | Large message payload references. |
| `.ai/feedback.jsonl` | Structured improvement feedback when enabled. |
| `.ai/artifacts.json` | Shared artifact ownership and finalization metadata when enabled. |
| `_archive/` | Historical logs and archived state. Exclude from source control. |
| `_sys/claude/config/telemetry/` | Runtime telemetry. Exclude from source control. |

## Audit Notes

- `traceability_map.json` should be updated whenever protocol sections, config keys, runtime functions, or tests are added.
- `README.md` should stay user-facing and attractive; detailed engineering maps belong in `_sys/docs/`.
- Generated root temp files and telemetry must be investigated before deletion, then handled by cleanup rules or `.gitignore`.
