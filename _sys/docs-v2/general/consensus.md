# General — Consensus & Voting
> Source: protocol-consensus.md v4.1

---

## 1. Round Lifecycle

```
PROPOSE → VOTE → FINALIZE
```

1. `hub.py consensus-propose --subject "..." --voters cc,gc,cx --from {peer}`
2. `hub.py consensus-vote --round-id r-XXXX --voter {peer} --vote agree|disagree|abstain`
3. Auto-finalize when all votes collected:

| Outcome | Condition | Action |
|---------|-----------|--------|
| `unanimous` | All agree | Proceed |
| `abstain` | Mix of agree + abstain | Proceed |
| `human_gate` | Any disagree | Escalate to Human (Tier 0) |
| `timeout` | Stalled > 30min | Escalate to Human |

---

## 2. Vote Meanings

| Vote | Meaning |
|------|---------|
| `agree` | Explicit approval |
| `disagree` | Explicit rejection (reason required) |
| `abstain` | Offline auto-abstain after `offline_auto_abstain_minutes` |

---

## 3. R:10 Rules

- All registered voters must explicitly `agree` — no exceptions
- Offline auto-abstain does NOT satisfy unanimity at R:10
- Any offline/abstaining required voter → escalate to Human for override or policy downgrade
- PTY peers (ag): write vote directly to `.ai/consensus/{round_id}.json` OR relay via `hub.py send --to cc` (NEVER `hub.py ask` — PTY deadlock risk)

### 3.1 Gate-Based Quorum (D-08g)
- **Gate-OPEN peers only**: Only peers whose health gate is OPEN at round-start count toward quorum. A gate-CLOSED peer's timeout is gate-closure (availability loss), NEVER silent approval.
- **At COLLAB_RATE = 10**: Every gate-OPEN registered voter in `protocol.json["consensus"]["r10_voters"]` must explicitly vote `agree` before FINALIZE. A mid-round gate closure without a prior `agree` blocks finalization and escalates to Human (Tier 0). A previously cast `agree` remains valid.
- **At COLLAB_RATE < 10**: Mix of `agree` + `abstain` permitted if min quorum met. Any explicit `disagree` blocks; requires unanimous active consent or Human override.
- **Gate state is round-scoped**: Snapshot captured at round-start. Gate closure after snapshot does NOT change N (the quorum denominator). A previously cast vote stands through round close.
- **Voter set change**: If the effective eligible voter set must change mid-round, the round must restart with a fresh snapshot.
- **Stale examples updated**: `hub.py consensus-propose --voters cc,ag,cx` (gc SUSPENDED 2026-06-19).

### 3.2 Quorum Authority Principle (INV-28, D-08g unanimous)
- **Minimum quorum**: `max(2, f(N, risk))` where N = count of gate-OPEN eligible voters at round-start snapshot. f is risk-adjusted (undefined above N=3; default to N).
- **Non-proposer requirement**: At least one voter from a distinct failure domain from the proposer must actively `agree`. Proposer MUST NOT self-finalize.
- **Retroactive veto**: NONE for procedurally valid rounds. A peer gate-OPEN at round-start that did not vote `disagree` before FINALIZE cannot retroactively block. Exception: finalization that violates a higher-order invariant (INV-01~19) may be voided by Human.
- **Mid-round gate closure rule**: Gate closure after snapshot does not change N. At R:10, any required voter with no cast `agree` → blocks finalization. No silent-approval by inaction.

---

## 4. Final Call (mandatory at R:8+)

Proposer sends: *"Any additional feedback or missed context?"*
All peers reply `ACK/Proceed` or raise concerns.
Round finalizes only after all ACKs received. (INV-02)

---

## 5. Tiebreak (2v2 or N/2 split)

1. Check `protocol.json["workload"]["capability_registry"]` for disputed task domain
2. Highest-domain-expertise peer recommends to Human
3. Human (Tier 0) makes final decision — no peer can override

---

## 6. Stale Round Sweep

```
hub.py consensus-sweep   # clean rounds stalled > timeout_minutes (30m)
```

Run at session end or ctx-save.
