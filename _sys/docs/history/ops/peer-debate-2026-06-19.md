# Peer and Profile Architecture — Exhaustive Debate

**Date:** 2026-06-19
**Participants:** cc, ag, and cx
**Audit scope:** cc, ca, gc, ag, cx and every configured model/profile node
**Status:** FINAL — cc `AGREE`, ag `AGREE`, cx `AGREE`

## 1. Outcome

The runtime configuration now distinguishes four concepts:

1. **Installation** — a locally installed CLI/provider family in `peers.json`.
2. **Peer** — an independent root worker identity such as `cc`, `ag`, or `cx`.
3. **Profile** — a model and performance option set owned by one peer.
4. **Node** — a routable runtime instance. Root IDs remain stable; profile nodes use
   `{peer}.{profile}`.

The term **virtual peer** is retired. `cc-deep` and `gc-plan` are deleted. The
tracked topology contains root peers only; `standard`, `effort`, and `deepthink`
children are generated in memory.

## 2. Findings Ledger

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| F-01 | HIGH | Physical peers and virtual variants were mixed in one flat array. | Nested profiles and deterministic normalization. |
| F-02 | HIGH | `peers.json`, `orchestration.json`, and `model_profiles.json` duplicated model decisions. | `peers.json` is installation-only; `orchestration.json` is runtime SSOT; independent `model_profiles.json` removed. |
| F-03 | HIGH | Model facts contained inferred/nonexistent entries and stale prices/limits. | Registry rebuilt from official vendor facts; unknown values omitted. |
| F-04 | HIGH | Gemini lifecycle used both `enabled` state and a legacy `status.json` gate. | Gate removed; lifecycle plus live health is authoritative. |
| F-05 | HIGH | Static status declarations disagreed with live state. | `status_checks.json` now defines probes only. |
| F-06 | HIGH | Governance equality was conflated with identical full-danger flags. | Equal voting/leadership/role rights are separate from CLI capability mappings. |
| F-07 | MEDIUM | Context sharing was described as shared memory. | Context is an explicit envelope plus durable references and promotion/ACK. |
| F-08 | MEDIUM | Adding a profile required edits in multiple files. | A profile is added once under its root peer. |
| F-09 | MEDIUM | Human interface and worker/coordinator identities were conflated. | Human terminal is a thin client; worker sessions and coordinator role are independent. |
| F-10 | MEDIUM | General and Specific docs contained stale statuses and permission claims. | Pattern contract and peer-specific deltas updated. |
| F-11 | MEDIUM | Runtime files could be accidentally tracked despite ignore rules. | Git hygiene contract and tracked-runtime test added. |
| F-12 | LOW | Independent cx review invocation hit account usage limits. | Failure recorded; cx review completed in the active cx session and cross-reviewed by ag. |
| F-13 | HIGH | Suspend/resume overwrote child-local profile routing state. | Lifecycle now changes the root only; effective disablement is inherited. |
| F-14 | HIGH | Default-profile fields could leak into sibling generated profiles. | Every child is generated from a pristine root base before profile overlay. |
| F-15 | HIGH | Resume restored execution but not voter/role membership. | Lifecycle command synchronizes active/inactive voters and role registries in both policy stores. |
| F-16 | MEDIUM | Repeated hot-path normalization performed avoidable reads and deep copies. | File-mtime raw cache and retained-source normalized cache added. |

## 3. Debate and Dissent Resolution

### 3.1 Registry shape

- **cx proposal:** one logical manifest per root peer.
- **ag objection:** the repository is small enough that per-peer files add I/O and
  fragment the source of truth.
- **Decision:** one centralized logical manifest in `orchestration.json`, with one
  nested profile map per root. Installation concerns remain separate in
  `peers.json`.

### 3.2 Permissions

- **cx proposal:** capability classes must not be equated with full-danger flags.
- **ag objection:** migration must preserve active DIR-002 mappings.
- **Decision:** preserve current DIR-002 invocation mappings in this migration.
  Define equality as equal governance rights and equivalent declared task scope.
  The conflict between minimum-scope requirements and bypass-based CLI mappings is
  explicit policy debt requiring empirical sandbox testing and a separate governed
  change.

### 3.3 Final Cross-Review

- **ag finding:** parent lifecycle commands mutated child-local profile state and
  normalization allowed default-profile option leakage.
- **cc finding:** resume restored execution without restoring governance membership;
  lifecycle tests checked raw JSON but not effective routability.
- **Resolution:** all findings were reproduced with failing tests, fixed, and
  independently re-reviewed. cc and ag both returned `AGREE`.

## 4. Canonical Runtime Contract

```text
Installation (peers.json)
  └─ Peer (orchestration.json root)
       ├─ peer.standard
       ├─ peer.effort
       └─ peer.deepthink
```

Effective routability is:

```text
known node
AND local enabled != false
AND routing_state != blocked
AND every ancestor is effectively routable
AND no missing parent or cycle
```

Parent disablement does not mutate child-local state. Re-enabling a parent restores
children except those locally disabled or blocked.

## 5. Context and Collaboration

Peers do not share hidden model memory. They collaborate through:

- `.ai/state.json`
- `.ai/sessions/{room_id}/handoff.md`
- mailbox/thread/proposal/checkpoint records
- versioned query envelopes and file references

Outputs become shared state only after an explicit durable write, promotion, or
context acknowledgement. Credentials are never forwarded.

## 6. Interface and Worker Separation

The user may enter through any peer terminal. That terminal is the fixed
**human-interface peer** for the session and performs only framing, forwarding, and
concise synthesis when another worker is selected.

The **active coordinator** is a task role, not a superior peer. It may rotate among
eligible peers based on health, capability match, continuity, and cost. Worker
sessions are peer-owned and independent from the interface terminal. Forwarding is
single-hop and reference-based to avoid paying one model to relay another model's
full context.

## 7. Governance and Permission Parity

All active peers have:

- equal vote weight;
- equal eligibility for leadership and all collaboration roles;
- equal ability to propose, object, verify, and communicate with the human;
- the same lifecycle, context, audit, and consensus protocol.

Execution flags may differ because CLI permission systems differ. Every mapping must
declare a capability class and pass parity tests. Identical dangerous flags are not
a requirement for equality.

## 8. Status Model

Routine status is zero-token and combines:

1. configured lifecycle state;
2. executable presence and version probe;
3. recorded health and freshness timestamp;
4. recent invocation failures/rate limits.

Peer-specific legacy gate files are not authoritative. Disabled peers may still be
listed for diagnostics but are never routable.

## 9. Model Fact Policy

`model-registry.json` contains vendor facts with source, as-of date, and confidence.
Runtime CLI availability belongs to a profile and may be `unverified` even when the
vendor model exists. Unverified high-cost variants fail closed. ag model labels
were subsequently verified through PTY model discovery on 2026-06-20; see
`ops/automatic-profile-routing-2026-06-20.md`.

As of 2026-06-19:

- OpenAI: GPT-5.5, GPT-5.4, GPT-5.4-mini, o3, o3-pro.
- Anthropic: Claude Fable 5, Opus 4.8, Sonnet 4.6, Haiku 4.5. Fable 5 is
  documented but unavailable to the current cc account as of 2026-06-20.
- Google: Gemini 3.5 Flash stable, Gemini 3.1 Pro Preview, Gemini 3 Flash Preview,
  Gemini 2.5 Pro stable. Gemini 3 Pro Preview shut down on 2026-03-09.

## 10. TDD Matrix

| Area | Required coverage |
|---|---|
| Schema | Root-only tracked topology; exactly three standard profile names. |
| Normalization | Deterministic IDs, inherited adapter/invoke fields, no mutation of source. |
| Lifecycle | Root/child disable, recovery, local child block, missing parent, cycle, alias. |
| Routing | Blocked profiles excluded from defaults, fallback, voters, and role routes. |
| Invocation | Model/effort args per CLI; root uses default profile. |
| Context | Envelope version parsing, reference injection, ACK/promotion boundary. |
| Status | No model call; lifecycle + health freshness; no legacy gate dependency. |
| Governance | Equal active vote weight and role eligibility. |
| Permissions | Capability class present; hub/console DIR-002 parity. |
| Models | Every declared model exists in official registry; unknowns explicit. |
| Docs | General/Specific pattern and lifecycle status consistency. |
| Git | No tracked runtime health/status/session/IPC files. |
| Lifecycle CLI | Add/suspend/resume/remove dry-run and idempotency. |
| Provisioning surfaces | Add/remove synchronizes topology, installation mapping, probes, governance, roles, and Specific docs. |
| Governance lifecycle | Suspend/resume atomically updates active/inactive voters and all role registries. |
| Child state | Locally blocked profiles remain blocked across parent suspend/resume. |
| Profile isolation | Missing sibling options never inherit default-profile values. |

## 11. Benchmark Matrix

| Metric | Method | Acceptance |
|---|---|---|
| Normalize latency | 10,000 uncached and cached expansions | uncached median under 1 ms; cached under 0.1 ms |
| Routability latency | all nodes, repeated 10,000 times | median under 0.1 ms per check |
| Config size | tracked bytes before/after | no generated node file |
| Context envelope | serialized bytes by template | compact <= 800, standard <= 4,000 |
| Status latency | zero-token probes | no model invocation |
| Ask reliability | `routing_metrics.jsonl` | success, timeout, and rate-limit separated |
| Cost overhead | prompt envelope tokens | interface forwarding contains refs, not full history |

Measured on 2026-06-19 with 5 tracked roots and 20 normalized nodes:

- configuration size: 7,620 bytes;
- uncached normalization median: 0.256 ms, p95: 0.327 ms;
- cached normalization median: 0.008 ms, p95: 0.014 ms;
- full-tree routability median: 0.064 ms, p95: 0.090 ms.

## 12. Migration and Rollback

Migration preserves root IDs, adapters, and query-file compatibility. Profile IDs
change to `peer.standard|effort|deepthink`. Runtime generated nodes are not written
to Git.

Rollback is one commit because no runtime state migration is required. Existing
room/task records that reference root IDs remain valid. Old static child IDs are
intentionally not resurrected.

## 13. Acceptance Criteria

- `cc-deep`, `gc-plan`, and independent `model_profiles.json` are absent.
- Strict peer validator passes.
- Unit, integration, dependency, and portability checks pass.
- Live status does not read the Gemini status gate.
- No active routing rule references a missing or blocked profile.
- Two consecutive final review passes produce no HIGH finding.

## 14. Validation Evidence

- portable full suite: 745 unit + 9 integration tests passed;
- current environment unit suite: 765 tests passed;
- strict peer configuration validator: PASS, zero warnings;
- profile and permission parity validator: PASS;
- documentation MECE checks CHK-01 through CHK-07: PASS;
- dependency scan: exit 0;
- portability scan: exit 0, structured result `UNKNOWN` when the optional active
  analysis peer was unavailable;
- Git runtime hygiene: no tracked health/status/session/IPC/runtime log files.

## 15. Final Call

ag requested two DIR-002 clarifications and later identified lifecycle/profile
isolation defects. cc identified incomplete governance restoration and missing
effective-routability coverage. All were fixed through TDD. Final responses:
cc `AGREE` (no HIGH blockers), ag `AGREE` (no HIGH blockers), cx `AGREE`.
