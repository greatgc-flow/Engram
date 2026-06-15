# Amendment Debate: debate-protocol-amendment-crossreview
# Round 11

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v10 | reason: §14 cross-review CRv10-A]
Cross-review counter RESET — v11 proposal lineage begins.

---

[PROPOSAL: crossreview-amendment-20260613-v11]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5 — v11

### Summary of changes from v10

| # | Change | Source |
|:-:|:-------|:-------|
| 1–38 | All v10 changes retained | (see round10) |
| 39 | §14-5: path (a) SEVERITY_CHALLENGE — clarify that the challenging peer is excluded from the vote pool; only other non-ABSENT active peers vote; if all other peers vote LOW → confirms LOW; if any other peer votes HIGH → HIGH applies | CRv10-A (cx+gc) |

---

### §14-5 path (a) — v11 exact change (diff vs v10)

**v10 text (path (a)):**
```
(a) Classification dispute — the refusing peer believes the finding is actually HIGH
(not LOW): the peer MAY challenge via SEVERITY_CHALLENGE. If the challenge confirms
LOW (all non-ABSENT active peers vote LOW), the peer must either accept as Accepted
Risk or proceed via path (b).
```

**v11 text (path (a)):**
```
(a) Classification dispute — the refusing peer believes the finding is actually HIGH
(not LOW): the peer MAY challenge via SEVERITY_CHALLENGE. For this challenge, the
challenging peer is excluded from the vote pool — only other non-ABSENT active peers
vote. If all such peers vote LOW → challenge fails (confirms LOW); the challenging
peer must then accept as Accepted Risk or proceed via path (b). If any other
non-ABSENT active peer votes HIGH → HIGH applies.
```

All other §14 text (§14-1 through §14-7, plus changes 1–38) is identical to v10.

---

Version-Tag: v11
Issued By: cc
Issued At: 2026-06-13T19:00:00Z
Status: PROPOSED

---

## Round 11 — Peer Responses

[PEER: gc] [ROUND: 11]
POSITION: AGREE
REASONING: Change 39 directly resolves CRv10-A. Excluding the challenging peer from the
SEVERITY_CHALLENGE vote pool makes "confirms LOW" reachable. Other peers voting LOW confirms LOW;
any other peer voting HIGH correctly elevates to HIGH. LOW findings CRv10-B~H are minor procedural
ambiguities manageable as Accepted Risks.
CONCERNS: NONE / STATUS: AGREE
CRv10-B~H: Accepted Risk YES (batch)
CRv9-D, CRv9-E, CR-10, CR-21~28: Accepted Risk YES (batch)

[PEER: cx] [ROUND: 11]
POSITION: AGREE
REASONING: Change 39 correctly fixes CRv10-A. Excluding the challenging/refusing peer from the
path (a) SEVERITY_CHALLENGE vote pool makes "confirms LOW" branch reachable: if all other
non-ABSENT active peers vote LOW → confirms LOW; if any other votes HIGH → HIGH. Closes
CRv9-B/CRv10-A exploit where challenger could force HIGH by voting in own challenge. Existing
v10 fail-safe rules still cover non-response/non-standard from other peers. CRv10-B~H remain LOW;
change 39 does not worsen any of them.
CONCERNS: NONE / STATUS: AGREE
CRv10-B~H: Accepted Risk YES
CRv9-D, CRv9-E, CR-10, CR-21~28: Accepted Risk YES

---

[CONSENSUS_OK: crossreview-amendment-20260613-v11]
Consensus by: cc, gc, cx
Round: 11
Date: 2026-06-13T19:10:00Z

---

## §14 Cross-Review Phase — v11 Lineage

**Trigger:** CONSENSUS_OK on crossreview-amendment-20260613-v11
**Cross-review round counter:** RESET (v11 lineage, started after v10 CONSENSUS_REVOKE)
**Original debate rounds in this lineage:** 1 (Round 11 only)
**Cross-review round limit:** 1 × 3 = 3

### Accepted Risks (v11 lineage):
[CRv10-B] Accepted Risk: merge/split re-report loop bounded by cross-review limit + H-2
[CRv10-C] Accepted Risk: merged finding severity covered by coordinator classification + SEVERITY_CHALLENGE
[CRv10-D] Accepted Risk: SUB_ISSUE vs ABORT authority already established via H-2 in path (b)
[CRv10-E] Accepted Risk: path (a) non-challenge stall handled by preserved-LOW loop guard + H-2
[CRv10-F] Accepted Risk: "one round" contextually clear as cross-review round
[CRv10-G] Accepted Risk: duplicate split at limit handled by H-2
[CRv10-H] Accepted Risk: intermediate H-2 ledger state implicit (final outcomes defined)
[CRv9-D] Accepted Risk: vote/acceptance roster snapshot governed by §4-4 (re-accepted)
[CRv9-E] Accepted Risk: round9.md artifact inconsistency — documentation fix only (re-accepted)
[CR-10] Accepted Risk: coordinator judgment + challenge mechanism sufficient (re-accepted)
[CR-21~26, CR-28] Accepted Risk: v11 changes do not affect these areas (re-accepted)

### Step 1: PEER_SUMMARY Collection

[PEER_SUMMARY: cc]
Round 1 position: Proposed §14 dual scope, binary verdict, parallel queries, loop prevention.
Key concerns raised: coordinator exemption; loop prevention (§14-6); ledger schema; MISSED_BY_ALL;
mixed finding; context bounding. v7 CR: CR-16~20 HIGH, CR-21~28 LOW. v9 CR: CRv9-A/B/C HIGH,
CRv9-D/E LOW. v10 CR: CRv10-A HIGH (path (a) vote population), CRv10-B~H LOW.
Concerns I dropped: coordinator PEER_SUMMARY exemption (resolved by CR-11 HIGH).
Final position: AGREE v11 — 39 changes. CRv10-A fixed: challenging peer excluded from path (a)
SEVERITY_CHALLENGE vote pool; "confirms LOW" now reachable.

[PEER_SUMMARY: gc]
Round 1 position: Advocated for rigorous structured debate with explicit tie-breaking, deadlock
resolution, formal termination conditions.
Key concerns raised: Coordinator bias and severity voting fail-safes; CR-16~20 HIGH; CR-21~28 LOW;
CRv9-A/B/D; CRv10-A (vote population in path (a)), CRv10-B (merge/split loop), CRv10-C (severity
inheritance), CRv10-D (terminal authority).
Concerns I dropped: NONE.
Final position: AGREE on v11; re-accepted all LOW findings.

[PEER_SUMMARY: cx]
Round 1 position: Supported §14 but required structural enforceability — coordinator included, no
silent consensus, quorum/ABSENT explicit, no extra CLEAN round after unanimous LOW Accepted Risk.
Key concerns raised: §14 structure issues Rounds 1-3; CR-16~20 HIGH; CR-21~28 LOW; CRv9-A~E;
CRv10-A (vote population, SEVERITY_CHALLENGE structure broken), CRv10-B~H (all LOW).
Concerns I dropped: NONE.
Final position: AGREE on v11 — CRv10-A correctly fixed; all LOW findings acceptable as
Accepted Risk.

---

### Step 2: §14 Cross-Review Round 1 (v11 lineage)

Open LOW findings re-evaluated this lineage (v11):
[CRv10-B~H] All accepted above — simple re-accept available if area unchanged by v11
[CRv9-D, CRv9-E, CR-10, CR-21~28] Re-accepted above

---

[PEER: cc] [CROSS_REVIEW: round 1]

MISSED_BY_gc:
The empty vote pool scenario in path (a): if all non-ABSENT active peers OTHER than the
challenging peer happen to be ABSENT, the vote pool after exclusion is empty. "If all such
peers vote LOW" is vacuously satisfied by the empty set → automatic confirms LOW. While §4-4
ABSENT rules and broader quorum requirements mitigate this, gc did not flag the interaction
between path (a)'s exclusion rule and the degenerate empty-pool case.
WRONG_BY_gc: NONE
PREMATURE_CONSENSUS_BY_gc: NONE

MISSED_BY_cx:
Same empty vote pool scenario. cx focused on closing the CRv10-A exploit and confirming that
the exclusion makes "confirms LOW" reachable, without explicitly addressing the boundary case
where the vote pool itself might be empty.
WRONG_BY_cx: NONE
PREMATURE_CONSENSUS_BY_cx: NONE

MISSED_BY_ALL:
Path (a) empty vote pool: Change 39 excludes the challenging peer from the vote pool, but the
text does not define the outcome when the remaining vote pool is empty (all other non-ABSENT
active peers are ABSENT). Under an empty pool, "all such peers vote LOW" is vacuously true →
automatic confirms LOW. Intent may be: if quorum cannot be formed for the challenge vote,
suspend challenge until quorum restored (consistent with §4-4 spirit). However, §14-4 states
ABSENT peers do not block ANY §14 processes — applying this literally, vacuous confirms LOW
would be the correct outcome even under empty pool.
Severity: LOW — cannot change implementation behavior under normal operation (ABSENT/quorum
framework governs degenerate cases); cannot alter consensus meaning; cannot affect acceptance
criteria. The vacuous-LOW outcome under an empty pool is an edge case consistent with §14-4's
statement that ABSENT peers do not block §14 processes.

VERDICT: GAPS_FOUND

---

[PEER: gc] [CROSS_REVIEW: round 1]
MISSED_BY_cc: Empty vote pool scenario (challenger is ONLY active peer) and non-binary vote/abstention edge cases.
WRONG_BY_cc: NONE
PREMATURE_CONSENSUS_BY_cc: Agreed to v11 without verifying empty vote pool edge case from challenger exclusion rule.
MISSED_BY_gc: Same — empty vote pool + non-binary vote/abstention edge cases.
WRONG_BY_gc: NONE
PREMATURE_CONSENSUS_BY_gc: Agreed to v11 without thoroughly testing limits of new challenger exclusion rule.
MISSED_BY_cx: Empty vote pool (all others ABSENT, quorum drops to 0 via exclusion) and non-binary abstention case.
WRONG_BY_cx: NONE
PREMATURE_CONSENSUS_BY_cx: Agreed to v11 despite quorum/ABSENT focus, missed case where quorum drops to 0.
MISSED_BY_ALL:
CRv11-A: Empty vote pool — when challenger is ONLY active peer, "all vote LOW" is vacuously true,
forcing the sole active peer to accept a LOW classification for what they believe is HIGH, breaking
the safety constraint.
CRv11-B: Non-exhaustive condition — if a peer abstains or submits invalid vote, outcome falls
through both explicitly defined cases.
VERDICT: GAPS_FOUND
CRv11-A severity: HIGH
CRv11-B severity: LOW / Accepted Risk vote: NO

---

[PEER: cx] [CROSS_REVIEW: round 1]
MISSED_BY_cc: Empty vote pool scenario; non-exhaustive two-case outcome for non-response/non-standard.
WRONG_BY_cc: NONE
PREMATURE_CONSENSUS_BY_cc: AGREE v11 premature — change 39 fixes self-voting only for non-empty vote pools.
MISSED_BY_gc: Empty vote pool + incomplete outcome coverage for non-response/non-standard under path (a).
WRONG_BY_gc: NONE
PREMATURE_CONSENSUS_BY_gc: AGREE v11 premature — safeguards enforceable only when pool is non-empty.
MISSED_BY_cx: Challenger exclusion creates empty-pool case and possible vacuous LOW confirmation.
WRONG_BY_cx: NONE
PREMATURE_CONSENSUS_BY_cx: "CRv10-A correctly fixed" only true when at least one other non-ABSENT active peer votes.
MISSED_BY_ALL:
Change 39 does not explicitly state that general SEVERITY_CHALLENGE rules govern timeout, non-response,
non-standard votes, quorum, or empty eligible pool. Challenger exclusion may be exploitable by making
all other peers ABSENT/non-responsive, causing either deadlock or unintended LOW confirmation.
VERDICT: GAPS_FOUND
CRv11-A (empty vote pool): HIGH — §14-5(a) fails to resolve challenge when pool is empty or confirms
LOW with zero independent votes.
CRv11-B (non-exhaustive two-case): HIGH — not exhaustive without explicit delegation to general rules.
Accepted Risk vote: NO (both)

---

## §14 Cross-Review Round 1 — Finding Classification (Coordinator)

**CRv11-A** — Empty vote pool in path (a)
Raised By: gc (MISSED_BY_ALL), cx (MISSED_BY_ALL), cc (MISSED_BY_ALL)
Description: §14-5 path (a) excludes the challenging peer from the vote pool. When the vote
pool is empty (all other non-ABSENT active peers are ABSENT), "If all such peers vote LOW"
is vacuously satisfied → automatic confirms LOW with zero independent votes. This forces the
sole active peer (the challenger) to accept a LOW classification they believe is HIGH, breaking
the safety constraint of the challenge mechanism.
Coordinator initial classification: LOW
Severity Challenge: gc votes HIGH, cx votes HIGH → any HIGH → **HIGH applies** (fail-safe)
Final Severity: HIGH

**CRv11-B** — Non-exhaustive two-case outcome in path (a)
Raised By: gc (MISSED_BY_ALL), cx (MISSED_BY_ALL), cc (MISSED_BY_ALL)
Description: Path (a) states only two outcome cases: "all such peers vote LOW → confirms LOW"
and "any other votes HIGH → HIGH applies." The general SEVERITY_CHALLENGE section explicitly
covers non-response (→ HIGH fail-safe) and non-standard responses (→ HIGH fail-safe), but
path (a) text is silent on these cases. If path (a) is read as a self-contained specification,
non-response/abstain outcomes are undefined.
Coordinator initial classification: LOW
Severity Challenge: cx votes HIGH → any HIGH → **HIGH applies** (fail-safe)
Final Severity: HIGH

---

## Mixed-Finding Handling (§14-5)

HIGH findings CRv11-A and CRv11-B present → CONSENSUS_OK invalidated.

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v11 | reason: §14 cross-review CRv11-A, CRv11-B]
Cross-review counter RESET — v12 proposal lineage begins.

LOW findings: NONE in this round.
Previously Accepted Risks (CRv10-B~H, CRv9-D/E, CR-10, CR-21~28) → Status: OPEN,
re-evaluated in first cross-review round of v12 lineage.

