# Ops — JSON Schema Reference

> Status: ACTIVE v1.0 | Created: 2026-06-18
> Purpose: Data dictionary for all key JSON config files. Source of truth for field names, types, defaults, and ownership.
> Cross-ref: `general/resource-governance.md §11` (model-registry.json), `general/protocol.md` (protocol.json)

---

## 1. protocol.json

**Path:** `_sys/ai/protocol.json`
**Purpose:** Single runtime SSOT for collab_rate, routing, health thresholds, and consensus settings.
**Change requires:** R:10 unanimous consent (PRO-12)

### Key Fields

```jsonc
{
  "collab_rate": {
    "current": 10,               // 0–10: collaboration depth level (see general/tradeoffs.md)
    "override": null             // temporary per-session override
  },
  "health": {
    "failure_threshold": 5,      // consecutive failures before HALT (INV-15)
    "yellow_threshold": 2,       // failures before YELLOW state
    "ttl_green_hours": 4         // GREEN → stale after N hours without update
  },
  "consensus": {
    "r8_timeout_minutes": 15,    // fast-consensus window for R:8
    "r10_voters": ["cc","gc","cx"] // active voters for R:10 unanimous
  },
  "ipc": {
    "query_file_naming": "{peer_id}-{YYYYMMDDHHMMSS}-{RAND4}.txt",
    "timeout_seconds": 180
  },
  "active_constraints": {        // runtime flags (auto-updated by hub.py)
    "ipc_query_file_naming": "unique_per_call"
  }
}
```

---

## 2. peers.json

**Path:** `_sys/ai/peers.json`
**Purpose:** Peer capability registry — model mappings, sandbox levels, health gate config.
**Change requires:** R:5 (single `_sys/` file)

### Key Fields

```jsonc
{
  "peers": {
    "{peer_id}": {               // cc, gc, cx, ag
      "status": "active",        // active | inactive | deprecated
      "health_file": "_sys/{peer}/health.json",
      "model_profiles": {
        "standard":  {           // object form (P2 schema — see resource-governance.md §3.1)
          "model_id":          "...",
          "context_limit":     200000,
          "output_limit":      4096,
          "reasoning_budget":  0,
          "thinking":          false
        },
        "effort":    { ... },
        "deepthink": { ... }
      },
      "sandbox_levels": ["read-only","workspace-write","danger-full-access"],
      "capabilities": {
        "vision": false,
        "web_search": false,
        "tool_use": true,
        "file_write": true,
        "code_exec": false
      }
    }
  }
}
```

---

## 3. model-registry.json

**Path:** `_sys/ai/model-registry.json` (planned — not yet created)
**Purpose:** Measured model specs SSOT. Derived source for peers.json model_profiles.
**Change requires:** R:8 unanimous ACK (constitutional level — affects all routing decisions)

### Schema

```jsonc
{
  "_version": "1.0",
  "_last_validated": "2026-06-18",
  "models": {
    "{model_id}": {
      "provider":              "anthropic|google|openai",
      "context_limit":         1000000,
      "output_limit":          128000,
      "reasoning_type":        "adaptive|thinking_budget|reasoning_effort|none",
      "reasoning_params": {
        "effort":              ["low","medium","high","max"],  // cc
        "budget_range":        [0, 24576],                    // gc
        "effort_levels":       ["none","low","medium","high","xhigh"]  // cx
      },
      "temperature_supported": true,
      "vision":                true,
      "tool_use":              true,
      "pricing": {
        "input_per_1m":        3.00,   // USD
        "output_per_1m":       15.00
      },
      "status":                "GA",   // GA | Preview | EOL | Deprecated
      "validated_at":          "2026-06-18"
    }
  }
}
```

---

## 4. routing-config.json

**Path:** `_sys/ai/routing-config.json` (planned — not yet created)
**Purpose:** QUALITY_MODE setting, role→node weights, task-type overrides.
**Change requires:** R:3 for QUALITY_MODE; R:5 for routing weights

### Schema

```jsonc
{
  "quality_mode":          5,        // 0–10: Budget→Premium (see resource-governance.md §10)
  "quality_mode_override": null,     // per-session override
  "task_overrides": {
    "ESCALATION": 10,
    "FAST_QA":    0,
    "IMPLEMENT":  5
  },
  "routing_weights": {
    "{role_id}": {                   // R01~R12 (see resource-governance.md §7)
      "primary":  "{node_id}",       // cc::sonnet::adaptive:medium::none
      "fallback": "{node_id}",
      "weight":   1.0                // 0.0–2.0; adjusted by feedback loop
    }
  }
}
```

---

## 5. health.json

**Path:** `_sys/{peer}/health.json`
**Purpose:** Per-peer health state (zero-token read — no model calls needed).
**Change requires:** Only via `hub.py health-update` or `hub.py peer-recover` (INV-11)

### Schema

```jsonc
{
  "peer":             "cc",
  "status":           "GREEN",      // GREEN | YELLOW | RED
  "gate_open":        true,
  "consecutive_failures": 0,
  "last_updated":     "2026-06-18T10:30:00Z",
  "session_usage": {
    "failover_count": 0,
    "ask_count":      12,
    "error_count":    0
  }
}
```

---

## 6. runtime-directives.jsonl

**Path:** `_sys/ai/runtime-directives.jsonl`
**Purpose:** Active TTL-bound operational corrections auto-promoted from lessons.
**Change requires:** Auto-managed by hub.py (write only via `hub.py directive-add`)

### Entry Schema

```jsonc
{
  "id":         "RD-{YYYYMMDD}-{seq:03}",
  "source":     "LL-008",           // lesson ID or manual
  "text":       "...",              // the directive content (English only — INV-19)
  "scope":      ["cc","gc","cx"],   // which peers receive this
  "ttl_hours":  6,
  "created_at": "2026-06-18T10:00:00Z",
  "expires_at": "2026-06-18T16:00:00Z"
}
```

---

## 7. Schema Validation

All schemas listed here should be validated against their respective JSON files:
- `_sys/ai/collaboration_policy.schema.json` — validates collab policy structure
- Future: `check_docs_mece.py` will include schema drift detection (see ops/governance.md §6)

When a JSON file's actual structure diverges from this document → create proposal-add for schema update. Both the JSON and this doc update in the same commit (Doc-as-Code).
