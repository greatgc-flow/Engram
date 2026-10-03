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

## Addendum: P5 + fresh-install E2E (v3.6.1)

- P5 done: `_old` dirs, `*.pre-merge.bak`, `Engram.exe.old` and core-update backups now go through the registry (`backups.create_file` added).
- Real fresh-install E2E on a Korean+space root (bootstrap, missing Python, broken venv, folder rename + relocate, update dry-run, full unit suite inside the install) found and fixed: duplicated help, stray `cannot find the drive` (`::` comments inside paren blocks), venv rebuild lacking `virtualenv`, noisy tracebacks, dry-run writing snapshots, tidy touching backup payloads, cp949 decode errors, pending quarantine backups.
- cx.pro re-gates found and we fixed: interpreter-refresh undo restored nothing, launcher regen failures ignored, tidy ignoring an active journal (fail closed), commit-before-regen ordering, unreadable payload in undo. ag.pro: APPROVE_PUSH at fe1c743 (cx.pro re-gate errored out on the peer side).
- Suite: 1122 passed, 4 skipped, 0 failed.

## Addendum: CLI freeze (v3.7.0)

- Help system: static `_sys/core/help/<verb>.txt` for all 13 verbs plus `index.txt`, printed by `engram.cmd` without Python; unified layout (Usage / Description / Options / Examples / Exit codes / See also); `engram help <verb>`; consistent unknown verb/flag errors with 'Did you mean'; `--dry-run` accepted on dry-run-by-default verbs.
- tidy: `--deep` implies `--adopt-legacy`; new `--purge-legacy` deletes `legacy-old` backups immediately (no 14-day grace), dry-run default, fail-closed on journal/lock/pin/running interpreter.
- Docs: `docs/cli_reference.md` (kept identical to the help files by a test).
- Gate: ag.pro found a batch-injection echo and Python-dependent help routing; both fixed; ag.pro APPROVE_PUSH at 714637b (cx.pro was not admitted by peerhub during this gate). Suite: 1369 passed, 4 skipped.
