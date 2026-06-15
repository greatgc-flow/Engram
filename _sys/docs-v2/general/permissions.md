# General — Minimum Permission Model
> Source: protocol-permissions.md · user-directives.md §DIR-002
> Principle: minimum non-interactive permissions required for collaborative tasks.

---

## 1. Governing Principle

Every peer subprocess gets ONLY: read project files + write within workspace (with approval) + execute within declared scope.

NEVER grant: root/SYSTEM elevation · full-danger bypass · interactive approval bypass · unrestricted shell injection from external input.

---

## 2. Per-Peer Permission Profiles

| Peer | Invocation flags | Forbidden |
|------|-----------------|-----------|
| **cc** | `claude --allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits` | `--dangerously-skip-permissions`, `--no-permission-mode` |
| **gc** | `gemini --approval-mode auto_edit --skip-trust` | `--approval-mode yolo`, `--approval-mode full-auto` |
| **cx** | `codex exec -s workspace-write --json --ignore-rules` | `--dangerously-bypass-approvals-and-sandbox`, `-s full-auto` |
| **ag** | `agy --allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits` (**TARGET — not yet impl**) | `--dangerously-skip-permissions` (**CURRENT GAP — see PRO-15**) |

---

## 3. Minimum Rights Table

| Peer | Read | Write (workspace) | Execute | Approval Mode |
|------|:----:|:----------------:|:-------:|:-------------|
| cc | ✓ | ✓ (acceptEdits) | ✓ | acceptEdits |
| gc | ✓ | ✓ (auto_edit) | prompt | auto_edit |
| cx | ✓ | ✓ (sandbox) | ✓ | workspace-write sandbox |
| ag | ✓ | ✓ (acceptEdits) | ✓ | acceptEdits (**TARGET**) |

---

## 4. Enforcement Paths (must be kept in sync — INV-13)

| Path | File | Function |
|------|------|---------|
| Hub P2P ask | `_sys/core/hub.py` | `_build_session_cmd()` |
| Direct console | `_sys/cli/peer_console.py` | peer-specific blocks |

Verify parity: `hub.py profile-validate` / `hub.py profile-validate --peer <id>`

---

## 5. Session Fingerprint (cx, gc — INV-14)

Hub stores a fingerprint of invocation flags per session.
On resume: if flags hash differs → retire session → fresh start.
Prevents silent compatibility failures when permission flags change.

---

## 6. MUST-NEVER List (PRO-01~05)

1. NEVER pass raw user shell text as executable/flag fragments → injection risk
2. NEVER grant root/SYSTEM/admin elevation to any peer subprocess
3. NEVER use bypass/full-danger flags (`yolo`, `dangerously-bypass-*`)
4. NEVER route asks to RED or gate-closed peers
5. NEVER resume peer session without verifying session fingerprint
6. NEVER hardcode credentials into peer invocation args or environment
