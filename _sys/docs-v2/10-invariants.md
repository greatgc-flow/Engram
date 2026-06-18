# Invariants — MUST / MUST-NOT Index
> Authority: Highest. Change requires R:10 unanimous consent (all active voters).
> Source: PROTOCOL_INVARIANTS.md v1.0 · 2026-06-14

---

## MUST DO (INV)

### Consensus & Execution
| ID | Rule |
|----|------|
| INV-01 | No execution before consensus. `FINALIZED` check mandatory at COLLAB_RATE ≥ 3. |
| INV-02 | At COLLAB_RATE ≥ 8: Final Call required — "Any additional feedback?" → all peers ACK before proceeding. |
| INV-03 | At COLLAB_RATE = 10: offline peer auto-abstain does NOT satisfy unanimity. Human override required. |
| INV-04 | All consensus decisions recorded in `handoff.md [CONSENSUS_HISTORY]`. |

### Session & Context
| ID | Rule |
|----|------|
| INV-05 | Every peer entry MUST run: `init-session → health-update GREEN → context-fill → check mailbox`. |
| INV-06 | Re-orientation (read handoff.md) mandatory before any work in a new session. |
| INV-07 | If skipping re-orientation (no prior session): state explicitly `[SKIPPED: no prior session found]`. |

### Health & Routing
| ID | Rule |
|----|------|
| INV-08 | Health checks are zero-token (local `health.json` reads only — never model calls). |
| INV-09 | Every peer ask outcome (exit code, stderr) MUST be classified via `_record_ask_success/failure()`. |
| INV-10 | Before routing work to a peer, `health-precheck` must pass (GREEN or YELLOW, gate_open=true). |
| INV-11 | RED recovery MUST use `peer-recover` — NOT manual `health-update --status GREEN`. |

### Permissions & Security
| ID | Rule |
|----|------|
| INV-12 | All peers run with minimum non-interactive permissions (DIR-002). See `general/permissions.md`. |
| INV-13 | Permission parity between `hub.py _build_session_cmd` and `peer_console.py` MUST be verified via `profile-validate`. |
| INV-14 | Session fingerprint MUST be checked on resume. Drift → retire session → fresh start. |

### Error Handling
| ID | Rule |
|----|------|
| INV-15 | Same error repeats `failure_error` times (default 5, see `protocol.json["health"]`) → HALT, consult peers. |
| INV-16 | P0/P1 errors escalated to Human Gate MUST include: Root Cause · System Impact · Actionable Remediation. |

### Directives & Communication
| ID | Rule |
|----|------|
| INV-17 | All communication within a room is shared with all participating nodes (no private channels). |
| INV-18 | Active runtime directives injected into every peer ask. Peers MUST treat as standing operational context. |
| INV-19 | All internal content (IPC queries, docs-v2 documents, source code, commit messages, proposals) MUST be written in English. Exception: console output delivered directly to the human user MAY be in Korean. Rationale: CJK tokens cost 2–7× more than ASCII — internal English reduces per-session token spend by ~40%. |

---

## MUST NOT (PRO)

### Permission Prohibitions
| ID | Rule |
|----|------|
| PRO-01 | NEVER pass raw user shell text as executable/flag fragments (injection risk). |
| PRO-02 | NEVER grant root, SYSTEM, or admin elevation to any peer subprocess. |
| PRO-03 | NEVER use bypass/full-danger flags (`yolo`, `dangerously-bypass-*`) in hub-managed asks. |
| PRO-04 | NEVER resume a peer session without first verifying session fingerprint compatibility. |
| PRO-05 | NEVER hardcode credentials into peer invocation arguments or environment variables. |

### Routing Prohibitions
| ID | Rule |
|----|------|
| PRO-06 | NEVER route asks to RED or gate-closed peers hoping they will self-heal. |
| PRO-07 | NEVER infer peer health from prose content — only from transport signals (exit code, stderr markers). |
| PRO-08 | NEVER send a dedicated model ping just to check health (wastes tokens). |

### Directive Prohibitions
| ID | Rule |
|----|------|
| PRO-09 | NEVER write auto-generated rules into `user-directives.md` — that muddies human authority. |
| PRO-10 | NEVER inject directive content that is user-shell-injectable. |
| PRO-11 | NEVER skip injection for a peer claiming "it already knows" — every peer gets full context. |

### Governance Prohibitions
| ID | Rule |
|----|------|
| PRO-12 | NEVER modify `CLAUDE.md`, `PROTOCOL.md`, `GEMINI.md`, `protocol.json`, or `hub.py` without R:10 unanimous consensus (all active voters in `protocol.json["consensus"]["r10_voters"]`). |
| PRO-13 | NEVER access Security/Auth files (`auth`, USERPROFILE area) from any AI peer. |
| PRO-14 | NEVER let a stale coordinator keep task ownership without a checkpoint. |

### Language & Communication
| ID | Rule |
|----|------|
| PRO-16 | NEVER write IPC query files, proposals, or peer-to-peer messages in Korean. Always English. (INV-19 enforcement) |

### ag-Specific (Temporary)
| ID | Rule |
|----|------|
| PRO-15 | NEVER re-enable ag until `peer_console.py` ag block is updated with correct minimum flags. Current gap: `--dangerously-skip-permissions` in use. |
