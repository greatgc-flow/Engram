# Ops - Hub Mutation Broker
> Status: implemented | Created: 2026-06-29 | Updated: 2026-06-30 | Purpose: authority boundary for hub-managed state mutation under managed sandboxes.
> Cross-ref: `10-invariants.md` INV-20/PRO-12/PRO-19, `general/permissions.md`, `general/lifecycle.md`, `20-architecture.md`.

---

## 1. Problem

Managed Windows sandboxes can allow ordinary file writes while denying rename/replace/delete operations used by `os.replace`. This breaks hub-managed state updates such as `.ai/leases.json` and `.ai/sessions/{room}/handoff.json` even when the target file ACL is normal.

The failure mode is not peer-specific. `cx` exposes it directly because it runs with workspace-write sandboxing. `ag` exposes adjacent risks because it has PTY/session/config-state behavior and no verified flag-based filesystem sandbox. Any peer that asks `hub.py` to mutate `.ai` state from inside the sandbox can hit the same boundary.

---

## 2. Non-Goals

- Do not replace `os.replace` with copy/write/bak fallback for hub state.
- Do not make blanket `require_escalated` the normal execution model.
- Do not add peer-specific branches to bypass the boundary.
- Do not modify `hub.py` without the required R:10 consensus gate.

---

## 3. Architecture

Hub state mutation crosses an explicit authority boundary:

```text
sandbox peer
  -> broker-submit creates a unique request under .ai/broker/pending
  -> host-side broker-drain validates schema and target whitelist
  -> guard action + lock + intent journal
  -> atomic os.replace commit
  -> done/error archive + commit/error journal
```

The sandbox peer may read state and may submit a request. The host-side drain is the component that commits `.ai` governance/session state when the active runtime cannot guarantee atomic rename/replace semantics.

---

## 4. Public Commands

- `hub broker-submit --file <relative-target> --text <json-object> --from <peer>` or `hub broker-submit --file <relative-target> --payload-file <json-file> --from <peer>`
  - Submit-only path.
  - Creates one unique JSON request file under `.ai/broker/pending` using exclusive create.
  - Does not call `os.replace`, delete, or commit the target file.
- `hub broker-drain --limit <n> [--force-tier0]`
  - Host-side commit path.
  - Processes pending request files in deterministic filename order.
  - Validates schema, operation, request id, target whitelist, and payload shape before commit.
  - Uses `_guard_action`, hub locks, intent/commit journal, and `_write_json_atomic`.
  - Moves committed requests to `.ai/broker/done` and malformed/failed requests to `.ai/broker/error` using `os.replace`.
- `hub broker-status`
  - Read-only queue count and pending filename view.

---

## 5. Whitelist

Broker targets are relative to `.ai` only. Absolute paths, drive-relative paths, `.` segments, and `..` traversal are rejected before commit.

Allowed target families:

- `state.json`
- `task_registry.json`
- `mailbox.json`
- `leases.json`
- `nodes.json`
- `sessions/<room>/handoff.json`
- `consensus/*.json`

Each target family has payload validation before commit. Unknown targets fail closed and are archived to `.ai/broker/error` during drain.

---

## 6. Guard And Authority

`broker-submit` is classified as a recovery action because it only appends a request to the broker queue. `broker-status` is read-only. `broker-drain` is classified as a mutating hub action because it commits `.ai` state.

Interactive terminal drain normally requires Tier-0 override via `--force-tier0`. A host-side broker process may run with `HUB_ORIGIN=broker`, but it still goes through `_guard_action` unless explicitly Tier-0 overridden.

---

## 7. Rejected Fallback

Copy/write/bak fallback is rejected for hub-managed state. It may make a write succeed under some sandboxes, but it weakens the atomicity contract and can leave inconsistent state after process death, concurrent mutation, or partial write. This conflicts with INV-20.

---

## 8. Implementation Status

Implemented, 2026-06-30:

- R:10 round `r-b9a0`: `SANDBOX_RENAME_DENIED` classification and private broker boundary skeleton.
- R:10 round `r-936c`: live `broker-submit`, `broker-drain`, and `broker-status` API.
- Windows `os.replace` ACCESS_DENIED (`WinError 5`) is classified as `SANDBOX_RENAME_DENIED` after the existing retry loop.
- Windows sharing violations (`WinError 32`) remain ordinary `PermissionError` after retry exhaustion.
- No copy/write/bak fallback and no blanket escalation path was introduced.

---

## 9. Operational Notes

Use direct external execution only as break-glass recovery when the broker path itself is unavailable. Keep approval scoped to the exact command and record the reason in the user report or error log.