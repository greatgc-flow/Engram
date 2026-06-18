# PROTOCOL.md — Collaboration Protocol Index (v4.2)

> This file is a **routing index only**. All normative content lives in `_sys/docs-v2/` (SSOT v1.3).
> Do NOT add protocol content here — edit the appropriate `docs-v2/` file instead.
> Config-driven via `_sys/ai/protocol.json` | Language policy: INV-19 (English internal, Korean console only)

---

## Load Order (peer startup)

```
1. _sys/docs-v2/10-invariants.md   ← ALWAYS FIRST: hard rules (INV-01~19, PRO-01~16)
2. _sys/docs-v2/20-architecture.md ← directory layout, path conventions
3. _sys/docs-v2/general/protocol.md← COLLAB_RATE, P2P model, feedback loop
4. _sys/docs-v2/general/session.md ← session startup contract, resume decision tree
5. _sys/docs-v2/specific/{id}.md   ← peer delta only (load after general/)
```

## SSOT Map

| Domain | File | Keywords |
|--------|------|---------|
| **Hard Rules** | `_sys/docs-v2/10-invariants.md` | INV-01~19, PRO-01~16, MUST/MUST-NOT |
| **Architecture** | `_sys/docs-v2/20-architecture.md` | directory layout, brain layers, connectivity map |
| **Collaboration** | `_sys/docs-v2/general/protocol.md` | COLLAB_RATE, P2P, feedback loop, virtuous cycle |
| **Consensus** | `_sys/docs-v2/general/consensus.md` | R:10, voting, tiebreak, Final Call |
| **Session** | `_sys/docs-v2/general/session.md` | startup contract, resume, handoff, INV-05/06 |
| **Health** | `_sys/docs-v2/general/health.md` | GREEN/YELLOW/RED, zero-token, recovery |
| **Routing** | `_sys/docs-v2/general/routing.md` | leader election, failover, first_healthy |
| **Permissions** | `_sys/docs-v2/general/permissions.md` | minimum permissions, DIR-002, MUST-NEVER |
| **Directives** | `_sys/docs-v2/general/directives.md` | standing rules, TTL, runtime-directives.jsonl |
| **Communication** | `_sys/docs-v2/general/communication.md` | sync/async, send vs thread, alerting |
| **Knowledge** | `_sys/docs-v2/general/knowledge.md` | lesson propagation, pack delivery |
| **Self-Evolution** | `_sys/docs-v2/general/self-evolution.md` | self-care, DocsSyncer, SaturationDetector |
| **Tradeoffs** | `_sys/docs-v2/general/tradeoffs.md` | COLLAB_RATE, EFFORT, SLIM, SANDBOX parameters |
| **Resource Gov.** | `_sys/docs-v2/general/resource-governance.md` | model inventory, node arch, cost/quality, QUALITY_MODE |
| **Peers** | `_sys/docs-v2/specific/{cc\|gc\|cx\|ag}.md` | per-peer delta flags and gate configs |
| **Anti-Patterns** | `_sys/docs-v2/ops/anti-patterns.md` | AP-01~AP-21 failure modes |
| **Logging** | `_sys/docs-v2/ops/logging.md` | IPC log, cost log, rolling policy, 5-Whys |
| **Governance** | `_sys/docs-v2/ops/governance.md` | proposal lifecycle, archival, retention |
| **Skills** | `_sys/docs-v2/ops/skills.md` | hub skill definitions, registration, catalog |
| **Schemas** | `_sys/docs-v2/ops/schemas.md` | JSON schema reference for all config files |
| **Debate** | `_sys/docs-v2/ops/debate.md` | exhaustive work session rules |
| **Audit** | `_sys/docs-v2/ops/audit-checklist.md` | MECE audit items |
| **User Manual** | `_sys/docs-v2/user/manual.md` | quick start, daily workflow, commands |
| **Requirements** | `_sys/docs-v2/user/requirements.md` | MECE user requirements |
| **Master Index** | `_sys/docs-v2/MOC.md` | Map of Content — full navigation index |

## Active Constraints (Quick Check)

- `collab_rate`: read `_sys/ai/protocol.json["collab_rate"]["current"]`
- Standing default: ALL requests use peer collaboration per collab_rate (no explicit trigger needed)
- Consensus required for: `_sys/` changes, this file, `protocol.json`, `peers.json`, `docs-v2/`
- Language: internal content English (INV-19) | user console Korean

## Related Root Files (DO NOT MOVE)

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Claude Code global config + collaboration defaults |
| `GEMINI.md` | Gemini CLI global config + collaboration interface |
| `AGENTS.md` | Repo contributor guidelines (agent-facing) |
| `CONVENTION.md` | Coding conventions (bat, ps1, naming, language policy) |
| `README.md` | Human onboarding entry point |
