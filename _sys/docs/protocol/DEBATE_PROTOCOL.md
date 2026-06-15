# DEBATE_PROTOCOL v0.10

> Status: CANONICAL v0.10
> Encoding: UTF-8. Korean text in parentheses are display labels for the bilingual project.
> Previous: v0.9 | Added: §12 Tier 1.5; §13 expedited amendment; §14-5 CRITICAL severity; §16-2 constitutional constraint; §16/§17 reordered; Appendix D Closure Manifest.
> Date: 2026-06-14

---

## Changelog from v0.9 → v0.10

> Applied 2026-06-14 via §16 exhaustive work session (cc+cx, HIGH findings)

| # | Section | Change | Source |
|:-:|:--------|:-------|:-------|
| 1 | §12 | Added Tier 1.5 (User Directives) between Tier 1 and Tier 2; conflict rules clarified | cx HIGH finding |
| 2 | §13 | Added §13-1 expedited amendment clause for §16 Exhaustive Work Sessions | cx HIGH finding |
| 3 | §14-5 | Added CRITICAL severity (above HIGH): invalidates goal frame, triggers ABORT(A-3) + new T-2 | cx HIGH finding |
| 4 | §16-2 | Added constitutional constraint: HIGH findings on Tier 1 artifacts → DEFER to T-2 | cx HIGH finding |
| 5 | §16/§17 | Reordered: §16 (Exhaustive Work Session) now physically precedes §17 (User Directives) | cx HIGH finding |
| 6 | §17 | Fixed Tier precedence description: see §12 for Tier 1.5; above Tier 2 for operational matters | cx HIGH finding |
| 7 | Appendix D | Added Closure Manifest template section | cx HIGH finding |

## Changelog from v0.9 (amendments)

> v0.9 amendment — applied 2026-06-14 via §16 exhaustive work session

| # | Section | Change | Source |
|:-:|:--------|:-------|:-------|
| 1 | §17 | New: User Directives — first-class artifact, Tier 1.5, hub.py auto-injection | cc+cx exhaustive review |
| 2 | §8 | Feedback loop diagram updated: §17 injection path, §16 boundary, NEXT CYCLE carry-forward | cc+cx exhaustive review |
| 3 | §14 | Added scope boundary note vs §16 | cc+cx exhaustive review |
| 4 | §16-3 | Termination authority: "active coordinator" (not cc-specific) | cx HIGH finding |
| 5 | §16-4 | Added finding ledger rules (HIGH/LOW/DEFER) | cx LOW finding |

## Changelog from v0.8

| # | Section | Change | Source |
|:-:|:--------|:-------|:-------|
| 1 | §16 | New: Exhaustive Work Session Governance (끝장 작업) — ROI-based termination, standing rule (2026-06-14) | User directive |
| 2 | §4-2 | Peer invocation now uses minimum non-interactive permissions (cc: `--allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits`, cx: `-s workspace-write`, gc: `--approval-mode auto_edit --skip-trust`); §14 queries MUST use `--session-policy fresh` | hub-session-reuse-T2, peer-minimum-permissions |
| 3 | §1 | Added Debate Tier (FULL/ABBREVIATED) for low-stakes T-5 debates | Exhaustive review |
| 4 | §3 | Added expertise routing guidance; 2-5/6 scope boundary clarification | MECE review |
| 5 | §15 | Marked resolved deferred items | Status update |
| 6 | Appendix C | Anti-patterns #20, #21 added | Exhaustive review |

## Changelog from v0.7

| # | Section | Change | Source |
|:-:|:--------|:-------|:-------|
| 1 | §8 | Added `Closure Manifest` to ensure structural closure of all ledger items before `VERIFY_PASS` | cc+gc+cx T-2 debate |
| 2 | §14-5 | Added `R:10 Voting Override` to strictly enforce `protocol.json.consensus.r10_voters` quorum over operational `active_peers` | cc+gc+cx T-2 debate |

## Changelog from v0.6

| # | Section | Change | Source |
|:-:|:--------|:-------|:-------|
| 1 | §14-5 | Complete rewrite: explicit path (a) and path (b) escalation for LOW acceptance refusal | cc+gc+cx T-2 debate |
| 2 | §14-5 | Clarified Mixed-Finding Handling and Historical LOW Findings during CONSENSUS_REVOKE | cc+gc+cx T-2 debate |
| 3 | §14-5 | Added Duplicate Findings disambiguation rules | cc+gc+cx T-2 debate |

## Changelog from v0.5

| # | Section | Change | Source |
|:-:|:--------|:-------|:-------|
| 1 | §14 | New: Exhaustive Cross-Review Phase (끝장 교차검토) — trigger, peer self-summary, response format, termination, severity handling, loop limit, ledger schema | cc+gc+cx T-2 debate |
| 2 | §15 | Renamed from §14 DEFERRED (content unchanged) | — |
| 3 | §6 | Added: proceed to §14 after CONSENSUS_OK | — |
| 4 | §8 | Replaced diagram: linear §6→§14→§7→DO→§8 | — |
| 5 | §8 | Added note: §14 = DESIGN validation; §8 = IMPLEMENTATION validation | — |
| 6 | Appendix A | Step 6-B inserted: Exhaustive Cross-Review steps | — |
| 7 | Appendix B | B-13 added: Exhaustive Cross-Review example (all 3 peers) | — |
| 8 | Appendix C | Anti-patterns #17–19 added | — |
| 9 | Appendix D | §14 template section added | — |

## Changelog from v0.4

| # | Section | Change | Source |
|:-:|:--------|:-------|:-------|
| 1 | §3 | Added transition note: "When to draft §9 Proposal" | gc GAPS |
| 2 | §8 | Formally defined VERIFY_PASS / VERIFY_FAIL | cx GAPS |
| 3 | Appendix A | Rewritten: exact file names + invocation commands at each step | cx GAPS |
| 4 | Appendix B | B-3 example rewritten: peer MECE node submission format added | gc GAPS |
| 5 | Appendix B | B-4 fixed: STATUS: AGREE(pending) → NEED_MORE_INFO | gc GAPS |
| 6 | Appendix B | B-10 added: VERIFY_FAIL recovery path | cx TOP_ADDITION |
| 7 | Appendix B | B-11 added: SUB_ISSUE lifecycle | cx FAILURE_MODES |
| 8 | Appendix B | B-12 added: Mid-debate goal change | cx FAILURE_MODES |
| 9 | Appendix C | 8 anti-patterns added (conditional STATUS, stale consensus, etc.) | gc+cx |
| 10 | Appendix D | Fully rewritten: §3 MECE stub, §10 ledger stubs, query file naming, H-1/H-4 checkpoints, §7 output checklist, SEE/VERIFY checklist | gc+cx TEMPLATE_GAPS |

---

## Purpose

A reusable, recursive, closed-loop protocol for thorough multi-peer debate.
- Applicable to any topic
- MECE requirement exploration before any implementation
- Unanimous consent required — no compromise, no implicit agreement
- Quality guaranteed by structure, not by AI capability or memory

---

## §0. Input Gathering

Triggered after debate proposed. Before §2 Goal Framing.

**0-1. User Input (Clear)**
- Scope: memos, brain dumps, related files, previous debate results, handoff.md context
- Done: user confirms "no more" → `INPUT_COMPLETE`

**0-2. User Input (Ambiguous)** → Ambiguity Register (§10); fed into §5 H-1

**0-3. Peer Context Dump** (each peer before §2):
```
[PEER_CONTEXT: {peer_id}]
Relevant Prior Knowledge:
Known Assumptions:
Known Constraints:
Open Issues Carried In:
```

**0-4. Prior Debate Scan**
Auto-scan `P:\.ai\debate\` for related previous rounds.
Conflicting prior debates → Ambiguity Register.

**0-5. Collection Methods**
- File: `[INPUT_FILE: path]` → coordinator reads and summarizes
- Direct text: user pastes → coordinator organizes
- Prior debates: 0-4

---

## §1. Trigger Conditions

| Code | Condition | Evidence Required |
|:----:|:----------|:-----------------|
| T-1 | Requirements ambiguous or divergently interpreted | Conflicting peer statements |
| T-2 | Structural decision needed | — |
| T-3 | Same problem recurred | 2+ documented occurrences |
| T-4 | Completeness verification before implementation | Scope statement |
| T-5 | User explicitly requests | — |
| T-6 | Policy/persistence/cross-agent behavior change | Affected artifact list |
| T-7 | Conflict between documented rules | Conflicting rule references |

Proposal: `[DEBATE_PROPOSE: topic | trigger: T-x]`

**Debate Tier:**
| Tier | Applies When | Abbreviated Sections |
|:----:|:-------------|:---------------------|
| FULL | T-1, T-2, T-3, T-4, T-6, T-7 | None — run all sections |
| ABBREVIATED | T-5 only AND no HIGH_RISK scope | §0 optional; §3 one-pass only; §14 single-round spot-check (1 peer) |

ABBREVIATED still requires §6 Consensus and §7 Outputs. Use FULL when in doubt.

---

## §2. Goal Framing

All active peers must agree to a Goal Frame Artifact:

```
[GOAL_FRAME: {topic-slug}-{YYYYMMDD}-v{n}]
General Goal:
Specific Goal:
Explicit Assumptions:
Non-Goals:
Success Criteria:
Affected Artifacts:
Decision Authority:
```

Lock: all active peers declare `GOAL_OK:{goal-frame-id}`.
Changes → new version, re-lock required.

Decision Authority: only activated after H-2 mediation fails; produces PROVISIONAL_DECISION (Tier 3, §12).

---

## §3. MECE Requirement Exploration

**§3→§9 Transition:**
The §9 Canonical Proposal is drafted by the coordinator AFTER §3 exploration reaches sufficient depth for a concrete solution to emerge. The proposal encodes the proposed solution; peers then review it in rounds. §3 exploration may continue (reopen nodes) if the proposal review reveals new gaps.

**Expertise Routing (token-efficient):**
Coordinator may assign specific tree nodes to peers based on strengths rather than requiring all peers to explore all nodes:
- cx → nodes 3 (Constraints), 5 (Exception Handling), 6 (Lifecycle)
- gc → nodes 1–2 (Functional/Non-Functional, research-heavy), 4 (Assumptions)
- cc → all nodes; leads on 2 (Non-Functional NFRs), structural/policy framing
Node assignment is advisory — any peer may contribute to any node.

**Scope boundary — 2-5 vs 6:**
- 2-5 Maintainability: ongoing maintenance after deployment (readability, documentation quality, update procedures)
- 6. Lifecycle: one-time structural transitions (migration from current state, versioning/amendment, deprecation path)
When in doubt: if it involves a state transition, place in 6.

**Minimal [DONE] checklist:**
- [ ] All sub-nodes explicitly visited (not silently skipped)
- [ ] At least one concrete example or evidence cited
- [ ] No open questions remain under this node
- [ ] All active peers signed off: `[DONE: {node} | peers: {list} | date: {YYYYMMDD}]`
- `[DONE]` can be reopened: `[REOPENED: {node} | reason | by: {peer}]`

Note: For simple/low-stakes debates, lifecycle and observability nodes (2-6, 2-7, 6-x) may be marked N/A with peer consensus. They must be explicitly visited before marking N/A — not silently skipped.

**MECE Node Submission Format** (how a peer reports a node exploration):
```
[NODE_DONE: {node-id} | peer: {name} | date: {YYYYMMDD}]
Findings: (what was discovered)
Evidence: (concrete reference or example)
Open Questions: (or NONE)
Proposed [DONE]: YES | NO (if NO, why not)
```

```
[Exploration Tree]

1. Functional Requirements
   1-1. Must-have features
   1-2. Optional features
   1-3. Out-of-scope
   1-4. Stakeholders

2. Non-Functional Requirements
   2-1. Efficiency
   2-2. Effectiveness
   2-3. Flexibility
   2-4. Scalability
   2-5. Maintainability
   2-6. Observability
   2-7. Acceptance Criteria

3. Constraints
   3-1. System/structural
   3-2. AI capability
   3-3. Token/cost
   3-4. Security/privacy
   3-5. Compatibility

4. Assumptions and Dependencies
   4-1. Environmental
   4-2. State/persistence
   4-3. Peer capability
   4-4. External dependencies

5. Exception Handling
   5-1. Failure modes
   5-2. Batch handling
   5-3. Rollback/recovery

6. Lifecycle
   6-1. Migration from current state
   6-2. Versioning/amendment
   6-3. Deprecation

[Cross-Cutting Lens — applied to nodes 1-6]
General-Specific Separation:
  (G) workspace-independent
  (S) session/project-specific
  (C) connector between G and S
```

---

## §4. Collaboration Method

**4-1. Coordinator:** dynamically assigned; any peer; 1 vote only.
Duties: issue queries, maintain transcript, track rounds, manage ledgers, merge sub-issues.

**4-2. Query Mode:**
Coordinator writes ALL query files before invoking any peer.
Queries use `[INPUT_FILE: path]` format; files go to: `P:\_sys\gemini\{peer_id}-{YYYYMMDDHHMMSS}-{RAND4}.txt`
Invocation (standard rounds): `python "P:\_sys\core\hub.py" ask --to {peer_id} --query-file "{file}" 2>&1`

**Peer Permissions:** All peers run with minimum non-interactive permissions (no interactive approval prompts):
- cc: `--allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits`
- cx: `-s workspace-write`
- gc: `--approval-mode auto_edit --skip-trust` (auto-edit mode in default invoke_args)
These are set in `_sys/ai/orchestration.json`; no manual flag needed in hub.py calls.

**Session Policy:**
- Standard debate rounds (§4): `--session-policy auto` (default — context continuity across rounds)
- §14 Cross-Review queries: MUST use `--session-policy fresh` to prevent anchoring bias from session history:
  `python "P:\_sys\core\hub.py" ask --to {peer_id} --query-file "{file}" --session-policy fresh 2>&1`

**4-3. Round Format:**
```
[PEER: {name}] [ROUND: {n}] [PROPOSAL: {proposal-id}]
POSITION:
REASONING:
CONCERNS: (numbered, or NONE)
OPEN_QUESTIONS: (or NONE)
MISSING_ELEMENTS: (or NONE)
STATUS: AGREE / DISAGREE / NEED_MORE_INFO
```
Note: STATUS must be one of the three options — no conditional qualifiers (e.g., "AGREE pending X" is prohibited; use NEED_MORE_INFO instead).

**4-4. Round Management:**
- Rounds numbered from 1.
- Marking ABSENT: coordinator, after confirmed 30-min timeout (per `protocol.json consensus.timeout_minutes`), with user notification.
- Minimum quorum: N-1 active peers (3 peers → minimum 2).
- Transcripts: `P:\.ai\debate\{topic}-round{n}.md` — IMMUTABLE after written.

**4-5. Context Bounding Rule:**
Per round, peers load ONLY:
- §9 Canonical Proposal (full text — NOT a file path reference)
- §10 Ledgers
Compaction: ledgers >~10,000 chars → coordinator may archive resolved items ([ARCHIVED]).

**4-6. Sharing:** large → file; small → direct response.

**4-7. Sub-Issue Handling:**
- Discover: `[SUB_ISSUE: {id} | description]`
- File: `P:\.ai\debate\{topic}-subissue-{id}.md`
- Block parent if needed: `[BLOCKED_ON: subissue-{id}]`
- Merge: sub-issue conclusion → parent transcript → affected §3 nodes updated.

---

## §5. Human-in-the-Loop

Risk classes:
- **HIGH_RISK**: policy changes, security changes, cross-agent behavior, persistence schema changes
- **NORMAL**: documentation, internal design, non-policy implementation

| Code | When | Method | Autonomous Fallback |
|:----:|:-----|:-------|:--------------------|
| H-1 | Before goal locked | Show Goal Frame; request corrections | Timeout 30min → proceed ONLY if all assumptions CONFIRMED; UNCONFIRMED assumptions BLOCK goal lock |
| H-2 | Deadlock (5+ same-position rounds OR total rounds > 15) | Escalation + mediation request | Timeout 30min → ABORT(A-2); NO majority; see §11 |
| H-3 | Resource/cost decisions | Show estimated cost; request approval | Timeout 15min → ABORT |
| H-4 | Final consensus | Show consensus artifact | NORMAL: timeout 60min → proceed; HIGH_RISK: USER_REVIEW_REQUIRED (never autonomous) |
| H-5 | After implementation | Show results; trigger next cycle | Auto-schedule verification; notify async |

H-2 note: "No limits on turns/tokens" applies to normal rounds. H-2 is deadlock detection — not a turn cap.

---

## §6. Consensus Definition

**Consensus = all active peers declare `CONSENSUS_OK:{proposal-id}` for the same proposal version.**

1. All Concerns Ledger items: RESOLVED or moved to Accepted Risks (unanimously)
2. Accepted Risks = unanimously agreed — NOT a bypass mechanism
3. Proposal text unchanged since any CONSENSUS_OK declaration
4. Active peer = participated in at least one round AND not ABSENT in final round
5. Quorum: N-1 minimum

Prohibited: implicit agreement, conditional agreement, agreement on ambiguous text.

**Revocation:** `CONSENSUS_REVOKE:{proposal-id} | reason: ...` — debate resumes at affected §3 node.
**ABSENT peer:** cannot revoke; must propose new T-7 debate on return.

After all active peers have declared `CONSENSUS_OK:{proposal-id}`, proceed to §14 Exhaustive Cross-Review Phase before §7 documentation and implementation.

---

## §7. Outputs

| Output | Location | Rule |
|:-------|:---------|:-----|
| Round transcripts | `P:\.ai\debate\{topic}-round{n}.md` | IMMUTABLE |
| Full debate log | `P:\.ai\debate\{topic}-full.md` | Append-only |
| Ledgers | `P:\.ai\debate\{topic}-ledgers.md` | Updated by coordinator |
| Consensus record | `P:\_sys\docs\DEBATE_LOG.md` | Append-only |
| Handoff pointer | `handoff.md [PROMOTED_RULES]` | Update on consensus |
| Implementation tasks | `handoff.md PENDING_ISSUES` | Append |

DEBATE_LOG.md entry schema:
```
## [{YYYY-MM-DD}] {topic}
- Proposal: {proposal-id}
- Participants: {list}
- Rounds: {n}
- Decision: {one-line}
- Rationale: {key reasoning}
- Risk Class: NORMAL | HIGH_RISK
- Affected Artifacts: {list}
- Promoted To Constitutional Layer: YES | NO
- Full Log: P:\.ai\debate\{topic}-full.md
```

Handoff PROMOTED_RULES schema:
```
[PROMOTED_RULE: {id}]
Source: DEBATE_LOG.md#{date}-{topic}
Rule: {one-line actionable statement}
Scope: GLOBAL | PROJECT:{name}
Risk Class: NORMAL | HIGH_RISK
Constitutional: YES | NO
Enforcement: {how checked}
```

Verification: coordinator confirms each output by read-back after writing.

---

## §8. Feedback Loop

```
[§17 USER DIRECTIVES] ──────────────────────────────────────────┐
       |                                                         |
       v (auto-injected by hub.py into every peer ask)          |
[INPUT GATHER §0]                                               |
       |                                                         |
       v                                                         |
[TRIGGER §1] --> [GOAL FRAME §2] --> [MECE EXPLORE §3]         |
       ^                                      |                  |
       |                          [§9 PROPOSAL when emerges]    |
       |                                      |                  |
       |                                      v                  |
  [NEXT CYCLE] <-- [SEE/VERIFY §8] <-- [DO/IMPLEMENT]          |
       ^                                      ^                  |
       |                                      |                  |
       | (carries: active directives,         |                  |
       |  accepted risks, feedback sinks)  [§7 DOCUMENT + H-4]  |
       |                                      ^                  |
       |                                      |                  |
       └──── loop sealed ──────────[§14 CROSS-REVIEW]           |
                                    CLEAN --> §7                 |
                                    HIGH  --> §3 (new proposal)  |
                                    LOW + accepted --> §7        |
                                              ^                  |
                                              |                  |
                                    [CONSENSUS_OK §6]            |
                                              ^                  |
                                              |                  |
                                        [ROUNDS §4/§5] <────────┘
```

> Note: §14 Exhaustive Cross-Review (pre-implementation) and §8 SEE/VERIFY
> (post-implementation) are distinct phases. §16 Exhaustive Work Session is
> a separate meta-process (not a sub-step of the debate loop).
> §14 = validates DESIGN before implementation.
> §8  = validates IMPLEMENTATION after it is built.
> §16 = iterative improvement with ROI gate; does not produce a §9 Proposal.

**NEXT CYCLE carries forward:**
- Active User Directives (auto via hub.py §17-2)
- Accepted Risks from prior cycles (coordinator re-injects into §0)
- Unresolved DEFER items from handoff.md PENDING_ISSUES

**SEE/VERIFY steps:**
1. All §7 outputs written and verified by read-back
2. At least one peer reviews the diff/change
3. §3 acceptance criteria (2-7) evaluated
4. No unexpected side effects detected

**Closure Manifest:**
Before `VERIFY_PASS`, the coordinator MUST produce a Closure Manifest that maps every non-archived ledger item to a terminal sink. `VERIFY_PASS` is prohibited until this manifest is complete and read-back verified.

Required manifest schema:
```
[CLOSURE_MANIFEST: {proposal-id}]
Open Issues:
  - {ISSUE-id}: RESOLVED | DEFERRED | PROMOTED
    Sink: DEBATE_LOG.md | .ai/feedback.jsonl | handoff.md PENDING_ISSUES | SUB_ISSUE:{id}
    Evidence: {path or log reference}

Assumptions:
  - {ASSUMPTION-id}: CONFIRMED | INVALIDATED | ACCEPTED_RISK
    Sink: DEBATE_LOG.md | Accepted Risks Ledger | .ai/feedback.jsonl
    Evidence: {path or log reference}

Accepted Risks:
  - {RISK-id}: ACCEPTED
    Sink: DEBATE_LOG.md
    Mitigation Sink: .ai/feedback.jsonl | handoff.md PENDING_ISSUES | NONE
    Evidence: {path or log reference}

Ambiguities:
  - {AMBIGUITY-id}: RESOLVED | DISCARDED | PROMOTED
    Sink: DEBATE_LOG.md | .ai/feedback.jsonl | Open Issues Ledger | SUB_ISSUE:{id}
    Evidence: {path or log reference}
```

Closure rules:
- No `OPEN` Open Issue may remain without a sink.
- No `UNCONFIRMED` Assumption may remain before implementation; it must be confirmed, invalidated, or converted to an Accepted Risk by unanimous required voters.
- Every Accepted Risk must appear in `DEBATE_LOG.md` or be explicitly linked from the consensus record.
- Every Ambiguity must be resolved, discarded with rationale, or promoted to a tracked issue or feedback item.
- Items may not be silently dropped because they are LOW severity, historical, duplicated, or carried across proposal lineage.
- For R:10 tasks, Closure Manifest acceptance requires explicit approval from every `protocol.json.consensus.r10_voters` voter.

5. Result:
   - `VERIFY_PASS` → loop closed; debate complete
   - `VERIFY_FAIL: {reason}` → re-enter §3 at affected node; create new proposal version; invalidate prior consensus; rerun from §4

---

## §9. Canonical Proposal Artifact

**Proposal ID format:** `{topic-slug}-{YYYYMMDD}-v{n}`

```
[PROPOSAL: {proposal-id}]
Content: {FULL TEXT — no file path references}
Version-Tag: v{n}
Hash: OPTIONAL — SHA-256 if computed by external tool
Issued By: {coordinator}
Issued At: {YYYY-MM-DDTHH:MM:SSZ}
Status: DRAFT | UNDER_REVIEW | CONSENSUS | REVOKED
```

Rules:
- Content = full text always
- Immutable once issued
- Amendments → new version; prior CONSENSUS_OK invalidated
- All peer responses reference `[PROPOSAL: {proposal-id}]`

---

## §10. Ledgers

File: `P:\.ai\debate\{topic}-ledgers.md`
Compaction threshold: ~10,000 chars → archive resolved items.

```
## Open Issues
[ISSUE-{n}] Status: OPEN | RESOLVED | DEFERRED | ARCHIVED
Raised By: {peer} Round {n}
Description:
Resolution:

## Assumptions
[ASSUMPTION-{n}] Status: CONFIRMED | UNCONFIRMED | INVALIDATED | ARCHIVED
Statement:
Source:
Confirmed By:

## Accepted Risks
[RISK-{n}]
Description:
Accepted By: (ALL active peers — unanimous)
Mitigation:

## Ambiguity Register
[AMBIGUITY-{n}] Status: OPEN | RESOLVED | DISCARDED | ARCHIVED
Source:
Quote:
Competing Interpretations:
  - A:
  - B:
Owner:
Resolution:
Promoted To:
```

---

## §11. Abort Mechanism

| Code | Condition |
|:----:|:----------|
| A-1 | False positive — already solved |
| A-2 | Currently unsolvable |
| A-3 | Scope changed fundamentally |
| A-4 | User explicitly requests |

Normal procedure: `[ABORT_PROPOSE: A-{n} | reason]` → unanimous or user override → write abort record.
H-2 exception: timeout auto-abort = emergency escape valve; coordinator declares A-2 without unanimity; MUST document exception explicitly.

---

## §12. Artifact Precedence

```
Tier 1:   Constitutional (amended only via T-2 debate)
  - CLAUDE.md / protocol.json / DEBATE_PROTOCOL.md

Tier 1.5: User Directives (operational standing rules; see §17)
  - P:\_sys\ai\user-directives.md
  - Override Tier 2–6 for operational matters
  - Conflict with Tier 1: coordinator escalates (H-3 type); cannot be silently applied or ignored

Tier 2:   Consensus Decisions (extend policy within Tier 1 space)
  - DEBATE_LOG.md entries

Tier 3:   Provisional (30-day expiry; elevate to Tier 2 or discard)
  - PROVISIONAL_DECISION entries

Tier 4:   Session-Level
  - handoff.md [PROMOTED_RULES]
  - handoff.md [KEY_DECISIONS]

Tier 5:   Peer-Specific Instructions

Tier 6:   Default AI Behavior
```

Conflict: DEBATE_LOG entry extends Tier 1 → ALLOWED.
Conflict: DEBATE_LOG entry contradicts Tier 1 → BLOCKED; T-7 first, then T-2.
Conflict: User Directive contradicts Tier 1 → BLOCKED; coordinator escalates to user (H-3 type).
Conflict: User Directive vs Tier 2 → User Directive prevails for operational matters; escalate if structural.

---

## §13. Amendment Rule

Only via T-2 debate following full protocol.
Result: `P:\_sys\docs\DEBATE_PROTOCOL.md` (always current canonical).
Previous version: `P:\_sys\docs\archive\DEBATE_PROTOCOL-{YYYYMMDD}-v{n}.md`.

**13-1. Expedited Amendment (§16 Exhaustive Work Session)**

§16 Exhaustive Work Sessions may apply non-constitutional amendments without a full T-2 debate:

- **Eligible:** Tier 2–6 content — policy extensions, examples, clarifications, procedural text
- **Ineligible (constitutional):** Tier 1 core sections — those that define debate validity, consensus criteria, abort conditions, or tier precedence. These require T-2 finalization even when identified in a §16 session.
- **Handling:** Tier 1 HIGH findings from a §16 session → classify as DEFER (§16-2 constitutional constraint); file in handoff PENDING_ISSUES for T-2.
- **User oversight (H-4 equivalent):** coordinator summarizes all §16 changes in the session completion report; user may reject any change post-hoc.
- **Version bump:** each §16 session that modifies DEBATE_PROTOCOL.md increments the minor version number.

---

## §14. Exhaustive Cross-Review Phase (끝장 교차검토)

**Trigger:** Immediately after CONSENSUS_OK (§6), before §7 documentation and implementation.

**Purpose:** Adversarially validate that no structural gaps, logical errors, or missing
considerations escaped the debate. Each peer acts as an independent critic of all other
peers' reasoning and the final proposal — not just a reviewer of the output.

**Scope boundary vs §16:**
§14 is a sub-phase within a debate cycle (triggered by CONSENSUS_OK, peer-to-peer adversarial review of a proposal).
§16 is a standalone meta-process (triggered directly by user, applies standard lenses to an artifact, no §9 Proposal).
Do NOT merge these: §14 requires fresh-session independence (--session-policy fresh); §16 is coordinator-led and may use session continuity.

---

**14-1. Scope**

Each active peer (including coordinator) cross-reviews:

(a) All other peers' reasoning across ALL rounds
    — Missed concerns? Conclusions reached too quickly? Wrong positions adopted?

(b) The final §9 Canonical Proposal (full text)
    — Internal inconsistencies? Underspecified parts? Dangerous assumptions?

Coordinator is NOT exempt from submitting CROSS_REVIEW unless explicitly marked ABSENT.
Queries must be written and sent in parallel before any peer sees another's response.

---

**14-2. Peer Self-Summary (Pre-Cross-Review Input)**

Before cross-review queries are sent, each peer writes their own position summary
(NOT authored by coordinator — each peer summarizes their own reasoning):

```
[PEER_SUMMARY: {name}]
Round 1 position: (key stance)
Key concerns raised: (list or NONE)
Concerns I dropped: (and why)
Final position: (what I agreed to and why)
```

Coordinator collects all summaries and distributes them with the cross-review query.
Any peer may flag an inaccurate self-summary: `[SUMMARY_DISPUTE: peer_name | what is wrong]`
— coordinator must correct before cross-review proceeds.

---

**14-3. Cross-Review Response Format**

```
[PEER: {name}] [CROSS_REVIEW: round {n}]
MISSED_BY_{PEER_A}: (or NONE)
WRONG_BY_{PEER_A}: (or NONE)
PREMATURE_CONSENSUS_BY_{PEER_A}: (or NONE)
[repeat per peer reviewed]
MISSED_BY_ALL: (gaps NO peer raised — most critical)
VERDICT: CLEAN | GAPS_FOUND
```

CLEAN is ONLY valid when ALL of the following are true:
- All MISSED_BY, WRONG_BY, PREMATURE_CONSENSUS_BY fields = NONE
- MISSED_BY_ALL = NONE
- No open questions remain
If any field is non-NONE, VERDICT MUST be GAPS_FOUND (declaring CLEAN with listed gaps is an anti-pattern).

---

**14-4. Termination Condition**

Cross-review terminates when ALL active peers declare VERDICT: CLEAN in the SAME round.
Silence is NOT CLEAN — explicit declaration required.

---

**14-5. Finding Handling**

When GAPS_FOUND, the coordinator classifies each finding:

**Severity CRITICAL** (any of the following):
- Invalidates the debate goal frame itself (§2): the scope, problem statement, or success criteria are fundamentally wrong or undefined
- The proposal solves a different problem than stated in the goal
- A core assumption in the goal frame is false and cannot be patched by a new proposal version

CRITICAL action:
1. Invalidate current debate: `[CONSENSUS_REVOKE: {proposal-id} | reason: CRITICAL — goal frame invalid]`
2. ABORT current debate via A-3: `[ABORT: A-3 | scope changed fundamentally]`
3. File new T-2 debate with corrected goal frame
4. All prior CONSENSUS_OK, Accepted Risks, and finding dispositions from the invalidated debate are nullified
5. Cross-review rounds from the aborted debate do NOT carry over to the new debate

**Severity HIGH** (any of the following):
- Changes the proposal text, acceptance criteria, or affected artifacts
- Invalidates a confirmed assumption
- Introduces or removes a safety/security constraint
- Alters risk class (NORMAL to HIGH_RISK)
- Affects portability, compatibility, or consensus validity
- Reveals the CONSENSUS_OK was invalid: quorum was miscounted, a peer's assent was conditional or withheld, or the proposal text was interpreted inconsistently between agreeing peers

**Severity LOW** (ALL of the following must be true):
- Cannot change implementation behavior
- Cannot change user-facing risk
- Cannot alter consensus meaning
- Cannot affect acceptance criteria

**Unclassifiable findings (fail-safe default):**
If a finding fails any LOW criterion but does not explicitly match any HIGH criterion, the coordinator defaults to HIGH classification.
Any peer may challenge this default classification via SEVERITY_CHALLENGE.

**Severity Challenge:**
If any peer disagrees with the coordinator's severity classification:
`[SEVERITY_CHALLENGE: finding_id | proposed: HIGH or LOW | reason: ...]`

A peer may challenge in either direction: proposing HIGH if they believe a LOW classification is incorrect, or proposing LOW if they believe a HIGH classification is incorrect.

Resolution: all non-ABSENT active peers respond HIGH or LOW within one cross-review round.

Vote outcomes:
- All non-ABSENT active peers vote LOW: LOW applies.
- Any non-ABSENT active peer votes HIGH: HIGH applies.
- A non-ABSENT active peer fails to respond within the round: their vote defaults to HIGH.
- A non-ABSENT active peer submits a non-standard response, including ABSTAIN or NEED_MORE_INFO: their vote defaults to HIGH.

Only peers marked ABSENT per 4-4 are excluded from the vote.
Challenge does NOT automatically invalidate CONSENSUS_OK; it only triggers the vote.

**HIGH action:**
1. CONSENSUS_OK is invalidated: `[CONSENSUS_REVOKE: {proposal-id} | reason: 14 finding]`
2. Re-enter 3 at affected nodes; new proposal version issued.
3. Cross-review round counter RESETS for the new proposal lineage.
4. Old cross-review rounds are preserved in the audit log but not counted in the new limit.

**LOW action:**
All non-ABSENT active peers must unanimously accept the finding as Accepted Risk (10 entry).
An ABSENT peer's absence is not a veto; peers marked ABSENT per 4-4 are excluded from the unanimous count.

Once all non-ABSENT active peers accept:
- No new proposal version is required.
- No additional CLEAN round is required.
- Proceed to 7 after all LOW findings are dispositioned.

LOW acceptance failure to respond: A non-ABSENT active peer who fails to respond to a LOW finding Accepted Risk acceptance request within one cross-review round is treated as having refused acceptance.

LOW acceptance non-standard response: Any response to a LOW finding Accepted Risk acceptance request that is neither explicit acceptance nor explicit refusal is treated as refusal.

LOW acceptance refusal: If a peer refuses to accept a LOW finding as Accepted Risk, whether by explicit refusal, silence, or non-standard response, the basis for refusal determines the escalation path.

(a) Classification dispute: the refusing peer believes the finding is actually HIGH, not LOW.

Path (a) boundary: path (a) is only available when the refusing peer disputes the LOW severity classification. The peer must file SEVERITY_CHALLENGE within one cross-review round. If the peer claims a classification dispute but does not file SEVERITY_CHALLENGE within that round, the coordinator defaults to path (b).

For this path (a) challenge, the challenging peer is excluded from the vote pool; only other non-ABSENT active peers vote.

Path (a) vote outcomes:
- If all other non-ABSENT active peers vote LOW: challenge fails, LOW is confirmed, and the challenging peer must accept as Accepted Risk or proceed via path (b).
- If any other non-ABSENT active peer votes HIGH: HIGH applies.
- If any other non-ABSENT active peer fails to respond within one cross-review round: that peer's vote defaults to HIGH.
- If any other non-ABSENT active peer submits a non-standard response, including ABSTAIN or NEED_MORE_INFO: that peer's vote defaults to HIGH.

If no other non-ABSENT active peers are available to vote, the vote pool is empty. The challenge cannot be resolved by vote and is automatically escalated to H-2.

For an empty-pool path (a) escalation, H-2 may:
1. Classify the finding as HIGH, triggering the standard HIGH action.
2. Classify the finding as LOW, with or without narrowing scope. LOW classification also covers the case where H-2 determines the challenge was unfounded and the original LOW stands. After this, all non-ABSENT active peers, including the challenger, must accept the finding as Accepted Risk, or each refusing peer must proceed via path (b).
3. Split to SUB_ISSUE.
4. ABORT(A-2).

If H-2 narrows the finding scope under option 2, the narrowed description replaces the original ledger entry and constitutes a revised finding. All non-ABSENT active peers must accept the revised finding; prior acceptance of the un-narrowed description does not transfer.

When a previously ABSENT peer returns to active status after an empty-pool H-2 LOW resolution, they must accept any outstanding LOW findings from this resolution within one cross-review round, or the LOW acceptance refusal rules apply.

(b) Acceptance refusal: the refusing peer accepts the LOW classification but believes the risk is unacceptable.

Path (b) escalates directly to H-2. No SEVERITY_CHALLENGE is required.

For path (b), H-2 may:
1. Direct the refusing peer to accept or reconsider.
2. Narrow the finding scope.
3. Split to SUB_ISSUE.
4. ABORT(A-2).

H-2 mediation does not substitute for unanimous acceptance. If the peer ultimately accepts after H-2 direction, normal Accepted Risk handling applies. If not, the debate ends via SUB_ISSUE or ABORT.

If the refusing peer does not state a basis for refusal within one cross-review round, the coordinator defaults to path (b).

H-2 has final mediation authority for acceptance refusals. A peer who refuses acceptance after H-2 direction may not restart the SEVERITY_CHALLENGE cycle for the same finding; the debate ends via SUB_ISSUE or ABORT.

**Duplicate Findings:**
When multiple peers raise identical or substantially overlapping findings in the same cross-review round, the coordinator assigns a single ledger entry with all raising peers listed in the Raised By field. No duplicate entries are created for the same finding.

If a peer believes two findings assigned to a single entry are actually distinct and not covered by the merged description, the peer may request the coordinator to create separate entries, stating the reason. The coordinator makes the final determination on the merge.

If a peer still believes a distinct finding is not captured in the merged entry, they may report the allegedly separate finding as an additional finding in their own CROSS_REVIEW response in the same round or the next round.

**Mixed-Finding Handling:**
When a single cross-review round yields both HIGH and LOW findings:
1. HIGH findings are processed first: CONSENSUS_REVOKE plus new proposal lineage.
2. LOW findings from the same round are recorded in the ledger as Status: OPEN and re-evaluated in the first cross-review round of the new proposal lineage.
3. LOW findings are NOT automatically carried forward as Accepted Risk across lineage boundaries; they must be explicitly re-assessed in the new lineage.

**Historical LOW Findings during CONSENSUS_REVOKE:**
When a HIGH finding in a later cross-review round triggers CONSENSUS_REVOKE, previously RESOLVED_LOW findings from earlier cross-review rounds within the same lineage are reclassified as Status: OPEN and must be re-evaluated in the first cross-review round of the new lineage.

If the new proposal does not change the area covered by the Accepted Risk, peers may confirm existing acceptance with a simple explicit re-accept vote rather than full re-debate.

If the new proposal changes the relevant area, full re-evaluation is required.

If a peer refuses to re-accept, the LOW acceptance refusal rules apply.

**R:10 Voting Override:**
For R:10 governed decisions, all severity challenge votes, LOW finding Accepted Risk acceptances, re-accept votes, and closure approvals use `protocol.json.consensus.r10_voters` as the required voter set. `active_peers`, `non-ABSENT active peers`, ABSENT marking, timeout defaults, and default-to-HIGH rules apply only to non-R:10 tasks.

For R:10 tasks, a missing required voter does not default, abstain, or disappear from the voter set. The decision remains `R10_UNFINALIZED` until every required voter explicitly responds, or until the human performs an allowed override/downgrade/abort path under `protocol.json.collab_rate.r10_semantics`.

---

**14-6. Infinite Loop Prevention**

Cross-review round limit per proposal lineage: original debate rounds × 3.
If exceeded → H-2 escalation (user mediation, not automatic acceptance or abort).
H-2 may decide: continue, narrow scope to specific finding, split to SUB_ISSUE, or ABORT(A-2).

"Original debate rounds" = rounds from proposal creation to first CONSENSUS_OK for the current
proposal lineage. Resets when a new proposal version is created due to CRITICAL/HIGH finding.

---

**14-7. Ledger Entries**

Each finding goes into the Open Issues Ledger with this schema:
```
[CROSSREVIEW-{n}] Status: OPEN | RESOLVED_HIGH | RESOLVED_LOW | ARCHIVED
Found In: CROSS_REVIEW round {n}
Raised By: {peer}
Type: MISSED_BY | WRONG_BY | PREMATURE_CONSENSUS | MISSED_BY_ALL
Description:
Severity: CRITICAL | HIGH | LOW | CHALLENGED
Challenge: (if any, with resolution)
Disposition:
  HIGH: New proposal v{n}; affected §3 nodes: {list}
  LOW: Accepted Risk #{n}
Proposal After: {new-proposal-id or "unchanged"}
```

---

## §15. DEFERRED

| Item | Status | Note |
|:-----|:-------|:-----|
| Ledger compaction detailed strategy | PARTIAL — §4-5 threshold defined (~10k chars → archive) | Full strategy still deferred |
| Absent peer acknowledgment on return | PARTIAL — §14-5 covers LOW acceptance on return; general re-inclusion lifecycle still DEFERRED (T-2) | See D-1 below |
| Encoding audit / mojibake remediation | DEFERRED | — |
| Full RACI ownership | DEFERRED | — |
| Automatic validation tooling | DEFERRED | — |
| Audit trail protection | DEFERRED | — |
| Testability node in §3 MECE tree | DEFERRED | Currently implicit in 2-7 Acceptance Criteria |
| Context adequacy gate (§0→§2) | DEFERRED | Low-urgency; partially covered by 0-3 Peer Context Dump |
| [D-1] §4-4/§6: Peer re-inclusion lifecycle | DEFERRED (T-2) | General ABSENT→REINCLUDED procedure (catch-up packet, CATCHUP_ACK, PEER_REINCLUDED token) undefined. T-2 candidate text in handoff.md PENDING_ISSUES |
| [D-2] §4-4/§6: Solo coordinator prohibition | DEFERRED (T-2) | N-1 quorum implies solo is invalid but no explicit prohibition or no-quorum hold state defined. T-2 candidate text in handoff.md PENDING_ISSUES |
| [D-3] v0.10 constitutional provenance | DEFERRED (T-2 ratification) | v0.10 applied constitutional-scope changes (§12, §13-1, §14-5, §16-2) via §16 session — predates own §13-1/§16-2 constraint. Requires T-2 retroactive ratification to ensure amendment authority integrity |
| R:10 voter set not integrated into §6/§16 | DEFERRED (T-2) | R:10 vote semantics currently only in §14-5; §6 and §16 base still use operational active_peers logic |
| §8 feedback sinks as mandatory §0 inputs | DEFERRED (T-2) | §8 output types not formally listed as §0 input candidates for next cycle |

---

## §16. Exhaustive Work Session (끝장 작업)

An Exhaustive Work Session (끝장 작업/검토/개선) is a multi-iteration improvement pass on an artifact or system. Unlike a debate (consensus on a single proposal), an Exhaustive Work Session applies multiple review lenses iteratively until ROI diminishes.

Trigger: user or peer invokes "끝장 개선/검토/업데이트" on a target artifact.

---

**16-1. Standard Review Lenses**

Apply in sequence; each lens generates findings independently:

| Lens | Question |
|:-----|:---------|
| MECE | Are all dimensions covered? No overlaps? No silent gaps? |
| Closed Feedback Loop | Does success in one cycle improve the next? Is the loop sealed? |
| 5 Whys | What is the root cause of each observed problem? Can it be resolved now? |
| Alternative Perspective | Is there a fundamentally different approach worth considering? |
| Resource Efficiency | Same or better outcome with fewer tokens/calls/files/steps? |

All five lenses must be applied at least once per session. Additional lenses may be added by the user.

---

**16-2. Finding Classification**

| Class | Criterion | Action |
|:------|:----------|:-------|
| HIGH | Changes behavior, correctness, safety, or loop closure | Apply immediately — unless finding affects a Tier 1 constitutional artifact (see below) |
| LOW | Clarity, wording, style, minor completeness | Accumulate; apply in final batch |
| DEFER | Requires T-2 debate or external input; not solvable alone | Log in DEBATE_LOG.md or handoff PENDING_ISSUES |

**Constitutional constraint:** Any HIGH finding that affects a Tier 1 artifact (§12) — including core sections of DEBATE_PROTOCOL.md that define debate validity, consensus, abort, or tier precedence — MUST be reclassified as DEFER and requires a full T-2 debate to apply. A §16 session coordinator may NOT directly apply such changes unilaterally. This constraint exists because §16 sessions operate outside the T-2 quorum safeguards that constitutional content requires. (See also §13-1 Expedited Amendment for the full eligibility rule.)

---

**16-3. ROI Termination Gate**

Terminate when ALL of the following are true:
1. All standard lenses applied at least once
2. Two consecutive lens passes yield no HIGH findings
3. Remaining LOW findings are cosmetic only (no behavioral or structural impact)

Coordinator declares:
```
[EXHAUSTIVE_COMPLETE: lenses={MECE,Loop,5Whys,Alt,Resource} | iterations={n} | reason: ROI_DIMINISHED]
```

**Standing Rule (effective 2026-06-14, DIR-001):**
Unless the user explicitly requests continuation, the **active coordinator** (default: cc) autonomously declares EXHAUSTIVE_COMPLETE when the ROI gate is met. No user confirmation required for termination. If cc is not the coordinator, the active coordinator inherits this authority. Any peer may propose EXHAUSTIVE_COMPLETE; it takes effect when the active coordinator endorses it.

---

**16-4. Finding Ledger**

HIGH findings: apply immediately (subject to §16-2 constitutional constraint); no separate ledger entry required (changes are self-documenting).
LOW findings: accumulate in session notes; apply in batch at end.
DEFER findings: write one-line entry to handoff.md PENDING_ISSUES with DEBATE_LOG.md reference.
No full §10 Open Issues Ledger is required for exhaustive work sessions (ledger is for debate proposals).

**16-5. Documentation on Completion**

Simplified output — does NOT require full §7 checklist:
1. Update version header of all modified artifacts
2. Append one-line entry to DEBATE_LOG.md: topic, lenses applied, iterations, affected files
3. Any DEFER items → handoff.md PENDING_ISSUES (if session-relevant)

---

## §17. User Directives

User Directives are standing instructions issued by the user that apply to ALL peers and ALL sessions indefinitely (unless explicitly revoked).

---

**17-1. Canonical Storage**

File: `P:\_sys\ai\user-directives.md`

Format per directive:
```
### [DIR-{id}] {title}
- Effective: {YYYY-MM-DD}
- Status: ACTIVE | REVOKED:{date} | SUSPENDED:{scope}
- Rule: {one-paragraph statement}
- Reference: {doc}
```

Owner: coordinator (updates on user instruction).
Precedence: **Tier 1.5** — see §12 for full tier definition. User Directives override Tier 2–6 for operational matters; they are below Tier 1 (constitutional). Conflict with Tier 1: coordinator escalates (H-3 type); cannot be silently applied or ignored.

---

**17-2. Delivery Rule**

`hub.py` MUST prepend the content of `user-directives.md` as a `[USER DIRECTIVES]` block into every peer ask via `_build_ask_query_with_context`. This is the only reliable delivery mechanism — coordinator memory is peer-local and fails on cold-start or new coordinator.

---

**17-3. Directive Lifecycle**

| State | Meaning |
|:------|:--------|
| ACTIVE | Injected into all peer queries |
| REVOKED:{date} | No longer injected; file entry retained for audit |
| SUSPENDED:{scope} | Temporarily inactive for a named debate or session only |

Revocation: user explicitly revokes by name or ID. Coordinator marks REVOKED and updates file.
If a directive conflicts with Tier 1: coordinator escalates (H-3 type) rather than silently applying or ignoring.
If a directive conflicts with Tier 2: User Directive prevails for operational matters; escalate if structural.

---

**17-4. Adding a Directive**

Any peer or user may propose a new directive. Only the user may confirm it as ACTIVE.
Confirmed directives are written to `user-directives.md` by cc (or active coordinator).
Directive creation does NOT require a T-2 debate unless it conflicts with Tier 1 artifacts.

---

# APPENDIX A: Quick Start — How to Run a Debate

## Step 1: Propose the debate
Any peer or user:
```
[DEBATE_PROPOSE: {topic-slug} | trigger: T-x]
```
Coordinator is assigned (or volunteers).

## Step 2: Gather inputs (§0)
Coordinator creates files:
- `P:\.ai\debate\{topic}-ledgers.md` (initialize empty ledger stubs)
- Collects user brain dump + file inputs
- Gets peer context dumps (0-3)
- Scans prior debate files in `P:\.ai\debate\`
- User confirms: `INPUT_COMPLETE`

## Step 3: Frame the goal (§2)
Coordinator drafts `[GOAL_FRAME: {topic}-{YYYYMMDD}-v1]` and shows it to user (H-1).
After user confirms/revises, coordinator writes query files for all peers:
```
P:\_sys\gemini\gc-{YYYYMMDDHHMMSS}-{RAND4}.txt   ← GOAL_OK request
P:\_sys\gemini\cx-{YYYYMMDDHHMMSS}-{RAND4}.txt   ← GOAL_OK request
```
Invoke in parallel:
```
python "P:\_sys\core\hub.py" ask --to gc --query-file "{file}" 2>&1
python "P:\_sys\core\hub.py" ask --to cx --query-file "{file}" 2>&1
```
All declare `GOAL_OK:{goal-frame-id}` → goal locked.

## Step 4: Explore requirements (§3)
Coordinator assigns MECE tree nodes to peers.
Each peer submits node findings using `[NODE_DONE: ...]` format.
Coordinator updates ledgers and marks `[DONE: ...]` when checklist passes.
**When a solution shape emerges from §3 findings:**
→ Coordinator drafts §9 Canonical Proposal (full text, not a file path).

## Step 5: Debate rounds (§4)
Coordinator writes ALL peer query files FIRST, then invokes:
```
python "P:\_sys\core\hub.py" ask --to gc --query-file "{gc-file}" 2>&1
python "P:\_sys\core\hub.py" ask --to cx --query-file "{cx-file}" 2>&1
```
Each peer responds with structured template.
Coordinator synthesizes:
- Issues → Open Issues Ledger
- New assumptions → Assumptions Ledger
- Agreed risks → Accepted Risks Ledger
- All AGREE → proceed to §6

## Step 6: Consensus (§6)
All active peers declare:
```
CONSENSUS_OK:{proposal-id}
```
Coordinator verifies: all concerns RESOLVED or in Accepted Risks; proposal unchanged; quorum met.

## Step 6-B: Exhaustive Cross-Review (§14)
Each peer writes their own PEER_SUMMARY first.
Coordinator distributes summaries with cross-review queries (ALL query files written before invoking any peer).
**Invoke with `--session-policy fresh`** (required — prevents anchoring from session history):
```
python "P:\_sys\core\hub.py" ask --to {peer_id} --query-file "{file}" --session-policy fresh 2>&1
```
Peers respond with CROSS_REVIEW template.
If all CLEAN in same round → proceed to Step 7.
If GAPS_FOUND → classify severity → CRITICAL/HIGH: re-enter Step 4; LOW: unanimous Accepted Risk → proceed to Step 7 without a further CLEAN round.
Repeat until all CLEAN (LOW findings unanimously accepted as Accepted Risk are exempt from further CLEAN requirement).

## Step 7: Document (§7)
Coordinator writes:
1. `P:\.ai\debate\{topic}-full.md` (append full log)
2. `P:\_sys\docs\DEBATE_LOG.md` (append consensus entry)
3. `handoff.md [PROMOTED_RULES]` (add pointer)
4. `handoff.md PENDING_ISSUES` (add implementation tasks)
5. Read-back verify each file.
Show to user (H-4). HIGH_RISK → wait for explicit user approval before implementing.

## Step 8: Implement and verify (§8)
Implement per PENDING_ISSUES.
Run SEE/VERIFY checklist.
`VERIFY_PASS` → debate closed.
`VERIFY_FAIL` → re-enter §3, new proposal version, new consensus round.

---

# APPENDIX B: Filled Examples

---

## B-1: §0 Input Gathering

**User brain dump (raw text provided):**
```
agentapi.bat 관리 지침이 계속 사라짐
- agy.exe가 agentapi.bat을 덮어씀
- cc가 수정해도 다음 세션에 없어짐
- 포터블 경로 하드코딩 문제도 반복됨
```

**Ambiguity Register entry (§10):**
```
[AMBIGUITY-1] Status: OPEN
Source: "direct text"
Quote: "agy.exe가 agentapi.bat을 덮어씀"
Competing Interpretations:
  - A: agy.exe regenerates agentapi.bat on every run (always overwrites)
  - B: agy.exe only generates if file missing (idempotent)
Owner: cc
Resolution: (pending H-1)
Promoted To: (pending)
```

**Peer Context Dump (cc):**
```
[PEER_CONTEXT: cc]
Relevant Prior Knowledge: agentapi.bat was fixed from hardcoded P:\ to %~dp0 in session b1630177; fix was overwritten in the next session.
Known Assumptions: agy.exe has auto-generation behavior; frequency unknown.
Known Constraints: agentapi.bat must remain portable (USB/cloud); never hardcode P:\.
Open Issues Carried In: No structural mechanism prevents agy.exe from overwriting cc's changes.
```

---

## B-2: §2 Goal Frame Artifact

```
[GOAL_FRAME: agentapi-bat-persistence-20260613-v1]
General Goal:
  AI peer management decisions (file-level configurations, portability rules) must persist
  across sessions and survive auto-generation by peer tools.

Specific Goal:
  Ensure agentapi.bat always uses portable %~dp0 path even when agy.exe regenerates it,
  without requiring human or cc to manually re-fix each session.

Explicit Assumptions:
  - agy.exe regenerates agentapi.bat (frequency/trigger: pending H-1 clarification)
  - The correct fix is %~dp0-based dynamic path (confirmed from prior session)
  - agy.exe templates may be text files (unconfirmed — ASSUMPTION-2)

Non-Goals:
  - Fixing any other agy.exe behavior
  - General session context loss (separate topic)
  - Changing how non-.bat files are managed

Success Criteria:
  - agentapi.bat always contains %~dp0 path after any agy.exe invocation
  - No manual fix required across 10+ consecutive sessions
  - Solution survives USB drive letter changes (e.g., D:\ → E:\)

Affected Artifacts:
  - P:\_sys\antigravity\config\bin\agentapi.bat
  - agy.exe generation template (location TBD)
  - P:\_sys\docs\PEER_MANAGEMENT.md

Decision Authority: user (only if all consensus paths fail)
```

---

## B-3: §3 MECE Node Exploration

**Coordinator assigns nodes. Peer submits findings:**

```
[NODE_DONE: 1-1 | peer: gc | date: 20260613]
Findings:
  Three must-haves identified:
  1. agentapi.bat must always contain %~dp0-based SYS_DIR derivation
  2. Solution must survive agy.exe regeneration without any manual intervention
  3. Must work on any drive letter (portability invariant)
Evidence:
  - Session b1630177 showed: hardcoded P:\ caused failure when drive was E:\
  - agy.exe regenerated the file 3 times, each time with wrong path
Open Questions: NONE
Proposed [DONE]: YES
```

**After all peers submit, coordinator marks node:**
```
[DONE: 1-1 | peers: cc,gc,cx | date: 20260613]
```

---

## B-4: §4 Round Response Example

```
[PEER: gc] [ROUND: 1] [PROPOSAL: agentapi-bat-persistence-20260613-v1]
POSITION: Template modification is the right fix direction.
REASONING:
  Root cause: agy.exe regenerates agentapi.bat on every invocation (ASSUMPTION-1).
  Two options:
  (A) Modify agy.exe template → fix at source, always correct output
  (B) Post-generation hook → patches file after each agy.exe run
  Option A preferred: single fix point, no race condition.
  Option B: fragile, depends on hook reliability.
  However: ASSUMPTION-2 (template is a text file) is still UNCONFIRMED.
CONCERNS:
  1. If template is binary-embedded, Option A is blocked
OPEN_QUESTIONS:
  1. Is agy.exe template a modifiable text file or compiled-in?
MISSING_ELEMENTS: NONE
STATUS: NEED_MORE_INFO
```
Note: STATUS = NEED_MORE_INFO (not "AGREE pending template confirmation" — conditional STATUS is prohibited).

---

## B-5: §9 Canonical Proposal Header

```
[PROPOSAL: agentapi-bat-persistence-20260613-v2]
Content:
  Modify agy.exe template at P:\_sys\tools\agy\templates\agentapi.bat.tmpl.
  Replace line:
    SET "SYS_DIR=P:\_sys"
  With:
    if not defined SYS_DIR for %%I in ("%~dp0..\..\..\_sys") do set "SYS_DIR=%%~fI"
  This derives SYS_DIR dynamically, making the file portable.
  Full template diff:
  --- agentapi.bat.tmpl (before)
  +++ agentapi.bat.tmpl (after)
  @@ -2,2 +2,3 @@
  -SET "SYS_DIR=P:\_sys"
  +"if not defined SYS_DIR for %%I in ("%%~dp0..\..\..\_sys") do set "SYS_DIR=%%~fI""
  [... complete diff embedded here ...]

Version-Tag: v2
Hash: (OPTIONAL — omit if no external tool available)
Issued By: cc
Issued At: 2026-06-13T07:00:00Z
Status: UNDER_REVIEW
```

---

## B-6: §10 All Ledger Types

```
# agentapi-bat-persistence-ledgers.md

## Open Issues
[ISSUE-1] Status: RESOLVED
Raised By: gc Round 1
Description: agy.exe template location unknown
Resolution: Found at P:\_sys\tools\agy\templates\agentapi.bat.tmpl (text file, modifiable)

[ISSUE-2] Status: OPEN
Raised By: cx Round 1
Description: No automated test verifies agentapi.bat after agy.exe run

## Assumptions
[ASSUMPTION-1] Status: CONFIRMED
Statement: agy.exe regenerates agentapi.bat on every invocation
Source: cc (observed 3x), gc (confirmed from agy source)
Confirmed By: cc, gc

[ASSUMPTION-2] Status: CONFIRMED
Statement: agy.exe template is a modifiable text file at templates/agentapi.bat.tmpl
Source: cc (verified by file inspection)
Confirmed By: cc

## Accepted Risks
[RISK-1]
Description: Template modification may be overwritten on agy.exe upgrades
Accepted By: cc, gc, cx
Mitigation: Document in PEER_MANAGEMENT.md; add post-upgrade check

## Ambiguity Register
[AMBIGUITY-1] Status: RESOLVED
Source: "direct text"
Quote: "agy.exe가 agentapi.bat을 덮어씀"
Competing Interpretations:
  - A: regenerates on every run
  - B: only generates if missing
Owner: cc
Resolution: Interpretation A confirmed (ASSUMPTION-1)
Promoted To: ASSUMPTION-1
```

---

## B-7: §6 Consensus Declaration

```
All active peers have reviewed [PROPOSAL: agentapi-bat-persistence-20260613-v2].
All concerns resolved. All assumptions confirmed. Risk-1 accepted unanimously.

[PEER: cc] CONSENSUS_OK:agentapi-bat-persistence-20260613-v2
[PEER: gc] CONSENSUS_OK:agentapi-bat-persistence-20260613-v2
[PEER: cx] CONSENSUS_OK:agentapi-bat-persistence-20260613-v2

Active peers: cc, gc, cx (quorum 3/3 ✓)
Proposal version unchanged since first CONSENSUS_OK: confirmed ✓
```

---

## B-8: §11 Abort Example

```
[ABORT_PROPOSE: A-2]
Reason:
  ASSUMPTION-2 was found to be INVALID: agy.exe template is binary-embedded (EXE resource),
  not a modifiable text file. The proposed fix (template modification) is structurally blocked.

  Current debate cannot proceed with existing proposal.
  New information: a post-generation hook approach may be viable — requires fresh analysis.

Proposed next step: start new T-2 debate with hook-based approach as new proposal.
```

Agreement: cc [agree], gc [agree], cx [agree] → ABORT confirmed.
State saved to: `P:\.ai\debate\agentapi-bat-persistence-abort.md`

---

## B-9: §8 SEE/VERIFY Checklist (VERIFY_PASS)

```
SEE/VERIFY [agentapi-bat-persistence-20260613-v2]

1. §7 outputs:
   [x] P:\.ai\debate\agentapi-bat-persistence-full.md — appended, read-back OK
   [x] P:\_sys\docs\DEBATE_LOG.md — entry added, read-back OK
   [x] handoff.md [PROMOTED_RULES] — PR-002 added, read-back OK
   [x] handoff.md PENDING_ISSUES — 1 task added

2. Peer diff review:
   gc reviewed git diff → confirmed %~dp0 pattern at correct line in template

3. Acceptance criteria (§3-2-7):
   [x] agentapi.bat contains %~dp0 after running agy.exe (tested)
   [x] Works on E:\ drive letter (USB test passed)
   [ ] 10-session persistence — DEFERRED (long-running; scheduled check in 1 week)

4. Side effects: none detected

5. Result: VERIFY_PASS
   Note: 10-session criterion deferred — acceptable; logged in ISSUE-3 for follow-up.
```

---

## B-10: VERIFY_FAIL Recovery Path

```
Implementation complete. Running SEE/VERIFY.

SEE/VERIFY [agentapi-bat-persistence-20260613-v2]
1. §7 outputs: [x] all written
2. Peer diff review: cx found issue — template change only applies when agy.exe version >= 2.1;
   current deployed version is 2.0; fix has no effect.
3. Result: VERIFY_FAIL: template variable name changed in agy.exe 2.0 (%%~dp0 vs %~dp0)

Action:
[VERIFY_FAIL: template path derivation syntax differs in agy.exe 2.0]

→ Re-enter §3:
[REOPENED: 3-1 (system/structural constraints) | reason: agy.exe version compatibility unaccounted for | by: cx]
[REOPENED: 4-1 (environmental assumptions) | reason: agy.exe version was assumed to be 2.1+ | by: cc]

→ Update ledgers:
[ASSUMPTION-3] Status: INVALIDATED
Statement: agy.exe version is 2.1+ (%%~dp0 syntax)
Source: cc (assumed, not verified)

[ISSUE-3] Status: OPEN
Raised By: cx (SEE/VERIFY)
Description: agy.exe 2.0 uses different path syntax; v2 proposal fails on 2.0

→ Create new proposal:
[PROPOSAL: agentapi-bat-persistence-20260613-v3]
Content: [syntax-compatible fix for agy.exe 2.0 and 2.1+ ...]
Version-Tag: v3
...

→ Prior consensus invalidated. New round query files written for gc and cx.
→ Round 3 queries sent. Await responses.
```

---

## B-11: SUB_ISSUE Lifecycle

```
During Round 1:
[SUB_ISSUE: SI-1 | agy.exe upgrade policy — does upgrade restore template to default?]

File created: P:\.ai\debate\agentapi-bat-persistence-subissue-SI-1.md
Parent debate: [BLOCKED_ON: SI-1] (can't finalize §6 lifecycle node without this)

--- SUB_ISSUE debate ---
cc: checked agy.exe changelog — upgrades DO restore template to default.
gc: AGREE — this means template fix must be re-applied after every upgrade.
cx: AGREE — risk should go in Accepted Risks or we need upgrade hook too.
All: SI-1 RESOLVED — add to Accepted Risks with "upgrade-check" mitigation.
---

Merge back to parent:
- SI-1 conclusion appended to agentapi-bat-persistence-full.md
- [DONE: 6-1 (migration/lifecycle)] now includes: "Template fix must be re-applied after agy.exe upgrades"
- [RISK-2] added to Accepted Risks: agy.exe upgrades restore default template → mitigation: post-upgrade check script
- Parent BLOCKED_ON: SI-1 cleared. Debate resumes.
```

---

## B-13: §14 Exhaustive Cross-Review Example

After Round 3 CONSENSUS_OK on agentapi-bat-persistence-20260613-v2.

Coordinator asks each peer to write PEER_SUMMARY. Distributes summaries. Sends queries in parallel.

**Cross-Review Round 1:**

cc cross-reviews gc and cx:
```
[PEER: cc] [CROSS_REVIEW: round 1]
MISSED_BY_GC: NONE
WRONG_BY_GC: NONE
PREMATURE_CONSENSUS_BY_GC: NONE
MISSED_BY_CX: NONE
WRONG_BY_CX: NONE
PREMATURE_CONSENSUS_BY_CX: NONE
MISSED_BY_ALL:
  1. Neither peer verified whether agy.exe writes a checksum file alongside agentapi.bat
     that might detect the template modification and regenerate the original
VERDICT: GAPS_FOUND
```

gc cross-reviews cc and cx:
```
[PEER: gc] [CROSS_REVIEW: round 1]
MISSED_BY_CC: NONE
WRONG_BY_CC: NONE
PREMATURE_CONSENSUS_BY_CC: NONE
MISSED_BY_CX:
  1. cx did not verify whether the fix is agy.exe version-specific (2.0 vs 2.1 path syntax)
WRONG_BY_CX: NONE
PREMATURE_CONSENSUS_BY_CX: NONE
MISSED_BY_ALL: NONE
VERDICT: GAPS_FOUND
```

cx cross-reviews cc and gc:
```
[PEER: cx] [CROSS_REVIEW: round 1]
MISSED_BY_CC: NONE
WRONG_BY_CC: NONE
PREMATURE_CONSENSUS_BY_CC: NONE
MISSED_BY_GC:
  1. gc did not verify that templates/ folder is not in .gitignore
WRONG_BY_GC: NONE
PREMATURE_CONSENSUS_BY_GC: NONE
MISSED_BY_ALL: NONE
VERDICT: GAPS_FOUND
```

Coordinator severity classification:
```
[CROSSREVIEW-1] MISSED_BY_ALL: checksum file → severity: HIGH (could invalidate solution)
[CROSSREVIEW-2] MISSED_BY_CX: version-specific → severity: HIGH (affects implementation)
[CROSSREVIEW-3] MISSED_BY_GC: .gitignore → severity: LOW (does not change implementation behavior)
```

Action:
- CROSSREVIEW-1, -2: CRITICAL/HIGH → CONSENSUS_OK invalidated
  `[CONSENSUS_REVOKE: agentapi-bat-persistence-20260613-v2 | reason: §14 CROSSREVIEW-1,-2]`
  Re-enter §3 nodes (4-4 external dependencies, 3-5 compatibility). New proposal v3.
  Cross-review counter RESET for v3 lineage.
- CROSSREVIEW-3: LOW → Accepted Risk
  `[RISK-2]: templates/ in .gitignore confirmed as not applicable; accepted by: cc, gc, cx`

After new §3 exploration and new CONSENSUS_OK on v3:

**Cross-Review Round 1 (v3 lineage):**
```
[PEER: cc] [CROSS_REVIEW: round 1] — MISSED_BY_GC: NONE / MISSED_BY_CX: NONE / MISSED_BY_ALL: NONE
VERDICT: CLEAN

[PEER: gc] [CROSS_REVIEW: round 1] — all NONE
VERDICT: CLEAN

[PEER: cx] [CROSS_REVIEW: round 1] — all NONE
VERDICT: CLEAN
```
All active peers CLEAN in same round → §14 complete. Proceed to §7.

---

## B-12: Mid-Debate Goal Change

```
During Round 2, cx raises:
"The proposed fix only addresses agentapi.bat. But gc-tools.bat has the same P:\ hardcoding
issue and will need the same fix. Should we expand scope to all auto-generated bat files?"

Coordinator assessment:
- This is a scope change → requires goal re-lock (§2)
- Original goal: only agentapi.bat
- New goal would be: all auto-generated bat files

Action:
[GOAL_FRAME: agentapi-bat-persistence-20260613-v2]  ← new version
General Goal: (unchanged)
Specific Goal: Ensure ALL auto-generated bat files under _sys use portable %~dp0 path
Non-Goals: (expanded — still excludes manual bat files)
Affected Artifacts: [expanded list including gc-tools.bat, ...]

GOAL_OK re-lock required:
All active peers declare GOAL_OK:agentapi-bat-persistence-20260613-v2-goalf

Prior proposal [agentapi-bat-persistence-20260613-v1] → REVOKED (scope changed)
New proposal v2 to be drafted after §3 nodes reopened for expanded scope.
```

---

# APPENDIX C: Anti-Patterns

| # | Anti-Pattern | Why Wrong | Correct Approach |
|:-:|:-------------|:----------|:----------------|
| 1 | Saying "I agree" without `CONSENSUS_OK:{id}` | Implicit agreement prohibited (§6) | Write `CONSENSUS_OK:{proposal-id}` explicitly |
| 2 | `STATUS: AGREE (pending X)` | Conditional agreement prohibited (§6) | Use `NEED_MORE_INFO` instead |
| 3 | Moving concern to Accepted Risks without unanimous agreement | §6 — risks require unanimity | Get all active peers to explicitly agree to each risk |
| 4 | Starting implementation before `CONSENSUS_OK` + H-4 | Loop not closed | Complete §6 consensus + H-4 user review first |
| 5 | Loading full transcript in Round 3+ | Context exhaustion (§4-5) | Load only §9 Proposal + §10 Ledgers per round |
| 6 | Skipping §3 nodes without explicit N/A | Unexplored = incomplete | Mark N/A with peer consensus; never silently skip |
| 7 | Issuing §9 proposal as a file path | Defeats context bounding (§9) | Embed full proposal text directly |
| 8 | DEBATE_LOG entry contradicting CLAUDE.md | Tier 2 cannot override Tier 1 (§12) | T-7 debate first, then T-2 to amend Tier 1 |
| 9 | Treating `GOAL_OK` as proposal approval | GOAL_OK only locks the goal frame | Proposal approval is `CONSENSUS_OK:{proposal-id}` |
| 10 | Changing proposal content without new version | Prior `CONSENSUS_OK` becomes stale | Issue new version; all prior approvals invalidated |
| 11 | Leaving UNCONFIRMED assumptions before implementation | May invalidate solution | Confirm or move to Accepted Risks; UNCONFIRMED blocks H-1 |
| 12 | Marking peer ABSENT without timeout evidence | May invalidate quorum | Confirm timeout via hub.py log; notify user first |
| 13 | Skipping H-4 for HIGH_RISK changes | Unauthorized high-impact action | HIGH_RISK → always USER_REVIEW_REQUIRED |
| 14 | Deleting concern from ledger to "resolve" it | Audit trail lost | Mark `Status: RESOLVED` + add resolution text |
| 15 | Updating handoff PROMOTED_RULES without DEBATE_LOG source | No traceability | Every PROMOTED_RULE must have a DEBATE_LOG source reference |
| 16 | Using undefined status tokens (e.g., `VERIFY_PASS` without §8 definition) | Protocol drift | Only use tokens defined in the canonical protocol |
| 17 | VERDICT: CLEAN while listing non-NONE fields | CLEAN is invalid if any field non-NONE | Declare GAPS_FOUND; address findings |
| 18 | Using LOW severity to bypass an unresolved design issue | LOW requires: cannot affect implementation behavior/risk | Challenge severity; if design issue, it's HIGH |
| 19 | Coordinator writes peer position summaries | Introduces coordinator bias; can hide prior concerns | Each peer writes their own PEER_SUMMARY |
| 20 | Continuing an exhaustive work session past the ROI gate | Token waste; zero marginal value | Declare `EXHAUSTIVE_COMPLETE`; stop and document |
| 21 | Running §14 full cross-review for T-5 ABBREVIATED debates | Overkill; burns peer quota | Use single-round spot-check (1 peer) for ABBREVIATED tier |

---

# APPENDIX D: Minimal Debate Template

Copy to: `P:\.ai\debate\{topic}-round1.md`

```markdown
# Debate: {topic}
Date: {YYYY-MM-DD}
Coordinator: {peer_id}
Trigger: T-{x}
Risk Class: NORMAL | HIGH_RISK
Active Peers: cc, gc, cx  (quorum minimum: 2)

---
## §0 Input Gathering

User Input (Clear):
-

User Input (Ambiguous): → see ledgers file
Peer Context Dumps: → see ledgers file
Prior Debates Scanned: none | {list}
INPUT_COMPLETE: [ ]

---
## §2 Goal Frame

[GOAL_FRAME: {topic-slug}-{YYYYMMDD}-v1]
General Goal:
Specific Goal:
Explicit Assumptions:
Non-Goals:
Success Criteria:
Affected Artifacts:
Decision Authority:

H-1 shown to user: [ ]    GOAL_OK: [ ] cc  [ ] gc  [ ] cx

---
## §3 MECE Tree Status

(updated by coordinator after each round)

1. Functional Requirements
   1-1. Must-have [ ]  1-2. Optional [ ]  1-3. Out-of-scope [ ]  1-4. Stakeholders [ ]
2. Non-Functional
   2-1. Efficiency [ ]  2-2. Effectiveness [ ]  2-3. Flexibility [ ]
   2-4. Scalability [ ]  2-5. Maintainability [ ]
   2-6. Observability [ ]  2-7. Acceptance Criteria [ ]
3. Constraints
   3-1. System [ ]  3-2. AI capability [ ]  3-3. Token/cost [ ]
   3-4. Security [ ]  3-5. Compatibility [ ]
4. Assumptions & Dependencies
   4-1. Environmental [ ]  4-2. State/persistence [ ]
   4-3. Peer capability [ ]  4-4. External [ ]
5. Exception Handling
   5-1. Failure modes [ ]  5-2. Batch handling [ ]  5-3. Rollback [ ]
6. Lifecycle
   6-1. Migration [ ]  6-2. Versioning [ ]  6-3. Deprecation [ ]

Cross-Cutting G/S/C lens: [ ]

---
## §9 Canonical Proposal (draft after solution shape emerges from §3)

[PROPOSAL: {topic-slug}-{YYYYMMDD}-v1]
Content:
[FULL PROPOSAL TEXT — NOT A FILE PATH]

Version-Tag: v1
Issued By: {coordinator}
Issued At: {timestamp}
Status: UNDER_REVIEW

---
## Rounds

### Round 1
Query files written: [ ] gc ({filename})  [ ] cx ({filename})
gc invoked: [ ]   cx invoked: [ ]
gc response: P:\.ai\debate\{topic}-round1.md (gc section)
cx response: P:\.ai\debate\{topic}-round1.md (cx section)
Coordinator synthesis: [next round? / consensus?]

(repeat for each round)

---
## §6 Consensus

All concerns: RESOLVED or in Accepted Risks (unanimous): [ ]
Proposal unchanged: [ ]
Quorum met: [ ]

[PEER: cc] CONSENSUS_OK:
[PEER: gc] CONSENSUS_OK:
[PEER: cx] CONSENSUS_OK:

---
## §14 Exhaustive Cross-Review

Peer Self-Summaries (each peer writes their own):
[ ] cc summary: P:\.ai\debate\{topic}-round-summaries.md (cc section)
[ ] gc summary: (gc section)
[ ] cx summary: (cx section)
Summary disputes: (none | list)

Cross-review query files:
[ ] cc → reviews gc, cx: {filename}
[ ] gc → reviews cc, cx: {filename}
[ ] cx → reviews cc, gc: {filename}

Cross-review round {n}:
cc verdict: CLEAN | GAPS_FOUND
gc verdict: CLEAN | GAPS_FOUND
cx verdict: CLEAN | GAPS_FOUND
All CLEAN in same round: [ ]

If GAPS_FOUND:
[CROSSREVIEW-{n}] Severity: CRITICAL/HIGH | LOW | CHALLENGED
Challenge vote: (all peers responded HIGH/LOW | outcome: CRITICAL/HIGH | LOW | defaulted HIGH)
Disposition: [new proposal v{n+1}] | [Accepted Risk #{n}]
Cross-review counter (this lineage): {current}/{limit}

---
## H-4 User Review

Shown to user: [ ]
Risk Class: NORMAL (proceed after 60min) | HIGH_RISK (wait for explicit approval)
User approval: [ ]

---
## §7 Output Checklist

[ ] P:\.ai\debate\{topic}-full.md — appended
[ ] P:\_sys\docs\DEBATE_LOG.md — entry added
[ ] handoff.md [PROMOTED_RULES] — pointer added
[ ] handoff.md PENDING_ISSUES — tasks added
[ ] All read-back verified

---
## §8 SEE/VERIFY

After implementation:
[ ] All §7 outputs written and read-back verified
[ ] At least one peer reviewed diff/change
[ ] Acceptance criteria (§3-2-7) evaluated
[ ] No unexpected side effects
[ ] Closure Manifest completed (see below) — all ledger items dispositioned before VERIFY_PASS

Result: VERIFY_PASS | VERIFY_FAIL: {reason}
If VERIFY_FAIL: [REOPENED: {node} | reason | by: {peer}] → new proposal version → new consensus round

---
## Closure Manifest

> Complete before declaring VERIFY_PASS. Every open ledger item must have a final disposition.
> No item may remain Status: OPEN at VERIFY_PASS.

```
[CLOSURE_MANIFEST: {topic-slug}-{YYYYMMDD}]

Open Issues Ledger:
  #{id}: {description} → Status: RESOLVED | ACCEPTED_RISK | DEFERRED:{target}
  (repeat per item)
  All items dispositioned: [ ]

Assumptions Ledger:
  #{id}: {description} → Status: CONFIRMED | ACCEPTED_RISK | INVALIDATED+REOPENED
  All items dispositioned: [ ]

Accepted Risks Ledger:
  #{id}: {description} → Status: ACKNOWLEDGED (all non-ABSENT peers accepted)
  All items acknowledged: [ ]

Ambiguity Register:
  #{id}: {description} → Status: RESOLVED | CARRIED_FORWARD:{doc}
  All items dispositioned: [ ]

CLOSURE_COMPLETE: [ ]
Signed: {coordinator_id} at {timestamp}
```

---
## Ledgers

See: P:\.ai\debate\{topic}-ledgers.md
(Initialize with empty stubs for: Open Issues, Assumptions, Accepted Risks, Ambiguity Register)
```
