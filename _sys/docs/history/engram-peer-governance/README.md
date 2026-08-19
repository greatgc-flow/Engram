# Engram peer-governance archive (superseded)

**Non-normative.** These documents describe the multi-peer collaboration
and governance system Engram used to carry before it was separated from
[peerhub](https://github.com/greatgc-flow/peerhub) on **2026-08-19**.

They are kept for provenance only. Nothing here describes current Engram
behaviour, and nothing here should be treated as a requirement.

## What changed

Engram is now strictly a **portable Windows AI development environment**:
install/bootstrap, update/doctor, virtual-drive and context-menu
registration, cleanup, and interactive vendor-CLI launching.

All **peer/profile communication and coordination** moved to the
separately-installed `peerhub` package: dispatch (`peerhub ask`),
fan-out (`peerhub broadcast`), status and quota telemetry
(`peerhub status`, `peerhub diag`).

## Intentionally dropped, not ported

These were removed as product features rather than migrated. Reviving any
of them requires a fresh design against a real need, not restoration from
this archive:

- `collab_rate` and the R:6-R:10 escalation ladder
- `consensus-propose/-vote/-check/-sweep` round-based voting, Final Call,
  unanimity gates, and the arbiter
- leader election, coordinator role, terminal-duty rotation/handoff
- mailbox / threads / blackboard messaging
- directives, lessons, feedback, proposals, credits
- the governed-mutation broker and generic advisory file locks

## Where the decision lives

The ratified plan is recorded in peerhub's
`docs/design/BACKLOG-CONSOLIDATED-2026-08-16.md` under
"Engram/peerhub full separation", which cites the round-1 proposal and
the reconciliation note that superseded it.

Engram's replacement guard is `_sys/tests/unit/l1_core/test_contracts.py`
-- product-boundary contracts that fail closed if the coordination layer
starts creeping back in.
