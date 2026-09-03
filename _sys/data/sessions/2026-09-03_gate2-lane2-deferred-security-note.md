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
