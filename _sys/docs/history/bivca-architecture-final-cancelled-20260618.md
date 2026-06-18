# BIVCA Architecture: The Absolute Masterpiece
> Status: LOCKED_FOR_IMPLEMENTATION
> Date: 2026-06-16 | Version: 2.0 (Post-Recursive MECE Audit)

## 1. Unified Directory Tree (Physical MECE)
This structure maps directly to the PARA methodology and BIVCA cognitive layers without overlap.

```text
_sys/
├── ai/
│   ├── knowledge/
│   │   ├── staging/                       # [SHORTHAND] Zero-token buffer (Concurrency safe)
│   │   │   └── LL-{peer}-{uuid}.json      
│   │   ├── active-lessons.critical.jsonl  # [CORTEX] Max 10 items (Hard Cap)
│   │   ├── active-lessons.general.jsonl   # [HIPPOCAMPUS] Decay applied (-0.05/day)
│   │   └── active-lessons.retired.jsonl   # [ARCHIVE] Weight < 0.2
│   ├── exocortex/
│   │   ├── entries/YYYY-MM-DD.jsonl       # [EXOCORTEX] Narrative history (Query only)
│   │   └── index.json                     # O(1) Tag/Keyword resolution
│   ├── runtime-alerts.jsonl               # [AMYGDALA] Reactive TTL alerts (Max 50)
│   └── runtime-rules.jsonl                # [CORTEX] Unanimous Invariants (SSOT)
│
└── docs-v2/                               # [RESOURCES] Human-decided Architecture
    ├── general/                           # Core cross-peer specs
    ├── specific/                          # Peer-specific specs
    ├── ops/                               # Operational protocols
    └── _exceptions/                       # [CLASSIFICATION DEBT] TTL 7 days
        └── EXC-{id}.json                  
```

---

## 2. Zero-Token Shorthand Specification
**Mechanism:** Peers output insights naturally in text. The Hub extracts them. No tool call overhead.

**Regex Pattern (Hub-side):**
```python
import re
LEARN_PATTERN = re.compile(r'\[LEARN:\s*(.+?)\]', re.DOTALL)
```

**JSON Schema (`staging/LL-{peer}-{id}.json`):**
```json
{
  "id": "LL-gc-a1b2",
  "content": "Windows SUBST drives require os.replace() instead of os.rename() for atomic writes.",
  "status": "proposed",
  "weight": 0.5,
  "trigger_count": 0,
  "domain_tags": ["filesystem", "windows", "atomic"],
  "ts": "2026-06-16T18:30:00"
}
```

---

## 3. Cognitive Processing Algorithms (hub.py)

### 3.1. Auto-Focus Inference (Closing the Feedback Loop)
If an alert is active, its tags automatically force the Hippocampus to inject relevant lessons, preventing 'Dead Ends'.

```python
def infer_focus_tags(ai_root: Path) -> set:
    alerts = load_active_alerts() # From Amygdala
    focus_tags = set()
    for alert in alerts:
        focus_tags.update(alert.get("domain_tags", []))
    return focus_tags
```

### 3.2. Context Builder with Hard Caps
```python
def compile_prompt_context(query_tags: set, inferred_tags: set):
    context = []
    
    # 1. Cortex Rules (Absolute)
    context.append(load_runtime_rules())
    
    # 2. Critical Lessons (Hard Cap: 10)
    critical_lessons = load_critical_lessons()
    critical_lessons.sort(key=lambda x: x['weight'], reverse=True)
    context.append(critical_lessons[:10]) # Strict slice
    
    # 3. General Lessons (Auto-Focused)
    general_lessons = load_general_lessons()
    active_tags = query_tags | inferred_tags
    focused_lessons = [l for l in general_lessons if set(l['domain_tags']) & active_tags]
    context.append(focused_lessons[:5]) # Soft Cap: 5
    
    return context
```

---

## 4. Exception Handling (MECE Isolation)
Any ambiguous architectural decision or documentation piece is forced here with a ticking clock.

**Schema (`docs-v2/_exceptions/EXC-{id}.json`):**
```json
{
  "id": "EXC-001",
  "title": "BIVCA and PARA mapping overlap",
  "description": "docs-v2 structure overlaps with AI knowledge areas.",
  "resolve_by": "2026-06-23T00:00:00", 
  "status": "pending_debate"
}
```
**Rule:** `hub.py saturation-scan` runs weekly. If `now() > resolve_by`, it triggers a Tier-0 Alert (blocking operations) until peers resolve the exception.

---

## 5. Exocortex Query Implementation (Action Spec)
**Action:** `action_exocortex_query`
- **Input:** `--tags`, `--since`
- **Output:** Max 3 summaries (to prevent context blowout).

```json
{
  "count": 1,
  "results": [
    {
      "id": "EX-20260616",
      "title": "LL-008 silent pass incident",
      "tags": ["testing", "silent_failure"],
      "summary": "Changed _lease_cfg tuple caused 26 silent passes. Fixed by DIR-003."
    }
  ]
}
```
*Full body is only retrieved if explicitly requested via `--fetch-id`.*