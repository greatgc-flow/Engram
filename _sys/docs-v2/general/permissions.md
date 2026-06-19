# General — Minimum Permission Model
> Source: protocol-permissions.md · user-directives.md §DIR-002
> Principle: minimum non-interactive permissions required for collaborative tasks.

---

## 1. Governing Principle

Every peer subprocess gets ONLY: read project files + write within workspace (with approval) + execute within declared scope.

NEVER grant: root/SYSTEM elevation · full-danger bypass · interactive approval bypass · unrestricted shell injection from external input.

---

## 2. Per-Peer Permission Profiles

Active peers use `--dangerously-skip-permissions` (or equivalent full-access) for trusted IPC sessions.
This is intentional: all hub.py peer invocations are controlled internal calls, not user shell input.
PRO-15 resolved 2026-06-19 — peer equality established.

| Peer | Invocation flags | Status |
|------|-----------------|--------|
| **cc** | `claude -p {query} --dangerously-skip-permissions` | ACTIVE |
| **ag** | `agy --dangerously-skip-permissions -p {query}` | ACTIVE (gc replacement) |
| **cx** | `codex exec {query} --json --ephemeral --ignore-rules -s danger-full-access` | ACTIVE |
| **ca** | `claude -p {query} --dangerously-skip-permissions` | INACTIVE (never activated) |
| **gc** | `gemini --approval-mode auto_edit --skip-trust` | SUSPENDED (IneligibleTierError 2026-06-19) |

---

## 3. Minimum Rights Table

| Peer | Read | Write (workspace) | Execute | Approval Mode |
|------|:----:|:----------------:|:-------:|:-------------|
| cc | ✓ | ✓ (all tools) | ✓ | skip-permissions |
| ag | ✓ | ✓ (all tools) | ✓ | skip-permissions |
| cx | ✓ | ✓ (danger-full-access) | ✓ | danger-full-access |
| ca | ✓ | ✓ (all tools) | ✓ | skip-permissions (inactive) |
| gc | — | — | — | SUSPENDED |

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
3. NEVER use bypass/full-danger flags for external/untrusted input (`yolo`, `dangerously-bypass-*`).
   Exception: `--dangerously-skip-permissions` is acceptable for trusted IPC peer sessions (PRO-15 resolved).
4. NEVER route asks to RED or gate-closed peers
5. NEVER resume peer session without verifying session fingerprint
6. NEVER hardcode credentials into peer invocation args or environment
