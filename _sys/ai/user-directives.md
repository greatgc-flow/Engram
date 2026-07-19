# User Directives - Active Standing Rules

> Scope: all peers (`cc`, `gc`, `cx`, `ag`)
> Effective: immediately
> Expiry: none unless explicitly revoked
> Canonical path: `P:\_sys\ai\user-directives.md`
> Managed by: coordinator
> Injection: `hub.py` appends this file to every peer ask as a `[USER DIRECTIVES]` block.

## Active Directives

### DIR-001: ROI-Based Auto-Termination for Exhaustive Work Sessions

- Effective: 2026-06-14
- Status: ACTIVE
- Rule: During exhaustive improvement work sessions, the active coordinator must autonomously declare `EXHAUSTIVE_COMPLETE` when the ROI gate is met, without requiring additional user confirmation.
- ROI gate:
  1. All standard review lenses were applied.
  2. Two consecutive passes produced no HIGH findings.
  3. Remaining findings are cosmetic only.
- Reference: `DEBATE_PROTOCOL.md` section 16-3.

### DIR-002: Minimum Non-Interactive Permissions for All Peers

- Effective: 2026-06-13 | Updated: 2026-07-03
- Status: ACTIVE
- Rule: All peers run with minimum non-interactive permissions and must not block on interactive approval prompts during `hub.py ask` or console wrapper invocations.
- Implementation:
  - `cc`: `-p {query} --dangerously-skip-permissions` (least-privilege allowlist was trialed 2026-07-03 but REVERTED pre-merge — see Evidence)
  - `cc.standard|effort|deepthink`: generated profile nodes inherit the cc DIR-002 mapping; reasoning depth does not independently widen permission scope.
  - `gc`: SUSPENDED — `--approval-mode auto_edit --skip-trust` (reference only; gc is tier_suspended)
  - `cx`: `-s workspace-write` (hub reuse path uses `-c sandbox="workspace-write"`; no `--ignore-rules`)
  - `ag`: PTY mode via AgyAdapter (requires_pty=true on Windows); no --permission-mode flag
- KNOWN GAP (ag filesystem confinement): `agy --sandbox` does NOT enforce workspace filesystem confinement (empirically verified 2026-06-23: ag wrote outside workspace with --sandbox regardless of cwd/skip-permissions). ag has NO flag-based FS sandbox equivalent to cx `-s workspace-write`; mutation safety relies on trust boundary + read-only review profile + SEC-01 git-diff guard.
- Evidence:
  - `cx` no-`--ignore-rules` canary returned `OK` via real `codex.cmd exec ... -c sandbox="workspace-write"` on 2026-07-03.
  - `cc` allowlist (`--permission-mode default --allowedTools …`) was trialed and REVERTED to `--dangerously-skip-permissions` pre-merge (2026-07-03). Findings: (1) no hang — a `cc.standard` ask invoking a NON-allowlisted `Bash(echo)` completed in 12s; but (2) that non-allowlisted call still EXECUTED, proving `--permission-mode default` under `-p` does not hard-confine in print mode; and (3) both ag and cx pre-merge reviews flagged the list as under-scoped/unverified. Per DIR-004 (measured, not assumed) we do not ship a permission control that does not demonstrably enforce. cc least-privilege deferred to a follow-up with a real enforcement mechanism (OS-level or hook) + full canary. See ops/overnight-hardening-2026-07-03.md.
- References:
  - `_sys/ai/orchestration.json`
  - `_sys/docs-v2/general/permissions.md` (authoritative per-peer profiles, updated 2026-06-19)

### DIR-003: test_contracts.py Must Be Updated When hub.py Public API Changes

- Effective: 2026-06-16
- Status: ACTIVE
- Rule: When modifying the public API of `hub.py` (`_lease_cfg`, `_build_session_cmd`, `action_ask`, or any `action_*` function) — including parameter names, defaults, or return type annotations — `_sys/tests/unit/test_contracts.py` MUST be updated in the same commit.
- Why: Derived from incident where `_lease_cfg()` 2-tuple→3-tuple change silently broke 26 tests. Source: LL-008.
- Scope: Applies to all peers (cc, gc, cx). Include contract-update verification in PR checklist for any API change.
- Source: LL-008 / gc self-evolution audit 2026-06-16.

### DIR-004: Measured-Only Claims — No Guessing, No Estimation

- Effective: 2026-07-03
- Status: ACTIVE
- Ratification: proposed during overnight hardening 2026-07-03 (pending_user_approval); ratified 2026-07-03 by the user's standing order to proceed with the full consensus backlog (R:10 unanimous cc+ag+cx, W-batch Final Call).
- Rule: Any claim about CLI capability, model availability, permissions, behavior, or quota MUST carry a source tag from {cli_live | app_server | statusline | empirical_probe}. Declaration-only sources (orchestration.json, docs, --help) may be relayed only as `declared, unverified`. When no evidence exists, state `absent` or `TEST NEEDED` — never estimate. Only machine-owned fields are trusted; model/permission declaration changes require attached drift_report evidence.
- Enforcement: `check_cli_reality.py` (P0 drift blocks), diag source tags (`[decl]`/`absent` rendering), lesson LL-20260703-003 (declared-vs-actual reconciliation).
- Source: user guidance repeated across sessions ("measure before use, never guess"); H-constitution path (user ratifies the rule, peers ratify the artifact).

### DIR-005: Smartest-Model Final Arbiter — scoped peer-equality exception

- Effective: 2026-07-04
- Status: ACTIVE
- Ratification: user-ratified 2026-07-04 (Tier-0) via explicit choice "override on dissent/high-risk" after the R:10 arbiter design discussion (ag design + cx review).
- Rule: The designated arbiter (the premium/smartest model, e.g. `cc.fable`, selected via a config `arbiter_models` list, NOT the stale active_coordinator) MAY **override** cheap-peer consensus and be recorded as the canonical `FINAL_OPINION` ONLY on (a) unresolved cheap-peer dissent/tie, and (b) high-risk / irreversible decisions. On ALL other decisions the arbiter is **advisory-recorded-only** (peer-equality preserved). This is a bounded, user-ratified exception to strict peer-equality — the arbiter is invoked sparingly (rare triggers, budget 5/5h window, target ≤5% of decisions, condensed single-shot input) and premium models are structurally excluded from bulk load-balancing.
- Enforcement (pending TDD): routing-config `final_arbiter` block; structured dissent-detection + high-risk classifier + budget guard; the arbiter returns advisory text and the terminal applies it (LL-20260703-005).
- Design: `_sys/docs/history/ops/token-load-balancing-design.md` (Smartest-Model Final Arbiter section).
- Reconciles with the peer-equality protocol clause as an explicit, scoped, human-ratified carve-out.

### DIR-006: Unanimous Consensus Required at Direction/Plan Altitude, Not Per-Tool-Call

- Effective: 2026-07-19
- Status: ACTIVE
- Ratification: user-ratified 2026-07-19 ("get everyone's unanimous agreement on direction before proceeding — I always want it this way") after a 3-way consensus round (ag.deepthink + cx.deepthink + cc.fable, all AGREE) on this exact rule's scoping.
- Rule:
  1. Unanimous agreement of the active R:10 voters (ag, cx, cc) is REQUIRED before starting any new distinct task/direction, any architectural decision, any change to standing config/directives, or any destructive/irreversible action.
  2. Individual tool calls and edits inside an already-agreed plan do NOT require a fresh consensus round — re-open consensus only on a material deviation (scope growth, a different approach, touching files/systems outside the agreed surface).
  3. A fast user go-ahead (e.g. "ㄱㄱㄱ") means "run the consensus round quickly," NOT "skip it." Only an explicit override phrase ("skip consensus", "override unanimity") waives peer consensus; enthusiasm or speed alone never does. Once a plan IS finalized, "ㄱㄱㄱ" after that point authorizes proceeding with execution without re-voting each step.
  4. On non-unanimous outcome: DIR-005's arbiter resolves dissent, or escalate to the user. A peer that's unreachable/quarantined is not implicit agreement — proceed on unanimity of reachable voters (minimum 2) with the absence logged, or hold if the decision is high-risk.
  5. Codified here (not left to peer memory) specifically because an un-codified process rule is exactly the kind of thing a long-running or forked session never hears about (see the 2026-07-19 orphaned-session incident that prompted this directive).
- Source: 2026-07-19 3-way consensus round (orphan-session-diag-quota-consensus-2026-07-19 scope) on the user's standing-default request.

## Revoked Directives

None.
