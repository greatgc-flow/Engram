# Ops — Exhaustive Work Session (끝장 작업)
> Source: DEBATE_PROTOCOL.md v0.10 CANONICAL · 2026-06-14
> Changelogs and appendices → _sys/docs/protocol/DEBATE_PROTOCOL.md (original)

---

## §1 — Roles

| Role | Responsibility |
|------|---------------|
| **Proposer** | Submits the subject and frames the debate topic |
| **Challenger** | Adversarially challenges all claims and edge cases |
| **Synthesizer** | Builds consensus from points of agreement |
| **Active Coordinator** | Controls round lifecycle, calls vote |

---

## §3 — Invocation

```
hub.py consensus-propose --subject "..." --voters cc,gc,cx --from {peer} --mode DEBATE
```

Two debate tiers:
- **FULL**: multi-round (T-2 format). Required for HIGH/CRITICAL findings.
- **ABBREVIATED**: single-round fast-path for LOW-stakes T-5 debates.

---

## §4 — Round Format

Each round:
1. Proposer presents position
2. All challengers respond (one round = one response per peer)
3. Synthesizer consolidates + identifies unresolved points
4. Vote or proceed to next round

---

## §5 — Voting

Same consensus rules as `general/consensus.md`. At FULL tier, R:10 rules apply.

---

## §6 — Tiebreak

Follow `general/consensus.md §5`. Tiebreak escalates to Human (Tier 0).

---

## §7 — Amendment

Amendments to `DEBATE_PROTOCOL.md` itself require: FULL tier debate → R:10 unanimous → ledger entry in `history/crossreview-amendment-ledgers.md`.

**Expedited amendment (§13-1):** For §16 Exhaustive Work Sessions, HIGH findings may trigger immediate amendment without a new T-2 round. Coordinator certifies and records in closure manifest.

---

## §8 — Feedback Loop

```
debate outcome → narrow Specific rule OR General proposal → improve step
HIGH/CRITICAL finding → immediate amendment or DEFER to T-2
```

---

## §12 — Tier Precedence

| Tier | Authority | Examples |
|:----:|-----------|---------|
| 0 | Human veto | Final override, policy downgrade |
| 1 | Core invariants | 10-invariants.md (NEVER overridden) |
| 1.5 | User Directives | `user-directives.md` (auto-injected, above Tier 2) |
| 2 | General protocol | `general/*.md` |
| 3 | Project/room | `protocol.json` session config |
| 4 | Peer | `specific/*.md` deltas |
| 5 | Task | Task-scoped overrides |

**Constitutional constraint**: HIGH findings against Tier 1 artifacts → DEFER to T-2 (cannot resolve in current session).

---

## §14 — Review Criteria

Finding severity:

| Severity | Definition | Required action |
|----------|-----------|-----------------|
| CRITICAL | Invalidates goal frame or produces unsafe output | ABORT current session, open T-2 |
| HIGH | Correct, causes significant breakage if unresolved | Fix before closure |
| LOW | Improvement, not blocking | Ledger only (DEFER acceptable) |

---

## §16 — Exhaustive Work Session Rules (끝장 작업 거버넌스)

1. **ROI Gate**: Continue rounds as long as HIGH findings are being resolved. Stop when 2 consecutive rounds produce only LOW or no findings.
2. **Termination authority**: Active coordinator (not peer-specific) calls closure.
3. **Finding ledger**: Track HIGH/LOW/DEFER explicitly. Unresolved HIGH → cannot close.
4. **Closure Manifest** (Appendix D template): record final state, all HIGH resolutions, open LOWs/DEFERs, next T-2 scope if any.

**Standing Rule (2026-06-14):** ROI-gate autonomous termination is authorized — when gate reached, coordinator may terminate without user confirmation.

---

## §17 — User Directives in Debate Context

User Directives (`_sys/ai/user-directives.md`) are Tier 1.5 — above operational Tier 2 rules.
They are auto-injected into all peer asks (see `general/directives.md`).
Debate may NOT override User Directives. If conflict: escalate to Human (Tier 0).
