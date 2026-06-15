# Protocol: Consensus & Voting (v4.1)
> Source: `_sys/ai/protocol.json["consensus"]` | Part of composable PROTOCOL.md

## 1. Consensus Round Lifecycle

1. **PROPOSE** — Any peer initiates a round via `hub.py consensus-propose --subject "..." --voters cc,gc,ag --from {peer}`
2. **VOTE** — All registered voters reply via `hub.py consensus-vote --round-id r-XXXX --voter {peer} --vote agree|disagree|abstain`
3. **FINALIZE** — Auto-finalized when all votes are collected:
   - All agree → `unanimous` → proceed
   - Mix of agree/abstain → `abstain` → proceed
   - Any disagree → `human_gate` → escalate to Human (Tier 0)
   - Timeout (30min) → `timeout` → escalate to Human

## 2. Voting Options

| Vote | Meaning |
|------|---------|
| `agree` | Explicit approval |
| `disagree` | Explicit rejection (reason required) |
| `abstain` | Declining to vote (offline peers auto-abstain after `offline_auto_abstain_minutes`) |

## 3. R=10 Unanimity Rules

- **Mandatory**: All registered voters must explicitly `agree`. 
- **No Auto-Abstain Bypass**: For R=10, an offline auto-abstain does NOT satisfy unanimity. If a required voter is offline or abstains, the round must be escalated to Human (Tier 0) for override or policy downgrade.
- **No Exceptions**: Strict prohibition of arbitrary judgment for any governed action (write/execute). Every phase change requires consensus round + Final Call before execution.
- **PTY Peers (ag)**: Must write vote directly to `.ai/consensus/{round_id}.json` OR relay via `hub.py send --to cc` (never use `hub.py ask` for consensus — PTY deadlock risk).

## 4. Tiebreak Protocol (2v2 or N/2 split)

1. Check `protocol.json["workload"]["capability_registry"]` for the disputed task domain.
2. The peer with highest domain expertise makes a recommendation to Human.
3. Human (Tier 0) makes final decision. No peer can override Human veto.

## 5. Final Call (§P-3-FC, mandatory at R:8+)

Proposer sends: `"Any additional feedback or missed context?"`  
All peers must reply `ACK/Proceed` or raise concerns.  
Round finalizes only after all ACKs received.

## 6. Timeout & Sweep

- Auto-escalation: rounds stalled > `consensus.timeout_minutes` (30m) → outcome=timeout, escalated to human
- Run `hub.py consensus-sweep` at session end or ctx-save to clean stalled rounds

## §HISTORY
- v4.1 (2026-06-12): Canonicalized default consensus voters across protocol.json and orchestration.json.
- v4.0 (2026-06-11): Extracted from PROTOCOL.md §P-3; added PTY vote policy, tiebreak, ag direct-write rule
