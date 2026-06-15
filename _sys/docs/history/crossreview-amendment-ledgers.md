# Ledgers: debate-protocol-amendment-crossreview

## Open Issues
(none — all resolved)

## Assumptions

[ASSUMPTION-1] Status: CONFIRMED
Statement: Cross-review happens AFTER initial CONSENSUS_OK, BEFORE §7 documentation + implementation
Source: cc
Confirmed By: cc, gc, cx

[ASSUMPTION-2] Status: CONFIRMED
Statement: CLEAN = all MISSED_BY/WRONG_BY/PREMATURE_CONSENSUS_BY/MISSED_BY_ALL fields = NONE, no open questions
Source: cc
Confirmed By: cc, gc, cx

[ASSUMPTION-3] Status: CONFIRMED
Statement: Cross-review target = (a) all other peers' reasoning across all rounds AND (b) the final §9 proposal text
Source: cc
Confirmed By: gc, cx (Round 1 AGREE)

[ASSUMPTION-4] Status: CONFIRMED
Statement: New §14 is the right placement; §8 SEE/VERIFY remains post-implementation only
Source: cc
Confirmed By: gc, cx

---

## Cross-Review Findings — Full Ledger

> Abbreviations: RESOLVED_HIGH = triggered CONSENSUS_REVOKE + new proposal;
> RESOLVED_LOW = accepted as Accepted Risk; status at debate close shown.

| ID | Round | Raised By | Severity | Description (short) | Status |
|:---|:------|:----------|:---------|:---------------------|:-------|
| CR-1~9 | v3 CR | — | — | (resolved in v3 lineage; see round3 files) | RESOLVED |
| CR-10 | v3 CR | gc | LOW | (see round3.md) | RESOLVED_LOW |
| CR-21~28 | v3–v9 CR | various | LOW | (see prior round files) | RESOLVED_LOW |
| CRv9-A | v9 CR-1 | gc,cx | HIGH | coordinator §14 scope exemption | RESOLVED_HIGH → v10 |
| CRv9-B | v9 CR-1 | cx | HIGH | "confirms LOW" structurally unreachable (challenger in vote pool) | RESOLVED_HIGH → v10 |
| CRv9-C | v9 CR-1 | cx | HIGH | SEVERITY_CHALLENGE non-exhaustive (silent/non-standard not defined) | RESOLVED_HIGH → v10 |
| CRv9-D | v9 CR-1 | gc | LOW | finding limit per round | RESOLVED_LOW |
| CRv9-E | v9 CR-1 | cx | LOW | "active peers" vs "non-ABSENT active peers" | RESOLVED_LOW |
| CRv10-A | v10 CR-1 | cx | HIGH | vote population in path(a) — challenger always votes HIGH, confirms LOW unreachable | RESOLVED_HIGH → v11 |
| CRv10-B | v10 CR-1 | cx | LOW | merge/split loop | RESOLVED_LOW |
| CRv10-C | v10 CR-1 | cx | LOW | severity inheritance | RESOLVED_LOW |
| CRv10-D | v10 CR-1 | cx | LOW | terminal authority | RESOLVED_LOW |
| CRv10-E | v10 CR-1 | cx | LOW | non-challenge stall | RESOLVED_LOW |
| CRv10-F | v10 CR-1 | cx | LOW | "one round" ambiguity | RESOLVED_LOW |
| CRv10-G | v10 CR-1 | cx | LOW | at-limit boundary | RESOLVED_LOW |
| CRv10-H | v10 CR-1 | cx | LOW | intermediate ledger state | RESOLVED_LOW |
| CRv11-A | v11 CR-1 | gc,cx | HIGH | empty vote pool vacuously confirms LOW (no peers = no objection) | RESOLVED_HIGH → v12 |
| CRv11-B | v11 CR-1 | cx | HIGH | non-exhaustive two-case outcome (empty pool not a third case) | RESOLVED_HIGH → v12 |
| CRv13-A | v13 CR-1 | cx | HIGH | returning ABSENT peer acceptance req + scope-narrowing fresh assent unspecified | RESOLVED_HIGH → v14 |
| CRv13-B | v13 CR-1 | gc | LOW | H-2 recursive loop (path(b) → H-2 → path(b)...) | RESOLVED_LOW |
| CRv13-C | v13 CR-1 | gc | LOW | non-MECE H-2 options (HIGH/LOW/SUB/ABORT cover all cases) | RESOLVED_LOW |
| CRv14-A | v14 CR-1 | cx | LOW* | returning ABSENT peer timing / §7 interaction — no defined trigger post-§7 | RESOLVED_LOW (H-2) |
| CRv14-B | v14 CR-1 | cx | LOW* | post-H-2 option(ii) path(b) premise mismatch | RESOLVED_LOW (H-2) |

> \* CRv14-A and CRv14-B were initially classified HIGH by coordinator; reclassified to LOW
>   and accepted as Accepted Risk by H-2 directive (user). §14 cross-review closure.

---

## Accepted Risks (Final — All Lineages)

| ID | Description | Lineage | Basis |
|:---|:------------|:--------|:------|
| CR-10 | (see round3.md) | v3 | peers |
| CR-21~28 | (see prior round files) | v3–v9 | peers |
| CRv9-D | finding limit per round | v9 | peers |
| CRv9-E | "active peers" vs "non-ABSENT active peers" | v9 | peers |
| CRv10-B | merge/split loop | v10 | peers |
| CRv10-C | severity inheritance | v10 | peers |
| CRv10-D | terminal authority | v10 | peers |
| CRv10-E | non-challenge stall | v10 | peers |
| CRv10-F | "one round" ambiguity | v10 | peers |
| CRv10-G | at-limit boundary | v10 | peers |
| CRv10-H | intermediate ledger state | v10 | peers |
| CRv13-B | H-2 recursive loop | v13 | peers |
| CRv13-C | non-MECE H-2 options | v13 | peers |
| CRv14-A | returning ABSENT peer timing / §7 interaction | v14 | H-2 closure |
| CRv14-B | post-H-2 option(ii) path(b) premise mismatch | v14 | H-2 closure |

---

## Ambiguity Register

[AMBIGUITY-1] Status: RESOLVED
Source: protocol gap analysis
Quote: "더이상 의견, 질문이 나오지 않을 때까지 완결적으로 반복"
Competing Interpretations:
  - A: Cross-review of all peers' REASONING
  - B: Cross-review of the FINAL PROPOSAL DOCUMENT only
  - C: Both A and B
Owner: cc
Resolution: C (Both) — adopted in §14-1 Scope
Promoted To: §14-1 (a) + (b)

---

## Debate Outcome

Status: COMPLETE
Final Proposal: crossreview-amendment-20260613-v14
Total Debate Rounds: 14 (v7 → v14)
§14 Cross-Review Rounds (v14 lineage): 1
§14 Closure: H-2 directive — 2026-06-13
Consensus By: cc, cx (gc ABSENT Round 14 — N-1 quorum)
Implemented: DEBATE_PROTOCOL.md v0.7 (§14-5 path(a)/(b) complete; incorporated in v0.8)
DEBATE_LOG entry: 2026-06-13 debate-protocol-amendment-crossreview-v0.7
