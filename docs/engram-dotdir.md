# `.engram/`: the AI CLI personal-config root

Ratified 2026-09-09: [`docs/design/dotdir-consolidation-RATIFIED-2026-09-09.md`](https://github.com/greatgc-flow/peerhub/blob/main/docs/design/dotdir-consolidation-RATIFIED-2026-09-09.md) in the [peerhub](https://github.com/greatgc-flow/peerhub) repo (the design record for both repos; this repo's own Round-1 proposal is at [`docs/design/dotdir-consolidation-engram-proposal-2026-09-09.md`](design/dotdir-consolidation-engram-proposal-2026-09-09.md)). This page is the Engram-side user-facing reference.

## What it is

Every AI CLI Engram manages (Claude Code, Codex, Antigravity) reads and writes its personal, durable config — memory, settings, session history, rules, skills — from one consolidated root: `<portable-root>/.engram/{claude,codex,agy}/`. PeerHub's own global config joins it at `.engram/peerhub/config/`, and `git`'s global config at `.engram/git/.gitconfig` when one exists.

This happens **automatically**, at every `engram launch`/environment build — there is nothing to run by hand. It works by setting each tool's own config-root environment variable for the launched session (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `GEMINI_DIR`, `GH_CONFIG_DIR`, `PEERHUB_CONFIG_HOME`), declared in [`_sys/env.json`](../_sys/env.json)'s `tool_env_vars` and resolved by [`_sys/core/launcher.py`](../_sys/core/launcher.py)'s `build_env()`. **No `subst` drive and no directory junction is used for this** — pure environment-variable redirection, so it works identically wherever the portable root happens to sit, with no host-registry or filesystem side effect to clean up on uninstall.

## `.engram/` is a live root, not a backup

`.engram/` accumulates whatever each tool actually writes there during real use — including credentials (`codex/auth.json`, `gh/hosts.yml`) and caches (`claude/cache/`, `claude/shell-snapshots/`, and similar). It is **not** a clean, curated, "safe to hand off" folder by itself.

Consequences:
- `.engram/` is **gitignored** at the portable root — it is never committed.
- It is **never copied wholesale** for backup, migration, or sharing. [`_sys/checks/backup_personal_data.py`](../_sys/checks/backup_personal_data.py) exists for exactly this reason: it extracts only the durable, non-secret subset via an explicit named allowlist (never a wholesale directory copy with an exclude list, so a credential file simply has no entry that would ever copy it) into a separate bundle you can actually move around.
  ```
  python _sys/checks/backup_personal_data.py --base-dir . --backup --out ./my-backup
  python _sys/checks/backup_personal_data.py --base-dir . --restore ./my-backup
  python _sys/checks/backup_personal_data.py --list ./my-backup
  ```
- `check_root_hygiene`/`_sys/checks/_common.py`'s vendor-cache allowlist treats `.engram/` the same way it already treats `.claude/`/`.codex/`/`.agy/`/`.peerhub/`/`.vscode/` — a recognized, expected root entry, not hygiene noise.

## Retired: `.ais/` and `ais-env.bat`

`.ais/` was this feature's first prototype (built during a same-day parallel-install exercise, D:\tttt) — a folder you pointed `CLAUDE_CONFIG_DIR`/`CODEX_HOME`/`GEMINI_DIR` at yourself, by running `ais-env.bat` in every new shell. `.engram/` is the permanent replacement: the same idea, but automatic (no script to remember to run) and generalized to every tool Engram manages, not just the 3 AI CLIs.

If you still have an `.ais/` folder from before this change, migrate it once:
```
python _sys/core/migrate_ais_to_engram.py --base-dir . --apply
```
This refuses outright (rather than guessing) if `.ais/` turns out to be a `backup_personal_data.py` *snapshot* rather than a live root (it checks for `MANIFEST.txt`), or if `.engram/` already has real content of its own — inspect both and resolve the conflict by hand in that case. A dry run (the default, no `--apply`) reports the plan without changing anything.

## Global vs. workspace

`.engram/` is Engram's **global** tier — one per portable installation, holding your personal AI-CLI state. It is not, and never becomes, a per-project thing: a project's own settings live in that project's own dot-directories (`.peerhub/`, `.git/config`, `.vscode/settings.json`, `.claude/settings.json`) exactly as they always have. Engram's job here is limited to choosing *where the global root is*; it never merges or overlays a tool's own project-vs-global config resolution — each tool already does that correctly on its own.

## Relationship to `register.bat`'s SUBST/junction machinery

`register.bat` has its own, separate optional host-integration step (a directory-junction step driven by `_sys/managed-links.json`, and legacy read-support for a SUBST drive letter saved by an older Engram version). That machinery is unrelated to `.engram/` and does not need to run for `.engram/` to work: `managed-links.json` ships with zero entries, so a fresh `register` creates no junctions, and nothing in the current codebase ever creates a new SUBST mapping — only an install carried forward from an older version (one that saved `subst_drive` in `register.state.json` before that write path was removed) still has one, and only for backward compatibility does Engram keep re-mounting it on launch. A brand-new install never needs either.
