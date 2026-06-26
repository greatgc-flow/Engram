# Automatic Profile Routing Decision

**Date:** 2026-06-20

**Participants:** cx, cc, ag
**Status:** FINAL

## 1. Outcome

Peer terminals now start with the lowest-cost verified `standard` profile.
Requests sent through `hub.py ask --to <root-peer>` are classified before model
invocation and routed to `standard`, `effort`, or `deepthink`.

Explicit targets such as `cx.deepthink` are immutable and bypass classification.
The classifier is deterministic, local, zero-token, and configuration-driven.

## 2. Debate Record

### cx position

Use `standard` for terminal framing and transport. Escalate only the worker call.
Keep root peer identity stable and route root asks to generated profile children.

### ag position

Accepted deterministic classification, profile-scoped sessions, audit records,
and fail-closed behavior. ag proposed horizontal fallback to another peer when a
profile is blocked.

### cc position

Accepted deterministic routing but raised a HIGH concern that a low-cost
interactive terminal can miss complex intent. cc recommended retaining `effort`
for the human-facing terminal and limiting classification to IPC.

### Final decision

The explicit user requirement to make terminal defaults low-cost takes
precedence. The quality risk is mitigated by:

1. ambiguous root asks defaulting to `effort`, not `standard`;
2. complex multilingual requests using language-independent shape signals;
3. explicit `[PROFILE:<name>]` and `[RISK:<0-10>]` tags;
4. direct `peer.profile` targeting remaining immutable;
5. failure feedback promoting at most one tier per request;
6. blocked selections falling downward only within the same peer.

Horizontal fallback was rejected at this layer because silently changing peers
changes identity, provider, memory, and permission semantics. Cross-peer failover
remains a separate coordinator policy.

## 3. Runtime Flow

```text
Request
  -> explicit peer.profile? -> preserve
  -> deterministic signal scoring
  -> requested profile
  -> same-peer eligibility check
  -> downward fallback if blocked
  -> profile-scoped session and invocation
  -> routing_metrics.jsonl audit event
```

The root peer remains the health, governance, and role identity. The selected
profile child controls model and reasoning options.

## 4. Signal Contract

Configuration source: `_sys/ai/routing-config.json["auto_profile_routing"]`.

| Source | Examples | Effect |
|---|---|---|
| Explicit metadata | `[PROFILE:deepthink]`, `[RISK:10]` | Deterministic override |
| Semantic markers | architecture, implement, status | Weighted score |
| Request shape | length, token count, list/code structure | Complexity evidence |
| Multilingual shape | non-ASCII ratio and delimiters | Language-independent complexity |
| Runtime feedback | consecutive failures | Promote one tier |
| Eligibility | enabled and not blocked | Same-peer downward fallback |

Thresholds:

- score below `3` with simple evidence: `standard`;
- score `3` through `7`: `effort`;
- score `8` or higher: `deepthink`;
- no decisive evidence: `effort`.

## 5. Terminal Defaults

Console wrappers read `standard.profile_args` from `orchestration.json`; model
choices are not duplicated in Python.

| Terminal | Default |
|---|---|
| cc | Claude Haiku 4.5, low effort |
| cx | GPT-5.4-mini, low reasoning |
| ag | Gemini 3.5 Flash (Low) |
| gc | disabled |

Management, help, and version commands are not modified. Explicit model or
reasoning options are not overwritten.

## 6. Failure and Fallback Rules

- Explicit `peer.profile`: never promote, demote, or substitute.
- Root target: classify every request.
- Two or more quality, test, or reasoning failures: promote one tier.
- Rate-limit, authentication, timeout, and CLI failures never promote.
- Blocked selected profile: try lower profiles in the same peer.
- All profiles blocked: fail closed with a visible error.
- Never change peer identity in the profile router.
- A profile change uses only that profile's session scope.

## 7. Audit Schema

Each decision writes an `auto_profile_route` event to
`.ai/routing_metrics.jsonl` with the requested target, selected node,
requested/selected profile, score, signals, confidence, explicit/classifier
flags, failure promotion, and fallback source.

## 8. TDD Coverage

Coverage includes simple, implementation, architecture, ambiguous, explicit,
risk-tag, failure-promotion, blocked, all-blocked, multilingual, terminal
override, hub integration, session isolation, audit payload, golden-set accuracy,
and latency cases.

## 9. Benchmark

Measured on 2026-06-20, 10,000 iterations:

| Metric | Median | p95 |
|---|---:|---:|
| Automatic profile classification | 0.018 ms | 0.044 ms |
| Cached topology normalization | 0.010 ms | 0.021 ms |
| Full-tree routability check | 0.117 ms | 0.206 ms |

The classifier adds no model call and remains below the 1 ms target.

## 10. Known Limits

1. A model already running in an interactive vendor CLI cannot replace itself
   mid-turn. It must delegate a complex subtask through the hub.
2. Heuristic classification is auditable but not equivalent to semantic model
   judgment. Ambiguity therefore defaults to `effort`.
3. ag model labels are account/runtime values returned by `agy models`, not
   stable vendor API model IDs. They must be revalidated after account, tier, or
   CLI-version changes.
4. Claude Fable 5 is documented and recognized by the CLI but unavailable to
   the current cc account, so deepthink remains Claude Opus 4.8.
5. Codex runtime catalog context can be smaller than the API model maximum.
6. Cross-peer selection and within-peer profile selection remain separate.

## 11. User Contract

Normal use requires no model selection:

```text
hub.py ask --to cx --query "<request>"
```

Optional hard overrides:

```text
hub.py ask --to cx.standard --query "<request>"
hub.py ask --to cx.deepthink --query "<request>"
hub.py ask --to cx --query "[PROFILE:deepthink] <request>"
hub.py ask --to cx --query "[RISK:10] <request>"
```

## 12. Final Validation and Review

- current environment unit suite: 790 passed;
- portable suite: 770 unit and 9 integration tests passed;
- strict peer validator: PASS with zero warnings;
- profile and permission parity: PASS;
- documentation MECE checks CHK-01 through CHK-07: PASS;
- dependency check: exit 0;
- portability check: exit 0 with structured analysis reported as `UNKNOWN`;
- git diff whitespace check: PASS, line-ending warnings only;
- classifier benchmark: median 0.025 ms, p95 0.045 ms;
- ag final review: `AGREE`, no HIGH or MEDIUM finding;
- cc final review: `AGREE`, no HIGH finding.
