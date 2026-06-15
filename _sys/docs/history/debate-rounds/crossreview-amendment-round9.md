# Amendment Debate: debate-protocol-amendment-crossreview
# Round 9

[PROPOSAL: crossreview-amendment-20260613-v9]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5 — v9

### Summary of changes from v8

| # | Change | Source |
|:-:|:-------|:-------|
| 1–32 | All v8 changes retained | (see round8) |
| 33 | §14-5: LOW acceptance — non-standard responses (ABSTAIN etc.) treated as refusal | CR-20 full fix (gc+cx) |
| 34 | §14-5: SEVERITY_CHALLENGE example updated — shows both HIGH and LOW directions | gc+cx R8 concern |
| 35 | §14-5/§14-7: Duplicate findings — single ledger entry, all raisers listed | CR-27 (gc+cx) |

---

### §14 Exhaustive Cross-Review Phase (끝장 교차검토) — v9 full text

**Trigger:** Immediately after CONSENSUS_OK (§6), before §7 documentation and implementation.

**Purpose:** Adversarially validate that no structural gaps, logical errors, or missing
considerations escaped the debate. Each peer acts as an independent critic of all other
peers' reasoning and the final proposal — not just a reviewer of the output.

---

**14-1. Scope**

Each active peer (including coordinator) cross-reviews:

(a) All other peers' reasoning across ALL rounds
    — Missed concerns? Conclusions reached too quickly? Wrong positions adopted?
    Note: the MISSED_BY_ALL field also requires assessing collective debate blind spots,
    including the reviewer's own prior omissions.

(b) The final §9 Canonical Proposal (full text)
    — Internal inconsistencies? Underspecified parts? Dangerous assumptions?

Coordinator is NOT exempt from submitting CROSS_REVIEW unless explicitly marked ABSENT.
Queries must be written and sent in parallel before any peer sees another's response.

---

**14-2. Peer Self-Summary (Pre-Cross-Review Input)**

Before cross-review queries are sent, each peer writes their own position summary
(NOT authored by coordinator — each peer summarizes their own reasoning):

```
[PEER_SUMMARY: {name}]
Round 1 position: (key stance)
Key concerns raised: (list or NONE)
Concerns I dropped: (and why — or NONE)
Final position: (what I agreed to and why)
```

Coordinator collects all summaries and distributes them with the cross-review query.
Any peer may flag an inaccurate self-summary:
`[SUMMARY_DISPUTE: peer_name | what is wrong]`
— the original authoring peer must revise and resubmit their own summary before
cross-review proceeds. Coordinator distributes the revised summary but does NOT
edit peer summary content.

SUMMARY_DISPUTE resolution limit: the authoring peer has a maximum of 2 revision
attempts. If the peer cannot produce an acceptable revision within 2 attempts, or if the
peer becomes ABSENT during dispute resolution, the dispute is automatically escalated to
H-2. H-2 may: (a) rule the original summary acceptable as-is, (b) direct the authoring
peer to incorporate specific corrections, (c) proceed with cross-review treating the
disputing peer's concerns as noted-but-unresolved in the ledger, or (d) ABORT(A-2).
H-2 does NOT author or edit summary content.

Context note: PEER_SUMMARYs distributed by the coordinator are the bounded representation
of each peer's prior reasoning for §14 purposes. No additional context is loaded by peers
beyond what the coordinator distributes. This is consistent with §4-5: the coordinator
packages the complete permitted context for each §14 round.

---

**14-3. Cross-Review Response Format**

```
[PEER: {name}] [CROSS_REVIEW: round {n}]
MISSED_BY_{PEER_A}: (or NONE)
WRONG_BY_{PEER_A}: (or NONE)
PREMATURE_CONSENSUS_BY_{PEER_A}: (or NONE)
[repeat per peer reviewed]
MISSED_BY_ALL: (gaps NO peer raised — most critical)
VERDICT: CLEAN | GAPS_FOUND
```

CLEAN is ONLY valid when ALL of the following are true:
- All MISSED_BY, WRONG_BY, PREMATURE_CONSENSUS_BY fields = NONE
- MISSED_BY_ALL = NONE
- No open questions remain
If any field is non-NONE, VERDICT MUST be GAPS_FOUND (declaring CLEAN with listed gaps is an anti-pattern).

---

**14-4. Termination Condition**

Cross-review terminates when ALL active peers declare VERDICT: CLEAN in the SAME round.
Silence is NOT CLEAN — explicit declaration required.

ABSENT peer handling: §4-4 ABSENT peer rules and N-1 quorum requirements apply to ALL
§14 processes — including CLEAN termination, severity challenge votes, and LOW Accepted
Risk acceptance. A peer marked ABSENT per §4-4 protocol does not block any of these
processes.

LOW disposition exception: when all LOW findings from a cross-review round have been
fully dispositioned as Accepted Risk (per §14-5 LOW action), no additional CLEAN round
is required for those findings — proceed to §7 after all LOW findings are dispositioned.
This exception applies only after unanimous non-ABSENT acceptance; it does not waive the
CLEAN round requirement for any remaining unresolved findings.

---

**14-5. Finding Handling**

When GAPS_FOUND, coordinator classifies each finding:

**Severity HIGH** (any of the following):
- Changes the proposal text, acceptance criteria, or affected artifacts
- Invalidates a confirmed assumption
- Introduces or removes a safety/security constraint
- Alters risk class (NORMAL ↔ HIGH_RISK)
- Affects portability or compatibility
- Reveals the CONSENSUS_OK was invalid: quorum was miscounted, a peer's assent was
  conditional or withheld, or the proposal text was interpreted inconsistently between
  agreeing peers

**Severity LOW** (ALL of the following must be true):
- Cannot change implementation behavior
- Cannot change user-facing risk
- Cannot alter consensus meaning
- Cannot affect acceptance criteria

**Unclassifiable findings (fail-safe default):**
If a finding fails any LOW criterion (cannot be classified as LOW) but does not
explicitly match any HIGH criterion, the coordinator defaults to HIGH classification.
Any peer may challenge this default classification via SEVERITY_CHALLENGE.

**Severity Challenge:**
If any peer disagrees with a classification:
`[SEVERITY_CHALLENGE: finding_id | proposed: HIGH or LOW | reason: ...]`
A peer may challenge in either direction — proposing HIGH if they believe the
coordinator's LOW classification is incorrect, or proposing LOW if they believe the
coordinator's HIGH classification is incorrect.
Resolution: all non-ABSENT active peers respond HIGH or LOW within one round.
Vote outcomes (exhaustive):
- All non-ABSENT active peers vote LOW → LOW applies.
- Any non-ABSENT active peer votes HIGH → HIGH applies (fail-safe).
- A non-ABSENT active peer fails to respond within the round → their vote defaults to HIGH
  (fail-safe). Only peers marked ABSENT per §4-4 are excluded from the vote.
- Any non-ABSENT active peer submits a non-standard response (e.g., ABSTAIN,
  NEED_MORE_INFO) → treated as failure to respond; defaults to HIGH (fail-safe).
Challenge does NOT automatically invalidate CONSENSUS_OK; it only triggers a vote.

**HIGH action:**
1. CONSENSUS_OK invalidated: `[CONSENSUS_REVOKE: {proposal-id} | reason: §14 finding]`
2. Re-enter §3 at affected nodes; new proposal version issued
3. Cross-review round counter RESETS for the new proposal lineage (new debate segment begins)
4. Old cross-review rounds preserved in audit log but not counted in new limit

**LOW action:**
All non-ABSENT active peers must unanimously accept finding as Accepted Risk (§10 entry).
An ABSENT peer's absence is not a veto — peers marked ABSENT per §4-4 are excluded from
the unanimous count. Once all non-ABSENT active peers accept: no new proposal version
required; no additional CLEAN round required. Proceed to §7 after all LOW findings are
dispositioned.

LOW acceptance failure to respond: A non-ABSENT active peer who fails to respond to a
LOW finding Accepted Risk acceptance request within one round is treated as having refused
acceptance. The LOW refusal rules apply (see below).

LOW acceptance non-standard response: Any response to a LOW finding Accepted Risk
acceptance request that is neither an explicit acceptance nor an explicit refusal (e.g.,
ABSTAIN, NEED_MORE_INFO, or any non-standard response) is treated as refusal. The LOW
refusal rules apply.

LOW acceptance refusal: If a peer refuses to accept a LOW finding as Accepted Risk (via
explicit refusal, silence, or non-standard response), the refusing peer must challenge the
severity via SEVERITY_CHALLENGE within one round. If the challenge vote confirms LOW and
the peer still refuses acceptance, escalate to H-2 for that specific finding. H-2 may:
(a) direct the refusing peer to accept or reconsider, (b) narrow the finding scope to
resolve the disagreement, (c) split to SUB_ISSUE, or (d) ABORT(A-2). H-2 mediation does
not substitute for unanimous acceptance — if the peer ultimately accepts after H-2
direction, normal Accepted Risk (§10) applies; if not, the debate ends via SUB_ISSUE
resolution or ABORT. If the refusing peer fails to challenge within one round, the matter
is escalated to H-2.

**Duplicate Findings:**
When multiple peers raise identical or substantially overlapping findings in the same
cross-review round, the coordinator assigns a single ledger entry with all raising peers
listed in the Raised By field. No duplicate entries are created for the same finding.
The coordinator determines whether findings are identical or overlapping; any peer may
dispute this determination via SEVERITY_CHALLENGE on the merged entry.

**Mixed-Finding Handling:**
When a single cross-review round yields both HIGH and LOW findings:
1. HIGH findings are processed first → CONSENSUS_REVOKE + new proposal lineage.
2. LOW findings from the same round are recorded in the ledger as Status: OPEN and
   re-evaluated in the first cross-review round of the new proposal lineage.
3. LOW findings are NOT automatically carried forward as Accepted Risk across lineage
   boundaries — they must be explicitly re-assessed in the new lineage.

**Historical LOW Findings during CONSENSUS_REVOKE:**
When a HIGH finding in a later cross-review round triggers CONSENSUS_REVOKE, previously
RESOLVED_LOW findings (Accepted Risks) from earlier cross-review rounds within the same
lineage are reclassified as Status: OPEN and must be re-evaluated in the first cross-review
round of the new lineage. If the new proposal does not change the area covered by the
Accepted Risk, peers may confirm existing acceptance with a simple re-accept vote (explicit
"re-accept" response) rather than full re-debate. If the new proposal changes the relevant
area, full re-evaluation is required.

---

**14-6. Infinite Loop Prevention**

Cross-review round limit per proposal lineage: original debate rounds × 3.
If exceeded → H-2 escalation (user mediation, not automatic acceptance or abort).
H-2 may decide: continue, narrow scope to specific finding, split to SUB_ISSUE, or ABORT(A-2).

"Original debate rounds" = rounds from proposal creation to first CONSENSUS_OK for the current
proposal lineage. Resets when a new proposal version is created due to HIGH finding.

Preserved-LOW loop guard: a LOW finding carried into N or more new proposal lineages
without unanimous Accepted Risk disposition is automatically escalated to H-2 for that
specific finding, where N = the original debate round count at the time the finding was
first recorded. This prevents preserved LOW findings from bouncing indefinitely across
lineage resets.

---

**14-7. Ledger Entries**

Each finding goes into the Open Issues Ledger with this schema:
```
[CROSSREVIEW-{n}] Status: OPEN | RESOLVED_HIGH | RESOLVED_LOW | ARCHIVED
Found In: CROSS_REVIEW round {n}
Raised By: {peer} (or {peer1}, {peer2} for merged duplicate findings)
Type: MISSED_BY | WRONG_BY | PREMATURE_CONSENSUS | MISSED_BY_ALL
Description:
Severity: HIGH | LOW | CHALLENGED
Challenge: (if any, with resolution)
Disposition:
  HIGH: New proposal v{n}; affected §3 nodes: {list}
  LOW: Accepted Risk #{n}
Proposal After: {new-proposal-id or "unchanged"}
Lineage Count: {number of lineages this finding has been carried into, if preserved LOW}
```

Note: Severity field uses HIGH or LOW (CRITICAL is subsumed into HIGH — same action applies).
Preserved LOW findings include a Lineage Count field to track the loop guard threshold.

---

### Changes 2–9 (unchanged from v9/v8/v7/v6/v5)

All other changes (§6 update, §8 diagram, §8 note, §15 DEFERRED, Appendix A, B-13, C, D)
are identical to v8. Only §14 section text is modified in this version.

---

Version-Tag: v9
Issued By: cc
Issued At: 2026-06-13T18:15:00Z
Status: CONSENSUS_OK

---

## Round 9 — Peer Responses

[PEER: gc] [ROUND: 9]
POSITION: AGREE
REASONING: v9 resolves all three v8 concerns. Non-standard LOW acceptance gap fully closed. SEVERITY_CHALLENGE bidirectional explicitly clarified. Duplicate findings now have clean merged ledger protocol.
CONCERNS: NONE / OPEN_QUESTIONS: NONE / STATUS: AGREE
CR-21~26, 28, CR-10: Accepted Risk YES

[PEER: cx] [ROUND: 9]
POSITION: AGREE
REASONING: CR-20 exhaustive (explicit refusal + silence + non-standard → refusal → SEVERITY_CHALLENGE/H-2). SEVERITY_CHALLENGE bidirectional. CR-27 single-entry ledger rule correct.
CONCERNS: NONE / OPEN_QUESTIONS: NONE / STATUS: AGREE
CR-21~26, 28, CR-10: Accepted Risk YES

---

[CONSENSUS_OK: crossreview-amendment-20260613-v9]
Consensus by: cc, gc, cx
Round: 9
Date: 2026-06-13T18:20:00Z

---

## §14 Cross-Review Phase — v9 Lineage

**Trigger:** CONSENSUS_OK on crossreview-amendment-20260613-v9
**Cross-review round counter:** RESET (new v9 lineage — same as v8 lineage, started after v7 CONSENSUS_REVOKE)
**Original debate rounds in this lineage:** 2 (rounds 8 and 9)
**Cross-review round limit:** 2 × 3 = 6

### Accepted Risks (cr-21~28, cr-10) — Unanimous in Round 9:
[CR-10] Accepted Risk: coordinator judgment + challenge mechanism sufficient for inconsistent interpretation adjudication
[CR-21] Accepted Risk: parallel query operational details are implementation concern, not protocol gap
[CR-22] Accepted Risk: ledger schema basic structure sufficient; parent/child links are implementation enhancements
[CR-23] Accepted Risk: "active peer" / "non-ABSENT active peer" inconsistency covered by §14-4 ABSENT note
[CR-24] Accepted Risk: preserved-LOW loop guard edge cases (0/1 rounds) are outside normal flow
[CR-25] Accepted Risk: new peers mid-lineage is rare edge case governed by §4-4
[CR-26] Accepted Risk: SEVERITY_CHALLENGE mechanism provides the escape valve for editorial HIGH classification
[CR-27] ADDRESSED IN V9 — duplicate findings rule added to §14-5
[CR-28] Accepted Risk: summary completeness is architectural trade-off; SUMMARY_DISPUTE and cross-review catch dishonest summaries

### Step 1: PEER_SUMMARY Collection

[PEER_SUMMARY: cc]
Round 1 position: Proposed §14 Exhaustive Cross-Review Phase with dual scope (peer reasoning + final proposal), binary CLEAN/GAPS_FOUND verdict, parallel queries (anti-anchoring), and loop prevention (round limit × 3).
Key concerns raised: Coordinator exemption; loop prevention (§14-6); ledger schema (§14-7); MISSED_BY_ALL distinction; mixed HIGH+LOW handling; context bounding (§14-2/§4-5 alignment). As cross-review coordinator for v7 lineage: classified CR-16~20 HIGH (SUMMARY_DISPUTE loop, unclassifiable gap, historical LOWs, non-standard votes, LOW acceptance deadlock), CR-21~28 LOW.
Concerns I dropped: Coordinator authoring PEER_SUMMARYs — dropped after gc raised CR-11 (HIGH). 
Final position: AGREE on v9 with all 35 changes. All structural gaps, deadlock vectors, and voting state machine holes are addressed.

[PEER_SUMMARY: gc]
Round 1 position: Supported §14 addition but required rigorous criteria to prevent coordinator bias, infinite loops, and subjective severity thresholds.
Key concerns raised: Coordinator bias and severity voting fail-safes (Rounds 1-3); CR-16 (SUMMARY_DISPUTE loop); CR-17 (unclassifiable gaps); CR-18 (historical LOWs during revoke); CR-19 (non-standard challenge votes); CR-20 (LOW acceptance deadlocks); CR-21~28 LOW findings; Round 8: CR-20 partial, SEVERITY_CHALLENGE direction, CR-27 text.
Concerns I dropped: NONE. CR-10, CR-21~26, CR-28 accepted as Accepted Risks (dispositions, not withdrawals).
Final position: AGREE on v9. All blockers resolved. v9 §14 is secure and exhaustive.

[PEER_SUMMARY: cx]
Round 1 position: Supported §14 but required structural enforceability — coordinator included, no silent consensus, quorum/ABSENT explicit, no extra CLEAN round after LOW acceptance.
Key concerns raised: §14 structure issues (Rounds 1-3); CR-1/2/4/8/9/13/14/15/16 (context bounding, ABSENT quorum, LOW no-clean, non-ABSENT fail-safes, SUMMARY_DISPUTE loop); CR-21~28 LOW findings; Round 8: CR-20 non-standard responses, SEVERITY_CHALLENGE direction, CR-27 ledger.
Concerns I dropped: NONE. Accepted Risks and text additions are dispositions.
Final position: AGREE on v9. All blockers resolved. CR-10, CR-21~26, CR-28 accepted as Accepted Risks.

---

### Step 2: §14 Cross-Review Round 1 (v9 lineage)

[PEER: cc] [CROSS_REVIEW: round 1]
MISSED_BY_gc: NONE
WRONG_BY_gc: NONE
PREMATURE_CONSENSUS_BY_gc: NONE
MISSED_BY_cx: NONE
WRONG_BY_cx: NONE
PREMATURE_CONSENSUS_BY_cx: NONE
MISSED_BY_ALL: NONE
VERDICT: CLEAN

[PEER: cx] [CROSS_REVIEW: round 1]
MISSED_BY_cc: 1. Active-peer snapshot rule missing — voting set not frozen when vote opens. 2. CR-27 fix incomplete — SEVERITY_CHALLENGE can't adjudicate MERGE/SPLIT. 3. v9 artifact CR-10/CR-21~28 listed as both Accepted Risks AND OPEN/re-eval pending.
WRONG_BY_cc: "All voting state machine holes addressed" too strong — active-set snapshot gap remains.
PREMATURE_CONSENSUS_BY_cc: Agreed to v9 before resolving voting-state ambiguity and before ledger status was internally consistent.
MISSED_BY_gc: 1. Duplicate dispute uses wrong mechanism. 2. v9 contradiction between Accepted Risk YES and OPEN/re-eval-pending status.
WRONG_BY_gc: "Duplicate findings now have clean merged ledger protocol" — dispute path has no valid decision grammar.
PREMATURE_CONSENSUS_BY_gc: Agreed to v9 without validating logical coherence of using SEVERITY_CHALLENGE for non-severity disputes.
MISSED_BY_ALL:
  1. Vote/acceptance roster not snapshotted per opened §14 process.
  2. Duplicate-finding disputes need MERGE/SPLIT mechanism, not SEVERITY_CHALLENGE.
  3. Historical LOW "simple re-accept vote" not tied to LOW acceptance failure/refusal rules.
  4. v9 ledger: CR-10/CR-21~28 Accepted Risks AND OPEN re-eval pending — contradictory.
VERDICT: GAPS_FOUND

[PEER: gc] [CROSS_REVIEW: round 1]
MISSED_BY_cc: 1. Category error in §14-5 Duplicate Findings (SEVERITY_CHALLENGE can't answer MERGE/SPLIT). 2. LOW acceptance refusal exploit — refusing peer forced to challenge; any HIGH vote triggers CONSENSUS_REVOKE, bypassing H-2.
WRONG_BY_cc: Claimed all voting state machine holes addressed — SEVERITY_CHALLENGE misuse and refusal exploit remain.
PREMATURE_CONSENSUS_BY_cc: Declared CLEAN without tracing SEVERITY_CHALLENGE state machine against non-severity disputes.
MISSED_BY_cx: 1. Duplicate Findings category error (despite reviewing CR-27). 2. LOW refusal exploit (despite reviewing CR-20 pathways).
WRONG_BY_cx: Supported using SEVERITY_CHALLENGE for Duplicate Findings disputes — structural impossibility.
PREMATURE_CONSENSUS_BY_cx: Agreed to v9 without validating logical coherence of forcing severity vote for non-severity disagreements.
MISSED_BY_ALL:
  1. Category error in duplicate disputes — HIGH/LOW vote cannot answer MERGE/SPLIT question.
  2. LOW Refusal Exploit — refusing peer forced to challenge; peer votes HIGH in own challenge → unilateral CONSENSUS_REVOKE; bypasses H-2; destroys HIGH/LOW distinction.
VERDICT: GAPS_FOUND

---

### §14 Cross-Review Round 1 — Finding Classification (cc coordinator)

[CRv9-A] HIGH: Duplicate-finding dispute mechanism uses SEVERITY_CHALLENGE (type mismatch: HIGH/LOW ≠ MERGE/SPLIT) [cx#2, gc#1]
[CRv9-B] HIGH: LOW Refusal Exploit — refusing peer forced to use SEVERITY_CHALLENGE, can vote HIGH unilaterally → CONSENSUS_REVOKE; bypasses H-2 [gc#2]
[CRv9-C] HIGH: Historical LOW re-accept refusal not linked to LOW refusal rules [cx#3]
[CRv9-D] LOW: Vote/acceptance roster snapshot not frozen per opened vote [cx#1]
[CRv9-E] LOW: CR-10/CR-21~28 artifact status inconsistency (document fix only) [cx#4]

Open LOW findings from v7 cross-review (re-evaluated this lineage):
[CR-21] "Parallel query" operationally underspecified — OPEN (re-eval pending)
[CR-22] Ledger schema gaps — OPEN (re-eval pending)
[CR-23] "active peer" vs "non-ABSENT active peer" normalization — OPEN (re-eval pending)
[CR-24] Preserved-LOW loop guard edge cases — OPEN (re-eval pending)
[CR-25] New peers added mid-lineage — OPEN (re-eval pending)
[CR-26] HIGH criterion may over-invalidate editorial changes — OPEN (re-eval pending)
[CR-27] Duplicate findings handling — addressed in v9 §14-5; CLOSED pending acceptance
[CR-28] Summary completeness — OPEN (re-eval pending)
[CR-10] "inconsistent interpretation" adjudication — OPEN (re-eval pending, status reset per CR-18 fix)

---

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v9 | reason: §14 cross-review CRv9-A, CRv9-B, CRv9-C]
Cross-review counter RESET — v10 proposal lineage begins.
Low findings CRv9-D, CRv9-E preserved as OPEN for re-evaluation in v10 lineage.
Note: CR-10, CR-21~28 (previously Accepted Risks in v9) reclassified as OPEN per CR-18 rule (CONSENSUS_REVOKE in later round); simple re-accept vote available in v10 lineage if new proposal does not change their areas.
