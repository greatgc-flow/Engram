# Skill: peer-propose
> Status: CANONICAL | Version: 1.0.0

## 1. When to Use
- When proposing a change that requires consensus at COLLAB_RATE >= 5.
- Use for protocol changes, _sys/ modifications, or hub.py changes.

## 2. Procedure

1. Open a topic thread:
   ```
   python _sys/core/hub.py thread-new --topic "{slug}" --from {peer_id} --msg "[PROPOSAL DISCUSSION]"
   ```

2. Submit the formal proposal using [PROPOSAL:] template from ops/templates.md:
   ```
   python _sys/core/hub.py proposal-add \
     --subject "{subject}" --from {peer_id} \
     --impact {LOW|MED|HIGH|CRITICAL} \
     --rationale "{why}" \
     --text "{what changes}"
   ```

3. Notify peers via broadcast:
   ```
   python _sys/core/hub.py broadcast --from {peer_id} --msg "PROPOSAL: {proposal-id} posted. Please vote."
   ```

4. Collect votes:
   ```
   python _sys/core/hub.py proposal-vote --proposal-id {id} --voter {peer} --vote agree|disagree|abstain
   ```

5. Check consensus:
   ```
   python _sys/core/hub.py proposal-list
   ```

## 3. Consensus Reached → Execute
Only proceed with the proposed change when `proposal-list` shows `CONSENSUS_OK`.
Record in handoff: `hub.py append-handoff --section CONSENSUS_HISTORY --text "proposal:{id} approved"`
