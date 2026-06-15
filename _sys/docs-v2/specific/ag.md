# Specific — ag (AntiGravity)
> Delta from general/*. Status: INACTIVE (default). DO NOT ROUTE TASKS.

---

## Status: INACTIVE

ag is excluded from R:10 voting and task routing until PRO-15 is resolved.

**Known gap (PRO-15):** `peer_console.py` currently uses `--dangerously-skip-permissions` for ag
because correct minimum agy CLI flags are not yet confirmed. This violates PRO-03.

---

## Recovery Path (before re-enabling)

1. Confirm correct agy CLI minimum flags (equivalent to cc's `--allowedTools ... --permission-mode acceptEdits`)
2. Update `_sys/cli/peer_console.py` ag block with confirmed flags
3. Run `hub.py profile-validate --peer ag` → must pass parity check + no forbidden flags
4. Update `health.json`: `hub.py health-update --peer ag --status GREEN --failures 0`
5. Add to `protocol.json["collab_rate"]["r10_voters"]` if ag will participate in R:10

**Target permission profile:**
```
agy --allowedTools Edit Write Read Glob Grep Bash MultiEdit --permission-mode acceptEdits
```

---

## Directory Layout

```
_sys/antigravity/
├── config/
│   ├── AGY.md              ← session instructions
│   ├── brain/              ← reasoning modules (now archived to _archive/reviews/agy/)
│   ├── builtin/            ← built-in commands
│   ├── settings.json       ← agy settings
│   └── log/                ← session logs
├── health.json             ← peer health (current: INACTIVE)
└── project/
```

---

## Gate & Entry (when active)

- Entry: `_sys/cli/agy.bat` → `agy_entry.py`
- Health: `_sys/antigravity/health.json`
- Config: `CODEX_HOME`-style env var pointing to `_sys/antigravity/config/`
