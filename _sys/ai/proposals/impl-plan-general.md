# Implementation Plan — General Requirements (Step 3)
> Authors: cc + gc | Date: 2026-06-18 | Status: APPROVED (debate consensus)
> Source: docs-v2/user/requirements.md | Target: Step 4 (TDD) → Step 5 (implementation)

---

## Priority Order

| # | Item | Priority | Effort | Risk |
|---|------|----------|--------|------|
| I1 | managed-links.json | P1 | Low | Low — data file only |
| I2 | peers.json model_profiles | P2 | Low | Low — additive config |
| I4 | self_care.py pipeline | P3 | Medium | Low — wraps existing scripts |
| I3 | protocol.json reelect_per_task | P4 | Trivial | None |
| I5 | workspace_base template | P5 | Low | None |

---

## I1. managed-links.json — Junction SSOT

**What**: Single source of truth for all junctions managed by virtualizer.py.  
**Why missing**: Root swap cancelled before this was populated.  
**Requirement**: D4 (docs-v2/user/requirements.md)

### File Path
`P:\_sys\data\state\pathmap\managed-links.json`

### Schema (from virtualizer.py:311-336)
```json
{
  "_version": "1.0",
  "_help": "SSOT for all managed junctions. virtualizer.py apply reads this first.",
  "entries": {
    "<entry_id>": {
      "relative_link_path": "EXTERNAL:%USERPROFILE%\\.claude  OR  relative/to/sys_dir",
      "relative_target_path": "relative/to/sys_dir"
    }
  }
}
```

### Entries to populate
| entry_id | link_path | target_path | Notes |
|----------|-----------|-------------|-------|
| cc_host | `EXTERNAL:%USERPROFILE%\.claude` | `claude\config` | claude config SSOT |
| gc_host | `EXTERNAL:%USERPROFILE%\.gemini` | `gemini\config` | gemini config SSOT |

Note: root-level project junctions (P:\.claude, P:\.gemini) continue to be managed by peers.json fallback — they reference base_dir not sys_dir. managed-links.json covers host-level junctions only.

### Tests
- `test_virtualizer.py`: verify `managed-links.json` loaded correctly → entries applied as junctions
- `test_virtualizer.py`: verify fallback to peers.json if managed-links.json missing
- `test_virtualizer.py`: verify `EXTERNAL:` prefix expands via `os.path.expandvars`

---

## I2. peers.json model_profiles — Per-Peer Model Selection

**What**: Each peer declares its available models by tier (standard/effort/deepthink).  
**Why missing**: model_profiles key not yet in peers.json schema.  
**Requirement**: B6 (routing.md §6)

### File Path
`P:\_sys\ai\peers.json` — update `peers.{id}` objects

### Change Per Peer
```json
"model_profiles": {
  "standard":  "<fast/cheap model>",
  "effort":    "<default capable model>",
  "deepthink": "<most capable model>"
}
```

### Values
| peer | standard | effort | deepthink |
|------|----------|--------|-----------|
| claude | claude-haiku-4-5-20251001 | claude-sonnet-4-6 | claude-opus-4-8 |
| gemini | gemini-2.0-flash | gemini-2.5-pro | gemini-2.5-pro |
| codex | codex-mini-latest | o4-mini | o3 |
| antigravity | default | default | default |

### No hub.py change needed
Each peer CLI handles model selection internally based on its profile. hub.py stays thin.

### Tests
- `test_config.py`: verify `peers.json` schema includes model_profiles for all enabled peers
- `test_config.py`: verify no peer has `deepthink` = `null` (must have a fallback)

---

## I4. self_care.py — Event-Based Self-Care Pipeline

**What**: A single entry-point script that runs the 7-step self-care procedure on trigger.  
**Why missing**: saturation_scan.py and sync_docs.py exist but no wiring to ctx-end.  
**Requirement**: C4 (self-evolution.md §4)

### File Path
`P:\_sys\checks\self_care.py` (NEW)

### Trigger Wiring
`P:\_sys\hooks\ctx_end.py` — add self-care call at end of session hook.

### Interface
```
python self_care.py [--trigger session_end|error_threshold|commit_interval|manual]
```

### Procedure (7 steps — maps to self-evolution.md §4)
```
Step 1: [Observe]   read health.json, runtime-directives.jsonl, active-lessons.jsonl
Step 2: [Validate]  virtualizer.py status → check junction health
Step 3: [Cleanup]   sweep expired directives (TTL), prune _sys/data/temp/ if > 50MB
Step 4: [Scan]      saturation_scan.py --quiet → capture findings
Step 5: [Propose]   if saturation findings: hub.py proposal-add (never auto-execute)
Step 6: [Sync]      sync_docs.py --dry-run → report pending capsules (no auto-apply at this stage)
Step 7: [Record]    append summary to _archive/self-care-log.jsonl
```

### Output
- Exit 0 if all steps pass
- Exit 1 if any step raises an exception (non-blocking: log error, continue remaining steps)
- Always writes a summary to `_archive/self-care-log.jsonl`

### ctx_end.py change
```python
# At end of ctx_end.py, after session archive:
import subprocess
subprocess.run(["python", str(checks_dir / "self_care.py"), "--trigger", "session_end"],
               capture_output=True)  # non-blocking: don't fail session-end if self-care fails
```

### Tests
- `test_self_care.py`: mock saturation_scan, sync_docs, virtualizer → verify all 7 steps called in order
- `test_self_care.py`: verify step failure is non-blocking (remaining steps still run)
- `test_self_care.py`: verify output written to `_archive/self-care-log.jsonl`

---

## I3. protocol.json reelect_per_task — Leader Election Flag

**What**: Add `reelect_per_task: false` to protocol.json leader_election section.  
**Why missing**: New parameter from Step 1 debate (D6 resolution).  
**Requirement**: H (tradeoffs.md)

### File Path
`P:\_sys\ai\protocol.json` — add to existing `leader_election` object

### Change
```json
"leader_election": {
  ...existing fields...,
  "reelect_per_task": false,
  "reelect_per_task_note": "If true, hub.py triggers elect-leader before every ask. Default false (session-scoped)."
}
```

### hub.py change (minimal)
`action_ask`: before routing, if `protocol_json["leader_election"]["reelect_per_task"]` is `true`, call `action_elect_leader` first. This is already architecturally supported — just needs the config read.

### Tests
- `test_hub.py`: verify `reelect_per_task=false` → no re-election on ask
- `test_hub.py`: verify `reelect_per_task=true` → elect-leader called before each ask

---

## I5. workspace_base Template Completion

**What**: Expand `_sys/templates/workspace_base/` with full skeleton for new workspaces.  
**Why missing**: Only README.md currently; workspace creation needs a real template.  
**Requirement**: D2 (docs-v2/user/requirements.md)

### File Path
`P:\_sys\templates\workspace_base\` — add files

### Files to Create
| File | Purpose |
|------|---------|
| `.gitignore` | Workspace-specific ignores: `.env`, `node_modules/`, `__pycache__/`, `_state/` |
| `CLAUDE.md` | Minimal stub: project name placeholder + link to `_sys/docs-v2/user/manual.md` |
| `GEMINI.md` | Minimal stub: project name placeholder + link to `_sys/docs-v2/user/manual.md` |
| `specific/` | Empty dir placeholder (workspace-specific agents/skills go here) |
| `config/settings.json` | `{"project_name": "", "collab_rate_override": null}` |

### Portability Constraint
All paths in templates use `{BASE_DIR}` or relative paths. No hardcoded drive letters.

### Tests
- `test_path_scenarios.py`: verify workspace_base template contains no hardcoded paths
- `test_path_scenarios.py`: verify all template files are valid (parseable JSON where applicable)

---

## Implementation Order

```
I3 → I2 → I1 → I5 → I4
(trivial)  (additive)  (data file)  (template)  (code)
```

Dependencies:
- I4 (self_care.py) depends on I1 (managed-links.json) for virtualizer status check
- I1 can be created independently
- I2, I3, I5 are fully independent

## Rollback Safety
All items are additive (new files or new keys in existing JSON). No existing behavior removed.  
I3 flag defaults to `false` → identical to current behavior.  
I4 runs as non-blocking subprocess in ctx_end → session-end cannot fail due to self-care.
