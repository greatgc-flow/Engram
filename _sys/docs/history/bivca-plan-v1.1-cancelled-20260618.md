# BIVCA Master Plan v1.1 — Detail Design (The End-game)
> Status: DESIGN_COMPLETE (Locked for Implementation)
> Date: 2026-06-16 | Version: 1.1

## 1. Physical Directory & Storage Structure (MECE)

All cognitive storage is strictly separated by access pattern and durability.

```
_sys/ai/
├── knowledge/
│   ├── general/
│   │   ├── active-lessons.critical.jsonl  # High weight, always injected (Cortex)
│   │   ├── active-lessons.general.jsonl   # Standard weight, task-filtered (Hippocampus)
│   │   └── active-lessons.retired.jsonl   # Weight < 0.2, audit only (Forgotten)
│   └── staging/                           # Staged Sidecar pattern (Concurrency)
│       └── LL-{peer_id}-{short_id}.json   # Individual peer proposals
├── runtime-alerts.jsonl                   # Reactive errors, TTL (Amygdala)
└── runtime-rules.jsonl                    # Normative invariants, ratified (Cortex SSOT)

.ai/sessions/{room_id}/
├── handoff.json                           # Working Memory (Always)
├── episodic.json                          # Long-term Memory (Selective)
└── attention.json                         # Attention State (MetaData driver)
```

---

## 2. Component Detail Specification

### 2.1. Amygdala: `runtime-alerts.jsonl`
- **Schema:** `{id, rule, trigger_reason, ts, expires, trigger_count, status: "active"|"resolved"}`
- **Auto-Compaction:** Hub `sweep` removes entries where `ts > expires` or `status == "resolved"`.
- **Constraint:** Max 50 active entries. Priority escalation if the same `rule` appears > 3 times in 1 hour.

### 2.2. Hippocampus: The Staged Write & Decay
- **Concurrency (Staged Sidecar):** Peers never write to `active-lessons.jsonl` directly. They write to `staging/`.
- **Decay Algorithm (The Forgetting Curve):**
    - Initial Weight: `0.5`
    - Trigger Bonus: `+0.1` per hit.
    - Decay Penalty: `-0.05` per 24 hours of non-use.
    - Transition: 
        - Weight > 0.8 → Move to `.critical.jsonl`
        - Weight < 0.2 → Move to `.retired.jsonl`
- **Sweep Logic:** Hub merges `staging/*.json` into `active-lessons.general.jsonl` every 10 mins.

### 2.3. PFC: Attention-Driven Context (`attention.json`)
- **Schema:**
  ```json
  {
    "active_focus": ["SECURITY", "PERFORMANCE"],
    "working_memory_sections": ["GOAL", "ACTIVE_THREADS"],
    "include_episodic": false,
    "last_checkpoint_hash": "abc123"
  }
  ```
- **Logic (`hub.py _build_context`):**
    1. Load `attention.json`.
    2. Inject `handoff.json` filtered by `working_memory_sections`.
    3. Inject `active-lessons.critical.jsonl`.
    4. IF `include_episodic` OR `query` matches `active_focus`: Inject `episodic.json` and `active-lessons.general.jsonl`.

---

## 3. Implementation Logic (Pseudo-code)

### 3.1. Atomic Staged Write (Peer Side)
```python
def propose_lesson(peer_id, content):
    lesson = {"id": f"LL-{now()}", "content": content, "status": "proposed", "weight": 0.5}
    path = AI_ROOT / "knowledge" / "staging" / f"LL-{peer_id}-{rand(4)}.json"
    _write_json_atomic(path, lesson)
```

### 3.2. Attention Filter (Hub Side)
```python
def compile_context(query, task_type):
    att = load_attention()
    lessons = load_critical_lessons() # Always
    if task_type in att["active_focus"]:
        lessons += load_general_lessons_filtered(task_type)
    
    # User Checklist Injection (The Focus Guide)
    checklist = load_focus_checklist(att["active_focus"])
    return render_block(lessons, checklist)
```

---

## 4. Immediate Consistency Cleanup (Consensus)
- **Action:** Delete `DIR-003` from `user-directives.md`.
- **Action:** Rename `LL-008` to `DIR-003` in `active-lessons.jsonl` to maintain the stable ID.
- **Action:** `docs-v2/00-MANIFEST.md` to point to `general/self-evolution.md` as the authority for BIVCA.

---

## 5. Transition Strategy: Build vs. Cut-over
- **Build:** Create directories, move files, initialize `attention.json`.
- **Logic Patch:** Update `hub.py` methods (`_load_active_lessons`, `_build_context`).
- **Validation:** 
    1. `pytest` all hub actions.
    2. Verify `staging/` merge.
    3. Verify Selective Injection (Task A shouldn't see Task B lessons).
