---
status: living
---

# T82 Re-Scope: Engram = Internal Multi-Peer Collaboration Engine Only (2026-07-27)

User-directed narrowing of T82. Prior framing (evaluated 2026-07-26,
`residual-backlog-and-packaging-precheck-2026-07-26.md` §2) treated T82 as
"should Engram become a standalone, installable product" and found the
5-condition activation gate 0/5 satisfied. The user's 2026-07-27 instruction
does not ask to re-litigate that question — it permanently removes
productization from Engram's own scope entirely. Engram's purpose is now
defined as: the multi-peer (cc/ag/cx) collaboration mechanism living inside
the portable dev environment. Packaging, portable-vs-local install, and
distribution channels are the user's own separate concern to configure ad
hoc, or a fully separate future project if ever spun off — not something
Engram itself is architected toward.

This was run as a full R:10 round (collab_rate=10): independent design
questions to `ag` and `cx`, a synthesized draft, a Final Call ACK round, one
substantive correction from `cx` incorporated, unanimous close.

## 1. Scope boundary (converged: cc synthesis, cx's formulation, ag corroboration)

- **In scope — core collaboration engine:** peer/profile resolution &
  adapters, dispatch/process/session lifecycle, routing, health/quarantine,
  leases, IPC/audit logging, brokered mutations, consensus/arbiter behavior,
  room/handoff state.
- **Out of scope — packaging/distribution:** acquiring/updating binaries,
  install roots, PATH integration, bootstrappers, signed artifacts,
  package-manager channels (PyPI/Homebrew/WinGet), rollback/uninstall,
  external-consumer APIs, cross-install compatibility.
- **Shared seam:** the core may consume a configured executable path and
  report readiness on it. It neither owns nor architects around
  *distributing* that executable.

`ag` independently verified zero runtime coupling to the shelved product
lifecycle: no `EngramHome`, `InstallationRecord`, bootstrap transactions, or
distribution-channel logic exists anywhere in `_sys/core/` or `_sys/cli/`.
`cx` confirmed the same from the adapter-selection code path
(`hub_peer.py`'s `PeerAdapter` already only wires to PortableDev-managed
executable paths; it is not evidence of productization). **The conflation is
entirely in two design documents, not in any live code.**

## 2. Governance bar (converged, with cx's correction applied)

- **Standalone product / external integration:** the original 5-condition
  activation gate (named owner, committed delivery intent, concrete external
  use case, executable conformance fixtures, maintenance/funding commitment)
  is preserved unchanged as a historical record and as readiness criteria
  *for a genuinely separate future project* — but satisfying it can **never
  again reactivate Engram-the-collaboration-engine's own scope**. Doing that
  would require a brand-new, explicit user decision plus a fresh R:10 scope
  approval, not a gate check. This is why T82 itself is now closed as
  **superseded**, not left `deferred` — `deferred` would wrongly imply a
  pending Engram goal.
- **Internal collaboration-engine hardening:** uses the already-standard
  lighter bar — DIR-004 (measured evidence) + DIR-001 (ROI) for routine
  fixes; DIR-006/a fresh R:10 direction round only if a change is genuinely
  structural. T83 (the real lease-clobber concurrency bug, fixed without
  ever activating the shelved product architecture) is the precedent this
  bar already follows in practice.

## 3. Documentation corrections made

- **`engram-refactor-blueprint-2026-07-20.md`**: status banner amended —
  the 5-condition gate may at most justify evaluating a *separate* future
  project; it does not and cannot reactivate Engram itself. T82's own
  backlog entry now points here as superseded.
- **`phase2-arch-general-specific-2026-07-22.md`**: a scope-correction note
  added near the top and directly at the `## 14. Host Distribution,
  Packaging & User Lifecycle` heading, marking §14 (and the §14-derived
  Phase-3 "Step 4" backlog items) non-normative for current work — outside
  Engram's scope entirely now, not merely gated. §0–§13's internal
  General-Specific/RuntimeContext/adapter-contract content is untouched;
  `ag`/`cx` both confirmed it isn't packaging-specific and remains a
  separate, unrelated question (whether Phase 2 itself should ever be
  built) from this scoping decision.
- **`MOC.md`**: the Phase 2 architecture pointer annotated to note §14 is
  out of scope under the T82 re-scope.
- **`backlog.json`**: `T82` status changed `deferred` → `superseded`; title
  and `next_action` updated to record this re-scope decision and point here.

## 4. Concrete pain point surfaced (cc-verified by direct code read, not speculation)

`cx`'s independent investigation, while establishing the boundary, surfaced
a real, currently-active defect unrelated to packaging: automatic proposal
flooding. As of this session, `_sys/ai/proposals/` contained dozens of
untracked `auto--saturation-detected-*` files (60 at last count, and rising
— the exact number will keep changing until fixed) from repeated
near-identical events.

Root cause, verified directly against the live code (not cx's claim taken
on faith):

- `ctx_end.py:472-479` launches `self_care.py --trigger session_end` as a
  fire-and-forget background subprocess on **every** session end.
- `self_care.py`'s `propose()` (line 244) calls `hub.py proposal-add`
  whenever the scan step produced any stdout at all — no dedup against
  existing open proposals.
- `saturation_scan.py:281`'s `commit_count % 10 != 0` skip check is
  supposed to limit scans to roughly every 10th commit. `.ai/state.json`
  has **no `commit_count` key at all**, so `_read_commit_count()` always
  returns its `0` default (confirmed by direct read: `.get("commit_count",
  0)`), and `0 % 10 == 0` — the skip condition never fires. The scan runs
  unconditionally, every session, forever, not as a one-off coincidence.
- `hub.py:10438-10450`'s `action_proposal_add()` only computes the next
  sequence number by globbing same-date-same-subject files; it has zero
  content/fingerprint-based deduplication.

This is filed as a new standalone item, **T89**, separate from T82 (it's
unrelated to packaging — the re-scope discussion simply surfaced it).
Acceptance criteria (per `cx`'s proposal):
1. The same normalized finding-fingerprint produces at most one open
   proposal.
2. Concurrent session-end runs still produce only one.
3. `commit_count` being `0` or missing must not behave like "every 10th
   commit."
4. A genuinely new finding set may still create a new proposal.
5. At most one pending-handoff entry is recorded.

`T87` and `T88` keep their existing `deferred` status, unchanged — this
re-scope doesn't newly obligate fixing them; it confirms they (plus T89) are
the correct category of future work versus speculative packaging
architecture.

## 5. R:10 process record

- Independent round: `ag` (ag.deepthink) and `cx` (cx.deepthink) each
  answered the scope-boundary question independently, without seeing each
  other's response. Both AGREED with the user's narrower framing.
- Final Call: cc synthesized a draft conclusion, sent it to both for ACK.
  `ag` ACKed without changes. `cx` ACKed conditionally, catching a real
  self-contradiction in the draft (§2 above) — incorporated, not
  re-litigated with a third round (the correction was a refinement of the
  already-agreed direction, not a new dissent, and `ag`'s ACK doesn't
  conflict with it).
- Unanimous close: `cc` (proposer) + `ag` + `cx` all agree on the content of
  this document.
