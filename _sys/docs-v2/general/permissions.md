# General — Minimum Permission Model
> Source: protocol-permissions.md · user-directives.md §DIR-002
> Principle: minimum non-interactive permissions required for collaborative tasks.

---

## 1. Governing Principle

Every peer subprocess gets ONLY: read project files + write within workspace (with approval) + execute within declared scope.

NEVER grant: root/SYSTEM elevation · full-danger bypass · interactive approval bypass · unrestricted shell injection from external input.

---

## 2. Per-Peer Permission Profiles

Governance equality and execution permission are separate contracts. Active peers
have equal vote weight, leadership eligibility, role eligibility, and access to
collaboration state. CLI execution flags remain adapter-specific and must satisfy
the declared capability class plus DIR-002.

| Peer | Invocation flags | Status |
|------|-----------------|--------|
| **cc** | `claude -p {query} --dangerously-skip-permissions` | ACTIVE |
| **ag** | `agy --dangerously-skip-permissions -p {query} --print-timeout 60m` | ACTIVE (gc replacement) |
| **cx** | `codex exec -s workspace-write --json --ignore-rules` | ACTIVE |
| **ca** | `claude -p {query} --dangerously-skip-permissions` | INACTIVE (never activated) |
| **gc** | `gemini --approval-mode auto_edit --skip-trust` | SUSPENDED (IneligibleTierError 2026-06-19) |

---

## 3. Minimum Rights Table

| Peer | Read | Write (workspace) | Execute | Approval Mode |
|------|:----:|:----------------:|:-------:|:-------------|
| cc | ✓ | ✓ (all tools) | ✓ | skip-permissions |
| ag | ✓ | ✓ (all tools) | ✓ | skip-permissions |
| cx | ✓ | ✓ (workspace) | ✓ | workspace-write |
| ca | ✓ | ✓ (all tools) | ✓ | skip-permissions (inactive) |
| gc | — | — | — | SUSPENDED |

---

## 4. Enforcement Paths (must be kept in sync — INV-13)

| Path | File | Function |
|------|------|---------|
| Hub P2P ask | `_sys/core/hub_peer.py` | adapter `build_cmd()` / `build_session_cmd()` |
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
   The current cc/ag DIR-002 mappings are trusted-IPC exceptions and remain
   explicit policy debt until adapter sandbox parity is empirically verified.
   See §7 — for ag, this parity was tested and **refuted** (no FS sandbox flag exists).
4. NEVER route asks to RED or gate-closed peers
5. NEVER resume peer session without verifying session fingerprint
6. NEVER hardcode credentials into peer invocation args or environment

---

## 7. DIR-002 KNOWN GAP — ag has no flag-based FS sandbox

**Empirically verified 2026-06-23:** agy `--sandbox` does **NOT** enforce workspace
filesystem confinement. Under a real PTY, ag wrote to `C:\Windows\Temp` (outside the
workspace) **with** `--sandbox` and the correct `cwd`, both with and without
`--dangerously-skip-permissions`. The `--sandbox` workspace-confinement premise is therefore
**refuted**, and `--sandbox` is intentionally NOT added to ag's invoke_args.

Consequence: ag has **no flag-based FS sandbox equivalent** to cx's `-s workspace-write`.
ag mutation safety instead relies on:

1. the **trust boundary** (ag runs as a trusted IPC peer, not on untrusted external input),
2. the **read-only review profile** for review-class tasks, and
3. the **SEC-01 git-diff guard** (post-hoc mutation review), NOT on a CLI sandbox flag.

This is an **accepted, documented gap**, pending an upstream agy mechanism that actually
enforces workspace filesystem confinement.
