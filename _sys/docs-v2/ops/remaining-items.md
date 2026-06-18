---
title: Remaining Items & Improvement Backlog
status: active
updated: 2026-06-18
---

# Remaining Items & Improvement Backlog

## 1. Technical Debt

### hub.py
- **T4 exit code consistency**: `test_ask_eperm_marks_peer_red_and_blocks_next_call` now accepts `code in (1, 4)`. Decide whether EPERM should be T1 (exit 1) or T4 (fatal exit 4) and unify.
- **`action_report_error` guard**: `_record_ask_failure` calls `action_report_error` which may trigger T4 sys.exit mid-function. Consider wrapping in try/except to allow health.json write to complete before exit.
- **`peer-recover` exit code**: Returns exit 1 even on success (line ~2410). Should return 0.
- **`update-signatures` guard**: Blocked by phase policy during 'planning' phase. Needs phase exemption for maintenance actions.

### hub_peer.py
- **`build_cmd` return type changed**: Now returns `tuple[list[str], bool]` but no changelog entry. Docs and tests were mismatched until this session. Add migration note to CHANGELOG.

### check_docs_mece.py
- **CHK-06 `_PROPOSALS_DIR` path**: Currently `_ROOT / "_archive" / "proposals" / "pending"` — this directory rarely exists in practice. Consider adding it to the test fixture or changing the path.
- **CHK-07 manifest format**: Checks for `.md` filenames in manifest. If manifest format changes, CHK-07 silently passes. Add format validation.

## 2. Test Coverage Gaps

| Area | Gap | Priority |
|:-----|:----|:--------:|
| `hub_error.py` | T4 exit + health write ordering not tested | HIGH |
| `_record_ask_failure` | T4 sys.exit timing relative to health.json write | HIGH |
| `hub_peer.py` | `use_stdin=True` path (query via stdin) not integration-tested | MEDIUM |
| `self_care.py` | lesson_graduation algorithm only unit-tested | MEDIUM |
| `check_docs_mece.py` | CHK-06 with real proposals dir | LOW |
| `hub.py` | `peer-recover` exit code correctness | LOW |

## 3. Missing Features

### Near-term (next phase)
- **`health-reset` action**: No command to reset a peer's health to GREEN. Currently requires direct JSON edit. Add `hub.py health-reset --peer gc`.
- **`update-signatures` phase bypass**: Should not be blocked by collab_rate guard since it's a maintenance action.
- **Remaining items dashboard**: `hub.py remaining-items` command that reads this file and formats it as a status report.

### Medium-term
- **token-management.md MECE update**: Model specs are outdated (cc context 200k→1M, output 4096→128k, Extended Thinking API changed). See plan file `delightful-imagining-tower.md` for full details.
- **Codex adapter stdin mode test**: VirtualAdapter and CodexAdapter use `use_stdin=True` but no integration test verifies the stdin pipe actually works end-to-end.
- **CHK-08: Test Coverage Gate**: Add check that verifies all `runtime` entries in `traceability_map.json` have at least one corresponding `tests` entry.

### Long-term
- **Linux/Mac portability**: Current design is Windows-only (subst, .bat files). Consider WSL2 bridge or cross-platform path handling.
- **Web dashboard**: Read-only status dashboard for `peer-status`, `health`, `collab_rate` via a local HTTP server.
- **Cost tracking integration**: `cost-log.jsonl` exists but no aggregation or alerting on cumulative spend.

## 4. Documentation Gaps

- `token-management.md` — model specs outdated (see `delightful-imagining-tower.md` plan)
- `hub_peer.py` migration guide — `build_cmd` return type change undocumented
- No CHANGELOG.md exists — all change history is in git log only
- `_sys/docs-v2/ops/schemas.md` — orchestration.json `adapter_class` field not documented

## 5. .gitignore Review

Items that should remain untracked (already gitignored):
- `/MemoryDump.md` — contains real credentials (MUST NOT commit)
- `_sys/data/logs/` — JSONL log files
- `_sys/tests/results/` — test outputs
- `_sys/data/temp/` — pytest temp dirs

Items to consider tracking:
- `_sys/ai/snapshots/hub_api.json` — currently untracked, generated artifact. Consider tracking to detect API drift in CI.
- `rollback_swap.bat` — currently untracked (`??`). Either track or add to .gitignore.

## 6. Process Improvements

- **Pre-commit hook**: Run `check_docs_mece.py --checks CHK-01,CHK-02` on every commit to catch violations early.
- **CI integration**: GitHub Actions workflow to run `pytest _sys/tests/unit/ -q` on every push.
- **Snapshot refresh automation**: `hub.py update-signatures` should run automatically after any hub.py change (post-commit hook).
