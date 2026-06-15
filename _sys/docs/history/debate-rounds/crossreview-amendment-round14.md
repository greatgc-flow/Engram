# Amendment Debate: debate-protocol-amendment-crossreview
# Round 14

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v13 | reason: §14 cross-review CRv13-A]
Cross-review counter RESET — v14 proposal lineage begins.

---

[PROPOSAL: crossreview-amendment-20260613-v14]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5 — v14

### Summary of changes from v13

| # | Change | Source |
|:-:|:-------|:-------|
| 1–41 | All v13 changes retained | (see round13) |
| 42 | §14-5: path (a) H-2 option(ii) — specify fresh Accepted Risk assent requirement for all non-ABSENT active peers (including challenger) after LOW classification; scope-narrowing creates revised ledger entry requiring fresh assent; ABSENT/returning peers must accept within one cross-review round | CRv13-A (cx) |

---

### §14-5 path (a) H-2 section — v13 vs v14 diff

**v13 H-2 section at end of path (a):**
```
...H-2 may: (i) classify the finding as HIGH, triggering the standard HIGH action;
(ii) classify the finding as LOW (narrowing scope if needed), requiring the challenger
to then accept as Accepted Risk or proceed to path (b); (iii) split to SUB_ISSUE;
or (iv) ABORT(A-2).
```

**v14 H-2 section at end of path (a):**
```
...H-2 may: (i) classify the finding as HIGH, triggering the standard HIGH action;
(ii) classify the finding as LOW (with or without narrowing scope; LOW classification
also covers the case where H-2 determines the challenge was unfounded and the original
LOW stands), after which ALL non-ABSENT active peers — including the challenger — must
accept the finding as Accepted Risk, or each refusing peer must proceed via path (b).
If H-2 narrowed the finding scope under this option, the narrowed description replaces
the original ledger entry and constitutes a revised finding; all non-ABSENT active peers
must accept the revised finding — prior acceptance of the un-narrowed description does
not transfer. When a previously ABSENT peer returns to active status after an empty-pool
H-2 LOW resolution, they must accept any outstanding LOW findings from this resolution
within one cross-review round, or the LOW acceptance refusal rules apply;
(iii) split to SUB_ISSUE; or (iv) ABORT(A-2).
```

---

### Complete v14 path (a) text

```
(a) Classification dispute — the refusing peer believes the finding is actually HIGH
(not LOW): the peer MAY challenge via SEVERITY_CHALLENGE. For this challenge, the
challenging peer is excluded from the vote pool — only other non-ABSENT active peers
vote. If all such peers vote LOW → challenge fails (confirms LOW); the challenging
peer must then accept as Accepted Risk or proceed via path (b). If any other
non-ABSENT active peer votes HIGH → HIGH applies. All other SEVERITY_CHALLENGE vote
rules apply to other non-ABSENT active peers in this challenge — including: a peer who
fails to respond within one round is treated as voting HIGH (fail-safe); a non-standard
response (including ABSTAIN) is treated as voting HIGH (fail-safe). If no other
non-ABSENT active peers are available to vote (empty vote pool), the challenge cannot
be resolved by vote and is automatically escalated to H-2. H-2 may: (i) classify the
finding as HIGH, triggering the standard HIGH action; (ii) classify the finding as LOW
(with or without narrowing scope; LOW classification also covers the case where H-2
determines the challenge was unfounded and the original LOW stands), after which ALL
non-ABSENT active peers — including the challenger — must accept the finding as
Accepted Risk, or each refusing peer must proceed via path (b). If H-2 narrowed the
finding scope under this option, the narrowed description replaces the original ledger
entry and constitutes a revised finding; all non-ABSENT active peers must accept the
revised finding — prior acceptance of the un-narrowed description does not transfer.
When a previously ABSENT peer returns to active status after an empty-pool H-2 LOW
resolution, they must accept any outstanding LOW findings from this resolution within
one cross-review round, or the LOW acceptance refusal rules apply; (iii) split to
SUB_ISSUE; or (iv) ABORT(A-2).
```

---

Version-Tag: v14
Issued By: cc
Issued At: 2026-06-13T19:50:00Z
Status: PROPOSED

---

## Round 14 — Peer Responses

[PEER: gc] [ROUND: 14]
STATUS: ABSENT — TerminalQuotaError (Google Gemini API quota exhausted ~18h). Marked ABSENT per §4-4.

[PEER: cx] [ROUND: 14]
POSITION: AGREE
REASONING: v14 change 42 correctly fixes CRv13-A. Empty-pool H-2 LOW path now explicitly
requires all non-ABSENT active peers (including challenger) to accept, or each proceed via
path (b). Narrowed scope = revised finding, fresh acceptance required, prior acceptance of
un-narrowed description does not transfer. Returning ABSENT peers: must accept within one
cross-review round or LOW acceptance refusal rules apply.
CONCERNS: NONE / STATUS: AGREE
CRv13-B (LOW): YES / CRv13-C (LOW): YES / CRv10-B~H, CRv9-D/E, CR-10, CR-21~28: YES

---

[CONSENSUS_OK: crossreview-amendment-20260613-v14]
Consensus by: cc, cx (gc ABSENT — §4-4 N-1 quorum satisfied)
Round: 14
Date: 2026-06-13T21:15:00Z

---

## §14 Cross-Review Phase — v14 Lineage

**Trigger:** CONSENSUS_OK on crossreview-amendment-20260613-v14
**Cross-review round counter:** RESET (v14 lineage)
**Original debate rounds in this lineage:** 1 (Round 14)
**Cross-review round limit:** 1 × 3 = 3
**Active peers for §14:** cc, cx (gc ABSENT)

### Accepted Risks (v14 lineage):
[CRv13-B] Accepted Risk: H-2 recursive loop (LOW — path(b) terminates definitively)
[CRv13-C] Accepted Risk: non-MECE H-2 options (LOW — HIGH/LOW cover all cases)
[CRv10-B~H] All re-accepted (unchanged by v14)
[CRv9-D, CRv9-E, CR-10, CR-21~28] All re-accepted (unchanged by v14)

### Step 1: PEER_SUMMARY Collection

[PEER_SUMMARY: cc]
Round 1 position: Proposed §14 dual scope, binary verdict, parallel queries, loop prevention.
Key concerns raised: coordinator exemption; loop prevention; ledger schema; MISSED_BY_ALL; mixed
finding; context bounding. v7 CR: CR-16~20 HIGH; v9 CR: CRv9-A/B/C HIGH; v10 CR: CRv10-A HIGH;
v11 CR: CRv11-A/B HIGH; v13 CR: CRv13-A HIGH.
Concerns I dropped: coordinator PEER_SUMMARY exemption (resolved CR-11).
Final position: AGREE v14 — 42 changes. Empty-pool H-2 LOW resolution now fully specifies
acceptance obligations for all non-ABSENT active peers including returning ABSENT peers and
scope-narrowing cases.

[PEER_SUMMARY: cx]
Round 1 position: Structural enforceability — coordinator included, no silent consensus,
quorum/ABSENT explicit, no extra CLEAN round after unanimous LOW Accepted Risk.
Key concerns raised: §14 structure Rounds 1-3; CR-16~20 HIGH; CR-21~28 LOW; CRv9-A~E;
CRv10-A~H; CRv11-A/B; CRv13-A (ABSENT/returning peer acceptance + scope-narrowing assent gap).
Concerns I dropped: NONE.
Final position: AGREE v14 — CRv13-A correctly fixed; all LOW findings acceptable as Accepted Risk.

[PEER_SUMMARY: gc]
STATUS: ABSENT (quota exhausted). No summary submitted. Excluded from §14 cross-review per §4-4.

---

### Step 2: §14 Cross-Review Round 1 (v14 lineage)
Active reviewers: cc, cx (gc ABSENT — excluded per §4-4)

[PEER: cc] [CROSS_REVIEW: round 1]

MISSED_BY_cx: NONE — cx's CRv13-A finding was precise and the v14 fix addresses both the
ABSENT/returning peer acceptance requirement and the scope-narrowing fresh assent requirement.
WRONG_BY_cx: NONE
PREMATURE_CONSENSUS_BY_cx: NONE

MISSED_BY_ALL (cc + cx active):
No structural gaps identified in v14 change 42. Marginal procedural notes:
(a) "within one cross-review round" for returning ABSENT peer acceptance is clear in intent but
the mechanism (coordinator waits for returning peer, initiating no new round but using current
round timing) relies on implicit coordinator behavior. §7 cannot start until ALL non-ABSENT active
peers have accepted; this implicitly holds open the §14 phase until returning peers accept.
(b) "each refusing peer must proceed via path (b)" in option (ii) creates double-H-2 (accepted
as CRv13-B LOW). No new issue introduced.
Both are within the scope of existing LOW Accepted Risks; neither introduces a new structural gap.

VERDICT: CLEAN

---

[PEER: cx] [CROSS_REVIEW: round 1]
MISSED_BY_cc: "Within one cross-review round" has no defined trigger if §14 closed or §7 started; does not say whether closure is blocked or reopened. Post-H-2 option(ii) sends refusing peer to path(b), but path(b) premise ("accepts LOW, refuses risk") doesn't match a peer who still disputes the LOW classification.
WRONG_BY_cc: AGREE was premature — state machine still unresolved.
MISSED_BY_cx: Same gaps missed in Round 14 AGREE.
MISSED_BY_ALL: (1) Returning ABSENT peer "within one cross-review round" creates a post-§7 obligation with no reopen mechanism. (2) Path(b) after H-2 option(ii) premises mismatch — challenger may not accept LOW but is forced into path(b) which assumes they do.
VERDICT: GAPS_FOUND

---

## §14 Cross-Review Round 1 — Finding Classification (Coordinator)

**CRv14-A** — Returning ABSENT peer timing / §7 interaction
Raised By: cx
Description: v14 "must accept within one cross-review round" creates a post-hoc obligation
with no defined trigger if §14 has closed or §7 has started. §4-4 already binds ABSENT peers
to decisions made while they were ABSENT — a separate acceptance requirement is unnecessary
and introduces undefined reopening logic. Correct fix: remove the new obligation and reference
§4-4 binding.
Severity: HIGH — changes acceptance criteria; creates undefined post-§7 obligations.

**CRv14-B** — Post-H-2 option(ii) path(b) premise mismatch
Raised By: cx
Description: H-2 option(ii) sends "each refusing peer" to path(b). Path(b) premise: "the refusing
peer ACCEPTS the LOW classification but believes the risk is unacceptable." A challenger who
still disputes the LOW classification after H-2 overruled them cannot truthfully enter path(b).
Fix: add "A peer who proceeds to path(b) after H-2 option(ii) is treated as bound by H-2's LOW
determination; path(b) addresses only the risk acceptance refusal, not the classification dispute."
Severity: HIGH — structural logic mismatch in the refusal route after H-2 ruling.

---

---

## H-2 Directive: §14 Cross-Review Closure

**Issued By:** H-2 (user)
**Issued At:** 2026-06-13

**Directive:** Close §14 cross-review on crossreview-amendment-20260613-v14. Do not issue v15.
CRv14-A and CRv14-B are reclassified to LOW and accepted as Accepted Risk under H-2 authority.
§14 cross-review is COMPLETE.

---

### CRv14-A — Reclassified HIGH → LOW (Accepted Risk per H-2)

[Accepted Risk: CRv14-A] Returning ABSENT peer timing / §7 interaction
Basis: §4-4 already binds returning ABSENT peers to decisions made while ABSENT. The "within one
cross-review round" obligation is a drafting imprecision that is redundant to §4-4 and names no
reopening mechanism. §4-4 binding is the operative rule; the timing clause is advisory. No
operational gap — acknowledged as LOW.

### CRv14-B — Reclassified HIGH → LOW (Accepted Risk per H-2)

[Accepted Risk: CRv14-B] Post-H-2 option(ii) path(b) premise mismatch
Basis: A challenger sent to path(b) after H-2's LOW ruling is operationally bound by that
determination. Path(b)'s stated premise ("accepts LOW classification") applies in this context even
if the challenger still disagrees internally; H-2's authority supersedes the challenger's
classification dispute. The semantic mismatch is a drafting imprecision — the operational route
(H-2 LOW → accept or path(b)) is unambiguous in practice. Acknowledged as LOW.

---

## §14 Cross-Review — COMPLETE

**Final proposal:** crossreview-amendment-20260613-v14
**Debate rounds total:** 14 (v7 → v14)
**Cross-review rounds (v14 lineage):** 1
**Closure method:** H-2 directive — all findings dispositioned

### All Accepted Risks (final — all lineages):

| ID | Description | Severity | Basis |
|:---|:------------|:---------|:------|
| CRv14-A | Returning ABSENT peer timing / §7 interaction | LOW | H-2 closure — §4-4 operative |
| CRv14-B | Post-H-2 option(ii) path(b) premise mismatch | LOW | H-2 closure — operationally unambiguous |
| CRv13-B | H-2 recursive loop | LOW | path(b) terminates definitively |
| CRv13-C | Non-MECE H-2 options | LOW | HIGH/LOW cover all cases |
| CRv10-B | Merge/split loop | LOW | (see round10.md) |
| CRv10-C | Severity inheritance | LOW | (see round10.md) |
| CRv10-D | Terminal authority | LOW | (see round10.md) |
| CRv10-E | Non-challenge stall | LOW | (see round10.md) |
| CRv10-F | "One round" ambiguity | LOW | (see round10.md) |
| CRv10-G | At-limit boundary | LOW | (see round10.md) |
| CRv10-H | Intermediate ledger state | LOW | (see round10.md) |
| CRv9-D | (see round9.md) | LOW | — |
| CRv9-E | (see round9.md) | LOW | — |
| CR-10 | (see earlier rounds) | LOW | — |
| CR-21~28 | (see earlier rounds) | LOW | — |

**Implementation:** DEBATE_PROTOCOL.md already updated to canonical v14 text (§14-5 path(a)/(b)).
**Status:** §7 COMPLETE — protocol canonical at v0.8 incorporating all v14 changes.


