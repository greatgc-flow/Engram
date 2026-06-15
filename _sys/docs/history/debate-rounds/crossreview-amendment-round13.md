# Amendment Debate: debate-protocol-amendment-crossreview
# Round 13

[PROPOSAL: crossreview-amendment-20260613-v13]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5 — v13

### Summary of changes from v12

| # | Change | Source |
|:-:|:-------|:-------|
| 1–39 | All v11 changes retained | (see round11) |
| 40 (revised) | §14-5: path (a) — empty vote pool: revise H-2 options to include "classify as LOW (narrowing scope if needed)" path | CRv11-A + gc Round 12 |
| 41 (revised) | §14-5: path (a) — non-exhaustive outcome: add "(including ABSTAIN)" to non-standard definition | CRv11-B + cx Round 12 |

---

### §14-5 path (a) — v13 full text (diff vs v12)

**v12 path (a) (H-2 options at end):**
```
...H-2 may: (i) classify the finding as HIGH, triggering the standard HIGH action;
(ii) narrow the finding scope so it clearly meets LOW criteria and require
re-acceptance; (iii) split to SUB_ISSUE; or (iv) ABORT(A-2).
```

**v13 path (a) (H-2 options revised):**
```
...H-2 may: (i) classify the finding as HIGH, triggering the standard HIGH action;
(ii) classify the finding as LOW (narrowing scope if needed), requiring the
challenger to then accept as Accepted Risk or proceed to path (b);
(iii) split to SUB_ISSUE; or (iv) ABORT(A-2).
```

**v12 change 41 (non-standard definition):**
```
...a non-standard response is treated as voting HIGH (fail-safe).
```

**v13 change 41 (non-standard, revised):**
```
...a non-standard response (including ABSTAIN) is treated as voting HIGH (fail-safe).
```

All other §14 text is identical to v12.

---

### Complete v13 §14-5 path (a) text

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
(narrowing scope if needed), requiring the challenger to then accept as Accepted Risk
or proceed to path (b); (iii) split to SUB_ISSUE; or (iv) ABORT(A-2).
```

---

Version-Tag: v13
Issued By: cc
Issued At: 2026-06-13T19:30:00Z
Status: PROPOSED

---

## Round 13 — Peer Responses

[PEER: gc] [ROUND: 13]
POSITION: AGREE
REASONING: Option (ii) resolves "LOW as-is" — H-2 can classify as LOW with optional narrowing.
"False positive" treatment as LOW preserves audit trail while functionally dismissing HIGH challenge.
ABSTAIN explicit as non-standard = fail-safe, prevents ambiguous consensus.
CONCERNS: NONE
OPEN_QUESTIONS: Option (ii) says "proceed to path (b)" — slightly unclear cross-reference, but
non-blocking since path (b) is defined in the same §14-5 section.
STATUS: AGREE
CRv10-B~H: YES / CRv9-D, CRv9-E, CR-10, CR-21~28: YES

[PEER: cx] [ROUND: 13]
POSITION: AGREE
REASONING: Revised H-2 option (ii) now covers "LOW as-is" — H-2 can classify LOW with narrowing
only if needed; challenger still has path (b) option preserving unanimity requirement.
ABSTAIN inclusion closes my Round 12 wording concern without changing fail-safe behavior.
CONCERNS: NONE / STATUS: AGREE
CRv10-B~H: YES / CRv9-D, CRv9-E, CR-10, CR-21~28: YES

---

[CONSENSUS_OK: crossreview-amendment-20260613-v13]
Consensus by: cc, gc, cx
Round: 13
Date: 2026-06-13T19:40:00Z

---

## §14 Cross-Review Phase — v13 Lineage

**Trigger:** CONSENSUS_OK on crossreview-amendment-20260613-v13
**Cross-review round counter:** RESET (v13 lineage)
**Original debate rounds in this lineage:** 1 (Round 13)
**Cross-review round limit:** 1 × 3 = 3

### Accepted Risks (v13 lineage):
[CRv10-B~H] All re-accepted (unchanged by v13)
[CRv9-D, CRv9-E, CR-10, CR-21~28] All re-accepted (unchanged by v13)

### Step 1: PEER_SUMMARY Collection

[PEER_SUMMARY: cc]
Round 1 position: Proposed §14 dual scope, binary verdict, parallel queries, loop prevention.
Key concerns raised: coordinator exemption; loop prevention; ledger schema; MISSED_BY_ALL; mixed
finding; context bounding. v7 CR: CR-16~20 HIGH; v9 CR: CRv9-A/B/C HIGH; v10 CR: CRv10-A HIGH;
v11 CR: CRv11-A/B HIGH.
Concerns I dropped: coordinator PEER_SUMMARY exemption (resolved CR-11).
Final position: AGREE v13 — 41 changes. Empty vote pool → H-2; ABSTAIN explicit; path (a) exhaustive.

[PEER_SUMMARY: gc]
Round 1 position: Rigorous structured debate with tie-breaking, deadlock resolution, termination conditions.
Key concerns raised: Coordinator bias, severity fail-safes; CR-16~20 HIGH; CR-21~28 LOW; CRv9-A/B/D;
CRv10-A/B/C/D; CRv11-A/B; Round 12: H-2 missing "LOW as-is" and "false positive" paths.
Concerns I dropped: NONE.
Final position: AGREE v13; re-accepted all LOW findings.

[PEER_SUMMARY: cx]
Round 1 position: Structural enforceability — coordinator included, no silent consensus, quorum/ABSENT
explicit, no extra CLEAN round after unanimous LOW Accepted Risk.
Key concerns raised: §14 structure Rounds 1-3; CR-16~20 HIGH; CR-21~28 LOW; CRv9-A~E; CRv10-A~H;
CRv11-A/B; Round 12: ABSTAIN non-standard clarity (non-blocking, incorporated in v13).
Concerns I dropped: NONE.
Final position: AGREE v13; all LOW findings acceptable as Accepted Risk.

---

### Step 2: §14 Cross-Review Round 1 (v13 lineage)

[PEER: cc] [CROSS_REVIEW: round 1]

MISSED_BY_gc: NONE — gc's Round 12 concerns (H-2 missing "LOW as-is") were valid and addressed.
gc's open question about "path (b)" cross-reference is a documentation clarity note, not a
structural miss.
WRONG_BY_gc: NONE
PREMATURE_CONSENSUS_BY_gc: NONE

MISSED_BY_cx: NONE — cx's Round 12 ABSTAIN concern was valid and incorporated. cx's analysis
of the full v13 path (a) text was thorough.
WRONG_BY_cx: NONE
PREMATURE_CONSENSUS_BY_cx: NONE

MISSED_BY_ALL: NONE — v13 changes are narrow clarifications to existing text. The H-2 options
for the empty pool case are complete: HIGH (→ CONSENSUS_REVOKE), LOW with/without narrowing
(→ Accepted Risk or path (b)), SUB_ISSUE, or ABORT. The fail-safe rules are now exhaustive
for other non-ABSENT active peers in path (a) challenges. gc's "path (b)" cross-reference
question is correctly answered by reading the full §14-5 section; no structural gap.

VERDICT: CLEAN

---

[PEER: gc] [CROSS_REVIEW: round 1]
MISSED_BY_cc: H-2 option(ii) → path(b) → H-2 recursive loop; non-MECE H-2 options.
WRONG_BY_cc: "path (a) exhaustive" too strong given H-2 state gaps.
PREMATURE_CONSENSUS_BY_cc: YES
MISSED_BY_gc: Same H-2 recursive loop; non-MECE options.
PREMATURE_CONSENSUS_BY_gc: YES
MISSED_BY_cx: Same H-2/P-1 recursive loop; non-MECE options.
PREMATURE_CONSENSUS_BY_cx: YES
MISSED_BY_ALL:
1. Recursive escalation loop: empty pool → H-2 option(ii) → path(b) → H-2 again; peer rejects H-2 ruling by re-escalating to H-2/H-1.
2. Non-MECE: H-2 missing "agree LOW, fix it anyway" and "dismiss as invalid" paths.
VERDICT: GAPS_FOUND

---

[PEER: cx] [CROSS_REVIEW: round 1]
MISSED_BY_cc: H-2 option(ii) does not state whether ABSENT/returning peers must accept LOW Accepted Risk. "Narrowing scope if needed" may require fresh assent if scope changed.
WRONG_BY_cc: "path (a) exhaustive" too strong.
PREMATURE_CONSENSUS_BY_cc: YES (change 40)
MISSED_BY_gc: Same ABSENT/returning peer acceptance + scope-narrowing disposition gap.
PREMATURE_CONSENSUS_BY_gc: YES (change 40)
MISSED_BY_cx: Accepted ABSTAIN + H-2 options without checking ABSENT-peer acceptance and scope-narrowing assent.
PREMATURE_CONSENSUS_BY_cx: YES (change 40)
MISSED_BY_ALL: Change 40 option(ii) omits: (1) whether ABSENT/returning peers must accept the LOW Accepted Risk after empty-pool H-2 resolution; (2) whether scope narrowing creates a revised finding requiring fresh Accepted Risk assent from all non-ABSENT active peers.
VERDICT: GAPS_FOUND

---

## §14 Cross-Review Round 1 — Finding Classification (Coordinator)

**CRv13-A** — H-2 option(ii) Accepted Risk incompleteness after empty pool
Raised By: cx (MISSED_BY_ALL)
Description: §14-5 change 40 H-2 option(ii): "classify the finding as LOW (narrowing scope if
needed), requiring the challenger to then accept as Accepted Risk or proceed to path (b)."
Two gaps: (1) Only the challenger's acceptance is mentioned — when previously ABSENT peers
return to active status after this resolution, it is unspecified whether they must also accept
the LOW finding. (2) If H-2 narrows scope, prior acceptance of the un-narrowed description
may not transfer; fresh assent requirement is unspecified.
Severity: HIGH — affects acceptance criteria for LOW Accepted Risk in empty pool case; could
allow §7 to proceed without full unanimous acceptance when ABSENT peers return; alters risk
class if scope-narrowed finding is accepted by the challenger alone.

**CRv13-B** — H-2 "recursive loop" concern (gc)
Raised By: gc (MISSED_BY_ALL)
Description: gc claims H-2 option(ii) → path(b) → H-2 creates a loop where peer rejects an
H-2 ruling by re-escalating to H-2/P-1. Analysis: path(b) escalates to H-2 (NOT H-1/P-1) for
a DIFFERENT question (acceptance, not classification). After path(b) H-2 directs acceptance, the
peer "may not restart the SEVERITY_CHALLENGE cycle; the debate ends via SUB_ISSUE or ABORT." This
terminates definitively. The concern appears to conflate H-2 (mediation) with H-1 (goal setting).
Severity: LOW — path(b) terminates definitively; the two H-2 invocations address distinct questions.

**CRv13-C** — Non-MECE H-2 options (gc)
Raised By: gc (MISSED_BY_ALL)
Description: gc says H-2 missing "fix it anyway" and "dismiss as invalid" options.
Analysis: "fix it anyway" = classify as HIGH (triggering CONSENSUS_REVOKE + fix); "dismiss as
invalid" = classify as LOW (challenge unfounded, original LOW stands). Both covered by options (i)
and (ii). Non-MECE concern is addressed by correct interpretation of existing options.
Severity: LOW

---

## Mixed-Finding Handling (§14-5)

HIGH finding CRv13-A present → CONSENSUS_OK invalidated.

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v13 | reason: §14 cross-review CRv13-A]
Cross-review counter RESET — v14 proposal lineage begins.

LOW findings CRv13-B, CRv13-C → Status: OPEN, re-evaluated in v14 lineage.
Previously Accepted Risks (CRv10-B~H, CRv9-D/E, CR-10, CR-21~28) → Status: OPEN,
re-evaluated in first cross-review round of v14 lineage.

