# R10 Model Routing and Collaboration Reliability Consensus Draft

Status: FINAL
Owner: cx
Participants: cc, ca, gc, ag, cx
Source inputs:
- P:\_archive\mece-peer-status-and-continuity.md
- P:\workspace\plans\mece-r10-round1.md
- P:\plans\mece-peer-status-and-continuity.md
- P:\_sys\docs\leader-role-health-continuity.md
- P:\_sys\docs\collaboration-mece-review.md
- P:\workspace\DESIGN_REVIEW_MULTI_PEER.md

## 1. Shared Acknowledgement

All peers must first acknowledge the human request before implementation:

- Work under Collab_RATE=10.
- Use open-ended peer questions until there are no unresolved objections.
- Prefer no-code / declarative / composable design before code changes.
- Separate General policy from Specific peer/model details.
- Put ambiguous constants, ranges, enum values, and routing choices in JSON-config.
- Use files for long results and cite workspace-local paths.
- Keep interim ``, ``, ``, `` tags until final agreement.

## 2. Message Delivery Reliability

"Messages must always arrive" should be interpreted as durable delivery, not infinite blocking transport.

Proposed contract:

- Every `send` writes an append-only durable mailbox record with a unique id.
- Delivery means the message is durably recorded in `.ai/mailbox.json` or payload storage.
- Read acknowledgement is separate: recipient must mark-read or reply with ACK.
- Processing acknowledgement is separate: recipient confirms it understood or asks questions.
- Large messages must be stored as payload files and referenced by `payload://...` or workspace-local paths.
- Mailbox writes must be serialized by hub lock; concurrent sends should retry with bounded backoff instead of failing immediately.
- Handoff/init/checkpoint messages are governance state, but not semantic decisions; they should bypass R10 consensus while still being logged.

Need peer agreement on exact delivery states:

- `queued`
- `delivered`
- `read`
- `acknowledged`
- `acted`
- `failed`

## 3. Init, Handoff, and Continuity Exemptions

Init/handoff/continuity actions should be exempt from finalized consensus only when they do not decide policy or mutate project implementation.

Exempt action class:

- session start/end
- peer recovery notices
- health update/report
- append handoff factual notes
- task checkpoint
- mailbox send/broadcast
- status read/validation

Governed action class:

- protocol changes
- implementation changes
- config changes that alter future behavior
- role or leader changes that affect execution authority, unless emergency recovery is required

Need decide whether `leader-claim`, `assign-role`, and `health-sweep` are normal exempt continuity actions or governed routing changes.

## 4. General-Specific MECE Structure

Proposed layer split:

- General schema: valid concepts, state machines, enums, required fields, invariants.
- Specific profile: peer, model, CLI, connector, path, auth indicator, limits, cost, tool affordances.
- Binding map: JSON file that connects General task taxonomy to Specific peer/model profiles.
- Runtime state: current room, health, role assignment, message state, task registry.
- Evidence log: routing decision, health observation, consensus result, review result.

Candidate files:

- `_sys/ai/protocol.json`: General policy and invariants.
- `_sys/ai/orchestration.json`: node invocation and role routing bindings.
- `_sys/ai/model_profiles.json`: Specific model capabilities, cost tiers, modes, context, tools.
- `_sys/ai/status_checks.json`: declarative health/auth/status check definitions.
- `.ai/state.json`: runtime state.
- `.ai/task_registry.json`: task continuity.
- `.ai/mailbox.json`: durable message queue.

Need decide whether to create new JSON files or extend existing `protocol.json` and `orchestration.json` only.

## 5. Peer and Model Status

Replace per-peer status bat scripts as the default with a declarative checker engine.

General status dimensions:

- installed: binary/tool present.
- authenticated: usable credentials/session exist.
- rate_state: ok, limited, exhausted, unknown.
- context_state: green, yellow, red, stale.
- gate_state: open, degraded, closed.
- tool_state: local_files, shell, web, connector, pty, none.
- evidence: observed command, file, timestamp, exit code, sanitized detail.

Specific check examples:

- Codex: `codex --version`, auth/session status if CLI exposes it, config existence without credential leakage.
- Gemini: existing status.json gate and CLI model listing if available.
- Claude: session limit/auth hints from health.json and CLI status if available.
- Antigravity: agy binary/config availability and PTY viability.

Need confirm which CLI commands safely expose model/auth/status without leaking credentials or consuming significant quota.

## 6. Sub-Model and Model-Unit Routing Strategy

Model-unit routing should be represented separately from peer identity.

MECE model profile fields:

- provider: openai, anthropic, google, local, other.
- peer: cx, cc, ca, gc, ag, virtual node id.
- model_id: exact model name if discoverable.
- mode: default, fast, deep, high_reasoning, web_enabled, tool_enabled.
- context_window: tokens or unknown.
- output_limit: tokens or unknown.
- cost_tier: low, mid, high, unknown.
- latency_tier: low, mid, high, unknown.
- reasoning_depth: low, medium, high, unknown.
- tool_affordances: files, shell, web, connectors, pty, image, none.
- strengths: code, review, planning, research, summarization, validation, cleanup.
- weaknesses: hallucination risk, low context, weak tool use, high cost, rate limit risk.
- status_source: cli, docs, config, empirical, unknown.
- confidence: observed, documented, inferred, unknown.

Task taxonomy:

- coordination
- consensus framing
- implementation planning
- code mutation
- test authoring
- verification
- large corpus research
- web/doc research
- summarization/compaction
- mailbox/handoff hygiene
- status/health checking
- security/auth-sensitive operation

Routing decision inputs:

- task taxonomy
- required capabilities
- risk level
- context size
- desired reasoning depth
- tool requirements
- peer health
- model rate/quota state
- token/cost budget
- continuity owner
- human interface peer

Need peer agreement on whether dynamic runtime `--model` / `--effort` overrides are safer than static virtual nodes such as `cx-fast`, `gc-deep`, `cc-review`.

## 7. Model Metadata and Q/A Provenance

For every peer ask/reply, record enough provenance to interpret the answer:

- peer id
- model profile id if known
- effort/mode if known
- tools enabled
- context references supplied
- output file path if used
- health state at ask time
- elapsed time
- failure/retry info
- confidence source: declared, discovered, inferred

Purpose:

- Identify whether an answer came from a high-context/deep mode or a low-cost mode.
- Decide whether follow-up verification is required.
- Improve routing metrics over time.

Need decide where to store this: mailbox metadata, routing_metrics.jsonl, task_registry checkpoints, or a new ask_history.jsonl.

## 8. Coordinator and Role Reassignment

Coordinator peer and coordinator model should be changeable by policy.

Rules:

- Human interface peer can stay fixed while active coordinator changes.
- Active coordinator should not change mid-task unless health/rate/context fails or task type changes materially.
- Low-tier models may coordinate only bounded hygiene/status tasks, not R10 semantic decisions.
- High-tier/deep modes should be reserved for constitutional decisions, complex architecture, or deadlock resolution.
- Coordinator failover must record a checkpoint before role transfer.

Need define leader churn guard:

- max re-elections per time window
- cooldown seconds
- fallback if all candidates degraded

## 9. Minimal Protocol for Low-Intelligence Models

Define a compact protocol envelope that even weak models can follow:

```text
TASK:
INPUT_REFS:
DO:
DO_NOT:
OUTPUT:
ACK_REQUIRED:
```

Constraints:

- no nested policy explanation
- no full transcript
- explicit allowed actions
- explicit forbidden actions
- short output schema
- route back to coordinator on ambiguity

Need test this envelope against low-cost/fast modes once model access is discoverable.

## 10. Compliance and Collaboration Quality Metrics

Measure understanding and execution, not just output.

Metrics:

- acknowledgement rate
- instruction adherence rate
- consensus participation latency
- unsupported-action attempt count
- handoff completeness score
- evidence citation rate
- correction rate after peer review
- token/cost per accepted decision
- routing success rate by model profile
- stale/failed message recovery rate

Need decide acceptance thresholds and where to store measurements.

## 11. Closed Feedback Loop

Proposed loop:

1. Observe current state and user request.
2. Classify task, risk, model needs, and required peers.
3. Ask open questions to all required peers.
4. Consolidate into tagged draft.
5. Resolve objections or record open items.
6. Vote / final call under R10.
7. Implement only agreed non-code/config/docs changes.
8. Test and cross-review.
9. Record evidence and update feedback backlog.
10. Return to step 1 until no peer has additions or blockers.

Need decide whether this loop is documented as protocol text, JSON policy, or both.

## 12. Current Round 2 Consensus Candidate

Candidate decision:

Adopt a no-code-first declarative design for peer/model status and model-unit routing:

- Do not implement new per-peer `.bat` status scripts as the primary approach.
- Prefer a declarative checker config plus a general existing hub/runtime interpreter.
- Represent sub-models as model profiles decoupled from peer identity.
- Use static virtual nodes only when CLI runtime model override is unavailable or unsafe.
- Treat message delivery as durable queue + ACK state machine, not guaranteed immediate processing.
- Exempt init/handoff/checkpoint factual continuity records from R10 finalized consensus.
- Keep semantic decisions, protocol/config behavior changes, and implementation changes under R10.

Round 2 question for peers:

What objections, missing categories, unsafe assumptions, or better alternatives remain before this candidate can move to Final Call?

## 13. Round 2 Objections and Resolutions

Round 2 peer responses from cc, ca, and ag produced blockers. gc timed out on Round 2 and must be asked again after this draft.

### 13.1 Message Storage and Delivery

Single-file `.ai/mailbox.json` remains the current implementation, but the target design should move toward a Maildir-like mailbox for concurrency:

- active design target: `.ai/mailbox/msg-{uuid}.json`
- compatibility bridge: keep `.ai/mailbox.json` until migration is implemented
- delivery state target: `sent`, `acked`, `completed`, `failed`
- TTL field: `expires_at` or `ttl_sec`
- payload reference: workspace-local file path or `payload://{id}` only if the resolver is defined

For now, "guaranteed arrival" means:

- hub command exits 0 only after durable local write succeeds
- sender can later verify by message id
- recipient ACK is a separate state
- timeout/lock failure must be visible and retryable

### 13.2 Exemption Boundary

Factual continuity actions are exempt from finalized R10 consensus:

- `send`
- `broadcast`
- `init-session`
- `end-session`
- `append-handoff` for factual notes only
- `append-log`
- `checkpoint`
- `task-checkpoint`
- `health-update`
- `peer-recover`
- read/status/check actions

Governance-sensitive routing actions are semi-governed:

- `leader-claim`
- `assign-role`
- `release-role`
- `task-failover`
- `health-sweep` when it mutates state

Semi-governed rule:

- emergency failover is exempt only when current coordinator or role holder is `RED`, `STALE`, missing, or rate-limited
- normal elective change requires visible proposal and peer verification
- all semi-governed changes must write an audit record

Strictly governed actions remain under R10:

- protocol behavior changes
- config behavior changes
- implementation changes
- voter list changes
- policy changes
- role/leader changes that are elective rather than recovery

### 13.3 Existing Config Conflicts

Existing `protocol.json` values are treated as current source of truth unless this consensus explicitly changes them.

Known alignments:

- `leader_election.cool_down_seconds = 300` is accepted as the churn cooldown.
- `leader_election.yield_failure_threshold = 3` is accepted as failover pressure.
- `leader_election.health_stale_minutes = 120` is accepted as current stale threshold.
- existing `prompt_templates.compact` remains the base compact envelope.

Compact envelope should align with existing config:

```text
TASK:
INPUT_REFS:
CONSTRAINTS:
DO:
DO_NOT:
OUTPUT_SCHEMA:
ACK_REQUIRED:
```

For low-tier models, prefer strict flat JSON output with `allowed_actions` and `forbidden_actions` enums instead of free-form `DO_NOT` interpretation.

### 13.4 Model Status Fields

Avoid overlapping `rate_state` and `gate_state`.

Proposed separation:

- `rate_state`: quota/request ability only: `ok`, `limited`, `exhausted`, `unknown`
- `auth_state`: `authenticated`, `unauthenticated`, `expired`, `unknown`
- `context_state`: `green`, `yellow`, `red`, `stale`, `unknown`
- `gate_state`: derived aggregate: `open`, `degraded`, `closed`

Rule:

- `gate_state` is derived from auth/rate/context/tool checks, not independently asserted unless a peer-specific gate file already exists.

### 13.5 CLI Safe Status Discovery

No peer may assume a CLI status/model-list command is safe until classified.

Safe discovery classes:

- `version_only`: command returns version only and should be no-quota.
- `local_config_presence`: checks file/directory existence without reading secrets.
- `declared_profile`: profile is manually configured from docs or observed behavior.
- `empirical_probe`: tiny prompt or noop that may consume quota; use sparingly.
- `unsupported`: no safe discovery known.

Each peer must report known safe commands for its CLI before implementation.

### 13.6 Virtual Nodes vs Dynamic Overrides

Adopt hybrid strategy:

- Use declared `model_profile` objects as the stable abstraction.
- Prefer dynamic CLI model/effort overrides only when the CLI supports them safely and predictably.
- Use static virtual nodes when dynamic override is unavailable, unsafe, or session-state-sensitive.
- Store exact command binding in orchestration-specific config, not in General policy.

### 13.7 Provenance and Metrics Storage

Keep active state small.

Storage decision candidate:

- `.ai/ask_history.jsonl`: ask/reply provenance and routing decision facts.
- `.ai/routing_metrics.jsonl`: machine-readable routing events and success/failure.
- `_archive/compliance_metrics.jsonl`: post-session aggregate metrics.
- `.ai/task_registry.json`: only current task checkpoints, not full ask history.
- `.ai/mailbox*`: message transport, not analytical history.

Initial metrics:

- acknowledgement_rate
- routing_success_rate
- correction_rate_after_review
- human_interface_redirect_rate

Deferred metrics:

- exact token/cost per accepted decision unless exposed by CLI or reliable logs.

### 13.8 Coordinator Churn Guard

Adopt existing config defaults as current proposal:

- elective coordinator shift cooldown: 300 seconds
- max re-elections per query: 3
- if exceeded: ask human interface peer for direction
- if all candidates degraded: human interface peer coordinates a minimal recovery question
- phase handoff allowed: planning -> implementation -> verification, with checkpoint

### 13.9 CA Membership

`ca` is now registered into `room-26ab` to align active room membership with the R10 voter set.

Rule candidate:

- R10 voters should be active room members.
- R10 voter status is tied to room membership, not active task role.
- A peer in `observer` role still votes under R10 if it is a room member and protocol voter.
- If protocol voters and room members diverge, the coordinator must either register the missing peer or explicitly escalate to the human before Final Call.

### 13.10 Delivery Durability During Migration

Until Maildir-like storage exists, current `mailbox.json` delivery must obey the stricter contract:

- hub `send` exits 0 only after the local durable write succeeds.
- lock timeout or write failure is a failed delivery, not a silent success.
- sender must be able to retry and verify by message id.
- migration to Maildir-like storage must preserve backward compatibility with existing `check` and `mark-read`.

## 14. Round 3 Consensus Candidate

Candidate decision for Final Call after gc re-review:

1. Adopt durable delivery as `sent -> acked -> completed/failed`, with future Maildir-like storage to reduce lock contention.
2. Exempt factual init/handoff/checkpoint/health messages from finalized R10 consensus, while prohibiting semantic decisions or implementation directives from being smuggled into handoff notes.
3. Classify leader/role/task failover as semi-governed: exempt only for recovery from RED/STALE/rate-limited/missing coordinator, otherwise visible proposal and peer verification.
4. Use General-Specific layering: General policy in protocol config, Specific peer/model/connector bindings in orchestration/profile config.
5. Prefer a declarative status checker engine over per-peer status scripts as the target design.
6. Decouple peer identity from model profiles; use hybrid dynamic override plus static virtual node strategy.
7. Store ask provenance and routing metrics in append-only logs, not main state.
8. Use strict compact envelopes and JSON-schema outputs for low-tier models, with escalation after repeated schema failure.
9. Use existing churn defaults: 300 second cooldown, 3 re-elections per query, then human-interface fallback.
10. Require each peer to report safe model/status discovery methods before model profile implementation.

Round 3 question:

Do any peers still object to this candidate, or are there missing categories/unsafe assumptions that block Final Call?

## 15. Safe CLI Discovery Baseline

Status: POST-FINAL-CALL IMPLEMENTATION PREREQUISITE

Local and peer-reported safe discovery methods observed on 2026-06-12.

### 15.1 Codex / cx

Observed locally:

- `codex --version`: safe version command, returned `codex-cli 0.139.0`.
- `codex --help`: safe local help, exposes `--model`, `--search`, `--sandbox`, `--ask-for-approval`, `--profile`, `doctor`, `features`, `mcp`.
- `codex doctor`: useful status command but may perform network reachability checks; classify as low-quota diagnostic, not pure local read.

Current findings:

- configured model: `gpt-5.5` via local config
- auth configured: ChatGPT token present
- websocket failed; HTTP reachability failed in current environment
- state DB check partly failed for goals/memories DB
- version command emitted temp cleanup/PATH alias permission warnings

Routing implication:

- cx should be treated as `YELLOW` until state DB/reachability warnings are resolved.
- `codex --version` and `codex --help` are safe.
- `codex doctor` is allowed as diagnostic but should not be run on every message.
- model listing is not confirmed as safe; use declared profile until official/local safe method is found.

### 15.2 Claude / cc and ca

Observed locally:

- `claude --version`: safe version command, returned `2.1.170 (Claude Code)`.
- `claude --help`: safe local help.
- `claude auth status`: safe auth/status command in this environment; returned logged-in first-party Claude.ai Pro account metadata.

Confirmed help flags:

- `--model <model>`: model override.
- `--effort <low|medium|high|xhigh|max>`: effort override.
- `--fallback-model <model>`: fallback list, print mode only.
- `--permission-mode <default|acceptEdits|auto|dontAsk|plan|bypassPermissions>`.
- `--json-schema`: structured output validation.
- `--tools`: tool availability selection.
- `--print`: non-interactive prompt, quota-consuming.

Routing implication:

- version/help/auth status are safe local discovery.
- prompt/print calls consume quota.
- model list is not dynamically discovered by CLI; use declared profile plus official documentation or manually verified config.
- web/search is not a simple CLI flag in local help; treat web tools as harness/session affordances, not baseline CLI capability.

### 15.3 Gemini / gc

Observed locally:

- `gemini --version`: safe version command, returned `0.46.0`.
- `gemini --help`: safe local help.

Confirmed help flags:

- `--model`: model override.
- `--prompt` / `--prompt-interactive`: quota-consuming.
- `--approval-mode <default|auto_edit|yolo|plan>`.
- `--sandbox`.
- `--list-sessions`: local session listing.
- `--output-format <text|json|stream-json>`.
- `gemini mcp`, `gemini extensions`, `gemini skills`, `gemini hooks`, `gemini gemma`.

Peer-reported:

- `_sys\gemini\gemini-status.bat` is current local status checker.
- `gemini --list-sessions` is safe local discovery.
- ping prompt such as `gemini -p "ok"` consumes quota and should be optional.
- no confirmed safe remote model list command.

Routing implication:

- use `--model` only with declared profiles.
- use `--approval-mode plan` for read-only planning.
- treat prompt modes as quota-consuming.

### 15.4 Antigravity / ag

Observed locally:

- `agy --version`: safe version command, returned `1.0.7`.

Peer-reported:

- direct `agy.exe models` / wrapper `agy.bat models` appeared to hang or behave like a prompt in exploration.
- unknown subcommands may consume quota or block.

Routing implication:

- `agy --version` is safe.
- model/status discovery beyond version is unsupported until a safe command is proven.
- ag should use declared profile and existing health.json until a no-quota checker is defined.

## 16. Final Call Result

Final Call was issued to cc, ca, gc, and ag against Round 3.

Results:

- cc: Proceed.
- ca: Proceed; no P0/P1 blocker.
- gc: Proceed.
- ag: Proceed.
- cx: Proceed as proposer/implementer.

Consensus status:

- R10 design consensus is finalized for the no-code-first architecture and discovery prerequisites.
- Implementation must still respect the agreed prerequisite: safe status/model discovery methods must be recorded before model-profile/config implementation.

