# Engram-Side Personal/Durable Settings Consolidation Proposal
**Date**: 2026-09-09
**Author**: Antigravity

## 1. Tool Inventory and Verdict

We investigated the tools managed by Engram in `_sys/env` and `_sys/tools` to determine which contain genuine durable/personal settings vs. stateless binaries/caches. 

| Tool | Verdict | Findings & Rationale |
|---|---|---|
| **Claude Code** | **Durable** | Contains irreplaceable workspace session memory (`projects/`), `CLAUDE.md`, and custom settings. |
| **Codex** | **Durable** | Contains SQLite memories (`memories_1.sqlite`), custom skills, and `config.toml`. |
| **Antigravity (agy)** | **Durable** | Contains conversation summaries DB, keybindings, and skills. |
| **git** | **Durable** | Found real customizations in `_sys/git-config/.gitconfig` (aliases, delta UI configs). Highly personal. |
| **VS Code** | **Durable** | Found custom user settings in `_sys/env/vscode/data/user-data/User/settings.json`. However, VS Code natively bundles `User` settings alongside heavy caches (`Cache`, `CachedData`, `Code Cache`) inside the `user-data` dir. |
| **gh CLI** | **Stateless (Currently)** | No local config found in `_sys/`. It is running stateless or leaking auth to the host `%AppData%`. Should be mapped to capture future auth. |
| **node / npm** | **Stateless** | `_sys/env/nodejs/npm-global` contains only installed CLI wrapper binaries (`claude`, `codex`, `gemini`). No `.npmrc` or user config found. Can be easily rebuilt. |
| **oh-my-posh** | **Stateless** | Binary plus default themes zip (`_sys/tools/oh-my-posh/themes`). No `.omp.json` personal config discovered. |
| **bat, ripgrep, fzf** | **Stateless** | Pure binaries without customized config files in the environment. |

## 2. Global Tier: `.engram/` Folder Layout

The `.engram/` directory will sit at the portable root and hold ONLY durable configuration. Caches and logs are strictly redirected to `%TEMP%` (`_sys/data/temp`) or left in `_sys`. 

```text
.engram/
  claude/
    settings.json
    CLAUDE.md
  codex/
    config.toml
    skills/
    rules/
    CODEX.md
  agy/
    settings.json
    keybindings.json
    AGY.md
    knowledge/
    skills/
  git/
    .gitconfig
  gh/
    config.yml
    hosts.yml
```

*(Note on VS Code: Because VS Code's `--user-data-dir` (or `VSCODE_PORTABLE`) forces heavy caches (`Cache/`, `Crashpad/`, `CachedData/`) into the same directory as `User/settings.json`, we cannot perfectly satisfy the "no caches in `.engram/`" and "env-var-based redirection only" rules simultaneously for its user data. VS Code's global settings will remain in `_sys/env/vscode/data` to keep caches out of `.engram/`, while relying on `.vscode/` (workspace-tier) for portable project settings.)*

## 3. Auto-Apply Mechanism at Launch

We will modify `_sys/core/launcher.py` to auto-set the environment variables for these tools at launch, bypassing the need for manual scripts like `ais-env.bat`.

**Target File**: `_sys/core/launcher.py`
**Changes**:
Inside `build_env(base_dir, sys_dir)` (around line 72, before/during the peer iteration), dynamically point the tools to `.engram/` instead of `_sys/<peer>/config`:

```python
    engram_dir = base_dir / ".engram"
    
    # AI CLIs
    env["CLAUDE_CONFIG_DIR"] = str(engram_dir / "claude")
    env["CODEX_HOME"]        = str(engram_dir / "codex")
    env["GEMINI_DIR"]        = str(engram_dir / "agy")
    env["AGY_CONFIG_HOME"]   = str(engram_dir / "agy")
    
    # git & gh
    env["GIT_CONFIG_GLOBAL"] = str(engram_dir / "git" / ".gitconfig")
    env["GH_CONFIG_DIR"]     = str(engram_dir / "gh")
```
We also need to update `_sys/ai/peers.json` to safely remove or bypass the hardcoded `"env_vars": { "CLAUDE_CONFIG_DIR": "config" }` dictionaries, ensuring `launcher.py`'s absolute path injection takes precedence.

## 4. Workspace-Tier Design

The workspace-tier `.engram/` directory will live under the active workspace root (e.g., `workspace/MyProject/.engram/`).

**What goes in the workspace tier?**
It will strictly contain **project-scoped AI memory and transcripts** for THIS environment.
- `workspace/MyProject/.engram/claude/projects/`: Claude's conversational memory for this specific workspace.
- `workspace/MyProject/.engram/codex/memories_1.sqlite`: Codex's local SQLite memory.
- `workspace/MyProject/.engram/agy/conversation_summaries.db`: Antigravity's local DB.

**Why not other tools?**
- `git` already has a perfect workspace tier: `.git/config`.
- `VS Code` already has a perfect workspace tier: `.vscode/settings.json`.
There is no need to reinvent local configuration for tools that already natively support it in a clean way. The workspace `.engram/` serves to quarantine the AI CLIs' messy, auto-generated project state out of the root project folder, keeping the user's workspace pristine.

## 5. Migration Plan

For users (and alternate environment copies like `D:\tttt`) already utilizing the `.ais/` prototype naming:
1. **At Startup**: `launcher.py` will include a one-time migration check early in `main()`.
2. **Auto-Rename**: If `base_dir / ".ais"` exists and `base_dir / ".engram"` does not, `launcher.py` will automatically rename `.ais` to `.engram`.
3. If both exist, it will log a warning and use `.engram`.
4. Users can manually delete the old `ais-env.bat` script, but its presence is harmless since `launcher.py` will overwrite those variables in the active session.

## 6. MECE Self-Check / Missing Considerations

- **gh Authentication Leaks**: By mapping `GH_CONFIG_DIR` to `.engram/gh`, we ensure that GitHub CLI auth tokens (like `hosts.yml`) are stored locally. This is highly durable but also a credential. If external backup scripts are used, they must explicitly ignore `.engram/gh/hosts.yml` to avoid leaking secrets.
- **Missing Directories at Launch**: If a tool's directory in `.engram/` doesn't exist yet, tools like `git` might complain if `.gitconfig` is missing and they try to read it. `launcher.py` should run `mkdir -p` for the base directories (`.engram/git`, `.engram/gh`, etc.) during startup.
- **NPM Caches**: `env.json` already cleanly separates `NPM_CONFIG_CACHE` into `_sys/data/temp/npm-cache`. This remains intact and unaffected by `.engram/`.
