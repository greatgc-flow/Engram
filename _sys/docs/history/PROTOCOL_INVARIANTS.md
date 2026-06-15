# PROTOCOL_INVARIANTS.md — Single Authoritative MUST / MUST-NOT Index

> **Version**: 1.0 | **Date**: 2026-06-14
> **Authority**: This document is the single source of truth for all mandatory rules and absolute prohibitions.
> Rules in other docs (`PROTOCOL.md §M-*`, `protocol-permissions.md §4`, `protocol-directives.md §10`, `protocol-health.md §9b`) reference or summarize this index.
> **Change requires**: R:10 unanimous consensus (all active voters).

---

## §1 — MUST DO (Mandatory Positive Rules)

### §1-A — Consensus & Execution

| ID | Rule | Source |
|----|------|--------|
| INV-01 | No execution before consensus (`FINALIZED` check mandatory at COLLAB_RATE ≥ 3). | PROTOCOL.md §M-3 |
| INV-02 | All decisions at COLLAB_RATE ≥ 8 require Final Call: "Any additional feedback or missed context?" before proceeding. | PROTOCOL.md §P-3-FC |
| INV-03 | At COLLAB_RATE = 10, offline peer auto-abstain does NOT satisfy unanimity. Human override required. | collaboration_protocol.md §5.3 |
| INV-04 | All consensus decisions must be recorded in `handoff.md [CONSENSUS_HISTORY]`. | PROTOCOL.md §P-3 |

### §1-B — Session & Context

| ID | Rule | Source |
|----|------|--------|
| INV-05 | Every peer entry point MUST run: `init-session → health-update GREEN → context-fill → check mailbox`. | protocol-session.md §4 |
| INV-06 | Re-orientation (read handoff.md) is mandatory before any work begins in a new session. | collaboration_protocol.md §2 Observe |
| INV-07 | If skipping re-orientation (no prior session found), state explicitly: `[SKIPPED: no prior session found]`. | PROTOCOL.md §P-11 |

### §1-C — Health & Routing

| ID | Rule | Source |
|----|------|--------|
| INV-08 | Health checks are zero-token (local `health.json` reads). Never contact the model for routine health checks. | protocol-health.md §9b |
| INV-09 | Peer ask outcomes (exit code, stderr) MUST be classified and recorded via `_record_ask_success/failure()`. | protocol-health.md §9b |
| INV-10 | Before routing work to a peer, `health-precheck` must pass (GREEN or YELLOW, gate_open=true). | protocol-health.md §5 |
| INV-11 | RED recovery MUST use `peer-recover` (not manual `health-update --status GREEN`). | protocol-health.md §6 |

### §1-D — Permissions & Security

| ID | Rule | Source |
|----|------|--------|
| INV-12 | All peers run with minimum non-interactive permissions (DIR-002). See `protocol-permissions.md §2`. | user-directives.md DIR-002 |
| INV-13 | Permission parity between `hub.py _build_session_cmd` and `peer_console.py` MUST be verified via `profile-validate`. | protocol-permissions.md §3 |
| INV-14 | Session fingerprint MUST be checked on resume. Drift → retire session → fresh start. | protocol-permissions.md §5 |

### §1-E — Error Handling

| ID | Rule | Source |
|----|------|--------|
| INV-15 | If the same error repeats `failure_error` consecutive times (default 5, see `protocol.json["health"]`), HALT and consult peers. | PROTOCOL.md §M-3 |
| INV-16 | P0/P1 errors escalated to Human Gate MUST include: Root Cause, System Impact, Actionable Remediation Steps. | TAXONOMY_v11 §3-5-4 |

### §1-F — Directives & Communication

| ID | Rule | Source |
|----|------|--------|
| INV-17 | All communication within a room is shared with all participating nodes (no private channels). | PROTOCOL.md §M-2 |
| INV-18 | Active runtime directives are injected into every peer ask. Peers MUST treat them as standing operational context. | protocol-directives.md §1 |

---

## §2 — MUST NOT (Absolute Prohibitions)

### §2-A — Permission Prohibitions

| ID | Rule | Source |
|----|------|--------|
| PRO-01 | **NEVER** pass raw user shell text as executable/flag fragments to peer invocations (injection risk). | protocol-permissions.md §4 |
| PRO-02 | **NEVER** grant root, SYSTEM, or admin elevation to any peer subprocess. | protocol-permissions.md §4 |
| PRO-03 | **NEVER** use bypass/full-danger flags (`yolo`, `dangerously-bypass-*`) in hub-managed asks. | protocol-permissions.md §4 |
| PRO-04 | **NEVER** resume a peer session without first verifying session fingerprint compatibility. | protocol-permissions.md §4 |
| PRO-05 | **NEVER** hardcode credentials into peer invocation arguments or environment variables. | protocol-permissions.md §4 |

### §2-B — Routing Prohibitions

| ID | Rule | Source |
|----|------|--------|
| PRO-06 | **NEVER** route asks to RED or gate-closed peers hoping they will self-heal. | protocol-permissions.md §4, protocol-health.md §9 |
| PRO-07 | **NEVER** infer peer health from arbitrary prose content — only from transport signals (exit code, stderr markers). | protocol-health.md §9b |
| PRO-08 | **NEVER** send a dedicated model ping just to check health (wastes tokens). | protocol-health.md §9b |

### §2-C — Directive Prohibitions

| ID | Rule | Source |
|----|------|--------|
| PRO-09 | **NEVER** write auto-generated rules into `user-directives.md` — that muddies human authority. | protocol-directives.md §10 |
| PRO-10 | **NEVER** inject directive content that is user-shell-injectable (hub constructs rules from internal strings only). | protocol-directives.md §10 |
| PRO-11 | **NEVER** skip injection for a peer claiming "it already knows" — every peer gets the full context. | protocol-directives.md §10 |

### §2-D — Governance Prohibitions

| ID | Rule | Source |
|----|------|--------|
| PRO-12 | **NEVER** modify `CLAUDE.md`, `PROTOCOL.md`, or `hub.py` without N-way consensus. | PROTOCOL.md §M-1 |
| PRO-13 | **NEVER** access Security/Auth files (`auth`, USERPROFILE area) from any AI peer. | PROTOCOL.md §M-1 |
| PRO-14 | **NEVER** let a stale coordinator keep task ownership without a checkpoint. | protocol-health.md §9 |

### §2-E — ag-Specific (Temporary)

| ID | Rule | Source |
|----|------|--------|
| PRO-15 | **NEVER** re-enable ag (AntiGravity) peer until `peer_console.py` ag block is updated with correct minimum flags (currently uses `--dangerously-skip-permissions` as known gap). | protocol-permissions.md §2 ag |

---

## §3 — Boundary Map

```
INV (MUST DO)  ←──────────────────────────────→  PRO (MUST NOT)
Positive obligations                           Absolute prohibitions
────────────────────────────────────────────────────────────────────
INV-01~04: Consensus                     PRO-01~05: Permissions
INV-05~07: Session lifecycle             PRO-06~08: Routing
INV-08~11: Health & routing              PRO-09~11: Directives
INV-12~14: Permissions                   PRO-12~14: Governance
INV-15~16: Error handling                PRO-15: ag temporary gap
INV-17~18: Directives
```

---

## §4 — Examples

### Correct behavior at COLLAB_RATE=10:
```
1. Read handoff.md (INV-06)
2. Check runtime-directives.jsonl (INV-18)
3. health-precheck --peer gc (INV-10)
4. consensus-propose --subject "Modify hub.py" (INV-01, PRO-12 avoided by consensus)
5. All peers vote AGREE → Final Call (INV-02)
6. Execute with minimum permissions (INV-12)
7. Record outcome → health updated (INV-09)
```

### Forbidden pattern:
```
hub.py ask --to gc  # when gc health.json shows RED (violates PRO-06 + INV-10)
hub.py ask --to cx --dangerously-bypass-approvals-and-sandbox  # violates PRO-03
```

---

*Ref: `PROTOCOL.md §M-1~§M-3` | `protocol-permissions.md §4` | `protocol-directives.md §10` | `protocol-health.md §9b` | `user-directives.md`*
