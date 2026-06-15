# Amendment Debate: debate-protocol-amendment-crossreview
# Round 7

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v6 | reason: §14 cross-review CR-13, CR-14, CR-15]
Cross-review counter RESET — v7 proposal lineage begins.

---

[PROPOSAL: crossreview-amendment-20260613-v7]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5 — v7

### Summary of changes from v6

| # | Change | Source |
|:-:|:-------|:-------|
| 1–24 | All v6 changes retained | (see round6) |
| 25 | §14-5: Silent non-ABSENT peer in challenge vote → defaults to HIGH (fail-safe) | CR-13 (cx) |
| 26 | §14-5: "All non-ABSENT active peers must unanimously accept" — ABSENT peers excluded, not a veto | CR-14 (cx) |
| 27 | §14-5: H-2 options for refusing peer — remove "accept on behalf of team"; H-2 directs but does NOT substitute for unanimity | CR-15 (cx) |

---

### §14 Exhaustive Cross-Review Phase (끝장 교차검토) — v7 full text

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

**Severity Challenge:**
If any peer disagrees with a classification:
`[SEVERITY_CHALLENGE: finding_id | proposed: HIGH | reason: ...]`
Resolution: all non-ABSENT active peers respond HIGH or LOW within one round.
Vote outcomes (exhaustive):
- All non-ABSENT active peers vote LOW → LOW applies.
- Any non-ABSENT active peer votes HIGH → HIGH applies (fail-safe).
- A non-ABSENT active peer fails to respond within the round → their vote defaults to HIGH
  (fail-safe). Only peers marked ABSENT per §4-4 are excluded from the vote.
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

LOW acceptance refusal: If a peer refuses to accept a LOW finding as Accepted Risk, the
refusing peer must first challenge the severity via SEVERITY_CHALLENGE. If the challenge
vote confirms LOW and the peer still refuses acceptance, escalate to H-2 for that specific
finding. H-2 may: (a) direct the refusing peer to accept or reconsider, (b) narrow the
finding scope to resolve the disagreement, (c) split to SUB_ISSUE, or (d) ABORT(A-2).
H-2 mediation does not substitute for unanimous acceptance — if the peer ultimately accepts
after H-2 direction, normal Accepted Risk (§10) applies; if not, the debate ends via
SUB_ISSUE resolution or ABORT.

**Mixed-Finding Handling:**
When a single cross-review round yields both HIGH and LOW findings:
1. HIGH findings are processed first → CONSENSUS_REVOKE + new proposal lineage.
2. LOW findings from the same round are recorded in the ledger as Status: OPEN and
   re-evaluated in the first cross-review round of the new proposal lineage.
3. LOW findings are NOT automatically carried forward as Accepted Risk across lineage
   boundaries — they must be explicitly re-assessed in the new lineage.

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
Raised By: {peer}
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

### Changes 2–9 (unchanged from v7/v6/v5)

All other changes (§6 update, §8 diagram, §8 note, §15 DEFERRED, Appendix A, B-13, C, D)
are identical to v6. Only §14 section text is modified in this version.

---

Version-Tag: v7
Issued By: cc
Issued At: 2026-06-13T11:30:00Z
Status: CONSENSUS_OK

---

## Round 7 — Peer Responses

[PEER: gc] [ROUND: 7]
POSITION: AGREE
REASONING: v7 changes 25/26/27 correctly and thoroughly resolve CR-13, CR-14, CR-15. Silent non-ABSENT peer → HIGH default (CR-13); ABSENT exclusion aligned with §4-4 quorum (CR-14); H-2 dictatorial override removed while preserving sound resolution pathways (CR-15).
CONCERNS: NONE
OPEN_QUESTIONS: NONE
STATUS: AGREE
CR-10 Accepted Risk: YES

[PEER: cx] [ROUND: 7]
POSITION: AGREE
REASONING: Changes 25/26/27 adequately address CR-13/14/15. Challenge vote now has explicit non-response default for non-ABSENT active peers; ABSENT peers clearly excluded from unanimous LOW acceptance counts; H-2 cannot substitute for unanimous Accepted Risk acceptance. Fail-safe direction is consistent throughout.
CONCERNS: NONE
OPEN_QUESTIONS: NONE
STATUS: AGREE
CR-10 Accepted Risk: YES

---

[CONSENSUS_OK: crossreview-amendment-20260613-v7]
Consensus by: cc, gc, cx
Round: 7
Date: 2026-06-13T17:30:00Z

---

## §14 Cross-Review Phase — v7 Lineage

**Trigger:** CONSENSUS_OK on crossreview-amendment-20260613-v7
**Cross-review round counter:** RESET (new v7 lineage)
**Original debate rounds:** 7 (rounds 1-7)
**Cross-review round limit:** 7 × 3 = 21

### Step 1: PEER_SUMMARY Collection

[PEER_SUMMARY: cc]
Round 1 position: Proposed §14 Exhaustive Cross-Review Phase with dual scope — (a) all other peers' reasoning across all rounds AND (b) the final §9 Canonical Proposal text. Proposed binary CLEAN/GAPS_FOUND verdict, parallel query requirement (anti-anchoring), and infinite loop prevention via round-limit × 3.
Key concerns raised: Coordinator exemption edge case (resolved: not exempt unless ABSENT); infinite loop prevention design (§14-6); ledger schema completeness (§14-7); MISSED_BY_ALL vs per-peer distinction clarity; mixed HIGH+LOW finding handling; context bounding for PEER_SUMMARYs (§14-2 §4-5 alignment).
Concerns I dropped: Initial assumption that coordinator could author PEER_SUMMARYs for efficiency — dropped after gc raised CR-11 (single-point bias/failure), accepted as HIGH finding.
Final position: Agreed to v7 with all 27 changes. Every decision point now has a fail-safe: silent non-ABSENT peer defaults to HIGH; ABSENT peers excluded from all unanimous counts; H-2 cannot substitute for unanimous Accepted Risk acceptance. The protocol is self-reinforcing — any attempt to bypass unanimity routes through H-2 which has only narrowing/splitting/aborting options, not override options.

[PEER_SUMMARY: gc]
Round 1 position: Supported the core concept of adding the §14 Exhaustive Cross-Review Phase to establish a rigorous, mandatory review mechanism for critical changes, preventing premature or superficial consensus.
Key concerns raised: Naming inconsistency regarding "BOTH_MISSED" (Round 2); logical contradiction in §14-5 "brief unanimous vote" during challenge phase (Round 2); CR-11: coordinator bias risk during SUMMARY_DISPUTE resolution (Round 6); CR-12: deadlock potential from repeated LOW severity refusals without clear escape hatch (Round 6).
Concerns I dropped: NONE. All raised concerns were either actively resolved in subsequent drafts (v6/v7) or documented as Accepted Risk (CR-10).
Final position: AGREED to v7. The final draft successfully incorporates structural fixes (renaming to MISSED_BY_ALL, removing unanimous contradiction) and introduces robust mitigations for HIGH severity risks (CR-11 and CR-12), making the protocol safe and logically sound.

[PEER_SUMMARY: cx]
Round 1 position: Supported adding §14 Exhaustive Cross-Review, but required explicit handling for absent peers and quorum so unanimity could not be ambiguously claimed.
Key concerns raised: CR-2 ABSENT/quorum gap; CR-8 §14-4 quorum scope; CR-9 preserved-LOW loop guard; CR-13 silent non-ABSENT must be treated as HIGH fail-safe; CR-14 ABSENT peers must be excluded from unanimous count; CR-15 H-2 cannot substitute for §14 unanimity.
Concerns I dropped: NONE.
Final position: AGREED to v7 because it resolved the HIGH voting-state and unanimity gaps, incorporated the ABSENT/quorum safeguards, preserved loop guards, and left CR-10 as an accepted risk rather than a blocker.

---

### Step 2: §14 Cross-Review Round 1

[PEER: cc] [CROSS_REVIEW: round 1]
MISSED_BY_gc: NONE
WRONG_BY_gc: NONE
PREMATURE_CONSENSUS_BY_gc: NONE
MISSED_BY_cx: NONE
WRONG_BY_cx: NONE
PREMATURE_CONSENSUS_BY_cx: NONE
MISSED_BY_ALL: NONE. After 7 rounds of intensive review, all structural gaps have been identified and addressed. §14 correctly delegates ABSENT gaming prevention to §4-4. Context bounding, loop guards, mixed-finding handling, fail-safe defaults, and H-2 scope limits are all present and internally consistent.
VERDICT: CLEAN

[PEER: cx] [CROSS_REVIEW: round 1]
MISSED_BY_cc: §14-2 summary-bounding weakens "exhaustive" — if peers only receive self-summaries, they cannot independently review "all other peers' reasoning across ALL rounds"; they can only review the bounded summary. This creates a self-reporting blind spot.
WRONG_BY_cc: Treating v7 as having "all decision point fail-safes" is too strong. §14-5 still underspecifies voting/disposition state when multiple LOW findings, severity challenges, refusals, and H-2 mediation occur concurrently or across lineage resets.
PREMATURE_CONSENSUS_BY_cc: Accepted v7 before resolving whether SUMMARY_DISPUTE can deadlock if the original summary author refuses to revise, disputes the dispute, becomes ABSENT, or repeatedly submits an inadequate revision.
MISSED_BY_gc: CR-11 identified coordinator bias in summary handling, but gc did not carry that through to the deeper issue: peer-authored summaries can still be selectively incomplete, and the protocol has no completeness standard or audit mechanism against the actual debate log.
WRONG_BY_gc: Stating that the "brief unanimous vote" contradiction was removed may be incomplete. §14-5 no longer says "brief," but still has several vote-like states without a complete state machine: challenge opened, votes pending/defaulted, LOW accepted/refused, H-2 directed, split to SUB_ISSUE, aborted, or carried to new lineage.
PREMATURE_CONSENSUS_BY_gc: Agreed to v7 despite unresolved interaction between §14-4 termination and §14-5 LOW handling: the text says LOW disposition needs no additional CLEAN round, but §14 terminates only when all active peers declare CLEAN in the same round. That exception should be explicit in §14-4, not only implied later.
MISSED_BY_ALL:
  1. SUMMARY_DISPUTE has no timeout, escalation path, or final authority when the author does not revise acceptably.
  2. "Parallel query" is underspecified operationally: who timestamps/submits, where drafts are held, what counts as "before any peer sees another's response," and what happens after a violation.
  3. The ledger schema lacks stable finding IDs, parent/child links for split findings, challenge voter records, timestamps/round numbers, and explicit closure criteria.
  4. "Active peer" versus "non-ABSENT active peer" should be normalized. Some clauses say active peers, some say non-ABSENT active peers, and the coordinator status can change mid-process.
  5. Preserved-LOW loop guard is unclear when the original debate round count is 0/1, when multiple LOW findings are merged/split, or when the finding changes scope across lineages.
  6. No rule defines whether new peers added mid-lineage participate in existing §14 votes, CLEAN termination, or preserved LOW lineage counts.
  7. Severity classification says HIGH if it "changes proposal text," but a finding about wording ambiguity may require proposal text changes while not changing behavior. That makes many editorial clarifications automatically HIGH, possibly over-invalidating consensus.
  8. The protocol does not define how to handle duplicate findings raised by multiple peers in the same round before assigning ledger status.
VERDICT: GAPS_FOUND

[PEER: gc] [CROSS_REVIEW: round 1]
MISSED_BY_cc:
  1. Challenge Vote State Gap: explicit non-standard votes (ABSTAIN, NEED_MORE_INFO) are undefined — they bypass the "fails to respond" fail-safe but are neither HIGH nor LOW.
  2. LOW Action Silent Deadlock: no timeout or default for non-ABSENT peer who silently ignores LOW acceptance request.
  3. Historical LOWs during Revoke: previously accepted LOW findings from EARLIER cross-review rounds in a revoked lineage — preserved, discarded, or re-evaluated? Protocol is silent.
WRONG_BY_cc: NONE
PREMATURE_CONSENSUS_BY_cc: Declared CONSENSUS_OK on v7 without verifying completeness of state transitions for non-standard inputs in voting phases.
MISSED_BY_cx:
  1. Silent Deadlock in LOW Action: cx pushed CR-13 (silent non-ABSENT = HIGH fail-safe for challenge votes) but did not apply the same rigor to the LOW Accepted Risk acceptance phase.
  2. Unclassifiable Findings: finding that fits neither HIGH "any of" list nor satisfies all LOW criteria — coordinator has no protocol-defined action.
  3. §14-2 SUMMARY_DISPUTE infinite loop vector: peer can block cross-review indefinitely with no H-2 escalation pathway.
WRONG_BY_cx: NONE
PREMATURE_CONSENSUS_BY_cx: Agreed to loop prevention mechanisms while missing the trivial SUMMARY_DISPUTE infinite loop in §14-2.
MISSED_BY_ALL:
  1. §14-2 SUMMARY_DISPUTE Infinite Loop: no termination condition or H-2 escalation if peer repeatedly flags a self-summary as inaccurate.
  2. §14-5 Unclassifiable Findings Gap: HIGH "any of" and LOW "ALL of" are not logically exhaustive — a finding can fit neither.
  3. §14-5 Historical LOW Findings during Revoke: protocol handles same-round mixed findings but is silent on previously accepted LOWs from earlier rounds in revoked lineage.
  4. §14-5 Challenge Vote State Gap: "exhaustive" vote outcomes do not account for explicit non-standard votes (ABSTAIN, NEED_MORE_INFO).
  5. §14-5 LOW Acceptance Missing Fail-safe: "All non-ABSENT active peers must unanimously accept" lacks a silence/timeout fail-safe.
VERDICT: GAPS_FOUND

---

### §14 Cross-Review Round 1 — Finding Classification (cc coordinator)

Findings CR-16 through CR-28 (overlap/dedup of gc + cx MISSED_BY_ALL):

**HIGH (5):**
[CR-16] SUMMARY_DISPUTE infinite loop / no escalation path [gc#1, cx#1]
[CR-17] Unclassifiable findings gap — neither HIGH nor LOW classification possible [gc#2, cx#2]
[CR-18] Historical LOW findings during revoke — previously RESOLVED_LOW from earlier rounds [gc#3]
[CR-19] Challenge Vote State Gap — non-standard votes (ABSTAIN, NEED_MORE_INFO) bypass all outcomes [gc#4]
[CR-20] LOW Acceptance silent deadlock — no fail-safe for non-ABSENT peer ignoring acceptance [gc#5]

**LOW (8):**
[CR-21] "Parallel query" operationally underspecified (who timestamps, what counts as violation) [cx#2]
[CR-22] Ledger schema gaps (parent/child for split findings, timestamps, closure criteria) [cx#3]
[CR-23] "active peer" vs "non-ABSENT active peer" wording inconsistency across clauses [cx#4]
[CR-24] Preserved-LOW loop guard edge cases (debate rounds = 0/1, merged/split findings) [cx#5]
[CR-25] New peers added mid-lineage — no rule for §14 participation [cx#6]
[CR-26] HIGH criterion "changes proposal text" may over-invalidate editorial clarifications [cx#7]
[CR-27] Duplicate findings raised by multiple peers in same round — no handling rule [cx#8]
[CR-28] Summary completeness — no audit mechanism against full debate log [cx MISSED_BY_cc#1, gc MISSED_BY_cx#1]

**Mixed-Finding Handling per §14-5:**
- HIGH findings (CR-16~20) processed first → CONSENSUS_REVOKE + new lineage
- LOW findings (CR-21~28) recorded as Status: OPEN, re-evaluated in v8 lineage first cross-review round
- CR-10 (previously accepted Accepted Risk in this lineage): status unclear due to CR-18 gap itself; preserved tentatively as OPEN pending CR-18 fix in v8

---

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v7 | reason: §14 cross-review CR-16, CR-17, CR-18, CR-19, CR-20]
Cross-review counter RESET — v8 proposal lineage begins.
Low findings CR-21~28 preserved as OPEN for re-evaluation in v8 first cross-review round.
