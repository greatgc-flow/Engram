# Legacy Document Archive Index — `_sys/docs`

> **⚠ ARCHIVE:** This directory is an archival ledger only.
> The active Single Source of Truth for architecture, protocol, and peer rules is **`_sys/docs-v2/`**.

## Active SSOT

| Resource | Location |
|----------|----------|
| Protocol architecture | `_sys/docs-v2/00-MANIFEST.md` |
| System invariants | `_sys/docs-v2/10-invariants.md` |
| Domain rules | `_sys/docs-v2/general/*.md` |
| Peer-specific rules | `_sys/docs-v2/specific/{cc,gc,cx,ag}.md` |
| Templates + anti-patterns | `_sys/docs-v2/ops/` |
| User manual | `_sys/docs-v2/user/manual.md` |

## Root-Level SSOT Files (Must Stay at Root)

| File | Reason |
|------|--------|
| `P:\PROTOCOL.md` | Read by `check_policy.py` (Axis-J) at hardcoded root path |
| `P:\CONVENTION.md` | Read by `check_policy.py` and test_doc_consistency at root |
| `P:\CLAUDE.md` | Consumed by Claude Code CLI as project-level config |
| `P:\AGENTS.md` | Consumed by Anthropic AGENTS.md tooling at root |
| `P:\GEMINI.md` | Consumed by Gemini CLI as project-level config at root |

## Archive Structure

| Folder | Contents |
|--------|----------|
| [`history/`](history/) | Immutable archive — past protocol versions, debate logs, cross-review ledgers |
| [`history/debate-rounds/`](history/debate-rounds/) | All P2P multi-model consensus rounds (archival) |
| [`architecture/`](architecture/) | MECE directory spec, TAXONOMY_v11, workspace maps |
| [`user/`](user/) | Legacy user manual snapshot |
| [`plans/`](plans/) | Completed execution blueprints |

*(Note: `protocol/` and `etc/` directories removed — MECE violation, superseded by `docs-v2/`.)*
