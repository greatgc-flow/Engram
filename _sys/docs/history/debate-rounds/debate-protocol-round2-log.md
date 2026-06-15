# DEBATE_PROTOCOL — Round 2 Log

> Date: 2026-06-13
> Draft version reviewed: v0.2
> Participants: cc, gc, cx

---

## gc Round 2 Response (46s)
STATUS: DISAGREE

CRITICAL CONCERN:
- §5 H-2 Autonomous Fallback allows "MAJORITY position" as provisional consensus — directly violates §6 unanimous consent
- Fix: deadlock → ABORT(A-2) or hard pause, NOT majority rule

UNRESOLVED CONCERN:
- Context/token exhaustion: peers need explicit rule to only load §9 Proposal + §10 Ledgers per round, not full transcripts

OPEN QUESTION:
- Can ABSENT peer use §6 Revocation after returning?

---

## cx Round 2 Response (70s)
STATUS: NEED_MORE_INFO

ADDRESSED: §0 ambiguity/context, §1 triggers, §2 GOAL_OK, §3 nodes/[DONE], §4 coordinator, §6 proposal-specific consensus, §7 schemas, §8 loop, §9/§10/§11 all added.

STILL UNRESOLVED:
1. Absent peer: who marks, after what timeout, minimum quorum undefined
2. Proposal identity format inconsistent across §4/§6/§9/query template
3. Hash: algorithm, text boundaries, line endings, metadata inclusion undefined
4. H-2 provisional majority (same as gc CRITICAL)
5. H-4 timeout: too broad for policy/security/cross-agent changes
6. Ambiguity Register has no persistence location in §10
7. §3 [DONE] "objective criteria" defined in spirit but not in minimal default form
8. Decision authority in §2 vs unanimous consent — semantics unclear

CONCERNS (new):
1. File encoding appears corrupted (Korean text in headings flagged) — v0.1 BLOCKING
2. Absent peer manipulation risk
3. Hash/version identity not canonical
4. Precedence model: PROTOCOL.md vs protocol.json vs handoff vs DEBATE_LOG
5. H-4 risk gate missing

DEFERRED objections that are v0.1-blocking:
- File encoding/integrity requirements
- Decision precedence model (minimal)
- Amendment procedure (minimal rule: "amendments require new debate")

---

## cc Synthesis Round 2

ADOPT ALL (gc + cx):
- Remove H-2 majority rule → ABORT(A-2) + user escalation hard stop
- Context bounding rule: §4 — peers load only §9 + §10 per round
- Absent peer rules: coordinator marks, confirmed timeout, N-1 quorum
- Hash: SHA-256, UTF-8, Unix LF, proposal content only
- Ambiguity Register → §10
- H-4 risk gate (HIGH RISK = USER_REVIEW_REQUIRED, no autonomous)
- Minimal precedence model (new §)
- Minimal amendment rule
- File encoding note (Korean annotations intentional, UTF-8 normalized)
- Proposal identity: standardize to single format across all sections

RESULT: v0.3 needed. Proceed.
