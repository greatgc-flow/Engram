# Operational Governance Policies

This document defines the lifecycle of discarded files, data retention periods, and audit triggers for the Engram environment.

## 1. /Garbage Folder Governance

The `/Garbage/` folder serves as a staging area for discarded or superseded artifacts.

- **Manual Control**: Engram agents may move items to `/Garbage/`, but the **final deletion is a human-only action**.
- **No Auto-Deletion**: No system process or agent is permitted to automatically empty this folder.
- **Git Protocol**: The `/Garbage/` directory must be included in `.gitignore` to prevent cluttering the repository history.
- **Classification**:
  - **Included**: Superseded documentation, failed experiments, renamed files (after verification), temporary architectural drafts.
  - **Excluded**: Active configuration files (`.json`, `.md`), tracked source files, environment binaries (`_sys/env/`).

## 2. Data Retention Policy

To balance historical traceability with system performance, the following retention rules apply:

| Data Target | Retention Period | Action after Expiry |
| :--- | :--- | :--- |
| **_archive/** | Indefinite | Permanent storage of session logs and handoffs. |
| **_sys/data/temp/** | Per-Session | Cleared automatically during Tier 1 cleanup. |
| **_sys/data/logs/** | 30 Days | Retained for 30 days then archived. |
| **runtime-directives.jsonl** | 6 Hours (TTL) | Expired entries swept on session start. |
| **health.json** | Per-Session | Overwritten each session; not retained. |

## 3. Audit Trigger Policy

Formal audits (using `ops/audit-checklist.md`) are mandatory under the following conditions:

- **Script Changes**: Before any modification to `_sys/` core scripts.
- **Hub Updates**: Before updating `hub.py` or its dependencies.
- **Protocol Shifts**: Before committing changes to `PROTOCOL.md` or `protocol.json`.
- **Release/Push**: Before any major release or push to a remote repository.
- **System Failure**: Automatically triggered when `consecutive_failures > 5`.

## 4. Garbage Cleanup Procedure (Manual)

When the human decides to purge the `/Garbage/` folder:

1. **Review**: Manually inspect items in `/Garbage/` to ensure no active drafts are included.
2. **Confirm**: Use `git rm` (if previously tracked) or `rm -rf` to permanently remove items.
3. **Log**: Commit the purge with: `chore: purge Garbage/ items`

---

## 5. Proposal Lifecycle

Governance proposals live in `_sys/ai/proposals/`. This section defines their full lifecycle.

### 5.1 States

| State | File Pattern | Description |
|-------|-------------|-------------|
| PENDING | `YYYYMMDD-{slug}-{seq}.md` | Open for voting |
| ACCEPTED | moved to `_archive/proposals/accepted/` | R:5 or R:8 ACK received |
| REJECTED | moved to `_archive/proposals/rejected/` | majority NACK |
| EXPIRED | moved to `_archive/proposals/expired/` | no votes after TTL |
| STALE | moved to `_sys/docs/history/` | superseded by newer decision |

### 5.2 Lifecycle Rules

- **Creation**: Any peer may create a proposal via `hub.py proposal-add --subject "..." --from {peer}`.
- **TTL**: 7 days for R:5 proposals; 14 days for R:8/R:10 proposals. After TTL with no votes → EXPIRED.
- **Reaper**: `self_care.py --trigger session_end` checks proposal age and moves expired/stale items.
- **Voting**: `hub.py proposal-vote --id {id} --voter {peer} --vote ACK|NACK|ABSTAIN`
- **Acceptance threshold**:
  - R:5: majority ACK (≥2 of active voters)
  - R:8: supermajority ACK (all active peers)
  - R:10: unanimous ACK (Human override required for offline peer)
- **Stale detection**: if a proposal refers to a file/concept that no longer exists → auto-tag STALE at next self_care run.

### 5.3 Naming Convention

```
{YYYYMMDD}-{short-kebab-description}-{sequence:03}.md
Example: 20260618-model-registry-update-001.md
```

### 5.4 Content Template

```markdown
# Proposal: {Title}
- ID: {YYYYMMDD}-{slug}-{seq}
- From: {peer_id}
- Created: {ISO date}
- Required consensus: R:{level}
- TTL: {days} days → expires {ISO date}

## Summary
{One paragraph: what is being proposed and why}

## Impact
- Files affected: {list}
- Consensus level required: R:{N} (reason: {scope})

## Votes
| Peer | Vote | Timestamp | Note |
|------|------|-----------|------|
| {id} | ACK/NACK/ABSTAIN | {ts} | {note} |

## Outcome
{PENDING / ACCEPTED {ts} / REJECTED {ts} / EXPIRED {ts}}
```

---

## 6. Doc-as-Code Atomic Commit Policy (5-Whys Root Fix)

> Root cause: documentation drifts from code because updates are optional, not enforced.
> Systemic fix: bind doc updates to code changes as a hard constraint.

### 6.1 Coverage Map

Each core script has a required docs-v2 counterpart. If the script changes, the doc MUST change in the same commit.

| Script | Required Doc Update |
|--------|-------------------|
| `_sys/core/hub.py` | `general/protocol.md` or `general/resource-governance.md` |
| `_sys/checks/self_care.py` | `general/self-evolution.md` |
| `_sys/checks/check_versions.py` | `general/resource-governance.md §11` |
| `_sys/checks/saturation_scan.py` | `general/self-evolution.md` |
| `_sys/ai/peers.json` | `general/resource-governance.md §3` |
| `_sys/ai/protocol.json` | `general/protocol.md` |

### 6.2 Validation (check_docs_mece.py — planned, EDGE-04)

A future `_sys/checks/check_docs_mece.py` will enforce these rules automatically.

**Implementation priority order (highest ROI first):**

1. **Path existence check** (E-07): All paths referenced in docs-v2 actually exist on disk.
   `check_docs_mece.py --path-check` → exit 1 on broken paths.
2. **INV-19 Korean detection** (E-11): No Korean text in `_sys/` except exempt paths.
   `check_docs_mece.py --korean-check` → grep `[가-힣]` recursively.
3. **Coverage map enforcement** (coverage map above): If script changes but required doc doesn't → WARN.
4. **Anchor link integrity** (E-08): Internal `§N` / `#section` anchors must exist in target file.
5. **Value sync check** (E-09): Numeric constants in docs must match `protocol.json` values.
6. **Proposal TTL expiry**: Flag expired proposals not yet closed.
7. **Orphaned file check**: Files not listed in `00-MANIFEST.md` or `MOC.md`.

Until implemented: manually verify using `ops/audit-checklist.md` (sections E-07~E-11) at every release.
