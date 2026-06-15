# Amendment Debate: debate-protocol-amendment-crossreview
# Round 8

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v7 | reason: §14 cross-review CR-16, CR-17, CR-18, CR-19, CR-20]
Cross-review counter RESET — v8 proposal lineage begins.

---

[PROPOSAL: crossreview-amendment-20260613-v8]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5 — v8

### Summary of changes from v7

| # | Change | Source |
|:-:|:-------|:-------|
| 1–27 | All v7 changes retained | (see round7) |
| 28 | §14-2: SUMMARY_DISPUTE escalation — max 2 revision cycles; unresolvable dispute → H-2 | CR-16 (gc+cx) |
| 29 | §14-5: Default-to-HIGH for unclassifiable findings (fail-safe classification) | CR-17 (gc) |
| 30 | §14-5: Historical RESOLVED_LOW re-evaluation rule when CONSENSUS_REVOKE occurs in later round | CR-18 (gc) |
| 31 | §14-5: Non-standard challenge votes (ABSTAIN, NEED_MORE_INFO) → default to HIGH fail-safe | CR-19 (gc) |
| 32 | §14-5: LOW Acceptance silence → treated as refusal; refusal path applies with one-round escalation | CR-20 (gc) |

---

### §14 Exhaustive Cross-Review Phase (끝장 교차검토) — v8 full text

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
`[SEVERITY_CHALLENGE: finding_id | proposed: HIGH | reason: ...]`
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
acceptance. The LOW refusal rules apply: the non-responding peer must challenge the
severity via SEVERITY_CHALLENGE within one additional round. If the peer fails to
challenge within that round, the matter is escalated to H-2.

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

### Changes 2–9 (unchanged from v8/v7/v6/v5)

All other changes (§6 update, §8 diagram, §8 note, §15 DEFERRED, Appendix A, B-13, C, D)
are identical to v7. Only §14 section text is modified in this version.

---

Version-Tag: v8
Issued By: cc
Issued At: 2026-06-13T18:00:00Z
Status: NO_CONSENSUS

---

## Round 8 — Peer Responses

[PEER: gc] [ROUND: 8]
POSITION: DISAGREE
REASONING: CR-20 fix incomplete — non-standard LOW acceptance responses (ABSTAIN, NEED_MORE_INFO) not handled. SEVERITY_CHALLENGE example only shows `proposed: HIGH`, should allow both directions. CR-27 needs explicit text not Accepted Risk.
CONCERNS: 1. CR-20 non-standard response clause missing. 2. SEVERITY_CHALLENGE format. 3. CR-27 text needed.
OPEN_QUESTIONS: NONE
STATUS: DISAGREE
CR-21~26, 28: Accepted Risk YES / CR-27: NO

[PEER: cx] [ROUND: 8]
POSITION: DISAGREE
REASONING: CR-20 only partially addressed — silence handled but ABSTAIN/NEED_MORE_INFO bypass "fails to respond" rule. SEVERITY_CHALLENGE example `proposed: HIGH` only. CR-27 needs text for auditable ledger.
CONCERNS: CR-20 non-standard response. SEVERITY_CHALLENGE direction. CR-27 text.
OPEN_QUESTIONS: NONE
STATUS: DISAGREE
CR-21~26, 28: Accepted Risk YES / CR-27: NO

Open LOW findings from v7 cross-review (re-evaluated this lineage):
[CR-21] "Parallel query" operationally underspecified — OPEN
[CR-22] Ledger schema gaps (parent/child for split findings, timestamps, closure criteria) — OPEN
[CR-23] "active peer" vs "non-ABSENT active peer" wording inconsistency — OPEN
[CR-24] Preserved-LOW loop guard edge cases (0/1 rounds, merged/split) — OPEN
[CR-25] New peers added mid-lineage — OPEN
[CR-26] HIGH criterion "changes proposal text" may over-invalidate editorial clarifications — OPEN
[CR-27] Duplicate findings raised by multiple peers in same round — OPEN
[CR-28] Summary completeness — no audit mechanism against full debate log — OPEN
[CR-10] "inconsistent interpretation" adjudication — OPEN (status reset per CR-18; was Accepted Risk in v7 lineage)
