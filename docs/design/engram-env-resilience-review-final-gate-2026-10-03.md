# Env resilience - final push-approval gate (2026-10-03)

Branch `feat/env-resilience-p0`, scope: P3/P4 repair engine, Python swap, runner handoff, hardening contract suite.

| Reviewer | Commit | Verdict |
|---|---|---|
| ag.pro | a4e1916 | APPROVE_PUSH (no blockers) |
| cx.pro | a4e1916 | BLOCK_PUSH: (1) standalone venv repair got no backup-path allocation, so quarantine failed and undo could not clear a `ROLLBACK_FAILED` journal; (2) `--rollback` lacked the runner handoff that `--resume` had |
| cx.pro | 9e235a5 | APPROVE_PUSH after fixes: paths now allocated for every apply; `--rollback` hands off when the spec needs the runner; regression tests in `test_runner_handoff.py` |

Verification: 1076 unit tests passed, 4 skipped, 0 failed; `check_encoding`, `check_root_hygiene`, `check_unreferenced_functions` clean; real install untouched by tests.

## Non-blocking follow-ups (not done)

1. Drive the contract suite through the real CLI and inject failures *inside* mutation and undo bodies (today: before step bodies and after completed steps, with fake interpreters).
2. `venv_repair.undo_refresh` does not remove files a failed `refresh-interpreter` step added; overwriting core binaries is normally enough.
3. `venv_repair.undo_quarantine` silently skips restore when the backup has no marker/payload; log loudly.
4. P5: register legacy producers (`*_old`, core-update backup, `.pre-merge.bak`, `Engram.exe.old`) in the backup registry.
5. Root-move hint is cleared only after `engram relocate` / `engram repair` completes.
6. Real Windows locking and non-UTF-8 code-page behaviour were verified by batch runs during development, not by an automated test.
