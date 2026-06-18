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

- Effective: 2026-06-13
- Status: ACTIVE
- Rule: All peers run with minimum non-interactive permissions and must not block on interactive approval prompts during `hub.py ask` or console wrapper invocations.
- Implementation:
  - `cc`: `--allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits`
  - `gc`: `--approval-mode auto_edit --skip-trust`
  - `cx`: `-s workspace-write`
  - `ag`: `--allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits`
- References:
  - `_sys/ai/orchestration.json`
  - `_sys/cli/peer_console.py`
  - `_sys/docs/protocol/protocol-permissions.md` (authoritative per-peer profiles)

### DIR-003: test_contracts.py Must Be Updated When hub.py Public API Changes

- Effective: 2026-06-16
- Status: ACTIVE
- Rule: When modifying the public API of `hub.py` (`_lease_cfg`, `_build_session_cmd`, `action_ask`, or any `action_*` function) — including parameter names, defaults, or return type annotations — `_sys/tests/unit/test_contracts.py` MUST be updated in the same commit.
- Why: Derived from incident where `_lease_cfg()` 2-tuple→3-tuple change silently broke 26 tests. Source: LL-008.
- Scope: Applies to all peers (cc, gc, cx). Include contract-update verification in PR checklist for any API change.
- Source: LL-008 / gc self-evolution audit 2026-06-16.

## Revoked Directives

None.
