# Specific — gc (Gemini CLI)
> Delta from general/*. Load after general/. Status: ACTIVE.

---

## Directory Layout

```
_sys/gemini/
├── config/
│   ├── GEMINI.md           ← session instructions (loaded at invocation)
│   ├── settings.json       ← model, temperature, tool settings
│   ├── state.json          ← current session state
│   ├── history/            ← conversation history
│   └── trustedFolders.json ← trusted folder list
├── health.json             ← peer health
├── status.json             ← legacy gate mirror (see §Legacy Gate below)
├── project/
└── templates/
```

---

## Permission Flags (delta from general/permissions.md)

```
gemini --approval-mode auto_edit --skip-trust
```

FORBIDDEN: `--approval-mode yolo`, `--approval-mode full-auto`.

---

## Session Reuse (delta from general/session.md)

`hub.py ask` reuses gc CLI sessions across calls:
- New: `gemini --session-id <uuid> -p - -o text --approval-mode auto_edit --skip-trust`
- Resume: `gemini --resume <uuid> -p - -o text --approval-mode auto_edit --skip-trust`
- State: `_sys/gemini/session_state.json`
- `fill_depth_multiplier = 3` (gc reads 3× more context-fill sections than other peers)
- IPC query files: `_sys/gemini/gc-{YYYYMMDDHHMMSS}-{RAND4}.txt` (English only — Korean costs 2-3× tokens)

---

## Legacy Gate Mirror

`status.json` is a legacy compat file for `gemini-gate.bat` / `gemini-status.bat`.
Kept in sync by `hub.py _sync_peer_gate_file()` on quarantine/recover.
Future: migrate bat scripts to read `health.json["availability"]["gate_open"]` directly.

---

## Gate & Entry

- Gate script: `_sys/gemini/gemini-gate.bat`
- Status check: `gemini-status.bat`
- Hub command: `hub.py ask --to gc --query-file <file>`

---

## Key Files

| File | Role |
|------|------|
| `_sys/gemini/health.json` | Health manifest |
| `_sys/gemini/status.json` | Legacy gate mirror (do not modify directly) |
| `_sys/gemini/config/GEMINI.md` | Session instructions |
| `P:\GEMINI.md` | Project-level Gemini config (at root, consumed at invocation) |
