---
name: tidy-structure
description: "Clean up Portable Dev Environment folder structure, file naming, and unnecessary files using MECE principles. Use for: folder cleanup, file organization, structure cleanup, source cleanup, name cleanup, root cleanup."
---

# Tidy Structure — MECE Structure Cleanup Procedure

## When to Use
- Root folder has files/folders not matching CLAUDE.md "Final Folder Structure"
- Naming inconsistencies detected
- Temp files, zip residuals, or duplicates found
- Structure needs MECE reorganization

## Ground Truth
CLAUDE.md "Final Folder Structure" section = reference for actual structure.
Root: 6 folders + system dirs. _sys: 5 integrated subfolders.

## Cleanup Steps

1. **Current state survey**
   - List root folder contents
   - Compare with CLAUDE.md "Final Folder Structure"
   - Identify: unexpected files, naming inconsistencies, duplicates

2. **Write cleanup plan**
   `_workspace/02_tidy_plan.md`:
   ```
   # Tidy Plan — {date}
   ## Move
   | From | To | Reason |
   | file.zip | _sys/data/setup-files/ | zip residual in root |
   ## Delete (requires confirmation)
   | File | Reason |
   | old_backup.txt | unused backup |
   ## Rename
   | From | To | Reason |
   | MyFolder | my-folder | kebab-case standard |
   ```

3. **Get coordinator/user confirmation**
   - Present plan before any execution
   - Get explicit approval for deletions
   - Never delete without confirmation

4. **Execute after confirmation**
   - Move files
   - Rename (with caution on Windows case-insensitive filesystem)
   - Delete confirmed items

5. **Record completion**
   `_workspace/02_tidy_done.md`: Before -> After list

## Rename Cautions
- Windows case-insensitive: Git/ -> git/ is NOT safe without user confirmation
- Hidden folders: check for .git, .claude, etc. — never rename without checking
- Registry references: if folder name is in registry key, update registry too (via script-engineer)

## Coordination Points
- Before moving: check _workspace/state.json artifacts — never move in-progress files
- During execution: scenario-auditor should confirm no scenario paths broken
- After structure change: docs-writer updates README.md structure diagrams