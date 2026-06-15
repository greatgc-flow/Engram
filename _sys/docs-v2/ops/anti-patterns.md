# Ops — Peer Anti-Patterns
> 21 failure modes for adversarial cross-review. "What NOT to do."
> Referenced by: ops/debate.md §14 (cross-review), ops/templates.md §4 ([DEBATE_ROUND])

---

## 1. Consensus Drift (4 patterns)

- **AP-01 Conditional Agreement**: Saying "Agree but..." or "Agree if..." instead of NEED_MORE_INFO.
  - [SIGNAL] Vote status field contains qualifiers or "if" statements.
  - [FIX] Revoke vote; move to NEED_MORE_INFO until condition is resolved in proposal.

- **AP-02 Silent Abstain**: Not voting in a round, hoping it proceeds without you.
  - [SIGNAL] Round times out with N-1 responses and no ABSENT marker.
  - [FIX] Coordinator must pause; explicitly query the silent peer before closing round.

- **AP-03 Scope Creep during Vote**: Adding new requirements mid-round after GOAL_OK.
  - [SIGNAL] A peer response introduces new requirements after GOAL_OK has been declared.
  - [FIX] Invalidate current round; update [GOAL_FRAME]; issue new proposal version.

- **AP-04 Premature FINALIZED Claim**: Calling a task done before Final Call (R:8+) or VERIFY_PASS.
  - [SIGNAL] Task moved to [RECENT_COMPLETED] without a [CLOSURE_MANIFEST] record.
  - [FIX] Revert status; perform Final Call or verification phase.

---

## 2. Communication Failure (4 patterns)

- **AP-05 Private Channel Use**: Logic updates not visible to all room members.
  - [SIGNAL] Out-of-band writes to files peers use as logic anchors, without broadcast.
  - [FIX] Immediately broadcast the change; record in handoff.md.

- **AP-06 Asymmetric Context**: One peer acting on info not shared in shared state.
  - [SIGNAL] Reasoning cites a file or decision not present in handoff.md or docs.
  - [FIX] Handoff-sync; peer must re-read handoff.md before continuing.

- **AP-07 Hallucinated History**: Referencing a decision or consensus that was never recorded.
  - [SIGNAL] "We already agreed to X" but [CONSENSUS_HISTORY] has no such entry.
  - [FIX] Search consensus log; if missing, treat as NEW proposal and seek consensus.

- **AP-08 Dead-drop Response**: Providing a reply without reading the previous peer's input.
  - [SIGNAL] Peer A raises a concern; Peer B's response in the same round ignores it.
  - [FIX] Coordinator rejects response; Peer B must acknowledge Peer A's concern explicitly.

---

## 3. Governance Violation (4 patterns)

- **AP-09 Solo Execution**: Making changes above collab_rate threshold without consensus.
  - [SIGNAL] workspace/ or _sys/ edits without a matching CONSENSUS_OK record.
  - [FIX] Immediate halt; rollback or retroactive consensus review.

- **AP-10 Direct state.json Write**: Manually editing IPC state instead of using hub.py.
  - [SIGNAL] state.json timestamp updated but hub.py command log is empty.
  - [FIX] Re-run hub.py update-status to ensure schema validity and audit trail.

- **AP-11 Bypassing Health Gate**: Routing work to a RED peer or peer with gate_open: false.
  - [SIGNAL] hub.py ask targeting a peer that fails health-precheck.
  - [FIX] Run peer-recover; if recovery fails, route to alternate peer.

- **AP-12 Quorum Inflation**: Counting offline or non-member peers to reach majority.
  - [SIGNAL] Consensus claimed with fewer than required active member votes.
  - [FIX] Recount; wait for missing votes or declare ABSENT per protocol.

---

## 4. Quality Anti-Patterns (4 patterns)

- **AP-13 Blind Copy-Paste**: Moving code fragments without verifying portability.
  - [SIGNAL] Hardcoded P:\ or absolute paths appear in new scripts.
  - [FIX] Run portability-auditor agent; replace with relative/dynamic paths.

- **AP-14 Incomplete Closure Manifest**: Finalizing with open ledger items.
  - [SIGNAL] [CLOSURE_MANIFEST] has items still marked OPEN.
  - [FIX] Block finalization; every item must have a sink (RESOLVED/DEFERRED/PROMOTED).

- **AP-15 Missing Test before Write**: Applying a fix without empirical reproduction.
  - [SIGNAL] Bug fix committed without a corresponding failing test in _sys/tests/.
  - [FIX] Write failing test first; verify fix passes; confirm no regressions.

- **AP-16 Format Drift**: Using non-standard headers or skipping template sections.
  - [SIGNAL] [DEBATE_ROUND] missing REASONING or POSITION field.
  - [FIX] Coordinator rejects output; peer must re-format using ops/templates.md.

---

## 5. Evolution Anti-Patterns (3 patterns)

- **AP-17 Lesson Ignored**: Repeating a mistake already recorded in active-lessons.jsonl.
  - [SIGNAL] Peer makes an error matching a CRITICAL or HIGH lesson in active set.
  - [FIX] Immediate halt; peer must acknowledge lesson and apply remediation before continuing.

- **AP-18 Proposal without Rationale**: Proposing a change without impact analysis.
  - [SIGNAL] [PROPOSAL] contains only "how" without "why" or Affected Artifacts.
  - [FIX] Reject proposal; peer must provide technical rationale and impact map.

- **AP-19 Directive Expiry Ignored**: Following a runtime-directive past its TTL.
  - [SIGNAL] Peer cites a directive that hub.py directive-list shows as expired.
  - [FIX] Clear directive; re-evaluate behavior based on general protocol.

---

## 6. Coordination Anti-Patterns (2 patterns)

- **AP-20 Coordinator Monopoly**: One peer performing all synthesis without delegation.
  - [SIGNAL] Same peer is coordinator for 3+ consecutive rooms/topics.
  - [FIX] Force rotate coordinator role to the next healthy peer via hub.py assign-role.

- **AP-21 Context Hoarding**: Storing complex analysis in peer-local memory only.
  - [SIGNAL] Peer output says "I recall X" but X is not in any shared doc.
  - [FIX] Peer must dump local context to a .md file in _archive/ and link it in handoff.md.
