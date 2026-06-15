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
