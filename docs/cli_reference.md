# Engram command-line reference

This is the complete reference for the `engram` command (`engram.cmd` / `Engram.exe`). The same text is printed by
`engram <command> --help` and `engram help <command>`; those files (`_sys/core/help/<command>.txt`) are the single
source, and a unit test keeps the per-command blocks below identical to them. Run `engram help` for the short overview.

The command help below defines the supported verbs and flags.

## Command groups

Every command belongs to exactly one group.

| Group | Command | What it does |
|---|---|---|
| Daily use | [`engram open`](#engram-open) | Open a workspace in Engram |
| Daily use | [`engram update`](#engram-update) | Check for and apply updates |
| Daily use | [`engram doctor`](#engram-doctor) | Report environment health (read-only) |
| Daily use | [`engram menu`](#engram-menu) | Manage the Explorer right-click "Open in Engram" entry |
| Daily use | [`engram version`](#engram-version) | Print the Engram version |
| Health & repair | [`engram repair`](#engram-repair) | Detect and fix environment drift |
| Health & repair | [`engram relocate`](#engram-relocate) | Re-anchor Engram after the folder moved |
| Health & repair | [`engram tidy`](#engram-tidy) | Clean temp files, caches and old environment backups |
| Backups & state | [`engram backup`](#engram-backup) | Back up personal AI data to a zip archive |
| Backups & state | [`engram restore`](#engram-restore) | Restore personal AI data from a backup archive |
| Backups & state | [`engram snapshots`](#engram-snapshots) | List, pin and restore environment backups |
| Removal | [`engram reset`](#engram-reset) | Delete personal AI data (start over, keep the programs) |
| Removal | [`engram uninstall`](#engram-uninstall) | Safe, allowlist-based uninstaller for Engram |

Calling `engram` with no command is the same as `engram open`. Paths require
explicit `engram open PATH`; relative paths use the caller directory.
`engram <command> --help`, `-h` and `/?` all show a command's help.

## Which command do I need?

| I want to... | Run |
|---|---|
| Start working in a folder | `engram open PATH` (or just `engram`) |
| Keep Engram, the runtimes and the AI CLIs current | `engram update` (add `--yes` to skip the prompt) |
| Update only some tools | `engram update --only claude,codex,agy --yes` |
| Update only the embedded Python | `engram update --only python --yes` |
| Find out what is wrong | `engram doctor` |
| Fix a broken Python/venv, launchers or manifest | `engram repair`, then `engram repair --apply` |
| Fix things after moving or renaming the folder | `engram relocate`, then `engram relocate --apply` |
| Finish or undo an interrupted operation | `engram repair --resume` or `engram repair --rollback` |
| Reclaim disk space | `engram tidy`, then `engram tidy --apply` |
| Get rid of leftover `_sys\env\<name>_old` folders | `engram tidy --adopt-legacy --apply` (kept 14 days) or `engram tidy --purge-legacy --apply` (now) |
| See, protect or restore environment backups | `engram snapshots list`, `pin NAME`, `restore NAME` |
| Save my AI settings, memory and sessions | `engram backup` |
| Put them back (new PC, mistake) | `engram restore PATH`, then `engram restore PATH --apply` |
| Start over but keep the programs | `engram reset`, then `engram reset --apply` |
| Add or remove the right-click entry | `engram menu enable` / `engram menu disable` |
| Remove Engram | `engram uninstall --dry-run`, then `engram uninstall` |

## Safety model

- **Preview first.** `tidy`, `repair`, `relocate`, `restore`, `reset` and `snapshots restore` only print a plan until
  you pass `--apply`. `update` shows its plan and asks; `uninstall` lists what it removes and keeps, then asks.
  `backup`, `open`, `doctor`, `menu status` and `snapshots list` do not delete anything.
- **Move, never delete.** Replaced Python trees, venvs, package lists and state files are moved into the backup
  registry (`_sys/data/backups/env/<kind>/<name>`, each with a `BACKUP.json` marker) before anything is changed.
  Only `engram tidy` removes registry entries, only expired ones, never pinned or still-pending ones, and
  `tidy --purge-legacy` only ever touches `legacy-old` entries.
- **Journal and lock.** Environment changes (`repair`, `relocate`, `update --only python|venv|packages`) run under
  the environment lock and write a crash-safe journal (`_sys/data/state/env-op.journal.jsonl`). If one is
  interrupted, every command except `help`, `version`, `doctor`, `repair`, `relocate` and `snapshots` refuses with
  exit 14 until you run `engram repair --resume` or `--rollback`. `tidy` also skips backups while the lock is held
  or a journal is open.
- **Personal data reset is limited to snapshot coverage.** `reset` deletes only archived portable files;
  credentials, secrets, uncovered `.engram/` files and workspace projects remain.
  `uninstall --purge-data` requires the folder name typed, even with `--yes`.

### Shared flags

| Flag | Meaning everywhere it exists | Where it differs |
|---|---|---|
| `--apply` | Execute the planned change. | `update` and `uninstall` have no preview mode, so they do not need it (`uninstall` accepts it as a no-op). |
| `--dry-run` | Preview only; always wins over `--apply`. A harmless no-op alias on preview-by-default commands. | Not offered on read-only or non-destructive commands (`doctor`, `menu`, `backup`, `open`). |
| `--yes`, `-y` | Skip the confirmation prompt (for scripts). | `tidy`: only the `--purge-legacy` prompt. `uninstall --purge-data` still require the typed folder name. `update --yes` is what applies the plan. |
| `--json` | Machine-readable output. | `doctor`, `repair`, `relocate` and `snapshots list` only. |
| `--only LIST` | Limit to the named parts (comma-separated). | `update`: tools/components; `repair`/`relocate`: python,venv,registry,state,ai-state,manifest,packages; `tidy`: cleanup categories. |
| `-h`, `--help`, `/?` | Show help; never changes anything. | none |

### Errors

An unknown command or option prints one `[Error] ...` line, a `Did you mean '...'?` line when something similar
exists, and a pointer to the right help (`Run 'engram <command> --help' for usage.`), then exits with code `2`.
There is never a traceback for a usage mistake. `--help` always works, even when Engram is not set up.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | success, nothing to do, or a preview was shown |
| 1 | failure (also: not set up, refused because an AI CLI is running, `doctor` needs attention) |
| 2 | usage error (unknown command, option or argument) |
| 3 | declined at a prompt (`update`, `reset`, `uninstall`, `tidy --purge-legacy`) |
| 10 | declined at the prompt (`repair`, `relocate`, `update --only python|venv|packages`) |
| 11 | precondition failed, nothing was changed (also: no terminal and no `--yes`; `tidy --purge-legacy` refused by the lock or the running interpreter) |
| 12 | verification failed and the change was rolled back |
| 13 | rollback failed |
| 14 | an unfinished operation (journal) blocks the request |

Each command lists the codes it can return in its own section below.

## Retired commands

`install`, `setup`, `status`, `register`, `unregister`, `menu-cleanup`, `cleanup`, `launch` and `start` exist only to
point at their replacement: each prints it and exits `2`.

## Command reference

### Daily use

#### engram open

```text
engram open - open a workspace in Engram

Usage: engram open [PATH] [ARGS...]
       engram                   open the default workspace

Description:
  Opens PATH as a workspace: a folder starts VS Code there; a file is run
  (.py with the managed Python, .bat/.cmd directly, anything else with its
  default app). Without PATH the default workspace is opened.
  Relative PATH uses the caller directory. ARGS are passed to script files.
  Use explicit open PATH; bare paths are not commands.
  On the very first run (no managed Python yet) it offers to set Engram up
  in this folder and to add the right-click "Open in Engram" menu entry.
  A folder literally named like a command (for example "update") is only
  opened through the explicit form: engram open update

Options:
  PATH             Folder or file to open (default: the default workspace)
  -h, --help, /?   Show this help (default: off)

Examples:
  engram
  engram open .
  engram open C:\work\project
  engram open tools\build.cmd

Exit codes:
  0   opened (or help shown); scripts return their child exit code
  1   not set up and setup was declined or failed
  2   path not found or unknown option
  14  an interrupted environment operation blocks Engram (run: engram repair)

See also:
  engram menu      right-click integration
  engram doctor    check the environment
```

#### engram update

```text
engram update - check for and apply updates

Usage: engram update [--yes] [--check | --dry-run] [--refresh]
                     [--only NAME[,NAME...]] [--allow-major-runtime-upgrade]
       engram update --only python|venv|packages [--to X.Y.Z]
                     [--all-packages] [--force] [--offline] [--yes]

Description:
  Discovers newer versions of Engram, its runtimes (Node.js, Git, VS Code,
  ...) and the AI CLIs, shows a plan, asks for confirmation, then applies it.
  Anything that cannot be checked is listed under "Not checked" and is never
  counted as up to date. Unlike tidy/repair, update is plan + prompt rather
  than dry-run + --apply: --yes is what skips the prompt.
  python, venv and packages are managed environment components: they run
  through the journaled repair engine (a backup is taken before the swap,
  dry-run by default, --yes applies) and cannot be mixed with tool names.

Options:
  --yes, -y        Apply without asking (default: ask first)
  --check          Print the plan only; exit 1 if something could not be
                   checked (default: off; for scripts and CI)
  --dry-run        Discover and show the plan, apply nothing (default: off)
  --refresh, -r    Ignore the discovery cache and re-check online (default:
                   use the cache)
  --only LIST      Update only these components, comma- or space-separated;
                   aliases cc, cx, ag work (default: everything)
  --allow-major-runtime-upgrade
                   Let a base runtime cross a major version, e.g. Node.js
                   22 to 24 (default: off; major jumps are shown, not applied)
  --to X.Y.Z       With --only python: target version (default: pinned one)
  --all-packages   With --only packages: upgrade every package (default:
                   only Engram's baseline set)
  --force          With --only python: reinstall even when already current
                   (default: off)
  --offline        With --only python: use only local files (default: off)
  -h, --help, /?   Show this help (default: off)

Examples:
  engram update
  engram update --yes
  engram update --check
  engram update --only claude,codex,agy --yes
  engram update --only python --yes
  engram update --only nodejs --allow-major-runtime-upgrade --yes

Exit codes:
  0   success or nothing to do
  1   a component failed, or --check found something unchecked
  2   usage error (unknown option or component)
  3   declined at the prompt
  10-14  python/venv/packages only: same codes as 'engram repair'

See also:
  engram doctor    what is installed and healthy
  engram snapshots   the backups an update leaves behind
  engram tidy      remove old backups once you are happy
```

#### engram doctor

```text
engram doctor - report environment health (read-only)

Usage: engram doctor [--json]

Description:
  Checks Python, the venv, managed tools, root-path hygiene (characters such
  as & % ^ ! in the folder path), context-menu registration, the environment
  manifest, a moved root, stale registry entries, the environment lock and any
  interrupted operation journal. Also checks declarative limitation warnings
  (special characters, code page, cloud-sync folders, and path length). It
  never changes anything and uses no network. It also works while an
  interrupted operation blocks other commands.

Options:
  --json           Print machine-readable JSON instead of the report
                   (default: off, human-readable)
  -h, --help, /?   Show this help (default: off)

Examples:
  engram doctor
  engram doctor --json
  engram doctor --json > doctor.json

Exit codes:
  0   healthy
  1   needs attention (the report names the fix: repair, relocate, ...)
  2   unknown option

See also:
  engram repair     fix what doctor reports
  engram relocate   fix a moved folder
  engram tidy       reclaim disk space
```

#### engram menu

```text
engram menu - Engram Right-Click Context Menu Management

Usage: engram menu [status|enable|disable|clean]

Description:
  Actions accept no extra operands.
  Manages the Explorer right-click entry "Open in Engram". It writes only
  per-user registry keys (no administrator rights). With no subcommand it
  shows the status. All subcommands are safe to repeat.

Options:
  status           Show whether the entry is registered (default subcommand)
  enable           Add "Open in Engram" to the Explorer context menu
  disable          Remove the entry again
  clean            Drop stale entries left by an old or moved installation
  -h, --help, /?   Show this help (default: off)

Examples:
  engram menu
  engram menu enable
  engram menu clean       after moving or renaming the portable folder

Exit codes:
  0   ok
  1   not set up, or the registry change failed
  2   unknown subcommand
  14  an interrupted environment operation blocks Engram (run: engram repair)

See also:
  engram relocate   re-anchor the install after a move
  engram doctor     reports stale or missing menu entries
```

#### engram version

```text
engram version - print the Engram version

Usage: engram version
       engram --version | -v

Description:
  Prints the installed Engram version and runtime name. Works even when the
  environment is not set up or an operation was interrupted.

Options:
  -h, --help, /?   Show this help (default: off)

Examples:
  engram version
  engram --version
  engram -v

Exit codes:
  0   version or help shown
  2   surplus operands

See also:
  engram doctor    full environment health report
  engram update    check for a newer version
```

### Health & repair

#### engram repair

```text
engram repair - detect and fix environment drift

Usage: engram repair [--apply] [--dry-run] [--yes] [--only LIST] [--offline]
                     [--remap-ai-state] [--json]
       engram repair --resume | --rollback

Description:
  Finds a broken venv, stale launchers, a missing Python, a missing manifest
  or stale registry entries and plans the fix. It previews by default: nothing
  changes until --apply. Every change runs under the environment lock and a
  crash-safe journal, and replaced Python/venv copies are moved into the
  backup registry (see 'engram snapshots'), never deleted. If a run is
  interrupted, other commands refuse to run (exit 14) until you finish it
  with --resume or undo it with --rollback.

Options:
  --apply          Execute the plan (default: off, preview only)
  --dry-run        Preview only; wins over --apply (default: on)
  --yes, -y        Do not ask for confirmation with --apply (default: ask;
                   without a terminal --yes is required)
  --only LIST      Limit to: python,venv,registry,state,ai-state,manifest,
                   packages (comma-separated; default: everything found)
  --offline        Never download anything (default: off)
  --remap-ai-state Also rewrite folder paths inside AI CLI state after a move
                   (default: off)
  --resume         Continue an interrupted operation (default: off;
                   mutually exclusive with --rollback)
  --rollback       Undo an interrupted operation (default: off)
  --json           One final JSON plan/result in every mode (default: off)
  -h, --help, /?   Show this help (default: off)

Examples:
  engram repair
  engram repair --apply
  engram repair --apply --yes --only venv
  engram repair --json
  engram repair --resume
  engram repair --rollback

Exit codes:
  0   ok, or nothing to repair, or preview shown
  2   usage error, including invalid --only or conflicting recovery flags
  10  declined at the prompt
  11  precondition failed, or no terminal and no --yes (nothing was changed)
  12  verification failed and the change was rolled back
  13  rollback failed (run: engram repair --rollback)
  14  an unfinished operation blocks the request (use --resume/--rollback)

See also:
  engram relocate    the same engine, for a moved or renamed folder
  engram snapshots   the backups repair creates
  engram doctor      what is wrong, read-only
```

#### engram relocate

```text
engram relocate - re-anchor Engram after the folder moved

Usage: engram relocate [--from OLD_PATH] [--apply] [--dry-run] [--yes]
                       [--remap-ai-state] [--offline] [--only LIST] [--json]
       engram relocate --resume | --rollback

Description:
  After the portable folder was moved or renamed (or copied to a new PC),
  fixes everything that still points at the old location: the venv, its
  launchers, registry hints and, optionally, paths inside AI CLI state.
  It runs the same engine and plan as 'engram repair' (plus --from), so the
  safety is identical: preview by default, environment lock, crash-safe
  journal, backups moved into the registry and never deleted.

Options:
  --from OLD_PATH  The previous location, if Engram cannot detect it
                   (default: auto-detected from the manifest)
  --apply          Execute the plan (default: off, preview only)
  --dry-run        Preview only; wins over --apply (default: on)
  --yes, -y        Do not ask for confirmation with --apply (default: ask)
  --remap-ai-state Also rewrite folder paths in AI CLI state (default: off)
  --only LIST      Limit to: python,venv,registry,state,ai-state,manifest,
                   packages (default: everything found)
  --offline        Never download anything (default: off)
  --resume         Continue an interrupted operation (default: off;
                   mutually exclusive with --rollback)
  --rollback       Undo an interrupted operation (default: off)
  --json           One final JSON plan/result in every mode (default: off)
  -h, --help, /?   Show this help (default: off)

Examples:
  engram relocate
  engram relocate --apply
  engram relocate --from D:\old\Engram --apply --yes
  engram relocate --apply --remap-ai-state

Exit codes:
  0   ok, nothing to do, or preview shown
  2   usage error, including invalid --only or conflicting recovery flags
  10  declined at the prompt
  11  precondition failed, or no terminal and no --yes (nothing was changed)
  12  verification failed and the change was rolled back
  13  rollback failed (run: engram relocate --rollback)
  14  an unfinished operation blocks the request (use --resume/--rollback)

See also:
  engram repair    broken venv or Python without a move
  engram menu clean   drop stale right-click entries after a move
  engram doctor    detects a moved folder
```

#### engram tidy

```text
engram tidy - clean temp files, caches and old environment backups

Usage: engram tidy [--apply] [--dry-run] [--deep] [--only LIST]
                   [--keep N] [--max-size-gb N]
                   [--adopt-legacy] [--purge-legacy [--yes]]

Description:
  Sweeps regenerable debris. It previews by default: it prints, per category,
  what would be deleted and how big it is, and deletes nothing until --apply.
  Categories (select with --only, default: all):
    tmp                   loose files in the root tmp/ folder (over 7 days old)
    data_temp             known test/probe debris in _sys/data/temp (older
                          than 5 days)
    brain                 old Antigravity task logs (older than 14 days)
    vscode                old VS Code session logs (the newest 2 are kept)
    pytest_cache          pytest temp rotation folders (older than 5 days)
    winget_cache          WinGet download cache
    npm_cache             npm download cache
    pip_cache             pip download cache
    vscode_cache          VS Code renderer/extension caches (skipped while
                          VS Code is running)
    pycache               __pycache__ folders under _sys (not env/ or tools/)
    pytest_cache_default  _sys/tests/.pytest_cache
    launcher_logs         launcher logs except the newest 5 (only with --deep)
    backups               expired entries of the environment backup registry
                          (see 'engram snapshots'): per-kind age limit, a
                          minimum kept per kind, and a size cap
    env_op_runners        leftover Python-swap runner copies (over 3 days old)
  Never touched: workspace/, .engram/, _archive/, the managed Python itself
  (only its pip cache), data/state, runtimes.json, the tool catalog, root
  *.md files, pinned backups, backups still pending or owned by a running
  operation, registry folders without a marker, and any <name>_old folder
  unless you ask (below). While an environment operation holds the lock or an
  interrupted-operation journal exists, backups are skipped entirely.

  The _old workflow: when Python/Node/VS Code/... is replaced, the previous
  copy may remain as _sys/env/<name>_old. To get rid of it:
    1. engram tidy --adopt-legacy            preview what would be adopted
    2. engram tidy --adopt-legacy --apply    move them into the registry as
                                             'legacy-old' (kept 14 days, then
                                             removed by a normal tidy)
    or in one step, with no 14-day wait:
    3. engram tidy --purge-legacy            preview: lists every item, size
    4. engram tidy --purge-legacy --apply    adopt and delete them all now
  --purge-legacy never deletes pinned entries or any other backup kind,
  refuses while an operation journal is open or the environment lock is
  held, holds the lock while deleting, and refuses if the running Python
  interpreter lives inside what it would delete. Pin what you want to keep:
  engram snapshots pin NAME.

Options:
  --apply          Actually delete (default: off, preview only)
  --dry-run        Preview only; wins over --apply (default: on)
  --deep           Also clean old launcher logs and adopt <name>_old folders,
                   as --adopt-legacy does (default: off)
  --only LIST      Comma-separated categories from the list above (default:
                   all; launcher_logs only does something with --deep)
  --keep N         backups: keep at least N newest committed per kind; can
                   only raise the built-in minimum (default: built-in)
  --max-size-gb N  backups: size cap in GiB (default: the smaller of 2 GiB
                   and 10 percent of free space)
  --adopt-legacy   backups: move valid _sys/env/<name>_old folders into the
                   registry as 'legacy-old' (default: off, they stay put)
  --purge-legacy   Adopt AND delete every 'legacy-old' backup at once, no
                   14-day wait (default: off). Needs the 'backups' category.
                   With --apply it asks first.
  --yes, -y        Skip the --purge-legacy confirmation prompt (default: ask;
                   a closed stdin counts as "no")
  -h, --help, /?   Show this help (default: off)

Examples:
  engram tidy
  engram tidy --apply
  engram tidy --apply --only pycache,pip_cache
  engram tidy --adopt-legacy --apply
  engram tidy --purge-legacy
  engram tidy --purge-legacy --apply --yes

Exit codes:
  0   done, or preview shown
  2   usage error (unknown option or category)
  3   --purge-legacy declined at the prompt
  11  --purge-legacy refused: environment lock held, or the running Python
      lives inside a deletion target
  14  --purge-legacy refused: an unfinished operation journal exists
      (run: engram repair --resume or --rollback)

See also:
  engram snapshots   list and pin environment backups
  engram repair      finish or undo an interrupted operation
  engram doctor      shows lock and journal state
```

### Backups & state

#### engram backup

```text
engram backup - back up personal AI data to a zip archive

Usage: engram backup [--out PATH] [--include-uncovered]

Description:
  Packs the durable part of .engram/ (memory, settings, rules, skills,
  session transcripts; never credentials) into one .zip, and records what
  it skipped. It only reads your data, so it needs no preview and no
  confirmation; a managed AI CLI that is running only produces a warning.
  Credentials and secret filenames are excluded recursively in every copy.
  Declared SQLite databases use a consistent SQLite backup, including WAL.
  Existing archives are replaced atomically after the new archive is ready.
  This is not the environment backup registry: for replaced Python/venv
  copies see 'engram snapshots'.

Options:
  --out PATH           Where to write the archive (default:
                       _sys/data/backups/engram_backup_<timestamp>.zip);
                       a trailing \ or / means "a folder, use the default name"
  --include-uncovered  Also package discovered extra dotfolders and project
                       configs such as .peerhub (default: off)
  -h, --help, /?       Show this help (default: off)

Examples:
  engram backup
  engram backup --out D:\backups\engram.zip
  engram backup --out D:\backups\
  engram backup --include-uncovered

Exit codes:
  0   archive written
  1   backup failed
  2   usage error (unknown option, missing --out value)
  14  an interrupted environment operation blocks Engram (run: engram repair)

See also:
  engram restore     put an archive back
  engram snapshots   environment backups (Python/venv), a different thing
```

#### engram restore

```text
engram restore - restore personal AI data from a backup archive

Usage: engram restore PATH [--apply] [--dry-run] [--force]

Description:
  Restores .engram/ (and any extra items the archive recorded) from a .zip
  made by 'engram backup', or from an old folder-shaped bundle. It previews
  by default and changes nothing until --apply. It refuses while a managed AI
  CLI is running, and takes an automatic safety snapshot of the current
  destinations it will overwrite, including extras, unless --force is given.
  Secret files stay excluded. Redirected source/destination paths are refused.

Options:
  PATH             Backup .zip or bundle folder to restore (required)
  --apply          Actually restore (default: off, preview only)
  --dry-run        Preview only; wins over --apply (default: on)
  --force, -f      Overwrite existing live session/project data and skip the
                   automatic pre-restore snapshot (default: off)
  -h, --help, /?   Show this help (default: off)

Examples:
  engram restore D:\backups\engram.zip
  engram restore D:\backups\engram.zip --apply
  engram restore D:\backups\engram.zip --apply --force

Exit codes:
  0   restored, or preview shown
  1   refused (an AI CLI is running) or the archive is invalid
  2   usage error (no PATH, unknown option, extra argument)
  14  an interrupted environment operation blocks Engram (run: engram repair)

See also:
  engram backup    create an archive
  engram reset     delete personal AI data
```

#### engram snapshots

```text
engram snapshots - list, pin and restore environment backups

Usage: engram snapshots list [--json]
       engram snapshots show NAME
       engram snapshots pin NAME | unpin NAME
       engram snapshots restore NAME [--apply] [--dry-run]

Description:
  Engram never deletes a replaced Python, venv or state file outright: it
  moves it into a backup registry under _sys/data/backups/env first. This
  command shows what is there. NAME is the folder name from 'list', or
  KIND/NAME when two kinds share a name. Pinned entries are never removed by
  'engram tidy'. restore previews by default, never overwrites an existing
  target, and holds the environment lock. Python and venv backups are
  not restorable yet. Keep them; repair fixes the current environment.

Options:
  list             One line per backup: kind, name, state, size, pin
  show NAME        Print one backup's marker (what, when, why, where from)
  pin NAME         Exempt a backup from tidy
  unpin NAME       Make it eligible for tidy again
  restore NAME     Move a backup's payload back to where it came from
  --json           With list: machine-readable output (default: off)
  --apply          With restore: do it (default: off, preview only)
  --dry-run        With restore: preview only; wins over --apply (default: on)
  -h, --help, /?   Show this help (default: off)

Examples:
  engram snapshots list
  engram snapshots list --json
  engram snapshots pin 20261002T010000Z-before-update
  engram snapshots restore state/20261002T010000Z-x
  engram snapshots restore state/20261002T010000Z-x --apply

Exit codes:
  0   ok, or preview shown
  2   usage error (unknown action or option)
  11  failed: no such backup, ambiguous name, target exists, lock busy, or
      restoring this backup kind is not supported yet

See also:
  engram tidy      removes expired, unpinned backups
  engram repair    repairs the current Python/venv environment
```

### Removal

#### engram reset

```text
engram reset - delete personal AI data (start over, keep the programs)

Usage: engram reset [--apply] [--dry-run] [--yes|-y]

Description:
  Deletes only portable files covered by a verified safety snapshot in
  _sys/data/backups/safety_pre_reset_*.zip. Credentials, secrets, uncovered
  .engram/ files and workspace/ stay. Discovered extra dotfolders use the
  same exclusions. It previews by default. With --apply it asks for
  confirmation, writes and verifies the snapshot, then deletes its files.
  It refuses while a managed AI CLI is running.
  Undo: engram restore <that snapshot> --apply.

Options:
  --apply          Actually delete (default: off, preview only)
  --dry-run        Preview only; wins over --apply (default: on)
  --yes, -y        Skip the [y/N] prompt (default: ask)
  -h, --help, /?   Show this help (default: off)

Examples:
  engram reset
  engram reset --apply
  engram reset --apply --yes

Exit codes:
  0   reset done, or preview shown
  1   refused (an AI CLI is running)
  2   usage error
  3   declined at a prompt
  14  an interrupted environment operation blocks Engram (run: engram repair)

See also:
  engram backup      make your own archive first
  engram restore     undo with the safety snapshot
  engram uninstall   remove the programs
```

#### engram uninstall

```text
engram uninstall - Safe, allowlist-based uninstaller for Engram

Usage: engram uninstall [--yes|-y] [--purge-data] [--dry-run] [--apply]

Description:
  Removes Engram's own files by allowlist and undoes its registry entries.
  Your data stays: .engram/ (AI settings and credentials) and workspace/ are
  kept unless --purge-data. Instead of dry-run plus --apply, uninstall lists
  what it will remove and keep, then asks "[y/N]"; --dry-run stops after the
  list. --purge-data additionally asks you to type the folder name, even with
  --yes. It refuses if a link under a target points outside the folder. The
  actual deletion is done by a helper that waits for Engram to exit.
  --apply is accepted for consistency with other verbs and changes nothing.

Options:
  --dry-run        Show what would be removed and kept, then stop (default:
                   off)
  --yes, -y        Skip the [y/N] prompt (default: ask)
  --purge-data     Also delete .engram/, workspace/ and discovered dotfolders
                   (default: off, data is kept)
  --apply          Accepted, no effect (default: off)
  -h, --help, /?   Show this help (default: off)

Examples:
  engram uninstall --dry-run
  engram uninstall
  engram uninstall --yes
  engram uninstall --purge-data

Exit codes:
  0   handed off to the removal helper, or dry-run shown
  1   refused or failed before hand-off
  2   usage error (unknown option)
  3   declined at a prompt
  14  an interrupted environment operation blocks Engram (run: engram repair)

See also:
  engram backup   save your data first
  engram reset    delete personal data but keep the programs
```

## The `_old` cleanup workflow

When Engram replaces a runtime (Python, Node.js, Git, VS Code, ...) the previous copy can remain as
`_sys\env\<name>_old`. Normal `engram tidy` never touches those folders. You have two ways to deal with them:

1. **Gradual:** `engram tidy --adopt-legacy --apply` (or `engram tidy --apply --deep`) moves each structurally valid
   `_old` folder into the backup registry as a `legacy-old` backup. A later `engram tidy --apply` deletes it after
   14 days. `engram snapshots pin NAME` keeps one for good.
2. **Immediate:** `engram tidy --purge-legacy` previews every item with its size; `engram tidy --purge-legacy --apply`
   asks `[y/N]` (or use `--yes`), then adopts and deletes all `legacy-old` backups at once. Pinned entries and all
   other backup kinds are never touched. It refuses, and says why, while an operation journal is open (exit 14),
   while the environment lock is held, or if the running Python lives inside what it would delete (exit 11).

Layout migration is explicit: `_sys\core\dispatch.bat migrate-layout` (available to
installation and maintenance callers). Public read-only and preview verbs never trigger it.
Help and version reject surplus operands with exit 2.
