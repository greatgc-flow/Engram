# DEBATE_PROTOCOL — Round 1 Log

> Date: 2026-06-13
> Draft version reviewed: v0.1
> Participants: cc (Claude), gc (Gemini), cx (Codex)

---

## gc Response (57s)
STATUS: NEED_MORE_INFO

CONCERNS:
1. Orchestration Rigidity — cc hardcoded as orchestrator, any peer should be able to lead
2. Headless Execution Deadlocks — H-1~H-5 hang in non-interactive CLI environments; need autonomous fallback
3. Context/Token Exhaustion — no mid-debate state compaction mechanism
4. Subjective [DONE] Criteria — must require explicit unanimous agreement
5. Diagram Ambiguity — "NO → next round" re-entry point not shown

MISSING:
- Assumptions & Dependencies node in §3
- Security & Safety Constraints node in §3
- Peer Context Dump in §0 (not just user, but peer session context too)
- Debate Abort Mechanism

OPEN QUESTIONS:
1. Peer failure/timeout during parallel query — retry/fallback?
2. Post-consensus implementation failure — resume existing debate or new debate (T-3)?
3. §3-5 General-Specific should be cross-cutting "lens", not sibling category

---

## cx Response (53s)
STATUS: NEED_MORE_INFO

CONCERNS (30 items, condensed):
- §0: ambiguity path not actionable — needs register with fields (source, quote, competing interpretations, owner, resolution, promotion target)
- §1: T-3 needs evidence criteria; T-4 too broad; missing triggers for policy/persistence/cross-agent changes
- §2: GOAL_OK too shallow — needs assumptions, non-goals, success criteria, affected artifacts, decision authority, re-lock rule
- §3: MECE tree incomplete — missing: stakeholders, state/persistence, lifecycle, observability, verification, migration, ownership, compatibility, rollback, security, data model, authority/precedence, acceptance criteria
- §3 [DONE]: needs objective close criteria per node, evidence links, reviewer signoff, reopen rule
- §4: cc-as-orchestrator bottleneck; needs: transcript integrity, round numbering, late responses, unavailable peers, sub-issue merge rules
- §5: H-2 "3 rounds" arbitrary; conflicts with "no limits" rule; H-3 needs thresholds
- §6: CONSENSUS_OK edge cases — "active peers" manipulable, must tie to specific proposal version/hash, no revocation mechanism
- §7: "Reflected in relevant docs" too abstract — needs file schemas, write order, promotion criteria, verification

MISSING (16 items):
1. Canonical proposal/version artifact
2. Open issue, assumption, ambiguity, accepted-risk registers
3. Consensus validity tied to proposal version/hash
4. Peer membership and availability policy
5. Persistence schema for debate logs, consensus records, handoff pointers
6. Artifact precedence and conflict-resolution model
7. Verification/checklist phase before implementation
8. Post-implementation validation and regression phase
9. Reopen/revocation procedure
10. Protocol amendment/versioning procedure
11. Encoding/file integrity requirements
12. Security/privacy review section
13. Ownership/RACI responsibility section
14. Migration and rollback section
15. Acceptance criteria/test planning section
16. Tooling for automatic validation

---

## cc Synthesis (Claude Judgment)

ADOPT (both agree):
- Dynamic orchestrator — any peer can lead, assigned per debate not hardcoded
- §3 MECE tree expansions: Assumptions/Dependencies, Security/Safety, Observability/Acceptance Criteria
- §3 [DONE] = objective criteria + unanimous peer sign-off + reopen permitted
- §0 expansion: peer context dumps + structured ambiguity register
- §6 canonical versioned proposal + revocation mechanism
- New §: Abort Mechanism
- New §: Canonical Proposal Artifact
- Persistence schemas for DEBATE_LOG.md and handoff promotion

REFINE:
- gc headless fallback: each H-x point gets timeout + autonomous default
- cx 30 concerns: split into v0.2-structural (address now) vs v1.0-operational (DEFERRED section)
- §3-5 General-Specific: reposition as cross-cutting "lens" applied to nodes 1-4 (gc's suggestion)

COUNTER: None — all feedback is valid.

RESULT: v0.2 draft needed. Proceed to Round 2.
