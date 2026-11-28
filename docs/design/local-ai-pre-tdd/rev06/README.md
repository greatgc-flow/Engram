# Engram Cognitive AI Platform — Pre-TDD design package

**Revision:** 0.6 · **Date:** 2026-11-28 KST · **Status:** proposed design, not implemented

Start with [SPECIFICATION.md](SPECIFICATION.md). The specification is the normative English consolidation of Rev. 0.5 and the subsequent discussion of cross-agent activity, existing documents, PeerHub, memory types, context windows, hippocampal-inspired indexing and sleep-time consolidation. It preserves the earlier portability, Multi-Python, lifecycle and safety requirements. All CLI commands and internal contracts introduced here are proposals unless explicitly labeled existing.

| File | Purpose |
|---|---|
| `SPECIFICATION.md` | Architecture, component contracts, data ownership, state machines, operational and security policies |
| `CONTRACTS.md` | Proposed versioned interfaces, event envelopes, relational records, CLI semantics and failure codes |
| `DECISIONS.md` | ADRs, open decisions, risk register and evidence boundaries |
| `TEST_CATALOG.csv` | Stable T01–T86 from Rev. 0.5, in English, plus new pre-TDD acceptance cases |
| `REQUIREMENTS.csv` | Requirements, owner, acceptance linkage, priority and gate |
| `IMPLEMENTATION_PLAN.md` | PoC blockers, ordered RED sequence, PR boundaries, release gates, runbooks |
| `SOURCES.md` | Pinned code baseline, public upstream documentation and Rev. 0.5 section coverage |
| `MANIFEST.sha256` | Package file integrity; does not claim upstream artifact authenticity |

No production source code, executable tests, credentials, actual personal activity logs or real DB dumps are included. No repository modification, merge, installation or live model run was performed. All acceptance cases start NOT_RUN. The user-requested stopping point is immediately before TDD; P0 environmental spikes and unresolved interface checks must precede the dependent test/implementation work. Use synthetic fixtures in public repositories. The design may proceed to pure-contract RED tests after review, but it is not a claim that Windows/GPU integration is feasible or production ready.
