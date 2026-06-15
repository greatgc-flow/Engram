# Amendment Debate: debate-protocol-amendment-crossreview
# Round 4

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v3 | reason: §14 cross-review CR-1, CR-2, CR-3, CR-4]
Cross-review counter RESET — v4 proposal lineage begins.

---

[PROPOSAL: crossreview-amendment-20260613-v4]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5 — v4

### Summary of changes from v3

| # | Change | Source |
|:-:|:-------|:-------|
| 1–16 | All v3 changes retained | (see round3) |
| 17 | §14-2: Add context bounding note — PEER_SUMMARYs are coordinator-provided input, consistent with §4-5 | CR-1 (cc+cx) |
| 18 | §14-4: Add ABSENT peer handling — §4-4 quorum rules (N-1) apply to §14 termination | CR-2 (cc+cx) |
| 19 | §14-5: Add mixed HIGH+LOW finding rule — HIGH processed first; LOW preserved and re-evaluated in new lineage | CR-3 (gc) |
| 20 | §14-5: Narrow "consensus validity" criterion — concrete §6 prerequisites only | CR-4 (cx) |

---

### §14 Exhaustive Cross-Review Phase (끝장 교차검토) — v4 full text

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
Any peer may flag an inaccurate self-summary: `[SUMMARY_DISPUTE: peer_name | what is wrong]`
— coordinator must correct before cross-review proceeds.

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

ABSENT peer handling: §4-4 quorum rules (N-1 minimum) apply to §14 termination.
A peer marked ABSENT per §4-4 protocol does not block termination of the cross-review phase.

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
Resolution: all active peers respond HIGH or LOW within one round.
Vote outcomes (exhaustive):
- Unanimous LOW (all peers vote LOW) → LOW applies.
- Any other outcome (at least one HIGH vote) → HIGH applies (fail-safe).
Challenge does NOT automatically invalidate CONSENSUS_OK; it only triggers a vote.

**HIGH action:**
1. CONSENSUS_OK invalidated: `[CONSENSUS_REVOKE: {proposal-id} | reason: §14 finding]`
2. Re-enter §3 at affected nodes; new proposal version issued
3. Cross-review round counter RESETS for the new proposal lineage (new debate segment begins)
4. Old cross-review rounds preserved in audit log but not counted in new limit

**LOW action:**
All active peers must unanimously accept finding as Accepted Risk (§10 entry).
Once accepted: no new proposal version required; no additional CLEAN round required.
Proceed to §7 after all LOW findings are dispositioned.

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
```

Note: Severity field uses HIGH or LOW (CRITICAL is subsumed into HIGH — same action applies).

---

### Changes 2–9 (unchanged from v3)

All other changes (§6 update, §8 diagram, §8 note, §15 DEFERRED, Appendix A, B-13, C, D)
are identical to v3. Only §14 section text is modified in this version.

---

Version-Tag: v4
Issued By: cc
Issued At: 2026-06-13T09:45:00Z
Status: UNDER_REVIEW

Open LOW findings from v3 cross-review (re-evaluated this lineage):
[CR-5] Vote rule redundancy: 2/3 clause subsumed by fail-safe HIGH (OPEN — v4 §14-5 challenge vote simplification addresses this)
[CR-6] §14-1 "other peers" vs MISSED_BY_ALL self-reference (OPEN — v4 §14-1 note addresses this)
[CR-7] CRITICAL vs HIGH distinction in §14-7 (OPEN — v4 §14-7 collapses to HIGH only, note added)
