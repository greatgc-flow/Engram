# Porta-Flow: Portable Multi-AI Dev Workspace

Porta-Flow is a Windows-first portable development workspace that lets Claude, Gemini, Antigravity, Codex, and human developers collaborate through one local folder.

Clone it, carry it, register it on any PC, and keep the same tools, AI peer settings, consensus protocol, tests, and workspace state without polluting the host machine.

## Why Star This

- **Multi-AI collaboration in one repo**: `cc`, `ca`, `gc`, `ag`, and `cx` work as equal peers through a shared hub.
- **Portable by design**: runtimes, tools, CLI wrappers, hooks, and AI configs live under `_sys/`.
- **Consensus-driven changes**: high-risk actions can be gated by `collab_rate`, finalized consensus, and traceable handoff state.
- **Zero-token control plane**: health checks, context fill, feedback tracking, artifact metadata, and policy routing run locally before model calls.
- **Auditable engineering loop**: protocol rules map to JSON config, runtime functions, and unit tests.

## AI Collaboration Model

```text
Human
  |
  v
_sys/cli/msg.bat
  |
  v
_sys/core/hub.py  <---->  _sys/ai/protocol.json
  |
  +-- cc / ca: Claude-based architecture, implementation, verification
  +-- gc: Gemini large-context analysis and documentation
  +-- ag: Antigravity shell and workflow orchestration
  +-- cx: Codex code review, refactoring, tests, and patch planning
```

Peers share room state through `.ai/`, exchange messages through the hub, record handoff context, and use `feedback-*` and `artifact-*` actions to keep collaboration durable.

## Key Capabilities

| Area | What it does |
|---|---|
| P2P hub | `_sys/core/hub.py` manages sessions, mailbox, ask, consensus, health, feedback, and artifacts. |
| Consensus | `PROTOCOL.md` and `_sys/ai/protocol.json` define R:10 unanimous governance and action gates. |
| Feedback loop | `feedback-add/list/resolve` keeps improvement items out of transient chat history. |
| Artifact workflow | `artifact-claim/status/finalize` tracks single-owner merge flow and final file hashes. |
| Health routing | Peer health files and gate checks prevent repeated calls to blocked peers. |
| Portable tools | `_sys/tools/` carries utilities such as ripgrep, jq, gh, fd, fzf, bat, delta, sqlite, and oh-my-posh. |
| Tests | `_sys/tests/unit` covers hub behavior, integration scenarios, locks, launchers, lifecycle, and paths. |

## Quick Start

1. Run `INSTALL.bat` to rebuild portable runtimes and tools.
2. Run `register.bat` to register the folder on the current PC.
3. Use `_sys\cli\msg.bat status` to inspect the collaboration room.
4. Use `_sys\tests\run-tests.bat --all` for full validation.

## Project Structure

```text
.
|-- README.md                  # Project overview
|-- AGENTS.md                  # Contributor guide for this repository
|-- PROTOCOL.md                # Multi-peer collaboration protocol index
|-- CLAUDE.md / GEMINI.md      # Peer-facing workspace guides
|-- INSTALL.bat                # Rebuild portable environment
|-- register.bat               # Register host integration
|-- unregister.bat             # Remove host integration
|-- CLEANUP.bat                # Cleanup entrypoint
|-- workspace/                 # Default user workspace
|-- .ai/                       # Runtime collaboration state, hub-managed only
|-- _archive/                  # Logs and archived runtime data
`-- _sys/
    |-- ai/                    # Protocol, peer registry, orchestration, traceability
    |-- core/                  # hub.py, setup, config, relocation logic
    |-- cli/                   # msg.bat and peer launch wrappers
    |-- checks/                # Health, policy, deps, portability checks
    |-- docs/                  # Architecture, protocol, environment maps
    |-- hooks/                 # Lifecycle and context hooks
    |-- tests/                 # Unit, integration, and sandbox tests
    |-- tools/                 # Portable binary tools
    |-- claude/                # Claude config, agents, skills
    |-- gemini/                # Gemini config and project settings
    |-- antigravity/           # Antigravity config and agentapi bridge
    `-- codex/                 # Codex config and templates
```

## Configuration and Audit Maps

- `_sys/ai/protocol.json`: collaboration policy, runtime policy, guards, model profile convention.
- `_sys/ai/peers.json`: managed peer registry and host/project junction metadata.
- `_sys/ai/orchestration.json`: hub node IDs, invoke commands, aliases, and default voters.
- `_sys/ai/lifecycle_policy.json`: health lifecycle, failure classification, room reset, messaging policy.
- `_sys/ai/traceability_map.json`: protocol-to-config-to-code-to-test mapping.
- `_sys/docs/workspace-connectivity-map.md`: root-to-runtime connectivity diagram.
- `_sys/docs/workspace-environment.md`: portable tools, peer configs, skills, and plugin layout.
- `_sys/docs/collaboration-mece-review.md`: collaboration design review and implemented feedback loop summary.

## Validation

Fast hub-focused check:

```bat
python -m pytest _sys\tests\unit\test_hub.py
```

Full unit suite:

```bat
python -m pytest _sys\tests\unit
```

Recent baseline: `198 passed, 1 skipped, 2 pytest config warnings`.

## Repository Hygiene

Generated state, logs, telemetry, runtime caches, `.ai/`, `_archive/`, and heavy portable binaries should stay out of source control. Source, policy, tests, templates, and documentation should remain traceable and reviewable.
