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

## Revoked Directives

None.
