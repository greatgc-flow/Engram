# DEBATE_PROTOCOL — Cross-Review Log (SEE/VERIFY Phase)

> Date: 2026-06-13
> Result: VERIFY_FAIL — gaps found by both peers
> Action: v0.4 patch required

---

## gc Cross-Review

MISSED_BY_CX:
1. Precedence model inversion: DEBATE_LOG > CLAUDE.md — log should not override constitutional documents
2. Infinite livelock: H-2 triggers on "same positions 5 rounds" — but minor positional changes can avoid trigger indefinitely

WRONG_BY_CX:
1. SHA-256 hash: LLMs cannot compute/verify cryptographic hashes accurately → hallucinated hashes
2. MECE tree over-specification: forcing all operational nodes on simple policy debates is excess token burn

PREMATURE_CONSENSUS_BY_CX:
1. ABSENT peer permanent revocation ban: N-1 quorum + no revocation = one timeout permanently strips objection rights

BOTH_MISSED:
1. §12 violates existing CLAUDE.md/GEMINI.md "Constitutional documents require full node consensus to modify"
2. PROVISIONAL_DECISION has no rank in §12
3. Ledger bloat: ledgers grow unbounded, eventually defeating context bounding rule

VERDICT: GAPS_FOUND

---

## cx Cross-Review

MISSED_BY_GC:
1. §9 "file path" option defeats context bounding — content must be full text
2. H-1: proceeding with UNCONFIRMED assumptions conflicts with "zero ambiguity" goal
3. PROVISIONAL_DECISION implementation ambiguity (can it be implemented or promoted?)
4. Absent peer loses all objection rights — no acknowledgment path on return

WRONG_BY_GC: NONE (minor: §9 "file path" incompleteness, gc could have caught this)

PREMATURE_CONSENSUS_BY_GC:
1. H-2 resolved correctly but PROVISIONAL_DECISION ambiguity remains
2. Absent peer resolved too easily — N-1 + no revocation is too aggressive
3. Context bounding incomplete because §9 allows file path

BOTH_MISSED:
1. §12 Precedence bootstrap contradiction: T-7 required before promotion, but DEBATE_LOG outranks CLAUDE.md — circular
2. §7 no guaranteed path to update protocol file (only §13 amendments); no rule for initial adoption write
3. §13: versioned DEBATE_PROTOCOL-v{n}.md created but canonical DEBATE_PROTOCOL.md not specified as "always current"
4. §6: accepted risks require unanimous — should be stated explicitly (not implied)
5. §11 unanimity vs H-2 auto-abort — internal exception undeclared
6. §4 immutable transcripts + §10 mutable ledgers + §7 append-only full log — relationship underspecified
7. Mojibake: file contains actual encoding artifacts, not just intentional Korean

VERDICT: GAPS_FOUND

---

## cc Synthesis (VERIFY_FAIL)

CRITICAL fixes for v0.4:
1. §12: Redesign precedence — CLAUDE.md/protocol.json is constitutional (top); DEBATE_LOG entries add to/extend policy within constitutional space; promoted rules require T-2/T-7 to enter constitutional layer
2. §9: Remove "file path" option — Content MUST be full text; file path option removed
3. §11 + H-2: Declare H-2 timeout auto-abort as explicit exception to §11 unanimity
4. §13: Clarify DEBATE_PROTOCOL.md = always current canonical; versioned files = archive
5. PROVISIONAL_DECISION in §12: assign rank (below DEBATE_LOG entries, above KEY_DECISIONS), flagged PROVISIONAL, expires in 30 days

HIGH fixes:
6. SHA-256: replace with coordinator-assigned version tag; hash optional/tool-computed
7. H-2 livelock: add "OR total rounds > 15" as additional trigger
8. §6: explicitly state accepted risks require unanimous agreement (not a bypass mechanism)
9. H-1: UNCONFIRMED assumptions block implementation; must be resolved or moved to Accepted Risks before goal lock

DEFERRED (v0.5):
- Ledger compaction strategy
- Absent peer acknowledgment path on return
- MECE tree optional nodes annotation
- Transcript/ledger/full-log relationship schema
- Mojibake fix (encoding audit)
