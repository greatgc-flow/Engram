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

- Effective: 2026-06-13 | Updated: 2026-06-19
- Status: ACTIVE
- Rule: All peers run with minimum non-interactive permissions and must not block on interactive approval prompts during `hub.py ask` or console wrapper invocations.
- Implementation:
  - `cc`: `-p {query} --dangerously-skip-permissions` (upgraded from --allowedTools/acceptEdits, 2026-06-19)
  - `cc.standard|effort|deepthink`: generated profile nodes inherit the cc DIR-002 mapping; reasoning depth does not independently widen permission scope.
  - `gc`: SUSPENDED — `--approval-mode auto_edit --skip-trust` (reference only; gc is tier_suspended)
  - `cx`: `-s workspace-write`
  - `ag`: PTY mode via AgyAdapter (requires_pty=true on Windows); no --permission-mode flag
- KNOWN GAP (ag filesystem confinement): `agy --sandbox` does NOT enforce workspace filesystem confinement (empirically verified 2026-06-23: ag wrote outside workspace with --sandbox regardless of cwd/skip-permissions). ag has NO flag-based FS sandbox equivalent to cx `-s workspace-write`; mutation safety relies on trust boundary + read-only review profile + SEC-01 git-diff guard.
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

## Revoked Directives

None.
