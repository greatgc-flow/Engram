# Document Index — P:\_sys\docs

> SSOT for all system documentation. Organized MECE. Last updated: 2026-06-15.

## Structure

| Folder | Contents |
|--------|----------|
| [`protocol/`](protocol/) | Protocol specs, debate protocol, invariants, 9 domain files (see `protocol/`) |
| [`architecture/`](architecture/) | MECE spec, taxonomy, workspace maps (see also `P:\CONVENTION.md` at root) |
| [`user/`](user/) | User manual, collaboration guide |
| [`plans/`](plans/) | Active execution plans |
| [`history/`](history/) | Completed plans, debate logs, amendment records |
| [`history/debate-rounds/`](history/debate-rounds/) | All crossreview-amendment rounds (archival) |
| [`etc/`](etc/) | Unclassified / ambiguous documents |

## ⚠ System Dependencies — Do NOT Move

The following root-level files are **SSOT at P:\\ root** due to functional requirements:

| File | Why It Must Stay at Root |
|------|--------------------------|
| `P:\PROTOCOL.md` | Read by `check_policy.py` (Axis-J) at hardcoded `_PORTABLE_ROOT / "PROTOCOL.md"` |
| `P:\CONVENTION.md` | Read by `check_policy.py` and `tests/unit/test_doc_consistency.py` at root |
| `P:\CLAUDE.md` | Consumed by Claude Code CLI as project-level config (always reads project root) |
| `P:\AGENTS.md` | Consumed by AI tools (Anthropic AGENTS.md format) at root |
| `P:\GEMINI.md` | Consumed by Gemini CLI as project-level config at root |

**Moving any of these files will break Axis-J policy checks and AI tool session initialization.**

## Operational Docs (Stay in Functional Location)

These are machine-readable operational configs, **not** user-facing documents — they stay at their functional SSOT path:

| File | Location | Purpose |
|------|----------|---------|
| `peer-rules.md` | `_sys/ai/common/peer-rules.md` | Common IPC rules loaded by hub.py |
| `user-directives.md` | `_sys/ai/user-directives.md` | Runtime user directives |
| `agents/*.md`, `skills/*.md` | `_sys/ai/common/agents/`, `skills/` | Agent/skill definitions (machine-readable) |
| `AGY.md` | `_sys/antigravity/config/AGY.md` | Antigravity peer config |

## Key Files

- [`protocol/DEBATE_PROTOCOL.md`](protocol/DEBATE_PROTOCOL.md) — v0.10 CANONICAL debate/review protocol
- [`protocol/PROTOCOL_INVARIANTS.md`](protocol/PROTOCOL_INVARIANTS.md) — MUST/MUST-NOT rules (INV-01~18, PRO-01~15)
- [`architecture/TAXONOMY_v11.md`](architecture/TAXONOMY_v11.md) — Active governance taxonomy
- [`architecture/MECE_Directory_Architecture_Specification.md`](architecture/MECE_Directory_Architecture_Specification.md) — Directory architecture spec
- [`plans/sys-restructure-plan.md`](plans/sys-restructure-plan.md) — Current restructure execution blueprint
- [`user/USER_MANUAL.md`](user/USER_MANUAL.md) — User manual
