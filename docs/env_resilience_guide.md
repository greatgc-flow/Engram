# Environment resilience guide: Python, venv, folder moves, backups

Engram keeps its own Python (`_sys/env/python`) and virtualenv (`_sys/env/venv`). This guide covers what happens
when they break, when the folder is moved or renamed, and how Engram keeps (and tidies) backups of what it replaces.
Design record: [`design/engram-env-resilience-design-2026-10-02.md`](design/engram-env-resilience-design-2026-10-02.md).

## Principles

- **Detect, plan, confirm, apply, verify, commit or roll back.** Every command is a dry run until you pass `--apply`.
- **Move, never delete.** Anything replaced (Python tree, venv, package list) is moved into a registered backup first.
- **One commit point.** Each operation writes a journal (`_sys/data/state/env-op/`). Until it reaches `COMMITTED`
  (or `ROLLED_BACK`), only `help`, `version`, `doctor`, `repair`, `relocate` and `snapshots` run.
- **Idempotent and resumable.** Re-running a command after a crash is safe.
- **Python swaps run from a runner copy.** The running interpreter cannot replace itself on Windows, so the engine
  copies it to `data/temp/env-op/<op>/runner`, exits with code 75, and `dispatch.bat` re-runs the same command there.
  This is automatic; the handoff path is ASCII and relative, so Korean/space-containing install roots work.

## Scenarios

| Situation | What to run |
|---|---|
| `_sys\env\python` deleted, venv kept | `engram repair`, `doctor` and `snapshots` cannot run without the managed Python (they print where to go). Run `_sys\core\bootstrap.bat` first: it keeps the venv, restores Python from the pinned, hash-verified download and re-verifies the venv. Then run `engram repair` (plan) and `engram repair --apply` if it reports drift. (An interrupted swap with a journal is different: `engram repair --resume/--rollback` runs on the alternate interpreter.) |
| venv broken or points at a missing interpreter | `engram repair --apply` (venv is quarantined as a backup, rebuilt, packages restored from the recorded list) |
| Folder moved or renamed | `engram relocate` (plan) then `engram relocate --apply`; pass `--from <old path>` if the old path cannot be detected; `--remap-ai-state` rewrites path references in AI CLI state |
| Python version change | `engram update --only python [--to X.Y.Z] [--force]` (snapshot, swap, venv refresh/rebuild, packages) |
| venv packages only | `engram update --only packages [--all-packages]` |
| Interrupted operation (journal not terminal) | `engram repair --resume` (roll forward) or `engram repair --rollback` (undo); both hand off to the runner automatically when Python is involved |
| Unsure | `engram doctor` reports drift, journal state, stale registry entries |

Useful flags: `--apply`, `--dry-run` (no-op alias of the default), `--yes`/`-y` (skip prompt), `--offline` (use cached download only), `--json`, `--only`. See [`cli_reference.md`](cli_reference.md).

Exit codes: `0` ok, `2` usage, `10` declined, `11` failed/precondition, `12` verification failed, `13` rolled back,
`14` blocked by a journal or lock, `75` handoff to runner (handled by `dispatch.bat`; not an error).

## Backups and `engram snapshots`

Every replaced item is registered under `_sys/data/backups/<kind>/<name>` with a marker file. Kinds include
`python`, `venv`, `venv-freeze` (package list), `venv-interp`, and `state`.

```
engram snapshots list [--json]
engram snapshots show <name>
engram snapshots pin <name>        # exempt from tidy
engram snapshots unpin <name>
engram snapshots restore <name> [--apply]   # dry run unless --apply; never overwrites
```

`engram tidy --apply` prunes backups by retention (newest kept, pinned and not-yet-committed ones never touched).
Python/venv backups are restored through `engram repair`, not by hand.

### Leftover `_old` folders (`engram tidy`)

Older Engram versions, and some runtime updates, leave the previous copy of a runtime next to the new one as
`_sys\env\<name>_old` (for example `python_old`, `nodejs_old`, `vscode_old`). Plain `engram tidy` never touches them.

| Goal | Command |
|---|---|
| See what would be adopted | `engram tidy --adopt-legacy` (dry run; `--deep` implies it) |
| File them as backups, delete after the normal 14 days | `engram tidy --adopt-legacy --apply` |
| Delete them all right now, no 14-day wait | `engram tidy --purge-legacy` (preview with sizes), then `engram tidy --purge-legacy --apply` (asks `[y/N]`; `--yes` skips) |
| Keep one forever | `engram snapshots pin <name>` before purging |

`--purge-legacy` adopts valid `_old` folders and then deletes **every** `legacy-old` backup. It never deletes pinned
entries or any other backup kind, takes the environment lock while it works, and refuses (printing why) while an
interrupted-operation journal exists (exit 14), while another operation holds the lock (exit 11), or when the running
Python interpreter lives inside something it would delete (exit 11). Declining the prompt exits 3.

The full command reference is [`cli_reference.md`](cli_reference.md); every command also has `engram <command> --help`.

## Known limitations

- Core-update's PowerShell helper still stages its backup under `data/temp/core-update`; the next layout migration run registers it (a later release may write straight into the registry).
- A root-move hint is only cleared once `engram relocate` / `engram repair` completes.
