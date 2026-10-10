# Personal data lifecycle guide

Supported update/repair boundary: **v3.2.6+ (layout v2)**. Older or unreadable layouts require reinstalling Engram; your data folders are not touched.

Full command reference: [cli_reference.md](cli_reference.md). Use `engram <command> --help` for command help.

## Backup

Run `engram backup` or `engram backup --out D:\Backups\engram.zip` to archive the declared durable AI settings, memory, rules, skills and sessions. Add `--include-uncovered` for discovered extras such as `.peerhub`.

Every copy recursively excludes credential filenames and secret patterns (`.env`, token, secret, credential, id_rsa, `.pem`, `.key`). Declared SQLite database items use the SQLite backup API so committed WAL data is included. Redirected sources and destinations are refused. An existing archive is replaced atomically once the new archive is ready. Copy backups off-drive for drive-failure recovery.

## Restore

Preview with `engram restore PATH`; apply with `engram restore PATH --apply`. Before writing, restore snapshots exactly the existing portable destinations it will overwrite, including extras, to `_sys/data/backups/pre_restore_*.zip`. Existing protected session/project directories are refused unless `--force` is supplied. `--force` also skips the safety snapshot.

Standard directory payloads replace portable files while preserving excluded secret files. Extras merge their portable files into their recorded locations. Source and destination containment/reparse checks run before snapshots or writes. Restore failures can leave partial changes; use the printed snapshot to recover overwritten data.

## Reset

Preview with `engram reset`; apply with `engram reset --apply`. Add `--yes` to skip confirmation. Reset refuses while a managed AI CLI is running, creates and verifies `_sys/data/backups/safety_pre_reset_*.zip`, then deletes only files covered by that archive.

Credentials, secrets, uncovered `.engram/` files and `workspace/` projects remain. Discovered dotfolders share the same recursive exclusions; empty directories may remain. Recover with `engram restore <snapshot> --apply`. Reset does not provide automatic rollback after a partial deletion failure.

## Uninstall

Use `engram uninstall --dry-run` to inspect removal. `engram uninstall --purge-data` requests permanent personal-data removal and requires the typed folder name. See the command reference for its scope.

For Python/venv recovery, relocation and environment backup management, see [env_resilience_guide.md](env_resilience_guide.md).

Backup/restore: empty directories are not preserved. Existing folder backups replace directory payloads, removing stale files. Restore previews create no files or directories. Confirmed updates maintain layout, merge declarations, retire obsolete shipped files, and clean preserved update staging; preview and --check skip this maintenance.
