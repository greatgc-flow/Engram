# Collaboration MECE Review

Date: 2026-06-12

This review consolidates local code inspection and peer input from `cc`, `ca`, `gc`, and `ag`. The purpose is to evaluate collaboration efficiency, P2P communication limits, shared artifact editing, and a closed feedback loop for improvement items.

## Executive Summary

The current collaboration system is materially stronger than before because it now has health-aware peer asks, large mailbox payload offload, operational preflight rules, role-based peer routing, runtime communication policy, feedback tracking, artifact metadata, and traceability mapping. Remaining gaps are mostly outside hub enforcement: direct out-of-band file writes, full heartbeat leasing, root temp-file cleanup, and broader protocol-to-test coverage beyond the current hub suite.

## 1. P2P Communication Without Message or Time Limits

### Current State

| Dimension | Current support | Notes |
|---|---|---|
| Sync `ask` time limit | Implemented | Default timeout and PTY lease are configured in `protocol.json["runtime"]`; explicit `--timeout` can override. |
| Async `send` size limit | Good | `action_send()` offloads messages over `_LARGE_PAYLOAD_THRESHOLD` to `.ai/payloads/*.json` and sends `payload://...`. |
| Sync `ask` output size handling | Implemented | `ask --quiet` and `ask --output-file` support programmatic/file-based output. |
| Health precheck | Partial | `_ask_health_precheck()` blocks `RED` or `gate_open == false` before model call. YELLOW avoidance, fallback routing, and heartbeat while running are not implemented. |
| Failure recording | Good | ask success/failure updates peer health. Operational errors can now be recorded separately. |
| Long-running progress detection | Weak | No heartbeat/lease protocol for a peer that is alive but slow. |

### Peer Consensus

- `cc`: Unlimited size is useful, but unlimited time can deadlock. Needs config-driven timeout, health routing, and file references for large content.
- `ca`: Directly unlimited time is risky. Distinguish IPC timeout from consensus timeout and add health-aware skip/fallback.
- `gc`: Large payload offload is the right direction. `collab_rate` still needs runtime enforcement.
- `ag`: No hard size limit is acceptable only through offload. No hard time limit is undesirable without heartbeat and lease expiry.
- `cx`: The safest model is "unbounded semantic discussion, bounded transport leases." Large messages should become files; long tasks should renew a heartbeat rather than block forever.

### Implemented Policy

The agreed policy is now represented in `protocol.json`:

1. `runtime.ask_default_timeout_sec`: configurable ask timeout.
2. `runtime.pty_lease_sec`: configurable PTY lease.
3. `communication_policy.large_content_strategy`: file references for large content.
4. `communication_policy.heartbeat_sec` and `lease_timeout_sec`: declared policy for long-running work.

This gives the user effectively unlimited collaboration semantics without unbounded blocked transport.

## 2. Shared Artifact Collaboration (`Result.md`)

### Current State

The hub protects internal state files with `filelock`, including mailbox, state, handoff, nodes, and consensus files. It does not protect arbitrary workspace files edited directly by peers. Therefore, a single artifact such as `Result.md` can still suffer from last-writer-wins overwrite, stale context edits, or unreviewed direct mutation.

### MECE Workflow Options

| Pattern | When to use | Strength | Weakness |
|---|---|---|---|
| Single owner / designated merger | Most shared documents | Simple and safe | Slower than parallel direct edits |
| Section-owned drafts | Long reports with independent sections | Parallelizable | Needs final integration |
| Patch proposal files | Code-like review, contentious docs | Reviewable | More overhead |
| Artifact lock | High-risk shared file writes | Prevents overwrite | Requires tooling and stale lock cleanup |
| Git branch/merge | Large multi-file artifact work | Strong audit trail | Heavyweight for quick docs |

### Recommended Default

For one shared artifact:

1. Decide artifact owner and final merger in consensus or handoff.
2. Non-owners write section drafts to separate files, for example `.ai/artifacts/Result.gc.md`.
3. Owner merges into `Result.md`.
4. Peers review the final artifact by `context-hash` or file hash.
5. Owner records result path, reviewers, and hash in handoff.

### Implemented Metadata

Hub-supported artifact metadata is now available through `artifact-claim`, `artifact-status`, and `artifact-finalize`:

```json
{
  "artifact": "Result.md",
  "owner": "gc",
  "mode": "single_owner_merge",
  "drafts": {
    "cc": ".ai/artifacts/Result.cc.md",
    "ca": ".ai/artifacts/Result.ca.md"
  },
  "status": "claimed|draft|review|finalized|abandoned",
  "hash": "sha256:..."
}
```

Direct file writes outside hub remain technically possible, so governed artifacts should use this metadata workflow and peer review by hash.

## 3. Closed Feedback Loop for Improvement Items

### Current State

Improvements are currently scattered across chat, `handoff.md`, docs, and peer outputs. The protocol says `observe -> classify -> decide -> sync -> act_or_ask -> record -> handoff -> improve`, but the `improve` step does not yet have a durable structured store.

### Implemented Feedback Loop

Use the structured append-only backlog configured by `protocol.json["feedback_loop"]`:

Path:

```text
.ai/feedback.jsonl
```

Schema:

```json
{
  "id": "GAP-20260612-001",
  "ts": "2026-06-12T00:00:00",
  "source_peer": "cx",
  "category": "protocol|runtime|test|doc|hygiene|model-routing",
  "severity": "high|medium|low",
  "title": "collab_rate is not fully runtime enforced",
  "evidence": ["_sys/ai/protocol.json", "_sys/core/hub.py"],
  "status": "open|accepted|in_progress|done|rejected",
  "next_action": "proposal|implementation|test|doc",
  "owner": null
}
```

Implemented hub actions:

- `feedback-add`
- `feedback-list`
- `feedback-resolve`

### Skill or Tool?

Peers split on this, but the practical answer is both:

- Tool first: hub actions should own durable state and validation.
- Skill second: a `propose-improvements` or `kaizen` skill can help peers phrase high-quality entries, deduplicate them, and propose policy patches.

The skill should not be the source of truth. The JSONL backlog should be.

## 4. Known Gaps With Priority

| Priority | Gap | Current risk | Recommended action |
|---|---|---|---|
| P0 | Direct out-of-band file writes | Hub cannot fully enforce tools that bypass it | Policy-governed; use artifact workflow and future audit tooling |
| P1 | Full heartbeat leasing | Long-running work declares heartbeat policy but lacks a complete lease sweeper | Add heartbeat renew/sweep actions if long asks become common |
| P1 | Root temp files | Workspace hygiene issue | Identify producer and add cleanup/generation fix |
| ~~P1~~ | ~~Broader protocol-to-test map~~ | ~~Traceability map exists, but not every protocol paragraph maps to tests~~ | **RESOLVED 2026-06-13**: `traceability_map.json` v1.1 — 14 entries covering all v4.1 protocol features (semi-governed, peer-status, model-profile-validation, ask-provenance, routing-metrics, virtual-nodes, lifecycle-policy). |
| ~~P1~~ | ~~External peer artifacts~~ | ~~Important reports can land outside workspace~~ | **RESOLVED 2026-06-13**: `_is_workspace_local()` added to hub.py; `artifact-status` (draft) and `artifact-finalize` emit `[HUB:WARN]` for external paths. 8 tests in `TestArtifactWorkspaceLocal`. |
| ~~P2~~ | ~~`state_actions` partially generic~~ | ~~Lifecycle policy looks more declarative than it is~~ | **RESOLVED 2026-06-13**: `lifecycle_policy.json` v1.0 fully declarative; hub.py reads via `_load_lifecycle_policy()`. |
| ~~P2~~ | ~~Model-specific virtual nodes~~ | ~~`model_profiles` convention exists, but example nodes are not yet added~~ | **RESOLVED 2026-06-13**: `cc-deep` and `gc-plan` virtual nodes added to `orchestration.json`. `profile_id` field links nodes to `model_profiles.json`. |
| ~~P3~~ | ~~Taxonomy root links weak~~ | ~~Maturity docs are discoverable but not central~~ | **RESOLVED 2026-06-13**: README.md "Configuration and Audit Maps" updated — TAXONOMY_v10.md, model_profiles.json, status_checks.json, collaboration_loop_bindings.json all linked. |

## 5. Recommended Implementation Order

1. Add heartbeat renew/sweep only if real long-running asks need it.
2. Identify the producer of random root temp files before cleanup.
3. Expand `traceability_map.json` as protocol sections gain tests.
4. Add virtual nodes for model profiles when exact supported model flags are stable.
5. Add artifact locks only if owner/draft/finalize metadata proves insufficient.

## 6. Effectiveness Improvement From Recent Collaboration Changes

| Area | Improvement |
|---|---|
| Role routing | Queries were sent to peers by specialty instead of broad undirected discussion. |
| Health safety | RED/gate-closed peers are blocked before ask, reducing wasted calls. |
| Large async content | Mailbox messages can offload to payload files. |
| Operational mistakes | Preflight rules now classify shell mismatches and risky commands. |
| Traceability | Connectivity maps and `traceability_map.json` make implicit gaps visible. |
| Consensus quality | Peer disagreements surfaced real implementation gaps instead of being hidden by a single summary. |
| Feedback durability | `feedback-*` actions preserve improvements outside transient chat. |
| Artifact safety | `artifact-*` actions track owner, drafts, final path, and hash. |

The system is now better at detecting, discussing, recording, and routing problems. The next maturity step is broadening automated audits around direct file writes, heartbeat leases, and full protocol coverage.
