# Protocol Permissions — Minimum-Permission Model

> Single source of truth for peer invocation permission profiles.
> All peers MUST be invoked with exactly these flags; no more, no less.
> Authority: `_sys/ai/user-directives.md` §DIR-002 + this document.

---

## §1 — Governing Principle

Every peer subprocess is launched with the **minimum permission set** required for its collaborative tasks:
- Read project files
- Write within the workspace (with user-visible approval where required)
- Execute shell commands within declared scope

**NEVER grant:** root/SYSTEM elevation, full-danger bypass, interactive approval bypass, or unrestricted shell injection from external input.

---

## §2 — Per-Peer Permission Profiles

### cc (Claude Code)
```
claude --allowedTools Edit Write Read Glob Grep Bash MultiEdit \
       --permission-mode acceptEdits
```
- `acceptEdits`: auto-accepts file edits; shows diffs without per-edit prompt
- `--allowedTools`: explicit whitelist; no additional tools granted
- **NEVER**: `--dangerously-skip-permissions`, `--no-permission-mode`

### gc (Gemini CLI)
```
gemini --approval-mode auto_edit --skip-trust
```
- `auto_edit`: auto-approves file edits only; all other operations prompt
- `--skip-trust`: does not inherit host trust from parent shell
- **NEVER**: `--approval-mode yolo`, `--approval-mode full-auto`

### cx (Codex / OpenAI CLI)
```
codex exec -s workspace-write --json --ignore-rules
```
- `-s workspace-write`: workspace-scoped sandbox (read + write project files)
- `--json`: structured JSONL output for reliable parsing
- `--ignore-rules`: ignore local `.codex_rules` files to prevent injection
- **NEVER**: `--dangerously-bypass-approvals-and-sandbox`, `-s full-auto`

### ag (AntiGravity — inactive)
```
# TARGET (not yet implemented in peer_console.py):
agy --allowedTools Edit Write Read Glob Grep Bash MultiEdit \
    --permission-mode acceptEdits
```
- Status: `⚠️ inactive` — do not route asks until peer is re-enabled
- **KNOWN GAP**: `peer_console.py` currently defaults ag to `--dangerously-skip-permissions`
  because agy CLI flag names are not yet confirmed. This must be fixed before ag is re-enabled.
- Do NOT re-enable ag until `peer_console.py` ag block is updated with correct minimum flags.

---

## §3 — Enforcement Paths

Two code paths must be kept in sync:

| Path | File | Function |
|------|------|----------|
| Hub P2P ask | `_sys/core/hub.py` | `_build_session_cmd()` |
| Direct console | `_sys/cli/peer_console.py` | peer-specific blocks |

**Both paths MUST produce identical effective permission flags.**
`hub.py action profile-validate` checks parity automatically.

---

## §4 — MUST-NEVER List

These actions are ABSOLUTELY FORBIDDEN in any peer invocation:

1. **Never pass raw user shell text** as executable/flag fragments to peer invocations (injection risk)
2. **Never grant root, SYSTEM, or admin elevation** to any peer subprocess
3. **Never use bypass/full-danger flags** (`yolo`, `dangerously-bypass-*`) in hub-managed asks
4. **Never route asks to RED or gate-closed peers** hoping they will self-heal
5. **Never resume a peer session** without first verifying session fingerprint compatibility
6. **Never hardcode credentials** into peer invocation arguments or environment

---

## §5 — Session Fingerprint (cx, gc)

Hub stores a fingerprint of each peer session's invocation flags.
On resume, if the current flags hash differs from the stored fingerprint → the session is retired and a fresh one is started.

This prevents silent compatibility failures when permission flags change between sessions.

Computed by: `_session_fingerprint(health_peer, exe_name)` in `hub.py`

---

## §6 — Profile Validation

Run at any time to verify parity:
```
python _sys/core/hub.py profile-validate
python _sys/core/hub.py profile-validate --peer gc
```

Validation checks:
- Flags present in console path match hub path
- No forbidden flags present in any profile
- All enabled peers have a profile entry

---

## §7 — Canonical Minimum Rights Table

| Peer | Read | Write (workspace) | Execute | Approval Mode |
|------|------|-------------------|---------|---------------|
| cc   | ✓    | ✓ (acceptEdits)   | ✓       | acceptEdits   |
| gc   | ✓    | ✓ (auto_edit)     | ✗ auto  | auto_edit     |
| cx   | ✓    | ✓ (workspace-write) | ✓     | sandbox       |
| ag   | ✓    | ✓ (acceptEdits)   | ✓       | acceptEdits   |

Legend: ✓ = granted, ✗ auto = not automatically approved (requires user prompt)

---

*Ref: `_sys/ai/user-directives.md` §DIR-002 | `_sys/core/hub.py` `_build_session_cmd` | `_sys/cli/peer_console.py`*
