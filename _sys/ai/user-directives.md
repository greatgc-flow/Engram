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

## Revoked Directives

None.
