# [User Guide] Engram & PeerHub Smart Lifecycle (Backup/Restore/Reset) User Manual

A practical guide from the user's perspective summarizing how to use commands for **daily operations**, **moving to a new PC**, **recovering from issues/resetting**, and **complete uninstallation**.

All complex internal defenses (disk space checks, inode cycle detection, atomic SQLite backups, fail-closed safety guards) are **handled 100% automatically in the background**, so users only need to know a few simple commands.

---

> Full command reference (English): [`cli_reference.md`](cli_reference.md). Every command also prints its own help with `engram <command> --help`.

---

## ⚡ 3-Second Quick Cheat Sheet (Frequently Used Core Commands)

| Goal | Command | What Happens? |
| :--- | :--- | :--- |
| **Safely back up current state** | `engram backup` | Automatically archives sessions, brain, and settings (uncovered items like `.peerhub` added via `--include-uncovered`) |
| **Save backup to a specific location** | `engram backup --out D:\MyBackup.zip` | Creates a single `.zip` archive at the specified path |
| **Restore from a backup file** | `engram restore D:\MyBackup.zip --apply` | Creates a pre-restore safety snapshot, then restores standard + custom extras to original locations (dry-run preview without `--apply`) |
| **Clean reset (factory restore)** | `engram reset --apply` | Creates an automatic pre-reset snapshot, then fully purges `.engram` and discovered dotfolders like `.peerhub` (dry-run preview without `--apply`) |
| **Completely uninstall Engram** | `engram uninstall --purge-data` | Unregisters Windows context menu, terminates processes, and cleans up runtime and data |

---

## 🛠️ Practical Usage Guide by Scenario

### Scenario 1: Routine Scheduled Backup or PC Migration Preparation
> **"I want to safely back up all AI conversations, brain memories, prompts, and tool configurations!"**

#### How to run:
```powershell
PS D:\PortableDev> engram backup
```

#### Terminal screen flow:
```text
Backing up personal AI-CLI data from D:\PortableDev\.engram to: D:\PortableDev\_sys\data\backups\engram_backup_20260930_173000.zip

  [OK]   claude/projects                  <- D:\PortableDev\.engram\claude\projects (2,296 files)
  [OK]   claude/CLAUDE.md                 <- D:\PortableDev\.engram\claude\CLAUDE.md (1 file)
  [OK]   claude/settings.json             <- D:\PortableDev\.engram\claude\settings.json (1 file)
  [OK]   codex/CODEX.md                   <- D:\PortableDev\.engram\codex\CODEX.md (1 file)
  [OK]   codex/config.toml                <- D:\PortableDev\.engram\codex\config.toml (1 file)
  [OK]   codex/rules                      <- D:\PortableDev\.engram\codex\rules (12 files)
  [OK]   codex/skills                     <- D:\PortableDev\.engram\codex\skills (45 files)
  [OK]   codex/memories_1.sqlite          <- D:\PortableDev\.engram\codex\memories_1.sqlite (1 file)
  [OK]   agy/AGY.md                       <- D:\PortableDev\.engram\agy\AGY.md (1 file)
  [OK]   agy/settings.json                <- D:\PortableDev\.engram\agy\settings.json (1 file)
  [OK]   agy/keybindings.json             <- D:\PortableDev\.engram\agy\keybindings.json (1 file)
  [OK]   agy/conversation_summaries.db    <- D:\PortableDev\.engram\agy\conversation_summaries.db (1 file)
  [OK]   agy/knowledge                    <- D:\PortableDev\.engram\agy\knowledge (8 files)
  [OK]   agy/skills                       <- D:\PortableDev\.engram\agy\skills (30 files)

Done. Manifest written inside D:\PortableDev\_sys\data\backups\engram_backup_20260930_173000.zip

[NOTE] Same-drive backup created. This protects against accidental local
resets/config mistakes, NOT drive failure. For disaster recovery, copy
this backup file off-drive (USB, external drive, cloud storage).
```
- By default, `engram backup` safely backs up personal AI data inside `.engram/` (uncovered items like `.peerhub` are not included by default).
- To include discovered dotfolders or project configurations like `.peerhub`:
  - `engram backup --include-uncovered`: Appends discovered dotfolders/configs (`.peerhub`, etc.) to the backup archive.

---

### Scenario 2: Restoring on a New PC or Rolling Back to an Earlier Point
> **"Bought a new laptop or encountered issues and want to restore from an earlier backup!"**

#### How to run:
```powershell
PS D:\PortableDev> engram restore D:\Backups\engram_backup_20260930_173000.zip --apply
```

#### Terminal screen flow:
```text
[Engram Restore] Inspecting backup archive: D:\Backups\engram_backup_20260930_173000.zip
Manifest Version: 2 (Created at 2026-09-30 17:30 UTC)

Archive Contents:
  - Standard: agy, claude, codex
  - Custom Extras: .peerhub (with --include-uncovered)

[Safety] Creating pre-restore snapshot of current live state...
[OK] Safety snapshot saved: _sys/data/backups/pre_restore_20260930_173500.zip

Restoring items...
  [OK] .engram/agy restored (29,620 files)
  [OK] .engram/claude restored (2,296 files)
  [OK] .engram/codex restored (810 files)
  [OK] .peerhub restored

Done! All AI personal data and custom items have been restored.
```
- A safety snapshot of the current live state is created before restoring, so accidental restore invocations never destroy existing data.
- Running without `--apply` performs a dry run to inspect the restore plan without modifying any files.
- Extra items bundled with `--include-uncovered` (`custom_extras`, e.g., `.peerhub`) are automatically restored to their original locations.

---

### Scenario 3: Corrupted Environment Requiring a Clean Reset
> **"Tool settings or sessions became corrupted and you want to start fresh with a factory clean state!"**

#### How to run:
```powershell
PS D:\PortableDev> engram reset --apply
```

#### Terminal screen flow:
```text
[Engram Reset]
Resetting will completely purge .engram/ and discovered dotfolders like .peerhub/.
(Your project source codes in workspace/ will be KEPT SAFE).

[Phase 1: Safety Snapshot]
Creating mandatory safety snapshot before deletion...
[OK] Snapshot created & verified: _sys/data/backups/safety_pre_reset_20260930_174000.zip

[Phase 2: Clean Sweep]
  [OK] Atomic rename & purged: .engram/
  [OK] Atomic rename & purged: .peerhub/

Reset complete. The system is in pristine state.
Next time you run 'engram' or an AI CLI, empty skeletons will be auto-scaffolded instantly.
```
- Even if you forgot to take a backup before resetting, do not worry: a complete pre-deletion snapshot is always saved to `safety_pre_reset_*.zip`.
- Running without `--apply` performs a dry run to preview the list of targets to be deleted without making changes.
- After a reset, running `engram` or `peerhub status` self-heals a clean empty folder structure in milliseconds.

---

### Scenario 4: Completely Uninstalling Engram
> **"Completely remove Engram from this machine and clean up the registry!"**

#### How to run:
```powershell
PS D:\PortableDev> engram uninstall --purge-data
```
- The Windows right-click context menu ("Open in Engram") is completely removed from the registry.
- Running processes are safely terminated, and `_sys`, `.engram`, and `.peerhub` are cleanly deleted from disk.

---

## 📌 Summary: One Sentence to Remember

> **"In daily use run `engram backup`, to revert run `engram restore <path> --apply`, and to clean up run `engram reset --apply`. Disk pre-flight checks and safety nets are handled automatically by the system!"**

> For Python/venv recovery, relocation (`engram relocate`), and backup registry management (`engram snapshots`), see [env_resilience_guide.md](env_resilience_guide.md).
