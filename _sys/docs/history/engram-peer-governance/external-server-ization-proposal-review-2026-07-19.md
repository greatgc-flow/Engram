# External "Server-ize Engram" Proposal — Review Framework & Verdict (2026-07-19)

> Status: living | Verdict: **REJECT server-izing Engram itself as a build target for third-party integrations.** Counter-pattern: extract the reusable core (capability-leveled, pin-respecting routing) as an importable library; the requesting party builds and owns its own service around it, including all of its domain-specific tenancy/auth/compliance semantics.

## What happened (generalized — no third-party business/domain specifics recorded here)

An external document proposed that Engram — a portable, local, single-user, multi-AI-peer workspace — be turned into a network-facing, multi-tenant backend service for an unrelated third-party product, so that product could delegate an AI-processing step to Engram instead of building its own orchestration. The document asked for a full server API (auth/consent tokens, signed execution receipts, tenant-isolated caching, capability-leveling-based routing) plus an async client/server contract, and claimed prior peer consensus that could not be substantiated from this instance's own records.

3-way independent review (ag.deepthink, cx.deepthink, cc.fable — explicitly instructed not to defer to the document's own claimed consensus) converged unanimously.

## General finding pattern (the reusable lesson)

1. **Generic/specific separation, checked against Engram's own INV-29** (general/core must not branch on specific identity; domain-specific behavior belongs behind an adapter, never baked into the shared core): the proposal's "generic service layer" repeatedly embedded the requesting party's domain vocabulary (auth/consent semantics, business-entity identifiers, a closed domain-specific enum, and a domain-specific output-authority flag) directly into what it called generic schemas. No adapter/extension layer was ever defined — a second unrelated client would require breaking changes throughout. **Verdict: the underlying mechanics (signed tokens, hash-chained receipts, idempotency/cache-key split, circuit breakers, pin-first-then-rank resolver ordering) are genuinely generic and well-designed in isolation; the contract as a whole fails Engram's own separation test by wrapping them directly in one client's domain model instead of a neutral envelope.**

2. **System-kind mismatch, not just a separation defect**: Engram's actual invariants (peer equality with human-ratified consensus, no private/tenant-isolated channels, minimal credential custody, R:10 consensus required to touch core dispatch code) are structurally opposed to what a multi-tenant, credential-custodial, network-facing backend requires. This is a **scope graft** — building a different kind of system on top of Engram because Engram has one reusable internal component (capability-leveled routing) the proposal wants — not a natural generalization of what Engram already is.

3. **The proposal's own premise overstated Engram's current state** (a DIR-004 concern beyond just the unverifiable-consensus claim): it described Engram's capability-leveling work as an "existing service," when the project's own SSOT records that work as design/measurement-framework stage, not an operational service ready to sit behind a public API.

4. **A concrete technical instance of the same root pattern**: one probabilistic, generic-layer verification mechanism (a Bloom-filter-based revocation check, which has false positives by construction) fed directly into the *single most severe*, domain-specific failure class (a hard, tenant-wide stop requiring manual reset) with no distinction between "definitely revoked" and "could not verify." This is the abstract pattern from finding #1, recurring at the mechanism level: a generic building block's real failure modes were never checked against the specific layer's escalation policy before they were wired together.

## Recommendation (unanimous, 3/3)

Do not server-ize Engram's core to serve external integrations. Where a genuinely reusable capability exists (e.g. capability-leveled, pin-respecting routing), extract it as a standalone library. The requesting integration builds and owns its own service around that library, keeping all of its domain-specific auth/tenancy/compliance semantics in its own layer — never merged into Engram's shared core. This is Engram's own General→Specific dependency rule (INV-29), applied at the scale of "should Engram become someone else's backend" rather than just "how should one peer adapter be structured."

## Process note

Full technical review detail (exact schemas, endpoint names, and the requesting party's domain terminology) is intentionally NOT reproduced here — this repository is public, and that level of detail belongs to the external party's own document, not Engram's public history. This entry preserves only the architecturally reusable finding and verdict.
