# Amendment Debate: debate-protocol-amendment-crossreview
# Round 2

[PROPOSAL: crossreview-amendment-20260613-v2]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5 — v2

### Summary of changes from v1

| # | Change | Source |
|:-:|:-------|:-------|
| 1 | Renumber existing §14(DEFERRED) to §15 | cx |
| 2 | Peer self-summary (not coordinator-authored) | gc |
| 3 | Severity challenge: 3-peer vote, not auto-CRITICAL | gc+cx |
| 4 | CRITICAL: cross-review counter resets for new proposal segment | cx |
| 5 | LOW + Accepted Risk: no extra CLEAN round required | cx |
| 6 | CLEAN invalidated if any non-NONE field listed | cx |
| 7 | Coordinator must submit CROSS_REVIEW (unless ABSENT) | cx |
| 8 | §8 diagram: linear §6→§14→§7→DO→§8 | cx |
| 9 | Severity rubric: precise CRITICAL/HIGH vs LOW criteria | cx+gc |
| 10 | §14 ledger entry schema | cx |
| 11 | Appendix A updated (§14 step inserted) | cx |
| 12 | B-13 updated (cc CLEAN, ledger updates, new proposal id) | cx |
| 13 | Anti-patterns for §14 added (3 items) | cx |

---

### Change 1: Add §14 Exhaustive Cross-Review Phase

(Existing §14 DEFERRED renamed to §15.)

---

#### §14. Exhaustive Cross-Review Phase (끝장 교차검토)

**Trigger:** Immediately after CONSENSUS_OK (§6), before §7 documentation and implementation.

**Purpose:** Adversarially validate that no structural gaps, logical errors, or missing
considerations escaped the debate. Each peer acts as an independent critic of all other
peers' reasoning and the final proposal — not just a reviewer of the output.

---

**14-1. Scope**

Each active peer (including coordinator) cross-reviews:

(a) All other peers' reasoning across ALL rounds
    — Missed concerns? Conclusions reached too quickly? Wrong positions adopted?

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
Concerns I dropped: (and why)
Final position: (what I agreed to and why)
```

Coordinator collects all summaries and distributes them with the cross-review query.
Any peer may flag an inaccurate self-summary: `[SUMMARY_DISPUTE: peer_name | what is wrong]`
— coordinator must correct before cross-review proceeds.

---

**14-3. Cross-Review Response Format**

```
[PEER: {name}] [CROSS_REVIEW: round {n}]
MISSED_BY_{PEER_A}: (or NONE)
WRONG_BY_{PEER_A}: (or NONE)
PREMATURE_CONSENSUS_BY_{PEER_A}: (or NONE)
[repeat per peer reviewed]
BOTH_MISSED: (gaps NO peer raised — most critical)
VERDICT: CLEAN | GAPS_FOUND
```

CLEAN is ONLY valid when ALL of the following are true:
- All MISSED_BY, WRONG_BY, PREMATURE_CONSENSUS_BY fields = NONE
- BOTH_MISSED = NONE
- No open questions remain
If any field is non-NONE, VERDICT MUST be GAPS_FOUND (declaring CLEAN with listed gaps is an anti-pattern).

---

**14-4. Termination Condition**

Cross-review terminates when ALL active peers declare VERDICT: CLEAN in the SAME round.
Silence is NOT CLEAN — explicit declaration required.

---

**14-5. Finding Handling**

When GAPS_FOUND, coordinator classifies each finding:

**Severity CRITICAL/HIGH** (any of the following):
- Changes the proposal text, acceptance criteria, or affected artifacts
- Invalidates a confirmed assumption
- Introduces or removes a safety/security constraint
- Alters risk class (NORMAL ↔ HIGH_RISK)
- Affects portability, compatibility, or consensus validity

**Severity LOW** (ALL of the following must be true):
- Cannot change implementation behavior
- Cannot change user-facing risk
- Cannot alter consensus meaning
- Cannot affect acceptance criteria

**Severity Challenge:**
If any peer disagrees with a classification:
`[SEVERITY_CHALLENGE: finding_id | proposed: HIGH | reason: ...]`
Resolution: brief unanimous vote (all active peers respond HIGH or LOW within one round).
If 2/3 or more vote HIGH → CRITICAL/HIGH applies.
If vote is unanimous LOW → LOW applies.
Challenge does NOT automatically invalidate CONSENSUS_OK; it only triggers a vote.

**CRITICAL/HIGH action:**
1. CONSENSUS_OK invalidated: `[CONSENSUS_REVOKE: {proposal-id} | reason: §14 finding]`
2. Re-enter §3 at affected nodes; new proposal version issued
3. Cross-review round counter RESETS for the new proposal lineage (new debate segment begins)
4. Old cross-review rounds preserved in audit log but not counted in new limit

**LOW action:**
All active peers must unanimously accept finding as Accepted Risk (§10 entry).
Once accepted: no new proposal version required; no additional CLEAN round required.
Proceed to §7 after all LOW findings are dispositioned.

---

**14-6. Infinite Loop Prevention**

Cross-review round limit per proposal lineage: original debate rounds × 3.
If exceeded → H-2 escalation (user mediation, not automatic acceptance or abort).
H-2 may decide: continue, narrow scope to specific finding, split to SUB_ISSUE, or ABORT(A-2).

"Original debate rounds" = rounds from proposal creation to first CONSENSUS_OK for the current
proposal lineage. Resets when a new proposal version is created due to CRITICAL/HIGH finding.

---

**14-7. Ledger Entries**

Each finding goes into the Open Issues Ledger with this schema:
```
[CROSSREVIEW-{n}] Status: OPEN | RESOLVED_HIGH | RESOLVED_LOW | ARCHIVED
Found In: CROSS_REVIEW round {n}
Raised By: {peer}
Type: MISSED_BY | WRONG_BY | PREMATURE_CONSENSUS | BOTH_MISSED
Description:
Severity: CRITICAL | HIGH | LOW | CHALLENGED
Challenge: (if any, with resolution)
Disposition:
  HIGH: New proposal v{n}; affected §3 nodes: {list}
  LOW: Accepted Risk #{n}
Proposal After: {new-proposal-id or "unchanged"}
```

---

### Change 2: §6 update

Add after "ABSENT peer rules":
> After all active peers have declared CONSENSUS_OK:{proposal-id}, proceed to
> §14 Exhaustive Cross-Review Phase before §7 documentation and implementation.

---

### Change 3: §8 diagram (replace existing)

Replace diagram with:
```
[INPUT GATHER §0]
       |
       v
[TRIGGER §1] --> [GOAL FRAME §2] --> [MECE EXPLORE §3]
       ^                                      |
       |                          [§9 PROPOSAL when solution emerges]
       |                                      |
       |                                      v
  [NEXT CYCLE] <-- [SEE/VERIFY §8] <-- [DO/IMPLEMENT]
                                              ^
                                              |
                                    [§7 DOCUMENT + H-4]
                                              ^
                                              |
                                    [§14 CROSS-REVIEW]
                                    all CLEAN? YES --> §7
                                    CRITICAL/HIGH  --> §3 (new proposal)
                                    LOW + risk accepted --> §7
                                              ^
                                              |
                                    [CONSENSUS_OK §6]
                                              ^
                                              |
                                        [ROUNDS §4/§5]
```

---

### Change 4: §8 SEE/VERIFY note

Add:
> Note: §14 Exhaustive Cross-Review (pre-implementation) and §8 SEE/VERIFY
> (post-implementation) are distinct phases:
> §14 validates the DESIGN before implementation.
> §8 validates the IMPLEMENTATION after it is built.

---

### Change 5: §15 (renumbered from §14 DEFERRED)

Existing §14 DEFERRED content moved to §15, unchanged.

---

### Change 6: Appendix A update

Replace current "Step 6: Consensus" with:

**Step 6: Consensus (§6)**
All active peers declare CONSENSUS_OK:{proposal-id}.

**Step 6-B: Exhaustive Cross-Review (§14)**
Each peer writes their own PEER_SUMMARY first.
Coordinator distributes summaries with cross-review queries (ALL query files written before invoking any peer).
Peers respond with CROSS_REVIEW template.
If all CLEAN in same round → proceed.
If GAPS_FOUND → classify severity → CRITICAL/HIGH: re-enter Step 4; LOW: Accepted Risk → proceed.
Repeat until all CLEAN.

**Step 7: Document (§7)**
[unchanged]

---

### Change 7: Appendix B-13 update

Replace with:

**B-13: §14 Exhaustive Cross-Review Example**

After Round 3 CONSENSUS_OK on agentapi-bat-persistence-20260613-v2.

Coordinator asks each peer to write PEER_SUMMARY. Distributes summaries. Sends queries in parallel.

**Cross-Review Round 1:**

cc cross-reviews gc and cx:
```
[PEER: cc] [CROSS_REVIEW: round 1]
MISSED_BY_GC: NONE
WRONG_BY_GC: NONE
PREMATURE_CONSENSUS_BY_GC: NONE
MISSED_BY_CX: NONE
WRONG_BY_CX: NONE
PREMATURE_CONSENSUS_BY_CX: NONE
BOTH_MISSED:
  1. Neither peer verified whether agy.exe writes a checksum file alongside agentapi.bat
     that might detect the template modification and regenerate the original
VERDICT: GAPS_FOUND
```

gc cross-reviews cc and cx:
```
[PEER: gc] [CROSS_REVIEW: round 1]
MISSED_BY_CC: NONE
WRONG_BY_CC: NONE
PREMATURE_CONSENSUS_BY_CC: NONE
MISSED_BY_CX:
  1. cx did not verify whether the fix is agy.exe version-specific (2.0 vs 2.1 path syntax)
WRONG_BY_CX: NONE
PREMATURE_CONSENSUS_BY_CX: NONE
BOTH_MISSED: NONE
VERDICT: GAPS_FOUND
```

cx cross-reviews cc and gc:
```
[PEER: cx] [CROSS_REVIEW: round 1]
MISSED_BY_CC: NONE
WRONG_BY_CC: NONE
PREMATURE_CONSENSUS_BY_CC: NONE
MISSED_BY_GC:
  1. gc did not verify that templates/ folder is not in .gitignore
WRONG_BY_GC: NONE
PREMATURE_CONSENSUS_BY_GC: NONE
BOTH_MISSED: NONE
VERDICT: GAPS_FOUND
```

Coordinator severity classification:
```
[CROSSREVIEW-1] BOTH_MISSED: checksum file → severity: HIGH (could invalidate solution)
  Challenge? No unanimous agreement → HIGH confirmed
[CROSSREVIEW-2] MISSED_BY_CX: version-specific → severity: HIGH (affects implementation)
[CROSSREVIEW-3] MISSED_BY_GC: .gitignore → severity: LOW (does not change implementation behavior)
```

Action:
- CROSSREVIEW-1, -2: CRITICAL/HIGH → CONSENSUS_OK invalidated
  `[CONSENSUS_REVOKE: agentapi-bat-persistence-20260613-v2 | reason: §14 CROSSREVIEW-1,-2]`
  Re-enter §3 nodes (4-4 external dependencies, 3-5 compatibility). New proposal v3 to be drafted.
  Cross-review counter RESET for v3 lineage.
- CROSSREVIEW-3: LOW → Accepted Risk
  `[RISK-2]: templates/ in .gitignore confirmed as not applicable; accepted by: cc, gc, cx`

After new §3 exploration and new CONSENSUS_OK on v3:

**Cross-Review Round 1 (v3 lineage):**
```
[PEER: cc] [CROSS_REVIEW: round 1] — MISSED_BY_GC: NONE / MISSED_BY_CX: NONE / BOTH_MISSED: NONE
VERDICT: CLEAN

[PEER: gc] [CROSS_REVIEW: round 1] — all NONE
VERDICT: CLEAN

[PEER: cx] [CROSS_REVIEW: round 1] — all NONE
VERDICT: CLEAN
```

All active peers (cc, gc, cx) CLEAN in same round → §14 complete.
Ledger CROSSREVIEW-1,-2 → Status: RESOLVED_HIGH (proposal v3 created).
Ledger CROSSREVIEW-3 → Status: RESOLVED_LOW (Accepted Risk).
Proceed to §7.

---

### Change 8: Appendix C anti-patterns (add 3)

| # | Anti-Pattern | Why Wrong | Correct |
|:-:|:-------------|:----------|:--------|
| 17 | VERDICT: CLEAN while listing non-NONE fields | CLEAN is invalid if any field non-NONE | Declare GAPS_FOUND; address findings |
| 18 | Using LOW severity to bypass an unresolved design issue | LOW requires: cannot affect implementation behavior/risk | Challenge severity; if design issue, it's HIGH |
| 19 | Coordinator writes peer position summaries | Introduces coordinator bias; can hide prior concerns | Each peer writes their own PEER_SUMMARY |

---

### Change 9: Appendix D template — §14 section added

Add after "§6 Consensus" section:

```
## §14 Exhaustive Cross-Review

Peer Self-Summaries (each peer writes their own):
[ ] cc summary: P:\.ai\debate\{topic}-round-summaries.md (cc section)
[ ] gc summary: (gc section)
[ ] cx summary: (cx section)
Summary disputes: (none | list)

Cross-review query files:
[ ] cc → reviews gc, cx: {filename}
[ ] gc → reviews cc, cx: {filename}
[ ] cx → reviews cc, gc: {filename}

Cross-review round {n}:
cc verdict: CLEAN | GAPS_FOUND
gc verdict: CLEAN | GAPS_FOUND
cx verdict: CLEAN | GAPS_FOUND
All CLEAN in same round: [ ]

If GAPS_FOUND:
[CROSSREVIEW-{n}] Severity: CRITICAL/HIGH | LOW | CHALLENGED
Challenge vote result: (if any)
Disposition: [new proposal v{n+1}] | [Accepted Risk #{n}]
Cross-review counter (this lineage): {current}/{limit}
```

---

Version-Tag: v2
Issued By: cc
Issued At: 2026-06-13T07:30:00Z
Status: UNDER_REVIEW
