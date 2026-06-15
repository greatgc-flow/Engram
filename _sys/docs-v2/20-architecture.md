# Architecture — Physical/Logical Directory Design
> Synthesized from: MECE_Directory_Architecture_Specification.md v2.6 + TAXONOMY_v11 + workspace-connectivity-map.md
> Status: TARGET DESIGN (implementation via sys-restructure-plan.md + pathmap tooling)

---

## 1. Design Principles

| # | Principle | Rule |
|---|-----------|------|
| P1 | SSOT | Every original file exists in exactly ONE physical location |
| P2 | Physical/Logical separation | Physical layer = files. Logical layer = junctions/symlinks ONLY. |
| P3 | Downward encapsulation | Physical subdirs are independent; no upward/lateral physical references |
| P4 | IaC via PathMap | ALL logical-view mappings declared in `Path_Map.json` — never ad-hoc |
| P5 | Verify-first | Every FS change: dry-run → `--apply` explicit → audit log |
| P6 | Portable paths | No hardcoded drive letters in Path_Map.json (runtime detection) |
| P7 | Lifecycle-based root split | User Space / System Bin / Archive / Volatile — isolated at root |

---

## 2. Four-Layer Physical Structure

```
[Drive Root]
├── [00_Workspace_Views]   ← LOGICAL LAYER: junctions + symlinks ONLY (zero real files)
├── [01_User_Space]        ← SSOT origin: active user data (backup priority 1)
│   ├── [00_Inbox]         ← unclassified staging buffer
│   ├── 01_Development     ← project source files
│   ├── 02_Templates       ← reusable templates and prompts
│   ├── 03_App_State       ← app persistent state (excluded from backup)
│   ├── 98_App_Configs     ← app fixed-path config SSOT
│   └── 99_Path_Dictionary ← PathMap.json, managed-links.json, audit logs
├── [02_System_Bin]        ← reinstallable binaries (backup priority 2)
├── [03_Archive_Media]     ← cold data, media (backup priority 3)
└── [04_Volatile_Temp]     ← ephemeral temp (no backup)
```

---

## 3. PathMap Control Plane (`99_Path_Dictionary`)

| File | Role |
|------|------|
| `Path_Map.json` | IaC declaration: SSOT paths → logical view mappings |
| `Path_Map.schema.json` | JSON Schema validation |
| `Path_Map.status.json` | Runtime state (separate from IaC) |
| `managed-links.json` | Registry of all hub-managed junctions |
| `pathmap.lock` | Mutex for concurrent mutation prevention |
| `snapshots/` | Pre-apply snapshots |
| `logs/pathmap_audit.jsonl` | Immutable audit log |

---

## 4. Architecture Invariants

### MUST (physical layer)

| ID | Enforcement | Rule |
|----|------------|------|
| I-01 | [POLICY] | All original files exist in Physical Layer (01~04) exactly ONCE |
| I-02 | [TOOL] | `[00_Workspace_Views]` contains ONLY junctions/symlinks — zero real files |
| I-03 | [TOOL] | All junctions created by `pathmap apply` must be registered in `managed-links.json` |
| I-04 | [TOOL] | All mutating commands acquire `pathmap.lock` first |
| I-05 | [TOOL] | All mutating commands write to audit log after completion |
| I-06 | [TOOL] | Migration: Copy-Verify-Delete pattern ONLY (no /MOVE) |
| I-08 | [TOOL] | `managed-links.json` updates: atomic temp→rename |
| I-09 | [TOOL] | `prune --apply`: confirm physical delete before removing from registry |
| I-10 | [TOOL] | `migration-commit`: re-verify src/dst + atomic `consumed:true` before cleanup |

### MUST-NOT (physical layer)

| ID | Enforcement | Rule |
|----|------------|------|
| N-01 | [POLICY] | NEVER create/delete managed junctions outside pathmap |
| N-02 | [TOOL] | NEVER set `target_path` inside `[00_Workspace_Views]` (View-in-View forbidden) |
| N-03 | [TOOL] | NEVER use /MOVE in migration |
| N-04 | [POLICY] | NEVER create marker files inside junction or target folders |
| N-05 | [TOOL] | NEVER hardcode drive letters in Path_Map.json |
| N-06 | [ADVISORY] | NEVER include `[00_Workspace_Views]` in cloud sync scope |
| N-07 | [TOOL] | NEVER auto-apply/heal/repair without user confirmation |
| N-09 | [POLICY] | NEVER move/delete SSOT path referenced by active logical entry without `pathmap move` |

---

## 5. Current P:\ Implementation (portable env)

```
P:\                              ← SUBST root (portable drive)
├── README.md                    ← human entry point (keep at root)
├── CLAUDE.md / GEMINI.md / AGENTS.md / PROTOCOL.md / CONVENTION.md  ← AI tool configs (DO NOT MOVE)
├── workspace/                   ← default project folder ([01_User_Space] equivalent)
├── .claude/                     ← junction → _sys/claude/project/
├── .gemini/                     ← junction → _sys/gemini/project/
├── .ai/                         ← IPC state (hub.py managed — never write directly)
├── _archive/                    ← logs, sessions, reviews ([03_Archive_Media] equivalent)
├── _sys/                        ← system layer
│   ├── ai/                      ← cross-peer policy (shared state)
│   ├── core/                    ← hub.py, setup.py, relocation.py
│   ├── cli/                     ← entry wrappers + gate scripts
│   ├── checks/                  ← Axis validation scripts
│   ├── docs/                    ← SSOT documentation (this folder)
│   ├── docs-v2/                 ← reorganized MECE docs (THIS FOLDER)
│   ├── claude/                  ← cc peer config + health
│   ├── gemini/                  ← gc peer config + health
│   ├── codex/                   ← cx peer config + health
│   └── antigravity/             ← ag peer config + health (inactive)
├── Garbage/                     ← discarded files pending review
└── tmp/                         ← volatile temp ([04_Volatile_Temp] equivalent)
```

---

## 6. System Connectivity Map (condensed)

```
Root Docs (CLAUDE.md, GEMINI.md, etc.)
    ↓ loaded by AI tools at session start
_sys/ai/protocol.json            ← single runtime SSOT for all collab policy
    ↓ read by
_sys/core/hub.py                 ← orchestration engine
    ↓ manages
.ai/state.json + handoff.md      ← session state
_sys/{peer}/health.json          ← per-peer health
_sys/ai/runtime-directives.jsonl ← active behavioral corrections
    ↓ routes to
_sys/cli/{peer}*.bat/.py         ← peer entry points
    ↓ invokes
AI Peers: cc (Claude) · gc (Gemini) · cx (Codex) · ag (AntiGravity, inactive)
```

---

## 7. Key Design Decisions (from v2.6 debates)

- **Path_Map.json bootstrap**: stored at KNOWN fixed path, not dynamically discovered → avoids bootstrap paradox
- **Ghost junction guard**: pathmap status detects and reports `broken_link` state (N-09)
- **Cloud sync exclusion**: `[00_Workspace_Views]` must be excluded from OneDrive/Dropbox (`/XJ`)
- **Managed vs unmanaged junctions**: unmanaged junctions are reported by `pathmap prune` but NEVER auto-deleted
- **Snapshot before apply**: `pathmap apply` always snapshots current state before mutating

> Full spec: `_sys/docs/architecture/MECE_Directory_Architecture_Specification.md` (v2.6, 61KB)
> Implementation blueprint: `_sys/docs/plans/sys-restructure-plan.md`
