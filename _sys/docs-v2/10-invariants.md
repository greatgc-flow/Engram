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
| INV-13 | Permission parity between the live `hub_peer.py` adapter command and `peer_console.py` MUST be verified via `profile-validate`. |
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

### Hub Governance & Peer Routing (D-01g~D-08g)
| ID | Rule |
|----|------|
| INV-20 | Recovery Journal: Hub operations must journal intent to `operations.jsonl` (append-only), atomically replace affected state (via `os.replace`), then journal commit. This guarantees consistency across non-ACID filesystems. |
| INV-21 | Challenge Window: Leader claims must remain pending during a challenge window (default 60s) to allow other peers to challenge. |
| INV-22 | Term Limits: Coordinator claims must be rejected by the hub if a single peer has held coordinator role for 3 consecutive terms. |
| INV-23 | Stable Fingerprint: Session fingerprints must only hash normative compatibility fields, excluding environment-specific paths. |
| INV-24 | Declaration Priority: Local routing/classification inferences must not override explicit `peer.profile` declarations. |
| INV-25 | 5-Layer Evidence: Routing decisions must evaluate all 5 evidence layers (Explicit metadata, Semantic markers, Request shape, Multilingual shape, Runtime feedback) and record justification in `routing_metrics.jsonl`. Not all layers are required to provide positive evidence; absence is valid input. |
| INV-26 | Hub-Enforced Policy: Governance rules (including COLLAB_RATE and consensus verification) must be enforced programmatically by `hub.py`, not left to peer self-discipline. |
| INV-27 | Relay Fidelity: Inter-peer message routing must guarantee lossless transcription and zero semantic modification of payloads. |
| INV-28 | Quorum Authority: Active consensus rounds require quorum = `max(2, f(N, risk))` where N is the count of gate-OPEN eligible voters at round-start, and f is a risk-adjusted function (undefined above N=3; default to N). At least one non-proposing voter from a distinct failure domain must actively `agree`. Proposer MUST NOT self-finalize. |

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
| PRO-15 | ag requires the PTY adapter on Windows. Governance equality is independent of adapter-specific permission flags; DIR-002 remains authoritative. |

### Effect Surface Prohibitions (D-02g, D-06g)
| ID | Rule |
|----|------|
| PRO-17 | NEVER allow writing side-effects to files or executing commands on target peers during inter-peer routing unless explicitly authorized by a governance write profile. |
| PRO-18 | NEVER violate 5-channel effect surface isolation (no local temp write, no governance write, no workspace write, no process mutation, no external I/O) when executing under the `--read-only` flag. |

### Transport-Role Enforcement (PRO-19)
| ID | Rule |
|----|------|
| PRO-19 | NEVER allow the terminal/router peer to mutate governance or room state — consensus rounds/votes, `handoff.md`, leader/coordinator claims, directives, `protocol.json`, or any `_sys/` artifact. The terminal is a **mechanical transport**: it relays asks and routes to worker peers; it is NOT an author, voter, or coordinator. All state mutation MUST be performed by an identified worker peer through a governance-write profile. Tier-0 human authority is unaffected (human override remains supreme, INV-03). |

> **PRO-19 implementation status (target floors — NOT YET ENFORCED).** The intended controls are: (1) carry an authenticated `originator` identity and exclude terminal/router identities from voter and proposer rolls; (2) require a governance-write profile at or above `effort` for governance mutations; and (3) guard every mutating transport path programmatically. Current `hub.py` does not implement these three controls completely; PRO-19 therefore remains policy-governed pending a dedicated INV-26 enforcement change. Derived from the "Resetting blocked consensus and taking over" incident.
