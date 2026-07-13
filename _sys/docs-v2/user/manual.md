# User Manual - Portable Multi-Peer Dev Environment
> Condensed from USER_MANUAL.md. Full version archived in `_sys/docs/history/` (pre-docs-v2 SSOT).

---

## Quick Start (new machine)

```
1. INSTALL.bat           # bootstrap Python + provision tools/runtimes (no admin)
2. register.bat          # mount SUBST P: drive + add right-click context menu
3. STATUS.bat            # verify the environment is healthy
4. _sys\cli\claude.bat   # launch a peer (or codex.bat / agy.bat)
```

No Administrator rights are required for any of these — see **Permissions** below.

---

## Lifecycle at a Glance

| Command | Purpose | Mutates | Admin? | Reversible |
|---------|---------|---------|:------:|------------|
| `INSTALL.bat` | Bootstrap Python; provision tools/runtimes to match `runtimes.json` | portable tree | No | re-run / `CLEANUP.bat` |
| `register.bat` | Mount SUBST `P:` + HKCU context menu + peer junctions | host (per-user) | No | `unregister.bat` |
| `STATUS.bat` | Read-only health check (mount, versions, sessions, registration) | nothing | No | n/a |
| `UPDATE.bat` | Discover -> confirm -> apply tool/runtime version bumps | `runtimes.json` + tree | No | backup in `_archive/tool-updates/` |
| `CLEANUP.bat` | Tiered removal of caches/temp/logs (and, at high tiers, more) | portable tree | No | re-install |
| `unregister.bat` | Remove SUBST drive + HKCU entries + junctions | host (per-user) | No | `register.bat` |

INSTALL / register / STATUS / UPDATE / CLEANUP report **truthful outcomes**: a
partial install or a failed registration exits non-zero instead of falsely
reporting success.

---

## Install / Repair — `INSTALL.bat`

- Bootstraps a portable Python (embeddable build) if none is present, then
  provisions every tool/runtime declared in `_sys/runtimes.json`.
- **Idempotent**: safe to re-run. It only (re)installs components that are
  missing or version-mismatched, and re-running is the way to repair a partial
  install.
- **Python pin consistency**: INSTALL never advances the declared Python version
  in `runtimes.json` while an older interpreter is still installed. If a newer
  stable Python exists it prints an actionable notice and keeps the pin, so the
  declared version always equals the on-disk interpreter.
- `--skip-update` skips the "latest stable Python" network check and uses the
  pinned version.

---

## Host Registration — `register.bat` / `unregister.bat`

`register.bat` adds three per-user host integrations (no admin needed):

- a **SUBST `P:` drive** pointing at the portable folder,
- **HKCU context-menu** entries ("Open with ..."),
- **directory junctions** for peer config (per `peers.json`).

`unregister.bat` removes all three. **Always run `unregister.bat` before moving
the folder to a new drive or deleting the environment** — it is the only thing
that knows which HKCU keys and junctions to remove. Then `register.bat` on the
new location.

`register.state.json` is the teardown ledger for this integration; it is owned
by register/unregister and is **never** removed by `CLEANUP.bat`.

---

## Status / Doctor — `STATUS.bat`

A zero-network, read-only "is my environment healthy right now?" check:

```
STATUS.bat            # human-readable report
STATUS.bat --json     # machine-readable JSON (for scripting)
```

It reports: portable Python declared-vs-installed consistency (the one hard
gate — a mismatch is an error), which declared components are present, whether
the SUBST drive is mounted, whether the HKCU context menu is registered, any
active peer session/lease, and your elevation (standard user is expected).
`STATUS.bat` exits non-zero only when Python itself is broken; missing optional
tools or an unmounted drive are reported as advisories, not failures.

---

## Updating — `UPDATE.bat`

One command discovers, shows, and (on confirmation) applies tool/runtime
version bumps:

```
UPDATE.bat              # discover -> print planned changes -> "Apply? [y/N]"
UPDATE.bat --yes        # apply without the prompt
UPDATE.bat --install    # after applying, re-run INSTALL to deploy the new versions
UPDATE.bat --dry-run    # discover + show the proposal, change nothing
```

- The exact proposal (with a checksum of the current `runtimes.json`) is written
  under `_archive/tool-updates/<timestamp>/`; apply verifies that checksum and
  writes a backup before replacing `runtimes.json` atomically.
- Declining the prompt is not a failure — it prints the exact command to apply
  the same proposal later.
- **Honest coverage**: components with no discovery provider (the base runtimes
  `python`, `nodejs`, `git`, `vscode`, `pwsh`, and the manual `agy`) are listed
  under **"not checked"** rather than silently implied up-to-date.

---

## Cleanup — `CLEANUP.bat`

Tiered cleanup. Tier 1 is safe; higher tiers require confirmation.

| Tier | Name | Removes |
|:----:|------|---------|
| 1 | Light | caches (pip/npm), `_sys/data/temp`, **ephemeral** `.ai` logs/IPC, pytest caches, `__pycache__` |
| 2 | Soft | Tier 1 + setup archives, `venv`, local config, install state |
| 3 | Reset | Tier 2 + runtimes, tools, peer auth, junctions |
| 4 | ZeroBase | Tier 3 + workspace, archives, **`.ai` governance state**, peer systems |
| 5 | Purge | Tier 4 + portable Python (full reset) |

Safety guarantees:

- **Governance state is preserved by Tier 1.** A light cleanup clears only
  ephemeral `.ai` logs/IPC; consensus rounds, quarantine records, `state.json`,
  leases, and sessions survive. The full `.ai` governance state is only removed
  at Tier 4 (ZeroBase), which you must confirm.
- **Active-session guard.** Cleanup refuses to run while a peer session/lease is
  active (a fresh lock or an unexpired lease). Use `--dry-run` to preview safely,
  or `--force` to override.
- **Never orphans host integration.** `CLEANUP.bat` never deletes
  `register.state.json`; remove host integration with `unregister.bat`.

```
CLEANUP.bat --dry-run          # preview what a cleanup would remove
CLEANUP.bat --tier 1 --all     # run Tier 1 non-interactively
```

To fully uninstall: `unregister.bat`, then delete the portable folder.

---

## Permissions — the Zero-Admin Rule

**This environment requires no Administrator privileges.** Do not run the
lifecycle commands elevated. Everything operates in user space:

- SUBST drive mapping (not a real mount), HKCU registry (not HKLM), directory
  junctions (`mklink /J`, not symlinks), and portable download+extract.

The **only** reason you might use Administrator is an *optional* Windows Defender
real-time-scan exclusion for the workspace, to improve IO performance or avoid
occasional antivirus file-lock spawn errors. This is not automated (it changes
host security policy), is a last resort, and should only be added with evidence
that real-time scanning is the cause. `STATUS.bat` prints your elevation so you
can confirm you are running as a standard user.

---

## Command Wrappers

Use bare commands from any workspace: `hub`, `diag`, `msg`, `manage`, `git-draft`, `batch-review`, `set-collab-rate`, and the peer launchers (`claude`, `codex`, `agy`). `_sys\cli` is the single PATH entry for these operator commands. cmd/PowerShell resolve the `.bat` wrappers; Git Bash resolves the extensionless shims. Do not call `python _sys/core/hub.py ...` from arbitrary workspaces.

## Daily Workflow

### Session Start
```
hub init-session --agent cc     # (auto-called by claude.bat)
hub peer-status                 # all peers at a glance (canonical status)
```

### Check Peers
```
hub peer-status                 # all peers at a glance (canonical status)
hub health-precheck --peer ag   # before routing an ask to a peer
diag                             # action-first dashboard (attention strip, quotas, sessions)
diag --peers                     # add the verbose per-peer detail cards
diag --live 5                    # compact no-scroll SUMMARY + recent-session HUD
diag --json --watch 5            # NDJSON telemetry stream for automation
```

The one-shot `diag` is ordered most-actionable-first: a compact room line, an
**ATTENTION** strip (any `[CRIT]`/`[WARN]` peer, gate state, over-capacity
context, and the next failover target), then SUMMARY, HEADROOM, RECENT SESSIONS,
PROFILES & ROUTING, POLICY, and a freshness FRAME. Session rows show the real
lease state (`[OPEN]`/`[CLOSED]`/`[FAILED]`). The verbose per-peer cards live
behind `--peers`. Set `NO_COLOR=1` for plaintext severity (no emoji/ANSI).

`diag --live [seconds]` repaints a standalone SUMMARY → RECENT SESSIONS → FRAME
HUD in place (no scroll). It shows at most three newest sessions per peer with
their lease state, uses five seconds by default, and rejects intervals below
two seconds.

### Ask a Peer
```
hub ask --to cx --query-file <file.txt>
```
Query file format: TASK/CONTEXT/QUESTION in English.

### End of Session
```
ctx-save     # save session context (mid-session checkpoint)
ctx-end      # end-of-day: archive + cleanup
```

---

## Peer Reference & Topology

`_sys/ai/orchestration.json` is the canonical topology source. A peer is a provider-level participant; its runtime nodes are generated from the profile tree (standard / effort / deepthink).

| Peer | CLI | State | Standard | Effort | Deepthink |
|------|-----|-------|----------|--------|-----------|
| `cc` | Claude Code | Active | Haiku 4.5 / low | Sonnet 4.6 / high | Opus 4.8 / high |
| `ag` | Antigravity | Active | Gemini 3.5 Flash / low | Gemini 3.5 Flash / high | Gemini 3.1 Pro / high |
| `cx` | Codex | Active | gpt-5.6-luna / low | gpt-5.6-terra / high | gpt-5.6-sol / xhigh |
| `ca` | Claude alternate | Disabled | — | — | — |

`cc` also has a premium `fable` arbiter profile; `ag` has a manual-only `opus`
(Claude Opus 4.6) profile plus `gptoss` (GPT-OSS 120B) — both kept out of bulk
routing. The default profile is deliberately low cost; the hub promotes/demotes
each request among `standard`, `effort`, and `deepthink`.

---

## Collaboration Rate (collab_rate)

Current value: `_sys/ai/protocol.json["collab_rate"]["current"]`

| Rate | When to use |
|:----:|:-----------|
| 0 | Fully solo (read-only exploration) |
| 3 | Normal code work in workspace/ |
| 5 | Changing a single `_sys/` script |
| 8 | Multi-file `_sys/` changes |
| 10 | Protocol/hub.py changes (all peers must consent) |

See `general/protocol.md` for the R:3-vs-R:5-vs-escalate boundary examples.

---

## Common Commands

```
hub consensus-propose --subject "..." --voters cc,ag,cx --from cc
hub consensus-vote --round-id r-XXXX --voter ag --vote agree
hub consensus-sweep                    # clean stalled rounds
hub directive-list                     # show active runtime directives
hub peer-quarantine --peer cx --reason quota
hub peer-recover --peer cx --reason quota_reset
hub elect-leader --needs code --effort mid
hub task-checkpoint --id <id> --peer cc --msg "..."
```

---

## Maintenance

```
STATUS.bat                        # environment health (mount, versions, sessions)
_sys\checks\check-health.bat      # verify peer health + deps
_sys\checks\check-portability.bat # verify no host-path leaks
_sys\tests\run-tests.bat --all    # full test suite
```
