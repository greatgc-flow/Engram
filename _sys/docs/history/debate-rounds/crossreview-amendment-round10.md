# Amendment Debate: debate-protocol-amendment-crossreview
# Round 10

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v9 | reason: §14 cross-review CRv9-A, CRv9-B, CRv9-C]
Cross-review counter RESET — v10 proposal lineage begins.

---

[PROPOSAL: crossreview-amendment-20260613-v10]
Content:

## Proposed Amendment to DEBATE_PROTOCOL v0.5 — v10

### Summary of changes from v9

| # | Change | Source |
|:-:|:-------|:-------|
| 1–35 | All v9 changes retained | (see round9) |
| 36 | §14-5: Duplicate Findings — remove SEVERITY_CHALLENGE from dispute path; peer reports separate finding via own CROSS_REVIEW | CRv9-A (cx+gc) |
| 37 | §14-5: LOW acceptance refusal — separate "classification dispute" (SEVERITY_CHALLENGE optional) from "acceptance refusal" (H-2 direct); removes forced HIGH-vote exploit | CRv9-B (gc) |
| 38 | §14-5: Historical LOW re-accept refusal — explicit link to LOW acceptance refusal rules | CRv9-C (cx) |

---

### §14 Exhaustive Cross-Review Phase (끝장 교차검토) — v10 full text

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
If any peer disagrees with the coordinator's severity classification:
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
acceptance. The LOW acceptance refusal rules apply (see below), defaulting to H-2
escalation if no basis for refusal is stated.

LOW acceptance non-standard response: Any response to a LOW finding Accepted Risk
acceptance request that is neither an explicit acceptance nor an explicit refusal is
treated as refusal. The LOW acceptance refusal rules apply (see below), defaulting to H-2
escalation if no basis for refusal is stated.

LOW acceptance refusal: If a peer refuses to accept a LOW finding as Accepted Risk (via
explicit refusal, silence, or non-standard response), the basis for refusal determines
the escalation path:

(a) Classification dispute — the refusing peer believes the finding is actually HIGH
(not LOW): the peer MAY challenge via SEVERITY_CHALLENGE. If the challenge confirms
LOW (all non-ABSENT active peers vote LOW), the peer must either accept as Accepted
Risk or proceed via path (b).

(b) Acceptance refusal — the refusing peer accepts the LOW classification but believes
the risk is unacceptable: escalate directly to H-2 (no SEVERITY_CHALLENGE required).
H-2 may: (i) direct the refusing peer to accept or reconsider, (ii) narrow the finding
scope, (iii) split to SUB_ISSUE, or (iv) ABORT(A-2). H-2 mediation does not substitute
for unanimous acceptance — if the peer ultimately accepts after H-2 direction, normal
Accepted Risk (§10) applies; if not, the debate ends via SUB_ISSUE or ABORT.

If the refusing peer does not state a basis for refusal within one round, the coordinator
defaults to path (b) — H-2 escalation.

H-2 has final mediation authority for acceptance refusals. A peer who refuses acceptance
after H-2 direction may not restart the SEVERITY_CHALLENGE cycle for the same finding;
the debate ends via SUB_ISSUE or ABORT.

**Duplicate Findings:**
When multiple peers raise identical or substantially overlapping findings in the same
cross-review round, the coordinator assigns a single ledger entry with all raising peers
listed in the Raised By field. No duplicate entries are created for the same finding.
If a peer believes two findings assigned to a single entry are actually distinct and not
covered by the merged description, the peer may request the coordinator to create
separate entries, stating the reason. The coordinator makes the final determination on
the merge. If a peer still believes a distinct finding is not captured in the merged
entry, they may report the allegedly separate finding as an additional finding in their
own CROSS_REVIEW response in the same round or the next round.

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
area, full re-evaluation is required. If a peer refuses to re-accept, the LOW acceptance
refusal rules apply.

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

### Changes 2–9 (unchanged from v10/v9/v8/v7)

All other changes (§6 update, §8 diagram, §8 note, §15 DEFERRED, Appendix A, B-13, C, D)
are identical to v9. Only §14 section text is modified in this version.

---

Version-Tag: v10
Issued By: cc
Issued At: 2026-06-13T18:45:00Z
Status: CONSENSUS_OK

---

## Round 10 — Peer Responses

[PEER: gc] [ROUND: 10]
POSITION: AGREE
REASONING: v10 correctly implements CRv9-A (no SEVERITY_CHALLENGE for MERGE/SPLIT), CRv9-B (LOW refusal separated into classification dispute vs acceptance refusal; H-2 direct path; exploit closed), CRv9-C (re-accept refusal linked to refusal rules).
CONCERNS: NONE / STATUS: AGREE
CRv9-D, CRv9-E, CR-10, CR-21~26, CR-28: Accepted Risk YES

[PEER: cx] [ROUND: 10]
POSITION: AGREE
REASONING: CRv9-A: duplicate MERGE/SPLIT no longer forced through SEVERITY_CHALLENGE. CRv9-B: exploit closed — LOW classification accepted + risk rejected → H-2 direct, no forced HIGH-vote path. CRv9-C: re-accept refusal linked. CRv9-E correctly treated as documentation error.
CONCERNS: NONE / STATUS: AGREE
CRv9-D, CRv9-E, CR-10, CR-21~26, CR-28: Accepted Risk YES

---

[CONSENSUS_OK: crossreview-amendment-20260613-v10]
Consensus by: cc, gc, cx
Round: 10
Date: 2026-06-13T18:50:00Z

---

## §14 Cross-Review Phase — v10 Lineage

**Trigger:** CONSENSUS_OK on crossreview-amendment-20260613-v10
**Cross-review round counter:** RESET (v10 lineage, started after v9 CONSENSUS_REVOKE)
**Original debate rounds in this lineage:** 1 (Round 10 only)
**Cross-review round limit:** 1 × 3 = 3

### Accepted Risks (v10 lineage):
[CRv9-D] Accepted Risk: vote/acceptance roster snapshot governed by §4-4
[CRv9-E] Accepted Risk: round9.md artifact status inconsistency — documentation fix only
[CR-10] Accepted Risk: coordinator judgment + challenge mechanism sufficient (re-accepted)
[CR-21~26, CR-28] Accepted Risk: re-accepted (v10 changes do not affect these areas)

### Step 1: PEER_SUMMARY Collection

[PEER_SUMMARY: cc]
Round 1 position: §14 dual scope, binary verdict, parallel queries, loop prevention 제안.
Key concerns raised: 코디네이터 면제; 루프방지(§14-6); ledger schema(§14-7); MISSED_BY_ALL; mixed finding; context bounding. v7 cross-review: CR-16~20 HIGH 분류, CR-21~28 LOW 분류. v9 cross-review: CRv9-A/B/C HIGH, CRv9-D/E LOW 분류.
Concerns I dropped: 코디네이터 PEER_SUMMARY 작성 (CR-11에서 HIGH 분류 후 드롭).
Final position: AGREE v10 — 38개 변경사항 전부. LOW refusal exploit 제거, duplicate dispute 분리, re-accept 연결 완성.

[PEER_SUMMARY: gc]
Round 1 position: Advocated for rigorous structured debate protocol with explicit tie-breaking, deadlock resolution, and formal termination conditions.
Key concerns raised: Coordinator bias and severity voting fail-safes (Rounds 1-3); CR-16~20 HIGH findings; CR-21~28 LOW; Round 8 blockers. v9 cross-review: CRv9-A (duplicate dispute type mismatch), CRv9-B (LOW refusal exploit), CRv9-D (roster snapshot).
Concerns I dropped: NONE.
Final position: AGREE on v10; re-accepted all LOW findings. Protocol correctly implements all safeguards.

[PEER_SUMMARY: cx]
Round 1 position: Supported §14 but required structural enforceability — coordinator included, no silent consensus, quorum/ABSENT explicit, no extra CLEAN round after unanimous LOW Accepted Risk.
Key concerns raised: §14 structure issues Rounds 1-3; CR-1/2/4/8/9/13/14/15/16; CR-21~28 LOW; Round 8 concerns (CR-20 non-standard, SEVERITY_CHALLENGE bidirectional, CR-27 duplicate); v9 cross-review: CRv9-A~E including duplicate MERGE/SPLIT mechanism, LOW refusal exploit, re-accept link, roster snapshot, artifact inconsistency.
Concerns I dropped: NONE.
Final position: AGREE on v10 — all three v9 blockers resolved; re-accepted all LOW findings.

---

### Step 2: §14 Cross-Review Round 1 (v10 lineage)

Open LOW findings re-evaluated this lineage (v10):
[CRv9-D] Vote/acceptance roster snapshot — OPEN
[CRv9-E] CR-10/CR-21~28 ledger status inconsistency — NOTE: artifact error in round9.md; finding itself is LOW
Previously Accepted Risks (reset per CR-18; simple re-accept vote available):
[CR-10] OPEN (re-eval)
[CR-21] OPEN (re-eval)
[CR-22] OPEN (re-eval)
[CR-23] OPEN (re-eval)
[CR-24] OPEN (re-eval)
[CR-25] OPEN (re-eval)
[CR-26] OPEN (re-eval)
[CR-28] OPEN (re-eval)

---

[PEER: cc] [CROSS_REVIEW: round 1]

MISSED_BY_gc:
§14-5 path (a) non-challenge stall: gc focused on closing the CRv9-B exploit (forced HIGH-vote
path) and correctly agreed the path (a)→(b) separation resolves it. However, gc did not flag
that path (a) contains an unstated assumption: if a peer claims "classification dispute" as
their basis but then declines to file SEVERITY_CHALLENGE, the text specifies no coordinator
action for that sub-case. The existing default-to-(b) rule applies only when "the refusing peer
does not state a basis for refusal within one round" — not when a basis is stated but no
SEVERITY_CHALLENGE follows. A bad-faith peer could claim path (a) indefinitely without the
coordinator having an explicit mandate to move to path (b).

WRONG_BY_gc: NONE

PREMATURE_CONSENSUS_BY_gc: NONE

MISSED_BY_cx:
Same gap as MISSED_BY_gc. cx reviewed CRv9-B extensively and confirmed path (a)→(b) separation,
but did not flag the non-challenge stall within path (a). cx's PEER_SUMMARY lists "LOW refusal
exploit" as a concern raised and resolved — the stall variant was not identified.

WRONG_BY_cx: NONE

PREMATURE_CONSENSUS_BY_cx: NONE

MISSED_BY_ALL:
§14-5 path (a) non-challenge stall: No peer raised the scenario where a refusing peer claims
"classification dispute" basis (path (a)) but fails to file SEVERITY_CHALLENGE within the round.
The "MAY challenge" language permits non-challenge, but there is no coordinator default action
for "basis stated, action not taken." Coordinator cannot invoke the existing default-to-(b) rule
because that rule explicitly requires "does not state a basis." A one-sentence clarification
resolves this: "If a peer who claims path (a) does not file SEVERITY_CHALLENGE within one round,
the coordinator defaults to path (b) escalation."
Severity assessment: LOW — does not change consensus meaning or acceptance criteria; H-2 and the
preserved-LOW loop guard provide eventual resolution under good-faith operation; affects only
bad-faith edge case behavior in the acceptance refusal sub-path.

VERDICT: GAPS_FOUND

---

[PEER: gc] [CROSS_REVIEW: round 1]
MISSED_BY_cc:
Infinite loop vulnerability in the new duplicate finding process — coordinator merges, peer
re-reports next round, coordinator re-merges, cycle continues. Ambiguity of severity when
merging findings of different severities. Missing explicit authority for who chooses between
SUB_ISSUE and ABORT after H-2 mediation fails.
WRONG_BY_cc: NONE
PREMATURE_CONSENSUS_BY_cc: Prematurely agreed to v10, believing duplicate dispute path and
LOW refusal exploit were fully resolved without checking loop vulnerabilities or terminal
state authority gaps.
MISSED_BY_gc: Same — infinite loop vulnerability in duplicate finding process; missing
severity inheritance rule for merged findings; SUB_ISSUE vs ABORT authority gap.
WRONG_BY_gc: NONE
PREMATURE_CONSENSUS_BY_gc: Prematurely agreed, incorrectly assuming all safeguards implemented
when critical loop breakers and terminal state deciders were missing.
MISSED_BY_cx: Structural unenforceability of duplicate finding merge/split process (infinite
loop risk). Lack of severity inheritance for merged findings. Lack of explicit authority for
choosing SUB_ISSUE vs ABORT in terminal state.
WRONG_BY_cx: NONE
PREMATURE_CONSENSUS_BY_cx: Declared all v9 blockers resolved and agreed to v10 despite
structural enforceability gaps in new paths.
MISSED_BY_ALL:
1. Merge/Split Infinite Loop: §14-5 allows the coordinator to merge and the peer to re-report
   the separate finding in the "next round," enabling an endless cycle of merging and re-reporting.
2. Merged Finding Severity: Text does not specify that a merged finding must adopt the highest
   severity of its constituent parts, risking severity dilution.
3. Terminal State Authority: §14-5 LOW acceptance refusal states "the debate ends via SUB_ISSUE
   or ABORT" but fails to specify WHO (coordinator, H-2, or consensus) chooses between the two.
VERDICT: GAPS_FOUND

---

[PEER: cx] [CROSS_REVIEW: round 1]
MISSED_BY_cc:
§14-5 voting-state ambiguity in LOW classification disputes: "all non-ABSENT active peers vote LOW"
does not say whether the refusing/challenging peer is included — if they are, the refusing peer
who believes the finding is HIGH will vote HIGH, making "confirms LOW" structurally unreachable.
Also: duplicate-dispute timing gap when coordinator merge decision occurs after peers have
submitted same-round responses.
WRONG_BY_cc: NONE
PREMATURE_CONSENSUS_BY_cc: AGREE on v10 appears premature — §14-5 still has unresolved
vote-population and timing-state ambiguity.
MISSED_BY_gc:
H-2 escalation for LOW acceptance refusal does not define ledger outcome when H-2 directs
acceptance but unanimous acceptance is still absent or later withdrawn.
"One round" ambiguity for unstated refusal basis — debate round or cross-review round not
specified.
WRONG_BY_gc: "Protocol implements all safeguards" is too strong; v10 improves the refusal
exploit but does not fully specify voting state, timing, or terminal ledger state for all paths.
PREMATURE_CONSENSUS_BY_gc: AGREE appears premature — safeguards are not fully enforceable
without clarifying §14-5 state transitions.
MISSED_BY_cx:
Duplicate finding separation may fail at cross-review limit boundary: if the merge dispute is
recognized in the last allowed cross-review round, "same round or next round" may provide no
available procedural slot for the allegedly distinct finding.
WRONG_BY_cx: NONE
PREMATURE_CONSENSUS_BY_cx: AGREE was premature — accepted duplicate and LOW-refusal fixes
without checking exact voting population, round-boundary, and terminal-state mechanics.
MISSED_BY_ALL:
§14-5 needs explicit state-machine rules: whether the challenging/refusing peer is excluded from
"all non-ABSENT active peers vote LOW" in SEVERITY_CHALLENGE; what happens on mixed LOW/HIGH votes
when challenger is included (→ always HIGH because challenger votes HIGH); "within one round" timer
definition; "one round" = debate round or cross-review round; how non-standard response is
distinguished from classification dispute vs acceptance refusal; how duplicate split requests work
after same-round submissions are closed; how a distinct finding is preserved when next round would
exceed cross-review limit. Terminal-state gap: H-2 "direct acceptance" is not itself unanimous
acceptance — protocol must confirm ledger remains open until explicit acceptance, or becomes
SUB_ISSUE/ABORT on continued refusal.
VERDICT: GAPS_FOUND

---

## §14 Cross-Review Round 1 — Finding Classification (Coordinator)

**CRv10-A** — SEVERITY_CHALLENGE vote population in path (a)
Raised By: cx (MISSED_BY_cc, MISSED_BY_ALL), gc (implicitly, terminal state authority gap intersects)
Description: §14-5 path (a) SEVERITY_CHALLENGE: "all non-ABSENT active peers respond HIGH or LOW."
If the challenging/refusing peer is included in this vote, they will always vote HIGH (by
definition — they claim classification dispute), making the "confirms LOW" branch of path (a)
structurally unreachable. Any peer filing a path (a) challenge can guarantee HIGH outcome by
voting. This re-opens the CRv9-B exploit vector: a refusing peer claims classification dispute,
files SEVERITY_CHALLENGE, votes HIGH → CONSENSUS_REVOKE — bypassing H-2.
Severity: HIGH
Rationale: (1) Invalidates the "confirms LOW" branch of path (a), making it dead code.
(2) Partially re-opens the CRv9-B exploit (LOW refusal exploit) that v10 was specifically
designed to close. (3) Changes acceptance criteria for path (a). The fix requires only one
clarifying sentence: exclude the challenging peer from their own challenge vote.

**CRv10-B** — Merge/Split re-report loop
Raised By: gc (MISSED_BY_ALL), cx (duplicate split at limit)
Description: §14-5 Duplicate Findings allows a peer to re-report allegedly distinct finding
"in the same round or the next round." A bad-faith peer could re-report each round; coordinator
re-merges each time. Loop is bounded by cross-review round limit → H-2.
Severity: LOW
Rationale: Cannot change consensus meaning; bounded by existing cross-review limit + H-2;
does not introduce unbounded behavior.

**CRv10-C** — Merged finding severity inheritance
Raised By: gc (MISSED_BY_ALL)
Description: When two findings of different severity are merged, the text does not specify
which severity applies. After CRv10-A is fixed (SEVERITY_CHALLENGE vote population correct),
the peer who raised the higher-severity concern can challenge any downward classification via
the standard SEVERITY_CHALLENGE mechanism.
Severity: LOW
Rationale: Standard coordinator classification + SEVERITY_CHALLENGE covers it; no implementation
behavior change that isn't already addressable.

**CRv10-D** — Terminal state authority (SUB_ISSUE vs ABORT)
Raised By: gc (MISSED_BY_ALL)
Description: "The debate ends via SUB_ISSUE or ABORT" does not name the decision-maker.
H-2 authority is already established earlier in path (b): "H-2 may: ... (iii) split to
SUB_ISSUE, or (iv) ABORT(A-2)." The final sentence refers back to H-2's established authority.
Severity: LOW
Rationale: H-2 authority already stated in path (b); the final sentence is a summary of
outcomes, not a new decision point.

**CRv10-E** — Path (a) non-challenge stall
Raised By: cc (MISSED_BY_ALL)
Description: Peer claims classification dispute (path (a)) but declines to file
SEVERITY_CHALLENGE. Default-to-(b) rule only applies when no basis stated; does not cover
"basis stated, action not taken."
Severity: LOW
Rationale: Preserved-LOW loop guard + H-2 provide eventual resolution; does not change normal
operation behavior.

**CRv10-F** — "One round" ambiguity
Raised By: cx (MISSED_BY_gc, MISSED_BY_ALL)
Description: "Within one round" for unstated refusal basis — debate round vs cross-review round
not specified. In §14 context, cross-review rounds are the active rounds.
Severity: LOW
Rationale: Context makes "cross-review round" the obvious interpretation; clarity issue only.

**CRv10-G** — Duplicate split at cross-review limit boundary
Raised By: cx (MISSED_BY_cx)
Description: At the cross-review limit, "same round or next round" may provide no slot.
H-2 at limit handles this explicitly.
Severity: LOW
Rationale: H-2 invoked at limit can decide to allow additional rounds.

**CRv10-H** — H-2 intermediate ledger state
Raised By: cx (MISSED_BY_gc)
Description: Ledger state during H-2 mediation not defined. Final outcomes (accept → Accepted
Risk; refuse → SUB_ISSUE or ABORT) are explicitly defined.
Severity: LOW
Rationale: Final states defined; intermediate state is procedurally implicit (OPEN, pending H-2).

---

## Mixed-Finding Handling (§14-5)

HIGH finding CRv10-A present → process HIGH first.

1. CONSENSUS_OK invalidated.

[CONSENSUS_REVOKE: crossreview-amendment-20260613-v10 | reason: §14 cross-review CRv10-A]
Cross-review counter RESET — v11 proposal lineage begins.

2. LOW findings CRv10-B through CRv10-H → Status: OPEN, re-evaluated in v11 lineage.
3. Previously Accepted Risks (CRv9-D, CRv9-E, CR-10, CR-21~28) → Status: OPEN, re-evaluated
   in first cross-review round of v11 lineage per CR-18 (simple re-accept vote if area unchanged).
