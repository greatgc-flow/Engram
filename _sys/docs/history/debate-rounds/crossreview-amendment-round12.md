# Amendment Debate: debate-protocol-amendment-crossreview
# Round 12

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v11 | reason: §14 cross-review CRv11-A, CRv11-B]
Cross-review counter RESET — v12 proposal lineage begins.

---

[PROPOSAL: crossreview-amendment-20260613-v12]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5 — v12

### Summary of changes from v11

| # | Change | Source |
|:-:|:-------|:-------|
| 1–39 | All v11 changes retained | (see round11) |
| 40 | §14-5: path (a) — empty vote pool → automatic H-2 escalation | CRv11-A (gc+cx) |
| 41 | §14-5: path (a) — explicit fail-safe rules for non-response and non-standard votes by other peers | CRv11-B (gc+cx) |

---

### §14-5 path (a) — v12 full text (diff vs v11)

**v11 path (a):**
```
(a) Classification dispute — the refusing peer believes the finding is actually HIGH
(not LOW): the peer MAY challenge via SEVERITY_CHALLENGE. For this challenge, the
challenging peer is excluded from the vote pool — only other non-ABSENT active peers
vote. If all such peers vote LOW → challenge fails (confirms LOW); the challenging
peer must then accept as Accepted Risk or proceed via path (b). If any other
non-ABSENT active peer votes HIGH → HIGH applies.
```

**v12 path (a):**
```
(a) Classification dispute — the refusing peer believes the finding is actually HIGH
(not LOW): the peer MAY challenge via SEVERITY_CHALLENGE. For this challenge, the
challenging peer is excluded from the vote pool — only other non-ABSENT active peers
vote. If all such peers vote LOW → challenge fails (confirms LOW); the challenging
peer must then accept as Accepted Risk or proceed via path (b). If any other
non-ABSENT active peer votes HIGH → HIGH applies. All other SEVERITY_CHALLENGE vote
rules apply to other non-ABSENT active peers in this challenge — including: a peer who
fails to respond within one round is treated as voting HIGH (fail-safe); a non-standard
response is treated as voting HIGH (fail-safe). If no other non-ABSENT active peers are
available to vote (empty vote pool), the challenge cannot be resolved by vote and is
automatically escalated to H-2. H-2 may: (i) classify the finding as HIGH, triggering
the standard HIGH action; (ii) narrow the finding scope so it clearly meets LOW criteria
and require re-acceptance; (iii) split to SUB_ISSUE; or (iv) ABORT(A-2).
```

All other §14 text (§14-1 through §14-7, plus changes 1–39) is identical to v11.

---

Version-Tag: v12
Issued By: cc
Issued At: 2026-06-13T19:20:00Z
Status: PROPOSED

---

## Round 12 — Peer Responses

[PEER: cx] [ROUND: 12]
POSITION: AGREE
REASONING: Change 40 fixes CRv11-B (non-exhaustive) — path (a) now exhaustive for available voters:
LOW-only → LOW, HIGH/non-response/non-standard → HIGH fail-safe, silence no longer undefined.
Change 41 fixes CRv11-A (empty pool) — escalates to H-2 instead of vacuous LOW.
Four H-2 outcomes cover needed dispositions.
CONCERNS: Non-blocking clarity — explicitly naming ABSTAIN as non-standard (→ HIGH) would remove ambiguity.
STATUS: AGREE
CRv10-B~H: YES / CRv9-D, CRv9-E, CR-10, CR-21~28: YES

[PEER: gc] [ROUND: 12]
POSITION: DISAGREE
REASONING: Changes 40+41 resolve CRv11-A and CRv11-B. However, the newly defined H-2 options
(change 41 empty pool section) introduce new gaps: they restrict H-2 into limited paths, omitting:
1. Classify the finding as LOW as-is (if H-2 determines no scope narrowing is needed).
2. Discard/reject the finding (if it is a false positive or invalid concern).
CONCERNS:
1. H-2 options lack "classify as LOW as-is" path.
2. H-2 options lack "discard/reject finding (false positive)" path.
STATUS: DISAGREE
CRv10-B~H: YES / CRv9-D, CRv9-E, CR-10, CR-21~28: YES

---

## Coordinator Response to gc DISAGREE

Concern #1 ("classify as LOW as-is"): ACCEPTED — option (ii) "narrow the finding scope" doesn't
cover the case where the finding is already clearly LOW and no narrowing is needed. Fix: replace
option (ii) with "classify the finding as LOW (narrowing scope if needed), requiring the challenger
to accept as Accepted Risk or proceed to path (b)."

Concern #2 ("discard/reject finding"): NOT ACCEPTED as a separate option. The finding already
exists in the ledger as a confirmed cross-review finding. H-2 can "dismiss the challenge" by
classifying as LOW, which is covered by the corrected option (ii). A false-positive concern would
be classified as LOW, not "discarded." Discarding a finding would bypass the ledger audit trail.

cx non-blocking concern (ABSTAIN explicit): ACCEPTED as minor clarification to change 41.

→ v13 to follow.

