# Amendment Debate: debate-protocol-amendment-crossreview
# Round 1

Date: 2026-06-13
Coordinator: cc
Trigger: T-2 (structural decision)
Risk Class: NORMAL
Active Peers: cc, gc, cx

---

[PROPOSAL: crossreview-amendment-20260613-v1]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5

### Change 1: Add §14 Exhaustive Cross-Review Phase

Insert as new §14, after current §13 Amendment Rule.

---

#### §14. Exhaustive Cross-Review Phase (끝장 교차검토)

**Trigger:** Immediately after CONSENSUS_OK (§6), before §7 documentation and implementation.

**Purpose:** Adversarially validate that no structural gaps, logical errors, or missing
considerations escaped the debate rounds. Each peer acts as an independent critic
of all other peers' reasoning — not just the final proposal text.

---

**14-1. Scope**

Each peer cross-reviews:

(a) All other peers' reasoning across ALL rounds
    — Were concerns missed? Were conclusions reached too easily? Were wrong positions adopted?

(b) The final §9 Canonical Proposal (full text)
    — Are there internal inconsistencies? Underspecified parts? Dangerous assumptions?

Each peer reviews independently (writes before seeing others' cross-reviews — same anchoring
prevention rule as §4-2).

---

**14-2. Cross-Review Response Format**

```
[PEER: {name}] [CROSS_REVIEW: round {n}]
MISSED_BY_{PEER_A}: (concerns peer_A should have raised — or NONE)
WRONG_BY_{PEER_A}: (peer_A concerns that were incorrect — or NONE)
PREMATURE_CONSENSUS_BY_{PEER_A}: (issues peer_A dropped too early — or NONE)
[repeat block per peer reviewed]
BOTH_MISSED: (gaps NO peer raised across all rounds — most critical)
VERDICT: CLEAN | GAPS_FOUND
```

CLEAN = no new concerns AND no open questions remain.
Silence is NOT CLEAN — explicit VERDICT: CLEAN declaration required.

---

**14-3. Termination Condition (끝장 조건)**

Cross-review terminates when ALL active peers declare VERDICT: CLEAN in the SAME round.

If any peer declares GAPS_FOUND in round N → all peers must re-run cross-review in round N+1
after findings are addressed (see 14-4).

---

**14-4. Finding Handling**

When GAPS_FOUND:

| Severity | Criteria | Action |
|:--------:|:---------|:-------|
| CRITICAL/HIGH | Structural flaw, logic error, invalidated assumption | Invalidate CONSENSUS_OK; re-enter §3 at affected nodes; new proposal version |
| LOW | Minor clarification, style, non-structural | Move to Accepted Risks (unanimous) or add to DEFERRED; proceed to §7 |

Coordinator classifies severity; any peer may challenge the classification
(challenge → treated as CRITICAL until resolved).

---

**14-5. Infinite Loop Prevention**

If cross-review round count exceeds (original debate round count × 3):
→ Escalate to H-2 (user mediation).
This prevents pathological loops while preserving thoroughness.

Example: 3-round debate → cross-review may run up to 9 rounds before H-2 trigger.

---

**14-6. Context Bounding**

Per round, each reviewer loads:
- §9 Canonical Proposal (full text)
- §10 Ledgers (current state)
- Coordinator-prepared compact summary of each peer's key positions per round
  (format: "Peer X: Round 1 position — ...; Round 2 change — ...; Final status — ...")

Full raw transcripts on disk for audit; NOT loaded into context.

---

### Change 2: Update §6 — add cross-review reference

After the Consensus Revocation / ABSENT peer rules, add:

> After all active peers have declared CONSENSUS_OK:{proposal-id}, proceed to
> §14 Exhaustive Cross-Review before §7 documentation and implementation.

---

### Change 3: Update §8 Feedback Loop diagram

Replace current diagram with:

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
                                   [§14 CROSS-REVIEW]
                                   all CLEAN? YES --> §7 document --> DO
                                              |
                                   NO --> re-enter §3 (CRITICAL)
                                       or Accepted Risks (LOW) --> retry §14
                                              ^
                                              |
                                   [CONSENSUS_OK §6]
                                              ^
                                              |
                                        [ROUNDS §4]
```

---

### Change 4: Update §8 SEE/VERIFY — clarify distinction

Add note to §8:

> Note: §14 Exhaustive Cross-Review (pre-implementation) and §8 SEE/VERIFY
> (post-implementation) are distinct phases:
> - §14: validates the DESIGN (proposal + peer reasoning) before anything is built
> - §8: validates the IMPLEMENTATION (diff, acceptance criteria) after it is built

---

### Change 5: Add Appendix B-13 example (Exhaustive Cross-Review)

Add to Appendix B:

**B-13: §14 Exhaustive Cross-Review Example**

Situation: 3-round debate on agentapi.bat persistence reached CONSENSUS_OK.
Coordinator prepares peer position summaries and sends cross-review queries simultaneously.

gc cross-reviews cx:
```
[PEER: gc] [CROSS_REVIEW: round 1]
MISSED_BY_CX: 
  1. cx did not raise that the template fix may be agy.exe version-specific
WRONG_BY_CX: NONE
PREMATURE_CONSENSUS_BY_CX: NONE
BOTH_MISSED:
  1. Neither peer asked whether agy.exe is invoked by other tools (cx calls it too)
VERDICT: GAPS_FOUND
```

cx cross-reviews gc:
```
[PEER: cx] [CROSS_REVIEW: round 1]
MISSED_BY_GC:
  1. gc did not verify whether templates/ folder is in .gitignore
WRONG_BY_GC: NONE
PREMATURE_CONSENSUS_BY_GC: NONE
BOTH_MISSED:
  1. Neither peer verified that agy.exe does not also write a checksum file alongside agentapi.bat
VERDICT: GAPS_FOUND
```

Coordinator: two GAPS_FOUND — classify severity:
- "agy.exe version-specific" → HIGH (could invalidate proposal) → re-enter §3
- "cx also invokes agy.exe" → HIGH → re-enter §3
- "templates/ in .gitignore" → LOW → Accepted Risk
- "checksum file" → HIGH → re-enter §3

→ CONSENSUS_OK invalidated. New §3 exploration. New proposal v2.

Round 2 cross-review (after new proposal):
```
[PEER: gc] [CROSS_REVIEW: round 2]
MISSED_BY_CX: NONE
WRONG_BY_CX: NONE
PREMATURE_CONSENSUS_BY_CX: NONE
BOTH_MISSED: NONE
VERDICT: CLEAN
```
```
[PEER: cx] [CROSS_REVIEW: round 2]
MISSED_BY_GC: NONE
WRONG_BY_GC: NONE
PREMATURE_CONSENSUS_BY_GC: NONE
BOTH_MISSED: NONE
VERDICT: CLEAN
```
Both CLEAN in same round → §14 complete → proceed to §7.

---

### Change 6: Update Appendix D template — add §14 section

Add to Appendix D after the "§6 Consensus" section:

```
## §14 Exhaustive Cross-Review

Peer position summaries (coordinator prepares before sending queries):
- cc: Round 1 — ... | Round N — ...
- gc: Round 1 — ... | Round N — ...
- cx: Round 1 — ... | Round N — ...

Cross-review query files:
[ ] gc ({filename})   [ ] cx ({filename})

Cross-review round {n}:
gc verdict: CLEAN | GAPS_FOUND
cx verdict: CLEAN | GAPS_FOUND
All CLEAN in same round: [ ]

If GAPS_FOUND:
Severity classification: CRITICAL/HIGH | LOW
Action taken: [re-enter §3 / Accepted Risk]
New proposal version: v{n+1}
```

---

Version-Tag: v1
Issued By: cc
Issued At: 2026-06-13T07:20:00Z
Status: UNDER_REVIEW
