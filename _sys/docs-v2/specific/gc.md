# Specific — gc (Gemini CLI)
> Delta from general/*. Load after general/. Status: SUSPENDED.

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
├── project/
└── templates/
```

---

## Permission Flags (delta from general/permissions.md)

```
gemini --approval-mode auto_edit --skip-trust
```

FORBIDDEN: `--approval-mode yolo`, `--approval-mode full-auto`.

## Runtime Profiles

`gc.standard`, `gc.effort`, and `gc.deepthink` remain declared for diagnostics but
inherit the disabled root lifecycle and are not routable.

## Context and Collaboration

If gc is re-enabled by a governed lifecycle change, it receives the same room
references and promotion/ACK contract as every peer.

---

## Session Reuse (delta from general/session.md)

`hub.py ask` reuses gc CLI sessions across calls:
- New: `gemini --session-id <uuid> -p - -o text --approval-mode auto_edit --skip-trust`
- Resume: `gemini --resume <uuid> -p - -o text --approval-mode auto_edit --skip-trust`
- State: `_sys/gemini/session_state.json`
- `fill_depth_multiplier` is configured by `protocol.json["workload"]["fill_depth_multiplier"]["gc"]`
- IPC query files: `_sys/ai/ipc/gc-{YYYYMMDDHHMMSS}-{RAND4}.txt` (English only — Korean costs 2-3× tokens)

---

## Lifecycle Gate

`orchestration.json` is authoritative. The legacy `status.json` gate is retired;
live diagnostics use lifecycle state plus `health.json` freshness and zero-token
CLI probes.

---

## Health & Auto-Remediation

- INV-15 triggers SelfHealer when `consecutive_failures ≥ protocol.json["health"]["failure_error"]`.
- gc is the **primary large-corpus analyst**. On gc RED: hub.py routes analysis tasks to cc as fallback.
- RED recovery: `hub.py peer-recover --peer gc` (NOT manual health-update). See INV-11.
- See `general/self-evolution.md §2.1` for full SelfHealer tier description.

---

## Gate & Entry

- Gate: `hub.py peer-quarantine --peer gc` / `hub.py peer-recover --peer gc`
- Status check: `hub.py peer-status --peer gc`
- Hub command: `hub.py ask --to gc --query-file <file>`

---

## Key Files

| File | Role |
|------|------|
| `_sys/gemini/health.json` | Health manifest |
| `_sys/gemini/config/GEMINI.md` | Session instructions |
| `P:\GEMINI.md` | Project-level Gemini config (at root, consumed at invocation) |
