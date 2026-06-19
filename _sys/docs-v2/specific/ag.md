# Specific — ag (AntiGravity)
> Delta from general/*. Status: ACTIVE (gc replacement, 2026-06-19).

---

## Status: ACTIVE

ag is an active consensus voter (cc/ag/cx). Replaces gc after IneligibleTierError (tier_suspended 2026-06-19).

**PRO-15 resolved:** `--dangerously-skip-permissions` is the accepted IPC flag for all active peers.
Peer equality established: all peers have identical autonomy and fill_depth_multiplier=1.

**Permission profile:**
```
agy --dangerously-skip-permissions -p {query}
```

**Critical Windows note:** agy writes to Windows Console API, not stdout pipes.
`requires_pty=true` is mandatory in orchestration.json. subprocess.PIPE capture hangs indefinitely.

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
