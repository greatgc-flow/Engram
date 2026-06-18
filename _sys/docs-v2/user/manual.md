# User Manual — Portable Multi-Peer Dev Environment
> Condensed from USER_MANUAL.md. Full version archived → `_sys/docs/history/` (pre-docs-v2 SSOT).

---

## Quick Start

```
1. register.bat          ← register on new PC (SUBST P: + context menu)
2. _sys\cli\claude.bat   ← launch Claude Code peer
3. _sys\cli\gemini.bat   ← launch Gemini CLI peer
```

---

## Daily Workflow

### Session Start
```
hub.py init-session --agent cc     # (auto-called by claude.bat)
hub.py health-check                # verify peer status
hub.py peer-status                 # all peers at a glance
```

### Check Peers
```
hub.py health-check                # all peers health summary
hub.py health-precheck --peer gc   # before routing ask to gc
```

### Ask a Peer
```
python _sys/core/hub.py ask --to gc --query-file <file.txt>
```
Query file format: TASK/CONTEXT/QUESTION in English.

### End of Session
```
ctx-save     # save session context (mid-session checkpoint)
ctx-end      # end-of-day: archive + cleanup
```

---

## Peer Reference

| Peer | Launch | ID | Best for |
|------|--------|----|----------|
| Claude Code | `claude.bat` | cc | Code, architecture, memory |
| Gemini CLI | `gemini.bat` | gc | Large corpus, research, cross-review |
| Codex | `codex.bat` | cx | Code execution, short tasks |
| AntiGravity | `agy.bat` | ag | Shell scripts, quick CLI (**INACTIVE**) |

---

## Collaboration Rate (collab_rate)

Current value: `_sys/ai/protocol.json["collab_rate"]["current"]`

| Rate | When to use |
|:----:|:-----------|
| 0 | Fully solo (read-only exploration) |
| 3 | Normal code work in workspace/ |
| 5 | Changing `_sys/` scripts |
| 8 | Multi-file `_sys/` changes |
| 10 | Protocol/hub.py changes (all peers must consent) |

---

## Common Commands

```
hub.py consensus-propose --subject "..." --voters cc,gc --from cc
hub.py consensus-vote --round-id r-XXXX --voter gc --vote agree
hub.py consensus-sweep                    # clean stalled rounds
hub.py directive-list                     # show active runtime directives
hub.py peer-quarantine --peer gc --reason quota
hub.py peer-recover --peer gc --reason quota_reset
hub.py elect-leader --needs code --effort mid
hub.py task-checkpoint --id <id> --peer cc --msg "..."
```

---

## New PC Setup

1. Clone/copy the portable folder to any drive
2. Run `register.bat` (creates SUBST P: + right-click "Open with Claude Code")
3. Run `_sys\cli\claude.bat` to launch

To move to a new drive: run `unregister.bat` on old PC, then `register.bat` on new PC.

---

## Maintenance

```
_sys\checks\check-health.bat      ← verify peer health + deps
_sys\checks\check-portability.bat ← verify no host-path leaks
_sys\tests\run-tests.bat --all    ← full test suite
```
