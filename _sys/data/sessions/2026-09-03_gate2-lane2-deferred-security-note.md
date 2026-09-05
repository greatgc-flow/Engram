# Gate 2 Lane 2 (trusted-manifest discovery) — deliberately deferred

While grounding a Lane 1 implementation dispatch, the terminal discovered
that `docs/design/PHASE1-MANIFEST-SCHEMA-V2-2026-08-20.md` (peerhub repo)
already specifies, in far more depth than the ratified Gate 2
discovery-sweep design referenced, a full **adapter-manifest admission
engine**: JSON Schema validation, semantic template guards, Windows ACL/
NTFS evaluation (world-writable/anonymous-logon denial, ownership checks,
junction-safety), single-node executable hashing (SHA-256, MZ magic-byte
verification), a collision algorithm (Unicode NFC + casefold key
normalization, AST-digest collision detection), and atomic RCU-style
registry publication (`PublishedRegistry`, monotonic `registry_generation`,
reader-immunity across reloads).

Grepped the real peerhub source for `PublishedRegistry`/`AdmissionReceipt`/
`chain_complete`/`registry_generation`: real `AdmissionReceipt` hits exist
in `peerhub/dispatch/*.py`, but tracing the import (`from .contract import
AdmissionReceipt` in `peerhub/dispatch/admission.py`) confirms this is
`peerhub/dispatch/contract.py`'s own class — the *dispatch/command-request*
admission system (idempotency, capability leases), a coincidental name
collision with an unrelated subsystem. **The adapter-manifest admission
engine PHASE1-MANIFEST-SCHEMA-V2 describes does not appear to be
implemented anywhere in the codebase yet** — it is still only a design
doc.

This means Gate 2's "Lane 2 — trusted-manifest discovery for third
parties" (scanning `%LOCALAPPDATA%\PeerHub\adapters.d`, parsing untrusted
`.json` files as adapter declarations, and trusting them enough to
eventually spawn the executable they name) is a **security trust boundary
over untrusted third-party input that currently has no real
implementation to build on** — building it now means writing the entire
ACL-evaluation + hash-pinning + collision-detection + atomic-publication
engine from scratch.

**Decision (terminal, not a full R:10 round): implement Lane 1 only for
now** (built-in PATH resolution for the 3 known peers — cc/cx/ag — no
untrusted-file admission involved, much lower risk, and directly serves
the explicitly-stated "auto-detect installed AI CLIs" goal for the common
case). Lane 2 is deliberately NOT implemented in this pass. Rationale: a
trust-boundary security feature that ultimately gates code execution from
third-party-dropped files deserves genuine adversarial peer review (real
consensus, not terminal-substituted critique) before being built, per this
session's own standing "no arbitrary choices on ambiguous/high-risk
decisions" discipline (DIR-006, now itself one of the 6 migrated
directives) — this is a materially higher-stakes call than the
deletion/refactor work terminal-substituted critique has covered so far
this session. Resume this either once `cx` recovers (2026-09-07) for a
real security-focused critique round, or on explicit user direction to
proceed without it.

**2026-09-04 update — preliminary second-opinion review done (NOT a
substitute for the required cx round above).** With otherwise-idle
3P-pool quota, dispatched `ag.opus` for a from-scratch adversarial paper
review of the design doc. 10 concrete findings, all grounded in specific
design-doc sections (spot-checked, citations accurate) — see peerhub's
`docs/design/PHASE1-MANIFEST-SCHEMA-V2-PRELIM-SECURITY-REVIEW-2026-09-04.md`
for the full writeup. Headline: findings 1-3 (unbounded Phase-1 TOCTOU
between admission-time hashing and spawn, junction/symlink swap after
admission, and an unspecified path-vs-PATH-re-resolution question at
spawn time) compose into a real local-attacker kill chain achieving code
execution, PLUS two undocumented gaps worth cx's attention specifically:
unrestricted `env_policy.set`/`inherit` (credential/PATH injection into
the spawned process) and all-or-nothing snapshot rejection (one bad
manifest DoSes all discovery). The review's own conclusion agrees with
this note's original deferral decision: "do not ship Lane 2 third-party
admission with Phase 1's validation model." This does not close the
item — cx's real review on 2026-09-07 is still required — but it gives
cx's round a concrete starting checklist instead of a blank page.

**2026-09-05 update — the required cx.deepthink review is DONE (dispatched
early, on the user's explicit direction, rather than waiting for 09-07 —
cx has in fact been available and reliable throughout this whole session,
so the original quota-exhaustion assumption behind the 09-07 date was
stale).** Full writeup: peerhub's
`docs/design/PHASE1-MANIFEST-SCHEMA-V2-2026-08-20.md` review round
(no separate file yet — see peerhub git/session record; the terminal
independently spot-verified 3 of cx's most load-bearing claims directly
against real source before trusting the report: (a) `adapter_id`/
`peer_kind`'s schema patterns really are ASCII-only (`^[a-z0-9-]+$` /
`^[a-z]+$`), confirming ag.opus's Unicode-homoglyph finding was
overstated for those two fields specifically (but cx correctly found
`aliases`/`profile_id`/`shim_names` have NO pattern constraint at all,
so the homoglyph risk moves there instead of disappearing); (b) the
claimed JSON-Schema trailing-LF bypass is real, reproduced directly
with this environment's actual `jsonschema==4.26.0`:
`Draft202012Validator({"type":"string","pattern":"^[a-z0-9-]+$"}).is_valid("evil\n")`
returns `True`; (c) the claimed `env=None`-means-full-ambient-inheritance
regression is real, confirmed by reading `peerhub/application/workflows.py`
line 896-898 (`env=dict(...) if invocation_plan.environment_delta else None`)
and `peerhub/dispatch/pipe.py`'s own `PipeRunnerConfig.env` docstring
("defaults to inheriting the parent environment").

**Verdict: REJECT / DO NOT RATIFY runnable Lane 2 under the Phase 1
validation model described in the design doc.** cx found the design's
core flaw runs deeper than ag.opus's TOCTOU-centric findings: admission-time
hashing "authenticates no publisher or intent" — an attacker doesn't need
a race at all, they can simply place malicious bytes at the target BEFORE
admission (Phase 1 faithfully hashes and admits them), or point the
manifest at an already-trusted system interpreter (`powershell.exe`,
`python.exe`, `node.exe`) and put the actual payload in `argv`/`stdin`,
which no amount of rehashing the interpreter itself would catch. cx's
own summary: "admission-time hashing without authenticated provenance or
explicit activation is change detection, not trust establishment."
10 more concrete findings beyond this (untrusted `"status":"active"` as
self-activation authority with no publisher/signature/admin-approval
concept anywhere in the design; the manifest itself being unconstrained
executable policy via argv/env/cwd even for an honestly-hashed binary;
third-party adapters becoming indistinguishable from first-party ones
downstream with no trust-tier field anywhere in `ResolvedPeerTarget`;
real, reproduced JSON-Schema gaps beyond the LF bypass — duplicate keys,
empty-profile/transport arrays, unbounded sizes; the RCU registry
publication design missing the concurrency/revocation-epoch machinery it
would actually need) — full detail in the peer's own report, archived in
this session's record.

**A safe, much narrower middle ground exists and was independently
proposed by cx, not assumed by the terminal**: ship ONLY a passive,
non-executable "candidate discovery" pass — scan the directory with a
hardened reader, produce inert `CandidateAdapter` records, display them
as "untrusted/unactivated," and never insert them into
`resolve_peer_target()`, the routing/health candidate pool, or run any
readiness/version probe against them. No execution, no probing, no trust
grant — pure display. This is NOT yet authorized for implementation;
it's the peer's recommendation, reported to the user alongside the
verdict above, pending the user's own decision on whether/when to build
even that narrower slice.
